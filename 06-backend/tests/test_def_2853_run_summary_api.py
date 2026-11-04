# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2853 (the phase-4 summary is computed in full by
#           `release.summary_for` and reaches no endpoint and no screen —
#           S31 steps 4 and 5 draw "Not worked out" for customers, usage and
#           amount) · DEF-2854 (the release gate asks a clerk to sign that
#           they have seen a coverage figure the screen refuses to compute)
# Story:    US-BIL-005 (phase 4 — the summary and the gate)
#           Screens: S31 step 4 (See the totals) · S31 step 5 (Confirm & sign off)
# Rules:    BR-BIL-056 (the pre-release summary carries accounts · bills ·
#           consumption per service WITH its unit · amount with currency ·
#           category breakdowns; the SCREEN recalculates live — PO 2026-08-11
#           option B — while `bill_run_releases` is written once) ·
#           BR-BIL-057 (the category axes are PROPOSED, not ruled) ·
#           BR-BIL-059 (each confirmation is shown against its coverage, and a
#           missing mandate never blocks a release) · BR-BIL-036 (print is the
#           floor) · CLAUDE.md rule 2 (money with its currency) · rule 3 (every
#           quantity with its explicit unit) · BR-TEN-003 / HR-1 (another
#           tenant's run reads as absent)
# ───────────────────────────────────────────────────────
"""The read half of phase 4 — one route, and it is the only thing missing.

**HARD-WON LAW 2, AT THE ROUTING LAYER, FOR THE SECOND TIME ON THIS SCREEN.**
DEF-116 was `authorise_release` and `issue_run` built, tested and reachable from
no route. This is the same shape one function over: `release.summary_for` has
computed every figure BR-BIL-056 names since 2026-08-11 — accounts, bills,
consumption per service with its unit, amount with its currency, the derivable
category axes and the mandate coverage — and its only caller is
`POST .../release`, which STORES it into `bill_run_releases.summary` and never
serves it back. `EP-BIL-01`'s own field map wrote the gap down in prose eleven
days before this file: *"Built since 2026-08-11: `apps/billing/release.
summary_for` computes this row; still no endpoint and no screen"*. Nothing reads
prose for truth.

**WHY THE ABSENCE WAS INVISIBLE TO BOTH SUITES.** The backend tests call
`summary_for` directly, so every figure is proved correct. The frontend tests
assert the string *"Not worked out"* is on the screen, so the absence is
ASSERTED GREEN. Each half is internally honest and the product is wrong.

**WHY IT IS A GET AND NOT A FIELD ON `GET /billing/runs/{id}`.** `run_item` is
five grouped count queries and no money at all (BR-MET-078 as hardened by
CR-029); it is polled while a batch runs. This one sums bills, walks every
correction chain and reaches the customers seam, and it exists to be read ONCE
at the gate. Folding it in would put a money aggregation on a poll.

**AND IT RECALCULATES, WHICH IS THE POINT.** The PO chose option B on
2026-08-11 over their own worked figure — approve 480 bills at $52,847.19, void
two, and the screen must read 478. So this route computes on every call and
reads `bill_run_releases` never; `release_dict` is the other answer, and the two
are different questions on purpose.
"""

import uuid
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models
from core import errors

from tests.test_us_bil_005_issue import a_priced_draft, electric_gl_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    staff_actor,
    tenant_ctx,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: GT-1's frozen shape, which `a_priced_draft` writes: 684 kWh × $0.12 = 82.08
#: of usage plus an 18.50 base = **100.58**. The consumption assertion below is
#: that 684 and its unit, never a bare number (CLAUDE.md rule 3).
DRAFT_TOTAL = Decimal("100.58")
DRAFT_QUANTITY = Decimal("684")


def a_summary_world(tenant, actor, *, bills=1):
    """A run carrying `bills` priced drafts, each on its own account."""
    electric_gl_accounts()
    run = a_run(tenant, key="2026-06|summary-api")
    drafts = []
    for index in range(bills):
        account = an_account(actor, tenant, account_no=f"ACC-90{index:02d}")
        drafts.append(a_priced_draft(tenant, account, run, invoice_no=f"BL-2607-0002{index:02d}"))
    return run, drafts


