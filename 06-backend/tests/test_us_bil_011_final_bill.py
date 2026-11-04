# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-011 (final bill: immediate at move-out, deposit auto-applies
#           FIRST, exactly one settlement path)   Screens: S20 · S30
# Rules:    BR-BIL-013 (the settlement matrix) · BR-CUS-056 (billed THROUGH the
#           move day) · BR-CUS-057 (deposit interest — customers' rule) ·
#           BR-BIL-004 (issued bills immutable) · CLAUDE.md rule 2 (Decimal)
# Golden:   GT-23 (= WE-7, ❄️ FROZEN 2026-08-08): deposit 150 held 14 mo @ 2%
#           simple → interest **3.50** → credit **153.50** applies FIRST;
#           Case A charges 142.30 → refund **11.20**; Case B charges 289.40 →
#           due **135.90**.
# ───────────────────────────────────────────────────────
"""WE-7 end to end, plus the two one-character mistakes it exists to catch.

The deposit arithmetic is three subtractions and there is no clever part, which
is exactly why it needs a test with the frozen numbers in it: `charges - credit`
written twice, or not written at all, produces a bill that foots, prints
plausibly, and is wrong in the customer's favour or the utility's by the price
of a deposit. Both mutations were executed against this file before it was
trusted — the verbatim failures are in the Lifecycle trailer.

The interest is NOT computed here or anywhere in billing (BR-CUS-057 belongs to
customers, US-CUS-023 §7, unbuilt). These tests publish a fake
`deposit_interest_accrued` seam carrying WE-7's 3.50, exactly as
`test_us_bil_002_gather.py` publishes fake seams for the modules whose lanes
have not landed — and `tc9` asserts what happens when nobody publishes it,
which is a refusal and never a principal-only credit.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import final_bill, models as billing_models, single
from apps.customers import models as customer_models, selectors as customer_selectors
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

# WE-7 verbatim.
DEPOSIT = Decimal("150.00")
INTEREST = Decimal("3.50")  # 150 x 2% x 14/12, computed by CUSTOMERS
CREDIT = Decimal("153.50")
CASE_A_CHARGES = Decimal("142.30")
CASE_A_REFUND = Decimal("11.20")
CASE_B_CHARGES = Decimal("289.40")
CASE_B_DUE = Decimal("135.90")
THRESHOLD = Decimal("5")  # BR-BIL-013 seeded default, tenant-config 0–50
MOVE_OUT = date(2026, 6, 12)


def a_credit(principal=DEPOSIT, interest=INTEREST, currency="USD"):
    return final_bill.DepositCredit(
        principal=principal, interest=interest, currency=currency, received_on=date(2025, 4, 1)
    )


def publish_interest(monkeypatch, amount=INTEREST):
    """Stand in for customers' accrual engine (BR-CUS-057 / US-CUS-023 §7).

    ⚠ **THAT ENGINE IS NO LONGER UNBUILT (CR-059 CS-20, 2026-09-03) AND THE
    STUB TAKES TWO ARGUMENTS NOW.** The published read is
    `deposit_interest_accrued(account_id, as_of)` — it states the day it
    accrues to, because BR-TEN-043 and gate G6 keep a clock out of a money
    path — so a stub written for the one-argument shape stops matching the
    contract, which is what a contract change is supposed to do to a stub.

    It is still STUBBED here rather than exercised, and the reason is the one
    this file already gives for every other seam: these cases are BILLING's
    settlement matrix, and the accrual's own arithmetic — ❄️ GT-61's **22.25**
    and WE-7's **3.50** — is asserted against the real engine in
    `test_cr059_cs20_deposit_interest.py`. `_as_of` is accepted and ignored for
    the same reason the amount is fixed: varying it here would test the engine
    twice and the settlement not at all.
    """
    monkeypatch.setattr(
        customer_selectors,
        final_bill.DEPOSIT_INTEREST_READ,
        lambda _account_id, _as_of=None: amount,
        raising=False,
    )


def publish_master(monkeypatch, master_id="ACC-9001"):
    """Stand in for the landlord-agreement link (OQ-069's prereq — no table)."""
    monkeypatch.setattr(
        customer_selectors,
        final_bill.MASTER_ACCOUNT_READ,
        lambda _unit_id: master_id,
        raising=False,
    )


def a_unit_read_before_the_move(actor, tenant, cycle, plan, *, asset_no, label, day):
    """A metered unit whose ONLY read falls inside the closing period.

    `a_billed_unit`'s read is dated the 28th, which a final period ending on
    the 12th correctly does not contain — a final bill reads the meter ON the
    move day (US-CUS-005's committed final reads), so the fixture does too.
    """
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services
    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    commit_read(
        actor,
        asset["id"],
        day=day.isoformat(),
        value="14100",
        prior_value="13800",
        consumption="300.000000",
        unit="kWh",
    )
    return unit


def an_account_with_deposit(tenant, unit_id, account_no, deposit=DEPOSIT, balance=Decimal("0")):
    """An account holding a deposit and, optionally, ARREARS.

    ⚠ **THE ARREARS ARE POSTED TO THE BOOKS, NOT WRITTEN TO THE COLUMN
    (DEF-127, 2026-08-16).** This fixture used to `.update(balance=...)` on
    `accounts.balance`, and that stopped being a way to give an account a debt
    on 2026-08-15: nothing in the product has ever written that column, so
    customers now serves the LEDGER's own position and a balance parked in the
    column is invisible — correctly. Seeding it that way would have made
    `tc12`'s arithmetic (PO 2026-08-12, *"everything outstanding"*) pass against
    a number no real account can ever carry.

    So a non-zero `balance` is posted as an OPENING AR debit through the real
    posting service (B2 r9 #3's `opening_balance` source, BR-CUS-049's cutover
    shape) — the same way a migrated customer's arrears actually arrive. The
    column is left at its default and is now simply unread.
    """
    account = an_account(tenant, unit_id, account_no)
    customer_models.Account.objects.filter(pk=account.pk).update(
        deposit_on_file=deposit, deposit_received_on=date(2025, 4, 1)
    )
    if balance:
        _post_opening_arrears(tenant, account, balance)
    return customer_models.Account.objects.get(pk=account.pk)


def _post_opening_arrears(tenant, account, amount):
    """DR AR / CR opening balance, for `amount`, dated before the period.

    The ONE way an account gets a prior balance in this product: through
    `apps.ledger.posting.post`, which is the sole writer (CLAUDE.md rule 5).
    Dated before `PERIOD_START` so it is genuinely PRIOR to the final bill.
    """
    from apps.ledger import models as ledger_models
    from apps.ledger import posting as ledger_posting

    def _gl(code, type_, name):
        row, _made = ledger_models.LedgerAccount.objects.get_or_create(
            tenant=tenant, code=code, defaults={"name": name, "type": type_}
        )
        return row

    ar = _gl("1200", "asset", "Accounts receivable")
    opening = _gl("3000", "equity", "Opening balance equity")
    source_id = uuid.uuid4()
    ledger_posting.post(
        ledger_posting.PostingRequest(
            posting_key=f"opening_balance|{account.account_no}|cutover",
            entry_date=date(2026, 5, 31),
            posted_at=datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc),
            currency="USD",
            source_type="opening_balance",
            source_id=source_id,
            memo="fixture — prior balance at cutover (BR-CUS-049)",
            lines=(
                ledger_posting.PostingLine(
                    ledger_account_id=ar.id,
                    side=ledger_models.SIDE_DEBIT,
                    amount=Decimal(amount),
                    source_type="opening_balance",
                    source_id=source_id,
                    account_id=account.id,
                ),
                ledger_posting.PostingLine(
                    ledger_account_id=opening.id,
                    side=ledger_models.SIDE_CREDIT,
                    amount=Decimal(amount),
                    source_type="opening_balance",
                    source_id=source_id,
                    account_id=account.id,
                ),
            ),
        )
    )


