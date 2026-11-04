# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (S22/S35 Record payment) · US-CUS-012 (the account's own
#           Record/Adjust controls)
#           Screens: S33 (Record payments — the type select) · S21/S22 (the
#           account's `Adjust` quick action and its Adjustments tab)
# Change:   CR-059 CS-35, 2026-09-02 — which taught `record_payment` the type
#           AND the reason, and published neither list to a screen.
# Defects:  DEF-PAY-5128 (S33 offers Credit and Adjustment and sends no reason,
#           so both are incapable of passing) · DEF-CUS-5126 (the account's
#           `Adjust` refuses on an endpoint that exists)
# Rules:    BR-TEN-036 (a reason comes from the tenant's OWN maintained list) ·
#           BR-PAY-012 · BR-PAY-020 (System-Admin approval above the tenant
#           threshold) · BR-SHL-025 (a screen that hides a control is not an
#           authorisation) · CLAUDE.md rule 1 (tenant scoping) · hard-won law 2
# ───────────────────────────────────────────────────────
"""`GET /payments/reason-codes` — the list a live control has needed since 2026-09-02.

**WHY THIS FILE EXISTS, and it is hard-won law 2 rather than a missing feature.**
`CR-059` CS-35 landed three things on 2026-09-02: `record_payment` learned
`payment_type`, it learned `reason_code`, and S33 got a `<select>` offering
*Payment*, *Credit* and *Adjustment*. `services._reason_code` REFUSES a credit or
an adjustment carrying no reason, **by name**. Nothing was ever published for a
screen to fill a reason picker from — `apps.tenancy.selectors.active_reason_codes`
was written for exactly this and had **zero callers** for eleven days.

So two of the three options on a live control could only ever fail, and the suite
was green over it: every test of that form drives the default `payment`, for which
a reason is REFUSED. That is a check exercising the one branch that works.

**THE FIRST CASE IS PLUMBING AND NOT MONEY, ON PURPOSE.** A view function that
exists is not an endpoint until `config/urls.py` resolves it and a real request
survives the middleware, the authentication and the permission class. **401 means
the route exists and asked for a sign-in; 404 means there is no route** — which is
exactly what this path answered before this lane, and is the assertion that was
shown RED first.

**WHY NOT `GET /lookups/reason_codes`.** That route is gated on
`SettingsReadAnyWriteSystemAdmin` and A4 gives the **Billing Clerk no
`settings_lookups` cell at all** — so the one role A4 lets *Request* an adjustment
(`adjustment_approval`: billing_clerk = Request) cannot read the reasons through
Settings. These are the same rows on the surface that role can reach, which is why
the last case asserts a Billing Clerk gets them.
"""

import uuid

import pytest

from core import errors

from apps.payments import api as payments_api
from apps.payments import ledger_seam
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def read(tenant, *, role="billing_clerk"):
    """GET /payments/reason-codes exactly as the reason picker calls it."""
    return api_call(
        payments_api.payment_reason_codes,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
    )


# ══════════════════════════════════════════════════════════════════════════
# Is it REACHABLE at all? (hard-won law 2 — the case shown RED first)
# ══════════════════════════════════════════════════════════════════════════
def test_def5128_the_route_is_mounted_and_reachable_through_the_whole_stack(brazos):
    from django.test import Client
    from django.urls import resolve

    assert (
        resolve("/api/brazosbend/payments/reason-codes").func
        is payments_api.payment_reason_codes
    )

    path = f"/api/{brazos.subdomain}/payments/reason-codes"
    response = Client().get(path)
    assert response.status_code == 401, (
        f"GET {path} answered {response.status_code}: a 404 here means the route is still "
        "not reachable, whatever the URLconf says — which is the state DEF-PAY-5128 records"
    )
    assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


def test_def5128_the_literal_route_is_not_shadowed_by_a_payment_id(brazos):
    """`payments/reason-codes` must not be read as a payment id.

    The DEF-520 route-ordering shape. There is no `payments/<id>` route today,
    so this asserts the property rather than a past failure — the day one is
    added, this is the case that says where it may go.
    """
    from django.urls import resolve

    # The tenant segment is captured by the OUTER resolver's regex rather than
    # as a kwarg, so `.kwargs` is `{}` here — asserting a kwarg would have been
    # a test looking at the wrong thing. What actually decides the question is
    # WHICH VIEW the literal reaches: a `payments/<id>` route placed above this
    # one would resolve it to that view with `reason-codes` as the id.
    match = resolve("/api/brazosbend/payments/reason-codes")
    assert match.func is payments_api.payment_reason_codes
    assert match.args == ()
    assert match.kwargs == {}


