# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-052 (EP-CWP-10) — your payment plan, whole, not a monthly
#           summary of it. Screen: CWP-043
# Rules:    BR-CWP-063 (a plan holds the arrears; new bills still arrive and
#           still have to be paid) · BR-CWP-064 (late-fee and disconnection
#           suspension are a per-PLAN election) · BR-CWP-010 (both halves in the
#           query) · B14 rule 31 (no database id is a visible value) ·
#           CLAUDE.md hard rule 2 · PO ruling 2026-08-11 (*"nodrop we chase for
#           payments until write off"* — see OQ-CWP-1720; this line read
#           OQ-CWP-1569 until 2026-09-05, an id a sibling lane took for the
#           bill-comparison question — DEF-CWP-3800)
# Tests:    this file
# Impacts:  apps/portal/seams/payments_seam.py `current_plans` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-052`'s cases — the whole plan, and the four facts that reach no screen.

⚠ **THE INVARIANT (§7):** the down payment plus every instalment must equal the
arrears the plan was raised against — `40.00 + 5 × 22.03 + 22.05 = ` **`172.20`**.
A plan silently covering the wrong figure is the defect that catches.

⚠ **AND ONE TEST HERE IS AN ABSENCE.** `US-CWP-052` TC-7 says two missed
instalments end the plan and the whole remaining balance falls due. **The PO
ruled the opposite on 2026-08-11** — *"nodrop we chase for payments until write
off"* — and that ruling is implemented and tested: `record_missed_instalment`
returns `active` on the tenth miss. The collision is `OQ-CWP-1720`, OPEN, and
until it is answered this file asserts what the code does and no screen may say
a plan ends.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.portal.seams import payments_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

#: `US-CWP-052` §4 — the story's own fixture.
ARREARS = Decimal("172.20")
DOWN = Decimal("40.00")
BASE = Decimal("22.03")
FINAL = Decimal("22.05")
DUE_DATES = [
    date(2026, 9, 14),
    date(2026, 10, 14),
    date(2026, 11, 14),
    date(2026, 12, 14),
    date(2027, 1, 14),
    date(2027, 2, 14),
]
#: The day the story's screen is opened — *"Three of six paid. Next payment
#: 14 December."* 14 Dec − 5 Dec = **9 days**.
TODAY = date(2026, 12, 5)
PAYMENT_NUMBERS = ("PAY-26-09011", "PAY-26-10004", "PAY-26-11077")


def a_plan(tenant, account, *, suspend_late_fees=True, status="active", closed_on=None,
           paid_through=3, late_on=3):
    """One plan with six instalments, the first `paid_through` of them met.

    ⚠ **THE ROWS ARE WRITTEN AS THE WIZARD WRITES THEM.** `paid_posted_on` is
    `BR-PAY-021`'s fact — the day the payment POSTED — and on-time-ness is
    `posted ≤ due`, which is why instalment 3 here is *paid late* by being
    posted one day after its date rather than by a flag.
    """
    from apps.payments import collections_models, models as payment_models

    plan = collections_models.PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=ARREARS,
        down_payment=DOWN,
        currency="USD",
        installment_count=6,
        cadence="monthly",
        status=status,
        suspend_late_fees=suspend_late_fees,
        suspend_disconnect=True,
        autopay_enabled=True,
        proposed_on=date(2026, 9, 2),
        agreement_sent_on=date(2026, 9, 2),
        signed_on=date(2026, 9, 3),
        closed_on=closed_on,
    )
    for index, due in enumerate(DUE_DATES, start=1):
        paid_payment = None
        paid_on = None
        if index <= paid_through:
            posted = due if index != late_on else date(due.year, due.month, due.day + 1)
            paid_payment = payment_models.Payment.objects.create(
                tenant=tenant,
                account=account,
                payment_no=(
                    PAYMENT_NUMBERS[index - 1]
                    if index <= len(PAYMENT_NUMBERS)
                    else f"PAY-27-{index:05d}"
                ),
                amount=BASE,
                currency="USD",
                status=payment_models.PAYMENT_CLEARED,
                posted_at=datetime(posted.year, posted.month, posted.day, 9, 0, tzinfo=UTC),
                cleared_at=datetime(posted.year, posted.month, posted.day, 9, 0, tzinfo=UTC),
            )
            paid_on = posted
        collections_models.PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=index,
            due_date=due,
            amount=FINAL if index == 6 else BASE,
            currency="USD",
            paid_payment=paid_payment,
            paid_posted_on=paid_on,
        )
    return plan


def read(tenant, account, *, as_of=TODAY):
    with tenant_context(tenant.id):
        return payments_seam.current_plans(account.pk, as_of=as_of)


