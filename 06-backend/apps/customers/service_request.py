# ── Trace ──────────────────────────────────────────────
# Story:    CR-031 (PO 2026-08-24 — the SR workflow in the requester's own
#           words) · B19 (the same feature DRAWN: REQ-01 list · REQ-02 detail ·
#           REQ-03.1..6 capture · REQ-03.sent)   Screens: REQ-01 · REQ-02 · REQ-03
# Rules:    BR-CUS-079 (acknowledgement at submission) · BR-CUS-080
#           (origin link · outcome + outcome_ref · documents BY REFERENCE) ·
#           BR-CUS-070 (`address_as_given` never overwritten) · B18 §4.6 (fees
#           are a quote; the request never posts to the ledger) · CLAUDE.md
#           rule 6 (idempotent number allocation)
#           ── the PO rulings of 2026-08-24, all CONFIRMED ──
#           BR-CUS-090 (the counter accepts what is handed over; a shortfall is
#           an open fee balance) · BR-CUS-091 (a customer MAY request a
#           disconnect; a disconnect is not a move-out) · BR-CUS-093 (numbered
#           AT CREATION) · BR-CUS-094 (seven categories; `government` legacy) ·
#           BR-CUS-095 (each utility ticks its own required documents; nothing
#           ticked by default)
# Questions: OQ-355 (the FIFTH approval condition — STILL OPEN) · OQ-356 (the
#           verdict for the evidence combinations the screens never draw —
#           STILL OPEN) · OQ-357 ✅ CLOSED 2026-09-23 as "both" (remove while a
#           draft, waive after)
#           · OQ-351 ✅ CLOSED 2026-08-24 → BR-CUS-095
# Defects:  DEF-632 (the SSN — ruled by BR-CUS-092 and NOT built here: the
#           app-layer encryptor it requires is a `core/` file and `tenancy.ein`
#           is another module's table) · DEF-634 ✅ closed → BR-CUS-093 ·
#           DEF-635 ✅ closed → BR-CUS-094 · DEF-637 ✅ closed → BR-CUS-090 ·
#           DEF-638 12.a ✅ closed → BR-CUS-091
# Tests:    06-backend/tests/test_cr031_service_request.py
# Impacts:  apps/customers/service_request_service.py (the write path) ·
#           apps/customers/service_request_reads.py (REQ-01/02/03's read model)
# ───────────────────────────────────────────────────────
"""CR-031 — the service-request LIFECYCLE, as rules with no database in them.

Same shape as `apps/customers/payment_plan.py`: the judgments live here where a
test can reach them without a tenant, a row or a transaction, and the write path
next door does the ORM, the audit and the numbering.

────────────────────────────────────────────────────────────────────────────
THE ONE SENTENCE THIS MODULE EXISTS TO ENFORCE
────────────────────────────────────────────────────────────────────────────
**The system SUGGESTS; the clerk DECIDES.** B19 §12.3 draws it twice — the
decision panel is right-labelled *"The application never asked what kind of job
this is — that is decided here"* and headed *"Nothing is preselected. Approving
creates real service and real charges, so the decision is made deliberately."*

So `outcome_verdicts()` below returns EVIDENCE and a verdict per option, and
nothing anywhere in this module writes an outcome from a verdict. CR-031 §4
reversed B18 §6.4's proposed classifier (*"the system classifies"*) before it
was ratified — BR-CUS-071 as worded is still wrong and is not implemented.

────────────────────────────────────────────────────────────────────────────
A `not_possible` BADGE IS ONLY EVER AWARDED BY A REASON THE PO'S SCREEN WROTE
────────────────────────────────────────────────────────────────────────────
B19 §12.3 draws the five verdicts for exactly ONE evidence state (served, and
the unit is vacant) and the Location tab draws one more consequence (no premise
record → *"This becomes a new connection"*). Every other combination of evidence
is undrawn.

The temptation is to invert each drawn impossibility into a possibility — *"the
applicant holds no live account at this address, so there is nothing to close"*
reads like a rule that says move-out fits when they DO hold one. It is not: it
is a sentence about one case. So this module awards

  * `FITS_THE_EVIDENCE` only where a screen draws that badge,
  * `NOT_POSSIBLE` only where the condition a drawn reason states is TRUE,
  * `POSSIBLE` everywhere else — *the evidence does not rule this out, and
    nothing rules it in* — which is **OQ-356**, filed rather than guessed.

That rule is one line to state and it is why the verdict table below reproduces
the PO's screenshot exactly without inventing a sixth sentence.

────────────────────────────────────────────────────────────────────────────
FOUR REFUSALS THIS MODULE CARRIED YESTERDAY AND CARRIES NO LONGER
────────────────────────────────────────────────────────────────────────────
Every one of them was a contradiction between two things the PO had drawn, and
every one was put to the PO on 2026-08-24 and ruled. **Read the ruling before
touching the code it produced — none of these is a lane's judgment.**

* **`disconnect` COMMITS — BR-CUS-091.** *"Yes customer can request it."* The
  list's `SR-26-0048 · DISCONNECT` was right; REQ-02's decision-panel reason is
  WITHDRAWN. ⚠ **What that reason got RIGHT survives:** a disconnect and a
  move-out are different OUTCOMES — a move-out closes the account and settles
  the deposit (BR-CUS-030), a disconnect leaves it open and accruing
  (BR-MET-105's base charge keeps running). Nothing here converts one into the
  other; `_verdict_for` therefore stops awarding `disconnect` a `not_possible`
  badge and awards it **`possible`**, the same third verdict every other
  undrawn combination gets. It does NOT award it `fits_the_evidence`: no screen
  draws that badge for a disconnect, and inventing one would be authoring the
  rule OQ-356 exists to ask for.
* **The number-allocation MOMENT — BR-CUS-093.** *"At creation — every draft is
  numbered."* `TRANSITIONS` below still says nothing about numbering, and that
  is now the POINT rather than the gap: `create_request` allocates and no
  transition does, so a repeated submit is a state move on a row that already
  has its identity (consequence (e), CLAUDE.md rule 6 getting simpler).
* **The fee figure — BR-CUS-090.** Both screens were right about their own
  half: $130.00 is the QUOTE, $25.00 is what the counter TOOK. `fee_condition`
  below reads the OUTSTANDING figure, which is the difference.
* **The customer categories — BR-CUS-094.** Seven, with `government` marked
  legacy rather than re-labelled.

────────────────────────────────────────────────────────────────────────────
AND THREE QUESTIONS THAT ARE STILL OPEN, EACH STUBBED RATHER THAN GUESSED
────────────────────────────────────────────────────────────────────────────
* **OQ-355** — the FIFTH approval condition. The panel prints *"4 of 5"* and
  four are nameable. `CONDITION_KEYS` holds four and `conditions_summary` states
  the gap; nothing prints a `5` it cannot itemise.
* **OQ-356** — the verdict for undrawn evidence combinations. Unchanged by
  today's rulings, and now carrying one more `possible` row than it did.
* ✅ **OQ-357 — CLOSED 2026-09-23 as "both"** (the PO approved the step-5 fee
  table carrying a Waive tick and a remove icon): a DRAFT's line is removed, a
  submitted request's is waived with a reason. It read *"remove, or waive with a
  reason?"* until then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# ── the eleven states, imported from the model so they cannot drift ──────────
from apps.customers.models import ServiceRequest as _SR

DRAFT = _SR.DRAFT
SUBMITTED = _SR.SUBMITTED
UNDER_REVIEW = _SR.UNDER_REVIEW
MORE_INFO = _SR.MORE_INFO
APPROVED = _SR.APPROVED
IN_FULFILMENT = _SR.IN_FULFILMENT
ON_HOLD = _SR.ON_HOLD
COMPLETED = _SR.COMPLETED
REFUSED = _SR.REFUSED
WITHDRAWN = _SR.WITHDRAWN
CLOSED = _SR.CLOSED
STATES = _SR.STATES
TERMINAL_STATES = _SR.TERMINAL_STATES


class ServiceRequestRuleError(ValueError):
    """A lifecycle rule was broken with no tenant, row or request in sight —
    raised by this module so the write path can translate it into a catalog
    refusal with a `message_key`. Same split as `PaymentPlanRuleError`."""


# ── the actions, and what each is allowed to do ─────────────────────────────
#: B18 §5.3.3's state diagram, plus B19's `Manual close`. Each action names the
#: states it may be taken FROM and the state it lands in.
#:
#: ⚠ **PARK IS NOT HERE, AND THAT IS THE POINT.** B19 §12.2 draws `Park —
#: waiting on ▾` beside `Save & exit` and the list proves they are orthogonal to
#: state: `SR-26-0046` is `Submitted` waiting on a *scheduled date* while
#: `SR-26-0042` is `Under review` waiting on *payment*. Park writes
#: `waiting_on` / `park_note` / `remind_on` and moves nothing.
SUBMIT = "submit"
REQUEST_INFO = "request_info"
APPROVE = "approve"
REFUSE = "refuse"

#: ⚠ **THE NINE RETIRED MOVES KEEP THEIR NAMES AND LOSE THEIR ROWS (PO ruling
#: 2026-09-19).** They are deliberately still DEFINED: a caller that has not
#: been updated then reaches `next_state`, which raises this module's own
#: `ServiceRequestRuleError` naming the action — rather than an `AttributeError`
#: three frames away that reads like a broken import. `actions_available`
#: cannot offer them, because it reads `TRANSITIONS` and they are not in it.
PICK_UP = "pick_up"
INFO_RECEIVED = "info_received"
ROUTE = "route"
HOLD = "hold"
RESUME = "resume"
COMPLETE = "complete"
WITHDRAW = "withdraw"
REOPEN = "reopen"
MANUAL_CLOSE = "manual_close"

#: Every move that was removed today, as one list, so a caller can ASK instead
#: of hardcoding a second copy of it — which is the defect `DEF-CUS-5874`
#: records one module over.
RETIRED_ACTIONS: tuple[str, ...] = (
    PICK_UP,
    INFO_RECEIVED,
    ROUTE,
    HOLD,
    RESUME,
    COMPLETE,
    WITHDRAW,
    REOPEN,
    MANUAL_CLOSE,
)

# ⚠⚠ **FIVE STATES AND FOUR MOVES — PO RULING 2026-09-19.** This table held
# THIRTEEN moves and eleven reachable states until today. The PO put the screen
# beside its drawing and ruled the difference out, verbatim: *"see service
# request i simple - clark submit it - it is revewed, then decision, apporve,
# refuse or ask for more - that it; once requets is approved then in move in or
# new connect we take all those decision to in fulfill etc - youa re mising too
# many thing hre - we have to keep it simple"*.
#
# **What a request can now be:** `draft` → `submitted` → `under_review` →
# `approved` or `refused`, with `more_info` off to the side. That is all.
#
# ⚠ **NINE MOVES WERE REMOVED AND NOTHING IS MIGRATED.** `pick_up`,
# `info_received`, `route`, `hold`, `resume`, `complete`, `withdraw`,
# `manual_close` and `reopen` are gone. Rows already sitting in
# `in_fulfilment`, `on_hold`, `completed`, `closed` or `withdrawn` KEEP those
# states and still read correctly everywhere — `STATES`, `TERMINAL_STATES`,
# the segment map and every catalogue word are untouched. What changed is that
# nothing can PUT a request into them any more.
#
# ⚠ **THE DECISIONS WORK STRAIGHT FROM `submitted`, AND NOTHING AUTO-WRITES A
# STATE** — the PO chose option (a) when both were put to them: *"a is
# correct"*. A clerk who opens a submitted request and approves it does not
# first trip an invisible `pick_up`; the state moves when a real decision is
# made and at no other time. That is why `APPROVE`, `REFUSE` and
# `REQUEST_INFO` gained `SUBMITTED` rather than `submit` gaining a side effect.
#
# ⚠ **`under_review` IS REACHED BY PARKING, WHICH IS NOT IN THIS TABLE.** See
# `park` in `service_request_service.py`: a clerk who parks a SUBMITTED request
# has self-evidently picked it up, and the blueprint's own register draws
# `SR-26-0042` as *Under review, waiting on a supervisor* — which is precisely
# a parked request. Park moves nothing from any other state.
#
# ⚠ **`withdrawn` IS RETIRED AND A WITHDRAWAL IS NOW A REASON, NOT A STATE.**
# p084 draws `Applicant withdrew` as one of the Refuse dialog's five reasons.
# The customer's own portal door closed with the clerk's, on the PO's ruling of
# 2026-09-19: *"if customer dont want it - they will call and clark will refuse
# it. thats'it . keep it simple"* (`OQ-CUS-12486`, which supersedes
# `BR-CWP-079`'s *withdrawable until approved*).
#
# ⚠ **REFUSE IS TERMINAL AND THERE IS NO WAY BACK.** `reopen` is gone even
# though p085 names it, because a reapplication is a NEW request. That is the
# one place this table knowingly contradicts the drawing, and it is a ruling.
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    SUBMIT: ((DRAFT,), SUBMITTED),
    # ⚠ `MORE_INFO` is here so a request that was sent back for more can be
    # decided the moment the answer arrives, without a second control to press
    # first. `info_received` was exactly that second control and it is gone.
    APPROVE: ((SUBMITTED, UNDER_REVIEW, MORE_INFO), APPROVED),
    REFUSE: ((SUBMITTED, UNDER_REVIEW, MORE_INFO), REFUSED),
    # ⚠ **`MORE_INFO` → `MORE_INFO` IS LAWFUL AND DELIBERATE.** A clerk who has
    # asked for a site plan and then needs the identity document too must be
    # able to ask again; refusing the second ask would leave the only way
    # forward a refusal.
    REQUEST_INFO: ((SUBMITTED, UNDER_REVIEW, MORE_INFO), MORE_INFO),
}

# ⚠⚠ **ONE WAY BACK FROM `refused` — FOR A MOVE-IN REQUEST ONLY (PO ruling
# 2026-10-05, `OQ-CUS-12789` CLOSED → (a)).** Verbatim: *"Reopen: SR-26-0014
# goes back to "To approve". Same number, her documents stay, and the decline
# stays in its history."* That SUPERSEDES the 2026-09-19 clause above (*"refuse
# is terminal … a reapplication is a NEW request"*) **for move-in requests and
# for nothing else** — the question was put to the PO from the Move-ins details
# view (image 08) and answered there.
#
# ⚠ **A SEPARATE TABLE, NOT A FIFTH ROW OF `TRANSITIONS` — THE SCOPE MADE
# MECHANICAL.** `actions_available` reads `TRANSITIONS` and is what the request
# page's action bar offers every request; a fifth row there would put *Reopen*
# on every refused new-connection request too, which nobody ruled. So `reopen`
# stays in `RETIRED_ACTIONS` for the generic door (`/transitions` still refuses
# it by name) and is lawful only through `next_state(..., move_in=True)`, which
# the one writer (`service_request_service.reopen_declined_move_in`) passes
# after checking the request IS a move-in (`suggests_move_in`).
#
# **It lands on `submitted`** — the Move-ins list's *To approve* (CR-171 §6.1
# maps `submitted` and `under_review` to it; `submitted` is the state nobody has
# picked up, which is what a reopened application is).
MOVE_IN_TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    REOPEN: ((REFUSED,), SUBMITTED),
}


def suggests_move_in(resolution_kind: str | None) -> bool:
    """Is this request a MOVE-IN request? CR-171 §6.1: *"a `service_requests`
    row … whose resolver says served, vacant (the request page's Suggested:
    Move-in)"* — the existing suggestion, never a second classifier. One
    predicate, so the Move-ins list and the reopen door cannot disagree."""
    return str(resolution_kind or "") == _SR.RESOLUTION_SERVED_VACANT

#: Actions whose reason the screen says is REQUIRED. `refuse` — *"Refusing keeps
#: the request and its reason on record"* (and TC-REQ-9 refuses a reasonless
#: refusal outright); `manual_close` — *"Reason required"*; `reopen` — B18's own
#: *"with a reason"*; `request_info` — *"Reason visible to anyone answering the
#: phone"*; `hold` — *"Reason on the face of the record"*.
#: ⚠ **THREE OF THE FIVE LEFT WITH THEIR ACTIONS (2026-09-19).**
#: `manual_close`, `reopen` and `hold` are retired moves, so a reason can never
#: be asked for them again. `refuse` and `request_info` are the whole list now.
REASON_REQUIRED = (REFUSE, REQUEST_INFO)

# ── WHY a request was refused, and WHAT a clerk is waiting for ───────────────
#
# ⚠ **BOTH ARE DRAWN AND NEITHER EXISTED (`DEF-CUS-5389`, `CR-094-BRC01`).** The
# Accounts blueprint's entry 06 draws the Refuse dialog with `Reason *` as a
# SELECT of five and the Ask-for-more dialog with a tick list of four, read as
# images from p084 and p085. The server accepted a free-text `reason_code` that
# no screen set and had nowhere at all to put the tick list.
#
# ⚠ **A FREE-TEXT REASON ANSWERS NO QUESTION.** The point of a closed list is
# that *"why does this utility turn people down"* becomes countable: five values
# group, and five hundred typed sentences do not.
#
# ⚠ **THESE ARE CODES; THE WORDS ARE THE SCREEN'S.** B14 rule 31 keeps a
# database value off a screen and rule 32 keeps our vocabulary out of
# clerk-facing copy, so the drawn labels live in the locale catalogues under
# `customers.serviceRequest.refusalReason.*` and are translated in all eleven.
# **Nothing here reaches an applicant either**: the refusal LETTER carries the
# clerk's own `What to tell them` sentence and never a reason code.
REFUSAL_NOT_OUR_AREA = "not_our_service_area"
REFUSAL_DOCUMENTS_NOT_PROVIDED = "documents_not_provided"
REFUSAL_APPLICANT_WITHDREW = "applicant_withdrew"
REFUSAL_DUPLICATE = "duplicate_of_another_request"
REFUSAL_OTHER = "other"
REFUSAL_REASONS: tuple[str, ...] = (
    REFUSAL_NOT_OUR_AREA,
    REFUSAL_DOCUMENTS_NOT_PROVIDED,
    REFUSAL_APPLICANT_WITHDREW,
    REFUSAL_DUPLICATE,
    REFUSAL_OTHER,
)

#: The four the drawing ticks. ⚠ **THE FIRST ONE IS DRAWN AS *"A readable site
#: plan — the one attached was rejected"* AND THE CLAUSE AFTER THE DASH IS AN
#: ILLUSTRATION** (B14 rule 37): it is true of the one request in the picture
#: and false of a request with nothing attached, so the label a clerk reads is
#: the first half. The other three are drawn as they stand.
NEEDS_SITE_PLAN = "readable_site_plan"
NEEDS_IDENTITY_PROOF = "proof_of_identity"
NEEDS_CONNECTION_DATE = "connection_date"
NEEDS_SOMETHING_ELSE = "something_else"
INFO_NEEDED_KINDS: tuple[str, ...] = (
    NEEDS_SITE_PLAN,
    NEEDS_IDENTITY_PROOF,
    NEEDS_CONNECTION_DATE,
    NEEDS_SOMETHING_ELSE,
)


def next_state(current: str, action: str, *, move_in: bool = False) -> str:
    """The state `action` lands in, or raise. The ONLY place a state moves.

    `move_in=True` also admits `MOVE_IN_TRANSITIONS` (the 2026-10-05 reopen);
    a caller passes it only for a request `suggests_move_in` says is one."""
    table = {**TRANSITIONS, **MOVE_IN_TRANSITIONS} if move_in else TRANSITIONS
    if action not in table:
        raise ServiceRequestRuleError(f"unknown lifecycle action {action!r}")
    allowed_from, lands_in = table[action]
    if current not in allowed_from:
        raise ServiceRequestRuleError(
            f"{action!r} is not allowed from {current!r} (allowed: {', '.join(allowed_from)})"
        )
    return lands_in


def actions_available(current: str) -> tuple[str, ...]:
    """Every action lawful from `current` — what REQ-02's action bar may offer."""
    return tuple(a for a, (allowed_from, _) in TRANSITIONS.items() if current in allowed_from)


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


