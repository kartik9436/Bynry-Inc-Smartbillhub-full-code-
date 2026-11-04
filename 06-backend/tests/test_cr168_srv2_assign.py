# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — assign: P4.4 (reassign is one act
#           with a reason), P4.5 (advice, never a block), P4.6 (the override is
#           audited 🔒), P4.12 (candidates paged, uncapped), P4.14 (send back),
#           P2.17 (the area chip walks the premises)
# Rules:    ruling 2 (2026-09-23) SUPERSEDES BR-WRK-029 · PO answer 2
#           (2026-10-04) SUPERSEDES BR-WRK-030 · BR-WRK-025 (append-only, five
#           acts) · judgment J2 · J9 · NFR-3 · NFR-5 · hard rule 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The assign half of `CR-168-BRC10` round 3. SQLite is enough for every case
here: none depends on a trigger, RLS or an aborted transaction (the bulk raise's
savepoint is proved on PostgreSQL in `test_cr168_srv2_bulk_raise_pg.py`)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import advice, api as work_api, dispatch
from apps.work import edit as work_edit
from apps.work import models as work_models
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _reference():
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")
    work_services.seed_reference_list("work_skills", [], "test")


def _technician(tenant, email, name, *, skills=(), status="on_shift"):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    tech = work_models.Technician.objects.create(tenant_id=tenant.id, user=user, status=status)
    for skill in skills:
        work_models.TechnicianSkill.objects.create(
            tenant_id=tenant.id, technician=tech, skill_id=skill.id, proficiency="trained"
        )
    return tech


def _skilled_order(dana, tenant, address="77 Cedar Ct"):
    skill = work_models.WorkSkill.objects.filter(tenant_id=tenant.id).order_by("code").first()
    service = tenancy_models.Service.objects.filter(code="water").first()
    template = work_tables.WorkOrderTemplate.objects.create(
        tenant_id=tenant.id, name=f"Meter exchange {address}", skill_id=skill.id,
        service=service, version=1,
    )
    premises = make_premises(dana, address_line=address, services_available=["water"])
    raised = w6.create_work_order(
        dana, None,
        {"type": "Leak investigation", "premises_id": premises["id"],
         "template_id": str(template.id)},
    )
    return raised, skill, premises


# ══════════════════════════════════════════════════════════════════════════
# P4.5 · P4.12 — every holder, advice beside each, paged and uncapped
# ══════════════════════════════════════════════════════════════════════════


def test_candidates_are_everybody_with_advice_and_the_skilled_one_is_best_fit(dana, brazos):
    """Ruling 2: the dispatcher sees EVERYBODY. R. Patel holds the skill and is
    the best fit; N. Obody does not and is still offered, with the advice."""
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        nobody = _technician(brazos, "nobody@b.test", "N. Obody")
        work_models.Crew.objects.create(tenant_id=brazos.id, name="Field crew B")
        work_models.Crew.objects.create(tenant_id=brazos.id, name="Redline Meter", kind="contractor")

        page = dispatch.assign_candidates(raised["id"])
        by_name = {row["name"]: row for row in page["rows"]}
        assert set(by_name) == {"R. Patel", "N. Obody", "Field crew B", "Redline Meter"}
        assert page["total"] == 4
        assert by_name["R. Patel"]["advice"]["has_skill"] is True
        assert by_name["R. Patel"]["best_fit"] is True
        assert by_name["N. Obody"]["advice"]["has_skill"] is False
        assert by_name["N. Obody"]["best_fit"] is False
        assert by_name["N. Obody"]["advice"]["skill"] == {"name": skill.name}
        # Technicians, then crews, then contractors (image 16's groups).
        assert [row["kind"] for row in page["rows"]] == ["person", "person", "crew", "contractor"]
        assert page["rows"][0]["name"] == "R. Patel"
        assert str(nobody.id) in {row["id"] for row in page["rows"]}
        assert str(patel.id) == page["rows"][0]["id"]


