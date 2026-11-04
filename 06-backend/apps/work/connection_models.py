# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-43 — the six Work tables move out of
#           `apps/metering/connections.py` into the Work module, which owns
#           them (`04-docs/05-modules/16-work/03-field-map.md` §4; `CR-070`
#           §10; PO 2026-09-03, *"it will become the module itself"*).
#           A MODEL-STATE move, never a data move: `work/0046` creates the six
#           in Work's migration state and `metering/0078` deletes them from
#           metering's, both through `SeparateDatabaseAndState` with NO
#           database operation, so every table keeps its name, its rows, its
#           constraints, its indexes and its RLS policies byte for byte.
# Rules:    BR-WRK-001/002 (Work owns its tables and writes nobody else's) ·
#           BR-MET-108 (a flat service's characteristic is a ROW) · CLAUDE.md
#           hard rule 1 (tenant-scoped; RLS FORCE stays in metering/0027 and
#           its successors — no policy moved) · hard rule 3 (an explicit unit
#           — `unit_of_measure` is a column)
# Tests:    06-backend/tests/test_w6_connections.py · tests/test_us_wrk_*.py ·
#           tests/test_t43_work_tables_moved.py (the move itself)
# Impacts:  apps/work/migrations/0046_t43_take_the_six_work_tables.py ·
#           apps/metering/migrations/0078_t43_release_the_six_work_tables.py ·
#           apps/work/models.py (imports this module so Django registers it) ·
#           apps/metering/connections.py (keeps the services, imports these)
# ───────────────────────────────────────────────────────
"""The six Work tables — `connections`, `connection_services`, `work_orders`,
`work_order_templates`, `service_characteristics`, `connection_todos` — and
the vocabulary their check constraints read.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the declarations below were AI-authored in
`apps/metering/connections.py` (CR-030 W6 onward, every one already flagged
HUMAN-REVIEW-PENDING there) and are MOVED here unchanged by T-43; the move is
migration ordering, a CLAUDE.md 🔒 path, under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). The review-ledger row is
reported by the T-43 lane for the orchestrator to land.

WHY THEY ARE HERE
-----------------
`CR-070` §10 makes `work` the owner of these tables. Until T-43 they were
declared in metering's `connections.py`, and `16-work/03-field-map.md` §4
recorded that as choice (b) — *"the day the models move, `metering_seam.py`
changes and nothing that calls it does"*. They have moved. The class bodies,
field names, `db_table`s, constraint and index names are byte-identical to what
`connections.py` declared, so the migration autodetector sees no difference
between the old state and the new one beyond the app label.

WHAT DID NOT MOVE, AND WHY THAT IS STATED RATHER THAN HIDDEN
-------------------------------------------------------------
The SERVICES that write these tables — `create_connection`,
`create_work_order`, `commit_new_connect`, `accept_field_result` and the rest —
are still in `apps/metering/connections.py`, which now imports the models from
here. So metering's code writes tables Work owns, the mirror of the gap (b)
recorded. That is T-43's honest boundary: it moves the DECLARATIONS (and the
migration state with them) and nothing that decides behaviour. Moving the
services is a separate act with its own blast radius.

The two references to metering's own tables (`Premises`, `Unit`) are written as
strings — `"metering.Premises"` — rather than through an import of
`apps.metering.models`, so this file imports no other module's models and
`G78` reads it as clean without a seam. The deconstructed FK is identical
(`to="metering.premises"`), which is why no migration changes a column.

Kept beside `models.py` and imported from it, as `evidence_models.py`,
`rules_models.py`, `sync_models.py` and `field_order_models.py` already are.

The vocabulary and the class bodies below are moved VERBATIM, comments
included; where a comment says *"this module"* it was written about
`apps/metering/connections.py`, whose module docstring still carries the
design reasoning (§1 the state machine, §2 the characteristics).
"""

from decimal import Decimal, InvalidOperation

from django.db import models
from django.db.models import Q

from core import errors
from core import numbering as core_numbering
from core.dbfields import uuid7_pk

# ── number series ───────────────────────────────────────────────────────────
#: ✅ **LANDED 2026-08-25 — `CON-{YY}-{0000}`, GROUP_WORK.** The paragraph below
#: is kept as the record of why this module allocates by name and reports rather
#: than faking, which is still how it behaves if a tenant's row is ever absent.
#: `test_w6_a_new_connection_is_draft_and_carries_a_number` flipped with it and
#: now asserts the DRAWN grammar (`CON-26-0110`), which is the check DEF-615's
#: prevention column asks for.
#:
#: ⚠ **WHEN THIS WAS WRITTEN THE SERIES DID NOT EXIST AND THIS LANE COULD NOT
#: ADD IT.** `core/numbering.py` holds twenty-four series keys and `connection` is
#: not one of them; `work_order` IS (`WO-{0000}`, GROUP_WORK, CR-005). B18
#: §5.4.8 seeds `CON-26-0110`, which is a `CON-{YY}-{0000}` number, but the
#: catalogue's option list and its seeded default are the numbering owner's
#: decision, not this module's — and **DEF-615 is what happens when a test and
#: the catalogue each pick one independently**: `import_run` seeds `IMP-` while
#: CR-023's own test asserts `RUN-`, and one of the two has been wrong since the
#: day it landed.
#:
#: So this module ALLOCATES from the series by name and, when the row is absent,
#: REPORTS a `numbering_series_missing` warning and leaves `connection_no` NULL
#: — the same honest fallback `metering.services._allocate_number` has always
#: used (*"a missing series row is REPORTED, never faked"*). That behaviour is
#: unchanged; what changed is that the catalogue row now exists, so the healthy
#: path is the one that runs.
CONNECTION_SERIES = "connection"
WORK_ORDER_SERIES = core_numbering.WORK_ORDER

# ── the connection's seven states (B18 §5.4.3, verbatim) ────────────────────
#: ⚠ **RENAMED 2026-08-25 — CR-032, PO verbatim: *"instead of energise can we use
#: activated"*.** *Energise* is **electric jargon**, and the platform seeds TEN
#: services: only Electric, Solar and Battery are energised in any literal
#: sense — **water is turned on, gas is lit, broadband is provisioned, trash is
#: scheduled, sewer is connected.** One token has to cover all ten, and
#: `activated` is the only one of the two that is true of every service.
#: `BR-MET-110` had already reached for the neutral wording (*"service goes
#: live"*) without anyone noticing the token had not.
#:
#: The old spellings (`energised`, `partly_energised`) do not survive anywhere:
#: this was done as a **migration**, not a find-and-replace, because the value
#: is STORED on `connections.state` and a text swap would leave a fresh database
#: and an existing one silently disagreeing about a word.
DRAFT = "draft"
REQUESTED = "requested"
IN_PROGRESS = "in_progress"
PARTLY_ACTIVATED = "partly_activated"
ON_HOLD = "on_hold"
ACTIVATED = "activated"
CANCELLED = "cancelled"

CONNECTION_STATES: tuple[str, ...] = (
    DRAFT,
    REQUESTED,
    IN_PROGRESS,
    PARTLY_ACTIVATED,
    ON_HOLD,
    ACTIVATED,
    CANCELLED,
)

# ── the per-service states ──────────────────────────────────────────────────
#: ⚠ NOT DRAWN ANYWHERE — see §1 of the module docstring. The design says *"a
#: status per service"* and names no tokens; this is the connection vocabulary
#: minus `partly_energised`, which is an aggregate word. REPORTED for PO
#: confirmation rather than presented as signed.
SVC_PENDING = "pending"
SVC_IN_PROGRESS = "in_progress"
SVC_ON_HOLD = "on_hold"
SVC_ACTIVATED = "activated"
SVC_CANCELLED = "cancelled"

SERVICE_STATES: tuple[str, ...] = (
    SVC_PENDING,
    SVC_IN_PROGRESS,
    SVC_ON_HOLD,
    SVC_ACTIVATED,
    SVC_CANCELLED,
)

#: The legal transitions, and the shape of the two refusals underneath them:
#:
#:   * **A TERMINAL STATE IS TERMINAL.** `energised` and `cancelled` have no
#:     outgoing edges here. Taking a live service back OFF is a DISCONNECT — a
#:     different record with its own ladder, its own notices and its own
#:     protections (B18 §5.8, W7) — and letting a connection wizard silently
#:     de-energise a billing service would route around every one of them.
#:   * **NOTHING RE-ENTERS `pending`.** Work that has started cannot un-start;
#:     a service that is stuck goes `on_hold`, which is reversible, and one that
#:     is abandoned goes `cancelled`, which is not.
#:
#: `pending → energised` IS legal, and it is not an oversight: storm water is
#: *"assessed from records — no visit"* (§8.1) and has ZERO work orders, so
#: requiring it to pass through `in_progress` would invent a step the design
#: explicitly removed. Whether the gate has passed is task 6.8's question, not
#: this table's.
SERVICE_TRANSITIONS: dict[str, frozenset[str]] = {
    SVC_PENDING: frozenset({SVC_IN_PROGRESS, SVC_ON_HOLD, SVC_ACTIVATED, SVC_CANCELLED}),
    SVC_IN_PROGRESS: frozenset({SVC_ON_HOLD, SVC_ACTIVATED, SVC_CANCELLED}),
    SVC_ON_HOLD: frozenset({SVC_IN_PROGRESS, SVC_ACTIVATED, SVC_CANCELLED}),
    SVC_ACTIVATED: frozenset(),
    SVC_CANCELLED: frozenset(),
}

# ── work orders ─────────────────────────────────────────────────────────────
#: B18 §8.2, verbatim: *"A template declares `scope`: per-premise · per-unit ·
#: per-asset."*
SCOPE_PREMISE = "per_premise"
SCOPE_UNIT = "per_unit"
SCOPE_ASSET = "per_asset"
WORK_ORDER_SCOPES: tuple[str, ...] = (SCOPE_PREMISE, SCOPE_UNIT, SCOPE_ASSET)

#: B18 §8.3's three modes. `we_schedule` is drawn and **⛔ deferred to R5** —
#: *"the Work module is R5 (OQ-249)"* — so selecting it raises rather than
#: half-implementing a dispatch board. The other two ship in v1 and differ only
#: in the right-hand columns of the same list, which is why mode is settable
#: PER ORDER: a utility that does its own water work and contracts out gas is
#: the normal case, not the edge.
MODE_WE_SCHEDULE = "we_schedule"
MODE_OUR_CREW = "our_crew"
MODE_EXTERNAL = "external"
WORK_ORDER_MODES: tuple[str, ...] = (MODE_WE_SCHEDULE, MODE_OUR_CREW, MODE_EXTERNAL)