# ══════════════════════════════════════════════════════════════════════════
# THE ROWS — the tenant's own five, and the SAME rows the recorder validates
# ══════════════════════════════════════════════════════════════════════════
def test_def5128_it_serves_this_tenants_five_seeded_reasons(brazos):
    body = read(brazos).data
    codes = [row["code"] for row in body["reasons"]]

    # BR-TEN-036 / `tenancy/0004` SEED_REASON_CODES, in code order.
    assert codes == ["BILLERR", "DISPUTE", "GOODWILL", "LEAK", "METERR"]
    assert body["count"] == 5
    # Every row carries the NAME a clerk reads, never a bare code and never a
    # database id (B14 rule 31).
    assert all(row["name"] for row in body["reasons"])
    assert all(set(row) == {"code", "name"} for row in body["reasons"])


def test_def5128_the_picker_and_the_recorder_read_the_same_rows(brazos):
    """The whole reason this goes through tenancy rather than a seed list here.

    A picker built on its own copy would eventually offer a reason the recorder
    refuses, and the clerk would meet a server error on a value the screen had
    just handed them.
    """
    from apps.tenancy import selectors as tenancy_selectors

    offered = {row["code"] for row in read(brazos).data["reasons"]}
    # The selector reads `app.tenant_id`, which the REQUEST sets and a bare call
    # does not — so the comparison is made inside the same tenant context the
    # recorder validates in.
    with tenant_ctx(brazos):
        validated = {row["code"] for row in tenancy_selectors.active_reason_codes()}
    assert offered == validated


def test_def5128_a_deactivated_reason_leaves_the_picker(brazos):
    """`[]` — never the seeded five — when a tenant deactivates every reason.

    Offering the seeds back would offer codes the recorder then refuses, which
    is the same posture `usePaymentMethods` takes on the S22 form.
    """
    tenancy_models.ReasonCode.objects.filter(tenant=brazos).update(active=False)
    body = read(brazos).data
    assert body["reasons"] == []
    assert body["count"] == 0


# ══════════════════════════════════════════════════════════════════════════
# THE ROLE — the one A4 lets *Request* an adjustment can read the reasons
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("role", ["billing_clerk", "system_admin", "executive"])
def test_def5128_every_role_that_records_or_approves_can_read_them(brazos, role):
    """A4 `adjustment_approval`: billing_clerk = Request · admin/executive =
    Approve. A clerk who cannot read the reasons cannot request an adjustment
    at all, and `GET /lookups/reason_codes` gives them no cell."""
    assert read(brazos, role=role).status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# TENANT SCOPING (CLAUDE.md rule 1)
# ══════════════════════════════════════════════════════════════════════════
def test_def5128_one_tenants_reasons_never_reach_another(brazos, lonestar):
    """Two tenants, two lists, no leak. `active_reason_codes` filters on
    `_tenant_id()` and the request sets it; this asserts the join, not the
    filter's source code."""
    tenancy_models.ReasonCode.objects.create(
        tenant=brazos, code="ZZBRAZOS", name="Brazosbend only", active=True
    )
    brazos_codes = {row["code"] for row in read(brazos).data["reasons"]}
    other_codes = {row["code"] for row in read(lonestar).data["reasons"]}
    assert "ZZBRAZOS" in brazos_codes
    assert "ZZBRAZOS" not in other_codes


# ══════════════════════════════════════════════════════════════════════════
# THE SEAM REFUSES BY NAME rather than falling back to a seeded list
# ══════════════════════════════════════════════════════════════════════════
def test_def5128_an_unpublished_tenancy_read_refuses_rather_than_guessing(
    brazos, monkeypatch
):
    from apps.payments.exceptions import PaymentRuleError

    monkeypatch.setattr(ledger_seam, "REASON_CODE_LIST", "no_such_selector_" + uuid.uuid4().hex)
    with pytest.raises(PaymentRuleError) as refusal:
        ledger_seam.active_reason_codes()
    assert refusal.value.br_ref == "BR-TEN-036"
