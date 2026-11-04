# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-42, lane S-ORDER — field-raised orders (FF-37,
#           FF-62, E2E-16) and the template catalogue a technician reads (N8).
# Rules:    BR-FLD-00112 (R112) · BR-FLD-00024 (R24) · BR-FLD-00023 (R23) ·
#           BR-WRK-006 · BR-WRK-008 · BR-WRK-061 · hard rules 1, 6's shape, 7
# Code:     apps/work/field_raise.py · apps/work/field_orders_api.py
# ───────────────────────────────────────────────────────
"""Raise on the kerb; the office accepts; the template version is stamped."""

from __future__ import annotations

import pytest

from apps.work import connection_models as work_tables
from apps.work import field_raise, templates_svc
from apps.work import models as work_models
from apps.work.field_order_models import WorkFieldRaise
from core import errors

from tests.test_cr187_order_helpers import FIX, close, job, order, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import THREE_HELP

pytestmark = pytest.mark.django_db


def _raise_body(tid, **extra):
    return {
        "key": "raise-1",
        "template_id": str(tid),
        "template_version": 2,
        "need": "Leak",
        "urgency": "same_day",
        "note": "Water at the kerb",
        "captured_at": "2026-03-15T16:05:00Z",
        "location": FIX,
        **extra,
    }


def test_e2e16_raised_on_the_kerb_auto_filled_and_pending(brazos, dana, audit_rows):
    """Carried from the technician's job: premise and account come from it,
    the number is the server's, the version is stamped, it lands PENDING in the
    office's REVIEW queue and — since FB-028 (PO 2026-10-31, R23 superseded) —
    ASSIGNED to the raiser, and a replay raises nothing."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        tid = template(dana, brazos, "Leak investigation")
        first = field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
        again = field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
        new = order(first["order_id"])
        original = order(oid)
        copies = work_models.WorkOrderTask.objects.filter(work_order_id=new.id).count()
        raises = WorkFieldRaise.objects.filter(tenant_id=brazos.id).count()

    assert first["order_no"] and first["order_no"].startswith("WO-") and first["duplicate"] is False
    assert again["duplicate"] is True and again["order_no"] == first["order_no"] and raises == 1
    assert first["status"] == "pending" and first["assigned"] is True
    assert new.dispatch_state == "scheduled" and new.assignee_technician_id is not None
    assert new.premises_id == original.premises_id and new.template_version == 2
    assert first["template"] == {
        "id": str(tid),
        "name": "Leak investigation",
        "version_stamped": 2,
        "version_picked": 2,
        "version_moved": False,
    }
    assert copies == 7, "the order took its own copy of the template"
    assert first["carried_from"]["order_no"] == original.order_no
    assert first["position"] == {"lat": "30.261200", "lng": "-97.743100", "accuracy_m": "4.0"}
    assert first["premise"] is not None
    assert any(r["action"] == "work.order.raised_in_field" for r in audit_rows)


def test_the_version_picked_and_the_version_stamped_are_both_told(brazos, dana):
    """R112 — the handset picked v2; the office published v3 since. The order
    is one honest copy of v3 and the answer says the version moved."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        templates_svc.replace_collection(dana, tid, "help", THREE_HELP[:1])
        templates_svc.publish(dana, tid)
        out = field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
    assert out["template"]["version_stamped"] == 3 and out["template"]["version_moved"] is True


def test_a_reconnect_raised_in_the_field_is_the_raisers_and_accept_means_seen(brazos, dana):
    """⚠ R23 SUPERSEDED 2026-10-31 (FB-028 W1): this test read *cannot be
    claimed until the office accepts*. A raised reconnect is now assigned to
    the raiser in the raise; the office's Accept records that it was seen and
    moves nothing."""
    from apps.work import field_dispatch

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Reconnect")
        out = field_raise.raise_from_field(
            tech, _raise_body(tid, need="Reconnect", carried_from=str(oid))
        )
        mine = field_dispatch.claim(tech, out["order_id"])
        accepted = field_raise.decide(dana, out["order_id"], {"decision": "accept"})
        queue = field_raise.field_raised_queue(status="accepted")

    assert out["is_reconnect"] is True and out["assigned"] is True
    assert mine["already_yours"] is True
    assert accepted["status"] == "accepted" and accepted["dispatch_state"] == "scheduled"
    assert [r["order_no"] for r in queue["rows"]] == [out["order_no"]]
    assert queue["counts"]["accepted"] == 1


