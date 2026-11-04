# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-051 (EP-CWP-10) — ask for a payment plan, and the last
#           instalment carries the rounding. Screen: CWP-042
# Rules:    BR-CWP-062 (the remainder goes on the FINAL instalment and the
#           screen shows it) · BR-CWP-063 (a plan holds the arrears; new bills
#           still arrive) · BR-CWP-064 (late-fee suspension is a per-PLAN
#           election) · BR-CWP-066 (a plan is GRANTED BY A CLERK; a customer may
#           only ASK — PO 2026-09-04, OQ-1391 closed option (a)) ·
#           BR-CUS-043 / ❄️ GT-47 (the arithmetic, which lives in
#           apps/customers/payment_plan.py and NOT in the portal) ·
#           CLAUDE.md hard rule 2
# Tests:    this file
# Impacts:  apps/portal/seams/payments_seam.py `plan_preview` ·
#           apps/portal/services.py `SHAPE_PLAN_REQUEST` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-051`'s cases — and the invariant the whole story rests on.

⚠ **THE INSTALMENTS MUST SUM TO THE AMOUNT COVERED, EXACTLY.**
`172.20 − 40.00 = 132.20`; `132.20 ÷ 6 = 22.0333…` → `22.03`; five at `22.03` is
`110.15`; the final is what is LEFT, `132.20 − 110.15 = 22.05`; **Σ = 132.20**.
Every one of those figures comes out of `apps.customers.payment_plan.
build_schedule` — the function the CLERK's wizard calls, frozen as ❄️ GT-47 —
and the portal contributes none of them. `test_…_the_portal_adds_no_arithmetic`
below is the assertion that says so out loud.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.portal.seams import payments_seam
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

#: `US-CWP-051` §4 — the story's own fixture, and `J41`'s.
ARREARS = "172.20"
UP_FRONT = "40.00"
TERM = 6
FIRST_DUE = date(2026, 9, 14)
TODAY = date(2026, 9, 2)
BASE = "22.0300"
FINAL = "22.0500"
SPREAD = "132.2000"
#: TC-7 — a balance that divides exactly.
EXACT_BALANCE = "120.00"


@pytest.fixture()
def owing(monkeypatch):
    """The LEDGER's AR answer, stated by the test rather than posted.

    The same shape `tests/test_us_cus_018_payment_plan_api.py` uses, and for its
    stated reason: the balance is read through `customers.seams.ar_positions`
    (DEF-127's one derivation), so patching the seam is exactly the deployment
    shape the screen sees and lets a test say *"this account owes $172.20"*
    without standing up a bill run to prove an unrelated rule.
    """

    def _owe(amount: str | None, *, unavailable: str | None = None):
        from apps.customers import seams

        reason = None if amount is not None else (unavailable or "seam_unwired")

        class _Positions:
            available = amount is not None
            currency = "USD" if amount is not None else None
            basis = "accrual"
            unavailable = reason

            def amount_for(self, _account_id):
                return None if amount is None else Decimal(amount)

        monkeypatch.setattr(seams, "ar_positions", lambda *a, **k: _Positions())

    return _owe


def preview(tenant, account, **kwargs):
    body = {
        "months": TERM,
        "first_due_on": FIRST_DUE,
        "down_payment": UP_FRONT,
        "as_of": TODAY,
    }
    body.update(kwargs)
    with tenant_context(tenant.id):
        return payments_seam.plan_preview(account.pk, **body)


