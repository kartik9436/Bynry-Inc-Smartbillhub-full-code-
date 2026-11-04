# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-019 (the budget bill: actuals computed monthly, variance on
#           every bill, settle-up month)   Screens: S30
# Rules:    BR-BIL-017 (actuals every month; the customer pays the LEVEL;
#           variance accumulates and shows on every bill; annual settle-up) ·
#           BR-BIL-072 (THE LEVEL IS WHAT IS DUE — PO 2026-08-11, OQ-140
#           CLOSED) · BR-BIL-011 (the monthly posting is the ACTUALS posting) ·
#           B4.2 (the settle-up line is non-taxable AR-timing) · BR-BIL-001 as
#           amended 2026-08-11 (no late fee under a $25.00 overdue balance) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4's reasoning (the
#           variance derives from APPEND-ONLY events) · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""US-BIL-019 §3 — and the live defect the PO's ruling of 2026-08-11 closes.

`tc1b` is the one to read first. It puts a real budget customer through the
real late-fee assessment: actual **292.87**, level **242**, the customer pays
**242** on time, and NOTHING is overdue and no fee is charged. The same test
states, in the same place, what the product did before the ruling — because the
defect is not a crash, it is a customer who paid what they were asked for and
was chased for $50.87 anyway.

Everything else here is WE-8's frozen chain and the settle-up.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import budget, budget_service, late_fee, models, selectors
from apps.ledger import models as ledger_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db

# ❄️ WE-8 / GT-24 verbatim.
LEVEL = Decimal("242")
JULY = Decimal("292.87")
AUGUST = Decimal("231.40")
SEPTEMBER = Decimal("198.75")
CHAIN = (Decimal("-50.87"), Decimal("-40.27"), Decimal("2.98"))

JUL = date(2026, 7, 1)
AUG = date(2026, 8, 1)
SEP = date(2026, 9, 1)
APRIL = date(2027, 4, 1)  # the tenant's settle-up month (BR-BIL-017 ratifies none)


def enrolled(actor, account, *, settle_up_month=None):
    status = budget_service.enroll(
        actor=actor,
        account_id=account.id,
        trailing_actuals=(Decimal("2904"),),
        months_of_history=12,
        plan_offers_budget=True,
        currency="USD",
        on_date=date(2026, 6, 28),
    )
    if settle_up_month is not None:
        # Set on the ACCOUNT, not on the tenant: BR-BIL-017 copies the month at
        # enrolment so a tenant moving it mid-year cannot move it for an account
        # already part-way through one (BR-TEN-043's config-forward law).
        status.settle_up_month = settle_up_month
        status.save(update_fields=["settle_up_month"])
    return status