@pytest.mark.django_db
def test_us_cwp_052_tc1_six_rows_with_their_four_states(pine_hill, sarah):
    """TC-1 — *paid on time · paid on time · paid late · due in 9 days · to come
    · to come*, on 5 December.

    ⚠ **ONLY ONE ROW IS *due next*.** A screen that said *due in 40 days* four
    times would be asking for four payments; one payment is being asked for.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account)

    plan = read(pine_hill, account)["plans"][0]
    assert [row["state"] for row in plan["instalments"]] == [
        payments_seam.INSTALMENT_PAID_ON_TIME,
        payments_seam.INSTALMENT_PAID_ON_TIME,
        payments_seam.INSTALMENT_PAID_LATE,
        payments_seam.INSTALMENT_DUE_NEXT,
        payments_seam.INSTALMENT_TO_COME,
        payments_seam.INSTALMENT_TO_COME,
    ]
    # ⚠ A FACT, so eleven catalogues write *due in 9 days* in their own words.
    assert plan["instalments"][3]["days_until"] == 9
    assert plan["instalments"][4]["days_until"] is None


@pytest.mark.django_db
def test_us_cwp_052_tc2_instalment_two_NAMES_the_payment_that_cleared_it(
    pine_hill, sarah
):
    """TC-2 — ⚠ **the field that reaches no screen today.**

    Without it a customer cannot match an instalment to a line on their bank
    statement, which the story names as the reason a plan cannot be reconciled
    at all. **A payment NUMBER, never a row id** (B14 rule 31).
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan_row = a_plan(pine_hill, account)

    plan = read(pine_hill, account)["plans"][0]
    assert plan["instalments"][1]["paid_reference"] == "PAY-26-10004"
    assert plan["instalments"][0]["paid_reference"] == "PAY-26-09011"
    assert plan["instalments"][3]["paid_reference"] is None, "unpaid names nothing"
    body = str(plan)
    assert str(plan_row.pk) not in body, "B14 rule 31 — no plan id on the wire"
    assert str(plan_row.pk)[:8] not in body, "eight characters is the same breach"


@pytest.mark.django_db
def test_us_cwp_052_tc3_and_tc4_the_down_payment_is_SHOWN_and_the_cadence_is_READ(
    pine_hill, sarah
):
    """TC-3 and TC-4.

    ⚠ **THE DOWN PAYMENT IS SHOWN, NOT ONLY AT CREATION** — otherwise the
    instalments look as though they came from nowhere. ⚠ **THE CADENCE IS READ
    FROM THE RECORD, NEVER ASSUMED MONTHLY**: it is a column, and a plan may be
    weekly or fortnightly.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan_row = a_plan(pine_hill, account)
        plan_row.cadence = "weekly"
        plan_row.save(update_fields=["cadence"])

    plan = read(pine_hill, account)["plans"][0]
    assert plan["down_payment"] == "40.0000"
    assert plan["cadence"] == "weekly", "read from the record, not assumed"


@pytest.mark.django_db
def test_us_cwp_052_section7_the_whole_plan_equals_the_arrears_it_was_raised_against(
    pine_hill, sarah
):
    """⚠ **§7's INVARIANT.** `$40.00 + 5 × $22.03 + $22.05 = $172.20`.

    *"That total must equal the arrears the plan was raised against, and a test
    asserting it is what catches a plan that silently covers the wrong figure."*
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account)

    plan = read(pine_hill, account)["plans"][0]
    instalments = sum(Decimal(row["amount"]) for row in plan["instalments"])
    assert instalments == Decimal("132.2000")
    assert Decimal(plan["down_payment"]) + instalments == Decimal("172.2000")
    assert Decimal(plan["total"]) == Decimal("172.2000")
    assert plan["instalments_total"] == "132.2000"


@pytest.mark.django_db
def test_us_cwp_052_tc5_a_plan_with_suspension_OFF_says_fees_still_apply(
    pine_hill, sarah
):
    """TC-5 · **negative** / `BR-CWP-064`. ⚠ **Per PLAN, not global.**

    This is the case the blueprint singles out as *worse than a blank space*:
    a panel that promised *no late fees* on a plan where the clerk left the
    election off.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account, suspend_late_fees=False)

    plan = read(pine_hill, account)["plans"][0]
    assert plan["suspend_late_fees"] is False
    assert plan["suspend_disconnect"] is True, "the two elections are separate facts"


@pytest.mark.django_db
def test_us_cwp_052_tc6_the_hold_panel_carries_new_bills_still_arrive(pine_hill, sarah):
    """TC-6 / `BR-CWP-063` — *"a plan holds the arrears; it does not pause the
    current month's bill."* Carried on the row, so no screen has to remember it
    (believing otherwise is DEF-061)."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account)
    assert read(pine_hill, account)["plans"][0]["current_bill_still_due"] is True


