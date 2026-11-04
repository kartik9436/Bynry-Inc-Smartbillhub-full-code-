# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W6 task 6.13 — `NCT-02` THE CONNECTION DETAIL (screen S88),
#           the backend half. The screen is built, is routed at
#           `/connections/:connectionId` and rendered the SERVER'S 404, because
#           `GET /connections/{id}` did not exist. `connection_reads
#           .connection_detail()` + the view that returns it verbatim.
# Rules:    B18 §5.4.9 `NCT-02` (the six tabs, drawn) · BR-MET-110 (a person
#           accepts the field's data — a NULL `accepted_at` on a completed
#           order IS the review queue) · BR-MET-114 (outstanding work is
#           human-marked, never derived, and never blocks) · BR-MET-036
#           (occupancy is DERIVED from the active account) · BR-MET-113 (the
#           owner's account) · CLAUDE.md hard rule 1 (tenant scoping — a
#           cross-tenant read is a 404, never a 403) · hard rule 2 (money
#           stored 4 dp, displayed 2, never a float)
# Questions: ⛔ OQ-379 (`charges` — the quote is four coded lines and billing's
#           one-time door takes one code with no amount) and ⛔ DEF-678
#           (`quote_settled_at` — nothing records a settlement) are OPEN. Both
#           serve `null` beside a stated reason; the tests below assert the
#           NULL and the reason, so answering either by picking a value goes RED.
# ───────────────────────────────────────────────────────
"""S88's payload, pinned field by field to the contract the screen was built to.

`07-frontend/src/features/customers/newConnectEndpoints.ts` declares
`ConnectionDetail` and every field on it names a function in `connections.py`.
This file asserts the two agree — key set first, then what each figure means —
because the failure this endpoint can have is not a crash: it is a screen that
renders, and renders a number nobody computed.

⚠ **FOUR FIELDS ARE NULL ON PURPOSE AND EACH CARRIES A REASON.** `charges`
(OQ-379), `quote_settled_at` (DEF-678), `deposit` (no consumer category exists
for a vacant unit) and five of the nine asset columns (the assets selector
publishes four). Every one of them is asserted BOTH ways here — the null AND the
sentence — so that a later lane filling one in with a zero, a dash or a guessed
word goes red rather than quietly shipping DEF-127 again.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import api as metering_api
from apps.metering import connection_reads as reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables

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


@pytest.fixture()
def real_audit_trail():
    """The audit rows in the DATABASE, for the two history tests.

    ⚠ **`tests/test_us_met_helpers.py` installs an autouse sink that CAPTURES
    audit rows into a list**, so no metering test writes `audit_log` at all —
    which is right for every other file here and is exactly wrong for a read
    model whose History tab IS that table. This swaps audit's own registered
    sink back in for the duration, so the assertions below run end to end:
    `connections._audit` → BE-03 → `apps.audit.services.store_row` → the row →
    `entity_trail` → the payload the screen draws. Restored afterwards, so a
    later test in this file still sees the capture sink it expects.
    """
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


#: `ConnectionDetail`, verbatim from the TypeScript the screen imports. The key
#: SET is asserted rather than a subset: a field the screen reads and the server
#: does not send is `undefined` in a browser and a blank cell on a table, which
#: is precisely the failure that cannot be seen from either side alone.
DETAIL_KEYS = {
    "id",
    "connection_no",
    "state",
    "premises",
    "unit_summary",
    "applicant",
    "request_no",
    # ⚠ **`prefill` ARRIVED ON 2026-09-21 WITH `DEF-CUS-6109` AND THIS SET WAS
    # NEVER MOVED, SO THIS CASE HAS BEEN RED SINCE THE 2026-09-22 MERGE
    # (`DEF-CUS-7621`, dated by searching the history for the key rather than
    # by assuming — CLAUDE.md law 7).** The assertion did its job: it named the
    # extra key the moment it appeared. Then nobody read it for six days, which
    # is the shape law 7 says dominates this project — a guard proved red at
    # birth and never read again. It also HID a later break, because
    # `set(work_orders[0]) == WORK_ORDER_KEYS` sits two lines below it and
    # never ran while this line failed first.
    "prefill",
    "mode",
    "started_at",
    "target_activation",
    "waiting_on",
    "units",
    "orders",
    "services",
    "work_orders",
    "unit_rows",
    "assets",
    "sub_meter_links",
    "quote_total",
    "quote_settled_at",
    "charges",
    "deposit",
    "outstanding",
    "history",
    "owner_account_no",
    "unavailable",
}

WORK_ORDER_KEYS = {
    "id",
    "order_no",
    "type",
    "service",
    "scope",
    "unit_label",
    "mode",
    "state",
    "outcome",
    "is_gate",
    "blocked_by_order_no",
    "external_ref",
    "completed_at",
    "accepted_at",
    "accepted_by",
    # ⚠ **`CR-150-BRC09` — WHO HAS IT, AS TWO FACTS AND NEVER ONE.** A crew can
    # hold an order with nobody named on it yet, and that unassigned case is
    # what stalls a build; one field cannot tell *the contractor has it* from
    # *nobody has it*. `ck_work_orders_one_assignee` makes the two mutually
    # exclusive, so both null means unassigned and the screen draws its red
    # pill rather than two empty cells.
    "crew",
    "crew_kind",
    "technician",
    "field_data",
}

UNIT_ROW_KEYS = {
    "id",
    "label",
    "unit_type",
    "services",
    "meters",
    "plan",
    "occupancy",
    "account_no",
    # ⚠ **THE SECOND SET `DEF-CUS-7621` PREDICTED.** `characteristics` arrived
    # with `CR-070` wave B (`US-WRK-002`) and this set was never moved — and
    # NOBODY COULD HAVE SEEN IT, because `set(detail) == DETAIL_KEYS` failed
    # two assertions earlier and this line never executed. Repairing the first
    # red is what uncovered the second, which is the whole cost of leaving a
    # red unread: one stale assertion hides every assertion beneath it.
    "characteristics",
}

ASSET_ROW_KEYS = {
    "id",
    "asset_no",
    "service",
    "kind",
    "unit_label",
    "size",
    "multiplier",
    "read_method",
    "parent",
    "status",
}

SERVICE_BLOCK_KEYS = {"service", "state", "units_energised", "units_total", "activated_at"}


# ── the fixture: `CON-26-0110` as `NCT-02` heads it ─────────────────────────
def _build(actor, *, no="CON-26-0110", address="3450 Oak Ridge Dr", units=1, target=None):
    """One build, through the real write paths — no ORM shortcuts.

    Electric per unit and water at the first unit, which is the single-unit
    shape `NCT-02` draws: *"ELECTRIC Activated 1 of 1 units · WATER Activated
    1 of 1 units"*.
    """
    premises = make_premises(actor, address_line=address)
    unit_ids = [
        make_unit(actor, premises["id"], label=f"{no} unit {n + 1}")["id"] for n in range(units)
    ]
    created = w6.create_connection(
        actor,
        {"premises_id": premises["id"], "target_activation": target or date(2026, 8, 14)},
    )
    connection = work_tables.Connection.objects.get(pk=created["id"])
    work_tables.Connection.objects.filter(pk=connection.id).update(connection_no=no)
    electric = [
        w6.add_connection_service(actor, connection.id, service_code="electric", unit_id=unit_id)[
            "id"
        ]
        for unit_id in unit_ids
    ]
    water = w6.add_connection_service(
        actor, connection.id, service_code="water", unit_id=unit_ids[0]
    )["id"]
    w6.submit_connection(actor, connection.id)
    connection.refresh_from_db()
    return connection, premises, unit_ids, electric, water


# ════════════════════════════════════════════════════════════════════════════
# THE CONTRACT — the key set the screen reads
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_serves_every_field_the_screen_declares(dana, brazos):
    """`ConnectionDetail`'s twenty-six fields, no more and no fewer.

    A missing key is `undefined` in the browser and a blank cell on the page;
    an extra one is a contract two lanes disagree about. Neither is visible from
    one side, which is why the SET is asserted.
    """
    with tenant_ctx(brazos):
        connection, premises, unit_ids, _electric, _water = _build(dana)
        w6.create_work_order(dana, connection.id, {"type": "meter set", "service": "electric"})
        detail = reads.connection_detail(connection.id)

    assert set(detail) == DETAIL_KEYS
    # ⊕ `DEF-CUS-10045` — the register's town, state and ZIP joined the block
    # (and `ConnectionDetail.premises` in `newConnectEndpoints.ts`).
    assert set(detail["premises"]) == {
        "id", "premise_no", "name", "address", "city", "state", "postal_code",
    }
    assert set(detail["orders"]) == {"done", "total"}
    assert set(detail["quote_total"]) == {"stored", "display"}
    assert set(detail["work_orders"][0]) == WORK_ORDER_KEYS
    assert set(detail["unit_rows"][0]) == UNIT_ROW_KEYS
    assert set(detail["services"][0]) == SERVICE_BLOCK_KEYS
    assert detail["id"] == str(connection.id)
    assert detail["connection_no"] == "CON-26-0110"
    assert detail["premises"]["address"] == "3450 Oak Ridge Dr"
    assert detail["premises"]["id"] == premises["id"]
    assert len(unit_ids) == 1


def test_w6_detail_header_reads_as_the_screen_draws_it(dana, brazos):
    """*"Started Aug 12 · target energisation Aug 14"* · `PROGRESS 5 of 5
    orders` · `WAITING ON Nothing`.

    `started_at` is the SUBMISSION, falling back to creation — §2's rule for the
    list's OLDEST tile, applied to the same fact on the detail. `waiting_on` is
    served as stored: `None` is *"nothing / not blocked"*, and the screen owns
    that word, not this payload.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        for _ in range(5):
            w6.create_work_order(dana, connection.id, {"type": "step"})
        orders = list(work_tables.WorkOrder.objects.filter(connection_id=connection.id))
        work_tables.WorkOrder.objects.filter(pk__in=[o.id for o in orders]).update(state=work_tables.WO_COMPLETED)
        detail = reads.connection_detail(connection.id)

    assert detail["orders"] == {"done": 5, "total": 5}
    assert detail["target_activation"] == "2026-08-14"
    assert detail["waiting_on"] is None
    assert detail["started_at"] == connection.submitted_at.isoformat()
    assert detail["units"] == 1


