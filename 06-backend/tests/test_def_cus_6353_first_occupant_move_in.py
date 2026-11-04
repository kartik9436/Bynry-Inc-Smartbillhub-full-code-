# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6353 — the move-in wizard offered a vacant unit nobody had
#           ever lived in, then refused it (`customers.moveIn.find.noPredecessor`)
#           because its only endpoint needed a closed previous account.
# Decision: 12-governance/02-decision-log.md 2026-09-23, "NO APPLICATION FEE IS
#           EVER CARRIED…" §3 — *"the move-in wizard serves a first-occupant
#           unit … the server opens the account under the SAME guards
#           `POST /accounts` already takes (BR-CUS-017 unit free, BR-CUS-056),
#           and a linked move-in job closes as it does today."*
# Rules:    BR-CUS-017 (one active account per unit) · BR-CUS-056 (no start on
#           the outgoing tenancy's move day) · BR-CUS-1024 (no identifier, no
#           account) · BR-CUS-1077 (the approved request's move-in job closes
#           on the recorded move) · CLAUDE.md hard-won law 14 (run this file on
#           PostgreSQL too: `--ds=config.settings.pgtest`)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A first occupant moves in through the move-in wizard's own door.**

`POST /units/{unit_id}/move-in` runs the SAME `services._move_in` body as
`POST /accounts/{id}/move-in`; only where the unit comes from differs. So the
cases here are about the two things that are new — a unit with NO finished
tenancy, and a predecessor the server derives instead of the client — and about
the guards being the account door's guards, not a copy of them.

RED-FIRST (hard-won law 7), in pytest: before `move_in_to_unit` existed every
case here failed at the import of the route or the service. The predecessor case
was then proved red by making `move_in_to_unit`'s `resolve()` answer
`(unit_id, None)` unconditionally, quoted from that run:

    E  AssertionError: assert None == '01a0d011-d1c1-7f75-b1b2-091e7f6e7482'
    FAILED ...::test_the_unit_door_derives_the_predecessor_and_keeps_its_move_day
    1 failed, 3 passed

⚠ **AND THE BR-CUS-056 REFUSAL INSIDE THAT SAME CASE STILL HELD IN THE RED RUN**,
which is the point rather than a gap: `_occupancy_guards` reads the move day off
the UNIT, not off whatever the door resolved, so the guard cannot be switched off
by a door that forgets the predecessor. What the resolver decides is only what
the move record says came before.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * asserting the RESPONSE instead of the tables — every case reads the account,
    the move record and the job back out of the database;
  * a "first occupant" fixture that secretly had an account — the first case
    asserts `last_closed_account_for_unit` is None AND no account row exists for
    the unit before the move-in runs;
  * a refusal case that passes because the call errored for another reason — each
    asserts the named `message_key`.
"""

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import move_in_jobs, moves
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors
from core import errors

from tests import identity_fixtures
from tests.move_out_draft_isolation import billable_unit
from tests.test_br_cus_1077_move_in_job import _move_in_request, _served_unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import a_meter, commit_read
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

NAME = "Okonjo, Ada"


def _payload(**overrides):
    body = {
        "account_type": "residential",
        "opened_at": "2026-08-01",
        "contact": {"full_name": NAME},
        "customer": identity_fixtures.customer_block(NAME, account_type="residential"),
    }
    body.update(overrides)
    return body


def _unit_move_in(tenant, actor, unit_id, payload):
    # A REAL user id: the move record's `performed_by` is a foreign key to
    # `users`, and a random one fails the constraint check at teardown.
    return api_call(
        customers_api.unit_move_in,
        "post",
        user=FakeUser(actor.id),
        role="billing_clerk",
        tenant=tenant,
        data=payload,
        unit_id=unit_id,
    )


def test_a_unit_nobody_has_lived_in_moves_in_end_to_end(brazos, dana):
    """**The PO's case: highland park U-00003 — no account, ever.**

    Approve a move-in request for it, then complete the move-in from the unit:
    the account opens occupying, the move record names nobody as the tenancy
    before, and the request's pending job leaves the queue.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="U-00003", address="highland park")
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 0
        assert customers_selectors.last_closed_account_for_unit(unit["id"]) is None

        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_PENDING

    # Through the HTTP view — the door the wizard presses — which enters its own
    # tenant context, so the read-back below re-enters one.
    response = _unit_move_in(
        brazos, dana, str(unit["id"]), _payload(service_request_id=str(request.id))
    )

    with tenant_ctx(brazos):
        assert response.status_code == 201, response.data
        body = response.data
        assert body["moved_in_after_account_id"] is None
        account = customers_models.Account.objects.get(pk=body["id"])
        assert str(account.unit_id) == str(unit["id"])
        assert account.opened_at.isoformat() == "2026-08-01"
        assert metering_selectors.occupancy_of(metering_selectors.unit_row(unit["id"])) == (
            "occupied"
        )
        record = moves.MoveRecord.objects.get(pk=body["move_record_id"])
        assert record.kind == moves.KIND_MOVE_IN
        assert record.from_account_id is None
        assert str(record.request_id) == str(request.id)
        job.refresh_from_db()
        assert job.state == move_in_jobs.STATE_DONE
        assert body["move_in_jobs_closed"] == 1


