# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (deposit batches — TC-1 the PE-10 pair, TC-3 the drawer
#           day, TC-5 no hand-edit, TC-6 isolation) · US-PAY-021 (S38 import —
#           TC-1 the lines and the matches, TC-2 the tolerance IS a setting,
#           TC-5 the re-import block, TC-6 a bad file) · US-PAY-022 (S40 —
#           TC-1 PE-11's −5.00, TC-3 the card day NET with its fee line, TC-5
#           reason+GL required, TC-6 a partial explanation) · US-PAY-023 (TC-3
#           the lock, TC-4 Unreconcile, TC-5 the direct UPDATE)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-004 · BR-PAY-019 · BR-PAY-021 · BR-PAY-025 · BR-PAY-028 ·
#           BR-PAY-035 · BR-PAY-039 (cash is realised at reconciliation) ·
#           BR-PAY-040 (a card day reconciles NET with a fee line) ·
#           BR-REP-013 (the batch day is the POSTING day) · BR-LED-001 ·
#           CLAUDE.md rules 1, 2, 4, 5, 6, 7
# Golden:   PE-10 ❄️ — checks 292.87 + 142.30 + 36.22 = **471.39**
#           (DEP-260808-CHK, the LABEL those ❄️ frozen rows were banked under;
#           a live cut allocates `DEP-260808-0001` since `P0.6`) · cash
#           105.36 + 16.42 = **121.78** (DEP-260808-CSH) ·
#           PE-11 ❄️ — bank **588.17** vs batch **593.17** → **−5.00** explained
#           as a bank fee with reason + GL · the PO's card day (2026-08-11):
#           **5,120.40** recorded, **4,972.90** banked, **147.50** to 6800
# ───────────────────────────────────────────────────────
"""Deposit batches, the bank statement, and the moment money becomes CASH.

**THE TWO TESTS THIS FILE EXISTS FOR** are
`test_us_pay_022_tc3__the_card_day_reconciles_net_with_its_fee_as_its_own_line`
and `test_us_pay_023_tc1__cash_is_realised_at_reconciliation_and_not_before`.
They are the two PO rulings of 2026-08-11 driven end to end:

  * *"Match net with a fee line"* — the $5,120.40 card day that could never
    match now reconciles against the bank's $4,972.90 with $147.50 posted to
    6800 Bank fees as its OWN line;
  * *"Cash is received but undeposted … until bank record and reconcilaition
    confirm it it is not realised"* — the receipt sits in 1010 Undeposited
    funds and only the reconciliation moves it to 1000 Cash.

EVERY FIGURE HERE IS COPIED, NEVER COMPUTED. PE-10 and PE-11 are the ratified
worked examples (08-payments/07-pre-session-model.md §7) and the card day's
three numbers are the PO's own, from the decision log. A test that recomputed
its expectation would agree with a broken implementation.

WHAT RUNS WHERE, because it changes what a green run is worth:

  * The SERVICE-LAYER refusals — an unexplained residual, a missing GL, a
    locked batch, a duplicate statement file — run everywhere, including on the
    SQLite developer database which has no triggers and no RLS.
  * The DATABASE laws — the reconciled-batch lock, the append-only trail, the
    write-once membership door and RLS — carry `requires_postgres` and SKIP on
    SQLite rather than passing vacuously.

EVERY GUARD IN THIS FILE WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won
law 7). The five proofs, each run and each quoted verbatim in the lane report
and in 12-governance/09-human-review-ledger.md: the card day reconciled against
GROSS; the fee absorbed into the cash line instead of posting to 6800; a
reconciled+locked batch edited (service and trigger); cash posted on receipt
instead of on reconciliation; and the same statement file imported twice.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import lockbox, models, reconciliation, services
from apps.payments.exceptions import PaymentRuleError
from core import numbering as core_numbering

from tests.isolation_helpers import (
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

# ── PE-10, verbatim (08-payments/07-pre-session-model.md §7 · EP-PAY-06 §4) ──
# "Aug 8, 2026 — checks 292.87 (ACC-1042 PE-1) + 142.30 (ACC-1103) + 36.22
#  (ACC-1310 installment) → DEP-260808-CHK 471.39; cash 105.36 (ACC-1077) + 16.42
#  → DEP-260808-CSH 121.78."
PE10_CHECKS = (Decimal("292.87"), Decimal("142.30"), Decimal("36.22"))
PE10_CASH = (Decimal("105.36"), Decimal("16.42"))
PE10_CHECK_TOTAL = Decimal("471.39")
PE10_CASH_TOTAL = Decimal("121.78")
PE10_DAY = date(2026, 8, 8)
PE10_CHECK_CODE = "DEP-260808-CHK"
PE10_CASH_CODE = "DEP-260808-CSH"

#: PE-11, verbatim: "bank 588.17 vs batch 593.17 → −5.00 explained (bank fee)".
PE11_RECORDED = Decimal("593.17")
PE11_BANK = Decimal("588.17")
PE11_DIFFERENCE = Decimal("-5.00")

# ── The PO's own card day (decision log 2026-08-11, OQ-144 → BR-PAY-040) ────
# "a card day takes $5,120.40 from customers, the bank credits $4,972.90, and
#  $147.50 is the processor's fee … the deposit matches the bank credit NET and
#  the $147.50 posts as a fee line to signed account 6800 Bank fees."
CARD_RECORDED = Decimal("5120.40")
CARD_BANKED = Decimal("4972.90")
CARD_FEE = Decimal("147.50")

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)


# ── fixture helpers ─────────────────────────────────────────────────────────
def an_issued_bill(tenant, account, *, number, total, issued_on):
    """One ISSUED bill, in the shape `record_payment` meets it (the US-PAY-001
    helper's shape — created through billing's ORM so this file's subject stays
    the money-landed pipeline rather than the rating engine)."""
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        due_date=issued_on,
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
    )


def an_account_of(actor, tenant, *, service="electric"):
    """One account on a unit of a service THIS tenant actually sells.

    `an_account` hardcodes electric; Lone Star Ridge is water-only (its
    provisioning payload says so), and creating an electric unit there is
    refused by metering with VAL-005 — correctly. The isolation case needs a
    real account in BOTH tenants, so the service is a parameter here.
    """
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(actor, address_line="1901 Bluestem Ln", services_available=[service])
    unit = make_unit(actor, premises["id"], label="Unit A", services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=f"A-{uuid.uuid4().hex[:8]}",
    )


def a_cleared_payment(
    actor, tenant, *, amount, method_code, posted_at=POSTED_AT, cleared_at=None, service="electric"
):
    """One cleared payment through the REAL service — no ORM shortcuts.

    Each payment gets its own account and its own bill so the allocation is
    ordinary and this file asserts BATCHING rather than re-asserting US-PAY-006.
    """
    account = an_account_of(actor, tenant, service=service)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2608-{uuid.uuid4().hex[:6]}",
        total=amount,
        issued_on=date(2026, 8, 1),
    )
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        method_code=method_code,
        posted_at=posted_at,
        cleared_at=cleared_at or posted_at,
        idempotency_reference=uuid.uuid4(),
    )


def a_bank_account(tenant, *, name="Chase Operating", mask="4021"):
    return bankrec.BankAccount.objects.create(tenant=tenant, name=name, mask=mask)


def a_statement(rows, *, header="Posting date,Description,Amount"):
    """A bank CSV in the shape S38 step 1 accepts."""
    body = "\n".join(f"{when},{reference},{amount}" for when, reference, amount in rows)
    return f"{header}\n{body}\n".encode()


def gl_id(tenant, designation):
    from apps.ledger import models as ledger_models

    return ledger_models.LedgerAccount.objects.get(tenant=tenant, designation=designation).pk


def journal_legs(tenant):
    """Every posted journal line of a tenant as `(code, side, amount)`."""
    from apps.ledger import models as ledger_models

    return [
        (code, side, amount)
        for code, side, amount in ledger_models.JournalLine.objects.filter(
            tenant=tenant, journal_entry__status=ledger_models.JE_POSTED
        ).values_list("ledger_account__code", "side", "amount")
    ]


def leg(legs, code, side):
    return sum(
        (amount for gl, gl_side, amount in legs if gl == code and gl_side == side), Decimal("0")
    )


def audit_actions_for(rows, action):
    return [row for row in rows if row["action"] == action]


def the_days_batches(tenant, day):
    """Every batch banked for `day`, as the cut used to report them.

    ⚠ CR-186-BRC10 (PO 2026-10-21): a payment is stamped into its till's or
    its channel's batch AT POSTING, all tenders together, so the nightly cut
    finds nothing left to sweep on an ordinary day and `cut.batches` is empty.
    The batch a test wants is the day's batch the payments already joined.
    """
    rows = bankrec.DepositBatch.objects.filter(tenant=tenant, deposited_on=day).order_by("code")
    return tuple(
        reconciliation.BatchSummary(
            batch_id=str(row.pk),
            code=row.code,
            method_code=None if row.method_id is None else row.method.code,
            deposited_on=row.deposited_on,
            recorded_total=row.recorded_total,
            payment_count=models.Payment.objects.filter(deposit_batch_id=row.pk).count(),
            status=row.status,
            created=False,
        )
        for row in rows
    )


def a_batch(actor, tenant, *, amounts, method_code, day=PE10_DAY, service="electric"):
    """Record `amounts` through the service and cut the day's batch."""
    for amount in amounts:
        a_cleared_payment(
            actor,
            tenant,
            amount=amount,
            method_code=method_code,
            service=service,
            posted_at=datetime(day.year, day.month, day.day, 10, 30, tzinfo=UTC),
        )
    reconciliation.cut_deposit_batches(actor=actor, day=day, occurred_at=POSTED_AT)
    # CR-186-BRC10 — the payments joined the day's batch at posting.
    return the_days_batches(tenant, day)[-1]