#: ══════════════════════════════════════════════════════════════════════════
#: **WHILE A REQUEST MAY STILL BE CORRECTED — `DEF-CUS-6427`.** The Edit ruling
#: of 2026-09-23 (decision log, *"THE PO ASKS FOR *EDIT* ON A SERVICE REQUEST"*):
#: *Draft*, *Submitted*, *Under review*, *More info needed* — the request is
#: still being worked. **Not** once *Approved* or *Refused*: those are
#: decisions, and an approved request has already become an account and a job,
#: so correcting it is a correction to THOSE records, not to the request.
#:
#: ⚠ **IT IS NARROWER THAN `not is_terminal`, AND THAT GAP WAS THE DEFECT'S
#: SERVER HALF.** `update_request` refused only the four TERMINAL states, so
#: `approved`, `in_fulfilment` and `on_hold` — all past an approval — took a
#: PATCH without a word. The front end's `EDITABLE_REQUEST_STATES`
#: (`serviceRequestEditDoor.tsx`) is the same four and a test pins the two equal.
#: ══════════════════════════════════════════════════════════════════════════
EDITABLE_STATES: tuple[str, ...] = (DRAFT, SUBMITTED, UNDER_REVIEW, MORE_INFO)


def is_editable(state: str) -> bool:
    return state in EDITABLE_STATES