def test_w6_detail_units_figure_agrees_with_the_worklist(dana, brazos):
    """One definition of `UNITS`, read twice. The list and the detail draw the
    same figure for the same build, and it counts the units this build's
    SERVICES name — not every unit standing on the premise."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main Street")
        unit_ids = [make_unit(dana, premises["id"], label=f"Apt {n}")["id"] for n in range(3)]
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        for unit_id in unit_ids[:2]:
            w6.add_connection_service(dana, created["id"], service_code="electric", unit_id=unit_id)
        w6.add_connection_service(dana, created["id"], service_code="water")  # per-premise
        w6.submit_connection(dana, created["id"])
        detail = reads.connection_detail(created["id"])
        row = reads.list_connections(segment="all")["rows"][0]

    assert detail["units"] == 2, "three units stand on the premise; the build services two"
    assert detail["units"] == row["units"]
    assert [unit["label"] for unit in detail["unit_rows"]] == ["Apt 0", "Apt 1"]


def test_w6_detail_state_is_the_derivation_never_the_cached_column(dana, brazos):
    """§1, on the screen a person actually reads a state from.

    `connections.state` is a CACHE. The detail reports
    `derive_connection_state()` over this build's own service rows, so a drifted
    cache can never put the wrong badge on the header. Forced apart on purpose;
    in the product `refresh_connection_state()` keeps them equal.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, electric, _water = _build(dana)
        w6.transition_service(dana, electric[0], work_tables.SVC_ACTIVATED)
        connection.refresh_from_db()
        assert connection.state == work_tables.PARTLY_ACTIVATED
        work_tables.Connection.objects.filter(pk=connection.id).update(state=work_tables.REQUESTED)
        detail = reads.connection_detail(connection.id)

    assert detail["state"] == work_tables.PARTLY_ACTIVATED