# ══ US-PAY-020 · the batches ════════════════════════════════════════════════
def test_us_pay_020_tc1__pe10_cuts_two_batches_by_day_and_method(brazos, marcus, audit_rows):
    """US-PAY-020 TC-1 / PE-10, verbatim: 471.39 in checks, 121.78 in cash.

    Five things become true at once and all five are asserted, because any one
    of them missing is a batch that cannot be reconciled: two batches (not one,
    not three), the frozen totals, the DEP- codes, the membership stamp on every
    payment, and the audit row hard rule 7 requires.
    """
    with tenant_ctx(brazos):
        for amount in PE10_CHECKS:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")
        for amount in PE10_CASH:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="cash")

        result = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=POSTED_AT
        )

        # ⚠ **CR-186-BRC10 (PO 2026-10-21): ONE BATCH PER TILL OR CHANNEL PER
        # DAY, ALL TENDERS, STAMPED AT POSTING.** This case asserted TWO batches
        # (check and cash) under the 2026-09-22 "one till and one tender" ruling,
        # which the PO superseded with *"this is one batch only - it will ahve 1
        # batch ID not 2"*. PE-10's money is untouched — 471.39 and 121.78 are
        # now the batch's TENDER TOTALS, and the batch is their sum, 593.17.
        assert result.payments_batched == 0, "every payment was stamped when it was posted"
        batches = the_days_batches(brazos, PE10_DAY)
        assert len(batches) == 1, batches
        (day,) = batches
        assert day.code.startswith("DEP-260808-") and "CHK" not in day.code
        assert day.method_code is None, "all tenders"
        assert day.recorded_total == PE10_CHECK_TOTAL + PE10_CASH_TOTAL
        assert day.payment_count == 5
        assert day.status == bankrec.BATCH_IN_TRANSIT
        row = bankrec.DepositBatch.objects.get(pk=day.batch_id)
        totals = {t["method_code"]: t["amount"] for t in reconciliation.tender_totals(row)}
        assert totals == {"check": PE10_CHECK_TOTAL, "cash": PE10_CASH_TOTAL}

        # Every payment carries its batch — the S33 batch column's source.
        assert (
            models.Payment.objects.filter(tenant=brazos, deposit_batch_id__isnull=True).count() == 0
        )
        # hard rule 7 — one row for the batch the first posting opened.
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_BATCH_CREATED)) == 1
        assert (
            bankrec.DepositBatchEvent.objects.filter(
                tenant=brazos, event=bankrec.EVENT_CREATED
            ).count()
            == 1
        )


def test_us_pay_020_tc3__the_batch_day_is_the_posting_day_not_the_clearing_day(brazos, marcus):
    """US-PAY-020 TC-3 — **CORRECTED**: the drawer day, per the PO's RQ-5 ruling.

    The epic's own TC-3 read *"A check posted Aug 8, cleared Aug 9 → it joins
    the **Aug 9** check batch — grouping is by clearing day"*. That text predates
    RQ-5 and contradicts BR-PAY-025 (*"day = POSTING date per RQ-5/BR-REP-013"*),
    BR-REP-013 and journey J14 step 4. The ruling wins; the epic is corrected in
    this commit and the stale line carries defect row DEF-065.

    This case is the corrected one, and it is only meaningful because the two
    dates DIFFER: with them equal, both readings give the same answer.
    """
    with tenant_ctx(brazos):
        a_cleared_payment(
            marcus,
            brazos,
            amount=Decimal("292.87"),
            method_code="check",
            posted_at=datetime(2026, 8, 8, 16, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 9, 9, 0, tzinfo=UTC),
        )

        # The drawer day.
        cut = reconciliation.cut_deposit_batches(
            actor=marcus, day=date(2026, 8, 8), occurred_at=POSTED_AT
        )
        # The DAY is what this case is about and the day is still in the code;
        # the tender is not (allocated since `P0.6`).
        # CR-186-BRC10 — the payment joined its POSTING day's batch at posting.
        assert cut.payments_batched == 0
        (day,) = the_days_batches(brazos, date(2026, 8, 8))
        assert day.code.startswith("DEP-260808-")
        assert day.recorded_total == Decimal("292.87")

        # The bank's day cuts nothing: the money was already in Friday's drawer.
        later = reconciliation.cut_deposit_batches(
            actor=marcus, day=date(2026, 8, 9), occurred_at=POSTED_AT
        )
        assert later.batches == ()
        assert later.payments_batched == 0


