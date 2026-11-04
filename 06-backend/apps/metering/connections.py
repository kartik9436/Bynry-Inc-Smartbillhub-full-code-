# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W6 — New Connect (design B18 §5.4 · §6.3 · §8 · §11 W6) ·
#           **the PO's five New Connect screens, 2026-08-25 (NCT-01 list ·
#           NCT-02 detail + its Units/Work-orders tabs)** — the screen is the
#           reference (PO 2026-08-16), and it MOVED three things: `mode` onto
#           the order, `is_gate` onto the order it produced, and `waiting_on`
#           into a column of its own beside STATE.
#           Tasks 6.1 (five tables + RLS), 6.2 (the connection state machine
#           PLUS a state per service), 6.9 (`service_characteristics`).
#           Screens: S86 (list) · S87 (8-step wizard) · S88 (detail) — none of
#           them built by this lane; this is the backend half only.
# Rules:    BR-MET-108 (a flat service's pricing characteristic is a ROW in
#           `service_characteristics`, keyed by unit and service — CONFIRMED
#           2026-08-25, HUMAN-REVIEW-PENDING) · BR-MET-104 (the characteristic
#           lives on the UNIT — PO 2026-08-24, closing OQ-348) ·
#           BR-TEN-035 (number series: allocate, never renumber) ·
#           BR-TEN-057 (the sample-data tag on the OWNING row) ·
#           BR-MET-048 (every metering change writes who/when/before→after) ·
#           CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE — migration 0027) ·
#           hard rule 3 (an explicit unit, ALWAYS — `unit_of_measure` is a
#           COLUMN and never a suffix on a key name) · hard rule 7 (audit)
# Questions: OQ-249 (is Work a tenth module? — the *"we schedule it"* dispatch
#           mode is R5 and is STUBBED here, not guessed) ·
#           ⚠ NO REGISTERED QUESTION covers WHICH characteristic keys exist,
#           their units of measure, or which services require one before a bill
#           can be produced. BR-MET-108's closing clause says exactly that and
#           no OQ was minted for it. This module therefore REFUSES by name
#           rather than choosing (see `required_characteristic_keys`), and the
#           lane reports that a question is OWED. Minting one from inside code
#           is what G8 clause B exists to catch.
# Tests:    06-backend/tests/test_w6_connections.py
# Impacts:  apps/metering/migrations/0026_cr030_w6_connections.py (the tables) ·
#           0027_rls_cr030_w6_connections.py (the policies) ·
#           apps/metering/models.py ⚠ MUST import this module for the model
#           registry to see these classes — NOT this lane's file, REPORTED, and
#           guarded RED by test_w6_the_app_registry_is_told_this_module_exists
# ───────────────────────────────────────────────────────
"""CR-030 W6 — New Connect: the connection, its per-service states, its work
orders, and the flat services' pricing characteristics.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and RLS policies are
CLAUDE.md 🔒 paths, and BR-MET-108 is itself CONFIRMED-not-ratified. AI-authored
2026-08-25 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). A row is owed in `12-governance/09-human-review-ledger.md`;
that file is not this lane's, so the row is reported for the orchestrator to
land — exactly as `metering/0025` did on 2026-08-24.

**WHY THESE CLASSES ARE NOT IN `apps/metering/models.py`.** The same reason
`apps/billing/correction_models.py` and `apps/payments/bankrec_models.py` each
record for themselves: two lanes editing one models module is how a migration
graph forks, and `metering/models.py` is 2,000 lines with three lanes in it this
week. `app_label` resolves to `metering` from the module path, the tables are
metering's own (B2 r4/r16 owner map — metering owns premises, units and service
points, so it owns what connects them), and folding it back into `models.py`
later is a move, not a redesign.

⚠ **AND THAT CARRIES ONE COST THIS LANE CANNOT PAY ITSELF.** Django's app
registry imports `<app>.models` and nothing else, so a model class in this file
registers only when something imports the module. Nothing on the startup path
does. MEASURED on this tree with `makemigrations --check --dry-run`: the
autodetector proposes **`Delete model Connection / ConnectionService /
ServiceCharacteristic / WorkOrder / WorkOrderTemplate`** — migration state holds
five tables the registry lacks, so the project sits in permanent drift with CI
proposing to drop them.

**THE FIX IS ONE LINE, IN A FILE THIS LANE DOES NOT OWN**, at the foot of
`apps/metering/models.py`, and `apps/rating/models.py:1628` already does exactly
this for `apps/rating/discounts.py` with the reason written beside it (*"Imported
for its SIDE EFFECT — importing the module is what registers its models"*):

    from apps.metering import connections  # noqa: E402,F401  (registers five models)

**THE ALTERNATIVE WAS CONSIDERED AND REJECTED, and the reasoning is here so the
next lane does not re-open it.** A sibling lane made its own tables
`managed = False` and wrote raw per-vendor DDL in a `RunPython`, which is
self-contained and needs nothing from anyone. It was not taken here because it
costs more than it saves: it removes five tables from Django's model state
PERMANENTLY, so every later column on them is hand-written DDL in two dialects
forever; it puts a `RunPython` into a migration that is otherwise free of the
DEF-639 hazard class (and which `test_w6_the_migration_leaves_tenant_context_
alone` asserts against); and it trades a LOUD one-line gap for a SILENT permanent
one. `tests/test_w6_connections.py::test_w6_the_app_registry_is_told_this_module_
exists` is RED until the line lands and green the moment it does — a known gap
that cannot be forgotten beats a workaround that cannot be seen.

════════════════════════════════════════════════════════════════════════════
1 · THE STATE MACHINE, AND WHY THE CONNECTION'S OWN STATE IS A CACHE
════════════════════════════════════════════════════════════════════════════
B18 §5.4.3 states it in one sentence: *"A connection does not finish when the
button is pressed. `Draft` · `Requested` · `In progress` · `Partly energised` ·
`On hold` · `Energised` · `Cancelled` — **with a status per service**, because

⚠ **EVERY "ENERGISED" IN THIS DOCSTRING IS THE WORD THE SCREENS DRAW, AND IS NO
LONGER THE PRODUCT'S WORD (CR-032, PO 2026-08-25).** The tokens below this
docstring read `activated` and `partly_activated`. The prose is left as drawn on
purpose: it is the record of what was handed over, and rewriting a quotation to
match a later ruling destroys the evidence that the ruling changed something.
**Read the constants for the product; read the prose for the drawing.**

electric can be billing while gas waits on its pressure test."*

Two states in one object is how they disagree. So there is ONE stored truth and
one derived view of it:

  * **STORED** — `connection_services.state`, one row per service (per unit
    where the service is per-unit), and three facts about the connection that no
    service can express: `submitted_at`, `held_at`/`waiting_on`, `cancelled_at`.
  * **DERIVED** — `derive_connection_state()`, a pure function of those. It is
    the only thing that decides what a connection's state IS.

`connections.state` is a COLUMN, and it is a CACHE of that function — written by
`refresh_connection_state()` and by nothing else. It is stored rather than
computed on read for one reason, and it is a screen reason: S86's segment strip
(`All · In progress · Waiting · Partly energised · Done`) filters the list, and
a derived state cannot be a `WHERE` clause without annotating every row of every
page. `test_w6_connections.py` asserts the cache equals the function after every
transition, so the two cannot drift silently — a stored figure whose agreement
with its source is not asserted is a comment (hard-won law 1).

**THE DERIVATION, and it reproduces all eight of B18 §5.4.8's seeded rows** —
which is the proof that it is the design's rule and not a rule of this file's
own invention:

    cancelled                                        → Cancelled
    not submitted                                    → Draft
    held                                             → On hold      (outranks
                                                        progress: CON-26-0119
                                                        is `5 of 9` AND On hold)
    every live service energised                     → Energised    (CON-26-0110)
    some live service energised, not all             → Partly energised
                                                        (CON-26-0117 `5 of 7`,
                                                         CON-26-0126 `3 of 9`,
                                                         CON-26-0128 `2 of 5`)
    some live service in progress, none energised    → In progress
                                                        (CON-26-0121 `2 of 5`,
                                                         CON-26-0122 `1 of 6`)
    otherwise                                        → Requested    (CON-26-0124
                                                        `0 of 7`)

A CANCELLED service is excluded from the tally rather than counted as unfinished
— a connection whose gas was cancelled and whose electric is live is Energised,
not Partly energised, because there is nothing left waiting.

✅ **CONFIRMED BY THE PO'S NCT-02 SCREEN (2026-08-25).** The per-service state
is drawn explicitly, as side-by-side blocks — `ELECTRIC Energised 1 of 1 units ·
Aug 18` — so a connection-service row carries its own state, a units-energised /
units-total count and an energised date, and the connection's own `Energised`
badge sits above two energised services. That is this design, drawn. The count
is `service_progress()` below; nothing about it is stored twice.

✅ **AND THE END STATE IS CONFIRMED TOO, WHICH MATTERS BECAUSE IT LOOKS LIKE A
BUG.** NCT-02's Units tab reads `[Vacant · service off]` with `ACCOUNT —` on a
build whose header says **Energised**. A new connect finishes with the supply
live, the unit vacant and NO ACCOUNT: infrastructure exists and nobody has moved
in. That is the end of this state machine, not an incomplete run — which is also
why `energised` is terminal here (taking a live service off is a disconnect, a
different record with its own ladder) and why no code in this module touches
occupancy or accounts.

⚠ **WHAT IS SIGNED HERE AND WHAT IS THIS FILE'S READING.** The SEVEN connection
states are B18 §5.4.3 verbatim. The stored PER-SERVICE set is not drawn as a
token list, and this file reads it as the same vocabulary MINUS
`partly_energised`: a stored row is one service AT ONE UNIT and cannot be partly
anything. `partly_energised` re-enters as a DERIVED reading over a service's
rows (`service_progress`), because a service across `CON-26-0117`'s 25 units
plainly can be part-done. Recorded rather than presented as law.

⚠ **NCT-01's SEGMENTS ARE NOT STATE TOKENS, AND THIS IS A CORRECTION TO A
SUMMARY THIS LANE WAS HANDED.** The tab's segments read `All · In progress ·
Waiting · Partly energised · Done`, which was passed to this lane as though
`state ∈ {In progress, Waiting, On hold, Partly energised, Energised, Done}`.
**The drawn rows refute it: not one of the five reads `Waiting` or `Done` in the
STATE column.** They read Energised, On hold, In progress, Partly energised —
four of §5.4.3's seven. `Waiting` and `Done` are SEGMENTS: filters over state
plus the `waiting_on` column, which the list draws as its own column beside
STATE. So no token was added to `CONNECTION_STATES`.

⛔ **AND THE SEGMENT RULE IS NOT DERIVABLE FROM THE DRAWING, SO IT IS NOT BUILT.**
`CON-26-0126` is **Partly energised** AND waiting on `inspection`; the segments
are drawn as one exclusive strip, and nothing says whether that row appears under
`Waiting`, under `Partly energised`, or under both. The KPI tiles plainly DO
overlap — *"PARTLY ACTIVATED 3"* and *"WAITING ON INSPECTION 2"* count the same
build twice — but a tile and a segment are not the same control. This module
therefore ships no `segment_for()`; it is task 6.12's screen and the question is
REPORTED as owed rather than answered by a guess about precedence.

════════════════════════════════════════════════════════════════════════════
2 · `service_characteristics` — BR-MET-108, AND WHAT IT REFUSES
════════════════════════════════════════════════════════════════════════════
BR-MET-108 (CONFIRMED 2026-08-25) fixes the SHAPE: a row per characteristic,
keyed by unit and service, `unit_id · service · key · value · unit_of_measure`.
Not a column per service on `units`.

**The deciding argument is about money, and it is worth restating where the
table is built.** A NULL column cannot say WHICH KIND OF NOTHING it is. On a
25-unit building where 20 units take trash + storm water + broadband and 5 take
trash only, a `storm_impervious_sqft` column holds NULL for those 5 — and that
NULL means either *"does not take storm water"* or *"takes it and nobody
recorded the area"*. **Those two price differently**: the first bills nothing,
the second is unpriceable and must REFUSE. One nullable column cannot tell them
apart, so the engine either prices an unrecorded impervious area at zero — under-
billing every one of those units, every month, silently — or refuses service a
customer is entitled to. A MISSING ROW is unambiguous: it says *no characteristic
recorded*, and whether the service is taken is answered where it already lives.

That building holds `20 × 3 + 5 × 1 = 65` rows.

**AND THE UNIT OF MEASURE IS A COLUMN, NEVER A SUFFIX ON THE KEY** (hard rule 3).
Container count, impervious square feet and a speed tier are three different
units. `storm_impervious_sqft` encodes its unit in an identifier that nothing can
validate, compare or migrate; `unit_of_measure` as DATA is the same discipline
the rule already imposes on consumption — *never assume the unit*.

⚠ **WHAT THIS FILE REFUSES TO DECIDE.** BR-MET-108's own closing clause: *"It
does not name the characteristic keys, their UoMs, or which services require one
before a bill can be produced — none of that is signed, and a lane must not
invent it."* So:

  * ⚠ **`characteristic_or_refuse()` IS GONE, AND ITS RULE WAS REVERSED BY THE
    PO ON 2026-08-25 — verbatim, *"Bill it as zero"*.** It implemented
    BR-MET-108's original last sentence (*"A service whose characteristic is
    required and absent must REFUSE with the absence named, never price it at
    zero"*). That sentence, and the cost of dropping it, were put to the PO in
    plain English with a worked figure; the PO chose zero. `BR-MET-108` is
    AI-authored and HUMAN-REVIEW-PENDING, so this IS its human review arriving
    and ruling differently — no finance re-sign was required.
    **`characteristic_for_pricing()` replaces it and never refuses**; it returns
    zero with `absent`, `priced_at_zero` and a `reason` stamped, and
    `units_priced_at_zero()` lists every unit it happened to — because billing
    zero is the ruling and billing zero *silently* is not.
  * `required_characteristic_keys()` RAISES `NotImplementedError("OQ-370")`.
    It once raised a stated absence in prose because no open question covered
    the gap and minting an OQ-### from inside code is what G8 clause B exists to
    catch. **OQ-370 was registered on 2026-08-25**, so the prime directive's
    ordinary form applies. ⚠ The PO's ruling dissolved half of what this
    function was for — nothing is *required* before a bill can be produced any
    more — and what OQ-370 still asks is which keys and units of measure a
    SETTINGS FORM must offer, since a form cannot ask for "a characteristic".

`value` is TEXT and deliberately not a decimal. *"Three 96-gallon containers"* is
a count, *"2,450"* is an area, and *"100/20 Mbps"* is a speed tier that is not a
number at all. Coercing at write would lose the third; a text column loses
nothing and refuses nothing, and the reader that needs arithmetic asks for it
(`decimal_value()`), which refuses BY NAME when the value is not a number rather
than silently reading zero.

════════════════════════════════════════════════════════════════════════════
3 · WHAT THIS LANE DID NOT BUILD
════════════════════════════════════════════════════════════════════════════
W6 is seventeen tasks; this lane holds three (6.1, 6.2, 6.9). Named so the next
lane does not assume they are missing by accident:

  * **6.3** the ten per-service template sets and their gates (§8.1) — the TABLE
    is here, empty. Gas gates on the LIGHT-UP and not the meter set; a lane that
    seeds it otherwise will bill a customer with no gas.
  * **6.4** batching (25 units → 7 orders, §8.2) · **6.5** dependencies ·
    **6.6** outcomes (`failed` → follow-up + connection On hold) ·
    **6.8** `energise` per service, gate-checked. `ConnectionService.gate_order`
    is the column 6.8 reads; this file writes no gate check.
  * **6.7 / 6.11–6.14** every screen. This lane has NO frontend half at all
    (r11 step 2b) and says so rather than letting the absence add up.
  * **6.10** connection charges → the developer's master account (BR-CUS-083).
    No money is written by this module and no ledger line is posted from it.
    NCT-02's `CHARGES $2,340.00 · paid Aug 15` and *"charges follow the
    connection"* are that task's, not this one's: **no payer is built here.**

════════════════════════════════════════════════════════════════════════════
4 · TWO PROTOTYPE DEFECTS, OBSERVED AND NOT COPIED (CR-028 §11's precedent)
════════════════════════════════════════════════════════════════════════════
Recorded so a later lane reading the same screens does not reproduce them, and
so nobody "fixes" them here — both are filed by the lane that supplied them:

  1. **NCT-02's Timeline on `CON-26-0110` — a ONE-unit build — reads *"Electric
     energised — 25 units"* and *"WO-4904 passed — 25 electric meters set"*.**
     Those belong to `CON-26-0117`, the 25-unit build; the prototype has pasted
     the wrong fixture. The header of the same screen says *"single unit"*, and
     the Units tab draws one row. **`service_progress()` computes the count from
     the rows and can never print 25 for one unit** — the test asserts `1 of 1`.
  2. **The Account row renders as `AccountNot an account — charges follow the
     connection`** — label and value jammed with no separator. A rendering
     defect in a tab this module does not serve.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import dateparse, timezone
from django.db.models import Q

from apps.metering import models as metering_models
from apps.metering import seams
from apps.metering import services as metering_services
from core import audit as core_audit
from core import errors
from core import numbering as core_numbering
from core import idempotency as core_idempotency

# ── T-43 (CR-187-BRC10): the six Work tables and the vocabulary their columns
# are checked against now live in `apps/work/connection_models.py` — the Work
# module owns them (`16-work/03-field-map.md` §4). This module keeps the SERVICES
# that act on them and imports the names it uses; it declares no model.
from apps.work.connection_models import (
    CONNECTION_SERIES,
    WORK_ORDER_SERIES,
    DRAFT,
    REQUESTED,
    IN_PROGRESS,
    PARTLY_ACTIVATED,
    ON_HOLD,
    ACTIVATED,
    CANCELLED,
    SVC_PENDING,
    SVC_IN_PROGRESS,
    SVC_ACTIVATED,
    SVC_CANCELLED,
    SERVICE_STATES,
    SERVICE_TRANSITIONS,
    SCOPE_PREMISE,
    SCOPE_ASSET,
    WORK_ORDER_SCOPES,
    MODE_WE_SCHEDULE,
    MODE_OUR_CREW,
    WORK_ORDER_MODES,
    OUTCOME_FAILED,
    WORK_ORDER_OUTCOMES,
    WO_PLANNED,
    WO_IN_PROGRESS,
    WO_COMPLETED,
    WO_CANCELLED,
    DISPATCH_QUEUED,
    DISPATCH_SCHEDULED,
    DISPATCH_COMPLETE,
    DISPATCH_ON_HOLD,
    DISPATCH_CANCELLED,
    SOURCE_NEW_CONNECT,
    SOURCE_SERVICE_REQUEST,
    SOURCE_MOVE_IN,
    SOURCE_FAILED_OUTCOME,
    WORK_ORDER_SOURCES,
    Connection,
    ConnectionService,
    WorkOrder,
    WorkOrderTemplate,
    ServiceCharacteristic,
    ConnectionTodo,
)

# ⚠ THE ONE THIN RE-EXPORT, AND IT IS MIGRATION HISTORY'S, NOT A CONVENIENCE.
# `metering/0050_cr070_g_dispatch.py` does `from apps.metering.connections import
# DISPATCH_STATES` to build its check constraint, and an applied migration is
# not rewritten to follow a move (it is a 🔒 path and its operations must read
# the same forever). This module does not use the name itself, so without this
# line `manage.py migrate` dies on an ImportError at graph load. Nothing else
# may import it from here — every live importer moved to
# `apps.work.connection_models` in T-43. (`WORK_ORDER_SOURCES`, which
# `metering/0049`, `0052`, `0056` and `0075` read from here the same way, is in
# the import above because this module uses it.)
from apps.work.connection_models import DISPATCH_STATES  # noqa: F401  (metering/0050 reads it here)


# ════════════════════════════════════════════════════════════════════════════
# THE STATE MACHINE (task 6.2)
# ════════════════════════════════════════════════════════════════════════════
def derive_connection_state(
    *,
    submitted: bool,
    held: bool,
    cancelled: bool,
    service_states: Any,
) -> str:
    """THE connection state — a pure function of the stored truth.

    Pure and primitive-argument on purpose: the eight seeded rows of B18 §5.4.8
    can be asserted against it with no tenant, no row and no transaction, which
    is what makes the derivation reviewable rather than merely tested.

    A CANCELLED service is excluded from the tally rather than counted as
    unfinished — a connection whose gas was cancelled and whose electric is live
    is `Energised`, because nothing is left waiting.
    """
    if cancelled:
        return CANCELLED
    if not submitted:
        return DRAFT
    # ON HOLD OUTRANKS PROGRESS, and the seed says so: CON-26-0119 is `5 of 9`
    # AND `On hold` — the permit stops the build whatever has already been done.
    if held:
        return ON_HOLD
    live = [state for state in service_states if state != SVC_CANCELLED]
    if live and all(state == SVC_ACTIVATED for state in live):
        return ACTIVATED
    if any(state == SVC_ACTIVATED for state in live):
        return PARTLY_ACTIVATED
    if any(state == SVC_IN_PROGRESS for state in live):
        return IN_PROGRESS
    return REQUESTED


def connection_state(connection: Connection) -> str:
    """`derive_connection_state` over one connection's own rows."""
    states = list(
        ConnectionService.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        ).values_list("state", flat=True)
    )
    return derive_connection_state(
        submitted=connection.submitted_at is not None,
        held=connection.held_at is not None,
        cancelled=connection.cancelled_at is not None,
        service_states=states,
    )


def refresh_connection_state(connection: Connection) -> str:
    """Recompute the CACHE. **The only writer of `connections.state`.**

    Also maintains `activated_at`, which is a fact about the build and not about
    any one service: it is stamped the moment the derived state first reaches
    `Energised` and is never cleared by a later hold, because the date the
    supply went live does not un-happen.
    """
    state = connection_state(connection)
    fields = []
    if connection.state != state:
        connection.state = state
        fields.append("state")
    if state == ACTIVATED and connection.activated_at is None:
        connection.activated_at = timezone.now()
        fields.append("activated_at")
    if fields:
        connection.save(update_fields=[*fields, "updated_at"])
    return state


def connection_mode(connection: Connection) -> str | None:
    """What the ORDERS say this build's mode is — the DERIVED half of the pair.

    NCT-01's Work orders tab draws a MODE column per order, every row reading
    `Our crew`, so a connection-level answer is a reading of its orders and not
    a column. One mode across every order → that mode (the drawn case). More
    than one → `"mixed"`, which is a real and normal state: *"a utility that
    does its own water work and contracts out gas is the normal case, not the
    edge"* (§8.3). No orders yet → None, and the wizard's step-1 default on
    `connections.mode` is what will be stamped onto the first one.
    """
    modes = set(
        WorkOrder.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        ).values_list("mode", flat=True)
    )
    if not modes:
        return None
    return modes.pop() if len(modes) == 1 else "mixed"


def order_progress(connection: Connection) -> tuple[int, int]:
    """NCT-01's `ORDERS` column — `5 of 9`, *"done of total"*, under a progress
    underline. A fraction rather than a percentage, and never a bar alone: the
    fraction is readable and a bar is not (B18 §5.4.2).

    `done` counts orders in `completed`; a CANCELLED order is removed from BOTH
    halves, because `4 of 4` and `4 of 5 with one cancelled` are the same build
    and the second reads as unfinished forever.
    """
    rows = WorkOrder.objects.filter(
        tenant_id=connection.tenant_id, connection_id=connection.id
    ).exclude(state=WO_CANCELLED)
    total = rows.count()
    return rows.filter(state=WO_COMPLETED).count(), total


def connection_home(connection: Connection) -> dict[str, str] | None:
    """**Where a person goes to see this build** — CR-070 wave O, `§W.11`.

    PO, 2026-09-04: *"you are duplicating this — there is nothing called as
    conenctions; Connection = Account only - you cannot have two differnt screen
    - this is an integration problem"*, scoped the same day to *"One screen too
    many. The objection is the duplicate destination — a person should reach the
    build's progress, its units, its work orders and its charges from the
    account, not from a parallel screen."*

    So `/connections/<uuid>` is no longer a destination, and every cell, row
    action and bookmark that pointed at it needs to be told where to go instead:
    **the owner account when the build has one, the premises otherwise.**

    ⚠ **IT LIVES HERE, IN METERING, BECAUSE THE FACT IS THE CONNECTION'S.**
    Four callers want it — this module's own worklist row, `apps/work`'s two
    scoped order lists through its seam, and the redirect — and a second
    implementation is the drifting copy this repo keeps re-learning about (law
    5: one source, derive the rest). `apps/work` reaches it by name through
    `seams/metering_seam.home_of_connection`, which is the same posture that
    seam already takes on `create_work_order`.

    ⚠ **THE PREMISES HALF ALWAYS EXISTS; THE ACCOUNT HALF IS OPTIONAL RATHER
    THAN UNBUILT.** This paragraph said `create_owner_account()` *"raises
    `NotImplementedError("OQ-373")`"* until 2026-09-12 (`DEF-MET-5081`); it does
    not, and has not since 2026-08-25. **The behaviour below did not change and
    neither did the judgment that the premises is the host to build on** — a
    build may simply have no owner account, because nobody named an owner. What
    changed is the proof: it is now *"the column is optional"* and not *"the
    writer is missing"*. ⚠ **AND THE SECOND REASON THIS SENTENCE GAVE IS GONE
    (2026-09-21):** it read *"or because `BR-MET-116` refuses a build with no
    common area by design"*, and the PO has ruled *"common area is option"*, so
    a build with no shared space now gets its owner an account like any other.

    Measured 2026-09-12 with `app.tenant_id` set: **8 `brazosbend` connections,
    0 with an `owner_account_id`** — so every build here does answer `premises`
    today. That is a fact about this fixture (its connections were seeded
    directly, never committed through step 4) and not about the function.

    Both values are ids for a LINK and never a value drawn on a screen, which
    B14 rule 31 forbids: what a person reads is `CON-26-0117`.
    """
    if connection.owner_account_id:
        return {"kind": "account", "id": str(connection.owner_account_id)}
    if connection.premises_id:
        return {"kind": "premises", "id": str(connection.premises_id)}
    # ⚠ **REACHABLE SINCE `DEF-CUS-6109` (2026-09-21), AND THIS COMMENT SAID IT
    # WAS NOT.** It read *"Unreachable while `connections.premises_id` is NOT
    # NULL"* — true when written and false the moment the column became
    # nullable, which is hard-won law 1 in one line. A DRAFT raised from an
    # application whose address had not resolved has neither an owner account
    # nor a premises, so it has no home until it commits, and the list renders
    # its number with no link on it rather than crashing.
    return None


def service_progress(connection: Connection) -> list[dict[str, Any]]:
    """NCT-02's side-by-side per-service blocks:

        ELECTRIC  Energised   1 of 1 units · Aug 18
        WATER     Energised   1 of 1 units

    **The block's STATE is derived by the SAME function that derives the
    connection's**, fed this service's rows instead of all of them — so a
    service and a build cannot disagree about what "partly" means, because
    there is one rule and it is applied twice.

    ⚠ **AND IT IS WHY `partly_energised` IS ABSENT FROM `SERVICE_STATES` AND
    PRESENT HERE.** A stored row is one service AT ONE UNIT and cannot be
    partly anything. A service ACROSS a 25-unit build plainly can — `CON-26-0117`
    is 25 units — and that is a count over rows, not a sixth token to store.
    The drawn `1 of 1 units` is the single-unit case of exactly this.
    """
    rows = list(
        ConnectionService.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        ).select_related("service")
    )
    by_service: dict[str, list[ConnectionService]] = {}
    for row in rows:
        by_service.setdefault(row.service.code, []).append(row)
    blocks = []
    for code, service_rows in by_service.items():
        states = [row.state for row in service_rows]
        energised = [row for row in service_rows if row.state == SVC_ACTIVATED]
        dates = [row.activated_at for row in energised if row.activated_at is not None]
        blocks.append(
            {
                "service": code,
                # Submitted and unheld: the block reports the SERVICES, and the
                # build's own hold is drawn once, in the header, not per block.
                "state": derive_connection_state(
                    submitted=True, held=False, cancelled=False, service_states=states
                ),
                "units_energised": len(energised),
                "units_total": len(service_rows),
                "activated_at": max(dates) if dates else None,
            }
        )
    return sorted(blocks, key=lambda block: block["service"])


def transition_service(
    actor: Any, connection_service_id: Any, to_state: str, *, reason: str | None = None
) -> dict[str, Any]:
    """Move ONE service, refuse an illegal move, then refresh the cache.

    The refusal is a `BIZ-STATE` carrying `BR-MET-108`'s neighbour rule set and
    the two states by name, because *"cannot transition"* with no nouns in it is
    a message a clerk cannot act on.
    """
    if to_state not in SERVICE_STATES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.connection_service_state_unknown",
            params={"state": to_state},
        )
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = (
            ConnectionService.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=connection_service_id)
            .first()
        )
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        before = row.state
        if to_state != before and to_state not in SERVICE_TRANSITIONS[before]:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-104",
                message_key="metering.connection_service_transition_refused",
                params={"from": before, "to": to_state},
            )
        row.state = to_state
        if to_state == SVC_ACTIVATED and row.activated_at is None:
            row.activated_at = timezone.now()
        row.save(update_fields=["state", "activated_at", "updated_at"])
        connection = Connection.objects.select_for_update().get(
            tenant_id=tenant_id, pk=row.connection_id
        )
        state = refresh_connection_state(connection)
        _audit(
            actor,
            "connection_service.transitioned",
            "connection_service",
            row.id,
            before={"state": before},
            after={"state": to_state, "reason": reason, "connection_state": state},
        )
    return {"id": str(row.id), "state": row.state, "connection_state": state}


def submit_connection(actor: Any, connection_id: Any) -> dict[str, Any]:
    """`Draft` → `Requested` (step 8 of the wizard, *"Review & request"*)."""
    return _stamp(
        actor,
        connection_id,
        field="submitted_at",
        action="connection.submitted",
        expect_unset=True,
    )


def hold_connection(actor: Any, connection_id: Any, *, reason: str) -> dict[str, Any]:
    """Put the build `On hold` — the permit, the inspection, the materials.

    §8.3: a `failed` work-order outcome must also land here (task 6.6). It is
    not wired from this module, and saying so is the point (hard-won law 2).
    """
    return _stamp(
        actor,
        connection_id,
        field="held_at",
        action="connection.held",
        expect_unset=True,
        extra={"waiting_on": reason},
    )


def release_connection(
    actor: Any, connection_id: Any, *, waiting_on: str | None = None
) -> dict[str, Any]:
    """Lift the hold. The derived state goes back to whatever the SERVICES say
    it is — which is the reason the hold is a timestamp and not a state token:
    clearing it cannot lose the progress underneath.

    `waiting_on` is passed rather than assumed: releasing a permit hold usually
    means nothing is waited on (the default), but a build can come off hold and
    still be waiting for materials — NCT-01 draws exactly that combination on
    `CON-26-0121`. The caller says; this function does not guess.

    ⚠ **`expect_set=True` SINCE `DEF-MET-3652` (2026-09-04).** Releasing a build
    that is not held used to answer HTTP 200 and clear `waiting_on` on the way
    past — and `waiting_on` is exactly the note the paragraph above says a
    released build may legitimately still carry, so the accidental call
    destroyed the one field this function is most careful about. The screen has
    always disabled the button ("This build is not on hold."); now the server
    says the same thing, which is what `BR-SHL-025` asks for and what the
    connection detail's own docstring already claimed."""
    return _stamp(
        actor,
        connection_id,
        field="held_at",
        action="connection.released",
        expect_set=True,
        clear=True,
        extra={"waiting_on": waiting_on},
    )


def set_waiting_on(actor: Any, connection_id: Any, *, waiting_on: str | None) -> dict[str, Any]:
    """NCT-01's `WAITING ON` column, on a build that is NOT held.

    `CON-26-0121` is **In progress · materials** and `CON-26-0126` is **Partly
    energised · inspection**: waiting on something is not the same as being on
    hold, so it has its own write path and does not touch `held_at`.
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        connection = (
            Connection.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=connection_id)
            .first()
        )
        if connection is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        before = connection.waiting_on
        connection.waiting_on = waiting_on
        connection.save(update_fields=["waiting_on", "updated_at"])
        _audit(
            actor,
            "connection.waiting_on_set",
            "connection",
            connection.id,
            before={"waiting_on": before},
            after={"waiting_on": waiting_on},
        )
    return {"id": str(connection.id), "waiting_on": waiting_on, "state": connection.state}


def cancel_connection(actor: Any, connection_id: Any, *, reason: str) -> dict[str, Any]:
    result = _stamp(
        actor,
        connection_id,
        field="cancelled_at",
        action="connection.cancelled",
        expect_unset=True,
        extra={"cancel_reason": reason},
    )
    # ── `CR-162-BRC10` · THE ACCOUNTS LEFT OPEN ON THE BUILD'S UNITS ─────────
    # PO 2026-10-02 (move-in before approval, ruled B): if the New Connection
    # is cancelled with such an account open, *"show a warning listing the
    # account(s) to close. Do not auto-close."* So the cancel answers with them
    # and closes NOTHING — closing an account is the move-out flow (BR-CUS-030),
    # a clerk's act. The Cancel dialog lists the same set before the press.
    from apps.metering import connection_activation

    return {
        **result,
        "accounts_to_close": connection_activation.accounts_on_build_units(connection_id),
    }


def _stamp(
    actor: Any,
    connection_id: Any,
    *,
    field: str,
    action: str,
    expect_unset: bool = False,
    expect_set: bool = False,
    clear: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set or clear one timestamp on a build, with the audit row that goes with it.

    ⚠ **`expect_set` IS THE MIRROR OF `expect_unset`, AND ITS ABSENCE WAS
    `DEF-MET-3652`.** A hold/release pair is two calls on one column, and until
    2026-09-04 only the SETTING half could state its precondition. So
    `release_connection` on a build that was never held wrote `NULL` over
    `NULL`, answered **HTTP 200**, and — because `waiting_on` travels in
    `extra` — **silently cleared a note somebody had typed**, then wrote an
    audit row saying the build was released. Not a no-op: a data loss with a
    false record of it.
    It survived every test because the screen disables that button, so nobody
    wrote the case the button prevents; the browser walkthrough found it by
    calling the door directly. **Both halves of a pair state their
    precondition, or the one that does not is free.**
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        connection = (
            Connection.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=connection_id)
            .first()
        )
        if connection is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        before = connection.state
        current = getattr(connection, field)
        if expect_unset and current is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-104",
                message_key="metering.connection_already_stamped",
                params={"field": field, "state": before},
            )
        # DEF-MET-3652 — the other direction. Lifting a hold that is not there
        # is refused BEFORE anything is written, because `extra` would clear
        # `waiting_on` on the way past.
        if expect_set and current is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-104",
                message_key="metering.connection_not_stamped",
                params={"field": field, "state": before},
            )
        if connection.cancelled_at is not None and field != "cancelled_at":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-104",
                message_key="metering.connection_cancelled",
                params={"state": before},
            )
        setattr(connection, field, None if clear else timezone.now())
        fields = [field]
        for name, value in (extra or {}).items():
            setattr(connection, name, value)
            fields.append(name)
        connection.save(update_fields=[*fields, "updated_at"])
        state = refresh_connection_state(connection)
        _audit(
            actor,
            action,
            "connection",
            connection.id,
            before={"state": before},
            after={"state": state, **(extra or {})},
        )
    return {"id": str(connection.id), "state": state}


# ════════════════════════════════════════════════════════════════════════════
# WRITE PATHS
# ════════════════════════════════════════════════════════════════════════════
def create_connection(actor: Any, payload: Any) -> dict[str, Any]:
    """Step 1–2 of the wizard: a `Draft` build against a premise — **and, since
    `CR-056` task 23, against a premise this door CREATES when asked to.**

    Prefilled from an approved request where there is one (TC-NCT-1); B18 §2.1's
    six channels include builds that never had a request record, so the link is
    optional and the absence is not an error.

    ── `BR-MET-1024` · NEW CONNECT MAY CREATE THE ADDRESS IT BUILDS ON ────────
    Until 2026-09-01 this door REFUSED without a `premises_id`, so a new build
    had to be typed into the Premises screen first and then found again in the
    wizard — for a connection whose entire purpose is that the address is new.
    It now takes **either**:

      * `premises_id` — an address already on file. Unchanged, and every caller
        that exists today takes this path with the same refusal on a bad id.
      * `premises` — a payload block, passed **VERBATIM** to
        `metering.services.create_premises`.

    **NO SECOND CREATOR AND NO SECOND VALIDATOR.** A premises created here is
    byte-for-byte a premises created on S16: the same `_validate_premises`, the
    same `PREMISES_SERIES` number, the same `premises.created` audit row, the
    same area cascade, and the same MANDATORY OWNER — which is what makes
    *every address gets its owner a Master Account* (`BR-MET-1010`, PO ruling
    2026-08-31) reachable from this wizard at all. A copy of that validation
    here would be a second place for the owner requirement to be relaxed.

    ⚠ **NAMING BOTH IS REFUSED BY NAME, not silently preferred.** *"Build on
    this address"* and *"build on a new address"* are different intentions and
    a door that quietly picked one would sometimes create an address a clerk
    thought they had chosen from a list.

      * `premises_at_commit` — **neither, yet.** `DEF-CUS-6109`, PO ruling
        2026-09-21: approving an application into a new connection *"may create
        a new conenct request - as draft request"*, and a request whose address
        has not resolved has no premises to name and must not have one created
        for it. The draft is raised with `premises = None` and the address is
        created **at commit**, by `commit_new_connect`, exactly as it is for a
        build a clerk starts directly. ⚠ It is an EXPLICIT key and not the
        absence of the other two, for the same reason *naming both* is refused
        by name: a door that silently accepted *neither* would let a caller
        that forgot its `premises_id` raise an addressless build and never
        learn it had.

    ⚠ **`BR-MET-112` — *"nothing is written until step 9"* — IS NOT BROKEN BY
    ANY OF THE THREE.** This door already writes: it creates the `Connection`.
    What is still true of step 9 is that the BUILD — units, meters, plans, the
    owner's account, the quote — is written there and nowhere else, and on the
    `premises_at_commit` path the ADDRESS is written there too, so abandoning
    the wizard leaves a draft build and no property.

    `premises_created` rides on the response so the caller knows which of the
    two happened. It is reported HERE, at the door that did it, rather than in
    the commit's manifest, which cannot know (see `commit_connection` and
    `DEF-2961`).
    """
    data = metering_services._payload_dict(payload)
    warnings: list[dict[str, Any]] = []
    tenant_id = _tenant_id()
    premises_id = data.get("premises_id")
    premises_block = data.get("premises")
    # `DEF-CUS-6109` — the third answer: *no address yet, and one is not being
    # created here*. Refused BY NAME beside either of the other two, because
    # *build on this address*, *build on a new address* and *the address comes
    # later* are three different intentions and a door that quietly ranked them
    # would sometimes silently ignore the one the caller meant.
    at_commit = bool(data.get("premises_at_commit"))
    if at_commit and (premises_id or premises_block):
        metering_services._refuse_fields(
            [
                metering_services._field_error(
                    "premises_at_commit",
                    errors.VAL_FORMAT,
                    "metering.connection.premises_named_twice",
                )
            ]
        )
    if premises_id and premises_block:
        metering_services._refuse_fields(
            [
                metering_services._field_error(
                    "premises",
                    errors.VAL_FORMAT,
                    "metering.connection.premises_named_twice",
                )
            ]
        )
    premises_created = False
    if premises_block is not None:
        # `BR-MET-1024` — the SAME door S16 uses. It allocates the premise
        # number, writes the audit row, cascades the area's routes and refuses
        # a premises with no owner, all of which this wizard needs and none of
        # which is restated here.
        # ⚠ **THROUGH THE WRAPPER, SO A REFUSAL NAMES STEP 2** (`DEF-MET-7690`).
        made = _premises_made_for_the_wizard(actor, premises_block)
        premises_id = made["id"]
        premises_created = True
        warnings.extend(made.get("warnings") or [])
    if not premises_id and not at_commit:
        metering_services._refuse_fields(
            [
                metering_services._field_error(
                    "premises_id", errors.VAL_REQUIRED, "metering.connection.premises_required"
                )
            ]
        )
    premises = None
    if premises_id:
        premises = metering_models.Premises.objects.filter(
            tenant_id=tenant_id, pk=premises_id
        ).first()
        if premises is None:
            raise errors.deny_as_not_found("BR-TEN-003")
    mode = data.get("mode") or MODE_OUR_CREW
    _check_mode(mode)
    with transaction.atomic():
        number = metering_services._allocate_unused_number(
            actor, CONNECTION_SERIES, warnings, model=Connection, field="connection_no"
        )
        connection = Connection.objects.create(
            tenant_id=tenant_id,
            connection_no=number,
            service_request_id=data.get("service_request_id"),
            premises=premises,
            state=DRAFT,
            mode=mode,
            target_activation=data.get("target_activation"),
            # ── CR-126-BRC07 · STEP 1's THREE ANSWERS NOW LAND SOMEWHERE ────
            # ⚠ **THEY HAVE BEEN COLLECTED AND DISCARDED SINCE THE WIZARD WAS
            # BUILT.** `scope` and `units_prefix` arrived on the commit payload
            # and `commit_new_connect` answered a stated absence saying nothing
            # read them (`DEF-CUS-5435`); `owner_type` — the drawn *Owner type*
            # — was deleted from the payload by
            # `_owner_block_in_the_doors_language` before it reached the
            # accounts door, correctly, because `customers.kind` is
            # `person`/`company` and refuses all four of these words by name.
            # `metering/0058` gives all three a column and this is the writer.
            #
            # ⚠ **`or None` RATHER THAN `""`, ON ALL THREE.** An empty string is
            # a clerk who typed nothing, which is the same fact as NULL, and two
            # spellings of one absence is how a filter comes to disagree with a
            # count. The same posture the wizard already takes on `units_prefix`
            # before it sends it.
            owner_type=(data.get("owner_type") or None),
            units_prefix=(data.get("units_prefix") or None),
            scope=(data.get("scope") or None),
            created_by=getattr(actor, "id", None) or getattr(actor, "pk", None),
            is_sample=bool(data.get("is_sample", False)),
        )
        _audit(
            actor,
            "connection.created",
            "connection",
            connection.id,
            after={
                "connection_no": number,
                "premises_id": str(premises.id) if premises is not None else None,
                "state": DRAFT,
            },
        )
    return {
        "id": str(connection.id),
        "connection_no": connection.connection_no,
        "state": connection.state,
        # `BR-MET-1024` — WHICH of the two paths was taken, and the address it
        # landed on. Reported rather than inferred: the commit's manifest cannot
        # establish it (`DEF-2961`) and a caller that has to guess would guess.
        # `DEF-CUS-6109` — `None` on the `premises_at_commit` path, and that is
        # the answer rather than a gap: the draft genuinely has no address yet
        # and the caller must not be handed a string it can print.
        "premises_id": str(premises.id) if premises is not None else None,
        "premises_created": premises_created,
        "warnings": warnings,
    }


def add_connection_service(
    actor: Any, connection_id: Any, *, service_code: str, unit_id: Any = None
) -> dict[str, Any]:
    """Step 4 of the wizard — one service, at one unit or at the premise.

    Refuses a service the tenant does not run, through metering's own seam, so
    the refusal is the SAME one the unit wizard gives (`ensure_service_point`)
    rather than a second vocabulary for the same mistake.
    """
    tenant_id = _tenant_id()
    connection = Connection.objects.filter(tenant_id=tenant_id, pk=connection_id).first()
    if connection is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    service = _service_row(service_code)
    unit = None
    if unit_id is not None:
        unit = metering_models.Unit.objects.filter(tenant_id=tenant_id, pk=unit_id).first()
        if unit is None:
            raise errors.deny_as_not_found("BR-TEN-003")
    with transaction.atomic():
        row, created = ConnectionService.objects.get_or_create(
            tenant_id=tenant_id,
            connection=connection,
            unit=unit,
            service=service,
            defaults={"state": SVC_PENDING, "is_sample": connection.is_sample},
        )
        state = refresh_connection_state(connection)
        if created:
            _audit(
                actor,
                "connection_service.added",
                "connection_service",
                row.id,
                after={"service": service.code, "state": row.state, "connection_state": state},
            )
    return {"id": str(row.id), "service": service.code, "state": row.state, "created": created}


def parse_moment(value: Any, *, field: str) -> Any:
    """An ISO-8601 instant from a payload, made aware, or a readable refusal.

    ⚠ **A NAIVE DATETIME IS THE BUG THIS EXISTS TO STOP.** `USE_TZ` is on, so a
    naive value reaching the ORM warns and is then interpreted in the server's
    zone — which silently moves a promised appointment window by whatever the
    offset happens to be. So a naive value is read in the UTILITY's zone
    (`DEF-WRK-9688`). A date with no time is accepted (a dispatcher promising
    *Thursday*) and read as midnight in the utility's zone.

    Exported rather than private because `apps/work/dispatch.py` parses the same
    four fields — `due_at`, `scheduled_for`, `window_start`, `window_end` — and
    two parsers for one wire format is two answers to *what does 15:30 mean*.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        moment = dateparse.parse_datetime(text)
        if moment is None:
            day = dateparse.parse_date(text)
            moment = datetime.combine(day, time.min) if day is not None else None
    if moment is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.moment_format", params={"field": field}
        )
    if timezone.is_naive(moment):
        # ⚠ **THE UTILITY'S ZONE, NEVER THE SERVER'S (`DEF-WRK-9688`).** Every
        # screen that writes these four fields sends the clock time a person
        # typed — *08:00* on a Brazos Bend form means 08:00 in Brazos Bend —
        # and `get_current_timezone()` is the SERVER's (UTC in every deploy),
        # so a Central 08:00–12:00 was stored as 08:00Z and read back on every
        # surface as 03:00–07:00. The utility's own Regional setting decides
        # (`BR-TEN-081`); a value that carries its own offset is untouched.
        moment = timezone.make_aware(moment, seams.tenant_timezone())
    return moment


def _asset_walk(tenant_id: Any, asset_id: Any) -> dict[str, Any]:
    """Where an asset STANDS — `CR-168-BRC10` P2.20: asset → service point →
    unit → premises, and the point's service. A cross-tenant or absent asset is
    a 404 (HR-1). Metering owns the asset set (B2 r4); the rows are hosted in
    `apps.assets` and only READ here.

    ⚠ THE PREMISES IS WALKED, NEVER READ OFF THE ASSET (hard rule 8)."""
    from apps.assets import models as assets_models

    row = (
        assets_models.Asset.objects.filter(tenant_id=tenant_id, pk=asset_id)
        .select_related("service_point__unit")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    point = row.service_point if row.service_point_id else None
    unit = point.unit if point is not None and point.unit_id else None
    if unit is None:
        # ⚠ **`DEF-WRK-9660` — A DEVICE THAT MEASURES NOTHING STANDS ON ITS UNIT
        # THROUGH ITS CURRENT ASSIGNMENT.** A backflow preventer, a battery, a
        # PV array or a comms hub has no service point (`BR-AST-009`); where it
        # is installed is its OPEN `asset_assignments` row (`BR-AST-017`: at
        # most one). Reading only the point left every rule-raised job on such
        # a device with no premises and no unit — *Premise —* on the rule's
        # Jobs tab, the order list and the map. A device in the warehouse has
        # neither and still stands nowhere: the walk follows it, never invents.
        seat = (
            assets_models.AssetAssignment.objects.filter(
                tenant_id=tenant_id, asset_id=row.id, to_date__isnull=True
            )
            .select_related("unit")
            .first()
        )
        unit = seat.unit if seat is not None else None
    return {
        "asset_no": row.asset_no,
        "type_id": row.type_id,
        "service_id": point.service_id if point is not None else None,
        "unit_id": str(unit.id) if unit is not None else None,
        "premises_id": str(unit.premises_id) if unit is not None and unit.premises_id else None,
    }


def _template_asset_refusal(template: Any, asset_walk: dict[str, Any]) -> dict[str, Any] | None:
    """Whether a PUBLISHED template may be raised on the asset `_asset_walk`
    walked — `None`, or the refusal's `{message_key, params}`.

    P2.11: a water template on an electric meter is the wrong job. P2.14: a
    template naming asset types binds the asset it is raised on (a template
    naming none applies to every type).

    ⚠ **ONE CHECK, TWO CALLERS (`DEF-WRK-9661`).** `create_work_order` raises
    it; the rules preview and the rule's *Tonight* ASK it, so *Tonight it
    raises N jobs* counts only the subjects this function lets through. Until
    2026-10-04 the preview never asked, promised 4 and the sweep raised 3.
    """
    if asset_walk["service_id"] and str(asset_walk["service_id"]) != str(template.service_id):
        return {"message_key": "work.order.template_wrong_service", "params": {"template": template.name}}
    from apps.work.seams import metering_seam as work_metering_seam

    named = work_metering_seam.template_asset_type_ids(template.id)
    if named and str(asset_walk["type_id"] or "") not in named:
        return {
            "message_key": "work.order.asset_type_not_on_template",
            "params": {"asset": asset_walk["asset_no"]},
        }
    return None


def asset_raise_refusal(template_id: Any, asset_id: Any) -> str | None:
    """READ ONLY — the refusal key `create_work_order` would answer for this
    template raised on this asset, or `None` (`DEF-WRK-9661`). An asset of
    another tenant, or gone, answers `not_found` — the raise's 404, which has
    no sentence of its own (HR-1)."""
    tenant_id = _tenant_id()
    template = WorkOrderTemplate.objects.filter(tenant_id=tenant_id, pk=template_id).first()
    if template is None:
        return "work.order.template_not_published"
    try:
        walk = _asset_walk(tenant_id, asset_id)
    except errors.NotFoundError:
        return "not_found"
    refusal = _template_asset_refusal(template, walk)
    return None if refusal is None else refusal["message_key"]


def _resolve_order_type(tenant_id: Any, data: dict[str, Any], typed: str) -> Any:
    """The catalogue row behind the words a clerk typed — or `None`.

    ⚠ **NOTHING IS GUESSED** (`US-WRK-007` TC-6). Two ways in, and both are
    exact: the caller names `type_id`, or the typed words match a catalogue
    row's `code` or `name` **case-insensitively and in full**. *Meter set* and
    *Meter Set* land on one row, which is the whole reason `BR-WRK-017` asked
    for the catalogue; *Meter setting* lands on none and stays a string.

    ⚠ **THIS IS THE FIRST WRITER OF `work_orders.type_id`.** Wave C added the
    column and no path populated it, so it was NULL on every row in the
    product. It matters here because the job type is where the DEFAULT PRIORITY
    comes from, and the priority is where `due_at` comes from — with no type
    resolved, `BR-WRK-018` has no SLA to add and the order gets no promise.
    """
    from apps.work import models as work_models

    if data.get("type_id"):
        row = work_models.WorkOrderType.objects.filter(
            tenant_id=tenant_id, pk=data["type_id"]
        ).first()
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return row
    if not typed:
        return None
    return (
        work_models.WorkOrderType.objects.filter(tenant_id=tenant_id, active=True)
        .filter(Q(code__iexact=typed) | Q(name__iexact=typed))
        .first()
    )


def _resolve_priority(tenant_id: Any, data: dict[str, Any], type_ref: Any) -> Any:
    """`BR-WRK-018` — the priority this order was raised at, or `None`.

    Named by the caller, else the job type's own default, else **its heading's**.
    **No fourth fallback**: a tenant that has not seeded priorities gets an order
    with none and a DUE cell that draws a dash, rather than an invented *Normal*
    that reads as a promise somebody made.

    ⚠ **THE HEADING STEP WAS MISSING UNTIL 2026-09-12 AND THREE DOCUMENTS SAID
    IT WAS THERE (`DEF-WRK-5109`).** `work/models.py`'s own comment — *"which
    hangs under Consumer Complaint, would inherit **8 hours**"* — `OQ-WRK-1765`'s
    closure, and the name `URGENT_BEATS_ITS_PARENT`, which only means anything if
    there is an inheritance to beat. **The code walked no parent at all**, so
    twelve of the seeded sub-types — `Billing Issues`, `Low Pressure`, `Missed
    collection`, `Voltage complaint` among them — produced an order with NO
    priority and therefore NO `due_at`. That is the *Respond by* column of the
    complaints queue, empty on nearly every row, reading exactly like a utility
    that has not seeded priorities. Hard-won law 1: a comment claiming a
    guarantee is not the guarantee.

    ⚠ **IT IS A FALLBACK AND NEVER AN OVERRIDE.** A walk written as *"take the
    heading's"* would answer 8 hours for a gas leak call-out, which is the exact
    figure `OQ-WRK-1765` exists to prevent — *"arriving by accident, with nothing
    on any screen showing that a choice had been skipped"*. The four rows in
    `URGENT_BEATS_ITS_PARENT` carry their own and keep it.

    ⚠ **ONE LEVEL.** `BR-WRK-058` allows exactly two, and `work.lookups` refuses
    a grandparent, so there is no deeper chain to walk and no loop to write.
    """
    from apps.work import models as work_models

    if data.get("priority_id"):
        row = work_models.WorkPriority.objects.filter(
            tenant_id=tenant_id, pk=data["priority_id"]
        ).first()
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return row
    if type_ref is None:
        return None
    return type_ref.default_priority or (
        type_ref.parent.default_priority if type_ref.parent_id else None
    )


def _resolve_est_duration(data: dict[str, Any], type_ref: Any, template: Any = None) -> Any:
    """How long this job is expected to take — the caller's figure, else the SUM
    OF ITS TEMPLATE'S TASK MINUTES, else the job type's, else nothing.

    ⚠ **THE TEMPLATE'S MINUTES WERE NEVER READ** (`CR-168-BRC10` P3.47):
    measured, `est_duration` was set on 0 of 40 demo jobs, so *time against
    estimate* could not be counted on Performance, on a technician's page or on
    the phone. A job raised from *Meter exchange* (tasks of 8 + 15 + 10 + 5
    minutes) now carries 38 minutes, the figure the checklist's *38 MIN
    ESTIMATED* header already shows. A template whose tasks sum to 0 falls back
    to the job type, because zero is not an estimate anybody made.

    ⚠ **THE PAYLOAD SPEAKS MINUTES AND THE COLUMN IS A `timedelta`.** A number on
    the wire is minutes, because that is what `WS-24` and `US-WRK-007` §4 write
    (*45 min*) and what a form field collects; the conversion happens ONCE, here,
    so no caller has to remember it. An ISO duration string is accepted too, for
    a caller that already holds one.
    """
    given = data.get("est_duration", data.get("est_minutes"))
    if given in (None, ""):
        if template is not None:
            from django.db.models import Sum

            from apps.work import models as work_models

            minutes = work_models.WorkOrderTemplateTask.objects.filter(
                tenant_id=template.tenant_id, template_id=template.id
            ).aggregate(total=Sum("est_minutes"))["total"]
            if minutes:
                return timedelta(minutes=int(minutes))
        return type_ref.est_duration if type_ref is not None else None
    if isinstance(given, timedelta):
        return given
    if isinstance(given, (int, float)):
        return timedelta(minutes=int(given))
    parsed = dateparse.parse_duration(str(given).strip())
    if parsed is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.moment_format",
            params={"field": "est_duration"},
        )
    return parsed


def _resolve_due_at(
    data: dict[str, Any], priority: Any, raised_at: Any, type_ref: Any = None
) -> Any:
    """`BR-WRK-018`, verbatim: *"`due_at` defaults to the raise time plus the
    SLA."*

    STAMPED, never derived on read. `US-WRK-008` TC-4 is explicit: moving Urgent
    from 4 hours to 2 must not move a job already in the field. A caller may
    override it (a dispatcher promising a specific day), and an order with no
    priority gets no due date at all — an absence, not a zero.
    """
    if data.get("due_at"):
        return parse_moment(data["due_at"], field="due_at")
    # `CR-168-BRC10` P5.10 (lane SRV-4) — a job TYPE's own hours override its
    # priority's; a type with none (every type until a supervisor sets one)
    # leaves the priority's promise exactly as before.
    type_hours = getattr(type_ref, "sla_hours", None) if type_ref is not None else None
    if type_hours:
        return raised_at + timedelta(hours=int(type_hours))
    if priority is None or not priority.sla_hours:
        return None
    return raised_at + timedelta(hours=int(priority.sla_hours))


#: CR-161-BRC10 W4 — the slot key of the New work order screen (`WRK-12`) in
#: `apps/tenancy/custom_fields.SLOTS`. Work's edit door uses `WORK_EDIT`.
WORK_ORDER_NEW_SCREEN = "WORK_NEW"


def create_work_order(actor: Any, connection_id: Any = None, payload: Any = None) -> dict[str, Any]:
    """One order on at least one ANCHOR — a build, a premises, an account or an
    asset (BR-WRK-006, `WM-01`; CR-070 wave A, 2026-09-03).

    Until metering/0044 this read *"one order against a build"* and the
    connection was a required positional argument, which is the blueprint's
    one structural blocker: *"a leak investigation, a meter exchange, a
    reconnect or a backflow test … cannot be recorded at all, not even by
    hand."* The contract is WIDENED rather than replaced — every existing
    caller (`commit_connection`, the seeder, some thirty tests) still passes
    the connection positionally — and the payload may now carry
    `connection_id` · `premises_id` · `account_id` · `asset_id` instead. At
    least one of the four, or the raise is refused with a sentence
    (`work.order.anchor_required`) before the database's CHECK
    (`ck_work_orders_has_anchor`) ever sees it. An unknown premises or account
    id is a 404, never a 403 (HR-1: existence must not leak).

    An order with no connection touches no connection: `refresh_connection_state`
    is not called and nothing here reads `connection.*` on it. `mode` then comes
    from the payload or the platform default; `is_sample` from the payload or
    the premises.

    BATCHING IS NOT DONE HERE — task 6.4 owns §8.2's arithmetic (25 units → 7
    orders, not 76). This writes the row the batcher decides on, and `scope` is
    what it decides with.
    """
    data = metering_services._payload_dict(payload)
    warnings: list[dict[str, Any]] = []
    tenant_id = _tenant_id()
    connection = None
    connection_key = connection_id or data.get("connection_id")
    if connection_key:
        connection = Connection.objects.filter(tenant_id=tenant_id, pk=connection_key).first()
        if connection is None:
            raise errors.deny_as_not_found("BR-TEN-003")
    premises = None
    if data.get("premises_id"):
        premises = metering_models.Premises.objects.filter(
            tenant_id=tenant_id, pk=data["premises_id"]
        ).first()
        if premises is None:
            raise errors.deny_as_not_found("BR-TEN-003")
    account = _account_or_404(data["account_id"]) if data.get("account_id") else None
    asset_id = data.get("asset_id") or None
    if data.get("unit_id") and premises is None and connection is None:
        # `CR-168-BRC10` P2.20 — a unit-only raise stands on the unit's
        # building: the unit refines a premises by label (hard rule 8), so its
        # premises IS the anchor. A unit of another tenant is a 404 below.
        unit_row = metering_models.Unit.objects.filter(
            tenant_id=tenant_id, pk=data["unit_id"]
        ).select_related("premises").first()
        premises = unit_row.premises if unit_row is not None else None
    if connection is None and premises is None and account is None and not asset_id:
        # BR-WRK-006's floor, in Python first so the clerk reads a sentence; the
        # CHECK in Meta is the backstop for anything that reaches the table
        # around this function (US-WRK-001 TC-3, TC-6).
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.order.anchor_required",
            br_ref="BR-WRK-006",
        )
    scope = data.get("scope") or None
    if scope is not None and scope not in WORK_ORDER_SCOPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.work_order_scope_unknown",
            params={"scope": scope},
        )
    # STAMPED, never a fallback read: the order carries how IT is run, taken
    # from the payload or from the connection's step-1 default at this instant.
    # With no connection there is no step-1 default, so the platform's own.
    mode = data.get("mode") or (connection.mode if connection is not None else MODE_OUR_CREW)
    _check_mode(mode)
    service = _service_row(data["service"]) if data.get("service") else None
    # ── `DEF-CUS-9177` (2026-10-02, `CR-163-BRC10` item 1) · THE UNIT IS CHECKED ─
    # The build detail's *Raise work order* form now sends a unit a clerk
    # PICKED, and `unit_id` was written straight onto the row unread. A unit of
    # another tenant is a 404 (HR-1 — existence must not leak), and on a build
    # the unit must stand on the build's own premises: an order for Suite 101
    # of a different building is not this build's work.
    if data.get("unit_id"):
        picked_unit = metering_models.Unit.objects.filter(
            tenant_id=tenant_id, pk=data["unit_id"]
        ).first()
        if picked_unit is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if connection is not None and str(picked_unit.premises_id) != str(connection.premises_id):
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.unit_not_on_build",
                br_ref="BR-WRK-006",
                params={"unit": picked_unit.label or ""},
            )
        # ── `CR-168-BRC10` P2.13 · `DEF-WRK-9527` — AND ON A PREMISES ────────
        # The same rule one anchor over: a job raised on 12 Kestrel Park may
        # not name Unit 205 of 500 Main St. Until this only the BUILD's premises
        # was compared, so the raise page — which anchors on a premises — took
        # any unit of any building.
        if premises is not None and str(picked_unit.premises_id) != str(premises.id):
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.unit_not_on_premises",
                br_ref="BR-WRK-006",
                params={"unit": picked_unit.label or ""},
            )
    template = None
    if data.get("template_id"):
        template = WorkOrderTemplate.objects.filter(
            tenant_id=tenant_id, pk=data["template_id"]
        ).first()
        if template is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        # ── CR-070 wave H · BR-WRK-008 — ONLY A PUBLISHED VERSION MAY BE
        # COPIED (`US-WRK-032` TC-4). `version` 0 IS the draft state
        # (`BR-WRK-011`: *"0 is a draft and it is not a version"*), so a draft
        # has no version to stamp and no settled bundle to copy.
        #
        # ⚠ REFUSED HERE, BEFORE THE ORDER ROW IS WRITTEN, and that placement
        # is the rule rather than tidiness: the alternative is an order stamped
        # `template_version = 0` whose six copies came from a bundle that may
        # still be edited under it — `BR-WRK-008` broken by a VALUE instead of
        # by a join, and invisible to the schema test that guards the join.
        if int(template.version or 0) < 1:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-WRK-008",
                message_key="work.order.template_not_published",
                params={"template": template.name},
            )
    # ── `CR-168-BRC10` P2.11 · P2.14 · P2.20 · ruling 20 — THE TEMPLATE AND
    # THE ASSET SHAPE THE JOB ─────────────────────────────────────────────
    asset_walk = _asset_walk(tenant_id, asset_id) if asset_id else None
    if data.get("asset_type_id") and not asset_id:
        # Ruling 20 (2026-09-24): *"if asset type is selected then user needs to
        # select asset"* — a unit with two water meters must say which.
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.order.asset_required", br_ref="BR-WRK-006"
        )
    if asset_walk is not None:
        if data.get("asset_type_id") and str(data["asset_type_id"]) != str(
            asset_walk["type_id"] or ""
        ):
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.asset_type_not_on_template",
                br_ref="BR-WRK-006",
                params={"asset": asset_walk["asset_no"]},
            )
        # P2.20 — a job raised on an asset SAYS WHERE IT IS: the premises and
        # unit are walked asset → service point → unit → premises, and must
        # agree with any the caller named.
        if premises is not None and asset_walk["premises_id"] and str(
            asset_walk["premises_id"]
        ) != str(premises.id):
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.asset_not_on_premises",
                br_ref="BR-WRK-006",
                params={"asset": asset_walk["asset_no"]},
            )
        if data.get("unit_id") and asset_walk["unit_id"] and str(asset_walk["unit_id"]) != str(
            data["unit_id"]
        ):
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.asset_not_on_premises",
                br_ref="BR-WRK-006",
                params={"asset": asset_walk["asset_no"]},
            )
        if premises is None and connection is None and asset_walk["premises_id"]:
            premises = metering_models.Premises.objects.filter(
                tenant_id=tenant_id, pk=asset_walk["premises_id"]
            ).first()
        if not data.get("unit_id") and asset_walk["unit_id"]:
            data["unit_id"] = asset_walk["unit_id"]
    if data.get("unit_id") and premises is None and connection is None:
        # P2.20 — the unit an ASSET walked to names the building too.
        unit_row = metering_models.Unit.objects.filter(
            tenant_id=tenant_id, pk=data["unit_id"]
        ).select_related("premises").first()
        premises = unit_row.premises if unit_row is not None else None
    if template is not None:
        # P2.11 — a water template on an electric meter is the wrong job.
        if service is not None and service.id != template.service_id:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.order.template_wrong_service",
                br_ref="BR-WRK-008",
                params={"template": template.name},
            )
        # P2.11 · P2.14 — the template against the asset it is raised on, ONE
        # check shared with the rules preview (`DEF-WRK-9661`).
        refusal = _template_asset_refusal(template, asset_walk) if asset_walk else None
        if refusal is not None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key=refusal["message_key"],
                br_ref="BR-WRK-008",
                params=refusal["params"],
            )
        # P2.14 · `DEF-WRK-9528` — COPIED when the payload omits them
        # (`BR-WRK-008`, copy never link): a *per unit, water* template raises
        # a per-unit water job.
        if scope is None:
            scope = template.scope
        if service is None:
            service = template.service
            # ⚠ **ON A BUILD, ONLY A SERVICE THE BUILD CARRIES (`DEF-MET-9700`).**
            # This copy (`DEF-WRK-9528`, 2026-10-04) read a payload's `None` as
            # *omitted* — and `commit_connection` sends `None` DELIBERATELY for
            # a template whose service the build does not have (`DEF-MET-9179`),
            # so a Water template on an electric-only build read Water again.
            # The rule is the build's, so it is applied HERE, under every door
            # that raises on a build: the commit and the build page's form.
            if (
                service is not None
                and connection is not None
                and not ConnectionService.objects.filter(
                    tenant_id=tenant_id, connection_id=connection.id, service_id=service.id
                ).exists()
            ):
                service = None
    if service is None and asset_walk is not None and asset_walk["service_id"]:
        from apps.tenancy import models as tenancy_models

        service = tenancy_models.Service.objects.filter(pk=asset_walk["service_id"]).first()
    scope = scope or SCOPE_PREMISE
    # The 🚩 NCT-01 draws on the order's name. Stamped from the template it was
    # produced by; an ad-hoc order has no template and is not a gate unless the
    # caller says so.
    is_gate = bool(data["is_gate"]) if "is_gate" in data else bool(template and template.is_gate)
    # BR-WRK-024 (CR-070 wave P) — WHY this job exists, and the flow record's own
    # number. Refused in Python with a readable sentence before the CHECK
    # (`ck_work_orders_source`) sees it, the same posture the anchor takes above.
    source = str(data.get("source") or "").strip() or None
    if source is not None and source not in WORK_ORDER_SOURCES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.order.source_unknown",
            br_ref="BR-WRK-024",
            params={"source": source},
        )
    source_ref = str(data.get("source_ref") or "").strip() or None
    # ── CR-070 wave G · THE PROMISE, STAMPED AT THE RAISE (BR-WRK-018) ───────
    type_ref = _resolve_order_type(tenant_id, data, str(data.get("type") or "").strip())
    priority = _resolve_priority(tenant_id, data, type_ref)
    raised_at = timezone.now()
    due_at = _resolve_due_at(data, priority, raised_at, type_ref)
    est_duration = _resolve_est_duration(data, type_ref, template)
    area_id = data.get("area_id") or None
    if area_id is not None:
        from apps.tenancy import models as tenancy_models

        if not tenancy_models.Area.objects.filter(tenant_id=tenant_id, pk=area_id).exists():
            raise errors.deny_as_not_found("BR-TEN-003")
    # CR-161-BRC10 W4 — the utility's OWN fields on the order. ONE raise serves
    # every door (`07-endpoints.md` §1 row 14), and only the New work order
    # screen (`WORK_NEW`) draws them: it always sends `custom_data`, `{}` when
    # there are none, and the build commit, the flows, the rules engine and the
    # Assets door never do. So the key's presence names the screen, a required
    # field binds there and nowhere else (BR-TEN-052 as amended), and a door
    # that sends nothing writes `{}` and asks tenancy nothing. Checked BEFORE
    # the transaction, so a refusal burns no `WO-` number.
    custom_data = (
        seams.validate_custom_data(
            "work_orders", data.get("custom_data") or {}, screen=WORK_ORDER_NEW_SCREEN
        )
        if "custom_data" in data
        else {}
    )
    with transaction.atomic():
        number = metering_services._allocate_unused_number(
            actor, WORK_ORDER_SERIES, warnings, model=WorkOrder, field="order_no"
        )
        order = WorkOrder.objects.create(
            tenant_id=tenant_id,
            order_no=number,
            connection=connection,
            premises=premises,
            account=account,
            # `DEF-WRK-9638` — never a placeholder word: the typed name, else
            # the job type's, else the template's, else nothing (the page then
            # derives it). `"unspecified"` stored here read as a real job name.
            type=(
                str(data.get("type") or "").strip()
                or (type_ref.name if type_ref is not None else "")
                or (template.name if template is not None else "")
            ),
            scope=scope,
            service=service,
            unit_id=data.get("unit_id"),
            asset_id=asset_id,
            blocked_by_id=data.get("blocked_by"),
            # CR-070 wave I (`BR-WRK-054`) — *the follow-up names what failed*.
            # Written by `_failed_outcome_chain` and by nothing else today; a
            # caller that sets it without `source = failed_outcome` is making a
            # claim the RAISED BY column will contradict.
            follows_order_id=data.get("follows_order_id"),
            # `DEF-CUS-6363` — the note a clerk typed on a flow's work-order
            # row, the office talking to the field (this column's own note).
            # Absent on every other door, which writes NULL exactly as before.
            technician_notes=str(data.get("technician_notes") or "").strip() or None,
            state=WO_PLANNED,
            mode=mode,
            template=template,
            # BR-WRK-008 — copy, never link: the order remembers WHICH version
            # it came from, so a later publish changes nothing about it.
            template_version=(template.version if template is not None else None),
            is_gate=is_gate,
            source=source,
            source_ref=source_ref,
            # CR-070 wave G — the dispatch columns, every one of them STAMPED
            # here and never derived on read (BR-WRK-018, US-WRK-008 TC-4).
            type_ref=type_ref,
            priority=priority,
            due_at=due_at,
            est_duration=est_duration,
            area_id=area_id,
            dispatch_state=DISPATCH_QUEUED,
            custom_data=custom_data,
            is_sample=(
                connection.is_sample
                if connection is not None
                else bool(data.get("is_sample")) or bool(premises and premises.is_sample)
            ),
        )
        # ── CR-070 wave H · BR-WRK-008 — THE ORDER TAKES ITS OWN COPIES ────
        # Six tables, written by WORK because they are Work's (`work/0010`),
        # called by name from here because `work_orders` is metering's and
        # neither module writes the other's table (B2 §2). It is the shape
        # `publish` already takes in the other direction.
        #
        # ⚠ INSIDE THIS TRANSACTION ON PURPOSE: an order that exists with half
        # a checklist is a job a technician can pick up and complete without
        # the steps somebody meant them to follow. A refusal in the copy takes
        # the order row with it.
        #
        # ⚠ AND IT HANGS OFF THE RAISE RATHER THAN OFF THE WIZARD, so the five
        # customer flows, `commit_connection`, a failed outcome's follow-up and
        # the seeder all get copies too — `BR-WRK-008` says *when an order is
        # raised*, not *when a dispatcher raises one*.
        from apps.work import order_copies as work_order_copies

        work_order_copies.copy_template_onto_order(
            actor,
            order_id=order.id,
            template_id=template.id if template is not None else None,
            template_version=order.template_version,
            tenant_id=tenant_id,
        )
        _audit(
            actor,
            "work_order.created",
            "work_order",
            order.id,
            after={
                "order_no": number,
                "type": order.type,
                "scope": scope,
                "mode": mode,
                "is_gate": is_gate,
                # BR-WRK-006 — the audit row names the anchor(s) the order stands on.
                "connection_no": connection.connection_no if connection is not None else None,
                "premise_no": premises.premise_no if premises is not None else None,
                "account_no": account.account_no if account is not None else None,
                "asset_id": str(asset_id) if asset_id else None,
                # BR-WRK-024 — hard rule 7's row says WHY, not only what.
                "source": source,
                "source_ref": source_ref,
                # BR-WRK-018 — the audit row carries the PROMISE that was made,
                # so a missed SLA can be read back to the moment it was set.
                "priority": priority.code if priority is not None else None,
                "due_at": due_at.isoformat() if due_at is not None else None,
            },
        )
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        "connection_id": str(order.connection_id) if order.connection_id else None,
        "premises_id": str(order.premises_id) if order.premises_id else None,
        "account_id": str(order.account_id) if order.account_id else None,
        "asset_id": str(order.asset_id) if order.asset_id else None,
        "source": order.source,
        "source_ref": order.source_ref,
        "priority": priority.code if priority is not None else None,
        "due_at": due_at.isoformat() if due_at is not None else None,
        "dispatch_state": order.dispatch_state,
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE D · THE TEMPLATE WRITER THIS FILE HAS OWED SINCE 2026-08-25
# ══════════════════════════════════════════════════════════════════════════
#
# `apps/metering/sample_data.py` records the debt in its own words —
# *"a `create_work_order_template` service is OWED"* — and has written rows
# straight through the model ever since, because there was nothing to write
# them through. `US-WRK-015` is the story that pays it.
#
# ⚠ **WHY IT IS HERE AND NOT IN `apps/work/`.** `work_order_templates` is
# METERING's table (`03-field-map.md` §4, PENDING the blueprint's §16). Work
# owns the CONCEPT and orchestrates the write — `apps/work/templates_svc.py`
# holds the seven child collections, the version log and every rule about
# them — but the header row belongs to this module, so this module writes it,
# reached by name through `apps/work/seams/metering_seam.py`. That is exactly
# the door `BR-WRK-002` sanctions and `G78` enforces, and it is the same shape
# `raise_work_order` already uses for `create_work_order`.
#
# The day `03-field-map.md` §4 is decided and the table moves, these four
# functions move with it and the seam changes; nothing that calls them does.

#: ⚠ **EVERY REFUSAL BELOW REUSES A `message_key` THAT ALREADY RESOLVES, AND
#: THAT IS A CONSTRAINT RATHER THAN A PREFERENCE.** `G32` requires every key
#: the backend raises to resolve to a customer sentence in `en.json`, with a
#: ratchet at ZERO — a key that resolves to nothing renders as its own raw
#: dotted name on a clerk's screen (`DEF-322`). The wave D lane could not write
#: to the catalogues (three other lanes were editing them the same afternoon),
#: so it reuses sentences that are TRUE of these refusals rather than minting
#: `work.template.*` keys that would resolve to nothing.
#: **Two of them are looser than a purpose-written sentence would be** and are
#: filed for the commit that lands the catalogue keys: `assets.must_be_positive`
#: says *"Enter a number greater than zero"* for a crew size (correct, but says
#: nothing about crews), and `settings.lookups.locked_referenced` says
#: *"{{used_by}} records reference this entry"* for a template that has produced
#: work orders (correct, and the count is right, but *records* is vaguer than
#: *work orders*). The SCREEN says both properly — `Work-022` draws its own
#: sentence with the count — so what is loose here is the API's answer to a
#: scripted call, not what a person reads.

#: The header fields a caller may set. **An unknown field is REFUSED, never
#: ignored** (B12 §3) — a silently dropped `crew_size` is a template that says
#: one technician when the utility asked for two.
TEMPLATE_HEADER_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "service",
        "scope",
        "sequence",
        "type_id",
        "skill_id",
        "safety_kit_id",
        "crew_size",
        "est_duration",
        "is_gate",
        "no_gate_reason",
    }
)


def _template_or_404(template_id: Any) -> "WorkOrderTemplate":
    """The template, or a 404 — never a 403 (HR-1: existence must not leak).

    A cross-tenant id and an absent one answer byte-identically, which is
    `US-WRK-015` TC-6 and `US-WRK-018` TC-6.
    """
    row = WorkOrderTemplate.objects.filter(tenant_id=_tenant_id(), pk=template_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _template_header_row(row: "WorkOrderTemplate") -> dict[str, Any]:
    """The header as the seam publishes it. **`id` is here and it is a LINK
    target, never a visible value** (B14 rule 31): what a person reads is
    `template_no`."""
    return {
        "id": str(row.id),
        "template_no": row.template_no,
        "name": row.name,
        "service_id": str(row.service_id) if row.service_id else None,
        "scope": row.scope,
        "sequence": row.sequence,
        "type_id": str(row.type_id) if row.type_id else None,
        "skill_id": str(row.skill_id) if row.skill_id else None,
        "safety_kit_id": str(row.safety_kit_id) if row.safety_kit_id else None,
        "crew_size": row.crew_size,
        "est_duration": row.est_duration,
        "is_gate": row.is_gate,
        "no_gate_reason": row.no_gate_reason,
        "is_sample": row.is_sample,
        "active": row.active,
        "version": row.version,
        "updated_at": row.updated_at,
    }


def _clean_template_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Refuse an unknown field; refuse a name that is only whitespace."""
    unknown = sorted(set(data) - TEMPLATE_HEADER_FIELDS)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="metering.unknown_field",
            params={"field": unknown[0]},
        )
    cleaned = dict(data)
    if "name" in cleaned:
        name = str(cleaned["name"] or "").strip()
        if not name:
            raise errors.ValidationError(
                errors.VAL_REQUIRED, message_key="work.lookups.required"
            )
        cleaned["name"] = name
    if "crew_size" in cleaned and cleaned["crew_size"] is not None:
        try:
            crew = int(cleaned["crew_size"])
        except (TypeError, ValueError):
            crew = 0
        if crew < 1:
            raise errors.ValidationError(
                errors.VAL_RANGE, message_key="assets.must_be_positive"
            )
        cleaned["crew_size"] = crew
    if "service" in cleaned and cleaned["service"] is not None:
        cleaned["service"] = _service_row(cleaned["service"])
    return cleaned


def _refuse_duplicate_template(
    tenant_id: Any, service_id: Any, name: str, version: int, exclude_id: Any = None
) -> None:
    """`BR-WRK-010` in Python, so a clerk reads a sentence rather than a
    constraint name. The database key is the backstop, not the message."""
    qs = WorkOrderTemplate.objects.filter(
        tenant_id=tenant_id, service_id=service_id, name=name, version=version
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    if qs.exists():
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-010",
            message_key="work.lookups.duplicate_code",
            params={"existing": name},
        )


def create_work_order_template(actor: Any, payload: Any = None) -> dict[str, Any]:
    """**The write `sample_data.py` says is OWED** — one template header, as a
    DRAFT (`BR-WRK-011`: publish is the one write, so nothing here is a
    version and nothing here allocates a number).

    `version` is 0 and `template_no` is NULL until `publish_work_order_template`
    is called. That is not a placeholder: a draft has produced nothing an order
    can stamp, and `BR-TEN-035` forbids handing out a number that a row might
    never keep.
    """
    data = _clean_template_payload(metering_services._payload_dict(payload))
    tenant_id = _tenant_id()
    name = str(data.get("name") or "").strip()
    if not name:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="work.lookups.required")
    service = data.get("service")
    if service is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.lookups.required"
        )
    scope = data.get("scope") or SCOPE_PREMISE
    if scope not in WORK_ORDER_SCOPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.work_order_scope_unknown",
            params={"scope": scope},
        )
    _refuse_duplicate_template(tenant_id, service.id, name, 0)
    with transaction.atomic():
        row = WorkOrderTemplate.objects.create(
            tenant_id=tenant_id,
            service=service,
            name=name,
            scope=scope,
            # ⚠ **0, NOT `max + 1`.** `BR-WRK-016` reads `sequence >= 1` as
            # *"holds a place in the connection sequence"*, so an authored
            # leak-investigation or meter-exchange template must NOT get one by
            # default or New Connect step 6 would propose it (`DEF-WRK-3573`).
            # A caller that means it says so.
            sequence=int(data.get("sequence") or 0),
            type_id=data.get("type_id"),
            skill_id=data.get("skill_id"),
            safety_kit_id=data.get("safety_kit_id"),
            crew_size=int(data.get("crew_size") or 1),
            est_duration=data.get("est_duration"),
            is_gate=bool(data.get("is_gate", False)),
            no_gate_reason=data.get("no_gate_reason"),
            version=0,
        )
        _audit(
            actor,
            "work_order_template.created",
            "work_order_template",
            row.id,
            after={"name": row.name, "scope": row.scope, "version": 0},
        )
    return _template_header_row(row)


def update_work_order_template(actor: Any, template_id: Any, payload: Any = None) -> dict[str, Any]:
    """Header edits on a DRAFT or a published template's editable face.

    ⚠ **`active` IS NOT IN `TEMPLATE_HEADER_FIELDS` AND THAT IS `DEF-WRK-3579`.**
    Deactivate and Reactivate are named routes with their own audit action;
    a `PATCH` that could flip `active` would let the one control a supervisor
    presses arrive as an untraceable field edit.

    ⚠ **A SUPERSEDED VERSION IS READ-ONLY** (`US-WRK-018` TC-3). What is edited
    here is the template's CURRENT face; the versions log is append-only and no
    route reaches into it.
    """
    row = _template_or_404(template_id)
    data = _clean_template_payload(metering_services._payload_dict(payload))
    before = _template_header_row(row)
    service = data.get("service", row.service)
    name = data.get("name", row.name)
    _refuse_duplicate_template(_tenant_id(), service.id, name, row.version, exclude_id=row.id)
    if "scope" in data and data["scope"] not in WORK_ORDER_SCOPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.work_order_scope_unknown",
            params={"scope": data["scope"]},
        )
    for field, value in data.items():
        setattr(row, field, value)
    with transaction.atomic():
        row.save()
        _audit(
            actor,
            "work_order_template.updated",
            "work_order_template",
            row.id,
            before={"name": before["name"], "scope": before["scope"]},
            after={"name": row.name, "scope": row.scope},
        )
    return _template_header_row(row)


def publish_work_order_template(
    actor: Any, template_id: Any, *, issue_date: Any = None
) -> dict[str, Any]:
    """**THE ONE WRITE** (`BR-WRK-011`) — the header half of it.

    Sets the next version, allocates `ST-{0000}` from the tenant's own series
    the FIRST time (`BR-TEN-035`: an issued number is never reused and never
    renumbered, so a v2 keeps v1's number), and makes the template active.

    ⚠ **THE VERSIONS ROW IS NOT WRITTEN HERE.** `work_order_template_versions`
    is Work's table and this module does not write it — `apps/work/
    templates_svc.publish` writes it inside the same transaction, which is the
    boundary running in the direction G78 cannot see and B2 §2 still forbids.
    """
    row = _template_or_404(template_id)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        locked = WorkOrderTemplate.objects.select_for_update().get(pk=row.pk)
        version = int(locked.version or 0) + 1
        _refuse_duplicate_template(
            _tenant_id(), locked.service_id, locked.name, version, exclude_id=locked.pk
        )
        if not locked.template_no:
            locked.template_no = metering_services._allocate_unused_number(
                actor,
                core_numbering.SERVICE_TEMPLATE,
                warnings,
                model=WorkOrderTemplate,
                field="template_no",
            )
        locked.version = version
        locked.active = True
        locked.save(update_fields=["template_no", "version", "active", "updated_at"])
        _audit(
            actor,
            "work_order_template.published",
            "work_order_template",
            locked.id,
            after={"template_no": locked.template_no, "version": version},
        )
    return {**_template_header_row(locked), "warnings": warnings}


def touch_work_order_template(template_id: Any) -> None:
    """Move a template's `updated_at` and NOTHING else.

    Work's `templates_svc` calls this after replacing one of the seven child
    collections it owns, so `publish` can tell *"the bundle changed"* from
    *"somebody double-clicked"*. It writes no audit row: the collection
    replace already wrote one naming the collection and its row count, and a
    second entry saying the timestamp moved is noise in a trail a supervisor
    reads.
    """
    WorkOrderTemplate.objects.filter(tenant_id=_tenant_id(), pk=template_id).update(
        updated_at=timezone.now()
    )


def set_work_order_template_active(
    actor: Any, template_id: Any, *, active: bool
) -> dict[str, Any]:
    """Deactivate / Reactivate — `BR-WRK-012`'s two named routes.

    Deactivating stops NEW orders being proposed from the template and leaves
    every order already raised readable, because an order carries its own
    copies (`BR-WRK-008`). This is the only writer of `active`.
    """
    row = _template_or_404(template_id)
    was = row.active
    with transaction.atomic():
        row.active = bool(active)
        row.save(update_fields=["active", "updated_at"])
        _audit(
            actor,
            "work_order_template.reactivated" if active else "work_order_template.deactivated",
            "work_order_template",
            row.id,
            before={"active": was},
            after={"active": row.active},
        )
    return _template_header_row(row)


def count_orders_from_template(template_id: Any, version: Any = None) -> int:
    """How many orders this template has produced — the figure `Delete` is
    refused with and the Versions tab counts by (`US-WRK-018` TC-7).

    ⚠ **COUNTED FROM `work_orders`, NEVER CACHED ON THE TEMPLATE.** A cached
    count is a second answer to a question the orders table already answers,
    and it is the copy that goes stale (PO, 2026-09-05: *"two answers to one
    question is how a figure drifts"*).
    """
    qs = WorkOrder.objects.filter(tenant_id=_tenant_id(), template_id=template_id)
    if version is not None:
        qs = qs.filter(template_version=version)
    return qs.count()


def delete_work_order_template(actor: Any, template_id: Any) -> dict[str, Any]:
    """`BR-WRK-012` — **refused while any version is referenced**, naming the
    count, with Deactivate offered instead.

    The refusal carries the number because *"it has produced orders"* invites
    the question *"how many?"* and the screen would then have to ask again.
    """
    row = _template_or_404(template_id)
    raised = count_orders_from_template(row.id)
    if raised:
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-WRK-012",
            message_key="settings.lookups.locked_referenced",
            params={"used_by": raised},
        )
    before = {"name": row.name, "template_no": row.template_no, "version": row.version}
    with transaction.atomic():
        row.delete()
        _audit(
            actor,
            "work_order_template.deleted",
            "work_order_template",
            template_id,
            before=before,
        )
    return {"id": str(template_id), "deleted": True}


def tag_charges_to_account(actor: Any, connection_id: Any, account_id: Any) -> dict[str, Any]:
    """**BR-MET-113 — tag this build's charges to an account number.**

    PO 2026-08-25: *"You will have to assign account number to owner and tag
    everything to account number"*. This is the *tagging* half, and it works
    today: it attaches an account that **already exists**.

    ⚠ **It refuses to RE-tag.** A quote that moved from one account to another
    after being stated is a debt that changed debtor with nothing recording the
    move — the same hazard financial immutability exists for (hard rule 4). A
    correction is a new charge on the right account, not a quiet re-pointing of
    the old one.
    """
    connection = _connection_or_404(connection_id)
    _refuse_if_cancelled(connection)
    if connection.owner_account_id is not None:
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-113",
            message_key="metering.connection_payer_already_set",
            params={"connection_no": connection.connection_no or ""},
        )
    account = _account_or_404(account_id)
    connection.owner_account = account
    connection.save(update_fields=["owner_account", "updated_at"])
    _audit(
        actor,
        "connection.payer_tagged",
        "connection",
        connection.id,
        after={"owner_account_id": str(account.id), "br_ref": "BR-MET-113"},
    )
    return {
        "id": str(connection.id),
        "owner_account_id": str(account.id),
        "account_no": account.account_no,
        "br_ref": "BR-MET-113",
    }


#: **BR-MET-112's manifest — the seven counts step 9 draws.**
#: `Customer 1 · Premises 1 · Units 26 · Meters 50 · Sub-meter links 24 ·
#: Plan assignments 26 · One-time charges $14,435.00`. It is a CONTRACT, not a
#: log line: the wizard shows it before committing and the commit must produce
#: exactly it, so the keys are fixed here rather than assembled per call.
#:
#: ⚠ **`work_orders` IS AN EIGHTH KEY FROM 2026-09-16 AND THE SEVEN ABOVE IT DO
#: NOT MOVE (`DEF-MET-5428`).** Step 6 has proposed orders since `CR-070` wave
#: E and step 8 has told the clerk how many will be raised; the commit raised
#: none and REPORTED none, so the figure on the review screen was computed in
#: the browser from the proposal and compared with nothing. **A figure the
#: server never returns cannot be wrong on screen and cannot be right either** —
#: which is why the count is added here rather than only the write. The manifest
#: is the contract the screen reads its own promise back off.
MANIFEST_KEYS: tuple[str, ...] = (
    "customers",
    "premises",
    "units",
    "meters",
    "sub_meter_links",
    "plan_assignments",
    "one_time_charges",
    "work_orders",
    # ⊕ **`messages` — the NINTH count, 2026-09-16.** Step 8 draws *"Three
    # messages are queued to the owner"* and until today the browser RECOMPUTED
    # that from the ticks it still held. `DEF-MET-5428` is the identical defect
    # one step over: the review step promised nine work orders and the server
    # raised none. A figure the server never returns cannot be wrong on screen
    # and cannot be right either, so the screen reads THIS.
    "messages",
    # ⊕ **`one_time_charge_invoice_no` — the TENTH key, 2026-09-16 (`CR-109`).**
    # Step 8 draws the quote as money the developer now owes, and a figure with
    # no document behind it is a promise the screen cannot keep. The server
    # names the invoice it actually raised, so the review step READS the
    # posting instead of recomputing the total from the lines it just showed
    # itself — `DEF-MET-5428`'s lesson one step over. `None` on every path that
    # posted nothing, never an empty string: an absence says so.
    "one_time_charge_invoice_no",
    # ⊕ **`one_time_charge_payment_no` AND `one_time_charge_paid` — THE
    # ELEVENTH AND TWELFTH KEYS, 2026-09-28 (`BR-MET-1187`, `CR-150-BRC09`
    # task `B1`).** Step 5 draws *what pressing Create makes*, and under the
    # PO's ruling one of the things it now makes is a PAYMENT: *"we create
    # entries in books"*, *"do it at creation once submitted"*, and *"based on
    # payment type we nedd to give all paymnet fields"*.
    #
    # ⚠ **THE RECEIPT NUMBER, NEVER THE PAYMENT'S ROW ID** (B14 rule 31: no
    # database id is ever the visible value of a field), and the AMOUNT as the
    # stored 4-decimal string `one_time_charges` beside it already uses.
    # `None` on every build where no payment was taken — which is the drawn
    # default, *No payment now* — because `0` would read as *"they paid
    # nothing"* where the truth is *"nobody was asked to"*.
    #
    # ⚠ **HERE RATHER THAN RECOMPUTED ON THE SCREEN, FOR `DEF-MET-5428`'s
    # REASON**, which this constant's own header already states: a figure the
    # server never returns cannot be wrong on screen and cannot be right
    # either.
    "one_time_charge_payment_no",
    "one_time_charge_paid",
)



#: The three payers step 6 draws, and what each one means here.
#:
#: ⚠ **THE THIRD IS DRAWN AS REFUSED AND STAYS REFUSED.** *"The connection
#: itself — Refused: a charge on a build is a debt owed by nobody, and nothing
#: in the product can settle it."* `BR-MET-113`'s own field note says why at
#: length: a charge floating on a `connections` row needs a SECOND money path —
#: a payable that is not an invoice, settled by a payment referencing no
#: account — and B4's ❄️ FROZEN math, the ledger and hard rule 7 are all
#: account-shaped. There is ONE money path.
#: Hard rule 2's written precision for money. Used to state two prices in ONE
#: precision in a refusal, never to round one — `quantize` raises rather than
#: discards, which is the behaviour a money path wants.
_MONEY_4 = Decimal("0.0001")

PAYER_OWNER_ACCOUNT = "owner_account"
PAYER_EACH_UNIT_FIRST_BILL = "each_unit_first_bill"
PAYER_CONNECTION = "connection"


#: ⚠ **THE TWO ABSENCES THAT MEAN *THERE IS NOTHING TO WRITE* — `BR-MET-1187`,
#: PO ruling 2026-09-28.** Every other reason `_post_connection_quote` cannot
#: post means there IS a books entry to write and it failed, and the ruling
#: makes that a REFUSAL: *"It is one act: if the books entry cannot be written,
#: the connection is not created either."*
#:
#: ⚠ **STATING THE BOUNDARY IS PART OF THE RULING AND NOT A SOFTENING OF IT.**
#: The business rule says so in terms — *"A BUILD THAT NAMES NO CHARGE HAS
#: NOTHING TO WRITE AND IS UNAFFECTED … the rule bites where there IS an entry
#: to write and it fails"* — because *"the connection is not created"* read
#: without it would refuse every build that raises no fee, and a build with no
#: one-time charge on it is perfectly lawful (`BR-MET-1178`).
#:
#: `quote_has_no_chargeable_line` is the second of the two and it is the one a
#: reader has to think about: the request's lines are all either WAIVED by a
#: named person with a recorded reason or already carry an invoice reference
#: from an earlier commit. Both mean the money has already been dealt with, so
#: there is no entry this commit owes anybody — the same statement as *nobody
#: put a charge on this build*, arriving by a different route.
#:
#: ⚠ **THE OTHER THREE ARE NOT ON THIS LIST AND MUST NOT JOIN IT.** The payer's
#: four codes, `quote_payment_terms_not_captured` and
#: `billing_quote_door_unpublished` each describe a charge that EXISTS and
#: could not be raised. Adding one here would put `$1,035.00` back on a
#: `connections` row with no invoice behind it, which is `DEF-MET-7641`.
QUOTE_ABSENCES_WITH_NOTHING_TO_WRITE: frozenset[str] = frozenset(
    {
        "build_names_no_charge",
        "quote_has_no_chargeable_line",
    }
)

#: ── `BR-MET-1187` · THE PAYMENT STEP 4 TAKES, IN THE PAYLOAD'S OWN WORDS ────
#:
#: PO 2026-09-28, on the same breath as the books entry: *"based on payment
#: type we nedd to give all paymnet fields"*. Five keys, and **every one of
#: them is optional**: the drawn payment option's first entry is *No payment
#: now*, which is a build committed with an invoice and no receipt.
#:
#: ⚠ **`payment_method` IS THE TENANT'S OWN CODE AND NEVER A DRAWN LABEL.**
#: `BR-PAY-026` makes the method list a seeded, tenant-extensible LOOKUP:
#: `cash`, `check`, `card`, `ach`, `wire`, `money_order` are seeded and a
#: utility may add its own. The drawing's *Cheque* is the code `check` and its
#: *Bank transfer* is `ach` or `wire`; a screen offers `GET /payments`
#: `methods[]` and never a hand-typed list, which is the `SignupWizard` lesson
#: (a list typed out by hand fails SILENTLY when the catalogue moves).
#: ⚠ **NO CLEARING DATE — `CR-186-BRC10` (PO 2026-10-21), `DEF-CUS-10324`.**
#: This list carried `payment_cleared_date` because a payment with no clearing
#: date used to be `processing`, met no bill and posted no ledger pair. Since
#: CR-186 every payment is `posted` at entry — applied to the build's bill and
#: journalled at once — and becomes `cleared` only when its deposit batch is
#: reconciled with the bank. `record_payment` no longer stores a caller's
#: clearing date, so the step no longer asks for one and this commit no longer
#: reads one; a stale client that still sends the key has it ignored (this
#: payload has no unknown-key refusal to route it to).
PAYMENT_FIELDS: tuple[str, ...] = (
    "payment_method",
    "payment_amount",
    "payment_date",
    "payment_reference",
    "payment_memo",
    # DEF-PAY-9263 — not a payment FACT: the clerk's *Record anyway* after
    # "Looks like a duplicate" (`BR-PAY-1199`). Only a literal `true` counts.
    "payment_duplicate_confirmed",
)

#: What this build's counter payment is called inside payments' idempotency
#: key — the REFERENCE half of `"<source>|<reference>"`, `entry` being the
#: source. The whole string lands in `payments.webhook_key`, whose
#: `UNIQUE (tenant_id, webhook_key)` is B2 DB-12's row and hard rule 6's
#: guarantee here. Written as a constant so the one place that composes it and
#: the tests that assert it read the same characters — a key spelled twice is
#: a key that dedupes nothing the day one spelling moves.
PAYMENT_KEY_PREFIX = "new-connect:"


def _post_connection_quote(
    actor: Any,
    connection: Any,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Raise this build's quote as a real receivable, or say precisely why not.

    ⚠ **THIS IS `OQ-379`'s ANSWER AND IT REPLACES A STATED ABSENCE
    (`quote_recorded_not_posted`) THAT WAS TRUE UNTIL 2026-09-16.** The absence
    read: *"Step 7's quote is four coded lines with quantities and billing's
    one-time door takes ONE connection_charge_code with no amount and no lines
    (BR-BIL-020, an absent field rather than a removable validation). The total
    is recorded on the connection and posted by nothing."* `CR-109` widened that
    door (`billing.fee_bill.raise_and_issue_quote_bill`), so the sentence is no
    longer true and is deleted rather than reworded — **a stated absence that
    outlives its cause is a lie the product tells about itself** (hard-won
    law 1).

    ⚠⚠ **THIS FUNCTION WAS WRITTEN ON 2026-09-16 AT 04:09, REVERTED OUT OF THIS
    FILE AT 04:12 BY A WHOLE-FILE PATHSPEC COMMIT FROM A STALE BLOB, AND
    RESTORED HERE — `DEF-MET-5446`, hard-won law 11 mechanism two.** It is NOT
    a blind paste of what was lost: the door it calls was repaired three times
    the same afternoon (`DEF-BIL-5457` a master account could not be billed ·
    `DEF-BIL-5458` a counted line could never be issued · `DEF-LED-5459` the
    ledger could not dimension a premises-anchored account), and every argument
    below was re-read against `fee_bill.raise_and_issue_quote_bill`'s signature
    as it stands today rather than as it stood then. **A caller shaped for an
    older signature would be worse than the gap**, because the gap at least
    said so out loud.

    ── WHERE THE LINES COME FROM — TWO SOURCES SINCE 2026-09-21 ─────────────
    ⚠ **`BR-MET-1178`, PO ruling 2026-09-21: a build PRICES ITSELF, and the
    application it came from is PROVENANCE rather than a dependency.** Verbatim:
    *"…this request is new work and recognized seperately from applcaition and
    hence we should not make it dependent on applciation #"*.

    **(1) A BUILD WITH A REQUEST** still takes the APPROVED SERVICE REQUEST's
    quote (`connections.service_request`). The ruling removes a REQUIREMENT, not
    a source: those lines are what the customer was SHOWN, `BR-CUS-090`'s
    waivers apply to them, and `_refuse_quote_price_drift` still refuses a
    catalogue that has moved under a quoted price. The finance-proved posting of
    2026-09-16 (`BL-2609-000082`) is untouched.

    **(2) A BUILD WITH NO REQUEST** prices ITSELF, from `quote_lines` on the
    commit payload: a **charge code the clerk picked out of the tenant's own
    catalogue** and a **quantity counted from step 4's grid**. Accounts
    blueprint p094 says so in red — *"Every quantity is counted from the
    services grid, not typed"*.

    ⚠ **THE SENTENCE THIS REPLACES IS SUPERSEDED, NOT REWORDED, AND IT IS
    DATED.** It read *"A quote arrives with an approved application; a build a
    developer starts without one is priced by nobody and charges nothing."*
    **Measured while it stood: not one of the nine connections in the demo
    tenant carried a quote total, and the wizard sent `service_request_id`
    EMPTY on every commit — so no build made through that screen could EVER
    raise a charge.**

    ⚠ **THE PRICE-DRIFT REFUSAL IS NOT RUN ON A BUILD'S OWN LINE, AND THAT IS
    NOT A GAP.** It exists because a request's fee line stores the `unit_amount`
    a customer was QUOTED; a build's own line stores no price at all, so the
    catalogue IS the price and there are not two figures to disagree.
    `OQ-BIL-12376` stays open and is about the request path.

    ⚠ **NOTHING IS CHARGED TWICE, STRUCTURALLY.** The request path stamps
    `service_request_fees` so a second commit cannot re-raise it. A build's own
    lines have no such row and need none: `commit_connection` refuses any
    connection that is not `DRAFT` (`metering.connection_already_committed`), so
    a second commit cannot happen at all. The bill is found again through
    `connections.quote_invoice_id`.

    ── WHAT CROSSES THE SEAM IS A COUNT, NEVER A FIGURE ─────────────────────
    Metering hands billing `(charge_code, quantity)` per line. Billing reads the
    price from the tenant's own charge-code row and multiplies (`BR-BIL-007`,
    `BR-BIL-020`), which is CLAUDE.md hard rule 2's *"no figure is multiplied up
    anywhere but the server"* — the server that owns the price list. **Nothing
    here multiplies anything**, and that is why there is no arithmetic in this
    function at all. It follows that there is no rounding here either: hard
    rule 2 rounds ONCE, at finalization, and finalization is billing's.

    ── THE PRICE CHECK, AND WHY IT REFUSES RATHER THAN CHOOSES ──────────────
    A quote line stores the `unit_amount` the customer was shown: the charge
    code's price AT THE MOMENT THE FEE WAS ADDED — since `DEF-CUS-6416`,
    `customers.service_request_service.add_fee_line` prices the line from the
    catalogue and refuses any other figure (this read *"caller-supplied"* until
    `DEF-CUS-6461`). A bill is priced from the catalogue as it stands at commit
    (`BR-BIL-007`), so the snapshot is never what is billed. But billing a
    DIFFERENT figure from the one the customer was quoted,
    silently, is its own defect. So the two are COMPARED and a disagreement
    refuses the whole commit by name, printing the code and both figures.
    Whether a quote holds its price is a commercial promise only the utility can
    make: `OQ-BIL-12376`, open, and nothing here resolves it by choosing.

    ── FIVE THINGS THAT STOP A POSTING, EACH REPORTED AS ITSELF ─────────────
    Each is returned as a coded ABSENCE rather than raised, and **the CALLER
    now decides which of them is fatal** — see `commit_connection` step 6 and
    `_refuse_a_books_entry_that_cannot_be_written`.

    ⚠ **THIS PARAGRAPH READ *"Every one is an ABSENCE on a successful commit
    rather than a refusal, because none of them means the BUILD is wrong — only
    that no charge can be raised yet. A build that created 26 units must not be
    thrown away because nobody captured payment terms"* UNTIL 2026-09-28, AND
    THE PRODUCT OWNER RULED THE OTHER WAY.** `BR-MET-1187`, verbatim: *"we
    create entries in books"* and *"do it at creation once submitted"*, over
    the sentence *"It is one act: if the books entry cannot be written, the
    connection is not created either."* A build that kept its 26 units and lost
    its `$1,035.00` was the outcome nobody chose; the clerk is now stopped and
    told, which is a worse moment and a better outcome.

    ⚠ **TWO OF THE FIVE SURVIVE THAT RULING AND THE BOUNDARY IS PART OF IT.**
    `build_names_no_charge` and `quote_has_no_chargeable_line` mean there is
    nothing to write, so there is nothing to fail — a build that raises no fee
    is lawful and commits exactly as it did. The other three describe a charge
    that EXISTS and could not be raised, and those refuse.
    `QUOTE_ABSENCES_WITH_NOTHING_TO_WRITE` is where the split is named.

    **The shape of this function does not move**: it still returns rather than
    raising, because it is also the read `connection_reads.preview_quote`'s
    neighbour reasons about, and because a refusal composed HERE could not say
    which step a clerk should go back to. The price disagreement above is still
    the one thing it raises itself, because there the money is knowable and
    wrong.

    ⚠ **DEPOSITS ARE NOT RAISED HERE AND THEIR ABSENCE IS DELIBERATE.** A
    deposit is a LIABILITY at `2300`, not revenue; it has no charge-code row;
    and `BR-RAT-020`/`BR-RAT-023` put its amount on the plan's deposit rules and
    *"explicitly supersede a flat deposit charge"*. Which signed rule the PO's
    2026-09-16 deposit ruling supersedes is `OQ-BIL-12381`, open, with a
    `$900.00` worked figure. **Connection fees and work-order fees only** — a
    deposit stubbed through this path would be revenue the utility has to give
    back.
    """
    request_id = getattr(connection, "service_request_id", None)
    # ── BR-MET-1178 · TWO SOURCES, AND THE BUILD'S OWN IS THE NEW ONE ────────
    # A build that came from an approved application takes that application's
    # quote; a build a developer started directly prices ITSELF. See this
    # function's docstring for the ruling and for what it does NOT change.
    own_lines = build_quote_lines(data) if request_id is None else []
    lines = seams.request_quote_lines(request_id) if request_id is not None else own_lines
    if not lines:
        if request_id is None:
            return {
                "posted": False,
                "total": None,
                "invoice_no": None,
                "absence": {
                    "field": "one_time_charges",
                    "code": "build_names_no_charge",
                    "tracks": "BR-MET-1178",
                    "detail": (
                        "Nobody put a charge on this build, so there is nothing to raise. "
                        "A build prices itself from the charge codes a clerk picks and the "
                        "quantities step 4 counts; none was sent. Reported rather than "
                        "counted as $0.00 - a zero would read as 'this build was free'."
                    ),
                },
            }
        return {
            "posted": False,
            "total": None,
            "invoice_no": None,
            "absence": {
                "field": "one_time_charges",
                "code": "quote_has_no_chargeable_line",
                "tracks": "BR-CUS-090",
                "detail": (
                    "The request has no quote line left to raise: every line is either "
                    "waived by a named person with a recorded reason, or already carries an "
                    "invoice reference from an earlier commit. Nothing is charged twice and "
                    "no waiver is overturned."
                ),
            },
        }

    payer = _quote_payer(connection, data)
    if payer["account_id"] is None:
        return {
            "posted": False,
            "total": None,
            "invoice_no": None,
            "absence": {
                "field": "one_time_charges",
                "code": payer["code"],
                "tracks": payer["tracks"],
                "detail": payer["detail"],
            },
        }

    due_days = data.get("quote_due_days")
    if due_days is None:
        return {
            "posted": False,
            "total": None,
            "invoice_no": None,
            "absence": {
                "field": "one_time_charges",
                "code": "quote_payment_terms_not_captured",
                "tracks": "CR-029 D8(3) · BR-BIL-024",
                "detail": (
                    "Nobody captured how many days this charge is due in, so it cannot be "
                    "issued. BR-BIL-024 is 'due date = bill date + the cycle's due-days' and "
                    "a build's bill has no cycle to take them from; the PO ruled on "
                    "2026-08-23 that the terms are captured by the clerk and never guessed. "
                    "The three available guesses are each a real date on a real customer's "
                    "invoice, and a guessed due date starts a late-fee clock on a figure no "
                    "signed document contains."
                ),
            },
        }

    door = seams.quote_bill_door()
    shape = seams.quoted_charge_shape()
    if door is None or shape is None:
        return {
            "posted": False,
            "total": None,
            "invoice_no": None,
            "absence": {
                "field": "one_time_charges",
                "code": "billing_quote_door_unpublished",
                "tracks": "OQ-379",
                "detail": (
                    "billing.fee_bill.raise_and_issue_quote_bill is not published, so no "
                    "charge can be raised. Reported rather than passed over in silence: "
                    "this module never claims a charge it did not post."
                ),
            },
        }

    # ⚠ **ONLY ON A REQUEST'S LINES.** A build's own line stores no quoted
    # price, so there is no second figure for the catalogue to have drifted
    # from — see the docstring. Running it here would compare the catalogue
    # with itself, which is law 7's *incapable of failing* on a money path.
    if request_id is not None:
        _refuse_quote_price_drift(connection, lines)

    # ⚠ **AN EVENT DATE, NEVER A WALL CLOCK ON A MONEY PATH** (BR-TEN-043,
    # gate G6) — and the same shape `complete_work_order` in this file already
    # uses: the caller's date wins, and it falls back to today only because the
    # clerk is pressing commit with the build in front of them. The blueprint
    # draws this field on step 6 as *Posting date · "The day this payment counts
    # from."*
    on_date = _quote_posting_date(data)
    charges = [
        shape(
            charge_code=str(line["charge_code"]),
            quantity=Decimal(str(line["quantity"])),
            description=line.get("description") or None,
            basis=line.get("basis") or None,
        )
        for line in lines
    ]
    invoice = door(
        actor,
        account_id=payer["account_id"],
        charges=charges,
        on_date=on_date,
        due_days=int(due_days),
    )
    # Customers owns `service_request_fees`, so the stamp goes through its own
    # door (B2 section 2 — no cross-module writes). Without it a second commit
    # would raise the same quote again.
    #
    # ⚠ **A BUILD'S OWN LINES HAVE NO SUCH ROW AND NEED NONE (`BR-MET-1178`).**
    # There is nothing in `customers` to stamp, and the double-raise it guards
    # against cannot happen: `commit_connection` refuses any connection that is
    # not `DRAFT` with `metering.connection_already_committed`, so a build is
    # committed once. The bill is found again through `quote_invoice_id`.
    invoice_no = getattr(invoice, "invoice_no", None)
    if request_id is not None:
        seams.mark_request_quote_invoiced(
            actor,
            request_id,
            invoice_ref=str(invoice_no or invoice.pk),
        )
    return {
        "posted": True,
        "total": getattr(invoice, "total", None),
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice_no,
        "account_id": str(payer["account_id"]),
        "line_count": len(charges),
        "absence": None,
    }


#: **THE THREE BASES A BUILD'S OWN CHARGE LINE MAY BE COUNTED ON** — Accounts
#: blueprint p094's own BASIS column, in its drawn order (`BR-MET-1178`).
#:
#: ⚠ **THEY ARE THE BASIS THE CLERK CHOSE, NOT A THING THIS MODULE COMPUTES.**
#: The QUANTITY is counted on the screen, from step 4's grid, and arrives here
#: as a number; the basis travels beside it so the bill line can say what the
#: number counted. **Nothing here re-derives it** — a second counter would be a
#: second answer to *how many meters is this*, which is what `DEF-MET-5428`
#: already cost once on the neighbouring screen.
#:
#: ⚠⚠ **THEY ARE BILLING'S OWN SPELLINGS, WITH SPACES, AND THAT IS THE WHOLE
#: REASON THIS CONSTANT IS WORTH READING.** `apps/billing/fee_bill.BASIS_UNITS`
#: is the map a quoted line's basis is resolved through, and its keys are
#: `"per unit"` · `"per meter"` · `"per premise"`. Its own docstring says why
#: it is a MAP and not a `.removeprefix("per ")`: *"string surgery on a
#: caller's text would mint a unit out of whatever arrived — a typo becomes a
#: unit nobody defined and it lands on an immutable document (hard rule 4). An
#: unknown basis REFUSES below."* **A first draft of this constant wrote
#: `per_unit` with underscores**, which billing refuses two modules away with
#: *"basis of 'per_unit', which is not one this product counts in"* — a refusal
#: with no charge code and nothing a clerk can act on, after a build has been
#: written. Refusing it HERE, by name, is the difference.
#:
#: ⚠ **AND IT IS NOT `WORK_ORDER_SCOPES`, THOUGH THE IDEA LOOKS THE SAME.**
#: That tuple is what a work-order TEMPLATE declares — `per_premise` ·
#: `per_unit` · `per_asset`, underscores, B18 §8.2. A charge counted
#: `per meter` has no counterpart there and a job raised `per_asset` has none
#: here. Two vocabularies about the same idea, spelled differently, are exactly
#: the pair a reader collapses, so they sit apart with this sentence between
#: them. **A new basis is a ruling, not a string** (`fee_bill`'s own words).
QUOTE_BASES: tuple[str, ...] = ("per unit", "per meter", "per premise")


def build_quote_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    """**THE BUILD'S OWN CHARGE LINES — `BR-MET-1178`, PO ruling 2026-09-21.**

    A build a developer started has no application to take a quote from, and
    the ruling is that it prices ITSELF: *"this request is new work and
    recognized seperately from applcaition and hence we should not make it
    dependent on applciation #"*.

    ⚠ **A LINE IS A CHARGE CODE AND A COUNT. IT IS NEVER AN AMOUNT.** The
    payload carries `{charge_code, quantity, basis?, description?}` and there
    is deliberately no field for money: billing reads the price off the
    tenant's own charge row and multiplies (`BR-BIL-007`, `BR-BIL-020`), which
    is `CLAUDE.md` hard rule 2's *"no figure is multiplied up anywhere but the
    server"*. A caller that handed in a product would be the second rounding
    path this module exists to keep out.

    ⚠ **THE CHARGE CODE IS THE CLERK'S, NOT THIS FILE'S.** The drawing names
    `CC-CONN`, `CC-METERSET` and `CC-CASVC`, and **nothing in this product
    declares which code is counted per unit, per meter or per premise** —
    `rating.Charge` has no basis column. Hard-coding those three would be a
    vocabulary invented here, and `Charge.is_base`'s own docstring records the
    cost: *"it breaks the moment a tenant names theirs `SERVICE-CHG`, and it
    breaks silently"*. The clerk picks from the tenant's catalogue exactly as
    they already do on a service request's fee line; **an unknown code is
    refused BY BILLING, by name**, which is the module that owns the list.

    ⚠ **EVERY REFUSAL HERE IS SHAPE, NEVER PRICE.** A quantity that is not a
    positive number, and a basis outside `QUOTE_BASES`, are both things the
    caller got wrong about the SHAPE of a line; what a line is WORTH is asked
    of billing. A refusal raises rather than reporting an absence, because a
    malformed line means the caller does not know what it is asking for — as
    against the absences above, which mean *the build is fine and no charge can
    be raised yet*.
   
    ⚠ **IT LOST ITS LEADING UNDERSCORE ON 2026-09-21 (`DEF-CUS-6115`) AND
    NOTHING ELSE ABOUT IT MOVED.** `connection_reads.preview_quote` prices the
    SAME lines for step 6's screen that this file raises at commit, and it has
    to read them through this function or the screen and the commit would have
    two answers to *what is a quote line* — `DEF-MET-5428`'s shape, on money.
    A private name reached across a module boundary is the other way to get
    that, and it is worse because nothing says it happened.
    """
    raw = data.get("quote_lines")
    if raw in (None, "", []):
        return []
    if not isinstance(raw, (list, tuple)):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-MET-1178",
            message_key="metering.connection_quote_lines_shape",
        )
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                br_ref="BR-MET-1178",
                message_key="metering.connection_quote_lines_shape",
            )
        code = str(entry.get("charge_code") or "").strip()
        if not code:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                br_ref="BR-BIL-020",
                message_key="metering.connection_quote_line_code_required",
            )
        try:
            quantity = Decimal(str(entry.get("quantity")))
        except (ArithmeticError, TypeError, ValueError):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                br_ref="BR-MET-1178",
                message_key="metering.connection_quote_line_quantity_invalid",
                params={"charge_code": code, "value": str(entry.get("quantity"))[:40]},
            ) from None
        # ⚠ **ZERO IS REFUSED AND IT IS NOT PEDANTRY.** A line counted zero
        # prices `$0.00` and prints on a real customer's bill as a charge that
        # was free — the same reading the absences above refuse to publish. A
        # basis that counted nothing is a line the clerk should not have added.
        if quantity <= 0:
            raise errors.ValidationError(
                errors.VAL_RANGE,
                br_ref="BR-MET-1178",
                message_key="metering.connection_quote_line_quantity_invalid",
                params={"charge_code": code, "value": str(quantity)},
            )
        basis = str(entry.get("basis") or "").strip() or None
        if basis is not None and basis not in QUOTE_BASES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                br_ref="BR-MET-1178",
                message_key="metering.connection_quote_line_basis_unknown",
                params={"charge_code": code, "basis": basis[:40]},
            )
        out.append(
            {
                "charge_code": code,
                "quantity": quantity,
                "basis": basis,
                "description": (str(entry.get("description")).strip() or None)
                if entry.get("description")
                else None,
            }
        )
    return out


def _quote_posting_date(data: dict[str, Any]) -> Any:
    """The day this charge counts from — the caller's, or today IN THE UTILITY'S
    TIMEZONE.

    ⚠ `DEF-MET-9236`: this read `timezone.now().date()` — the UTC date — so a
    build created at 19:48 in Chicago on 2 October dated its quote bill 3
    October, and an Add fee for the real 3 October was then refused as a second
    fee on the same day. `tenant_today` is the utility's own day."""
    raw = data.get("quote_posting_date")
    if raw in (None, ""):
        return seams.tenant_today()
    if isinstance(raw, datetime):
        return raw.date()
    parsed = dateparse.parse_date(str(raw)[:10])
    if parsed is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-TEN-043",
            message_key="metering.connection_quote_posting_date_invalid",
            params={"value": str(raw)[:40]},
        )
    return parsed


def _refuse_quote_price_drift(connection: Any, lines: list[dict[str, Any]]) -> None:
    """Refuse when the catalogue has moved away from what the customer was quoted.

    See `_post_connection_quote` and `OQ-BIL-12376`. This is the ONE money
    question on this path where both available answers are wrong in a way a
    customer would notice, so neither is taken.
    """
    read_charge = seams.resolve("rating", "charge_by_code", kind="selectors")
    if read_charge is None:
        # Billing refuses this by name a moment later, with a better message
        # than this module could write. Not duplicated here.
        return
    for line in lines:
        charge = read_charge(str(line["charge_code"]))
        if not charge:
            continue
        catalogue = charge.get("amount")
        if catalogue is None:
            continue
        quoted = Decimal(str(line["unit_amount"]))
        current = Decimal(str(catalogue))
        if current != quoted:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-BIL-020",
                message_key="metering.connection_quote_price_moved",
                params={
                    "connection_no": connection.connection_no or "",
                    "charge_code": str(line["charge_code"]),
                    # ⚠ **BOTH FIGURES IN ONE PRECISION, AND IT IS THE ONE HARD
                    # RULE 2 WRITES MONEY IN.** `service_request_fees.unit_amount`
                    # is `NUMERIC(18,4)` and the charge catalogue's `amount` is
                    # one of the legacy `NUMERIC(18,6)` containers, so this
                    # refusal read *"quoted 40.0000, current 45.000000"* — one
                    # sentence putting two prices side by side in two
                    # precisions, which is the shape of a figure a clerk then
                    # reads as different. **Nothing is rounded**: money is
                    # written to four decimals, so a fifth or sixth here would
                    # be unlawful rather than significant, and `quantize`
                    # RAISES on one instead of hiding it.
                    "quoted": str(quoted.quantize(_MONEY_4)),
                    "current": str(current.quantize(_MONEY_4)),
                },
            )


def _quote_payer(connection: Any, data: dict[str, Any]) -> dict[str, Any]:
    """WHICH account this build's charges are tagged to — step 6's *Who is billed*.

    ── THE THREE DRAWN CHOICES, AND WHAT THE PRODUCT CAN HONOUR ─────────────

    **1 · The owner's account for this address — HONOURED, when it exists.**
    `BR-MET-113` (PO 2026-08-25: *"You will have to assign account number to
    owner and tag everything to account number"*) put `connections.owner_account`
    there for exactly this, and `create_owner_account` fills it at step 4.

    **2 · Each unit's first bill — NOT HONOURED, and the reason is not the one
    the drawing prints.** Three things are missing and each is real: the unit
    accounts **do not exist at commit** (the drawing says so itself — *"Split
    across six accounts that do not exist yet"*); nothing carries a share of a
    build's quote forward to an account that opens later, `first_bill`'s
    `connection_charge_code` being ONE code from the tenant's catalogue rather
    than a slice of a quote; and splitting a quote across N units is a DIVISION
    with a remainder, and who takes the odd cent on `$3,030.00 / 6` is money
    arithmetic no signed document contains. It is refused rather than
    approximated.

    **3 · The connection itself — REFUSED, and correctly so.** The drawing draws
    it refused; `BR-MET-113` explains it; there is ONE money path.

    ⚠ **THE DRAWING'S STATED REASON FOR THE REFUSAL IS STALE AND MUST NOT BE
    REPEATED.** `02 Accounts Menu Blueprint.pdf` p090 prints, in orange: *"The
    create-a-payer path refuses, and the stated reason is that an account must
    name a unit."* **That expired on 2026-09-01 and the drawing carries its own
    correction beside it.** Measured against the live schema on 2026-09-16:
    `accounts.unit_id` is **nullable**, `ck_accounts_regular_has_unit` binds only
    `kind='regular'`, and `ck_accounts_anchored` is
    `CHECK (unit_id IS NOT NULL OR premises_id IS NOT NULL)` — so a master
    account anchored on a premises with no unit is lawful, and `brazosbend`
    holds one. `DEF-MET-5081` already had to correct eight surfaces repeating
    that false sentence, two of them decision-log rows citing it as proof.
    **`DEF-BIL-5457` and `DEF-LED-5459` are the same sentence surviving in
    CODE** — billing refused to bill such an account and the ledger reported it
    as a forged cross-tenant id — and both were repaired on 2026-09-16, which
    is why this payer can now be honoured at all.

    **THE REFUSAL IS REAL AND ITS ACTUAL CAUSE IS `BR-CUS-1024`** (PO
    2026-09-01): the master-account door requires an IDENTIFIER, and a wizard
    `owner` block that does not carry one cannot open an account —
    `create_owner_account`'s own body states that refusal and `DEF-MET-5093` is
    the row. So a build whose owner has no account yet reports THAT, naming the
    identifier, and a clerk who reads it looks for the right thing.
    """
    choice = str(data.get("quote_payer") or PAYER_OWNER_ACCOUNT).strip() or PAYER_OWNER_ACCOUNT

    if choice == PAYER_CONNECTION:
        return {
            "account_id": None,
            "code": "quote_payer_connection_refused",
            "tracks": "BR-MET-113",
            "detail": (
                "A charge on a build is a debt owed by nobody, and nothing in the product "
                "can settle it: the ledger posts against accounts, the frozen money rules "
                "are account-shaped, and a payable that is not an invoice would be a second "
                "money path. Charges are tagged to an account number."
            ),
        }

    if choice == PAYER_EACH_UNIT_FIRST_BILL:
        return {
            "account_id": None,
            "code": "quote_payer_per_unit_not_built",
            "tracks": "BR-MET-113 · BR-BIL-012",
            "detail": (
                "Splitting this quote across each unit's first bill is not built. The unit "
                "accounts do not exist at commit; nothing carries a share of a build's quote "
                "forward to an account that opens later; and dividing a quote across units "
                "is money arithmetic - including who takes the odd cent - that no signed "
                "document contains. The owner's account is the payer the product can honour."
            ),
        }

    account_id = getattr(connection, "owner_account_id", None)
    if account_id is None:
        return {
            "account_id": None,
            "code": "quote_payer_owner_has_no_account",
            "tracks": "BR-CUS-1024 · DEF-MET-5093",
            "detail": (
                "This build's owner has no account yet, so there is nobody to tag the "
                "charges to. The master-account door requires an identifier for the party "
                "(BR-CUS-1024, PO 2026-09-01) and the owner block did not carry one. NOTE: "
                "this is NOT the reason the blueprint prints beside this control - 'an "
                "account must name a unit' expired on 2026-09-01, accounts.unit_id is "
                "nullable and ck_accounts_anchored allows a premises-only anchor."
            ),
        }

    # ⚠ **THE PAYER'S BILLABLE CLASS, ASKED BEFORE THE DOOR RATHER THAN CAUGHT
    # AFTER IT — `DEF-MET-5472`.** Billing refuses a pending-activation or
    # closed account by RAISING (`BR-CUS-055`, `single.billable_account`), which
    # is right for billing and wrong here: this call sits inside the one
    # transaction that already wrote the premises, the units, the meters, the
    # plan assignments, the owner's account and the work orders, so a raise
    # discards a whole build over who the clerk named as payer. **The build is
    # not wrong; only the charge cannot be raised yet** — which is the shape of
    # every other absence on this path.
    #
    # ⚠ **ASKED, NOT CAUGHT, AND THAT IS CLAUDE.md LAW 14.** The obvious
    # alternative — call the door and catch its refusal — is the trap that law
    # names: on PostgreSQL a failed statement aborts the whole transaction and
    # every later query raises `InFailedSqlTransaction`, so the build would be
    # lost anyway at COMMIT, **and the test suite runs on SQLite, which has no
    # aborted-transaction state and would report it green on every machine.**
    # A read before the write has no such state to get wrong.
    #
    # Customers owns the answer (`billable_accounts()`, BR-CUS-055's class set)
    # and it is a second READER, never a second statement of the rule. `None`
    # means nobody could establish the class, and there this module says
    # nothing: billing refuses it by name a moment later with a better message
    # than metering could write — the same judgment `_refuse_quote_price_drift`
    # already makes one function up.
    if seams.payer_is_billable(account_id) is False:
        return {
            "account_id": None,
            "code": "quote_payer_account_not_billable",
            "tracks": "BR-CUS-055 · DEF-MET-5472",
            "detail": (
                "The account named as payer is not one this utility bills: it is awaiting "
                "activation, or it is closed. A bill to a closed or unopened account is a "
                "document nobody can settle, so the charge cannot be raised - and under "
                "BR-MET-1187 the build is not created either, because the books entry is "
                "part of the same act. Activate the account, or name another payer, and "
                "create the connection again. NOTE: this sentence read 'the build itself "
                "committed in full' until 2026-09-28 and the PO ruled the other way."
            ),
        }
    return {"account_id": account_id, "code": None, "tracks": None, "detail": None}


# ════════════════════════════════════════════════════════════════════════════
# `BR-MET-1187` — THE BOOKS ENTRY IS PART OF THE ACT, SO A BOOKS ENTRY THAT
# CANNOT BE WRITTEN TAKES THE BUILD WITH IT (PO ruling 2026-09-28)
# ════════════════════════════════════════════════════════════════════════════
def _refuse_a_books_entry_that_cannot_be_written(connection: Any, absence: dict[str, Any]) -> None:
    """The build is not created when its one-time charges cannot reach the books.

    **PO ruling 2026-09-28, verbatim:** *"we create entries in books"* and, asked
    when, *"do it at creation once submitted"*, over this sentence, shown to
    them and accepted: *"It is one act: if the books entry cannot be written,
    the connection is not created either."* (`BR-MET-1187`, decision log answer
    18, `CR-150-BRC09` task `B1`.)

    ⚠ **WHAT THIS REPLACES, QUOTED BECAUSE IT IS A MONEY PATH — `DEF-MET-7641`.**
    The commit used to take `data["quote_total"]` **from the client**, save it on
    `connections.quote_total`, leave `one_time_charge_invoice_no` NULL, append the
    absence and CARRY ON. So a build could be created with its money remembered
    as a figure on the build and **no invoice anywhere**: nothing reached
    Billing, nothing reached Finance, nobody was ever asked for it. On a build
    the size of the drawn example that is **`$1,035.00` that exists on one
    screen and in no ledger.**

    ⚠ **THE CLIENT'S FIGURE IS NOT RECORDED ON ANY PATH NOW, AND THAT IS HARD
    RULE 2 RATHER THAN TIDINESS.** A total arriving over the wire is a figure
    multiplied up somewhere other than the server that owns the price list. The
    posted branch stopped honouring it on 2026-09-16 and the unposted branch went
    on honouring it, which is the same rule enforced in one direction only.

    ⚠ **TWO CODES PASS, AND THE BOUNDARY IS THE RULING'S OWN.**
    `QUOTE_ABSENCES_WITH_NOTHING_TO_WRITE` is where they are named and argued;
    everything else describes a charge that exists and could not be raised.

    ⚠ **IT RAISES AND DOES NOT CATCH, WHICH MATTERS ON POSTGRESQL** (CLAUDE.md
    hard-won law 14). This runs INSIDE `commit_connection`'s `transaction.atomic()`
    and nothing before it has failed, so the transaction is healthy and the raise
    simply unwinds it: the premises, the units, the meters, the plan assignments,
    the owner's account and the work orders all go, which is `BR-MET-112`'s
    both-or-neither. The trap this law names is the opposite move — swallowing a
    database error and continuing — and there is none here.
    """
    code = str(absence.get("code") or "")
    if code in QUOTE_ABSENCES_WITH_NOTHING_TO_WRITE:
        return
    # ⚠ **IT CARRIES THE STEP, LIKE EVERY OTHER REFUSAL A CLERK CAN ACT ON.**
    # Every reason that reaches here — the payer, the payment terms, the
    # billing door — is something chosen (or not typed) on the CHARGES step, so
    # the wizard can open the step that owns the field instead of leaving the
    # clerk to find it. `DEF-MET-6110` is the row that made this the house
    # habit, and `_refused_on_the_step_that_chose_it` is its one implementation.
    raise _refused_on_the_step_that_chose_it(
        step=STEP_OF_THE_CHARGES,
        br_ref="BR-MET-1187",
        # A LITERAL key at the raise site. `G32` can only resolve a key where
        # the helper is defined in the same file and reported `0 unresolved`
        # over 21 live refusals that reached a clerk as silence.
        message_key="metering.connection_books_entry_required",
        params={
            "connection_no": connection.connection_no or "",
            # The clerk acts on WHICH thing is missing; support reads the
            # absence's own sentence. `BR-SHL-020 r2` keeps `detail` off the
            # screen, so the two travel separately.
            "reason": code,
            "detail": str(absence.get("detail") or ""),
        },
    )


def _refuse_a_total_the_screen_never_showed(
    connection: Any, data: dict[str, Any], posted_total: Any
) -> None:
    """The client's quote total may REFUSE the commit; it may never become one.

    **Hard rule 2, and the instruction that goes with `BR-MET-1187`:** never
    take a total from the client — recompute it server-side from the charges
    and their quantities; the client figure may be used only to refuse a
    mismatch, never to post.

    So the arithmetic stays where it already was — billing prices the lines and
    `raise_and_issue_quote_bill` finalizes — and the number the clerk was shown
    on step 4 is compared with the number the customer is actually being asked
    for. A disagreement means the catalogue moved between the preview and the
    press (`rating.selectors.charge_by_code`: *"the amount is a SEED the tenant
    edits, never a constant"*), and it is refused rather than silently billed,
    for `_refuse_quote_price_drift`'s reason one function up: billing a
    DIFFERENT figure from the one the clerk just read, silently, is its own
    defect.

    ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY, SAID OUT LOUD** (CLAUDE.md law
    7, habit 2): a client that sends **no** `quote_total` is not compared with
    anything, and this returns without looking. That is not a hole to plug by
    inventing a requirement — `commitPlanOf` sends `null` on every build whose
    step-4 preview could not be priced, and demanding a figure there would
    refuse builds that are fine. **The invoice is the authority either way**;
    this only stops the screen and the bill disagreeing in the one case where
    both numbers exist.

    ⚠ **BOTH FIGURES ARE COMPARED AT FOUR DECIMALS, WHICH IS THE PRECISION HARD
    RULE 2 WRITES MONEY IN.** `invoices.total` is one of the legacy
    `NUMERIC(18,6)` containers, so an unquantized comparison would call
    `800.000000` different from `800.0000`. `quantize` RAISES on a fifth or
    sixth decimal rather than discarding it, which is the behaviour a money
    path wants.
    """
    stated = data.get("quote_total")
    if stated in (None, "") or posted_total is None:
        return
    try:
        shown = Decimal(str(stated)).quantize(_MONEY_4)
    except (ArithmeticError, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-MET-1187",
            message_key="metering.connection_quote_total_invalid",
            params={"value": str(stated)[:40], "step": STEP_OF_THE_CHARGES},
        ) from None
    raised = Decimal(str(posted_total)).quantize(_MONEY_4)
    if shown == raised:
        return
    raise _refused_on_the_step_that_chose_it(
        step=STEP_OF_THE_CHARGES,
        br_ref="BR-MET-1187",
        message_key="metering.connection_quote_total_moved",
        params={
            "connection_no": connection.connection_no or "",
            "shown": str(shown),
            "raised": str(raised),
        },
    )


def _payment_taken_at_the_counter(data: dict[str, Any], *, on_date: Any) -> dict[str, Any] | None:
    """Step 4's *Taking payment* block, refused for SHAPE and never for price.

    **PO 2026-09-28:** *"based on payment type we nedd to give all paymnet
    fields"* (`DEF-CUS-7611`). `PAYMENT_FIELDS` names the five and says why each
    is spelled the way it is.

    `None` is the ordinary answer and it is the drawn default — *No payment
    now*. A build is committed with an invoice and no receipt, and the developer
    pays it like any other bill.

    ── WHAT IS REFUSED HERE, AND WHAT IS DELIBERATELY NOT ───────────────────
    This refuses SHAPE, exactly as `build_quote_lines` does: an amount with no
    tender, a tender with no amount, an amount that is not a positive number, a
    date that is not a date. **What a tender IS, whether a till is open and
    whether the money can be allocated are all payments' to answer**, and each
    of them has one implementation over there — see the note beside
    `seams.payment_door`. Two readers of one rule eventually disagree, and on
    this path the disagreement is a payment refused after a bill exists.

    ⚠ **AN AMOUNT WITH NO TENDER IS REFUSED RATHER THAN DEFAULTED TO CASH.**
    `payments.method` is nullable, so the write would succeed — and the money
    would sit in the day's takings belonging to no drawer, un-bankable and
    un-reconcilable. It is `BR-BIL-024`'s shape on the other side of the
    receipt: a guessed tender is a real row on a real deposit.

    ⚠ **THE PAYMENT'S DATE FALLS BACK TO THE CHARGE'S POSTING DATE AND NOT TO A
    CLOCK** (`BR-TEN-043`, gate `G6`). They are one event — the clerk is taking
    the money for the charge they are raising in the same press — and the
    posting date is the one the clerk typed on the same step. A wall clock here
    would date a Friday counter payment to Saturday on a late commit.
    """
    method = data.get("payment_method")
    method_code = str(method).strip() if method not in (None, "") else ""
    raw_amount = data.get("payment_amount")
    stated_amount = raw_amount not in (None, "")

    if not method_code and not stated_amount:
        return None
    if not method_code:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_method_required",
            params={"step": STEP_OF_THE_CHARGES},
        )
    if not stated_amount:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_amount_required",
            params={"method": method_code[:40], "step": STEP_OF_THE_CHARGES},
        )
    # ⚠ **A FLOAT IS REFUSED RATHER THAN CONVERTED** (hard rule 2, and
    # `payments.services._amount`'s own rule): converting hides the place where
    # money became binary and the books would carry a figure nobody can
    # reproduce. `Decimal(str(...))` on a JSON number is a STRING round-trip of
    # what the wire carried, which is the only lossless reading available here.
    if isinstance(raw_amount, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_amount_invalid",
            params={"value": repr(raw_amount)[:40], "step": STEP_OF_THE_CHARGES},
        )
    try:
        amount = Decimal(str(raw_amount))
    except (ArithmeticError, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_amount_invalid",
            params={"value": str(raw_amount)[:40], "step": STEP_OF_THE_CHARGES},
        ) from None
    if amount <= 0:
        # Zero is refused for `build_quote_lines`' reason: a receipt for $0.00
        # is a statement that money changed hands when none did. A refund is a
        # new reversing row (`BR-PAY-002`, hard rule 4), never a negative here.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_amount_invalid",
            params={"value": str(amount), "step": STEP_OF_THE_CHARGES},
        )

    return {
        "method_code": method_code,
        "amount": amount,
        "on_date": _payment_day(data, "payment_date", fallback=on_date),
        # No clearing date — see `PAYMENT_FIELDS` (CR-186-BRC10).
        "confirmation": _payment_text(data.get("payment_reference")),
        "memo": _payment_text(data.get("payment_memo")),
        # DEF-PAY-9263 · BR-PAY-1199 — the clerk's *Record anyway* after
        # "Looks like a duplicate". Only a literal `true` counts.
        "duplicate_confirmed": data.get("payment_duplicate_confirmed") is True,
    }


def _payment_day(data: dict[str, Any], field: str, *, fallback: Any) -> Any:
    """One calendar day off the payload, refused by SHAPE, or the fallback.

    One function for both dates so the two cannot drift into two readings of
    `YYYY-MM-DD`; what differs is only the fallback, and each caller states its
    own beside the call.
    """
    raw = data.get(field)
    if raw in (None, ""):
        return fallback
    if isinstance(raw, datetime):
        return raw.date()
    parsed = dateparse.parse_date(str(raw)[:10])
    if parsed is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-TEN-043",
            message_key="metering.connection_payment_date_invalid",
            params={"value": str(raw)[:40], "field": field, "step": STEP_OF_THE_CHARGES},
        )
    return parsed


def _payment_text(value: Any) -> str | None:
    """A reference or a memo: the clerk's own text, or nothing at all.

    `None` rather than `""` — `payments.confirmation` is nullable and a blank
    string on a cheque row reads as *"the cheque had no number"* where the truth
    is *"nobody typed one"*.
    """
    if value in (None, ""):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _record_the_payment_taken(
    actor: Any, connection: Any, taken: dict[str, Any], quote: dict[str, Any]
) -> dict[str, Any]:
    """Write the counter payment, against THIS account and THIS bill.

    **`BR-MET-1187`:** pressing *Create connection* writes the connection, the
    invoice, **and the payment if one was taken** — one act.

    ── THE IDEMPOTENCY KEY, NAMED RATHER THAN DESCRIBED (hard rule 6) ───────
    `payments.webhook_key`, `UNIQUE (tenant_id, webhook_key)` — **B2 §2 and
    DB-12's second row**, which is the one idempotency key this product has for
    a payment. The string is composed by payments' own
    `idempotency.inbound_payment_key(source="entry", reference=…)`, and the
    reference is **this connection's id**:

        entry|new-connect:6f21c0f6-…

    ⚠ **THE CONNECTION'S ID AND NOT A CLIENT TOKEN, AND THE DIFFERENCE IS THE
    WHOLE GUARANTEE.** A token minted by the browser is different on the second
    submit and would dedupe nothing while looking as though it did — payments'
    own idempotency docstring says exactly that. The connection id is stable
    across every retry of one build, it is unique per build, and it is the
    thing this payment is FOR. A retried request therefore finds the row and
    `record_payment` answers `created=False`: one payment, one audit row, one
    journal entry, and the money is not doubled.

    ⚠ **AND IT IS THE SECOND OF TWO GUARDS, NOT THE ONLY ONE.** The first is
    structural and predates this work: `commit_connection` refuses any
    connection that is not `DRAFT` with `metering.connection_already_committed`,
    so a second press on one build cannot reach here at all. The key is what
    covers the case the state cannot — a request that wrote and then lost its
    answer, retried against the same draft.

    ── ALLOCATED TO THE BILL THE CLERK TOOK IT FOR ─────────────────────────
    `seams.payment_against_one_bill` composes payments' `specific` instruction
    for the invoice just raised. Its docstring holds the reason; in one line:
    `oldest_first` would put a developer's connection payment against an older
    bill on the same account.

    ── WHAT IS NOT DECIDED HERE ────────────────────────────────────────────
    The ledger pair, the receipt number, the deposit batch and the audit row
    are all `record_payment`'s, written inside its own `atomic()` — a SAVEPOINT
    under this commit's transaction, so the whole act is still both-or-neither
    (`BR-MET-112`). **Only the ledger posting service writes journal lines**
    (hard rule 5) and nothing here goes near one.
    """
    door = seams.payment_door()
    instruction = seams.payment_against_one_bill(quote["invoice_no"])
    source = seams.payment_entry_source()
    if door is None or instruction is None or source is None:
        # ⚠ **REFUSED, NEVER REPORTED AS AN ABSENCE.** Everywhere else on this
        # path an unpublished neighbour is reported and the build stands. Here
        # the clerk has taken money over a counter: a build committed with a
        # receipt nobody can find is worse than a build the clerk re-enters.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-1187",
            message_key="metering.connection_payment_door_unpublished",
            params={
                "connection_no": connection.connection_no or "",
                "step": STEP_OF_THE_CHARGES,
            },
        )
    recorded = door(
        actor,
        account_id=quote["account_id"],
        amount=taken["amount"],
        # Posted at entry; bank reconciliation clears it (CR-186-BRC10).
        posted_at=_moment_of(taken["on_date"]),
        method_code=taken["method_code"],
        confirmation=taken["confirmation"],
        memo=taken["memo"],
        order=instruction["order"],
        targets=instruction["targets"],
        idempotency_source=source,
        idempotency_reference=f"{PAYMENT_KEY_PREFIX}{connection.id}",
        counter_session_id=taken.get("till_id"),
        # DEF-PAY-9263 · BR-PAY-1199 — step 4 is a clerk at a screen, so it
        # asks "Looks like a duplicate" exactly as Record payment does.
        warn_on_possible_duplicate=True,
        duplicate_confirmed=bool(taken.get("duplicate_confirmed")),
    )
    return {
        "payment_no": getattr(recorded, "payment_no", None),
        "amount": getattr(recorded, "amount", None),
        "applied": getattr(recorded, "applied", None),
        "credit_carried": getattr(recorded, "credit_carried", None),
        "created": bool(getattr(recorded, "created", False)),
        "posted_to_ledger": bool(getattr(recorded, "posted_to_ledger", False)),
        # ⚠ **PAYMENTS' OWN CODED PROBLEMS, CARRIED OUT RATHER THAN SWALLOWED.**
        # `record_payment` answers a RESULT and not an exception for the states
        # that are lawful but incomplete — chiefly `not_cleared_so_not_allocated`,
        # a payment the money has not arrived for. Dropping them here would
        # leave the commit reporting a receipt over a bill nothing was
        # allocated to, which is `DEF-MET-7641`'s disease one layer down.
        "problems": tuple(getattr(recorded, "problems", ()) or ()),
    }


def _moment_of(on_date: Any) -> datetime:
    """The business day as an instant — **derived, never a clock read.**

    `record_payment` takes a `datetime` because `payments.posted_at` is one, and
    what the clerk gave us is a DATE. `BR-TEN-043` and gate `G6`: a money path
    reads no wall clock, so the instant comes from the date the caller named.

    ⚠ **START OF DAY IN THE UTILITY'S OWN TIMEZONE — `OQ-153`, CLOSED BY THE
    PO ON 2026-08-12 (`DEF-MET-9213`).** This read *"START OF DAY, IN UTC"*
    until 2026-10-02, borrowing `billing.fee_bill.issue_moment`'s reasoning,
    and the New Connection end-to-end walk measured what that costs: on a
    utility on America/Chicago a payment typed **10/02/2026** on step 4 was
    stored `2026-10-02T00:00Z` — 19:00 on 1 October in Chicago — and the
    request's Charges tab showed **10/01/2026**, because every screen reads the
    instant back in the utility's zone (`tenancy.selectors.tenant_timezone`,
    BR-TEN-081). `DEF-094` was the same fault in `payments.api._moment`. The
    start of the day is still the only instant the date alone determines, so a
    replay of this commit still produces the same value: the tenant's zone is a
    stored setting, not the clock of the process running it.

    ⚠ **IT IS NOT `parse_moment` ABOVE, AND THE DIFFERENCE IS DELIBERATE.**
    That one reads a wire value that may carry a TIME and makes it aware in the
    CURRENT zone, which is right for a dispatcher promising *Thursday 15:30*
    and wrong here: two runs of one commit in two zones would then date one
    payment to two different days.
    """
    return datetime.combine(on_date, time.min, tzinfo=seams.tenant_timezone())


def _unit_for_spec(spec: dict[str, Any], by_label: dict[str, Any], *, field: str) -> str:
    """**Which unit this meter stands on, or this plan prices — `DEF-MET-5437`.**

    ⚠ **THE LABEL WINS AND THERE IS NO FALLBACK TO UNIT ONE.** The commit read
    `unit_id` and fell back to `units[0].id` when it found none, and the wizard
    can only ever send LABELS — `BR-MET-112` means the units do not exist until
    this same call creates them. So every meter on a 26-unit build landed on
    `Apt 1`, silently, with every count in the manifest correct.

    ⚠ **A LABEL THAT NAMES NO UNIT IS REFUSED, NOT GUESSED.** That is the whole
    lesson of the defect: the old fallback was a guess that looked like an
    answer, and `BR-MET-112` is both-or-neither, so a build referring to a unit
    it never made takes the whole thing down rather than quietly re-pointing.

    `unit_id` still wins when it is sent, because every existing caller of this
    commit — and every test written against it — creates its units first and
    names them by id. Both keys absent is refused for the same reason a bad
    label is.
    """
    named = spec.get("unit_id")
    if named:
        return str(named)
    label = str(spec.get("unit_label") or "").strip()
    unit = by_label.get(label) if label else None
    if unit is None:
        metering_services._refuse_fields(
            [
                metering_services._field_error(
                    f"{field}.unit_label",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "metering.connection.unit_label_unknown",
                    allowed=sorted(by_label),
                )
            ]
        )
    return str(unit.id)


def _services_without_a_meter(data: dict[str, Any]) -> list[str]:
    """**Which of this build's services reach the commit on no key at all.**

    `commitPlanOf` emits a `meters` row only where `takesAMeter(service)` is
    true, so a unit taking trash, fire, storm water, broadband or thermal heat
    arrives here in NOTHING — not in `meters`, not in `plan_assignments`, and
    there is no `unit_services` member. Step 4's grid maps them to units in the
    browser and the answer stops there.

    ⚠ **THIS REPORTS AND DOES NOT REPAIR (`DEF-MET-6119`).** Step 4's premise
    ticks travel as `premises.services_available`, so the difference below is
    the honest name of what is missing — but it is the ADDRESS's list and not
    the per-unit answer, and pairing it with every unit would write a row for a
    unit the clerk deliberately unticked. `BR-MET-112` is that a wizard does not
    mint a record because a field was filled in somewhere near it.

    ⚠ **IT UNDER-REPORTS ON A PICKED ADDRESS, DELIBERATELY.** That path sends
    `services_available: null` — the premises' own list is not this wizard's to
    rewrite on the way past — so there is nothing to subtract from and the list
    is empty. An absence that names the wrong services would be worse than one
    that names none.
    """
    block = data.get("premises") or {}
    offered = block.get("services_available")
    if not offered:
        return []
    metered = {
        str(spec.get("service"))
        for spec in (data.get("meters") or [])
        if spec.get("service")
    }
    # `DEF-MET-6119` — a service that arrived on `unit_services` is recorded
    # and is no longer missing.
    recorded = {
        str(spec.get("service"))
        for spec in (data.get("unit_services") or [])
        if isinstance(spec, dict) and spec.get("service")
    }
    return sorted({str(code) for code in offered if code} - metered - recorded)


#: **The capacity services that take NO meter — PO ruling 2026-10-02
#: (`DEF-MET-9037`):** *"Capacity is the panels or battery only."* Net metering
#: is not done now, so a solar or battery build fits no net meter; its size is
#: the panels' and batteries' kW, which travel on `unit_services`.
NO_METER_CAPACITY_SERVICES: frozenset[str] = frozenset({"solar", "battery"})


def _meters_to_fit(data: dict[str, Any]) -> list[dict[str, Any]]:
    """The payload's `meters` rows less any for a service that takes no meter."""
    return [
        spec
        for spec in data.get("meters") or []
        if spec.get("service") not in NO_METER_CAPACITY_SERVICES
    ]


def _build_meter_for(
    template: Any, service: str | None, unit_id: Any, build_meters: list[dict[str, Any]]
) -> str | None:
    """The one meter a build's PER-METER job is for, or None (`DEF-WRK-9683`).

    Only a *per asset* template asks (`SCOPE_ASSET`); only a meter this build
    created for the order's service counts; the order's unit narrows it when the
    row names one. **Exactly one is an answer.** None leaves the job on the
    build as before, and two or more is `OQ-WRK-1723`'s question — which meter
    a reading belongs to — and is never chosen here (prime directive).
    """
    if getattr(template, "scope", None) != SCOPE_ASSET or not service:
        return None
    matches = [
        meter
        for meter in build_meters
        if meter.get("id")
        and meter.get("service") == service
        and (unit_id is None or str(meter.get("unit_id")) == str(unit_id))
    ]
    return str(matches[0]["id"]) if len(matches) == 1 else None


def _commit_unit_services(
    actor: Any, connection: Any, data: dict[str, Any], by_label: dict[str, Any]
) -> int:
    """**`DEF-MET-6119` — the services a meter does not carry, and their SIZES.**

    `unit_services: [{unit_label, service, equipment: [{type, size_class,
    count}]}]`. Until 2026-10-01 only METERED services reached the commit, so
    a build selling trash, fire, solar or battery recorded none of them: no
    `connection_services` row, and no cart, fire line, panel or battery to say
    how big the service is. Those four are billed on what stands on the unit —
    a COUNT of carts or fire lines by their band, a SUM of kW for panels and
    batteries (`BR-RAT-090`, `BR-TEN-171`) — so a unit with the service and no
    sized equipment bills `$0.00`, and one with equipment of NO size refuses
    the whole account's bill (`installed_capacity_undetermined`). Found walking
    a portal new-connection request to an active customer on the six-service
    utility the PO named that day.

    **What each entry writes, through each owner's own door:**
      * one `connection_services` row for the unit and service
        (`add_connection_service`, idempotent on unit × service);
      * `count` pieces of equipment of that `type` and `size_class`, through the
        assets seam exactly as step 2's meters are — `installed=False`, because
        nobody has been to site (PO 2026-09-21: *"generate … asset # and
        assigned it - but theya re not yet installed"*). The work order's
        completion installs them, and only then do they count on a bill.

    ⚠ **THE DEVICE TYPE IS THE CALLER'S, NEVER INFERRED HERE.** Which device
    sizes a service is the tenant's reference data (a cart, a fire line, a PV
    panel, a battery — `assets.SEED_ASSET_TYPES`); a map from service to type
    written in this file would be a pricing rule nobody ruled, which is
    `required_characteristic_keys`'s own warning one function down. A
    `size_class` is required with every piece and validated by the assets door
    against the service's ratified ladder, so a size that is not on it is
    refused by name rather than written blank.

    Returns how many pieces were created — a COUNT, so `0` is a true answer.
    """
    created = 0
    for spec in data.get("unit_services") or []:
        if not isinstance(spec, dict) or not spec.get("service"):
            continue
        service_code = str(spec["service"])
        unit_id = _unit_for_spec(spec, by_label, field="unit_services")
        add_connection_service(actor, connection.id, service_code=service_code, unit_id=unit_id)
        # The unit's SERVICE POINT for it — what an account's agreement attaches
        # to. A metered or sized service gets one from its first device; SEWER
        # has none (a share of water, `BR-RAT-015`), so without this line a
        # build selling sewer opened accounts that never took sewer. Metering's
        # own get-or-create, the same one the unit wizard uses.
        metering_services.ensure_service_point(unit_id, service_code)
        _record_unit_capacity(actor, unit_id, service_code, spec.get("size_class"))
        for piece in spec.get("equipment") or []:
            if not isinstance(piece, dict):
                continue
            size_class = str(piece.get("size_class") or "").strip()
            device = str(piece.get("type") or "").strip()
            if not size_class or not device:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-TEN-171",
                    message_key="metering.connection_equipment_size_required",
                    params={"service": service_code},
                )
            try:
                count = int(piece.get("count") or 1)
            except (TypeError, ValueError):
                count = 0
            if count < 1:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-RAT-090",
                    message_key="metering.connection_equipment_count_invalid",
                    params={"service": service_code},
                )
            for _ in range(count):
                made = seams.create_asset_for_unit(
                    actor=actor,
                    unit_id=unit_id,
                    service_point_id=None,
                    payload={"type": device, "service": service_code, "size_class": size_class},
                    installed=False,
                )
                if made is not None:
                    created += 1
    return created


def _record_unit_capacity(actor: Any, unit_id: Any, service_code: str, size_class: Any) -> None:
    """**`DEF-MET-9222` — the size step 3 showed, for a service no device sizes.**
    🔒 a billable quantity. HUMAN-REVIEW-PENDING (review-ledger row, 2026-10-03).

    Storm water's class and thermal/heat's connected tonnage are UNIT facts
    (`UNIT_CAPACITY_CHARACTERISTIC`, PO 2026-09-02 and 2026-09-07): nobody
    installs an ERU or a ton. Until 2026-10-03 the wizard sent neither and this
    commit wrote neither, so every unit read BR-MET-108's absence and both
    services billed `$0.00` — found by the New Connection end-to-end walk on
    S1, S2 and S7 with `service_characteristics` holding 0 rows.

    The row's `size_class` is the CLASS the clerk saw (`SW-APT` *Apartment
    building*, `TH-T10` *10 tons*). What it is WORTH is read from `BR-TEN-171`'s
    ratified ladder through `seams.total_installed_capacity` — the same call the
    bill and the demo seed make — and recorded with that ladder's own unit
    (hard rule 3), so a class and a bill cannot disagree about what it means.

    ⚠ **PER UNIT, AS THE ROW SHOWS IT.** Step 3 sizes each unit's row on its
    own, so the class picked on a unit is that unit's: *Apartment building* on
    each of three flats is 6 ERU on each. A premises-level class split across
    its units is the demo seed's shape and is not what this screen asks.

    No size sent is a finished answer — BR-MET-108's stamped absence, never a
    size nobody chose. A code the ladder does not hold for this service is
    REFUSED by name rather than recorded as a plausible number.
    """
    key = unit_capacity_key(service_code)
    code = str(size_class or "").strip()
    if key is None or code == "":
        return
    uom = seams.capacity_uom_for_service(service_code)
    total = seams.total_installed_capacity(service_code, [code]) if uom else None
    if total is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-TEN-171",
            message_key="metering.connection_unit_size_unknown",
            params={"service": service_code, "size_class": code},
        )
    set_characteristic(
        actor,
        unit_id,
        service_code=service_code,
        key=key,
        value=str(total),
        unit_of_measure=uom,
    )


def queue_messages_on_commit(
    actor: Any, connection: Any, choices: Any = None
) -> dict[str, Any]:
    """Step 7's letters, queued — the manifest entry step 8 reads its promise off.

    A one-call forwarder to `connection_messages.queue_on_commit`, which owns
    every decision about WHICH letters, WHICH template and WHAT language. This
    exists so the commit has one named line for its seventh act rather than an
    import buried in a 300-line function, and so the manifest's shape is stated
    in the module that publishes the manifest.

    ⚠ **THE RETURN IS PASSED THROUGH WHOLE AND IS NOT SUMMARISED TO A COUNT.**
    The door's own docstring is explicit that it *"never reports a message it did
    not queue"*: every outcome carries its state, and a refused one carries the
    reason and the open question that would unblock it. A manifest entry of `3`
    over three rows that do not exist is precisely `DEF-MET-5428`, one step over
    — the review step promised nine work orders and the server raised none —
    and `queued_count` here counts ROWS WRITTEN.

    ⚠ **TODAY IT WILL SAY ZERO, AND ZERO IS THE TRUE ANSWER RATHER THAN A BUG TO
    ROUTE AROUND.** The platform has no `connection` source kind (open since
    `CR-030`), so all three are refused BY NAME. **Nobody may close that by
    picking an existing kind:** filing a welcome letter as `notice` would put it
    among disconnection notices, where a clerk reading the queue would find a new
    customer's greeting in the cut-off list. The refusal is the honest state and
    the question belongs to the Product Owner.

    The import is local for the same reason every other cross-file call in this
    module is: `connection_messages` reaches metering's seams, and a module-level
    import here would make the commit path depend on that graph being importable
    at start-up rather than at call time.
    """
    from apps.metering import connection_messages

    return connection_messages.queue_on_commit(actor, connection, choices)


def commit_connection(actor: Any, connection_id: Any, plan: Any) -> dict[str, Any]:
    """**Task 6.10 — step 9's commit, and it is an ORCHESTRATOR across five
    modules rather than one write.**

    `BR-MET-112`: *"nothing is written until step 9"*. Every step's footer says
    it, so the whole wizard is a draft and this is the only place any of it
    becomes real. The drawn manifest is seven counts, not one row — **EIGHT
    since 2026-09-16, when `work_orders` joined it** (`DEF-MET-5428`; step 6's
    proposal was collected and discarded for eleven days) — and the commit
    spans **customers · metering (premises/units) · assets · rating · billing**
    — five modules that `CLAUDE.md` forbids writing across.

    **So each module writes its own tables through its own service**, and this
    function only sequences them. A direct ORM write to another module's table
    here would skip that module's guards — the very guards that stop one meter
    being billed twice — and would be invisible to every test that module owns.

    ── THE ORDER, AND IT IS NOT ARBITRARY ────────────────────────────────────
    Plans are assigned **before** the owner's account is created, and that
    ordering was discovered by building it rather than by reading the screen.
    `create_master_account` creates the account **ACTIVE** (BR-CUS-068 made that
    deliberate: an unattached master is the half-built state that ruling
    closed), and `BR-MET-040` refuses an activation on a unit with **no rate
    plan** — correctly, since an active account on an unpriced unit is an
    unbillable bill waiting to happen. Reverse the two and the commit fails on
    a rule that is right. Recorded on `BR-MET-116`.

    ── BOTH OR NEITHER ───────────────────────────────────────────────────────
    One `transaction.atomic()`, on the transfer wizard's own principle: *"Both
    halves commit together … otherwise the customer ends up with no account
    anywhere."* A build that created 26 units and then failed to price them
    would leave a premises nobody can bill and no way to tell how far it got.

    ⛔ **THE CHARGES HALF REFUSES, AND THE REASON IS A DOOR THAT CANNOT EXPRESS
    THE QUOTE — `OQ-379`.** Step 7 draws **four coded lines with quantities**
    (`CC-CONN-E $185 × 25` · `CC-TAP-W $310 × 24` · `CC-MSET $45 × 50` ·
    `CC-INSP $120 × 1` = **$14,435.00**). Billing's one-time door takes a single
    `connection_charge_code` and has **no `amount`, no `description` and no
    `lines` member** — BR-BIL-020 enforced as an absent field rather than a
    removable validation, which is right and is why this is not a bug to route
    around. **The quote is therefore recorded as a FIGURE on the connection and
    posted by nothing**, and the manifest says so rather than reporting a total
    it did not raise.

    ⚠ **`Sub-meter links` IS IN THE MANIFEST AND IS NOT WRITTEN HERE.** The
    drawn `24` is the count of water taps, and a sub-meter link is an assets
    relationship this module does not own a door to. Reported in the manifest as
    an absence, never as `0` — a zero would read as *"we made none"* where the
    truth is *"we cannot make them from here"*.
    """
    connection = _connection_or_404(connection_id)
    _refuse_if_cancelled(connection)
    if connection.state != DRAFT:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-112",
            message_key="metering.connection_already_committed",
            params={"connection_no": connection.connection_no or "", "state": connection.state},
        )
    data = metering_services._payload_dict(plan)
    tenant_id = _tenant_id()
    made: dict[str, Any] = {key: 0 for key in MANIFEST_KEYS}
    #: `DEF-WRK-9683` — the meters this commit fits, for step 5's per-meter jobs.
    build_meters: list[dict[str, Any]] = []
    # ⚠ **NOT `0`, AND NOT `""`.** Every other manifest key is a COUNT, whose
    # zero is a true statement. This one names a document; there is no invoice
    # number that means "none", so the honest value on every unposted path is
    # nothing at all.
    made["one_time_charge_invoice_no"] = None
    # ⚠ **THE SAME REASONING, FOR THE PAYMENT — `BR-MET-1187`.** One names a
    # receipt and one is money; neither has a zero that means *none*. A build
    # where no payment was taken reports nothing at all, and *No payment now*
    # is the drawn default rather than an edge case.
    made["one_time_charge_payment_no"] = None
    made["one_time_charge_paid"] = None
    absences: list[dict[str, Any]] = []

    # ⚠ **ASKED BEFORE ANYTHING IS WRITTEN — `DEF-MET-6111`.** A label this
    # address already holds cannot be created, and until 2026-09-21 the clerk
    # learned that from `uq_units_tenant_premises_label` as an HTTP 500 after
    # eight steps. It sits OUTSIDE the block because it writes nothing and a
    # refusal here has nothing to roll back; the constraint is still the
    # authority and `commit_new_connect` translates the race.
    _refuse_a_unit_label_already_at_this_address(connection, data.get("units"))

    with transaction.atomic():
        # 1 · UNITS — metering's own table, so a direct write is not a
        #     cross-module one. `is_common_area` is what BR-MET-101 keys off and
        #     what BR-MET-116's master account anchors on.
        units: list[Any] = []
        # ⚠ **`DEF-MET-5437` — THE LABEL IS THE ONLY KEY THE BROWSER CAN SEND,
        # SO IT IS THE KEY THIS COMMIT RESOLVES ON.** `BR-MET-112` means the
        # units do not exist until the three lines below create them, so
        # `commitPlanOf` has always emitted `plan_assignments: [{unit_label,
        # …}]` and `meters: [{unit_label, …}]` — labels are what it HAS. Steps
        # 2 and 3 read `spec["unit_id"]`, found nothing, and fell back to
        # `units[0].id`, so **on a 26-unit build every meter landed on unit 1
        # and not one unit was priced**: `assign_unit_plan(actor, None, …)`
        # resolved no unit at all. This map is what closes it.
        by_label: dict[str, Any] = {}
        for spec in data.get("units") or []:
            # ⚠ **A COMMON AREA IS ACCEPTED ON ANY PREMISE TYPE AND IS REFUSED
            # BY NOTHING — `BR-MET-1179`, PO 2026-09-21, corrected the same
            # day.** A four-code refusal stood here for part of one afternoon
            # and the PO removed it in their own words: *"i said Comemrcial
            # Building also Common area is optional not mandetory , I did not
            # say No common area"*. The rule is about the wizard's DEFAULT —
            # step 3 no longer opens with the tick already on — and a clerk who
            # deliberately asks for a shared unit on a house gets one.
            # `CR-162-BRC10` item 36 — the Units tab's *Unit type* column was
            # empty on every build because the commit dropped the type the
            # wizard chose. Resolved through the unit wizard's own rule
            # (`_validate_unit` → `_resolve_unit_type`, BR-MET-084), so an
            # unknown type is refused by name, never stored blind; absent stays
            # NULL exactly as before.
            typed = (
                metering_services._validate_unit({"unit_type": spec["unit_type"]}, partial=True)
                if spec.get("unit_type")
                else {}
            )
            unit = metering_models.Unit.objects.create(
                tenant_id=tenant_id,
                premises_id=connection.premises_id,
                label=str(spec.get("label") or "").strip() or "Unit",
                is_common_area=bool(spec.get("is_common_area", False)),
                **({"unit_type": typed["unit_type"]} if typed.get("unit_type") else {}),
            )
            units.append(unit)
            by_label[unit.label] = unit
        made["units"] = len(units)
        # ⊕ **`DEF-MET-9230` — THE READ ROUTE STEP 2 PICKED REACHES THE UNITS.**
        # `create_premises` honours the route by joining the premises' units to
        # it (CR-089 B6) — and a New Connection's premises is created BEFORE
        # its units, so the join found none and the route was lost: every unit
        # of every new build sat on no route and no billing cycle, no cycle run
        # could reach it, and the master account's first bill was refused
        # *no billing cycle* (the end-to-end walk, `CON-26-0131`). Joined here,
        # once the units exist, through the SAME door the premises create used.
        route_block = data.get("premises") if isinstance(data.get("premises"), dict) else {}
        if units and route_block.get("read_route"):
            chosen = metering_services._resolve_create_route({"route": route_block["read_route"]})
            if chosen is not None:
                premises_row = metering_models.Premises.objects.get(
                    tenant_id=tenant_id, pk=connection.premises_id
                )
                metering_services._join_premises_to_route(actor, premises_row, chosen)
        # ⚠ **`DEF-2961` — THIS READ `1 if units else 0` AND REPORTED A PREMISES
        # THIS FUNCTION HAS NEVER CREATED.** `create_connection` refuses without
        # an address (and, since `BR-MET-1024`, may create one), so by the time
        # a commit runs the premises is already there — the count was derived
        # from the presence of UNITS, which is a different fact entirely, and a
        # manifest is a statement about what was written.
        #
        # **`None`, not `0`, and it is the posture `sub_meter_links` below
        # already takes for exactly this situation:** a zero reads as *"we made
        # none"* where the truth is *"this count cannot be answered here"*. The
        # address is created at step 1–2 by `create_connection`, which reports
        # `premises_created` on its own response — the door that did it is the
        # door that can say so.
        made["premises"] = None
        absences.append(
            {
                "field": "premises",
                "code": "premises_created_at_step_1_not_at_commit",
                "tracks": "DEF-2961",
                "detail": (
                    "connections.premises_id is NOT NULL, so the address exists before this "
                    "draft does and the commit creates none. New Connect can now CREATE the "
                    "address (BR-MET-1024) and says so on create_connection's own response "
                    "as premises_created; this manifest reports what the COMMIT wrote."
                ),
            }
        )

        # 2 · METERS — through the assets seam, never `Asset.objects.create`.
        #     Keyed by the LABEL this commit just created (`DEF-MET-5437`).
        #
        # ⚠ **THIS CALL NAMED TWO ARGUMENTS THE SEAM HAS NEVER TAKEN, SO IT
        # RETURNED 500 THE FIRST TIME ANYTHING EXECUTED IT (`DEF-MET-5464`).**
        # It read `service_code=` and `asset_no=`; the published seam is
        # `create_asset_for_unit(*, actor, unit_id, service_point_id, payload)`
        # and both of those travel INSIDE `payload`. The line was dead code from
        # task 6.10: the door in front of it answered 404 (`DEF-MET-5441`) so no
        # browser reached it, and every test here commits with `meters: []`.
        # `metering/seams.py` forwards `**kwargs`, which checks nothing, so
        # nothing failed at import either.
        #
        # ⚠ **`service_point_id=None` IS DELIBERATE AND IS NOT A GAP.**
        # `_create_asset_inner` raises the service point itself when it is given
        # a unit and a service — *"if unit_id and service_code and not
        # service_point_id"* — which is the SAME path `create_premises`'s unit
        # wizard takes. Passing one from here would be a second raiser of a row
        # the assets module already owns.
        #
        # ⚠ **`asset_no` IS PASSED THROUGH AS `None` ON PURPOSE.** The wizard
        # sends null because step 8's own outstanding-work item says so —
        # *"50 meters still read 'to assign'"* — and the assets door then
        # allocates from the series. A number invented here would be a meter
        # serial nobody has.
        #
        # ⚠ **`installed=False` — PO RULING 2026-09-21, AND IT IS THE WHOLE
        # DIFFERENCE BETWEEN A NUMBER AND A FITTED METER.** Verbatim: *"you can
        # generate meter, sub meter or asset # and assigned it - but theya re
        # not yet installed or actiavted"*, and *"install date on work order
        # completion - yes"*. Before this flag existed, a build's meter was
        # measured landing `install_date 2026-09-20` (the day of the commit)
        # with status `active`, label *Installed*, behaviour `in_service` — on
        # a site nobody had visited. `DEF-MET-6066` / `DEF-MET-6067`.
        #
        # ⚠ **IT IS A MONEY CONSEQUENCE AS WELL AS A WORD.** `in_service` is
        # one of `billable_asset_count`'s three predicates, so an unfitted
        # meter was in the population a capacity or per-meter service bills
        # from. It no longer is.
        # ⚠ **NO NET METER ON A SOLAR OR BATTERY BUILD — PO ruling 2026-10-02
        # (`DEF-MET-9037`), verbatim:** *"we are not doing net metering right
        # now - we are doing capacity based panel - A · The net meter doesn't
        # count toward capacity. Capacity is the panels or battery only."* The
        # wizard stopped sending this row the same day (`takesAMeter`); a row
        # that still arrives — an older bundle in an open tab — is LEFT OUT and
        # named on `unavailable`, never refused: refusing would lose a whole
        # build over a row the clerk never chose. The panels and batteries
        # travel on `unit_services` and are untouched.
        skipped_meters = sorted(
            {
                str(spec.get("service"))
                for spec in data.get("meters") or []
                if spec.get("service") in NO_METER_CAPACITY_SERVICES
            }
        )
        if skipped_meters:
            absences.append(
                {
                    "field": "meters",
                    "code": "no_net_meter_on_a_capacity_service",
                    "tracks": "DEF-MET-9037",
                    "detail": (
                        "Solar and battery are billed on the panels and batteries "
                        "alone (PO 2026-10-02), so no meter is fitted for them."
                    ),
                    "services": skipped_meters,
                }
            )
        for spec in _meters_to_fit(data):
            meter_unit = _unit_for_spec(spec, by_label, field="meters")
            created = seams.create_asset_for_unit(
                actor=actor,
                unit_id=meter_unit,
                service_point_id=None,
                payload={
                    "type": "meter",
                    "service": spec.get("service"),
                    "asset_no": spec.get("asset_no"),
                    # ⊕ `DEF-MET-9221` — the size step 3 showed on the meter's
                    # row. Only when one was sent: the assets door validates it
                    # against the service's own size list.
                    **({"size_class": spec["size_class"]} if spec.get("size_class") else {}),
                },
                installed=False,
            )
            if created is not None:
                made["meters"] += 1
                # `DEF-WRK-9683` — remembered so step 5 can stand a per-meter
                # job on the meter this build fits (see `_build_meter_for`).
                build_meters.append(
                    {"id": created.get("id"), "unit_id": meter_unit, "service": spec.get("service")}
                )

        # 2b · WHAT THIS BUILD PROVIDES, AND WHERE — one `connection_services`
        #      row per unit × service, written in the same pass that raised the
        #      service points, because this is the only place that knows both
        #      halves at once.
        #
        # ⚠ **NO COMMIT THIS PRODUCT HAS EVER PERFORMED WROTE ONE
        # (`DEF-MET-6108`), AND THE BUILD'S OWN RECORD THEREFORE READ ZERO OVER
        # A REAL BUILD.** Measured on `CON-26-0139`: eight units, sixteen
        # meters, a `$315.00` invoice — and `UNITS 0 · ACTIVATED 0 of 0 · 0 of 0
        # points live`. **The units, the plans and the service points were all
        # REAL**; the one thing missing was the row that says *this BUILD
        # provides this SERVICE at this UNIT*, which is what every one of those
        # figures counts (`_unit_counts`, `_unit_rows`, `_units_activated`,
        # `_service_point_progress`) — and what `connection_state` itself
        # derives from, so the state a clerk read was a reading of nothing.
        #
        # ⚠ **THE MANIFEST IS NOT THE PROOF, WHICH IS WHY THIS SURVIVED.** The
        # done panel counts what the commit just made from its OWN manifest —
        # `Units 8`, `Meters 16` — and is right; the readback asks a different
        # table. Both halves green, one of them describing a build the record
        # could not see.
        #
        # ⚠ **`add_connection_service` IS REUSED RATHER THAN RE-IMPLEMENTED.**
        # It owns this write: the tenant-enabled refusal (metering's own seam,
        # so one mistake has one message), the `get_or_create` that makes two
        # meters on one unit for one service ONE service row, `is_sample`, and
        # the audit row. A second writer here is a second place for the
        # uniqueness pair and the refusal to drift apart.
        #
        # ⚠ **NO `try/except`, LIKE EVERY OTHER STEP OF THIS COMMIT.**
        # `BR-MET-112` is both-or-neither, and CLAUDE.md hard-won law 14 is why
        # a skip would be worse than useless: on PostgreSQL the transaction is
        # already poisoned by the refused statement, and this repo's SQLite
        # suite would pass the broken version green.
        #
        # ⚠ **A METER WITH NO SERVICE IS SKIPPED AND NOT REFUSED.**
        # `_create_asset_inner` raises a service point only when it is handed a
        # unit AND a service, so such a meter left no point to record either —
        # refusing here would refuse a build the loop above accepted.
        for spec in _meters_to_fit(data):
            service_code = spec.get("service")
            if not service_code:
                continue
            add_connection_service(
                actor,
                connection.id,
                service_code=service_code,
                unit_id=_unit_for_spec(spec, by_label, field="meters"),
            )
        # ⚠ **AND A SERVICE THAT TAKES NO METER IS NOT RECORDED HERE, BECAUSE
        # IT IS NOT ON THE PAYLOAD AT ALL (`DEF-MET-6119`).** `commitPlanOf`
        # emits `meters` only where `takesAMeter(service)` is true, so trash,
        # fire, storm water, broadband and thermal reach this commit in no
        # member of any key. This absence is stated rather than guessed around:
        # deriving the pairs from `premises.services_available` would invent a
        # row for a unit the clerk deliberately unticked, and that is the
        # wizard's answer to give, not this door's.
        made["sized_equipment"] = _commit_unit_services(actor, connection, data, by_label)
        unmetered = _services_without_a_meter(data)
        if unmetered:
            absences.append(
                {
                    "field": "connection_services",
                    "code": "unmetered_services_are_not_on_the_payload",
                    "tracks": "DEF-MET-6119",
                    "detail": (
                        "A service that takes no meter (trash, fire, storm water, broadband, "
                        "thermal) is mapped to its units by step 4 and travels on no key of "
                        "this payload, so this commit cannot record where it is provided. "
                        "The metered services ARE recorded. Reported rather than derived from "
                        "the address's service list, which would invent a row for a unit the "
                        "clerk unticked."
                    ),
                    "services": unmetered,
                }
            )

        # 3 · PLAN ASSIGNMENTS — BEFORE the account. See the docstring.
        #     Keyed by the LABEL as well, for the same reason (`DEF-MET-5437`):
        #     a `None` here priced NOTHING and raised nothing, so a build could
        #     not price a single unit it had created in the same call.
        for spec in data.get("plan_assignments") or []:
            metering_services.assign_unit_plan(
                actor,
                _unit_for_spec(spec, by_label, field="plan_assignments"),
                {"tariff_id": spec.get("tariff_id")},
            )
            made["plan_assignments"] += 1

        # 4 · THE OWNER'S ACCOUNT — BR-MET-116, through the customers door, so
        #     BR-CUS-068's whole guard set applies to a build account exactly as
        #     it applies to a hand-made one.
        if data.get("create_owner_account"):
            opened = create_owner_account(actor, connection.id, data.get("owner") or {})
            made["customers"] = 1
            made["owner_account_id"] = opened["owner_account_id"]
            # ⚠ **`DEF-MET-5479` — WITHOUT THIS LINE THE ACCOUNT EXISTS AND NO
            # LATER STEP OF THIS TRANSACTION CAN SEE IT.**
            # `create_owner_account` re-fetches its OWN connection row through
            # `_connection_or_404`, writes `owner_account_id` on that object and
            # saves it. The database is right; this function's object is a copy
            # taken before step 4 and still says `None`. So step 6's payer
            # answered `quote_payer_owner_has_no_account` and step 7's three
            # letters answered `this_build_names_no_owner_account` — **on a
            # build that had just opened the account they were looking for.**
            #
            # Measured in a browser rather than in a fixture, and the fixture
            # shape is exactly what hid it: every test that exercises the payer
            # tags the account through `tag_charges_to_account` and then calls
            # `connection.refresh_from_db()` itself, so the object under test is
            # always fresh and the commit's own object is never the one asserted
            # on. Only a build that creates the account INSIDE the commit can
            # show this, and nothing drove that end to end while the commit door
            # answered 404.
            connection.refresh_from_db(fields=["owner_account"])

        # 4b · THE OWNER'S ACCOUNT AT THE ADDRESS — `BR-MET-1010`, through the
        #      door `CR-056` W1 opened and named this task as the caller of.
        #
        # ⚠ **THIS IS A DIFFERENT ACCOUNT FROM STEP 4, FOR A DIFFERENT PARTY,
        # AND THE TWO ARE NOT INTERCHANGEABLE.** Step 4 is `BR-MET-116`: the
        # BUILD account for a development, COVERING its common areas where it
        # has any, which is the developer's. This is `BR-MET-1010`: the account the
        # ADDRESS's declared owner holds at that address, whether or not
        # anything is shared — the PO's ruling of 2026-08-31 that *every address
        # gets its owner a Master Account*. ⚠ **`BR-MET-116` NO LONGER REFUSES A
        # BUILD WITH NO COMMON AREA (PO 2026-09-21, *"common area is option"*),
        # so the two doors now overlap on a house** — and the thing that keeps
        # them from making two accounts is `BR-CUS-1011` below, which already
        # refused a second master at one address and is the reason this needed
        # no new guard.
        #
        # ⚠ **ASKING FOR BOTH IS REFUSED, BY A RULE THAT ALREADY EXISTS.**
        # `BR-CUS-1011` — one owner account per address — makes the second call
        # refuse by name inside `create_master_account`. That refusal is the
        # right one and is deliberately not pre-empted here: a second copy of
        # the guard is a second place for it to be relaxed.
        #
        # ⚠ **OPT-IN, BY NAME.** An account is a money object and `BR-MET-112`
        # is the rule that says a wizard does not mint one because a field was
        # filled in. It is also IDEMPOTENT: an owner already holding an account
        # at this address gets it back and nothing is written.
        if data.get("create_owner_master_account"):
            from apps.metering import premises_owners

            owner_id = getattr(connection.premises, "owner_id", None)
            if owner_id is None:
                # ⚠ **THE MIDDLE CLAUSE OF THIS REFUSAL LIVES HERE NOW.** The copy
                # said *"…so there is no one to open an owner's account for"* until
                # 2026-09-03; B14 rule 33 caps a sentence at six words, so the
                # RATIONALE was dropped and both halves that a clerk acts on were
                # kept — which connection, and what to do. The dropped fact is
                # this: an owner master account is opened FOR a party, and the
                # premise names none, so there is no party to open it for. Nothing
                # is guessed from the free-text owner name (`BR-MET-112`), which is
                # why the answer is a refusal rather than a blank account.
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-MET-1024",
                    message_key="metering.connection_premises_names_no_owner",
                    params={"connection_no": connection.connection_no or ""},
                )
            owner = premises_owners.ensure_owner_master_account(
                actor,
                owner_id,
                connection.premises_id,
                data.get("owner_account") or {},
            )
            made["owner_master_account_id"] = owner.get("master_account_id")

        # 5 · THE WORK ORDERS STEP 6 LEFT STANDING — `BR-MET-112`, `BR-WRK-006`,
        #     `BR-WRK-008`, and `DEF-MET-5428` is why this block exists at all.
        #
        # ⚠ **THEY WERE COLLECTED AND DISCARDED FROM `CR-070` WAVE E UNTIL
        # 2026-09-16.** `commitPlanOf` has emitted `work_orders` since step 6
        # began proposing them and its own comment said *"the server raises the
        # orders inside the same transaction as the build"*. This function never
        # read the key. A clerk who kept nine proposals was told at step 8 that
        # nine orders would be written, pressed **Create connection ✓**, and got
        # a build with ZERO and no refusal — hard-won law 2 one module boundary
        # away, invisible because BOTH sides were tested on the PAYLOAD.
        #
        # ⚠ **THIS IS A SAME-MODULE CALL AND NOT A SEAM, WHICH IS WORTH SAYING
        # OUT LOUD BECAUSE THE TABLE'S NAME SUGGESTS OTHERWISE.** `work_orders`
        # is METERING's table — `WorkOrder` is declared in this file — and
        # `create_work_order` is metering's own service. Work's six COPY tables
        # are Work's, and they are written by `apps.work.order_copies` from
        # inside that function, which is where the boundary actually runs and
        # where `G78` watches it. Reaching for a seam here would have put a
        # second, drifting raiser beside the one every other door uses.
        #
        # ⚠ **THE PAYLOAD IS `work.from_flows.raise_for`'s, COPIED RATHER THAN
        # INVENTED.** The five customer flows have raised from a proposal since
        # wave P; an order raised there and one raised here differ in their
        # `source` and in nothing else, which is the point.
        #
        # ⚠ **NO `try/except` AND NO PER-ORDER SAVEPOINT, DELIBERATELY.**
        # `BR-MET-112` is BOTH OR NEITHER, so a template that cannot be copied
        # takes the whole build down rather than leaving a premises with 26
        # units and a promise nobody kept. Catching here would be CLAUDE.md
        # hard-won law 14's trap exactly: on PostgreSQL the transaction is
        # already poisoned by the refused statement, the units are lost at
        # COMMIT anyway, and this repo's SQLite suite — which has no
        # aborted-transaction state — would pass the broken version green.
        # **Do not "simplify" this into a skip.**
        raised_orders: list[dict[str, Any]] = []
        republished: list[dict[str, Any]] = []
        # ── `DEF-MET-9179` (2026-10-02, `CR-163-BRC10` item 15) ─────────────
        # **THE SERVICES THIS BUILD ACTUALLY CARRIES**, read off the rows this
        # same commit has just written. An order was stamped with its
        # TEMPLATE's own service, so on the PO's Battery/Solar build *G Trade
        # Tower* a whole-build *"Installation Template"* read **Water** and
        # *"Service connection"* read **Fire** — services the build does not
        # have. A template's service is a property of the CHECKLIST; which
        # service an order stands on is a fact about the BUILD.
        build_services = set(
            ConnectionService.objects.filter(
                tenant_id=tenant_id, connection_id=connection.id
            ).values_list("service__code", flat=True)
        )
        for spec in data.get("work_orders") or []:
            template = WorkOrderTemplate.objects.filter(
                tenant_id=tenant_id, pk=spec.get("template_id") or None
            ).first()
            if template is None:
                # HR-1 — existence must not leak. 404, never 403.
                raise errors.deny_as_not_found("BR-TEN-003")
            # ⚠ **THE VERSION THE PAYLOAD NAMES IS COMPARED AND NEVER STAMPED,
            # AND THAT IS `BR-WRK-008` RATHER THAN A PREFERENCE.** The copies
            # `order_copies` writes are taken from the template's rows AT THE
            # RAISE, so stamping the browser's older number would produce an
            # order whose version says v1 over a checklist copied from v2 — the
            # rule broken by a VALUE instead of by a join, which is the exact
            # failure `create_work_order` already refuses a DRAFT to avoid.
            #
            # A template republished between step 6's proposal and step 9's
            # press is ordinary — two clerks, one afternoon — and refusing the
            # build over it would lose 26 units to a checklist edit. So the
            # order is raised from the version actually copied and the
            # divergence is REPORTED on the commit, which is the posture this
            # manifest already takes for everything it cannot answer.
            proposed_version = spec.get("template_version")
            if proposed_version is not None and int(proposed_version or 0) != int(
                template.version or 0
            ):
                republished.append(
                    {
                        "template": template.name,
                        "proposed_version": int(proposed_version or 0),
                        "raised_version": int(template.version or 0),
                    }
                )
            # ⚠ **A UNIT ONLY WHEN THE ROW NAMES ONE; OTHERWISE THE WHOLE
            # BUILD.** The wizard's per-row work-order pick (another lane's,
            # `CR-162`/NC-C) sends `unit_label`; until it does every order here
            # stands on the build itself, which the Work tab now says in words
            # (`DEF-CUS-9178`). A label that names no unit is refused by
            # `_unit_for_spec`, never guessed (`DEF-MET-5437`).
            names_a_unit = bool(spec.get("unit_id") or str(spec.get("unit_label") or "").strip())
            order_unit = (
                _unit_for_spec(spec, by_label, field="work_orders") if names_a_unit else None
            )
            # ⚠ **THE SERVICE: the row's own pick, else the template's — and
            # EITHER ONLY WHEN THE BUILD CARRIES IT** (`DEF-MET-9179`). A
            # template whose service the build does not have raises an order
            # with NO service rather than a false one: an absence the screen
            # can state, where a wrong word is a claim nobody can see through.
            asked = str(spec.get("service") or "").strip() or (
                template.service.code if template.service_id else ""
            )
            order_service = asked if asked in build_services else None
            # ⚠ **A PER-METER JOB STANDS ON THE METER THIS BUILD FITS
            # (`DEF-WRK-9683`).** *Meter set* posts its opening read to the
            # order's own meter at Accept (`BR-WRK-003`), and a build's job
            # named none — the meter was created a few lines up, in inventory,
            # and `DEF-WRK-9620`'s fallback looks only for a meter IN SERVICE —
            # so Accept refused it for ever (`work.reading.no_meter_on_order`,
            # WO-0047). Exactly one meter of the order's service (on its unit,
            # when it names one) is the answer; two is `OQ-WRK-1723` and is not
            # guessed between.
            fitted = _build_meter_for(template, order_service, order_unit, build_meters)
            order = create_work_order(
                actor,
                connection.id,
                {
                    "type": template.name,
                    "scope": template.scope,
                    # `_service_row` takes the CODE and refuses a service this
                    # tenant does not run — the same refusal `ensure_service_point`
                    # gives, so one mistake has one message.
                    "service": order_service,
                    "unit_id": order_unit,
                    "template_id": str(template.id),
                    "is_gate": template.is_gate,
                    **({"asset_id": fitted} if fitted else {}),
                    # `BR-WRK-024` — WHY the job exists, and WHICH record asked.
                    "source": SOURCE_NEW_CONNECT,
                    "source_ref": connection.connection_no,
                },
            )
            # `CR-168-BRC10` P3.42 — step 6 showed this job ticked by a Work
            # rule on *a new connection is built*; the rule's priority and
            # holder are applied here, in their own savepoint, exactly as the
            # failed-job retry takes its rule's (P3.35). No rule naming the
            # template is the ordinary case and changes nothing.
            _shape_retry_by_rule(actor, order["id"], str(template.id), SOURCE_NEW_CONNECT)
            raised_orders.append(order)
        made["work_orders"] = len(raised_orders)
        if republished:
            absences.append(
                {
                    "field": "work_orders",
                    "code": "template_republished_since_proposal",
                    "tracks": "BR-WRK-008",
                    "detail": (
                        "A template was published again between step 6's proposal and this "
                        "commit. The order copies the version it was raised from, so it is "
                        "stamped with that one and not with the number the browser held — a "
                        "stamp that did not describe the copy would break copy-never-link by "
                        "a value instead of by a join."
                    ),
                    "templates": republished,
                }
            )

        # 6 · THE QUOTE — PRICED BY BILLING AND POSTED. `OQ-379` answered.
        #
        # ⚠ **THE ABSENCE THAT STOOD HERE IS DELETED RATHER THAN REWORDED.** It
        # said the quote was *"recorded on the connection and posted by
        # nothing"*, which was true while billing's one-time door took one bare
        # code. `CR-109` widened it, so the sentence became false the moment
        # `_post_connection_quote` landed — and a stated absence that outlives
        # its cause is a lie the product tells about itself (hard-won law 1).
        #
        # ⚠ **INSIDE THIS TRANSACTION AND BEFORE THE MESSAGES, AND BOTH HALVES
        # OF THAT MATTER.** Inside, because `BR-MET-112` is both-or-neither: a
        # build that rolled back must not leave a receivable behind it, and a
        # receivable that failed to post must not leave 26 units nobody can
        # bill. Before, because step 7 queues the letter that ASKS FOR THIS
        # MONEY — you do not send a bill before the bill exists.
        #
        # ⚠ **`quote_total` IS NEVER TAKEN FROM THE PAYLOAD, ON ANY PATH, AND
        # THAT IS HARD RULE 2 — `DEF-MET-7641`, `BR-MET-1187`.** This block used
        # to store whatever figure the client sent. A total arriving over the
        # wire is a figure multiplied up somewhere other than the server, and it
        # can disagree with the invoice the customer actually receives — two
        # numbers for one debt. The POSTED invoice's own total is what the
        # connection records, so the build and the bill cannot drift.
        #
        # ⚠ **THIS PARAGRAPH ENDED *"The client's figure is still honoured on
        # the paths where nothing is posted: there it is the only statement of
        # what was quoted, and recording it loses nothing"* UNTIL 2026-09-28,
        # AND IT WAS THE DEFECT WRITTEN DOWN AS A DESIGN.** What it lost was the
        # money: `$1,035.00` on a `connections` row, no invoice, nothing in
        # Billing, nothing in Finance and nobody ever asked for it. The same
        # rule was being enforced in one direction only. The client's figure is
        # now used for exactly one thing — REFUSING a commit whose bill
        # disagrees with what the clerk was shown (`_refuse_a_total_the_screen_
        # never_showed`) — and is written nowhere.
        #
        # ⚠ **NO ROUNDING HAPPENS HERE.** Hard rule 2 rounds ONCE, at
        # finalization; `raise_and_issue_quote_bill` finalizes, and what comes
        # back is already the document's own total to four decimals. Re-rounding
        # a figure billing has issued would make the connection and the invoice
        # two statements of one debt.
        #
        # ── `BR-MET-1187` · THE TILL IS ASKED FOR BEFORE THE BILL IS RAISED ──
        # PO ruling 2026-09-23 §3.4: cash, cheques and money orders are refused
        # until the person recording them has a till open. Asked HERE, before
        # `_post_connection_quote` writes anything, for `_quote_payer`'s reason
        # word for word — a refusal after the invoice exists discards a build
        # that was fine, and on PostgreSQL a refusal raised by the far side
        # would already have poisoned this transaction (hard-won law 14). The
        # rule has ONE implementation, in `payments.counters`; this is a call
        # site.
        #
        # ⚠ **`_quote_posting_date` IS ASKED TWICE ON THIS PATH AND THAT IS
        # SAID OUT LOUD RATHER THAN LEFT TO BE FOUND.** `_post_connection_quote`
        # asks it again for the invoice. When the clerk TYPED a posting date —
        # which step 4 draws and the wizard sends — both reads return that date
        # and the two are identical. Only when nobody typed one do they each
        # fall back to *today*, and then a commit crossing midnight between
        # these two lines would date the payment one day after the charge. That
        # is two true statements about two acts rather than a drift, and
        # threading the value through would change a signature for a
        # one-second window; if it ever matters, pass it in rather than
        # caching a clock.
        taken = _payment_taken_at_the_counter(data, on_date=_quote_posting_date(data))
        if taken is not None:
            till = seams.counter_till_for_tender(actor, taken["method_code"])
            if till["refusal"] is not None:
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-PAY-1186",
                    # The literal key Record a payment's own door raises, so a
                    # clerk reads the same words at both counters.
                    message_key="payments.counter.till_required",
                    params={"detail": till["refusal"], "step": STEP_OF_THE_CHARGES},
                )
            taken["till_id"] = till["till_id"]
        quote = _post_connection_quote(actor, connection, data)
        if quote["posted"]:
            _refuse_a_total_the_screen_never_showed(connection, data, quote["total"])
            connection.quote_total = Decimal(str(quote["total"]))
            # ⚠ **THE BILL'S ID IS WRITTEN DOWN HERE, AND UNTIL `CR-126-BRC07`
            # IT WAS NOT WRITTEN DOWN ANYWHERE.** `_post_connection_quote` has
            # returned it since 2026-09-16 and it lived for the length of one
            # HTTP response; the only durable trace was a stamp on
            # `service_request_fees`, written through
            # `seams.mark_request_quote_invoiced` — and that hangs off the
            # REQUEST.
            #
            # ⚠ **PO RULING 2026-09-21 IS WHY THAT IS NOT ENOUGH:** *"this
            # request is new work and recognized seperately from applcaition and
            # hence we should not make it dependent on applciation #"*. A build
            # raised directly has no request, so with the invoice recorded only
            # against one, such a build could never name its own bill — and the
            # build record's `OUTSTANDING` tile would be underivable for ever.
            # With the id on the row, *Quoted*, *Taken* and *Outstanding* are
            # all DERIVED and no money figure is stored twice (`DEF-127`).
            connection.quote_invoice_id = quote.get("invoice_id")
            connection.save(
                update_fields=["quote_total", "quote_invoice_id", "updated_at"]
            )
            # ⚠ **READ BACK WHAT WAS STORED, DO NOT REPORT WHAT WAS IN MEMORY —
            # HARD RULE 2.** `invoices.total` is one of the legacy `NUMERIC(18,6)`
            # containers the rule leaves lawful, so billing hands back
            # `800.000000`; `connections.quote_total` is `NUMERIC(18,4)`, which
            # is what the rule says money is WRITTEN to. Reporting the in-memory
            # object would put a six-decimal figure on the manifest and a
            # four-decimal one in the database — two statements of one debt,
            # which is the exact thing taking the total off the client was meant
            # to stop. **No rounding is performed here**: the column holds it or
            # it does not, and this reads the column.
            connection.refresh_from_db(fields=["quote_total"])
            made["one_time_charges"] = str(connection.quote_total)
            made["one_time_charge_invoice_no"] = quote["invoice_no"]
            # 6b · THE PAYMENT THE CLERK TOOK, AGAINST THE BILL JUST RAISED —
            #      `BR-MET-1187`: *"we create entries in books"* and the
            #      payment with them, in the SAME act.
            #
            # ⚠ **AFTER THE INVOICE AND INSIDE THE SAME TRANSACTION.** After,
            # because the money is allocated to a named bill and the bill has
            # to exist to be named. Inside, because `BR-MET-112` is
            # both-or-neither: a build that rolled back must not leave a
            # receipt behind it, and a payment that could not be recorded must
            # not leave a receivable the clerk believes is settled.
            if taken is not None:
                paid = _record_the_payment_taken(actor, connection, taken, quote)
                made["one_time_charge_payment_no"] = paid["payment_no"]
                made["one_time_charge_paid"] = (
                    None if paid["amount"] is None else str(paid["amount"])
                )
                # ⚠ **PAYMENTS' OWN CODED PROBLEMS RIDE THE COMMIT.** Until
                # CR-186-BRC10 the one that mattered was
                # `not_cleared_so_not_allocated` (a `processing` payment met no
                # bill); a new payment is now `posted` and applied at entry, but
                # any problem payments reports is still carried here in its own
                # code and sentence rather than swallowed.
                for problem in paid["problems"]:
                    absences.append(
                        {
                            "field": "one_time_charge_paid",
                            "code": problem.get("code"),
                            "tracks": problem.get("br_ref"),
                            "detail": problem.get("detail"),
                            # ⊕ `DEF-MET-9245` — WHICH copy had no address. A
                            # receipt with no mobile number still went by email
                            # and print, and a note without the channel read as
                            # if nobody got one.
                            "channel": problem.get("channel"),
                        }
                    )
                if paid["credit_carried"]:
                    # ⚠ **REPORTED, NEVER DROPPED (`BR-PAY-010`).** More money
                    # than the bill owes is lawful — a developer rounding up —
                    # and it carries as an account credit. Saying so on the
                    # commit is the difference between a clerk who knows where
                    # the extra $40.00 went and one who thinks it vanished.
                    absences.append(
                        {
                            "field": "one_time_charge_paid",
                            "code": "payment_exceeded_the_bill_and_carries_as_credit",
                            "tracks": "BR-PAY-010",
                            "detail": (
                                "The payment is larger than this build's bill, so the "
                                "remainder is held on the account as a credit and will "
                                "meet the next bill. Nothing is lost and nothing is "
                                "refunded here."
                            ),
                            "credit_carried": str(paid["credit_carried"]),
                        }
                    )
        else:
            # ⚠ **REFUSES, WHERE IT USED TO CARRY ON — `BR-MET-1187`.** Two
            # absences mean there is nothing to write and the build stands;
            # every other one means the books entry exists and failed, and then
            # the connection is not created either. The whole argument, with
            # the PO's words and what it supersedes, is on the helper.
            _refuse_a_books_entry_that_cannot_be_written(connection, quote["absence"])
            # ⚠ **`None`, NOT `""` AND NOT `"0"`.** Nothing was billed because
            # nothing was chargeable, and `$0.00` would read as *"this build
            # was free"* — the same posture `sub_meter_links` and
            # `one_time_charge_invoice_no` already take on this manifest. It
            # read `str(connection.quote_total or "")` while the client's
            # figure was being stored here; with nothing stored, an empty
            # string would be a figure-shaped hole.
            made["one_time_charges"] = None
            absences.append(quote["absence"])
        absences.append(
            {
                "field": "sub_meter_links",
                "code": "no_door_from_metering",
                "tracks": "OQ-379",
                "detail": (
                    "A sub-meter link is an assets relationship and this module has no seam "
                    "that writes one. Reported rather than counted as 0 — a zero would read as "
                    "'we made none' where the truth is 'we cannot make them from here'."
                ),
            }
        )
        made["sub_meter_links"] = None

        # 7 · THE MESSAGES — the LAST act, in the PO's ruled order.
        #
        # ⚠ **`connection_messages.queue_on_commit` HAD NO CALLER UNTIL NOW, AND
        # THAT IS HARD-WON LAW 2 EXACTLY** — lane D built and proved the three
        # letters a new build sends its owner (*the build has been created*, *the
        # contract*, *what it costs, please pay it*), 13 cases green against real
        # PostgreSQL, and nothing in the product reached them. A built path
        # nothing calls passes every test on either side of the gap.
        #
        # **LAST, AND INSIDE THE TRANSACTION.** Last because the PO's order is the
        # request row, the premises, the units, the assets, the plan, the master
        # account, the customer, THEN the messages — you do not tell somebody
        # what they owe before the thing they owe it for exists. Inside because
        # `BR-MET-112` is both-or-neither: a build that rolled back must not
        # leave three letters queued about it. The door writes only queue rows
        # and one audit row per message and says so, so it is safe here.
        #
        # ⚠ **IT REPORTS THAT NOTHING WAS QUEUED, AND THAT IS THE CORRECT ANSWER
        # TODAY — DO NOT "FIX" IT BY CHOOSING A SOURCE KIND.** All three are
        # refused by name because the platform has no `connection` source kind,
        # open since `CR-030`. Filing them as `notice` would put a welcome letter
        # among disconnection notices, which is a worse answer than none. The
        # refusals ride in the manifest with the question that would unblock
        # them; the count is of ROWS WRITTEN, never of intentions.
        made["messages"] = queue_messages_on_commit(actor, connection, data.get("messages"))

        # ── `CR-162-BRC10` · THE OWNER'S MASTER ACCOUNT WAITS FOR APPROVAL ────
        # PO 2026-10-02 (Q1): *"created PENDING at Create, ACTIVE on approval"*.
        # Held HERE, after the charges and any payment are on the books, because
        # billing's door refuses a pending account (see
        # `customers.services.hold_new_master_pending`). Only on a premises this
        # build created (still `pending`): an owner account at an address
        # already in service is left exactly as it opened.
        connection.refresh_from_db(fields=["owner_account", "premises"])
        if connection.premises is not None and connection.premises.status == "pending":
            held = {
                str(one)
                for one in (connection.owner_account_id, made.get("owner_master_account_id"))
                if one
            }
            for account_id in sorted(held):
                seams.hold_new_master_pending(actor, account_id)

        # `DEF-CUS-9211` — the property answers typed on the request this build
        # was raised from reach the premises it stands on (W6's rules: active
        # fields only, an answer already there is kept, one audit row).
        if connection.service_request_id and connection.premises_id:
            seams.carry_request_custom_answers(
                actor, connection.service_request_id, premises_id=connection.premises_id
            )

        # ⚠ `_stamp` takes the id and keyword-only `field`/`action` — it also
        # opens its own atomic block, which nests inside this one as a
        # savepoint. That is correct: a refusal inside it rolls back the whole
        # commit, which is BOTH OR NEITHER.
        _stamp(
            actor,
            connection.id,
            field="submitted_at",
            action="connection.submitted",
            expect_unset=True,
        )
        _audit(
            actor,
            "connection.committed",
            "connection",
            connection.id,
            after={k: made.get(k) for k in MANIFEST_KEYS},
        )

    refresh_connection_state(connection)
    return {
        "id": str(connection.id),
        "connection_no": connection.connection_no,
        "manifest": {key: made.get(key) for key in MANIFEST_KEYS},
        # `DEF-MET-6119` — beside the manifest rather than in it: the manifest
        # is a contract both sides of the wire hold equal (a front-end test
        # reads `MANIFEST_KEYS`), and this count is read by no screen yet.
        "sized_equipment": made.get("sized_equipment", 0),
        # CR-070 wave O — where the wizard's *Open this connection* goes. Served
        # from the commit rather than fetched afterwards, because the answer is
        # known the moment the row exists and a second round trip on a
        # completion screen is a spinner over a fact we already have.
        "home": connection_home(connection),
        "unavailable": absences,
        "br_ref": "BR-MET-112",
    }


# ════════════════════════════════════════════════════════════════════════════
# `DEF-MET-5441` — THE WIZARD'S BUTTON GETS A DOOR, AND IT IS ONE DOOR
# ════════════════════════════════════════════════════════════════════════════
#: **The wizard's premises block, in `create_premises`'s own vocabulary.**
#:
#: The screen collects `{id, address, premise_type, parcel_ref, read_route}`
#: and `_validate_premises` refuses, by name, every key it does not know. Four
#: of the five are spelled differently there, and each mapping is evidence-led
#: rather than chosen — the reasoning is in the decision log of 2026-09-16.
#:
#: ⚠ **`parcel_ref` LANDS ON `external_ref` BECAUSE THAT IS ALREADY WHERE A
#: PARCEL KEY LIVES.** `integrations/seams/metering.py` writes
#: `"external_ref": candidate.get("parcel")` from the City's answer and
#: `parcel_is_taken` reads it back through `premises_external_ref_taken`
#: (`BR-INT-048`, `DEF-INT-4273`). There is no `parcel_ref` column, and adding
#: one would give one key a second home — the thing hard rule 8 exists to stop.
PREMISES_BLOCK_FIELDS: dict[str, str] = {
    "address": "address_line",
    "premise_type": "premises_type",
    "parcel_ref": "external_ref",
    "read_route": "route",
    # `DEF-MET-5465` — step 4's ticks, which decide whether a meter may be
    # fitted here at all. `BR-MET-003`'s inner bound (`DEF-772`) refuses a
    # meter for a service the PREMISES does not list, and a property created
    # with this NULL reads as *"nobody has been asked"* and refuses every one.
    # The name is the same on both sides, so this row is the door SAYING it is
    # carried rather than leaving it to the unknown-key refusal below.
    "services_available": "services_available",
    # ── `DEF-MET-5469` · THE TOWN AND THE BUILDING'S NAME ─────────────────
    # ⚠ **`_validate_premises` HAS KNOWN ALL FOUR SINCE `US-MET-001` AND THIS
    # TABLE CARRIED NONE OF THEM**, so this wizard was the one property-creating
    # door in the product that structurally could not record a town. It was
    # invisible precisely BECAUSE the refusal above works: an unknown key is
    # refused by name, so no screen ever sent one, so nothing ever went red —
    # the field was absent rather than broken. `AddPremisesWizard` has collected
    # city, state and postal code since S16 shipped, and `accountDetailHeader`
    # walks to the premises for its `Austin, TX 78704` line, which was therefore
    # blank forever on every account built here (`DEF-CUS-5468`, and
    # `DEF-CUS-3653` is the same silence one door over).
    #
    # The names are identical on both sides; the rows exist so this door SAYS it
    # carries them rather than leaving it to the unknown-key refusal.
    "name": "name",
    "city": "city",
    "state": "state",
    "postal_code": "postal_code",
    # ── `CR-161-BRC10` W3 · `DEF-MET-9226` — the tenant's own premises fields,
    # typed on step 2 where Settings places them on *New Connection · Step 2
    # Premise*. Validated by `create_premises` with that screen, so a required
    # field binds here and nowhere else.
    "custom_data": "custom_data",
}


#: The custom-field slot New Connection's step 2 is (`custom_fields.SLOTS`).
NEW_CONNECTION_PREMISE_SCREEN = "NEW_CONNECTION_PREMISE"
#: ⊕ `CR-164-BRC10` wave 2 — the slot New Connection Step 1 draws the OWNER's customer
#: fields on (`tenancy.custom_fields.SLOTS`), named to the master-account door.
NEW_CONNECTION_OWNER_SCREEN = "NEW_CONNECTION_OWNER"


def _premises_block_in_the_doors_language(block: dict[str, Any]) -> dict[str, Any]:
    """Translate, and **REFUSE a key nobody reads rather than dropping it.**

    ⚠ **A TOLERATED KEY WITH NO CONSUMER IS `DEF-MET-4715` EXACTLY** — `route`
    sat on `create_premises`'s payload for weeks, refused by nothing and read by
    nothing, so `POST /premises {"route": "COMPLETE NONSENSE"}` answered 201 and
    dropped it. The fifth key of this block is `id`, handled by the caller; any
    OTHER key is a field the screen believes it is sending somewhere, so it is
    refused by name here and the next person adding one meets a red door instead
    of a silent hole.

    `address_line` is emitted even when it is blank, so the refusal a clerk sees
    for an empty address is `create_premises`'s own `premises.address_required`
    and not a second copy of it written here.
    """
    unknown = [
        key for key in block if key not in PREMISES_BLOCK_FIELDS and key != "id"
    ]
    if unknown:
        metering_services._refuse_fields(
            [
                metering_services._field_error(
                    f"premises.{key}",
                    errors.VAL_FORMAT,
                    "metering.connection.premises_field_unknown",
                )
                for key in sorted(unknown)
            ]
        )
    out: dict[str, Any] = {"address_line": block.get("address")}
    for sent, known in PREMISES_BLOCK_FIELDS.items():
        if sent == "address":
            continue
        value = block.get(sent)
        # ⚠ **`[]` IS SENT AND `None` IS NOT, WHICH IS `DEF-756`'s DISTINCTION
        # AND NOT A TIDY-UP.** An ANSWERED empty list means *"this address
        # offers nothing"*; `NULL` means nobody was asked. `_clean_services`
        # keeps the two apart and both refuse a meter, in different words, so
        # the clerk is told which job is theirs.
        if value == [] or value not in (None, ""):
            out[known] = value
    # ── `CR-162-BRC10` items 1 and 27 · THE ADDRESS IS BORN PENDING ──────────
    # PO 2026-10-02: *"premises is not yet active - it will be activated at the
    # time of approval of new conenct request"*. A premises this wizard CREATES
    # is written at Create (this one press — `BR-MET-112`, never at draft start)
    # with `status = 'pending'`, one of the four values `PREMISES_STATUSES`
    # already allows; the build's first activation moves it to `active`
    # (`connection_activation._activate_premises`). It is set HERE and not taken
    # from the screen: the clerk never chooses it, and a key the wizard does not
    # send cannot be refused by the unknown-key check above. An address already
    # on file (`premises.id`) never passes through this function and keeps its
    # status — existing data unchanged.
    out["status"] = "pending"
    return out


def _commit_raised_draft(
    actor: Any,
    data: dict[str, Any],
    connection_id: Any,
    block: dict[str, Any],
    named: Any,
    commit_key: str | None = None,
) -> dict[str, Any]:
    """**`DEF-CUS-6109` — step 8, for a build an approval already raised.**

    PO ruling 2026-09-21, verbatim: *"then approve applciation may create a new
    conenct request - as draft request - this request is new work and
    recognized seperately from applcaition and hence we should not make it
    dependent on applciation #"*. So the row exists before the clerk reaches
    step 1, and the wizard's last button FINISHES it rather than creating a
    second build beside it.

    ⚠ **THE ADDRESS IS STILL WRITTEN HERE AND NOWHERE EARLIER.** A draft raised
    from a request whose address had not resolved carries `premises = None`
    (`metering/0059`), and `BR-MET-112` is why: a premises created at approval
    would stand for ever the moment a clerk closed the tab, and no screen in
    this product can find that wreckage. So this function takes exactly the
    same two paths `commit_new_connect` takes — name one on file, or create one
    through `metering.services.create_premises` — and attaches the result to
    the draft inside the SAME transaction as the commit. Both or neither.

    ⚠ **A DRAFT THAT ALREADY HAS AN ADDRESS KEEPS IT.** Where the application's
    address DID resolve, the draft was raised against that premises and the
    wizard's step 2 shows it rather than asking again. A block naming a
    DIFFERENT premises is refused by name rather than silently preferred —
    `create_connection`'s *named twice* reasoning, one step later.

    ⚠ **NOTHING ELSE IS RE-DECIDED HERE.** `commit_connection` owns the
    five-module commit and its manifest, and step 1's three answers were
    already written onto the row when the draft was raised; what the clerk
    changes in the wizard is written by the commit, not by a second writer in
    this function.
    """
    # ⛔ **THE SAME TWO TRANSLATIONS `commit_new_connect` MAKES, AND NOT A COPY
    # OF ITS REASONING — `DEF-MET-6110` / `DEF-MET-6111`.** PO ruling
    # 2026-09-21: *"this fix is correct - you ahve to show the error at step you
    # mentioned"*, and that decision log says the shape generalises: **any
    # `RuleError` escaping the New Connect commit is that defect, not a new
    # one.** This is a SECOND door onto the same commit, so a refusal leaving it
    # as a raw 500 is the identical fault on the identical press — the clerk is
    # told the product is broken when they have simply chosen something it
    # refuses, and the whole build is gone.
    #
    # ⚠ **THE `try` IS OUTSIDE THE `atomic()` BLOCK, AS IT IS THERE**, and for
    # CLAUDE.md hard-won law 14's reason: on PostgreSQL the refused statement
    # has already poisoned the transaction, so catching inside and carrying on
    # loses the work at COMMIT anyway, while this repo's SQLite suite — which
    # has no aborted-transaction state — passes the broken version green. By the
    # time either handler runs the block has exited and rolled back, which is
    # `BR-MET-112`'s both-or-neither unchanged.
    refusal_class = seams.quote_refusal_class()
    payment_refusal = seams.payment_refusal_class()
    # `DEF-CUS-8021` — the key is claimed BEFORE the build on this path, and
    # that is safe here in a way it would not be on the from-scratch one: both
    # presses finish the SAME pre-existing row, so a re-claim is an update of
    # one row to the value it already holds and can never collide. On the
    # from-scratch path the row is created inside the transaction, so the claim
    # goes inside it too — see `_claim_the_commit_key`.
    _claim_the_commit_key(connection_id, commit_key)
    try:
        draft, built, premises_created, warnings = _finish_the_draft(
            actor, data, connection_id, block, named
        )
    except IntegrityError as clash:
        _refuse_if_two_units_share_a_label(clash)
        raise  # every other constraint is a defect and stays loud
    except refusal_class as refusal:
        raise _refused_on_the_step_that_chose_it(
            step=STEP_OF_THE_CHARGES,
            br_ref=getattr(refusal, "br_ref", None) or "BR-BIL-020",
            message_key="metering.connection_charge_refused",
            params={"detail": str(refusal)},
        ) from refusal
    except payment_refusal as refusal:
        # ⚠ **`DEF-MET-6110`'s SHAPE, ONE MODULE OVER — ADDED WITH
        # `BR-MET-1187` RATHER THAN AFTER THE FIRST 500.** Payments refuses a
        # tender this tenant does not run, a deactivated method and a till that
        # is closed by RAISING `PaymentRuleError`, which is right for payments
        # and is deliberately NOT a catalogue exception. Left uncaught, a clerk
        # who typed `cheque` where this utility spells it `check` would press
        # *Create connection* after thirty-three acts and read *"Something went
        # wrong on our side."* Translated here, they read which step to go back
        # to.
        #
        # **OUTSIDE THE `atomic()` BLOCK, like the handlers above** (law 14):
        # by the time this runs the block has exited and rolled everything
        # back, so nothing here issues a query and `BR-MET-112`'s
        # both-or-neither is unchanged. It TRANSLATES one recognised refusal
        # and re-raises; it does not swallow a database error and carry on.
        raise _payment_refused_on_the_charges_step(refusal) from refusal

    manifest = dict(built.get("manifest") or {})
    manifest["premises"] = 1 if premises_created else 0
    absences = [
        absence
        for absence in (built.get("unavailable") or [])
        if absence.get("field") != "premises"
    ]
    # `DEF-CUS-8021` — press one's answer is STORED for press two, exactly as
    # it is on the from-scratch path. Both doors onto this commit answer the
    # same way; one of them alone would be a guarantee with a hole in it.
    return _remember_the_commit(
        built["id"],
        commit_key,
        {
            **built,
            "manifest": manifest,
            "premises_id": str(draft.premises_id) if draft.premises_id else None,
            "premises_created": premises_created,
            "warnings": warnings,
            "unavailable": absences,
        },
    )


def _release_the_draft_that_held_this(actor: Any, data: dict[str, Any]) -> None:
    """**`BR-SHL-048 (d)` — one piece of work is ONE row once it is finished.**

    PO ruling 2026-09-21, verbatim: *"this is big problem - we cannot create two
    build - you can update the existing build"*. A clerk who parks a wizard and
    comes back finishes the build; the `wizard_parks` row was only ever holding
    their typing, and once the build is committed it is holding nothing. Left
    behind, it draws a SECOND row on the New connects tab for one build — which
    is the other half of what the acceptance walk saw beside the second build
    itself.

    ⚠ **A MISSING DRAFT NEVER REFUSES A BUILD.** The clerk may have discarded it
    in another tab, or pressed the last button twice; neither is a reason to
    throw away eight steps of work. The posture and the words are
    `customers.services._adopt_wizard_draft`'s: *"No draft, a draft of another
    flow, a draft another tenant owns, a draft already gone — none of them is a
    reason to refuse."*

    ⚠ **THE `except` IS NARROW BY CLASS AND THAT IS CLAUDE.md HARD-WON LAW 14.**
    `NotFoundError` is a DOMAIN refusal raised from a lookup that FOUND NOTHING —
    no statement failed, so nothing here is carrying on inside a poisoned
    PostgreSQL transaction. A bare `except Exception` would be: it would swallow
    a real `IntegrityError` and continue, and this repo's SQLite suite, which has
    no aborted-transaction state, would pass that version green.

    ⚠ **IT IS INSIDE THE COMMIT'S TRANSACTION ON PURPOSE.** A commit that rolls
    back must leave the clerk's typing exactly where it was — a draft deleted by
    a build that then failed would destroy the very work park-and-resume exists
    to protect. `_adopt_wizard_draft` says the same thing one module over:
    *"Call it INSIDE the commit's own transaction."*
    """
    park_id = data.get("wizard_park_id")
    if not park_id:
        return
    try:
        seams.discard_wizard_park(actor, park_id)
    except errors.NotFoundError:
        return


# ════════════════════════════════════════════════════════════════════════════
# `DEF-CUS-8021` — CLAUDE.md HARD RULE 6 ON THE ONE PRESS THAT BUILDS EVERYTHING
# ════════════════════════════════════════════════════════════════════════════
#: The absence a build committed WITHOUT a submit token reports, so a caller
#: that is not the wizard learns it has no replay protection rather than
#: assuming it has. Hard-won law 1: a guarantee nobody wrote is not a guarantee.
COMMIT_TOKEN_ABSENT = {
    "field": "commit_token",
    "code": "commit_token_absent_no_replay_protection",
    "br_ref": "CLAUDE.md rule 6",
    "reason": (
        "this build was committed without a submit token, so a second identical "
        "post would build a second connection. The New Connect wizard mints one "
        "per build; the seeder, the tests and an approval do not"
    ),
}


def _the_commit_key(data: dict[str, Any]) -> str | None:
    """**The wizard's submit token, turned into hard rule 6's key.**

    ⚠ **THE TOKEN IS POPPED, NOT READ.** `commit_connection` and
    `create_connection` each refuse a key they do not know, so a token left on
    `data` would turn the fix into a 422 — `DEF-CUS-8020`'s shape, the defect
    this one landed beside, one payload over.

    ⚠ **OPTIONAL, AND THAT IS STATED RATHER THAN HIDDEN.** Twenty-odd existing
    callers of this door — the seeder, the tests, an approval finishing a
    raised draft — send no token and cannot be made to; refusing them would
    break the product to protect a press they never make. A build with no token
    carries `COMMIT_TOKEN_ABSENT` on `unavailable`, and
    `NewConnectCommitToken.dom.test.tsx` asserts the wizard always sends one —
    so the optionality cannot quietly become the wizard's behaviour too.
    """
    token = data.pop("commit_token", None)
    if token in (None, ""):
        return None
    return core_idempotency.new_connect_commit_key(submit_token=token)


def _the_first_press_answer(commit_key: str | None) -> dict[str, Any] | None:
    """**The SECOND press's whole job: find press one's answer and return it.**

    Rule 6 asks for the first RESULT, never for an error. `409` is what the
    parcel-number constraint was accidentally giving (`premises.external_ref_taken`)
    and it is the wrong answer twice over: it fires only on the minority of
    builds that type a parcel, and it tells a clerk their build failed when it
    succeeded.

    ⚠ **A ROW WITH A KEY AND NO RESULT IS ANSWERED HONESTLY RATHER THAN
    REBUILT.** The key is claimed INSIDE the build's transaction and the result
    is written one statement later, so the only way to reach that state is for
    the process to die between the two. The build exists; what was not recorded
    is press one's manifest. Answering with the connection and a stated absence
    is true; re-running the build would be the double-write this function
    exists to prevent, and recounting the rows would answer what EXISTS rather
    than what that press MADE.
    """
    if not commit_key:
        return None
    row = (
        Connection.objects.filter(tenant_id=_tenant_id(), commit_key=commit_key)
        .only("id", "connection_no", "commit_result")
        .first()
    )
    if row is None:
        return None
    if row.commit_result:
        return {**row.commit_result, "idempotent_replay": True}
    return {
        "id": str(row.id),
        "connection_no": row.connection_no,
        "manifest": {},
        "home": connection_home(row),
        "warnings": [],
        "unavailable": [
            {
                "field": "manifest",
                "code": "first_press_answer_not_recorded",
                "br_ref": "CLAUDE.md rule 6",
                "reason": (
                    "this build was committed by an earlier press of the same button "
                    "and that press's own answer was not recorded. The build is real "
                    "and nothing has been created twice; open it to see what it holds"
                ),
            }
        ],
        "br_ref": "BR-MET-112",
        "idempotent_replay": True,
    }


def _claim_the_commit_key(connection_id: Any, commit_key: str | None) -> None:
    """**Stamp the key ON THE ROW, INSIDE the build's own transaction.**

    ⚠ **THIS IS THE HALF THAT SURVIVES A RACE, AND IT IS WHY IT IS HERE RATHER
    THAN AFTER THE COMMIT.** `_the_first_press_answer` above is the ordinary
    path — two presses a second apart, the second finds the first. Two presses
    in the same millisecond both read nothing and both build; what stops the
    second is `uq_connections_commit_key`, `UNIQUE (tenant_id, commit_key)`
    WHERE `commit_key IS NOT NULL`, and it can only stop it if the key is
    written inside the transaction that writes the build. A key stamped after
    the commit would leave the race entirely unprotected while looking
    identical in every test that presses twice in sequence (law 7: ask what
    would make this check pass wrongly).

    A no-op without a key, so every tokenless caller is untouched.
    """
    if not commit_key:
        return
    Connection.objects.filter(tenant_id=_tenant_id(), pk=connection_id).update(
        commit_key=commit_key
    )


def _remember_the_commit(
    connection_id: Any, commit_key: str | None, answer: dict[str, Any]
) -> dict[str, Any]:
    """Store press one's answer for press two, and hand it back unchanged.

    One `UPDATE` of `commit_result`. It is separate from `_claim_the_commit_key`
    because the answer is assembled from `built` AFTER the transaction has
    closed — the refusal translators sit outside it on purpose (hard-won law
    14) and moving the assembly in would move them with it.

    ⚠ **THE WINDOW BETWEEN THE TWO IS ONE STATEMENT WIDE AND IS NOT PAPERED
    OVER**: if the process dies in it, the build exists, its key is claimed, and
    `_the_first_press_answer` says the manifest was not recorded. Nothing is
    ever built twice, which is the guarantee rule 6 asks for.
    """
    if not commit_key:
        answer = {**answer, "unavailable": [*(answer.get("unavailable") or []), COMMIT_TOKEN_ABSENT]}
        return answer
    Connection.objects.filter(tenant_id=_tenant_id(), pk=connection_id).update(
        commit_result=answer
    )
    return answer


def _finish_the_draft(
    actor: Any,
    data: dict[str, Any],
    connection_id: Any,
    block: dict[str, Any],
    named: Any,
) -> tuple[Any, dict[str, Any], bool, list[dict[str, Any]]]:
    """The address — attached or created — and the commit, in ONE transaction.

    Split out of `_commit_raised_draft` so the two refusal translators sit
    OUTSIDE the `atomic()` block rather than inside it (hard-won law 14). It is
    a SHAPE and not a second decision: every rule here belongs to
    `create_premises`, `create_connection` or `commit_connection`.
    """
    tenant_id = _tenant_id()
    warnings: list[dict[str, Any]] = []
    premises_created = False
    with transaction.atomic():
        draft = (
            Connection.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=connection_id)
            .first()
        )
        if draft is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if draft.premises_id is None:
            if named:
                premises = metering_models.Premises.objects.filter(
                    tenant_id=tenant_id, pk=named
                ).first()
                if premises is None:
                    raise errors.deny_as_not_found("BR-TEN-003")
                draft.premises = premises
            else:
                # The SAME door S16 and `create_connection` use — the premise
                # number, the audit row, the area cascade and the owner's
                # master account all come from it and none of it is restated.
                # ⚠ **THROUGH THE WRAPPER, SO A REFUSAL NAMES STEP 2**
                # (`DEF-MET-7690`). This is the second of the two doors and it
                # must not diverge from the first — a build raised from an
                # approval hits this one.
                made = _premises_made_for_the_wizard(
                    actor, _premises_block_in_the_doors_language(block)
                )
                draft.premises_id = made["id"]
                premises_created = True
                warnings.extend(made.get("warnings") or [])
            draft.save(update_fields=["premises", "updated_at"])
        elif named and str(named) != str(draft.premises_id):
            metering_services._refuse_fields(
                [
                    metering_services._field_error(
                        "premises",
                        errors.VAL_FORMAT,
                        "metering.connection.premises_named_twice",
                    )
                ]
            )
        built = commit_connection(actor, str(draft.id), data)
        # `BR-SHL-048 (d)` — the draft that was holding this clerk's typing has
        # nothing left to hold, and a leftover row is a second row for one build.
        _release_the_draft_that_held_this(actor, data)
    return draft, built, premises_created, warnings


# ════════════════════════════════════════════════════════════════════════════
# `DEF-MET-6110` / `DEF-MET-6111` — A RULE REACHES THE CLERK ON THE STEP THEY
# CHOSE IT, NEVER AS A 500
# ════════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-09-21, verbatim: *"this fix is correct - you ahve to show the
# error at step you mentioned"*.
#
# **THE FAULT WAS ONE FAULT WEARING TWO FACES**, both found in a browser on the
# acceptance walk:
#
#   * step 6, pick `TAP` — **a code the product's own picker offered** — and the
#     last press answered *"Something went wrong on our side."* `TAP` carries no
#     flat amount, `fee_bill.charge_code_line` raises `BillingRuleError`, and
#     nothing on this path caught it. **Thirty-three clerk acts gone.**
#   * pick an address already holding `Apt 101–103`, add units labelled
#     `Apt 101–103`, and the same 500 arrived from
#     `uq_units_tenant_premises_label`. **The database was right to refuse and
#     nothing had asked first.**
#
# **A business rule that reaches a clerk as a 500 tells them the product is
# broken when they have simply chosen something the product refuses.** They
# cannot act on it, and the work is gone.
#
# ── WHAT THIS IS NOT, AND THE DISTINCTION IS THE WHOLE GUARD ────────────────
# ⛔ **NOTHING HERE IS A CATCH-ALL.** A `try/except Exception` that answered
# every failure with a polite sentence would hide a genuine crash behind a
# refusal a clerk cannot escape, which is worse than the defect. So:
#
#   * a refusal is recognised **by CLASS** (billing's own rule-error tree) or
#     **by the CONSTRAINT NAME** the driver reports — never by reading prose;
#   * anything unrecognised is **re-raised untouched**, keeps its traceback and
#     still answers `SYS-INTERNAL` with a trace id;
#   * `BR-MET-112` is untouched: the refusal leaves the `transaction.atomic()`
#     block on its way out, so the address, the units and the build roll back
#     together. **A half-built 26-unit development is still worse than none.**
#
# ── AND WHY THE SERVER NAMES THE STEP ───────────────────────────────────────
# The browser knows which control the clerk touched; only the SERVER knows
# which rule refused. So the refusal carries the step's **stable id** — never
# its number, which moves the day a step is inserted (it already moved once,
# when owner and scope merged into one screen) — and the wizard resolves the id
# to a position out of its own declared list.
STEP_OF_THE_UNITS = "units"
STEP_OF_THE_CHARGES = "charges"
STEP_OF_THE_PREMISE = "premise"

#: The one unique constraint on this path that a CLERK chooses the value of.
#:
#: ⚠ **THE OTHER FOUR ARE DELIBERATELY NOT LISTED.** `uq_premises_tenant_premise_no`,
#: `uq_units_tenant_unit_no`, `ux_accounts_no` and `uq_assets_tenant_no` are all
#: numbers this SERVER allocates, so a collision on one is a numbering fault and
#: not a clerk's choice — it must stay loud, with a trace id, exactly as it is
#: today. Adding one of them here would convert a real defect into a sentence
#: telling a clerk to change something they never typed.
UNIT_LABEL_CONSTRAINT = "uq_units_tenant_premises_label"


def _payment_refused_on_the_charges_step(refusal: BaseException) -> errors.BizError:
    """A payments refusal of step 4's payment, as the step-4 answer.

    ⚠ **ONE REFUSAL IS NOT A REFUSAL: "LOOKS LIKE A DUPLICATE" (`DEF-PAY-9263`,
    `BR-PAY-1199`, PO 2026-10-03).** A card or ACH payment matching one already
    on the account (same amount, reference and day) is a WARNING the clerk may
    override — *"let the clerk confirm"*. It is answered as payments' own
    `Record payment` door answers it (409 `BIZ-IDEMPOTENT`,
    `payments.record.possible_duplicate`, the earlier payment in `params`) plus
    the step, so the wizard can show the earlier payment and offer *Record
    anyway*, which resends the commit with `payment_duplicate_confirmed: true`.
    Recognised by the `earlier` facts payments attaches, so metering imports
    nothing of payments' at module scope.
    """
    earlier = getattr(refusal, "earlier", None)
    if isinstance(earlier, dict):
        return errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1199",
            message_key="payments.record.possible_duplicate",
            params={**earlier, "possible_duplicate": True, "step": STEP_OF_THE_CHARGES},
        )
    return _refused_on_the_step_that_chose_it(
        step=STEP_OF_THE_CHARGES,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-022",
        message_key="metering.connection_payment_refused",
        params={"detail": str(refusal)},
    )


def _refused_on_the_step_that_chose_it(
    *, step: str, br_ref: str, message_key: str, params: dict[str, Any] | None = None
) -> errors.BizError:
    """One refusal, carrying the step that owns the field the clerk chose.

    ⚠ **`step` RIDES IN `params` AND IS A STABLE CODE, NOT PROSE.**
    `BillingRuleError`'s own docstring draws that line — *"`params` MUST NOT
    CARRY PROSE. It carries figures and stable codes"* — and a step id is
    exactly a stable code. The SENTENCE is composed in the eleven catalogues
    from `message_key`, as `BR-SHL-020 r2` requires, and nothing English
    crosses the wire.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key=message_key,
        params={**(params or {}), "step": step},
    )


def _premises_made_for_the_wizard(actor: Any, block: dict[str, Any]) -> dict[str, Any]:
    """`create_premises`, with anything it refuses named to **STEP 2**.

    **`DEF-MET-7690`.** `_refused_on_the_step_that_chose_it` above was built for
    `DEF-MET-6110` and covers the two refusals that reach this path as a RULE
    error. It does not cover a `ValidationError`, and the address block raises
    several — the loudest being an unknown **read route**, which
    `metering.services._resolve_create_route` refuses BY NAME so that a create
    cannot answer `201` for a route it did not honour.

    That refusal is correct, its sentence is in the eleven catalogues and it
    names `route` in `field_errors`. **What it never carried is the STEP**, so
    the wizard — which routes on `params["step"]` and nothing else — dropped it
    onto the ordinary failure card at step 8. Measured 2026-09-28: `RT-07` typed
    into *Read route* on step 2, thirty-odd acts later the last press answered
    *"Failed. The connection was not created. That route is not on file."* with
    Retry, Download error report and Cancel, on step 8, naming neither the field
    nor the step. That is PO ruling 2026-09-21 — *"you ahve to show the error at
    step you mentioned"* — unmet on the one refusal that predates it.

    ⚠ **THE STEP IS THE CALL SITE'S, NOT A GUESS FROM THE FIELD NAME.**
    Everything `create_premises` is handed here came out of
    `_premises_block_in_the_doors_language`, whose whole payload is typed on
    step 2 and nowhere else — so wrapping THE CALL says *step 2* about exactly
    the right set, and a list of field names to match against would be a second
    copy of `PREMISES_BLOCK_FIELDS` that drifts the day a field is added.

    ⚠ **THE ENVELOPE IS OTHERWISE UNTOUCHED.** Same code, same `message_key`,
    same `field_errors`, same `br_ref`, same 422 — `step` is added to `params`
    and that is all. `BR-SHL-020 r2` is unbroken: a step id is a stable code and
    the sentence is still composed in the catalogues.

    ⚠ **NOT A CATCH-ALL, AND NOT MOVED OUTSIDE THE TRANSACTION.** Only
    `ValidationError` is caught; a `BizError`, an `IntegrityError` or a genuine
    crash passes straight through to the handlers that already own it. Nothing
    here issues a query and nothing continues after the catch — the refusal is
    re-raised at once, so the enclosing `atomic()` unwinds exactly as before and
    CLAUDE.md hard-won law 14's aborted-transaction trap is not reachable from
    here. `BR-MET-112`'s both-or-neither is unchanged.
    """
    try:
        return metering_services.create_premises(
            actor, block, custom_fields_screen=NEW_CONNECTION_PREMISE_SCREEN
        )
    except errors.ValidationError as refusal:
        raise errors.ValidationError(
            refusal.code,
            message_key=refusal.message_key,
            params={**refusal.params, "step": STEP_OF_THE_PREMISE},
            field_errors=refusal.field_errors,
            br_ref=refusal.br_ref,
        ) from refusal


def _refuse_a_unit_label_already_at_this_address(connection: Any, specs: Any) -> None:
    """**`DEF-MET-6111` — ASK BEFORE THE WRITE, and name the label.**

    A unit's label is unique within its address (`uq_units_tenant_premises_label`),
    which is right: two `Apt 101`s at one building are two names for one place.
    A clerk adding units to an address already on file cannot see what is there,
    so the collision was discovered by the database, after eight steps, as a 500.

    **TWO SOURCES OF THE SAME CLASH, AND BOTH ARE THE CLERK'S TO FIX:** a label
    the ADDRESS already holds, and a label this payload holds TWICE (a range
    typed over a common area, say). The second one never reached the database
    constraint at all in the old code either — it simply failed on the second
    `create` — so both are answered here, in the same words.

    ⚠ **THIS IS A PRE-CHECK AND IT IS NOT THE GUARANTEE.** Two clerks committing
    at the same moment both read an address with no `Apt 101` on it; the loser's
    `INSERT` is still refused by the constraint. That race is caught in
    `commit_new_connect`, which translates the constraint to this same key —
    **the database stays the authority and this is the sentence that makes it
    legible.**
    """
    wanted: list[str] = [
        str((spec or {}).get("label") or "").strip() or "Unit" for spec in (specs or [])
    ]
    if not wanted:
        return
    seen: set[str] = set()
    twice: list[str] = []
    for label in wanted:
        if label in seen:
            twice.append(label)
        seen.add(label)
    taken = set(
        metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(),
            premises_id=connection.premises_id,
            label__in=wanted,
        ).values_list("label", flat=True)
    )
    if not [label for label in wanted if label in taken] and not twice:
        return
    # ⚠ **NO LABEL TRAVELS IN `params`, AND THAT IS NOT AN OMISSION.** Step 3
    # names every clashing label ON THE SCREEN, beside the row it belongs to,
    # from the same read — which is where a list of them is legible and a
    # refusal strip is not. The strip says what happened and what to do; the
    # table says which one. It also keeps ONE sentence for this rule: the race
    # below cannot know WHICH label lost, and two near-identical catalogue
    # entries would be a distinction no clerk can use.
    raise _refused_on_the_step_that_chose_it(
        step=STEP_OF_THE_UNITS,
        br_ref="BR-MET-112",
        message_key="metering.connection_unit_label_taken",
    )


def _constraint_name_of(clash: BaseException) -> str:
    """The constraint a database refusal names, or `""`.

    ⚠ **IT TAKES A WALK, NOT ONE HOP — CLAUDE.md hard-won law 14's own clause.**
    `exc.__cause__` on a caught Django `IntegrityError` is *another* Django
    exception; the driver's object, the one carrying `diag`, is two or three
    hops down. A first draft that read one hop finds nothing and **looks
    handled**, which is the check-that-cannot-fail shape.

    The text fallback is deliberate and is not prose-reading: a constraint NAME
    is a stable identifier this repo declares in its own migration, and it is
    compared against that literal. It exists because a driver that reports no
    `diag` would otherwise silently stop translating anything.
    """
    hop: BaseException | None = clash
    for _ in range(6):
        if hop is None:
            break
        diag = getattr(hop, "diag", None)
        named = getattr(diag, "constraint_name", None)
        if named:
            return str(named)
        hop = hop.__cause__
    text = str(clash)
    return UNIT_LABEL_CONSTRAINT if UNIT_LABEL_CONSTRAINT in text else ""


def _refuse_if_two_units_share_a_label(clash: IntegrityError) -> None:
    """Translate the ONE clerk-chosen constraint, and **return for every other**.

    Returning is what keeps this honest: the caller's next statement is a bare
    `raise`, so an unrecognised integrity error leaves with its own traceback
    and still answers `SYS-INTERNAL`. A numbering collision is a defect and must
    go on looking like one.
    """
    if _constraint_name_of(clash) != UNIT_LABEL_CONSTRAINT:
        return
    raise _refused_on_the_step_that_chose_it(
        step=STEP_OF_THE_UNITS,
        br_ref="BR-MET-112",
        message_key="metering.connection_unit_label_taken",
    ) from clash


def commit_new_connect(actor: Any, plan: Any) -> dict[str, Any]:
    """**`POST /connections/commit` — step 8's ONE press, and the whole build.**

    ⚠ **THIS DOOR DID NOT EXIST UNTIL 2026-09-16 AND THE BUTTON HAS BEEN
    PRESSING IT SINCE THE WIZARD SHIPPED (`DEF-MET-5441`).** `POST
    /api/v1/connections/commit` answered **404** on the running server while
    `POST /connections` and `POST /connections/<uuid>/commit` each answered 401
    — real doors behind a login. So **no build made through that screen had ever
    reached the database**, through eight finished steps, and both halves stayed
    green the whole time: the front-end suite mocks this module and the backend
    suite calls `commit_connection` directly, so nothing ever exercised the wire.
    The gap was written into two docstrings and never onto the defect register,
    which is hard-won law 1 — *a comment claiming a gap is not a plan*.

    ── WHY ONE DOOR AND NOT TWO ROUND TRIPS ──────────────────────────────────
    The browser could have called `POST /connections` for an id and then posted
    to the id-bearing commit. **It must not**, and the reason is `BR-MET-112`:
    *nothing is written until the last button*. Two calls write a premises, a
    premise number, a connection and a `CON-` number on the FIRST one, so a
    refusal on the second — a parcel already taken, a template a clerk retired
    an hour ago, a unit with no plan — leaves a Draft connection and possibly a
    brand-new address standing with no units, no meters and no plan behind
    them. **No screen in this product can find that wreckage:** the wizard's
    park-and-resume context is empty by construction, *"a new connect has no
    premise id, no unit id and no account id until it commits"*.

    ── AND IT INTRODUCES NO NEW WRITER ───────────────────────────────────────
    `create_connection` has taken a whole `premises` block and created the
    address since `BR-MET-1024` (2026-09-01), so this function calls two
    services that already exist, in order, and computes nothing. Every rule
    stays where it was: `create_premises` owns the address's validation, its
    number, its audit row and its area cascade; `commit_connection` owns the
    five-module commit and its manifest.

    ── BOTH OR NEITHER, AND IT COSTS NO NEW MACHINERY ────────────────────────
    One `transaction.atomic()` wraps both calls. Each of them opens its own,
    which NESTS as a savepoint rather than starting a second transaction, so a
    refusal anywhere — including inside `create_premises` — rolls the address
    back with the build. A half-built 26-unit development is worse than none.

    ⚠ **NOTHING ON THIS PATH SWALLOWS A DATABASE ERROR AND CARRIES ON**, which
    is CLAUDE.md hard-won law 14's trap: on PostgreSQL the transaction is
    already poisoned by the refused statement and the work is lost at COMMIT
    anyway, while this repo's SQLite suite — which has no aborted-transaction
    state — would pass the broken version green.

    ⚠ **AMENDED 2026-09-21 (`DEF-MET-6110`/`DEF-MET-6111`): THIS PARAGRAPH READ
    *"NO `try/except` ANYWHERE ON THIS PATH"* AND THE COST WAS A 500.** Two
    handlers now sit OUTSIDE the `atomic()` block — so the rollback has already
    happened and neither runs a query — and each **TRANSLATES one recognised
    refusal and re-raises everything else untouched**. A rule the clerk broke
    now answers on the step they broke it on; a genuine crash still answers
    `SYS-INTERNAL` with a trace id. The sentence above is the rule; *never
    catch* was a shorthand for it that was wrong in one direction.

    ── WHAT THIS DOOR ANSWERS THAT `commit_connection` CANNOT ────────────────
    `commit_connection` reports `premises: None` with a stated absence, and
    `DEF-2961`'s reasoning is why: *"the address is created at step 1–2 by
    `create_connection` … the door that did it is the door that can say so."*
    **This door is that door**, so it fills the count in — `1` when it created
    the address, `0` when the clerk named one already on file — and replaces the
    absence with the plain statement of which of the two happened.

    ⚠ **`scope` AND `units_prefix` ARE ACCEPTED AND READ BY NOTHING, AND THAT
    IS SAID OUT LOUD RATHER THAN LEFT TO BE DISCOVERED.** `connections` has no
    column for either (`DEF-CUS-5435`). Inventing one would be this function
    choosing an answer nobody asked for; dropping them silently is what
    `DEF-MET-4715` was. So they ride on `unavailable`, where the screen can read
    the absence in words.
    """
    data = metering_services._payload_dict(plan)
    # ── `DEF-CUS-8021` · CLAUDE.md HARD RULE 6, BEFORE ANYTHING IS WRITTEN ───
    # On 2026-09-29 the identical payload posted twice with the parcel box
    # EMPTY answered 200 both times — `CON-26-0130` and `CON-26-0131`, two
    # accounts, two customers, two properties at one address and **two
    # payments of $250.00, each posting its own balanced ledger pair.** With a
    # parcel typed the second press was refused `409
    # premises.external_ref_taken`, which is a uniqueness constraint on a
    # different column: it refuses by accident of a different rule, only on
    # the minority of builds that type a parcel, and it answers an ERROR where
    # rule 6 asks for the FIRST RESULT. **That is why the first walk of this
    # check passed**, and why the test runs with no parcel number.
    #
    # ⚠ **FIRST, BEFORE THE PAYLOAD IS EVEN UNPACKED.** A replay must reach no
    # writer at all, and the cheapest way to be sure of that is for the answer
    # to leave before anything else runs.
    commit_key = _the_commit_key(data)
    replay = _the_first_press_answer(commit_key)
    if replay is not None:
        return replay
    block = dict(data.get("premises") or {})
    named = block.get("id")
    # ── `DEF-CUS-6109` · FINISHING A DRAFT THAT WAS RAISED FOR THIS CLERK ────
    # An approved application raises the build BEFORE the wizard opens (PO
    # ruling 2026-09-21), so on that path there is already a row and this door
    # must not create a second one. Everything after the address is identical:
    # one `commit_connection`, one transaction, one manifest.
    resuming = data.get("connection_id")
    if resuming:
        return _commit_raised_draft(actor, data, resuming, block, named, commit_key)
    draft_payload: dict[str, Any] = {
        "mode": data.get("mode") or MODE_OUR_CREW,
        "target_activation": data.get("target_activation"),
        "service_request_id": data.get("service_request_id"),
        # ── CR-126-BRC07 · STEP 1's THREE ANSWERS, FORWARDED TO THE ROW ─────
        # ⚠ **`owner_type` IS `owner.kind` AND IS NOT `owner.party_kind`.**
        # `OWNER_KINDS` is the CLASSIFICATION the blueprint draws as *Owner
        # type* — builder or developer · property owner · landlord · occupier —
        # and `party_kind` is `person`/`company`, which is the accounts door's
        # question and travels to `customers` separately. Reading one as the
        # other is `DEF-MET-5438`, which is why the wizard asks both by name.
        "owner_type": ((data.get("owner") or {}) or {}).get("kind") or None,
        "units_prefix": data.get("units_prefix"),
        "scope": data.get("scope"),
    }
    if named:
        # The address is already on file. `create_connection`'s *named twice*
        # refusal is untouched, because only ONE of these two keys is ever set.
        draft_payload["premises_id"] = named
    else:
        draft_payload["premises"] = _premises_block_in_the_doors_language(block)

    # ⚠ **THE `try` IS OUTSIDE THE `atomic()` BLOCK ON PURPOSE, AND THAT IS
    # CLAUDE.md hard-won law 14.** On PostgreSQL a refused statement poisons the
    # whole transaction, so catching INSIDE and carrying on loses the work at
    # COMMIT anyway — and this repo's SQLite suite, which has no aborted state,
    # would pass the broken version green. By the time either handler below
    # runs, the block has already exited and **rolled everything back**, which
    # is `BR-MET-112`'s both-or-neither unchanged. Neither handler issues a
    # query; each raises.
    #
    # ⚠ **THE DOCSTRING ABOVE SAID *"NO `try/except` ANYWHERE ON THIS PATH,
    # DELIBERATELY"* UNTIL 2026-09-21 AND THE REASON IT GAVE IS STILL RIGHT.**
    # What it forbade is a `try/except` that **swallows** a database error and
    # continues; these two TRANSLATE one and re-raise. The paragraph is amended
    # in place rather than left contradicting the code.
    refusal_class = seams.quote_refusal_class()
    payment_refusal = seams.payment_refusal_class()
    try:
        with transaction.atomic():
            draft = create_connection(actor, draft_payload)
            # `DEF-CUS-8021` — INSIDE the transaction, so `uq_connections_commit_key`
            # catches two presses that raced past the lookup above. See the
            # helper's own docstring for why after the commit would not do.
            _claim_the_commit_key(draft["id"], commit_key)
            built = commit_connection(actor, draft["id"], data)
            # `BR-SHL-048 (d)` — a New Connect started from SCRATCH parks too,
            # and finishing one leaves the same orphan row behind. The build is
            # brand new on this path and the draft is still spent.
            _release_the_draft_that_held_this(actor, data)
    except IntegrityError as clash:
        # `DEF-CUS-8021`'s RACE — two presses in the same millisecond, both
        # past the lookup, the second refused by `uq_connections_commit_key`.
        # The transaction has already rolled back, so this query is safe (law
        # 14) and the second press's build is gone. Answer press one's result,
        # which is what rule 6 asks for; raising here would tell a clerk their
        # build failed when it succeeded.
        raced = _the_first_press_answer(commit_key)
        if raced is not None:
            return raced
        # `DEF-MET-6111`'s RACE, not its ordinary case: two clerks adding the
        # same unit number to one address in the same second. The ordinary case
        # is asked and answered before the write, in `commit_connection`.
        _refuse_if_two_units_share_a_label(clash)
        raise  # every other constraint is a defect and stays loud
    except refusal_class as refusal:
        # `DEF-MET-6110`. **Layer 1 cannot close this and that is why layer 2
        # exists:** step 6 offers only codes a build can price TODAY, and a
        # tenant editing that code on Settings this afternoon makes the picker's
        # answer stale — `rating.selectors.charge_by_code` says so in its own
        # words, *"the amount is a SEED the tenant edits, never a constant"*.
        raise _refused_on_the_step_that_chose_it(
            step=STEP_OF_THE_CHARGES,
            br_ref=getattr(refusal, "br_ref", None) or "BR-BIL-020",
            message_key="metering.connection_charge_refused",
            # The rule's OWN sentence, for the `BR-AUD-018` attempt row and the
            # server log. `BR-SHL-020 r2` keeps `detail` off the screen; support
            # still reads which of billing's checks refused.
            params={"detail": str(refusal)},
        ) from refusal
    except payment_refusal as refusal:
        # ⚠ **`DEF-MET-6110`'s SHAPE, ONE MODULE OVER — ADDED WITH
        # `BR-MET-1187` RATHER THAN AFTER THE FIRST 500.** Payments refuses a
        # tender this tenant does not run, a deactivated method and a till that
        # is closed by RAISING `PaymentRuleError`, which is right for payments
        # and is deliberately NOT a catalogue exception. Left uncaught, a clerk
        # who typed `cheque` where this utility spells it `check` would press
        # *Create connection* after thirty-three acts and read *"Something went
        # wrong on our side."* Translated here, they read which step to go back
        # to.
        #
        # **OUTSIDE THE `atomic()` BLOCK, like the handlers above** (law 14):
        # by the time this runs the block has exited and rolled everything
        # back, so nothing here issues a query and `BR-MET-112`'s
        # both-or-neither is unchanged. It TRANSLATES one recognised refusal
        # and re-raises; it does not swallow a database error and carry on.
        raise _payment_refused_on_the_charges_step(refusal) from refusal

    manifest = dict(built.get("manifest") or {})
    manifest["premises"] = 1 if draft.get("premises_created") else 0
    absences = [
        absence
        for absence in (built.get("unavailable") or [])
        # `DEF-2961`'s absence is retired ON THIS PATH ONLY. Its own words were
        # *"the door that did it is the door that can say so"*, and here that
        # door is this one; `commit_connection` called on its own still answers
        # `None`, which is still the truth there.
        if absence.get("field") != "premises"
    ]
    # ⚠ **THE `scope` ABSENCE IS RETIRED, NOT REWORDED (`CR-126-BRC07`).** It
    # read: *"Step 1's scope and unit prefix arrive on this payload and nothing
    # reads them: connections has no column for either."* `metering/0058` gives
    # `scope`, `units_prefix` and `owner_type` columns and `create_connection`
    # writes all three from `draft_payload` above, so the sentence stopped being
    # true and is DELETED rather than softened — **a stated absence that
    # outlives its cause is a lie the product tells about itself** (hard-won law
    # 1, and `_post_connection_quote`'s own docstring makes the same move for
    # the same reason).
    # `DEF-CUS-8021` — press one's answer is STORED for press two, and handed
    # back unchanged. Without a token it is handed back with the absence that
    # says so, and nothing is stored.
    return _remember_the_commit(
        built["id"],
        commit_key,
        {
            **built,
            "manifest": manifest,
            # WHICH of the two paths the address took, reported by the door that
            # took it (`BR-MET-1024`) — the same fact `create_connection` puts on
            # its own response, carried out to the screen that pressed one button.
            "premises_id": draft.get("premises_id"),
            "premises_created": bool(draft.get("premises_created")),
            "warnings": draft.get("warnings") or [],
            "unavailable": absences,
        },
    )


def _owner_block_in_the_doors_language(data: dict[str, Any]) -> dict[str, Any]:
    """**`DEF-MET-5093` — the wizard's owner, in the account door's vocabulary.**

    New Connect's step 1 collects `{name, kind, sub_category, email, phone}` and
    `create_master_account` reads `contact` and `customer`. **It read NEITHER,
    so the owner's NAME never reached the account either — not only the
    identifier.** Proved against a real PostgreSQL on `CON-26-0117`: the
    wizard's own payload came back `BIZ-COMPLETENESS
    customers.account.identity_kind_required`, which is to say a build
    committed with an owner on it was refused outright.

    **THE TRANSLATION BELONGS HERE, IN THE MODULE THAT OWNS THE DOOR.** Two
    vocabularies meet at this call and one of them has to give way; doing it in
    the browser would make every other caller of this function speak the
    wizard's words, and doing it in `customers` would teach the accounts module
    what a *builder or developer* is.

    ⛔ **`kind` IS NOT `customer.kind`, AND THE ROW THAT PRESCRIBED THAT MAPPING
    WAS WRONG (`DEF-MET-5438`).** `OWNER_KINDS` is a CLASSIFICATION — builder or
    developer, property owner, landlord, occupier — and `customer.kind` is
    `person` or `company`. **All FOUR classifications are refused by
    `_validate_customer_kind`**, so mapping one onto the other would have traded
    a missing-kind refusal for an unknown-lookup one. Deriving *company* from
    *builder or developer* would be worse: `BR-MET-112` is that a wizard does
    not mint a money object because a field was filled in, and
    `identity_match.normalise_kind` already refuses to pick a kind for a sole
    trader for precisely this reason. **So the classification is mapped nowhere
    and the party kind is asked for BY NAME**, as `party_kind`.

    ⚠ **THE IDENTITY BLOCK TRAVELS ONLY WHEN A PARTY KIND IS STATED**, which is
    `BR-CUS-1022` rather than caution: evidence presented against an unstated
    kind *cannot be assessed at all*, so sending it would turn one refusal that
    names the missing dropdown into a field error about the evidence. One
    missing thing, one sentence.

    ⚠ **THE OWNER'S PHONE BECOMES AN IDENTITY CLAIM, AND IT IS A JUDGMENT
    (decision log 2026-09-16).** `BR-CUS-1023` accepts a phone as enough to MINT
    a number for a PERSON and never for a COMPANY, and step 1 has collected one
    all along — so a landlord who gives a phone opens an account and a developer
    still has to give its Tax ID. It is the owner's own phone, not a borrowed
    field. It does NOT let anyone REUSE a number on file: `BR-CUS-1024`'s
    matching test is a name plus a government identifier, and this changes
    nothing about that.

    ⚠ **A TRANSLATION, NEVER AN OVERRIDE.** A caller that already assembled
    `contact` or `customer` properly — the seeder, a test, any door that speaks
    the accounts vocabulary — keeps what it wrote. Overwriting those would
    quietly demote every one of them to whatever the wizard happens to collect.
    """
    owner_name = str(data.get("name") or "").strip()
    if not owner_name and "party_kind" not in data and "identity" not in data:
        # Nothing of the wizard's shape is present, so there is nothing to
        # translate and the payload is already somebody else's.
        return data
    out = dict(data)
    email = str(data.get("email") or "").strip() or None
    phone = str(data.get("phone") or "").strip() or None

    if not out.get("contact") and owner_name:
        out["contact"] = {"full_name": owner_name, "email": email, "phone": phone}
    # ⊕ lane CF-1 (2026-10-18) — the shared customer form's *Contact by* and
    # *Government ID* (last four), asked on Step 1 exactly as Move-in asks them
    # (drawing set `customer-forms-2026-10-18`, image 06). Both are the accounts
    # door's own CONTACT words (`customers.CONTACT_FIELDS`), so they ride the
    # contact block; a caller that assembled its own contact keeps what it wrote.
    for contact_key in ("contact_by", "gov_id_last4"):
        given = str(out.pop(contact_key, None) or "").strip()
        contact = out.get("contact")
        if given and isinstance(contact, dict) and not contact.get(contact_key):
            out["contact"] = {**contact, contact_key: given}

    # ⊕ `CR-164-BRC10` wave 2 — Step 1's own customer fields (slot
    # `NEW_CONNECTION_OWNER`). They belong to a customer this build CREATES, so
    # they ride the customer block the wizard's words become; over a customer
    # the clerk picked (`customer.customer_id`) nothing is rewritten.
    owner_custom = out.pop("customer_custom_data", None)
    if not out.get("customer"):
        party_kind = str(data.get("party_kind") or "").strip() or None
        customer: dict[str, Any] = {"display_name": owner_name or None, "kind": party_kind}
        if isinstance(owner_custom, dict):
            customer["custom_data"] = owner_custom
        if party_kind:
            identity = dict(data.get("identity") or {})
            if phone and not identity.get("phone"):
                identity["phone"] = phone
            if identity:
                customer["identity"] = identity
        out["customer"] = customer
    # The wizard's own words are not the door's, and an unknown key inside
    # `customer` is refused there by name. They are dropped from what travels
    # rather than passed along to be rejected.
    for wizard_key in ("name", "kind", "sub_category", "email", "phone", "party_kind", "identity"):
        out.pop(wizard_key, None)
    return out


def create_owner_account(actor: Any, connection_id: Any, payload: Any = None) -> dict[str, Any]:
    """**BR-MET-116 — the owner's build account is a MASTER account.**

    PO 2026-08-25, closing OQ-373: *"it will be master acocunt ; unit will be all
    vacant right now, if there is common area you can add that in premises"*.

    ⚠ **THE MECHANISM ALREADY EXISTED AND OQ-373 SHOULD NEVER HAVE BEEN ASKED —
    recorded here because the miss is worth more than the answer (DEF-682).**
    `BR-CUS-068` (PO 2026-08-22) had already made a master account **an ordinary
    `accounts` row with `kind='master'`** that **anchors on the premises' first
    common-area unit** and covers the rest through `service_agreements`; and
    `BR-CUS-083` (PO 2026-08-24) had already ruled that connection charges on a
    multi-unit build go to the developer **through exactly that master account**,
    worked at `CON-26-0117` · 25 units · **$14,390.00**.

    OQ-373 was raised because `accounts.unit_id` was NOT NULL and a build account
    seemed to have no unit. All three options that question offered were wrong
    for the same reason: they solved a problem with a signed answer two modules
    away.

    ⚠ **THE ANSWER THIS PARAGRAPH GAVE IS ITSELF SUPERSEDED, AND IT IS
    `DEF-MET-5081`'s NINTH SURFACE (amended 2026-09-16).** It read: *"**It does
    have one** — the common area"*. **Both halves of that are now false**,
    checked against the running PostgreSQL rather than inferred:
    `information_schema` reports `accounts.unit_id` **`is_nullable = YES`**, and
    `customers.create_master_account` writes **`unit_id=None`** with
    `premises_id` set. `CR-056` W1 / `BR-CUS-1010` moved the anchor to the
    ADDRESS on 2026-09-01 — *"a shared space is something this account is
    CHARGED FOR, not the thing it hangs off"* — and the common areas are reached
    through `service_agreements` like any other covered unit.

    **WHAT THE MONEY DOES: NOTHING.** `1408 Elm` still bills `$41.20` of hallway
    plus `$28.40` of irrigation = **`$69.60`** on one owner document, because
    `covered_unit_ids` answered *anchor + the SA units* and now answers *the SA
    units*, in the same order. The figure is unchanged; only the sentence
    explaining it was wrong.

    ⛔ **AND THE COMMON AREA IS NO LONGER REQUIRED HERE — PO RULING 2026-09-21,
    verbatim: *"common area is option"*.** This paragraph read *"THE COMMON AREA
    IS STILL REQUIRED HERE"* until that day, and the refusal it described
    (`connection_no_common_area_for_master`) was the SECOND of the three
    refusals that made every New Connect build impossible. `BR-MET-116`'s own
    row said a single-unit build *"does NOT get a master account, and that is a
    boundary, not an omission"*; the PO has narrowed it, and the row is amended
    with the date rather than left disagreeing with this code.

    ── WHERE THE ACCOUNT ANCHORS WITH NO COMMON AREA, AND WHY ────────────────
    **It anchors where it already anchored: on the PREMISES.** `CR-056` W1 /
    `BR-CUS-1010` moved the anchor to the address on 2026-09-01 —
    `accounts.unit_id` is nullable and `create_master_account` writes
    `unit_id=None` with `premises_id` set — so *"nothing to hang the row on"*
    stopped being true three weeks before the pincer was measured. **The common
    areas were never the anchor; they were the COVERAGE**, carried by
    `service_agreements`. With none, the account covers nothing and bills
    nothing, which is `CR-056` W4's *no lines, no document* and not a new state.

    ⚠ **MEASURED RATHER THAN CHOSEN, BECAUSE THE RULING ASKED WHICH IS SMALLER.**
    The alternative was to anchor on a DWELLING unit. Against the premises:

      · **Anchor on the premises — 0 new lines in `customers`.**
        `_master_attachment_units` ALREADY returns `[]` for a premises with no
        common area (`CR-056` W1 task 9 deleted that refusal by name), the
        per-unit guard loop ALREADY iterates nothing, and
        `_open_master_service_agreements` ALREADY writes nothing. The whole
        change is the deletion of THIS module's refusal.
      · **Anchor on a dwelling — a new choice, a new rule and a money risk.**
        It needs an answer to *which* dwelling (`Apt 101`? the lowest label?),
        it puts the developer's master account's coverage on a unit a resident's
        own account must later occupy — `BR-CUS-017`'s one-occupying-account
        guard, refusing the first move-in on the building — and
        `covered_unit_ids` would then bill the developer for a DWELLING, which
        `BR-CUS-083` never said.

    **So the premises. The smaller change is also the one that invents nothing**,
    and the money is unmoved: a build with common areas still bills exactly what
    it billed (`1408 Elm`, `$41.20 + $28.40 = $69.60`), and a build without them
    bills `$0.00` on no document because it covers no unit.

    ✅ **WHAT THE RULING ADDS, AND IT IS A REAL FACT ABOUT NEW CONNECT.**
    *"unit will be all vacant right now"* — at confirm **no unit is occupied**, so
    `BR-CUS-017`'s one-occupying-account guard cannot bite and the master path's
    per-unit refusals are all satisfiable. BR-CUS-068 and BR-CUS-083 describe a
    master over a **running** building; this one is created over an **empty** one,
    and nobody had said that was allowed until now.

    ⛔ **THIS PARAGRAPH READ *"A BUILD WITH NO COMMON AREA GETS NO MASTER
    ACCOUNT, BY DESIGN"* UNTIL 2026-09-21 AND IT IS REVERSED BY THE PO.** Their
    words: *"common area is option"*. A house or a duplex **does** get one now,
    covering nothing and billing nothing, because the owner is still the owner
    and `BR-MET-113`'s *"assign account number to owner and tag everything to
    account number"* does not stop applying to a building with one flat in it.

    ⚠ **CROSS-MODULE WRITE, THROUGH THE SEAM AND NEVER AROUND IT** (CLAUDE.md).
    `customers` owns accounts; this resolves `create_master_account` and calls
    it, so BR-CUS-068's whole guard set — the per-unit advisory locks,
    BR-CUS-017's family, BR-MET-040's plan requirement — applies to a build
    account exactly as it applies to a hand-made one. A second creator here would
    be a second, drifting copy of the only thing standing between one meter and
    two bills.
    """
    connection = _connection_or_404(connection_id)
    _refuse_if_cancelled(connection)
    if connection.owner_account_id is not None:
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-113",
            message_key="metering.connection_payer_already_set",
            params={"connection_no": connection.connection_no or ""},
        )

    common_areas = list(
        metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(), premises_id=connection.premises_id, is_common_area=True
        ).order_by("label", "id")
    )
    # ⛔ **`connection_no_common_area_for_master` WAS RAISED HERE AND IS GONE —
    # PO ruling 2026-09-21, *"common area is option"*.** It was the second of
    # the three refusals that took eight builds out of eight in a browser: with
    # a common area the build was refused for the area having no plan, and
    # WITHOUT one it was refused here. Both sides of that pincer are open now.
    #
    # ⚠ **NOTHING REPLACES IT, AND THAT IS THE POINT OF THE MEASUREMENT IN THE
    # DOCSTRING.** An empty `unit_ids` is what `_master_attachment_units`
    # already answers for a premises with nothing shared (`CR-056` W1 task 9),
    # the account hangs off `premises_id` (`BR-CUS-1010`), and the per-unit
    # guard loop simply iterates nothing. There is no anchor to choose.
    #
    # ⚠ **THE MESSAGE KEY IS KEPT IN THE CATALOGUES DELIBERATELY** — it is still
    # the honest sentence for any caller that reaches this state another way,
    # and deleting eleven catalogue rows to save nine bytes is the mass
    # shared-file rewrite law 11 exists to prevent.

    # ⊕ **`DEF-CUS-9228` — A SINGLE-FAMILY BUILD OPENS THE OWNER'S OWN
    # REGULAR ACCOUNT** (PO ruling 2026-10-02, item 1: *"The owner asked for
    # the work, so the owner pays"*). Where the premises TYPE says *Regular
    # account* and the address holds exactly ONE home, the owner's account is
    # a regular one on that home (`customers.create_build_owner_account`);
    # everywhere else this door is the master door it always was, and its
    # refusals (`BR-CUS-1114`) are unchanged — two homes on a single-family
    # type, or an unanswered type with one home, still refuse by name.
    home = _single_family_home(connection)
    door_name = "create_build_owner_account" if home is not None else "create_master_account"
    create_master = seams.resolve("customers", door_name)
    if create_master is None:  # pragma: no cover - the customers lane is landed
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-116",
            message_key="metering.connection_master_path_unavailable",
            params={},
        )

    data = metering_services._payload_dict(payload) if payload is not None else {}
    # ⊕ 🔒 HUMAN-REVIEW-PENDING **`DEF-CUS-9830` (PO ruling 2026-10-06, option (a))
    # — THE CO-APPLICANT IS SAVED AS A CO-OWNER ON THE NEW ACCOUNT, THE WAY
    # MOVE-IN SAVES ONE.** PO, verbatim: *"Save her the way move-in does: a
    # co-owner on the new account, SSN scrambled so staff see only the last four
    # digits … - but make SSN, Email, Phone , DOb optional for co applicant"*.
    # Taken off the owner block HERE, before the door's translation, and checked
    # by move-in's own `move_in_people.pop` (only `full_name` is required; an
    # email, a date of birth is checked for its FORMAT only when given — the
    # ruling's *optional*). Written below through `write_at_complete`, the one
    # writer of `account_co_owners` (🔒 `co_owner_models.py`, unchanged): the
    # SSN and licence encrypted with their blind index, the audit row naming
    # the last four only. A second writer here would be a second, drifting copy
    # of the record the PO signed this morning. Review-ledger row 2026-10-06.
    co_block = None
    if data.get("co_owners") not in (None, []):
        pop_people = seams.resolve("customers", "pop", kind="move_in_people")
        if pop_people is None:  # pragma: no cover - the customers module is landed
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="DEF-CUS-9830",
                message_key="metering.connection_master_path_unavailable",
                params={},
            )
        co_owners = data.pop("co_owners")
        # ⊕ lane CF-1 (2026-10-18) — a build raised from a request: a card the
        # clerk kept gets the request's stored SSN and licence (the screen is
        # only ever shown their last four), exactly as on move-in.
        if connection.service_request_id:
            carry_numbers = seams.resolve("customers", "carry_request_co_owner_numbers")
            if carry_numbers is not None:
                co_owners = carry_numbers(
                    co_owners,
                    str(connection.service_request_id),
                    customer_kind=str(data.get("party_kind") or "") or None,
                )
        co_block = pop_people({"co_owners": co_owners})
    else:
        data.pop("co_owners", None)
    # ⊕ `CR-164-BRC10` wave 4 — step 1's *Owner type*, read BEFORE the door's
    # language drops it: the payload's own answer, else the one on the build.
    # ⊕ 🔒 HUMAN-REVIEW-PENDING **lane CF-1 (2026-10-18) — MOVE-IN'S TAX
    # EXEMPTION AND DISCOUNT CLAIMS, THROUGH MOVE-IN'S OWN CODE.** Drawing set
    # `customer-forms-2026-10-18` image 02 gives New Connect's charges step
    # Move-in's Tax panel (exemption type, certificate number, issued, expiry,
    # certificate file) and its Discounts panel. `move_in_preferences.clean`
    # pops and checks the same three keys a move-in's commit carries
    # (`tax_exemption`, `discount_claims`, `autopay_instrument_id`), and
    # `apply` below writes them for the owner's account inside this
    # transaction — rating's certificate row, the KYC filing, the claim — so
    # nothing here is a second copy of that rule. With a certificate the
    # account's BLANKET exemption columns are dropped (`merge_account_values`,
    # `DEF-CUS-9724`: an exemption removes only the tax on its certificate).
    prefs_clean = seams.resolve("customers", "clean", kind="move_in_preferences")
    prefs_extras = prefs_clean(data) if prefs_clean is not None else None
    if prefs_extras is not None and not prefs_extras.empty:
        merge_prefs = seams.resolve("customers", "merge_account_values", kind="move_in_preferences")
        if merge_prefs is not None:
            data = merge_prefs(data, prefs_extras)
    lives_there = owner_lives_there(data.get("kind") or connection.owner_type)
    data = _owner_block_in_the_doors_language(data)
    # `DEF-CUS-9036` — a build raised from an approved request names it, so the
    # owner's master account carries what the clerk decided ON the request (the
    # customer they linked, the class they picked) and the request's trail says
    # this account fulfilled it. `None` for a build raised directly, which
    # behaves exactly as before (`BR-MET-1178`: provenance, never a dependency).
    request_id = str(connection.service_request_id) if connection.service_request_id else None
    with transaction.atomic():
        account = create_master(
            actor,
            # ⊕ `CR-164-BRC10` wave 2 — the slot the owner's fields were typed on.
            customer_fields_screen=NEW_CONNECTION_OWNER_SCREEN,
            # ⊕ `DEF-CUS-9228` — the one home a regular owner's account holds.
            # ⊕ `CR-164-BRC10` wave 4 — and only if the owner lives there.
            **(
                {"unit_id": str(home.id), "lives_there": lives_there}
                if home is not None
                else {}
            ),
            payload={
                "premises_id": str(connection.premises_id),
                "unit_ids": [str(area.id) for area in common_areas],
                # Left blank for a request's build so the request's own class
                # can fill it; `create_master_account` falls back to the same
                # `commercial` this line always defaulted to.
                # ⊕ `DEF-CUS-9228` — a single-family owner's own account
                # defaults to `residential` where nothing named a class; the
                # wizard always sends step 1's category, so this is reached
                # only by a caller that sent none.
                "account_type": data.get("account_type")
                or (None if request_id else ("residential" if home is not None else "commercial")),
                **({"service_request_id": request_id} if request_id else {}),
                #: BR-CUS-068's path requires a start date. The caller may name
                #: one; otherwise the account opens on the TENANT'S today
                #: (`seams.tenant_today`, the clock every other date in this
                #: product reads) — not the server's. A build account that opened
                #: "yesterday" in a utility's own timezone would date the
                #: connection charge into a period that may already be closed.
                "opened_at": data.get("opened_at") or str(seams.tenant_today()),
                "contact": data.get("contact") or {},
                #: ⚠ **`CR-058` / `BR-CUS-1024` — THE CUSTOMER BLOCK TRAVELS
                #: THROUGH, AND WITHOUT THIS LINE THIS DOOR COULD NOT SATISFY
                #: THE RULE IT IS UNDER.** PO 2026-09-01, said of THIS door:
                #: *"we have to create it if not matching customer ID not
                #: available, - rest is correct"*. The master door matches a
                #: customer first and creates one where no match exists, and it
                #: can only do that with the name, the kind and the identifier
                #: the caller was given. Passed through UNREAD — this module
                #: does not own the vocabulary and must not validate a second
                #: copy of it; `customers._validate_customer_block` refuses an
                #: unknown key there, once, for every door.
                #:
                #: ⛔ **AND WITHOUT AN IDENTIFIER THE MASTER DOOR NOW REFUSES**,
                #: which refuses this action too: *"Without identifier we cannot
                #: create Customer ID or master account ot regular account"*.
                #: That is the ruling reaching a door the question was not about,
                #: and it is stated here rather than discovered at a counter.
                "customer": data.get("customer"),
                #: -- CR-150-BRC09 task 11 - THE BILLING PREFERENCES --------
                #: `step4-charges.png` draws a *Billing preferences* panel --
                #: Autopay, Tax exempt, Certificate number, Exemption expires
                #: -- and all four are `customers.CREATE_FIELDS` entries that
                #: have existed since the accounts module was built.
                #:
                #: ⛔ **AND THAT CITATION WAS THE DEFECT — `DEF-CUS-8020`, THE
                #: REASON THIS BUTTON HAD NEVER CREATED ANYTHING.**
                #: `CREATE_FIELDS` is the ORDINARY account's allow list, and
                #: this door builds a **MASTER** account, whose list is
                #: `customers.MASTER_CREATE_FIELDS`. That set held nine fields
                #: and none of these four, so `_reject_unknown` answered
                #: `customers.account.unknown_field` and **every press of
                #: *Create connection* with an owner on it answered 422** --
                #: *"This app sent a field an account doesn't have. Nothing was
                #: saved."* -- from the day this block landed. The four are now
                #: in `MASTER_CREATE_FIELDS` **and written by
                #: `create_master_account`**; the omission was an oversight
                #: rather than a boundary, and the evidence for that is written
                #: out where the list is, not here.
                #:
                #: ⚠ **THE GENERAL LESSON IS ONE INDIRECTION OUT AND IT IS THIS
                #: REPO'S HARD-WON LAW 1: A COMMENT NAMING THE ALLOW LIST IS NOT
                #: THE ALLOW LIST.** This block cited a set it does not post to,
                #: truthfully about that set, and the citation is what made the
                #: mistake look checked. Cite the door you are actually calling.
                #:
                #: WARNING **THIS DICT IS AN ALLOW LIST BY CONSTRUCTION, WHICH
                #: IS WHY THEY HAD TO BE NAMED HERE.** It is assembled key by
                #: key rather than spread, so a preference on the wizard's
                #: owner block reached this line and went no further -- four
                #: boxes whose values are discarded at the commit, which is
                #: `DEF-CUS-5485`'s shape (*"THE THREE COMMIT FIELDS NOBODY
                #: SENT"*) and hard-won law 2.
                #:
                #: WARNING **OMITTED WHEN THE CALLER DID NOT SEND THEM, NEVER
                #: DEFAULTED HERE.** Every existing caller of this door -- the
                #: seeder, the tests, an approval -- sends no `autopay` key,
                #: and writing `False` for them would be this function
                #: answering a question nobody was asked. The accounts door
                #: applies the column defaults for an absent key.
                **{
                    key: data[key]
                    for key in (
                        "autopay",
                        "tax_exempt",
                        "tax_exempt_ref",
                        "tax_exempt_expires",
                        #: `DEF-CUS-9159` (CR-161-BRC10 W3) — the account
                        #: fields Step 1 renders under *Account details*. They
                        #: were typed, shown and dropped HERE, the fifth key
                        #: of this allow list's own warning above. Passed
                        #: through unread: `create_master_account` checks
                        #: them through tenancy as the `S18` slot.
                        "custom_data",
                        #: `CR-164-BRC10` / `DEF-CUS-9195` — step 1's
                        #: Communication panel, dropped here until now
                        #: (`DEF-CUS-7863`). Cleaned by the accounts door.
                        "preferred_language",
                        "paperless",
                        "sms_reminders",
                        #: ⊕ `DEF-CUS-9822` (N1, PO 2026-10-06) — step 1's
                        #: Sub-category, the utility's own sub-type code, in
                        #: the accounts door's own word (as move-in sends it).
                        #: Resolved and refused by that door
                        #: (`_resolve_account_subtype`).
                        "account_subtype",
                        #: ⊕ `DEF-CUS-10222` (lane CF-1, 2026-10-18) — WHERE
                        #: THE BILL GOES. Step 1 has asked for a mailing
                        #: address since `CR-150-BRC09` and it was dropped
                        #: HERE, the allow list's own warning above once more:
                        #: the owner's account opened with no mailing address
                        #: and every bill went to the building. Passed
                        #: through unread as `[{kind: "mailing", …}]`; both
                        #: doors validate it (`customers._validate_addresses`,
                        #: hard rule 8's named exception).
                        "addresses",
                    )
                    if key in data
                },
            },
        )
        connection.owner_account_id = account["id"]
        connection.save(update_fields=["owner_account", "updated_at"])
        # ⊕ **`DEF-CUS-9828` (N2, PO 2026-10-06) — THE REQUEST'S DOCUMENTS
        # REACH THE OWNER'S ACCOUNT, LINKED AND NOT COPIED**, exactly as a
        # move-in carries a request's papers (`carry_request_documents`,
        # BR-CUS-080/073: the account's card points at the SAME stored file,
        # one row per file, audited). Step 1 lists them as already brought in.
        # A build raised directly names no request and carries nothing.
        documents_carried = 0
        if request_id:
            carry = seams.resolve("customers", "carry_request_documents", kind="move_in_people")
            if carry is not None:
                documents_carried = carry(
                    actor,
                    account=_account_or_404(account["id"]),
                    service_request_id=request_id,
                )
        # ⊕ 🔒 `DEF-CUS-9830` — the co-applicant, written in this transaction so
        # a refusal rolls the account back with it (move-in's own order:
        # account first, then its people). `service_request_id=None`: the
        # request's papers were carried just above and must not be counted
        # twice. A company owner's second person is an OWNER OR OFFICER, by
        # the holder's kind, exactly as on move-in.
        co_owners_written = 0
        if co_block is not None:
            write_people = seams.resolve("customers", "write_at_complete", kind="move_in_people")
            if write_people is not None:
                co_owners_written = write_people(
                    actor, account_id=account["id"], block=co_block, service_request_id=None
                )["co_owners"]
        # ⊕ 🔒 lane CF-1 — the exemption certificate, its file and the
        # discount claims, by move-in's own writer (see `prefs_clean` above),
        # on the day the account opens.
        preferences_written = None
        if prefs_extras is not None and not prefs_extras.empty:
            apply_prefs = seams.resolve("customers", "apply", kind="move_in_preferences")
            if apply_prefs is not None:
                opened = data.get("opened_at") or str(seams.tenant_today())
                preferences_written = apply_prefs(
                    actor,
                    _account_or_404(account["id"]),
                    prefs_extras,
                    on_day=date.fromisoformat(str(opened)[:10]),
                )
        # `DEF-MET-9201` — `BR-MET-1181` says every door that OPENS an owner's
        # account names it on the premises, and this door never did: the
        # property read *Master a/c: Needs an owner* beside a live master
        # account. Only where the premises names none, so an address that
        # already declares its master is never re-pointed by a build.
        from apps.metering import premises_owners

        # A regular account is not a master account and is never named as
        # one on the property (`BR-MET-1181` names a MASTER).
        if home is None and getattr(connection.premises, "master_account_id", None) is None:
            premises_owners._declare_premises_master_account(
                actor, connection.premises_id, account["id"]
            )
        _audit(
            actor,
            "connection.owner_account_created",
            "connection",
            connection.id,
            after={
                "owner_account_id": str(account["id"]),
                "account_no": account.get("account_no"),
                "kind": "regular" if home is not None else "master",
                "unit_id": str(home.id) if home is not None else None,
                "holds_home": (lives_there if home is not None else None),
                "common_areas": len(common_areas),
                "documents_carried": documents_carried,
                "co_owners": co_owners_written,
                "preferences": preferences_written is not None,
                "br_ref": "DEF-CUS-9228" if home is not None else "BR-MET-116",
            },
        )
    return {
        "id": str(connection.id),
        "owner_account_id": str(account["id"]),
        "account_no": account.get("account_no"),
        "kind": "regular" if home is not None else "master",
        # ⊕ `CR-164-BRC10` wave 4 — True: the owner lives there and the
        # account will hold the home on approval; False: billing only.
        "holds_home": (lives_there if home is not None else None),
        "common_areas_covered": len(common_areas),
        "br_ref": "DEF-CUS-9228" if home is not None else "BR-MET-116",
    }


#: ⊕ **`CR-164-BRC10` wave 4 — THE OWNER TYPES WHOSE ACCOUNT KEEPS TODAY'S
#: BEHAVIOUR AND HOLDS THE HOME.** The PO answered *"C By owner type: an owner
#: who lives there holds it; a landlord or builder doesn't"*, then *"B"* (never),
#: then *"i dont know yet"* (all 2026-10-03). **What B and C share is built**: a
#: landlord, builder, property manager, HOA, a utility's own code or no answer
#: opens the owner's account BILLING ONLY. **What they disagree on — an
#: owner-occupier — is `OQ-CUS-12785`, OPEN**, and until it is answered that
#: owner keeps TODAY's behaviour (2.467.0: the account holds the home). That is
#: deliberately not a `NotImplementedError`: a raise here would refuse every
#: owner-occupier's New Connection at Create, while holding the home is what
#: already happens and a Move-out undoes. **Under B this set becomes empty; under
#: C it stays as it is** — the only line that moves, with its screen mirror
#: `ownerLivesThere` in `newConnectDraft.ts`. Step 1's *Owner type* is the
#: tenant's `owner_categories` list (`BR-TEN-150`); `occupier` is the code builds
#: were stored under before `DEF-CUS-9192`.
OWNER_TYPES_THAT_LIVE_THERE = frozenset({"owner_occupier", "occupier"})


def owner_lives_there(owner_type: Any) -> bool:
    """⊕ `CR-164-BRC10` wave 4 — does this step-1 owner type keep today's
    behaviour (the account holds the home)? Only an owner-occupier, pending
    `OQ-CUS-12785` (OPEN) — see `OWNER_TYPES_THAT_LIVE_THERE`.

    HUMAN-REVIEW-PENDING — 🔒 occupancy path (whether a single-family owner's
    account becomes the home's occupant on approval). Row in
    `12-governance/09-human-review-ledger.md` (`CR-164-BRC10` wave 4)."""
    return str(owner_type or "").strip().lower() in OWNER_TYPES_THAT_LIVE_THERE


def _single_family_home(connection: Any) -> Any:
    """**`DEF-CUS-9228` — the ONE home a single-family build's owner account
    holds, or `None` when this build's owner account is a master.**

    A home is returned only when BOTH are true, and each is the utility's own
    answer rather than a guess: the premises TYPE says *Regular account*
    (`premises_types.account_kind`, `CR-162-BRC10` Q1 — never a count), and the
    address holds exactly one unit that is not a common area. Two homes on a
    single-family type answer `None` so the master door refuses them by name,
    exactly as before the ruling; an unanswered type answers `None` too, and
    falls back to the master door's counting rule."""
    from apps.metering import premises_capacity

    if premises_capacity.premises_account_kind(connection.premises_id) != "regular":
        return None
    homes = list(
        metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(),
            premises_id=connection.premises_id,
            is_common_area=False,
            deleted_at__isnull=True,
        ).order_by("label", "id")[:2]
    )
    return homes[0] if len(homes) == 1 else None


def _account_or_404(account_id: Any) -> Any:
    """The account, or a 404 — read through the seam, never by importing
    `customers` models here. Cross-module READS go through the reviewed
    interface (B2 §2) for the same reason cross-module WRITES are forbidden."""
    from apps.customers import models as customers_models

    row = customers_models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _refuse_unticked_safety(order: Any) -> None:
    """**THE SERVER HALF OF THE SAFETY GATE** — `BR-WRK-037`, `US-WRK-043`.

    r10, verbatim, and it is the whole reason this function exists rather than
    only a greyed-out button: *"The lock is on the phone, and it must also be on
    the server. A screen that greys a list is a convenience; a server that
    refuses a completion with an unticked mandatory safety row is the guarantee.
    **Build both or you have built neither.**"*

    ⚠ **IT CALLS `apps.work.checklist.safety_lock` AND DOES NOT RESTATE THE
    CONDITION.** That function's own docstring asks for exactly this: *"wave J's
    phone call reads it rather than restating the condition"*, because the
    plausible failure is two surfaces that disagree about whether a job may
    proceed — one gets a fix, the other does not, and a technician is allowed to
    start work the office believes is blocked. There is ONE evaluator. Ticking
    is `tick_safety`, the task lock is `tick_task`, and the completion lock is
    here; all three ask the same function.

    ⚠ **TWO OF THREE IS LOCKED.** `safety_lock` returns a COUNT and never a
    proportion, and this reads `remaining > 0` through its `locked` key. Nothing
    in this file may introduce a threshold: a partially-completed safety list is
    exactly the state in which somebody gets hurt.

    ⚠ **ONLY *MANDATORY* ROWS GATE** — `US-WRK-043` TC-4: a completion with a
    NON-mandatory safety row unticked is ACCEPTED. A template may carry an
    advisory line, and refusing on one would make the advisory line mandatory by
    accident, in a place nobody would look.

    ⚠ **AN ORDER WITH NO SAFETY ROWS AT ALL IS NOT REFUSED.** Orders raised
    before wave H copied nothing, and a template may legitimately declare no
    safety step. `safety_lock` returns `locked = False` for an empty list, which
    is the correct reading — the lock is *"a mandatory row is outstanding"*, not
    *"a safety list was found"*. Refusing here would make every historical order
    uncloseable, which is a data migration disguised as a safety rule.

    THE REFUSAL SENTENCE, AND WHY THE ROW IS IN `params`
    ----------------------------------------------------
    `BR-WRK-037` says the server NAMES the row. B14 rule 33 caps a refusal at
    five or six words. Both hold at once only if the row travels beside the
    sentence rather than inside it: the message key renders *"Finish safety
    first."* (three words) and `params["safety"]` carries
    *Confined space check where pit-set*, which the screen prints next to it.
    Naming it inside the sentence would break rule 33; naming it nowhere would
    break the rule the sentence serves.

    ⚠ **`BIZ_LOCKED` → 409, THE SAME CODE `tick_task` USES.** Nothing is wrong
    with the request; the job is not ready for it yet, and it will be as soon as
    somebody ticks the row. A 400 would tell the phone to stop retrying.

    ⚠ **BEFORE ANY WRITE, AND BEFORE THE AUDIT ROW.** `US-WRK-043` TC-3 asserts
    `state` unchanged and **no audit of a completion** — so this is the first
    statement after the order resolves, not a check inside the save.
    """
    # Imported at CALL time: `apps/work` imports this module through its seam,
    # and a module-scope import here would close that loop at startup.
    from apps.work import checklist as work_checklist

    lock = work_checklist.safety_lock(order.id, tenant_id=order.tenant_id)
    if not lock["locked"]:
        return
    raise errors.BizError(
        errors.BIZ_LOCKED,
        br_ref="BR-WRK-037",
        # Three words; the outstanding row rides in `params`. See the docstring.
        message_key="work.order.finish_safety_first",
        params={"safety": lock["first_outstanding"], "remaining": lock["remaining"]},
    )


def submit_field_result(
    actor: Any,
    work_order_id: Any,
    *,
    field_data: dict[str, Any] | None = None,
    outcome: str | None = None,
    external_ref: str | None = None,
    completed_at: Any = None,
) -> dict[str, Any]:
    """**BR-MET-110, step one: THE FIELD SENDS ITS DATA. Nothing activates yet.**

    PO 2026-08-25: *"Work order will send the data and confirm from field;
    utility staff will review these work order, accept them and use data from
    them to activate these services or confirm the installation is completed."*

    This is the first of the three steps and it deliberately does the least:
    it records what came back and marks the order **completed**, which under
    this rule means *"the crew says it is done"* and **not** *"a person agrees
    it is done"*. `accepted_by` stays NULL, and **that NULL is the review
    queue** — it is the only thing in the schema that says an order is waiting
    for a human.

    ⚠ CR-038 W9 task 7: `field_data` stays free-shaped (BR-MET-109), and ONE
    key is now documented — `set_reads`, `[{meter_no, value, read_at?,
    channel?}, ...]`, the register the crew set the meter at. NOTHING posts
    here: the reading waits with the rest of the field data for the human
    acceptance (`accept_field_result`), which is what BR-MET-110 means by
    *"use data from them"*.

    ⚠ **`completed_at` IS A PARAMETER SINCE CR-070 WAVE L, AND IT IS NOT A
    CONVENIENCE — IT IS THE DATE A METER READ LANDS ON.** A technician closes
    three jobs at 10:20, 12:05 and 16:07 with no signal and the phone reaches
    the server at 17:40 (`J65` step 7). `accept_field_result` DATES EVERY SET
    READ FROM THIS COLUMN (`BR-WRK-003`, `BR-TEN-043` — *an event date, never a
    wall clock*), so a wall-clock stamp here would put a whole offline day's
    readings on the wrong day, on a billing path, with nothing on any screen to
    show it. Omitted, it still defaults to now, which is right for the staff
    app pressing the button while the job is in front of them.

    **A FUTURE time is refused** rather than trusted: the handset's clock is the
    handset's, and a close stamped tomorrow would date a meter read into a
    period that has not been billed yet.
    """
    order = _work_order_or_404(work_order_id)
    # ⚠ **RULING 18, AND IT IS HERE SO EVERY DOOR INHERITS IT** (`CR-168-BRC10`
    # P1.34, judgment J4, `DEF-WRK-9525`). PO, 24 Sep: *"back office cannot
    # complete the job it can only accept it"* — `BR-MET-110`'s three steps,
    # with the first one made a rule rather than a habit. The web's *Mark
    # complete*, a script against `/field-result` and the phone's sync all
    # arrive at THIS function, so the guard is written once, below every door.
    # A hidden button is not a rule (hard-won law 1).
    _refuse_unless_field(actor, order)
    # ⚠ **A MISSING REQUIRED PHOTOGRAPH WARNS, IT NO LONGER STOPS THE CLOSE —
    # `BR-WRK-040` SUPERSEDED 2026-10-21** (PO, verbatim: *"warn"*; decision log
    # *"Field app: the PO corrects four of the ten answers"* item 3; R110 as the
    # design wrote it). Until then this line was `_refuse_missing_required_
    # photos(order)` (`DEF-WRK-9625`, which moved the stop from the phone's
    # button to the server). The DOOR is still the server's and still below
    # every route — what it does now is RECORD THE GAP on the close, where the
    # office's acceptance queue reads it (`work.field_outcomes.outcome_record`
    # → `photos_missing`). The cancelled and safety refusals are unchanged:
    # safety is a stop the technician fixes on the spot (`BR-WRK-037`).
    _refuse_if_cancelled(order.connection)
    _refuse_unticked_safety(order)
    field_data = _with_photo_gap(order, field_data)
    result = _record_field_result(
        actor,
        order,
        field_data=field_data,
        outcome=outcome,
        external_ref=external_ref,
        completed_at=completed_at,
    )
    # CR-169-BRC10 §2 row 9 — sent AFTER COMMIT, from the DOOR and not from
    # `_record_field_result`, so the demo's seeded history (its other caller)
    # never reaches a PostHog project. No PII: the fact, the utility, the actor.
    from config import product_analytics

    product_analytics.capture_after_commit(
        "work_order_completed",
        tenant_id=order.tenant_id,
        actor_id=product_analytics.actor_id_of(actor),
        properties={"source": "field"},
        dedupe_key=str(order.id),
    )
    return result


def _with_photo_gap(order: Any, field_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """**THE CLOSE RECORDS ITS GAP** — `BR-WRK-040` as superseded 2026-10-21
    (PO: *"warn"*). A missing REQUIRED photograph no longer stops the close;
    the close is recorded WITH the gap and the office sees it.

    The gap is written by the SERVER into `field_data["photos_missing"]` —
    `{"count", "items": [{scope, id, prompt}]}` — beside `close_location` and
    `labour_time`, which the server writes the same way and never takes from
    the phone. A close with nothing missing carries no key at all, and a key
    the phone sent under that name is dropped, so the office can only ever
    read the server's own count. `work.field_outcomes.outcome_record` serves it
    on every acceptance-queue row and on `GET /work-orders/{id}/outcome`.

    ⚠ **IT ASKS `apps.work.evidence.close_readiness` AND DOES NOT RESTATE THE
    CONDITION** — the posture `_refuse_unticked_safety` takes: the phone's
    Close pane reads that one function too (`missing_photos`), so the two
    cannot disagree about which photographs are missing. A photograph whose
    link exists and is still uploading is PENDING, not missing (`BR-WRK-062`).
    """
    # Imported at CALL time for `_refuse_unticked_safety`'s reason.
    from apps.work import evidence as work_evidence

    ready = work_evidence.close_readiness(order.id)
    missing = list(ready.get("missing_photos") or [])
    data = dict(field_data) if isinstance(field_data, dict) else {}
    data.pop("photos_missing", None)
    if missing:
        data["photos_missing"] = {
            "count": len(missing),
            "items": [
                {"scope": row.get("scope"), "id": row.get("id"), "prompt": row.get("prompt") or ""}
                for row in missing
            ],
            "br_ref": "BR-WRK-040",
        }
    return data or field_data


def _refuse_unless_field(actor: Any, order: Any) -> None:
    """Only the person or crew the job was GIVEN TO may say it is done.

    Admitted: the job's technician (`assignee_technician.user` is the caller),
    or a technician whose crew — a crew or a contractor — holds it (ruling 36:
    *"a contractor's people close their own jobs on the phone"*). Everyone else,
    whatever their role, is refused `work.order.closed_by_field_only`; an
    unassigned job therefore cannot be closed at all, which is the point —
    somebody has to be sent before anybody can say they went.

    ⚠ **THE OFFICE IS NOT EXEMPT BY ROLE, DELIBERATELY.** A System Admin who
    also holds a technician profile and was given the job may close it — as
    the technician. Their role is not the question; whether they were sent is.
    """
    from apps.work import models as work_models

    actor_id = getattr(actor, "id", None)
    technician = (
        work_models.Technician.objects.filter(tenant_id=order.tenant_id, user_id=actor_id).first()
        if actor_id is not None
        else None
    )
    if technician is not None and (
        (order.assignee_technician_id and order.assignee_technician_id == technician.id)
        or (order.assignee_crew_id and order.assignee_crew_id == technician.crew_id)
    ):
        return
    raise errors.AuthError(
        errors.AUTH_PERMISSION_DENIED,
        br_ref="BR-MET-110",
        message_key="work.order.closed_by_field_only",
        params={"order_no": order.order_no or ""},
    )


def _record_field_result(
    actor: Any,
    order: Any,
    *,
    field_data: dict[str, Any] | None = None,
    outcome: str | None = None,
    external_ref: str | None = None,
    completed_at: Any = None,
) -> dict[str, Any]:
    """The close itself, once `submit_field_result` has admitted the caller.

    ⚠ **PRIVATE, AND THE ONE CALLER BESIDE THE DOOR IS SAMPLE HISTORY.**
    `sample_data._seed_w6_connections` writes the demo's PAST — builds whose
    orders were finished before any technician existed in the demo — and is not
    a door anybody can reach (`BR-TEN-057`). Every request path goes through
    `submit_field_result` and its guard; a new caller of this function is a new
    door, and must not be one.
    """
    _refuse_if_cancelled(order.connection)
    _refuse_unticked_safety(order)
    before = {"state": order.state, "outcome": order.outcome}
    named = str(outcome or "").strip()
    if named and named not in WORK_ORDER_OUTCOMES:
        # `DEF-WRK-6737` — refused here so the caller gets a sentence; the
        # database's `ck_work_orders_outcome` (`metering/0076`) is the backstop.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="B18 §8.3",
            message_key="metering.work_order.outcome_unknown",
            params={"outcome": named, "allowed": ", ".join(WORK_ORDER_OUTCOMES)},
        )
    order.field_data = field_data
    order.outcome = named or order.outcome
    if external_ref:
        order.external_ref = str(external_ref).strip()
    order.state = WO_COMPLETED
    now = timezone.now()
    if completed_at is not None and completed_at > now:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-TEN-043",
            message_key="metering.work_order_completed_at_future",
            params={"order_no": order.order_no or ""},
        )
    order.completed_at = completed_at or now
    # ⚠ **THE THIRD AXIS MOVES WITH THE CLOSE** (`CR-168-BRC10` P1.31,
    # `DEF-WRK-9526`). `BR-WRK-023` has seven dispatch tokens and `complete` is
    # one of them, but this save wrote `state` alone, so a finished job went on
    # reading *Scheduled* on the dispatcher's list and *Queued* on the demo (22
    # of 23). A job a person put ON HOLD or CANCELLED keeps that token: those
    # are deliberate acts, and a phone's close must not overrule them (the
    # `dispatch._refresh_cache` posture).
    if order.dispatch_state not in (DISPATCH_ON_HOLD, DISPATCH_CANCELLED):
        order.dispatch_state = DISPATCH_COMPLETE
    order.save(
        update_fields=[
            "field_data",
            "outcome",
            "external_ref",
            "state",
            "completed_at",
            "dispatch_state",
            "updated_at",
        ]
    )
    # ⚠ **THE RATE AND THE MINUTES ARE STAMPED HERE, AND NOTHING CALLED THIS
    # UNTIL `DEF-WRK-4124`.** `BR-WRK-020` and `US-WRK-051` TC-2 fix the labour
    # rate AT CLOSE — this is the close — so that a rate superseded next April
    # cannot move a report signed today. `work_services.snapshot_labour_rate_at_
    # close` existed, was documented, and had no caller anywhere in the
    # repository, so `labour_rate_snapshot` was NULL on every order that had
    # ever closed and every report priced its labour at nothing.
    #
    # ⚠ **AFTER the save, deliberately.** The minutes are `completed_at` minus
    # the last arrival, so the stamp needs the completion time to be on the row
    # already. It writes its own three columns and nothing here depends on it —
    # a job with no rate for its role, or no recorded arrival, simply carries no
    # labour line (`costing.py`'s *we cannot say* rather than *free*).
    #
    # Work's service, called from metering, the way `accept_field_result` below
    # already calls `generate_work_order_report`.
    from apps.work import services as work_services

    work_services.snapshot_labour_rate_at_close(order)
    _audit(
        actor,
        "work_order.field_result",
        "work_order",
        order.id,
        before=before,
        after={"state": order.state, "outcome": order.outcome, "accepted": False},
    )
    return {
        "id": str(order.id),
        "state": order.state,
        "awaiting_review": True,
        "br_ref": "BR-MET-110",
    }


def send_back_field_result(
    actor: Any, work_order_id: Any, reason: Any = None, *, after_acceptance: bool = False
) -> dict[str, Any]:
    """`CR-168-BRC10` P4.14 — the office SENDS A FINISHED JOB BACK TO THE FIELD,
    with a reason, **only before it has accepted it** (judgment J9).

    The field closed it; the office read what came back and it is not right —
    a photograph missing, a reading that cannot be true. Before this there was
    no door: the office could accept a job it disagreed with or leave it in the
    queue for ever. So: `state` back to *in progress*, `dispatch_state` back to
    *scheduled*, `completed_at` and `outcome` cleared (the job is no longer
    done), and **`field_data` KEPT** — the technician's readings, ticks and
    photographs stay on the job they are being asked to finish.

    ⚠ **REFUSED ONCE ACCEPTED (`work.order.already_accepted`).** Acceptance
    writes cost lines and posts meter reads (`BR-MET-110`); re-opening an
    accepted job would leave those standing behind a job the field is still
    working — hard rule 4's shape. Nothing accepted is ever re-opened.

    ⚠ **EXCEPT BY THE OFFICE'S REOPEN, SINCE 2026-10-21 — `after_acceptance`.**
    PO answer 11 (decision log *"Field app: ten PO answers"*): *"yes"* — the
    office MAY reopen a job it has already accepted; judgment J9 is SUPERSEDED
    for the office. The one caller that passes `after_acceptance=True` is
    `work.field_reopen._office_reopen` (`POST /work-orders/{id}/come-back`,
    `decision: reopen`), which writes the reopen history row first. This
    route's own door (`POST /work-orders/{id}/send-back`) keeps J9's refusal.
    The acceptance is cleared (`accepted_at`, `accepted_by`) so the job can be
    accepted again; what it was is kept in the audit row below, in the reopen
    history's `prior`, and in the frozen `-v1` report, which is never edited —
    the next acceptance writes `-v2` beside it
    (`work.services.generate_work_order_report`). What the first acceptance
    POSTED (meter reads, an installed meter) stands and is not posted again
    (`accept_field_result`'s re-acceptance branch).

    Who may press it: the office roles that may ACCEPT (`work_accept`) — the
    act is the other answer to the same question. Audited
    `work.order.sent_back` with the reason; the order's history reads it
    (`dispatch.AUDIT_ACTS`). The technician's phone receives the job back on
    its next sync (the job is open again and still theirs).
    """
    from apps.identity import selectors as identity_selectors

    if not identity_selectors.role_holds(getattr(actor, "role", None), "work_accept"):
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            message_key="metering.work_order_accept_not_permitted",
            br_ref="BR-WRK-044",
        )
    order = _work_order_or_404(work_order_id)
    was_accepted = order.accepted_at is not None
    if was_accepted and not after_acceptance:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-110",
            message_key="work.order.already_accepted",
            params={"order_no": order.order_no or ""},
        )
    if order.state != WO_COMPLETED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-110",
            message_key="metering.work_order_not_completed",
            params={"order_no": order.order_no or "", "state": order.state},
        )
    why = str(reason or "").strip()
    if not why:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.order.send_back_reason_required"
        )
    before = {
        "state": order.state,
        "dispatch_state": order.dispatch_state,
        "outcome": order.outcome,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }
    fields = ["state", "dispatch_state", "completed_at", "outcome", "updated_at"]
    if was_accepted:
        # PO answer 11 — what the acceptance was, kept in the audit row.
        before["accepted_at"] = order.accepted_at.isoformat()
        before["accepted_by"] = str(order.accepted_by_id) if order.accepted_by_id else None
    with transaction.atomic():
        order.state = WO_IN_PROGRESS
        order.dispatch_state = DISPATCH_SCHEDULED
        order.completed_at = None
        order.outcome = None
        if was_accepted:
            order.accepted_at = None
            order.accepted_by = None
            fields[-1:-1] = ["accepted_at", "accepted_by"]
        order.save(update_fields=fields)
        if order.connection_id:
            refresh_connection_state(order.connection)
        _audit(
            actor,
            "work.order.sent_back",
            "work_order",
            order.id,
            before=before,
            after={
                "state": order.state,
                "dispatch_state": order.dispatch_state,
                "order_no": order.order_no,
                "reason": why,
                **({"after_acceptance": True} if was_accepted else {}),
            },
        )
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        "state": order.state,
        "dispatch_state": order.dispatch_state,
        "reason": why,
        "after_acceptance": was_accepted,
    }


def _clear_waiting_on_after_last_job(actor: Any, order: Any) -> bool:
    """`DEF-MET-9633` — a build whose every field job is accepted waits on no one
    in the field, so its *Waiting on* is cleared and audited.

    Measured on `2.503.2`: `CON-26-0126` read *Partly activated · Waiting on:
    inspection* with 5 of 5 jobs accepted and its inspection among them. The
    note is free text a clerk set (`set_waiting_on`); this clears it only at the
    one moment it is provably stale — the last open job accepted — and never
    touches a build that still has a job open, held or awaiting acceptance.
    The clerk's next act is then the build's own *Approve* (`CR-162-BRC10`
    Q2), which this does not take for them: activation stays a person's act.
    OUR judgment, decision log 2026-10-04 *"CR-168 FLOW-FIX · A BUILD STOPS
    WAITING WHEN ITS LAST JOB IS ACCEPTED"*.
    """
    if not order.connection_id:
        return False
    connection = Connection.objects.select_for_update().filter(pk=order.connection_id).first()
    if connection is None or not (connection.waiting_on or "").strip():
        return False
    still_open = (
        WorkOrder.objects.filter(tenant_id=connection.tenant_id, connection_id=connection.id)
        .exclude(state=WO_CANCELLED)
        .filter(accepted_at__isnull=True)
        .exists()
    )
    if still_open:
        return False
    before = connection.waiting_on
    connection.waiting_on = None
    connection.save(update_fields=["waiting_on", "updated_at"])
    _audit(
        actor,
        "connection.waiting_on_cleared",
        "connection",
        connection.id,
        before={"waiting_on": before},
        after={"waiting_on": None, "reason": "last_field_job_accepted", "order": order.order_no},
    )
    return True


def accept_field_result(actor: Any, work_order_id: Any) -> dict[str, Any]:
    """**BR-MET-110, step two — THE HUMAN ACT, and the one the rule is about.**

    A member of staff reviews what the field sent and accepts it. Only then is
    the data allowed to activate a service or confirm an installation.

    ⚠ **AND SINCE `BR-MET-115` (ruled the same day) THIS IS ALSO THE SEND.**
    PO verbatim: *"dont keep it at the time of new conenct creation , remove it;
    and sent it whnr utility user mar that job complete traigger it tat that
    time"*. So this single call is **one human act, one auditable moment, three
    consequences** — data accepted, service activated, customer told.

    ⛔ **THE THIRD CONSEQUENCE IS GUARDED, NOT DEFAULTED — `OQ-372`.** The PO
    fixed the TRIGGER and did not say **which job**. `CON-26-0117` carries
    **7 work orders across 25 units**; accepting order 3 of 7 must NOT tell 25
    households their service is on. Three readings and no evidence between
    them — the service's GATE order, the LAST order, or the utility's choice per
    template. **The failure is not symmetric:** sending late is an annoyance,
    sending early tells a customer their supply is live when it is not, and a
    letter cannot be amended. So this records that a send is DUE and refuses to
    name a piece.
    """
    # ⚠ **WHO MAY PRESS THIS — `OQ-WRK-1492`, RULED 2026-09-04.** PO verbatim:
    # *"clark can do it sicne it s a day to day work"*. Accepting a finished
    # job is ordinary daily work and must not queue behind a supervisor,
    # because a two-person utility has none sitting by the screen. So the named
    # permission `work_accept` is held by the three OFFICE roles
    # (`identity/0005`) and this is where the server checks it — `BR-SHL-025`:
    # the server independently enforces every mutating call, whatever the
    # screen has disabled.
    #
    # ⚠ **AND THERE IS NO SECOND CHECK FOR A FIELD TECHNICIAN, DELIBERATELY.**
    # `BR-WRK-044` records the reason: `OQ-WRK-1494` keeps a technician's login
    # off the web app entirely and the Accept control is there, so *a
    # technician never accepts their own work* is a CONSEQUENCE of the surface
    # scope. A rule of its own here would go stale the day the phone gains an
    # approval screen.
    # A LOCAL import, the shape line 3646 already uses for `identity.User`:
    # identity is imported where it is read and never at module scope, so
    # metering's import graph does not depend on it to load.
    from apps.identity import selectors as identity_selectors

    # CR-070 wave L. A LOCAL import for the same reason identity is one: work
    # imports metering at module scope, so a module-scope import here would
    # close the cycle and neither app would load.
    from apps.work.seams import metering_seam as work_metering_seam

    if not identity_selectors.role_holds(getattr(actor, "role", None), "work_accept"):
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            message_key="metering.work_order_accept_not_permitted",
            br_ref="BR-WRK-044",
        )
    order = _work_order_or_404(work_order_id)
    _refuse_if_cancelled(order.connection)
    if order.state != WO_COMPLETED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-110",
            message_key="metering.work_order_not_completed",
            params={"order_no": order.order_no or "", "state": order.state},
        )
    if order.accepted_at is not None:
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-MET-110",
            message_key="metering.work_order_already_accepted",
            params={"order_no": order.order_no or ""},
        )
    # ⚠ **ACCEPT WAITS FOR REQUIRED PHOTOS STILL UPLOADING** — PO 2026-10-04,
    # verbatim: *"(a) Dana sees \"3 photos uploading\", and Accept stays
    # unavailable until they've all arrived"*. Below every door; optional
    # photos never hold it. Imported at call time, `_refuse_unticked_safety`'s
    # reason.
    from apps.work import photo_links as work_photo_links

    work_photo_links.refuse_accept_while_uploading(order.id)
    # ── PO answer 11 (2026-10-21) · A RE-ACCEPTANCE ─────────────────────────
    # The office may now reopen an ACCEPTED job (`send_back_field_result`,
    # `after_acceptance`). Accepting it AGAIN is a second human act over a job
    # whose first acceptance already put facts in the books: its meter reads
    # are committed and a fitted meter is installed. Posting them again would
    # meet the read pipeline's committed-duplicate rule and refuse the whole
    # acceptance for ever, so a re-acceptance posts NEITHER — they stand, and a
    # reading that was wrong is corrected through metering's own read
    # correction, never by a second post. Everything else runs as before; the
    # report is the NEXT version beside the frozen one, and a failed outcome
    # raises its follow-up only if the first acceptance did not already.
    from apps.work import services as work_reaccept

    reaccepting = work_reaccept.reopened_after_acceptance(order.id)
    with transaction.atomic():
        # ── CR-038 W9 task 7: the SET READ, activated by the acceptance ──────
        # BR-MET-110's whole shape — *"utility staff will review these work
        # order, accept them and USE DATA FROM THEM to activate these
        # services"* — so the field's set reading (`field_data.set_reads`,
        # `[{meter_no, value, read_at?, channel?}, ...]`) posts through the
        # event door ONLY at this human acceptance, event `new_connect`, the
        # ACCEPTER as the acting user (BR-MET-128). The default read date is
        # the order's own `completed_at` — the field's recorded completion,
        # an event date, never a wall clock (BR-TEN-043). BR-MET-129 rides
        # the door: the vacant-unit warning (no occupant yet at energisation
        # — the expected state) posts FLAGGED; an ERROR refuses the WHOLE
        # acceptance with rows named, because accepting field data the
        # pipeline refuses to store would activate a service off a reading
        # that does not exist. One transaction = one human act (BR-MET-115's
        # own framing), so a refusal leaves the order still awaiting review.
        set_reads = (order.field_data or {}).get("set_reads")
        event_reads = None
        if set_reads and not reaccepting:
            completed = order.completed_at.date().isoformat() if order.completed_at else None
            rows = []
            for raw in set_reads:
                row = dict(raw) if isinstance(raw, dict) else {}
                if not row.get("read_at") and completed:
                    row["read_at"] = completed
                rows.append(row)
            event_reads = metering_services.commit_event_reads(
                actor,
                {
                    "event": "new_connect",
                    "reads": rows,
                    "context": {
                        "work_order_id": str(order.id),
                        # DEF-WRK-3635 — `str(None)` here wrote the literal
                        # string "None" into a read's provenance, which is worse
                        # than an absence: it looks like an id.
                        "connection_id": (
                            str(order.connection_id) if order.connection_id else None
                        ),
                        "flow": "new_connect",
                    },
                },
            )
        # ── CR-070 wave L · `L2` · US-WRK-046 · BR-WRK-003 ──────────────
        # **THE SECOND SET-READ SOURCE, AND IT IS A DIFFERENT FACT FROM THE
        # ONE ABOVE.** The block above posts `field_data.set_reads` — the
        # free-shaped list the NEW-CONNECTION WIZARD types (CR-038 W9). This
        # posts `work_order_readings` — the STRUCTURED rows a TEMPLATE asked
        # for and a technician filled in on a phone, each with its own
        # `unit_of_measure` column (`BR-WRK-015`, hard rule 3).
        #
        # ⚠ **TWO SOURCES, ONE DOOR, AND NO DOUBLE POST.** Both go through
        # `commit_event_reads`, and a template reading and a wizard-typed
        # entry for the SAME meter on the SAME date meet the read pipeline's
        # own committed-duplicate rule, which is an ERROR naming the existing
        # read and refuses the whole acceptance. That is the correct answer —
        # one read per meter per date (`BR-MET-059`) — and it is metering's
        # rule doing the work rather than a reconciliation invented here.
        #
        # ⚠ **INSIDE THE TRANSACTION, DELIBERATELY.** `BR-MET-115`'s framing is
        # *one human act, one auditable moment*: a reading the read pipeline
        # refuses must leave the order still awaiting review, exactly as the
        # block above already does. `US-WRK-046` TC-4/TC-5 assert the rollback.
        field_reads = (
            {"posted_reads": 0}
            if reaccepting
            else work_metering_seam.post_set_reads(actor, order)
        )
        # ── `DEF-AST-9712` (`CR-171-BRC10` P1.27) · BR-AST-020 ──────────────
        # A MOVE-IN visit raised FOR a meter still In stock fitted it, and this
        # acceptance confirms the installation — the same human act that
        # installs a new connection's earmarked meters (`connection_activation`).
        # Dated by the field's own completion (BR-TEN-043), inside the
        # transaction so a refused acceptance installs nothing.
        if order.source == SOURCE_MOVE_IN and order.asset_id and not reaccepting:
            seams.install_fitted_asset(
                actor,
                asset_id=order.asset_id,
                install_date=order.completed_at.date() if order.completed_at else None,
            )
        order.accepted_by = _user_or_none(actor)
        order.accepted_at = timezone.now()
        order.save(update_fields=["accepted_by", "accepted_at", "updated_at"])
        _audit(
            actor,
            "work_order.accepted",
            "work_order",
            order.id,
            after={
                "accepted_at": order.accepted_at.isoformat(),
                "br_ref": "BR-MET-110",
                "set_reads_posted": (event_reads or {}).get("posted_reads", 0),
                # Reported separately from the wizard's count above, because
                # *the wizard typed three and the field posted one* is a
                # different sentence from *four reads were posted*.
                "field_readings_posted": field_reads.get("posted_reads", 0),
                **({"reaccepted": True} if reaccepting else {}),
            },
        )
        # ── CR-070 wave I · BR-WRK-054's consequence chain (US-WRK-034) ─────
        # INSIDE the transaction, deliberately — see `_failed_outcome_chain`.
        consequence = (
            None
            if reaccepting
            and WorkOrder.objects.filter(
                tenant_id=order.tenant_id, follows_order_id=order.id
            ).exists()
            else _failed_outcome_chain(actor, order)
        )
        # `DEF-MET-9633` — the build stops *waiting on* the field once its LAST
        # job is accepted (after the chain above, so a failed job's follow-up
        # counts as work still open).
        _clear_waiting_on_after_last_job(actor, order)
    # ⚠ **AN ORDER WITH NO BUILD RE-DERIVES NOTHING, AND `None` IS THE ANSWER
    # RATHER THAN A GUESS (`DEF-WRK-3635`).** `refresh_connection_state` is the
    # ONLY writer of `connections.state`; with no connection there is no state
    # to refresh and no state to report. Returning a word here — `"activated"`,
    # say, because the job passed — would be this function inventing a fact
    # about a build that does not exist.
    state = refresh_connection_state(order.connection) if order.connection_id else None
    #: ⚠ **OQ-372 CLOSED 2026-08-25 — the send fires HERE, not behind a guard.**
    #: This used to return `communication_due: True` with `piece: None` and
    #: `blocked_by: "OQ-372"`, because which of a build's seven orders should
    #: send was unruled and a letter three weeks early cannot be amended. The PO
    #: ruled: *"When Utility user mark it as complete using button on screen"* —
    #: the system never ranks the orders, and this acceptance IS that press
    #: (BR-MET-110: *"accept them and … confirm the installation is completed"*).
    sent = dispatch_communication(actor, order.id)
    # ── CR-070 wave P · B19 §12.3, made executable (US-WRK-039) ────────────
    #
    # *"A request closes on its own when the job it created finishes."* An order
    # raised by an approved service request carries that request's own number in
    # `source_ref` (BR-WRK-024), and customers decides whether the application is
    # now finished — EVERY job accepted, never the first, because a new water
    # connection is three jobs days apart and closing on the inspector's report
    # would mark the application done before anybody dug the trench.
    #
    # ⚠ **OUTSIDE THE TRANSACTION ABOVE, AND CAUGHT.** The acceptance is a
    # committed fact the moment the block closes; a request that could not be
    # closed must not un-accept a field result somebody has already reviewed
    # (BR-MET-110: one human act, one auditable moment). A failure here leaves
    # the request in fulfilment, which is exactly where a clerk can close it by
    # hand — `manual_close` already exists for it.
    request_closed = None
    if order.source == SOURCE_SERVICE_REQUEST and order.source_ref:
        try:
            request_closed = seams.close_service_request_if_field_work_done(
                actor, order.source_ref
            )
        except Exception:  # noqa: BLE001 - an accepted field result stands regardless
            request_closed = None
    # ── CR-070 wave N · the work-order report (US-WRK-053, BR-WRK-050) ─────
    #
    # ⚠ **THIS IS THE ONE CALL SITE, AND `submit_field_result` IS DELIBERATELY
    # NOT ANOTHER** (`US-WRK-053` TC-7 asserts there is no second one). `WM-47`:
    # *"It is generated on approval and not on completion, because until a
    # person accepts the field data nothing on the page is final."* A report
    # produced at completion would carry a total a supervisor had not yet
    # agreed to — and a report is the document the cost is read off.
    #
    # A second Accept produces no second `v1`: this function already refused
    # above on `accepted_at is not None`, and the unique key on
    # (tenant, order, version) is the backstop underneath it (hard rule 6's
    # shape for a bill run).
    #
    # ⚠ **OUTSIDE THE TRANSACTION, AND CAUGHT — the same posture the service
    # request above takes, for the same reason.** The acceptance is a committed
    # fact the moment that block closes; a report that could not be generated
    # must not un-accept a field result somebody has already reviewed
    # (BR-MET-110: one human act, one auditable moment). A missing report is a
    # document a supervisor can regenerate; a rolled-back acceptance is a
    # service that did not go live.
    report = None
    try:
        from apps.work import services as work_services

        report = work_services.generate_work_order_report(actor, order)
    except Exception:  # noqa: BLE001 - an accepted field result stands regardless
        report = None
    # ── CR-168-BRC10 P6.1 (lane SRV-5) · the customer told it is DONE ───────
    # Ruling 3's fourth consumer message, at the one human act that makes the
    # field result final — a PASSED job only (`visit_notices.after_accept`).
    # Outside the transaction and never able to fail it, the posture of the two
    # consequences above.
    try:
        from apps.work import visit_notices

        visit_notices.after_accept(order, actor=actor)
    except Exception:  # noqa: BLE001 - an accepted field result stands regardless
        pass
    result = {
        "id": str(order.id),
        "accepted_at": order.accepted_at.isoformat(),
        "connection_state": state,
        "service_request": request_closed,
        "communication": sent,
        # `BR-WRK-054` — what a FAILED outcome produced. Always present and
        # `None` on a job that passed, so a caller reads an ANSWER rather than
        # having to know that a missing key means nothing failed.
        "failed_outcome": consequence,
        "report": report,
        "br_ref": "BR-MET-115",
    }
    if event_reads is not None:
        # W9 task 7 — the set read the acceptance activated, on the answer so
        # the (future — task 6.14) accept surface can show what it committed.
        result["event_reads"] = event_reads
    return result


def _failed_outcome_chain(actor: Any, order: Any) -> dict[str, Any] | None:
    """**`BR-WRK-054` — a failure is not a token nobody acts on** (`US-WRK-034`,
    `WM-25`, `J66`; CR-070 wave I).

    The rule, verbatim: *"A `failed` outcome raises a follow-up order and puts
    the connection on hold, with the reason in Waiting on."* Before this, the
    design said so and **neither happened** — `failed` was one of five outcome
    tokens that shipped, and a supervisor accepting one got a completed order
    and silence.

    TWO CONSEQUENCES, AND THE SECOND IS CONDITIONAL WHERE THE FIRST IS NOT
    ----------------------------------------------------------------------
    1. **A follow-up order**, copied from the SAME template and version
       (`BR-WRK-008` — copy, never link), carrying:
         * `blocked_by` = the failed order — *do not start me yet*;
         * `follows_order_id` = the failed order — *I exist because that one
           failed*. Two columns because they are two facts; `metering/0052`'s
           docstring carries the full argument and the short form is that
           `EP-WRK-10`'s FIRST-TIME FIX counts the second and would be wrong
           every month if it counted the first.
         * `source = failed_outcome` (`BR-WRK-024`) — the FIFTEENTH token, added
           by `metering/0052` because it did not exist and this chain would
           otherwise have been refused by `ck_work_orders_source` at the moment
           somebody pressed Accept.
         * the failed order's own ANCHORS, so a one-off job's follow-up stands
           on what the original stood on.
    2. **The build on hold**, `waiting_on` = the technician's stated reason,
       through `hold_connection` — **metering's own writer**. `US-WRK-034` §5 is
       explicit that this is *"the one place Work asks metering to write a
       connection, and it is metering's function that writes"*.

    ⚠ **A FAILED ONE-OFF JOB GETS THE FOLLOW-UP AND NO HOLD, AND SAYS SO**
    (`US-WRK-034` TC-4, `J66` step 8). `WO-4823` is a leak investigation at
    `77 Cedar Ct` with `connection_id` NULL — **there is no build to hold.**
    Inventing one, or holding whatever connection the premises happens to have,
    would stop somebody's service over a job that was never about it. The answer
    carries `held: False` with the reason rather than an absent key.

    ⚠ **IT RUNS INSIDE THE CALLER'S TRANSACTION, AND THAT IS THE WHOLE OF
    TC-3.** *"A refusal anywhere in step 3 rolls the whole acceptance back — the
    order stays in the queue."* If the template was deactivated and the
    follow-up cannot be raised, the supervisor's Accept must NOT stand: an
    accepted failure with no follow-up is the exact state `BR-WRK-054` exists to
    prevent, and it would be invisible — the order reads *accepted*, correctly,
    and nothing ever raises the return visit.

    ⚠ **SO DO NOT WRAP THIS IN A SAVEPOINT AND DO NOT CATCH ANYTHING** — the
    opposite of hard-won law 14's advice, deliberately. Law 14 is about a loop
    that must SURVIVE one bad row (`bulk_act` over eight orders). This is one
    human act over one order and the correct response to a refusal is to lose
    all of it. A lane "hardening" this with `try/except: pass` would convert a
    loud failure into exactly the silent one the rule is about.

    ⚠ **AND IT IS NOT IDEMPOTENT BY ITS OWN EFFORT — `accept_field_result`'s
    `accepted_at` GUARD IS WHAT STOPS A SECOND FOLLOW-UP** (`J66`: *"Accepting
    `WO-4907` twice → refused; no second follow-up, no second hold"*). That
    guard runs before the transaction opens. A later wave that adds a second
    caller needs its own: this function will happily raise a second `WO-4910`.
    """
    if order.outcome != OUTCOME_FAILED:
        # `US-WRK-034` TC-2 — a `passed` outcome raises nothing and holds
        # nothing. `partially_done` and `waiting_on_someone_else` are also not
        # `failed`: the rule names ONE token, and widening it here would be this
        # module inventing signed law.
        return None

    reason = _failure_reason(order)
    follow_up = create_work_order(
        actor,
        None,
        {
            "connection_id": str(order.connection_id) if order.connection_id else None,
            "premises_id": str(order.premises_id) if order.premises_id else None,
            "account_id": str(order.account_id) if order.account_id else None,
            "asset_id": str(order.asset_id) if order.asset_id else None,
            "unit_id": str(order.unit_id) if order.unit_id else None,
            "type": order.type,
            "scope": order.scope,
            # `DEF-WRK-9647` — `create_work_order` reads the service CODE under
            # `service`; it read `service_id` here, a key nothing reads, so every
            # follow-up was raised with no service and a service filter could
            # not find it (WO-0049, *Service —*).
            "service": order.service.code if order.service_id else None,
            "mode": order.mode,
            "template_id": str(order.template_id) if order.template_id else None,
            # `J66`: *"`is_gate` TRUE (the follow-up carries the gate)"*. A gas
            # light-up that failed is still the gate for gas — the RETRY is what
            # the service now waits on, and dropping the flag would let the
            # failed order's siblings activate the service.
            "is_gate": order.is_gate,
            "blocked_by": str(order.id),
            "follows_order_id": str(order.id),
            "source": SOURCE_FAILED_OUTCOME,
            "source_ref": order.order_no,
        },
    )
    _shape_retry_by_rule(actor, follow_up["id"], order.template_id)
    if order.connection_id:
        hold_connection(actor, order.connection_id, reason=reason)
        held: dict[str, Any] = {"held": True, "waiting_on": reason}
    else:
        held = {"held": False, "reason": "no_connection_to_hold"}
    _audit(
        actor,
        "work_order.failed_outcome_chain",
        "work_order",
        order.id,
        after={
            "follow_up_order_no": follow_up["order_no"],
            "waiting_on": reason if order.connection_id else None,
            "br_ref": "BR-WRK-054",
        },
    )
    return {
        "follow_up": {"id": follow_up["id"], "order_no": follow_up["order_no"]},
        "reason": reason,
        **held,
        "br_ref": "BR-WRK-054",
    }


def _shape_retry_by_rule(
    actor: Any, follow_up_id: Any, template_id: Any, process: str = SOURCE_FAILED_OUTCOME
) -> dict[str, Any] | None:
    """`CR-168-BRC10` P3.35 — a Work rule on *a job is accepted as failed*
    naming this template sets the retry's priority and assignee. **Never a
    second job**: the retry is the one `BR-WRK-054` already raised above.

    Resolved BY NAME (`apps.work.rules.shape_by_rule`) — Work writes its own
    columns through its own seam, metering imports nothing of Work's. A rule
    that cannot be applied must not lose the acceptance (the retry exists
    either way), so it runs in its own SAVEPOINT (hard-won law 14) and a
    failure is logged, not raised.
    """
    import logging
    from importlib import import_module

    if not template_id:
        return None
    try:
        shape = getattr(import_module("apps.work.rules"), "shape_by_rule", None)
    except ImportError:  # pragma: no cover - work ships in this repo
        return None
    if shape is None:
        return None
    try:
        with transaction.atomic():
            shaped = shape(actor, follow_up_id, process, template_id)
    except Exception:  # noqa: BLE001 — the retry stands without its rule's shape
        logging.getLogger("smartbillhub.metering").exception(
            "the failed-job retry %s could not take its rule's priority and assignee",
            follow_up_id,
        )
        return None
    if shaped and shaped.get("pending"):
        rules = import_module("apps.work.rules")
        transaction.on_commit(lambda: rules._push_pending(actor, shaped["pending"]))
    return shaped


def _failure_reason(order: Any) -> str:
    """What the crew said went wrong — *pressure test failed at 2.1 bar*.

    ⚠ **THE REASON IS THE CREW'S SENTENCE, NOT A WORD THIS MODULE CHOOSES.** It
    becomes `connections.waiting_on`, which `Work-001` draws to a clerk verbatim
    and which is the only thing on that screen explaining why a build stopped. A
    generic *"a work order failed"* would be true, useless, and would replace
    the one sentence somebody actually needs to read.

    `field_data` is free-shaped by `BR-MET-109`, so the sentence is looked for
    under the keys the field app actually writes, in order; the fallback names
    the ORDER rather than pretending to a reason it does not have.
    """
    data = order.field_data if isinstance(order.field_data, dict) else {}
    for key in ("failure_reason", "reason", "outcome_note", "note"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"{order.order_no or 'a work order'} failed"


def dispatch_communication(actor: Any, work_order_id: Any) -> dict[str, Any]:
    """**BR-MET-115's third consequence — and `OQ-372` is CLOSED.**

    PO 2026-08-25, asked which of a build's seven work orders sends the customer
    letter: **"When Utility user mark it as complete using button on screen"**.

    ✅ **THE ANSWER IS THAT THE SYSTEM NEVER RANKS THE ORDERS.** The question
    offered three derivations — the service's GATE order, the LAST order, or a
    per-template choice — and the PO chose none of them. **A person presses a
    button, and that press is the send.** Whichever order a utility user marks
    complete, the letter goes then, and the utility carries the judgement of
    when to press it.

    ✅ **AND "MARK COMPLETE" IS THE ACCEPTANCE THAT ALREADY EXISTS**, which is
    why no new action was invented for it. `BR-MET-110`'s own PO quote is
    *"utility staff will review these work order, accept them and use data from
    them to activate these services **or confirm the installation is
    completed**"* — accepting IS confirming completion. One act, one button,
    already built as `accept_field_result`.

    ⚠ **THE FOOTGUN THIS CREATES IS THE UTILITY'S, DELIBERATELY, AND IT IS
    WRITTEN DOWN RATHER THAN DESIGNED AROUND.** `CON-26-0117` carries seven
    orders across twenty-five units. Under this rule, accepting order three of
    seven sends the letter for that order's service. That is the cost of the
    system not guessing, the PO was shown the figure before ruling, and the
    guard against it is a person reading the screen — not a rule this module
    invents.

    ⛔ **NO SUCH BUTTON IS DRAWN ANYWHERE.** `NCT-02`'s actions are `Continue
    setup →`, `Add work order` and `Cancel`; the work-order detail screen that
    would carry a completion control is task **6.14**, deferred as **D1**. So
    the trigger is ruled and built and **has no surface** — reported, not
    papered over.

    **What this does:** queues the customer piece through the ONE cross-module
    door (`seams.queue_document` → `outbound_messages`, B2 r16 #7). Delivery is
    in-app, the only adapter that exists, on `BR-CUS-100`'s reasoning for the
    disconnect notice — the message travels the same queue and the same seam
    every other channel will travel, and nothing here changes when email and
    print arrive.

    **What it refuses:** a second send for the same order (a letter cannot be
    unsent, so re-pressing must not re-send), and any send at all on a cancelled
    connection.

    ⚠ **IT NEVER REPORTS A NOTIFICATION IT DID NOT QUEUE.** If the seam is
    unwired the return says so plainly, because a caller that claims *"customer
    notified"* over a missing row is the defect `queue_document`'s own docstring
    was written against.
    """
    order = _work_order_or_404(work_order_id)
    _refuse_if_cancelled(order.connection)
    if order.accepted_at is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-115",
            message_key="metering.work_order_not_accepted_for_send",
            params={"order_no": order.order_no or ""},
        )
    stamp = dict(order.field_data or {})
    if stamp.get(SEND_STAMP):
        return {
            "id": str(order.id),
            "queued": False,
            "already_sent": True,
            "br_ref": "BR-MET-115",
        }
    #: ⛔ **THE PLATFORM HAS NO WRITER FOR A CONNECTION MESSAGE, AND THAT IS A
    #: REFUSAL WE REPORT RATHER THAN ROUTE AROUND.** `queue_document`'s source
    #: vocabulary is a CONSTANT and its own words are that *"a tenant cannot
    #: invent a source the platform has no writer for, and a row nothing
    #: recognises is a message nothing will ever send."* `connection` is not in
    #: it.
    #: ⚠ **THIS LISTED EIGHT KINDS UNTIL 2026-09-05 AND THERE ARE TWELVE** —
    #: `move` and `account` arrived 2026-08-30, `portal` on 2026-09-04 and
    #: `appointment` on 2026-09-05. The COUNT is not what this paragraph turns
    #: on, which is why it went stale unnoticed: the argument is that
    #: `connection` is absent, and it still is. Read
    #: `notifications.models.SOURCE_TYPES` for the list rather than this
    #: sentence — a vocabulary quoted in prose is a second copy free to
    #: disagree with the first.
    #:
    #: **The tempting fix is to send it as `notice`, and that would be wrong.**
    #: The kind is what reports group by and what the renderer dispatches on, so
    #: a "your service is live" letter filed as a disconnect-style notice is a
    #: misclassification that only shows up in somebody's monthly figures. →
    #: **OQ-376**: the platform vocabulary needs `connection`, and a connection
    #: message needs a template before it has a writer at all.
    #:
    #: So the trigger is RULED and BUILT and the queue refuses it today. That is
    #: reported on the return, never swallowed.
    #: ⚠ **AN ORDER WITH NO BUILD SENDS NOTHING, AND SAYS SO (`DEF-WRK-3635`).**
    #: `BR-MET-115`'s letter is *"your service is live"* — a sentence about a NEW
    #: CONNECTION. A leak investigation on a meter that has been in the ground
    #: for years has no such moment: nothing was connected, and the customer is
    #: already a customer. The three lines below read `order.connection.*`
    #: unguarded and raised `AttributeError` — a 500 on the acceptance itself —
    #: for the whole day between `metering/0044` and this fix.
    #:
    #: **The tempting fix is to send it anyway with the premises in place of the
    #: build, and that would be worse than the crash**: it would tell somebody
    #: their service is live because a leak was investigated. WHICH letter a
    #: job-without-a-build sends, if any, is nobody's ruling yet — it is
    #: `OQ-WRK-1495`'s neighbourhood and `OQ-376` is not even answered for the
    #: build case. So this reports *not sent, and here is why*, in the same shape
    #: the queue refusal below already uses, and invents no piece.
    if order.connection_id is None:
        return {
            "id": str(order.id),
            "queued": False,
            "no_connection": True,
            "reason": "work_order_has_no_connection",
            "br_ref": "BR-MET-115",
        }
    try:
        queued = seams.queue_document(
            source_type="connection",
            source_id=order.connection_id,
            channels=("in_app",),
            account_id=order.connection.owner_account_id,
            actor=actor,
            category="new_connect_service_live",
            render_context={
                "connection_no": order.connection.connection_no,
                "order_no": order.order_no,
                "service": getattr(order.service, "code", None),
            },
        )
    except tuple(seams.queue_refusals()) as refused:
        return {
            "id": str(order.id),
            "queued": False,
            "already_sent": False,
            "unavailable": str(refused),
            "tracks": "OQ-376",
            "br_ref": "BR-MET-115",
        }
    if queued is None:
        # ⚠ **THIS SENTENCE SAID `"notifications.queue_document is not wired"`
        # UNTIL 2026-09-16 AND HAD BEEN FALSE FOR WEEKS (`DEF-MET-5456`).**
        # `apps.notifications.services.queue_document` IS published, so
        # `seams.queue_document` resolves it and this branch is a DEFENSIVE
        # guard rather than a description of the product — measured twice
        # before this edit: the function exists at `services.py:1306`, and it
        # has no `return None` on any path, so nothing reachable produces this
        # today.
        #
        # **The branch is kept and only the sentence is corrected.** The seam's
        # own contract still allows `None` — *"Unwired ⇒ None ⇒ THE CALLER
        # REPORTS THAT NOTHING WAS QUEUED"* — so deleting the guard would trade
        # a false sentence for a missing one, and a caller that assumed a row
        # existed would go on to stamp the order as sent. What it may no longer
        # do is NAME A CAUSE IT HAS NOT CHECKED: it reports what it observed.
        #
        # ⚠ **THIS IS WHY IT MATTERED.** A comment that outlived its truth is
        # exactly what `DEF-MET-5441` cost — the wizard's Create button posting
        # to a 404 because a note said a door did not exist. Hard-won law 1 cuts
        # both ways: a comment claiming an ABSENCE is not the absence either.
        return {
            "id": str(order.id),
            "queued": False,
            "unavailable": "the notifications door returned no message row",
            "br_ref": "BR-MET-115",
        }
    stamp[SEND_STAMP] = True
    order.field_data = stamp
    order.save(update_fields=["field_data", "updated_at"])
    _audit(
        actor,
        "connection.communication_sent",
        "work_order",
        order.id,
        after={"channel": "in_app", "br_ref": "BR-MET-115"},
    )
    return {"id": str(order.id), "queued": True, "already_sent": False, "br_ref": "BR-MET-115"}


def mark_outstanding(
    actor: Any,
    connection_id: Any,
    *,
    title: str,
    detail: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """**BR-MET-114 — a person adds an item to `Outstanding work`.**

    PO 2026-08-25: *"human will mark everything to start with"*. `source` is
    stamped `human` and the actor is recorded, because the sentence a person
    wrote — *"Left off, **because** common area has no water service"* — is the
    thing the ruling exists to keep, and an unattributed reason is half a reason.

    ⚠ **This never blocks.** The wizard's own sentence is *"none of them block
    creating the connection"*, and there is deliberately no flag that could say
    otherwise.
    """
    connection = _connection_or_404(connection_id)
    _refuse_if_cancelled(connection)
    label = str(title or "").strip()
    if not label:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.todo.title_required",
            field_errors=[{"field": "title", "message_key": "metering.todo.title_required"}],
        )
    # `CR-162-BRC10` — a NOTE rides the same door (PO 2026-10-02: *"in to do
    # also keep notes"*). Absent means a to-do, which is every caller before it.
    row_kind = str(kind or ConnectionTodo.KIND_TODO).strip().lower()
    if row_kind not in ConnectionTodo.KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.todo.kind_unknown",
            field_errors=[{"field": "kind", "message_key": "metering.todo.kind_unknown"}],
        )
    row = ConnectionTodo.objects.create(
        tenant_id=_tenant_id(),
        connection=connection,
        title=label,
        detail=str(detail).strip() if detail else None,
        source=ConnectionTodo.SOURCE_HUMAN,
        kind=row_kind,
        marked_by=_user_or_none(actor),
        marked_at=timezone.now(),
        is_sample=connection.is_sample,
    )
    _audit(
        actor,
        "connection_note.added" if row_kind == ConnectionTodo.KIND_NOTE else "connection_todo.marked",
        "connection_todo",
        row.id,
        after={"title": label, "kind": row_kind},
    )
    return {"id": str(row.id), "title": row.title, "kind": row_kind, "blocks_creation": False}


def close_outstanding(actor: Any, todo_id: Any) -> dict[str, Any]:
    """**BR-MET-114's other half: only a PERSON closes one.**

    The ruling leaves the door open for the system to SUGGEST items later. It
    does not open the door to the system CLOSING one — that would be the reason
    half of the drawn item 3 disappearing again, which is the failure the whole
    rule was chosen to avoid. So this refuses without an actor, by name.
    """
    who = _user_or_none(actor)
    if who is None:
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-MET-114",
            message_key="metering.todo.human_close_required",
            params={},
        )
    row = ConnectionTodo.objects.filter(tenant_id=_tenant_id(), id=todo_id).first()
    if row is None:
        raise errors.NotFoundError("connection_todo", str(todo_id))
    if row.kind == ConnectionTodo.KIND_NOTE:
        # `CR-162-BRC10` — a note is never done; only a to-do closes.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-114",
            message_key="metering.todo.a_note_is_not_done",
            params={},
        )
    if row.closed_at is not None:
        return {"id": str(row.id), "closed_at": row.closed_at.isoformat(), "already_closed": True}
    row.closed_by = who
    row.closed_at = timezone.now()
    row.save(update_fields=["closed_by", "closed_at", "updated_at"])
    _audit(actor, "connection_todo.closed", "connection_todo", row.id, after={"title": row.title})
    return {"id": str(row.id), "closed_at": row.closed_at.isoformat(), "already_closed": False}


def outstanding_work(connection_id: Any) -> list[dict[str, Any]]:
    """Every open item on a connection, oldest first. Never derived — BR-MET-114."""
    rows = (
        ConnectionTodo.objects.filter(
            tenant_id=_tenant_id(), connection_id=connection_id, closed_at__isnull=True
        )
        .exclude(kind=ConnectionTodo.KIND_NOTE)
        .order_by("created_at")
    )
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "detail": row.detail,
            "source": row.source,
            "blocks_creation": False,
        }
        for row in rows
    ]


# ── CR-162-BRC10 · the To-do tab: to-dos AND notes, reopen, edit your note ──
def reopen_outstanding(actor: Any, todo_id: Any) -> dict[str, Any]:
    """`CR-162-BRC10` item 9 (Q3) — a to-do marked Done by mistake comes back.

    A person's act, like closing (`BR-MET-114`): refused without an actor. The
    closing stamp is cleared and the audit row keeps who closed it and when,
    so the history is not lost by reopening. A note is never closed, so it
    cannot be reopened either."""
    who = _user_or_none(actor)
    if who is None:
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-MET-114",
            message_key="metering.todo.human_close_required",
            params={},
        )
    row = ConnectionTodo.objects.filter(tenant_id=_tenant_id(), id=todo_id).first()
    if row is None:
        raise errors.NotFoundError("connection_todo", str(todo_id))
    _refuse_if_cancelled(row.connection)
    if row.kind == ConnectionTodo.KIND_NOTE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-114",
            message_key="metering.todo.a_note_is_not_done",
            params={},
        )
    if row.closed_at is None:
        return {"id": str(row.id), "reopened": False}
    before = {
        "closed_at": row.closed_at.isoformat(),
        "closed_by": str(row.closed_by_id) if row.closed_by_id else None,
    }
    row.closed_by = None
    row.closed_at = None
    row.save(update_fields=["closed_by", "closed_at", "updated_at"])
    _audit(
        actor,
        "connection_todo.reopened",
        "connection_todo",
        row.id,
        before=before,
        after={"title": row.title},
    )
    return {"id": str(row.id), "reopened": True}


def update_note(actor: Any, todo_id: Any, *, title: str) -> dict[str, Any]:
    """`CR-162-BRC10` item 48 — a clerk corrects THEIR OWN note.

    The account notes' convention (`BR-CUS-035`, `AccountNote`): an audited
    edit with the whole before/after, and NO delete. Only the note's author may
    edit it; anybody else is refused by name, because a note is a sentence a
    person signed."""
    who = _user_or_none(actor)
    row = ConnectionTodo.objects.filter(tenant_id=_tenant_id(), id=todo_id).first()
    if row is None:
        raise errors.NotFoundError("connection_todo", str(todo_id))
    _refuse_if_cancelled(row.connection)
    if row.kind != ConnectionTodo.KIND_NOTE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-114",
            message_key="metering.todo.only_a_note_is_edited",
            params={},
        )
    if who is None or row.marked_by_id != getattr(who, "id", None):
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-MET-114",
            message_key="metering.todo.only_the_author_edits",
            params={},
        )
    text = str(title or "").strip()
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.todo.title_required",
            field_errors=[{"field": "title", "message_key": "metering.todo.title_required"}],
        )
    before = {"title": row.title}
    row.title = text
    row.save(update_fields=["title", "updated_at"])
    _audit(
        actor,
        "connection_note.updated",
        "connection_todo",
        row.id,
        before=before,
        after={"title": text},
    )
    return {"id": str(row.id), "title": row.title, "kind": row.kind}


def todo_list(connection_id: Any, *, viewer: Any = None) -> dict[str, Any]:
    """`GET /connections/{id}/todos` — the To-do tab: every to-do (open and
    done) and every note, NEWEST FIRST, each saying which it is, who wrote it
    and when (PO: *"notes and to-dos appear together, newest first, each marked
    'Note' or 'To-do'"*). Plus the two counts the Overview's summary reads.

    `mine` says whether the viewer wrote the row, so the screen offers *Edit*
    on the viewer's own notes only — a flag, never the author's id (B14 rule
    31)."""
    connection = _connection_or_404(connection_id)
    rows = list(
        ConnectionTodo.objects.filter(tenant_id=connection.tenant_id, connection_id=connection.id)
        .select_related("marked_by", "closed_by")
        .order_by("-created_at", "-id")
    )
    me = _user_or_none(viewer)
    my_id = getattr(me, "id", None)

    def _who(user: Any) -> str | None:
        if user is None:
            return None
        return getattr(user, "full_name", None) or getattr(user, "email", None) or None

    out = [
        {
            "id": str(row.id),
            "kind": row.kind,
            "title": row.title,
            "detail": row.detail,
            "source": row.source,
            "written_by": _who(row.marked_by),
            "mine": my_id is not None and row.marked_by_id == my_id,
            "written_at": (row.marked_at or row.created_at).isoformat(),
            "done": row.closed_at is not None,
            "done_by": _who(row.closed_by),
            "done_at": row.closed_at.isoformat() if row.closed_at else None,
        }
        for row in rows
    ]
    return {
        "connection_id": str(connection.id),
        "rows": out,
        "todos_open": sum(
            1 for r in out if r["kind"] == ConnectionTodo.KIND_TODO and not r["done"]
        ),
        "notes": sum(1 for r in out if r["kind"] == ConnectionTodo.KIND_NOTE),
    }


def add_unit_to_build(actor: Any, connection_id: Any, payload: Any) -> dict[str, Any]:
    """`CR-162-BRC10` item 7 (T2-7) — *Add unit* on a committed build: a new
    unit at the build's premises, with the services it will take.

    Two owners' doors, in one transaction: `metering.services.create_unit`
    (the S16 unit wizard's own door — label uniqueness, the unit number series,
    the route cascade, the service points, the `unit.created` audit row) and
    `add_connection_service` for each service (one `connection_services` row
    per unit × service, `pending` until activated). No meter is fitted and no
    plan is assigned here: the unit's own page does both, and an activation
    later installs whatever is earmarked. A draft build has the wizard for
    this, so a draft is refused; so is a cancelled one."""
    connection = _connection_or_404(connection_id)
    _refuse_if_cancelled(connection)
    if connection.submitted_at is None or connection.premises_id is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-112",
            message_key="metering.activation.build_is_a_draft",
            params={"connection_no": connection.connection_no or ""},
        )
    data = metering_services._payload_dict(payload)
    services = [str(code) for code in (data.get("services") or []) if code]
    if not services:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.build.unit_needs_a_service",
            field_errors=[
                {"field": "services", "message_key": "metering.build.unit_needs_a_service"}
            ],
        )
    # ⊕ **`DEF-MET-9262` — THE BUILD'S OWN SERVICES, AND ONLY THOSE.** The form
    # offered all eleven and this door took any the ADDRESS offers, so a unit
    # could join a battery-and-solar build taking water. Bringing a NEW service
    # to the build is *Add service*'s job (`add_connection_service`), which
    # this door already uses for each of the unit's own.
    carried = set(
        ConnectionService.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        ).values_list("service__code", flat=True)
    )
    for code in services:
        if code not in carried:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="metering.build.unit_service_not_on_build",
                params={"service": code},
                field_errors=[
                    {
                        "field": "services",
                        "message_key": "metering.build.unit_service_not_on_build",
                        "params": {"service": code},
                    }
                ],
            )
    with transaction.atomic():
        unit = metering_services.create_unit(
            actor,
            {
                "premises_id": str(connection.premises_id),
                "label": data.get("label"),
                **({"unit_type": data["unit_type"]} if data.get("unit_type") else {}),
                "services": services,
            },
        )
        added = [
            add_connection_service(actor, connection.id, service_code=code, unit_id=unit["id"])
            for code in services
        ]
        _audit(
            actor,
            "connection.unit_added",
            "connection",
            connection.id,
            after={"unit_id": unit["id"], "label": unit.get("label"), "services": services},
        )
    connection.refresh_from_db()
    return {
        "id": str(connection.id),
        "unit_id": unit["id"],
        "label": unit.get("label"),
        "services": [row["service"] for row in added],
        "connection_state": connection.state,
    }


def _check_mode(mode: str) -> None:
    """§8.3's three modes, with the deferred one refused BY NAME.

    ⛔ `we_schedule` is drawn and deferred: *"Later — the Work module is R5
    (OQ-249)"*. Crew, skill, date, priority, dispatch and field completion are a
    dispatch board, and OQ-249 (*is Work a tenth module?*) is OPEN. A stub is the
    honest answer; a half-built scheduler is not.
    """
    if mode == MODE_WE_SCHEDULE:
        raise NotImplementedError(
            "OQ-249: the 'we schedule it' dispatch mode needs the Work module "
            "(crew · skill · date · priority · dispatch · field completion). "
            "B18 §8.3 defers it to R5; 'our crew did it' and 'external system' ship in v1."
        )
    if mode not in WORK_ORDER_MODES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.work_order_mode_unknown",
            params={"mode": mode},
        )


# ════════════════════════════════════════════════════════════════════════════
# SERVICE CHARACTERISTICS (task 6.9 · BR-MET-108)
# ════════════════════════════════════════════════════════════════════════════
def set_characteristic(
    actor: Any,
    unit_id: Any,
    *,
    service_code: str,
    key: str,
    value: str,
    unit_of_measure: str,
) -> dict[str, Any]:
    """Record one characteristic of a unit's relationship to a service.

    `unit_of_measure` is REQUIRED and is refused when blank — hard rule 3, and
    the reason BR-MET-108 rejected a column per service: a number whose unit is
    implied by an identifier is a number nothing can validate or migrate.
    """
    tenant_id = _tenant_id()
    unit = metering_models.Unit.objects.filter(tenant_id=tenant_id, pk=unit_id).first()
    if unit is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    service = _service_row(service_code)
    cleaned_key = str(key or "").strip()
    cleaned_value = str(value if value is not None else "").strip()
    cleaned_uom = str(unit_of_measure or "").strip()
    field_errors = []
    if not cleaned_key:
        field_errors.append(
            metering_services._field_error(
                "key", errors.VAL_REQUIRED, "metering.characteristic.key_required"
            )
        )
    if not cleaned_value:
        field_errors.append(
            metering_services._field_error(
                "value", errors.VAL_REQUIRED, "metering.characteristic.value_required"
            )
        )
    if not cleaned_uom:
        # THE ONE THAT MATTERS. A blank unit of measure is how `2450` becomes a
        # number nobody can price — square feet, square metres or acres.
        field_errors.append(
            metering_services._field_error(
                "unit_of_measure",
                errors.VAL_REQUIRED,
                "metering.characteristic.uom_required",
            )
        )
    metering_services._refuse_fields(field_errors)
    with transaction.atomic():
        row, created = ServiceCharacteristic.objects.update_or_create(
            tenant_id=tenant_id,
            unit=unit,
            service=service,
            key=cleaned_key,
            defaults={
                "value": cleaned_value,
                "unit_of_measure": cleaned_uom,
                "is_sample": unit.is_sample,
            },
        )
        _audit(
            actor,
            "service_characteristic.recorded" if created else "service_characteristic.updated",
            "service_characteristic",
            row.id,
            after={
                "unit_id": str(unit.id),
                "service": service.code,
                "key": cleaned_key,
                "value": cleaned_value,
                "unit_of_measure": cleaned_uom,
            },
        )
    return {
        "id": str(row.id),
        "key": row.key,
        "value": row.value,
        "unit_of_measure": row.unit_of_measure,
        "created": created,
    }


def characteristic(unit_id: Any, service_code: str, key: str) -> ServiceCharacteristic | None:
    """The row, or None. **None means NO CHARACTERISTIC RECORDED** — it does not
    mean the unit does not take the service, and it never means zero. Whether
    the service is taken is answered where it already lives (the tenant's own
    service list and the unit's service points)."""
    tenant_id = _tenant_id()
    return ServiceCharacteristic.objects.filter(
        tenant_id=tenant_id,
        unit_id=unit_id,
        service__code=service_code,
        key=str(key or "").strip(),
    ).first()


#: **BR-MET-108 AS AMENDED — PO 2026-08-25, verbatim: *"Bill it as zero"*.**
#: The reason stamped on a line that was priced at zero because the number the
#: charge needed was never recorded. It exists as a CONSTANT rather than a
#: message string because billing must be able to FILTER on it: the ruling is to
#: bill zero, and billing zero *silently* is not what was ruled.
PRICED_AT_ZERO_ABSENT_CHARACTERISTIC = "characteristic_absent"


# ── CR-062 D6 · WHICH CAPACITY SERVICE READS ITS QUANTITY OFF THE UNIT ──────
#: **PO RULING 2026-09-02, verbatim: *"In case of strom water - we have to take
#: it from Unit - B ⭐ Take the size from the property, not from equipment.
#: Storm water becomes the one capacity service whose quantity comes from the
#: premises"*.**
#:
#: They chose option B of three **and corrected it in the same sentence**: the
#: option as written said *from the property*; the ruling says **from the
#: UNIT**. A bill is for an account, an account serves a unit, and every other
#: quantity on that bill is a unit fact — so on the premises storm water would
#: be the only line needing to be divided down before it could be charged, and
#: the apartment block is where that goes wrong first (6 units, one figure, no
#: ruled way to split it). **Do not flatten this back to "the premises".**
#:
#: ⚠ **WHY THIS MAP EXISTS AT ALL, WHICH IS THE PART A LATER LANE WILL WANT TO
#: "TIDY AWAY".** Every other capacity service reads its quantity off INSTALLED
#: EQUIPMENT — solar has panels, battery has batteries, broadband has modems,
#: trash has carts, and each carries its size on the device (`BR-AST-500`).
#: **Storm water has nothing.** An ERU measures hard surface on a property; it
#: is not equipment and nobody installs one, so the sum was `0` on every unit
#: and the line printed `$0.00` on a document that footed (`DEF-2388`). The
#: ruling says that difference **is what the service is**, not an inconsistency
#: to be reconciled later. A change that made the other four read a unit field
#: would have implemented the ruling and broken four working services, three of
#: which started billing real money the same day.
#:
#: ⚠ **THE UNIT OF MEASURE IS NOT IN THE KEY NAME, AND THAT IS BR-MET-108's OWN
#: THIRD ARGUMENT.** The key is `assessment` and the row's `unit_of_measure`
#: carries `ERU`. `eru` as a key would be the `storm_impervious_sqft` mistake in
#: shorter letters — a unit encoded in an identifier that nothing can validate,
#: compare or migrate.
#:
#: ⚠ **THIS IS NOT AN ANSWER TO `OQ-370` AND MUST NOT BE READ AS ONE.** That
#: question asks which keys EVERY flat service has and what a settings form
#: offers, and it warned in terms that a hardcoded map *"decides pricing"* —
#: naming `storm_water → impervious_area` as an example of a pricing rule
#: nobody had ruled on. **Storm water's pricing rule has now been ruled**
#: (capacity, per ERU, read from the unit), so this one entry is a CONSEQUENCE
#: of that ruling rather than a lane choosing. Trash's and broadband's keys are
#: still unruled, `required_characteristic_keys` still refuses, and nothing here
#: enumerates a second service.
#
# ── CR-080 · THERMAL/HEAT JOINS IT ON 2026-09-07, AND FOR STORM WATER'S OWN
#    REASON RATHER THAN BY ANALOGY ─────────────────────────────────────────
# PO verbatim, 2026-09-07: *"connected tonnage - it is capacity not metering;
# i will ahve 100 tonne or 200 tonne etc"*.
#
# **NOBODY INSTALLS A TON.** A connected tonnage is the SIZE OF THE BUILDING'S
# SERVICE CONNECTION — how much cooling the utility has agreed to stand ready
# to deliver — exactly as an ERU measures hard surface on a property. There is
# no device to carry it: the chiller is the utility's, in the plant, serving
# hundreds of buildings, and a heat exchanger in a basement is not sized "per
# customer" in any way this product records. Route thermal down the equipment
# path and `billable_asset_size_classes` returns an empty list on every unit,
# `total_installed_capacity` sums to `0`, and every thermal line prints
# **`$0.00`** on a document that foots perfectly — `DEF-2388` exactly, one
# service over, and no check in this repo can see it.
#
# ⚠ **SO THIS IS TWO SERVICES NOW AND NOT "STORM WATER'S SPECIAL CASE".** The
# sentence above this map that reads *"`None` for the other ten"* is `unit_
# capacity_key`'s and has been amended with it. What has NOT changed is the
# other nine: solar has panels, battery has batteries, broadband has modems,
# trash has carts, fire has lines, and each carries its size on the device.
#
# ⚠ **THE KEY IS `connected_capacity` AND THE UNIT IS NOT IN IT** — the same
# BR-MET-108 argument storm water's `assessment` carries two paragraphs up. The
# row's `unit_of_measure` holds `ton`; a key called `tons` would be a unit
# encoded in an identifier that nothing can validate, compare or migrate.
UNIT_CAPACITY_CHARACTERISTIC: dict[str, str] = {
    "storm_water": "assessment",
    "thermal_heat": "connected_capacity",
}


def unit_capacity_key(service_code: str) -> str | None:
    """The characteristic key this service's capacity is recorded under on the
    UNIT, or `None` when its capacity comes from installed equipment instead.

    `None` is the answer for NINE of the eleven services and is a FINISHED one —
    *"ask the equipment"* — never *"there is no capacity"*.

    ⚠ **IT SAID "TEN OF THE ELEVEN" UNTIL 2026-09-07.** `CR-080` moved thermal
    /heat from metered to capacity on the PO's ruling, and its connected
    tonnage is a unit fact for the same reason storm water's ERU is: nobody
    installs a ton. Two services answer a key now; the map above says why.
    """
    return UNIT_CAPACITY_CHARACTERISTIC.get(str(service_code or "").strip())

#: ⚠ **BR-MET-115's "sent once" marker, kept on the order's own `field_data`.**
#: A letter cannot be unsent, so a second press of the same button must not
#: produce a second letter. It lives here rather than in a new column because it
#: is one boolean about one order, and a column would need a migration to say
#: what a key already says. If a send ever needs a TIME or a recipient, that is
#: a column and this note is the record of why it was not one first.
SEND_STAMP = "br_met_115_communication_sent"


@dataclass(frozen=True)
class CharacteristicReading:
    """What a charge gets when it asks a unit for a pricing characteristic.

    Always answers. **Never raises for an absence** — that is the whole point of
    the amendment. `absent` and `priced_at_zero` are the two facts a bill line
    must carry forward so the zero can be explained afterwards.
    """

    unit_id: str
    service: str
    key: str
    value: Decimal | None
    unit_of_measure: str | None
    absent: bool
    priced_at_zero: bool
    reason: str | None
    br_ref: str = "BR-MET-108"

    def as_stamp(self) -> dict[str, Any]:
        """The dict a bill line stores so the zero is explainable months later."""
        return {
            "service": self.service,
            "key": self.key,
            "unit_id": str(self.unit_id),
            "absent": self.absent,
            "priced_at_zero": self.priced_at_zero,
            "reason": self.reason,
            "br_ref": self.br_ref,
        }


def characteristic_for_pricing(unit_id: Any, service_code: str, key: str) -> CharacteristicReading:
    """The value a charge should price on, and **zero when nothing is recorded**.

    ⚠ **THIS REVERSES THIS MODULE'S PREVIOUS BEHAVIOUR, AND THE REVERSAL IS A PO
    RULING, NOT A REFACTOR.** `characteristic_or_refuse()` used to raise
    `BIZ_COMPLETENESS` on an absence, implementing BR-MET-108's original closing
    sentence: *"A service whose characteristic is required and absent must REFUSE
    with the absence named, never price it at zero."* On 2026-08-25 the PO was
    shown that sentence, and the cost of the alternative, in plain English with
    the worked figure below, and ruled: **"Bill it as zero"**.

    **No finance re-sign was needed and that is not a loophole.** BR-MET-108 is
    AI-authored, CONFIRMED and HUMAN-REVIEW-PENDING under the PO's 2026-08-09
    ruling (*"AI will do it; we will review it later as human"*). **This IS that
    review arriving and ruling differently** — the protocol working as designed.
    A ❄️ FROZEN B4/B5 figure would have gone through HUMAN-GUIDE §6 instead.

    **THE WORKED COST, ON THE RECORD, BECAUSE IT WAS PUT TO THE PO BEFORE THE
    RULING:** a 25-unit building, 24 units carrying a trash container count,
    unit 12 blank. The bill run **completes**. Unit 12's trash line is
    **$0.00**. Nothing errors, the customer pays it, and the shortfall recurs
    every cycle until somebody notices by other means. The build raised that
    objection once, in writing; the PO chose it; it is built as ruled and is not
    re-argued here.

    ⚠ **BILLING ZERO IS THE RULING — BILLING ZERO *SILENTLY* IS NOT.** The
    ruling asks for a figure, not for concealment, and hard rule 7 already
    obliges a money path to record what it did. So the absence is returned
    stamped (`absent`, `priced_at_zero`, `reason`), `as_stamp()` gives billing
    the dict to carry on the line, and `units_priced_at_zero()` below lets a
    utility list every unit this happened to. That is implementing the ruling,
    not softening it.

    ⚠ **AND A TENANT-ISOLATION FAILURE NOW DEGRADES TO A $0.00 LINE INSTEAD OF
    AN ERROR.** `characteristic()` filters on the tenant from context, so a row
    belonging to another tenant is not absent-in-truth, it is
    absent-to-this-tenant — and under the old refusal that surfaced loudly.
    Under the ruling it prices at zero like any other absence. The stamp is what
    keeps it findable; nothing else does. Recorded here because it is a
    consequence of the ruling that nobody chose and a later reader will need.

    ⚠ **UNWIRED (hard-won law 2).** Nothing in `rating` or `billing` calls this
    yet — no flat-service charge reads a characteristic today. This is the seam
    those charges must use when they are built, and until one does, the ruling
    is implemented and **not yet in effect on any bill**. Do not read a green
    test suite as "flat services bill correctly".
    """
    service = str(service_code or "").strip()
    key_name = str(key or "").strip()
    row = characteristic(unit_id, service, key_name)
    if row is None:
        return CharacteristicReading(
            unit_id=str(unit_id),
            service=service,
            key=key_name,
            value=Decimal("0"),
            unit_of_measure=None,
            absent=True,
            priced_at_zero=True,
            reason=PRICED_AT_ZERO_ABSENT_CHARACTERISTIC,
        )
    return CharacteristicReading(
        unit_id=str(unit_id),
        service=service,
        key=key_name,
        value=_numeric_or_none(row.value),
        unit_of_measure=row.unit_of_measure,
        absent=False,
        priced_at_zero=False,
        reason=None,
    )


def _numeric_or_none(raw: Any) -> Decimal | None:
    """A characteristic's value is TEXT in the table, because a speed tier is not
    a number and BR-MET-108's shape is one row for every kind of characteristic.
    A charge that needs arithmetic gets `None` rather than a coerced guess, and
    decides for itself what to do with a non-numeric value."""
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None


def units_priced_at_zero(
    service_code: str, key: str, unit_ids: Iterable[Any]
) -> list[dict[str, Any]]:
    """**THE SURFACING HALF OF THE RULING.** Every unit that takes this service
    and has no `key` recorded — the units whose lines will read $0.00.

    Without this, *"bill it as zero"* and *"lose the money and never find out"*
    are the same behaviour, and the PO ruled the first. A utility runs this
    before a bill run and sees exactly which units to go and measure.

    `unit_ids` is the population to check, and it is a REQUIRED POSITIONAL
    ARGUMENT with no default on purpose: *"which units take this service"* is
    answered by the tenant's own service list and the unit's service points, and
    this module must not re-decide it (BR-MET-108: a missing row means *no
    characteristic recorded*, never *does not take this service*). A default
    here would be this module quietly answering a question that is not its own.
    """
    service = str(service_code or "").strip()
    key_name = str(key or "").strip()
    ids = [str(one) for one in unit_ids]
    recorded = set(
        ServiceCharacteristic.objects.filter(
            tenant_id=_tenant_id(),
            unit_id__in=ids,
            service__code=service,
            key=key_name,
        ).values_list("unit_id", flat=True)
    )
    recorded = {str(one) for one in recorded}
    return [
        {
            "unit_id": one,
            "service": service,
            "key": key_name,
            "reason": PRICED_AT_ZERO_ABSENT_CHARACTERISTIC,
            "br_ref": "BR-MET-108",
        }
        for one in ids
        if one not in recorded
    ]


def required_characteristic_keys(service_code: str) -> frozenset[str]:
    """WHICH characteristic keys a service has, and in what units.

    **UNANSWERED — and the question has a registered number now.** This used to
    raise `CharacteristicRequirementUnsigned` in prose, because BR-MET-108 left
    the gap and no open question covered it, and minting an OQ-### from inside
    code is what G8 clause B exists to stop. **`OQ-370` was registered on
    2026-08-25**, so the prime directive's ordinary form applies.

    ⚠ **THE PO'S RULING DISSOLVED HALF OF WHAT THIS FUNCTION WAS FOR.** It is no
    longer *"which characteristic must be present before a bill can be
    produced"* — the answer to that is now **none**; an absence bills zero and
    is stamped. What OQ-370 still asks is what a SETTINGS SCREEN and the New
    Connect wizard must offer, because a form cannot ask for *"a
    characteristic"*: it needs named fields with units. The PO gave exactly one
    key set — trash stores `count = 3` and `size = 96 gal` — and that is not a
    catalogue.

    A hardcoded map here would look like configuration and would BE a pricing
    rule: `trash → count` decides that a utility billing purely by container
    SIZE is out of scope, and `storm_water → impervious_area` decides that a
    flat per-premise storm charge is not allowed. Neither has been ruled on.

    ⚠ **HALF OF THAT SECOND EXAMPLE IS NOW STALE, AND IT IS CORRECTED HERE
    RATHER THAN LEFT TO MISLEAD (`CR-062` D6, PO ruling 2026-09-02).** Storm
    water's pricing rule HAS been ruled: its quantity is a CAPACITY in ERU,
    recorded on the UNIT and priced per ERU. So its key is settled — it is
    `UNIT_CAPACITY_CHARACTERISTIC`'s one entry above, `assessment` — and it was
    settled by the Product Owner rather than chosen here. **This function still
    refuses**, because `OQ-370`'s live half is what a SETTINGS FORM and the New
    Connect wizard must OFFER, and one service's key is not a form. Trash's and
    broadband's keys remain unruled.
    """
    raise NotImplementedError("OQ-370")


# ── shared plumbing ─────────────────────────────────────────────────────────
def _tenant_id() -> UUID:
    return metering_services._tenant_id()


def _audit(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """BR-MET-048 — every metering change writes who/when/before→after through
    BE-03. No money moves in this module (connection charges are task 6.10,
    against the developer's master account per BR-CUS-083), so hard rule 7's
    money-action clause never fires here; this is the module rule, not the money
    rule, and the distinction is stated rather than blurred."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=before,
        after=after,
    )


def _connection_or_404(connection_id: Any) -> Connection:
    """The connection, or a 404 — never a 403. HR-1: existence must not leak, so
    another tenant's connection is ABSENT rather than forbidden."""
    row = Connection.objects.filter(tenant_id=_tenant_id(), pk=connection_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _work_order_or_404(work_order_id: Any) -> WorkOrder:
    """The order, or a 404. Same reasoning as `_connection_or_404`."""
    row = (
        WorkOrder.objects.filter(tenant_id=_tenant_id(), pk=work_order_id)
        .select_related("connection")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _refuse_if_cancelled(connection: Connection | None) -> None:
    """A cancelled connection takes no further records — the same refusal, and
    the same message key, the stamping path already uses, so one mistake has one
    message rather than two that differ by accident.

    ⚠ **`None` IS A LAWFUL ARGUMENT AND MEANS "THERE IS NO BUILD TO BE CANCELLED"
    — `DEF-WRK-3635`, CR-070 wave B.** Since `metering/0044` an order stands on
    any of four anchors (`BR-WRK-006`), so a leak investigation on `77 Cedar Ct`
    has no connection at all. This function used to take the row unguarded and
    every caller passed `order.connection`, so the field-result door, the
    acceptance and the letter each raised `AttributeError` — a 500 — on exactly
    the order phase 0 exists to make possible. It could be raised and then never
    closed.

    Passing here is not a loosening of the rule: the rule is *"a cancelled build
    takes no further records"*, and an order with no build is not a record
    against a cancelled build. Its own cancellation is `work_orders.state`, which
    the callers check separately."""
    if connection is not None and connection.cancelled_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-104",
            message_key="metering.connection_cancelled",
            params={"state": CANCELLED},
        )


def _user_or_none(actor: Any) -> Any:
    """The `identity.User` row an actor stands for, or None.

    ⚠ **Returning None is meaningful and is not a fallback.** `BR-MET-114` turns
    on a human being named — the system may suggest an outstanding item later
    but must never CLOSE one — so `close_outstanding()` reads a None here as a
    refusal, not as a missing nicety.
    """
    from apps.identity import models as identity_models

    user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    if user_id is None:
        return None
    return identity_models.User.objects.filter(pk=user_id).first()


def _service_row(service_code: str) -> Any:
    """The platform 10-service catalog row, refused unless the TENANT runs it —
    the same seam and the same refusal `ensure_service_point` uses, so one
    mistake has one message."""
    from apps.tenancy import models as tenancy_models

    if service_code not in seams.enabled_service_codes():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.service_not_enabled",
            params={"service": service_code},
        )
    row = tenancy_models.Service.objects.filter(code=service_code).first()
    if row is None:  # pragma: no cover - enabled_service_codes reads the same catalog
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.service_not_enabled",
            params={"service": service_code},
        )
    return row


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W6 tasks 6.1 · 6.2 · 6.9 (B18 §5.4/§6.3/§8/§11 W6 + BR-MET-104
#         + BR-MET-108 snapshot 2026-08-25)
# generated: 2026-08-25 by the CR-030 W6 lane S1 (backend half only)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — apps/metering/api.py is not this
#         lane's file; the endpoints of §5.4.6 are REPORTED as owed)
#         E=deferred(NO FRONTEND HALF — r11 step 2b; S86/S87/S88 are tasks
#         6.11-6.13 and this lane states the absence rather than letting it add
#         up) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 migration ordering + RLS;
#         HUMAN-REVIEW-PENDING, and the ledger row is REPORTED because
#         12-governance/09-human-review-ledger.md is not this lane's file)
# gates: see the lane report
# exceptions: (1) `apps/metering/models.py` must import this module for the
#         model registry — one line (the `apps/rating/models.py:1628` precedent),
#         NOT this lane's file, REPORTED and guarded by a deliberately RED test.
#         (1a) THREE COLUMNS ARE NOT IN B18 §5.4.6 AND COME FROM THE PO's
#         SCREENS: `connections.waiting_on` (NCT-01's own column, and NOT the
#         hold's reason — two of five drawn rows wait while not held),
#         `work_orders.is_gate` and `work_orders.template_id` (NCT-01 draws the
#         🚩 on the order). REPORTED as schema beyond the design's column set.
#         (1a-i) ✅ CLOSED 2026-08-25 — the reported divergence on the order's
#         `mode` (this file STAMPS it NOT NULL; §5.4.9 had said *"nullable,
#         inheriting"*) was settled in favour of the stamp and §5.4.9 was
#         amended. Reasoning kept in the model docstring.
#         (1b) NCT-01's `Waiting`/`Done` SEGMENTS are deliberately NOT state
#         tokens — no drawn row carries them — and no segment rule is shipped,
#         because `CON-26-0126` is Partly energised AND waiting on inspection
#         and nothing says which exclusive segment holds it. REPORTED as owed.
#         (1c) Two NCT-02 drawing defects observed and NOT copied (§4 of the
#         module docstring), per CR-028 §11's precedent. (2) The
#         `connection` number series does not exist in core/numbering.py —
#         allocation falls back to a reported warning and a NULL number,
#         REPORTED as owed. (3) Two NEW cross-module FKs (→ customers.
#         service_requests, → assets.assets) drawn by B18 §5.4.6 and REPORTED
#         for B2 §2 interface review. (4) The per-service and work-order state
#         vocabularies are this file's reading of an undrawn set — REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