@pytest.mark.django_db
def test_us_cwp_051_tc1_and_tc2_five_of_22_03_a_final_22_05_and_they_sum_EXACTLY(
    pine_hill, sarah, owing
):
    """⚠ **TC-1 and TC-2, the case the story exists for.**

    Five instalments of `$22.03` and a final `$22.05`, totalling `$132.20` — and
    the sum is asserted as ARITHMETIC rather than eyeballed, because a schedule
    that does not re-sum is an agreement whose own numbers disagree and the
    customer signs it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    plan = preview(pine_hill, account)

    amounts = [row["amount"] for row in plan["instalments"]]
    assert amounts == [BASE, BASE, BASE, BASE, BASE, FINAL], amounts
    assert sum(Decimal(one) for one in amounts) == Decimal(SPREAD), (
        "the instalments must sum to the amount covered, to the cent"
    )
    assert plan["spread"] == SPREAD
    assert plan["down_payment"] == "40.0000"
    assert plan["balance"] == "172.2000"
    # And the whole plan comes back to the arrears it was raised against.
    assert Decimal(plan["spread"]) + Decimal(plan["down_payment"]) == Decimal("172.2000")


@pytest.mark.django_db
def test_us_cwp_051_the_LAST_instalment_is_the_one_flagged_as_carrying_the_rounding(
    pine_hill, sarah, owing
):
    """`BR-CWP-062` — *"the remainder goes on the FINAL instalment, and the
    screen shows it."*

    ⚠ **THE FLAG IS THE ENGINE'S OWN `Installment.final`, NOT THIS SEAM'S IDEA
    OF *last*.** The screen states the fact rather than inferring it from
    position, which is what `US-CWP-051` §1 asks for: *"the uneven last
    instalment is deliberate and must be shown."*
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    rows = preview(pine_hill, account)["instalments"]
    flagged = [row for row in rows if row["carries_the_rounding"]]
    assert len(flagged) == 1
    assert flagged[0]["seq"] == TERM
    assert flagged[0]["amount"] == FINAL
    assert flagged[0]["amount"] != BASE, "the rounding row is the uneven one"


@pytest.mark.django_db
def test_us_cwp_051_tc3_the_consequence_box_count_is_FIVE_then_one(pine_hill, sarah, owing):
    """TC-3 · **negative** — ⚠ *"Says **five** payments then one — not six then
    one. Assert the count in the copy matches the table."*

    The blueprint's own consequence box read *six payments of `$22.03`, then one
    of `$22.05`* — seven payments totalling `$154.23` — beside its own table of
    six totalling `$132.20`. **The count is SERVED** so the screen cannot
    compute a different one from the table beside it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    plan = preview(pine_hill, account)
    assert plan["base_instalment_count"] == 5, "five, then one — never six then one"
    assert plan["base_amount"] == BASE
    assert plan["final_amount"] == FINAL
    # The copy's own arithmetic, checked against the table it sits beside.
    assert (
        Decimal(plan["base_amount"]) * plan["base_instalment_count"]
        + Decimal(plan["final_amount"])
        == Decimal(plan["spread"])
    )
    assert plan["base_instalment_count"] + 1 == len(plan["instalments"])


@pytest.mark.django_db
def test_us_cwp_051_tc4_thirteen_months_is_refused_NAMING_the_two_to_twelve_range(
    pine_hill, sarah, owing
):
    """TC-4 · **negative**. ⚠ The refusal names the range — a bare *not allowed*
    leaves a customer guessing at a number the screen already knows.

    ⚠ **THE RANGE IS THE PORTAL'S AND NOT THE ENGINE'S**, and that is why it is
    checked here: `payment_plan.validate_proposal` refuses only
    `installments < 1`, so thirteen months would otherwise produce a perfectly
    valid thirteen-row schedule.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    for months in (13, 1, 0, 24):
        with pytest.raises(errors.ApiError) as refusal:
            preview(pine_hill, account, months=months)
        assert refusal.value.params["min"] == 2
        assert refusal.value.params["max"] == 12


@pytest.mark.django_db
def test_us_cwp_051_tc5_and_tc6_an_up_front_at_or_over_the_balance_is_refused(
    pine_hill, sarah, owing
):
    """TC-5 and TC-6 · **negative** — and the refusal is the ENGINE's sentence,
    carried rather than re-worded, so the customer and the clerk are refused for
    the same stated reason."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    with pytest.raises(errors.ApiError):
        preview(pine_hill, account, down_payment="172.20")
    with pytest.raises(errors.ApiError):
        preview(pine_hill, account, down_payment="200.00")


@pytest.mark.django_db
def test_us_cwp_051_tc7_a_balance_that_divides_EXACTLY_invents_no_odd_final_row(
    pine_hill, sarah, owing
):
    """TC-7 — `$120.00` over six is six of `$20.00`. ⚠ **No odd final instalment
    is invented**: the remainder rule only fires when there is a remainder."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(EXACT_BALANCE)

    plan = preview(pine_hill, account, down_payment="0")
    amounts = [row["amount"] for row in plan["instalments"]]
    assert amounts == ["20.0000"] * 6, amounts
    assert len(set(amounts)) == 1, "one amount, six times — nothing uneven"
    assert sum(Decimal(one) for one in amounts) == Decimal("120.0000")


