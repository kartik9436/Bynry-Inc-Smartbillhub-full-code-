# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10609 — no screen managed the can't-read reasons, and a
#           job reading's *Unable to read* carried no reason.
# Ruling:   decision log 2026-10-26 — PO *"yes do it"*: ONE list for route AND
#           job readings, managed in Settings → Reference data → Readings; the
#           utility adds, renames, reorders; a seeded reason is switched off,
#           never deleted; an own reason is deleted only if never used.
# Rules:    BR-FLD-00082 · BR-TEN-036 · NFR-3 · BR-SHL-025 · CLAUDE.md hard
#           rules 1 (tenant isolation) and 7 (audited)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The Settings door onto the can't-read reasons, and the job reading that
now names one.

RED FIRST: before this lane every case here failed on
`ImportError: cannot import name 'cant_read_reasons'` (the Settings half) or on
`KeyError: 'unable_reason_name'` / `'cant_read_reasons'` (the job half)."""

from __future__ import annotations

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.identity import models as identity_models
from apps.metering import cant_read_reasons, cant_read_reasons_api, field_reads
from apps.metering.field_read_models import CantReadReason, FieldRead
from apps.work import checklist, evidence, mobile
from apps.work import models as work_models
from core import errors

from tests.test_cr187_order_helpers import job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin · audit_rows
from tests.test_us_met_helpers import staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db


def _codes():
    return [r["code"] for r in field_reads.cant_read_reasons(include_inactive=True)["results"]]


# ══════════════════════════════════════════════════════════════════════════
# The list
# ══════════════════════════════════════════════════════════════════════════
def test_the_list_is_paged_by_the_server_and_includes_switched_off_reasons(brazos, dana):
    with tenant_ctx(brazos):
        field_reads.set_cant_read_reason_active(dana, "dog", {"active": False})
        rows = cant_read_reasons.reasons_queryset()
        assert rows.count() == 8
        page = cant_read_reasons.page_rows(list(rows[:3]))
    assert [r["code"] for r in page] == ["dog", "locked", "no_access"]
    assert page[0]["active"] is False and page[0]["is_system"] is True
    assert {r["used"] for r in page} == {0}


def test_used_counts_route_readings_and_job_readings(brazos, dana):
    with tenant_ctx(brazos):
        FieldRead.objects.create(tenant_id=brazos.id, key="k-1", reader_status="could_not_read",
                                 cant_read_reason="Dog")
        FieldRead.objects.create(tenant_id=brazos.id, key="k-2", reader_status="could_not_read",
                                 cant_read_reason="dog")
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        evidence.set_reading(tech, oid, row.id, {"unable_to_read": True, "unable_reason": "locked"})
        counts = cant_read_reasons.usage_counts(["dog", "locked", "unsafe"])
    assert counts == {"dog": 2, "locked": 1, "unsafe": 0}


# ══════════════════════════════════════════════════════════════════════════
# Add · rename · move · switch
# ══════════════════════════════════════════════════════════════════════════
def test_a_reason_is_added_by_name_with_a_minted_code_at_the_bottom(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        added = cant_read_reasons.add_reason(dana, {"name": "Flooded pit"})
        again = cant_read_reasons.add_reason(dana, {"name": "Flooded  pit!"})
        nonlatin = cant_read_reasons.add_reason(dana, {"name": "犬がいる"})
        codes = _codes()
    assert added["code"] == "flooded_pit" and again["code"] == "flooded_pit_2"
    assert nonlatin["code"] == "reason"
    assert codes[-3:] == ["flooded_pit", "flooded_pit_2", "reason"]
    assert added["is_system"] is False and added["active"] is True and added["used"] == 0
    assert [r["action"] for r in audit_rows if r.get("entity_type") == "cant_read_reason"] == [
        "cant_read_reason.created"
    ] * 3


def test_a_name_already_listed_is_refused_without_regard_to_case(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            cant_read_reasons.add_reason(dana, {"name": "DOG"})
    assert caught.value.message_key == "metering.lookups.duplicate_code"


def test_rename_changes_the_name_and_never_the_code(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        renamed = cant_read_reasons.update_reason(dana, "dog", {"name": "Dog in yard"})
        with pytest.raises(errors.ValidationError):
            cant_read_reasons.update_reason(dana, "dog", {"code": "hound"})
        with pytest.raises(errors.ValidationError):
            cant_read_reasons.update_reason(dana, "dog", {"name": "  "})
    assert renamed["code"] == "dog" and renamed["name"] == "Dog in yard"
    row = next(r for r in audit_rows if r.get("action") == "cant_read_reason.updated")
    assert row["before"]["name"] == "Dog" and row["after"]["name"] == "Dog in yard"


def test_switch_off_and_on(brazos, dana):
    with tenant_ctx(brazos):
        off = cant_read_reasons.update_reason(dana, "unsafe", {"active": False})
        offered = [r["code"] for r in field_reads.cant_read_reasons()["results"]]
        on = cant_read_reasons.update_reason(dana, "unsafe", {"active": True})
    assert off["active"] is False and "unsafe" not in offered
    assert on["active"] is True


def test_move_swaps_one_place_and_is_a_no_op_at_either_end(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        cant_read_reasons.move_reason(dana, "locked", {"direction": "up"})
        assert _codes()[:3] == ["locked", "dog", "no_access"]
        cant_read_reasons.move_reason(dana, "locked", {"direction": "up"})
        assert _codes()[:2] == ["locked", "dog"]
        cant_read_reasons.move_reason(dana, "illegible", {"direction": "down"})
        assert _codes()[-1] == "illegible"
        cant_read_reasons.move_reason(dana, "dog", {"direction": "down"})
        assert _codes()[:3] == ["locked", "no_access", "dog"]
        with pytest.raises(errors.ValidationError):
            cant_read_reasons.move_reason(dana, "dog", {"direction": "sideways"})
    moved = [r for r in audit_rows if r.get("action") == "cant_read_reason.moved"]
    assert len(moved) == 2  # the two no-ops wrote nothing


# ══════════════════════════════════════════════════════════════════════════
# Delete — own and never used, or refused with the way out
# ══════════════════════════════════════════════════════════════════════════
def test_an_own_unused_reason_is_deleted_and_audited(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        cant_read_reasons.add_reason(dana, {"name": "Flooded"})
        out = cant_read_reasons.delete_reason(dana, "flooded")
        assert not CantReadReason.objects.filter(code="flooded").exists()
    assert out == {"code": "flooded", "deleted": True}
    assert any(r.get("action") == "cant_read_reason.deleted" for r in audit_rows)


def test_a_seeded_reason_is_never_deleted(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            cant_read_reasons.delete_reason(dana, "dog")
    assert caught.value.message_key == "metering.cantReadReasons.seeded"


def test_an_own_reason_a_route_reading_named_is_refused_switch_it_off(brazos, dana):
    with tenant_ctx(brazos):
        cant_read_reasons.add_reason(dana, {"name": "Flooded"})
        FieldRead.objects.create(tenant_id=brazos.id, key="k-9", reader_status="could_not_read",
                                 cant_read_reason="flooded")
        with pytest.raises(errors.BizError) as caught:
            cant_read_reasons.delete_reason(dana, "flooded")
        assert CantReadReason.objects.filter(code="flooded").exists()
    assert caught.value.message_key == "metering.cantReadReasons.in_use"


def test_an_own_reason_a_job_reading_named_is_refused_too(brazos, dana):
    with tenant_ctx(brazos):
        cant_read_reasons.add_reason(dana, {"name": "Flooded"})
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        evidence.set_reading(tech, oid, row.id, {"unable_to_read": True, "unable_reason": "flooded"})
        with pytest.raises(errors.BizError) as caught:
            cant_read_reasons.delete_reason(dana, "flooded")
    assert caught.value.message_key == "metering.cantReadReasons.in_use"


# ══════════════════════════════════════════════════════════════════════════
# Who may write, and whose list it is
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("role", ["executive", "billing_clerk"])
def test_only_a_system_admin_writes(brazos, role):
    with tenant_ctx(brazos):
        actor = staff_actor(brazos, role, f"{role}@brazosbendutilities.test")
        for call in (
            lambda: cant_read_reasons.add_reason(actor, {"name": "Flooded"}),
            lambda: cant_read_reasons.update_reason(actor, "dog", {"name": "Hound"}),
            lambda: cant_read_reasons.move_reason(actor, "dog", {"direction": "down"}),
            lambda: cant_read_reasons.delete_reason(actor, "dog"),
        ):
            with pytest.raises(errors.AuthError):
                call()


def test_another_tenants_reasons_are_invisible_and_unreachable(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        cant_read_reasons.add_reason(dana, {"name": "Flooded"})
        FieldRead.objects.create(tenant_id=brazos.id, key="k-x", reader_status="could_not_read",
                                 cant_read_reason="dog")
    with tenant_ctx(lonestar):
        assert "flooded" not in [r.code for r in cant_read_reasons.reasons_queryset()]
        assert cant_read_reasons.usage_counts(["dog"]) == {"dog": 0}
        for call in (
            lambda: cant_read_reasons.update_reason(erin, "flooded", {"name": "Mine"}),
            lambda: cant_read_reasons.delete_reason(erin, "flooded"),
        ):
            with pytest.raises(errors.NotFoundError):  # HR-1: a 404, never a 403
                call()
    with tenant_ctx(brazos):
        assert CantReadReason.objects.filter(tenant_id=brazos.id, code="flooded").exists()


def test_the_routes_are_mounted_paged_and_refuse_a_used_delete(brazos, dana):
    factory = APIRequestFactory()
    user = identity_models.User.objects.get(pk=dana.id)

    def call(view, method, data=None, **kwargs):
        request = getattr(factory, method)("/api/brazosbend/settings/cant-read-reasons", data,
                                           format="json")
        force_authenticate(request, user=user)
        request.tenant_role = "system_admin"
        request.tenant_id = brazos.id
        return view(request, **kwargs)

    with tenant_ctx(brazos):
        listed = call(cant_read_reasons_api.reasons, "get", {"page": 1})
        added = call(cant_read_reasons_api.reasons, "post", {"name": "Flooded"})
        moved = call(cant_read_reasons_api.reason_move, "post", {"direction": "up"}, code="flooded")
        renamed = call(cant_read_reasons_api.reason_detail, "patch", {"name": "Flooded pit"},
                       code="flooded")
        refused = call(cant_read_reasons_api.reason_detail, "delete", code="dog")
        deleted = call(cant_read_reasons_api.reason_detail, "delete", code="flooded")
    assert listed.status_code == 200 and listed.data["count"] == 8
    assert listed.data["results"][0] == {"code": "dog", "name": "Dog", "sort_order": 10,
                                         "is_system": True, "active": True, "used": 0}
    assert added.status_code == 201 and added.data["code"] == "flooded"
    assert moved.status_code == 200 and renamed.data["name"] == "Flooded pit"
    assert refused.status_code == 409, refused.data
    assert deleted.status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# The job reading names a reason from the SAME list
# ══════════════════════════════════════════════════════════════════════════
def test_a_job_reading_stores_the_code_and_the_office_sees_the_name_and_note(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        cant_read_reasons.update_reason(dana, "dog", {"name": "Dog in yard"})
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        answer = evidence.set_reading(
            tech, oid, row.id,
            {"unable_to_read": True, "unable_reason": "dog", "note": " Barking at gate "},
        )
        page = checklist.checklist(oid)
        ready = evidence.close_readiness(oid)
        row.refresh_from_db()
    assert row.unable_reason == "dog" and row.unable_note == "Barking at gate"
    assert answer["unable_reason_name"] == "Dog in yard" and answer["unable_reason_known"] is True
    served = next(r for r in page["readings"] if r["id"] == str(row.id))
    assert served["unable_reason_name"] == "Dog in yard"
    assert served["unable_note"] == "Barking at gate"
    flagged = next(f for f in ready["flagged"] if f["kind"] == "unable_to_read")
    assert flagged["reason"] == "Dog in yard"
    captured = next(r for r in audit_rows if r.get("action") == "work.reading.captured")
    assert captured["after"]["unable_reason_known"] is True


@pytest.mark.parametrize("sent", ["flooded", "Meter buried"])
def test_an_unknown_reason_is_stored_and_flagged_never_refused(brazos, dana, audit_rows, sent):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        answer = evidence.set_reading(tech, oid, row.id, {"unable_to_read": True, "unable_reason": sent})
        row.refresh_from_db()
    assert row.unable_to_read is True and row.unable_reason == sent
    assert answer["unable_reason_known"] is False
    assert answer["unable_reason_name"] == sent
    captured = next(r for r in audit_rows if r.get("action") == "work.reading.captured")
    assert captured["after"]["unable_reason_known"] is False


def test_a_reason_switched_off_since_is_flagged_and_keeps_its_name(brazos, dana):
    with tenant_ctx(brazos):
        cant_read_reasons.update_reason(dana, "unsafe", {"active": False})
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        answer = evidence.set_reading(tech, oid, row.id, {"unable_to_read": True, "unable_reason": "unsafe"})
    assert answer["unable_reason_known"] is False and answer["unable_reason_name"] == "Unsafe"


def test_a_figure_after_unable_clears_the_note_too(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq").first()
        evidence.set_reading(tech, oid, row.id, {"unable_to_read": True, "unable_reason": "dog", "note": "x"})
        evidence.set_reading(tech, oid, row.id, {"value": "1204", "unit": row.unit_of_measure})
        row.refresh_from_db()
    assert row.unable_reason is None and row.unable_note is None


def test_the_job_bundle_carries_the_active_list_in_order(brazos, dana):
    with tenant_ctx(brazos):
        cant_read_reasons.update_reason(dana, "unsafe", {"active": False})
        cant_read_reasons.add_reason(dana, {"name": "Flooded"})
        oid, tech = job(dana, brazos)
        pack = mobile.bundle(tech, oid)
    codes = [r["code"] for r in pack["cant_read_reasons"]]
    assert codes[:2] == ["dog", "locked"] and codes[-1] == "flooded"
    assert "unsafe" not in codes
    assert pack["cant_read_reasons"][0] == {"code": "dog", "name": "Dog"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-10609
# generated: 2026-10-26 by the DEF-MET-10609 lane
