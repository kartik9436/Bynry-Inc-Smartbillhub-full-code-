# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-039 (EP-WRK-05) TC-1..TC-12 — the five flows raise their
#           jobs.  US-WRK-017 — the proposal engine, shared with New Connect.
#           Screens: Work-029 · REQ-04 · MVO-01 · MVI-01 · TRF-01 · DSC-02
# Rules:    BR-WRK-055 (the Customers door: Customers writes nothing to
#           `work_orders`; the flow does not wait for the visit and the visit
#           does not close the account) · BR-WRK-024 (every order carries its
#           source) · BR-WRK-006 (an order stands on an anchor) ·
#           BR-WRK-016 (what a flow proposes is the utility's PUBLISHED
#           templates) · BR-WRK-002 (Work reads other modules through seams and
#           writes none of them) · BR-SHL-025 (who may act) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_us_wrk_039_from_flows.py
# Impacts:  apps/customers/service_request_service.py · services.py ·
#           transfers.py · disconnects.py (the five doors, each through
#           apps/customers/seams.py) · apps/work/api.py
# ───────────────────────────────────────────────────────
"""**ONE RAISE SERVICE, FIVE CALLERS** — `CR-070` §W.10, the PO's own words:

    *"check out new services, new connect move in move out, transfer - you will
    see all these requirements are handled their , we had a missing element work
    order - now it go and fit in it"*

and §W.12: **before a new module builds a screen, find the flow that already
owns that moment.** Wave `E` did this for New Connect. This is the other four
plus the reconnect visit — the one place the code carried a named hole for it
(`customers/disconnects.py` `VISIT_NOT_SCHEDULED`).

THE FIVE MOMENTS, AND WHAT EACH ONE OFFERS
------------------------------------------
| flow | the moment | the anchor the job stands on | the number it quotes |
|---|---|---|---|
| `service_request` | an approved application is ROUTED | the premises it resolved to | `SR-…` |
| `move_out` | the final reads are entered | the account that is closing | `MVO-…` |
| `move_in` | the opening reads are taken | the NEW account | `MVI-…` |
| `transfer` | the changeover reads are done | the reassigned account | `TRF-…` |
| `reconnect` | a cut customer has paid | the account | `DSC-…` |
| `meter_read` | a meter is SHORT or cannot be read | the premises it stands at | `MTR-…` |

⚠ **THE SIXTH LANDED 2026-09-14 AND IS A CALLER, NOT A SIXTH MECHANISM** — PO,
verbatim, *"please build this"*, reversing that same morning's deferral of the
Reads→Work door. It is the one row whose *"the moment"* is an ABSENCE rather
than an event, and the one whose reference is a METER rather than a flow record;
both are explained at `FLOW_METER_READ` and at `_resolve_meter_read`.

⚠ **NO NEW ANCHOR COLUMN AND NO NEW CROSS-MODULE FK** (judgment 4). Every one of
those anchors is a column `work_orders` already has. What was missing is only
the reference BACK, and that is `source_ref` — text, because the five flows
number themselves in five different series. Worked against the alternative: one
nullable FK per flow takes the table from **4 anchor columns to 9** and
`ck_work_orders_has_anchor` from a four-way CHECK to a nine-way one, for a link
that is only ever read to print a reference.

THE THREE RULES THIS FILE EXISTS TO KEEP
----------------------------------------
**1 · THE RAISE IS OFFERED, NEVER AUTOMATIC.** `propose()` answers what fits and
writes nothing at all; `raise_for()` writes only the templates a person ticked.
A flow that raised jobs on its own would put a crew in a van because somebody
pressed *Close account*.

**2 · A FAILED RAISE NEVER FAILS THE FLOW** (`BR-WRK-055`, judgment 7). Every
caller catches, completes, and reports `work_orders_not_raised`. A customer's
move-out completes whether or not a visit could be booked — the alternative is a
field module able to block a customer from leaving.

⚠ **AND THE CATCH IS THE CALLER'S, NOT THIS FILE'S, DELIBERATELY.** This service
raises on failure so the caller decides what completing means for ITS flow. A
`try/except` here returning an empty list would look identical to *nothing was
ticked*, which is `DEF-708`'s shape exactly: an act recorded that never happened.

**3 · A REQUEST WITH NO RESOLVED PREMISES CANNOT RAISE A JOB** (judgment 8).
`resolve_address` can leave a request with no unit and no premises — one taken
by phone for an address not yet in the system. That request has **none of the
four anchors**, so `ck_work_orders_has_anchor` would refuse the row. It is
refused HERE, before anything is written, with a sentence a clerk can read,
rather than by adding a fifth anchor column for a state that is meant to be
temporary.

WHAT THIS FILE MAY TOUCH
------------------------
`apps/work` reads customers through `seams/customers_seam.py` and writes
`work_orders` through `seams/metering_seam.raise_work_order`, which calls
metering's own `create_work_order` BY NAME. No foreign model is imported here
and no foreign `.objects` is written — `G78` is what says so on every merge.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.work import selectors
from apps.work.seams import assets_seam, customers_seam, metering_seam, tenancy_seam
from core import errors

# ═══════════════════════════════════════════════════════════════════════════
# THE FLOWS — FIVE UNTIL 2026-09-14, SIX SINCE
# ═══════════════════════════════════════════════════════════════════════════
#: The tokens are `work_orders.source`'s own — one vocabulary, not a second one
#: that has to be mapped. `metering.connections.WORK_ORDER_SOURCES` holds the
#: full sixteen and `FLOW_SOURCES` the six below; they are not re-declared
#: here because two lists of the same strings is how they stop agreeing.
#: ⚠ **NO SCREEN RAISES FROM THIS FLOW ANY MORE (`DEF-WRK-9623`, `BR-WRK-055`
#: AMENDED 2026-10-04).** The table at the top of this file says *"an approved
#: application is ROUTED"*; the PO retired the request's *route* action on
#: 2026-09-19 (*"once requets is approved then in move in or new connect we take
#: all those decision"*), and an approved request now raises a CHILD move-in or
#: new connection whose own door carries the visit. The resolver stays, because
#: jobs already raised under `source = service_request` must still resolve and
#: be counted on their request; nothing calls `raise_for` with it today, and a
#: rule cannot be set on it (`rule_processes`: twelve processes, not thirteen).
FLOW_SERVICE_REQUEST = "service_request"
FLOW_MOVE_OUT = "move_out"
FLOW_MOVE_IN = "move_in"
FLOW_TRANSFER = "transfer"
FLOW_RECONNECT = "reconnect"
#: ⚠ **THE SIXTH CALLER, AND IT IS A CALLER RATHER THAN A SIXTH MECHANISM.** PO
#: ruling 2026-09-14, verbatim ***"please build this"***, reversing the same
#: day's `Q2` deferral of the Reads→Work door. A clerk looking at a shortfall can
#: send somebody out, and THE THREE RULES AT THE TOP OF THIS FILE ARE WHAT BIND
#: IT: the raise is OFFERED (a flagged reading must never summon a crew by
#: itself), a failed raise never fails the flow (a reading stays recordable when
#: no visit can be booked), and no new anchor column.
#:
#: ⚠ **IT IS THE ONE FLOW WHOSE `flow_id` IS NOT A FLOW RECORD — IT IS A METER,**
#: and that is the honest answer rather than a shortcut. A reading has no record
#: a crew can be dispatched against: you send somebody to a METER, at an address.
#: `_resolve_meter_read` walks meter → service point → unit → premises for the
#: anchor, exactly as hard rule 8 requires of every entity that is not `premises`
#: itself. Minting a *reading number* so this looked like its five neighbours
#: would be a numbering series nobody asked for, over a row that already has an
#: identity a clerk quotes — the meter's.
FLOW_METER_READ = "meter_read"
#: ⚠ **THE SEVENTH CALLER — THE DISCONNECT WIZARD'S CUT VISIT (`DEF-CUS-9631`,
#: 2026-10-05).** Step 3 asks *Who goes: Work order* per service point
#: (`BR-CUS-1098`) and its confirm step counts them; the commit raised none.
#: `flow_id` is the ACCOUNT being cut, exactly as `reconnect`'s is, and the
#: reference is its open case's number. **Not debt-shaped and not
#: `dunning_auto`**: four of the five cut reasons are no debt at all, and the
#: collections site visit `OQ-PAY-12578` ruled on is a different job — see
#: `metering.connections.SOURCE_DISCONNECT`.
FLOW_DISCONNECT = "disconnect"
FLOW_KINDS: tuple[str, ...] = (
    FLOW_SERVICE_REQUEST,
    FLOW_MOVE_OUT,
    FLOW_MOVE_IN,
    FLOW_TRANSFER,
    FLOW_RECONNECT,
    FLOW_METER_READ,
    FLOW_DISCONNECT,
)

#: ⚠ **WHICH HALF OF THE UTILITY'S TEMPLATE LIST EACH FLOW SEES.** A service
#: request is an application to BUILD a service, so it is offered the connection
#: sequence — the same set New Connect step 6 proposes. The other four act on a
#: service that already exists, so they are offered everything else the utility
#: has published: a final read, a turn-on, a changeover read, a reconnect visit.
#: Offering a move-out *Meter set* would be offering to build the thing the
#: customer already has.
#:
#: ⚠ **`meter_read` IS `False` FOR THE SAME REASON THE OTHER FOUR ARE, NOT BY
#: IMITATION.** The meter is standing there — that is the whole premise of the
#: shortfall — so the jobs that BUILD a service are exactly the wrong half of the
#: list. What this door needs offered is a re-read, a meter exchange, a leak
#: investigation: the `sequence` 0 set.
_IN_CONNECTION_SEQUENCE: dict[str, bool] = {
    FLOW_SERVICE_REQUEST: True,
    FLOW_MOVE_OUT: False,
    FLOW_MOVE_IN: False,
    FLOW_TRANSFER: False,
    FLOW_RECONNECT: False,
    FLOW_METER_READ: False,
    FLOW_DISCONNECT: False,
}

#: **Which job TYPE fits each flow** — `DEF-WRK-9626`, OUR judgment (decision
#: log 2026-10-04, *"CR-168 FLOW-FIX · WHICH JOB TYPE EACH FLOW IS OFFERED"*).
#: Nothing signed says it; the PO's two-level list (`BR-WRK-058`) has the rows.
#: A move-out's final read, a move-in's opening read, a transfer's changeover
#: read and a short read's visit are all READINGS — `Reading › Re-read`; a
#: reconnect is `Consumer Services › Disconnection/Reconnection`. A service
#: request builds a service and keeps the connection-sequence offer unchanged.
#:
#: ⚠ **IT NARROWS AND NEVER EMPTIES.** Where the utility has published a
#: template of a fitting type, only those are offered; where it has none, the
#: general sequence-0 offer stands exactly as before — a utility that never
#: typed its templates loses nothing.
FLOW_JOB_TYPE_CODES: dict[str, tuple[str, ...]] = {
    FLOW_SERVICE_REQUEST: (),
    FLOW_MOVE_OUT: ("RE_READ", "READING"),
    FLOW_MOVE_IN: ("RE_READ", "READING"),
    FLOW_TRANSFER: ("RE_READ", "READING"),
    FLOW_RECONNECT: ("DISCONNECT_RECONNECT",),
    FLOW_METER_READ: ("RE_READ", "READING"),
    FLOW_DISCONNECT: ("DISCONNECT_RECONNECT",),
}

#: `DEF-WRK-9694` — the visit each flow's OWN template is called where a tenant
#: keeps one per moment (the demo's `sample_data.FLOW_VISIT_TEMPLATES`, which
#: types four of them `RE_READ`, so the job type alone cannot tell a move-out's
#: *Final read* from a move-in's *Opening read*). A tenant that names its
#: templates differently loses nothing: the next rules in `_default_template`
#: decide. Our judgment, decision log *"CR-168 ROUND 8 · FIX-8B"*.
FLOW_VISIT_TEMPLATE_NAMES: dict[str, str] = {
    FLOW_MOVE_OUT: "Final read",
    FLOW_MOVE_IN: "Opening read",
    FLOW_TRANSFER: "Changeover read",
    FLOW_METER_READ: "Re-read",
    FLOW_RECONNECT: "Reconnect visit",
    FLOW_DISCONNECT: "Disconnect visit",
}

#: The platform's own sentence for a raise that could not happen. Five words
#: (B14 rule 33 caps a refusal at five or six), keyed so every one of the eleven
#: catalogues carries it (`G15`, `G32`).
NOT_RAISED_CODE = "work_orders_not_raised"
NOT_RAISED_KEY = "work.fromFlows.notRaised"

#: Judgment 8's refusal, raised before any row is written.
NO_ANCHOR_CODE = "flow_has_no_anchor"
NO_ANCHOR_KEY = "work.fromFlows.noAnchor"


class FlowRaiseRefused(Exception):
    """What this module raises when a flow may not raise a job at all.

    Deliberately NOT one of `core.errors`' catalogue exceptions, and the split is
    `apps.customers.disconnects.DisconnectRuleError`'s, for its reason: a caller
    inside another module's transaction has to be able to tell *the flow itself
    is refused* apart from *the job could not be created*, and an HTTP-shaped
    error class cannot carry that difference across a module boundary.
    """

    def __init__(self, message: str, *, code: str, message_key: str, br_ref: str | None = None):
        super().__init__(message)
        self.code = code
        self.message_key = message_key
        self.br_ref = br_ref


# ═══════════════════════════════════════════════════════════════════════════
# RESOLVING A FLOW — its anchor, its services, its number
# ═══════════════════════════════════════════════════════════════════════════
def _resolve(flow_kind: str, flow_id: Any) -> dict[str, Any]:
    """The three facts a raise needs: the ANCHOR, the SERVICES, the NUMBER.

    ⚠ **`flow_id` IS NOT THE SAME RECORD FOR EVERY FLOW, AND PRETENDING IT WAS
    WOULD BE THE BUG.** A screen asks `propose()` at a moment when its flow
    record may not exist yet — a move-out wizard on step 2 has an ACCOUNT and no
    `MoveRecord`, because the move has not been committed. So:

    | flow | `propose` is asked about | `raise_for` is told about |
    |---|---|---|
    | `service_request` | the request | the request |
    | `move_out` | the account that is leaving | the `MoveRecord` the move wrote |
    | `move_in` | the OUTGOING account (same unit) | the `MoveRecord` the move wrote |
    | `transfer` | the transfer | the transfer |
    | `reconnect` | the account | the account |
    | `meter_read` | the METER | the same METER |

    ⚠ **THE LAST ROW IS THE SAME ID IN BOTH COLUMNS, AND IT IS THE ONLY ONE**,
    because the meter exists before the shortfall does and does not stop existing
    when a visit is raised. There is no record that comes into being at the
    raise, so there is nothing for the two columns to differ about.

    Both columns resolve through this one function, which reads whichever record
    the id names and answers the same three facts either way. An id that names
    nothing in this tenant answers a 404-shaped refusal, never a 403 (HR-1).
    """
    if flow_kind not in FLOW_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.fromFlows.unknownFlow",
            br_ref="BR-WRK-055",
            params={"flow": flow_kind},
        )
    resolver = {
        FLOW_SERVICE_REQUEST: _resolve_service_request,
        FLOW_MOVE_OUT: _resolve_move,
        FLOW_MOVE_IN: _resolve_move,
        FLOW_TRANSFER: _resolve_transfer,
        FLOW_RECONNECT: _resolve_reconnect,
        FLOW_METER_READ: _resolve_meter_read,
        FLOW_DISCONNECT: _resolve_reconnect,
    }[flow_kind]
    resolved = resolver(flow_kind, flow_id)
    if resolved is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return resolved


def _resolve_service_request(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    request = customers_seam.service_request(flow_id)
    if request is None:
        return None
    premises_id = request["premises_id"]
    if premises_id is None and request["unit_id"]:
        # A request resolved to a UNIT knows its premises by walking — hard rule
        # 8: an address is stored on `premises` and every other record derives it
        # by walking there. A unit refines a premises by LABEL, not by address.
        premises_id = metering_seam.premises_id_of_unit(request["unit_id"])
    return {
        "kind": flow_kind,
        "id": request["id"],
        "ref": request["request_no"],
        "anchor": {"premises_id": premises_id, "unit_id": request["unit_id"]},
        "service_codes": request["service_codes"],
    }


def _resolve_move(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    """A move, asked about either way round — see `_resolve`'s table.

    A `MoveRecord` id resolves to the move (`raise_for`); an account id resolves
    to the account (`propose`, from a wizard whose move has not committed yet).
    Tried in that order because a move record is the more specific answer: an
    account id can never be a move-record id, so there is no ambiguity to fall
    through into.
    """
    move = customers_seam.move_record(flow_id)
    if move is not None:
        account_id = move["account_id"]
        ref = move["move_no"]
    else:
        account = customers_seam.account(flow_id)
        if account is None:
            return None
        account_id = account["id"]
        # No move record yet — the wizard has not committed. The panel needs no
        # number to draw itself, and the number it will carry is stamped at the
        # raise, which is the only moment it exists.
        ref = None
    services = customers_seam.account_service_codes(account_id)
    if not services:
        # `DEF-WRK-9645` — a move-in asked about a CLOSED outgoing account (the
        # normal case after a move-out) has no agreements in force, and the
        # offer read nothing. The unit's own service points are what the visit
        # is for, whoever holds the account (`_meter_for`'s walk).
        unit_id = (customers_seam.account(account_id) or {}).get("unit_id")
        services = metering_seam.service_codes_on_unit(unit_id)
    return {
        "kind": flow_kind,
        "id": str(flow_id),
        "ref": ref,
        "anchor": {"account_id": account_id},
        "service_codes": services,
    }


def _resolve_transfer(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    """A sale, asked about either way round — `_resolve`'s table, second half.

    ⚠ **A TRANSFER ID DOES NOT EXIST WHEN THE PANEL DRAWS.** `POST
    /transfers/commit` runs all five writes in ONE transaction precisely so a
    failure cannot strand an `in_progress` row nobody can see, which means there
    is no transfer row until the sale is complete — `getTransferMoney`'s own
    docstring records the same consequence for the money figures. So step 2 asks
    about the ACCOUNT that is being sold, and the raise, which happens inside
    that one transaction, names the transfer. Same shape as `_resolve_move`, and
    for the same reason rather than by imitation.
    """
    row = customers_seam.transfer(flow_id)
    if row is None:
        account = customers_seam.account(flow_id)
        if account is None:
            return None
        return {
            "kind": flow_kind,
            "id": account["id"],
            # No transfer row yet, so no `TRF-` number. The panel needs none to
            # draw itself and the number is stamped at the raise, which is the
            # only moment it exists.
            "ref": None,
            "anchor": {"account_id": account["id"]},
            "service_codes": customers_seam.account_service_codes(account["id"]),
        }
    account_id = row["account_id"]
    return {
        "kind": flow_kind,
        "id": row["id"],
        "ref": row["transfer_no"],
        # PO 2026-09-01: a transfer REASSIGNS the account rather than creating
        # one, so the anchor is that same account and the reads are done at its
        # own unit. Nothing here follows `to_account`, which no longer exists.
        "anchor": {"account_id": account_id},
        "service_codes": customers_seam.account_service_codes(account_id) if account_id else [],
    }


def _resolve_reconnect(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    account = customers_seam.account(flow_id)
    if account is None:
        return None
    case = customers_seam.open_disconnect_case(account["id"])
    return {
        "kind": flow_kind,
        "id": account["id"],
        # The case's own number when there is an open case; the account's
        # otherwise, because a reconnect visit raised outside a case is still a
        # visit somebody has to find later.
        "ref": (case or {}).get("case_no") or account["account_no"],
        "anchor": {"account_id": account["id"]},
        "service_codes": customers_seam.account_service_codes(account["id"]),
    }


def _resolve_meter_read(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    """The sixth door — a METER, and the address it stands at.

    ⚠ **`flow_id` IS AN ASSET ID AND NOT A READING ID, AND THAT IS THE DESIGN
    RATHER THAN A SIMPLIFICATION.** The moment this door serves is *"nobody could
    read this meter"* — which most often means **there is no reading row at
    all**: `BR-MET-023` gives the Missing flag the fix actions *estimate ·
    field-visit · skip*, `BR-MET-027` FORCES a visit on a third consecutive
    miss, and `BR-MET-062` forces one for a missing demand peak because an
    estimated peak is a dispute. A flow keyed on the reading could not be raised
    for the case it exists for. Keyed on the meter it always can.

    **THE WALK IS TWO HOPS AND EACH IS ITS OWN MODULE'S:** `assets_seam.meter`
    answers the number and the service point; `metering_seam.service_point_
    anchor` answers the unit, the premises and the service. Hard rule 8 —
    `BR-MET-1161` — is why the address is walked to rather than read: there is no
    address column on an asset, a point or a unit to take a short cut through.

    ⚠ **NO PREMISES MEANS NO ANCHOR, AND THAT IS ANSWERED AS A REFUSAL RATHER
    THAN FORCED THROUGH ON `asset_id` ALONE.** `ck_work_orders_has_anchor` would
    accept an asset-only row and `_require_anchor` deliberately does not, for the
    reason judgment 8 gives: a crew is sent to an ADDRESS. A meter standing on
    nothing produces a job nobody can be dispatched to, and the honest place to
    say so is the screen the clerk is on.
    """
    meter = assets_seam.meter(flow_id)
    if meter is None:
        return None
    point = (
        metering_seam.service_point_anchor(meter["service_point_id"])
        if meter["service_point_id"]
        else None
    )
    service_code = (point or {}).get("service_code")
    return {
        "kind": flow_kind,
        "id": meter["id"],
        # B14 rule 31 — the METER NUMBER a clerk quotes, never the uuid. It is
        # what `source_ref` stamps and what `orders_from_flow_tally` groups by,
        # so "how many visits has this meter needed" is a question the data can
        # answer without a reading number existing.
        "ref": meter["asset_no"],
        "anchor": {
            "premises_id": (point or {}).get("premises_id"),
            "unit_id": (point or {}).get("unit_id"),
            "asset_id": meter["id"],
        },
        # The meter runs ONE service, so the offer is that service's published
        # templates and nothing else — never the tenant's whole list.
        "service_codes": [service_code] if service_code else [],
    }


def _require_anchor(flow: dict[str, Any]) -> dict[str, Any]:
    """Judgment 8 — the refusal that comes BEFORE anything is written.

    `ck_work_orders_has_anchor` accepts a connection, a premises, an account or
    an asset. A flow that offers none of them cannot produce a lawful row, and
    the honest place to say so is the screen the clerk is standing on.
    """
    anchor = {k: v for k, v in flow["anchor"].items() if v}
    if not any(anchor.get(key) for key in ("connection_id", "premises_id", "account_id")):
        raise FlowRaiseRefused(
            "this record does not point at an address or an account yet, so a job raised "
            "from it would stand on nothing. Resolve the address first.",
            code=NO_ANCHOR_CODE,
            message_key=NO_ANCHOR_KEY,
            br_ref="BR-WRK-006",
        )
    return anchor


#: B18 §8.2's *per asset* — `metering.connections.SCOPE_ASSET`, the token
#: itself rather than an import, because `apps/work` reads metering through its
#: seam and a constant is not worth a second door.
SCOPE_PER_ASSET = "per_asset"


def _meter_for(template: dict[str, Any], anchor: dict[str, Any]) -> dict[str, Any]:
    """The METER a *per asset* job stands on, when the flow's anchor is an
    account — `DEF-WRK-9620`.

    A move-out, move-in, transfer or reconnect anchors its job on the ACCOUNT
    (the table at the top of this file), and that stays. A *per asset* template
    is a job done TO a meter, and `post_set_reads` posts its reading to the
    order's `asset` — so a flow job with no meter could be closed in the field
    and never accepted (`work.reading.no_meter_on_order`, WO-0046..WO-0049).

    The meter is walked, not chosen: the account's UNIT (customers' seam), its
    service point for the template's service (metering's), then the in-service
    meter on it (the assets seam). The unit and not the account's agreements,
    because a move-out ends those before it raises its visit. **Exactly one meter is an answer and is carried.** None adds
    nothing. **Two or more is a question** — which meter is `OQ-WRK-1723`'s
    shape one level down, and that question is OPEN — so nothing is added and
    the job stands on the account as before; Accept goes on refusing it in
    words rather than this function guessing (prime directive).
    """
    if template.get("scope") != SCOPE_PER_ASSET:
        return {}
    if anchor.get("asset_id") or not anchor.get("account_id"):
        return {}
    account = customers_seam.account(anchor["account_id"]) or {}
    service_code = (template.get("service") or {}).get("code")
    points = metering_seam.service_point_ids_on_unit(account.get("unit_id"), service_code)
    meters = assets_seam.in_service_meters_on_points(points)
    if len(meters) != 1:
        return {}
    return {"asset_id": meters[0]["id"]}


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO DOORS
# ═══════════════════════════════════════════════════════════════════════════
def propose(flow_kind: str, flow_id: Any) -> dict[str, Any]:
    """What field work this flow could raise. **WRITES NOTHING.**

    `BR-WRK-016`'s posture, widened from New Connect to the five: the offer is
    the utility's **own published templates** for the services this flow
    touches, never a list this platform invented. A tenant that has published
    none is offered none, and the panel says so — which is the truthful answer
    and not a gap (the templates are theirs to author, wave `D`/`E`).

    The answer carries the flow's own reference so the screen can say what
    raising will stamp, and `refusal` when judgment 8 bites — a refusal that is
    DATA rather than an exception, because `propose` is what the screen calls to
    decide whether to offer the control at all.
    """
    flow = _resolve(flow_kind, flow_id)
    refusal: dict[str, Any] | None = None
    try:
        _require_anchor(flow)
    except FlowRaiseRefused as exc:
        refusal = {"code": exc.code, "message_key": exc.message_key, "br_ref": exc.br_ref}
    offer = (
        {"services": [], "proposed": [], "count": 0}
        if refusal is not None
        else selectors.proposed_work_orders(
            flow["service_codes"], in_sequence=_IN_CONNECTION_SEQUENCE[flow_kind]
        )
    )
    proposed = _fitting(flow_kind, offer["proposed"])
    if refusal is None:
        proposed = _preselect(flow_kind, proposed)
    return {
        "flow": {"kind": flow["kind"], "id": flow["id"], "ref": flow["ref"]},
        "services": offer["services"],
        "proposed": proposed,
        "count": len(proposed),
        "refusal": refusal,
    }


def _preselect(flow_kind: str, proposed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`CR-168-BRC10` P3.34 — an ENABLED rule on this moment ticks its job.

    Each offered row gains `preselected_by {id, name}` when a rule names its
    template, and a rule's template that the offer does not hold (another job
    type) is ADDED, ticked, because the supervisor chose it for this moment.
    **Nothing is raised here** (`BR-WRK-055`: *No visit needed* is a recorded
    choice): the clerk sees the job ticked with the rule's name and may untick
    it. Rows no rule names are unchanged.
    """
    from apps.work import rules

    specs = rules.preselection(flow_kind)
    if not specs:
        return proposed
    by_template: dict[str, dict[str, Any]] = {}
    for spec in specs:
        by_template.setdefault(str(spec["template_id"]), spec["rule"])
    out = []
    held = set()
    for row in proposed:
        chosen = by_template.get(str(row.get("template_id")))
        out.append({**row, "preselected_by": chosen} if chosen else row)
        held.add(str(row.get("template_id")))
    for template_id, rule_ref in by_template.items():
        if template_id in held:
            continue
        template = metering_seam.template(template_id)
        if template is None or not template.get("active") or int(template.get("version") or 0) < 1:
            continue
        out.append({**selectors._proposed_row(template), "preselected_by": rule_ref})
    return out


