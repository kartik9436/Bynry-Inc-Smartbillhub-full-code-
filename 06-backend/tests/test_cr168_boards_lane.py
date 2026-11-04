# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 §30, lane BOARDS — the server half of three of the
#           PO's four answers of 2026-10-05 (decision log *"FOUR PO ANSWERS ON
#           WORK"*).
# Rules:    answer (2), verbatim: *"(b) Add a daily limit per technician
#           (default 6), editable on the technician's page."* · answer (3),
#           verbatim: *"(b) Only raise jobs for meters that are installed."* ·
#           ruling 2 (the match advises and never blocks) · NFR-3 · NFR-5 ·
#           hard rule 7 (audit) · DEF-WRK-9661 (one check, the preview and the
#           sweep agree)
# Tests:    this file — SQLite and PostgreSQL 16 (`--ds=config.settings.pgtest`)
# ───────────────────────────────────────────────────────
"""A technician carries a daily job limit (default 6), the advice says when a
day goes over it, and the certification rules find only installed meters."""

from __future__ import annotations

import datetime as dt

import pytest

from apps.assets import models as assets_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import advice
from apps.work import api as work_api
from apps.work import models as work_models
from apps.work import rules, workforce

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

@pytest.fixture()
def stored_audit():
    """The REAL trail, so a read of `audit_log` sees what the service wrote."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


YESTERDAY = dt.date.today() - dt.timedelta(days=1)
DAY = dt.date.today() + dt.timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════════
# Answer (2) — the daily job limit
# ══════════════════════════════════════════════════════════════════════════


def _technician(tenant, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _jobs_for(dana, tech, n, day=DAY):
    """`n` open jobs held by `tech`, each windowed on `day` at noon in the
    utility's zone — the jobs the advice counts as *that day*."""
    from apps.work.seams import tenancy_seam

    premises = make_premises(dana, address_line=f"{n} Limit Ln", services_available=["water"])
    noon = dt.datetime.combine(day, dt.time(12, 0)).replace(tzinfo=tenancy_seam.tenant_timezone())
    ids = []
    for _ in range(n):
        raised = w6.create_work_order(
            dana, None, {"type": "Leak investigation", "premises_id": premises["id"]}
        )
        ids.append(raised["id"])
    work_tables.WorkOrder.objects.filter(pk__in=ids).update(
        assignee_technician_id=tech.id, window_start=noon, window_end=noon + dt.timedelta(hours=2)
    )
    return ids


def test_a_technician_reads_a_daily_limit_of_six_by_default(brazos, dana):
    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        assert ortiz.daily_job_limit == 6
        detail = workforce.technician_by_slug(workforce.technician_slug(ortiz))
        assert detail["daily_job_limit"] == 6


def test_the_limit_is_edited_on_the_technicians_page_and_audited(brazos, dana, stored_audit):
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        slug = workforce.technician_slug(ortiz)
    response = api_call(
        work_api.technician, "patch", f"/api/{brazos.subdomain}/work/technicians/{slug}",
        user=dana.user, role="system_admin", tenant=brazos, data={"daily_job_limit": 8}, slug=slug,
    )
    assert response.status_code == 200, response.data
    assert response.data["daily_job_limit"] == 8
    # Editing the limit is not an availability write: the status stands.
    assert response.data["status"] == "on_shift"
    with tenant_ctx(brazos):
        ortiz.refresh_from_db()
        assert ortiz.daily_job_limit == 8
        row = audit_models.AuditLog.objects.filter(action="work.technician.daily_limit_set").get()
        assert (row.before, row.after) == ({"daily_job_limit": 6}, {"daily_job_limit": 8})


@pytest.mark.parametrize("bad", [0, -1, "six", "", None, 2.5])
def test_a_limit_that_is_not_a_whole_number_of_one_or_more_is_refused(brazos, dana, bad):
    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        slug = workforce.technician_slug(ortiz)
    response = api_call(
        work_api.technician, "patch", f"/api/{brazos.subdomain}/work/technicians/{slug}",
        user=dana.user, role="system_admin", tenant=brazos, data={"daily_job_limit": bad}, slug=slug,
    )
    assert response.status_code == 422, response.data
    with tenant_ctx(brazos):
        ortiz.refresh_from_db()
        assert ortiz.daily_job_limit == 6


def test_no_upper_bound_on_the_limit(brazos, dana):
    """NFR-5 — the limit is the utility's figure; nothing caps it."""
    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        workforce.set_daily_job_limit(dana, ortiz.id, 400)
        ortiz.refresh_from_db()
        assert ortiz.daily_job_limit == 400


def test_the_worked_case_limit_six_seven_jobs_is_over_and_six_is_not(brazos, dana):
    """The PO's worked case: limit 6, D. Ortiz with 7 jobs turns red. R. Patel
    with exactly 6 is AT his limit, not over it. A crew carries no limit."""
    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        patel = _technician(brazos, "patel@b.test", "R. Patel")
        work_models.Crew.objects.create(tenant_id=brazos.id, name="Field crew B")
        _jobs_for(dana, ortiz, 7)
        _jobs_for(dana, patel, 6)

        page = advice.candidates_page(on=DAY)
        by_name = {row["name"]: row["advice"] for row in page["rows"]}
        assert (by_name["D. Ortiz"]["jobs_that_day"], by_name["D. Ortiz"]["daily_job_limit"]) == (7, 6)
        assert by_name["D. Ortiz"]["over_daily_limit"] is True
        assert (by_name["R. Patel"]["jobs_that_day"], by_name["R. Patel"]["over_daily_limit"]) == (6, False)
        assert by_name["Field crew B"]["daily_job_limit"] is None
        assert by_name["Field crew B"]["over_daily_limit"] is False

        # Raise his limit to 7 and the same day is no longer over.
        workforce.set_daily_job_limit(dana, ortiz.id, 7)
        again = {row["name"]: row["advice"] for row in advice.candidates_page(on=DAY)["rows"]}
        assert again["D. Ortiz"]["over_daily_limit"] is False