@pytest.mark.django_db
def test_us_cwp_051_tc11_the_box_says_fees_STILL_APPLY_when_the_election_is_off(
    pine_hill, sarah, owing
):
    """TC-11 · **negative** / `BR-CWP-064`.

    ⚠ **THE ELECTION IS PER PLAN AND IT IS READ, NEVER ASSUMED.** The product's
    default is OFF — `wizard_context()["defaults"]["suspend_late_fees"]` — so a
    preview must not promise *late fees stop*, which only a clerk can grant.
    The blueprint calls this case *worse than a blank space*.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    plan = preview(pine_hill, account)
    assert plan["suspend_late_fees"] is False, (
        "the preview promised late fees stop on a plan no clerk has granted"
    )
    # And the other half of the pair, which IS on by default.
    assert plan["suspend_disconnect"] is True


@pytest.mark.django_db
def test_us_cwp_051_BR_CWP_063_the_current_bill_is_still_due_on_the_payload(
    pine_hill, sarah, owing
):
    """`BR-CWP-063` — carried on the payload rather than left for a screen to
    remember. Believing the plan replaces the bill is DEF-061."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)
    assert preview(pine_hill, account)["current_bill_still_due"] is True


@pytest.mark.django_db
def test_us_cwp_051_the_preview_WRITES_NOTHING(pine_hill, sarah, owing):
    """A preview that wrote a plan would activate one, which `BR-CWP-066`
    forbids outright. Counted as ROWS, not read off the response."""
    from apps.payments import collections_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    with tenant_context(pine_hill.id):
        before = collections_models.PaymentPlan.objects.count()
    plan = preview(pine_hill, account)
    with tenant_context(pine_hill.id):
        after = collections_models.PaymentPlan.objects.count()
    assert before == after == 0
    assert plan["writes"] == []


@pytest.mark.django_db
def test_us_cwp_051_the_portal_adds_no_arithmetic_it_previews_the_ENGINE(
    pine_hill, sarah, owing
):
    """⚠ **THE REUSE ASSERTION, AND IT IS THE POINT OF THE WHOLE STORY.**

    `US-CWP-051` §7: *"Existing, tested instalment arithmetic — this screen
    previews it and must not recompute it independently."* So the same inputs
    put through `apps.customers.payment_plan.build_schedule` — the function the
    CLERK's S24 wizard calls — must give the portal's figures exactly. **The day
    somebody writes a second schedule in the portal, this goes red**, and until
    then a clerk and a customer cannot be handed different instalments.
    """
    from apps.customers import payment_plan

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    engine = payment_plan.build_schedule(
        total=Decimal(ARREARS),
        down_payment=Decimal(UP_FRONT),
        installments=TERM,
        cadence=payment_plan.CADENCE_MONTHLY,
        first_due_date=FIRST_DUE,
    )
    portal = preview(pine_hill, account)

    assert [row["amount"] for row in portal["instalments"]] == [
        f"{row.amount:.4f}" for row in engine.installments
    ]
    assert [row["due_on"] for row in portal["instalments"]] == [
        row.due_date.isoformat() for row in engine.installments
    ]
    assert [row["carries_the_rounding"] for row in portal["instalments"]] == [
        row.final for row in engine.installments
    ]