def test_w6_detail_service_blocks_are_the_drawn_side_by_side_pair(dana, brazos):
    """```
    ELECTRIC   Activated   1 of 1 units · Aug 18
    WATER      Pending     1 of 1 units
    ```
    The block's state is the SAME derivation the connection's state uses, fed
    this service's rows — so a service and a build cannot disagree about what
    *"partly"* means. `activated_at` is null while nothing has gone live: an
    absence, not a date to invent.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, electric, _water = _build(dana)
        w6.transition_service(dana, electric[0], work_tables.SVC_ACTIVATED)
        detail = reads.connection_detail(connection.id)

    blocks = {block["service"]: block for block in detail["services"]}
    assert set(blocks) == {"electric", "water"}
    assert blocks["electric"]["state"] == work_tables.ACTIVATED
    assert (blocks["electric"]["units_energised"], blocks["electric"]["units_total"]) == (1, 1)
    assert blocks["electric"]["activated_at"] is not None
    assert blocks["water"]["state"] == work_tables.REQUESTED
    assert blocks["water"]["units_energised"] == 0
    assert blocks["water"]["activated_at"] is None, "no date is invented for a service not yet on"


# ════════════════════════════════════════════════════════════════════════════
# THE WORK ORDERS TAB — and BR-MET-110's review queue
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_work_order_rows_carry_the_gate_the_chain_and_the_stamped_mode(dana, brazos):
    """`WO-4905 → WO-4904` is drawn as a chain, and the 🚩 is a STAMP on the
    order it was raised for.

    `mode` is the ORDER's own column and is never inherited from the connection:
    a mode describes WORK, some of it finished, and inheriting would relabel an
    order completed in March as `external` in April with nothing recording it.
    """
    with tenant_ctx(brazos):
        connection, _premises, unit_ids, _electric, _water = _build(dana)
        first = w6.create_work_order(
            dana,
            connection.id,
            {
                "type": "meter set",
                "service": "electric",
                "scope": work_tables.SCOPE_UNIT,
                "unit_id": unit_ids[0],
                "is_gate": True,
            },
        )
        second = w6.create_work_order(
            dana,
            connection.id,
            {"type": "light-up", "blocked_by": first["id"], "mode": work_tables.MODE_EXTERNAL},
        )
        detail = reads.connection_detail(connection.id)

    rows = {row["type"]: row for row in detail["work_orders"]}
    assert rows["meter set"]["is_gate"] is True
    assert rows["meter set"]["service"] == "electric"
    assert rows["meter set"]["scope"] == work_tables.SCOPE_UNIT
    assert rows["meter set"]["unit_label"] == "CON-26-0110 unit 1"
    assert rows["meter set"]["order_no"] == first["order_no"]
    assert rows["light-up"]["is_gate"] is False
    assert rows["light-up"]["blocked_by_order_no"] == first["order_no"]
    assert rows["light-up"]["mode"] == work_tables.MODE_EXTERNAL, "the ORDER's stamp, not the build's"
    assert rows["meter set"]["mode"] == work_tables.MODE_OUR_CREW
    assert second["id"] == rows["light-up"]["id"]


def test_w6_detail_a_completed_order_with_no_acceptance_is_the_review_queue(dana, brazos):
    """**BR-MET-110.** A null `accepted_at` on an order that IS complete is the
    only thing in the product that says *"the field sent data and no person has
    accepted it yet"*. Served exactly as stored — never defaulted to the
    completion date, which would empty the queue by arithmetic.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        order = w6.create_work_order(dana, connection.id, {"type": "meter set"})
        field_close(
            dana, order["id"], field_data={"serial": "M-5001"}, outcome=work_tables.OUTCOME_PASSED
        )
        awaiting = reads.connection_detail(connection.id)["work_orders"][0]

        w6.accept_field_result(dana, order["id"])
        accepted = reads.connection_detail(connection.id)["work_orders"][0]

    assert awaiting["state"] == work_tables.WO_COMPLETED
    assert awaiting["completed_at"] is not None
    assert awaiting["accepted_at"] is None, "completed is not accepted — that gap IS the queue"
    assert awaiting["accepted_by"] is None
    assert awaiting["outcome"] == work_tables.OUTCOME_PASSED
    assert awaiting["field_data"] == {"serial": "M-5001"}, "free-shaped per BR-MET-109"

    assert accepted["accepted_at"] is not None
    assert accepted["accepted_by"] == dana.user.full_name