def test_the_unit_door_refuses_an_occupied_unit_by_name(brazos, dana):
    """BR-CUS-017, through `_make_occupying` — the account door's guard."""
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 2", address="12 Alder Row")
        customers_services.move_in_to_unit(dana, unit["id"], _payload())

        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(
                    contact={"full_name": "Second, Person"},
                    customer=identity_fixtures.customer_block(
                        "Second, Person", account_type="residential", phone="512-555-0199"
                    ),
                ),
            )
        assert refused.value.message_key == "customers.account.unit_already_occupied"
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 1


def test_the_unit_door_derives_the_predecessor_and_keeps_its_move_day(brazos, dana):
    """A unit WITH a finished tenancy: the server finds it, BR-CUS-056 refuses a
    start on its move day, and the record names it as the tenancy before."""
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 3", address="40 Birch Ct")
        # DEF-CUS-10127 — the move-out below drafts the final bill or refuses
        # (DEF-CUS-10093, 2.574.0): the unit needs a cycle, a price in force
        # and a meter read on the move day.
        billable_unit(dana, brazos, unit["id"], services=("electric",))
        meter = a_meter(dana, "M-6353", unit_id=unit["id"])
        commit_read(
            dana, meter["id"], day="2026-07-31", value="14100", prior_value="13800",
            consumption="300.000000", unit="kWh",
        )
        prior = customers_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
                "contact": {"full_name": "Prior, Tenant"},
                "customer": identity_fixtures.customer_block(
                    "Prior, Tenant", account_type="residential", phone="512-555-0111"
                ),
            },
        )
        closed = customers_services.move_out(dana, prior["id"], {"moved_out_on": "2026-07-31"})
        # The refusal is not weakened: billing really drafted the final bill.
        assert closed["final_bill"]["outcome"] == "drafted", closed["final_bill"]

        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(dana, unit["id"], _payload(opened_at="2026-07-31"))
        assert "BR-CUS-056" in (refused.value.br_ref or "")

        result = customers_services.move_in_to_unit(dana, unit["id"], _payload())
        assert result["moved_in_after_account_id"] == str(prior["id"])
        record = moves.MoveRecord.objects.get(pk=result["move_record_id"])
        assert str(record.from_account_id) == str(prior["id"])