def _fitting(flow_kind: str, proposed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`FLOW_JOB_TYPE_CODES` applied — the templates whose job type fits this
    flow, or the whole offer when none does (`DEF-WRK-9626`)."""
    from apps.work import models as work_models

    codes = FLOW_JOB_TYPE_CODES.get(flow_kind) or ()
    if not codes or not proposed:
        return proposed
    fitting_ids = {
        str(pk)
        for pk in work_models.WorkOrderType.objects.filter(
            tenant_id=customers_seam_tenant_id(), code__in=codes
        ).values_list("id", flat=True)
    }
    fitting = [
        row for row in proposed if str((row.get("job_type") or {}).get("id") or "") in fitting_ids
    ]
    return fitting or proposed


def raise_for(
    flow_kind: str, flow_id: Any, template_ids: Any, actor: Any = None
) -> dict[str, Any]:
    """Raise the jobs a person ticked, on the anchor the flow already has.

    ⚠ **THIS RAISES ON FAILURE AND DOES NOT SWALLOW.** `BR-WRK-055` says the
    flow completes whether or not the visit could be booked — and the way to
    honour that is for the CALLER to catch, because only the caller knows what
    completing means for its own flow. Returning an empty list here would look
    exactly like *nothing was ticked*, and a caller cannot tell those apart.

    ⚠ **ONE TRANSACTION, AND IT IS THE CALLER'S WHERE THERE IS ONE.** Four of the
    five customer doors are already inside `transaction.atomic()` when they reach
    this, so the `atomic()` below joins it as a SAVEPOINT rather than opening a
    second — which is what makes a partial raise impossible: either every ticked
    job exists or none does, and the flow's own writes are untouched either way
    because the caller's `except` runs outside this block.

    ⚠ **`meter_read` IS THE ONE CALLER WITH NO OUTER TRANSACTION, AND IT RELIES
    ON THIS BLOCK BEING ALL-OR-NOTHING PER METER.** `ATOMIC_REQUESTS` is not set
    anywhere in `config/settings`, so an HTTP raise reaches here in autocommit
    and the `atomic()` below is the OUTERMOST block. That is what lets its
    endpoint loop meters and catch per meter without hard-won law 14 biting: a
    refused row rolls this block back and the next iteration begins a fresh
    transaction, rather than every later statement raising
    `InFailedSqlTransaction` on PostgreSQL while passing on SQLite. Proved
    against a real PostgreSQL in `tests/test_reads_field_work_pg.py`, because the
    default suite cannot tell the two apart.
    """
    wanted = [str(tid) for tid in (template_ids or []) if str(tid).strip()]
    if not wanted:
        # Nothing ticked is not an error and never was: rule 1 above is that the
        # raise is OFFERED. A clerk who ticks nothing has answered the question.
        return {"raised": [], "count": 0, "flow": {"kind": flow_kind, "ref": None}}
    raised: list[dict[str, Any]] = []
    already_open: list[dict[str, Any]] = []
    pending: list[Any] = []
    # ⚠ **A SAVEPOINT, AND IT WRAPS THE READS AS WELL AS THE WRITES — hard-won
    # law 14.** On PostgreSQL ANY failed statement poisons the whole
    # transaction, and four of the five callers are already inside one when they
    # reach here. So the savepoint has to begin before the first query, not
    # before the first write: a refused read outside it would take the caller's
    # own account write down with it and the flow would fail for want of a job
    # nobody asked to be blocking — which is exactly what `BR-WRK-055` forbids.
    # The suite runs on in-memory SQLite, which has no aborted-transaction state
    # and would pass either version; `tests/test_us_wrk_039_from_flows_pg.py` is
    # what proves this one on a real PostgreSQL.
    with transaction.atomic():
        flow = _resolve(flow_kind, flow_id)
        anchor = _require_anchor(flow)
        for template_id in wanted:
            template = metering_seam.template(template_id)
            if template is None:
                raise errors.deny_as_not_found("BR-TEN-003")
            if not template.get("active") or int(template.get("version") or 0) < 1:
                # `BR-WRK-012` — deactivating a template stops NEW orders, and
                # `BR-WRK-011` — a draft has produced nothing an order can stamp.
                raise errors.ValidationError(
                    errors.VAL_UNKNOWN_LOOKUP,
                    message_key="work.fromFlows.templateNotPublished",
                    br_ref="BR-WRK-016",
                    params={"template": template.get("name")},
                )
            stands_on = {**anchor, **_meter_for(template, anchor)}
            # P3.38 — one subject, one open job per template, whoever raised
            # the first (a rule overnight, this screen a minute ago). Not a
            # refusal: the existing job is named back, so the screen can say
            # which job already covers it.
            open_now = metering_seam.open_order_for_template(template["id"], stands_on)
            if open_now is not None:
                already_open.append(
                    {"template_id": str(template["id"]), "order_no": open_now["order_no"]}
                )
                continue
            order = metering_seam.raise_work_order(
                actor,
                {
                    **stands_on,
                    "type": template["name"],
                    "scope": template["scope"],
                    # `_service_row` takes the CODE and refuses a service the
                    # tenant does not run, which is the same refusal
                    # `ensure_service_point` gives — one mistake, one message.
                    "service": (template["service"] or {}).get("code"),
                    "template_id": template["id"],
                    "is_gate": template["is_gate"],
                    # BR-WRK-024 — WHY, and WHICH record asked.
                    "source": flow_kind,
                    "source_ref": flow["ref"],
                },
            )
            # P3.34 — a ticked job a rule pre-selected arrives with that
            # rule's priority and assignee. Inside this savepoint: the job and
            # its shape are one unit.
            from apps.work import rules

            shaped = rules.shape_by_rule(actor, order["id"], flow_kind, template["id"])
            if shaped is not None:
                pending.extend(shaped.pop("pending", []))
            raised.append(
                {
                    "id": order["id"],
                    "order_no": order["order_no"],
                    "template_id": template["id"],
                    "name": template["name"],
                    "source": order.get("source"),
                    "source_ref": order.get("source_ref"),
                    "rule": (shaped or {}).get("rule"),
                }
            )
    if pending:
        from apps.work import rules

        rules._push_pending(actor, pending)
    return {
        "raised": raised,
        "count": len(raised),
        "already_open": already_open,
        "flow": {"kind": flow_kind, "ref": flow["ref"]},
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE THIRD DOOR — ROWS A CLERK TYPED, NOT TEMPLATES A CLERK TICKED
# (`DEF-CUS-6363`, PO rulings 2026-09-23: *"please provide the button to raise
# field work order … if work order is raised you should shown in table format
# and also on review step"* · *"show the status … and who is working on it"* ·
# the transfer's *"table array component with add option; also have no visit
# required option"*)
# ═══════════════════════════════════════════════════════════════════════════
#: The keys one order row may carry. Anything else is refused by name, so a
#: screen that grew a column the raise does not read is told so.
ORDER_ROW_FIELDS: frozenset[str] = frozenset(
    {
        "type_id",
        "priority_id",
        "due_on",
        "technician_id",
        "crew_id",
        "note",
        "rule_id",
        # `CR-171-BRC10` P1.19 (lane MVI-WIZ-UNIT, image 30): the move-in's
        # *Field visit* draws ONE *Work order* field naming a TEMPLATE (and so
        # its job type), a *For* column naming the meter, and a *Window*.
        "template_id",
        "asset_no",
        "window_start",
        "window_end",
    }
)
#: What an order row that could not be ASSIGNED says. The order exists and is
#: in the dispatcher's queue; only the holder did not stick.
NOT_ASSIGNED_CODE = "work_order_not_assigned"
NOT_ASSIGNED_KEY = "work.fromFlows.notAssigned"
#: What an order row whose WINDOW could not be written says (`CR-171-BRC10`
#: P1.19). The order exists; only the window did not stick.
NOT_SCHEDULED_CODE = "work_order_not_scheduled"
NOT_SCHEDULED_KEY = "work.fromFlows.notScheduled"


def raise_options() -> dict[str, Any]:
    """What a flow's *+ Add work order* row offers: the utility's own active job
    types and priorities — never a list this platform invented.

    ⚠ **A WORK READ, NOT THE SETTINGS LOOKUP, AND THAT IS THE POINT.** The same
    rows are served by `GET /lookups/work_order_types` and `…/work_priorities`,
    which are Settings doors (`SettingsReadAnyWriteSystemAdmin`, A4
    `settings_lookups`) and answer a Billing Clerk **403** — measured on
    2026-09-23 as the seeded clerk. A clerk completing a move-in is exactly who
    raises these orders, and every name here is already printed on every work
    order row that clerk can read, so this widens no door: it serves the ACTIVE
    rows, id + name + default priority, and nothing a settings screen edits.
    """
    from apps.work import models as work_models

    tenant = customers_seam_tenant_id()
    priorities = [
        {"id": str(row.id), "code": row.code, "name": row.name, "sla_hours": row.sla_hours}
        for row in work_models.WorkPriority.objects.filter(tenant_id=tenant, active=True).order_by(
            "rank", "name"
        )
    ]
    types = []
    for row in (
        work_models.WorkOrderType.objects.filter(tenant_id=tenant, active=True)
        .select_related("parent", "default_priority", "parent__default_priority")
        .order_by("name")
    ):
        default = row.default_priority or (row.parent.default_priority if row.parent_id else None)
        types.append(
            {
                "id": str(row.id),
                "code": row.code,
                "name": row.name,
                "parent_name": row.parent.name if row.parent_id else None,
                "default_priority_id": str(default.id) if default is not None else None,
            }
        )
    # `DEF-WRK-9626` — the job type each flow's new row opens on: the first of
    # `FLOW_JOB_TYPE_CODES` this utility has, active. The clerk may change it.
    by_code = {row["code"]: row["id"] for row in types}
    flow_types = {}
    for kind, codes in FLOW_JOB_TYPE_CODES.items():
        chosen = next((by_code[code] for code in codes if code in by_code), None)
        if chosen is not None:
            flow_types[kind] = chosen
    return {
        "types": types,
        "priorities": priorities,
        "flow_types": flow_types,
        "preselected": _preselected_rows(),
    }


#: The moments a clerk's *Field visit* TABLE stands on (`FieldVisitOrders`).
#: The reconnect row and the new connection's step 6 read their pre-selection
#: from `propose` and `/connections/proposed-work-orders` instead.
TABLE_MOMENTS: tuple[str, ...] = (FLOW_MOVE_IN, FLOW_MOVE_OUT, FLOW_TRANSFER)


def _preselected_rows() -> dict[str, list[dict[str, Any]]]:
    """`CR-168-BRC10` P3.42 — what an ENABLED rule on a screen moment puts in
    that moment's *Field visit* table before the clerk touches it.

    One row per rule: its template's JOB TYPE (the table is typed, not
    templated — `DEF-CUS-6363`), the rule's priority, and its holder where the
    rule NAMES one (`technician` / `crew`; *best skill fit* and *whoever covers
    the area* are worked out at the raise, so the row says nobody yet). The
    rule's own name travels so the screen can say who added it. **Nothing is
    raised here** — `BR-WRK-055`: the clerk may remove the row, and *No visit
    needed* stays a recorded choice. A rule whose template carries no job type
    cannot be a typed row and is left out rather than guessed.
    """
    from apps.work import rules

    out: dict[str, list[dict[str, Any]]] = {}
    for moment in TABLE_MOMENTS:
        rows: list[dict[str, Any]] = []
        for spec in rules.preselection(moment):
            template = metering_seam.template(spec["template_id"])
            type_id = str(((template or {}).get("job_type") or {}).get("id") or "")
            if not type_id:
                continue
            assign = spec.get("assign_to") or {}
            kind, holder_id = str(assign.get("kind") or ""), str(assign.get("id") or "")
            holder = f"{'technician' if kind == 'technician' else 'crew'}:{holder_id}" if (
                kind in ("technician", "crew") and holder_id
            ) else ""
            rows.append(
                {
                    "rule": spec["rule"],
                    "type_id": type_id,
                    "priority_id": spec.get("priority_id") or "",
                    "holder": holder,
                }
            )
        if rows:
            out[moment] = rows
    return out


def _rule_for_row(flow_kind: str, rule_id: Any, type_id: Any) -> str | None:
    """The rule a row names, ONLY when it is an enabled rule on this moment
    whose template is of the row's job type — else None, and the job is
    raised exactly as a clerk's own row would be. Never a refusal: a rule
    turned off between the screen opening and the save must not lose the
    visit (`BR-WRK-055`)."""
    if not rule_id:
        return None
    from apps.work import rules

    for spec in rules.preselection(flow_kind):
        if str(spec["rule"]["id"]) != str(rule_id):
            continue
        template = metering_seam.template(spec["template_id"])
        if str(((template or {}).get("job_type") or {}).get("id") or "") == str(type_id):
            return str(rule_id)
    return None


def customers_seam_tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def clean_order_rows(rows: Any) -> list[dict[str, Any]]:
    """The rows a clerk added, validated BEFORE any transaction opens.

    A row needs its JOB TYPE and nothing else: the priority falls back to the
    type's own (`BR-WRK-018`), an empty due date means the priority's target,
    nobody named means the dispatcher assigns it, and the note is optional.
    Refused by name, with the row's position, so the screen can point at it.
    """
    if rows in (None, ""):
        return []
    if not isinstance(rows, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.fromFlows.ordersFormat",
            params={"field": "field_visit.orders"},
        )
    cleaned: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="work.fromFlows.ordersFormat",
                params={"field": f"field_visit.orders[{index}]"},
            )
        unknown = sorted(set(row) - ORDER_ROW_FIELDS)
        if unknown:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="work.fromFlows.ordersFormat",
                params={"field": f"field_visit.orders[{index}].{unknown[0]}"},
            )
        type_id = str(row.get("type_id") or "").strip()
        if type_id == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.fromFlows.jobTypeRequired",
                params={"field": f"field_visit.orders[{index}].type_id", "row": index + 1},
            )
        cleaned.append(
            {
                "type_id": type_id,
                "priority_id": str(row.get("priority_id") or "").strip() or None,
                "due_on": str(row.get("due_on") or "").strip() or None,
                "technician_id": str(row.get("technician_id") or "").strip() or None,
                "crew_id": str(row.get("crew_id") or "").strip() or None,
                "note": str(row.get("note") or "").strip() or None,
                # `CR-168-BRC10` P3.42 — the rule that put this row on the
                # screen. Checked against the moment at the raise
                # (`_rule_for_row`), never trusted as sent.
                "rule_id": str(row.get("rule_id") or "").strip() or None,
                # `CR-171-BRC10` P1.19 — each checked at the raise, where the
                # flow is known (`raise_orders_for`), never trusted as sent.
                "template_id": str(row.get("template_id") or "").strip() or None,
                "asset_no": str(row.get("asset_no") or "").strip() or None,
                "window_start": str(row.get("window_start") or "").strip() or None,
                "window_end": str(row.get("window_end") or "").strip() or None,
            }
        )
    return cleaned


def _due_moment(due_on: str | None) -> Any:
    """`YYYY-MM-DD` → an aware midnight in the tenant's zone, or None."""
    if not due_on:
        return None
    from datetime import datetime, time

    from django.utils import dateparse

    day = dateparse.parse_date(due_on)
    if day is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.moment_format", params={"field": "due_on"}
        )
    return datetime.combine(day, time.min, tzinfo=tenancy_seam.tenant_timezone())