#: B18 §8.3, verbatim: *"Outcomes: `passed` · `failed` (raises a follow-up and
#: puts the connection on hold) · `partially done` · `cancelled` · `waiting on
#: someone else`."* The CONSEQUENCES are task 6.6; these are the tokens.
OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_PARTIALLY_DONE = "partially_done"
OUTCOME_CANCELLED = "cancelled"
OUTCOME_WAITING = "waiting_on_someone_else"
#: FB-013 (`DEF-WRK-10641`, PO ruling (b) of 2026-10-28, decision log *"FB-013:
#: a cleared balance STOPS the money-check step"*) — the technician found the
#: balance cleared on a FRESH read at a step whose template declares a money
#: check, and closed the job without doing it: *"Not done — payment received"*.
#: A SIXTH token, widened in `ck_work_orders_outcome` by `work/0059`. The server
#: accepts it only with the phone's snapshot of that read (`money.paid_close_record`).
OUTCOME_NOT_DONE_PAID = "not_done_payment_received"
WORK_ORDER_OUTCOMES: tuple[str, ...] = (
    OUTCOME_PASSED,
    OUTCOME_FAILED,
    OUTCOME_PARTIALLY_DONE,
    OUTCOME_CANCELLED,
    OUTCOME_WAITING,
    OUTCOME_NOT_DONE_PAID,
)

#: ⚠ NOT DRAWN — the same disposition as the per-service states above. §5.4.6
#: gives `work_orders` a `state` column and the design never lists its values.
#: These five are the minimum the drawn columns imply (`blocked_by` implies
#: `blocked`; an outcome implies `completed`) and are REPORTED, not signed.
WO_PLANNED = "planned"
WO_IN_PROGRESS = "in_progress"
WO_BLOCKED = "blocked"
WO_COMPLETED = "completed"
WO_CANCELLED = "cancelled"
WORK_ORDER_STATES: tuple[str, ...] = (
    WO_PLANNED,
    WO_IN_PROGRESS,
    WO_BLOCKED,
    WO_COMPLETED,
    WO_CANCELLED,
)


# ── CR-070 wave G · WHERE THE TECHNICIAN IS (BR-WRK-023) ────────────────────
#: **A THIRD AXIS, AND THAT IS THE WHOLE POINT.** `state` above says whether the
#: work has happened; `outcome` says what the field reported. **Neither can say
#: where the technician is right now**, and that is the only question a
#: dispatcher's screen exists to answer. `BR-WRK-023`, CONFIRMED, `WM-14`,
#: blueprint §9 Figure 8.
#:
#: The two axes move independently and the tests say so (`US-WRK-024` TC-1):
#: assigning a job takes `dispatch_state` from *queued* to *scheduled* and
#: leaves `state` at *planned*, because nobody has done any work yet. Collapsing
#: them into one column would mean a job cannot be both *planned* (no work done)
#: and *en route* (a van is moving), which is the ordinary state of half a
#: dispatcher's morning.
#:
#: ⚠ `cancelled` and `complete` appear on BOTH axes and are NOT redundant. A job
#: whose `state` is `cancelled` was called off; a job whose `dispatch_state` is
#: `cancelled` has been taken off the run. The screen shows the dispatch axis and
#: the order detail (wave H) shows both.
DISPATCH_QUEUED = "queued"
DISPATCH_SCHEDULED = "scheduled"
DISPATCH_EN_ROUTE = "en_route"
DISPATCH_ON_SITE = "on_site"
DISPATCH_COMPLETE = "complete"
DISPATCH_ON_HOLD = "on_hold"
DISPATCH_CANCELLED = "cancelled"
DISPATCH_STATES: tuple[str, ...] = (
    DISPATCH_QUEUED,
    DISPATCH_SCHEDULED,
    DISPATCH_EN_ROUTE,
    DISPATCH_ON_SITE,
    DISPATCH_COMPLETE,
    DISPATCH_ON_HOLD,
    DISPATCH_CANCELLED,
)

#: The dispatch states an order is still OPEN in — what `Work-007` lists and
#: what the five tiles count over. Complete and Cancelled have left the run.
DISPATCH_OPEN_STATES: tuple[str, ...] = (
    DISPATCH_QUEUED,
    DISPATCH_SCHEDULED,
    DISPATCH_EN_ROUTE,
    DISPATCH_ON_SITE,
    DISPATCH_ON_HOLD,
)

#: IN THE FIELD, as the KPI tile means it — *en route or on site*.
DISPATCH_IN_FIELD_STATES: tuple[str, ...] = (DISPATCH_EN_ROUTE, DISPATCH_ON_SITE)


# ── CR-070 wave P · WHY THIS JOB EXISTS (BR-WRK-024) ────────────────────────
#: **THE FLOW STAMP.** `BR-WRK-024`: *"Every order carries its SOURCE — why it
#: was raised."* `Work-007`'s RAISED BY column draws eight of these; the other
#: six are the doors the product has grown since r10 was drawn.
#:
#: ⚠ **THE VOCABULARY LIVES HERE AND NOT IN WAVE `G`, DELIBERATELY** — that is
#: `DEF-WRK-3726`. `G1` declares `source` as *"the eight r10 sources + Move-out
#: · Assets · New Connect"*, and `G` lands BEFORE the waves that write into it,
#: so a lane building `G` to its own row would ship a vocabulary the flow doors
#: then cannot write to: a refusal at raise time, three waves downstream of its
#: cause. Wave `P` declares the whole set in the commit that adds the column and
#: amends `G1` in the same one.
#:
#: ⚠ **`move_in` IS ONE VALUE, NOT TWO, AND THE PLAN ROW SAYS FOUR WHERE THE
#: CODE HAS THREE NEW ONES.** r10's eighth source is drawn *Move-in wizard* and
#: wave `P`'s move-in door is the same fact — one flow, one moment, one reason a
#: job exists. Two tokens meaning one thing is how a report grows a column that
#: has to be added up by hand. So the four `P1` names are three new tokens plus
#: one that r10 already had under a longer label; the label is a catalogue key,
#: the token is this. Recorded in the decision log 2026-09-05.
SOURCE_DUNNING_AUTO = "dunning_auto"
SOURCE_ASSET_AGE_RULE = "asset_age_rule"
SOURCE_HIGH_USAGE_ALERT = "high_usage_alert"
SOURCE_PAYMENT_RECEIVED = "payment_received"
SOURCE_BILLING_EXCEPTION = "billing_exception"
SOURCE_COMPLIANCE_CALENDAR = "compliance_calendar"
SOURCE_DISPATCHER = "dispatcher"
SOURCE_MOVE_OUT = "move_out"
SOURCE_ASSETS = "assets"
SOURCE_NEW_CONNECT = "new_connect"
#: ── the five flows of `CR-070` §W.10, `US-WRK-039` ──────────────────────────
SOURCE_SERVICE_REQUEST = "service_request"
SOURCE_MOVE_IN = "move_in"
SOURCE_TRANSFER = "transfer"
SOURCE_RECONNECT = "reconnect"
#: ⚠ **A FIFTEENTH, AND IT IS A WIDENING RATHER THAN THE NARROWING
#: `DEF-WRK-3726` FORBIDS** (`CR-070` wave I, `metering/0052`, 2026-09-05).
#:
#: `BR-WRK-054` and `US-WRK-034` §5 both name `source = failed_outcome` for the
#: order a FAILURE produces, and `J66` draws it on `Work-007` as *Raised by:
#: Failed outcome · WO-4907*. The token did not exist: wave P closed the
#: vocabulary at fourteen and `ck_work_orders_source` refuses anything else, so
#: the chain would have been refused BY THE DATABASE at the moment a supervisor
#: pressed Accept — inside the acceptance transaction, taking the whole
#: acceptance down with it. Found by reading the tuple before writing the
#: chain, not by watching it fail.
#:
#: **The distinction `DEF-WRK-3726` actually draws is direction, and it is worth
#: stating because the two look alike in a diff.** A wave that DECLARES a
#: shorter list narrows the vocabulary and starts refusing writes that other
#: waves make — three sprints downstream of the cause. A wave that ADDS a token
#: refuses nothing that worked yesterday. So the CHECK is dropped and rebuilt in
#: `metering/0052` rather than the constraint being left to disagree with this
#: tuple, which is the one outcome nobody could debug: Python would accept the
#: raise and PostgreSQL would refuse the INSERT.
#:
#: ⚠ **IT IS NOT `dispatcher`.** The nearest existing token is what a lane in a
#: hurry would reach for, and it would be wrong in the place it costs most:
#: `EP-WRK-10`'s FIRST-TIME FIX counts return visits, and a follow-up filed as
#: *raised by a dispatcher* is a failure that vanishes from the one report
#: measuring failures.
SOURCE_FAILED_OUTCOME = "failed_outcome"
#: ⚠ **A SIXTEENTH, AND IT IS THE SAME WIDENING AS THE FIFTEENTH** — the
#: Reads→Work door (`metering/0056`, PO ruling 2026-09-14, verbatim *"please build
#: this"*, reversing that morning's `Q2` deferral).
#:
#: **WHY AN EXISTING TOKEN WAS NOT REUSED, JUDGED ONE BY ONE RATHER THAN BY
#: RESEMBLANCE**, because the cost of the wrong answer here is a silently wrong
#: REPORT and not an error:
#:
#:   * **`high_usage_alert`** is the closest and it is still wrong. It names a FLAG
#:     on a reading that ARRIVED and was too big. This door is dominated by the
#:     opposite case — a reading that did NOT arrive at all: `BR-MET-023` gives the
#:     Missing flag the fix actions *estimate · field-visit · skip*, `BR-MET-027`
#:     FORCES a visit on a third consecutive miss, and `BR-MET-062` forces one for a
#:     missing demand peak because an estimated peak is a dispute. Filing an absent
#:     read as a high-usage alert puts a number in the high-usage count that nobody
#:     measured.
#:   * **`billing_exception`** is the bill run's own token; nothing has been billed
#:     at the moment a clerk presses this.
#:   * **`dispatcher`** — see the warning directly above. It is not this either, for
#:     exactly the reason written there.
#:
#: So the honest token names the MOMENT, the way `move_out` and `new_connect` do:
#: **a meter read, or its absence, is why somebody has to go out.** `source_ref`
#: carries the METER's own number (`MTR-0463`), which is what a clerk quotes and
#: what `orders_from_flow_tally` can then count per meter — B14 rule 31's
#: human-facing number, never the asset uuid.
#:
#: ⚠ **AND IT IS THE FLOW KIND TOO.** `from_flows` stamps `source = flow_kind`, so
#: this token and `from_flows.FLOW_METER_READ` are ONE string rather than two that
#: have to agree.
SOURCE_METER_READ = "meter_read"
#: ⚠ **A SEVENTEENTH — THE DISCONNECT WIZARD'S CUT VISIT (`DEF-CUS-9631`,
#: `metering/0075`, 2026-10-05), AND THE SAME WIDENING AS THE TWO ABOVE.**
#: Step 3 asks *Who goes: Work order* per service point (`BR-CUS-1098`) and
#: nothing raised one. **WHY NOT `dunning_auto`:** that token is the *Disconnect
#: for non-pay* RULE's (a job nobody pressed for), it reads *Dunning · auto* on
#: every list, and four of the five cut reasons are not a debt at all (unsafe,
#: tampering, abandoned, the customer asked). It is also the word
#: `tests/test_cr138_p4_17_site_visit_refusal.py` watches for a collections site
#: visit, which this is not. **WHY NOT `reconnect`:** the opposite act. So the
#: honest token names the MOMENT: a disconnection. It is the flow kind too
#: (`from_flows.FLOW_DISCONNECT`), one string rather than two.
SOURCE_DISCONNECT = "disconnect"
#: ⚠ **AN EIGHTEENTH — A ROUTE FINDING (`BR-WRK-067`, PO 2026-10-22,
#: `work/0048`), THE SAME WIDENING AS THE THREE ABOVE.** A meter reader reports
#: a leak, a broken seal or a tampered meter on a route; a Work rule for that
#: finding kind raises the job at once, else a person raises it by hand from
#: the finding. **WHY NOT `meter_read`:** that token is a reading, or its
#: absence, sending somebody out — a leak at the kerb is neither, and folding
#: it in would put findings in the count of missed reads. **WHY NOT `NULL`
#: (the field raise's choice):** a job raised from a finding has a known
#: reason, and `Raised by` should say so. It is also the rule PROCESS key
#: (`rule_processes`), one string rather than two that have to agree.
SOURCE_ROUTE_FINDING = "route_finding"
WORK_ORDER_SOURCES: tuple[str, ...] = (
    SOURCE_DUNNING_AUTO,
    SOURCE_ASSET_AGE_RULE,
    SOURCE_HIGH_USAGE_ALERT,
    SOURCE_PAYMENT_RECEIVED,
    SOURCE_BILLING_EXCEPTION,
    SOURCE_COMPLIANCE_CALENDAR,
    SOURCE_DISPATCHER,
    SOURCE_MOVE_OUT,
    SOURCE_ASSETS,
    SOURCE_NEW_CONNECT,
    SOURCE_SERVICE_REQUEST,
    SOURCE_MOVE_IN,
    SOURCE_TRANSFER,
    SOURCE_RECONNECT,
    SOURCE_FAILED_OUTCOME,
    SOURCE_METER_READ,
    SOURCE_DISCONNECT,
    SOURCE_ROUTE_FINDING,
)

