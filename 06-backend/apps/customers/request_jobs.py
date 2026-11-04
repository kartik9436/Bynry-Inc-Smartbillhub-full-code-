# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 — *"the service request's own screen is rebuilt to its
#           drawing"*, the APPROVE half. PO ruling 2026-09-15, verbatim:
#           *"pass all information to create the new connect requets or move -in
#           request based on selction"*. Drawn on p083–p084 of
#           `05-prototype/02 Accounts Menu Blueprint.pdf`, read AS IMAGES at
#           scale 2 (B14 rule 42): the modal's five radios each carry their own
#           consequence line, and the `WHAT APPROVING WILL DO` table carries
#           five THEN/WHAT rows, the second of which is *"A build is raised on
#           the New connects tab, naming this request"*.
# Defects:  DEF-CUS-5396 (approving created nothing) ·
#           DEF-MET-5397 (`connections.request_id` existed and nothing filled it)
# Rules:    BR-CUS-080 (the SR alone answers *what happened to this
#           application*; the child carries the link back) · BR-CUS-150/151/152
#           (a move record captures a job that HAS HAPPENED — §3 below) ·
#           BR-CUS-091 (a disconnect is not a move-out) · BR-WRK-055 (the flow
#           completes whether or not the downstream job could be raised — the
#           posture `service_request_service.route` already takes) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4dp stored, 2
#           displayed) · rule 4 (no UPDATE on an issued record) · rule 7 (every
#           money action audits) · B1/B2 §2 (cross-module writes go through the
#           owning module's own door, never its ORM)
# Screens:  the Approve modal (p083–p084) — WAVE 2 renders what `approval_preview`
#           publishes and computes none of it itself.
# Tests:    06-backend/tests/test_cr094_approval_raises_the_job.py
# Impacts:  apps/customers/service_request_service.py (`approve_and_raise`) ·
#           apps/customers/service_request_reads.py (the decision tab carries
#           the preview) · apps/customers/service_request_api.py ·
#           apps/customers/seams.py (`raise_connection_build`) ·
#           apps/customers/moves.py (`record_move` takes the request) ·
#           apps/customers/migrations/0048_cr094_request_raises_the_job.py
# ───────────────────────────────────────────────────────
"""**Approving a service request RAISES THE JOB and carries the request into it.**

PO ruling 2026-09-15, verbatim: *"pass all information to create the new connect
requets or move -in request based on selction"*. The drawing's button reads
**`Approve and raise the build`** and its callout on p082 reads *"Approving this
is what creates the job."*

Until this file existed, approving moved the state to `approved`, stamped who
decided and when, wrote one history line and one audit row, **and created
nothing**. Five queues downstream were fed by a clerk retyping the job.

═══════════════════════════════════════════════════════════════════════════
1 · THE FIVE OUTCOMES, AND WHAT EACH ONE RAISES
═══════════════════════════════════════════════════════════════════════════
Read off the drawn radios (p083–p084, images, scale 2), each with its own
consequence line, and matched to the row this product actually has for it:

| The drawing's words | Row raised | Table | Owner | Lands in |
|---|---|---|---|---|
| A new connection — *"Raises a build on the New connects tab, linked back to this request."* | a build | `connections` | **metering** | `draft` |
| A move-in — *"Opens an account on a unit that already has service."* | — see §3 | `move_records` | customers | — |
| A move-out — *"Closes an account and frees its unit."* | — see §3 | `move_records` | customers | — |
| A transfer — *"One customer, a different address of ours."* | a transfer job | `transfers` | customers | `scheduled`, step 1 of 5 |
| A disconnect — *"Raises a case and starts the notice ladder."* | a case | `disconnect_cases` | customers | `notice_sent` |

⚠ **THE JOB IS RAISED, NOT DONE.** The drawn table's last row is *"Not now — No
account opens, no meter is fitted, nothing is energised"*, and its fourth is
*"Next — The build's own wizard asks for units, services, plans and charges"*.
So every door below creates the row that puts the job on its queue and stops.
Nothing here opens an account, fits a meter, energises a service, posts money or
sends a notice.

═══════════════════════════════════════════════════════════════════════════
2 · NOTHING HERE WRITES ANOTHER MODULE'S TABLE, AND NOTHING COPIES A DOOR
═══════════════════════════════════════════════════════════════════════════
Each outcome is raised through the door its owning module already publishes:

  * `connections` is **metering's** (`apps/metering/connections.py`), so it goes
    through `seams.raise_connection_build` → `metering.connections
    .create_connection`, which already takes a `service_request_id` and has
    since `CR-070` wave B. **It was never called with one.** That door allocates
    the `CON-` number, writes the `connection.created` audit row and reports its
    own warnings; a second creator here would be a second place for
    `BR-MET-1024`'s owner requirement to be relaxed.
  * `transfers` is this module's, and `transfers.start_transfer` is its door: it
    reads the seller from `customer_accounts` (`BR-CUS-054`, never a name
    match), refuses an account nobody occupies, and allocates `TRF-`.
  * `disconnect_cases` is this module's, and `disconnects.open_case` is its
    door: it refuses when the ladder is not running (`_require_running`), reads
    the balance and the tenant's `CHAR(3)` currency, allocates `DSC-` and lands
    the case in `notice_sent` — which IS *"starts the notice ladder"*.

═══════════════════════════════════════════════════════════════════════════
3 · THE MOVE-IN RAISES A PENDING JOB. THE MOVE-OUT STILL RAISES NOTHING.
═══════════════════════════════════════════════════════════════════════════
⚠⚠ **AMENDED 2026-09-16 BY PO RULING — *"it should do B"*.** Everything below
this banner was written on 2026-09-15 and was honest then; **the move-in half of
it is now superseded and is kept, not deleted**, because the reasoning is what
makes the new shape legible and because two lanes cited it in prose the same
week. Read this banner first and the section under it as history.

**WHAT CHANGED.** Approving a move-in now raises a **pending `move_in_jobs`
row** — `apps/customers/move_in_jobs.py`, `BR-CUS-1077` — which appears on the
Move-ins tab at once, names the request it came from, and waits for somebody to
do the job. **Nothing below is contradicted by that**: no account opens,
`move_records` is untouched, and `move_in_jobs` is a THIRD table rather than
either of the two this section ruled out. The PO's own reason for picking it
over handing the clerk into the wizard was that *"the queue stays empty until
somebody finishes the wizard"*, which is the failure `DEF-CUS-5398` reported.

**WHAT DID NOT CHANGE.** The MOVE-OUT. The ruling names the move-in, the walk's
stuck request was a move-in, and widening it would be a lane widening a ruling.
`WIZARD_IS_THE_RECORD` is still the move-out's answer and still exactly true of
`move_records`.

⚠ **AND `outcome_ref` IS NOT WRITTEN FOR A MOVE-IN JOB.** For a move-in that
column already means *the account this application produced* — the fixture
writes `SR-26-0045 → "A-12048"` and `move_reads._requests_by_account_no` reads
it that way to serve the tab's `request #` search leg. Putting a job reference
there would break a leg that works today, so the link runs the other way only:
`move_in_jobs.request_id` names the request, exactly as `connections.request_id`
does. Idempotency therefore comes from that table's own unique constraint rather
than from `ux_service_requests_outcome_ref`, and `raise_job` says so at the line
where it skips `link_child`.

─────────────────────── the 2026-09-15 finding, as written ───────────────────
⛔ **`move_records` CANNOT BE THE RAISED JOB, and three signed things say so.**
Measured against the code on 2026-09-15 rather than assumed from the ruling
(build skill §0 — a written rule is a claim about the product, not evidence):

  1. **It is the record of a move that HAS HAPPENED.** `moves.MoveRecord`'s own
     docstring: *"a move record is written by a flow that has already committed,
     in the same transaction, so there is no in-flight moment for it to
     describe"*, and *"⛔ NOTHING UPDATES A ROW OF THIS TABLE"* (`BR-CUS-152`).
     A row written at approval would state that somebody performed a move-in
     that nobody has performed, and would then be **duplicated** when the wizard
     actually runs — two records for one job, on a table whose correction path
     is a third row.
  2. **It requires the account the job exists to create.** `account_id` is NOT
     NULL with `on_delete=PROTECT`. Raising a move-in would therefore have to
     open an account, and the drawing forbids exactly that in as many words:
     *"No account opens, no meter is fitted, nothing is energised"*.
  3. **A case table for a move is ruled out by the design it would come from.**
     `move_reads.STEP_HAS_NO_STORE` records B18 §5.5.2's own footnote — *"a
     move-in is short enough that the wizard is the record"* — so inventing
     `move_jobs` here would be authoring a schema against a signed decision, on
     a lane that was asked to fill a link.

⚠ **POINT 3 IS THE ONE THE PO OVERTURNED FOR THE MOVE-IN.** `move_in_jobs` is
not the case table B18 §5.5.2's footnote rules out: it carries **no step**, for
the same reason this section gives, and the footnote's *"the wizard is the
record"* still holds for everything the wizard does. What the footnote never
weighed is where an APPROVED move-in waits before any wizard is opened, and that
is the only thing the new row holds.

**So what approval does for these two is what the drawn table's OTHER rows
say**, and no more: the request becomes `Approved`, the outcome is recorded
against the clerk's name, and the money stays readable through the request. The
preview says so BY NAME — `raises: null` with `reason: "the wizard is the
record"` — so the modal prints an honest absence instead of a promise nothing
keeps. **That is the `move_reads` posture applied one table over**, and it is
`DEF-CUS-5398`'s substance.

⚠ **THE LINK IS STILL BUILT, AND IT IS NOT A SLOT NOTHING FILLS.**
`move_records.request_id` lands in the same migration as the other two, and
`moves.record_move` takes `service_request_id` so the wizard fills it at the
moment the move commits. That completes `BR-CUS-080`'s child half for moves
properly — today the Move-ins tab finds the request by matching `outcome_ref`
against an ACCOUNT NUMBER (`move_reads._requests_by_account_no`), which its own
docstring records as two vocabularies already disagreeing.

═══════════════════════════════════════════════════════════════════════════
4 · WHAT THE REQUEST CARRIES INTO THE JOB, AND WHAT IT CANNOT
═══════════════════════════════════════════════════════════════════════════
*"Carry the request's information into the job, not merely a link."* What each
door will actually accept, measured against its signature:

| Fact | Where it lands | Where it does not, and why |
|---|---|---|
| the request itself | `connections.request_id` · `transfers.request_id` · `disconnect_cases.request_id` | — |
| the resolved premises | `connections.premises_id` | a transfer does not move address (`BR-CUS-1030`); a case is anchored on the account |
| the requested start | `connections.target_activation` | `transfers.out_date`/`in_date` are the wizard's step 3, not the application's ask |
| the resolved unit | — | `connections` has no unit column; units are the build wizard's step 5 |
| the services asked for | — | `connection_services` is written at `commit_connection` (`BR-MET-112`: *"nothing is written until step 9"*) |
| the applicant | — | the job reads it by walking `request_id`; a second copy is how two names come to disagree |
| **the outstanding money** | **read through the link** | see below |

⚠ **THE MONEY TRAVELS BY THE LINK AND IS NEVER COPIED.** The drawn row is *"The
$105.00 still outstanding here travels with it"*, and `$105.00` is
`fee_total_to_collect`'s `outstanding` — quoted $130.00 less $25.00 taken at the
counter (`BR-CUS-090`). **None of the four tables has a column that means
that**, and adding one would be the exact fault `moves.py` §1 and `Transfer`'s
docstring each refuse in their own words: *"a second copy of a fact that already
has an owner is how two numbers come to disagree"*, *"a stored `deposit_carried`
would read as money that moved on a path where nothing moved"*.
`connections.quote_total` is the BUILD's quote and not the application's fee;
`disconnect_cases.amount_owed_at_open` is the ACCOUNT's AR balance and not the
application's fee. So the figure stays on the request, the job names the
request, and `carried_money()` below is the ONE place that reads it — which is
what lets the modal and the job screen print the same $105.00.

═══════════════════════════════════════════════════════════════════════════
5 · THE APPROVAL STANDS EVEN WHEN THE JOB CANNOT BE RAISED
═══════════════════════════════════════════════════════════════════════════
`service_request_service.route` already settled this posture for field work
(`BR-WRK-055`): *"the state moves in its own committed transaction FIRST and the
raise happens after it, so a field module that is down, unpublished or refusing
cannot hold an approved application in `approved` for ever."* This follows it
exactly rather than inventing a second posture, and the catch is deliberately
broad for the same reasons that function gives.

**What comes back instead is a named refusal**, in the same `{code, br_ref,
detail}` shape every stated absence in this module already uses, so a clerk
reads *why* rather than seeing a job that silently is not there. The four real
ones, each measured rather than imagined:

  * a new connection whose address resolved to **no premise record** —
    `connections.premises_id` is NOT NULL and creating the premises needs a
    mandatory owner (`BR-MET-1010`) the application does not carry;
  * a transfer or a disconnect on a request with **no live account** — the door
    refuses, and the verdict table already tells the clerk so before they pick;
  * a disconnect where **the ladder is not running** — a protection in force, a
    payment plan, or nothing owed;
  * **any door that is unpublished** in this deployment.

⚠ **AND IT IS REPORTED, NEVER SWALLOWED.** `job_not_raised()` is the platform's
one sentence for it, the shape `seams.flow_work_not_raised` already established.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.customers import models, seams

LOGGER = logging.getLogger(__name__)

_SR = models.ServiceRequest


# ═══════════════════════════════════════════════════════════════════════════
# THE MAP — one row per outcome, and it is the SAME table the preview and the
# raise both read. Two tables would be two answers to "what will this create".
# ═══════════════════════════════════════════════════════════════════════════
#: What kind of record each outcome becomes. ⚠ These are the values written to
#: `service_requests.outcome_kind` by `link_child`, so they stay exactly
#: `service_request_service.OUTCOME_CHILD_KINDS` — imported rather than
#: restated, because two spellings of one vocabulary is `DEF-CUS-5398`'s
#: neighbour and `move_reads._requests_by_account_no` already documents one.

#: The queue each job lands on — the register tab a clerk goes and looks at.
#: Drawn on p081–p082 as ten tabs; these are the five the outcomes feed.
QUEUE_NEW_CONNECTS = "new_connects"
QUEUE_MOVE_INS = "move_ins"
QUEUE_MOVE_OUTS = "move_outs"
QUEUE_TRANSFERS = "transfers"
QUEUE_DISCONNECTS = "disconnects"

#: ⛔ The stated absence for the two outcomes that raise no row — §3. It is a
#: CODE and a reason, never a sentence for a screen: `B14` rule 33 says
#: rationale is zero words on screen, and the words are the catalogue's.
WIZARD_IS_THE_RECORD: dict[str, Any] = {
    "code": "move_wizard_is_the_record",
    "br_ref": "BR-CUS-150 · BR-CUS-152 · B18 §5.5.2",
    "detail": (
        "A move-in and a move-out have no queue row to raise. `move_records` is the record of "
        "a move that has already happened — it carries the account the job would create, it is "
        "never updated, and it is written inside the wizard's own transaction. B18 §5.5.2's "
        "footnote rules out a case table for it: a move-in is short enough that the wizard is "
        "the record. So approval records the outcome and the money, and the wizard writes the "
        "record when somebody does the job."
    ),
    "wanted_columns": (),
}


def _window(kind: str) -> dict[str, Any]:
    """⊕ **`DEF-CUS-6350` / `DEF-CUS-6352` — WHAT THE APPROVE WINDOW SAYS, PER
    KIND, AND WHAT ITS BUTTON IS CALLED.**

    The five `THEN`/`WHAT` rows below (`_drawn_rows`) emit the SAME keys for
    every outcome, and the catalogue words each one for a BUILD — so a MOVE-IN
    read *"A build opens for this address"*, *"Unpaid fees move to the build"*
    and *"You finish it on the build"* over a button saying *"Approve and raise
    the build"* (the PO's screenshot of `SR-26-0014`). The row carried `kind`
    and nothing used it to pick the sentence.

    ⚠ **THE KEYS ARE CHOSEN HERE, ON THE SERVER, AND NOT IN THE COMPONENT.**
    `JOB_SHAPES` is already the ONE table that answers *what does this outcome
    create* for the preview and for the raise; a `switch (kind)` in the window
    would be a second copy of this map, free to disagree with it the day an
    outcome is added. Only the two outcomes the window offers carry one
    (`APPROVE_OUTCOMES`, PO 2026-09-22 option (b)); the other three have no
    `window` at all, which is an absence and never the build's wording.

    ⛔ **NO LINE ABOUT UNPAID FEES, FOR EITHER KIND.** PO, 2026-09-23:
    *"there are no unpaid fees either applcition fee is paid or it is waived -
    so this is not applicable anymore"*. Two sentences, each six words or
    fewer (B14 rule 33's consequence cap), saying only what the product does.
    """
    base = "customers.serviceRequest.approveChecks"
    return {
        "submit": f"{base}.submit.{kind}",
        "lines": (f"{base}.effect.{kind}.first", f"{base}.effect.{kind}.second"),
    }


#: One row per outcome: what it raises, where that lands, and which number
#: series names it. `raises=None` is §3's honest absence and not a hole.
JOB_SHAPES: dict[str, dict[str, Any]] = {
    _SR.OUTCOME_NEW_CONNECTION: {
        "kind": "connection",
        "raises": "connections",
        "module": "metering",
        "queue": QUEUE_NEW_CONNECTS,
        "lands_in": "draft",
        "series": "connection",
        "drawn_consequence": "raises_a_build_on_the_new_connects_tab",
        "window": _window("new_connection"),
    },
    _SR.OUTCOME_MOVE_IN: {
        "kind": "move_in",
        # ⚠ **THIS READ `None` UNTIL 2026-09-16 — PO ruling, *"it should do
        # B"*.** §3 below records what changed and why the old absence was
        # honest when it was written.
        "raises": "move_in_jobs",
        "module": "customers",
        "queue": QUEUE_MOVE_INS,
        "lands_in": "pending",
        "series": "move_in",
        "drawn_consequence": "opens_an_account_on_a_unit_that_already_has_service",
        "window": _window("move_in"),
        # ⛔ **AND IT WRITES NO `outcome_ref`** — see `raise_job`'s own note.
        # For a move-in that column already means *the account this application
        # produced*, and the Move-ins tab's request search leg reads it that
        # way; taking it for the job would break a leg that works today.
        "links_child": False,
    },
    # ⚠ **THE MOVE-OUT IS UNCHANGED, AND THAT IS A BOUNDARY RATHER THAN AN
    # OVERSIGHT.** The PO ruled on the MOVE-IN — the walk's stuck request was a
    # move-in and the option they picked names one — so widening it to the
    # move-out would be a lane widening a ruling. §3's absence still holds here
    # word for word, and the move-out's own queue is a question for the day
    # somebody asks it.
    _SR.OUTCOME_MOVE_OUT: {
        "kind": "move_out",
        "raises": None,
        "module": "customers",
        "queue": QUEUE_MOVE_OUTS,
        "lands_in": None,
        "series": "move_out",
        "drawn_consequence": "closes_an_account_and_frees_its_unit",
        "absence": WIZARD_IS_THE_RECORD,
    },
    _SR.OUTCOME_TRANSFER: {
        "kind": "transfer",
        "raises": "transfers",
        "module": "customers",
        "queue": QUEUE_TRANSFERS,
        "lands_in": "scheduled",
        "series": "transfer",
        "drawn_consequence": "one_customer_a_different_address_of_ours",
    },
    _SR.OUTCOME_DISCONNECT: {
        "kind": "disconnect",
        "raises": "disconnect_cases",
        "module": "customers",
        "queue": QUEUE_DISCONNECTS,
        "lands_in": "notice_sent",
        "series": "disconnect_case",
        "drawn_consequence": "raises_a_case_and_starts_the_notice_ladder",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# THE REFUSALS — one code per reason a job could not be raised
# ═══════════════════════════════════════════════════════════════════════════
#: ⛔ **RETIRED 2026-09-21 (`DEF-CUS-6109`) AND KEPT AS A NAME RATHER THAN
#: DELETED.** Nothing raises it any more: an unresolved address raises a DRAFT
#: build with no premises and the wizard writes the address at its last button.
#: It stays declared so that a reader meeting
#: `customers.serviceRequest.jobRefusal.no_premises_resolved` in the thirteen
#: locale catalogues finds the reason here instead of an absence — and so that
#: nobody reintroduces the refusal by reaching for a spare code.
NO_PREMISES_RESOLVED = "no_premises_resolved"
NO_LIVE_ACCOUNT = "no_live_account"
DOOR_REFUSED = "job_door_refused"
DOOR_UNPUBLISHED = "job_door_unpublished"
ALREADY_LINKED = "job_already_linked"


def job_not_raised(code: str, detail: str, *, br_ref: str = "BR-WRK-055") -> dict[str, Any]:
    """The platform's one sentence for a job that could not be created.

    Same shape as `seams.flow_work_not_raised` and every other stated absence in
    this module (`{code, br_ref, detail}`), deliberately: a reader who has met
    one absence in this product has met all of them, and a screen that can
    render one can render this.
    """
    return {"code": code, "br_ref": br_ref, "detail": detail}


# ═══════════════════════════════════════════════════════════════════════════
# WHAT THE MONEY DOES — one reader, so two screens cannot print two figures
# ═══════════════════════════════════════════════════════════════════════════
def carried_money(request: models.ServiceRequest) -> dict[str, Any]:
    """*"The $105.00 still outstanding here travels with it"* — §4.

    Read from `fee_total_to_collect`, never re-totalled here, and **never
    copied onto the job**: `travels` says HOW it travels, which is by the job
    naming the request. Stored 4 dp, `display` 2 dp, `CHAR(3)` beside it
    (CLAUDE.md rule 2, rounding for a human happening exactly once).
    """
    from apps.customers import service_request_service as writes

    totals = writes.fee_total_to_collect(request.id)
    currency = totals["currency"]
    outstanding = totals["outstanding"]
    return {
        "outstanding": {
            "amount": str(outstanding),
            "display": f"{outstanding:.2f}",
            "currency": currency,
        },
        "quoted": {"amount": str(totals["quoted"]), "currency": currency},
        "collected": {"amount": str(totals["collected"]), "currency": currency},
        # HOW it travels. Not a copy — §4.
        "travels": "by_the_link",
        "copied_onto_the_job": False,
        # ⛔ **TRUE SINCE 2026-09-23 (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).**
        # This read False on the drawn callout *"the money does not gate
        # approval"* (Accounts blueprint p083). PO: *"either fee is paid or
        # waived - no other condition"* — so an unpaid fee stops the press, on
        # the remainder, through `service_request.fee_condition`.
        "gates_approval": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE PREVIEW — what the Approve modal PRINTS. It renders this; it computes none
# ═══════════════════════════════════════════════════════════════════════════
def approval_preview(request: models.ServiceRequest, outcome: str | None = None) -> dict[str, Any]:
    """`WHAT APPROVING WILL DO` — the drawn table, as data.

    Drawn p083–p084 (images, scale 2): five `THEN` / `WHAT` rows, of which the
    second and third change with the chosen radio and the other three do not.
    **Wave 2's modal renders this and works nothing out for itself** — a screen
    that computed *"a build is raised"* would be a second implementation of the
    rule, and the two would disagree the first time either moved.

    `outcome` defaults to the request's own committed pick, so the same call
    serves the decision tab (what WAS chosen) and the modal (what is being
    considered). An unknown outcome is refused by name rather than rendered
    empty.
    """
    chosen = outcome or request.outcome
    if chosen is not None and chosen not in JOB_SHAPES:
        return {
            "outcome": chosen,
            "known": False,
            "creates": None,
            "carries": None,
            "rows": [],
        }
    shape = JOB_SHAPES.get(chosen) if chosen else None
    money = carried_money(request)
    creates = None
    if shape is not None:
        creates = {
            "kind": shape["kind"],
            "table": shape["raises"],
            "module": shape["module"],
            "queue": shape["queue"],
            "state_it_lands_in": shape["lands_in"],
            "named_by_series": shape["series"],
            "names_this_request": True,
            "drawn_consequence": shape["drawn_consequence"],
            # §3 — `None` where the product has no queue row, with its reason.
            "raises_a_row": shape["raises"] is not None,
            "absence": shape.get("absence"),
            "blockers": _blockers_for(request, chosen),
        }
    return {
        "outcome": chosen,
        "known": shape is not None,
        "creates": creates,
        "carries": {
            "request_no": request.request_no,
            "applicant": request.applicant_name,
            "premises_id": str(request.resolved_premises_id) if request.resolved_premises_id else None,
            "unit_id": str(request.resolved_unit_id) if request.resolved_unit_id else None,
            "requested_start": (
                request.requested_start.isoformat() if request.requested_start else None
            ),
            "services": _service_codes(request),
            "money": money,
            # ⚠ **THE UNCHECKED DOCUMENTS TRAVEL WITH THE JOB (PO ruling
            # 2026-09-16, *"lets not make it mandetory"*).** They no longer
            # BLOCK the approval — and *not mandatory* is not *not mentioned*,
            # so what is still outstanding is named here and carried into the
            # job's own wizard. Read back through the link on every call, never
            # snapshotted: a document that arrives tomorrow makes this `None`
            # tomorrow with nothing to keep in step.
            "documents_outstanding": _documents_outstanding(request),
        },
        # The drawn table, in its drawn order. `then` is the drawn left column.
        # ⚠ These are KEYS, never sentences — G32/G33 and the 2026-08-19 ruling
        # that server text never reaches a customer screen.
        "rows": _drawn_rows(shape),
        # *"No account opens, no meter is fitted, nothing is energised."*
        "not_now": ("no_account_opens", "no_meter_is_fitted", "nothing_is_energised"),
        # ⊕ `DEF-CUS-6352` — the window's two lines and its button, per kind.
        # `None` for an outcome the window does not offer. See `_window`.
        "window": (dict(shape["window"], lines=list(shape["window"]["lines"])) if shape and shape.get("window") else None),
    }


def _drawn_rows(shape: dict[str, Any] | None) -> list[dict[str, Any]]:
    """p084's five `THEN` / `WHAT` rows, in the drawn order."""
    rows: list[dict[str, Any]] = [
        {"then": "now", "what": "request_becomes_approved_and_recorded_against_you"},
    ]
    if shape is None:
        return rows
    if shape["raises"] is not None:
        rows.append(
            {
                "then": "now",
                "what": "job_is_raised_naming_this_request",
                "queue": shape["queue"],
                "kind": shape["kind"],
            }
        )
    else:
        rows.append(
            {
                "then": "now",
                "what": "no_job_row_is_raised",
                "queue": shape["queue"],
                "kind": shape["kind"],
                "absence": shape.get("absence"),
            }
        )
    rows.append({"then": "now", "what": "the_outstanding_travels_with_it"})
    rows.append({"then": "next", "what": "the_jobs_own_wizard_asks_for_the_rest"})
    rows.append({"then": "not_now", "what": "no_account_no_meter_nothing_energised"})
    return rows


def _service_codes(request: models.ServiceRequest) -> list[str]:
    """The services asked for, in the catalogue's order — read, never copied.

    ⚠ **THIS READ `row.service_code` UNTIL 2026-09-15 AND THERE IS NO SUCH FIELD
    (`DEF-CUS-5412`).** `ServiceRequestService.service` is a FK to the platform
    catalogue, so the code is `row.service.code`; the old spelling raised
    `AttributeError: 'ServiceRequestService' object has no attribute
    'service_code'` and turned `GET /service-requests/{id}` into a 500 — but
    only for a request that HAS services.

    **Nothing could see it, and that is the interesting part.** A list
    comprehension evaluates the attribute only when the queryset yields a row,
    and `service_request_services` held ZERO rows in the demo tenant and in
    every suite: `sample_data.py` did not call `set_services`. ⚠ **That last
    clause stopped being true on 2026-09-16 (`DEF-CUS-5423`) — the seeder drives
    capture step 2 now, so a freshly seeded tenant carries twelve service rows
    and this branch is exercised by ordinary demo data.** An empty queryset
    makes every attribute name inside the loop unfalsifiable — hard-won law 7's
    *incapable of failing*, with no gate in this repo able to look at it. The
    first lane to write a service row is the first to see it, which is how
    BR-CUS-1070's own tests found it.

    `select_related` is not decoration here: without it this walks the
    catalogue once per row.
    """
    return [
        row.service.code
        for row in models.ServiceRequestService.objects.filter(request=request)
        .select_related("service")
        .order_by("id")
    ]


def _documents_outstanding(request: models.ServiceRequest) -> dict[str, Any] | None:
    """What is still unchecked, in the one place that reads it — see `carries`.

    ONE reader, for `carried_money`'s reason: the modal and the job screen must
    print the same answer, and two readers is how they come to print two.
    `move_in_jobs.outstanding_documents` is that reader.
    """
    from apps.customers import move_in_jobs

    return move_in_jobs.outstanding_documents(request)


def _blockers_for(request: models.ServiceRequest, outcome: str | None) -> list[dict[str, Any]]:
    """What would stop THIS outcome's job being raised, before the clerk commits.

    ⚠ **This is not the approval gate.** Approval is gated by
    `rules.blocking_conditions` — the documents — and this list never blocks it
    (§5): the drawn callout is *"the money does not gate approval and the
    documents do"*, and a request whose job cannot be raised is still approved.
    It exists so the modal can say so BEFORE the clerk presses the button rather
    than after.
    """
    from apps.customers import selectors

    out: list[dict[str, Any]] = []
    # ⛔ **THE `new_connection` BLOCKER IS GONE — `DEF-CUS-6109`, 2026-09-21.**
    # It read: *"A build is written against a premise record and this request's
    # address has not resolved to one. Resolve the address, or create the
    # premise, then approve."* An unresolved address now raises a DRAFT build
    # with no premises and the wizard creates the address at its last button
    # (`BR-MET-112`), so there is nothing here to warn a clerk about. The
    # sentence it printed was true of the code and the code's own reason was
    # false — see `_raise_connection` and `DEF-MET-6117`.
    if outcome in (_SR.OUTCOME_TRANSFER, _SR.OUTCOME_DISCONNECT):
        account = _account_at_the_address(request, selectors)
        if account is None:
            out.append(
                job_not_raised(
                    NO_LIVE_ACCOUNT,
                    "There is no live account at this address to act on, so no job can be "
                    "raised. The request is still approved and the outcome is recorded.",
                    br_ref="BR-CUS-030",
                )
            )
    if outcome == _SR.OUTCOME_MOVE_IN:
        # ⚠ **THE MOVE-IN JOB CARRIES NO `outcome_ref`, SO THE CHECK BELOW
        # CANNOT SEE IT — §3.** Its idempotency lives on its own table, and a
        # modal that could not say *"this one is already waiting"* would send a
        # clerk to press a button whose only answer is a refusal.
        from apps.customers import move_in_jobs

        if move_in_jobs.pending_queryset().filter(request_id=request.id).exists():
            out.append(
                job_not_raised(
                    ALREADY_LINKED,
                    "This request already has a move-in job waiting on the Move-ins tab, and "
                    "one decision raises one job. Nothing further is created.",
                    br_ref="BR-CUS-1077",
                )
            )
    if request.outcome_ref:
        out.append(
            job_not_raised(
                ALREADY_LINKED,
                "This request already names a job, and one decision raises one job "
                "(BR-CUS-080). Nothing further is created.",
                br_ref="BR-CUS-080",
            )
        )
    return out


def _account_at_the_address(request: models.ServiceRequest, selectors: Any) -> Any:
    """The live account the job would act on, or None.

    The occupying account at the RESOLVED UNIT — `BR-MET-036`'s derived
    occupancy, read through `selectors.active_account_for_unit` rather than
    re-derived, so this and the evidence table cannot disagree about who is
    there.
    """
    if not request.resolved_unit_id:
        return None
    return selectors.active_account_for_unit(request.resolved_unit_id)


# ═══════════════════════════════════════════════════════════════════════════
# THE RAISE — called by `approve`, AFTER the state has committed (§5)
# ═══════════════════════════════════════════════════════════════════════════
def raise_job(actor: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """Create the job this approval raises, and name the request on it.

    Returns `{"raised": {...}} ` or `{"not_raised": {...}}` — never both, and
    never neither. **It raises nothing itself**: every refusal is caught and
    reported, because `BR-WRK-055` says the flow completes whether or not the
    downstream job could be created, and an approval that rolled back because a
    neighbouring module was unpublished would hold an application in review for
    a reason that has nothing to do with the application.

    ⚠ **IDEMPOTENT ON `outcome_ref`.** `link_child` refuses a second child by
    name (`ux_service_requests_outcome_ref` is unique per tenant), so a
    double-click cannot raise two builds. It is checked HERE too rather than
    only caught, so the second call reports *"already linked"* and not a
    database error.
    """
    from apps.customers import service_request_service as writes

    shape = JOB_SHAPES.get(request.outcome or "")
    if shape is None:
        return {
            "not_raised": job_not_raised(
                DOOR_REFUSED,
                f"{request.outcome!r} names no job this product raises.",
                br_ref="BR-CUS-080",
            )
        }
    if shape["raises"] is None:
        # §3 — the honest absence, not a failure.
        return {"not_raised": dict(shape["absence"])}
    if request.outcome_ref:
        return {
            "not_raised": job_not_raised(
                ALREADY_LINKED,
                f"This request already names {request.outcome_ref}.",
                br_ref="BR-CUS-080",
            )
        }

    try:
        raised = _RAISERS[request.outcome](actor, request)
    except Exception as exc:  # noqa: BLE001 — BR-WRK-055, and §5 says why
        # ⚠ **THE EXCEPTION'S CLASS IS REPORTED, AND THAT IS NOT DECORATION.**
        # A broad catch turns OUR bug into something that reads exactly like the
        # product refusing — which is hard-won law 7's *check that cannot fail*
        # wearing a business face, and it happened to this lane on its first run
        # (`could not be raised: 'id'` was a `KeyError` on a payload key, not a
        # refusal). A `BizError` is the product saying no; a `KeyError`,
        # `AttributeError` or `TypeError` is a defect and must be legible as one.
        LOGGER.exception("service request %s: the %s could not be raised", request.id, shape["kind"])
        return {
            "not_raised": job_not_raised(
                DOOR_REFUSED,
                f"The {shape['kind']} could not be raised: {type(exc).__name__}: {exc}",
                br_ref="BR-WRK-055",
            )
        }
    # ⚠ **A RAISER RETURNS EITHER A JOB OR A NAMED REFUSAL, AND NEVER A BARE
    # `None` — FOUND LIVE, BY WALKING THE REAL API (`DEF-CUS-5406`).** The first
    # version returned `None` for every reason there was and this function
    # reported `job_door_unpublished` for all of them, so a clerk approving a
    # request whose address had not resolved was told the product had no door
    # for a build. **Both unit tests passed**, because the one covering that
    # path accepted either code with an `or` — hard-won law 7's *a check you
    # cannot describe a false pass for*, described and then shipped anyway.
    #
    # A refusal is told apart by carrying `code`, which a raised job never does.
    if "code" in raised:
        return {"not_raised": raised}

    # BR-CUS-080's own half — the SR alone answers *what happened to this
    # application*. Through `link_child`, never by setting the columns here:
    # that function owns the uniqueness refusal, the history line and the audit
    # row, and a second writer would be a second place the link can go wrong.
    #
    # ⚠ **EXCEPT FOR THE MOVE-IN JOB, WHICH LINKS THE OTHER WAY ONLY — §3.**
    # `outcome_ref` on a move-in already means *the account this application
    # produced*, and the Move-ins tab's `request #` search leg reads it that
    # way; taking the column for the job would break a working leg. The job's
    # own `uq_move_in_jobs_tenant_request` is what makes a second press
    # idempotent instead.
    if shape.get("links_child", True):
        writes.link_child(
            actor,
            request.id,
            child_ref=raised["ref"],
            child_kind=shape["kind"],
        )
    writes._audit(
        actor,
        "service_request.job_raised",
        request.id,
        before={"outcome_ref": None},
        after={
            "outcome": request.outcome,
            "kind": shape["kind"],
            "table": shape["raises"],
            "ref": raised["ref"],
            "id": raised["id"],
        },
    )
    return {
        "raised": {
            "kind": shape["kind"],
            "table": shape["raises"],
            "module": shape["module"],
            "queue": shape["queue"],
            "id": raised["id"],
            "ref": raised["ref"],
            # ⊕ `DEF-CUS-6350` — present for a move-in (its `MVI-` number, or
            # `None` where the tenant keeps no series); absent otherwise.
            "move_no": raised.get("move_no"),
            "state": raised.get("state"),
            "names_this_request": True,
            "warnings": raised.get("warnings") or [],
        }
    }


# ── the five doors ─────────────────────────────────────────────────────────
def _raise_connection(actor: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """*"Raises a build on the New connects tab, linked back to this request."*

    ⚠ **`request_id` HAS BEEN ON `connections` SINCE `CR-030` W6 AND NOTHING
    HAS EVER FILLED IT** (`DEF-MET-5397`). `create_connection` reads
    `data.get("service_request_id")` and its own docstring says *"Prefilled from
    an approved request where there is one"* — the door was built for this call
    and the call was never made.

    ⛔ **THIS FUNCTION REFUSED A REQUEST WHOSE ADDRESS HAD NOT RESOLVED UNTIL
    2026-09-21, AND THE REASON IT GAVE WAS FALSE — `DEF-MET-6117`.** It read:
    *"creating the premise here would need the mandatory owner `BR-MET-1010`
    requires and the application does not carry."* **Both halves fail against
    the schema, and the PO is who asked for the measurement** — *"why youa re
    saying request dont have owner - we take details on customer when service
    request is created"*:

      * **`premises.owner_id` is NULLABLE.** The only `NOT NULL` business column
        on `premises` is `address_line`, and the request carries it as
        `address_as_given`. The owner refusal on a premises create was itself
        REVERSED on 2026-08-27 (`DEF-650`), and `_validate_premises` says so.
      * **The code it cited refutes it.** `metering/services.py::create_premises`
        opens the owner's master account LAST, in its own savepoint, and its own
        comment reads *"a refused account leaves the address standing"* and
        *"SERVED EVEN WHEN IT IS `None`, AND THAT IS THE POINT"*. A premises is
        deliberately creatable with no owner account.

    ⚠ **IT IS WRITTEN OUT HERE RATHER THAN DELETED, BECAUSE THE COMMENT WAS
    PERSUASIVE** — it cited a rule id, named a mandatory field and gave a
    reason, and it was relayed to the PO as a finding. Hard-won law 1: *a
    comment claiming a guarantee is not the guarantee*, and a comment supplying
    a REASON FOR A REFUSAL is the most dangerous kind, because a lane meeting it
    stops measuring.

    ── WHAT HAPPENS NOW (PO ruling 2026-09-21, `DEF-CUS-6109`) ───────────────
    *"then approve applciation may create a new conenct request - as draft
    request - this request is new work and recognized seperately from
    applcaition and hence we should not make it dependent on applciation #"*.

    **Both shapes raise a DRAFT build and neither creates an address:**

      * the address RESOLVED → the draft is raised against that premises, and
        the wizard simply has no address to create. An existing property with no
        service is an ordinary new connection.
      * the address did NOT resolve → the draft is raised with **no premises**
        (`metering/0059` makes the column nullable for exactly this), and the
        address is created at the wizard's last button. ⚠ **Creating it here
        instead would break `BR-MET-112`**: a clerk who abandons the wizard
        would leave a brand-new property standing with no units, no meters and
        no plan, and no screen in this product can find that wreckage.

    ⛔ **`request_id` IS PROVENANCE AND NEVER A DEPENDENCY** (`BR-MET-1178`).
    The draft carries it and is not owned by it; a build raised directly has
    none and behaves identically.

    ⚠ **THE TWO REFUSALS ARE DIFFERENT ANSWERS AND USED TO BE ONE** — see
    `raise_job`. Only one of them is left: *"this deployment publishes no
    door"* is something only an engineer can act on, and it is still reported
    as itself rather than as a clerk's problem.
    """
    resolved = request.resolved_premises_id
    made = seams.raise_connection_build(
        actor,
        # `None` is the *address comes later* path and is not a missing
        # argument — the seam turns it into `premises_at_commit`, which
        # `create_connection` demands BY NAME rather than inferring from two
        # absent keys.
        premises_id=str(resolved) if resolved else None,
        service_request_id=str(request.id),
        target_activation=request.requested_start,
    )
    if made is None:
        return job_not_raised(
            DOOR_UNPUBLISHED,
            "This deployment publishes no door for a build, so nothing was created. The "
            "request is approved and the outcome is recorded.",
        )
    return {
        "id": made["id"],
        # The number a clerk quotes. NULL where the tenant has no `connection`
        # series — the door reports `numbering_series_missing` in `warnings`
        # rather than faking one, and the id is still a real link.
        "ref": made.get("connection_no") or made["id"],
        "state": made.get("state"),
        "warnings": made.get("warnings") or [],
    }


def _raise_move_in(actor: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """*"Opens an account on a unit that already has service."* — **later.**

    PO ruling 2026-09-16, *"it should do B"*. This raises the PENDING JOB and
    opens nothing: the drawn table's last row is *"Not now — No account opens,
    no meter is fitted, nothing is energised"*, and that is as true of this
    outcome after the ruling as it was before it.

    ⚠ **THE REFERENCE IT REPORTS IS THE REQUEST'S OWN NUMBER, AND THAT IS NOT A
    PLACEHOLDER.** A pending move-in has no number of its own — B18 §5.5.2 draws
    exactly this row with `— draft` in the account column — and inventing a
    fourth number series for a job that has not happened would give a clerk two
    references for one move-in, because `moves.record_move` allocates the real
    `MVI-` the moment somebody does it. So the job is quoted by the application
    it came from, which is the number the clerk has in front of them, and
    `B14` rule 31 keeps the row's uuid off the screen.

    ⚠ **NOTHING IS COPIED ONTO IT.** The applicant, the address, the requested
    start, the money and the unchecked documents all stay on the request and are
    read back through the link — `move_in_jobs` §2, which is this file's own §4
    doctrine applied to a whole table.
    """
    from apps.customers import move_in_jobs

    made = move_in_jobs.raise_for_request(actor, request)
    if "code" in made:
        # `raise_for_request` already speaks the `{code, br_ref, detail}` shape,
        # so it is returned as it stands rather than re-wrapped: a second
        # wrapper is a second place the sentence can drift.
        return made
    return {
        "id": made["id"],
        "ref": request.request_no,
        # ⊕ `DEF-CUS-6350` — the job's OWN number (`BR-CUS-1090`), which is what
        # the request page links to after approval (`/moves/{move_no}`). `ref`
        # above is unchanged, because every existing reader quotes it.
        "move_no": made.get("move_no"),
        "state": made["state"],
        "warnings": [],
    }


def _raise_transfer(actor: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """*"One customer, a different address of ours."*

    Through `transfers.start_transfer`, which reads the seller from
    `customer_accounts` (`BR-CUS-054`) and refuses an account nobody occupies.
    The job lands `scheduled` at step 1 of 5 — raised, not done, exactly as the
    drawing asks.
    """
    from apps.customers import selectors, transfers

    account = _account_at_the_address(request, selectors)
    if account is None:
        return job_not_raised(
            NO_LIVE_ACCOUNT,
            "There is no live account at this address for a transfer to move, so no job "
            "was raised. The request is approved and the outcome is recorded.",
            br_ref="BR-CUS-030",
        )
    with transaction.atomic():
        row = transfers.start_transfer(actor, {"from_account_id": account["id"]})
        transfers.Transfer.objects.filter(pk=row["id"]).update(request_id=request.id)
    return {
        "id": row["id"],
        "ref": row.get("transfer_no") or row["id"],
        "state": row.get("state"),
        "warnings": [],
    }


def _raise_disconnect(actor: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """*"Raises a case and starts the notice ladder."*

    Through `disconnects.open_case`, which refuses when the ladder is not
    running (a protection in force, a payment plan, nothing owed), reads the
    balance and the tenant's `CHAR(3)` currency, and lands the case in
    `notice_sent` — which IS *"starts the notice ladder"*. Nothing is cut and no
    notice is sent here; `record_notice` and the cut are the case's own doors.
    """
    from apps.customers import disconnects, selectors

    account = _account_at_the_address(request, selectors)
    if account is None:
        return job_not_raised(
            NO_LIVE_ACCOUNT,
            "There is no live account at this address to open a case against, so no job "
            "was raised. The request is approved and the outcome is recorded.",
            br_ref="BR-CUS-030",
        )
    with transaction.atomic():
        payload = disconnects.open_case(actor, account["id"], as_of=seams.tenant_today())
        # ⚠ `case_payload`'s primary key is `case_id`, not `id` — `transfers`
        # and `connections` both say `id` and this one does not. Read from the
        # door's own payload rather than assumed, because assuming it cost this
        # lane a run: the raise came back `could not be raised: 'id'`.
        disconnects.DisconnectCase.objects.filter(pk=payload["case_id"]).update(
            request_id=request.id
        )
    return {
        "id": payload["case_id"],
        "ref": payload.get("case_no") or payload["case_id"],
        "state": payload.get("state"),
        "warnings": [],
    }


#: The FOUR outcomes that have a row. ⚠ `move_in` joined on 2026-09-16 (PO,
#: *"it should do B"*); `move_out` still never reaches here, because `raise_job`
#: returns §3's absence for it before it looks.
_RAISERS = {
    _SR.OUTCOME_NEW_CONNECTION: _raise_connection,
    _SR.OUTCOME_MOVE_IN: _raise_move_in,
    _SR.OUTCOME_TRANSFER: _raise_transfer,
    _SR.OUTCOME_DISCONNECT: _raise_disconnect,
}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 (12-governance/11-change-requests.md) + the decision-log
#         row of 2026-09-15. ⚠ G1 wants `US-XXX-###@<hex>` and no story owns a
#         CR wave task — DEF-810 records that the packet grammar has no form for
#         CR- or DEF-driven work.
# generated: 2026-09-15 by the CR-094-BRC01 wave 1 lane A
# checklist: A✔ B✔ C=n/a D✔(the preview is what wave 2 renders) E=n/a(no screen
#         in this lane) F✔ G✔ H=n/a
# gates: proved RED first — every one of the five outcomes asserted that
#         approval creates the job, against the product as it stood, and all
#         five failed before this file existed.
