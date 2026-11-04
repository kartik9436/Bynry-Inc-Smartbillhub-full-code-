# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8221 (Scope's Nobody to bill / Missing meter panels had
#           counts and no rows) · DEF-BIL-8222 (the template select offered
#           only the tenant's one fallback template)
# Rulings:  14-bulk-bill-run-changes.md row 42 (every link goes somewhere) ·
#           EP-BIL-01 TC-12 (panels) · BR-BIL-1041 (template chosen at Scope)
# Code:     apps/billing/run_scope.py (scope_list, run_templates) ·
#           apps/billing/run_scope_api.py (scope_list, scope_templates)
# ───────────────────────────────────────────────────────
"""The two Scope panels' rows and the template select's list, over HTTP.

RED FIRST: run against the tip before these reads existed, every case failed
on `AttributeError: module 'apps.billing.run_scope_api' has no attribute
'scope_list'` / `'scope_templates'` — the honest *not built* red.

The world is `test_bulk_run_scope.counted_world`, so the rows here are the
units and services its counts already count (1 and 1): a panel that listed a
row its count did not count, or missed one, goes red here AND there.
"""

from __future__ import annotations

import pytest

from apps.billing import run_scope, run_scope_api
from core import errors
from tests.test_bulk_run_scope import (
    a_cycle,
    a_draft_template,
    a_published_template,
    a_second_published_template,
    counted_world,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db


def listed(tenant, query, role="billing_clerk"):
    return api_call(
        run_scope_api.scope_list, "get", user=FakeUser(), role=role, tenant=tenant, query=query
    )


def templates(tenant, query=None, role="billing_clerk"):
    return api_call(
        run_scope_api.scope_templates,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        query=query or {},
    )


# ── DEF-BIL-8221 ─────────────────────────────────────────────────────────────


def test_nobody_to_bill_lists_the_unit_its_count_counts(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
    response = listed(brazos, {"cycle_id": str(cycle.id), "list": "nobody"}, role="executive")
    assert response.status_code == 200, response.data
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 1
    [row] = response.data["results"]
    assert row["unit"] == "Unit C"
    assert row["address"]
    assert row["services"]  # the unit's connected services, by code
    assert row["last_account"] is None
    assert row["unit_id"]  # for the Add account link — never the visible value


def test_missing_meter_lists_the_service_with_its_unit_and_account(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
    response = listed(brazos, {"cycle_id": str(cycle.id), "list": "missing_meter"})
    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    [row] = response.data["results"]
    assert row["address"] == "9104 Bluestem Ln"
    assert row["unit"] == "Unit D"
    assert row["service"] == "electric"
    assert row["account_no"] == "A-9104"


def test_the_lists_are_paged(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
    response = listed(
        brazos, {"cycle_id": str(cycle.id), "list": "nobody", "page": "2", "per": "25"}
    )
    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    assert response.data["results"] == []
    assert response.data["previous"] is not None


def test_a_list_is_refused_without_a_cycle_or_with_an_unknown_name(brazos):
    response = listed(brazos, {"list": "everyone"})
    assert response.status_code == 422
    assert {item["field"] for item in response.data["field_errors"]} == {"cycle_id", "list"}


def test_a_module_that_does_not_answer_is_named_not_a_500(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
    from apps.metering import selectors as metering_selectors

    def broken(*_args, **_kwargs):
        raise RuntimeError("meter reads is down")

    monkeypatch.setattr(metering_selectors, "units_in_cycle", broken)
    response = listed(brazos, {"cycle_id": str(cycle.id), "list": "nobody"})
    assert response.status_code == 503
    assert response.data["code"] == errors.SYS_PROVIDER
    assert response.data["message_key"] == run_scope.PROBLEMS["meter_reads_not_answering"][1]


def test_the_routes_are_mounted_ahead_of_the_run_item_route(brazos):
    from django.urls import resolve

    assert resolve("/api/brazosbend/billing/runs/scope-list").func is run_scope_api.scope_list
    assert (
        resolve("/api/brazosbend/billing/runs/scope-templates").func
        is run_scope_api.scope_templates
    )


# ── DEF-BIL-8222 ─────────────────────────────────────────────────────────────


def test_the_template_list_serves_every_published_bill_template_and_no_draft(brazos, dana):
    with tenant_ctx(brazos):
        fallback = a_published_template()
        second = a_second_published_template(dana)
        draft = a_draft_template(dana)
        a_cycle(brazos)
    response = templates(brazos, role="executive")
    assert response.status_code == 200, response.data
    ids = [row["id"] for row in response.data["results"]]
    assert str(fallback.pk) in ids
    assert str(second.pk) in ids
    assert str(draft.pk) not in ids
    assert response.data["count"] == len(ids)
    names = [row["name"] for row in response.data["results"]]
    assert names == sorted(names)
    assert all(isinstance(row["version_no"], int) for row in response.data["results"])


def test_a_draft_template_is_still_refused_by_name_at_scope(brazos, dana):
    """*Must be published* stays the refusal — the list narrowing is not the guard."""
    with tenant_ctx(brazos):
        draft = a_draft_template(dana)
        check = run_scope.ScopeCheck()
        assert run_scope._check_template(check, str(draft.pk)) is None
    assert "template_unpublished" in check.codes()


def test_another_utilitys_templates_are_not_listed(brazos, lonestar, dana):
    with tenant_ctx(lonestar):
        theirs = a_published_template()
    with tenant_ctx(brazos):
        a_published_template()
    response = templates(brazos)
    assert str(theirs.pk) not in [row["id"] for row in response.data["results"]]