def test_us_bil_011_tc1__the_deposit_and_its_interest_are_read_and_applied_first(
    brazos, dana, monkeypatch
):
    """WE-7: 150.00 + 3.50 = **153.50**, and it applies BEFORE any path is chosen."""
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7401", label="A")
        account = an_account_with_deposit(brazos, unit["id"], "A-11001")
        publish_interest(monkeypatch)

        credit = final_bill.deposit_credit_for(account.id)

    assert credit.principal == DEPOSIT
    assert credit.interest == INTEREST
    assert credit.total == CREDIT  # the frozen figure
    assert credit.currency == "USD"  # rule 2 — money never travels alone


def test_us_bil_011_tc2__case_a_the_deposit_covers_the_bill_and_the_rest_refunds():
    """WE-7 Case A: 142.30 − 153.50 = **−11.20** → path REFUND, automatically.

    Nobody chooses whether to give back money that is not theirs, so the path
    is not offered as a choice — `available` is the single automatic answer.
    """
    settlement = final_bill.settle(
        charges=CASE_A_CHARGES,
        deposit=a_credit(),
        write_off_threshold=THRESHOLD,
        currency="USD",
    )

    assert settlement.remainder == -CASE_A_REFUND
    assert settlement.refund_amount == CASE_A_REFUND  # 11.20
    assert settlement.amount_due == 0
    assert settlement.path == final_bill.PATH_REFUND
    assert settlement.automatic is True
    assert settlement.settled is True