@pytest.mark.django_db
def test_us_cwp_052_tc7_two_missed_instalments_END_NOTHING_oq_cwp_1563(pine_hill, sarah):
    """TC-7 · **negative, and it is the OPPOSITE of what the story asks for.**

    ⚠ **`US-CWP-052` TC-7 EXPECTS THE PLAN TO END AND THE WHOLE REMAINING
    BALANCE TO FALL DUE. THIS PRODUCT DOES NOT DO THAT.** PO ruling 2026-08-11,
    verbatim: *"nodrop we chase for payments until write off"* — `BR-CUS-044`'s
    `defaulted` state, its `{missed_count}` clause and `BR-PAY-016`'s *"2nd miss
    VOIDS plan"* are all SUPERSEDED, and `apps/payments/plans.py` carries no
    `void`, no `defaulted` and no `missed_count`.

    **Worked, so the gap is a figure:** two misses would end this plan and make
    `$66.11` fall due at once under the blueprint's sentence; under this product
    the plan is still `active`, `$22.03` is still due on 14 February, and a
    notice goes out.

    The collision is **`OQ-CWP-1720`**, OPEN and routed to the Product Owner. It
    is asserted here as an ABSENCE because a test asserting the blueprint's
    behaviour would be asserting a promise the code does not keep — and until it
    is answered **no screen may say a plan ends on a missed instalment**.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan_row = a_plan(pine_hill, account, paid_through=0)

    # Two instalments (14 Sep, 14 Oct — and a third, 14 Nov) are past and unmet.
    plan = read(pine_hill, account)["plans"][0]
    missed = [
        row for row in plan["instalments"] if row["state"] == payments_seam.INSTALMENT_MISSED
    ]
    assert len(missed) >= 2

    with tenant_context(pine_hill.id):
        plan_row.refresh_from_db()
    assert plan_row.status == "active", "nobody is dropped off a plan (PO 2026-08-11)"
    assert plan["live"] is True
    assert plan["closed_on"] is None
    # And the product holds no machinery that could end it, which is the RULE
    # rather than work left undone.
    from apps.customers import payment_plan

    assert payment_plan.record_missed_instalment(missed_count=10) == "active"
    from apps.payments import plans as payment_plans

    assert not hasattr(payment_plans, "void_payment_plan")


@pytest.mark.django_db
def test_us_cwp_052_tc8_a_CLOSED_plan_is_still_reachable_and_marked_closed(
    pine_hill, sarah
):
    """TC-8 · **negative** — ⚠ *"a finished plan disappears from the portal
    today. It must not."* Nothing filters by status, and the row carries its
    close date."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(
            pine_hill, account, status="closed", closed_on=date(2025, 12, 1), paid_through=6,
        )

    plans = read(pine_hill, account)["plans"]
    assert len(plans) == 1
    assert plans[0]["status"] == "closed"
    assert plans[0]["closed_on"] == "2025-12-01"
    assert plans[0]["live"] is False


@pytest.mark.django_db
def test_us_cwp_052_tc10_autopay_on_the_plan_reaches_the_screen(pine_hill, sarah):
    """TC-10 — `autopay_enabled` is on the plan row and reached no screen today."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account)
    assert read(pine_hill, account)["plans"][0]["autopay_enabled"] is True


@pytest.mark.django_db
def test_us_cwp_052_tc9_tenant_isolation_a_plan_answers_its_own_utility_only(
    pine_hill, sarah, oak_ridge, elena
):
    """TC-9 · **tenant isolation** / `BR-CWP-010`, hard rule 1.

    ⚠ **THE HARD DIRECTION:** a Pine Hill account id read under Oak Ridge's
    context answers NOTHING, which is only true if the tenant half is in the
    query rather than in the caller.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_plan(pine_hill, account)

    assert len(read(pine_hill, account)["plans"]) == 1
    with tenant_context(oak_ridge.id):
        assert payments_seam.current_plans(account.pk, as_of=TODAY) == {"plans": []}


@pytest.mark.django_db
def test_us_cwp_052_an_account_with_no_plan_answers_an_empty_list(pine_hill, sarah):
    """`BR-CWP-093` — the SCREEN names what would fill it; the read answers
    nothing rather than a fabricated row."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert read(pine_hill, account) == {"plans": []}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-052@8bcd8b6a (EP-CWP-10 story §1–§8 + BR-CWP-063/064 verbatim + J41)
# generated: 2026-09-04 by the CR-068 wave G/M slice lane
# checklist: A✔ B✔ C✔ D✔(apps/portal/api.py `plans_current`) E✔(portal/plans/YourPlan.tsx) F✔ G✔ H=n/a(the seam composes payments' own published read)
# gates: pytest tests/test_us_cwp_052_your_plan.py · G81 (the seam performs no ORM write)
# exceptions: (1) TC-7 is asserted as its OPPOSITE — the PO's 2026-08-11 "nodrop" ruling means two misses end nothing, and the collision with the blueprint is OQ-CWP-1720, OPEN · (2) `paid_payment`'s NUMBER is composed in the seam because the published read carries only `paid_posted_on` and `on_time`; the story itself says the field reaches no screen today
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