def test_candidates_page_in_sql_and_count_the_whole_workforce(dana, brazos):
    """NFR-5 (`DEF-WRK-9531`): 60 holders, per=50 — page 1 carries 50, page 2
    the other 10, and `count` is 60 on both. Nothing is dropped."""
    with tenant_ctx(brazos):
        _reference()
        raised, _skill, _ = _skilled_order(dana, brazos)
        for n in range(60):
            work_models.Crew.objects.create(tenant_id=brazos.id, name=f"Crew {n:02d}")
        first = dispatch.assign_candidates(raised["id"], per=50)
        second = dispatch.assign_candidates(raised["id"], page=2, per=50)
        assert first["total"] == second["total"] == 60
        assert len(first["rows"]) == 50 and len(second["rows"]) == 10
        names = {r["name"] for r in first["rows"]} | {r["name"] for r in second["rows"]}
        assert len(names) == 60


def test_advice_names_a_lapsed_certification_off_day_and_jobs_that_day(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        kind = tenancy_models.CertificationType.objects.create(
            tenant_id=brazos.id, code="BACKFLOW", name="Backflow tester"
        )
        kaur = _technician(brazos, "kaur@b.test", "J. Kaur", skills=[skill])
        work_models.TechnicianCertification.objects.create(
            tenant_id=brazos.id, technician=kaur, certification_type_id=kind.id,
            expires_on=date.today() - timedelta(days=3),
        )
        _technician(brazos, "off@b.test", "M. Chen", skills=[skill], status="unavailable")
        page = dispatch.assign_candidates(raised["id"])
        by_name = {row["name"]: row for row in page["rows"]}
        lapsed = by_name["J. Kaur"]["advice"]["certifications_lapsed"]
        assert lapsed == [
            {"name": "Backflow tester", "expired_on": (date.today() - timedelta(days=3)).isoformat()}
        ]
        # never a block — and no `eligible` key at all since lane SRV-3 retired
        # the one-round twin (2026-10-04)
        assert "eligible" not in by_name["J. Kaur"]
        assert by_name["M. Chen"]["advice"]["off_that_day"] is True
        # Neither is the best fit — one is lapsed, the other off.
        assert not any(row["best_fit"] for row in page["rows"])


def test_candidates_api_is_the_house_envelope_with_advice(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
    response = api_call(
        work_api.work_order_candidates, "get",
        f"/api/{brazos.subdomain}/work-orders/{raised['id']}/candidates",
        user=dana.user, role="system_admin", tenant=brazos, query={"q": "patel"},
        order_id=raised["id"],
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert {"results", "count", "next", "previous"} <= set(body)
    assert body["count"] == 1
    row = body["results"][0]
    assert set(row["advice"]) == {
        "skill", "has_skill", "area_match", "off_that_day", "jobs_that_day",
        "certifications_lapsed",
        # CR-168-BRC10 §30 (2026-10-05) — the technician's daily job limit.
        "daily_job_limit", "over_daily_limit",
        # FB-033 (2026-10-31) — the phone's Off duty / On break, or null.
        "availability",
    }
    assert row["best_fit"] is True


def test_raise_candidates_need_no_order(dana, brazos):
    """P2.5 — step 2 of the raise asks before the job exists."""
    with tenant_ctx(brazos):
        _reference()
        skill = work_models.WorkSkill.objects.filter(tenant_id=brazos.id).first()
        service = tenancy_models.Service.objects.filter(code="water").first()
        template = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, name="Swap", skill_id=skill.id, service=service, version=1
        )
        _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        _technician(brazos, "nobody@b.test", "N. Obody")
    response = api_call(
        work_api.raise_candidates, "get", f"/api/{brazos.subdomain}/work/candidates",
        user=dana.user, role="system_admin", tenant=brazos,
        query={"template_id": str(template.id), "on": "2026-10-06"},
    )
    assert response.status_code == 200, response.data
    assert response.data["count"] == 2
    assert response.data["on"] == "2026-10-06"
    assert [r["best_fit"] for r in response.data["results"]] == [True, False]


# ══════════════════════════════════════════════════════════════════════════
# P4.5 · P4.6 🔒 — an assignment against the advice stands, and is recorded
# ══════════════════════════════════════════════════════════════════════════


def test_an_override_is_recorded_once_and_marks_the_history_line(dana, brazos, stored_audit):
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        nobody = _technician(brazos, "nobody@b.test", "N. Obody")
        out = dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(nobody.id)})
        assert out["against_advice"] == {"missing_skill": skill.name, "lapsed": []}
        rows = audit_models.AuditLog.objects.filter(
            tenant_id=brazos.id, action=dispatch.AGAINST_ADVICE, entity_id=raised["id"]
        )
        assert rows.count() == 1
        assert rows.first().after["assignment_id"] == out["assignment_id"]
        history = dispatch.order_audit(raised["id"])["rows"]
        assert [row["against_advice"] for row in history if row["act"] == "assign"] == [True]