def test_us_pay_020_tc5__cutting_twice_changes_nothing_and_a_total_is_never_typed(brazos, marcus):
    """US-PAY-020 TC-5 — totals are Σ members, and the grouping is idempotent.

    Two claims in one case because they are the same guarantee from two sides:
    a batch is (tenant, day, method) so a second cut adds nothing (hard rule 6),
    and `recorded_total` is derived so no caller can hand one in.
    """
    with tenant_ctx(brazos):
        for amount in PE10_CHECKS:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")

        first = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=POSTED_AT
        )
        second = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=POSTED_AT
        )

        # CR-186-BRC10 — stamped at posting, so neither cut adds anything.
        assert first.payments_batched == 0
        assert second.batches == () and second.payments_batched == 0
        assert bankrec.DepositBatch.objects.filter(tenant=brazos).count() == 1
        assert bankrec.DepositBatch.objects.get(tenant=brazos).recorded_total == PE10_CHECK_TOTAL


def test_us_pay_020_tc5b__a_reversing_row_and_a_methodless_row_are_reported_not_banked(
    brazos, marcus
):
    """Money that did not go to the bank is SKIPPED with a reason, never dropped.

    A negative row (the shape BR-PAY-013's reversal takes) and a payment with no
    instrument cannot be in a drawer batch — `deposit_batches.method` is NOT
    NULL and a reversal is not a deposit. Both are reported on the result rather
    than silently ignored, because a payment nobody banked is a real thing to
    look at.
    """
    with tenant_ctx(brazos):
        good = a_cleared_payment(marcus, brazos, amount=Decimal("100.00"), method_code="check")
        # Written through the ORM: `record_payment` refuses both shapes at the
        # door, and what this case asserts is that BATCHING refuses them too —
        # a row that arrives by any other path is still not a deposit.
        account = models.Payment.objects.get(pk=good.payment_id).account
        models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("-100.00"),
            currency="USD",
            status=models.PAYMENT_CLEARED,
            method=models.Payment.objects.get(pk=good.payment_id).method,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
        )
        models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("50.00"),
            currency="USD",
            status=models.PAYMENT_CLEARED,
            method=None,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
        )

        result = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=POSTED_AT
        )

        # CR-186-BRC10 — the good payment joined the day's batch at posting.
        assert the_days_batches(brazos, PE10_DAY)[0].recorded_total == Decimal("100.00")
        assert {row["reason"] for row in result.skipped} == {"not_positive_money", "no_method"}


@pytest.mark.isolation
def test_us_pay_020_tc6__batches_never_cross_tenants(brazos, marcus, lonestar, erin):
    """US-PAY-020 TC-6 — the same DEP- code in two tenants, and no leak.

    The code is unique PER TENANT (B2 §2), so both utilities bank a check deposit
    that day and neither sees the other's. ⚠ Since `P0.6` the code is ALLOCATED
    and **every tenant's series starts at 1**, so the two codes are now
    identical (`DEP-260808-0001`) where they used to be identical for a
    different reason (both composed from the same day and tender). The
    collision is real either way and hard rule 1 is what makes it harmless. Cutting Brazos Bend's day
    while Lone Star Ridge has its own money proves the grouping query is
    tenant-scoped rather than filtered by luck.
    """
    with tenant_ctx(lonestar):
        a_cleared_payment(
            erin, lonestar, amount=Decimal("64.00"), method_code="check", service="water"
        )
        reconciliation.cut_deposit_batches(actor=erin, day=PE10_DAY, occurred_at=POSTED_AT)

    with tenant_ctx(brazos):
        for amount in PE10_CHECKS:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")
        result = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=POSTED_AT
        )
        # CR-186-BRC10 — stamped at posting into this tenant's day batch.
        assert the_days_batches(brazos, PE10_DAY)[0].recorded_total == PE10_CHECK_TOTAL

    with tenant_ctx(lonestar):
        assert bankrec.DepositBatch.objects.filter(tenant=lonestar).count() == 1
        lone_batch = bankrec.DepositBatch.objects.get(tenant=lonestar)
        assert lone_batch.recorded_total == Decimal("64.00")
        # ⚠ **THE TWO TENANTS STILL SHARE A CODE AFTER `P0.6`, AND AN EARLIER
        # DRAFT OF THIS COMMENT CLAIMED THEY DO NOT.** They did when the code
        # was composed from (day, tender), and they still do now it is
        # allocated, because **every tenant's `deposit_batch` series starts at
        # 1** — so both utilities render `DEP-260808-0001` for this day.
        # `uq_deposit_batches_code` is UNIQUE **PER TENANT**, and RLS is the
        # whole of what keeps the two apart. That is exactly what this case
        # exists to assert and the re-key did not weaken it.
        assert lone_batch.code.startswith("DEP-260808-")
        shared_code = lone_batch.code
        # ⚠ **SCOPED BY TENANT EXPLICITLY, AND THAT IS A WEAKENING SAID OUT
        # LOUD.** This read used to be `filter(code=…)` with no tenant term,
        # answering 1 because the two utilities' codes differed by luck of the
        # fixture. Now both allocate `DEP-260808-0001`, so an unscoped read
        # answers **2 on SQLite — where there is no RLS to make it 1.** The
        # honest statement on this database is the explicit scope; the real
        # guarantee is `payments/0005`'s RLS policy and is provable only on
        # PostgreSQL, which is what `@pytest.mark.isolation` and
        # `tests/test_cr135_p0_rls_pg.py` are for.
        assert (
            bankrec.DepositBatch.objects.filter(tenant=lonestar, code=shared_code).count() == 1
        )

    # ⚠ THE "TWO TENANTS, NO COLLISION" HALF IS NOW ASSERTED AS TWO READS, ONE
    # PER TENANT, AND THAT IS THE ONLY WAY IT CAN BE ASSERTED AT ALL. It used to
    # be `filter(code=…).count() == 2` taken with NO tenant context — a single
    # query seeing both utilities' rows at once. On a connection row-level
    # security genuinely applies to that query returns ZERO, and no context
    # exists from which it could return two: seeing both tenants' money in one
    # result set is precisely what hard rule 1 forbids. Two ones, from two
    # contexts, with different ids is the same fact stated lawfully — and it is
    # a stronger statement, because it also says neither tenant can see the other's.
    with tenant_ctx(brazos):
        assert bankrec.DepositBatch.objects.filter(tenant=brazos, code=shared_code).count() == 1
        brazos_batch = bankrec.DepositBatch.objects.get(tenant=brazos, code=shared_code)
    assert brazos_batch.id != lone_batch.id
    # ⚠ THE SAME STRING, TWO DIFFERENT ROWS, NEITHER VISIBLE FROM THE OTHER'S
    # CONTEXT. Two ones from two contexts with different ids — the collision is
    # real and hard rule 1 is what makes it harmless.
    assert brazos_batch.code == lone_batch.code