def test_the_office_refuses_with_a_reason_and_the_order_is_cancelled_not_deleted(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        out = field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
        with pytest.raises(errors.ValidationError):
            field_raise.decide(dana, out["order_id"], {"decision": "refuse"})
        refused = field_raise.decide(
            dana, out["order_id"], {"decision": "refuse", "reason": "Duplicate"}
        )
        with pytest.raises(errors.BizError) as decided:
            field_raise.decide(dana, out["order_id"], {"decision": "accept"})
        with pytest.raises(errors.AuthError):
            field_raise.decide(tech, out["order_id"], {"decision": "accept"})
        row = order(out["order_id"])
    assert refused["status"] == "refused" and row.dispatch_state == "cancelled"
    assert row.order_no == out["order_no"], "nothing deleted"
    assert decided.value.message_key == "work.raise.already_decided"


@pytest.mark.parametrize(
    "change,key",
    [
        ({"key": ""}, "work.raise.capture_key_required"),
        ({"template_id": ""}, "work.raise.template_required"),
        ({"urgency": "whenever"}, "work.raise.urgency_unknown"),
        ({"location": {"lat": "1"}}, "work.mobile.location_malformed"),
    ],
)
def test_malformed_raises_are_refused_by_name(brazos, dana, change, key):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        with pytest.raises(errors.ValidationError) as refused:
            field_raise.raise_from_field(
                tech, {**_raise_body(tid, carried_from=str(oid)), **change}
            )
    assert refused.value.message_key == key


def test_an_inactive_template_and_a_colleagues_job_are_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        _s, stranger = person(brazos, "sam@field.test", "Sam Ng")
        with pytest.raises(errors.NotFoundError):
            field_raise.raise_from_field(stranger, _raise_body(tid, carried_from=str(oid)))
        work_tables.WorkOrderTemplate.objects.filter(pk=tid).update(active=False)
        with pytest.raises(errors.BizError) as inactive:
            field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
    assert inactive.value.message_key == "work.raise.template_inactive"


def test_raise_without_carried_from_takes_the_anchor_it_is_given(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        premises_id = order(oid).premises_id
        out = field_raise.raise_from_field(tech, _raise_body(tid, premises_id=str(premises_id)))
        with pytest.raises(errors.ValidationError) as no_anchor:
            field_raise.raise_from_field(tech, _raise_body(tid, key="raise-2"))
    assert order_premises(out["order_id"], brazos) == premises_id
    assert no_anchor.value.message_key == "work.order.anchor_required"


def order_premises(oid, tenant):
    with tenant_ctx(tenant):
        return order(oid).premises_id


def test_the_key_is_per_tenant_and_the_queue_is_tenant_scoped(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        field_raise.raise_from_field(tech, _raise_body(tid, carried_from=str(oid)))
    with tenant_ctx(lonestar):
        queue = field_raise.field_raised_queue(status="all")
        with pytest.raises(errors.NotFoundError):
            field_raise.template_body(tid)
    assert queue["total"] == 0


# ── the catalogue (FF-62, N8) ─────────────────────────────────────────────
def test_the_catalogue_offers_published_templates_recently_used_first(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        older = template(dana, brazos, "Broken seal")
        used = template(dana, brazos, "Zeta leak")
        draft = templates_svc.create_draft(dana, {"name": "Draft only", "service": "electric"})[
            "id"
        ]
        field_raise.raise_from_field(tech, _raise_body(used, carried_from=str(oid)))
        page = field_raise.templates_catalogue(tech)
        searched = field_raise.templates_catalogue(tech, q="seal")
        body = field_raise.template_body(used)
        with pytest.raises(errors.NotFoundError):
            field_raise.template_body(draft)

    names = [r["name"] for r in page["rows"]]
    assert names[0] == "Zeta leak" and page["rows"][0]["recent"] is True
    assert "Draft only" not in names and "Broken seal" in names
    assert [r["name"] for r in searched["rows"]] == ["Broken seal"]
    first = page["rows"][0]
    assert (first["steps"], first["safety_checks"], first["readings"]) == (7, 3, 3)
    assert len(body["tasks"]) == 7 and body["version"] == 2
    assert str(older) in {r["id"] for r in page["rows"]}