def test_over_the_limit_never_refuses_an_assignment(brazos, dana):
    """Ruling 2 — advice, never a block. An eighth job is given to a person
    whose limit is 6 and already holds 7."""
    from apps.work import dispatch

    with tenant_ctx(brazos):
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz")
        _jobs_for(dana, ortiz, 7)
        premises = make_premises(dana, address_line="8 Over Ln", services_available=["water"])
        raised = w6.create_work_order(dana, None, {"type": "Leak investigation", "premises_id": premises["id"]})
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        assert str(work_tables.WorkOrder.objects.get(pk=raised["id"]).assignee_technician_id) == str(ortiz.id)


# ══════════════════════════════════════════════════════════════════════════
# Answer (3) — the certification rules raise only on installed meters
# ══════════════════════════════════════════════════════════════════════════


def _template(actor, *, name, service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _installed_meter(dana, brazos, asset_no):
    """A meter in the ground through its OPEN assignment (`BR-AST-017`)."""
    premises = make_premises(dana, address_line=f"{asset_no} Main St", services_available=["electric"])
    unit = make_unit(dana, premises["id"], label=f"Unit {asset_no}")
    meter = make_asset(dana, asset_no=asset_no)
    assets_models.AssetAssignment.objects.create(
        tenant_id=brazos.id, asset_id=meter["id"], unit_id=unit["id"], from_date=dt.date(2024, 1, 1)
    )
    return premises, meter


def _past_due(asset, due=YESTERDAY):
    assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=due)


def test_a_warehouse_meter_is_not_raised_and_the_preview_says_the_same(brazos, dana):
    """The PO's case: *"a meter on the shelf with a lapsed certificate gets a
    job with no address"*. Two meters past certification — one installed, one
    on the shelf. The preview, the rule's Tonight and the sweep all say ONE."""
    with tenant_ctx(brazos):
        premises, installed = _installed_meter(dana, brazos, "M-30A")
        shelf = make_asset(dana, asset_no="M-30B")
        _past_due(installed)
        _past_due(shelf)
        template = _template(dana, name="Meter exchange")
        triggers = [{"kind": "asset_age_rule", "params": {}}]

        preview = rules.preview({"template_id": template["id"], "triggers": triggers})
        assert (preview["subjects"], preview["would_raise"], preview["cannot_raise"]) == (1, 1, 0)

        rule = rules.create_rule(dana, {"name": "Past cert", "template_id": template["id"], "triggers": triggers})
        assert rules.rule_detail(rule["id"])["tonight"]["would_raise"] == 1

        report = rules.sweep(dana, rule_ids=[rule["id"]])["rules"][0]
        assert report["raised"] == preview["would_raise"] == 1
        orders = list(work_tables.WorkOrder.objects.filter(rule_id=rule["id"]))
        assert [str(o.asset_id) for o in orders] == [str(installed["id"])]
        assert str(orders[0].premises_id) == str(premises["id"])


def test_due_soon_skips_a_warehouse_meter_too(brazos, dana):
    with tenant_ctx(brazos):
        _premises, installed = _installed_meter(dana, brazos, "M-30C")
        shelf = make_asset(dana, asset_no="M-30D")
        soon = dt.date.today() + dt.timedelta(days=10)
        _past_due(installed, soon)
        _past_due(shelf, soon)
        template = _template(dana, name="Meter test")
        preview = rules.preview(
            {"template_id": template["id"],
             "triggers": [{"kind": "compliance_calendar", "params": {"days_ahead": 30}}]}
        )
        assert (preview["subjects"], preview["would_raise"]) == (1, 1)


def test_a_meter_on_a_service_point_counts_as_installed(brazos, dana):
    """The other way into the ground: a service point (every point sits on a
    unit, and so on a premises)."""
    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models
    from apps.work.seams import assets_seam

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="30 Point Rd", services_available=["electric"])
        unit = make_unit(dana, premises["id"], label="Unit P")
        point = metering_models.ServicePoint.objects.create(
            tenant_id=brazos.id, unit_id=unit["id"],
            service=tenancy_models.Service.objects.get(code="electric"),
        )
        meter = make_asset(dana, asset_no="M-30E")
        _past_due(meter)
        assert "M-30E" not in [r["asset_no"] for r in assets_seam.assets_past_certification()]
        assets_models.Asset.objects.filter(pk=meter["id"]).update(service_point_id=point.id)
        assert "M-30E" in [r["asset_no"] for r in assets_seam.assets_past_certification()]


def test_a_job_already_raised_on_a_warehouse_meter_is_left_alone(brazos, dana):
    """*"Jobs already raised on warehouse meters are left as they are, not
    deleted."* A job raised before the change stays open after a sweep."""
    with tenant_ctx(brazos):
        shelf = make_asset(dana, asset_no="M-30F")
        _past_due(shelf)
        template = _template(dana, name="Bench test")
        before = w6.create_work_order(
            dana, None, {"type": "Bench test", "asset_id": shelf["id"], "template_id": template["id"]}
        )
        rule = rules.create_rule(
            dana, {"name": "Bench", "template_id": template["id"],
                   "triggers": [{"kind": "asset_age_rule", "params": {}}]}
        )
        report = rules.sweep(dana, rule_ids=[rule["id"]])["rules"][0]
        assert report["raised"] == 0
        assert work_tables.WorkOrder.objects.filter(pk=before["id"]).exists()