def test_us_bil_011_tc3__case_b_leaves_135_90_and_exactly_one_path_may_be_picked():
    """WE-7 Case B: 289.40 − 153.50 = **135.90** → collect / payment plan.

    Write-off is ABSENT from `available`, not merely discouraged — 135.90 is
    far above the $5 threshold, which is US-BIL-011 TC-3's "write-off greyed".
    Transfer is absent too, because no unit here is landlord-linked.
    """
    settlement = final_bill.settle(
        charges=CASE_B_CHARGES,
        deposit=a_credit(),
        write_off_threshold=THRESHOLD,
        currency="USD",
    )

    assert settlement.remainder == CASE_B_DUE  # 135.90
    assert settlement.amount_due == CASE_B_DUE
    assert settlement.refund_amount == 0
    assert settlement.path is None  # awaiting the staff choice
    assert settlement.settled is False
    assert settlement.available == (final_bill.PATH_COLLECT, final_bill.PATH_PAYMENT_PLAN)
    assert final_bill.PATH_WRITE_OFF not in settlement.available
    assert final_bill.PATH_TRANSFER not in settlement.available

    chosen = final_bill.settle(
        charges=CASE_B_CHARGES,
        deposit=a_credit(),
        write_off_threshold=THRESHOLD,
        currency="USD",
        chosen=final_bill.PATH_COLLECT,
    )
    assert chosen.path == final_bill.PATH_COLLECT
    assert chosen.settled is True