def test_us_bil_019_tc1__the_bill_is_full_actuals_and_the_customer_owes_the_level(brazos, marcus):
    """Actual **292.87** · level **242** · variance **−50.87** — all three, and
    the amount to pay is the level (PO 2026-08-11, *"Level is due"*)."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        enrolled(marcus, account)

        facts = budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)

        assert facts.actual == JULY  # the bill is still full actuals…
        assert facts.level == LEVEL  # …and this is what we asked for
        assert facts.variance_movement == CHAIN[0]
        assert facts.running_balance == CHAIN[0]
        assert facts.amount_due == Decimal("242.00")

        # BR-BIL-011: the level is a collection schedule, never a price. The
        # ledger side of this month is the ACTUAL and nothing here moved it.
        assert facts.amount_due != facts.actual


def test_us_bil_019_tc1b__paying_the_level_settles_the_month_in_full(brazos, marcus):
    """**THE LIVE DEFECT (DEF-062), closed.** PO 2026-08-11: *"Level is due"*.

    The customer is billed 292.87, asked for 242, and pays 242 on the due date.
    Run through billing's OWN late-fee assessment — not a paraphrase of it —
    the overdue portion is **0.00** and the fee is **0.00**: they do not age,
    they earn no fee, and they never enter the collection ladder.

    WHAT THIS PRODUCT DID BEFORE THE RULING, asserted here so the defect is
    visible rather than described: measured against the ACTUAL bill the same
    customer is 50.87 short, which is over BR-BIL-001's $25.00 floor, so they
    earn `max($5, 1.5% × 50.87)` = **$5.00** and a place in the ladder. Both
    figures are in this test on purpose — one is the rule, the other is what it
    replaced.
    """
    due_date = date(2026, 7, 22)
    paid = late_fee.PaymentReceipt(
        amount=Decimal("242.00"), arrived_on=due_date, recorded_on=due_date
    )
    fee_terms = dict(
        percent=Decimal("0.015"),
        minimum=Decimal("5"),
        due_date=due_date,
        as_of=date(2026, 8, 5),
        grace_days=5,
        grace_mode=late_fee.GRACE_CALENDAR,
    )

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        enrolled(marcus, account)
        facts = budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)

        # THE RULE. What is due is the level, and the level was paid.
        overdue = late_fee.overdue_portion(
            amount_billed=facts.amount_due,
            payments=(paid,),
            due_date=due_date,
            assessed_on=date(2026, 8, 5),
        )
        assert overdue == Decimal("0.00")
        assert late_fee.assess_late_fee(overdue_amount=overdue, **fee_terms) == Decimal("0.00")

        # WHAT IT REPLACED. Measured against the actual, the same customer is
        # 50.87 short and earns the $5.00 minimum — over the $25.00 floor, so
        # the 2026-08-11 threshold does not save them either.
        was_overdue = late_fee.overdue_portion(
            amount_billed=facts.actual,
            payments=(paid,),
            due_date=due_date,
            assessed_on=date(2026, 8, 5),
        )
        assert was_overdue == Decimal("50.87")
        assert late_fee.assess_late_fee(overdue_amount=was_overdue, **fee_terms) == Decimal("5.00")


def test_us_bil_019_tc2__the_frozen_chain_lands_on_every_bill(brazos, marcus):
    """❄️ WE-8: −50.87 → −40.27 → **+2.98**, with all three columns each month
    and the level due on every one of them."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enrolled(marcus, account)

        running = []
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG), (SEPTEMBER, SEP)):
            facts = budget_service.record_bill(
                account_id=account.id, actual=actual, on_date=on_date
            )
            running.append(facts.running_balance)
            assert facts.amount_due == Decimal("242.00")

        assert tuple(running) == CHAIN
        assert tuple(f for f in (Decimal("10.60"), Decimal("43.25"))) == (
            budget.variance_movement(level=LEVEL, actual=AUGUST),
            budget.variance_movement(level=LEVEL, actual=SEPTEMBER),
        )

        # The cached balance and its derivation agree — a cache nobody checks is
        # a second source of truth waiting to disagree.
        status.refresh_from_db()
        assert status.variance_balance == CHAIN[-1]
        assert budget_service.recompute_balance(status) == CHAIN[-1]


def test_us_bil_019_tc3__the_settle_up_credits_a_positive_balance_and_resets_it(
    brazos, marcus, audit_rows
):
    """Settle-up month with balance **+2.98** → credits 2.98, non-taxable,
    balance resets 0.00, audited — and the level is still due beside it, so
    **239.02** is what the customer owes that month."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enrolled(marcus, account, settle_up_month=APRIL.month)
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG)):
            budget_service.record_bill(account_id=account.id, actual=actual, on_date=on_date)

        facts = budget_service.record_bill(account_id=account.id, actual=SEPTEMBER, on_date=APRIL)

        assert facts.settle_up_direction == budget.SETTLE_CREDIT
        assert facts.settle_up_amount == Decimal("2.98")
        assert facts.amount_due == Decimal("239.02")  # 242.00 − 2.98
        assert facts.running_balance == Decimal("0.00")

        status.refresh_from_db()
        assert status.variance_balance == Decimal("0.00")
        assert budget_service.recompute_balance(status) == Decimal("0.00")

        settled = [row for row in audit_rows if row["action"] == "budget.settled"]
        assert len(settled) == 1
        assert settled[0]["after"]["direction"] == budget.SETTLE_CREDIT
        assert settled[0]["after"]["amount"] == "2.98"
        assert settled[0]["after"]["taxable"] is False


def test_us_bil_019_tc4__a_negative_balance_collects_the_same_line_the_other_way(brazos, marcus):
    """Fixture −40.27 → **collects 40.27**; same line class, opposite sign, so
    the customer owes **282.27** that month."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1091")
        enrolled(marcus, account, settle_up_month=APRIL.month)
        budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)

        facts = budget_service.record_bill(account_id=account.id, actual=AUGUST, on_date=APRIL)
        assert facts.settle_up_direction == budget.SETTLE_COLLECT
        assert facts.settle_up_amount == Decimal("40.27")
        assert facts.amount_due == Decimal("282.27")  # 242.00 + 40.27
        assert facts.running_balance == Decimal("0.00")


