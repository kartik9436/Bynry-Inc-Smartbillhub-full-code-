# ── Trace ──────────────────────────────────────────────
# Defects: DEF-177 (the deposit register is never written — payments credits
#          the 2300 liability on every cleared deposit and NOTHING writes
#          `accounts.deposit_on_file`) · DEF-1713 (its exact MIRROR — a
#          migrated deposit writes the register and posts nothing, so the
#          seeded estate carried a register of $750.00 against a 2300 GL of
#          $0.00).  Screens: S36 (the tie-out panel)
# Rules:   BR-CUS-670 (NEW — the register moves with the money, in both
#          directions) · BR-CUS-671 (NEW — a migrated deposit posts an opening
#          entry, DR opening clearing / CR deposit liability, dated at cutover)
#          · BR-LED-007 (deposit-liability GL = Σ deposits held; ANY drift =
#          red flag + release blocker) · BR-CUS-049 (opening balances post as
#          balanced opening JEs, dated at cutover, immutable) · BR-CUS-050
#          (the ORIGINAL receipt date) · BR-CUS-025 (a deposit is a LIABILITY)
#          · CLAUDE.md hard rule 2 (money, 4 dp) · rule 4 (immutability) ·
#          rule 5 (balanced pairs, posting service only) · rule 6 (idempotency)
# Golden:  none moved.  golden-verify stayed 33 PASS / 0 FAIL across this work
#          and this file pins no ❄️ FROZEN figure — GT-16's batch tie-out is Σ
#          AR debits = Σ imported BUCKETS and the deposit batch is deliberately
#          kept out of that sum.
# Tests:   this file
# Impacts: apps/ledger/opening_balances (the composer) · apps/customers/
#          import_writer · apps/customers/services.record_deposit_movement ·
#          apps/payments/services · apps/payments/reversal · apps/ledger/tie_out
# ───────────────────────────────────────────────────────
"""**Does the deposit register equal the deposit liability?** — asked both ways.

WHY THIS FILE EXISTS
--------------------
Two open high-severity defects that are exact mirrors of each other, and one
job: money taken as a deposit reached the books and not the register; money
migrated in reached the register and not the books.

    DEF-177   payments credits 2300 · nothing writes `accounts.deposit_on_file`
    DEF-1713  `create_from_import` writes `accounts.deposit_on_file` · nothing posts

**And in BOTH directions the books still footed.** Every journal entry balanced;
the entry was simply never made on one side. That is the shape of this whole
class — a subledger and its control account written by DIFFERENT PATHS — and the
only check that can see it is the tie-out, which is why every case below asserts
through `apps.ledger.tie_out` rather than through a private sum.

WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT
------------------------------------------------
No demo figure is pinned.  $750.00 is the seeded estate's total today and it is
not a signed number; the guard that watches it lives in
`test_cr040_seeded_books_tie_out.py`, on the estate itself.  What is pinned here
is the PROPERTY, on figures this file states: after money moves, the two sides
are EQUAL and both are NON-ZERO — because `agreed` at 0.00 against 0.00 is a row
that agreed with itself about nothing.

RED-FIRST RECORD (hard-won law 7) — every mutation was RUN, in this worktree,
and the verbatim failure is quoted in the lane report:

1. the register write removed from `_hold_and_post` → DEF-177 restored, and this
   file failed `deposit_liability DRIFTING: GL 150.000000 register 0.000000`;
2. `deposits=` dropped from the sample seeder's handoff → DEF-1713 restored, and
   the seeded-estate guard failed at `register 750.00 / GL 0.00`;
3. the release in `reversal` made unconditional on NSF only → a voided deposit
   left the books and stayed in the register;
4. the deposit entry keyed with `cutover_event` instead of
   `cutover_deposit_event` → the deposit posting became a REPLAY of the account's
   AR opening entry and silently posted nothing, which is DEF-1713 with a guard
   on top;
5. the migrated deposit dated at its RECEIPT date instead of the cutover →
   2024-02-05 in a book that opens on the cutover day.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.customers import import_writer
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.ledger import chart, models as ledger_models, opening_balances, selectors, tie_out
from apps.payments import models as payment_models, reversal, services as payment_services

from tests.ledger_le_fixtures import make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: PE-6's deposit, the figure US-PAY-002 §4 states and the one DEF-177 was filed
#: with (*"books $150.00 / register $0.00"*).  Used as INPUT, never derived.
A_DEPOSIT = Decimal("150.00")

#: A migrated deposit and its ORIGINAL receipt date — the seeded estate's own
#: `A-12048 · Kwan, Michael` shape (`core/sample_fixture.py`), where the receipt
#: date is more than two years before the cutover.  That gap is the whole reason
#: BR-CUS-050 exists and the reason the entry date is NOT the receipt date.
A_MIGRATED_DEPOSIT = Decimal("150.00")
A_RECEIPT_DATE = date(2024, 2, 5)
A_CUTOVER = date(2026, 8, 31)
IMPORTED_AT = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
BATCH_ID = "0192f0aa-0000-7000-8000-0000000d1713"


# ── helpers ────────────────────────────────────────────────────────────────
def _deposit_row(*, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)):
    """The product's OWN tie-out row for the deposit subledger.

    Read through `tie_out.tie_outs` and never through a private sum: BR-LED-007
    is the rule under test, the S36 panel is what a finance officer looks at,
    and a test that computed its own comparison could pass over a panel that
    still showed a drift.
    """
    result = tie_out.tie_outs(period_start=period_start, period_end=period_end)
    return {row.subledger: row for row in result["rows"]}[tie_out.SUBLEDGER_DEPOSITS]


def _register_total() -> Decimal:
    """Σ `accounts.deposit_on_file` — the register side, tenant-scoped."""
    total = ZERO
    for held in customer_models.Account.objects.values_list("deposit_on_file", flat=True):
        total += held or ZERO
    return total


def _a_plan(tenant, service_code="electric"):
    """A published plan the unit can sit on.

    BR-MET-040 blocks account activation on a unit with no plan, and a migrated
    account is ACTIVE from day one — so this is a precondition of the case under
    test rather than part of it.  Plan CONTENT is EP-RAT-01's story; all that is
    asked here is that `units.rate_plan_id` is non-null (the shape
    `test_br_cus_068_master_accounts._plan` already uses).
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="Cutover Residential", defaults={"code": "cut-res", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"Cutover — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _a_unit(dana, tenant, label="1A", address="14 Cutover Row", service="electric"):
    from apps.metering import services as metering_services

    premises = make_premises(dana, address_line=address, services_available=[service])
    unit = make_unit(dana, premises["id"], label=label, services=[service])
    metering_services.assign_unit_plan(
        dana, unit["id"], {"tariff_id": str(_a_plan(tenant, service).id)}
    )
    return unit


def _migrate_an_account(
    dana, tenant, *, account_no, held, received_on=A_RECEIPT_DATE, batch=BATCH_ID
):
    """One migrated account carrying a deposit, through the REAL import door.

    `create_from_import` is the only path that accepts `deposit_on_file` with its
    original receipt date (`IMPORT_ACCOUNT_FIELDS`, US-CUS-023), and
    `post_opening_batch_from_import` is the ONE handoff that reaches the ledger.
    Neither is bypassed here: the defect was that these two were not connected,
    so a test that composed the ledger request by hand would prove the contract
    and miss the wiring (hard-won law 2).
    """
    unit = _a_unit(dana, tenant, label=account_no, address=f"{account_no} Cutover Row")
    result = customer_services.create_from_import(
        actor=dana,
        payload={
            "mapped": {"customer_name": "Kwan, Michael", "customer_ref": f"CUS-{account_no}"},
            "unit_id": unit["id"],
            "account_no": account_no,
            "currency": "USD",
            "cutover_on": A_CUTOVER,
            "account": {
                "account_type": "residential",
                "status": "active",
                "opened_at": "2024-01-01",
                "deposit_on_file": str(held),
                "deposit_received_on": received_on.isoformat(),
            },
        },
    )
    posting = import_writer.post_opening_batch_from_import(
        actor=dana,
        batch_id=batch,
        cutover_on=A_CUTOVER,
        imported_at=IMPORTED_AT,
        currency="USD",
        accounts=[],
        deposits=[
            {
                "account_id": result["id"],
                "account_ref": result["account_no"],
                "held": Decimal(result["deposit_on_file"]),
                "received_on": result["deposit_received_on"],
            }
        ],
    )
    return result, posting


# ═══════════════════════════════════════════════════════════════════════════
# DEF-177 — money TAKEN as a deposit reaches the register as well as the books
# ═══════════════════════════════════════════════════════════════════════════
def test_def177__a_cleared_deposit_lands_in_the_register_and_in_the_books(brazos, dana):
    """A $150.00 deposit clears: 2300 rises by 150.00 and so does the register.

    DEF-177's own words were *"books $150.00 / register $0.00"*.  Both figures
    are asserted, and so is the tie-out's verdict — because BR-LED-007 makes a
    drift a RELEASE BLOCKER, and the thing a utility actually experiences is the
    red panel rather than the column.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        before = _deposit_row()
        assert before.gl == ZERO and before.register == ZERO

        recorded = payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=A_DEPOSIT,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        assert recorded.created is True
        # Stated as a VALUE on the result, so a caller can assert the move
        # happened rather than trust a docstring (hard-won law 1).
        assert recorded.deposit_held_after == A_DEPOSIT

        row = _deposit_row()

    assert row.gl == A_DEPOSIT, f"the 2300 deposit liability reads {row.gl}, not {A_DEPOSIT}"
    assert row.register == A_DEPOSIT, (
        f"the customer deposit register reads {row.register}, not {A_DEPOSIT} — DEF-177"
    )
    assert row.drift == ZERO
    assert row.state == tie_out.STATE_AGREED
    # NON-VACUITY: `agreed` over 0.00 against 0.00 agreed with itself about
    # nothing.  This row must be agreeing about real money.
    assert row.gl != ZERO


def test_def177__the_receipt_date_is_stamped_from_the_clearing_date_and_only_once(brazos, dana):
    """BR-CUS-050 — a second deposit must not restart the interest clock.

    BR-CUS-057 accrues from `deposit_received_on`, so re-stamping it on every
    later top-up would quietly under-pay the customer who has held a deposit
    longest.  Both halves are asserted: the first deposit stamps the date, the
    second moves the money and leaves the date alone.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=A_DEPOSIT,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        account.refresh_from_db()
        first_stamp = account.deposit_received_on
        assert first_stamp == POSTED_AT.date()

        later = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
        payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("25.00"),
            posted_at=later,
            cleared_at=later,
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        account.refresh_from_db()
        row = _deposit_row()

    assert account.deposit_on_file == Decimal("175.00")
    assert account.deposit_received_on == first_stamp, (
        "a later deposit re-stamped the ORIGINAL receipt date — BR-CUS-050/057 accrue "
        "interest from it, so this under-pays the longest-standing customers"
    )
    assert row.gl == row.register == Decimal("175.00")


def test_def177__a_reversed_deposit_leaves_the_register_as_well_as_the_books(brazos, dana):
    """The drift must not be able to come back one bounced cheque at a time.

    `posting.reverse_entry` mirrors the deposit entry, so the 2300 liability
    falls.  A register that did not fall with it would re-open DEF-177 from the
    other side — on a book that still foots perfectly, which is the state
    nothing but the tie-out can see.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        recorded = payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=A_DEPOSIT,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        assert _deposit_row().register == A_DEPOSIT

        reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            reason=payment_models.REVERSAL_REASON_NSF,
            returned_on=datetime(2026, 8, 20, 9, 0, tzinfo=UTC),
        )
        account.refresh_from_db()
        row = _deposit_row()

    assert account.deposit_on_file == ZERO
    assert row.gl == ZERO and row.register == ZERO
    assert row.state == tie_out.STATE_AGREED


def test_def177__a_release_bigger_than_what_is_held_is_refused_not_clamped(brazos, dana):
    """Clamping to zero would CREATE the drift this rule exists to prevent.

    The ledger reversal takes the FULL amount out of 2300; a register clamped at
    0.00 would then differ from the books by exactly the excess, and the clamp
    is the kind of "safe" default that reads as tidy and is a money error.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        customer_services.record_deposit_movement(account.pk, A_DEPOSIT, actor=dana)
        with pytest.raises(customer_services.DepositRegisterError) as excinfo:
            customer_services.record_deposit_movement(
                account.pk, Decimal("200.00"), actor=dana, released=True
            )
        account.refresh_from_db()

    # Both figures are in the refusal, so a reader can act on it.
    assert "150" in str(excinfo.value) and "200" in str(excinfo.value)
    assert account.deposit_on_file == A_DEPOSIT


# ═══════════════════════════════════════════════════════════════════════════
# DEF-1713 — money MIGRATED in reaches the books as well as the register
# ═══════════════════════════════════════════════════════════════════════════
def test_def1713__a_migrated_deposit_reaches_the_balance_sheet(brazos, dana):
    """The mirror: the register held it and the balance sheet had never heard.

    Asserted through the tie-out, and asserted on BOTH sides at a NON-ZERO
    figure, because the failure this replaces was a register of 750.00 against a
    GL of 0.00 on a book where every entry balanced.
    """
    with tenant_ctx(brazos):
        result, posting = _migrate_an_account(dana, brazos, account_no="A-12048", held=A_MIGRATED_DEPOSIT)
        assert posting is not None
        assert posting["deposits_posted"] == 1
        assert Decimal(posting["deposit_credits"]) == A_MIGRATED_DEPOSIT

        row = _deposit_row()
        register = _register_total()

    assert Decimal(result["deposit_on_file"]) == A_MIGRATED_DEPOSIT
    assert register == A_MIGRATED_DEPOSIT
    assert row.gl == A_MIGRATED_DEPOSIT, (
        f"the 2300 deposit liability reads {row.gl} against a register of {register} — DEF-1713"
    )
    assert row.register == A_MIGRATED_DEPOSIT
    assert row.drift == ZERO
    assert row.state == tie_out.STATE_AGREED


def test_def1713__the_entry_is_dated_at_cutover_and_the_receipt_date_is_kept(brazos, dana):
    """BR-CUS-049 dates it at cutover; BR-CUS-050 keeps the true receipt date.

    They answer different questions and collapsing them either way loses one:
    book at the receipt date and a 2024 liability lands in a book that opens in
    2026; accrue from the cutover and BR-CUS-057 under-pays by two and a half
    years.  Both are asserted on the same migrated row.
    """
    with tenant_ctx(brazos):
        result, _ = _migrate_an_account(dana, brazos, account_no="A-12048", held=A_MIGRATED_DEPOSIT)
        account = customer_models.Account.objects.get(pk=result["id"])
        liability_id = selectors.gl_account_id_for_designation(chart.DEPOSIT_LIABILITY)
        clearing_id = selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
        lines = list(
            ledger_models.JournalLine.objects.filter(
                ledger_account_id__in=[liability_id, clearing_id],
                account_id=account.id,
            ).select_related("journal_entry")
        )

    assert account.deposit_received_on == A_RECEIPT_DATE
    assert len(lines) == 2, "a migrated deposit is ONE balanced pair, not more and not fewer"
    for line in lines:
        assert line.journal_entry.entry_date == A_CUTOVER, (
            f"the migrated deposit booked on {line.journal_entry.entry_date}; BR-CUS-049 dates "
            "an opening entry AT CUTOVER, and the receipt date is often years earlier"
        )
        assert line.amount == A_MIGRATED_DEPOSIT
    sides = {str(line.ledger_account_id): line.side for line in lines}
    # BR-CUS-025 — a deposit is a LIABILITY, so 2300 is the CREDIT.  The debit
    # is the opening clearing account: no cash was received today.
    assert sides[str(liability_id)] == ledger_models.SIDE_CREDIT
    assert sides[str(clearing_id)] == ledger_models.SIDE_DEBIT


def test_def1713__re_running_the_same_migration_does_not_double_the_liability(brazos, dana):
    """CLAUDE.md hard rule 6 — and the classic way a tie-out fix creates a fault.

    A resumed or re-run import must post the deposit ONCE.  It is keyed per
    (batch, account) exactly as the AR opening entry is, so the second run finds
    its own entry and writes nothing; a posted entry cannot be edited afterwards
    (hard rule 4), so a double here is permanent.
    """
    with tenant_ctx(brazos):
        result, first = _migrate_an_account(dana, brazos, account_no="A-12048", held=A_MIGRATED_DEPOSIT)
        entries_after_one = ledger_models.JournalEntry.objects.count()

        again = import_writer.post_opening_batch_from_import(
            actor=dana,
            batch_id=BATCH_ID,
            cutover_on=A_CUTOVER,
            imported_at=IMPORTED_AT,
            currency="USD",
            accounts=[],
            deposits=[
                {
                    "account_id": result["id"],
                    "account_ref": result["account_no"],
                    "held": A_MIGRATED_DEPOSIT,
                    "received_on": A_RECEIPT_DATE,
                }
            ],
        )
        entries_after_two = ledger_models.JournalEntry.objects.count()
        row = _deposit_row()

    assert Decimal(first["deposit_credits"]) == A_MIGRATED_DEPOSIT
    assert Decimal(again["deposit_credits"]) == A_MIGRATED_DEPOSIT
    assert entries_after_two == entries_after_one, "the re-run wrote a SECOND opening entry"
    assert row.gl == A_MIGRATED_DEPOSIT and row.register == A_MIGRATED_DEPOSIT
    assert row.state == tie_out.STATE_AGREED


def test_def1713__the_deposit_entry_does_not_collide_with_the_accounts_ar_opening(brazos, dana):
    """One account, one batch, TWO entries — and neither may be a replay of the other.

    Both are keyed `opening_balance | <account> | <event>`, so if the deposit
    reused the AR entry's event the migration would post the receivable and
    silently swallow the deposit.  That is DEF-1713 again with a replay guard on
    top, which is why the event halves differ by construction.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        opening_balances.post_opening_batch(
            batch_id=BATCH_ID,
            accounts=[
                opening_balances.OpeningAccount(
                    account_id=account.id, balance=Decimal("267.30"), account_ref="ACC-1042"
                )
            ],
            cutover_on=A_CUTOVER,
            imported_at=IMPORTED_AT,
            currency="USD",
        )
        deposits = opening_balances.post_opening_deposit_batch(
            batch_id=BATCH_ID,
            deposits=[
                opening_balances.OpeningDeposit(
                    account_id=account.id, held=A_MIGRATED_DEPOSIT, account_ref="ACC-1042"
                )
            ],
            cutover_on=A_CUTOVER,
            imported_at=IMPORTED_AT,
            currency="USD",
        )
        keys = set(
            ledger_models.JournalEntry.objects.values_list("posting_key", flat=True)
        )

    assert deposits.created_count == 1, "the deposit entry was swallowed as a replay of the AR one"
    assert deposits.ties_out
    assert len(keys) == 2, f"one account's two opening entries share a key: {sorted(keys)}"
    assert any(opening_balances.EVENT_CUTOVER_DEPOSIT_PREFIX in key for key in keys)


def test_def1713__a_negative_migrated_deposit_is_refused_by_name(brazos, dana):
    """A utility cannot hold less than none of a customer's money (BR-CUS-025).

    Posting it as written would DEBIT the deposit-liability account and state
    that the customer owes the utility their own deposit back.  Refused with the
    account and the figure, so the migration stops on the row rather than
    mis-stating it — the posture `post_opening_balance` already takes for an
    opening CREDIT balance.
    """
    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        with pytest.raises(opening_balances.OpeningBalanceError) as excinfo:
            opening_balances.post_opening_deposit_batch(
                batch_id=BATCH_ID,
                deposits=[
                    opening_balances.OpeningDeposit(
                        account_id=account.id,
                        held=Decimal("-42.10"),
                        account_ref="ACC-1042",
                    )
                ],
                cutover_on=A_CUTOVER,
                imported_at=IMPORTED_AT,
                currency="USD",
            )
        assert ledger_models.JournalEntry.objects.count() == 0

    assert "ACC-1042" in str(excinfo.value) and "-42.10" in str(excinfo.value)


def test_def1713__a_migrated_deposit_on_an_account_that_owes_nothing_still_posts(brazos, dana):
    """THE NESTING BUG THAT MADE THE DRIFT $750.00, pinned so it cannot return.

    Three of the seeded estate's five deposit-holding accounts carry NO opening
    buckets at all.  Accumulating the deposit inside `if not opening_empty:` —
    the obvious place, one line up from where it belongs — would post exactly
    none of them while every test that looks at an account WITH arrears passed.
    """
    with tenant_ctx(brazos):
        result, posting = _migrate_an_account(dana, brazos, account_no="A-10650", held=A_MIGRATED_DEPOSIT)
        row = _deposit_row()

    assert result["opening_empty"] is True, "this case is only meaningful with no opening balance"
    assert posting["posted"] == 0
    assert posting["deposits_posted"] == 1
    assert row.gl == row.register == A_MIGRATED_DEPOSIT
    assert row.state == tie_out.STATE_AGREED


# ═══════════════════════════════════════════════════════════════════════════
# BOTH DIRECTIONS AT ONCE — the case neither defect covers on its own
# ═══════════════════════════════════════════════════════════════════════════
def test_both__a_migrated_deposit_and_a_new_one_tie_out_together(brazos, dana):
    """A real utility has both, and the sum of the two must still agree.

    This is the case that would have caught either defect: one account brought
    its deposit across at cutover, another handed one over last week, and the
    2300 liability has to equal what the register says is held — 150.00 + 150.00
    = 300.00 on both sides.
    """
    with tenant_ctx(brazos):
        _migrate_an_account(dana, brazos, account_no="A-12048", held=A_MIGRATED_DEPOSIT)
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=A_DEPOSIT,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        row = _deposit_row()
        register = _register_total()

    assert register == Decimal("300.00")
    assert row.gl == Decimal("300.00")
    assert row.register == Decimal("300.00")
    assert row.drift == ZERO
    assert row.state == tie_out.STATE_AGREED
    assert row.blocks_release is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-177 + DEF-1713 (12-governance/10-defect-log.csv) + BR-LED-007 +
#         BR-CUS-049/050 + CLAUDE.md hard rules 4/5/6 + apps/ledger/tie_out.py +
#         apps/ledger/opening_balances.py + 10-scripts/gates/g48_import_money_posts.py
# generated: 2026-08-28 by the deposit-register lane
# checklist: A✔ B=n/a(no UI change — the S36 panel already renders this row and
#            renders it GREEN now) C✔ D✔(five mutations RUN and quoted in the
#            module docstring and the lane report)
# gates: golden-verify 33 PASS / 0 FAIL, unmoved — this file pins no ❄️ figure
# exceptions: (1) NO DEMO FIGURE IS PINNED HERE. $750.00 is the seeded estate's
#            total and is not a signed number; the estate guard lives in
#            test_cr040_seeded_books_tie_out.py, which is where it can redden on
#            a fixture change rather than on a rule change.
#            (2) THE DEPOSIT BATCH IS DELIBERATELY OUT OF GT-16's TIE-OUT. ❄️
#            GT-16 is signed as Σ opening JEs = Σ imported BUCKETS; folding a
#            deposit into that sum would move a frozen figure without a re-sign.
#            Each batch ties out against its own two sides.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