def test_us_bil_011_tc4__transfer_exists_only_on_a_landlord_linked_unit(brazos, dana, monkeypatch):
    """TC-4: the transfer path appears only when the unit IS linked, and the
    target is the LINK's master account — never a caller's argument.

    Today no landlord-agreement link exists in this repository at all (OQ-069's
    prereq), so the first half asserts the honest default: the option is absent
    and says why. The second half publishes the link's seam and shows the path
    appearing with the master account the SEAM named.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7402", label="B")
        account = an_account_with_deposit(brazos, unit["id"], "A-11004")
        publish_interest(monkeypatch)

        unlinked = final_bill.settle_account(
            account_id=account.id,
            unit_id=unit["id"],
            charges=CASE_B_CHARGES,
            currency="USD",
        )
        assert final_bill.PATH_TRANSFER not in unlinked.available
        assert "landlord-agreement link" in unlinked.transfer_unavailable
        assert unlinked.write_off_threshold == THRESHOLD  # read from S71, not a constant

        publish_master(monkeypatch)
        linked = final_bill.settle_account(
            account_id=account.id,
            unit_id=unit["id"],
            charges=CASE_B_CHARGES,
            currency="USD",
            chosen=final_bill.PATH_TRANSFER,
        )

    assert linked.path == final_bill.PATH_TRANSFER
    assert linked.master_account_id == "ACC-9001"  # from the seam, not the caller
    assert linked.remainder == CASE_B_DUE  # the deposit still applied FIRST


def test_us_bil_011_tc5__a_remainder_inside_the_threshold_writes_off_either_way():
    """TC-5: |3.20| ≤ $5 → automatic write-off, in BOTH directions (BR-BIL-013).

    Tested before the refund branch on purpose: a $3.20 overpayment is a
    write-off, not a refund. Issuing a cheque for it costs more than it returns
    and leaves a closed account with an open refund nobody chases.
    """
    for charges, expected in (
        (CREDIT + Decimal("3.20"), Decimal("3.20")),  # customer still owes 3.20
        (CREDIT - Decimal("3.20"), Decimal("-3.20")),  # customer is owed 3.20
    ):
        settlement = final_bill.settle(
            charges=charges,
            deposit=a_credit(),
            write_off_threshold=THRESHOLD,
            currency="USD",
        )
        assert settlement.remainder == expected
        assert settlement.path == final_bill.PATH_WRITE_OFF
        assert settlement.automatic is True
        assert settlement.settled is True


def test_us_bil_011_tc6__two_paths_cannot_be_taken_and_a_transfer_cannot_be_forged():
    """TC-6 (negative), both halves.

    "Two settlement paths attempted" is not rejected by a validation — it is
    UNREPRESENTABLE, because `settle` takes one `chosen`. What CAN be attempted
    is a choice that contradicts the automatic outcome, or a transfer on a unit
    with no master account, and both refuse by name.
    """
    with pytest.raises(Exception) as clash:
        final_bill.settle(
            charges=CASE_A_CHARGES,  # settles automatically as a refund
            deposit=a_credit(),
            write_off_threshold=THRESHOLD,
            currency="USD",
            chosen=final_bill.PATH_COLLECT,
        )
    assert clash.value.reason == final_bill.FINAL_PATH_UNAVAILABLE
    assert "exactly ONE settlement path" in str(clash.value)

    with pytest.raises(Exception) as forged:
        final_bill.settle(
            charges=CASE_B_CHARGES,
            deposit=a_credit(),
            write_off_threshold=THRESHOLD,
            currency="USD",
            chosen=final_bill.PATH_TRANSFER,  # no master account was resolved
        )
    assert forged.value.reason == final_bill.FINAL_PATH_UNAVAILABLE

    with pytest.raises(Exception) as greyed:
        final_bill.settle(
            charges=CASE_B_CHARGES,
            deposit=a_credit(),
            write_off_threshold=THRESHOLD,
            currency="USD",
            chosen=final_bill.PATH_WRITE_OFF,  # 135.90 is above the threshold
        )
    assert "above the tenant's write-off threshold" in str(greyed.value)


def test_us_bil_011_tc7__a_final_settlement_never_reads_another_tenant_s_account(
    brazos, dana, lonestar, monkeypatch
):
    """TC-7 (isolation): the deposit position is unreachable from another tenant.

    Cross-tenant, unknown and malformed ids are ONE answer (HR-1), so a closing
    balance cannot be probed. The RLS-level proof is the isolation suite's;
    this is the queryset scoping every read in the path goes through.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7403", label="C")
        account = an_account_with_deposit(brazos, unit["id"], "A-11007")
        publish_interest(monkeypatch)

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as raised:
            final_bill.deposit_credit_for(account.id)
    assert raised.value.__class__.__name__ == "NotFoundError"


def test_us_bil_011_tc8__the_final_bill_is_billed_through_the_move_day(brazos, dana, monkeypatch):
    """BR-CUS-056: the OUTGOING account pays the move day — `period_end` IS it.

    The off-by-one this pins down is the one the customers handoff went out of
    its way to state (`bill_through: <move day>`, `bill_through_br_ref:
    BR-CUS-056`): billing to the day BEFORE the move loses a day of revenue on
    every move-out, and billing past it charges a customer for a home they had
    left — the incoming tenant is billed from the next day, from the same read.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_unit_read_before_the_move(
            dana, brazos, a_cycle(brazos), plan, asset_no="M-7404", label="D", day=MOVE_OUT
        )
        account = an_account_with_deposit(brazos, unit["id"], "A-11008")
        publish_interest(monkeypatch)

        data = final_bill.prepare_final_bill(
            account_id=account.id,
            period_start=PERIOD_START,
            moved_out_on=MOVE_OUT,
            cycle_days=(PERIOD_END - PERIOD_START).days + 1,
        )
        assert data.period_end == MOVE_OUT  # THROUGH, not up to
        assert data.service_days == 12  # Jun 1..Jun 12 inclusive
        assert data.cycle_days == 30  # the CYCLE's length, not the stub period's

        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-F"),
            period_start=PERIOD_START,
            period_end=MOVE_OUT,
            idempotency_key="final-1",
        )
        invoice = final_bill.calculate_final_bill(data, bill_run=run)

    assert invoice.bill_type == "final"
    assert invoice.period_end == MOVE_OUT
    assert invoice.status == billing_models.INVOICE_DRAFT  # issue is a separate act


def test_us_bil_011_tc9__an_unaccrued_deposit_refuses_rather_than_crediting_principal_only(
    brazos, dana
):
    """The refusal that protects the customer's own money.

    With customers' accrual engine unbuilt, `deposit_on_file` alone is
    available and irresistible. Using it would credit 150.00 where WE-7 says
    153.50 — the customer is **$3.50** short, the bill foots, the account
    closes, and nobody looks again. GT-61's 89-month deposit would be **$22.25**
    short. So the settlement stops.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7405", label="E")
        account = an_account_with_deposit(brazos, unit["id"], "A-11009")

        with pytest.raises(Exception) as raised:
            final_bill.deposit_credit_for(account.id)

    assert raised.value.reason == final_bill.FINAL_DEPOSIT_INTEREST_UNAVAILABLE
    assert "BR-CUS-057" in str(raised.value)
    assert "principal-only" in str(raised.value)