def test_an_assignment_WITH_the_advice_records_no_override(dana, brazos, stored_audit):
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        out = dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(patel.id)})
        assert out["against_advice"] is None
        assert not audit_models.AuditLog.objects.filter(action=dispatch.AGAINST_ADVICE).exists()


# ══════════════════════════════════════════════════════════════════════════
# P4.4 — a reassign is ONE request, TWO rows, ONE reason
# ══════════════════════════════════════════════════════════════════════════


def test_reassign_writes_two_rows_sharing_a_reason_and_reads_as_one_line(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz", skills=[skill])
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        out = dispatch.record_act(
            dana, raised["id"],
            {"act": "reassign", "technician_id": str(patel.id),
             "reason": "Workload — D. Ortiz has four jobs that day"},
        )
        assert out["act"] == "reassign"
        assert out["technician"]["name"] == "R. Patel"
        rows = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=raised["id"]).order_by("at", "id")
        )
        assert [r.act for r in rows] == ["assign", "unassign", "assign"]
        assert rows[1].act_group is not None and rows[1].act_group == rows[2].act_group
        assert rows[1].reason == rows[2].reason == "Workload — D. Ortiz has four jobs that day"
        history = dispatch.order_audit(raised["id"])["rows"]
        assert [h["act"] for h in history] == ["assign", "reassign"]
        assert history[1]["reason"] == "Workload — D. Ortiz has four jobs that day"


def test_moving_a_job_off_somebody_without_a_reason_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz", skills=[skill])
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        with pytest.raises(errors.ValidationError) as caught:
            dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(patel.id)})
        assert caught.value.message_key == "work.dispatch.reason_required"
        assert work_models.WorkOrderAssignment.objects.filter(work_order_id=raised["id"]).count() == 1


def test_the_edit_page_carries_the_reason_onto_both_rows(dana, brazos):
    """Lane ASSIGN saves image 13's reassign through `PATCH …/edit` with
    `reason`; a move off somebody without one is refused there too."""
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        ortiz = _technician(brazos, "ortiz@b.test", "D. Ortiz", skills=[skill])
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        with pytest.raises(errors.ValidationError) as caught:
            work_edit.save_order_edit(dana, raised["id"], {"technician_id": str(patel.id)})
        assert caught.value.message_key == "work.dispatch.reason_required"
        work_edit.save_order_edit(
            dana, raised["id"], {"technician_id": str(patel.id), "reason": "Closer to the site"}
        )
        rows = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=raised["id"]).order_by("at", "id")
        )
        assert [r.act for r in rows] == ["assign", "unassign", "assign"]
        assert {rows[1].reason, rows[2].reason} == {"Closer to the site"}
        assert rows[1].act_group == rows[2].act_group is not None