def _default_template(
    flow_kind: str,
    flow: dict[str, Any],
    type_id: Any,
    fits: Any = None,
) -> dict[str, Any] | None:
    """`DEF-WRK-9694` — the published template a TYPED row is raised from.

    A row a clerk adds names a job TYPE; the job's checklist lives on a
    TEMPLATE. Before this the row raised the type alone and the phone had
    nothing to tick or read (WALK-B W2). The template is chosen among the ones
    this flow is OFFERED (`propose`'s own read: published, the flow's services)
    whose job type is the row's, in this order — the first rule that answers:

      1. one an enabled RULE pre-selects for this moment (P3.34) — the
         supervisor already chose it;
      2. the one named for this flow's visit (`FLOW_VISIT_TEMPLATE_NAMES`);
      3. the only one of that type;
      4. otherwise the first by template number — stable across two raises.

    None when no published template carries the type: the row then raises the
    type alone, exactly as before, and nothing is invented.
    """
    offer = selectors.proposed_work_orders(
        flow["service_codes"], in_sequence=_IN_CONNECTION_SEQUENCE[flow_kind]
    )["proposed"]
    of_type = [
        row for row in offer if str((row.get("job_type") or {}).get("id") or "") == str(type_id)
    ]
    # `DEF-WRK-9784` — a row whose *For* names a meter takes a template of THAT
    # meter's service or none. The offer is every service the flow starts, so
    # without this a typed row on an electric meter picked the WATER *Opening
    # read*, Work refused it (`work.order.template_wrong_service`) and the whole
    # raise came back empty. No template of the meter's service is an answer:
    # the row raises its type alone, as the last paragraph above says.
    if fits is not None:
        of_type = [row for row in of_type if fits((row.get("service") or {}).get("code"))]
    # Lowest number first, so a tenant whose visit templates exist once per
    # service gets the same one on every raise of a row naming no meter.
    of_type.sort(key=lambda row: str(row.get("template_no") or ""))
    if not of_type:
        return None
    from apps.work import rules

    chosen_by_rule = {str(spec.get("template_id")) for spec in rules.preselection(flow_kind)}
    for row in of_type:
        if str(row["template_id"]) in chosen_by_rule:
            return metering_seam.template(row["template_id"])
    named = FLOW_VISIT_TEMPLATE_NAMES.get(flow_kind)
    for row in of_type:
        if named is not None and row.get("name") == named:
            return metering_seam.template(row["template_id"])
    first = sorted(of_type, key=lambda row: str(row.get("template_no") or ""))[0]
    return metering_seam.template(first["template_id"])