@pytest.mark.django_db
def test_us_cwp_051_an_unreadable_balance_never_opens_the_plan_at_zero(
    pine_hill, sarah, owing
):
    """DEF-127's rule, applied to a customer. ⚠ **A zero that means *I don't
    know* is the defect**: it looks exactly like a settled account, and a
    customer would be offered a plan over nothing."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(None, unavailable="no_ar_designation")

    with pytest.raises(errors.ApiError):
        preview(pine_hill, account)


@pytest.mark.django_db
def test_us_cwp_051_tc10_asking_creates_a_REQUEST_and_never_a_plan(
    pine_hill, sarah, owing
):
    """TC-10 · **negative** / `BR-CWP-066`.

    ⚠ **A REFUSAL NOW, NOT A STUB.** `OQ-1391` closed on 2026-09-04 — *"Utility
    Clark will di it for Consumer; COnsumer cannot do it by themself; these are
    special cases"* — so there is no self-serve activation path to reach and none
    to stub. What the ask leaves behind is ONE service request on a clerk's
    worklist carrying the previewed schedule, and **no `payment_plan` row at
    all**.
    """
    from apps.customers import models as customers_models
    from apps.payments import collections_models
    from apps.portal import services

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)
    plan = preview(pine_hill, account)

    with tenant_context(pine_hill.id):
        answer = services.raise_service_request(
            pine_hill.id,
            shape=services.SHAPE_PLAN_REQUEST,
            payload={
                "account_no": account.account_no,
                "address": plan["service_address"],
                "name": "Maria Alvarez",
                "email": "maria.alvarez@example.test",
                "phone": "(512) 555-4218",
                **{
                    key: plan[key]
                    for key in (
                        "balance",
                        "down_payment",
                        "spread",
                        "term_months",
                        "first_due_on",
                        "base_instalment_count",
                        "base_amount",
                        "final_amount",
                    )
                },
            },
        )
        request = customers_models.ServiceRequest.objects.get(request_no=answer["reference"])
        assert collections_models.PaymentPlan.objects.count() == 0, (
            "asking for a plan CREATED one — BR-CWP-066: the clerk grants it"
        )

    assert answer["plan_created"] is False
    assert answer["granted_by"] == "clerk"
    assert answer["reference"].startswith("SR-")
    # `BR-CWP-076` — identifiable on the worklist and in every count.
    assert request.channel == "customer_portal"
    # ⚠ The clerk reads the whole previewed schedule in words, and the account
    # by its NUMBER (B14 rule 31) — never a row id.
    assert account.account_no in request.what_they_said
    assert "5 instalments of 22.0300" in request.what_they_said
    assert "final 22.0500" in request.what_they_said
    assert "totalling 132.2000" in request.what_they_said
    assert str(account.pk) not in request.what_they_said


@pytest.mark.django_db
def test_us_cwp_051_tc9_tenant_isolation_the_preview_reads_this_utility_only(
    pine_hill, sarah, oak_ridge, elena, owing
):
    """TC-9 · **tenant isolation** — a Pine Hill account read under Oak Ridge's
    context is refused, because the account lookup is tenant-scoped in the
    query (`BR-CWP-010`, hard rule 1)."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    owing(ARREARS)

    # ⚠ **A 404 AND NOT A 403.** `NotFoundError` is deliberately NOT an
    # `ApiError` in this product: cross-tenant and genuinely-absent are
    # indistinguishable by law (G4/HR-1), so Oak Ridge cannot learn that a Pine
    # Hill account exists by watching which refusal comes back.
    with tenant_context(oak_ridge.id):
        with pytest.raises(errors.NotFoundError):
            payments_seam.plan_preview(
                account.pk,
                months=TERM,
                first_due_on=FIRST_DUE,
                down_payment=UP_FRONT,
                as_of=TODAY,
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-051@8bcd8b6a (EP-CWP-10 story §1–§8 + BR-CWP-062/063/064/066 verbatim + J41)
# generated: 2026-09-04 by the CR-068 wave G/M slice lane
# checklist: A✔ B✔ C✔ D✔(apps/portal/api.py `plan_preview`/`plan_request`) E✔(portal/plans/AskForPlan.tsx) F✔ G✔ H=n/a(the arithmetic is customers' 🔒 file and is CALLED, never copied)
# gates: pytest tests/test_us_cwp_051_plan_ask.py · G81 (no new write point; `plan_request` is a SHAPE)
# exceptions: (1) the two-to-twelve range is enforced at the portal edge because the engine holds no such rule — an INPUT constraint, never arithmetic · (2) `J41` step 5 expects `NotImplementedError("OQ-1391")` and was written while that question was open; it CLOSED 2026-09-04 and TC-10 asserts the refusal instead, which is what the story now says · (3) the *miss two and the plan ends* copy is withheld pending `OQ-CWP-1720`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