# ════════════════════════════════════════════════════════════════════════════
# THE UNITS TAB — the terminal state is vacant, unpriced and unaccounted
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_a_new_build_ends_vacant_with_no_plan_and_no_account(dana, brazos):
    """⚠ **THAT IS THE TERMINAL STATE, NOT AN INCOMPLETE ONE** — an account
    arrives with a move-in. `plan` and `account_no` are null and the screen says
    which kind of nothing each is; `occupancy` is BR-MET-036's derivation.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        detail = reads.connection_detail(connection.id)

    row = detail["unit_rows"][0]
    assert row["services"] == ["electric", "water"], "what the BUILD maps to this unit"
    assert row["unit_type"] == "residential"
    assert row["plan"] is None
    assert row["account_no"] is None
    assert row["occupancy"] == "vacant"
    assert row["meters"] == 0, "no meter is on this unit; the count is a real zero"


def test_w6_detail_a_units_services_are_this_builds_and_not_the_premises(dana, brazos):
    """A second connection at an existing block must not report the block's
    services as its own: the row lists the `connection_services` THIS build
    holds for that unit."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="8 Quarry Lane")
        unit = make_unit(dana, premises["id"], label="Whole property")["id"]
        first = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.add_connection_service(dana, first["id"], service_code="electric", unit_id=unit)
        w6.submit_connection(dana, first["id"])
        second = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.add_connection_service(dana, second["id"], service_code="water", unit_id=unit)
        w6.submit_connection(dana, second["id"])
        detail = reads.connection_detail(second["id"])

    assert [row["services"] for row in detail["unit_rows"]] == [["water"]]