def test_us_bil_011_tc10__an_account_with_no_deposit_settles_without_the_accrual_seam(brazos, dana):
    """A zero deposit accrues zero interest — that is arithmetic, not a guess.

    Blocking every deposit-less final bill on an unbuilt engine would be a
    refusal with no rule behind it, so `deposit_credit_for` answers zero and
    the settlement proceeds on the charges alone.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7406", label="F")
        account = an_account_with_deposit(brazos, unit["id"], "A-11010", deposit=Decimal("0"))

        credit = final_bill.deposit_credit_for(account.id)
        settlement = final_bill.settle_account(
            account_id=account.id,
            unit_id=unit["id"],
            charges=CASE_B_CHARGES,
            currency="USD",
            chosen=final_bill.PATH_COLLECT,
        )

    assert credit.exists is False
    assert credit.total == 0
    assert settlement.remainder == CASE_B_CHARGES  # nothing applied, nothing invented
    assert settlement.path == final_bill.PATH_COLLECT


def test_us_bil_011_tc11__the_deposit_settles_once_on_the_final_bill_only(brazos, dana):
    """BR-BIL-013 settles the deposit ONCE, on the FINAL bill.

    Applying it to an ordinary cycle bill would credit the customer their
    deposit every month — the loudest possible version of the double-apply
    mistake, and the one a type check can catch.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-7407", label="G")
        account = an_account_with_deposit(brazos, unit["id"], "A-11011")
        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=PERIOD_END,
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-G"),
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="cycle-not-final",
        )
        cycle_bill = single.calculate_single_bill(prepared, bill_run=run)

        with pytest.raises(Exception) as raised:
            final_bill.settle_final_bill(cycle_bill)

    assert "not 'final'" in str(raised.value)


