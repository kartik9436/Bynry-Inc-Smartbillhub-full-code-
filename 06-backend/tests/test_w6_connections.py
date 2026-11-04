# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W6 tasks 6.1 (five tables + RLS) · 6.2 (the connection state
#           machine PLUS a state per service) · 6.9 (`service_characteristics`)
#           Screens: S86 · S87 · S88 (no frontend half in this lane)
# Rules:    BR-MET-108 (a ROW per characteristic keyed by unit and service; an
#           absent required characteristic must REFUSE with the absence named,
#           NEVER price it at zero) · BR-MET-104 (the characteristic lives on
#           the UNIT — PO 2026-08-24, closing OQ-348) · BR-TEN-035 (numbering) ·
#           CLAUDE.md hard rule 1 (tenant scoping; RLS ENABLE + FORCE) ·
#           hard rule 3 (an explicit unit, ALWAYS — `unit_of_measure` is a
#           column and is refused when blank)
# Questions: OQ-249 (is Work a tenth module? — the `we schedule it` dispatch
#           mode raises rather than half-building a dispatch board)
# ───────────────────────────────────────────────────────
"""W6 New Connect — the state machine, the characteristics, and the isolation.

The eight rows of B18 §5.4.8 are the fixture this file pins, because they are
the ones on the PO's own screen and because they are the ONLY published
statement of what each connection state means:

    CON-26-0110  1 unit  E W    5 of 5  —            Energised
    CON-26-0119  1 unit  E W G  5 of 9  permit       On hold
    CON-26-0121  1 unit  E W    2 of 5  materials    In progress
    CON-26-0126  1 unit  E W G  3 of 9  inspection   Partly energised
    CON-26-0117  25 units E W S T +1  5 of 7  inspection  Partly energised
    CON-26-0128  1 unit  E W    2 of 5  —            Partly energised
    CON-26-0124  1 unit  E W B  0 of 7  —            Requested
    CON-26-0122  12 units E W S  1 of 6  site access  In progress

`derive_connection_state` reproduces all eight from per-service states alone,
which is what makes it the design's rule rather than this lane's invention.
"""

import pathlib
import re
from decimal import Decimal

import pytest
from django.db import migrations, models

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors

