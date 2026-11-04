# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-055 (EP-CWP-10) — *where your level pay stands.*
#           Screen: CWP-066
# Rules:    BR-CWP-054 (the level, the variance and the settle-up, plus each
#           re-levelling and what happened) · BR-BIL-017 (the override is kept
#           ALONGSIDE the computed level; the ±30% bound is measured against
#           the computed one) · BR-CWP-052 (the utility's own note about a
#           customer is held back) · B14 rule 31 · CLAUDE.md hard rule 2
# Golden:   ❄️ GT-24 is the frozen chain the LEVEL belongs to. Nothing here
#           recomputes it — `budget_service.effective_level` is read.
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `level_pay_standing` ·
#           `level_pay_months` · apps/portal/selectors.py `level_pay_standing`
# ───────────────────────────────────────────────────────
"""`US-CWP-055`'s cases — and the invariant that keeps two screens honest.

⚠ **`CWP-044` ANSWERS *WHAT WOULD I PAY* AND `CWP-066` ANSWERS *WHAT AM I
PAYING*, AND NEITHER MAY CARRY THE OTHER'S ARITHMETIC.** The joining screen's
own worked figure is twelve months of `$1,501.09` → an average of `$125.09` →
a level of `$125.00`; this screen reads `$125.00` off the enrolled status
rather than dividing anything, and
`test_us_cwp_055_the_standing_level_is_the_one_cwp_044_computed` is what stops
the two drifting apart.

⚠ **AND THE VARIANCE IS A READ OF A CACHE WHOSE TRUTH IS THE EVENTS.**
`AccountBudgetStatus.variance_balance` is a running total of the append-only
`account_budget_events`, and `budget_service.recompute_balance` exists so the
two can be asserted equal. This file asserts it on the portal's own answer, so
a portal read that ever started summing events itself would go RED.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.billing import budget_service
from apps.billing import models as billing_models
from apps.portal import selectors as portal_selectors
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-054` §4's twelve months, reused deliberately: `CWP-044` computes
#: `$125.00` from them, and this screen must show the SAME `$125.00`.
TWELVE = (
    "98.4000", "104.2000", "112.7000", "121.3000", "148.9000", "171.4000",
    "182.2000", "163.5000", "131.0000", "112.4000", "101.8000", "53.2900",
)
ENROLLED_ON = date(2026, 1, 1)


def _enrol(tenant, sarah, account, *, actuals=TWELVE):
    """Enrol through `budget_service.enroll` — the ONE door.

    A test that wrote `account_budget_status` itself would prove nothing about
    the level the product actually computes, which is the whole subject of the
    first case below.
    """
    with tenant_context(tenant.id):
        return budget_service.enroll(
            actor=sarah,
            account_id=account.pk,
            trailing_actuals=tuple(Decimal(one) for one in actuals),
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=ENROLLED_ON,
        )


def _read(tenant, account):
    with tenant_context(tenant.id):
        return billing_seam.level_pay_standing(account.pk)


@pytest.mark.django_db
def test_us_cwp_055_the_standing_level_is_the_one_cwp_044_computed(pine_hill, sarah):
    """⚠ **THE INVARIANT BETWEEN THE TWO SCREENS.**

    `CWP-044` divides `$1,501.09` by twelve and rounds; `CWP-066` reads what
    enrolment stored. They must be the same number, and this asserts it against
    the joining screen's own read rather than against a literal typed twice.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _enrol(pine_hill, sarah, account)
    standing = _read(pine_hill, account)
    with tenant_context(pine_hill.id):
        joining = billing_seam.level_pay_position(account.pk)
    assert standing["level"] == "125.0000"
    assert joining["enrolled_level"] is not None
    assert Decimal(standing["level"]) == Decimal(joining["enrolled_level"])