def test_us_bil_019_tc5__the_settle_up_line_cannot_be_taxable_or_reach_a_revenue_gl(brazos, marcus):
    """B4.2 / WE-8: revenue and tax recognised MONTHLY on the actuals, so the
    settle-up is AR-timing and never taxed.

    Two halves. The taxable flag is not a field a caller sets — `SettleUp`
    is frozen at `SETTLE_UP_TAXABLE`, so "forged as taxable" is a thing the type
    refuses. And the GL side REFUSES BY NAME.

    **The refusal changed meaning on 2026-08-15 and RESOLVED on 2026-08-18, and
    the test moved both times.** It began as `NotImplementedError("OQ-142")`.
    The PO answered that (*"Create seperate account"*), turning the stub into a
    refusal waiting on a signature. Then the PO ruled the account itself on
    2026-08-17 — CR-010 B-8, verbatim: *"8 - A ✅ 4180 "Budget billing
    variance", revenue, signed=False (the 4160/4170 precedent)"* — so the seed
    chart now carries 4180 with the `budget_variance` designation and the GL
    half RESOLVES to it. Neither declined option was touched: the money lands
    in 4180, never in receivables and never in `unbilled_ar`, which is what the
    designation assertion below pins.
    """
    settlement = budget.settle_up(balance=Decimal("2.98"))
    assert settlement.taxable is False
    with pytest.raises(AttributeError):
        settlement.taxable = True  # frozen dataclass — the flag is not settable

    with tenant_ctx(brazos):
        # CR-010 B-8: the settle-up's GL home is the tenant's own 4180 — the
        # designation resolves BY NAME, never by number, so a tenant who
        # renumbers it keeps their pointer.
        account_id = budget.settle_up_gl_account(settlement=settlement)
        home = ledger_models.LedgerAccount.objects.get(pk=account_id)
        assert home.designation == "budget_variance"
        assert (home.code, home.name, home.type) == (
            "4180",
            "Budget billing variance",
            "revenue",
        )
        # ...and neither declined option was quietly picked.
        assert home.designation not in ("accounts_receivable", "unbilled_ar")

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enrolled(marcus, account, settle_up_month=APRIL.month)
        budget_service.record_bill(account_id=account.id, actual=JULY, on_date=APRIL)
        # The settle-up moved NO invoice line and no total: the bill stays full
        # actuals, and nothing tax-bearing was written.
        assert models.InvoiceLine.objects.count() == 0


def test_us_bil_019_tc6__the_balance_derives_from_append_only_events(brazos, marcus):
    """A balance that can be edited is not a balance.

    `recompute_balance` re-derives the figure from the event rows, so a status
    row whose cache was tampered with disagrees with its own history and the
    disagreement is detectable. On Postgres migration 0013's trigger refuses the
    UPDATE outright; this assertion holds on the sqlite tier too, which is the
    database a developer actually runs.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        status = enrolled(marcus, account)
        budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)

        events = list(budget_service.event_queryset().filter(budget_status=status))
        assert [e.event for e in events] == [
            models.BUDGET_EVENT_ENROLLED,
            models.BUDGET_EVENT_BILLED,
        ]

        # Tamper with the cache only.
        models.AccountBudgetStatus.objects.filter(pk=status.pk).update(
            variance_balance=Decimal("0")
        )
        status.refresh_from_db()
        assert status.variance_balance == Decimal("0")
        # The derivation still says what actually happened.
        assert budget_service.recompute_balance(status) == CHAIN[0]


def test_us_bil_019_tc6b__a_redrafted_bill_never_moves_the_variance_twice(brazos, marcus):
    """A run that re-drafts a bill (BR-BIL-023) replays this path. Hard rule 6's
    shape: the second call reports the same facts and writes no second event."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        status = enrolled(marcus, account)
        invoice = an_invoice(brazos, account)

        first = budget_service.record_bill(
            account_id=account.id, actual=JULY, on_date=JUL, invoice=invoice
        )
        second = budget_service.record_bill(
            account_id=account.id, actual=JULY, on_date=JUL, invoice=invoice
        )

        assert first.running_balance == second.running_balance == CHAIN[0]
        assert (
            budget_service.event_queryset()
            .filter(budget_status=status, event=models.BUDGET_EVENT_BILLED)
            .count()
            == 1
        )


