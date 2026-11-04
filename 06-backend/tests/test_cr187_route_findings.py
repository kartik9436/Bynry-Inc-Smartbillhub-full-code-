# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane FINDINGS — a route finding through the reads door,
#           a Work rule that raises its job, and the job raised by hand.
# Rules:    BR-WRK-067 (PO 2026-10-22, *"if a rule is set work order will get
#           created , if not user can create the work order"*) · BR-MET-1202
#           (the capture position is evidence) · BR-WRK-024 (the rule stamp
#           and the process label) · hard rules 1, 6
# Tests:    this file (SQLite) · tests/test_cr187_route_findings_pg.py
# ───────────────────────────────────────────────────────
"""The worked case the PO was shown, run.

Brazos has a rule *Leak → Leak repair, Same day*: Dana's leak at a stop raises
the job at once and her receipt names it. Brazos has no rule for *Broken seal*:
that finding waits OPEN, and a person — Dana on her phone, or the office —
creates the job by hand, once.

RED FIRST (hard-won law 7): at the branch tip before this lane every case here
fails — the reads door answered `refused` / `unknown_kind` for a `finding`
item and `apps.work.route_findings` did not exist.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import field_reads
from apps.work import connection_models as work_tables
from apps.work import route_findings, rule_processes, rules
from apps.work import models as work_models
from apps.work.route_finding_models import WorkRouteFinding
from core import errors

from tests.test_cr187_order_helpers import person, template
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import build_route, captured, reader_actor, tenant_ctx

pytestmark = pytest.mark.django_db

LEAK_REPAIR = "Leak repair"
SEAL_CHECK = "Seal check"


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        technician, _ = work_models.Technician.objects.get_or_create(
            tenant_id=brazos.id, user_id=reader.id, defaults={"role_label": "Meter reader"}
        )
        route = build_route(brazos, dana, reader, history=False)
        same_day = work_models.WorkPriority.objects.filter(tenant_id=brazos.id).order_by("rank").first()
        leak_tid = template(dana, brazos, LEAK_REPAIR)
    return {
        "tenant": brazos,
        "admin": dana,
        "reader": reader,
        "technician": technician,
        "route": route,
        "priority": same_day,
        "leak_template": leak_tid,
    }


def _leak_rule(world, *, kind="leak", enabled=True, name="Leak → Leak repair"):
    return rules.create_rule(
        world["admin"],
        {
            "name": name,
            "triggers": [{"kind": "route_finding", "params": {"finding_kind": kind}}],
            "template_id": str(world["leak_template"]),
            "priority_id": str(world["priority"].id),
            "enabled": enabled,
        },
    )


def a_finding(key, world, *, kind="leak", meter_no="MTR-0471", **extra):
    w = world["route"]
    item = {
        "key": key,
        "kind": "finding",
        "finding": kind,
        "urgency": "now",
        "route_id": w.route_id,
        "premises_id": w.premises[0],
        "meter_no": meter_no,
        "remark": "Water pooling at the kerb box",
        "remark_source": "voice",
        "position": {"lat": "30.267200", "lng": "-97.743100", "accuracy_m": "6"},
        "captured_at": captured(),
    }
    item.update(extra)
    return item


def _sync(world, *items):
    return field_reads.sync_reads(world["reader"], {"items": list(items)})


def _orders(world):
    return work_tables.WorkOrder.objects.filter(
        tenant_id=world["tenant"].id, source=work_tables.SOURCE_ROUTE_FINDING
    )


# ══════════════════════════════════════════════════════════════════════════
# By rule
# ══════════════════════════════════════════════════════════════════════════
def test_a_rule_for_the_kind_creates_exactly_one_job_at_once(world):
    with tenant_ctx(world["tenant"]):
        rule = _leak_rule(world)
        out = _sync(world, a_finding("dana-f-1", world))
        receipt = out["items"][0]
        assert receipt["result"] == "accepted", receipt
        assert receipt["outcome"] == "work_order_created"
        finding = receipt["finding"]
        assert finding["conversion"] == "by_rule" and finding["rule"] == rule["name"]
        assert finding["work_order"]["order_no"].startswith("WO-")

        assert _orders(world).count() == 1
        order = _orders(world).get()
        assert order.order_no == finding["work_order"]["order_no"]
        # BR-WRK-024 — the rule stamp and the process's label, the meter quoted.
        assert str(order.rule_id) == rule["id"]
        assert order.source == "route_finding" and order.source_ref == "MTR-0471"
        assert order.priority_id == world["priority"].id
        assert str(order.asset_id) == world["route"].meters["MTR-0471"]["id"]
        assert order.technician_notes == "Water pooling at the kerb box"
        # The rule's memory (its THIS MONTH count) — keyed on the finding.
        memory = work_models.WorkOrderRuleRaise.objects.get(rule_id=rule["id"])
        assert memory.subject_kind == "route_finding" and memory.work_order_id == order.id


def test_a_resend_of_the_same_finding_creates_no_second_job(world):
    """Hard rule 6 — the key minted at capture is the identity."""
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        first = _sync(world, a_finding("dana-f-2", world))["items"][0]
        again = _sync(world, a_finding("dana-f-2", world))["items"][0]
        twice_in_one = _sync(world, a_finding("dana-f-3", world), a_finding("dana-f-3", world))
        assert again["result"] == "duplicate"
        assert again["finding"]["work_order"] == first["finding"]["work_order"]
        assert [i["result"] for i in twice_in_one["items"]] == ["accepted", "duplicate"]
        assert WorkRouteFinding.objects.filter(key="dana-f-2").count() == 1
        # dana-f-2 → one job; dana-f-3 → the SAME open leak repair on that
        # meter is joined, not doubled (P3.38).
        assert _orders(world).count() == 1
        f3 = WorkRouteFinding.objects.get(key="dana-f-3")
        assert f3.status == "work_order_created" and str(f3.work_order_id) == first["finding"]["work_order"]["id"]


def test_no_rule_leaves_the_finding_open_with_its_evidence(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)  # a rule for LEAK; this is a broken seal
        receipt = _sync(world, a_finding("dana-f-4", world, kind="broken_seal", photos=["p-1", "p-2"]))[
            "items"
        ][0]
        assert receipt["result"] == "accepted" and receipt["outcome"] == "open"
        assert receipt["finding"]["work_order"] is None
        assert _orders(world).count() == 0
        row = WorkRouteFinding.objects.get(key="dana-f-4")
        assert row.status == "open" and row.photo_ids == ["p-1", "p-2"]
        # BR-MET-1202 — where the PHONE was, kept as evidence beside the stop.
        assert row.lat == Decimal("30.267200") and row.lng == Decimal("-97.743100")
        assert str(row.premises_id) == world["route"].premises[0]
        assert row.captor_id == world["reader"].id
        assert row.captor_technician_id == world["technician"].id
        assert receipt["finding"]["capture_point"] == {
            "lat": "30.267200", "lng": "-97.743100", "accuracy_m": "6.00",
        }


def test_a_rule_that_is_off_raises_nothing(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world, enabled=False)
        receipt = _sync(world, a_finding("dana-f-5", world))["items"][0]
        assert receipt["outcome"] == "open" and _orders(world).count() == 0


def test_a_rule_whose_template_is_unpublished_leaves_the_finding_open(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        work_tables.WorkOrderTemplate.objects.filter(pk=world["leak_template"]).update(active=False)
        receipt = _sync(world, a_finding("dana-f-6", world))["items"][0]
        assert receipt["result"] == "accepted" and receipt["outcome"] == "open"
        assert _orders(world).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# By hand
# ══════════════════════════════════════════════════════════════════════════
def test_the_office_creates_the_job_once(world):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("dana-f-7", world, kind="broken_seal"))
        row = WorkRouteFinding.objects.get(key="dana-f-7")
        seal = template(world["admin"], world["tenant"], SEAL_CHECK)
        body = {"template_id": str(seal), "priority_id": str(world["priority"].id)}
        made = route_findings.office_create(world["admin"], row.id, body)
        assert made["duplicate"] is False and made["status"] == "work_order_created"
        assert made["conversion"] == "by_hand"
        again = route_findings.office_create(world["admin"], row.id, body)
        assert again["duplicate"] is True
        assert again["work_order"] == made["work_order"]
        assert _orders(world).count() == 1
        order = _orders(world).get()
        assert order.rule_id is None and order.priority_id == world["priority"].id
        assert order.due_at is not None  # BR-WRK-018 — the priority's promise, stamped


def test_the_reader_creates_the_job_from_the_phone_and_nobody_else_can(world, brazos):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("dana-f-8", world, kind="suspected_tamper"))
        seal = template(world["admin"], world["tenant"], SEAL_CHECK)
        _other, other_actor = person(brazos, "marco@b.test", "Marco Diaz")
        with pytest.raises(errors.NotFoundError):
            route_findings.mobile_create(other_actor, "dana-f-8", {"template_id": str(seal)})
        with pytest.raises(errors.NotFoundError):
            route_findings.mobile_finding(other_actor, "dana-f-8")
        made = route_findings.mobile_create(world["reader"], "dana-f-8", {"template_id": str(seal)})
        assert made["status"] == "work_order_created" and made["converted_by"] is not None
        assert route_findings.mobile_finding(world["reader"], "dana-f-8")["work_order"] == made["work_order"]
        assert _orders(world).count() == 1


def test_a_finding_a_rule_took_is_not_converted_again_by_hand(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        _sync(world, a_finding("dana-f-9", world))
        row = WorkRouteFinding.objects.get(key="dana-f-9")
        again = route_findings.office_create(
            world["admin"], row.id, {"template_id": str(world["leak_template"])}
        )
        assert again["duplicate"] is True and again["conversion"] == "by_rule"
        assert _orders(world).count() == 1


def test_by_hand_needs_a_published_template(world):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("dana-f-10", world, kind="unsafe_access"))
        row = WorkRouteFinding.objects.get(key="dana-f-10")
        with pytest.raises(errors.ValidationError):
            route_findings.office_create(world["admin"], row.id, {})
        work_tables.WorkOrderTemplate.objects.filter(pk=world["leak_template"]).update(active=False)
        with pytest.raises(errors.BizError):
            route_findings.office_create(
                world["admin"], row.id, {"template_id": str(world["leak_template"])}
            )
        assert WorkRouteFinding.objects.get(pk=row.id).status == "open"


# ══════════════════════════════════════════════════════════════════════════
# Refused back to the reader, and the office's list
# ══════════════════════════════════════════════════════════════════════════
def test_an_unknown_kind_or_no_place_goes_back_to_the_reader(world):
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world,
            a_finding("dana-f-11", world, kind="ufo"),
            a_finding("dana-f-12", world, premises_id=None, meter_no=None),
            a_finding("dana-f-13", world, urgency="yesterday"),
        )
        assert [i["reason"] for i in out["items"]] == [
            "finding_kind_unknown",
            "finding_place_unknown",
            "finding_urgency_unknown",
        ]
        assert all(i["result"] == "refused" for i in out["items"])
        assert out["items"][0]["message_key"] == "work.mobile.reads.finding_kind_unknown"
        assert not WorkRouteFinding.objects.exists()


def test_the_office_list_filters_by_status_and_names_no_raw_id(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        _sync(world, a_finding("dana-f-14", world), a_finding("dana-f-15", world, kind="broken_seal"))
        page = route_findings.office_page()
        assert page["counts"] == {"open": 1, "work_order_created": 1}
        assert [r["kind"] for r in page["rows"]] == ["broken_seal"]
        row = page["rows"][0]
        # B14 rule 31 — the meter's number, the stop's address, a name.
        assert row["meter_no"] == "MTR-0471"
        assert row["stop"]["address"] == "1318 Maple St"
        assert row["route"] == "WLK-07"
        assert row["photographs"] == 0
        made = route_findings.office_page(status="work_order_created")["rows"]
        assert [r["kind"] for r in made] == ["leak"]
        assert len(route_findings.office_page(status="all")["rows"]) == 2
        with pytest.raises(errors.ValidationError):
            route_findings.office_page(status="closed")


def test_another_utility_cannot_see_or_convert_the_finding(world, lonestar, erin):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("dana-f-16", world, kind="broken_seal"))
        row = WorkRouteFinding.objects.get(key="dana-f-16")
    with tenant_ctx(lonestar):
        assert route_findings.office_page(status="all")["total"] == 0
        with pytest.raises(errors.NotFoundError):
            route_findings.office_create(erin, row.id, {"template_id": "x"})


# ══════════════════════════════════════════════════════════════════════════
# The rule form
# ══════════════════════════════════════════════════════════════════════════
def test_the_process_is_served_with_its_closed_list_and_refuses_another_value(world):
    with tenant_ctx(world["tenant"]):
        served = {row["key"]: row for row in rules.processes()["results"]}
        process = served["route_finding"]
        assert process["moment"] == "arrival" and process["module"] == "reads"
        param = process["params"][0]
        assert param["kind"] == "choice" and param["required"] is True
        assert [o["value"] for o in param["options"]][:3] == ["leak", "damaged_meter", "broken_seal"]
        assert param["options"][0]["label_key"] == "work.findings.kind.leak"
        with pytest.raises(errors.ValidationError):
            _leak_rule(world, kind="ufo", name="Bad")
        with pytest.raises(errors.ValidationError):
            rules.create_rule(
                world["admin"],
                {
                    "name": "No kind",
                    "triggers": [{"kind": "route_finding", "params": {}}],
                    "template_id": str(world["leak_template"]),
                },
            )


def test_the_route_finding_process_is_never_read_by_the_overnight_sweep():
    assert "route_finding" in rule_processes.ARRIVAL_KEYS
    assert "route_finding" not in rule_processes.OVERNIGHT_KEYS
    assert "route_finding" not in rules.PROCESS_READERS


def test_the_finding_options_name_their_words_by_key(world):
    with tenant_ctx(world["tenant"]):
        options = route_findings.finding_options()
        assert [k["code"] for k in options["kinds"]][-1] == "meter_mismatch"
        assert [u["code"] for u in options["urgencies"]] == ["now", "this_week", "routine"]
        assert options["priorities"] and all("name" in p for p in options["priorities"])


def test_the_routes_are_mounted():
    from django.urls import resolve

    assert resolve("/api/v1/work/route-findings").url_name == "work_route_findings"
    assert resolve("/api/v1/work/mobile/findings/options").url_name == "mobile_finding_options"
    assert resolve("/api/v1/work/mobile/findings/k-1/work-order").url_name == "mobile_finding_work_order"
