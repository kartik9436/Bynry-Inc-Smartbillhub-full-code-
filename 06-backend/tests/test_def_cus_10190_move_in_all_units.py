# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10190 — Move-in step 1 listed only vacant units.
# Ruling:   PO 2026-10-17, decision log *"MOVE-IN SEARCHES ALL UNITS, NOT ONLY
#           VACANT ONES"* + its *"Same day"* confirmation.
# Code:     apps/customers/move_in_units.py · services._move_in / move_out ·
#           disconnects.stop_for_move_out · work.from_flows.cancel_flow_order
# Run:      also on PostgreSQL (hard-won law 14): --ds=config.settings.pgtest
# ───────────────────────────────────────────────────────
"""**Every unit is searchable; what a move-in may do on each is the server's.**

RED FIRST (law 7): written before `move_in_units` existed — every case failed
at `from apps.customers import move_in_units` (ModuleNotFoundError), and the
route cases with a 404 on `/move-ins/units`. The blocked-commit case was then
proved red by stubbing `refuse_if_blocked` to `return None`: the move-in onto a
unit with a move-out in progress was accepted (BR-CUS-017 cannot see a draft).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
RESPONSE where the table is the fact — the handover reads the draft row back,
the move-out reads the stop and the case back; and a "state" fixture that is
really another state — each case asserts the account's status code first.
"""

from datetime import date

import pytest