def _named_template(
    flow_kind: str, flow: dict[str, Any], template_id: Any, type_id: Any
) -> dict[str, Any]:
    """`CR-171-BRC10` P1.19 — the template a clerk NAMED in the *Work order*
    field, honoured only when this flow is OFFERED it (`propose`'s own read:
    published, the flow's services, the flow's half of the sequence split) and
    its job type is the row's. Anything else is refused by name rather than
    raised from a template the screen never offered."""
    offer = selectors.proposed_work_orders(
        flow["service_codes"], in_sequence=_IN_CONNECTION_SEQUENCE[flow_kind]
    )["proposed"]
    for row in offer:
        if str(row["template_id"]) != str(template_id):
            continue
        if str((row.get("job_type") or {}).get("id") or "") != str(type_id):
            break
        template = metering_seam.template(row["template_id"])
        if template is not None:
            return template
    raise errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="work.fromFlows.templateNotOffered",
        br_ref="BR-WRK-055",
        params={"field": "field_visit.orders.template_id"},
    )


def _flow_unit_id(flow: dict[str, Any]) -> Any:
    """The unit a flow's account stands on — what *For* names a meter on."""
    account_id = (flow.get("anchor") or {}).get("account_id")
    return (customers_seam.account(account_id) or {}).get("unit_id") if account_id else None