#: REQ-01's five segments (`All · Open · Waiting on customer · Approved ·
#: Closed`). `Open` is *"not yet turned into a job"* — the KPI strip's own
#: caption — so it is everything before `Approved` and every non-terminal state.
SEGMENT_STATES: dict[str, tuple[str, ...]] = {
    "all": tuple(STATES),
    "open": (DRAFT, SUBMITTED, UNDER_REVIEW, MORE_INFO),
    "waiting_on_customer": (MORE_INFO,),
    "approved": (APPROVED, IN_FULFILMENT, ON_HOLD),
    "closed": TERMINAL_STATES,
}


#: **BR-CUS-106 — the `AGE` accent threshold, in days. PO ruling 2026-08-25,
#: closing decision D4.** *"`REQ-01`'s `AGE` column accents a row once the
#: request is 7 days old or more; below that it renders plain."*
#:
#: ⚠ **THE BOUNDARY IS INCLUSIVE, AND THAT IS THE HALF A CARELESS READING GETS
#: WRONG.** `age_days >= AGE_ACCENT_DAYS`, never `>`. The eight seeded requests
#: cannot catch the difference — their ages are 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0,
#: so the nearest row to the line is `5d`, two days clear of it, and a `>`
#: reading passes on the whole fixture. `test_br_cus_106_*` asserts 6 · 7 · 8
#: explicitly for exactly that reason.
#:
#: The figure was RULED, never derived: B19 §12.1's drawing accents `15d` and
#: `11d` and leaves `5d` plain, which bounds the threshold to 6–11 days and no
#: further. Until 2026-08-25 `list_row` REFUSED to serve the flag rather than
#: pick a number inside that bound.
AGE_ACCENT_DAYS = 7