#: Which record a `source_ref` quotes, per source. Read by `from_flows` only —
#: the column is free text because these flows number themselves in six different
#: series and a FK per flow was refused (judgment 4: it would take `work_orders`
#: from four anchor columns to nine).
#:
#: ⚠ **SIX SINCE 2026-09-14, AND THE SIXTH QUOTES A METER RATHER THAN A FLOW
#: RECORD.** A reading has no *reading number* to quote and inventing one would be
#: a series nobody asked for, so `meter_read` puts the METER's own `asset_no`
#: here — the number a clerk says out loud and the one a tally can group by. It
#: is listed HERE rather than left out so that this tuple and
#: `from_flows.FLOW_KINDS` cannot quietly disagree about how many doors exist,
#: which is the only job this tuple has.
FLOW_SOURCES: tuple[str, ...] = (
    SOURCE_SERVICE_REQUEST,
    SOURCE_MOVE_IN,
    SOURCE_MOVE_OUT,
    SOURCE_TRANSFER,
    SOURCE_RECONNECT,
    SOURCE_METER_READ,
    SOURCE_DISCONNECT,
)


# ════════════════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════════════════
class Connection(models.Model):
    """One build — B18 §5.4. **Creates infrastructure; may finish with no
    account.**

    `state` IS A CACHE of `derive_connection_state()` and is written by
    `refresh_connection_state()` and by nothing else. See §1 of the module
    docstring for why it is stored at all: S86 filters the list by segment, and
    a derived state cannot be a `WHERE` clause.

    The three facts NO service can express are stored as timestamps rather than
    as extra state tokens, because each of them is a different question with a
    different answer — *when was it submitted*, *why is it held*, *when was it
    cancelled* — and a single `state` string can hold only one of them at a
    time.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: NULL until the `connection` series exists in the catalogue — REPORTED as
    #: a `numbering_series_missing` warning, never faked (see CONNECTION_SERIES).
    connection_no = models.TextField(null=True, blank=True)
    #: ⚠ CROSS-MODULE FK metering → customers, and a NEW one. B18 §5.4.6 draws
    #: it (`request_id`) and B2 §2 says cross-module FKs are the REVIEWED
    #: interface set — so this is REPORTED for that review rather than assumed
    #: into it. NULL is legitimate and common: B18 §2.1's six channels include
    #: builds a developer starts without a request record.
    service_request = models.ForeignKey(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="request_id",
    )
    #: ⚠ **NULLABLE SINCE `DEF-CUS-6109` (2026-09-21), AND ONLY WHILE THE BUILD
    #: HAS NOT BEEN SUBMITTED.** The PO ruled that approving an application into
    #: a new connection *"may create a new conenct request - as draft request"*
    #: and that the clerk finishes it in the wizard — where `BR-MET-112` says
    #: **nothing is written until the last button**. A request whose address has
    #: not resolved therefore raises a draft with **no premises**, and the
    #: address is created at commit exactly as it is for a build raised
    #: directly. Creating it at approval instead would leave a brand-new
    #: premises standing the moment a clerk abandons the wizard, and no screen
    #: in this product can find that wreckage (`commit_new_connect`'s docstring
    #: says so in as many words).
    #:
    #: ⚠ **THE GUARANTEE MOVED, IT DID NOT GO.**
    #: `ck_connections_premises_once_submitted` (metering/0059) refuses a
    #: SUBMITTED build with no address — keyed on `submitted_at`, which is the
    #: fact, and never on `state`, which is a cache `refresh_connection_state()`
    #: rewrites and which a cancel outranks.
    premises = models.ForeignKey(
        "metering.Premises",
        on_delete=models.PROTECT,
        db_column="premises_id",
        null=True,
        blank=True,
    )
    #: The CACHE. Never write it directly — `refresh_connection_state()` owns it.
    state = models.TextField(default=DRAFT)
    #: ⚠ **A DEFAULT, NOT A TRUTH — and NCT-01/NCT-02 are why.** The Work
    #: orders tab draws a **MODE** column PER ORDER, so how a job is run is a
    #: fact about the JOB. This column is the wizard's step-1 answer, COPIED
    #: onto each order as it is created and never read again.
    #:
    #: The rejected alternative was `order.mode or connection.mode` — a
    #: fallback, which reads like one truth and is two: editing this column
    #: would retroactively change how orders raised last week are described,
    #: and nothing would record that it had. A stamp cannot do that.
    #: `connection_mode()` below is the DERIVED reading for any screen that
    #: wants a connection-level answer: it reports what the ORDERS say.
    #:
    #: ⚠ **AND THIS DIVERGES FROM ONE CLAUSE OF B18 §5.4.9, DELIBERATELY AND ON
    #: THE RECORD (2026-08-25).** That section — captured from the same screens
    #: after this lane had built — settles finding 1 as *"Built on the order,
    #: nullable, inheriting the connection's"*, i.e. the fallback. **The DRAWN
    #: fact is only that MODE is a per-order column** (every row `Our crew`);
    #: *nullable* and *inheriting* are the capturing lane's inference, not
    #: something the picture shows, and this file infers differently:
    #:
    #:   * A mode describes WORK, and some of that work is finished. Under
    #:     inheritance, editing this column relabels an order completed in March
    #:     as `external` in April, with nothing recording that it moved. That is
    #:     the hazard `invoice_lines.tariff_version_id` is stamped to avoid, and
    #:     the same reasoning CLAUDE.md records as the locked-at-issue snapshot.
    #:   * §8.3's own economics point the same way: *"a utility that does its own
    #:     water work and contracts out gas is the normal case, not the edge"* —
    #:     so mixed is ordinary, and a column that is usually NULL and sometimes
    #:     not is a worse record of an ordinary thing than one that always says.
    #:
    #: ✅ **SETTLED 2026-08-25 AND §5.4.9 WAS CORRECTED, NOT THIS CODE.** The
    #: divergence was reported rather than resolved quietly, the capturing lane
    #: re-read its own capture, and the clause now reads that *"nullable,
    #: inheriting"* was an INFERENCE and not a drawn fact — the picture shows
    #: only that MODE is a per-order column. The stamp stands, and the design
    #: document and the code agree again. Kept here as the record of why, since
    #: the reasoning is the part that would otherwise be lost.
    mode = models.TextField(default=MODE_OUR_CREW)
    target_activation = models.DateField(null=True, blank=True)

    # ── CR-126-BRC07 · STEP 1's THREE ANSWERS, WHICH HAD NOWHERE TO LAND ────
    #: The blueprint's `OWNER AND SCOPE · STEP 1` block draws five rows. **Two
    #: of them are the owner's and are DERIVED by walking** — `Owner or
    #: developer` is the payer account's customer name and `External system
    #: reference` is that customer's legacy id, which is what p106 rules in as
    #: many words: *"Owner or developer — where it is edited: Account A-10088 —
    #: the name belongs to the account that pays."* **These three are the
    #: build's own and had no home anywhere**, which p107 also states: *"Owner
    #: type · prefix · external reference · scope — No path at all — the build
    #: row has no such columns."*
    #:
    #: ⚠ **THE WIZARD HAS COLLECTED ALL THREE ALL ALONG AND THE PRODUCT THREW
    #: THEM AWAY.** `scope` and `units_prefix` ride on the commit payload today
    #: and `commit_new_connect` answers with a stated absence saying nothing
    #: reads them (`DEF-CUS-5435`); `owner.kind` — the drawn *Owner type* — is
    #: dropped by `_owner_block_in_the_doors_language` before the payload ever
    #: reaches the accounts door. So the screen asked a clerk three questions
    #: and stored none of the answers.
    #:
    #: ── WHY THEY ARE THE BUILD'S AND NOT SOMEBODY ELSE'S ──────────────────
    #: `owner_type` is a CLASSIFICATION OF A RELATIONSHIP, not of a party: the
    #: same company is a developer on the estate it is building and a landlord
    #: on the block it already owns, so it cannot live on `customers` without
    #: one build's answer overwriting another's. It is deliberately NOT
    #: `customers.kind`, which is `person`/`company` and refuses all four of
    #: these words by name (`DEF-MET-5438`).
    #:
    #: `units_prefix` is how THIS build named its units. Its EFFECT already
    #: travels — `expandUnitPattern` bakes `Apt 1 … Apt 26` into 26 labels —
    #: and the prefix itself did not, so nobody adding a 27th flat next year
    #: can tell what the pattern was without reading a label and guessing.
    #:
    #: `scope` decides the build's SHAPE (how many units the pattern makes,
    #: whether a common area exists) and is the one field the screen validates
    #: and the server ignores entirely.
    #:
    #: ⚠ **NULLABLE, AND NO BACKFILL — hard-won law 3's shape for data.** NULL
    #: means *nobody was asked*, which is the truth on every build that exists
    #: today. Writing a default over them would be this migration answering a
    #: question three clerks were asked and never had recorded.
    owner_type = models.TextField(null=True, blank=True)
    units_prefix = models.TextField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)

    #: ── CR-126-BRC07 · THE BILL THIS BUILD RAISED, SO IT CAN FIND IT AGAIN ─
    #: `_post_connection_quote` has raised the quote as a REAL RECEIVABLE since
    #: 2026-09-16 and hands the invoice's id and number back on the commit
    #: RESPONSE — and nothing anywhere wrote either of them down. The only
    #: durable record is `service_request_fees`, stamped through
    #: `seams.mark_request_quote_invoiced`, which hangs off the REQUEST.
    #:
    #: ⚠ **THAT IS THE COLUMN THE PO's RULING OF 2026-09-21 REQUIRES.**
    #: Verbatim: an approved application *"may create a new conenct request …
    #: this request is new work and recognized seperately from applcaition and
    #: hence we should not make it dependent on applciation #"*. A build raised
    #: directly has no request, so with the invoice recorded only against the
    #: request such a build could never name its own bill — and `OUTSTANDING`,
    #: which the record's fifth tile draws, would be underivable for ever.
    #:
    #: A plain UUID rather than an FK: `invoices` is BILLING's table and the
    #: B11 F-3 deferred-FK convention already governs exactly this case one
    #: class down (`ConnectionService.gate_order_id`). Nothing here reads a
    #: billing model; the number and the money are asked for through the seam.
    quote_invoice_id = models.UUIDField(null=True, blank=True)

    # ── BR-MET-113 · the account every connection charge is tagged to ──────
    #: PO 2026-08-25, closing OQ-367: *"You will have to assign account number to
    #: owner and tag everything to account number"*.
    #:
    #: ✅ **THIS IS WHY THE RULING MATTERS MORE THAN IT LOOKS.** New Connect's
    #: step 7 offers three debtors for the quote — *the connection itself* · *the
    #: customer created at step 1* · *each unit's first bill* — and only the
    #: middle one named a party that exists at confirm. A charge floating on a
    #: `connections` row would have needed a **second, parallel money path**: a
    #: payable that is not an invoice, settled by a payment referencing no
    #: account. B4's ❄️ FROZEN math is account-shaped, the ledger posts against
    #: accounts, and hard rule 7 wants an entity to name — so every rule saying
    #: *"the account"* would have grown a silent exception. **This column means
    #: there is ONE money path.**
    #:
    #: ⚠ **Cross-module FK, customers→metering's mirror image** (B2 §2's reviewed
    #: interface set). It is the reverse direction of `accounts.unit_id` and is
    #: named here rather than added to `accounts`, because a connection has at
    #: most one payer and an account pays for many things.
    #:
    #: ✅ **`create_owner_account()` FILLS IT, AND HAS SINCE 2026-08-25.** This
    #: note said *"NOTHING FILLS IT AUTOMATICALLY YET — `OQ-373`"* until
    #: 2026-09-12 (`DEF-MET-5081`), **2,480 lines above the implementation, in
    #: this same file**. `OQ-373` is CLOSED → `BR-MET-116`; the function is at
    #: the bottom of this module and `commit_connection` calls it at step 4
    #: whenever the payload carries `create_owner_account`, which the wizard
    #: sends for any build whose owner is named (`NewConnectWizard.tsx:345`).
    #:
    #: ⚠ **THE OLD REASON WAS FALSE TWICE OVER AND IT REACHED A DESIGN
    #: DOCUMENT.** Measured on the running database 2026-09-12:
    #: `accounts.unit_id` is **nullable**, `ck_accounts_regular_has_unit` binds
    #: only `kind='regular'`, and `ck_accounts_anchored` accepts a premises
    #: anchor — so a `master` account need name no unit. `brazosbend` holds one
    #: such row today: `AC-2026-00052`, `kind='master'`, active, `unit_id` NULL,
    #: anchored on **`CON-26-0117`'s own premises**. The build this note said
    #: could have no owner account already has a master account at its address.
    #:
    #: ⚠ **IT IS STILL NULL ON ALL 8 `brazosbend` CONNECTIONS, FOR TWO REASONS
    #: THAT ARE NOT THIS ONE.** The seed writes connection rows directly rather
    #: than through `commit_connection`, so step 4 has never run here; and the
    #: master door requires an IDENTIFIER (`BR-CUS-1024`, PO 2026-09-01) that
    #: the wizard's `owner` block does not carry — see `create_owner_account`'s
    #: own body, which states that refusal, and `DEF-MET-5093`. A NULL here is
    #: therefore *"no owner account on this build yet"* and never *"the product
    #: cannot make one"*. `tag_charges_to_account()` still attaches an account
    #: that already exists; that half never changed.
    owner_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="owner_account_id",
    )
    #: The quote total from step 7, held as a FIGURE so the connection can state
    #: what is owed before anything is posted. 4 decimals stored, 2 displayed
    #: (hard rule 2, PO re-sign 2026-08-22); never a float, never cents.
    quote_total = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    #: The three facts the services cannot express — the STORED half of §1.
    submitted_at = models.DateTimeField(null=True, blank=True)
    held_at = models.DateTimeField(null=True, blank=True)
    #: NCT-01's `WAITING ON` column — a short free noun (`permit` · `materials`
    #: · `inspection`), or NULL, which the list renders `—` and the detail
    #: renders *"Nothing / not blocked"*.
    #:
    #: ⚠ **IT IS NOT THE HOLD'S REASON, AND THE SCREEN IS WHY.** This started
    #: life as `hold_reason` on the reading that a build only waits when it is
    #: held. NCT-01 refutes that in two of its five rows: `CON-26-0121` is
    #: **In progress** waiting on `materials` and `CON-26-0126` is **Partly
    #: energised** waiting on `inspection` — neither is On hold. Only
    #: `CON-26-0119` is both (On hold · `permit`). So waiting-on is an
    #: INDEPENDENT AXIS from state, exactly as the list draws it: two columns,
    #: side by side. The KPI tile confirms it — *"WAITING ON INSPECTION 2"*
    #: counts `CON-26-0126` and `CON-26-0117`, which have different STATES and
    #: the same waiting-on.
    waiting_on = models.TextField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)
    #: BR-TEN-057 — the sample tag on the OWNING row, so BR-TEN-061's sweep can
    #: delete on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    #: ── `DEF-CUS-8021` · CLAUDE.md HARD RULE 6 ON THE NEW CONNECT COMMIT ────
    #: `core.idempotency.new_connect_commit_key(submit_token=…)`, which is
    #: `"new-connect|<the wizard's per-build token>"`. NULL for every build
    #: made by a caller that sends no token — the seeder, a test, an approval
    #: — and the partial unique index below is why that is safe: two NULLs are
    #: not a duplicate of each other. The shape, and what it deliberately does
    #: NOT protect, are argued in that function's own docstring; this column is
    #: only its home.
    commit_key = models.TextField(null=True, blank=True)
    #: **The FIRST press's answer, returned verbatim to the second.**
    #:
    #: ⚠ **RULE 6 ASKS FOR THE FIRST RESULT AND NOT FOR AN ERROR**, and the
    #: commit's answer is not re-derivable: `manifest` counts what THAT press
    #: MADE (`units: 26`, `meters: 20`, `messages: 0` with its refusals), and
    #: a recount later would answer what EXISTS, which is a different fact the
    #: moment anybody adds a unit. The precedent is `bill_runs`, where the
    #: replay returns the persisted RUN ROW; a persisted response is the same
    #: move for a door whose answer no table already holds.
    commit_result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "connections"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "connection_no"],
                condition=Q(connection_no__isnull=False),
                name="uq_connections_tenant_no",
            ),
            # `DEF-CUS-8021` — the DATABASE half of hard rule 6. The lookup in
            # `commit_new_connect` is the ordinary path; this is what holds
            # when two presses race past it in the same millisecond, and it is
            # the layer that actually ensures the guarantee. PARTIAL, so every
            # build committed without a token (NULL) is unaffected.
            models.UniqueConstraint(
                fields=["tenant", "commit_key"],
                condition=Q(commit_key__isnull=False),
                name="uq_connections_commit_key",
            ),
            # `DEF-CUS-6109` — a DRAFT may have no address; a SUBMITTED build
            # may not. Keyed on `submitted_at` and never on `state`: see the
            # `premises` field's own note above for why the cache cannot carry
            # this guarantee.
            models.CheckConstraint(
                check=Q(submitted_at__isnull=True) | Q(premises__isnull=False),
                name="ck_connections_premises_once_submitted",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "state"], name="ix_connections_tenant_state"),
            models.Index(
                fields=["tenant", "target_activation"], name="ix_connections_tenant_target"
            ),
        ]


class ConnectionService(models.Model):
    """One service, at one unit, on one connection — **the stored truth about
    where this build has got to** (B18 §5.4.6 `connection_services`).

    *"Electric can be billing while gas waits on its pressure test"* is the whole
    reason this row exists rather than a `services` array on the connection: the
    services do not advance together, and the connection's own state is a
    reading of these rows (`derive_connection_state`), never a second opinion.

    `unit` is nullable because not every service is per-unit — a per-premise
    main tap belongs to the build, not to any one of its 25 units (§8.2).

    `gate_order` is task 6.8's column, written by nobody here: it names the work
    order whose completion permits energisation, and the gate is NOT the same
    order for every service. **Gas gates on the light-up, not the meter set**
    (§8.1) — a lane that gates gas on the meter set will bill a customer with no
    gas.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        Connection, on_delete=models.PROTECT, db_column="connection_id", related_name="services"
    )
    unit = models.ForeignKey(
        "metering.Unit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="unit_id",
    )
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    state = models.TextField(default=SVC_PENDING)
    #: Set by task 6.8's gate check — a plain uuid rather than an FK because
    #: `work_orders` is created in the same migration and the pair would be a
    #: circular dependency for no gain; the B11 F-3 deferred-FK convention.
    gate_order_id = models.UUIDField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "connection_services"
        constraints = [
            #: One row per service per unit on a connection. The partial pair
            #: is needed because NULL never equals NULL in SQL, so a
            #: per-premise service would otherwise be insertable twice.
            models.UniqueConstraint(
                fields=["tenant", "connection", "unit", "service"],
                condition=Q(unit__isnull=False),
                name="uq_connection_services_unit",
            ),
            models.UniqueConstraint(
                fields=["tenant", "connection", "service"],
                condition=Q(unit__isnull=True),
                name="uq_connection_services_premise",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "connection"], name="ix_connection_services_conn"),
        ]