# ══ US-PAY-021 · the statement import ═══════════════════════════════════════
def test_us_pay_021_tc1__the_statement_lands_and_the_exact_line_auto_matches(
    brazos, marcus, audit_rows
):
    """US-PAY-021 TC-1 — every line persists; equal amount + date in tolerance = Auto.

    The tolerance is doing real work here: the money was taken on **8 Aug** (the
    drawer day) and the bank posted it on **11 Aug**, three days later, which is
    exactly the seeded ±3 (BR-PAY-019). That gap is why the batch day being the
    POSTING day and the matching being on the bank's date can both be true.
    """
    with tenant_ctx(brazos):
        batch = a_batch(marcus, brazos, amounts=PE10_CHECKS, method_code="check")
        account = a_bank_account(brazos)

        result = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            file_name="chase-aug.csv",
            payload=a_statement(
                [
                    ("2026-08-11", "CHECK DEPOSIT 4410", "471.39"),
                    ("2026-08-11", "INTEREST", "0.42"),
                ]
            ),
            imported_at=STATEMENT_AT,
        )

        assert result.line_count == 2
        assert [row.batch_code for row in result.matched] == [batch.code]
        assert result.matched[0].state == "auto"
        assert result.matched[0].difference == Decimal("0")
        # The 0.42 belongs to nothing of ours — S38's fourth tile, counted.
        assert [row.state for row in result.not_in_our_system] == ["not_in_our_system"]

        assert bankrec.BankLine.objects.filter(tenant=brazos).count() == 2
        assert bankrec.DepositBatch.objects.get(pk=batch.batch_id).status == bankrec.BATCH_MATCHED
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_STATEMENT_IMPORTED)) == 1


def test_us_pay_021_tc2__the_date_tolerance_is_a_finance_setting_not_a_constant(brazos, marcus):
    """US-PAY-021 TC-2 — ±3 matches a 3-day gap; the tenant's ±1 stops matching it.

    BR-PAY-019 says *"the tolerance is a finance setting"*, and the only way to
    prove a setting is a setting is to MOVE it: a constant 3 in the matcher
    passes the first half of this case and fails the second.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        batch = a_batch(marcus, brazos, amounts=PE10_CHECKS, method_code="check")
        account = a_bank_account(brazos)

        settings_row = tenancy_models.TenantSettings.objects.get(tenant=brazos)
        settings_row.finance_controls = {
            **settings_row.finance_controls,
            "bank_match_date_tolerance_days": 1,
        }
        settings_row.save(update_fields=["finance_controls"])

        tight = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")]),
            imported_at=STATEMENT_AT,
        )
        assert tight.matched == ()
        assert [row.state for row in tight.exceptions] == ["needs_a_look"]

        settings_row.finance_controls = {
            **settings_row.finance_controls,
            "bank_match_date_tolerance_days": 3,
        }
        settings_row.save(update_fields=["finance_controls"])

        wide = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 12),  # a different tag ⇒ a different key
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")]),
            imported_at=STATEMENT_AT,
        )
        assert [row.batch_code for row in wide.matched] == [batch.code]


def test_us_pay_021_tc5__the_same_statement_file_cannot_be_imported_twice(brazos, marcus):
    """US-PAY-021 TC-5 — file+tags idempotency (BR-PAY-028 🔒, hard rule 6).

    The refusal must NAME who imported it first and when, because a clerk who
    only hears "already imported" cannot tell a duplicate upload from a bug.

    PROVED RED: with the pre-insert duplicate lookup removed, the second import
    writes a second `bank_statement_imports` row and every bank line twice.
    """
    with tenant_ctx(brazos):
        a_batch(marcus, brazos, amounts=PE10_CHECKS, method_code="check")
        account = a_bank_account(brazos)
        payload = a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")])
        kwargs = dict(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            file_name="chase-aug.csv",
            imported_at=STATEMENT_AT,
        )

        reconciliation.import_bank_statement(payload=payload, **kwargs)
        with pytest.raises(PaymentRuleError, match="already imported"):
            reconciliation.import_bank_statement(payload=payload, **kwargs)

        assert bankrec.BankStatementImport.objects.filter(tenant=brazos).count() == 1
        assert bankrec.BankLine.objects.filter(tenant=brazos).count() == 1


def test_us_pay_021_tc6__an_unreadable_file_is_refused_naming_the_row(brazos, marcus):
    """US-PAY-021 TC-6 — a malformed file is refused, never half-read.

    One bad row refuses the WHOLE statement: half a statement reconciles to
    nothing and there is no way to tell which half is missing. The refusal names
    the row number, and an OFX upload is refused by FORMAT so the clerk knows
    what to export instead.
    """
    with tenant_ctx(brazos):
        account = a_bank_account(brazos)
        kwargs = dict(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            imported_at=STATEMENT_AT,
        )
        with pytest.raises(PaymentRuleError, match="row 3"):
            reconciliation.import_bank_statement(
                payload=a_statement(
                    [("2026-08-11", "CHECK DEPOSIT 4410", "471.39"), ("2026-08-11", "X", "abc")]
                ),
                **kwargs,
            )
        with pytest.raises(PaymentRuleError, match="OFX"):
            reconciliation.import_bank_statement(payload=b"whatever", file_format="ofx", **kwargs)
        with pytest.raises(PaymentRuleError, match="no posted_on"):
            reconciliation.import_bank_statement(
                payload=b"when,what,how much\n2026-08-11,x,1.00\n", **kwargs
            )
        assert bankrec.BankStatementImport.objects.filter(tenant=brazos).count() == 0


# ══ US-PAY-022 · explaining the difference ══════════════════════════════════
def test_us_pay_022_tc1__pe11_minus_five_is_explained_with_a_reason_and_a_gl(
    brazos, marcus, audit_rows
):
    """US-PAY-022 TC-1 / PE-11, verbatim: bank 588.17 vs batch 593.17 → −5.00.

    The frozen figures drive the whole path: the batch cannot auto-match (the
    amounts differ), a human names the pairing, the −5.00 is explained as a bank
    fee with its GL, and only then does the batch reconcile.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("400.00"), Decimal("193.17")),  # Σ = PE-11's 593.17
            method_code="check",
        )
        assert batch.recorded_total == PE11_RECORDED
        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "588.17")]),
            imported_at=STATEMENT_AT,
        )
        # Not auto-matched: the amounts differ, and nothing here guesses.
        assert imported.matched == ()
        exception = imported.exceptions[0]

        difference = reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=exception.bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        assert difference == PE11_DIFFERENCE

        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=STATEMENT_AT,
            resolutions=(
                reconciliation.ResolutionInput(
                    reason_code="bank_fee",
                    gl_account_id=gl_id(brazos, "bank_fees"),
                    amount=PE11_DIFFERENCE,
                    note="Bank fee on the Aug 8 deposit, confirmed with the bank",
                ),
            ),
        )

        assert result.difference == PE11_DIFFERENCE
        assert result.explained == PE11_DIFFERENCE
        assert (
            bankrec.DepositBatch.objects.get(pk=batch.batch_id).status == bankrec.BATCH_RECONCILED
        )
        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == PE11_BANK  # what the bank gave us
        assert leg(legs, "6800", "debit") == Decimal("5.00")  # its own line
        assert leg(legs, "1010", "credit") == PE11_RECORDED  # what we took in
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_REC_RESOLVED)) == 1
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_BATCH_RECONCILED)) == 1