# ════════════════════════════════════════════════════════════════════════════
# THE ASSETS TAB — four of nine columns, and the count that IS derivable
# ════════════════════════════════════════════════════════════════════════════
def _meter(actor, unit_id, *, asset_no, service="electric", parent_no=None):
    from apps.assets import services as asset_services

    payload = {
        "type": "sub_meter" if parent_no else "meter",
        "asset_no": asset_no,
        "service": service,
        "unit": "kWh",
        "read_method": "ami",
        "multiplier": "1",
    }
    if parent_no:
        payload["parent_asset_no"] = parent_no
    return asset_services.create_asset_for_unit(
        actor=actor, unit_id=str(unit_id), service_point_id=None, payload=payload
    )


def test_w6_detail_assets_serve_what_the_registry_publishes_and_null_what_it_does_not(
    dana, brazos
):
    """`NCT-02.assets` draws NINE columns and the published read answers FOUR.

    The other five are null with ONE stated reason rather than filled in from
    somewhere else — and `size` is not a column anywhere in `assets.Asset`, so
    the drawn `5/8"` has no home in the product at all. ⚠ `parent` is null on a
    SUB-meter too: the qualifier says it has one, the number is not published,
    and putting the word *"sub"* in a column that draws a meter number would be
    a fabrication that looks like data.
    """
    with tenant_ctx(brazos):
        connection, _premises, unit_ids, _electric, _water = _build(dana)
        _meter(dana, unit_ids[0], asset_no="M-5001")
        _meter(dana, unit_ids[0], asset_no="M-5002", parent_no="M-5001")
        detail = reads.connection_detail(connection.id)

    assert {row["asset_no"] for row in detail["assets"]} == {"M-5001", "M-5002"}
    assert set(detail["assets"][0]) == ASSET_ROW_KEYS
    for row in detail["assets"]:
        assert row["unit_label"] == "CON-26-0110 unit 1"
        assert row["kind"] in ("meter", "sub_meter")
        for unpublished in ("service", "size", "multiplier", "read_method", "parent", "status"):
            assert row[unpublished] is None, f"{unpublished} is not published to this module"
    assert detail["sub_meter_links"] == 1, "the qualifier IS published, so the count is derivable"
    assert detail["unit_rows"][0]["meters"] == 2


def test_w6_detail_a_build_with_no_meters_counts_zero_links_rather_than_none(dana, brazos):
    """`0` and `None` are different sentences here and both are reachable:
    `0` is *"the registry answered and there are no sub-meters"*, `None` is
    *"nobody answered"*. A build with meters and no sub-metering is the first."""
    with tenant_ctx(brazos):
        connection, _premises, unit_ids, _electric, _water = _build(dana)
        _meter(dana, unit_ids[0], asset_no="M-5003")
        detail = reads.connection_detail(connection.id)

    assert detail["sub_meter_links"] == 0
    assert detail["assets"][0]["asset_no"] == "M-5003"