class WorkOrder(models.Model):
    """One job on a connection — B18 §5.4.6 `work_orders`, §8 the coupling.

    **Multi-unit work BATCHES by default** (§8.2): 500 Main Street's 25 units
    produce SEVEN orders, not seventy-six, because a per-unit meter set batches
    into crew days. The batching arithmetic is task 6.4; this table is what it
    writes into, and `scope` is the column it reads.

    `mode` is nullable and falls back to the connection's — §8.3's *"mode is
    settable per order, not only per connection"*.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    order_no = models.TextField(null=True, blank=True)
    #: ⚠ **NULLABLE SINCE `metering/0044` (CR-070 wave A, BR-WRK-006, `WM-01`).**
    #: This was NOT NULL — *"every work order in the product must belong to a
    #: new-connection build"* — so a leak investigation, a meter exchange or a
    #: backflow test on an EXISTING meter could not be recorded at all. An order
    #: now stands on at least one of four anchors: this connection, `premises`,
    #: `account` or `asset`, and `ck_work_orders_has_anchor` (Meta, below) is
    #: what stops it floating free of every record. Written by
    #: `create_work_order`, whose Python refusal comes first and whose CHECK is
    #: the backstop (US-WRK-001 TC-3, proved on PostgreSQL).
    connection = models.ForeignKey(
        Connection,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="connection_id",
        related_name="work_orders",
    )
    #: BR-WRK-006's second anchor — the premises a job is AT when there is no
    #: build (`77 Cedar Ct`, a leak investigation). Metering's own table, so
    #: not a cross-module FK.
    premises = models.ForeignKey(
        "metering.Premises",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="premises_id",
        related_name="work_orders",
    )
    #: ⚠ CROSS-MODULE FK metering → customers, and a NEW one (B2 §2 reviewed
    #: set, Addendum r23): the third anchor — the account a job is FOR (a
    #: move-out's final read, a reconnect). A POINTER, never a write: nothing
    #: in metering or work changes an account row through it.
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
        related_name="+",
    )
    #: The job's kind, as the template named it (*"meter set"*, *"light-up"*).
    #: Free text and not an enum: §8.1's sets are the USUAL ones, tenant-editable
    #: through `work_order_templates`, and an enum here would make a tenant's own
    #: step unrepresentable.
    type = models.TextField()
    #: ⚠ CROSS-MODULE FK metering → work, added by `metering/0045` (CR-070 wave
    #: C, `BR-WRK-017`, `WM-04`). The job-type CATALOGUE, **beside** the free
    #: text above and not replacing it: two clerks typing *Meter set* and
    #: *Meter Set* is what the catalogue exists to stop, and an existing order
    #: keeps its typed words until something matches them. `US-WRK-007` TC-6 is
    #: explicit that nothing is guessed — an unmatched string stays a string.
    #: When the free-text column retires is the blueprint's §16 to say
    #: (`03-field-map.md` §3 row 5), and it is not this wave's to decide.
    type_ref = models.ForeignKey(
        "work.WorkOrderType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="type_id",
        related_name="work_orders",
    )
    scope = models.TextField(default=SCOPE_PREMISE)
    service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    unit = models.ForeignKey(
        "metering.Unit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="unit_id",
    )
    #: ⚠ CROSS-MODULE FK metering → assets, and a NEW one (B2 §2 reviewed set).
    #: §5.4.6 draws it; REPORTED for that review.
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="asset_id",
    )
    #: §8.3 *"Dependencies: blocked-by · parallel · cross-service"*. Self-FK, so
    #: a gas light-up can be blocked by its own pressure test AND a sewer
    #: connection by a water tap on another service — task 6.5.
    blocked_by = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, db_column="blocked_by"
    )
    #: ⚠ **CR-070 wave I (`metering/0052`) — *WHY* THIS ORDER EXISTS, WHICH IS
    #: NOT THE SAME FACT AS `blocked_by` DIRECTLY ABOVE, AND THAT IS THE WHOLE
    #: REASON THERE ARE TWO COLUMNS.**
    #:
    #:   * `blocked_by` = *do not start me yet.* SEQUENCING. It stops being
    #:     interesting the moment the blocker finishes, and every wave that
    #:     orders work writes it — a gas light-up blocked by its own pressure
    #:     test is an ordinary two-step job and nothing failed.
    #:   * `follows_order` = *I exist BECAUSE that one failed.* PROVENANCE.
    #:     Permanent, written only by `BR-WRK-054`'s consequence chain, and it is
    #:     what `EP-WRK-10`'s FIRST-TIME FIX counts — *"share of orders with no
    #:     follow-up pointing at them; 88%"*.
    #:
    #: **Derive that percentage from `blocked_by` and it is wrong every month,
    #: quietly**: every ordinary sequenced job would count as a return visit, and
    #: nothing on the report would show it. `03-field-map.md` §3 row 18 says *"the
    #: follow-up names what failed"* in exactly those words, and this is the
    #: column that carries it.
    follows_order = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="follows_order_id",
        related_name="follow_ups",
    )
    state = models.TextField(default=WO_PLANNED)
    outcome = models.TextField(null=True, blank=True)
    #: NOT NULL — stamped at creation from the payload, or from the
    #: connection's step-1 default. §8.3: *"mode is settable per order, not only
    #: per connection"*, and NCT-01's Work orders tab draws it per row.
    mode = models.TextField(default=MODE_OUR_CREW)
    #: ⚠ **NOT IN B18 §5.4.6's COLUMN SET — added from the SCREEN**, which is
    #: the reference (PO 2026-08-16). NCT-01 draws the gate as a 🚩 on the
    #: ORDER's name (`WO-4902 Meter set · electric 🚩`), on two of five orders.
    #: The flag is declared per TEMPLATE and shows on the order it produced, so
    #: the order needs both the link and the answer:
    #:
    #:   * `template` is PROVENANCE — nullable, because an ad-hoc order added
    #:     through NCT-02's `Add work order` has no template behind it.
    #:   * `is_gate` is STAMPED at creation, not read through the FK, for the
    #:     reason `invoice_lines.tariff_version_id` is stamped: a tenant editing
    #:     a template must not silently change whether work already in the field
    #:     is the thing that permits energisation. What gated this build is what
    #:     gated it on the day the order was raised.
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="template_id",
    )
    #: ── CR-070 wave D · `US-WRK-018`, `BR-WRK-008` ─────────────────────────
    #: **WHICH VERSION OF THE TEMPLATE THIS ORDER WAS RAISED FROM.** Stamped
    #: once, at the raise, and never changed — the same posture `is_gate`
    #: above already takes, and for the same reason: publishing v2 of a
    #: template must not rewrite what a crew was told to do in January.
    #: NULL on the orders raised before this column existed and on every
    #: ad-hoc order, which carries no template at all.
    template_version = models.IntegerField(null=True, blank=True)
    is_gate = models.BooleanField(default=False)
    #: *"utility may use our work order system or they mght do it outside of our
    #: system and record the details in system"* (PO, §8) — `external` mode's
    #: whole payload is their reference, the date, the outcome and a file.
    external_ref = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attachment_ref = models.TextField(null=True, blank=True)

    # ── BR-MET-110 · what the field sent, who accepted it, and when ────────
    #: ⚠ **THESE THREE COLUMNS WERE RECORDED AS OWED ON 2026-08-25 AND ARE THE
    #: REASON BR-MET-110 SHIPPED "schema owed".** PO verbatim: *"Work order will
    #: send the data and confirm from field; utility staff will review these
    #: work order, accept them and use data from them to activate these
    #: services or confirm the installation is completed."*
    #:
    #: **Three steps, and the MIDDLE one is the rule.** `outcome`,
    #: `external_ref`, `completed_at` and `attachment_ref` above were enough to
    #: say an order FINISHED. They could not say **what the field sent**, **who
    #: reviewed it** or **when it was accepted** — and the acceptance is the
    #: human act standing between a field report and a customer's supply going
    #: live. Hard rule 7's discipline applies to it for the same reason it
    #: applies to money: somebody decided, and the record must name them.
    #:
    #: ⚠ **AND SINCE `BR-MET-115` (the same day) THIS IS ALSO WHAT SENDS THE
    #: CUSTOMER THEIR LETTER.** One human act, one auditable moment, three
    #: consequences: data accepted, service activated, customer told. A column
    #: that was merely owed is now load-bearing in three directions.
    #:
    #: `field_data` is a JSON document and deliberately NOT a set of columns:
    #: what a crew sends back differs per service and per template (a meter
    #: serial, a pressure reading, a photo reference, a signature), and
    #: BR-MET-109 makes the templates the utility's own — so a fixed column set
    #: would be us deciding what a utility may collect.
    field_data = models.JSONField(null=True, blank=True)
    #: WHO accepted it. Nullable because an order can be completed and not yet
    #: reviewed — that gap IS the review queue, and a NULL here is the only
    #: thing that says an order is waiting for a person.
    accepted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="accepted_by",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    #: ── CR-070 wave P · `BR-WRK-024`, `US-WRK-039` ────────────────────────
    #: **WHY THIS JOB EXISTS.** `Work-007` draws it as RAISED BY; a report that
    #: groups by it answers *how much of the crew's week is dunning and how much
    #: is people moving house*. NULL on every order raised before this column
    #: existed and on an order raised from a door that has no flow behind it —
    #: an absence, never a guess (the `type_ref` posture directly above).
    source = models.TextField(null=True, blank=True)
    #: **THE FLOW RECORD'S OWN NUMBER** — `SR-…`, `MVO-…`, `MVI-…`, `TRF-…`,
    #: `DSC-…`. Text, and deliberately not five nullable FKs: judgment 4 of the
    #: 2026-09-04 plan (*"a link that is only ever read to print a reference"*)
    #: worked the alternative and it takes this table from four anchor columns
    #: to nine and `ck_work_orders_has_anchor` from a four-way CHECK to a
    #: nine-way one. **The order stands on the anchor it already has** — the
    #: account it closes, the premises the request resolved to — and this column
    #: is how a clerk holding one finds the other.
    source_ref = models.TextField(null=True, blank=True)
    # ── CR-070 wave G · THE TWELVE DISPATCH COLUMNS ───────────────────────────
    #: `03-field-map.md` §3 rows 6–15, `WM-14`/`WM-15`/`WM-28`, `metering/0050`.
    #: Every one of them is NULLABLE or defaulted, because every order that
    #: exists at this migration was raised before a dispatcher screen existed and
    #: inventing a promise, an area or an owner for a real job is worse than
    #: drawing a dash (the `source` posture directly above).
    #:
    #: ⚠ **THEY ARE ON `work_orders`, WHICH IS METERING'S TABLE, SO THE MIGRATION
    #: IS METERING'S** — `metering/0044`, `0045` and `0049` for the same reason.
    #: Django resolves `model_name` inside the migration's own app, so an
    #: `AddField` on `workorder` written into `apps/work/migrations` raises before
    #: it can run. `10-execution-plan.md` `G1` says `work/000N`; it is amended in
    #: the commit that lands this, exactly as wave P amended `P1`.
    #:
    #: **THE PROMISE.** `BR-WRK-018` — a priority carries SLA hours and `due_at`
    #: defaults to the raise time plus them. STAMPED at the raise, never derived
    #: on read: `US-WRK-008` TC-4 is explicit that moving Urgent from 4 h to 2 h
    #: must not move a job already in the field. That is `is_gate`'s posture and
    #: `invoice_lines.tariff_version_id`'s, one more time.
    priority = models.ForeignKey(
        "work.WorkPriority",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="priority_id",
        related_name="work_orders",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    #: The appointment window a customer was promised — *08:00–12:00*. Two
    #: columns and not a range type, because the API, the phone and every screen
    #: read the two ends separately and a range would be decomposed at every one.
    window_start = models.DateTimeField(null=True, blank=True)
    window_end = models.DateTimeField(null=True, blank=True)
    #: `BR-WRK-023` — the third axis. NOT NULL with a default, unlike everything
    #: else in this block: every order that exists is somewhere on the run, and
    #: an order with no dispatch state is not a fact about the world, it is a
    #: column nobody filled in. Backfilled by `metering/0050` from `state`.
    dispatch_state = models.TextField(default=DISPATCH_QUEUED)
    #: WHICH RULE RAISED IT — `BR-WRK-024`'s second half, *"a rule-raised order
    #: also stamps the rule"*. A plain uuid, and it STAYS one: the B11 F-3
    #: deferred-FK convention `gate_order_id` above already uses — *"a uuid
    #: column, NO cross-module constraint"* — because `work_order_rules` is
    #: Work's table and a constraint would be a new metering → work FK, which is
    #: B2 §2's reviewed interface set and not a build lane's to add.
    #: `work/0020`'s docstring records why it adds none (`DEF-WRK-4082`: this
    #: comment predicted that migration would add the FK until 2026-10-05).
    rule_id = models.UUIDField(null=True, blank=True)
    #: ⚠ **A CACHE OF THE LATEST ASSIGNMENT, AND `work_order_assignments` IS THE
    #: RECORD** (`03-field-map.md` §3 row 12, verbatim: *"a cache"*). Nothing
    #: reads these two to answer *who has had this job* — that is the append-only
    #: history, and `apps/work/dispatch.py` writes the row FIRST and refreshes
    #: these SECOND, inside one transaction, so a cache can never be ahead of the
    #: record it caches.
    #:
    #: Both nullable and at most one set: a job goes to a person or to a crew,
    #: never to both (`ck_work_orders_one_assignee`, Meta below). A contractor is
    #: a `crews` row of kind `contractor` — wave F's decision, not a third column.
    assignee_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="assignee_technician_id",
        related_name="work_orders",
    )
    assignee_crew = models.ForeignKey(
        "work.Crew",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="assignee_crew_id",
        related_name="work_orders",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="assigned_by",
        related_name="+",
    )
    #: How long this job was expected to take, COPIED from the job type at the
    #: raise (`work_order_types.est_duration`). A `DurationField` and not an
    #: integer of minutes, which is what the catalogue column it is copied from
    #: already is — hard rule 3 is satisfied by the TYPE here rather than by a
    #: name suffix, because a `timedelta` cannot be read in the wrong unit.
    #: Copied rather than joined for `template_version`'s reason: re-timing a job
    #: type must not rewrite how long a crew was told a job in the field would
    #: take. It is what wave `F`'s UTILISATION and wave `N`'s *avg vs estimate*
    #: are measured against.
    est_duration = models.DurationField(null=True, blank=True)
    #: ⚠ **CR-070 wave I (`metering/0052`) — THE SENTENCE A DISPATCHER WRITES FOR
    #: THE CREW**, `03-field-map.md` §3 row 17, `WS-21`: *"Dog on property — use
    #: side gate. Customer notified 08:00."* Free text on purpose; the whole
    #: value of it is that it carries what no column anticipated.
    #:
    #: **IT IS ONE OF THREE SENTENCES ABOUT ONE JOB AND THEY MUST NOT BE MERGED.**
    #: This is the OFFICE talking to the FIELD. `field_data` (`BR-MET-109`,
    #: free-shaped) is the field talking back. What the CUSTOMER said belongs to
    #: the request that raised the order. They read alike, they are written by
    #: three different people at three different times, and folding any two of
    #: them together loses who said it — which on a *use the side gate* note is
    #: the difference between an instruction and a report.
    #:
    #: Carried to the phone unchanged (`US-WRK-042`), which is why a lane must
    #: not start putting structure into it.
    technician_notes = models.TextField(null=True, blank=True)
    #: ⚠ CROSS-MODULE FK metering → tenancy. `BR-WRK-022`, verbatim: *"Areas are
    #: `tenancy.Area`. Work references the existing lookup … it never duplicates
    #: it."* `US-WRK-011`'s whole content is that this is a POINTER and the Area
    #: filter's options come from the utility's own list through the seam.
    area = models.ForeignKey(
        "tenancy.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="area_id",
        related_name="+",
    )
    # ── CR-070 wave N · `US-WRK-051`, `BR-WRK-020` · `03-field-map.md` §3 row 19 ──
    #: **WHAT AN HOUR ON THIS JOB COST, FROZEN AT CLOSE.** `labour_rates` is
    #: append-only and one-current-per-role, so the rate a report needs can
    #: always be found by date — and it is stamped here anyway, for the reason
    #: `is_gate` and `template_version` above are stamped: a report must be
    #: reproducible from the ORDER, not from a join whose other side a
    #: supervisor may edit, supersede or delete next April.
    #:
    #: ⚠ **`US-WRK-051` TC-3 IS THE WHOLE POINT.** The rate moves from
    #: `48.5000` to `50.0000` on 1 April; `WO-4822`, closed 15 March, still
    #: prices at `48.5000`, and so do the 184 exchanges that closed before it.
    #: NULL on every order closed before this column existed and on every
    #: order that has not closed — a snapshot of a rate that was never taken
    #: is not zero, it is absent, and `costing.py` refuses rather than
    #: pricing an hour at nothing.
    labour_rate_snapshot = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    #: WHICH role's rate that was — `field_technician`, `contractor:<crew_id>`.
    #: Text for `labour_rates.role`'s reason: a utility names its own roles.
    labour_role = models.TextField(null=True, blank=True)
    #: HOW LONG THE CREW WERE THERE, in whole minutes, stamped at CLOSE beside
    #: the rate above — `metering/0053`, `DEF-WRK-4124`.
    #:
    #: ⚠ **`apps/work/costing.py` HAS READ THIS ATTRIBUTE SINCE THE DAY IT WAS
    #: WRITTEN AND THE COLUMN DID NOT EXIST.** `getattr(order, "minutes_on_site",
    #: None)` cannot fail, so every report priced its labour at *we cannot say*
    #: and no report has ever carried a labour line. That is why `WO-4822` reads
    #: `96.22` and the wave's signed figure is `138.42`.
    #:
    #: NULL is *not closed*, or *closed with no recorded arrival*. It is not
    #: zero: `0` minutes states that nobody was there.
    minutes_on_site = models.IntegerField(null=True, blank=True)
    # ── CR-168-BRC10 P0.2 / P0.3 · `metering/0071` ─────────────────────────
    #: **THE TECHNICIAN'S OWN ACCEPTANCE, AND IT IS NOT `accepted_by`.**
    #: `accepted_by`/`accepted_at` above are the OFFICE's acceptance of the
    #: FIELD's result (`BR-MET-110`'s human act). These say whether the person
    #: given the job took it — *accepted 07:42*, or *declined: van in the shop*
    #: — which the field app writes (P4.7) and the office reads (P4.1). Two
    #: different people, two different acts; one column for both would let a
    #: technician's tap read as a supervisor's sign-off on a money path.
    #: ⚠ Cross-module FK metering → work (`technicians`), beside
    #: `assignee_technician` in the reviewed set.
    accepted_by_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="accepted_by_technician_id",
        related_name="+",
    )
    accepted_at_technician = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    declined_reason = models.TextField(null=True, blank=True)
    #: **WHY IT IS OFF THE RUN, AND WHEN IT COMES BACK** (P0.3). A tenant lookup
    #: (`work_hold_reasons`, judgment J1), never a CHECK list. Set by Work's
    #: hold and cleared by its resume, through the seam; NULL whenever the job
    #: is not on hold.
    hold_reason = models.ForeignKey(
        "work.WorkHoldReason",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="hold_reason_id",
        related_name="+",
    )
    hold_expected_return_on = models.DateField(null=True, blank=True)
    #: When the CURRENT hold began, and how long every earlier hold lasted in
    #: whole seconds (the unit is in the name, hard rule 3). The SLA clock
    #: excludes held time (P5.2/P5.8): `held_seconds` is the closed holds and
    #: `now − held_at` the open one. 0, never NULL — a job never held was held
    #: for no time, which is a fact.
    held_at = models.DateTimeField(null=True, blank=True)
    held_seconds = models.IntegerField(default=0)
    is_sample = models.BooleanField(default=False)
    #: CR-161-BRC10 W4 — the utility's OWN fields on a work order (PO
    #: 2026-10-02, Part 2 row 10: *"New work order · Edit work order · Work
    #: order detail · Clerk / technician"*). Written by `create_work_order` when
    #: the New work order screen sends it (`WORK_NEW`) and by Work's edit door
    #: (`WORK_EDIT`, through `work.seams.metering_seam.save_order_fields`), both
    #: validated by tenancy's one validator. ⚠ The column is on METERING's
    #: table because `work_orders` is still metering's (`03-field-map.md` §4);
    #: Work owns the concept and writes it only through the seam. Never read by
    #: costing or any charge (BR-TEN-048). `metering/0067`.
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_orders"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "order_no"],
                condition=Q(order_no__isnull=False),
                name="uq_work_orders_tenant_no",
            ),
            # BR-WRK-006 (CR-070 wave A, metering/0044): at least one anchor —
            # connection · premises · account · asset. The database's own
            # refusal, so relaxing `connection_id` cannot create an order
            # attached to nothing even from a path that skips the service.
            models.CheckConstraint(
                condition=(
                    Q(connection__isnull=False)
                    | Q(premises__isnull=False)
                    | Q(account__isnull=False)
                    | Q(asset__isnull=False)
                ),
                name="ck_work_orders_has_anchor",
            ),
            # BR-WRK-024 (CR-070 wave P, metering/0049): `source` is NULL or one
            # of the fourteen. The CHECK is here rather than left to Python
            # because the whole point of DEF-WRK-3726 is that a LATER wave
            # narrows the vocabulary: a lane building wave G to its own row
            # would declare eleven values, and a database that already refuses
            # anything outside the fourteen makes that a failed migration
            # instead of a refusal at raise time in somebody else's sprint.
            models.CheckConstraint(
                condition=Q(source__isnull=True) | Q(source__in=WORK_ORDER_SOURCES),
                name="ck_work_orders_source",
            ),
            # BR-WRK-023 (CR-070 wave G, metering/0050): the third axis is one
            # of seven. In the database and not only in Python for the reason
            # `ck_work_orders_source` records one clause up — the phone (wave J)
            # and the rules engine (wave M) both write this column from code
            # this lane will never see.
            models.CheckConstraint(
                condition=Q(dispatch_state__in=DISPATCH_STATES),
                name="ck_work_orders_dispatch_state",
            ),
            # A job goes to a person or to a crew, never to both. The cache
            # columns are written by one service, but a bug that set both would
            # make the TECHNICIAN cell ambiguous with nothing raising.
            models.CheckConstraint(
                condition=Q(assignee_technician__isnull=True)
                | Q(assignee_crew__isnull=True),
                name="ck_work_orders_one_assignee",
            ),
            # `DEF-WRK-6737` — B18 §8.3's five outcomes, or none. The third
            # token column on this table and the only one that had no CHECK;
            # live data held `completed` (a STATE word) in it. `metering/0076`.
            models.CheckConstraint(
                condition=Q(outcome__isnull=True) | Q(outcome__in=WORK_ORDER_OUTCOMES),
                name="ck_work_orders_outcome",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "connection"], name="ix_work_orders_conn"),
            models.Index(fields=["tenant", "state"], name="ix_work_orders_tenant_state"),
            # The dispatcher's own read: open orders for one utility, and the
            # five tiles that count over the same window.
            models.Index(
                fields=["tenant", "dispatch_state"], name="ix_work_orders_dispatch"
            ),
            models.Index(fields=["tenant", "due_at"], name="ix_work_orders_due"),
            # ── DEF-MET-6881 (metering/0062) · THE RAISE DATE ──────────────
            # `created_at` is the RAISE, and it is `work_orders_dataset`'s
            # DEFAULT sort (`WORK_ORDER_SORT_COLUMNS["raised_on"]` is
            # `("created_at", "id")`), R33 Service Order Activity's declared
            # basis, the `from`/`to` filter's column, and the tiebreak of four
            # of the other five sorts. Four indexes stood on this table and not
            # one of them named it, so every page of a report dated by the raise
            # made PostgreSQL 16 read all 40,025 rows of a top-of-ICP tenant and
            # SORT them — `Sort Method: external merge  Disk: 4288kB`, spilled
            # to disk, on the deep pages.
            #
            # ⚠ **ASCENDING, WITH NO `DESC`, AND THAT IS THE POINT.** The
            # default direction is `desc` and PostgreSQL serves it by scanning
            # this index BACKWARD; ascending is the same index read forward. A
            # `(created_at DESC, id DESC)` index would serve one direction and
            # leave the other on a Seq Scan, which is one index doing half a
            # job. Measured both ways at 40,025 orders: `Index Scan Backward`
            # for `desc`, `Index Scan` for `asc`, no Sort node in either.
            #
            # ⚠ **`id` IS IN THE INDEX BECAUSE IT IS IN THE SORT.** Every tuple
            # in `WORK_ORDER_SORT_COLUMNS` ends in a unique column — a
            # bill-run-raised batch stamps a hundred orders in the same second,
            # so `created_at` alone is not a total order and a page over it can
            # show one order twice. Leave `id` out of the index and the planner
            # must still sort inside each equal run.
            #
            # ⚠ **`tenant` LEADS, like all four above.** RLS FORCE is on and
            # every read carries `tenant_id = current_setting('app.tenant_id')`;
            # an index that did not lead with it would not be usable under the
            # policy at all (hard rule 1).
            models.Index(
                fields=["tenant", "created_at", "id"], name="ix_work_orders_raised"
            ),
            # ── CR-168-BRC10 · `metering/0071` ─────────────────────────────
            # `GET /work-orders?status=complete` (judgment J3, P1.6): finished
            # jobs, newest close first, read under RLS so `tenant` leads.
            models.Index(
                fields=["tenant", "state", "completed_at"], name="ix_work_orders_completed"
            ),
            # The area walk and every premises-anchored read (P2.17).
            models.Index(fields=["tenant", "premises"], name="ix_work_orders_premises"),
        ]


class WorkOrderTemplate(models.Model):
    """The per-service default order set — B18 §5.4.6, §8.1. **Tenant-editable.**

    Seeding it with the ten sets is task 6.3 and this lane leaves the table
    EMPTY rather than seeding nine services and guessing the tenth. The one
    thing a seeding lane must not get wrong is written down where it will be
    read: **`is_gate` for GAS is the light-up, not the meter set.** Every other
    metered service is billable once the meter is set; gas is not, and a lane
    that copies electric's shape will bill a customer with no gas.

    `est_duration` is a `DurationField` — an interval carries its own unit, so
    there is no `_minutes` suffix to disagree with a caller (hard rule 3, the
    same reasoning that puts `unit_of_measure` in a column below).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    sequence = models.IntegerField(default=0)
    name = models.TextField()
    scope = models.TextField(default=SCOPE_PREMISE)
    est_duration = models.DurationField(null=True, blank=True)
    is_gate = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False)
    # ── CR-070 wave C (metering/0045) ──────────────────────────────────────
    # `BR-WRK-021` — the `service_template` number series (`ST-{0000}`) has
    # existed on Settings → Numbering since 2026-08-16 with NOWHERE TO WRITE.
    # This is the column. It is ALLOCATED ON PUBLISH (wave D), inside the
    # publish transaction, from the tenant's own series through
    # `core/numbering.py` — never faked and never renumbered (`BR-TEN-035`),
    # which is why it is nullable: the 24 seeded starters and every draft
    # predate their number and keep a NULL until they are published.
    template_no = models.TextField(null=True, blank=True)
    # `BR-WRK-017` — the job-type catalogue, beside the free-text `skill`/
    # `type` columns rather than replacing them. The retirement of the free
    # text is the blueprint's §16 to state (`03-field-map.md` §3 row 5), and a
    # column dropped before its replacement is populated is a data loss with a
    # migration number on it.
    type = models.ForeignKey(
        "work.WorkOrderType",
        on_delete=models.PROTECT,
        db_column="type_id",
        null=True,
        blank=True,
        related_name="templates",
    )
    # ── CR-070 wave D (metering/0048) · the header of a BUNDLE ─────────────
    # `BR-WRK-008`/`009`/`010`/`012` — the six columns a template needs once it
    # carries seven child collections and a version history. Every one of them
    # is Work's fact on metering's row: the table has not moved
    # (`03-field-map.md` §4) and a column added to a metering table is a
    # metering migration, which is the same reading `metering/0045` records.
    #
    # `skill_id` REPLACES the free-text `skill` (`03-field-map.md` §3 row 22).
    # It is a replacement rather than wave C's beside-it posture for `type`
    # because the free-text column was NULL on every row in this product —
    # nothing has ever written it — so there is nothing to preserve and
    # nothing to guess. `metering/0048` refuses to run if that is ever untrue.
    skill = models.ForeignKey(
        "work.WorkSkill",
        on_delete=models.PROTECT,
        db_column="skill_id",
        null=True,
        blank=True,
        related_name="templates",
    )
    safety_kit = models.ForeignKey(
        "work.WorkSafetyKit",
        on_delete=models.PROTECT,
        db_column="safety_kit_id",
        null=True,
        blank=True,
        related_name="templates",
    )
    crew_size = models.SmallIntegerField(default=1)
    #: `BR-WRK-012` — Deactivate stops NEW orders and leaves the old ones
    #: readable. It is never toggled by a `PATCH` on the header
    #: (`DEF-WRK-3579`): the two named routes are the only writers.
    active = models.BooleanField(default=True)
    #: **0 IS A DRAFT AND IT IS NOT A VERSION.** `BR-WRK-011` — publish is the
    #: one write, and a draft that has never been published has produced no
    #: version for an order to stamp. The first publish sets 1.
    version = models.IntegerField(default=0)
    #: `BR-WRK-013` — sewer, storm water and solar carry NO gate row and store
    #: WHY, so a test can assert an absence instead of inferring one.
    no_gate_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_templates"
        constraints = [
            # ⚠ **`uq(tenant, service, sequence)` IS GONE — `BR-WRK-010`.**
            # It is the blueprint's *"one structural blocker"* for templates:
            # a utility that wants *New connection* AND *Leak investigation*
            # for Water cannot have both, because the second one has to take a
            # sequence number in a list that is about the CONNECTION order.
            #
            # ⚠ **AND THE REPLACEMENT CARRIES `service`, WHICH THE RULE AS
            # WRITTEN DID NOT.** `BR-WRK-010` (PROPOSED) and `US-WRK-013` TC-2
            # both say `(tenant, name, version)`. Measured against the 24
            # CONFIRMED starters (`BR-WRK-013`, `sample_data.py:1889`) that key
            # cannot be created at all: **`Meter set` is seeded four times**
            # (electric, water, gas, thermal heat), **`Inspection` three times**
            # (gas, solar, thermal heat) and **`Service connection` twice**
            # (thermal heat, fire). A tenant-wide name key refuses the seed on
            # a fresh database and refuses this very migration on an existing
            # one. The rule's own PURPOSE — *"a utility holds New connection
            # and Leak investigation for Water at once"* — is satisfied
            # exactly by the four-column key, and TC-2's refusal (a second
            # *Leak investigation* v1 for the same service) still refuses.
            # Recorded as a judgment in the decision log, 2026-09-05.
            models.UniqueConstraint(
                fields=["tenant", "service", "name", "version"],
                name="uq_work_order_templates_name_version",
            ),
            # An issued number is unique to its tenant and never reused
            # (`BR-TEN-035`). NULLs do not collide in PostgreSQL, so every
            # unpublished template keeps its blank without fighting for it.
            models.UniqueConstraint(
                fields=["tenant", "template_no"],
                name="uq_work_order_templates_tenant_no",
            ),
            models.CheckConstraint(
                condition=Q(crew_size__gte=1), name="ck_work_order_templates_crew_size"
            ),
        ]
        indexes = [
            # `CR-168-BRC10` P3.23 (`metering/0071`) — the templates list pages
            # in SQL by active and name. On METERING's migration because this
            # is metering's model (§7.3 named `work/0031`; moved, with reason).
            models.Index(
                fields=["tenant", "active", "name"], name="ix_wo_templates_active_name"
            ),
        ]


