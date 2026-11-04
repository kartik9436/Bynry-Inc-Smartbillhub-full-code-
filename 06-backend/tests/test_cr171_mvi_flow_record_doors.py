# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.23 · P1.24 · P1.25
# Rules:    CR-171 §6.2 J7 · BR-CUS-056 · BR-CUS-021 / BR-MET-128 · BR-WRK-055 ·
#           BR-CUS-152 · CLAUDE.md hard rules 1 · 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**The committed move-in's doors — change date, opening read, work order —
through the routes the details view calls, read back from the tables.**

RED-FIRST (law 7): written before `move_in_flow` existed; first run
`ImportError: cannot import name 'move_in_flow' from 'apps.customers'`.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A date change that moves only the account.** The case reads every
    agreement's `started_on` back, and the move record's `effective_on`, which
    must NOT move (`BR-CUS-152`).
  * **An opening read that lands at today.** The read is asserted dated the
    move-in date, with event `move_in` and the acting user — metering's stamps.
  * **A route that resolves in a unit test and not in the product.** Every
    path is resolved through the ROOT urlconf (law 2).
"""

from datetime import date

import pytest
from django.urls import resolve

from core import errors

from apps.customers import models as customers_models
from apps.customers import move_in_cancel, move_in_flow, move_in_flow_api, moves
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.work import connection_models as work_tables

from tests import identity_fixtures
from tests.test_br_cus_1077_move_in_job import _move_in_request, _served_unit
from tests.test_def_cus_6353_first_occupant_move_in import _payload, _work_catalogue
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, audit_rows, brazos, dana, tenant_ctx  # noqa: F401
from tests.test_w9_event_reads import _asset_id, _head, _metered_unit
from tests.test_us_met_reads_helpers import seed_config

pytestmark = pytest.mark.django_db


def _committed(actor, tenant, *, label="Unit 3B", address="8 Kestrel Park", **extra):
    _premises, unit = _served_unit(actor, tenant, label=label, address=address)
    result = customers_services.move_in_to_unit(actor, unit["id"], _payload(**extra))
    return unit, result, moves.MoveRecord.objects.get(pk=result["move_record_id"])


def _post(view, ref, data, tenant, actor):
    return api_call(
        view,
        "post",
        user=FakeUser(actor.id),
        role="billing_clerk",
        tenant=tenant,
        data=data,
        ref=ref,
    )


def test_every_flow_route_resolves_through_the_root_urlconf():
    for tail, view in (
        ("cancel-preview", move_in_flow_api.move_cancel_preview),
        ("cancel", move_in_flow_api.move_cancel),
        ("move-in-date", move_in_flow_api.move_in_date),
        ("opening-reads", move_in_flow_api.move_opening_reads),
        ("work-orders", move_in_flow_api.move_work_orders),
    ):
        assert resolve(f"/api/brazos/moves/MVI-26-0011/{tail}").func is view, tail
    # …and the record's own read is not shadowed by them.
    from apps.customers import api as customers_api

    assert resolve("/api/brazos/moves/MVI-26-0011").func is customers_api.move_record_detail


# ═══════════════════════════════════════════════════════════════════════════
# P1.23 · CHANGE MOVE-IN DATE
# ═══════════════════════════════════════════════════════════════════════════
def test_changing_the_date_moves_the_account_and_its_agreements_not_the_record(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos)

    response = _post(move_in_flow_api.move_in_date, record.move_no, {"opened_at": "2026-08-03"}, brazos, dana)

    with tenant_ctx(brazos):
        assert response.status_code == 200, response.data
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.opened_at == date(2026, 8, 3)
        agreements = customers_models.ServiceAgreement.objects.filter(account=account)
        assert agreements.exists()
        assert {a.started_on for a in agreements} == {date(2026, 8, 3)}
        record.refresh_from_db()
        assert record.effective_on == date(2026, 8, 1)  # BR-CUS-152 — never updated
        assert response.data["was"] == "2026-08-01"
    changed = [r for r in audit_rows if r["action"] == "account.move_in_date_changed"]
    assert len(changed) == 1
    assert changed[0]["before"] == {"opened_at": "2026-08-01"}


def test_the_date_cannot_move_once_a_bill_has_issued(brazos, dana, monkeypatch):
    from apps.customers import seams

    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos, label="Unit 2", address="2 Elm")
        monkeypatch.setattr(seams, "last_issued_invoice_date", lambda _id: date(2026, 9, 1))
        with pytest.raises(errors.BizError) as caught:
            move_in_flow.change_move_in_date(dana, record.move_no, "2026-08-05")
        assert customers_models.Account.objects.get(pk=result["id"]).opened_at == date(2026, 8, 1)
    assert caught.value.message_key == "customers.moveIn.date.billIssued"


def test_the_new_date_meets_the_boundary_day_rule(brazos, dana):
    """BR-CUS-056: not ON the previous account's last day. A cancelled tenancy
    closed on 31 July; the next one cannot be moved back onto the 31st."""
    with tenant_ctx(brazos):
        unit, _result, record = _committed(dana, brazos, label="Unit 3", address="3 Elm")
        move_in_cancel.cancel(dana, record.move_no)
        again = customers_services.move_in_to_unit(dana, unit["id"], _payload())
        second = moves.MoveRecord.objects.get(pk=again["move_record_id"])
        with pytest.raises(errors.BizError) as caught:
            move_in_flow.change_move_in_date(dana, second.move_no, "2026-07-31")
        assert customers_models.Account.objects.get(pk=again["id"]).opened_at == date(2026, 8, 1)
    assert caught.value.message_key == "customers.account.start_on_prior_move_day"


def test_a_not_started_move_in_has_no_date_to_change(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="U-7", address="7 Oak")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        from apps.customers import move_in_jobs

        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        with pytest.raises(errors.BizError) as caught:
            move_in_flow.change_move_in_date(dana, job.move_no, "2026-08-05")
    assert caught.value.message_key == "customers.moveIn.notStartedYet"


def test_a_garbled_date_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos, label="Unit 4", address="4 Elm")
        with pytest.raises(errors.ValidationError) as caught:
            move_in_flow.change_move_in_date(dana, record.move_no, "08/05/2026")
    assert caught.value.message_key == "customers.moveIn.date.invalid"


# ═══════════════════════════════════════════════════════════════════════════
# P1.24 · ENTER OPENING READ
# ═══════════════════════════════════════════════════════════════════════════
def test_an_opening_read_after_complete_goes_through_metering_dated_the_move_in(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos, label="Unit R")
        moved = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-20",
                "contact": {"full_name": "Verma, Asha"},
                "customer": identity_fixtures.customer_block(
                    "Verma, Asha", account_type="residential"
                ),
            },
        )
        record = moves.MoveRecord.objects.get(pk=moved["move_record_id"])
        assert _head(_asset_id(unit, "M-9101")) is None

        answer = move_in_flow.enter_opening_reads(
            dana, record.move_no, [{"meter_no": "M-9101", "value": "43566"}]
        )

        head = _head(_asset_id(unit, "M-9101"))
    assert answer["posted_reads"] == 1
    assert head.event_context == "move_in"
    assert head.read_at.date().isoformat() == "2026-08-20"
    assert head.imported_by_id == dana.id


def test_an_empty_reading_list_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos, label="Unit 5", address="5 Elm")
        with pytest.raises(errors.ValidationError) as caught:
            move_in_flow.enter_opening_reads(dana, record.move_no, [])
    assert caught.value.field_errors[0]["message_key"] == "customers.event_reads.rows_required"


# ═══════════════════════════════════════════════════════════════════════════
# P1.25 · ADD A WORK ORDER (Send a message is the account's existing door)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_work_order_added_from_the_record_is_raised_against_the_move(brazos, dana):
    with tenant_ctx(brazos):
        _high, _normal, reconnect, _reread, crew = _work_catalogue(brazos)
        _unit, result, record = _committed(dana, brazos, label="Unit 6", address="6 Elm")

    response = _post(
        move_in_flow_api.move_work_orders,
        record.move_no,
        {"orders": [{"type_id": str(reconnect.id), "crew_id": str(crew.id), "note": "Turn on"}]},
        brazos,
        dana,
    )

    with tenant_ctx(brazos):
        assert response.status_code == 201, response.data
        order = work_tables.WorkOrder.objects.get(pk=response.data["work_orders"][0]["id"])
        assert order.source == "move_in" and order.source_ref == record.move_no
        assert str(order.account_id) == result["id"]


def test_nothing_to_raise_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos, label="Unit 7", address="7 Elm")
        with pytest.raises(errors.ValidationError) as caught:
            move_in_flow.add_work_orders(dana, record.move_no, {"orders": []})
    assert caught.value.message_key == "customers.moveIn.work.nothingToRaise"


def test_send_a_message_is_the_accounts_existing_door(brazos, dana):
    """P1.25's other half needs no new route: the record serves `account_id`
    and `/accounts/{id}/communication` resolves through the root urlconf."""
    from apps.customers import communication_api, move_record_reads

    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos, label="Unit 8", address="8 Elm")
        detail = move_record_reads.record_detail(record.move_no)
    assert str(result["id"]) in str(detail)
    assert (
        resolve(f"/api/brazos/accounts/{result['id']}/communication").func
        is communication_api.account_communication
    )
