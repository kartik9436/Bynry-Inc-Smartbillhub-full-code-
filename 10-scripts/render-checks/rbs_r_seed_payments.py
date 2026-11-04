#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-RBS-027 · US-RBS-029 · US-RBS-035 · US-RBS-036 (EP-RBS-05) —
#          CR-075 wave R′, the payments half. The part a browser cannot do.
# Rules:   CLAUDE.md hard rule 1 (every write inside one tenant's context) ·
#          hard rule 2 (money to 4 decimals, never a float) · hard rule 8 (an
#          address lives on `premises` and nowhere else) · `BR-RBS-014` (a
#          SAMPLE record is never acted on — which is why every row here is
#          NOT sample) · `BR-PAY-015` (autopay v1 is capture-INTENT) ·
#          `BR-PAY-016` (the plan figures) · `BR-CUS-050` / ❄️ `GT-61` (the
#          deposit interest rate and its arithmetic) · `BR-TEN-043` (the
#          business day is an argument, never a clock)
# Tests:   the walkthrough itself — 10-scripts/render-checks/rbs-r-money-runbooks.mjs
# ───────────────────────────────────────────────────────
"""Four runbooks' worth of real rows on a real tenant, then four real runs.

WHY THIS EXISTS, AND WHY IT IS THIS WAVE'S WORK RATHER THAN A PREREQUISITE
---------------------------------------------------------------------------
**Every account on the seeded demo tenant carries `is_sample=True` — all 72 of
them.** `BR-RBS-014` makes a sample record something an Action never touches, in
any tenant, at any time, so all four of this wave's runbooks correctly resolve a
scope and then correctly guard every member of it. Measured on `brazosbend`
before this fixture ran:

    deposit_review      2 deposits in scope · 2 guarded · 0 records
    autopay_prenotice   0 subjects (6 accounts on autopay, 0 debits scheduled)
    payment_plans       1 plan in scope  · 1 guarded · 0 records
    returned_payments   STOPPED at step 1 — and that one is CORRECT for ever

A walkthrough over those four screens proves the guard and nothing else. Wave `M`
hit exactly this and answered it the same way (*"a month of dry runs over an
empty board is evidence of nothing at all"*), so the rows are built here and every
figure the lane reports is read off them.

⚠ **RUNBOOK 26 IS SEEDED WITH NOTHING, ON PURPOSE, AND ITS SCREEN IS THE MOST
IMPORTANT ONE THIS FIXTURE PRODUCES.** There is no returns feed on this product,
no column for a bank's return code, and no port that reverses a payment — three
absences, `OQ-RBS-1741`. The Product Owner ruled on 2026-09-06 that a run which
finds no connection *"can stop the job saying APi or conenct not available; that
is a valid case and state for us"*, so what a real utility meets on day one is
the STOP, and only a browser can say whether it reads as a designed answer or as
a failure.

WHAT IS SEEDED, AND WHY EACH ROW IS THERE
-------------------------------------------
Six accounts, all `is_sample=False`, each one a branch the built runbook can
actually reach. Where a card's group has no reachable branch that is a FINDING
for the lane report, not a reason to reshape the fixture until the numbers agree.

    account   what it is                          what the run should say
    ────────────────────────────────────────────────────────────────────────
    R-0001    deposit held 3 years · paid on      **credit** (an open bill to
              time · one open bill                draw it against)
    R-0002    deposit held 3 years · account      **refund** · *Account closed*
              CLOSED
    R-0003    deposit $1,000 held 3 years ·       **refund** · *Over the
              paid on time                        $250.00 limit*
    R-0004    deposit held 2 months               not in scope — too recent
    R-0005    deposit held 3 years · a bill       **not eligible** · a bill was
              paid AFTER its due date             paid late
    R-0006    deposit held 3 years · a bill       GUARDED — past due this
              open and overdue TODAY              morning, and no record row
    ────────────────────────────────────────────────────────────────────────
    R-0001    autopay · a debit due in 4 days,    **notice queued**
              amount MOVED since the last one
    R-0003    autopay · a debit due in 6 days,    **no notice needed** — a fixed
              same amount as last time            amount needs none
    ────────────────────────────────────────────────────────────────────────
    R-0001    a plan with every instalment met    **in good standing**
    R-0002    a plan with ONE instalment missed   **warned**
    R-0005    a plan with TWO missed              **due to end** — and a person
                                                   ends it

⚠ **AND THE TENANT'S DEPOSIT INTEREST RATE IS SET TO 2.0%**, because it ships at
**0** and every accrual on a rate of zero is a real zero. ❄️ `GT-61` is
finance-signed at *$150 @ 2.0%, 89 months → $22.25*, so 2.0% is the rate the
frozen figure itself uses and putting it on this tenant is what lets a browser
read a non-zero interest tile at all. **The arithmetic is `customers`' and is
not reproduced here or in the runbook.**

⚠ **EVERY ROW IS WRITTEN THROUGH THE OWNING MODULE'S OWN PATH WHERE ONE
EXISTS.** The autopay intents go through `apps.payments.autopay
.record_intent_at_issue`, which is `BR-PAY-015`'s one write; the payment plans are
split the way the product splits them — `apps.customers.payment_plan
.build_schedule` computes the instalments (❄️ frozen as `GT-47`) and
`apps.payments.plans.propose_payment_plan` writes the rows, re-validating the
invariant rather than re-deriving the figures. Premises, units, accounts and bills are created
directly, exactly as `rbs_m_seed_ladder.py` does and for its reason: no service
in this product creates a whole utility from nothing.

⚠ **WHAT WOULD MAKE THIS FIXTURE PASS WRONGLY** (hard-won law 7, habit 2):

  * **Writing `is_sample=True` by accident**, which is the default nowhere but is
    what every existing row on this tenant carries. Every run below asserts a
    NON-EMPTY record list, so a fixture that produced only guarded subjects fails
    here rather than producing four thin green screens.
  * **A deposit account with no bills**, which would be *unproven* rather than
    *on time* — the runbook's own three-valued verdict, and the reason two of the
    five real deposits on this tenant are held. Every eligible account here is
    given a PAID bill, so *on time* is a fact rather than an absence.
  * **Counting outside the tenant context**, where RLS `FORCE` shows a session
    with the default marker nothing at all. Every write and every count below is
    inside `tenant_context`.
  * **Reporting the stop when the stop is a MISTAKE.** Runbook 26 is EXPECTED to
    stop; the other three are expected NOT to, and this script fails if any of
    them does.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3.12 10-scripts/render-checks/rbs_r_seed_payments.py --tenant brazosbend

It prints `SMOKE_DEPOSIT_RUN_ID`, `SMOKE_AUTOPAY_RUN_ID`, `SMOKE_PLANS_RUN_ID`
and `SMOKE_RETURNS_RUN_ID` for the browser check.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import sys
from decimal import Decimal

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.billing import models as billing_models  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.payments import models as payment_models  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.definitions import (  # noqa: E402
    autopay_prenotice,
    deposit_review,
    payment_plans,
    returned_payments,
)
from apps.runbooks.engine import executor  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: Every row this fixture writes carries it, so a re-run can find its own work
#: and a reader can tell wave R′'s rows from wave M's at a glance.
PREFIX = "R-"

#: ❄️ `GT-61`'s own rate. See the module docstring: the tenant ships at 0, every
#: accrual on 0 is a real zero, and the frozen figure is stated at 2.0%.
INTEREST_RATE = Decimal("2.000000")

#: `RB-115`'s own limit, and the card's own sentence — *Over the $250.00 limit*.
REFUND_LIMIT = Decimal("250.0000")

#: Money literals. Every one is a `Decimal` from a STRING (hard rule 2): a float
#: that has been through JSON is not money, and the column is a lawful container
#: for a four-decimal value rather than a check on it.
DEPOSIT_ORDINARY = Decimal("150.0000")
DEPOSIT_LARGE = Decimal("1000.0000")
BILL_SMALL = Decimal("84.6000")
BILL_ORDINARY = Decimal("184.2000")
PLAN_TOTAL = Decimal("657.4700")
PLAN_DOWN = Decimal("50.0000")


def fail(message: str) -> None:
    print(f"⛔ {message}", file=sys.stderr)
    raise SystemExit(2)


def lookups(tenant):
    """The status rows every account needs, chosen BY BEHAVIOUR CLASS.

    `BR-CUS-055` — billing keys off the CLASS, never the label — so a tenant that
    renamed *Active* still gets billable accounts here rather than a fixture of
    closed ones that no runbook would ever look at, silently.
    """
    live = (
        customer_models.AccountStatus.objects.filter(
            tenant_id=tenant.id, behavior_class="billable"
        )
        .order_by("id")
        .first()
    )
    closed = (
        customer_models.AccountStatus.objects.filter(
            tenant_id=tenant.id, behavior_class="terminal"
        )
        .order_by("id")
        .first()
    )
    if live is None or closed is None:
        fail(
            "this tenant has no 'billable' and 'terminal' account statuses, so a deposit "
            "review could not tell an open account from a closed one. Seed the lookups first."
        )
    account_type = customer_models.AccountType.objects.order_by("id").first()
    if account_type is None:
        fail("no account types exist — the platform catalogue has not been seeded.")
    return live, closed, account_type


def premises_for(tenant, seq: int):
    """One premises per account — hard rule 8, the ONE home of an address."""
    return metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"{PREFIX}P{seq:04d}",
        address_line=f"{2200 + seq} Cane Island Parkway",
        city="Katy",
        state="TX",
        postal_code="77494",
    )


def unit_for(tenant, premises, seq: int):
    return metering_models.Unit.objects.create(
        tenant=tenant,
        premises=premises,
        unit_no=f"{PREFIX}U{seq:04d}",
        label="1",
        unit_type="residential",
    )


def account_for(tenant, *, seq, status, account_type, unit, premises, deposit, received_on, autopay):
    """One account. ⚠ **`is_sample=False`, which is the whole point of it.**

    Every one of the tenant's own 72 accounts is `is_sample=True`, and
    `BR-RBS-014` makes a sample record something an Action never touches. A
    fixture that inherited that default would produce four screens showing a
    guard working and nothing else.
    """
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        premises_id=premises.id,
        account_no=f"{PREFIX}{seq:04d}",
        status=status,
        account_type=account_type,
        kind="regular",
        currency="USD",
        deposit_on_file=deposit,
        deposit_received_on=received_on,
        autopay=autopay,
        is_sample=False,
        opened_at=None,
    )


def bill_for(tenant, account, *, seq, total: Decimal, due_on: dt.date):
    """One ISSUED bill, dated. Money is a `Decimal` and never a float."""
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=f"{PREFIX}B{seq:05d}",
        status=billing_models.INVOICE_ISSUED,
        service_date=due_on - dt.timedelta(days=20),
        period_start=due_on - dt.timedelta(days=50),
        period_end=due_on - dt.timedelta(days=20),
        due_date=due_on,
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        issued_at=dt.datetime(due_on.year, due_on.month, due_on.day, 9, 0, tzinfo=dt.timezone.utc)
        - dt.timedelta(days=20),
    )


def pay(tenant, account, invoice, *, seq, amount: Decimal, posted_on: dt.date):
    """A payment that MET a bill, with its allocation.

    ⚠ **`posted_at` IS WHAT DECIDES ON-TIME** (`BR-PAY-021`): a cheque posted on
    the due date and cleared three days later is ON TIME, and the runbook reads
    the posting date for exactly that reason. So this fixture controls lateness
    by moving `posted_on` and never by moving a clearing date — a fixture that
    used the wrong column would prove the runbook read the wrong one too.
    """
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=f"{PREFIX}PM{seq:05d}",
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=dt.datetime(
            posted_on.year, posted_on.month, posted_on.day, 10, 0, tzinfo=dt.timezone.utc
        ),
    )
    payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=invoice, amount=amount
    )
    return payment


def set_interest_rate(tenant) -> Decimal | None:
    """Put ❄️ `GT-61`'s own 2.0% on this tenant — through tenancy's own row.

    ⚠ **THE RATE IS SETTINGS' AND THE ARITHMETIC IS `customers`'.** This writes
    the tenant's `deposit_interest_rate_annual` column and nothing else; the
    figure the screen shows is `apps/customers/deposit_interest.py`'s, which is
    asserted against the frozen $22.25 in its own test. A fixture that computed
    an interest figure would be a second implementation of a finance-signed rule.
    """
    row = tenancy_models.TenantSettings.objects.filter(tenant_id=tenant.id).first()
    if row is None:
        print("── ⚠ this tenant has no settings row; the interest rate is left unset")
        return None
    before = row.deposit_interest_rate_annual
    if Decimal(str(before or 0)) == INTEREST_RATE:
        return INTEREST_RATE
    row.deposit_interest_rate_annual = INTEREST_RATE
    row.save(update_fields=["deposit_interest_rate_annual"])
    print(f"── deposit interest rate {before} → {INTEREST_RATE}% (❄️ GT-61's own rate)")
    return INTEREST_RATE


def build(tenant, *, as_of: dt.date) -> dict[str, object]:
    """Six accounts, their bills, their payments, two intents and three plans.

    Every date is measured from `as_of`, which is an ARGUMENT (`BR-TEN-043`): a
    fixture that read a wall clock would produce a different board every day and
    no walkthrough could assert a figure.
    """
    live, closed, account_type = lookups(tenant)
    long_ago = as_of - dt.timedelta(days=1100)  # three years — past any period
    recently = as_of - dt.timedelta(days=60)  # two months — too recent

    made: dict[str, object] = {
        row.account_no: row
        for row in customer_models.Account.objects.filter(
            tenant=tenant, account_no__startswith=PREFIX
        )
    }
    plan_rows = []
    for seq, (deposit, received, status, autopay) in enumerate(
        [
            (DEPOSIT_ORDINARY, long_ago, live, True),  # R-0001 credit
            (DEPOSIT_ORDINARY, long_ago, closed, False),  # R-0002 refund · closed
            (DEPOSIT_LARGE, long_ago, live, True),  # R-0003 refund · over the limit
            (DEPOSIT_ORDINARY, recently, live, False),  # R-0004 too recent
            (DEPOSIT_ORDINARY, long_ago, live, False),  # R-0005 paid late
            (DEPOSIT_ORDINARY, long_ago, live, False),  # R-0006 past due today
        ],
        start=1,
    ):
        if f"{PREFIX}{seq:04d}" in made:
            # ⚠ **EACH SECTION GUARDS ITSELF RATHER THAN THE WHOLE BUILD.** The
            # first draft skipped everything once ANY wave R′ account existed,
            # so a run that died between the accounts and the intents left a
            # fixture that could never finish itself — and the browser check
            # would have walked an autopay screen with nothing on it and called
            # the runbook quiet. That is the shape hard-won law 7's second habit
            # asks about, and it happened on this script's first execution.
            continue
        premises = premises_for(tenant, seq)
        unit = unit_for(tenant, premises, seq)
        account = account_for(
            tenant,
            seq=seq,
            status=status,
            account_type=account_type,
            unit=unit,
            premises=premises,
            deposit=deposit,
            received_on=received,
            autopay=autopay,
        )
        made[f"{PREFIX}{seq:04d}"] = account

        if seq == 4:
            # Too recent to be in scope; it still gets a clean bill so that a
            # later change to the period brings it in with a real history.
            invoice = bill_for(
                tenant, account, seq=seq, total=BILL_SMALL, due_on=as_of - dt.timedelta(days=40)
            )
            pay(tenant, account, invoice, seq=seq, amount=BILL_SMALL, posted_on=as_of - dt.timedelta(days=45))
            continue

        if seq == 5:
            # ⚠ PAID **AFTER** ITS DUE DATE — `BR-PAY-021`, and the branch that
            # holds a deposit back with the reason *a bill was paid after its
            # due date*.
            due = as_of - dt.timedelta(days=60)
            invoice = bill_for(tenant, account, seq=seq, total=BILL_ORDINARY, due_on=due)
            pay(
                tenant,
                account,
                invoice,
                seq=seq,
                amount=BILL_ORDINARY,
                posted_on=due + dt.timedelta(days=9),
            )
            continue

        if seq == 6:
            # ⚠ OVERDUE THIS MORNING and unpaid — the guard `RB-115` step 3
            # calls *the morning of, not the month of*.
            bill_for(
                tenant, account, seq=seq, total=BILL_ORDINARY, due_on=as_of - dt.timedelta(days=12)
            )
            continue

        # 1, 2 and 3 — a clean payer, so *twelve months of on-time payment* is a
        # FACT rather than an absence. R-0001 also keeps one bill OPEN so the
        # credit has somewhere to be drawn against (`BR-PAY-010`).
        due = as_of - dt.timedelta(days=90)
        invoice = bill_for(tenant, account, seq=seq, total=BILL_ORDINARY, due_on=due)
        pay(
            tenant,
            account,
            invoice,
            seq=seq,
            amount=BILL_ORDINARY,
            posted_on=due - dt.timedelta(days=3),
        )
        if seq == 1:
            bill_for(
                tenant,
                account,
                seq=90 + seq,
                total=BILL_SMALL,
                due_on=as_of + dt.timedelta(days=14),
            )

    # ── autopay: two promised debits, through payments' OWN write ──────────
    #
    # ⚠ `BR-PAY-015`'s one write, and it is IDEMPOTENT ON THE INVOICE. R-0001's
    # amount MOVED since its last debit and R-0003's did not, which is the two
    # halves of *only when the amount changed*.
    from apps.payments import autopay as payments_autopay

    actor = _actor(tenant)
    for account_no, previous, amount, days in (
        (f"{PREFIX}0001", BILL_ORDINARY, BILL_SMALL, 4),
        (f"{PREFIX}0003", BILL_ORDINARY, BILL_ORDINARY, 6),
    ):
        account = made[account_no]
        if payment_models.AutopayCaptureIntent.objects.filter(
            tenant=tenant, account=account
        ).exists():
            continue
        old_invoice = bill_for(
            tenant, account, seq=800 + int(account_no[-1]), total=previous,
            due_on=as_of - dt.timedelta(days=30),
        )
        payments_autopay.record_intent_at_issue(
            actor=actor,
            account_id=account.id,
            invoice_id=old_invoice.id,
            amount=previous,
            due_date=as_of - dt.timedelta(days=30),
            currency="USD",
        )
        new_invoice = bill_for(
            tenant, account, seq=810 + int(account_no[-1]), total=amount,
            due_on=as_of + dt.timedelta(days=days),
        )
        payments_autopay.record_intent_at_issue(
            actor=actor,
            account_id=account.id,
            invoice_id=new_invoice.id,
            amount=amount,
            due_date=as_of + dt.timedelta(days=days),
            currency="USD",
        )

    # ── payment plans: three, through customers' OWN wizard sequence ───────
    from apps.payments.collections_models import LIVE_PLAN_STATUSES, PaymentPlan

    for account_no, misses in ((f"{PREFIX}0001", 0), (f"{PREFIX}0002", 1), (f"{PREFIX}0005", 2)):
        account = made[account_no]
        if PaymentPlan.objects.filter(
            tenant=tenant, account=account, status__in=LIVE_PLAN_STATUSES
        ).exists():
            continue
        plan_rows.append(_plan(tenant, account, as_of=as_of, misses=misses, actor=actor))

    return {"accounts": made, "plans": plan_rows}


def _actor(tenant):
    """A staff actor for the services that require one — never a runbook's.

    A fixture is a PERSON doing the setup by hand, which is what these services
    are written for. The runbook's own actor is the `AutomationActor` the engine
    composes at run time, and nothing here borrows it.
    """
    from apps.identity import models as identity_models

    user = (
        identity_models.User.objects.filter(tenant_id=tenant.id, deleted_at__isnull=True)
        .order_by("created_at", "id")
        .first()
    )
    if user is None:
        fail("this tenant has no active user, so no service that takes an actor can be called.")
    return user


def _plan(tenant, account, *, as_of: dt.date, misses: int, actor):
    """One payment plan, mid-schedule, with `misses` instalments unpaid.

    ⚠ **THE SCHEDULE IS `customers`' ARITHMETIC AND THE ROWS ARE `payments`'.**
    `apps.customers.payment_plan.build_schedule` owns the split — ❄️ frozen as
    `GT-47`: *267.30 − 50 down over 6 → 5 × 36.22 + 36.20, the remainder on the
    FINAL row* — and `apps.payments.plans.propose_payment_plan` is the one
    function that writes the plan and its instalments, re-validating the
    invariant rather than re-deriving the figures. A fixture that wrote the rows
    directly could create a plan whose instalments do not sum to its total, which
    is precisely the state `validate_schedule_sums` exists to make impossible.
    """
    from apps.customers import payment_plan
    from apps.payments import plans as payment_plans_service
    from apps.payments.collections_models import PaymentPlanInstallment

    first_due = as_of - dt.timedelta(days=56)
    schedule = payment_plan.build_schedule(
        total=PLAN_TOTAL,
        down_payment=PLAN_DOWN,
        installments=4,
        cadence="monthly",
        first_due_date=first_due,
    )
    proposed = payment_plans_service.propose_payment_plan(
        actor=actor,
        account_id=account.id,
        total_amount=PLAN_TOTAL,
        down_payment=PLAN_DOWN,
        installments=4,
        cadence="monthly",
        currency="USD",
        schedule=tuple(
            (one.seq, one.due_date, one.amount) for one in schedule.installments
        ),
        proposed_on=first_due - dt.timedelta(days=7),
    )
    plan_id = proposed["id"] if isinstance(proposed, dict) else proposed.id
    payment_plans_service.activate_payment_plan(
        actor=actor, plan_id=plan_id, signed_on=first_due - dt.timedelta(days=3)
    )

    # Mark the instalments that WERE met. `paid_posted_on` is the column the
    # runbook reads (`BR-PAY-021`), so a met instalment is one with a posting
    # date and a missed one is simply a row with none.
    due_rows = list(
        PaymentPlanInstallment.objects.filter(tenant=tenant, plan_id=plan_id).order_by("seq")
    )
    overdue = [row for row in due_rows if row.due_date < as_of]
    to_meet = overdue if misses == 0 else overdue[: max(len(overdue) - misses, 0)]
    for row in to_meet:
        row.paid_posted_on = row.due_date
        row.save(update_fields=["paid_posted_on"])
    return plan_id


def adopt(tenant, definition) -> runbook_models.Runbook:
    """The runbook row `POST /runbooks` writes, from the SHIPPED definition.

    Nothing here invents a name, a kind or a category — every field is the
    definition's own. `cap` is typed because `runbooks.cap` still has NO column
    default: `OQ-RBS-1731` closed at **100** and wave `L4` carries that change,
    so a fixture that pre-empted it would hide the gap.
    """
    runbook = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if runbook is None:
        print(f"── no runbook row for {definition.key!r}; adding the shipped one")
        runbook = runbook_models.Runbook.objects.create(
            tenant=tenant,
            key=definition.key,
            name=definition.name,
            kind=definition.kind,
            category=definition.category,
            subject_type=definition.subject_type,
            unit_of_work=definition.unit_of_work,
            tags=list(definition.tags),
            origin=runbook_models.ORIGIN_SHIPPED,
            template_key=definition.key,
            trigger_kind=runbook_models.TRIGGER_MANUAL,
            enabled=True,
            cap=100,
        )
    if not runbook.template_key:
        runbook_models.Runbook.objects.filter(pk=runbook.pk).update(template_key=definition.key)
        runbook.template_key = definition.key
    accepted = services.accept_template_update(runbook)
    if accepted is not None:
        print(f"── accepted the template update for {definition.key!r} → v{accepted.version}")
    return runbook


def run_it(tenant, definition, params):
    """Open, execute, close — and close STOPPED when a step stopped it.

    ⚠ **`services.close_run` TAKES THE STATUS AND `run_to_completion` DOES
    NOT.** A stopped run closed as `done` would be a lie in the one column the
    run history sorts and filters on, so the status is decided here from what the
    steps actually returned rather than defaulted.
    """
    runbook = adopt(tenant, definition)
    run = services.open_run(runbook, definition)
    result = executor.execute(definition, tenant_id=tenant.id, run_id=run.pk, params=params)
    stop = {}
    for step in definition.steps:
        candidate = result.set_results.get(step.key) or {}
        if isinstance(candidate, dict) and candidate.get("stop"):
            stop = candidate["stop"]
            break
    closed = services.close_run(
        run,
        result,
        status=(
            runbook_models.RUN_STATUS_STOPPED
            if stop
            else runbook_models.RUN_STATUS_AWAITING_APPROVAL
        ),
    )
    return closed, result, stop


def describe(name, closed, result, stop) -> None:
    """Print what the run actually said, in the figures a person would read."""
    print(f"\n── {name}  ({closed.status})")
    print(f"   subjects {len(result.subjects)} · guarded {len(result.guarded)} · counts {dict(result.counts)}")
    if stop:
        print(f"   STOP: {stop['headline']}")
    for block in result.report:
        if block["block"] == "kpis":
            for tile in block["payload"]["tiles"]:
                value = tile["value"]
                shown = value.get("text") or f"{value.get('amount')} {value.get('currency', '')}".strip()
                print(f"     · {tile['label']}: {shown}" + (f"  ({tile['detail']})" if tile.get("detail") else ""))
    for record in result.records:
        print(f"     {record.subject.label:>10}  {record.step_key:<14} {record.outcome:<16} {record.reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument(
        "--as-of",
        default=None,
        help="the business day, YYYY-MM-DD. BR-TEN-043: it is an argument, never a clock.",
    )
    parser.add_argument("--skip-build", action="store_true", help="run over rows that already exist")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        fail(f"no tenant with subdomain {args.tenant!r}")
    as_of = (
        dt.date.fromisoformat(args.as_of)
        if args.as_of
        else timezone.localdate()
    )
    print(f"tenant {args.tenant} · as of {as_of}")

    with core_tenancy.tenant_context(tenant.id):
        if not args.skip_build:
            # ⚠ **RE-ENTRANT BY SECTION.** Each half below asks whether ITS OWN
            # rows are there, so a re-run adds only what is missing and a run
            # that died half way can finish itself. See `build()`.
            set_interest_rate(tenant)
            build(tenant, as_of=as_of)
            print("── accounts, bills, payments, autopay intents and plans are in place")

        runs = {}
        for name, definition, params, expect_stop in (
            ("SMOKE_DEPOSIT_RUN_ID", deposit_review.RUNBOOK, {"as_of": as_of.isoformat()}, False),
            ("SMOKE_AUTOPAY_RUN_ID", autopay_prenotice.RUNBOOK, {"as_of": as_of.isoformat()}, False),
            ("SMOKE_PLANS_RUN_ID", payment_plans.RUNBOOK, {"as_of": as_of.isoformat()}, False),
            ("SMOKE_RETURNS_RUN_ID", returned_payments.RUNBOOK, {"as_of": as_of.isoformat()}, True),
        ):
            closed, result, stop = run_it(tenant, definition, params)
            describe(definition.name, closed, result, stop)
            runs[name] = str(closed.pk)
            # ⚠ **A STOP THAT IS A MISTAKE LOOKS EXACTLY LIKE A STOP THAT IS THE
            # ANSWER.** Runbook 26 is expected to stop; the other three are not,
            # and a fixture that let one of them quietly stop would hand the
            # browser check three screens proving nothing.
            if expect_stop and not stop:
                fail(f"{definition.key} did NOT stop, and on this product it must")
            if not expect_stop and stop:
                fail(f"{definition.key} STOPPED: {stop['headline']} — the fixture did not seed it")
            if not expect_stop and not result.records:
                fail(
                    f"{definition.key} produced NO record rows. Every account this fixture "
                    "writes is is_sample=False, so an empty result means the rows are not "
                    "there rather than that the runbook is quiet."
                )

    print("\n" + "\n".join(f"{name}={value}" for name, value in runs.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
