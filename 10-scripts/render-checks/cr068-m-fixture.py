# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-051 … US-CWP-055 (CR-068 wave M — plans and level pay)
# Rules:   BR-CWP-062 (the remainder goes on the FINAL instalment) ·
#          BR-CWP-063 · BR-CWP-064 (late-fee suspension is a PER-PLAN
#          election) · BR-CWP-066 (a plan is GRANTED BY A CLERK) ·
#          BR-CWP-054 (the level comes from the tenant's rounding setting) ·
#          CLAUDE.md hard rule 1 (every write inside one tenant's context) ·
#          hard rule 2 (money stored to 4 dp, displayed to 2)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-m-plans-and-level-pay.mjs
# ───────────────────────────────────────────────────────
"""WAVE M's DEMO STATE, AND A LOGIN THAT CAN SEE IT.

WHY THIS FILE EXISTS
--------------------
`10-execution-plan.md` lines 613-639 give wave M a six-step demo script whose
figures are exact: `$172.20` spread over six months after `$40.00` up front is
**five instalments of `$22.03` and a final `$22.05`, totalling `$132.20`**; an
offer *Sarah at the office* built on 2 September; twelve months totalling
`$1,501.09` averaging `$125.09` and rounding to `$125.00`; an enrolment
`$47.30` ahead settling up in June.

**None of it is in the seeded database.** After `seed_portal_demo` the clone
holds one active plan per tenant on a generated account — four biweekly
instalments of a generated amount — **zero rows in `account_budget_status`**,
and **no plan in `agreement_sent`**, so `CWP-063` and `CWP-066` have nothing to
draw and `CWP-043` draws figures the demo script never mentions. It also holds
**zero rows in `portal_credential`**, so nobody can sign in at all.

⚠ **AND THAT IS EXACTLY THE STATE A WALKTHROUGH MUST NOT ASSERT IN**
(`DEF-WRK-4121`: a dispatcher shipped who could not raise a work order on any
non-empty list, because every test used the empty list — the one state where it
worked). A run against the seeded clone would find `CWP-066` in its
*not enrolled* branch and `CWP-063` in its *no offer* branch, both of which
render, and would report GREEN over two screens nobody had looked at.

WHAT IT BUILDS, AND WHY ON THREE ACCOUNTS
-----------------------------------------
`payment_plans` carries `uq_one_live_plan_per_account` — one live plan per
account, held by the database — so the *active* plan of step 2 and the
*offered* plan of step 3 **cannot** sit on the same account. They go on two
accounts of the SAME customer, which is what the account switcher is for.

  * account 1 — the ACTIVE plan: `$172.20` over six after `$40.00`, five of
    `$22.03` and a final `$22.05`; instalments 1 and 2 paid on time, 3 paid
    late, 4 due next, 5 and 6 to come; `suspend_late_fees=False` so `CWP-043`
    must say *fees still apply*. It also carries the level-pay enrolment.
  * account 2 — **NO plan at all, and arrears**, because `CWP-042` refuses to
    preview anything for an account that already holds a live plan
    (*"this account already has a live payment plan"*, `BR-CUS-043`/`A3`). The
    ask screen is unreachable without one, which is the whole of step 1.
  * account 3 — the OFFER: the same schedule in `agreement_sent`, so `CWP-063`
    has an offer to draw. `CWP-063` reads the PLAN ROW and never the balance,
    so it does not matter that this account owes nothing.

THE ARITHMETIC IS NOT DONE HERE
-------------------------------
`apps.customers.payment_plan.build_schedule` owns it (`BR-CUS-043`, frozen as
`GT-47`), and this fixture CALLS it rather than typing six figures in. A
fixture that typed the numbers would prove the screen renders and prove nothing
about the figure on it — and if the engine ever drifts from `$22.03`/`$22.05`
the walkthrough should go red, which it cannot do if the fixture drifts with it.
The script asserts the schedule it got back matches the demo script's figures
and **refuses to write anything** if it does not.

RUN IT
------
    10-scripts/proof-db.sh clone <label>
    export DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-m-fixture.py)

It is IDEMPOTENT: a second run re-uses the credential and rewrites the plans.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from apps.billing import budget as budget_rules
from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.customers import payment_plan as plan_math
from apps.payments import collections_models
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

TENANT = "pine-hill"
EMAIL = "plans@example.test"
PASSWORD = "Pine-Hill-2026!"

# ── the demo script's own figures (10-execution-plan.md, wave M) ─────────────
ARREARS = Decimal("172.20")
DOWN = Decimal("40.00")
TERM = 6
SPREAD = Decimal("132.20")          # 172.20 − 40.00
EACH = Decimal("22.03")             # five of these …
FINAL = Decimal("22.05")            # … and one of this
#: The OFFER's first payment — the date `CWP-063`'s wireframe prints.
OFFER_FIRST_DUE = dt.date(2026, 9, 14)
#: The ACTIVE plan starts THREE MONTHS EARLIER, and that is deliberate.
#: `CWP-043` has to show *paid on time · paid on time · paid late · due in N
#: days · to come · to come*, and a payment can only be *paid* if it POSTED in
#: the past. Running the active plan from 15 June puts instalments 1-3 behind
#: today and instalment 4 nine days ahead of it — the wireframe's own state,
#: reached by real dates rather than by back-dating a future payment.
ACTIVE_FIRST_DUE = dt.date(2026, 6, 15)
OFFER_SET_UP_ON = dt.date(2026, 9, 2)

LEVEL = Decimal("125.00")           # the rounded level the tenant's setting gives
VARIANCE = Decimal("47.30")         # positive = ahead (they paid more than used)
SETTLE_UP_MONTH = 6                 # June
ENROLLED_ON = dt.date(2026, 1, 1)


def money(value: Decimal) -> Decimal:
    """Hard rule 2 — stored to four decimals, never a float."""
    return Decimal(value).quantize(Decimal("0.0001"))


def pick_accounts(tenant_id):
    """One customer of this tenant holding at least three accounts.

    Chosen by QUERY rather than by account number: the sample estate is
    generated and its numbers move between seeds. The script prints what it
    chose so a failing run can be reproduced.
    """
    holdings: dict[str, list] = {}
    for link in customers_models.CustomerAccount.objects.filter(tenant_id=tenant_id):
        account = customers_models.Account.objects.filter(
            tenant_id=tenant_id, pk=link.account_id
        ).first()
        if account is not None:
            holdings.setdefault(str(link.customer_id), []).append(account)
    ranked = sorted(holdings.items(), key=lambda kv: -len(kv[1]))
    for customer_id, accounts in ranked:
        if len(accounts) >= 3:
            ordered = sorted(accounts, key=lambda a: a.account_no)
            return customer_id, ordered[:3]
    raise SystemExit(
        "no customer on this tenant holds three accounts — wave M needs three "
        "(one live plan per account is a database constraint)"
    )


def schedule_for(total: Decimal, down: Decimal, term: int, first_due: dt.date):
    """The instalments, from the ENGINE the clerk's wizard uses (BR-CUS-043)."""
    return plan_math.build_schedule(
        total=total,
        down_payment=down,
        installments=term,
        cadence="monthly",
        first_due_date=first_due,
    )