def _meter_takes_service(unit_id: Any, meter: dict[str, Any], service_code: Any) -> bool:
    """`DEF-WRK-9784` — whether `meter` measures `service_code` on `unit_id`.

    The fact `metering.connections._template_asset_refusal` refuses on (the
    meter's service point is of another service), asked BEFORE the raise so a
    wrong pick is named at the step instead of emptying the raise at Complete.
    A device on no service point measures nothing and passes — the raise's own
    check lets it through for the same reason.
    """
    if not service_code:
        return True
    point = (assets_seam.meter(meter["id"]) or {}).get("service_point_id")
    if not point:
        return True
    return str(point) in metering_seam.service_point_ids_on_unit(unit_id, str(service_code))


def _refuse_wrong_service(index: int, template: dict[str, Any]) -> None:
    raise errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="work.order.template_wrong_service",
        br_ref="BR-WRK-008",
        params={
            "field": f"field_visit.orders[{index}].template_id",
            "row": index + 1,
            "template": template.get("name"),
        },
    )


def check_order_rows_on_unit(rows: Any, unit_id: Any) -> list[dict[str, Any]]:
    """`DEF-WRK-9784` — a flow's rows checked against its UNIT before the flow
    commits: each *For* meter stands on the unit, and a named template is of
    that meter's service. Refused by name with the row's position, so a wrong
    pick is answered with everything still on screen — never a move-in that
    completes and quietly books nothing. (`BR-WRK-055` keeps a flow from
    waiting on a RAISE; it never asked a flow to accept a wrong pick.)

    Returns the cleaned rows. READ ONLY.
    """
    cleaned = clean_order_rows(rows)
    for index, row in enumerate(cleaned):
        if not row.get("asset_no"):
            continue
        meter = assets_seam.asset_on_unit_by_no(unit_id, row["asset_no"])
        if meter is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.fromFlows.assetNotOnUnit",
                br_ref="BR-WRK-006",
                params={"field": f"field_visit.orders[{index}].asset_no", "asset": row["asset_no"]},
            )
        if not row.get("template_id"):
            continue
        template = metering_seam.template(row["template_id"])
        if template is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.fromFlows.templateNotOffered",
                br_ref="BR-WRK-055",
                params={"field": f"field_visit.orders[{index}].template_id"},
            )
        if not _meter_takes_service(unit_id, meter, (template.get("service") or {}).get("code")):
            _refuse_wrong_service(index, template)
    return cleaned