def age_is_accented(age_days: int | None) -> bool | None:
    """BR-CUS-106, in one place so the screen and the KPI cannot disagree.

    `None` in, `None` out: a request with no `received_at` has no age, and
    "we do not know how old this is" is not the same claim as "it is not old"
    (CLAUDE.md rule: never fabricate a value beside an absence).
    """
    if age_days is None:
        return None
    return age_days >= AGE_ACCENT_DAYS


# ═══════════════════════════════════════════════════════════════════════════
# THE EVIDENCE, AND THE VERDICT PER OPTION
# ═══════════════════════════════════════════════════════════════════════════
FITS_THE_EVIDENCE = "fits_the_evidence"
NOT_POSSIBLE = "not_possible"
POSSIBLE = "possible"


@dataclass(frozen=True)
class Evidence:
    """What the address resolver and the customer link FOUND. Facts only.

    `lookup_found` is the sentence the clerk reads — *"Served, and the unit is
    vacant"* — and it is STORED on the request (B19 §7), not recomputed at
    render time. The premises the request resolved to may be created, renamed or
    demolished after the decision; the sentence the decision was made on may not
    move with it.
    """

    resolution_kind: str = _SR.RESOLUTION_UNRESOLVED
    #: A premises row exists for the address as given.
    premise_exists: bool = False
    #: The resolved unit is served (has at least one service point).
    unit_is_served: bool = False
    #: The resolved unit has no occupying account (BR-MET-036's derived vacancy).
    unit_is_vacant: bool = False
    #: A live account at THIS address held by the matched customer.
    applicant_holds_account_here: bool = False
    #: A live account ANYWHERE held by the matched customer — what a transfer
    #: moves (*"A transfer moves a live account between two of your addresses"*).
    applicant_holds_live_account_anywhere: bool = False
    lookup_found: str | None = None


#: The five options, each with the message key its `not_possible` sentence
#: resolves to. **Every one of these sentences is the PO's own screen copy**
#: (B19 §12.3) — they are catalogue keys and not literals, per the 2026-08-19
#: ruling that server text never reaches a customer screen (G32/G33).
_REASON_KEY = "customers.serviceRequest.verdict"

_OPTION_ORDER = (
    _SR.OUTCOME_NEW_CONNECTION,
    _SR.OUTCOME_MOVE_IN,
    _SR.OUTCOME_MOVE_OUT,
    _SR.OUTCOME_TRANSFER,
    _SR.OUTCOME_DISCONNECT,
)


def outcome_verdicts(evidence: Evidence) -> list[dict[str, Any]]:
    """`WHAT SHOULD THIS BECOME?` — one row per option, in the drawn order.

    Returns `[{outcome, verdict, message_key}]`. **Nothing is preselected**, so
    it is perfectly lawful — and normal — for no row to carry
    `FITS_THE_EVIDENCE`: the resolver may not have run.
    """
    rows: list[dict[str, Any]] = []
    for outcome in _OPTION_ORDER:
        verdict, key = _verdict_for(outcome, evidence)
        rows.append({"outcome": outcome, "verdict": verdict, "message_key": key})
    return rows


def _verdict_for(outcome: str, ev: Evidence) -> tuple[str, str | None]:
    if outcome == _SR.OUTCOME_NEW_CONNECTION:
        # ⛔ **THE `premise_exists` REFUSAL IS WITHDRAWN — `DEF-CUS-6109`, and
        # THE DRAWING IS WHY.** It awarded `NOT_POSSIBLE` with the sentence
        # *"There is already a premise record at this address — service exists
        # here"*, which greyed the option on every request whose address the
        # resolver had matched. **Accounts blueprint p089, read AS AN IMAGE at
        # scale 2.4 (`B14` rule 42), draws the opposite on that exact case:**
        # `SR-26-0001` matched `PR-0731 · exact` and `U-001884 · exact` (p088),
        # and the approve modal draws `A new connection` **live and chosen**,
        # with its consequence line *"Raises a build on the New connects tab,
        # linked back to this request."* The drawn callout settles it in one
        # sentence — *"Nothing is preselected, deliberately. The resolver
        # matched this address to PR-0731 exactly, and that is EVIDENCE — not
        # the decision."*
        #
        # An existing property with no service IS an ordinary new connection;
        # the wizard simply has no address to create. So the option is
        # `POSSIBLE` — this module's third verdict, *the evidence does not rule
        # this out and nothing rules it in* — and NOT `FITS_THE_EVIDENCE`, which
        # no screen draws for a matched address and which would be this lane
        # inverting a withdrawn sentence into a rule (OQ-356, and the header of
        # this module).
        if ev.resolution_kind == _SR.RESOLUTION_NO_PREMISE:
            # Drawn on the Location tab: `Resolved to → No premise record` ·
            # `Consequence → This becomes a new connection`
            return FITS_THE_EVIDENCE, f"{_REASON_KEY}.newConnection.noPremiseRecord"
        return POSSIBLE, None

    if outcome == _SR.OUTCOME_MOVE_IN:
        if ev.unit_is_served and ev.unit_is_vacant:
            # Drawn: "The unit is served and vacant, so somebody is taking over
            # service that already exists"
            return FITS_THE_EVIDENCE, f"{_REASON_KEY}.moveIn.servedAndVacant"
        return POSSIBLE, None

    if outcome == _SR.OUTCOME_MOVE_OUT:
        if not ev.applicant_holds_account_here:
            # Drawn: "The applicant holds no live account at this address, so
            # there is nothing to close"
            return NOT_POSSIBLE, f"{_REASON_KEY}.moveOut.noAccountHere"
        return POSSIBLE, None

    if outcome == _SR.OUTCOME_TRANSFER:
        if not ev.applicant_holds_live_account_anywhere:
            # Drawn: "A transfer moves a live account between two of your
            # addresses. There is no live account here"
            return NOT_POSSIBLE, f"{_REASON_KEY}.transfer.noLiveAccount"
        return POSSIBLE, None

    if outcome == _SR.OUTCOME_DISCONNECT:
        # ⚠ **THE REASON THAT USED TO LIVE HERE IS WITHDRAWN — BR-CUS-091 (PO
        # 2026-08-24, *"Yes customer can request it"*).** The screen said a
        # disconnect *"is only ever started by collections, never from a
        # customer request"* and the LIST drew one anyway; the ruling says the
        # list was right and the sentence is withdrawn.
        #
        # So this option gets `POSSIBLE` — the module's third verdict, *the
        # evidence does not rule this out and nothing rules it in* — and NOT
        # `FITS_THE_EVIDENCE`. No screen draws that badge for a disconnect, and
        # awarding it would be inverting a withdrawn sentence into a rule, which
        # is precisely the mistake the header of this module exists to refuse
        # (OQ-356). Which evidence state SHOULD fit a disconnect is part of that
        # same open question.
        return POSSIBLE, None

    raise ServiceRequestRuleError(f"unknown outcome {outcome!r}")