# ════════════════════════════════════════════════════════════════════════════
# MONEY, AND THE FOUR ABSENCES
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_money_is_the_stored_display_pair_and_never_a_float(dana, brazos):
    """Hard rule 2, re-signed 2026-08-22: stored to 4 decimals, displayed to 2,
    rounded ONCE by the server. `14435` in, `14435.0000` / `14435.00` out —
    B18 §5.4.10 step 7's own quote total."""
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        empty = reads.connection_detail(connection.id)["quote_total"]
        work_tables.Connection.objects.filter(pk=connection.id).update(quote_total=Decimal("14435"))
        quoted = reads.connection_detail(connection.id)["quote_total"]

    assert empty == {"stored": None, "display": None}, "no quote is not a zero quote"
    assert quoted == {"stored": "14435.0000", "display": "14435.00"}
    assert isinstance(quoted["stored"], str), "money never travels as a float"


def test_w6_detail_the_four_absences_are_null_and_each_carries_its_reason(dana, brazos):
    """⛔ OQ-379 · DEF-678 · the deposit's missing category · the asset columns.

    Asserted BOTH ways — the null AND the sentence — so that answering an open
    question by picking a value goes RED here instead of shipping quietly.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        detail = reads.connection_detail(connection.id)

    assert detail["charges"] is None, "the quote's lines were never raised — OQ-379"
    assert detail["quote_settled_at"] is None, "nothing records a settlement — DEF-678"
    assert detail["deposit"] is None, "a vacant unit has no consumer category to price against"
    codes = {absence["code"] for absence in detail["unavailable"]}
    assert codes == {
        "quote_recorded_not_posted",
        "settlement_not_tracked",
        "deposit_policy_not_recorded",
        "asset_columns_not_published",
    }
    tracked = {a["code"]: a.get("tracks") for a in detail["unavailable"]}
    assert tracked["quote_recorded_not_posted"] == "OQ-379"
    assert tracked["settlement_not_tracked"] == "DEF-678"
    for absence in detail["unavailable"]:
        assert absence["detail"].strip(), "an absence with no sentence is a dash on a screen"


def test_w6_detail_absence_sentences_carry_no_internal_reference(dana, brazos):
    """G28/CR-016 — keep the honesty, drop the provenance. The sentence a clerk
    reads carries no question id, no route, no rule code and no file name;
    `tracks` keeps the provenance where support and engineers can reach it."""
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        detail = reads.connection_detail(connection.id)

    for absence in detail["unavailable"]:
        internals = ("OQ-", "DEF-", "BR-", "§", "GET ", "/connections", ".py", "connection_reads")
        for internal in internals:
            assert internal not in absence["detail"], (
                f"{internal!r} is an internal reference and this string is read by a utility user"
            )


def test_w6_detail_the_unit_summary_sentence_is_the_screens_and_its_parts_are_served(
    dana, brazos
):
    """The drawn sub-line *"single unit · Rodriguez, M. · from request
    SR-26-0018"* is THREE served parts and one translated sentence. The parts
    are here; the sentence is the catalogue's, because a plural rule shipped
    from a server is a copy path no translator can see."""
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        request = customer_models.ServiceRequest.objects.create(
            tenant=brazos,
            request_no="SR-26-0018",
            applicant_name="M. Rodriguez",
            address_as_given="3450 Oak Ridge Dr",
        )
        work_tables.Connection.objects.filter(pk=connection.id).update(service_request=request)
        detail = reads.connection_detail(connection.id)

    assert detail["unit_summary"] is None
    assert detail["applicant"] == "M. Rodriguez"
    assert detail["request_no"] == "SR-26-0018"
    assert detail["units"] == 1


# ════════════════════════════════════════════════════════════════════════════
# OUTSTANDING WORK · HISTORY · THE OWNER'S ACCOUNT
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_outstanding_work_is_the_human_list_and_never_blocks(dana, brazos):
    """**BR-MET-114** (PO 2026-08-25, *"human will mark everything to start
    with"*): the sentence somebody wrote, including the *because*, and
    `blocks_creation` is `false` with no flag that could say otherwise."""
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        assert reads.connection_detail(connection.id)["outstanding"] == []
        w6.mark_outstanding(
            dana,
            connection.id,
            title="Sewer on common area",
            detail="Left off, because common area has no water service",
        )
        detail = reads.connection_detail(connection.id)

    item = detail["outstanding"][0]
    assert item["title"] == "Sewer on common area"
    assert item["detail"] == "Left off, because common area has no water service"
    assert item["source"] == "human"
    assert item["blocks_creation"] is False


def test_w6_detail_history_is_the_connections_own_audit_trail(dana, brazos, real_audit_trail):
    """`WHEN · WHO · WHAT HAPPENED`, newest first, read through audit's own two
    published functions.

    `what` is the stored ACTION CODE and not a sentence: the trail records an
    action and a before→after payload, and the prose `NCT-02` draws is written
    nowhere. ⚠ The service transitions and the work-order events are audited
    against THEIR OWN entity ids and are not in this trail — asserted here so
    the gap is a fact the suite records rather than a claim a docstring makes.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, electric, _water = _build(dana)
        w6.set_waiting_on(dana, connection.id, waiting_on="inspection")
        w6.transition_service(dana, electric[0], work_tables.SVC_ACTIVATED)
        detail = reads.connection_detail(connection.id)

    assert [set(row) for row in detail["history"]] == [{"at", "who", "what"}] * len(
        detail["history"]
    )
    actions = [row["what"] for row in detail["history"]]
    assert "connection.created" in actions
    assert "connection.submitted" in actions
    assert "connection.waiting_on_set" in actions
    assert actions[0] == "connection.waiting_on_set", "newest first"
    assert all(row["who"] == dana.user.full_name for row in detail["history"])
    assert "connection_service.transitioned" not in actions, (
        "audited against the SERVICE row's id — the published trail addresses one entity"
    )


def test_w6_detail_a_system_actor_is_named_rather_than_left_blank(dana, brazos, real_audit_trail):
    """Audit's payload standard: a NULL actor IS a system job. `NCT-02` draws
    the word, and an unnamed PERSON is never given it — a machine credited with
    somebody's decision is a different claim."""
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        audit_models.AuditLog.objects.filter(
            tenant_id=brazos.id, entity_type="connection", entity_id=connection.id
        ).update(actor_user_id=None)
        detail = reads.connection_detail(connection.id)

    assert detail["history"], "the trail is not empty"
    assert {row["who"] for row in detail["history"]} == {reads.SYSTEM_ACTOR}
    assert reads.SYSTEM_ACTOR == "System"


def test_w6_detail_owner_account_is_null_until_one_is_tagged(dana, brazos):
    """**BR-MET-113** — *"Not an account — charges follow the connection"* is
    the drawn state of a build nobody has tagged, and it is served as null
    rather than as an empty string the screen would render as a blank cell."""
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        detail = reads.connection_detail(connection.id)

    assert detail["owner_account_no"] is None
    assert detail["mode"] is None, "no orders yet, so the ORDERS say nothing about mode"


# ════════════════════════════════════════════════════════════════════════════
# ISOLATION · THE ENDPOINT
# ════════════════════════════════════════════════════════════════════════════
def test_w6_detail_is_tenant_scoped_and_a_crossing_is_a_404(dana, brazos, erin, lonestar):
    """CLAUDE.md hard rule 1 and HR-1 together: another tenant's build is
    ABSENT, never forbidden — a 403 would confirm the id exists. The app filter
    is convenience; RLS FORCE is the law."""
    from core import errors

    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        assert reads.connection_detail(connection.id)["connection_no"] == "CON-26-0110"
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            reads.connection_detail(connection.id)


def test_w6_detail_endpoint_is_mounted_and_returns_the_read_model_verbatim(dana, brazos):
    """Built is not wired (hard-won law 2), and this screen was the mirror
    image: WIRED and not built — `ConnectionDetailPage.tsx` has been calling
    this route and rendering the server's 404.

    The view COMPUTES NOTHING: the payload is the read model's, byte for byte,
    so no figure can be derived and no absence defaulted at the edge.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)
        expected = reads.connection_detail(connection.id)

    response = api_call(
        metering_api.connection_detail,
        "get",
        f"/api/connections/{connection.id}",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        connection_id=connection.id,
    )
    assert response.status_code == 200
    assert response.data == expected
    # ⚠ **THE EQUALITY ABOVE IS NOT ENOUGH ON ITS OWN, AND THE MUTATION CYCLE IS
    # WHAT SAID SO (r11 step 2d).** A view defaulting `sub_meter_links` to `0`
    # passed it, because this build has no meters and the read model already
    # answers `0` — the two payloads agreed on a value the mutation could not
    # move. The fields that are ALWAYS null are where a helpful edge shows, so
    # they are named: a `[]`, a `{}` or a `0.00` here is DEF-127 again.
    assert response.data["charges"] is None
    assert response.data["deposit"] is None
    assert response.data["quote_settled_at"] is None
    assert response.data["unit_summary"] is None
    assert [absence["code"] for absence in response.data["unavailable"]] == [
        absence["code"] for absence in expected["unavailable"]
    ]

    routes = {getattr(entry.pattern, "_route", None) for entry in metering_api.urlpatterns}
    assert "connections/<uuid:connection_id>" in routes
    entry = next(
        e
        for e in metering_api.urlpatterns
        if getattr(e.pattern, "_route", None) == "connections/<uuid:connection_id>"
    )
    assert entry.callback is metering_api.connection_detail


def test_w6_detail_endpoint_404s_across_the_tenant_boundary(dana, brazos, erin, lonestar):
    """The same refusal at the edge, where a client can see it: a 404 and not a
    403, so existence does not leak through the status code."""
    with tenant_ctx(brazos):
        connection, _premises, _units, _electric, _water = _build(dana)

    response = api_call(
        metering_api.connection_detail,
        "get",
        f"/api/connections/{connection.id}",
        user=erin.user,
        role="system_admin",
        tenant=lonestar,
        connection_id=connection.id,
    )
    assert response.status_code == 404


def test_w6_detail_the_literal_commit_route_is_not_swallowed_by_the_id_route(dana, brazos):
    """⚠ The ordering trap `routes/next-code` records. `<uuid:…>` cannot match
    `commit`, so the two coexist — but the id route is registered AFTER the
    literal subpath and this pins that order, because the next literal somebody
    adds under `connections/` will not be a uuid either."""
    routes = [getattr(entry.pattern, "_route", None) for entry in metering_api.urlpatterns]
    assert routes.index("connections/<uuid:connection_id>/commit") < routes.index(
        "connections/<uuid:connection_id>"
    )
    assert routes.index("connections") < routes.index("connections/<uuid:connection_id>")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W6 task 6.13 (B18 §5.4.9 `NCT-02`) — no US-ID owns S88;
#         hard-won law 8 says every screen needs a story, REPORTED not invented.
# generated: 2026-08-25 by the CONNDETAIL lane (backend half of task 6.13)
# checklist: A✔ B✔ C✔ D✔ E✔(ConnectionDetailPage.tsx calls this route) F✔ G✔
#         H=deferred(PO)
# exceptions: (1) the four stated absences are asserted BOTH ways — null and
#         sentence — so answering OQ-379 or DEF-678 by picking a value goes RED
#         here · (2) `test_w6_detail_history_...` asserts what is NOT in the
#         trail, which is the reported seam gap made checkable · (3) no story
#         owns S88 (law 8)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def test_def713_every_write_door_reaches_the_connections_MODULE_not_the_view():
    """**DEF-713 — three doors shipped dead because a view shadowed its module.**

    `apps/metering/api.py` imported the module `connections` and then defined
    `def connections(request)`, rebinding the name. Every `connections.<fn>` in
    the file then resolved against the VIEW FUNCTION, so `commit_connection`,
    `submit_field_result` and `accept_field_result` each raised
    `AttributeError` the first time a request reached them.

    **Nothing caught it and the reasons are worth keeping.** The module
    byte-compiled — shadowing is legal Python. The OpenAPI export passed,
    because generating a schema never CALLS a view. All 29 tests passed,
    because none of them exercised the three new routes. `ruff` had been
    reporting `F811` on that line since before the doors existed, and no gate
    reads ruff's output. **A door that answers 500 on its first use is
    indistinguishable, to every check in this repo, from one that works.**

    So this asserts the ATTRIBUTES rather than the alias: `w6_connections` is
    an implementation choice, but "the name the views call must carry the
    service functions" is the property. Renaming the alias keeps this green;
    re-shadowing it turns it red.
    """
    from apps.metering import api

    for name in ("commit_connection", "submit_field_result", "accept_field_result"):
        assert hasattr(api.w6_connections, name), (
            f"api.w6_connections.{name} does not resolve — the connections MODULE is "
            "shadowed again. See DEF-713."
        )

    # And the bare name is still the view, which is why the alias is needed at
    # all: this is the collision itself, pinned so it reads as intended rather
    # than as an accident somebody later 'tidies up'.
    assert not hasattr(api.connections, "commit_connection")