class ServiceCharacteristic(models.Model):
    """**BR-MET-108** — one pricing characteristic of one unit's relationship to
    one service. A ROW per characteristic; NOT a column per service on `units`.

    See §2 of the module docstring for the full argument. The short form, and it
    is about money rather than tidiness: **a NULL column cannot say which kind
    of nothing it is.** *"Does not take storm water"* bills nothing; *"takes it
    and nobody recorded the impervious area"* is unpriceable and must refuse.
    A missing ROW is unambiguous.

    `unit_of_measure` is NOT NULL, and that is hard rule 3 doing the same job it
    does for consumption: container count, impervious square feet and a speed
    tier are three different units, and a quantity without its unit is
    unreadable. **The unit never goes in the key name** — `storm_impervious_sqft`
    is a unit nothing can validate, compare or migrate.

    ⚠ THE KEYS THEMSELVES ARE NOT SIGNED. BR-MET-108 says so in as many words.
    Nothing in this module enumerates them, and `required_characteristic_keys`
    refuses to answer which services require one.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    unit = models.ForeignKey("metering.Unit", on_delete=models.PROTECT, db_column="unit_id")
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    key = models.TextField()
    #: TEXT, deliberately. *"100/20 Mbps"* is a speed tier and not a number; a
    #: decimal column would refuse it or silently mangle it. `decimal_value()`
    #: is how a caller that needs arithmetic asks, and it refuses BY NAME.
    value = models.TextField()
    unit_of_measure = models.TextField()
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_characteristics"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "unit", "service", "key"],
                name="uq_service_characteristics_key",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "unit", "service"], name="ix_service_char_unit_service"),
        ]

    def decimal_value(self) -> Decimal:
        """The value as a number, or a REFUSAL naming what could not be read.

        ⚠ **THE PO'S 2026-08-25 RULING (*"Bill it as zero"*) DOES NOT REACH THIS
        METHOD, AND THE DISTINCTION IS THE WHOLE POINT.** That ruling is about a
        characteristic that was **never recorded** — nobody measured unit 12 —
        and `characteristic_for_pricing()` now prices that at zero and stamps it.
        **This method is about a value that IS recorded and is not a number:**
        somebody typed `"100/20 Mbps"`, which is a real answer to a real
        question and simply cannot be multiplied by a rate.

        Reading it as `0` would not be billing an absence at zero — it would be
        **discarding an answer the customer gave us**. So this still refuses, by
        name, carrying the key, the value and the unit so the message can say
        what was found. Not-recorded and not-a-number are different facts and
        must not collapse into one figure.
        """
        try:
            return Decimal(str(self.value).replace(",", "").strip())
        except (InvalidOperation, ArithmeticError, ValueError):
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-MET-108",
                message_key="metering.characteristic_not_numeric",
                params={"key": self.key, "value": self.value, "uom": self.unit_of_measure},
            ) from None


class ConnectionTodo(models.Model):
    """**BR-MET-114 — the "Outstanding work" list, and a HUMAN writes it.**

    PO 2026-08-25, verbatim: *"human will mark everything to start with"*,
    closing `OQ-369`.

    Step 9 of the New Connect wizard (`NCT-03.9`) draws three items under
    **`Outstanding work`** and one load-bearing sentence: *"3 things to finish —
    **none of them block creating the connection**."* The wizard **commits
    incomplete work on purpose** and carries the gaps forward as visible debt.

    **WHY A ROW AND NOT A QUERY, WHICH IS THE WHOLE RULING.** Two of the three
    drawn items are ABSENCES a query could recompute — *"50 meters still read
    'to assign'"*, *"impervious area recorded, but no assessment date"*. The
    third is not:

        Sewer on common area — "Left off, BECAUSE common area has no water
        service"

    That is **a decision somebody made and a reason they gave**, and no
    derivation can reconstruct a reason. Worse, a derivation would **re-raise it
    forever**: the sewer service genuinely is absent and always will be, so every
    recomputation would report the thing a person already decided. A human
    marking the list can say *"we chose this, here is why"*, and that sentence is
    the part worth keeping.

    ⚠ **"TO START WITH" IS PART OF THE RULING AND IS BUILT INTO THIS MODEL.**
    The PO scoped it: humans mark it **now**. Deriving CANDIDATES later — the
    system SUGGESTING *"50 meters have no number"* for a person to accept, amend
    or dismiss — is not excluded, which is why `source` exists and defaults to
    `human`. **What is NOT permitted is the system silently CLOSING an item a
    human opened**, because that is the reason half of item 3 disappearing
    again; `closed_by` is therefore NOT NULL-able-by-machine in practice — the
    service layer refuses a close with no actor.

    ⚠ **NOT A BLOCKER, BY DESIGN.** There is deliberately no `blocks_creation`
    flag. The screen says none of these block creating the connection, and a
    column that could say otherwise would invite a later lane to set it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        Connection,
        on_delete=models.PROTECT,
        related_name="todos",
        db_column="connection_id",
    )
    #: The short label — *"Meter numbers"*, *"Storm water figure"*.
    title = models.TextField()
    #: The sentence a person wrote, including the *because*. This is the field
    #: the ruling exists to protect; it is free text on purpose.
    detail = models.TextField(null=True, blank=True)
    #: `human` today. `suggested` is reserved for the later candidate-derivation
    #: the PO's *"to start with"* leaves open, so that a suggested row and a
    #: person's row are never confused once both exist.
    SOURCE_HUMAN = "human"
    SOURCE_SUGGESTED = "suggested"
    source = models.TextField(default=SOURCE_HUMAN)
    #: `CR-162-BRC10` (PO 2026-10-02, verbatim: *"in to do also keep notes -
    #: allow user to add notes"*) — the build's To-do tab holds NOTES as well.
    #: A note is free text a clerk leaves on the build; it is never done and
    #: never blocks anything. ⚠ **ONE TABLE, NOT `account_notes`**: a build has
    #: no account when it is a single-family home (Q1) and none at all before
    #: Create, so the account's notes cannot hold it (decision log 2026-10-02,
    #: CR-162-BRC10 row, judgment (e)). `metering/0065`; every row before it is
    #: a to-do, which is what the column's default says.
    KIND_TODO = "todo"
    KIND_NOTE = "note"
    KINDS = (KIND_TODO, KIND_NOTE)
    kind = models.TextField(default=KIND_TODO)
    marked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="marked_by",
    )
    marked_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="closed_by",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "connection_todos"
        indexes = [
            models.Index(fields=["tenant", "connection"], name="ix_conn_todo_tenant_conn"),
        ]