def verdict_for(outcome: str, evidence: Evidence) -> str:
    return _verdict_for(outcome, evidence)[0]


# ═══════════════════════════════════════════════════════════════════════════
# THE CONDITIONS THAT GATE APPROVAL
# ═══════════════════════════════════════════════════════════════════════════
CONDITION_CLEAR = "clear"
CONDITION_BLOCKED = "blocked"
CONDITION_UNKNOWN = "unknown"
CONDITION_NOTED = "noted"
#: ⊕ **DEF-CUS-6350, 2026-09-23 — a check that could not be ASKED, because one
#: before it failed.** *Is the unit free?* has no answer while no unit is known,
#: and printing `blocked` there would report a second blocker the product never
#: found (the kit's `Chain` draws the same state as *Never reached* for the same
#: reason). It is never `clear` and never blocking: the check it waits on is the
#: one that blocks, and it is the ONE the clerk is sent to fix.
CONDITION_NOT_REACHED = "not_reached"

#: ⚠ **THE SCREEN SAYS FIVE AND FOUR ARE IDENTIFIABLE — OQ-355.**
#: B19 §12.3 renders *"4 of 5 conditions clear"* and names three rows on screen
#: (`No blocking arrears` ✓ · `Eligibility evidence` — *None claimed — does not
#: block* · the document refusal *"documents verified: 2 of 3"*). REQ-03.5's
#: `Collect later` names the fourth in its own copy: *"the review step lists the
#: unpaid fee as a blocking condition. Nothing is refused — it simply cannot be
#: approved yet."* **The fifth is not drawn and is not invented here.** The read
#: model reports `of 4` with the gap stated and OQ-355 cited; it never prints a
#: `5` it cannot itemise.
CONDITION_KEYS = (
    "no_blocking_arrears",
    "eligibility_evidence",
    "documents_verified",
    "fee_settled",
)


@dataclass
class Condition:
    key: str
    state: str
    blocking: bool
    message_key: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def clear(self) -> bool:
        return self.state in (CONDITION_CLEAR, CONDITION_NOTED)


def arrears_condition(
    *, search_done: bool, amount_owed: Decimal | None, books_unavailable_reason: str | None
) -> Condition:
    """`Existing customer` — *"We search for any account you have held before,
    and check for anything outstanding on it."* (REQ-03.sent, `WHAT HAPPENS
    NEXT`), rendered on the Decision tab as `CLEAR` — *"…with nothing
    outstanding on A-11024. Nothing here blocks approval."*

    **An absent answer is never spelled the same way as zero.** DEF-127 cost a
    customer owing $108.88 being shown $0.00 on the one screen a clerk opens to
    find out; `apps.customers.seams.ArPositions` returns None rather than
    `Decimal("0")` when the books cannot be asked, and this condition carries
    that None through as `unknown` **and blocks**. A guessed "nothing
    outstanding" is exactly the sentence a clerk would approve on.
    """
    if not search_done:
        return Condition(
            "no_blocking_arrears",
            CONDITION_BLOCKED,
            True,
            "customers.serviceRequest.condition.arrearsNotSearched",
        )
    if books_unavailable_reason is not None or amount_owed is None:
        return Condition(
            "no_blocking_arrears",
            CONDITION_UNKNOWN,
            True,
            "customers.serviceRequest.condition.arrearsUnknown",
            {"reason": books_unavailable_reason or "ledger_unavailable"},
        )
    if amount_owed > 0:
        return Condition(
            "no_blocking_arrears",
            CONDITION_BLOCKED,
            True,
            "customers.serviceRequest.condition.arrearsOutstanding",
            {"amount": str(amount_owed)},
        )
    return Condition("no_blocking_arrears", CONDITION_CLEAR, False)


def eligibility_condition(*, claimed: bool) -> Condition:
    """B19 §12.3 draws it as *"None claimed — does not block"*, and B18 §5.3.4
    states the rule the other half of the time too: eligibility *"Never blocks
    service — only the discount"*. So this condition is reported and never
    gates: `blocking` is False on BOTH branches, which is the whole point of it
    appearing in the list at all."""
    if claimed:
        return Condition(
            "eligibility_evidence",
            CONDITION_NOTED,
            False,
            "customers.serviceRequest.condition.eligibilityClaimed",
        )
    return Condition("eligibility_evidence", CONDITION_CLEAR, False)


def documents_condition(
    *,
    total: int,
    verified: int,
    rejected: int,
    awaiting_file: int,
    checklist_unmet: tuple[str, ...] = (),
) -> Condition:
    """**GATE TWO, AND IT IS NO LONGER A GATE. Documents are REPORTED, never
    blocking — PO ruling 2026-09-16.**

    ⚠ **VERBATIM, and the reasoning is the PO's own rather than ours:** *"see
    anyway we are creating draft move in request , in such case clark can add
    document later; it is good that documents are available when request is
    submitted and aporve but lets not make it mandetory"*, and on how to say so,
    *"if you want ywe can show the messge documents will be required"*. Every
    approval now raises a DRAFT job whose own wizard asks for the rest, and a
    draft job is precisely a place where a missing document can still arrive;
    holding the approval to protect a job that has not started yet protects
    nothing.

    ⚠ **SO `blocking` IS FALSE ON EVERY BRANCH AND THE STATE IS STILL
    `blocked`, AND BOTH HALVES ARE DELIBERATE.** `blocking=False` is what takes
    it out of `blocking_conditions`, so approval proceeds. The STATE stays
    `blocked` — never `noted` — because `Condition.clear` reads the state, and
    calling this clear would print *"4 of 4 conditions clear"* over a request
    with two documents unchecked. **Not mandatory is not the same as not
    mentioned**: the clerk is told before they press, the queue still shows what
    is outstanding, and `waiting_on` is untouched.

    ⚠ **THE SENTENCES BELOW ARE STILL THIS FUNCTION'S ANSWER AND ARE WHAT THE
    CLERK READS.** They are the only place the product says WHICH documents are
    missing, so the message key and its params matter more now than when they
    gated something. The one that claimed approval waits (`requiredDocumentMissing`)
    was re-worded in all eleven catalogues in the same commit — a sentence
    describing a rule that has just been reversed is hard-won law 1 wearing a
    translation.

    ⚠ **WHAT THIS RULING DID NOT TOUCH:** the arrears condition still BLOCKS.
    It asks whether anybody has looked, which is a question about a PERSON and
    cannot be answered later by a job.

    ── superseded, kept because it is quoted elsewhere ──────────────────────
    B19 §12.4 called this the finding of that batch, and the detail said it in
    the clerk's own words: *"1 document still to verify. Approval is blocked
    until somebody checks each one — attaching a file is not the same as
    verifying it."* **The second sentence is SUPERSEDED (PO 2026-09-16 →
    documents no longer block); the third is still true and is still said.**
    The blueprint says it twice more, on p083 (*"The money does not gate
    approval and the documents do"*) and p084 (*"approval is exactly the thing
    it blocks"*), and **both of those sentences are now false and must not be
    shipped.**

    ✅ **AND IT NOW COMPARES AGAINST THE TENANT'S OWN CHECKLIST — BR-CUS-095
    (PO 2026-08-24), which closed OQ-351.** *"Settings grows a checklist — for
    each request type, tick which documents are required. We ship with nothing
    ticked, and a utility that configures nothing blocks nothing."*

    `checklist_unmet` is the doc types the tenant ticked for THIS request's
    outcome that are not both attached AND verified. **An empty tuple is the
    normal case and the shipped case**: no ticks, nothing unmet, nothing
    blocked. The caller (`service_request_reads._documents_condition`) reads the
    checklist; the arithmetic lives here where a test can reach it with no
    database.

    ⚠ **ORDER MATTERS AND IS DELIBERATE.** A ticked document that was never
    supplied is reported BEFORE an attached-but-unverified one, because *"go and
    get the deed"* and *"go and check the deed you have"* are different
    instructions to different people, and the clerk reads the first sentence.
    """
    if checklist_unmet:
        return Condition(
            "documents_verified",
            CONDITION_BLOCKED,
            # ⚠ REPORTED, NOT BLOCKING — PO 2026-09-16. See the docstring.
            False,
            "customers.serviceRequest.condition.requiredDocumentMissing",
            {"count": len(checklist_unmet), "doc_types": ",".join(checklist_unmet)},
        )
    if awaiting_file:
        return Condition(
            "documents_verified",
            CONDITION_BLOCKED,
            # ⚠ REPORTED, NOT BLOCKING — PO 2026-09-16. See the docstring.
            False,
            "customers.serviceRequest.condition.documentMissing",
            {"count": awaiting_file},
        )
    if rejected:
        return Condition(
            "documents_verified",
            CONDITION_BLOCKED,
            # ⚠ REPORTED, NOT BLOCKING — PO 2026-09-16. See the docstring.
            False,
            "customers.serviceRequest.condition.documentRejected",
            {"count": rejected},
        )
    if verified < total:
        return Condition(
            "documents_verified",
            CONDITION_BLOCKED,
            # ⚠ REPORTED, NOT BLOCKING — PO 2026-09-16. See the docstring.
            False,
            "customers.serviceRequest.condition.documentsUnverified",
            {"verified": verified, "total": total},
        )
    return Condition("documents_verified", CONDITION_CLEAR, False)