def test_us_pay_022_tc3__the_card_day_reconciles_net_with_its_fee_as_its_own_line(brazos, marcus):
    """**THE PO'S RULING OF 2026-08-11 (OQ-144 → BR-PAY-040), driven end to end.**

    Verbatim: *"Match net with a fee line"*. Worked, in the PO's own figures: a
    card day takes **$5,120.40**, the bank credits **$4,972.90**, the processor
    kept **$147.50**. Before this ruling that day could never match — it was one
    of roughly 250 hand-worked exceptions a year.

    The entry is the whole point, and every line of it is asserted:

        DR 1000 Cash               4,972.90
        DR 6800 Bank fees            147.50   ← ITS OWN LINE, never netted
        CR 1010 Undeposited funds  5,120.40

    PROVED RED, twice:
      * reconciling against GROSS (requiring bank_total == recorded_total) →
        *"deposit batch DEP-260804-CARD does not tie: we recorded 5120.40, the
        bank shows 4972.90, a difference of -147.50"* — the card day can never
        reconcile, which is the defect this ruling fixes;
      * the fee ABSORBED into the cash line (DR 1000 for the gross) → the books
        lose the $147.50 entirely: 6800 is never touched and the tenant cannot
        report what their processor charged them.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("3000.00"), Decimal("2120.40")),  # Σ = 5,120.40
            method_code="card",
            day=date(2026, 8, 4),
        )
        # The day is still in the code (2026-08-12); the tender is not,
        # since `P0.6` allocated it from the series (2026-09-22).
        assert batch.code.startswith("DEP-260804-")
        assert "CARD" not in batch.code
        assert batch.recorded_total == CARD_RECORDED

        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 6),
            payload=a_statement([("2026-08-04", "CARD SETTLEMENT", "4972.90")]),
            imported_at=STATEMENT_AT,
        )
        difference = reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        assert difference == -CARD_FEE

        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=STATEMENT_AT,
            resolutions=(
                reconciliation.ResolutionInput(
                    reason_code="processor_fee",
                    gl_account_id=gl_id(brazos, "bank_fees"),
                    amount=-CARD_FEE,
                ),
            ),
        )

        assert result.bank_total == CARD_BANKED
        assert result.recorded_total == CARD_RECORDED
        assert result.explained == -CARD_FEE

        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == CARD_BANKED  # NET — what the bank gave
        assert leg(legs, "6800", "debit") == CARD_FEE  # the fee, its own line
        assert leg(legs, "1010", "credit") == CARD_RECORDED  # gross, cleared out
        debits = sum(a for _c, s, a in legs if s == "debit")
        credits = sum(a for _c, s, a in legs if s == "credit")
        assert debits == credits, "hard rule 5 — a posted entry balances to the cent"


def test_us_pay_022_tc3b__deriving_the_fee_from_the_difference_is_refused_by_name(brazos, marcus):
    """OQ-160 — the ruling settled the fee LINE, not where the fee's amount comes from.

    The decision log records the residue in its own words: *"whether the net
    match requires the fee to be known in advance from the processor's
    settlement file, or is derived from the difference (which would silently
    absorb a genuine shortfall into 'fees'). That distinction decides whether a
    $10 customer chargeback hides inside a fee line."* So the automatic rule
    raises rather than choosing (prime directive).
    """
    # **PO ruling 2026-08-12, verbatim: "derived from shortfall" — OQ-160 CLOSED.**
    # The PO's own card day: we take 5,120.40, the bank credits 4,972.90.
    fee = reconciliation.derive_processor_fee(
        recorded_total=Decimal("5120.40"),
        bank_total=Decimal("4972.90"),
        gl_account_id="6800",
    )
    assert fee.amount == Decimal("-147.50")
    assert fee.gl_account_id == "6800"
    assert "5120.40" in (fee.note or "") and "4972.90" in (fee.note or "")

    # THE HAZARD THE REFUSAL EXISTED FOR IS STILL GUARDED. A bank crediting MORE
    # than we recorded has not charged a fee; calling it one would post a
    # negative expense over a real question about where the money came from.
    with pytest.raises(reconciliation.PaymentRuleError, match="cannot be one"):
        reconciliation.derive_processor_fee(
            recorded_total=Decimal("4972.90"),
            bank_total=Decimal("5120.40"),
            gl_account_id="6800",
        )


def test_us_pay_022_tc5__no_reason_no_gl_and_no_force_match(brazos, marcus):
    """US-PAY-022 TC-5 — BR-PAY-019's reason AND GL, and BR-PAY-035's superseded button.

    Three refusals, because each is a different way an unexplained residual
    could reconcile: a blank reason, no GL account, and a GL that is not this
    tenant's live chart. There is no fourth path — *"Force match anyway"* does
    not exist in this module at all.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus, brazos, amounts=(Decimal("400.00"), Decimal("193.17")), method_code="check"
        )
        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "588.17")]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        fees = gl_id(brazos, "bank_fees")

        with pytest.raises(PaymentRuleError, match="carries no reason"):
            reconciliation.reconcile_batch(
                actor=marcus,
                batch_id=batch.batch_id,
                posted_at=STATEMENT_AT,
                resolutions=(reconciliation.ResolutionInput("  ", fees, PE11_DIFFERENCE),),
            )
        with pytest.raises(PaymentRuleError, match="names no GL account"):
            reconciliation.reconcile_batch(
                actor=marcus,
                batch_id=batch.batch_id,
                posted_at=STATEMENT_AT,
                resolutions=(reconciliation.ResolutionInput("bank_fee", None, PE11_DIFFERENCE),),
            )
        with pytest.raises(PaymentRuleError, match="not a LIVE account"):
            reconciliation.reconcile_batch(
                actor=marcus,
                batch_id=batch.batch_id,
                posted_at=STATEMENT_AT,
                resolutions=(
                    reconciliation.ResolutionInput("bank_fee", uuid.uuid4(), PE11_DIFFERENCE),
                ),
            )
        assert bankrec.DepositBatch.objects.get(pk=batch.batch_id).status == bankrec.BATCH_MATCHED
        assert bankrec.BankRecResolution.objects.filter(tenant=brazos).count() == 0


def test_us_pay_022_tc6__a_partly_explained_difference_never_reconciles(brazos, marcus):
    """US-PAY-022 TC-6 — explain −80.00 of −100.00 and NOTHING happens.

    *"Σ reason-coded explanations + Σ member corrections = difference, then
    difference = 0 at reconcile"* (US-PAY-022 §7). The residual is named in the
    refusal, because "does not tie" without the number is not actionable.
    """
    with tenant_ctx(brazos):
        batch = a_batch(marcus, brazos, amounts=(Decimal("620.00"),), method_code="cash")
        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-09", "CASH DEPOSIT TELLER", "540.00")]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        # The difference is −80.00 and only −60.00 of it is explained.
        with pytest.raises(PaymentRuleError, match=r"leaving -20\.0+ unexplained"):
            reconciliation.reconcile_batch(
                actor=marcus,
                batch_id=batch.batch_id,
                posted_at=STATEMENT_AT,
                resolutions=(
                    reconciliation.ResolutionInput(
                        "cash_short", gl_id(brazos, "bank_fees"), Decimal("-60.00")
                    ),
                ),
            )
        assert journal_legs(brazos) and leg(journal_legs(brazos), "1000", "debit") == Decimal("0")
        assert bankrec.BankRecResolution.objects.filter(tenant=brazos).count() == 0