def summary_call(tenant, run, *, role="billing_clerk", user=None):
    return api_call(
        billing_api.run_summary,
        "get",
        user=user if user is not None else FakeUser(user_id=uuid.uuid4()),
        role=role,
        tenant=tenant,
        run_id=str(run.pk),
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-2853 — the route exists. Asserted twice, as DEF-116's own file argues:
# an `api.py` that exports `urlpatterns` no URLconf includes is not an endpoint.
# ══════════════════════════════════════════════════════════════════════════
def test_def_2853__the_summary_route_is_mounted(brazos):
    from django.urls import resolve

    run_id = uuid.uuid4()
    assert resolve(f"/api/brazosbend/billing/runs/{run_id}/summary").func is billing_api.run_summary


def test_def_2853__the_summary_route_is_reachable_over_real_http(brazos):
    """401 means the route exists and asked for a session; 404 is the defect."""
    from django.test import Client

    path = f"/api/{brazos.subdomain}/billing/runs/{uuid.uuid4()}/summary"
    response = Client().get(path)
    assert response.status_code == 401, (
        f"{path} answered {response.status_code}: a 404 here means the phase-4 summary is "
        "still reachable from nothing, which is DEF-2853 exactly"
    )
    assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-056 — the four figures the PO named, all four present
# ══════════════════════════════════════════════════════════════════════════
def test_def_2853__the_four_po_named_figures_are_served(brazos, dana):
    """*"how many accounts, how many bills generated, how much consumption and
    how much bill amount and various categories"* — every one of them, and the
    consumption carries its unit rather than being a bare number.
    """
    with tenant_ctx(brazos):
        run, _drafts = a_summary_world(brazos, dana, bills=2)
        response = summary_call(brazos, run)

    assert response.status_code == 200
    body = response.data
    assert body["bill_run_id"] == str(run.pk)
    assert body["accounts"] == 2
    assert body["bills"] == 2
    # Money is TEXT with its currency beside it (rule 2 / DEF-099) — a JSON
    # number is a float the moment anything parses it.
    assert body["currency"] == "USD"
    assert Decimal(body["amount"]) == DRAFT_TOTAL * 2
    assert Decimal(body["gross_amount"]) == DRAFT_TOTAL * 2
    assert Decimal(body["credits_applied"]) == Decimal("0")
    # CLAUDE.md rule 3 — never a bare number. The unit is asserted as hard as
    # the quantity: a consumption figure without one cannot be sanity-checked,
    # which is the whole reason this panel is drawn before money goes out.
    assert len(body["consumption"]) == 1
    figure = body["consumption"][0]
    assert figure["service"] == "electric"
    assert Decimal(figure["quantity"]) == DRAFT_QUANTITY * 2
    assert figure["unit"] == "kWh"
    assert body["axes_status"] == "PROPOSED"


def test_def_2853__the_category_axes_are_served_and_flagged_proposed(brazos, dana):
    """BR-BIL-057's axes are DERIVED and the axis SET is not ruled.

    Both facts travel: the rows this deployment can compute, and the problem
    code that says the set itself is the PO's to give. A screen that showed the
    rows without the caveat would read as a menu somebody had chosen.
    """
    with tenant_ctx(brazos):
        run, _drafts = a_summary_world(brazos, dana)
        response = summary_call(brazos, run)

    codes = {problem["code"] for problem in response.data["problems"]}
    assert "category_axis_set_is_proposed" in codes
    axes = {row["axis"] for row in response.data["by_category"]}
    assert {"bill_type", "consumer_category", "service"} <= axes
    for row in response.data["by_category"]:
        assert row["currency"] == "USD"


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-059 — DEF-2854: the coverage each confirmation is shown against
# ══════════════════════════════════════════════════════════════════════════
def test_def_2854__mandate_coverage_is_served_beside_every_confirmation(brazos, dana):
    """A clerk is asked to sign *"I have seen how many customers are on
    automatic payment"*. This is the figure they are signing about.

    Autopay is derivable — `accounts.autopay` is a plain column on the row
    billing's one reviewed FK reaches. Email and SMS are not, and they come back
    with `covered: null` AND A NAMED REASON: *"0 of 2 hold an address"* and *"we
    could not count"* must never render the same (BR-BIL-036 — coverage is shown
    and never enforced).
    """
    with tenant_ctx(brazos):
        run, _drafts = a_summary_world(brazos, dana, bills=2)
        response = summary_call(brazos, run)

    coverage = {row["mandate"]: row for row in response.data["coverage"]}
    assert set(coverage) == {"autopay", "email", "sms"}
    assert coverage["autopay"]["accounts"] == 2
    assert coverage["autopay"]["covered"] is not None
    assert coverage["autopay"]["not_covered"] is not None
    assert coverage["autopay"]["covered"] + coverage["autopay"]["not_covered"] == 2
    for mandate in ("email", "sms"):
        row = coverage[mandate]
        if row["covered"] is None:
            assert row["unavailable_reason"], (
                f"{mandate} coverage is uncountable and says nothing about why — which is "
                "the zero-versus-unknown collapse BR-BIL-059 exists to prevent"
            )


# ══════════════════════════════════════════════════════════════════════════
# Isolation + the empty run
# ══════════════════════════════════════════════════════════════════════════
def test_def_2853__another_tenants_run_reads_as_absent(brazos, lonestar, dana):
    """HR-1 / BR-TEN-003 — a Brazos Bend run id in a Lone Star request 404s.

    ABSENT, not forbidden: a 403 would confirm the run exists, which is
    existence leaking one bit at a time. This route takes the run through the
    same `run_or_404` every other run route uses, so a cross-tenant id, an
    unknown id and a malformed one are one answer.
    """
    with tenant_ctx(brazos):
        run, _drafts = a_summary_world(brazos, dana)
    with tenant_ctx(lonestar):
        response = summary_call(lonestar, run)

    assert response.status_code == 404


def test_def_2853__a_run_with_no_bills_says_so_rather_than_reading_as_zero_value(brazos, dana):
    """A run of nothing and a run of zero value are different facts.

    The figures are honestly 0 and the problem list says which of the two this
    is, so the panel cannot be read as *"nothing to bill"* by a clerk who has
    not looked at the break list.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|summary-empty")
        response = summary_call(brazos, run)

    assert response.status_code == 200
    assert response.data["bills"] == 0
    assert response.data["amount"] == "0.000000"
    assert response.data["currency"] is None
    assert "run_has_no_countable_bills" in {p["code"] for p in response.data["problems"]}


def test_def_2853__the_screen_recalculates_and_the_stored_row_does_not(brazos, dana):
    """PO 2026-08-11, option B, on their own worked figure.

    Approve the run, then void a bill: the ROUTE must read the smaller set while
    `bill_run_releases` keeps what was signed. This is the assertion that makes
    the two answers different questions rather than a bug.
    """
    with tenant_ctx(brazos):
        run, drafts = a_summary_world(brazos, dana, bills=2)
        before = summary_call(brazos, run).data
        models.Invoice.objects.filter(pk=drafts[0].pk).update(status=models.INVOICE_VOID)
        after = summary_call(brazos, run).data

    assert before["bills"] == 2
    assert after["bills"] == 1
    assert Decimal(after["amount"]) == DRAFT_TOTAL