def fee_condition(
    *,
    outstanding_lines: int,
    outstanding_amount: Decimal | None = None,
    currency: str | None = None,
) -> Condition:
    """REQ-03.5 `Collect later`, verbatim: *"The request will show $130.00
    outstanding until it is paid, and the review step lists the unpaid fee as a
    blocking condition. **Nothing is refused — it simply cannot be approved
    yet.**"*

    ✅ **IT READS THE OUTSTANDING FIGURE NOW — BR-CUS-090 (PO 2026-08-24), which
    closed DEF-637.** This condition used to count LINES and refuse to state a
    figure, because the capture totalled $130.00 and the receipt said $25.00 for
    the same cash and no lane could pick between them. The ruling says both were
    right about their own half: *"we acept it and in finance we will reconcile ;
    here segregation of responsibilitys, accept it and mark it as cash"*. The
    quote is the quote, the collection is the collection, **and the difference
    is an open fee balance the review step reads.**

    ⛔ **THE FEE NO LONGER BLOCKS — PO RULING 2026-09-21, verbatim: *"make
    application fees optional - so that we can approve it"*.** The sentence
    quoted at the top of this docstring is REQ-03.5's and it is SUPERSEDED in
    its second half: the request still *shows* the outstanding figure, and it is
    no longer true that it *"simply cannot be approved yet."* `BR-CUS-090` is
    AMENDED — the row in `03-customers/02-business-rules.md` carries the date.

    ⚠ **READ THE RULING NARROWLY, BECAUSE THE STATE BELOW DOES NOT MOVE.** It
    does not abolish the fee, cancel what was collected or hide anything. The
    money is still owed, still totalled and still printed on the request. So the
    state stays `blocked` and only `blocking` goes False — **exactly the shape
    the documents ruling of 2026-09-16 took one function up**, and for the same
    reason: `Condition.clear` reads the STATE, so calling this clear would print
    *"4 of 4 conditions clear"* over a request with money outstanding. **Not
    mandatory is not the same as not mentioned.** The condition leaves
    `blocking_conditions` and lands in `outstanding_conditions`, which is the
    *told rather than refused* list.

    **Worked, on the screen that raised the defect:** quoted $130.00, taken
    $25.00 cash, receipt `RCP-26-4471` → `outstanding_amount` is **105.0000**,
    this condition reports `blocked` and NAMES that figure, and the request can
    be approved. Before 2026-09-21 the same request could not be approved at
    all, and neither door out of it worked (`DEF-CUS-6096`, `DEF-CUS-6097`).

    ⚠ **AND A SHORTFALL IS STILL NEVER A WAIVER.** Not blocking is not
    forgiving: the $105.00 stays an open fee balance on the request, and turning
    it into a waiver still needs `BR-CUS-073`'s explicit act with a reason. The
    ruling moved a GATE, not a figure.

    ⚠ **WHAT THE PO CORRECTED THE SAME DAY, KEPT HERE BECAUSE IT IS WHY THIS
    FUNCTION'S OLD DOCSTRING READS AS IT DOES:** *"in practical this does not
    ahppen - it is application fees - customer will pay it once or clark will
    wavie it off - $20 or $0 - some utilities will not take applciation fees
    also"*. A part payment against an application fee is a case we invented. The
    three real shapes are **paid once**, **waived**, and **no fee at all** — and
    the third one never reaches this function with anything to report, because a
    request with no fee lines and no collection is `outstanding == 0`.

    `outstanding_lines` is kept as the fallback for a request whose money was
    never totalled (a legacy row with lines and no collection record): a line
    that is neither settled nor waived is still REPORTED even if no figure is
    available, because *unknown* may never be spelled the same way as *paid*.

    ⛔⛔ **AND THE 2026-09-21 RULING IS ITSELF SUPERSEDED — PO 2026-09-23,
    `OQ-CUS-12617` CLOSED, `DEF-CUS-6420`.** Verbatim: *"we already told you -
    either fee is paid or waived - no other condition"*, after *"there are no
    unpaid fees either applcition fee is paid or it is waived - so this is not
    applicable anymore"*. **Approve waits again, and this time the reason is the
    opposite of the one above it:** not that the fee must be collected to
    approve, but that an approved request with money still owed on it is a state
    the PO has said cannot exist — nothing after approval ever collects it.

      * **paid in full** → `outstanding == 0` → clear;
      * **waived** → the waived line leaves the total (`BR-CUS-073`'s explicit
        act, with its reason) → clear;
      * **no fee lines at all** → `outstanding == 0` → clear, so a utility that
        charges none is untouched;
      * **part-paid** → BLOCKS, on the REMAINDER. Worked: quoted $130.00, taken
        $25.00 → *✗ Fee · $105.00 unpaid*, Approve off.

    ⚠ **THE DESK HALF OF `BR-CUS-090` IS NOT TOUCHED.** The counter still
    accepts a short payment and never refuses one; only APPROVAL waits. The
    sentence no longer says *"Approval is not blocked"* — that was rationale
    (B14 rule 33) and it became false — it says what to do.
    """
    if outstanding_amount is not None and outstanding_amount > 0:
        return Condition(
            "fee_settled",
            CONDITION_BLOCKED,
            # ⛔ BLOCKING AGAIN — PO 2026-09-23, `OQ-CUS-12617`. See the docstring.
            True,
            "customers.serviceRequest.condition.feeOutstandingAmount",
            {"amount": str(outstanding_amount), "currency": currency},
        )
    if outstanding_amount is None and outstanding_lines:
        return Condition(
            "fee_settled",
            CONDITION_BLOCKED,
            # ⛔ BLOCKING AGAIN — PO 2026-09-23, `OQ-CUS-12617`. See the docstring.
            True,
            "customers.serviceRequest.condition.feeOutstanding",
            {"count": outstanding_lines},
        )
    return Condition("fee_settled", CONDITION_CLEAR, False)