# ══ US-PAY-023 · the lock, the trail, and the cash ══════════════════════════
def test_us_pay_023_tc1__cash_is_realised_at_reconciliation_and_not_before(brazos, marcus):
    """**THE PO'S RULING OF 2026-08-11 (OQ-143 → BR-PAY-039), driven end to end.**

    Verbatim: *"Cash is received but undeposted in such case payment will say
    csah but ledger will say undeposited - until bank record and reconcilaition
    confirm it it is not realised"*.

    So the same $471.39 appears in two different accounts at two different
    moments, and this case asserts BOTH — the first half is what the ruling
    changed, the second is what makes the change meaningful:

        after the receipt       DR 1010 Undeposited 471.39 · 1000 Cash 0.00
        after the reconcile     DR 1000 Cash 471.39 · 1010 nets to 0.00

    PROVED RED: with the receipt leg posting to 1000 (the pre-ruling behaviour),
    cash reads 471.39 before any bank statement exists — the ruling defeated,
    and the whole point of a reconciliation with it.
    """
    with tenant_ctx(brazos):
        batch = a_batch(marcus, brazos, amounts=PE10_CHECKS, method_code="check")

        # Money is IN, and the bank has confirmed nothing.
        legs = journal_legs(brazos)
        assert leg(legs, "1010", "debit") == PE10_CHECK_TOTAL
        assert leg(legs, "1000", "debit") == Decimal("0")

        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")]),
            imported_at=STATEMENT_AT,
        )
        assert imported.matched  # exact amount, three days apart, inside ±3

        result = reconciliation.reconcile_batch(
            actor=marcus, batch_id=batch.batch_id, posted_at=STATEMENT_AT
        )
        assert result.difference == Decimal("0")

        # The bank confirmed it, so now it is cash — and undeposited nets to nil.
        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == PE10_CHECK_TOTAL
        assert leg(legs, "1010", "debit") - leg(legs, "1010", "credit") == Decimal("0")

        # The BOOK date is the day the BANK confirmed it, not the drawer day.
        from apps.ledger import models as ledger_models

        entry = ledger_models.JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.entry_date == date(2026, 8, 11)


def test_us_pay_023_tc3__a_reconciled_batch_is_locked(brazos, marcus):
    """US-PAY-023 TC-3 — nothing about a reconciled batch changes (BR-PAY-004).

    Asserted at the SERVICE layer, which is where the SQLite developer database
    is protected; TC-5 below asserts the same law in the DATABASE, where it
    holds against a repair script.

    The recompute refusal is a RULE and no longer a parked question: the PO
    ruled on 2026-08-12 that the lock HOLDS, so a locked batch's total does not
    move and recomputing it is the in-place edit hard rule 4 forbids.
    """
    with tenant_ctx(brazos):
        batch = _a_reconciled_batch(marcus, brazos)

        with pytest.raises(PaymentRuleError, match="already reconciled"):
            reconciliation.reconcile_batch(
                actor=marcus, batch_id=batch.batch_id, posted_at=STATEMENT_AT
            )
        with pytest.raises(PaymentRuleError, match="cannot be recomputed"):
            reconciliation.recompute_batch_total(batch.batch_id)


def test_us_pay_023_tc3b__a_bounce_inside_a_locked_batch_is_allowed_and_the_total_holds(
    brazos, marcus
):
    """**OQ-134, RULED 2026-08-12 — the lock HOLDS and the bounce is new rows.**

    This test asserted a REFUSAL until then (`assert_bounce_allowed` raised for
    any payment in a reconciled batch), and that refusal was correct while the
    question stood: US-PAY-022 TC-2 resolves the UNLOCKED case by recomputing
    `recorded_total`, and doing that after the lock edits a signed-off money
    record. Which gave — the lock or the tie-out — was not an implementing
    lane's call.

    The PO ruled, verbatim: *"if this happen Utility will charge Cheque bounce
    charges and add new entry - this will be mnaul process by utility user in
    payments or in finance we have to decide the place - you decide for me"*.
    So the bounce goes ahead and the batch does not move. Asserted here on
    PE-10's own frozen figure — **471.39** before the bounce is allowed and
    **471.39** after — which is the shape of the ruling's DEP-260805-CHK worked
    case ($2,840.00 stays $2,840.00 when cheque #4021's $100.00 comes back).

    Two things the ruling did NOT settle still refuse, and each is asserted:
    a batch this process cannot read is a broken reference, not a lock; and the
    locked total may still never be recomputed.
    """
    with tenant_ctx(brazos):
        batch = _a_reconciled_batch(marcus, brazos)
        member = models.Payment.objects.filter(
            tenant=brazos, deposit_batch_id=batch.batch_id
        ).first()

        # The ruling: a locked batch does not stop a bounce.
        reconciliation.assert_bounce_allowed(member)

        # And the signed-off tie-out is exactly where it was.
        row = bankrec.DepositBatch.objects.get(pk=batch.batch_id)
        assert row.status == bankrec.BATCH_RECONCILED
        assert row.recorded_total == PE10_CHECK_TOTAL

        # A payment naming a batch that cannot be read still fails closed —
        # a broken reference was never the question the PO answered.
        member.deposit_batch_id = uuid.uuid4()
        with pytest.raises(PaymentRuleError, match="cannot be read"):
            reconciliation.assert_bounce_allowed(member)

        unlocked = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("64.00"),),
            method_code="cash",
            day=date(2026, 8, 9),
        )
        loose = models.Payment.objects.filter(
            tenant=brazos, deposit_batch_id=unlocked.batch_id
        ).first()
        reconciliation.assert_bounce_allowed(loose)  # no refusal — the ordinary path


def test_us_pay_023_tc4__unreconcile_is_the_only_way_back_and_it_reverses_the_cash(
    brazos, marcus, audit_rows
):
    """US-PAY-023 TC-4 — the audited state reversal, plus OQ-163's consequence.

    The batch returns to `unmatched` for rework and the whole trail survives
    (*"prior trail entries remain forever"*). And the cash comes back OUT of the
    books: leaving it would show CASH for a batch the product itself calls
    unmatched, and the next reconcile would realise the same money twice.
    Raised as OQ-163 for confirmation; implemented because the alternatives
    contradict rules already ruled.
    """
    with tenant_ctx(brazos):
        batch = _a_reconciled_batch(marcus, brazos)
        assert leg(journal_legs(brazos), "1000", "debit") == PE10_CHECK_TOTAL

        with pytest.raises(PaymentRuleError, match="needs a reason"):
            reconciliation.unreconcile_batch(
                actor=marcus, batch_id=batch.batch_id, reason="", posted_at=STATEMENT_AT
            )

        outcome = reconciliation.unreconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            reason="the bank line was another utility's deposit",
            posted_at=STATEMENT_AT,
        )
        assert outcome["status"] == bankrec.BATCH_UNMATCHED
        assert outcome["reversal_entry_id"]

        legs = journal_legs(brazos)
        # Cash nets to nil: the confirmation did not hold.
        assert leg(legs, "1000", "debit") - leg(legs, "1000", "credit") == Decimal("0")
        # And the money is back where it was — taken, not yet banked.
        assert leg(legs, "1010", "debit") - leg(legs, "1010", "credit") == PE10_CHECK_TOTAL

        events = list(
            bankrec.DepositBatchEvent.objects.filter(tenant=brazos).values_list("event", flat=True)
        )
        assert bankrec.EVENT_RECONCILED in events and bankrec.EVENT_UNRECONCILED in events
        assert len(audit_actions_for(audit_rows, reconciliation.AUDIT_BATCH_UNRECONCILED)) == 1