@pytest.mark.django_db
def test_us_cwp_055_tc1_the_three_tiles(pine_hill, sarah):
    """TC-1 — *you pay `$125.00` · you are ahead · it settles up in <month>*.

    ⚠ **THE SETTLE-UP MONTH IS THE ACCOUNT'S OWN COPY**, taken at enrolment: a
    tenant that moves its month in September must not move it for an account
    already mid-year (`BR-TEN-043`).
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    standing = _read(pine_hill, account)
    assert standing["level"] == "125.0000"
    assert standing["enrolled_on"] == ENROLLED_ON.isoformat()
    assert standing["settle_up_month"] == status.settle_up_month
    # A freshly enrolled account is exactly level and says so in a WORD.
    assert standing["variance"] == "0.0000"
    assert standing["variance_direction"] == billing_seam.LEVEL


@pytest.mark.django_db
def test_us_cwp_055_tc7_ahead_is_a_direction_and_a_positive_size(pine_hill, sarah):
    """TC-7 — *ahead* and *behind* in words, never a bare signed number.

    `$47.30` ahead means the levels collected `$47.30` more than the customer
    used, which is the model's own reading of a POSITIVE `variance_balance`.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    with tenant_context(pine_hill.id):
        billing_models.AccountBudgetStatus.objects.filter(pk=status.pk).update(
            variance_balance=Decimal("47.3000")
        )
    standing = _read(pine_hill, account)
    assert standing["variance"] == "47.3000"
    assert standing["variance_direction"] == billing_seam.AHEAD


@pytest.mark.django_db
def test_us_cwp_055_tc2_behind_is_the_same_size_with_the_other_word(pine_hill, sarah):
    """TC-2 · negative — a customer `$47.30` BEHIND.

    ⚠ **THE SIZE IS THE SAME POSITIVE FIGURE AND ONLY THE WORD CHANGES.** A
    screen handed `-47.30` would have to decide how to word a minus, and the
    two screens would eventually word it differently.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    with tenant_context(pine_hill.id):
        billing_models.AccountBudgetStatus.objects.filter(pk=status.pk).update(
            variance_balance=Decimal("-47.3000")
        )
    standing = _read(pine_hill, account)
    assert standing["variance"] == "47.3000"
    assert standing["variance_direction"] == billing_seam.BEHIND


@pytest.mark.django_db
def test_us_cwp_055_the_variance_agrees_with_the_events_behind_it(pine_hill, sarah):
    """⚠ **THE CACHE AND ITS TRUTH, ASSERTED ON THE PORTAL'S OWN ANSWER.**

    `variance_balance` is a running total of the append-only events;
    `recompute_balance` derives the same figure from those rows. A portal read
    that ever started summing events itself would be a third answer, and this
    is the case that would go red.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    standing = _read(pine_hill, account)
    with tenant_context(pine_hill.id):
        derived = budget_service.recompute_balance(status)
    assert Decimal(standing["variance"]) == abs(derived)