# ═══════════════════════════════════════════════════════════════════════════
# WHERE THE SERVICE GOES — DEF-CUS-6350, PO rulings of 2026-09-23
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim, first: *"on this screen when user select move-in , also check
# whether premise available and unit without this check move-in not work , This
# check is not required in newconnection"*; then, on the new connection, *"we
# should allow only if address is not available in register … on active presmies
# we cannot do new conenct - sicne it is physical address and service conenctions
# build process"* and *"we dont allow these status - dont create new request even
# if property is in draft, pending or inactive"*.
#
# **Until this, approval asked four questions about the APPLICANT and the MONEY
# and none about the PLACE.** A move-in onto a unit somebody already occupies was
# approved and discovered on move day, when `services._refuse_if_unit_occupied`
# refused the account; two move-ins for one unit were both approved, and the
# second failed only when its account opened.
#
# ⚠ **EVERY ONE OF THESE IS A `Condition`, SO `_refuse_unless_approvable`
# ENFORCES IT WITH NO SECOND CODE PATH** — the window greys Approve on the same
# rows the server refuses on, because they are the same rows.
#
# ⚠ **THEY APPLY TO ONE OUTCOME EACH.** The move-in four are asked only of a
# move-in and the new-connection two only of a new connection; the other three
# outcomes carry neither, because none of them opens service at an address.
#
# ⚠ **THE PURE HALF LIVES HERE; THE READS LIVE IN `service_request_reads`.**
# The same split as the four above it: the arithmetic of *which sentence* is
# testable with no database, and the reads — the premises, the occupier, the
# waiting job — are assembled where the tables are.

#: The move-in four, in the order the Approve window draws them.
PREMISES_ON_FILE = "premises_on_file"
UNIT_CHOSEN = "unit_chosen"
UNIT_FREE = "unit_free"
NO_OTHER_MOVE_IN = "no_other_move_in"
MOVE_IN_PLACE_KEYS = (PREMISES_ON_FILE, UNIT_CHOSEN, UNIT_FREE, NO_OTHER_MOVE_IN)

#: The new-connection two.
ADDRESS_NOT_IN_PREMISES = "address_not_in_premises"
NO_OPEN_REQUEST_HERE = "no_open_request_here"
NEW_CONNECTION_PLACE_KEYS = (ADDRESS_NOT_IN_PREMISES, NO_OPEN_REQUEST_HERE)

#: ⊕ **A CHECK THAT ASKS THE CLERK A QUESTION.** A near match — `highland pk`
#: against `Highland Park` — is neither in Premises nor out of it until a person
#: says which (the owner match's PO decision 3, *"offer the match, clerk
#: decides"*). It BLOCKS, so Approve stays off by default and a duplicate can
#: never be created by not looking; it is not a refusal, so the window draws it
#: as a question with its two answers rather than as a red cross.
CONDITION_CHOOSE = "choose"

_C = "customers.serviceRequest.condition."


def premises_on_file_condition(*, place: dict[str, Any] | None) -> Condition:
    """**(1) The address resolved to a premises in Premises.**

    `place` is the premises as metering names it (`address_match.premises_label`)
    or `None` when the request names none. A request whose address never
    resolved cannot open an account anywhere, so the move-in stops here — and
    the three checks below it are *not reached* rather than failed.
    """
    if place is None:
        return Condition(PREMISES_ON_FILE, CONDITION_BLOCKED, True, _C + "propertyNotOnFile")
    label = str(place.get("label") or place.get("address_line") or "")
    city = place.get("city") or None
    return Condition(
        PREMISES_ON_FILE,
        CONDITION_CLEAR,
        False,
        _C + "propertyOnFile",
        # `place` is the address itself rather than prose: a label and a town,
        # joined the way every language on this product writes an address line.
        {"property": label, "city": city, "place": f"{label}, {city}" if city else label},
    )


def unit_chosen_condition(
    *, premises_found: bool, unit: dict[str, Any] | None, units_at_premises: int | None
) -> Condition:
    """**(2) A unit is chosen where the premises has units.**

    ⚠ **A PREMISES WITH NO UNITS AT ALL IS ALSO REFUSED, AND THAT IS A READING
    OF THE RULING RATHER THAN A WIDENING OF IT.** The ruling's words are *"a unit
    is chosen where the premises has units"*; taken alone they would let a
    move-in through onto a property with none. But a move-in OPENS AN ACCOUNT ON
    A UNIT — `services._eligible_unit` refuses an account with no unit
    (`customers.account.unit_required`, `BR-CUS-020`) — so that approval would
    fail on move day, which is the exact defect the PO reported (*"without this
    check move-in not work"*). It is refused here with its own sentence, so the
    clerk is told the building has no units rather than that they forgot to pick
    one.

    `units_at_premises` is `None` when metering could not be asked; the check
    then refuses to certify rather than guessing a count.
    """
    if not premises_found:
        return Condition(UNIT_CHOSEN, CONDITION_NOT_REACHED, False, _C + "needsProperty")
    if unit is not None:
        return Condition(
            UNIT_CHOSEN,
            CONDITION_CLEAR,
            False,
            _C + "unitChosen",
            # B14 rule 31 — the NUMBER and the label; the id never travels here.
            {"unit_no": unit.get("unit_no") or "", "label": unit.get("label") or ""},
        )
    if units_at_premises is None:
        return Condition(UNIT_CHOSEN, CONDITION_UNKNOWN, True, _C + "unitsUnknown")
    if units_at_premises == 0:
        return Condition(UNIT_CHOSEN, CONDITION_BLOCKED, True, _C + "propertyHasNoUnits")
    return Condition(
        UNIT_CHOSEN,
        CONDITION_BLOCKED,
        True,
        _C + "unitNotChosen",
        {"count": units_at_premises},
    )


def unit_free_condition(*, unit_known: bool, occupier: dict[str, Any] | None) -> Condition:
    """**(3) The unit is free — no live account occupies it.**

    `occupier` is `selectors.active_account_for_unit`, which reads the ONE
    occupancy query (`occupying_accounts_for_unit`) — so a vacant unit billed to
    a MASTER account reads FREE here exactly as it does on move day: master and
    owner accounts name no unit (`BR-CUS-1010`/`BR-CUS-1012`), so they occupy
    none.

    ⚠ **THE REFUSAL NAMES WHO IS THERE BY ACCOUNT NUMBER, NEVER BY ID** (B14
    rule 31) — `AC-2026-00012`, the number the clerk can look up.
    """
    if not unit_known:
        return Condition(UNIT_FREE, CONDITION_NOT_REACHED, False, _C + "needsUnit")
    if occupier is not None:
        return Condition(
            UNIT_FREE,
            CONDITION_BLOCKED,
            True,
            _C + "unitOccupied",
            {"account_no": occupier.get("account_no") or ""},
        )
    return Condition(UNIT_FREE, CONDITION_CLEAR, False, _C + "unitFree")