def check_schedule(rows) -> None:
    """Refuse to seed a schedule that is not the demo script's own.

    ⚠ **THIS IS THE ASSERTION THAT MAKES THE WALKTHROUGH MEAN SOMETHING.** If
    the instalment engine ever stops producing five of `$22.03` and a final
    `$22.05`, the right outcome is a RED fixture naming the figure that moved —
    not a fixture that quietly seeds whatever the engine now says and a
    walkthrough that then asserts the screen agrees with it.
    """
    amounts = [Decimal(r.amount).quantize(Decimal("0.01")) for r in rows.installments]
    if len(amounts) != TERM:
        raise SystemExit(f"engine returned {len(amounts)} instalments, expected {TERM}")
    if amounts[:-1] != [EACH] * (TERM - 1) or amounts[-1] != FINAL:
        raise SystemExit(
            f"engine returned {amounts}, expected five of {EACH} and a final {FINAL} "
            "(BR-CWP-062 / GT-47) — seeding refused"
        )
    total = sum(amounts)
    if total != SPREAD:
        raise SystemExit(f"instalments sum to {total}, expected {SPREAD} — seeding refused")
    print(f"  engine: five of ${EACH} and a final ${FINAL}, summing to ${total}  ✓")


def clear_plans(tenant_id, account) -> None:
    """Close whatever the sample plant left, so the live-plan constraint is free."""
    live = collections_models.PaymentPlan.objects.filter(
        tenant_id=tenant_id,
        account_id=account.pk,
        status__in=collections_models.LIVE_PLAN_STATUSES,
    )
    for plan in live:
        collections_models.PaymentPlanInstallment.objects.filter(
            tenant_id=tenant_id, plan_id=plan.pk
        ).delete()
        plan.delete()