def _named_meter(flow: dict[str, Any], asset_no: str) -> dict[str, Any]:
    """`CR-171-BRC10` P1.19 — the *For* column: the meter a clerk named, by
    number, on the flow's own unit. A CHOICE, not a derivation, so it settles
    for this one job what `_meter_for` refuses to guess between two meters."""
    account_id = (flow.get("anchor") or {}).get("account_id")
    unit_id = (customers_seam.account(account_id) or {}).get("unit_id") if account_id else None
    meter = assets_seam.asset_on_unit_by_no(unit_id, asset_no)
    if meter is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.fromFlows.assetNotOnUnit",
            br_ref="BR-WRK-006",
            params={"field": "field_visit.orders.asset_no", "asset": asset_no},
        )
    return meter


def raise_orders_for(
    flow_kind: str, flow_id: Any, rows: Any, actor: Any = None
) -> dict[str, Any]:
    """Raise the orders a clerk ADDED as rows, on the anchor the flow already has.

    The same posture as `raise_for` above, and for the same reasons — read its
    docstring: it RAISES on failure (the caller catches, `BR-WRK-055`), and the
    whole raise is ONE savepoint, reads included (hard-won law 14), so either
    every row exists or none does.

    ⚠ **THE ASSIGNMENT IS THE ONE PART THAT MAY FAIL ALONE.** A named technician
    who lacks the job's skill is refused by `dispatch.record_act`
    (`BR-WRK-029`) — the same test the dispatcher's own picker applies. That
    refusal must not throw away an order the utility needs, so each assignment
    runs in its OWN nested savepoint and a refusal leaves the order raised,
    unassigned and in the dispatcher's queue, with a warning naming it.
    """
    from apps.work import dispatch
    from apps.work import models as work_models

    wanted = clean_order_rows(rows)
    if not wanted:
        return {"raised": [], "count": 0, "warnings": [], "flow": {"kind": flow_kind, "ref": None}}
    raised: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        flow = _resolve(flow_kind, flow_id)
        anchor = _require_anchor(flow)
        tenant = customers_seam_tenant_id()
        for index, row in enumerate(wanted):
            kind = work_models.WorkOrderType.objects.filter(
                tenant_id=tenant, pk=row["type_id"], active=True
            ).first()
            if kind is None:
                raise errors.deny_as_not_found("BR-TEN-003")
            # `DEF-WRK-9694` — the flow's template of this type, so the job
            # carries a checklist the technician's phone can show.
            # `CR-171-BRC10` P1.19 — the template the clerk NAMED wins.
            # The *For* column first — the clerk's own answer to which meter —
            # because it decides which service's templates may serve the row.
            meter = _named_meter(flow, row["asset_no"]) if row.get("asset_no") else None
            fits = None
            if meter is not None:
                unit_id = _flow_unit_id(flow)
                fits = lambda code, _m=meter, _u=unit_id: _meter_takes_service(_u, _m, code)  # noqa: E731
            template = (
                _named_template(flow_kind, flow, row["template_id"], kind.id)
                if row.get("template_id")
                else _default_template(flow_kind, flow, kind.id, fits)
            )
            # `DEF-WRK-9784` — a NAMED template of another service is refused by
            # name here, before any row is written, not deep inside the raise.
            if row.get("template_id") and template is not None and fits is not None:
                if not fits((template.get("service") or {}).get("code")):
                    _refuse_wrong_service(index, template)
            from_template: dict[str, Any] = {}
            stands_on = anchor
            if meter is not None:
                stands_on = {**anchor, "asset_id": meter["id"]}
            if template is not None:
                stands_on = {**stands_on, **_meter_for(template, stands_on)}
                from_template = {
                    "scope": template["scope"],
                    "service": (template["service"] or {}).get("code"),
                    "template_id": template["id"],
                    "is_gate": template["is_gate"],
                }
            order = metering_seam.raise_work_order(
                actor,
                {
                    **stands_on,
                    **from_template,
                    "type": kind.name,
                    "type_id": str(kind.id),
                    "priority_id": row["priority_id"],
                    # A calendar day the clerk picked, anchored at the START of
                    # that day in the TENANT's zone — `parse_moment` would read a
                    # bare date as midnight in the server's zone, and on a
                    # US tenant *due 05-Sep* came back as *04-Sep*. An empty one
                    # lets the priority's own target stand (`BR-WRK-018`).
                    "due_at": _due_moment(row["due_on"]),
                    # The office talking to the field — `technician_notes`'
                    # own note on `WorkOrder`, carried to the phone unchanged.
                    "technician_notes": row["note"],
                    "source": flow_kind,
                    "source_ref": flow["ref"],
                },
            )
            # `CR-168-BRC10` P3.42 — a row the rule put on the screen says so
            # on the job (`BR-WRK-024`: a rule-raised order stamps the rule).
            rule_id = _rule_for_row(flow_kind, row.get("rule_id"), kind.id)
            if rule_id is not None:
                work_order = metering_seam.work_order_row(order["id"])
                work_order.rule_id = rule_id
                metering_seam.save_order_fields(work_order, ["rule_id"])
            holder = None
            # `CR-171-BRC10` P1.19 — the *Window*, written by the dispatcher's
            # own act (an assign carries it; with nobody named it is a
            # schedule), so a window is validated exactly as on the board.
            window = {
                key: row.get(key)
                for key in ("window_start", "window_end")
                if row.get(key)
            }
            if window and not (row["technician_id"] or row["crew_id"]):
                try:
                    with transaction.atomic():
                        dispatch.record_act(actor, order["id"], {"act": "schedule", **window})
                except Exception as exc:  # noqa: BLE001 - one fact: not scheduled
                    warnings.append(
                        {
                            "code": NOT_SCHEDULED_CODE,
                            "message_key": NOT_SCHEDULED_KEY,
                            "br_ref": "BR-WRK-055",
                            "params": {"order": order["order_no"]},
                            "detail": str(exc) or None,
                        }
                    )
            if row["technician_id"] or row["crew_id"]:
                try:
                    with transaction.atomic():
                        dispatch.record_act(
                            actor,
                            order["id"],
                            {
                                "act": "assign",
                                "technician_id": row["technician_id"],
                                "crew_id": row["crew_id"],
                                **window,
                            },
                        )
                    holder = row["technician_id"] or row["crew_id"]
                except Exception as exc:  # noqa: BLE001 - one fact: not assigned
                    warnings.append(
                        {
                            "code": NOT_ASSIGNED_CODE,
                            "message_key": NOT_ASSIGNED_KEY,
                            "br_ref": "BR-WRK-029",
                            "params": {"order": order["order_no"]},
                            "detail": str(exc) or None,
                        }
                    )
            raised.append(
                {
                    "id": order["id"],
                    "order_no": order["order_no"],
                    "type_id": str(kind.id),
                    "name": kind.name,
                    "template_id": str(template["id"]) if template is not None else None,
                    "assigned": holder is not None,
                    "rule_id": rule_id,
                    "source": order.get("source"),
                    "source_ref": order.get("source_ref"),
                }
            )
    return {
        "raised": raised,
        "count": len(raised),
        "warnings": warnings,
        "flow": {"kind": flow_kind, "ref": flow["ref"]},
    }