from apps.customers import api as customers_api
from apps.customers import disconnects, move_in_units
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers.temporary_stop_models import STATUS_ON_HOLD, TemporaryStop
from apps.metering import models as metering_models
from apps.tenancy.models import WizardPark
from core import errors

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: F401
from tests.test_us_cus_004_005_move_in_out import (
    _account_payload,
    _occupant,
    _unit_with_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

MOVE_IN_DAY = "2026-08-15"


def _status(account_id, code):
    account = customers_models.Account.objects.get(pk=account_id)
    account.status = customers_models.AccountStatus.objects.get(tenant_id=account.tenant_id, code=code)
    account.save(update_fields=["status"])
    return account


def _row(unit_id, term=""):
    rows, _total = move_in_units.search(term, per=50)
    return next(row for row in rows if row["id"] == str(unit_id))


def _search(tenant, q="", **extra):
    return api_call(
        customers_api.move_in_units_search,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        data={"q": q, **extra},
    )


# ── task 2 · one state per status ───────────────────────────────────────────
def test_every_status_is_listed_with_its_state_path_and_reason(brazos, marcus):
    with tenant_ctx(brazos):
        vacant = _unit_with_plan(marcus, brazos, label="V-1")
        closed = _unit_with_plan(marcus, brazos, label="C-1")
        left = _occupant(marcus, brazos, closed, name="Cara Closed")
        customers_services.move_out(marcus, left["id"], {"moved_out_on": "2026-08-01"})
        active = _unit_with_plan(marcus, brazos, label="A-1")
        _occupant(marcus, brazos, active, name="Arlo Active")
        hold = _unit_with_plan(marcus, brazos, label="H-1")
        _status(_occupant(marcus, brazos, hold, name="Hana Hold")["id"], "vacation_hold")
        marked = _unit_with_plan(marcus, brazos, label="M-1")
        _status(_occupant(marcus, brazos, marked, name="Milo Marked")["id"], "marked_disconnect")
        cut = _unit_with_plan(marcus, brazos, label="D-1")
        _status(_occupant(marcus, brazos, cut, name="Dora Cut")["id"], "disconnected")
        pending = _unit_with_plan(marcus, brazos, label="P-1")
        _status(_occupant(marcus, brazos, pending, name="Pia Pending")["id"], "pending_activation")

        expect = {
            vacant["id"]: ("vacant", True, "move_in", None),
            closed["id"]: ("closed", True, "move_in", None),
            active["id"]: ("active", True, "move_out_first", None),
            hold["id"]: ("vacation_hold", True, "move_out_first", None),
            marked["id"]: ("marked_disconnect", True, "move_out_first", None),
            cut["id"]: ("disconnected", True, "close_out_first", None),
            pending["id"]: (
                "pending_activation",
                False,
                None,
                "customers.moveIn.unitSearch.blocked.pendingActivation",
            ),
        }
        for unit_id, (state, selectable, path, reason) in expect.items():
            row = _row(unit_id)
            assert (row["state"], row["selectable"], row["path"], row["reason_key"]) == (
                state,
                selectable,
                path,
                reason,
            ), row["label"]
        assert _row(active["id"])["occupant"]["name"] == "Arlo Active"
        assert _row(closed["id"])["occupant"]["name"] == "Cara Closed"
        assert _row(vacant["id"])["occupant"] is None


def test_vacant_first_then_paged_in_sql(brazos, marcus):
    with tenant_ctx(brazos):
        busy = _unit_with_plan(marcus, brazos, label="Z-busy")
        _occupant(marcus, brazos, busy, name="Busy Bee")
        free = [_unit_with_plan(marcus, brazos, label=f"Free-{n}") for n in range(3)]
        rows, total = move_in_units.search("", page=1, per=50)
        states = [row["state"] for row in rows]
        assert states.index("active") > max(i for i, s in enumerate(states) if s == "vacant")
        page1, total1 = move_in_units.search("", page=1, per=2)
        page2, _ = move_in_units.search("", page=2, per=2)
        assert total1 == total >= 4 and len(page1) == 2 and len(page2) == 2
        assert {r["id"] for r in page1}.isdisjoint({r["id"] for r in page2})
        assert {str(u["id"]) for u in free} <= {r["id"] for r in rows}


def test_search_by_name_unit_and_property_and_removed_not_listed(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos, label="Apt 104")
        _occupant(marcus, brazos, unit, name="Quentin Quill")
        by_name, _ = move_in_units.search("Quentin")
        assert [r["id"] for r in by_name] == [str(unit["id"])]
        by_label, _ = move_in_units.search("Apt 104")
        assert str(unit["id"]) in [r["id"] for r in by_label]
        premise_no = metering_models.Unit.objects.get(pk=unit["id"]).premises.premise_no
        if premise_no:
            by_premise, _ = move_in_units.search(premise_no)
            assert str(unit["id"]) in [r["id"] for r in by_premise]
        gone = _unit_with_plan(marcus, brazos, label="Gone 9")
        metering_models.Unit.objects.filter(pk=gone["id"]).update(deleted_at=date(2026, 8, 1))
        assert move_in_units.search("Gone 9")[1] == 0


def test_search_by_meter_number(brazos, marcus, monkeypatch):
    """The meter leg is assets' (`unit_ids_for_asset_search`), joined lazily."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos, label="Meter unit")
        from apps.customers import seams

        monkeypatch.setattr(
            seams, "unit_ids_for_asset_search", lambda term: [str(unit["id"])] if term == "E-7781" else []
        )
        rows, total = move_in_units.search("E-7781")
        assert total == 1 and rows[0]["id"] == str(unit["id"])


# ── tasks 3 + 4 + 5 · handover, blocked commit, resume ──────────────────────
def test_handover_parks_the_old_occupants_move_out_and_blocks_the_move_in(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        sitting = _occupant(marcus, brazos, unit, name="Sam Sitting")
        answer = move_in_units.start_handover(
            marcus, {"unit_id": str(unit["id"]), "opened_at": MOVE_IN_DAY, "move_in_park_id": None}
        )
        assert answer["path"] == "move_out_first"
        assert answer["moved_out_on"] == "2026-08-14"
        draft = WizardPark.objects.get(pk=answer["move_out_park_id"])
        assert draft.flow == "move_out"
        assert draft.values["moved_out_on"] == "2026-08-14"
        assert draft.values["account_id"] == sitting["id"]
        # The account is NOT closed by the move-in (PO: "won't close their account by itself").
        assert customers_models.Account.objects.get(pk=sitting["id"]).closed_at is None

        row = _row(unit["id"])
        assert (row["state"], row["selectable"]) == ("move_out_in_progress", False)
        assert row["reason_key"] == "customers.moveIn.unitSearch.blocked.moveOutInProgress"
        with pytest.raises(errors.BizError) as refused:
            move_in_units.start_handover(marcus, {"unit_id": str(unit["id"]), "opened_at": MOVE_IN_DAY})
        assert refused.value.message_key == "customers.moveIn.unitSearch.blocked.moveOutInProgress"

        # Finishing the move-out (it adopts the draft) unblocks the unit.
        customers_services.move_out(
            marcus,
            sitting["id"],
            {"moved_out_on": answer["moved_out_on"], "wizard_park_id": answer["move_out_park_id"]},
        )
        assert not WizardPark.objects.filter(pk=answer["move_out_park_id"]).exists()
        assert _row(unit["id"])["state"] == "closed"
        incoming = customers_services.move_in(marcus, sitting["id"], _account_payload())
        assert incoming["opened_at"] == MOVE_IN_DAY
        assert incoming["moved_in_after_account_no"] == sitting["account_no"]


def test_the_move_in_refuses_a_blocked_unit_by_name(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        old = _occupant(marcus, brazos, unit, opened_at="2026-06-01")
        customers_services.move_out(marcus, old["id"], {"moved_out_on": "2026-07-01"})
        _status(
            _occupant(marcus, brazos, unit, name="Pat Pending", opened_at="2026-07-10")["id"],
            "pending_activation",
        )
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in(marcus, old["id"], _account_payload())
        assert refused.value.message_key == "customers.moveIn.unitSearch.blocked.pendingActivation"

        removed = _unit_with_plan(marcus, brazos, label="Removed")
        metering_models.Unit.objects.filter(pk=removed["id"]).update(deleted_at=date(2026, 8, 1))
        with pytest.raises(errors.BizError) as gone:
            customers_services.move_in_to_unit(marcus, str(removed["id"]), _account_payload())
        assert gone.value.message_key == "customers.moveIn.unitSearch.blocked.removed"


# ── task 6 · what the move-out settles on the way ───────────────────────────
def test_a_vacation_hold_ends_when_the_holder_moves_out(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        holder = _occupant(marcus, brazos, unit, name="Hal Hold")
        _status(holder["id"], "vacation_hold")
        stop = TemporaryStop.objects.create(
            tenant=brazos,
            account_id=holder["id"],
            status=STATUS_ON_HOLD,
            stop_from=date(2026, 7, 10),
            restart_on=date(2026, 9, 30),
        )
        TemporaryStop.objects.filter(pk=stop.pk).update(shutoff_order_no="WO-0041", turnon_order_no="WO-0042")
        from apps.customers import seams

        called: list = []
        monkeypatch.setattr(
            seams, "cancel_flow_order", lambda actor, *, order_no: called.append(order_no) or True
        )
        result = customers_services.move_out(marcus, holder["id"], {"moved_out_on": "2026-08-14"})
        # DEF-CUS-10194 (walk W5) — BOTH of the hold's jobs are called off:
        # nobody is shutting off or turning on for a customer who has left.
        assert sorted(called) == ["WO-0041", "WO-0042"]
        stop.refresh_from_db()
        assert stop.status == "ended" and stop.restart_on == date(2026, 8, 14)
        assert customers_models.Account.objects.get(pk=holder["id"]).status.code == "closed"
        assert {"code": "temporary_stop_ended", "stop_id": str(stop.id)} in result["settled"]


def test_a_marked_disconnect_case_closes_as_customer_left_and_the_debt_stays(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        owing = _occupant(marcus, brazos, unit, name="Owen Owing")
        _status(owing["id"], "marked_disconnect")
        case = disconnects.DisconnectCase.objects.create(
            tenant=brazos,
            account_id=owing["id"],
            state=disconnects.STATE_SCHEDULED,
            amount_owed_at_open="310.0000",
            currency="USD",
            opened_on=date(2026, 7, 1),
        )
        balance_before = customers_models.Account.objects.get(pk=owing["id"]).balance
        result = customers_services.move_out(marcus, owing["id"], {"moved_out_on": "2026-08-14"})
        case.refresh_from_db()
        assert case.state == disconnects.STATE_STOPPED
        assert case.stopped_reason == disconnects.STOP_CUSTOMER_LEFT
        assert case.stopped_on == date(2026, 8, 14)
        assert customers_models.Account.objects.get(pk=owing["id"]).balance == balance_before
        assert any(row["code"] == "disconnect_case_closed_customer_left" for row in result["settled"])
        # The clerk's stop modal still refuses the system-only reason.
        assert disconnects.STOP_CUSTOMER_LEFT not in disconnects.STOP_REASONS


def test_a_move_in_after_a_closed_out_cut_raises_a_reconnect(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        cut = _occupant(marcus, brazos, unit, name="Cyd Cut")
        customers_services.move_out(marcus, cut["id"], {"moved_out_on": "2026-08-01"})
        disconnects.DisconnectCase.objects.create(
            tenant=brazos,
            account_id=cut["id"],
            state=disconnects.STATE_CLOSED_OUT,
            amount_owed_at_open="612.7500",
            currency="USD",
            opened_on=date(2026, 7, 1),
            cut_on=date(2026, 8, 1),
            reconnection_fee_amount="50.0000",
            reconnection_fee_code="RECONNECT",
            deposit_disposition=disconnects.DEPOSIT_DISPOSITIONS[0],
        )
        asked: list = []
        from apps.customers import seams

        def fake_raise(actor, *, account_id, visits):
            asked.append((account_id, visits))
            return {"raised": [{"order_no": "WO-9001", "role": "reconnect"}], "count": 1}

        monkeypatch.setattr(seams, "raise_temporary_stop_visits", fake_raise)
        incoming = customers_services.move_in(marcus, cut["id"], _account_payload())
        assert incoming["reconnect"] == [{"code": "reconnect_job_raised", "order_no": "WO-9001"}]
        assert asked[0][0] == incoming["id"]
        assert asked[0][1][0]["flow"] == "reconnect" and asked[0][1][0]["due_on"] == MOVE_IN_DAY


# ── tenant isolation (hard rule 1) ──────────────────────────────────────────
def test_another_utilitys_units_never_appear_and_cannot_be_handed_over(brazos, lonestar, marcus, erin):
    with tenant_ctx(lonestar):
        from tests.test_us_met_helpers import make_premises, make_unit

        foreign = make_unit(erin, make_premises(erin, services_available=["water"])["id"], label="Lonestar Unit")
    response = _search(brazos, q="Lonestar Unit")
    assert response.status_code == 200, response.data
    assert response.data["count"] == 0
    with tenant_ctx(brazos):
        with pytest.raises(Exception) as refused:
            move_in_units.start_handover(
                marcus, {"unit_id": str(foreign["id"]), "opened_at": MOVE_IN_DAY}
            )
        assert not isinstance(refused.value, errors.BizError)


def test_the_route_serves_the_standard_envelope(brazos, marcus):
    with tenant_ctx(brazos):
        _unit_with_plan(marcus, brazos, label="Route unit")
    response = _search(brazos, q="Route unit")
    assert response.status_code == 200, response.data
    assert set(response.data) >= {"count", "next", "previous", "results"}
    assert response.data["results"][0]["state"] == "vacant"
