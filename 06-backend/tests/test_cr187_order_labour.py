# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-38, lane S-ORDER — a second technician on an order
#           with their own labour record (E2E-20).
# Rules:    BR-FLD-00008 (R8) · BR-FLD-00009 (R9) · BR-FLD-00010 (R10) ·
#           BR-WRK-020 · BR-WRK-051 · hard rules 1, 7
# Code:     apps/work/field_labour.py · costing.py · services.py
# ───────────────────────────────────────────────────────
"""Labour per person; the cost is the sum; the lead closes it."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import costing, field_labour
from apps.work import models as work_models
from apps.work.field_order_models import WorkOrderLabour
from core import errors

from tests.test_cr187_order_helpers import close, job, order, person, tick_safety
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _rate(tenant, role, hourly):
    return work_models.LabourRate.objects.create(
        tenant_id=tenant.id, role=role, hourly=Decimal(hourly), effective_from=timezone.now().date()
    )


def _iso(dt):
    return dt.isoformat()


def test_e2e20_marco_joins_records_90_minutes_and_dana_closes(brazos, dana, audit_rows):
    """E2E-20 — two time records, the cost is their sum, the lead closes it.

    Worked (rates illustrative): Dana 120 min at 48.5000 = 97.00; Marco 90 min
    at 40.0000 = 60.00; labour 157.00 on two lines."""
    with tenant_ctx(brazos):
        _rate(brazos, "field_technician", "48.5000")
        _rate(brazos, "apprentice", "40.0000")
        oid, lead = job(dana, brazos)
        work_models.Technician.objects.filter(user_id=lead.id).update(role_label="Field technician")
        _marco, marco = person(brazos, "marco@field.test", "Marco Rossi", role_label="Apprentice")

        added = field_labour.add_technician(
            lead, oid, {"technician_id": str(_marco.id), "key": "add-1"}
        )
        again = field_labour.add_technician(
            lead, oid, {"technician_id": str(_marco.id), "key": "add-1"}
        )
        now = timezone.now()
        field_labour.record_time(
            marco,
            oid,
            {
                "arrive_at": _iso(now - timedelta(minutes=100)),
                "start_at": _iso(now - timedelta(minutes=95)),
                "end_at": _iso(now - timedelta(minutes=5)),
            },
        )
        # The lead's own minutes come from the close's labour_time (DEF-WRK-4127).
        tick_safety(lead, oid)
        close(
            lead,
            oid,
            "passed",
            field_data={
                "labour_time": {"minutes": 120},
            },
        )
        # A helper may NOT close (R8 — the lead closes it).
        with pytest.raises(errors.AuthError) as helper_close:
            w6.submit_field_result(marco, oid, outcome="passed")
        lines, total = costing.work_order_cost_lines(order(oid))
        summary = field_labour.labour_of(marco, oid)

    assert added["created"] is True and again["created"] is False and again["id"] == added["id"]
    assert helper_close.value.message_key == "work.order.closed_by_field_only"
    labour = [line for line in lines if line.kind == "labour"]
    assert [line.display_amount for line in labour] == [Decimal("97.00"), Decimal("60.00")]
    assert "Marco Rossi" in labour[1].description
    assert sum(line.display_amount for line in labour) == Decimal("157.00")
    assert total == sum((line.display_amount for line in lines), Decimal("0.00"))
    marco_row = next(p for p in summary["people"] if p["technician"]["name"] == "Marco Rossi")
    assert marco_row["labour_minutes"] == 90 and marco_row["labour_from"] == "start_at"
    assert marco_row["priced"] is True
    assert any(r["action"] == "work.labour.member_added" for r in audit_rows)


def test_no_helper_means_the_cost_is_unchanged(brazos, dana):
    """An order with no second technician prices exactly as before."""
    with tenant_ctx(brazos):
        _rate(brazos, "field_technician", "48.5000")
        oid, lead = job(dana, brazos)
        work_models.Technician.objects.filter(user_id=lead.id).update(role_label="Field technician")
        close(lead, oid, "passed", field_data={"labour_time": {"minutes": 52}})
        lines, total = costing.work_order_cost_lines(order(oid))
        expected = costing.compute(
            costing._labour_input(order(oid)), costing._used_parts(order(oid))
        )

    assert (lines, total) == expected


def test_travel_and_labour_are_separate_clocks_and_a_correction_is_recorded(
    brazos, dana, audit_rows
):
    """R9 — depart→arrive is travel, start→end is labour; changing a recorded
    moment is a correction that counts and writes its before-value (R10)."""
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        now = timezone.now()
        first = field_labour.record_time(
            lead,
            oid,
            {
                "depart_at": _iso(now - timedelta(minutes=80)),
                "arrive_at": _iso(now - timedelta(minutes=60)),
                "start_at": _iso(now - timedelta(minutes=55)),
                "end_at": _iso(now - timedelta(minutes=10)),
            },
        )
        same = field_labour.record_time(lead, oid, {"end_at": _iso(now - timedelta(minutes=10))})
        fixed = field_labour.record_time(lead, oid, {"end_at": _iso(now - timedelta(minutes=5))})

    assert first["travel_minutes"] == 20 and first["labour_minutes"] == 45
    assert first["corrected"] == [] and same["changed"] == []
    assert fixed["corrected"] == ["end_at"] and fixed["corrections"] == 1
    assert fixed["labour_minutes"] == 50
    corrected = [r for r in audit_rows if r["action"] == "work.labour.corrected"]
    assert len(corrected) == 1 and "end_at" in corrected[0]["before"]


@pytest.mark.parametrize(
    "body,key",
    [
        ({"start_at": "+10", "end_at": "+30"}, "work.labour.finished_before_starting"),
        ({"depart_at": "+30", "arrive_at": "+40"}, "work.labour.arrived_before_departing"),
        ({"end_at": "future"}, "work.labour.moment_in_future"),
        ({}, "work.labour.nothing_to_record"),
    ],
)
def test_backwards_future_and_empty_clocks_are_refused(brazos, dana, body, key):
    now = timezone.now()

    def moment(token):
        if token == "future":
            return _iso(now + timedelta(hours=2))
        return _iso(now - timedelta(minutes=int(token.lstrip("+"))))

    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        with pytest.raises(errors.ValidationError) as refused:
            field_labour.record_time(lead, oid, {k: moment(v) for k, v in body.items()})
    assert refused.value.message_key == key


def test_only_the_lead_adds_and_a_stranger_sees_a_404(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        _m, marco = person(brazos, "marco@field.test", "Marco Rossi")
        _s, stranger = person(brazos, "sam@field.test", "Sam Ng")
        field_labour.add_technician(lead, oid, {"technician_id": str(_m.id)})
        with pytest.raises(errors.AuthError) as helper_adds:
            field_labour.add_technician(marco, oid, {"technician_id": str(_s.id)})
        with pytest.raises(errors.NotFoundError):
            field_labour.labour_of(stranger, oid)
        with pytest.raises(errors.ValidationError) as self_add:
            field_labour.add_technician(
                lead,
                oid,
                {"technician_id": str(work_models.Technician.objects.get(user_id=lead.id).id)},
            )
    assert helper_adds.value.message_key == "work.labour.lead_adds_only"
    assert self_add.value.message_key == "work.labour.already_lead"


def test_another_tenants_technician_cannot_be_added(brazos, dana, lonestar):
    """Hard rule 1 — a Lone Star technician's id under Brazos Bend is a 404."""
    with tenant_ctx(lonestar):
        foreign, _actor = person(lonestar, "ls.tech@field.test", "Lone Star Tech")
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        with pytest.raises(errors.NotFoundError):
            field_labour.add_technician(lead, oid, {"technician_id": str(foreign.id)})
        assert not WorkOrderLabour.objects.filter(technician_id=foreign.id).exists()


def test_after_acceptance_labour_is_frozen(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        close(lead, oid, "passed")
        w6.accept_field_result(dana, oid)
        with pytest.raises(errors.BizError) as frozen:
            field_labour.record_time(lead, oid, {"end_at": _iso(timezone.now())})
    assert frozen.value.message_key == "work.labour.order_accepted"
