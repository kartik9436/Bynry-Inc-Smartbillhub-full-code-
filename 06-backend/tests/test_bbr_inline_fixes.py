# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-6 (fix a blocked account inline: written by its
#           owning module, the row reads Fixed · re-checked, it moves to Ready)
# Defects:  DEF-BIL-8218 (no owning-module write behind the Fix column) ·
#           DEF-BIL-8247 (a standing-charges-only account with no reading
#           blocked by the missing-multiplier refusal)
# Rules:    B1 / CLAUDE.md module map (no cross-module write) · rule 7
# Plan:     15-bulk-bill-run-build-plan.md B14, F10, B23 · T1, T3
# ───────────────────────────────────────────────────────
"""Inline fixes on the Check, written red first.

Red against `c0e8cbbe9`: there is no `POST …/check/fix` and no
`apps.billing.check_fixes`; a missing connection size arrives as
`ruled_path_refused` with no params naming it; a vacation-hold account with
no reading is blocked by *"billing's read seam publishes no meter
multiplier"*.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from apps.billing import check_api, check_store
from apps.metering import models as metering_models

from tests.test_bbr_check_engine import FIXTURE_WARNINGS, three_accounts
from tests.test_bbr_check_store import a_run, saved_status
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _no_base_code(service):
    """The fixture's base code stops being the service's base, so the base is
    NOT one price for all sizes (`DEF-RAT-8822`) and the ruled path still holds
    an unsized meter with `connection_size_unresolved`."""
    from apps.rating import models as rating_models

    rating_models.Charge.objects.filter(code=f"BASE-{service.upper()}-FIXTURE").update(is_base=False)


def _fix(run, tenant, user, data, role="billing_clerk"):
    return api_call(
        check_api.run_check_fix,
        "post",
        user=user,
        role=role,
        tenant=tenant,
        data=data,
        run_id=str(run.pk),
    )


# ══════════════════════════════════════════════════════════════════════════
# The boundary: billing writes no other module's table
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36
def test_8218__check_fixes_imports_no_other_module_and_names_each_owner():
    from apps.billing import check_fixes

    source = inspect.getsource(check_fixes)
    for module in ("metering", "assets", "customers", "rating"):
        assert f"from apps.{module}" not in source and f"import apps.{module}" not in source
    assert {f.owner for f in check_fixes.FIXES.values()} == {
        ("metering", "services", "assign_unit_plan"),
        ("assets", "services", "update_asset"),
        ("metering", "services", "update_premises"),
    }


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · choose a plan on the row → Accounts' own write → re-checked → Ready
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36
def test_8218_tc6__a_plan_chosen_on_the_row_is_written_by_its_owner_and_rechecked(
    brazos, dana, audit_rows
):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, plan, accounts = three_accounts(brazos, dana)
        a102 = accounts["A-00102"]
        metering_models.Unit.objects.filter(pk=a102.unit_id).update(rate_plan=None)
        run = a_run(cycle)
        check_store.check_run(run)
        before = saved_status(run, a102)
        clerk = an_actor_user(brazos)
        findings = check_store.account_findings(run, str(a102.id))["findings"]

    # PO 2026-10-01 (BR-BIL-1063): no plan BLOCKS until the plan is fixed.
    assert before == ("blocked", ["unit_has_no_plan"])
    assert [f["fix_here"] for f in findings] == ["set_plan"]

    answer = _fix(
        run, brazos, clerk, {"account_id": str(a102.id), "fix": "set_plan", "plan_id": str(plan.id)}
    )
    assert answer.status_code == 200, answer.data
    assert answer.data["account"]["status"] == "ready"
    with tenant_ctx(brazos):
        unit = metering_models.Unit.objects.get(pk=a102.unit_id)
        after = saved_status(run, a102)
    assert str(unit.rate_plan_id) == str(plan.id)  # the unit's plan, metering's row
    assert after[0] == "ready" and not set(after[1]) - FIXTURE_WARNINGS
    actions = [row.get("action") for row in audit_rows]
    assert "unit.plan_assigned" in actions  # the OWNER audited its write
    assert "bill_run.check_fix_applied" in actions  # and the Check its act


# BULK-CHG-36
def test_8218__a_fix_for_a_problem_the_account_does_not_have_is_refused(brazos, dana):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        clerk = an_actor_user(brazos)
    answer = _fix(
        run,
        brazos,
        clerk,
        {"account_id": str(accounts["A-00101"].id), "fix": "set_plan", "plan_id": str(plan.id)},
    )
    assert answer.status_code == 422
    assert answer.data["message_key"] == "billing.check.fix.notOnThisAccount"


# BULK-CHG-36
def test_8218__a_viewer_cannot_fix_and_another_tenant_cannot_see_the_run(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        cycle, plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
    body = {"account_id": str(accounts["A-00101"].id), "fix": "set_plan", "plan_id": str(plan.id)}
    assert _fix(run, brazos, FakeUser(), body, role="executive").status_code == 403
    assert _fix(run, lonestar, FakeUser(), body).status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# A missing connection size: named on the row, fixed on the meters
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36 · BULK-CHG-46
def test_8218__a_size_set_on_the_row_is_written_to_the_meter_and_rechecked(
    brazos, dana, audit_rows
):
    from apps.assets import models as asset_models

    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        a106 = accounts["A-00106"]
        asset_models.Asset.objects.filter(asset_no="M-9106").update(size_class=None)
        # `DEF-RAT-8822` (PO 2026-10-01, option A): an unsized meter is held
        # only where the base is not one price for every size. The fixture's
        # base is one $18.50 for all sizes, which now BILLS with a warning, so
        # it is taken away here — the case where the ruled path still holds
        # with `connection_size_unresolved` and this inline fix is offered.
        _no_base_code("electric")
        run = a_run(cycle)
        check_store.check_run(run)
        [found] = check_store.account_findings(run, str(a106.id))["findings"]
        clerk = an_actor_user(brazos)

    assert found["code"] == "ruled_path_refused"
    assert found["params"] == {"blocked": "connection_size_unresolved", "service_code": "electric"}
    assert found["fix_here"] == "set_size"

    answer = _fix(
        run,
        brazos,
        clerk,
        {"account_id": str(a106.id), "fix": "set_size", "size_class": "E-1P-100"},
    )
    assert answer.status_code == 200, answer.data
    assert answer.data["written"]["service_code"] == "electric"
    with tenant_ctx(brazos):
        size = asset_models.Asset.objects.get(asset_no="M-9106").size_class
        after = saved_status(run, a106)
    assert size == "E-1P-100"
    assert after[0] == "ready" and not set(after[1]) - FIXTURE_WARNINGS
    assert "asset.updated" in [row.get("action") for row in audit_rows]


# ══════════════════════════════════════════════════════════════════════════
# City limits: written on the PREMISES by metering
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36
def test_8218__city_limits_are_written_on_the_premises_by_metering(brazos, dana, monkeypatch):
    """Routing only: the premises flag goes to `metering.services.update_premises`
    with the unit's premises, and the account is re-checked. (A plan that
    surcharges outside the city is `test_def_484_size_and_jurisdiction`'s.)"""
    from apps.billing import check_fixes, check_models
    from apps.metering import services as metering_services

    calls = []
    monkeypatch.setattr(
        metering_services,
        "update_premises",
        lambda actor, premises_id, changes: calls.append((str(premises_id), changes)) or {},
    )
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        a101 = accounts["A-00101"]
        run = a_run(cycle)
        check_store.check_run(run)
        row = check_models.BillRunAccountCheck.objects.get(bill_run=run, account_id=a101.id)
        check_models.BillRunFinding.objects.create(
            tenant=brazos,
            bill_run=run,
            account_check=row,
            account_id=a101.id,
            code="premises_jurisdiction_unstated",
            category="accounts_units",
            severity="decision",
            service_code="electric",
            detail="unstated",
            check_step="services",
        )
        answer = check_fixes.apply_fix(
            run,
            account_id=str(a101.id),
            fix="set_city_limits",
            payload={"inside_city_limits": True},
            actor=dana,
        )
        premises_id = metering_models.Unit.objects.get(pk=a101.unit_id).premises_id

    assert calls == [(str(premises_id), {"inside_city_limits": True})]
    assert "premises_jurisdiction_unstated" not in [
        f["code"] for f in answer["account"]["findings"]
    ]


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8247 · standing charges only, no reading → not blocked
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-49
def test_8247__a_vacation_hold_account_with_no_reading_is_not_blocked(brazos, dana):
    """The PO's case 2 account (standing charges only) with NO reading this
    period. It bills no usage, so a missing multiplier cannot understate
    anything; before the fix it was blocked by *"billing's read seam publishes
    no meter multiplier"*."""
    from apps.billing import runs

    from tests.test_bbr_fixed_charge_next_bill import SEPTEMBER, _mine, _setup

    with tenant_ctx(brazos):
        cycle, _account, _asset = _setup(
            brazos,
            dana,
            account_no="A-08247",
            asset_no="M-8247",
            base="26",
            status_code="vacation_hold",
        )
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=SEPTEMBER[0],
            period_end=SEPTEMBER[1],
            service_date=date(2026, 10, 1),
        )
    blocked = [(p.account_no, p.reason, p.detail) for p in prepared.blocked]
    assert _mine(prepared, "A-08247"), blocked
    [data] = _mine(prepared, "A-08247")
    assert runs.price_account(data).priced.total == 26


# BULK-CHG-49
def test_8247__a_usage_billed_service_with_no_multiplier_is_still_refused():
    """The guard is kept where it bites: a service whose USAGE is billed still
    refuses a missing factor (`resolution_shadow.adapt`)."""
    from apps.billing import resolution_shadow

    source = inspect.getsource(resolution_shadow.adapt)
    assert "if multiplier is None and not _has_no_meter_at_all(reading) and usage_billed:" in source