@requires_postgres
def test_us_pay_023_tc5__the_database_refuses_an_update_to_a_locked_batch(brazos, marcus):
    """US-PAY-023 TC-5 — the LOCK is a trigger, not a service-layer promise.

    A service check is bypassed by the first repair script anybody writes at
    2am. This case takes the same route that script would — a direct ORM UPDATE
    on `recorded_total` — and the database refuses it.

    PROVED RED: with `trg_deposit_batch_lock` dropped, the same UPDATE succeeds
    and the batch's signed-off total silently becomes 0.00.
    """
    from django.db import DatabaseError, connection, transaction

    with live_tenant_context(brazos.id):
        batch = _a_reconciled_batch(marcus, brazos)
        # `transaction.atomic()` around each refusal so the aborted statement
        # does not poison the rest of the test — the pattern US-PAY-001 TC-8
        # uses for the same reason.
        with pytest.raises(DatabaseError, match="RECONCILED and LOCKED"), transaction.atomic():
            bankrec.DepositBatch.objects.filter(pk=batch.batch_id).update(
                recorded_total=Decimal("0.00")
            )
        # Raw SQL for the DELETE: the ORM's PROTECT would refuse it first, and
        # what this asserts is the TRIGGER — the guard that stands against a
        # management command or a repair script, which is where a delete of a
        # signed-off batch would actually come from.
        with pytest.raises(DatabaseError, match="cannot be removed"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM deposit_batches WHERE id = %s", [batch.batch_id])
        with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
            bankrec.DepositBatchEvent.objects.filter(tenant=brazos).update(event="created")
        assert (
            bankrec.DepositBatch.objects.get(pk=batch.batch_id).recorded_total == PE10_CHECK_TOTAL
        ), "the day's signed-off total is exactly as it was reconciled"


@requires_postgres
def test_us_pay_020_tc5c__batch_membership_is_write_once_in_the_database(brazos, marcus):
    """The door `payments/0002` shut and migration 0005 opened — ONCE.

    A cleared payment may take a batch stamp (BR-PAY-025 needs it) and may never
    move between batches: a batch total is Σ its members, so a moved payment
    would rewrite two signed-off day totals at once.

    PROVED RED: with migration 0005's replacement function reverted to 0002's
    body, cutting a batch raises *"payment … is cleared and is append-only — no
    column may change"* and no batch can ever be cut at all.
    """
    from django.db import DatabaseError, transaction

    with live_tenant_context(brazos.id):
        first = a_batch(marcus, brazos, amounts=(Decimal("100.00"),), method_code="check")
        second = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("64.00"),),
            method_code="check",
            day=date(2026, 8, 9),
        )
        member = models.Payment.objects.filter(
            tenant=brazos, deposit_batch_id=first.batch_id
        ).first()
        with pytest.raises(DatabaseError, match="WRITE-ONCE"), transaction.atomic():
            models.Payment.objects.filter(pk=member.pk).update(deposit_batch_id=second.batch_id)
        assert models.Payment.objects.get(pk=member.pk).deposit_batch_id == uuid.UUID(
            first.batch_id
        ), "the payment is still in the batch it was banked in"


@pytest.mark.isolation
@requires_postgres
def test_us_pay_023_tc6__rls_keeps_one_tenants_bank_position_from_another(
    brazos, lonestar, marcus, erin, rls  # noqa: F811
):
    """US-PAY-023 TC-6 — a batch, its trail and its bank lines are one tenant's.

    Run under `sbh_rls_probe`, a NOLOGIN NOSUPERUSER NOBYPASSRLS role, because
    the app's own role is a superuser and superusers bypass RLS unconditionally
    — every assertion made on that connection would be vacuous.

    PROVED RED: with `deposit_batches_tenant_isolation` dropped from
    `db/rls_payments_w5.sql`, the probe reads Brazos Bend's batch from inside
    Lone Star Ridge's context and this case fails naming the leak.
    """
    from tests.isolation_helpers import assert_denied_without_context, assert_rls_scoped

    with live_tenant_context(lonestar.id):
        a_batch(erin, lonestar, amounts=(Decimal("64.00"),), method_code="check", service="water")

    with live_tenant_context(brazos.id):
        batch = a_batch(marcus, brazos, amounts=PE10_CHECKS, method_code="check")
        account = a_bank_account(brazos)
        reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")]),
            imported_at=STATEMENT_AT,
        )

    assert_rls_scoped(
        rls, "deposit_batches", owner=brazos, intruder=lonestar, owner_ids={batch.batch_id}
    )
    assert_rls_scoped(rls, "deposit_batch_events", owner=brazos, intruder=lonestar)
    assert_rls_scoped(rls, "bank_lines", owner=brazos, intruder=lonestar)
    assert_rls_scoped(rls, "bank_statement_imports", owner=brazos, intruder=lonestar)
    assert_rls_scoped(rls, "bank_accounts", owner=brazos, intruder=lonestar)
    # With NO tenant context at all the `::uuid` cast of '' fails and every one
    # of them is unreadable — deny-by-default, the B2 §3 template's own property.
    assert_denied_without_context(
        rls,
        "deposit_batches",
        "deposit_batch_events",
        "bank_lines",
        "bank_statement_imports",
        "bank_accounts",
        "bank_rec_resolutions",
    )


# ── shared fixture for the locked-batch cases ───────────────────────────────
def _a_reconciled_batch(actor, tenant):
    """PE-10's check batch, matched to an exact bank line and reconciled."""
    batch = a_batch(actor, tenant, amounts=PE10_CHECKS, method_code="check")
    account = a_bank_account(tenant)
    reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=account.pk,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 11),
        payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "471.39")]),
        imported_at=STATEMENT_AT,
    )
    reconciliation.reconcile_batch(actor=actor, batch_id=batch.batch_id, posted_at=STATEMENT_AT)
    return batch


