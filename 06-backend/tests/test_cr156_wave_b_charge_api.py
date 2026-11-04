"""CR-156-BRC10 wave B — the HTTP layer the charge-code screens read.

Wave A fixed the service and selector shape (CR-156-BRC10 §7). Wave B owns
`apps/rating/api.py`; these cases call the VIEWS, not the selectors under them,
so a route that never reaches its selector cannot pass (the shape DEF-RAT-5742
was filed about).

* `GET /charges/picker?kind=&service=` — the Add picker: free codes only (PO
  2026-10-01, *"when user select code from list show what are not in use
  only"*), a code a plan names is left OUT, not shown disabled;
* `GET /charges` — `kind_counts` beside the page (the *All · Base · Plan ·
  Other* chips), the `kind` filter, and the `kind` sort;
* `GET /charges/{id}` — `prices[]` with versions, `usage` (the tiles) and
  `versions` (the Audit tab): BASE-T CART-64 $12.00 → $13.00 from a future date
  reads as a SCHEDULED version whose change is `$12.00 → $13.00`, who and why
  from `rate_change_log`, over the IN-FORCE version it closes.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from apps.rating import api as rating_api
from apps.rating import models, seams, services
from apps.rating.constants import PRICE_HISTORY_EPOCH

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _request(env, path="/api/t/charges", **params):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get(path, params)
    force_authenticate(request, user=env.owner)
    request.tenant_role = "system_admin"
    request.tenant_id = env.tenant.id
    return request


def _configure_sizes(tenant):
    from apps.tenancy import models as tenancy_models

    for code, name in (("CART-35", "Trash 35-gallon cart"), ("CART-64", "Trash 64-gallon cart")):
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant, code=code, defaults={"name": name, "active": True, "is_system": True}
        )


def _code(env, code, kind, **extra):
    payload = {
        "code": code,
        "name": f"{code} fee",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "10.00",
        "kind": kind,
        "effective_from": PRICE_HISTORY_EPOCH.isoformat(),
        **extra,
    }
    return services.create_charge(env.admin, payload)


def _attach_to_a_plan(env, charge_id):
    plan = models.RatePlan.objects.create(tenant=env.tenant, code="P1", name="Plan one")
    models.PlanChargeRule.objects.create(
        tenant=env.tenant, rate_plan=plan, charge_id=charge_id
    )


# ── the picker ──────────────────────────────────────────────────────────────
def test_picker_offers_free_codes_only_and_leaves_an_in_use_code_out(env):
    with tenant_ctx(env.tenant):
        free = _code(env, "TRANSFER", "plan")
        used = _code(env, "LATE", "plan")
        _code(env, "REREAD", "other")
        _attach_to_a_plan(env, used["id"])
        body = rating_api.charge_picker(_request(env, "/api/t/charges/picker", kind="plan")).data
    codes = [row["code"] for row in body["results"]]
    assert codes == ["TRANSFER"], codes  # LATE is named by a plan; REREAD is another kind
    assert body["results"][0]["id"] == free["id"]
    assert set(body["results"][0]) == {"id", "code", "name", "charge_type", "kind", "service"}


def test_picker_refuses_a_kind_it_does_not_know(env):
    with tenant_ctx(env.tenant):
        response = rating_api.charge_picker(_request(env, "/api/t/charges/picker", kind="banana"))
    assert response.status_code == 422, response.status_code
    fields = [fe["field"] for fe in response.data["field_errors"]]
    assert fields == ["kind"]


def test_picker_route_is_declared_before_the_id_route():
    names = [str(p.pattern) for p in rating_api.urlpatterns]
    assert names.index("charges/picker") < names.index("charges/<str:charge_id>")


# ── the list: kind counts, the kind filter, the kind sort ───────────────────
def test_list_serves_kind_counts_under_the_other_filters(env):
    with tenant_ctx(env.tenant):
        _code(env, "CONN", "plan")
        _code(env, "LATE", "plan")
        _code(env, "REREAD", "other")
        body = rating_api.charges(_request(env, **{"f.kind": "plan"})).data
        searched = rating_api.charges(_request(env, q="REREAD")).data
    assert [row["code"] for row in body["results"]] == ["CONN", "LATE"]
    # The chips count every kind under the OTHER filters, not under the chip.
    assert body["kind_counts"]["plan"] == 2 and body["kind_counts"]["other"] >= 1
    assert body["kind_counts"]["all"] >= 3
    assert searched["kind_counts"] == {"all": 1, "base": 0, "plan": 0, "other": 1}


def test_list_sorts_by_kind(env):
    with tenant_ctx(env.tenant):
        _code(env, "AAA", "other")
        _code(env, "ZZZ", "base", is_base=True)
        body = rating_api.charges(_request(env, sort="kind", dir="asc", q="")).data
    kinds = [row["kind"] for row in body["results"] if row["code"] in ("AAA", "ZZZ")]
    assert kinds == ["base", "other"]


# ── the detail: usage tiles and price versions ──────────────────────────────
def test_detail_serves_versions_scheduled_over_in_force_with_who_and_why(env):
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "BASE-T",
                "name": "Trash base",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "kind": "base",
                "effective_from": PRICE_HISTORY_EPOCH.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "12.00"},
                ],
            },
        )
        start = seams.tenant_today() + timedelta(days=31)
        services.update_charge(
            env.admin,
            created["id"],
            {
                "effective_from": start.isoformat(),
                "reason": "Board approved, Oct 2026",
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "13.00"},
                ],
            },
        )
        body = rating_api.charge_item(
            _request(env, f"/api/t/charges/{created['id']}"), created["id"]
        ).data
    assert "usage" in body and (body["usage"] is None or body["usage"]["bills"] == 0)
    scheduled, in_force = body["versions"]
    assert scheduled["state"] == "scheduled" and scheduled["effective_from"] == start.isoformat()
    assert scheduled["changes"] == [
        {
            "size_class": "CART-64",
            "customer_class": None,
            "before_display": "12.00",
            "after_display": "13.00",
            "new": False,
        }
    ]
    assert scheduled["why"] == "Board approved, Oct 2026"
    assert in_force["state"] == "in_force" and in_force["created"] is True
    assert in_force["effective_to"] == (start - timedelta(days=1)).isoformat()
    # The dated history is whole: the $12.00 row is KEPT, closed and killed.
    cart64 = [p for p in body["prices"] if p["size_class"] == "CART-64"]
    assert [(p["amount_display"], p["killed"], p["version"]) for p in cart64] == [
        ("12.00", True, 1),
        ("13.00", False, 2),
    ]