def test_the_edit_page_assigning_nobody_yet_needs_no_reason(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised, skill, _ = _skilled_order(dana, brazos)
        patel = _technician(brazos, "patel@b.test", "R. Patel", skills=[skill])
        out = work_edit.save_order_edit(dana, raised["id"], {"technician_id": str(patel.id)})
        assert "technician" in out["changed"]


# ══════════════════════════════════════════════════════════════════════════
# P4.14 — send back, refused once accepted (J9)
# ══════════════════════════════════════════════════════════════════════════


def _finished(dana, brazos):
    raised, skill, _ = _skilled_order(dana, brazos)
    order = work_tables.WorkOrder.objects.get(pk=raised["id"])
    order.state = work_tables.WO_COMPLETED
    order.dispatch_state = work_tables.DISPATCH_COMPLETE
    from django.utils import timezone

    order.completed_at = timezone.now()
    order.outcome = "passed"
    order.field_data = {"notes": "photo of the meter"}
    order.save()
    return order


def test_send_back_reopens_a_finished_job_and_keeps_what_the_field_sent(dana, brazos, stored_audit):
    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        _reference()
        order = _finished(dana, brazos)
        out = metering_seam.send_back_field_result(dana, order.id, "The photo is missing")
        order.refresh_from_db()
        assert (order.state, order.dispatch_state) == ("in_progress", "scheduled")
        assert order.completed_at is None and order.accepted_at is None
        assert order.field_data == {"notes": "photo of the meter"}
        assert out["reason"] == "The photo is missing"
        history = dispatch.order_audit(order.id)["rows"]
        assert history[-1]["act"] == "sent_back"
        assert history[-1]["reason"] == "The photo is missing"


def test_send_back_is_refused_once_accepted_and_needs_a_reason(dana, brazos):
    from django.utils import timezone

    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        _reference()
        order = _finished(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            metering_seam.send_back_field_result(dana, order.id, "  ")
        assert caught.value.message_key == "work.order.send_back_reason_required"
        order.accepted_at = timezone.now()
        order.save(update_fields=["accepted_at"])
        with pytest.raises(errors.BizError) as refused:
            metering_seam.send_back_field_result(dana, order.id, "Wrong meter")
        assert refused.value.message_key == "work.order.already_accepted"


def test_send_back_api(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        order = _finished(dana, brazos)
    response = api_call(
        work_api.work_order_send_back, "post",
        f"/api/{brazos.subdomain}/work-orders/{order.id}/send-back",
        user=dana.user, role="system_admin", tenant=brazos,
        data={"reason": "Reading cannot be true"}, order_id=order.id,
    )
    assert response.status_code == 200, response.data
    assert response.data["dispatch_state"] == "scheduled"


# ══════════════════════════════════════════════════════════════════════════
# P2.17 — the Area chip walks the premises
# ══════════════════════════════════════════════════════════════════════════


def test_the_area_chip_finds_a_job_by_its_buildings_area(dana, brazos):
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        _reference()
        area = tenancy_models.Area.objects.create(tenant_id=brazos.id, code="NW", name="North West")
        raised, _skill, premises = _skilled_order(dana, brazos)
        metering_models.Premises.objects.filter(pk=premises["id"]).update(area_id=area.id)
        page = dispatch.dispatch_page(filters={"area": str(area.id)})
        assert [row["order_no"] for row in page["rows"]] == [raised["order_no"]]


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-030 — the block switch is retired (PO answer 2)
# ══════════════════════════════════════════════════════════════════════════


def test_the_block_switch_is_retired(dana, brazos):
    from apps.work import workforce

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            workforce.set_lapse_policy(dana, "block")
        assert caught.value.message_key == "work.settings.lapse_policy_retired"
        work_models.WorkSettings.objects.update_or_create(
            tenant_id=brazos.id, defaults={"certification_lapse_policy": "block"}
        )
        assert workforce.lapse_policy() == "warn"


@pytest.fixture()
def stored_audit():
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def test_advice_module_has_no_maximum_constant():
    """NFR-5 — no cap rides on the candidates: the module names no MAX."""
    import inspect

    source = inspect.getsource(advice)
    assert "MAX_PAGE_SIZE" not in source
    assert json.dumps(advice.ORDERING)