def no_other_move_in_condition(
    *, unit_known: bool, waiting: list[dict[str, Any]]
) -> Condition:
    """**(4) No other move-in is already waiting for that unit.**

    `waiting` is every PENDING `move_in_jobs` row whose application resolved to
    this unit, other than this request's own — the PO's own case: `SR-26-0016`
    and `SR-26-0013` both ask for `U-00003`, and whichever is approved first
    raises the job this refuses the second on. Named by the APPLICATION's number,
    which is the number on the list the clerk is working.
    """
    if not unit_known:
        return Condition(NO_OTHER_MOVE_IN, CONDITION_NOT_REACHED, False, _C + "needsUnit")
    if waiting:
        first = waiting[0]
        return Condition(
            NO_OTHER_MOVE_IN,
            CONDITION_BLOCKED,
            True,
            _C + "moveInWaiting",
            {
                "request_no": first.get("request_no") or "",
                "move_no": first.get("move_no") or "",
                "count": len(waiting),
            },
        )
    return Condition(NO_OTHER_MOVE_IN, CONDITION_CLEAR, False, _C + "noOtherMoveIn")


def address_not_in_premises_condition(
    *,
    resolved: dict[str, Any] | None,
    match: dict[str, Any] | None,
    as_given: str,
    declared_new: bool,
) -> Condition:
    """**A new connection only where the address is NOT in Premises — in ANY
    status** (PO ruling 2026-09-23, `OQ-CUS-12615` CLOSED).

    A new connection BUILDS a physical service connection, so it is refused at
    a property already on file, and **`premises.status` is never read**: every
    premises is written `active` at creation, and the PO ruled out `draft`,
    `pending` and `inactive` too. PRESENCE decides.

      * the request RESOLVED to a premises → refused, naming it;
      * an EXACT match on file → refused, naming it (no choice: it is there);
      * a NEAR match → `choose` — Approve stays off until the clerk says *same
        property* (which picks it onto the request, and then the first branch
        refuses) or *it's a new address* (`declared_new`, sent WITH the
        approval, which clears this);
      * nothing close → clear. The build creates the address at its last button.

    `match` is `None` when metering could not be asked. That refuses to certify
    — `unknown`, blocking — because *not checked* must never read as *not on
    file* on the one screen that is about to let a duplicate be built.
    """
    if resolved is not None:
        return Condition(
            ADDRESS_NOT_IN_PREMISES,
            CONDITION_BLOCKED,
            True,
            _C + "addressInPremises",
            {"property": resolved.get("label") or resolved.get("address_line") or ""},
        )
    if match is None:
        return Condition(ADDRESS_NOT_IN_PREMISES, CONDITION_UNKNOWN, True, _C + "addressNotChecked")
    kind = match.get("match")
    candidates = list(match.get("candidates") or [])
    if kind == "exact" and candidates:
        return Condition(
            ADDRESS_NOT_IN_PREMISES,
            CONDITION_BLOCKED,
            True,
            _C + "addressInPremises",
            {"property": candidates[0].get("label") or ""},
        )
    if kind == "near" and candidates and not declared_new:
        best = candidates[0]
        postal = best.get("postal_code") or None
        label = best.get("label") or ""
        return Condition(
            ADDRESS_NOT_IN_PREMISES,
            CONDITION_CHOOSE,
            True,
            _C + "addressLooksLike",
            {
                "as_given": as_given,
                "property": label,
                "place": f"{label}, {postal}" if postal else label,
                # The id rides so *Same property* can PICK the row through the
                # capture door; it is never rendered (B14 rule 31).
                "premises_id": best.get("id"),
                "premise_no": best.get("premise_no"),
            },
        )
    return Condition(ADDRESS_NOT_IN_PREMISES, CONDITION_CLEAR, False, _C + "addressNotInPremises")


def no_open_request_condition(
    *, address_reached: bool, open_elsewhere: list[dict[str, Any]] | None
) -> Condition:
    """**Two open new-connection applications for one NEW address — the second
    is refused.** Both builds would create that premises at their last button,
    which is the one duplicate the address check above cannot see, because the
    first premises does not exist yet.

    `open_elsewhere` is every OTHER approved new-connection application whose
    address is the same after tidying and whose build is still open; `None`
    when metering could not be asked (refuses to certify, as above).
    """
    if not address_reached:
        return Condition(NO_OPEN_REQUEST_HERE, CONDITION_NOT_REACHED, False, _C + "needsAddress")
    if open_elsewhere is None:
        return Condition(NO_OPEN_REQUEST_HERE, CONDITION_UNKNOWN, True, _C + "openRequestsUnknown")
    if open_elsewhere:
        first = open_elsewhere[0]
        return Condition(
            NO_OPEN_REQUEST_HERE,
            CONDITION_BLOCKED,
            True,
            _C + "openRequestHere",
            {
                "request_no": first.get("request_no") or "",
                "connection_no": first.get("connection_no") or "",
                "count": len(open_elsewhere),
            },
        )
    return Condition(NO_OPEN_REQUEST_HERE, CONDITION_CLEAR, False, _C + "noOpenRequestHere")


def blocking_conditions(conditions: list[Condition]) -> list[Condition]:
    return [c for c in conditions if c.blocking and not c.clear]


def outstanding_conditions(conditions: list[Condition]) -> list[Condition]:
    """Not clear, and does not stop the press — *told*, rather than *refused*.

    ⚠ **THIS SET WAS EMPTY UNTIL 2026-09-16 AND IT IS WHY THE RULING NEEDED
    CODE AT ALL.** Before the documents ruling every unsatisfied condition also
    blocked, so *not clear* and *refused* were the same list and one of them was
    enough. They are now two different lists with two different jobs: the
    blocking one greys the commit, and this one is the *"show the messge
    documents will be required"* half the PO asked for in the same breath as
    *"lets not make it mandetory"*.

    **A condition in neither list is CLEAR. A condition in both is impossible** —
    the two are complements over `not c.clear`, which is what stops a lane
    reading the same row as both a refusal and a notice.
    """
    # ⊕ DEF-CUS-6350 — a `not_reached` check is neither: it waits on a blocker
    # that IS in `blocking_conditions`, and listing it again as *still needed*
    # would tell the clerk about one problem three times.
    return [
        c
        for c in conditions
        if not c.blocking and not c.clear and c.state != CONDITION_NOT_REACHED
    ]


def conditions_summary(conditions: list[Condition]) -> dict[str, Any]:
    """What REQ-02's `Conditions` panel prints, with its own gap stated.

    ⚠ `total` is **4**, not the 5 the screenshot renders. See `CONDITION_KEYS` —
    the fifth condition is not drawn and OQ-355 asks what it is. A read model
    that printed `5` would be claiming to have checked something it cannot name.
    """
    return {
        "clear": sum(1 for c in conditions if c.clear),
        "total": len(conditions),
        "blocking": [c.key for c in blocking_conditions(conditions)],
        # ⚠ PO 2026-09-16 — *told*, not *refused*. See `outstanding_conditions`.
        # A screen that renders `blocking` alone now says nothing at all about a
        # request with two unchecked documents, which is the failure the ruling
        # names as the worse of the two.
        "outstanding": [c.key for c in outstanding_conditions(conditions)],
        "conditions": [
            {
                "key": c.key,
                "state": c.state,
                "blocking": c.blocking,
                "message_key": c.message_key,
                "params": c.params,
            }
            for c in conditions
        ],
        # G38's discipline, applied to a served payload: a stated absence names
        # the row that will close it.
        "count_differs_from_design": {
            "designed_total": 5,
            "served_total": len(conditions),
            "tracks": "OQ-355",
        },
    }