def acceptance(flow_kind: str, source_ref: Any) -> dict[str, Any]:
    """How many of the jobs this flow record raised have been ACCEPTED.

    **B19 §12.3's promise needs a count, not a flag** — *"A request closes on
    its own when the job it created finishes"* is written in the singular and a
    new water connection raises three jobs days apart. `total` is what the flow
    raised; `accepted` is how many a person has reviewed and accepted
    (`work_orders.accepted_at`, `BR-MET-110`'s human act). The CALLER decides
    what to do when they are equal — this reads and concludes nothing.

    Cancelled orders are excluded from BOTH figures: a job somebody called off
    is not work outstanding, and leaving it in `total` would hold a request open
    for ever on a job nobody is going to do.
    """
    return metering_seam.orders_from_flow_tally(flow_kind, source_ref)


def visits(flow_kind: str, source_ref: Any) -> dict[str, Any]:
    """The jobs one flow record raised, for the record's own page to SHOW —
    `CR-168-BRC10` §F (the PO: *"when work orders are completed is the clerk
    able to see the status update in those requests"*).

    `raised` · `done` (the field closed it) · `accepted` (a person accepted it,
    `BR-MET-110`) and the orders themselves, each with the number a clerk quotes.
    A record with no `source_ref` raised nothing that can be found, and says 0.
    """
    rows = metering_seam.orders_from_flow_rows(flow_kind, source_ref) if source_ref else []
    return {
        "raised": len(rows),
        "done": sum(1 for row in rows if row["done"]),
        "accepted": sum(1 for row in rows if row["accepted"]),
        "orders": rows,
    }