@pytest.mark.django_db
def test_us_cwp_055_tc3_each_change_carries_what_happened(pine_hill, sarah):
    """TC-3 — every re-levelling listed with its actual, its movement and the
    balance after.

    ⚠ **THE ENROLMENT IS IN THE LIST TOO**, because *when did my amount become
    this* is the same question a re-levelling answers, and a list that started
    at the first change would leave a customer's first year unexplained.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _enrol(pine_hill, sarah, account)
    with tenant_context(pine_hill.id):
        budget_service.relevel(
            actor=sarah,
            account_id=account.pk,
            trailing_actuals=tuple(Decimal(one) for one in TWELVE[:-1] + ("353.2900",)),
            on_date=date(2026, 6, 30),
            manual=True,
        )
    standing = _read(pine_hill, account)
    events = [row["event"] for row in standing["changes"]]
    assert billing_models.BUDGET_EVENT_ENROLLED in events
    assert billing_models.BUDGET_EVENT_RELEVELED in events
    # Newest first — the change a customer is asking about is the last one.
    assert standing["changes"][0]["on"] >= standing["changes"][-1]["on"]
    for row in standing["changes"]:
        assert "balance_after" in row and "movement" in row
        # ⚠ B14 rule 31 — no row id on any change, not even part of one.
        assert "id" not in row


@pytest.mark.django_db
def test_us_cwp_055_tc4_the_override_shows_and_its_reason_does_not(pine_hill, sarah):
    """TC-4 · negative — the VALUE, never the internal reason.

    ⚠ **THE GUARD IS THAT THE BODY NEVER CARRIES IT** (`BR-CWP-052`'s posture).
    A screen that merely chose not to draw a field it was given is one careless
    edit from drawing it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    with tenant_context(pine_hill.id):
        budget_service.override_level(
            actor=sarah,
            account_id=account.pk,
            override=Decimal("160.0000"),
            reason="hardship agreed at the counter",
            on_date=date(2026, 3, 1),
        )
    standing = _read(pine_hill, account)
    assert standing["override"] == "160.0000"
    assert standing["computed_level"] == "125.0000"
    # The level a customer actually pays is the override.
    assert standing["level"] == "160.0000"
    assert "hardship" not in repr(standing)
    assert "reason" not in standing
    # ⚠ THE COLUMN STILL HOLDS IT — the guard is that the BODY does not.
    with tenant_context(pine_hill.id):
        stored = billing_models.AccountBudgetStatus.objects.get(pk=status.pk)
    assert stored.level_override_reason == "hardship agreed at the counter"


@pytest.mark.django_db
def test_us_cwp_055_tc5_a_customer_not_on_level_pay_is_routed(pine_hill, sarah):
    """TC-5 · negative — `standing: None`, and the SERVER names where to go.

    An empty standing screen would draw a variance of `$0.00`, which reads as
    *you are exactly level* rather than *this does not apply to you*.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert _read(pine_hill, account) is None
    with tenant_context(pine_hill.id):
        view = portal_selectors.level_pay_standing(account)
    assert view["standing"] is None
    assert view["months"] == []
    assert view["join_at"] == "/level-pay"


@pytest.mark.django_db
def test_us_cwp_055_tc6_another_utilitys_account_is_refused(pine_hill, sarah):
    """TC-6 · tenant isolation — `BR-CWP-010`, both halves in the query. An
    account outside the session's set answers the same 404 as one that does not
    exist."""
    import uuid

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{uuid.uuid4()}/level-pay/standing"
    )
    assert refused.status_code == 404, refused.content


@pytest.mark.django_db
def test_us_cwp_055_tc8_the_months_carry_what_was_paid_and_what_was_used(
    pine_hill, sarah
):
    """TC-8 — each row carries the month, what was paid and what was used.

    ⚠ **OUT OF THE `billed` EVENTS THE PROGRAMME ALREADY WRITES**, which hold
    the level IN FORCE that month and the actual. Re-reading invoices here
    would re-derive a level that may since have been re-levelled.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    status = _enrol(pine_hill, sarah, account)
    with tenant_context(pine_hill.id):
        billing_models.AccountBudgetEvent.objects.create(
            tenant_id=pine_hill.id,
            budget_status=status,
            account_id=account.pk,
            event=billing_models.BUDGET_EVENT_BILLED,
            level=Decimal("125.0000"),
            actual=Decimal("98.4000"),
            movement=Decimal("26.6000"),
            balance_after=Decimal("26.6000"),
            currency="USD",
            occurred_on=date(2026, 1, 31),
        )
        months = billing_seam.level_pay_months(account.pk)
    assert months == [
        {"month": "2026-01", "paid": "125.0000", "used": "98.4000", "currency": "USD"}
    ]


@pytest.mark.django_db
def test_us_cwp_055_the_standing_read_is_never_cached(pine_hill, sarah):
    """`BR-CWP-047` — the body carries what this customer pays a month and how
    far ahead or behind they are."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _enrol(pine_hill, sarah, account)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/level-pay/standing"
    )
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    assert response.json()["standing"]["level"] == "125.0000"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-055@d9d2f5f3 (EP-CWP-10)
# generated: 2026-09-04 by the CR-068 ending lane
# checklist: A✔ B✔ C✔ D✔(api.level_pay_standing) E✔(portal/plans/LevelPayStanding.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_055_level_standing.py · G81 · G84 · G96 · G82
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