def make_plan(tenant_id, account, rows, *, status, agreement_sent_on=None, signed_on=None):
    plan = collections_models.PaymentPlan.objects.create(
        tenant_id=tenant_id,
        account_id=account.pk,
        total_amount=money(ARREARS),
        down_payment=money(DOWN),
        currency="USD",
        installment_count=TERM,
        cadence="monthly",
        status=status,
        # BR-CWP-064 — a PER-PLAN election, and it is OFF here on purpose so
        # `CWP-043` has to say *fees still apply* (the demo script, step 2).
        suspend_late_fees=False,
        suspend_disconnect=True,
        autopay_enabled=False,
        proposed_on=OFFER_SET_UP_ON,
        agreement_sent_on=agreement_sent_on,
        signed_on=signed_on,
    )
    for row in rows.installments:
        collections_models.PaymentPlanInstallment.objects.create(
            tenant_id=tenant_id,
            plan_id=plan.pk,
            seq=row.seq,
            due_date=row.due_date,
            amount=money(Decimal(row.amount)),
            currency="USD",
        )
    return plan


def mark_paid(tenant_id, plan) -> None:
    """Instalments 1 and 2 on time, 3 late — the demo script's own six states.

    `paid_posted_on` is what decides on-time against late (`BR-PAY-021`:
    on-time is `posted_at ≤ due date`), so the fixture sets the POSTING DATE
    and lets the screen derive the word. Writing a status column here would be
    a second answer to a question the product already answers.
    """
    rows = list(
        collections_models.PaymentPlanInstallment.objects.filter(
            tenant_id=tenant_id, plan_id=plan.pk
        ).order_by("seq")
    )
    for row in rows[:2]:
        row.paid_posted_on = row.due_date - dt.timedelta(days=2)  # on time
        row.save(update_fields=["paid_posted_on"])
    rows[2].paid_posted_on = rows[2].due_date + dt.timedelta(days=5)  # paid LATE
    rows[2].save(update_fields=["paid_posted_on"])