from tests import identity_fixtures
from tests.br_cus_1114_fixtures import top_up_homes
from tests.isolation_helpers import (
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import (  # noqa: F401
    api_call,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

MIGRATION = "apps/metering/migrations/0026_cr030_w6_connections.py"
W6_TABLES = (
    "connections",
    "connection_services",
    "work_orders",
    "work_order_templates",
    "service_characteristics",
)


# ── fixture plumbing ────────────────────────────────────────────────────────
def _build(actor, *, services=("electric", "water"), submit=True):
    """One connection with a premise, a unit and its services — the shape every
    case below starts from."""
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    rows = {
        code: w6.add_connection_service(
            actor, connection.id, service_code=code, unit_id=unit["id"]
        )["id"]
        for code in services
    }
    if submit:
        w6.submit_connection(actor, connection.id)
    connection.refresh_from_db()
    return connection, unit, rows


def _assert_cache_agrees(connection):
    """The stored `connections.state` IS `derive_connection_state()`.

    This is the assertion the whole cache design rests on — a stored figure
    whose agreement with its source is not asserted is a comment (hard-won
    law 1).
    """
    connection.refresh_from_db()
    assert connection.state == w6.connection_state(connection), (
        "connections.state has drifted from its own derivation — it is a CACHE of "
        "derive_connection_state() and refresh_connection_state() is its only writer"
    )


# ════════════════════════════════════════════════════════════════════════════
# 6.2 · THE DERIVATION — pure, no database, all eight seeded rows
# ════════════════════════════════════════════════════════════════════════════
def _state(service_states, *, submitted=True, held=False, cancelled=False):
    return w6.derive_connection_state(
        submitted=submitted, held=held, cancelled=cancelled, service_states=service_states
    )


def test_w6_the_eight_seeded_rows_come_out_of_the_derivation():
    """B18 §5.4.8, row by row."""
    # CON-26-0110 · E W · 5 of 5 · Energised
    assert _state([work_tables.SVC_ACTIVATED, work_tables.SVC_ACTIVATED]) == work_tables.ACTIVATED
    # CON-26-0119 · E W G · 5 of 9 · On hold — the hold OUTRANKS the progress
    assert _state([work_tables.SVC_ACTIVATED, work_tables.SVC_IN_PROGRESS, work_tables.SVC_PENDING], held=True) == work_tables.ON_HOLD
    # CON-26-0121 · E W · 2 of 5 · In progress — work started, nothing live yet
    assert _state([work_tables.SVC_IN_PROGRESS, work_tables.SVC_PENDING]) == work_tables.IN_PROGRESS
    # CON-26-0126 · E W G · 3 of 9 · Partly energised
    assert _state([work_tables.SVC_ACTIVATED, work_tables.SVC_IN_PROGRESS, work_tables.SVC_PENDING]) == work_tables.PARTLY_ACTIVATED
    # CON-26-0117 · 25 units · 5 of 7 · Partly energised
    assert (
        _state([work_tables.SVC_ACTIVATED, work_tables.SVC_ACTIVATED, work_tables.SVC_PENDING, work_tables.SVC_IN_PROGRESS])
        == work_tables.PARTLY_ACTIVATED
    )
    # CON-26-0128 · E W · 2 of 5 · Partly energised
    assert _state([work_tables.SVC_ACTIVATED, work_tables.SVC_PENDING]) == work_tables.PARTLY_ACTIVATED
    # CON-26-0124 · E W B · 0 of 7 · Requested
    assert _state([work_tables.SVC_PENDING] * 3) == work_tables.REQUESTED
    # CON-26-0122 · 12 units · 1 of 6 · In progress
    assert _state([work_tables.SVC_IN_PROGRESS, work_tables.SVC_PENDING, work_tables.SVC_PENDING]) == work_tables.IN_PROGRESS


def test_w6_draft_and_cancelled_outrank_everything_the_services_say():
    assert _state([work_tables.SVC_ACTIVATED], submitted=False) == work_tables.DRAFT
    assert _state([work_tables.SVC_ACTIVATED], cancelled=True) == work_tables.CANCELLED
    # Cancelled beats held, and held beats progress — one order, stated once.
    assert _state([work_tables.SVC_ACTIVATED], held=True, cancelled=True) == work_tables.CANCELLED


def test_w6_a_cancelled_service_leaves_nothing_waiting():
    """Gas cancelled, electric live → Energised, not Partly energised.

    A cancelled service is EXCLUDED from the tally rather than counted as
    unfinished: there is nothing left to wait for, and a build stuck on
    `Partly energised` forever would put a permanently open row on S86.
    """
    assert _state([work_tables.SVC_ACTIVATED, work_tables.SVC_CANCELLED]) == work_tables.ACTIVATED
    assert _state([work_tables.SVC_CANCELLED, work_tables.SVC_CANCELLED]) == work_tables.REQUESTED


# ════════════════════════════════════════════════════════════════════════════
# 6.2 · THE MACHINE OVER REAL ROWS
# ════════════════════════════════════════════════════════════════════════════
def test_w6_a_new_connection_is_draft_and_carries_a_number(dana, brazos):
    """✅ **THE `connection` SERIES LANDED 2026-08-25 AND THIS ASSERTION FLIPPED.**

    It was written the other way round — `connection_no is None` plus a
    `numbering_series_missing` warning — because `core/numbering.py` had no
    `connection` key and this lane could not add one. The catalogue row is now
    there at `CON-{YY}-{0000}`, so the build numbers, and the test that reported
    the gap is the test that now proves it closed.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        assert created["state"] == work_tables.DRAFT
        assert created["connection_no"], "the connection series is seeded — a build must number"
        assert not [
            warning
            for warning in created["warnings"]
            if warning.get("code") == "numbering_series_missing"
        ]
        # DEF-615, which is a test and a catalogue disagreeing about a prefix
        # since the day both landed: the seeded default must render the grammar
        # the design DRAWS (`CON-26-0110`, B18 §5.4.8/§5.4.9), not merely some
        # number. This is the check DEF-615's own prevention column asks for.
        assert re.fullmatch(r"CON-\d{2}-\d{4}", created["connection_no"]), created["connection_no"]
        assert work_tables.Connection.objects.get(pk=created["id"]).connection_no == created["connection_no"]


def test_w6_services_that_disagree_make_the_connection_partly_energised(dana, brazos):
    """*"Electric can be billing while gas waits on its pressure test."*"""
    with tenant_ctx(brazos):
        connection, _unit, rows = _build(dana)
        assert connection.state == work_tables.REQUESTED
        _assert_cache_agrees(connection)

        w6.transition_service(dana, rows["electric"], work_tables.SVC_IN_PROGRESS)
        connection.refresh_from_db()
        assert connection.state == work_tables.IN_PROGRESS
        _assert_cache_agrees(connection)

        result = w6.transition_service(dana, rows["electric"], work_tables.SVC_ACTIVATED)
        assert result["connection_state"] == work_tables.PARTLY_ACTIVATED
        connection.refresh_from_db()
        assert connection.state == work_tables.PARTLY_ACTIVATED
        assert connection.activated_at is None  # the BUILD is not energised yet
        _assert_cache_agrees(connection)

        w6.transition_service(dana, rows["water"], work_tables.SVC_ACTIVATED)
        connection.refresh_from_db()
        assert connection.state == work_tables.ACTIVATED
        assert connection.activated_at is not None
        _assert_cache_agrees(connection)


def test_w6_a_hold_outranks_progress_and_lifting_it_restores_what_the_services_say(dana, brazos):
    with tenant_ctx(brazos):
        connection, _unit, rows = _build(dana)
        w6.transition_service(dana, rows["electric"], work_tables.SVC_ACTIVATED)
        assert w6.hold_connection(dana, connection.id, reason="permit")["state"] == work_tables.ON_HOLD
        _assert_cache_agrees(connection)
        # The hold is a TIMESTAMP, not a state token, so clearing it cannot lose
        # the progress underneath — the whole reason for that shape.
        assert w6.release_connection(dana, connection.id)["state"] == work_tables.PARTLY_ACTIVATED
        _assert_cache_agrees(connection)


@pytest.mark.parametrize(
    "start,target",
    [
        (work_tables.SVC_ACTIVATED, work_tables.SVC_IN_PROGRESS),  # de-energising is a DISCONNECT (W7)
        (work_tables.SVC_ACTIVATED, work_tables.SVC_PENDING),
        (work_tables.SVC_ACTIVATED, work_tables.SVC_ON_HOLD),
        (work_tables.SVC_CANCELLED, work_tables.SVC_IN_PROGRESS),  # cancelled is terminal
        (work_tables.SVC_CANCELLED, work_tables.SVC_ACTIVATED),
        (work_tables.SVC_IN_PROGRESS, work_tables.SVC_PENDING),  # work that has started cannot un-start
        (work_tables.SVC_ON_HOLD, work_tables.SVC_PENDING),
    ],
)
def test_w6_illegal_service_transitions_are_refused_by_name(dana, brazos, start, target):
    with tenant_ctx(brazos):
        connection, _unit, rows = _build(dana, services=("electric",))
        row = work_tables.ConnectionService.objects.get(pk=rows["electric"])
        row.state = start
        row.save(update_fields=["state"])
        w6.refresh_connection_state(connection)
        with pytest.raises(errors.BizError) as caught:
            w6.transition_service(dana, row.id, target)
        assert caught.value.code == errors.BIZ_STATE
        # B8: every BIZ refusal carries its BR-ID, and the message names BOTH
        # states — "cannot transition" with no nouns in it is unactionable.
        assert caught.value.br_ref
        assert caught.value.params == {"from": start, "to": target}
        row.refresh_from_db()
        assert row.state == start, "a refused transition must not have moved the row"


@pytest.mark.parametrize(
    "start,target",
    [
        (work_tables.SVC_PENDING, work_tables.SVC_IN_PROGRESS),
        (work_tables.SVC_PENDING, work_tables.SVC_ON_HOLD),
        # Storm water is *"assessed from records — no visit"* and has ZERO work
        # orders (B18 §8.1), so pending → energised must stay legal.
        (work_tables.SVC_PENDING, work_tables.SVC_ACTIVATED),
        (work_tables.SVC_IN_PROGRESS, work_tables.SVC_ON_HOLD),
        (work_tables.SVC_ON_HOLD, work_tables.SVC_IN_PROGRESS),
        (work_tables.SVC_IN_PROGRESS, work_tables.SVC_CANCELLED),
    ],
)
def test_w6_legal_service_transitions_are_allowed(dana, brazos, start, target):
    with tenant_ctx(brazos):
        connection, _unit, rows = _build(dana, services=("electric",))
        row = work_tables.ConnectionService.objects.get(pk=rows["electric"])
        row.state = start
        row.save(update_fields=["state"])
        w6.refresh_connection_state(connection)
        w6.transition_service(dana, row.id, target)
        row.refresh_from_db()
        assert row.state == target
        _assert_cache_agrees(connection)


# ── NCT-01 / NCT-02, the PO's screens of 2026-08-25 ─────────────────────────
def test_w6_waiting_on_is_an_axis_of_its_own_not_the_holds_reason(dana, brazos):
    """**NCT-01 draws WAITING ON and STATE as two columns, and two of its five
    rows wait on something while NOT being on hold.**

    This is the finding that moved the column: it began life as `hold_reason`.

        CON-26-0121  In progress       materials
        CON-26-0126  Partly energised  inspection
        CON-26-0119  On hold           permit
    """
    with tenant_ctx(brazos):
        # CON-26-0121 — In progress, waiting on materials, NOT held.
        connection, _unit, rows = _build(dana)
        w6.transition_service(dana, rows["electric"], work_tables.SVC_IN_PROGRESS)
        w6.set_waiting_on(dana, connection.id, waiting_on="materials")
        connection.refresh_from_db()
        assert (connection.state, connection.waiting_on) == (work_tables.IN_PROGRESS, "materials")
        assert connection.held_at is None, "waiting on materials is not a hold"

        # CON-26-0126 — Partly energised, waiting on inspection, still not held.
        w6.transition_service(dana, rows["electric"], work_tables.SVC_ACTIVATED)
        w6.set_waiting_on(dana, connection.id, waiting_on="inspection")
        connection.refresh_from_db()
        assert (connection.state, connection.waiting_on) == (work_tables.PARTLY_ACTIVATED, "inspection")
        assert connection.held_at is None

        # CON-26-0119 — On hold AND waiting on a permit: the two axes together.
        w6.hold_connection(dana, connection.id, reason="permit")
        connection.refresh_from_db()
        assert (connection.state, connection.waiting_on) == (work_tables.ON_HOLD, "permit")

        # …and coming off hold does not have to stop waiting (CON-26-0121's shape).
        w6.release_connection(dana, connection.id, waiting_on="materials")
        connection.refresh_from_db()
        assert (connection.state, connection.waiting_on) == (work_tables.PARTLY_ACTIVATED, "materials")
        _assert_cache_agrees(connection)


def test_w6_waiting_and_done_are_segments_and_never_state_tokens():
    """⚠ **A CORRECTION TO A SUMMARY THIS LANE WAS HANDED**, settled from the
    drawn rows rather than from the summary.

    NCT-01's segment strip reads `All · In progress · Waiting · Partly energised
    · Done`, and that was passed to this lane as the STATE set. Not one of the
    five drawn rows reads `Waiting` or `Done` in its STATE column — they read
    Energised, On hold, In progress, Partly energised, four of B18 §5.4.3's
    seven. `Waiting` and `Done` are filters over state plus `waiting_on`.
    """
    assert "waiting" not in work_tables.CONNECTION_STATES
    assert "done" not in work_tables.CONNECTION_STATES
    assert set(work_tables.CONNECTION_STATES) == {
        work_tables.DRAFT,
        work_tables.REQUESTED,
        work_tables.IN_PROGRESS,
        work_tables.PARTLY_ACTIVATED,
        work_tables.ON_HOLD,
        work_tables.ACTIVATED,
        work_tables.CANCELLED,
    }
    # Every STATE the five drawn rows show is one of the seven.
    for drawn in (work_tables.ACTIVATED, work_tables.ON_HOLD, work_tables.IN_PROGRESS, work_tables.PARTLY_ACTIVATED):
        assert drawn in work_tables.CONNECTION_STATES
    # ⛔ And no segment rule is shipped: `CON-26-0126` is Partly energised AND
    # waiting on inspection, and nothing says which exclusive segment holds it.
    assert not hasattr(w6, "segment_for"), (
        "segment precedence is undetermined by the drawing and is REPORTED as owed — "
        "a guess here would put a build under the wrong tab on the PO's own screen"
    )


def test_w6_order_progress_reads_done_of_total(dana, brazos):
    """NCT-01's `ORDERS` column — `5 of 9`, done of total, under a progress
    underline. A cancelled order leaves BOTH halves."""
    with tenant_ctx(brazos):
        connection, _unit, _rows = _build(dana)
        orders = [
            w6.create_work_order(dana, connection.id, {"type": f"step {n}"})["id"] for n in range(5)
        ]
        assert w6.order_progress(connection) == (0, 5)
        for order_id in orders[:2]:
            work_tables.WorkOrder.objects.filter(pk=order_id).update(state=work_tables.WO_COMPLETED)
        assert w6.order_progress(connection) == (2, 5)
        work_tables.WorkOrder.objects.filter(pk=orders[4]).update(state=work_tables.WO_CANCELLED)
        # `2 of 4`, not `2 of 5` — a cancelled step is not outstanding work, and
        # counting it would leave the build reading unfinished forever.
        assert w6.order_progress(connection) == (2, 4)


def test_w6_mode_is_stamped_on_the_order_and_the_connection_reading_is_derived(dana, brazos):
    """**NCT-01's Work orders tab draws MODE per order**, so the order owns it.

    `connections.mode` is the wizard's step-1 default, COPIED at creation. The
    rejected shape was `order.mode or connection.mode`, and this test is what
    rejects it: under a fallback, editing the connection would retroactively
    change how last week's orders are described.
    """
    with tenant_ctx(brazos):
        connection, _unit, _rows = _build(dana)
        assert connection.mode == work_tables.MODE_OUR_CREW
        first = w6.create_work_order(dana, connection.id, {"type": "service drop"})["id"]
        assert work_tables.WorkOrder.objects.get(pk=first).mode == work_tables.MODE_OUR_CREW
        assert w6.connection_mode(connection) == work_tables.MODE_OUR_CREW

        work_tables.Connection.objects.filter(pk=connection.id).update(mode=work_tables.MODE_EXTERNAL)
        connection.refresh_from_db()
        assert work_tables.WorkOrder.objects.get(pk=first).mode == work_tables.MODE_OUR_CREW, (
            "an order raised under 'our crew' must not become 'external' because the "
            "connection's default was edited afterwards"
        )

        w6.create_work_order(dana, connection.id, {"type": "gas tap", "mode": work_tables.MODE_EXTERNAL})
        # *"A utility that does its own water work and contracts out gas is the
        # normal case, not the edge"* (§8.3).
        assert w6.connection_mode(connection) == "mixed"


def test_w6_the_gate_flag_is_stamped_from_its_template_and_does_not_move(dana, brazos):
    """**NCT-01 draws the gate as a 🚩 on the ORDER's name** — `WO-4902 Meter set
    · electric 🚩` — on two of five orders. The flag is declared per template and
    shows on the order it produced.

    STAMPED, not read through the FK: a tenant editing a template must not
    silently change whether work already in the field is the thing that permits
    energisation (`invoice_lines.tariff_version_id`'s reasoning).
    """
    with tenant_ctx(brazos):
        connection, _unit, _rows = _build(dana)
        service = work_tables.ConnectionService.objects.first().service
        gate = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, service=service, sequence=1, name="Meter set", is_gate=True
        )
        plain = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, service=service, sequence=2, name="Service drop", is_gate=False
        )
        flagged = w6.create_work_order(
            dana, connection.id, {"type": "Meter set", "template_id": str(gate.id)}
        )["id"]
        unflagged = w6.create_work_order(
            dana, connection.id, {"type": "Service drop", "template_id": str(plain.id)}
        )["id"]
        assert work_tables.WorkOrder.objects.get(pk=flagged).is_gate is True
        assert work_tables.WorkOrder.objects.get(pk=unflagged).is_gate is False

        work_tables.WorkOrderTemplate.objects.filter(pk=gate.id).update(is_gate=False)
        assert work_tables.WorkOrder.objects.get(pk=flagged).is_gate is True, (
            "editing the template moved the gate on an order already raised — what gated "
            "this build is what gated it on the day the order was raised"
        )
        # An ad-hoc order (NCT-02's `Add work order`) has no template and no flag.
        adhoc = w6.create_work_order(dana, connection.id, {"type": "make good"})["id"]
        row = work_tables.WorkOrder.objects.get(pk=adhoc)
        assert row.template_id is None and row.is_gate is False


def test_w6_service_progress_draws_the_nct02_blocks(dana, brazos):
    """NCT-02's side-by-side blocks:

    ELECTRIC  Energised   1 of 1 units · Aug 18
    WATER     Energised   1 of 1 units
    """
    with tenant_ctx(brazos):
        connection, _unit, rows = _build(dana)
        w6.transition_service(dana, rows["electric"], work_tables.SVC_ACTIVATED)
        blocks = {block["service"]: block for block in w6.service_progress(connection)}
        assert blocks["electric"]["state"] == work_tables.ACTIVATED
        assert (blocks["electric"]["units_energised"], blocks["electric"]["units_total"]) == (1, 1)
        assert blocks["electric"]["activated_at"] is not None
        # Water is not live yet, so its block counts 0 of its 1 unit and carries
        # no date. `0 of 1` and "no water service" are different claims and the
        # block makes the difference visible.
        assert blocks["water"]["state"] == work_tables.REQUESTED
        assert (blocks["water"]["units_energised"], blocks["water"]["units_total"]) == (0, 1)
        assert blocks["water"]["activated_at"] is None

        # …and once water follows, the pair reads exactly as NCT-02 draws it.
        w6.transition_service(dana, rows["water"], work_tables.SVC_ACTIVATED)
        drawn = {block["service"]: block for block in w6.service_progress(connection)}
        for code in ("electric", "water"):
            assert drawn[code]["state"] == work_tables.ACTIVATED
            assert (drawn[code]["units_energised"], drawn[code]["units_total"]) == (1, 1)
            assert drawn[code]["activated_at"] is not None
        connection.refresh_from_db()
        assert connection.state == work_tables.ACTIVATED, (
            "NCT-02's header badge sits above two energised services — the build's own "
            "state is read off the blocks, not stored beside them"
        )
        # ⚠ THE PROTOTYPE DEFECT THIS CANNOT REPRODUCE. NCT-02's Timeline on
        # this one-unit build reads *"Electric energised — 25 units"*, pasted
        # from CON-26-0117. The count is computed from the rows, so it is 1.
        assert blocks["electric"]["units_total"] == 1


def test_w6_a_service_across_units_can_be_partly_energised(dana, brazos):
    """`partly_energised` is absent from the STORED per-service set and present
    in the DERIVED block, and CON-26-0117's 25 units are why.

    A row is one service AT ONE UNIT and cannot be partly anything; a service
    across a build plainly can.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit_a = make_unit(dana, premises["id"], label="Unit A")
        unit_b = make_unit(dana, premises["id"], label="Unit B")
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        connection = work_tables.Connection.objects.get(pk=created["id"])
        first = w6.add_connection_service(
            dana, connection.id, service_code="electric", unit_id=unit_a["id"]
        )["id"]
        w6.add_connection_service(
            dana, connection.id, service_code="electric", unit_id=unit_b["id"]
        )
        w6.submit_connection(dana, connection.id)
        w6.transition_service(dana, first, work_tables.SVC_ACTIVATED)
        block = w6.service_progress(connection)[0]
        assert block["state"] == work_tables.PARTLY_ACTIVATED
        assert (block["units_energised"], block["units_total"]) == (1, 2)
        assert work_tables.PARTLY_ACTIVATED not in work_tables.SERVICE_STATES, (
            "the STORED per-service set must not gain the aggregate token — it is a "
            "count over rows, not a sixth thing to store"
        )


def test_w6_the_deferred_dispatch_mode_raises_its_open_question(dana, brazos):
    """⛔ *"we schedule it"* is B18 §8.3's R5 mode — OQ-249, still open."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        with pytest.raises(NotImplementedError) as caught:
            w6.create_connection(dana, {"premises_id": premises["id"], "mode": work_tables.MODE_WE_SCHEDULE})
        assert "OQ-249" in str(caught.value)


# ════════════════════════════════════════════════════════════════════════════
# 6.9 · service_characteristics — BR-MET-108
# ════════════════════════════════════════════════════════════════════════════
def test_w6_a_characteristic_is_a_row_keyed_by_unit_and_service(dana, brazos):
    """The shape BR-MET-108 signed: one row per characteristic, and the unit of
    measure in a COLUMN."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="water",
            key="meter_size",
            value="0.75",
            unit_of_measure="in",
        )
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="electric",
            key="service_size",
            value="200",
            unit_of_measure="A",
        )
        rows = work_tables.ServiceCharacteristic.objects.filter(unit_id=unit["id"])
        assert rows.count() == 2, "a row per characteristic — not a column per service"
        # The UoM is DATA. Two characteristics, two different units, and neither
        # unit is encoded in a key name (hard rule 3).
        assert {row.unit_of_measure for row in rows} == {"in", "A"}


def test_w6_an_absent_characteristic_bills_zero_and_is_stamped(dana, brazos):
    """⚠ **THIS TEST WAS THE OPPOSITE ASSERTION UNTIL 2026-08-25, AND THE PO
    REVERSED IT — verbatim, *"Bill it as zero"*.**

    It used to be `test_w6_an_absent_characteristic_refuses_and_never_prices_zero`
    and it asserted `BIZ_COMPLETENESS`, implementing BR-MET-108's original
    closing sentence. That sentence, and the worked cost of dropping it — a
    25-unit building, unit 12 blank, a $0.00 trash line that recurs every cycle
    with nothing going red — were put to the PO in plain English. The PO chose
    zero. BR-MET-108 is AI-authored and HUMAN-REVIEW-PENDING, so this IS its
    human review arriving and ruling differently.

    **What is asserted instead is the half the ruling did NOT give away:** the
    zero is STAMPED. `absent`, `priced_at_zero` and a `reason` come back on the
    reading, so a bill line can carry why it is zero and a utility can find it
    afterwards. Billing zero is the ruling; billing zero *silently* is not.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])

        assert w6.characteristic(unit["id"], "water", "meter_size") is None

        reading = w6.characteristic_for_pricing(unit["id"], "water", "meter_size")
        # THE RULING: it does not raise, and the figure is zero.
        assert reading.value == Decimal("0")
        # THE HALF THAT SURVIVED: the zero explains itself.
        assert reading.absent is True
        assert reading.priced_at_zero is True
        assert reading.reason == w6.PRICED_AT_ZERO_ABSENT_CHARACTERISTIC
        assert reading.br_ref == "BR-MET-108"
        # The absence is still NAMED, so a clerk can be told what to record.
        assert reading.service == "water"
        assert reading.key == "meter_size"
        assert reading.unit_id == str(unit["id"])
        # And the stamp is a dict a bill line can store verbatim.
        assert w6.PRICED_AT_ZERO_ABSENT_CHARACTERISTIC in reading.as_stamp().values()

        # …and once it is recorded, the same call answers with the real number
        # and stamps NOTHING — a real value must not look like a priced zero.
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="water",
            key="meter_size",
            value="0.75",
            unit_of_measure="in",
        )
        recorded = w6.characteristic_for_pricing(unit["id"], "water", "meter_size")
        assert recorded.value == Decimal("0.75")
        assert recorded.unit_of_measure == "in"
        assert recorded.absent is False
        assert recorded.priced_at_zero is False
        assert recorded.reason is None


def test_w6_a_recorded_zero_is_not_the_same_as_an_absent_one(dana, brazos):
    """**The failure mode the ruling creates, pinned so it cannot go unnoticed.**

    BR-MET-108 chose rows over columns precisely because *"a NULL column cannot
    say which kind of nothing it is"*. Pricing an absence at zero brings that
    ambiguity back into the FIGURE — two units both bill $0.00. What keeps them
    distinguishable is the stamp, and nothing else, so it is asserted directly:
    a unit that genuinely measures zero and a unit nobody measured produce the
    same number and DIFFERENT records.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        measured = make_unit(dana, premises["id"], label="Unit 12A")
        never_measured = make_unit(dana, premises["id"], label="Unit 12B")
        w6.set_characteristic(
            dana,
            measured["id"],
            service_code="electric",
            key="connected_load",
            value="0",
            unit_of_measure="kW",
        )

        real_zero = w6.characteristic_for_pricing(measured["id"], "electric", "connected_load")
        no_number = w6.characteristic_for_pricing(
            never_measured["id"], "electric", "connected_load"
        )

        assert real_zero.value == no_number.value == Decimal("0"), "the same figure"
        assert real_zero.absent is False and no_number.absent is True
        assert real_zero.priced_at_zero is False and no_number.priced_at_zero is True
        assert real_zero.unit_of_measure == "kW" and no_number.unit_of_measure is None


def test_w6_every_unit_priced_at_zero_can_be_listed(dana, brazos):
    """**The surfacing half of the ruling, and the reason it is not concealment.**

    The PO ruled *"bill it as zero"*, not *"lose the money and never find out"*.
    A utility must be able to run one query before a bill run and see exactly
    which units will read $0.00 for want of a number.

    The population is the CALLER'S — this module must not decide which units
    take a service (BR-MET-108: a missing row means *no characteristic
    recorded*, never *does not take this service*), so `unit_ids` has no
    default.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        units = [make_unit(dana, premises["id"], label=f"Unit {n}") for n in range(1, 4)]
        w6.set_characteristic(
            dana,
            units[0]["id"],
            service_code="electric",
            key="connected_load",
            value="3",
            unit_of_measure="kW",
        )

        gaps = w6.units_priced_at_zero("electric", "connected_load", [u["id"] for u in units])
        assert {row["unit_id"] for row in gaps} == {str(units[1]["id"]), str(units[2]["id"])}
        assert all(row["reason"] == w6.PRICED_AT_ZERO_ABSENT_CHARACTERISTIC for row in gaps)
        assert all(row["br_ref"] == "BR-MET-108" for row in gaps)
        # A unit outside the population is not this query's business.
        assert w6.units_priced_at_zero("electric", "connected_load", [units[0]["id"]]) == []
        # And it does not answer for a population it was not given.
        with pytest.raises(TypeError):
            w6.units_priced_at_zero("electric", "connected_load")


def test_w6_a_value_that_is_not_a_number_refuses_rather_than_reading_zero(dana, brazos):
    """*"100/20 Mbps"* is a speed tier and is not a number.

    `value` is TEXT so the tier is not lost at write; a caller that needs
    arithmetic asks, and is refused BY NAME rather than handed a silent zero.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="electric",
            key="speed_tier",
            value="100/20 Mbps",
            unit_of_measure="Mbps down/up",
        )
        row = w6.characteristic(unit["id"], "electric", "speed_tier")
        assert row is not None
        assert row.value == "100/20 Mbps", "the tier survives the round trip verbatim"
        # And the PRICING seam hands back None rather than a coerced guess — a
        # speed tier is not a number, and `absent` stays False because the
        # characteristic IS recorded. Not-a-number and not-recorded are
        # different facts and must not collapse into one zero.
        reading = w6.characteristic_for_pricing(unit["id"], "electric", "speed_tier")
        assert reading.value is None
        assert reading.absent is False and reading.priced_at_zero is False
        with pytest.raises(errors.BizError) as caught:
            row.decimal_value()
        assert caught.value.code == errors.BIZ_COMPLETENESS
        assert caught.value.br_ref == "BR-MET-108"


def test_w6_a_characteristic_without_its_unit_of_measure_is_refused(dana, brazos):
    """Hard rule 3. `2450` is square feet, square metres or acres, and a number
    whose unit is implied by an identifier is a number nothing can validate."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        with pytest.raises(errors.ValidationError) as caught:
            w6.set_characteristic(
                dana,
                unit["id"],
                service_code="water",
                key="impervious_area",
                value="2450",
                unit_of_measure="  ",
            )
        assert [error["field"] for error in caught.value.field_errors] == ["unit_of_measure"]
        assert not work_tables.ServiceCharacteristic.objects.filter(unit_id=unit["id"]).exists()


def test_w6_which_characteristic_keys_a_service_has_is_not_answered_here():
    """**The refusal to decide, asserted so a later lane cannot quietly decide.**

    ⚠ This used to raise `CharacteristicRequirementUnsigned` in prose, because
    BR-MET-108 left the gap and **no open question covered it** — and minting an
    OQ-### from inside code is exactly what G8 clause B exists to catch.
    **OQ-370 was registered on 2026-08-25**, so the prime directive's ordinary
    form applies and the stub cites it.

    The PO's *"bill it as zero"* ruling dissolved half of what this function was
    for: nothing is *required* before a bill can be produced any more. What
    OQ-370 still asks is which keys and units of measure a SETTINGS FORM must
    offer, because a form cannot ask for "a characteristic". The PO gave exactly
    one key set — trash stores `count = 3` and `size = 96 gal` — and one example
    is not a catalogue.
    """
    with pytest.raises(NotImplementedError) as caught:
        w6.required_characteristic_keys("trash")
    assert str(caught.value) == "OQ-370"
    # And no key list leaked in anywhere while the question was open.
    source = pathlib.Path(w6.__file__).read_text(encoding="utf-8")
    for invented in ("container_count\":", "impervious_area\":", "speed_tier\":"):
        assert invented not in source, "a key map would BE a pricing rule, and none is signed"


# ════════════════════════════════════════════════════════════════════════════
# 6.1 · THE MIGRATION'S POLICIES — read from the module, not from a grep
# ════════════════════════════════════════════════════════════════════════════
def _migration_text():
    from pathlib import Path

    return Path(__file__).resolve().parents[1].joinpath(MIGRATION).read_text(encoding="utf-8")


def _policy_sql():
    """The SQL the migration will actually execute, not a grep of the file.

    ⚠ The first version of this helper read the FILE TEXT and searched for
    `ALTER TABLE connections ENABLE ROW LEVEL SECURITY;`. It went red on a
    migration whose policies are entirely correct, because the file builds them
    from an f-string over a table tuple — so the literal never appears in the
    source. A check that reads the SOURCE of generated SQL can pass on a file
    that generates nothing; this one asks the module for the string it will hand
    to Postgres.
    """
    from importlib import import_module

    return import_module("apps.metering.migrations.0026_cr030_w6_connections").POLICIES


def test_w6_the_app_registry_is_told_this_module_exists():
    """⛔ **THIS TEST IS RED UNTIL ONE LINE LANDS IN A FILE THIS LANE DOES NOT
    OWN, AND THAT IS DELIBERATE.**

    Django's app registry imports `<app>.models` and nothing else. These five
    model classes live in `apps/metering/connections.py`, so they register only
    when something on the startup path imports that module. Nothing does. The
    consequence is not cosmetic and it is not theoretical — MEASURED on this
    tree with `python3 -m manage makemigrations --check --dry-run`:

        Migrations for 'metering':
          apps/metering/migrations/0027_remove_connectionservice_connection_and_more.py
            - Delete model Connection
            - Delete model ConnectionService
            - Delete model ServiceCharacteristic
            - Delete model WorkOrder
            - Delete model WorkOrderTemplate

    Migration state holds five tables the registry lacks, so the autodetector
    answers with a DeleteModel and the project sits in permanent drift with CI
    proposing to drop the tables.

    **THE FIX IS ONE LINE, AND THE PRECEDENT IS IN THIS REPO** —
    `apps/rating/models.py:1628` does exactly this for `apps/rating/discounts.py`,
    with the reason written beside it (*"Imported for its SIDE EFFECT — importing
    the module is what registers its models"*). At the foot of
    `apps/metering/models.py`:

        from apps.metering import connections  # noqa: E402,F401  (registers five models)

    **WHY NOT `managed = False` + hand-written per-vendor DDL**, which is the
    self-contained alternative and which a sibling lane took for `transfers`:
    it takes five tables out of Django's model state permanently, so every later
    column on them is hand-written DDL in two dialects forever; it needs a
    `RunPython` in the migration, which is the DEF-639 hazard class this
    migration is otherwise free of (and which `test_w6_the_migration_leaves_
    tenant_context_alone` asserts against); and it trades a LOUD one-line gap
    for a SILENT permanent one. A test that goes red until a known one-line
    change lands is the better trade — it cannot be forgotten, and it turns
    green the moment the line is added.

    **This test cannot be written as `apps.get_model(...)`**: this test module
    imports `connections`, which registers the models, so a registry check would
    pass while the startup path stays empty — the DEF-672 failure exactly (a
    check whose output cannot distinguish pass from fail). So it reads the
    SOURCE of the files on the startup path.

    ⚠ **AMENDED 2026-10-21 (CR-187-BRC10 T-43): THE CLASSES MOVED, SO THE
    STARTUP FILE THIS READS MOVED WITH THEM.** The six tables are now declared
    in `apps/work/connection_models.py` and registered by the import at the
    foot of `apps/work/models.py`; `apps/metering/models.py` no longer carries
    the line above. The reasoning stands unchanged — the check still reads the
    SOURCE of the startup file, for the DEF-672 reason in the paragraph above.
    """
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    startup = "\n".join(
        (backend / name).read_text(encoding="utf-8")
        for name in ("apps/work/models.py", "apps/work/apps.py")
    )
    assert "from apps.work.connection_models import" in startup, (
        "apps/work/connection_models.py is never imported on the startup path, so the six "
        "Work tables (connections, connection_services, work_orders, work_order_templates, "
        "service_characteristics, connection_todos) are invisible to the app registry and "
        "`makemigrations --check` proposes DELETING them. Import them at the foot of "
        "apps/work/models.py, as evidence_models and rules_models already are."
    )


def test_w6_the_locked_path_files_declare_themselves_pending():
    """G7 / the PO ruling of 2026-08-09. Migration ordering and RLS policies are
    🔒 paths: AI may author them, and the file must SAY it is unratified so the
    review ledger and the source cannot quietly disagree."""
    from pathlib import Path

    module = Path(__file__).resolve().parents[1] / "apps/metering/connections.py"
    for text in (_migration_text(), module.read_text(encoding="utf-8")):
        assert "HUMAN-REVIEW-PENDING" in text
        assert "status: VERIFIED-UNRATIFIED" in text


def test_w6_every_new_table_gets_enable_force_and_a_policy():
    """Hard rule 1, and B18 §6.3's own *"no exceptions"*, checked as text.

    Read from the migration rather than from the module's docstring, because a
    comment claiming a guarantee is not the guarantee (hard-won law 1).
    """
    text = _policy_sql()
    for table in W6_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in text
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in text, (
            f"{table}: FORCE is what makes the policy apply to the table OWNER too — "
            "without it the application's own role reads every tenant"
        )
        assert f"CREATE POLICY {table}_tenant_isolation ON {table}" in text


def test_w6_the_policy_predicate_is_the_nullif_form():
    """DEF-639 / OQ-354. The bare cast RAISES on an unset marker and made a
    fresh database un-buildable; G41 ratchets the repo towards this form."""
    text = _policy_sql()
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in text
    assert "current_setting('app.tenant_id')::uuid" not in text, (
        "the bare cast is DEF-639: with app.tenant_id unset it raises inside FK "
        "validation and a fresh `migrate` dies"
    )
    # USING and WITH CHECK, both — a policy with only USING lets a row be
    # WRITTEN for another tenant.
    assert text.count("USING      (") >= 1 and text.count("WITH CHECK (") >= 1


def test_w6_the_migration_leaves_tenant_context_alone():
    """OQ-354/DEF-639's other half. This migration has no seed step at all, so
    there is nothing to leave `''` in — asserted rather than assumed, because
    the day somebody adds a data step here is the day it matters.

    ⚠ Read from the OPERATIONS LIST, not from the file text. The first version
    of this check greped the source for `RunPython` and went red on the
    DOCSTRING SENTENCE that says there is no RunPython — a check that reads
    prose cannot tell a rule from a description of the rule.
    """
    from importlib import import_module

    operations = import_module(
        "apps.metering.migrations.0026_cr030_w6_connections"
    ).Migration.operations
    assert not [op for op in operations if isinstance(op, migrations.RunPython)]
    assert "set_config" not in _policy_sql()


# ════════════════════════════════════════════════════════════════════════════
# 6.1 · TENANT ISOLATION — all five tables
# ════════════════════════════════════════════════════════════════════════════
def test_w6_the_app_layer_never_crosses_a_tenant(dana, erin, brazos, lonestar):
    """The queryset half. Every read in `connections.py` filters on the tenant
    from context; a foreign id is a 404 and never a 403 (HR-1 — existence must
    not leak)."""
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="water",
            key="meter_size",
            value="0.75",
            unit_of_measure="in",
        )
        w6.create_work_order(dana, connection.id, {"type": "meter set", "service": "water"})

    with tenant_ctx(lonestar):
        assert work_tables.Connection.objects.filter(tenant_id=lonestar.id).count() == 0
        # The other tenant's connection is ABSENT, not forbidden.
        with pytest.raises(errors.NotFoundError):
            w6.add_connection_service(erin, connection.id, service_code="water")
        with pytest.raises(errors.NotFoundError):
            w6.create_work_order(erin, connection.id, {"type": "meter set"})
        with pytest.raises(errors.NotFoundError):
            w6.transition_service(erin, rows["water"], work_tables.SVC_IN_PROGRESS)
        # …and a characteristic recorded by Brazos is simply not there.
        assert w6.characteristic(unit["id"], "water", "meter_size") is None
        # ⚠ AND UNDER THE PO'S 2026-08-25 RULING THIS NOW DEGRADES QUIETLY.
        # Before it, a foreign tenant's characteristic REFUSED loudly. Now an
        # absence — including absent-because-another-tenant-owns-it — prices at
        # zero like any other. The stamp is the only thing that keeps it
        # findable, which is why it is asserted here and not just in 6.9.
        leaked = w6.characteristic_for_pricing(unit["id"], "water", "meter_size")
        assert leaked.absent is True and leaked.priced_at_zero is True


@pytest.mark.isolation
@requires_postgres
def test_w6_rls_scopes_all_five_tables(rls, dana, erin, brazos, lonestar):  # noqa: F811
    """The DATABASE half — the app-layer filter is deliberately not in the path.

    Proved under a NOLOGIN NOSUPERUSER NOBYPASSRLS probe role, because a role
    that bypasses RLS proves nothing (`assert_is_a_real_proof`).
    """
    with tenant_ctx(brazos):
        connection, unit, _rows = _build(dana)
        w6.create_work_order(dana, connection.id, {"type": "meter set", "service": "water"})
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="water",
            key="meter_size",
            value="0.75",
            unit_of_measure="in",
        )
        service = work_tables.ConnectionService.objects.first().service
        work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, service=service, sequence=1, name="meter set", is_gate=True
        )
    with tenant_ctx(lonestar):
        premises = make_premises(erin, services_available=["water"])
        w6.create_connection(erin, {"premises_id": premises["id"]})

    for table in W6_TABLES:
        if table in ("work_orders", "work_order_templates", "service_characteristics"):
            # Lone Star has none of these, so the intruder half is proved by the
            # OWNER's rows being invisible rather than by a second row set.
            assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
        else:
            assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


# ════════════════════════════════════════════════════════════════════════════
# CR-032 · "instead of energise can we use activated" (PO 2026-08-25)
# ════════════════════════════════════════════════════════════════════════════
def test_w6_no_shipped_token_says_energised():
    """**The guard CR-032 §6 asks for, and it is about a STORED word.**

    *Energise* is electric jargon. The platform seeds TEN services and only
    Electric, Solar and Battery are energised in any literal sense — water is
    turned on, gas is lit, broadband is provisioned, trash is scheduled, sewer is
    connected. One token has to cover all ten.

    ⚠ **This asserts the TOKENS, not the prose.** Every docstring in
    `connections.py` still says *Energised* where it quotes a drawn screen, and
    that is deliberate: rewriting a quotation to match a later ruling destroys
    the evidence that the ruling changed something. What must not survive is a
    value the database stores or a name the code compares.

    ⚠ **THIS TEST WAS REWRITTEN ON THE DAY IT WAS WRITTEN — DEF-681.** The first
    version asserted the state TOKENS and two column names it happened to know
    about, and **it went green over a column the rename had missed**
    (`connections.target_energisation`, the NOUN form, which matched none of the
    spellings the rename regex used). A check that can only find what its author
    already remembered is the failure hard-won law 7 exists to catch.

    So it now walks **every field of every model in the module and every
    module-level constant**, and fails on any `energis` substring in a NAME. It
    cannot be defeated by a spelling nobody thought of.
    """
    import inspect

    # (a) the stored state tokens
    for token in work_tables.CONNECTION_STATES + work_tables.SERVICE_STATES:
        assert "energis" not in token, f"{token} is the pre-CR-032 spelling"
    assert work_tables.ACTIVATED == "activated"
    assert work_tables.PARTLY_ACTIVATED == "partly_activated"
    assert work_tables.SVC_ACTIVATED == "activated"
    for module in (w6, work_tables):
        assert not hasattr(module, "ENERGISED"), "the old name must not remain as an alias"
        assert not hasattr(module, "SVC_ENERGISED")

    # (b) EVERY column of EVERY model here — this is the clause DEF-681 added.
    # T-43 (2026-10-21): the six models now live in `apps.work.connection_models`
    # and register under `work`; the sweep follows them there.
    models_here = [
        value
        for _, value in inspect.getmembers(work_tables, inspect.isclass)
        if hasattr(value, "_meta") and getattr(value._meta, "app_label", None) == "work"
    ]
    assert models_here, "the sweep found no models — it would pass vacuously"
    offenders = [
        f"{model.__name__}.{field.name}"
        for model in models_here
        for field in model._meta.get_fields()
        if "energis" in field.name.lower()
    ]
    assert offenders == [], f"CR-032 missed these columns: {offenders}"
    assert hasattr(work_tables.Connection, "activated_at") and hasattr(work_tables.Connection, "target_activation")
    assert hasattr(work_tables.ConnectionService, "activated_at")

    # (c) every module-level CONSTANT name and string value
    named = [
        name
        for module in (w6, work_tables)
        for name, value in vars(module).items()
        if name.isupper() and "energis" in name.lower()
    ]
    assert named == [], f"constants still carry the old spelling: {named}"


def test_w6_the_rename_is_a_migration_not_a_find_and_replace():
    """**The stored value is rewritten, and the rollback is real.**

    CR-032 §5 names the one risk: the word lives in `connections.state`, so a
    source-only swap would leave a fresh database writing `activated` while an
    existing one still held `energised`, with every state comparison quietly
    false. Migration `0027` carries a `RunPython` both ways.
    """
    from pathlib import Path

    text = Path(
        "apps/metering/migrations/0027_cr030_w6_rulings.py"
    ).read_text(encoding="utf-8")
    assert "RunPython(forwards_states, backwards_states)" in text
    assert '("energised", "activated")' in text
    assert '("partly_energised", "partly_activated")' in text
    # It must use the HISTORICAL models — a migration importing today's module
    # reads today's code and breaks the moment the module changes again.
    assert 'apps.get_model("metering", "Connection")' in text
    assert "from apps.metering" not in text


# ════════════════════════════════════════════════════════════════════════════
# BR-MET-110 · the field confirms, a HUMAN accepts, then service goes live
# ════════════════════════════════════════════════════════════════════════════
def test_w6_a_completed_order_is_not_an_accepted_one(dana, brazos):
    """**The middle step is the rule, and the NULL is the review queue.**

    PO 2026-08-25: *"Work order will send the data and confirm from field;
    utility staff will review these work order, accept them and use data from
    them to activate these services or confirm the installation is completed."*

    `submit_field_result` records what came back and marks the order completed —
    which under this rule means *"the crew says it is done"*, NOT *"a person
    agrees it is done"*. `accepted_by` stays NULL, and that NULL is the only
    thing in the schema that says an order is waiting for a human.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]

        result = field_close(
            dana, order_id, field_data={"meter_serial": "W-88214"}, outcome=work_tables.OUTCOME_PASSED
        )
        assert result["awaiting_review"] is True
        assert result["br_ref"] == "BR-MET-110"

        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert order.state == work_tables.WO_COMPLETED, "the crew reported it done"
        assert order.completed_at is not None
        assert order.field_data == {"meter_serial": "W-88214"}, "what the field sent survives"
        # THE WHOLE POINT: done is not accepted.
        assert order.accepted_by_id is None
        assert order.accepted_at is None


def test_w6_accepting_a_field_result_is_recorded_against_a_person(dana, brazos):
    """The acceptance is the human act between a field report and a customer's
    supply going live, so hard rule 7's discipline applies: somebody decided,
    and the record names them."""
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]
        field_close(dana, order_id, field_data={"meter_serial": "W-88214"})

        accepted = w6.accept_field_result(dana, order_id)
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert accepted["br_ref"] == "BR-MET-115"
        assert order.accepted_by_id == dana.id, "the reviewer is named, not implied"
        assert order.accepted_at is not None
        assert accepted["accepted_at"] == order.accepted_at.isoformat()

        # Accepting twice is refused rather than silently re-stamped — the
        # acceptance is an auditable moment and there is only one of them.
        with pytest.raises(errors.BizError) as caught:
            w6.accept_field_result(dana, order_id)
        assert caught.value.code == errors.BIZ_IDEMPOTENT
        assert caught.value.br_ref == "BR-MET-110"


def test_w6_an_unfinished_order_cannot_be_accepted(dana, brazos):
    """A person cannot accept work the field has not reported. The three steps
    are ordered and the order is the rule."""
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]
        with pytest.raises(errors.BizError) as caught:
            w6.accept_field_result(dana, order_id)
        assert caught.value.code == errors.BIZ_STATE
        assert caught.value.br_ref == "BR-MET-110"
        assert caught.value.params["state"] == work_tables.WO_PLANNED


# ════════════════════════════════════════════════════════════════════════════
# BR-MET-115 · the completion IS the send — and which job is OQ-372
# ════════════════════════════════════════════════════════════════════════════
def test_w6_the_acceptance_press_is_the_send(dana, brazos):
    """⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-25, AND THE CHANGE IS
    `OQ-372` CLOSING.**

    It used to pin `communication_due: True` with `piece: None` and
    `blocked_by: "OQ-372"`, because which of a build's seven orders should send
    was unruled, and a letter three weeks early cannot be amended. Asked to rank
    the gate order, the last order, or a per-template choice, the PO chose none:
    **"When Utility user mark it as complete using button on screen"**.

    **So the system never ranks the orders — a person presses, and that press is
    the send.** And the press already existed: `BR-MET-110`'s own quote is
    *"accept them and … confirm the installation is completed"*, so accepting IS
    marking complete. One act, one button, no new action invented.

    ⚠ The footgun is the utility's, deliberately: accepting order three of seven
    sends for that order's service. The PO saw the figure before ruling.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]
        field_close(dana, order_id)

        accepted = w6.accept_field_result(dana, order_id)
        assert accepted["br_ref"] == "BR-MET-115"
        assert "communication_blocked_by" not in accepted
        assert accepted["communication"]["already_sent"] is False
        # ⚠ AND IT NEVER CLAIMS A NOTIFICATION IT DID NOT QUEUE. With
        # `notifications.queue_document` unwired the seam returns None, and the
        # result says so rather than reporting a send that did not happen.
        assert accepted["communication"]["queued"] in (True, False)
        if accepted["communication"]["queued"] is False:
            assert "unavailable" in accepted["communication"]


def test_w6_a_letter_is_never_sent_twice_for_one_order(dana, brazos):
    """**A letter cannot be unsent, so a second press must not produce one.**

    This is the guard that makes the PO's ruling safe to live with: the trigger
    is a human pressing a button, humans press buttons twice, and the cost of
    the second press is a customer receiving the same notice again.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]
        field_close(dana, order_id)
        accepted = w6.accept_field_result(dana, order_id)

        # ⚠ FIRST, THE HALF THIS ENVIRONMENT ACTUALLY EXERCISES, and it is the
        # more important one. The platform queue REFUSES `connection` as a
        # source kind (OQ-376), so nothing was sent — and because nothing was
        # sent, nothing is stamped and the call does not claim otherwise.
        # A "sent once" marker written on a send that never happened would
        # silently suppress the real letter forever.
        assert accepted["communication"]["queued"] is False
        assert accepted["communication"]["already_sent"] is False
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert not (order.field_data or {}).get(w6.SEND_STAMP), "no stamp without a send"

        # SECOND, the guard itself, exercised where the queue cannot reach: with
        # the stamp present, a second press short-circuits. A letter cannot be
        # unsent, and humans press buttons twice.
        order.field_data = dict(order.field_data or {}, **{w6.SEND_STAMP: True})
        order.save(update_fields=["field_data"])
        again = w6.dispatch_communication(dana, order_id)
        assert again["queued"] is False
        assert again["already_sent"] is True


def test_w6_an_unaccepted_order_cannot_tell_the_customer_anything(dana, brazos):
    """The three steps stay ordered. A crew's report is not a person's decision,
    and only the decision may reach a customer (BR-MET-110)."""
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        order_id = w6.create_work_order(
            dana, connection.id, {"type": "meter set", "service": "water"}
        )["id"]
        field_close(dana, order_id)

        with pytest.raises(errors.BizError) as caught:
            w6.dispatch_communication(dana, order_id)
        assert caught.value.code == errors.BIZ_STATE
        assert caught.value.br_ref == "BR-MET-115"


def test_w6_nothing_sends_at_connection_creation(dana, brazos):
    """**The half of the ruling that REMOVES something**, asserted so it cannot
    quietly come back.

    `NCT-03.8` draws two pieces with an `On creation` trigger. The PO removed it:
    a connection record being created is an INTERNAL event, and for a 26-unit
    build the customer is a developer who already knows they applied. The screen
    is now stale (DEF-679) and the rule wins over the drawing.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        assert "communication_due" not in created, "creation must not queue a send"
        assert "communication" not in str(created).lower()
        source = pathlib.Path(w6.__file__).read_text(encoding="utf-8")
        body = source[source.index("def create_connection"):source.index("def add_connection_service")]
        assert "communication" not in body.lower(), "no send may be wired to creation"


# ════════════════════════════════════════════════════════════════════════════
# BR-MET-114 · Outstanding work is MARKED BY A HUMAN, never derived
# ════════════════════════════════════════════════════════════════════════════
def test_w6_a_person_marks_outstanding_work_and_it_never_blocks(dana, brazos):
    """**PO 2026-08-25: *"human will mark everything to start with"*.**

    The drawn list's third item is the one that decided this: *"Sewer on common
    area — Left off, **because** common area has no water service"*. That is a
    decision and a reason. No derivation can reconstruct a reason, and a
    derivation would re-raise it forever because the sewer genuinely is absent
    and always will be.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        marked = w6.mark_outstanding(
            dana,
            connection.id,
            title="Sewer on common area",
            detail="Left off, because common area has no water service",
        )
        assert marked["blocks_creation"] is False, "the wizard's own sentence"

        row = work_tables.ConnectionTodo.objects.get(pk=marked["id"])
        assert row.source == work_tables.ConnectionTodo.SOURCE_HUMAN
        assert row.marked_by_id == dana.id, "an unattributed reason is half a reason"
        assert row.marked_at is not None
        # The REASON survives verbatim — it is the thing the ruling protects.
        assert row.detail == "Left off, because common area has no water service"

        open_items = w6.outstanding_work(connection.id)
        assert [item["title"] for item in open_items] == ["Sewer on common area"]
        assert all(item["blocks_creation"] is False for item in open_items)


def test_w6_only_a_person_can_close_an_outstanding_item(dana, brazos):
    """**The half of "to start with" that is NOT open.**

    The PO left room for the system to SUGGEST items later. It did not leave room
    for the system to CLOSE one — that is the reason half of the drawn item 3
    disappearing again, which is the failure this rule was chosen to avoid.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        marked = w6.mark_outstanding(dana, connection.id, title="Meter numbers")

        with pytest.raises(errors.BizError) as caught:
            w6.close_outstanding(None, marked["id"])
        assert caught.value.code == errors.BIZ_APPROVAL
        assert caught.value.br_ref == "BR-MET-114"
        assert work_tables.ConnectionTodo.objects.get(pk=marked["id"]).closed_at is None

        closed = w6.close_outstanding(dana, marked["id"])
        assert closed["already_closed"] is False
        row = work_tables.ConnectionTodo.objects.get(pk=marked["id"])
        assert row.closed_by_id == dana.id and row.closed_at is not None
        assert w6.outstanding_work(connection.id) == [], "a closed item leaves the list"
        # Closing twice is idempotent, not an error — a second click is not a bug.
        assert w6.close_outstanding(dana, marked["id"])["already_closed"] is True


def test_w6_the_todo_model_cannot_say_a_thing_blocks_creation(dana, brazos):
    """There is deliberately no `blocks_creation` column. The screen says none of
    these block creating the connection, and a column that could say otherwise
    would invite a later lane to set it."""
    names = {field.name for field in work_tables.ConnectionTodo._meta.get_fields()}
    for forbidden in ("blocks_creation", "blocking", "is_blocker", "required"):
        assert forbidden not in names, f"{forbidden} would let a lane reverse the ruling"


# ════════════════════════════════════════════════════════════════════════════
# BR-MET-113 · the owner gets an account number, and everything is tagged to it
# ════════════════════════════════════════════════════════════════════════════
def _plan_for(tenant, service_code="water", name="Common Standard"):
    """A published plan on a service, so a unit can be activated (BR-MET-040)."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _common_area(actor, tenant, premises, *, label="Common area", service_code="water"):
    """A common-area unit WITH A PLAN — and the plan is the point.

    ⚠ **BR-MET-116 MEETS BR-MET-040, AND THE ORDER OF STEP 9's COMMIT FALLS OUT
    OF IT.** `create_master_account` creates the account **ACTIVE** (BR-CUS-068
    made that deliberate: an unattached master is the half-built state that
    ruling closed), and activating an account on a unit with no rate plan is
    refused by `BR-MET-040` — correctly, because an active account on an
    unpriced unit is an unbillable bill waiting to happen.

    **So the owner's master account CANNOT be created before the common area has
    a plan.** The wizard's step-9 manifest lists `Plan assignments 26` and
    `Accounts 1`; this says the plan assignments must be written FIRST. That is a
    real ordering constraint on task 6.10's orchestrator, discovered by building
    it rather than by reading the screen, and it is recorded on BR-MET-116.
    """
    from apps.metering import services as metering_services

    unit = make_unit(actor, premises["id"], label=label)
    row = w6.metering_models.Unit.objects.get(pk=unit["id"])
    row.is_common_area = True
    row.save(update_fields=["is_common_area"])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan_for(tenant, service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _an_account(actor, unit, *, name="Ridge Property LLC"):
    """An account on a unit — the thing BR-MET-113 tags charges to.

    ⚠ **Deliberately left at BR-CUS-018's default `pending_activation`, not
    `active`.** An owner's build account is not occupying anything: nobody lives
    at the address, the units have no plans yet, and `_make_occupying` refuses an
    activation on a unit with no rate plan (BR-MET-040) — correctly, because an
    active account on an unpriced unit is an unbillable bill waiting to happen.
    A draft account is exactly what a build has, which is one more sign the
    ruling's shape is right.
    """
    from apps.customers import services as customers_services

    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-08-01",
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def test_w6_connection_charges_are_tagged_to_an_account_number(dana, brazos):
    """**PO 2026-08-25, closing OQ-367: *"You will have to assign account number
    to owner and tag everything to account number"*.**

    Step 7 offers three debtors for the **$14,435.00** quote and only one names a
    party that exists at confirm. The ruling removes the difficulty rather than
    choosing between shapes — the owner gets an ACCOUNT, and the charge is an
    ordinary account-shaped charge from that moment.

    **That is why it matters more than it looks.** A charge floating on a
    `connections` row would have needed a second money path: a payable that is
    not an invoice, settled by a payment referencing no account. B4's frozen
    math is account-shaped and the ledger posts against accounts, so every rule
    saying *"the account"* would have grown a silent exception.
    """
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        account = _an_account(dana, unit)

        assert connection.owner_account_id is None, "a draft build has no payer yet"

        tagged = w6.tag_charges_to_account(dana, connection.id, account["id"])
        assert tagged["owner_account_id"] == str(account["id"])
        assert tagged["account_no"] == account["account_no"]
        assert tagged["br_ref"] == "BR-MET-113"

        connection.refresh_from_db()
        assert str(connection.owner_account_id) == str(account["id"])


def test_w6_a_tagged_payer_cannot_be_quietly_repointed(dana, brazos):
    """A quote that moved from one account to another after being stated is a
    debt that changed debtor with nothing recording the move — the hazard hard
    rule 4 exists for. A correction is a NEW charge on the right account."""
    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        first = _an_account(dana, unit, name="Ridge Property LLC")
        w6.tag_charges_to_account(dana, connection.id, first["id"])

        premises_two = make_premises(dana)
        other_unit = make_unit(dana, premises_two["id"])
        second = _an_account(dana, other_unit, name="Someone Else")

        with pytest.raises(errors.BizError) as caught:
            w6.tag_charges_to_account(dana, connection.id, second["id"])
        assert caught.value.code == errors.BIZ_IMMUTABLE
        assert caught.value.br_ref == "BR-MET-113"

        connection.refresh_from_db()
        assert str(connection.owner_account_id) == str(first["id"]), "the debtor did not move"


def test_w6_a_build_with_no_common_area_still_gets_its_owner_a_master_account(dana, brazos):
    """⛔ **PO RULING 2026-09-21 — *"common area is option"*. THIS CASE IS
    REVERSED, AND IT USED TO BE NAMED `…_gets_no_master_account`.**

    **What it asserted, and why it was right at the time.** `BR-MET-116` scoped
    the build account to MULTI-UNIT developments, so a house or a duplex was
    refused by name with `connection_no_common_area_for_master` — *"the refusal
    is the boundary, not a gap"*.

    **What the PO measured.** Eight builds were raised in a browser and eight
    were refused at the final press, by a PINCER: a build WITH a common area was
    refused because the area had no rate plan, and a build WITHOUT one was
    refused **here**, for the opposite reason. Both sides are now open.

    ⚠ **WHERE IT ANCHORS IS THE QUESTION THIS CASE ANSWERS, AND THE ANSWER IS
    *THE PREMISES*.** Nothing new was built to make that true:
    `BR-CUS-1010` moved the anchor to the address on 2026-09-01, so
    `accounts.unit_id` is NULL and `accounts.premises_id` is set — on a build
    with common areas and on a build without, identically. The common areas were
    never the anchor; they were the COVERAGE, and with none the account covers
    nothing and bills nothing (`CR-056` W4's *no lines, no document*).

    ⚠ **THE TRIPWIRES THE OLD CASE CARRIED ARE KEPT**, because they guard a
    different fact that did not move: `unit` is nullable and a `regular` account
    must still name one (`ck_accounts_regular_has_unit`), which is the direction
    where a missing unit means a bill with nothing to price.
    """
    from apps.customers import models as customers_models

    assert customers_models.Account._meta.get_field("unit").null is True
    assert {c.name for c in customers_models.Account._meta.constraints} >= {
        "ck_accounts_anchored",
        "ck_accounts_regular_has_unit",
    }
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        connection, unit, rows = _build(dana)
        assert unit["id"], "the ordinary unit exists and is NOT a common area"
        from apps.metering import models as metering_models

        assert not metering_models.Unit.objects.filter(
            tenant_id=brazos.id, premises_id=connection.premises_id, is_common_area=True
        ).exists(), "the premise this build stands on has no shared space at all"

        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(dana, connection.premises_id)
        result = w6.create_owner_account(dana, connection.id, _owner_identity(premises))
        assert result["kind"] == "master"
        # It covers NOTHING — there is no common area to cover — and that is the
        # honest number rather than a missing one.
        assert result["common_areas_covered"] == 0

        connection.refresh_from_db()
        assert connection.owner_account_id is not None, "the owner has an account"
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        assert account.kind == "master"
        # `BR-CUS-1010` — the ADDRESS is the anchor, on this build exactly as on
        # one with a hallway. A dwelling was deliberately NOT chosen: it would
        # have put the developer's coverage on a unit a resident's own account
        # must later occupy, which `BR-CUS-017` refuses.
        assert account.unit_id is None
        assert str(account.premises_id) == str(connection.premises_id)


def _owner_identity(premises):
    """⛔ **`BR-CUS-1024` — NEW CONNECT REACHES THE MASTER DOOR AND THE RULE IS
    ON IT** (PO 2026-09-01, said of THIS door: *"we have to create it if not
    matching customer ID not available, - rest is correct"*).

    `create_owner_account` passes the caller's `customer` block straight through
    to `create_master_account`, and that door refuses an account whose customer
    identifies nobody. **A payload with no contact does not escape it**: when one
    is absent the master door BUILDS the contact from the premises' own
    `owner_manager` (PO 2026-08-22, *"payer = the premises' owner/manager"*), so
    a party is presented and the refusal fires. So the build account names the
    owner it is opened for, as a COMPANY, in the one shape every fixture in this
    repo uses (`tests/identity_fixtures.py`). No assertion in this file is about
    identity.
    """
    return {
        "customer": identity_fixtures.customer_block(
            premises.get("owner_manager") or "Owner", kind="company"
        )
    }


def test_w6_the_owner_account_is_a_master_anchored_on_the_common_area(dana, brazos):
    """**BR-MET-116 — and the mechanism was already built, which is the finding.**

    `BR-CUS-068` (2026-08-22) made a master account an ordinary `accounts` row
    with `kind='master'` anchored on the premises' first common-area unit;
    `BR-CUS-083` (2026-08-24) already ruled connection charges go to the
    developer through exactly that account. OQ-373 asked a question both had
    answered — **DEF-682**, an r11 step 0 miss.

    What the 2026-08-25 ruling adds is real: *"unit will be all vacant right
    now"*. The two earlier rules describe a master over a **running** building.
    This one is created over an **empty** one, and nobody had said that was
    allowed.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit 1")
        common = _common_area(dana, brazos, premises)

        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        connection = work_tables.Connection.objects.get(pk=created["id"])

        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(dana, connection.premises_id)
        result = w6.create_owner_account(dana, connection.id, _owner_identity(premises))
        assert result["kind"] == "master"
        assert result["common_areas_covered"] == 1
        assert result["br_ref"] == "BR-MET-116"

        connection.refresh_from_db()
        assert connection.owner_account_id is not None

        from apps.customers import models as customers_models
        from apps.customers import selectors as customers_selectors

        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        assert account.kind == "master", "BR-CUS-068's column, not a new one"
        # ⚠ **`CR-056` W1 / `BR-CUS-1010` — IT HANGS OFF THE ADDRESS NOW.** This
        # read `str(account.unit_id) == str(common["id"])`, "anchored on the
        # common area". There is no anchor: the account names the premises and
        # reaches the common area through the service agreement asserted below,
        # which is where every common area but the first already rode.
        assert str(account.premises_id) == str(premises["id"])
        assert account.unit_id is None
        # AND the ordinary unit is still not covered — the master path attaches
        # common areas only, and refuses anything else by name (BR-CUS-068).
        covered = customers_selectors.covered_unit_ids(account)
        assert covered == [str(common["id"])]
        assert str(unit["id"]) not in covered


def test_w6_an_owner_account_is_never_created_twice(dana, brazos):
    """The same immutability the tagging path enforces. A build that acquired a
    second payer would be a debt with two debtors and nothing recording the
    move (hard rule 4)."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        make_unit(dana, premises["id"], label="Unit 1")
        _common_area(dana, brazos, premises)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        connection = work_tables.Connection.objects.get(pk=created["id"])

        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(dana, connection.premises_id)
        w6.create_owner_account(dana, connection.id, _owner_identity(premises))
        with pytest.raises(errors.BizError) as caught:
            w6.create_owner_account(dana, connection.id, _owner_identity(premises))
        assert caught.value.code == errors.BIZ_IMMUTABLE
        assert caught.value.br_ref == "BR-MET-113"


def test_w6_the_quote_total_is_money_to_four_places(dana, brazos):
    """Hard rule 2 as the PO re-signed it on 2026-08-22: *"MOney 4 decimal,
    percentage 6 decimal, display both 2 decimal"*. Never a float, never cents.

    The figure is the drawn quote: `185 × 25 = 4,625` · `310 × 24 = 7,440` ·
    `45 × 50 = 2,250` · `120 × 1 = 120` — **$14,435.00**, which foots exactly.
    """
    field = work_tables.Connection._meta.get_field("quote_total")
    assert field.decimal_places == 4, "hard rule 2 — stored to four"
    assert field.max_digits == 18
    assert not isinstance(field, models.FloatField)

    with tenant_ctx(brazos):
        connection, unit, rows = _build(dana)
        connection.quote_total = Decimal("14435.0000")
        connection.save(update_fields=["quote_total"])
        connection.refresh_from_db()
        assert connection.quote_total == Decimal("14435.0000")
        # It foots — the four drawn lines, checked rather than quoted.
        assert (
            Decimal("185") * 25
            + Decimal("310") * 24
            + Decimal("45") * 50
            + Decimal("120") * 1
        ) == Decimal("14435")


# ════════════════════════════════════════════════════════════════════════════
# 6.10 · commit_connection — step 9's five-module orchestrator (BR-MET-112)
# ════════════════════════════════════════════════════════════════════════════
def test_w6_the_commit_produces_the_seven_count_manifest(dana, brazos):
    """**The drawn manifest is a CONTRACT, not a log line.**

    Step 9 shows `Customer · Premises · Units · Meters · Sub-meter links · Plan
    assignments · One-time charges` **before** committing, so the commit must
    produce exactly those seven keys — a manifest missing one is a promise the
    screen made and the code did not keep.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        connection = work_tables.Connection.objects.get(pk=created["id"])

        result = w6.commit_connection(
            dana,
            connection.id,
            {"units": [{"label": "Unit 1"}, {"label": "Common area", "is_common_area": True}]},
        )
        # ⚠ THE SEVEN NAMES ARE WRITTEN OUT, NOT COMPARED TO THE CONSTANT.
        # The first version of this assertion read
        # `set(result["manifest"]) == set(w6.MANIFEST_KEYS)` — and when the
        # constant was broken by deleting a key, IT STILL PASSED, because both
        # sides moved together. A tautology dressed as a contract.
        #
        # This is the fifth time this repo has recorded that shape (law 11's
        # `--stat` clause twice, the F-TABS lane's disabled-button count, the
        # `not.toContain("checked")` case, now this) and the first time I caught
        # it in my own guard — by proving RED, which is the only thing that
        # would have shown it.
        #
        # The seven names come from the SCREEN, so they are what the screen
        # promised and the only thing worth asserting.
        #
        # ⚠ **EIGHT FROM 2026-09-16, AND THE EIGHTH IS A DEFECT FIX RATHER THAN
        # A NEW DRAWING (`DEF-MET-5428`).** Step 6 has proposed work orders
        # since `CR-070` wave E and step 8 has told the clerk how many will be
        # raised; the commit raised none and reported none, so the promise on
        # the review screen was computed in the browser from the proposal and
        # compared with nothing on the server. The seven drawn counts are
        # untouched — `work_orders` is ADDED so the screen can read its own
        # promise back off the commit.
        #
        # ⚠ **NINE FROM 2026-09-16, AND THE NINTH IS THE SAME SHAPE AS THE
        # EIGHTH.** `connection_messages.queue_on_commit` had been built and
        # proved with 13 cases and **nothing called it** — hard-won law 2, a
        # path nothing reaches, which passes every test on either side of the
        # gap. The commit now calls it as its last act and `messages` carries
        # what it returned, so step 8's drawn *"Three messages are queued to
        # the owner"* is read off the server instead of recomputed in the
        # browser. **Today it reports ZERO queued with three refusals**, which
        # is the true answer while the platform has no `connection` source kind
        # — see the assertions below, which pin the honesty rather than the
        # number.
        #
        # ⚠ **TEN FROM 2026-09-16, AND THE TENTH IS WHAT TURNS A FIGURE INTO A
        # DOCUMENT (`CR-109`, `DEF-MET-5446`).** `one_time_charges` has carried
        # the quote as a STRING since this manifest was drawn, and until today
        # nothing raised it: the total sat on the `connections` row and reached
        # no book. The commit now posts it through billing's own door, so the
        # manifest names the INVOICE it raised — `one_time_charge_invoice_no` —
        # and the review step reads the posting instead of believing the total.
        # `None` wherever nothing was posted, with a stated absence saying which
        # of the six reasons it was.
        assert set(result["manifest"]) == {
            "customers",
            "premises",
            "units",
            "meters",
            "sub_meter_links",
            "plan_assignments",
            "one_time_charges",
            "work_orders",
            "messages",
            "one_time_charge_invoice_no",
            # ⊕ **TWELVE FROM 2026-09-28 (`BR-MET-1187`, `CR-150-BRC09` `B1`).**
            # Pressing Create now writes the payment too, when one was taken:
            # PO, *"we create entries in books"* and *"based on payment type we
            # nedd to give all paymnet fields"*. The receipt NUMBER, never the
            # payment's row id (B14 rule 31), and the amount as the same stored
            # 4-decimal string `one_time_charges` uses. `None` on this build,
            # which took none — a zero would read as *"they paid nothing"*
            # where the truth is *"nobody was asked to"*.
            #
            # ⚠ **THIS SET ASSERTION IS THE REASON THE CONTRACT HELD**, and it
            # went red the moment the two keys landed, which is the right kind
            # of failure: the manifest's own docstring makes its keys FIXED
            # rather than assembled per call, so a screen reads one shape off
            # every commit.
            "one_time_charge_payment_no",
            "one_time_charge_paid",
        }
        assert result["manifest"]["one_time_charge_payment_no"] is None
        assert result["manifest"]["one_time_charge_paid"] is None
        # **THE DOOR IS REACHED — this is the assertion that would have caught
        # the gap, and it asserts a ROW-SHAPED answer rather than a truthy one.**
        # A manifest entry of `None` or `0` would also be "not three", so the
        # test asks for the door's own report: one decided outcome per occasion,
        # and a queued count that counts rows.
        messages = result["manifest"]["messages"]
        assert isinstance(messages, dict), f"the door was not called: {messages!r}"
        assert messages["decided_count"] == len(messages["messages"]) >= 1
        # ⚠ **ZERO IS ASSERTED AS THE TRUTH OF TODAY, NOT AS A PREFERENCE.**
        # Every message is refused for want of a `connection` source kind. When
        # that question is answered this line goes RED and names the change —
        # which is the hold-expiry test hard-won law 2 asks for, rather than a
        # number somebody has to remember to revisit.
        assert messages["queued_count"] == 0, (
            "a message was queued: the `connection` source kind must have been "
            "answered. Update this assertion deliberately — do not delete it."
        )
        assert all(row["state"] != "queued" for row in messages["messages"])
        assert result["manifest"]["units"] == 2
        # ⚠ `premises` IS `None`, NOT `1`, AND THAT IS THE POINT (DEF-2961,
        # and this assertion's own staleness is DEF-MET-3619).
        #
        # `connections.premises_id` is NOT NULL, so the address exists before
        # the draft does and THE COMMIT CREATES NONE. The old `== 1` was a
        # count derived from the presence of units, which is a different fact;
        # a manifest is a statement about what this call WROTE. `None` says
        # *"this count cannot be answered here"* where `0` would say *"we made
        # none"* — the posture `sub_meter_links` already takes.
        #
        # The count that CAN be answered lives on `create_connection`'s own
        # response as `premises_created` (BR-MET-1024) — the door that did it
        # is the door that can say so.
        assert result["manifest"]["premises"] is None
        # …and the absence is REPORTED rather than left as a silent null, which
        # is the half of DEF-2961's fix that nothing was asserting.
        premises_absence = [row for row in result["unavailable"] if row["field"] == "premises"]
        assert len(premises_absence) == 1
        assert premises_absence[0]["code"] == "premises_created_at_step_1_not_at_commit"
        assert result["br_ref"] == "BR-MET-112"


def test_w6_nothing_is_written_until_the_commit(dana, brazos):
    """**BR-MET-112, asserted from the database rather than from the screen.**

    Every wizard footer says *"nothing is written until step 9"*. A wizard that
    created the premise at step 3 would leave an orphan behind every abandoned
    build, and `Save & exit` / `Park — waiting on` make abandonment ordinary
    rather than exceptional.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        before = w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count()
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        # A draft connection exists and NOT ONE unit does.
        assert w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count() == before

        w6.commit_connection(
            dana, created["id"], {"units": [{"label": "Unit 1"}]}
        )
        assert w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count() == before + 1


def test_w6_the_commit_runs_once_and_refuses_a_second_press(dana, brazos):
    """A wizard whose confirm button committed twice would double a building.
    The state is the guard, and `BR-MET-112` is why it can be: nothing exists
    before the commit, so `draft` is an honest precondition."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.commit_connection(dana, created["id"], {"units": [{"label": "Unit 1"}]})

        with pytest.raises(errors.BizError) as caught:
            w6.commit_connection(dana, created["id"], {"units": [{"label": "Unit 2"}]})
        assert caught.value.br_ref == "BR-MET-112"
        assert w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count() == 1


def test_w6_a_build_that_NAMES_NO_CHARGE_commits_and_claims_no_invoice(dana, brazos):
    """**A build with no charge on it is lawful, and it raises nothing.**

    ⚠ **RENAMED AND RE-POINTED TWICE, AND BOTH MOVES ARE RECORDED BECAUSE THIS
    CASE KEPT ASSERTING A WORLD THAT HAD MOVED.**

    **2026-09-16, `CR-109`:** it was `test_w6_the_quote_is_recorded_and_posted_
    by_nothing` and asserted `quote_recorded_not_posted` — *"billing's one-time
    door takes ONE `connection_charge_code` with no amount, no description and
    no lines"*. True when written; the fix was to WIDEN the door rather than
    route around `BR-BIL-020`.

    **2026-09-21, `BR-MET-1178`:** the absence's CODE became
    `build_names_no_charge` and this case was not moved with it, so it asserted
    `no_quote_on_this_build` — **a string the engine had not emitted for a
    week** — and was RED on the branch before `CR-150-BRC09` opened.

    **2026-09-28, `BR-MET-1187`** (`CR-150-BRC09` task `B2`): the CR named this
    line as *"THE WORST OF THEM, BECAUSE IT WILL GO ON PASSING"* — it asserted
    `one_time_charge_invoice_no is None` for *a build that commits with no
    books entry*, which is now the refused case. **The figure does not move and
    the REASON does**: this build commits and claims no invoice **because it
    names no charge**, which `BR-MET-1187` exempts by name (*"A BUILD THAT NAMES
    NO CHARGE HAS NOTHING TO WRITE AND IS UNAFFECTED"*). The case where a charge
    EXISTS and cannot be raised is now a refusal and is covered in
    `test_br_met_1187_books_entry_at_creation.py`.

    ⚠ **AND THE CLIENT'S `$14,435.00` IS NO LONGER RECORDED (`DEF-MET-7641`).**
    The old assertion `one_time_charges == "14435.0000"` was this file agreeing
    with hard rule 2 being broken: a total off the wire, written to a build with
    no invoice behind it.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})

        result = w6.commit_connection(
            dana,
            created["id"],
            {"units": [{"label": "Unit 1"}], "quote_total": "14435.0000"},
        )
        codes = {row["code"] for row in result["unavailable"]}
        # Two absences that outlived their cause are GONE — hard-won law 1.
        assert "quote_recorded_not_posted" not in codes
        assert "no_quote_on_this_build" not in codes
        assert "build_names_no_charge" in codes
        quote_rows = [
            row for row in result["unavailable"] if row["code"] == "build_names_no_charge"
        ]
        assert len(quote_rows) == 1
        # ⚠ **THE CLIENT'S FIGURE IS WRITTEN NOWHERE** — hard rule 2 and
        # `BR-MET-1187`. `None` rather than `""` or `"0"`: a zero reads as
        # *"this build was free"* and an empty string is a figure-shaped hole.
        assert result["manifest"]["one_time_charges"] is None
        assert work_tables.Connection.objects.get(pk=created["id"]).quote_total is None
        # Nothing was raised, so the manifest does NOT claim an invoice.
        #
        # ⚠ **THE KEY IS PRESENT AND `None`, NOT ABSENT — and this assertion
        # read `not in` until 2026-09-16.** The manifest's own docstring makes
        # it a CONTRACT whose keys are FIXED rather than assembled per call,
        # precisely so a screen can read the same shape off every commit; a key
        # that comes and goes is the thing that rule exists to stop.
        # `sub_meter_links` has been `None` in this same manifest for the same
        # reason since it was drawn — *"reported rather than counted as 0"*.
        # The two test files covering this path had drifted into asserting
        # opposite shapes of the same key, which is how a contract quietly
        # stops being one.
        assert result["manifest"]["one_time_charge_invoice_no"] is None


def test_w6_sub_meter_links_are_an_absence_never_a_zero(dana, brazos):
    """**A zero would read as *"we made none"* where the truth is *"we cannot
    make them from here"*.** Those are different statements about a building,
    and the manifest must not make the first one.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        result = w6.commit_connection(dana, created["id"], {"units": [{"label": "Unit 1"}]})

        assert result["manifest"]["sub_meter_links"] is None, "an absence, not 0"
        codes = {row["code"] for row in result["unavailable"]}
        assert "no_door_from_metering" in codes