def test_us_bil_011_tc12__the_deposit_settles_the_whole_closing_position(brazos, dana, monkeypatch):
    """**PO ruling 2026-08-12, verbatim: _"everything outstanding"_ — OQ-158
    CLOSED.**

    Found in the first place by diffing this flow against the prototype
    (hard-won law 6). The prototype's move-out step 3 settles a *Final amount
    due* of **184.20** that INCLUDES a **120.84** prior balance; WE-7 settles
    final CHARGES alone. Both are ours and they differ by every dollar of
    arrears — under the bill-only reading the product posts a refund to a
    customer who is in debt to it, on an account that has just closed.

    This test asserted the REFUSAL until the ruling landed. It now asserts that
    the **120.84** is inside the settled base, which is the whole difference.

    ❄️ A clean closure (WE-7's shape, every test above) is untouched and that is
    checkable rather than claimed: with no arrears the two readings produce the
    identical figure, which is why the frozen example never disambiguated them.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_unit_read_before_the_move(
            dana,
            brazos,
            a_cycle(brazos, code="06-H"),
            plan,
            asset_no="M-7408",
            label="H",
            day=MOVE_OUT,
        )
        account = an_account_with_deposit(brazos, unit["id"], "A-11012", balance=Decimal("120.84"))
        publish_interest(monkeypatch)

        data = final_bill.prepare_final_bill(
            account_id=account.id, period_start=PERIOD_START, moved_out_on=MOVE_OUT
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-I"),
            period_start=PERIOD_START,
            period_end=MOVE_OUT,
            idempotency_key="final-arrears",
        )
        invoice = final_bill.calculate_final_bill(data, bill_run=run)

        settlement = final_bill.settle_final_bill(invoice)

    # The settled base is the final CHARGES plus everything already outstanding.
    assert settlement.charges == invoice.total + Decimal("120.84"), (
        "the deposit must settle the whole closing position (PO 2026-08-12) — "
        "settling the bill alone refunds a customer who still owes 120.84"
    )


def test_us_bil_011_tc12b__a_closing_balance_the_books_cannot_state_refuses(
    brazos, dana, monkeypatch
):
    """DEF-127 — the same defect, one step further on, in a WRITE path.

    Since 2026-08-15 the closing balance is the ledger's own position, so it can
    be **null**: on a deployment where the per-account read is unpublished, or a
    tenant that has designated no AR account, the books cannot say what this
    customer owes. `_money` answers `Decimal("0")` for a None, which was
    harmless while the value came from a NOT NULL column.

    It is not harmless now. Under the PO's ruling of 2026-08-12 (*"everything
    outstanding"*, OQ-158) the prior balance is INSIDE the settled base, so a
    zero read there **refunds the deposit of a customer who is in debt** — on an
    account that has just closed and that nobody will open again. Exactly what
    DEF-127 did on a screen, done instead with money.

    So it refuses, and the refusal names the account. Proved by unwiring the
    ledger read the way a partial deployment leaves it — the same simulation
    `tests/test_def_127_one_account_one_figure.py::…tc5` uses.
    """
    from apps.customers import seams as customers_seams

    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_unit_read_before_the_move(
            dana,
            brazos,
            a_cycle(brazos, code="06-J"),
            plan,
            asset_no="M-7409",
            label="J",
            day=MOVE_OUT,
        )
        account = an_account_with_deposit(brazos, unit["id"], "A-11013", balance=Decimal("120.84"))
        publish_interest(monkeypatch)

        data = final_bill.prepare_final_bill(
            account_id=account.id, period_start=PERIOD_START, moved_out_on=MOVE_OUT
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-K"),
            period_start=PERIOD_START,
            period_end=MOVE_OUT,
            idempotency_key="final-unreadable",
        )
        invoice = final_bill.calculate_final_bill(data, bill_run=run)

        original = customers_seams.resolve
        monkeypatch.setattr(
            customers_seams,
            "resolve",
            lambda module, attribute, kind="services": (
                None
                if attribute == customers_seams.AR_POSITIONS_READ
                else original(module, attribute, kind)
            ),
        )
        with pytest.raises(Exception) as raised:
            final_bill.settle_final_bill(invoice)

    assert "could not be read from the books" in str(raised.value)
    assert "refunds the deposit" in str(raised.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-011@f0a3c21 (EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md · B2 §2 + Addendum r10)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane)
# gates: ruff✔ black✔ · 12 passed
# RED PROOFS EXECUTED 2026-08-11 (verbatim output, not predicted) — the two
#         mistakes named in `final_bill.py`'s docstring, each applied to
#         `settle()` and each reverted:
#         (1) DEPOSIT APPLIED TWICE — `remainder = charges - deposit.total` →
#             `charges - deposit.total - deposit.total`. Result:
#             `5 failed, 6 passed in 21.01s`.
#             FAILED tc2 — `assert Decimal('-164.70') == -Decimal('11.20')`
#             FAILED tc3 — `assert Decimal('-17.60') == Decimal('135.90')`:
#             Case B's customer, who owes **135.90**, is handed a **17.60**
#             refund instead, and the bill settles itself as a REFUND with no
#             human ever choosing a path.
#             FAILED tc4, tc5 (`assert Decimal('-150.30') == Decimal('3.20')`),
#             tc6.
#         (3) THE ARREARS GUARD REMOVED — `if prior_balance:` → `if False:`,
#             so a closing account with $120.84 of arrears would settle on its
#             bill alone and refund a customer who still owes. Result:
#             `1 failed, 11 passed in 23.16s` — FAILED tc12
#             `Failed: DID NOT RAISE NotImplementedError`. Reverted; 12 passed.
#         (2) DEPOSIT NOT APPLIED — `remainder = charges`. Result:
#             `5 failed, 6 passed in 20.70s`.
#             FAILED tc2 — `assert Decimal('142.30') == -Decimal('11.20')`: the
#             customer is billed **142.30** and their **153.50** deposit stays
#             with the utility on an account nobody will look at again.
#             FAILED tc3 / tc4 — `assert Decimal('289.40') == Decimal('135.90')`
#             FAILED tc5, tc6.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