def make_level_pay(tenant_id, account):
    """Enrol this account on level pay — and RE-USE an enrolment already here.

    ⚠ **`account_budget_events` IS APPEND-ONLY AND THE DATABASE ENFORCES IT**
    (`US-BIL-019` TC-6: *"the budget variance balance DERIVES from these rows,
    so delete is refused"* — a PL/pgSQL trigger, not a convention). A fixture
    that made itself idempotent by deleting the events would be refused by
    PostgreSQL, which is the right answer: the correction for a wrong event is
    another event. So a second run keeps what the first one wrote.
    """
    existing = billing_models.AccountBudgetStatus.objects.filter(
        tenant_id=tenant_id, account_id=account.pk
    ).first()
    if existing is not None:
        return existing
    status = billing_models.AccountBudgetStatus.objects.create(
        tenant_id=tenant_id,
        account_id=account.pk,
        status=budget_rules.STATUS_ENROLLED,
        level=money(LEVEL),
        currency="USD",
        # Positive = the levels collected MORE than the customer used, which is
        # what *you are $47.30 ahead* means on `CWP-066`.
        variance_balance=money(VARIANCE),
        last_leveled_at=dt.date(2026, 7, 1),
        settle_up_month=SETTLE_UP_MONTH,
        enrolled_on=ENROLLED_ON,
    )
    # The three re-levelling rows `CWP-066`'s *when the level changed* table
    # draws. Balances are the running variance AFTER each movement.
    for on, event, balance in (
        (ENROLLED_ON, billing_models.BUDGET_EVENT_ENROLLED, Decimal("0.00")),
        (dt.date(2026, 7, 1), billing_models.BUDGET_EVENT_RELEVELED, Decimal("31.10")),
        (dt.date(2026, 8, 30), billing_models.BUDGET_EVENT_BILLED, VARIANCE),
    ):
        billing_models.AccountBudgetEvent.objects.create(
            tenant_id=tenant_id,
            budget_status_id=status.pk,
            account_id=account.pk,
            event=event,
            level=money(LEVEL),
            currency="USD",
            balance_after=money(balance),
            occurred_on=on,
        )
    return status


def main() -> None:
    tenant = Tenant.objects.get(subdomain=TENANT)
    with tenant_context(tenant.id):
        customer_id, accounts = pick_accounts(tenant.id)
        plan_account, ask_account, offer_account = accounts
        print(f"customer {customer_id}")
        print(f"  plan account   {plan_account.account_no}  (active plan + level pay)")
        print(f"  ask account    {ask_account.account_no}  (arrears, NO plan)")
        print(f"  offer account  {offer_account.account_no}  (agreement_sent)")

        active_rows = schedule_for(ARREARS, DOWN, TERM, ACTIVE_FIRST_DUE)
        offer_rows = schedule_for(ARREARS, DOWN, TERM, OFFER_FIRST_DUE)
        check_schedule(active_rows)
        check_schedule(offer_rows)

        for account in accounts:
            clear_plans(tenant.id, account)

        active = make_plan(
            tenant.id, plan_account, active_rows,
            status=collections_models.PLAN_ACTIVE,
            agreement_sent_on=OFFER_SET_UP_ON,
            signed_on=OFFER_SET_UP_ON,
        )
        mark_paid(tenant.id, active)
        print(f"  active plan on {plan_account.account_no}: {TERM} instalments, three paid")

        make_plan(
            tenant.id, offer_account, offer_rows,
            status=collections_models.PLAN_AGREEMENT_SENT,
            agreement_sent_on=OFFER_SET_UP_ON,
        )
        print(f"  offered plan on {offer_account.account_no}: agreement_sent, unsigned")
        print(f"  no plan on {ask_account.account_no}: CWP-042 can preview there")

        make_level_pay(tenant.id, plan_account)
        print(f"  level pay on {plan_account.account_no}: ${LEVEL} a month, ${VARIANCE} ahead, June")

        existing = portal_models.PortalCredential.objects.filter(
            tenant_id=tenant.id, email=credentials.normalise_email(EMAIL)
        ).first()
        if existing is None:
            credentials.create_credential(
                tenant.id, account=plan_account, email=EMAIL, password=PASSWORD,
                otp_channel="email",
            )
            print(f"  credential created: {EMAIL} / {PASSWORD}")
        else:
            print(f"  credential re-used: {EMAIL}")

        print("SMOKE_EMAIL=" + EMAIL)
        print("SMOKE_PASSWORD=" + PASSWORD)
        print("SMOKE_PLAN_ACCOUNT=" + plan_account.account_no)
        print("SMOKE_ASK_ACCOUNT=" + ask_account.account_no)
        print("SMOKE_OFFER_ACCOUNT=" + offer_account.account_no)


main()