def raise_cut_visits(account_id: Any, visits: Any, actor: Any = None) -> dict[str, Any]:
    """The disconnect wizard's *Who goes: Work order* rows — `DEF-CUS-9631`.

    ``visits`` is ``[{service, instruction}]``, one per service point the clerk
    sent a crew to (`BR-CUS-1098`). Each becomes ONE job on the account, typed
    *Disconnection/Reconnection*, raised from the utility's own template for
    that SERVICE where it publishes one (`_default_template`, narrowed to the
    row's service — a water cut must not take an electric checklist), the
    instruction carried to the phone as `technician_notes`.

    The posture is `raise_orders_for`'s: it RAISES on failure and the caller
    catches (`BR-WRK-055`), and the whole raise is ONE savepoint, reads
    included (hard-won law 14), so either every visit exists or none does.
    """
    from apps.work import models as work_models

    rows = [row for row in (visits or []) if isinstance(row, dict)]
    if not rows:
        return {"raised": [], "count": 0, "flow": {"kind": FLOW_DISCONNECT, "ref": None}}
    raised: list[dict[str, Any]] = []
    with transaction.atomic():
        flow = _resolve(FLOW_DISCONNECT, account_id)
        anchor = _require_anchor(flow)
        kind = (
            work_models.WorkOrderType.objects.filter(
                tenant_id=customers_seam_tenant_id(),
                code__in=FLOW_JOB_TYPE_CODES[FLOW_DISCONNECT],
                active=True,
            )
            .order_by("code")
            .first()
        )
        for row in rows:
            service = str(row.get("service") or "").strip() or None
            narrowed = {**flow, "service_codes": [service] if service else flow["service_codes"]}
            template = (
                _default_template(FLOW_DISCONNECT, narrowed, kind.id) if kind is not None else None
            )
            stands_on = anchor
            from_template: dict[str, Any] = {}
            if template is not None:
                stands_on = {**anchor, **_meter_for(template, anchor)}
                from_template = {
                    "scope": template["scope"],
                    "template_id": template["id"],
                    "is_gate": template["is_gate"],
                }
            order = metering_seam.raise_work_order(
                actor,
                {
                    **stands_on,
                    **from_template,
                    "service": service,
                    "type": kind.name if kind is not None else "Disconnection",
                    **({"type_id": str(kind.id)} if kind is not None else {}),
                    "technician_notes": str(row.get("instruction") or "").strip() or None,
                    "source": FLOW_DISCONNECT,
                    "source_ref": flow["ref"],
                },
            )
            raised.append({"id": order["id"], "order_no": order["order_no"], "service": service})
    return {
        "raised": raised,
        "count": len(raised),
        "flow": {"kind": FLOW_DISCONNECT, "ref": flow["ref"]},
    }


def raise_temporary_stop_visits(account_id: Any, visits: Any, actor: Any = None) -> dict[str, Any]:
    """`CR-183-BRC10` B2 — a temporary stop's *Field visit needed*: a shut-off
    job dated the stop day and a turn-on job dated the restart day.

    ``visits`` is ``[{flow, due_on, role}]`` where ``flow`` is ``disconnect``
    (the shut-off) or ``reconnect`` (the turn-on) and ``role`` is echoed back so
    the caller can store each job's NUMBER against the right date. Both are
    *Disconnection/Reconnection* jobs on the ACCOUNT — the same type and the
    same template choice as the disconnect wizard's cut visit and a reconnect
    visit, because that is what a crew does at the meter whatever the reason —
    and each carries its due day. ⚠ **NOT DEBT-SHAPED**: the source is the
    flow's own token and the reference the ACCOUNT number (no disconnect case
    exists for a temporary stop).

    The posture is `raise_cut_visits`': it RAISES and the caller catches
    (`BR-WRK-055`), and the whole raise is one savepoint (hard-won law 14).
    """
    from apps.work import models as work_models

    rows = [row for row in (visits or []) if isinstance(row, dict)]
    raised: list[dict[str, Any]] = []
    if not rows:
        return {"raised": raised, "count": 0}
    with transaction.atomic():
        kind = (
            work_models.WorkOrderType.objects.filter(
                tenant_id=customers_seam_tenant_id(),
                code__in=FLOW_JOB_TYPE_CODES[FLOW_DISCONNECT],
                active=True,
            )
            .order_by("code")
            .first()
        )
        for row in rows:
            flow_kind = FLOW_RECONNECT if row.get("flow") == FLOW_RECONNECT else FLOW_DISCONNECT
            flow = _resolve(flow_kind, account_id)
            anchor = _require_anchor(flow)
            template = (
                _default_template(flow_kind, flow, kind.id) if kind is not None else None
            )
            stands_on = anchor
            from_template: dict[str, Any] = {}
            if template is not None:
                stands_on = {**anchor, **_meter_for(template, anchor)}
                from_template = {
                    "scope": template["scope"],
                    "template_id": template["id"],
                    "is_gate": template["is_gate"],
                }
            order = metering_seam.raise_work_order(
                actor,
                {
                    **stands_on,
                    **from_template,
                    "type": kind.name if kind is not None else "Disconnection",
                    **({"type_id": str(kind.id)} if kind is not None else {}),
                    "due_at": _due_moment(row.get("due_on")),
                    "source": flow_kind,
                    "source_ref": flow["ref"],
                },
            )
            raised.append(
                {"id": order["id"], "order_no": order["order_no"], "role": row.get("role")}
            )
    return {"raised": raised, "count": len(raised)}


def cancel_flow_order(order_no: Any, actor: Any = None) -> bool:
    """`DEF-CUS-10190` — take ONE still-open job a flow raised off the run, by
    its NUMBER (`dispatch.set_dispatch_state` → `cancelled`; nothing deleted).
    Used when a temporary stop ends because the customer moved out: its turn-on
    job has nobody to turn on for. `False` when no open job carries the number."""
    from apps.work import dispatch

    order_id = metering_seam.work_order_id_by_number(str(order_no))
    if order_id is None:
        return False
    order = metering_seam.work_order_row(order_id)
    if order is None or order.dispatch_state in ("complete", "cancelled"):
        return False
    dispatch.set_dispatch_state(actor, order.id, "cancelled", "work.order.cancelled")
    return True


def not_raised_warning(detail: str | None = None) -> dict[str, Any]:
    """The platform's own sentence for a raise that failed, in the shape every
    flow already puts its unavailabilities in (`MOVE_OUT_UNAVAILABLE`'s rows).

    ⚠ **IT NAMES NO ROW AND PROMISES NO RETRY.** The job was not created; the
    flow finished. Anything more would be a claim about a queue this product
    does not have.
    """
    return {
        "code": NOT_RAISED_CODE,
        "message_key": NOT_RAISED_KEY,
        "br_ref": "BR-WRK-055",
        "detail": detail
        or "the field job could not be created. The flow completed; nothing is waiting on it.",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-039 (EP-WRK-05) · US-WRK-017 · 10-execution-plan.md wave P · judgments 4, 7, 8
# generated: 2026-09-05 by the CR-070 wave P build lane
# checklist: A✔ B✔ C✔ D✔ E✔(RaiseFieldWork.tsx) F✔ G✔ H=n/a
# gates: G78 · G102 · pytest tests/test_us_wrk_039_from_flows.py
# exceptions: the dispatcher's own `source` values (dunning, asset age, high usage,
#   payment received, billing exception, compliance calendar, dispatcher) are wave G's
#   and are declared in `metering.connections.WORK_ORDER_SOURCES`, not stamped here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