# ── the file kernel, on its own (pure — no database) ────────────────────────
def test_us_pay_021_tc1b__the_file_kernel_reads_money_as_decimal_and_keys_the_file():
    """`lockbox.py` — CSV in, `Decimal` out, and a stable 🔒 file+tags key.

    The binary double nearest 4972.90 is 4972.8999999999996; a matcher comparing that against a
    `Decimal` batch total reports a difference of four ten-billionths of a cent
    to a human to explain (CLAUDE.md rule 2).
    """
    lines = lockbox.parse_bank_statement(
        b'Posting date,Description,Amount\n2026-08-04,CARD SETTLEMENT,"4,972.90"\n'
        b"2026-08-05,BANK FEE,(5.00)\n"
    )
    assert [line.amount for line in lines] == [Decimal("4972.90"), Decimal("-5.00")]
    assert all(isinstance(line.amount, Decimal) for line in lines)
    assert lines[0].posted_on == date(2026, 8, 4)

    tags = {
        "bank_account_id": "b0a1",
        "period_start": date(2026, 8, 1),
        "period_end": date(2026, 8, 6),
    }
    assert lockbox.statement_tag_fingerprint(tags) == lockbox.statement_tag_fingerprint(
        dict(reversed(list(tags.items())))
    ), "the key is order-independent — dict ordering must not change an idempotency key"
    assert lockbox.statement_tag_fingerprint(tags) != lockbox.statement_tag_fingerprint(
        {**tags, "period_end": date(2026, 8, 7)}
    )


def test_us_pay_020_tc1b__the_dep_code_carries_the_year_so_the_second_year_banks(brazos, marcus):
    """The batch code is year-bearing, and the anniversary is bankable.

    **This case USED to require a REFUSAL.** `DEP-{MMDD}-{METHOD}` carried no
    year, so 8 Aug 2027 rendered the same string as 8 Aug 2026 against a column
    B2 §2 makes UNIQUE per tenant — and the second year's takings could not be
    banked at all. The lane refused the collision by name rather than renumber a
    frozen figure, and raised OQ-162.

    **The PO closed it on 2026-08-12**, verbatim: *"Add the year + Date is
    important"*. So this case is REWRITTEN rather than deleted, the precedent
    the other reversals in this repo set — the question was answered, not
    quietly dropped, and the reversal stays readable to whoever comes next.

    What it now pins, and each of these would have been the old bug:

    * both years render DIFFERENT codes;
    * the 2027 batch is actually CUT, where it was previously refused;
    * PE-10's two codes carry their year (`DEP-260808-CHK` / `-CSH`), EP-PAY-06
      §4's shape being superseded by the same ruling;
    * **the MONEY did not move.** PE-10's 471.39 and 121.78 are ❄️ frozen and
      untouched by a change of label — which is the whole reason renaming was
      allowed and renumbering was not.
    """
    # ⚠ **RE-POINTED 2026-09-22 (`P0.6`) AT WHERE THE YEAR NOW LIVES.** This
    # block asserted `reconciliation.batch_code(day, method)`, a pure function
    # composing `DEP-{YY}{MM}{DD}-{METHOD}`. **That function is deleted.** Two
    # tills banking cheques on one day both rendered `DEP-260922-CHK` and the
    # second was refused by `uq_deposit_batches_code`, so the PO ruled the code
    # into Settings → Numbering (*"(b) Put it in Settings today —
    # DEP-260922-0001 — Settings → Numbering, like every other number"*) and
    # the TENDER left it.
    #
    # **THE 2026-08-12 RULING THIS TEST EXISTS FOR IS UNTOUCHED AND IS STILL
    # ASSERTED** — *"Add the year + Date is important"*. The year and the date
    # are both still in the code; they are now carried by the SEEDED SERIES
    # FORMAT rather than by a string this module builds, so that is what is
    # pinned. The anniversary defect (`DEF-066`) stays closed either way, and
    # the assertion below is the one that says so.
    dep_format = core_numbering.SERIES_CATALOG[core_numbering.DEPOSIT_BATCH][1][0]
    assert dep_format == "DEP-{YY}{MM}{DD}-{0000}"
    core_numbering.validate_format(dep_format)

    # The anniversary is a DIFFERENT code — the defect, stated as an assertion.
    assert core_numbering.render(dep_format, 7, date(2026, 8, 8)) != core_numbering.render(
        dep_format, 8, date(2027, 8, 8)
    )
    assert core_numbering.render(dep_format, 1, date(2026, 9, 22)) == "DEP-260922-0001"
    assert core_numbering.render(dep_format, 7, date(2027, 8, 8)) == "DEP-270808-0007"

    # ⚠ **AND THE PAD DOES NOT RUN OUT, WHICH A DECISION-LOG JUDGMENT CLAIMED
    # IT WOULD.** `render`'s own docstring: *"a counter that outgrows its pad
    # keeps all its digits (never truncated)"*, and `will_overflow` is a
    # Settings-screen WARNING, *"never a refusal"*. Asserted so that the claim
    # is checked by a machine rather than remembered.
    assert core_numbering.render(dep_format, 10000, date(2026, 9, 22)) == "DEP-260922-10000"
    assert core_numbering.will_overflow(dep_format, 10000) is True

    # PE-10's two codes are ❄️ frozen LABELS on rows banked before the re-key
    # and keep their composed shape for ever (hard rule 4). Nothing can produce
    # them any more, which is why they are written out literally.
    assert PE10_CHECK_CODE == "DEP-260808-CHK"
    assert PE10_CASH_CODE == "DEP-260808-CSH"

    with tenant_ctx(brazos):
        a_batch(marcus, brazos, amounts=(Decimal("100.00"),), method_code="check")
        a_cleared_payment(
            marcus,
            brazos,
            amount=Decimal("50.00"),
            method_code="check",
            posted_at=datetime(2027, 8, 8, 10, 30, tzinfo=UTC),
        )
        cut = reconciliation.cut_deposit_batches(
            actor=marcus, day=date(2027, 8, 8), occurred_at=POSTED_AT
        )

    # The code is allocated since `P0.6`, so what is asserted is what the
    # 2026-08-12 ruling guarantees: the SECOND YEAR BANKS, and its code carries
    # `270808` where the first year's carried `260808`.
    # CR-186-BRC10 — the 2027 payment joined its day's batch at posting.
    with tenant_ctx(brazos):
        second_year = the_days_batches(brazos, date(2027, 8, 8))
    assert cut.payments_batched == 0
    assert len(second_year) == 1 and second_year[0].code.startswith("DEP-270808-"), (
        "the second year's money is banked. Before the ruling this raised "
        "PaymentRuleError naming OQ-162, and every tenant would have hit it on the "
        "first anniversary of its go-live date."
    )

    # The ruling's second half: the date is a COLUMN, never decoded from the label.
    assert second_year[0].deposited_on == date(2027, 8, 8)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@b6e4c19 (the five EP-PAY-06 sources — 04-docs/02-decisions/02-database-design-brief.md §2 + Addenda r12 #10/#13/#17 + r14 #1 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020..023 · 08-payments/02-business-rules.md BR-PAY-004/019/021/025/028/035/039/040 · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7 PE-10/PE-11; plus the two PO rulings of 2026-08-11 in 12-governance/02-decision-log.md)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API — nothing serves S37–S40; REPORTED) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every guard driven RED first (hard-won law 7) — the five proofs are quoted verbatim in 12-governance/09-human-review-ledger.md
# exceptions: the DATABASE cases (the lock, the write-once membership door, RLS)
#         carry `requires_postgres` and SKIP on the SQLite developer database
#         rather than passing vacuously; each has a service-layer twin that runs
#         everywhere
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