def test_a_refused_move_in_writes_nothing_and_the_next_press_succeeds(brazos, dana):
    """**Refusal, then success, in one session — the law-14 shape.**

    No identifier is refused BEFORE the transaction opens (BR-CUS-1024). The
    second refusal is one a clerk meets INSIDE it: no start date (BR-CUS-022),
    raised by `_occupancy_guards` after the account row was inserted. On
    PostgreSQL an error inside a transaction aborts it, so this is the case that
    proves the rollback leaves nothing half-written and the retry is clean.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 4", address="7 Cedar Way")

        with pytest.raises(errors.BizError) as no_identity:
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(customer={"display_name": NAME, "kind": "person"})
            )
        assert no_identity.value.message_key.startswith("customers.account.identity_")

        without_start = _payload()
        without_start.pop("opened_at")
        with pytest.raises(errors.BizError) as no_start:
            customers_services.move_in_to_unit(dana, unit["id"], without_start)
        assert no_start.value.message_key == "customers.account.start_date_required"
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 0
        assert moves.MoveRecord.objects.filter(kind=moves.KIND_MOVE_IN).count() == 0

        result = customers_services.move_in_to_unit(dana, unit["id"], _payload())
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 1
        assert result["move_no"] is not None or result["move_no_unavailable"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-6363 — THE FIELD-VISIT ROWS A CLERK ADDED, RAISED WHEN THE MOVE-IN
# IS SAVED (the shared `FieldVisitOrders` table; `from_flows.raise_orders_for`)
# ═══════════════════════════════════════════════════════════════════════════
def _work_catalogue(tenant):
    """One job type with a default priority, one without, and a crew — the
    shapes the PO approved (B14 rule 37: shapes, not figures)."""
    from apps.work import models as work_models

    # The tenant may already be seeded with priorities, and `rank` is unique per
    # tenant — so these take ranks far above any seed rather than guessing one.
    high = work_models.WorkPriority.objects.create(
        tenant=tenant, code="high-6363", name="High (test)", rank=901, sla_hours=8
    )
    normal = work_models.WorkPriority.objects.create(
        tenant=tenant, code="normal-6363", name="Normal (test)", rank=903, sla_hours=72
    )
    reconnect = work_models.WorkOrderType.objects.create(
        tenant=tenant, code="DR-6363", name="Disconnection/Reconnection", default_priority=high
    )
    reread = work_models.WorkOrderType.objects.create(tenant=tenant, code="RR-6363", name="Re-read")
    crew = work_models.Crew.objects.create(tenant=tenant, name="Crew B (3)", kind="crew")
    return high, normal, reconnect, reread, crew


def test_the_rows_added_on_step_3_are_raised_at_save_with_their_note_and_holder(brazos, dana):
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        high, normal, reconnect, reread, crew = _work_catalogue(brazos)
        _premises, unit = _served_unit(dana, brazos, label="Unit 6", address="9 Elm Row")
        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(
                field_visit={
                    "orders": [
                        {
                            "type_id": str(reconnect.id),
                            "due_on": "2026-08-01",
                            "crew_id": str(crew.id),
                            "note": "Turn water on at curb",
                        },
                        {
                            "type_id": str(reread.id),
                            "priority_id": str(normal.id),
                            "note": "Check W-5041 opening read",
                        },
                    ]
                }
            ),
        )
        raised = result["work_orders"]
        assert [row["name"] for row in raised] == ["Disconnection/Reconnection", "Re-read"]
        first = work_tables.WorkOrder.objects.get(pk=raised[0]["id"])
        second = work_tables.WorkOrder.objects.get(pk=raised[1]["id"])
        # Read back out of `work_orders`, never off the response.
        assert first.state == "planned" and second.state == "planned"
        assert first.priority_id == high.id  # the type's own default
        assert second.priority_id == normal.id
        assert first.technician_notes == "Turn water on at curb"
        assert first.due_at is not None and second.due_at is not None  # SLA target
        # The picked DAY is the tenant's day — not midnight UTC, which a US
        # tenant reads back as the day before.
        from apps.tenancy import selectors as tenancy_selectors

        zone = tenancy_selectors.tenant_timezone()
        assert first.due_at.astimezone(zone).date().isoformat() == "2026-08-01"
        assert str(first.account_id) == result["id"]
        assert first.source == "move_in" and first.source_ref == result["move_no"]
        assert first.assignee_crew_id == crew.id and first.dispatch_state == "scheduled"
        assert second.assignee_crew_id is None and second.assignee_technician_id is None


def test_a_row_with_no_job_type_is_refused_before_anything_is_written(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 7", address="11 Elm Row")
        with pytest.raises(errors.ValidationError) as refused:
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(field_visit={"orders": [{"note": "no type"}]})
            )
        assert refused.value.message_key == "work.fromFlows.jobTypeRequired"
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 0

        declined = customers_services.move_in_to_unit(
            dana, unit["id"], _payload(field_visit={"none": True})
        )
        assert declined["field_visit_declined"] is True
        assert declined["work_orders"] == []