def test_us_bil_019_tc6c__a_non_budget_account_is_untouched(brazos, marcus):
    """The pipeline calls this for EVERY account. One that is not enrolled gets
    None, no row, and a bill identical to the one it always had."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        assert budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL) is None
        assert budget_service.event_queryset().count() == 0

        invoice = an_invoice(brazos, account)
        # …and `amount_due_for` answers with the bill's own total, unchanged.
        assert selectors.amount_due_for(invoice) == invoice.total


def test_us_bil_019_tc6d__a_budget_final_bill_is_the_level_only(brazos, marcus):
    """**PO ruling 2026-08-12, verbatim: _"Level only"_ — OQ-164 CLOSED.**

    ❄️ WE-8's level is **242** and its variance balance is **−40.27** (the
    customer has used more than they have paid for). The final bill asks for
    **242.00**, not 282.27 — the accumulated variance does not ride the last
    level payment, so a customer disputing their closing bill can tell their
    month apart from a year of under-collection.

    This test asserted the REFUSAL until the ruling landed, and the refusal was
    right: it is real money on a customer's LAST bill, where there is no next
    month in which to fix it.
    """
    assert budget.amount_due(level=LEVEL, actual=JULY, bill_type="final") == LEVEL

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enrolled(marcus, account)
        due = budget_service.record_bill(
            account_id=account.id, actual=JULY, on_date=JUL, bill_type="final"
        )
        assert due is not None


def test_us_bil_019_tc1c__stage_six_stamps_the_block_onto_a_real_draft(brazos, marcus):
    """**BUILT IS NOT WIRED (hard-won law 2), so this runs the REAL pipeline.**

    Stage 1 → stage 2 → rating's priced pass → stage 6, on GT-1's frozen fixture
    ($108.88), for an account enrolled at a level of $242. The draft comes back
    with the budget block IN its `bill_payload`, and `selectors.amount_due_for`
    reads the level off the bill rather than off today's status — which is what
    makes a re-level in January unable to rewrite what a July bill asked for.

    The bill itself is untouched: `invoice.total` is still GT-1's 108.88, every
    line is still there, and the ACTUALS are what the ledger will see.
    """
    from tests.test_us_bil_029_assemble import assemble, billing_data
    from tests.test_w3_billing_models import a_run

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        enrolled(marcus, account)
        run = a_run(brazos)
        invoice = assemble(brazos, account, run, billing_data(account))

        assert invoice.total == Decimal("108.880000")  # GT-1, untouched
        block = invoice.bill_payload["budget"]
        assert block["level"] == "242.000000"
        assert block["actual"] == "108.88"
        assert block["variance_movement"] == "133.12"  # 242 − 108.88
        assert block["variance_balance"] == "133.12"
        assert block["amount_due"] == "242.00"

        # The published read agrees, and it reads the BILL, not the status.
        assert selectors.amount_due_for(invoice) == Decimal("242.00")
        # Six decimals like every other money key in the A19 summary
        # (`current_charges` renders "247.870000") — the serve is consistent with
        # its neighbours rather than with this module's internal 2dp.
        assert selectors.invoice_detail(invoice.id)["summary"]["amount_due"] == "242.000000"
        assert selectors.invoice_detail(invoice.id)["budget"]["level"] == "242.000000"


@pytest.mark.isolation
def test_us_bil_019_tc7__budget_bills_never_cross_a_tenant(brazos, marcus, lonestar, erin):
    """Lone Star Ridge's own levels and balances only (RLS)."""
    with tenant_ctx(lonestar):
        lone = an_account(lonestar, erin, account_no="LSR-1", service="water")
        budget_service.enroll(
            actor=erin,
            account_id=lone.id,
            trailing_actuals=(Decimal("2160"),),
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=date(2026, 6, 28),
        )
        lone_facts = budget_service.record_bill(
            account_id=lone.id, actual=Decimal("200.00"), on_date=JUL
        )
        assert lone_facts.level == Decimal("180")  # 2,160 ÷ 12
        assert lone_facts.amount_due == Decimal("180.00")

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enrolled(marcus, account)
        facts = budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)
        assert facts.level == LEVEL
        assert budget_service.status_queryset().count() == 1
        assert budget_service.event_queryset().count() == 2


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-019@e9d5a48 (05-golden-tests.md + EP-BIL-05-budget-billing.md + 07-billing/02-business-rules.md + 07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's Budget Bills tab has no endpoint; REPORTED) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) `tc1b` reaches into apps/billing/late_fee.py READ-ONLY — the
#         $25.00 floor and the arrival-date rule are that module's and are not
#         restated here; the test passes `amount_due` where the product would.
#         (2) The settle-up POSTING is not asserted because it does not exist:
#         `settle_up_gl_account` raises OQ-142 and tc5 asserts the refusal.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
