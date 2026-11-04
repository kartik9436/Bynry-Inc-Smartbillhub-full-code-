# ── Trace ──────────────────────────────────────────────
# Change:   The MOVE RECORD screen, blueprint `02 Accounts Menu Blueprint.pdf`
#           p074 — *"The move-in, opened · MVI-26-0114 ·
#           /brazosbend/moves/mvi-26-0114 · Proposed · the record of the act,
#           and a door to the account it opened"*. Approved by the PO on
#           2026-09-19 (*"we have to buid … we have it in drawing that is our
#           next work"*), specified in
#           04-docs/05-modules/03-customers/conformance/
#           move-in-wizard-against-its-blueprint.md.
# Rules:    **BR-CUS-150/151** (a move is a RECORD of the JOB; it copies no
#           fact that already has an owner — so this module ASSEMBLES and
#           stores nothing) · **BR-CUS-056** (the earliest legal start is the
#           day after the previous occupant left) · **BR-MET-1161** (hard rule
#           8: an address lives on `premises`; a unit refines it by LABEL, so
#           the address is WALKED, never read off the account) · BR-CUS-023/024
#           (the deposit is a LOOKUP; carry-forward mechanics are PROPOSED) ·
#           B1 (no cross-module join — metering and payments are reached
#           through `seams` or not at all) · B14 rule 31 (no database id is a
#           field's visible value) · B14 rules 32/33 (what the SCREEN may say)
#           · CLAUDE.md rule 1 (tenant scoping / RLS FORCE)
# Screens:  the MOVE RECORD, `/moves/{ref}` — a NEW top-level route, not under
#           `/accounts/`
# Tests:    06-backend/tests/test_move_record_page.py
# Impacts:  apps/customers/api.py (one view, one route) ·
#           07-frontend/src/features/customers/MoveRecordPage.tsx
# ───────────────────────────────────────────────────────
"""The MOVE RECORD, assembled for one screen — `GET /moves/{ref}`.

═══════════════════════════════════════════════════════════════════════════
1 · THE DESIGN POINT, AND IT IS THE WHOLE SCREEN
═══════════════════════════════════════════════════════════════════════════
The blueprint states it on p074, verbatim:

    *"This record has no actions, and that is the answer rather than a gap. A
    move-in and a sale are records of acts that have already happened — there
    is nothing left to decide on them, so the only controls are doors to the
    account and the customer. The two things this record says are still wrong
    are deliberately not buttons here: the property's owner record and the
    account's contact details are both fixed on their own screens, by somebody
    who can see the whole picture."*

⚠ **SO NOTHING ON THIS PAGE CHANGES THE MOVE, AND THAT IS ON PURPOSE.** It is
unusual enough that somebody will try to "improve" it later, which is why it is
written down here before it is built rather than left to be inferred from the
absence of a verb.

**The PO ruled the control set on 2026-09-19 and it is TWO DOORS:**
`Open the account` (drawn) and `Open the customer` (the drawing's own prose
names two doors and draws one). Verbatim: *"Open the account, Open the customer
- if requried otherwise we will ahev to link to exisitng one"* — so where the
move HAS a customer record the control opens it, and where it does not the
screen states the absence rather than pretending one exists. Linking a move to
an existing customer is its own piece of work and is NOT built here.

**Two controls the PO explicitly REMOVED, recorded so they are not re-proposed:**
`Raise a visit` — *"not required"*. `Record the reading` — *"if provdied in move
in"*: the readings come from the wizard's step 3, which already accepts them and
commits them through metering's event door, so a button here would be a second
door onto one act. **This record DISPLAYS the opening reads it was given and
never offers to create one.**

═══════════════════════════════════════════════════════════════════════════
2 · TWO TABLES ANSWER TO ONE ADDRESS, AND THAT IS WHAT MAKES THE URL STABLE
═══════════════════════════════════════════════════════════════════════════
`/moves/MVI-26-0114` resolves in two places, in this order:

| Table | When | What the screen gets |
|---|---|---|
| `move_records` | the move COMPLETED | the whole record |
| `wizard_parks` | the move is STILL IN FLIGHT | the head, and a stated absence for every fact the commit has not produced yet |

⚠ **THE SAME STRING NAMES BOTH, WHICH IS WHY A DRAFT IS REACHABLE AT ALL.**
`CR-122-BRC06` (2026-09-19) gave a move-in draft the reference it will be filed
under — `wizard_parks.reference`, allocated from the SAME `move_in` series —
and `moves.record_move` ADOPTS it rather than allocating a second. So the number
a clerk quoted while they waited is the number the finished job carries, the
draft row is deleted in the same transaction, and **this URL does not change
when the move commits.** A page that resolved only `move_records` would 404 on
every row the list draws as `In progress`, which is half of what p073 draws.

⚠ **AN IN-FLIGHT MOVE HAS NO ACCOUNT, NO COMMITTED-BY AND NO OPENING READS**,
because none of them exists until the commit writes them. Each is served as a
STATED ABSENCE naming what it is waiting for — never as a blank, a dash or a
zero, which would read as *nobody recorded one* rather than *this has not
happened yet* (DEF-075 / DEF-127's rule, applied to a lifecycle instead of a
seam).

═══════════════════════════════════════════════════════════════════════════
3 · WHAT THIS MODULE MAY NOT REACH, STATED RATHER THAN FAKED
═══════════════════════════════════════════════════════════════════════════
**The cheque number on the deposit line is NOT servable today.** The drawing
draws *"Taken · cheque 4471"*. The tender and its confirmation live on the
PAYMENT row, which is payments' table; B1 forbids the join and **payments
publishes no read seam that returns a deposit payment for an account** —
measured 2026-09-19, `apps/payments/selectors.py` has `account_credit_position`,
`account_credit_sources` and `payment_account_id` and nothing that answers this.
So the money box serves the AMOUNT and the DATE from the register customers
owns (`accounts.deposit_on_file` / `deposit_received_on`, BR-CUS-670's writer)
and states the tender as an absence naming the seam it would take. A cheque
number invented here would be a figure nobody wrote.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from core import errors

# ═══════════════════════════════════════════════════════════════════════════
# THE STATED ABSENCES — every one names the column, seam or act it waits on
# ═══════════════════════════════════════════════════════════════════════════
#: ⛔ The move has not committed, so the account it will open does not exist.
#: A LIFECYCLE absence, not a missing column — see §2.
NO_ACCOUNT_UNTIL_IT_COMPLETES: dict[str, Any] = {
    "code": "move_has_not_opened_an_account_yet",
    "br_ref": "BR-CUS-018 · BR-CUS-150",
    "detail": (
        "This move-in has not completed, so no account has been opened and there is nothing "
        "to open a door onto. The account, the committed-by line and the opening reads are "
        "all written by the same commit, which is also when this row moves from the draft "
        "store into the move register."
    ),
}

#: ⛔ This move-in did not take over another account's unit, so there is no
#: outgoing account to name. An ORDINARY state and not a gap: a chained move-in
#: is one shape of the job and a fresh let is the other.
NOT_A_CHAINED_MOVE: dict[str, Any] = {
    "code": "move_did_not_follow_another_account",
    "br_ref": "BR-CUS-151",
    "detail": (
        "A chained move-in is the next occupant taking the unit an account is leaving, and "
        "`from_account` names that outgoing account. This move did not follow one, so there is "
        "nothing to name. A dash here would read as 'nobody recorded it'."
    ),
}

#: ⛔ Nothing committed this move yet, so nobody is recorded as having done it.
NOT_COMMITTED_YET: dict[str, Any] = {
    "code": "move_not_committed_yet",
    "br_ref": "BR-CUS-150 · BR-CUS-151",
    "detail": (
        "`performed_by` and `performed_at` are written at the commit and this move has not "
        "reached one. The clerk who parked the draft is recorded on the draft, which is a "
        "different fact from the clerk who completed the job."
    ),
}

#: ⛔ The clerk has not reached the step that asks for the date. `CR-035`'s
#: park keeps the TYPING and nothing else, so a draft parked on step 1 has no
#: move-in date because nobody has chosen one — not because it was lost.
NOT_CHOSEN_YET: dict[str, Any] = {
    "code": "move_in_date_not_chosen_yet",
    "br_ref": "BR-SHL-048 · BR-CUS-022",
    "detail": (
        "The move-in date is asked for on step 3 and this draft was parked before it. Nothing "
        "was lost: a parked draft holds what was typed and touches no records, so the date is "
        "simply not chosen yet."
    ),
}

#: **NOBODY WAS ASKED — and that is a different fact from *no reason*.**
#: PO ruling 2026-09-20 item 3. `accounts.close_reason` landed that day, so
#: every account closed before it holds NULL, and hard rule 4 forbids a
#: migration inventing one. This absence is what a completed move-out's record
#: shows over that NULL, so a clerk reading an old close is told the product
#: never asked rather than being shown a dash they would read as *unknown*.
CLOSE_REASON_NOT_ASKED: dict[str, Any] = {
    "code": "close_reason_was_not_asked",
    "br_ref": "BR-CUS-030",
    "detail": (
        "This account closed before the move-out screen began asking why, so no reason was "
        "recorded. Nothing was lost and nothing can be filled in now: a closed account is a "
        "permanent record, and writing a reason into one today would be inventing it."
    ),
}

#: The same column, NULL on a close made SINCE the screen began asking — the
#: clerk skipped the question. Separate from the one above on purpose: *we
#: never asked* and *we asked and they did not say* are two different states of
#: the utility's own record, and one sentence covering both would be wrong half
#: the time. Which one a row gets is decided by `closed_at` against the date
#: the column shipped — see `_close_reason_fact`.
CLOSE_REASON_NOT_GIVEN: dict[str, Any] = {
    "code": "close_reason_not_given",
    "br_ref": "BR-CUS-030",
    "detail": (
        "The clerk who closed this account did not say why. The question is optional on the "
        "move-out screen, so this is a complete record of what was entered — not a value that "
        "failed to save."
    ),
}

#: ⛔ BR-CUS-056 measures the earliest legal start against the PREVIOUS
#: occupant's last day, and a unit with no prior tenancy has no such day. An
#: ordinary state, not a gap: the first account on a new unit may start whenever
#: the utility likes.
NO_PRIOR_TENANCY_TO_MEASURE_FROM: dict[str, Any] = {
    "code": "no_prior_tenancy_on_this_unit",
    "br_ref": "BR-CUS-056",
    "detail": (
        "The earliest legal start is the day after the previous occupant left (BR-CUS-056), "
        "and this unit has no closed account before this one to measure from. There is no "
        "boundary day to state, and today's date standing in for one would be a wall clock "
        "answering a question about an event (BR-TEN-043)."
    ),
}

#: ⛔ The tender and its confirmation live on the payment row. See §3.
TENDER_NOT_READABLE_FROM_CUSTOMERS: dict[str, Any] = {
    "code": "deposit_tender_not_readable_from_customers",
    "br_ref": "B1 · BR-CUS-037 · BR-CUS-670",
    "detail": (
        "The blueprint draws the tender and its number — `Taken · cheque 4471`. Both are "
        "columns on the PAYMENT row, which payments owns, and payments publishes no read "
        "that returns a deposit payment for an account (measured 2026-09-19). B1 forbids the "
        "join, so the amount and the date are served from the register customers owns and the "
        "tender is stated rather than invented."
    ),
    "wanted_reads": (
        "apps.payments.selectors.deposit_payment_for_account(account_id) "
        "-> {amount, method, confirmation, posted_at, cleared_at}",
    ),
}

#: ⛔ BR-CUS-023 makes the deposit a LOOKUP from `plan_deposit_rules`, and this
#: account's plan × category pair names no rule. NOT the same fact as a standard
#: of zero — a plan that asks no deposit and a plan nobody wrote a rule for read
#: identically if either is printed as `$0.00`.
NO_PLAN_DEPOSIT_STANDARD: dict[str, Any] = {
    "code": "plan_states_no_deposit_standard",
    "br_ref": "BR-CUS-023 · BR-RAT-020",
    "detail": (
        "`plan_deposit_rules` names no deposit for this account's plan and consumer category, "
        "so there is no standard to compare what was taken against. A zero printed here would "
        "read as 'this plan asks for nothing', which is a different fact from 'nobody wrote a "
        "rule'."
    ),
}

#: ⛔ **NO DEPOSIT IS OWED ON THIS ACCOUNT AT ALL** — `accounts.deposit_assessed`
#: is NULL (`customers 0059`, `DEF-CUS-5909`). Two ordinary states reach it and
#: neither is a gap in the product: the clerk answered `No` on the deposit step
#: (`not_required` — none was ever assessed), or a supervisor **waived** one
#: (`BR-CUS-1050` — one was assessed and deliberately forgiven, so nothing is
#: still to collect). A third reaches it and IS historical: an account opened
#: before this column existed, which no migration may backfill (hard rule 4 —
#: deriving a figure now would write the very plan-standard number the defect
#: exists because we read).
#:
#: ⚠ **NOT THE SAME FACT AS `$0.00`.** A zero says *one was assessed and it is
#: fully collected*; this says *there is nothing to collect against*. Printing
#: either as the other is `DEF-CUS-5909` in the opposite direction.
#: `DEF-CUS-9755` — no deposit money is waiting to clear: nothing was taken by
#: a tender that clears later, or it has cleared, or payments could not be asked.
NOTHING_AWAITING_CLEARANCE: dict[str, Any] = {
    "code": "no_deposit_awaiting_clearance",
    "br_ref": "BR-CUS-025 · BR-CUS-670",
    "detail": (
        "No deposit payment on this account is recorded and still waiting to clear, "
        "so nothing stands between what was taken and what is still to collect."
    ),
}

NO_DEPOSIT_ASSESSED: dict[str, Any] = {
    "code": "no_deposit_assessed_on_this_account",
    "br_ref": "BR-CUS-1050 · BR-CUS-670",
    "detail": (
        "No deposit is owed on this account, so there is nothing for a shortfall to be "
        "measured against. Either none was assessed, or one was assessed and waived; a "
        "`$0.00` printed here would read as 'assessed and fully collected', which is a "
        "different fact."
    ),
}

#: ⛔ Carry-forward mechanics are PROPOSED (BR-CUS-024 / OQ-510) — there is no
#: column and no linkage to check. The blueprint draws this cell as an absence
#: too: *"Carry-forward · could not be checked"*.
CARRY_FORWARD_HAS_NO_MECHANISM: dict[str, Any] = {
    "code": "carry_forward_mechanics_are_proposed",
    "br_ref": "BR-CUS-024 · OQ-510",
    "detail": (
        "Whether a deposit carried over from the occupant's previous account is BR-CUS-024's "
        "question and its mechanics are PROPOSED: no column records an election and no "
        "linkage between the two accounts exists to walk. Nothing was checked, and a "
        "'carried nothing' printed here would be a verdict nobody derived."
    ),
}

#: ⛔ Work could not be asked. ⚠ **UNTIL 2026-10-04 THIS WAS SERVED ON EVERY
#: COMMITTED MOVE, AND IT WAS FALSE (`DEF-CUS-9628`).** Its sentence said Work
#: publishes no read keyed on a move record; `from_flows.acceptance` had been
#: published since CR-070 wave P, and a move-in read *Visit: Not raised* over a
#: visit raised, done and accepted. A committed move now reads
#: `seams.flow_work_visits` by its `MVO-`/`MVI-` number, and this absence is
#: served only when that seam answers None (Work not installed).
VISIT_NOT_READABLE: dict[str, Any] = {
    "code": "visit_not_readable_from_customers",
    "br_ref": "B1 · CR-070",
    "detail": (
        "Whether somebody was sent back to read the meter is a `work` fact. Work reads "
        "customers through its own seam and customers publishes no reciprocal read keyed on a "
        "move record, so this cannot be answered from here."
    ),
    "wanted_reads": ("apps.work.selectors.visits_for_move(move_record_id) -> list",),
}

#: ⛔ Work answered, and this move raised no field job. A TRUE absence: the
#: screen's *Not raised* is now a fact rather than a guess (`DEF-CUS-9628`).
NO_VISIT_RAISED: dict[str, Any] = {
    "code": "no_visit_raised",
    "br_ref": "BR-WRK-055",
    "detail": "This move raised no field job.",
}


#: ⛔ The move has a contact but no CUSTOMER row linked to the account it
#: opened. ⚠ This is the ORDINARY case on a move-in today, not an edge: measured
#: 2026-09-19 on the sample estate, the one seeded move-in's account carries ZERO
#: `customer_accounts` rows and the seeded move-out's carries one.
NO_CUSTOMER_LINKED: dict[str, Any] = {
    "code": "move_has_no_linked_customer",
    "br_ref": "BR-CUS-080",
    "detail": (
        "No customer record is linked to the account this move opened, so there is nobody to "
        "open. A move-in writes the occupant's contact details onto the account it creates and "
        "does not attach them to an existing customer; linking one is its own piece of work and "
        "is deliberately not offered from this record."
    ),
}

#: ⛔ The move committed no readings. A COUNT of zero is a real answer and is
#: NOT this absence — this one is served when the reads cannot be READ BACK,
#: which is a different fact.
READS_NOT_READABLE_HERE: dict[str, Any] = {
    "code": "opening_reads_not_readable",
    "br_ref": "B1 · BR-CUS-021 · CR-038 W9",
    "detail": (
        "The opening readings are metering's, reached through `seams.reads_for_unit`, and that "
        "seam could not answer for this unit: this deployment's metering publishes no "
        "`selectors.reads_for_unit`. None from a seam means 'cannot answer', never 'no reads'."
    ),
}

#: ⛔ The seam ANSWERED and the unit holds no meter, so no opening reading can
#: exist and none ever could. A configuration fact, stated the way
#: `move_reads.UNIT_HAS_NO_METERS` states it one table over.
UNIT_HAS_NO_METERS: dict[str, Any] = {
    "code": "unit_has_no_meters",
    "br_ref": "BR-MET-037 · BR-AST-028",
    "detail": (
        "The registry answered that this unit holds no asset, so there was no register to read "
        "when the move committed and there is none to read now. An empty reads table here is a "
        "configuration fact about the unit, not a job somebody failed to do."
    ),
}

#: The two `How` words the blueprint draws, and nothing else may appear in that
#: column. `READ` where a committed reading carries a figure; `NOT_ESTIMATED`
#: where the register opened with no figure AND no estimate stood in for one.
HOW_READ = "read"
HOW_NOT_ESTIMATED = "not_estimated"

#: The states this page renders. **THREE SINCE `BR-CUS-1090` (PO 2026-09-22)**,
#: from three tables and not §2's two: a finished `move_records` row, a
#: `wizard_parks` draft somebody is holding, and now an APPROVED move-in that
#: nobody has started — a `move_in_jobs` row carrying its own `MVI-`.
STATE_COMPLETED = "completed"
STATE_IN_FLIGHT = "in_flight"
#: ⚠ **`approved` AND NOT `in_flight`, AND THE WORD IS THE RULING.** A parked
#: draft is work somebody has BEGUN and put down; an approved job is work
#: nobody has touched. Folding them into one word would tell a clerk covering
#: somebody's desk that a job is half-done when nothing has been typed, and
#: `move_reads.MOVE_IN_STATE_PENDING` already keeps the two apart on the list
#: for exactly that reason (*"This row has no account at all"*).
STATE_APPROVED = "approved"

#: ⛔ Why an approved job has no opening reading, no money and no account. It is
#: a LIFECYCLE absence and not a missing column: every one of these facts is
#: written by the move-in wizard, which nobody has run.
NOTHING_HAS_BEEN_DONE_YET: dict[str, Any] = {
    "code": "move_in_approved_and_not_started",
    "br_ref": "BR-CUS-1077 · BR-CUS-1090",
    "detail": (
        "This move-in has been approved and nobody has run it yet, so nothing has been "
        "written: no account is open, no reading is taken and no money is held. Approving "
        "raises the job and opens nothing — the Approve dialog says so on every outcome."
    ),
}


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _fact(value: Any, absence: dict[str, Any] | None = None) -> dict[str, Any]:
    """One label→value row, or the reason there is no value.

    ⚠ **NEVER BOTH, AND NEVER NEITHER.** A cell carrying a value AND an absence
    lets a screen render whichever it reaches for first, which is how two
    surfaces come to disagree about one fact.
    """
    if value is not None and value != "":
        return {"value": value, "unavailable": None}
    return {"value": None, "unavailable": dict(absence) if absence else None}


def _money(value: Any) -> str | None:
    """CLAUDE.md rule 2 — money travels as a STRING at 4 decimals and the screen
    displays 2. Never a float, and never rounded here."""
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.0001")))


# ═══════════════════════════════════════════════════════════════════════════
# THE PARTS
# ═══════════════════════════════════════════════════════════════════════════
def _unit_label(unit_id: Any) -> str | None:
    """`1408 Elm Street · Unit A` — WALKED, never read off the account.

    Hard rule 8 / `BR-MET-1161`: the address lives on `premises` and a unit
    refines it by LABEL. So the street comes from the premises and the unit
    contributes its label, which is exactly what the blueprint's address line
    draws and why an envelope and this page cannot disagree.
    """
    from apps.customers import seams

    if unit_id is None:
        return None
    refs = seams.unit_refs([unit_id])
    ref = refs.get(str(unit_id)) or {}
    # `DEF-CUS-9763` — the unit NUMBER and the label together (`SCW-U-311 ·
    # Unit 4A`), as images 03–17 draw it and step 1's card shows it. This read
    # `unit_no or label`, and `unit_refs` served no `unit_no`, so every line
    # named the unit by its label alone.
    unit_label = " · ".join(
        part for part in ((ref.get("unit_no") or "").strip(), (ref.get("label") or "").strip()) if part
    )
    address = (ref.get("address_line") or ref.get("premise_address") or "").strip()
    if not address:
        premises_id = ref.get("premises_id")
        if premises_id:
            try:
                address = (seams.premises_ref(premises_id).get("address_line") or "").strip()
            except Exception:  # pragma: no cover - metering refuses unknown/foreign ids
                address = ""
    parts = [p for p in (address, unit_label) if p]
    return " · ".join(parts) or None


def _earliest_legal_start(account: Any) -> tuple[date | None, dict[str, Any] | None]:
    """BR-CUS-056 — the day after the previous occupant's last day.

    ⚠ **DERIVED, NOT STORED, AND THAT IS THE POINT.** `services
    ._refuse_if_start_lands_on_the_prior_move_day` computes exactly this figure
    to REFUSE a bad start date and then throws it away. The blueprint puts it on
    the record so a clerk can see the boundary the job respected — the same
    arithmetic, read rather than enforced.
    """
    from apps.customers import selectors

    if account is None or account.unit_id is None:
        return None, dict(NO_PRIOR_TENANCY_TO_MEASURE_FROM)
    prior = selectors.last_closed_account_for_unit(account.unit_id, exclude_id=account.pk)
    if prior is None or prior.closed_at is None:
        return None, dict(NO_PRIOR_TENANCY_TO_MEASURE_FROM)
    return prior.closed_at + timedelta(days=1), None


def _opening_reads(account: Any, *, effective_on: date | None, kind: str) -> dict[str, Any]:
    """The `Register · Reading · Read date · How` table.

    ⚠ **ON A MOVE-IN, A REGISTER'S OPENING READ IS ITS FIRST COMMITTED READ
    DATED ON OR AFTER THE MOVE-IN DATE — THE SAME TEST THE STATUS CHIP MAKES
    (`DEF-CUS-9726`, decision log 2026-10-05).** `move_in_list`'s *Waiting on a
    read* is `move_reads.unit_reads_cell`: a meter with no head on/after the
    date is due. This table used to read heads AS OF the date (`on=`), so the
    previous occupant's last read — dated before — showed as `Read`, the tile
    said *3 of 3* and *Still open* was empty under a chip saying *Waiting on a
    read* (lane DETAIL's MVI-26-0004). It now asks metering for each register's
    first head on/after the date (`since=`): a meter with none is
    `Not estimated` and lands on *Still open*, and a later cycle read never
    replaces the opening one. A read dated BEFORE the move-in is the unit's
    *Last read* (image 24's own column), not this tenancy's opening read.
    **A move-OUT keeps the as-of read** — its table is the final position on
    the day the tenancy ended, which is what `on=` answers.

    ⚠ **THE READINGS ARE METERING'S AND ARE REACHED THROUGH THE SEAM** (B1,
    BR-CUS-021). `reads_committed` on the record is a COUNT of what the job
    took, never a copy of the values, so the values are read back here from the
    register that owns them.

    ⚠ **`How` HAS EXACTLY TWO WORDS AND NEITHER IS INVENTED.** A register
    carrying a committed figure reads `Read`. A register with no figure reads
    `Not estimated`, which is the blueprint's own word and is a statement that
    nothing stood in for the missing reading — it is NOT a verdict that an
    estimate was refused.

    ⚠ **AND UNTIL 2026-09-20 IT TOOK THE WRONG FIGURE, SO A REGISTER A CLERK
    REALLY READ SAID `Not estimated` (`DEF-CUS-5910`).** The blueprint's table
    is `REGISTER · READING · READ DATE · HOW` and draws **`41,680`** — the
    METER INDEX. This read `consumption`, which is the DELTA between two reads,
    so an OPENING read — which has nothing before it to subtract from — carries
    `None` there **however carefully the dial was read**. Measured on the
    move-in scenario suite's `S5`: the read register held
    `current_value=41680.000000` with `consumption=None`, so it rendered as
    unread and **`unread_registers` counted TWO where one register was unread**.

    The seam now publishes both (`metering.selectors.reads_for_unit`), and they
    are independently null in BOTH directions: a first read has a reading and no
    usage, an ESTIMATE has a usage and no reading (`BR-MET-028` — nobody read
    the dial). So `How` asks whether EITHER figure arrived, and the `READING`
    column carries the index alone — `consumption` *"is the wrong number to put
    in a column headed previous reading"* (`DEF-MET-5862`, PO 2026-09-19).
    """
    from apps.customers import seams

    if account is None or account.unit_id is None:
        return {"rows": [], "unavailable": dict(NO_ACCOUNT_UNTIL_IT_COMPLETES)}
    from apps.customers import moves

    if kind == moves.KIND_MOVE_IN and effective_on is not None:
        answer = seams.reads_for_unit(account.unit_id, since=effective_on)
    else:
        answer = seams.reads_for_unit(account.unit_id, on=effective_on)
    if answer is None:
        return {"rows": [], "unavailable": dict(READS_NOT_READABLE_HERE)}
    meters = list(answer.get("meters") or ())
    if not meters:
        return {"rows": [], "unavailable": dict(UNIT_HAS_NO_METERS)}
    rows: list[dict[str, Any]] = []
    for meter in meters:
        asset_no = meter.get("asset_no") or ""
        registers = list(meter.get("registers") or ())
        if not registers:
            # A meter standing on the unit with no register read at all. The
            # blueprint's third row exactly: a figure was never taken and
            # nothing was estimated in its place.
            rows.append(
                {
                    "register": asset_no,
                    "reading": None,
                    "read_at": None,
                    "how": HOW_NOT_ESTIMATED,
                }
            )
            continue
        for register in registers:
            channel = register.get("channel") or ""
            # The blueprint's `READING` column is the meter INDEX, never the
            # usage — see the docstring and `DEF-CUS-5910`.
            reading = register.get("current_value")
            usage = register.get("consumption")
            rows.append(
                {
                    "register": " · ".join(p for p in (asset_no, channel) if p),
                    "reading": reading,
                    # Served beside it rather than folded into it: an estimate
                    # has one and not the other, and a screen must be able to
                    # draw either alone.
                    "consumption": usage,
                    "unit": register.get("unit"),
                    "read_at": register.get("read_at"),
                    # `estimated` True is still a READING — the amber chip in
                    # the head is what says an estimate was used. `Not
                    # estimated` is reserved for a register with NO FIGURE AT
                    # ALL, which is why this asks for EITHER.
                    "how": (
                        HOW_READ
                        if (reading is not None or usage is not None)
                        else HOW_NOT_ESTIMATED
                    ),
                    # `DEF-CUS-9765` — image 24's SOURCE: the event the reading
                    # was entered for (`move_in` …), None for an ordinary read.
                    "event": register.get("event_context"),
                }
            )
    return {"rows": rows, "unavailable": None}


def _money_taken(account: Any) -> dict[str, Any]:
    """The bordered `Money taken` box — `Required by the plan`, `Taken`,
    `Still to collect`.

    ⚠ **`Still to collect` IS ASSESSED MINUS TAKEN, AND IT READ THE WRONG PAIR
    UNTIL 2026-09-20 (`DEF-CUS-5909`).** It subtracted `deposit_on_file` from
    the PLAN STANDARD — and `BR-CUS-1050` is explicit that the standard is a
    reference figure *"reported beside what was typed"* and **never enforced**.
    **Worked:** a `$150.00` deposit with `$25.00` handed over, against a
    `$120.00` plan standard, read **`$95.00`** where blueprint **p075**'s
    review block computes **`$125.00`** from its own two drawn lines, `Amount`
    and `Amount taken`. Right arithmetic over the wrong pair, which is exactly
    why no test caught it: every one of them asserted the deposit REGISTER,
    correctly, and none asserted the difference.

    The assessed side now has a column of its own, `accounts.deposit_assessed`
    (`customers 0059`), so both ends are stored and the middle is derived.

    ⚠ **IT IS ONLY SERVED WHEN BOTH SIDES ARE KNOWN.** A NULL `deposit_assessed`
    means no deposit is owed on this account at all — `not_required`, or one a
    supervisor waived — and printing the taken figure's negative, or a `$0.00`,
    would be a number nobody computed. Where it is absent the third line is an
    absence rather than a total.

    ⚠ **`required` STILL SERVES THE PLAN STANDARD AND IS A DIFFERENT FACT.**
    p075 draws `Amount` (what the clerk assessed) and the step draws `Why this
    amount` beside the plan's own figure; keeping both means a clerk can see
    that they took `$150.00` where the plan says `$120.00`, which is the
    comparison `deposit_amount_differs_from_plan_standard` exists to report.
    """
    from apps.customers import deposit as deposit_module

    if account is None:
        return {
            "required": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "taken": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "awaiting_clearance": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "assessed": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "still_to_collect": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "tender": _fact(None, TENDER_NOT_READABLE_FROM_CUSTOMERS),
        }
    standard = deposit_module.plan_standard_for(account)
    # `OQ-RAT-12786` — a sized deposit this connection's size does not price
    # answers `amount: None` with a refusal; it reads as no standard here (the
    # Deposit step refuses it by name), never as `Decimal("None")`.
    required = (
        Decimal(str(standard["amount"]))
        if standard and standard.get("amount") is not None
        else None
    )
    held = account.deposit_on_file
    taken = Decimal(str(held)) if held is not None else None
    # p075's `Amount` — what the clerk ASSESSED, and the left side of the
    # subtraction. NULL where no deposit is owed (`DEF-CUS-5909`).
    assessed_raw = getattr(account, "deposit_assessed", None)
    assessed = Decimal(str(assessed_raw)) if assessed_raw is not None else None
    # ⚠ `DEF-CUS-9755` — A DEPOSIT IN THE DRAWER IS NOT STILL TO COLLECT.
    # `taken` is the CLEARED register and stays so — the PO's 2026-10-06
    # ruling (`DEF-BIL-9751` (a)) makes a processing deposit count as PAID for
    # the first bill's deposit line, which still-to-collect $0.00 below
    # already agrees with; it did not make uncleared money cleared. A check taken at the
    # counter has been collected; it has not cleared. So the recorded,
    # uncleared deposit money is served on its own line and is not counted as
    # still to collect. Worked (M1): assessed $150.00, cleared $0.00, check
    # 2041 for $150.00 processing → taken $0.00, not cleared $150.00, still
    # to collect $0.00 (was $150.00).
    from apps.customers import seams as customer_seams

    awaiting_raw = customer_seams.deposit_awaiting_clearance(account.pk)
    awaiting = Decimal(str(awaiting_raw)) if awaiting_raw is not None else None
    still: Decimal | None = None
    if assessed is not None and taken is not None:
        still = max(assessed - taken - (awaiting or Decimal("0")), Decimal("0"))
    return {
        "assessed": _fact(_money(assessed), NO_DEPOSIT_ASSESSED),
        "required": _fact(_money(required), NO_PLAN_DEPOSIT_STANDARD),
        "taken": _fact(_money(taken)),
        # None when nothing is waiting to clear (or payments could not be
        # asked) — a screen draws no line rather than a $0.00.
        "awaiting_clearance": _fact(
            _money(awaiting) if awaiting else None, NOTHING_AWAITING_CLEARANCE
        ),
        "taken_on": account.deposit_received_on.isoformat()
        if account.deposit_received_on
        else None,
        "still_to_collect": _fact(_money(still), NO_DEPOSIT_ASSESSED),
        # §3 — the amount is ours, the tender is payments'.
        "tender": _fact(None, TENDER_NOT_READABLE_FROM_CUSTOMERS),
        "currency": getattr(account, "currency", None),
    }


def _visit(kind: str | None, move_no: str | None) -> dict[str, Any]:
    """The field job this move raised — `raised · done · accepted` and the
    orders' numbers, read through `seams.flow_work_visits` by the move's NUMBER
    (`from_flows` stamps `source_ref = MVO-…/MVI-…`). `DEF-CUS-9628`."""
    from apps.customers import seams

    if not move_no or kind not in ("move_in", "move_out"):
        return _fact(None, NO_VISIT_RAISED)
    answer = seams.flow_work_visits(flow_kind=kind, source_ref=move_no)
    if answer is None:
        return _fact(None, VISIT_NOT_READABLE)
    if not answer.get("raised"):
        return _fact(None, NO_VISIT_RAISED)
    return _fact(answer)


def _still_owed(
    account: Any, reads: dict[str, Any], *, kind: str | None = None, move_no: str | None = None
) -> dict[str, Any]:
    """`What is still owed to this move` — three facts, NO buttons.

    ⚠ **THE BLUEPRINT IS EXPLICIT THAT THESE ARE NOT CONTROLS** (§1). Two of the
    three are absences in the drawing itself — *"Visit · not raised"* and
    *"Carry-forward · could not be checked"* — so this function states them
    rather than deriving a verdict it has no data for.
    """
    unread = [row for row in (reads.get("rows") or ()) if row.get("how") == HOW_NOT_ESTIMATED]
    if reads.get("unavailable"):
        demand = _fact(None, dict(reads["unavailable"]))
    elif unread:
        demand = _fact(
            # ≤ 6 words, B14 rule 33: this is a FACT, not a sentence.
            {"count": len(unread), "registers": [row["register"] for row in unread]}
        )
    else:
        demand = _fact({"count": 0, "registers": []})
    return {
        "demand_register": demand,
        "visit": _visit(kind, move_no),
        "carry_forward": _fact(None, CARRY_FORWARD_HAS_NO_MECHANISM),
    }


def _customer_door(account: Any) -> dict[str, Any]:
    """`Open the customer` — the second door, or the reason there is none.

    PO ruling 2026-09-19: *"Open the account, Open the customer - if requried
    otherwise we will ahev to link to exisitng one"*. Where a customer is
    linked this carries the id the route needs; where none is, it carries the
    absence and **no linking control**, because building that flow is its own
    piece of work with its own proof (see the module docstring).
    """
    from apps.customers import models as cmodels

    if account is None:
        return _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES)
    link = (
        cmodels.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id=account.pk
        )
        .order_by("created_at")
        .first()
    )
    if link is None:
        return _fact(None, NO_CUSTOMER_LINKED)
    customer = cmodels.Customer.objects.filter(
        tenant_id=_tenant_id(), pk=link.customer_id
    ).first()
    if customer is None:  # pragma: no cover - a link with no row is a broken FK
        return _fact(None, NO_CUSTOMER_LINKED)
    return _fact(
        {
            # The ID is carried for the ROUTE and is never the visible value —
            # B14 rule 31. The screen renders `name`.
            "customer_id": str(customer.pk),
            "name": customer.display_name or None,
        }
    )


def _account_label(account: Any) -> str | None:
    """`A-10432 · Okafor, D.` — the number, and who holds it.

    B14 rule 31: the NUMBER is the visible value. The uuid is carried separately
    for the route and never rendered.
    """
    if account is None:
        return None
    from apps.customers import models as cmodels

    link = (
        cmodels.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id=account.pk
        )
        .order_by("created_at")
        .first()
    )
    name = None
    if link is not None:
        customer = cmodels.Customer.objects.filter(
            tenant_id=_tenant_id(), pk=link.customer_id
        ).first()
        name = getattr(customer, "display_name", None)
    return " · ".join(p for p in (account.account_no, name) if p)


def _title_name(account: Any, park: Any) -> str | None:
    """The 32px page-head title is THE CUSTOMER'S NAME (B14 rule 40 · p074).

    Not the reference, which is the kicker above it, and not the account number,
    which is a fact in the body. Where nobody is named — an in-flight draft that
    has not reached step 2 — the screen falls back to the reference rather than
    rendering an empty heading.
    """
    from apps.customers import models as cmodels

    if account is not None:
        link = (
            cmodels.CustomerAccount.objects.filter(
                tenant_id=_tenant_id(), account_id=account.pk
            )
            .order_by("created_at")
            .first()
        )
        if link is not None:
            customer = cmodels.Customer.objects.filter(
                tenant_id=_tenant_id(), pk=link.customer_id
            ).first()
            if customer is not None and customer.display_name:
                return customer.display_name
        # ⚠ **THE CONTACT IS A REVERSE FK AND `account.contact` DOES NOT
        # EXIST.** A first draft read `getattr(account, "contact", None)`,
        # which returns None on every account without raising — so the 32px
        # title rendered EMPTY on a real move-in whose contact row said
        # `Kwan, Michael`, with no error anywhere. `Contact` carries
        # `account = ForeignKey(Account, db_column="account_id")`, so the
        # living primary contact is queried, and a deleted one is not a name.
        contact = (
            cmodels.Contact.objects.filter(
                tenant_id=_tenant_id(), account_id=account.pk, deleted_at__isnull=True
            )
            .order_by("-is_primary", "created_at")
            .first()
        )
        if contact is not None and (contact.full_name or "").strip():
            return contact.full_name.strip()
    if park is not None:
        # ⚠ **NOT `subject_label` — THAT IS THE ADDRESS, AND IT IS ALREADY THE
        # LINE UNDER THE TITLE.** A draft that has reached step 2 carries the
        # occupant's name in its typed values; one parked on step 1 carries
        # only the unit, so the heading falls back to the REFERENCE. A 32px
        # title repeating the address line verbatim reads as a rendering bug.
        values = park.values if isinstance(park.values, dict) else {}
        for key in ("customer_name", "full_name", "applicant_name", "occupant_name"):
            named = (values.get(key) or "").strip() if isinstance(values.get(key), str) else ""
            if named:
                return named
        return (park.reference or "").strip() or None
    return None


# ═══════════════════════════════════════════════════════════════════════════
# THE ONE PUBLIC READ
# ═══════════════════════════════════════════════════════════════════════════
def record_detail(ref: str) -> dict[str, Any]:
    """One move, as `/moves/{ref}` draws it. §2's two tables, in order.

    ⚠ **THE REFERENCE IS THE KEY, NEVER THE UUID** (B14 rule 31). The URL a
    clerk copies out of the list is `MVI-26-0114`, and it keeps working across
    the commit because the draft and the finished record carry the same string
    (§2). Matching is case-insensitive because the blueprint's own URL is
    lowercase — `/brazosbend/moves/mvi-26-0114` — while the number a clerk
    quotes is upper.
    """
    from apps.customers import models as cmodels, moves
    from apps.identity.models import User

    key = (ref or "").strip()
    if not key:
        raise errors.deny_as_not_found("BR-CUS-150")

    row = moves.MoveRecord.objects.filter(
        tenant_id=_tenant_id(), move_no__iexact=key
    ).first()
    if row is not None:
        return redesign(_completed(row, cmodels, User), record=row)

    # `CR-171-BRC10` P1.05 — an `SR-` reference opens the move-in view of its
    # REQUEST (images 03–08). BEFORE the park lookup on purpose: the request's
    # Edit draft carries the request's own `SR-` number as its reference
    # (§9.REQ), and a draft is never the row while the request is one.
    request_view = _move_in_request_by_reference(key)
    if request_view is not None:
        return request_view

    park = _park_by_reference(key)
    if park is not None:
        return redesign(_in_flight(park), park=park)

    # ⚠ **THE THIRD ARM — `BR-CUS-1090`, PO ruling 2026-09-22.** An approved
    # move-in nobody has started carries its own `MVI-` from the moment the
    # clerk pressed, and the Move-ins tab links that number here. Without this
    # branch the link would 404 on every approved job: a reference printed on a
    # live list, wrapped in a door that opens nothing — hard-won law 2's mirror,
    # which is the shape `DEF-CUS-5922` cost one flow over when a parked
    # move-out's NULL reference made its own page unreachable.
    #
    # ⚠ **LAST OF THE THREE, DELIBERATELY.** A job is `done` the moment its
    # record is written, and `pending_queryset` filters on that — but the record
    # is looked up FIRST regardless, so even a job left pending by a move-in
    # committed through another door (`PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE`)
    # resolves to the finished record rather than to the queue row.
    job = _pending_job_by_reference(key)
    if job is not None:
        return redesign(_approved(job), job=job)

    # A reference this tenant does not hold is a 404 and never a 403 (HR-1):
    # the boundary must not confirm that the row exists somewhere else.
    raise errors.deny_as_not_found("BR-CUS-150")


def _pending_job_by_reference(key: str) -> Any:
    """The approved-and-not-started half — `move_in_jobs` (`BR-CUS-1090`).

    `move_no__iexact` for the reason `record_detail` gives: the blueprint's own
    URL is lowercase (`/brazosbend/moves/mvi-26-0114`) and the number a clerk
    quotes is upper, and `uq_move_in_jobs_tenant_move_no_ci` is what makes that
    one row rather than a scan.

    Tenant-scoped on the queryset itself and not left to RLS alone — CLAUDE.md
    hard rule 1 is belt AND braces everywhere else in this module.
    """
    from apps.customers import move_in_jobs

    return (
        move_in_jobs.MoveInJob.objects.filter(tenant_id=_tenant_id(), move_no__iexact=key)
        .select_related("request")
        .order_by("-created_at")
        .first()
    )


def _park_by_reference(key: str) -> Any:
    """The in-flight half of §2 — the draft carrying the number it will be
    filed under (`CR-122-BRC06`)."""
    from apps.tenancy.wizard_parks import WizardPark

    return (
        WizardPark.objects.filter(tenant_id=_tenant_id(), reference__iexact=key)
        .order_by("-parked_at")
        .first()
    )


#: The day `customers/0058` added `accounts.close_reason`. A close dated on or
#: after it was made by a screen that ASKED; one dated before it was not.
#:
#: ⚠ **A DATE CONSTANT AND NOT A FEATURE FLAG, AND IT IS THE ONLY THING THAT
#: CAN TELL THE TWO ABSENCES APART.** Nothing on the row records whether the
#: question existed when it was written — that is exactly the fact a column
#: added after the data cannot carry. Reading `closed_at` against the day the
#: column shipped is an approximation and is stated as one: a close keyed with
#: a BACKDATED `moved_out_on` sits on the wrong side of it. The cost is one
#: sentence being slightly too generous on a handful of rows, against a screen
#: that would otherwise tell a clerk *"they did not say"* about a question the
#: product never put to anybody.
CLOSE_REASON_COLUMN_SHIPPED = date(2026, 9, 20)


def _close_reason_fact(account: Any) -> dict[str, Any]:
    """WHY THIS TENANCY ENDED — the code, or which KIND of silence it is.

    PO ruling 2026-09-20 item 3: the reason must be readable on the move record
    and not merely stored. It is read by walking to the account rather than
    copied onto `move_records`, because BR-CUS-150 makes the record a record of
    the JOB and nothing the close wrote is duplicated into it — the same
    reading that keeps `closed_at` and the status off it.
    """
    value = (getattr(account, "close_reason", None) or "").strip() or None
    if value:
        return _fact(value)
    closed_at = getattr(account, "closed_at", None)
    asked = closed_at is not None and closed_at >= CLOSE_REASON_COLUMN_SHIPPED
    return _fact(None, CLOSE_REASON_NOT_GIVEN if asked else CLOSE_REASON_NOT_ASKED)


def move_in_date_of(row: Any, account: Any) -> Any:
    """The date a committed move-in STARTS — the one every move-in surface shows.

    ⚠ **`accounts.opened_at`, NOT `move_records.effective_on` (`DEF-CUS-9790`).**
    *Change move-in date* (J7, `move_in_flow.change_move_in_date`) moves the
    account's `opened_at` and its agreements and, by `BR-CUS-152`, never
    updates the move record; CR-171 §9.FLOW already said a committed move-in's
    date is the account's. Until 2026-10-06 the details view and the Move-ins
    list read the record, so after 10/10/2026 → 10/15/2026 the account read
    10/15 and the move-in itself still read 10/10. A move-OUT is unchanged: its
    record's `effective_on` is its date. The opening-read window keeps the
    record's date on purpose — it is the day the readings were committed
    against, and moving it would hide a reading taken on the original day.
    """
    from apps.customers import moves

    if getattr(row, "kind", None) == moves.KIND_MOVE_IN:
        opened = getattr(account, "opened_at", None)
        if (
            opened is not None
            and not _reopened_since(row, account)
            and not _cancelled_reopen(row, account)
        ):
            return opened
    return getattr(row, "effective_on", None)


def _cancelled_reopen(row: Any, account: Any) -> bool:
    """`DEF-CUS-10126` — THIS move-in reopened the account and was cancelled,
    so the account got its EARLIER tenancy's dates back and its `opened_at` is
    that tenancy's start, not this move-in's: the record keeps its own date."""
    from apps.customers import move_in_cancel

    if account is None or getattr(account, "closed_at", None) is None:
        return False
    if move_in_cancel.is_cancelled(account):
        return False  # a NEW account's cancel: `opened_at` is still this move-in's
    return move_in_cancel.record_is_cancelled(row, account)


def _reopened_since(row: Any, account: Any) -> bool:
    """`CR-181-BRC10` — the account was REOPENED by a later move-in, so its
    `opened_at` is that tenancy's start and not this record's: this record
    keeps the date it was committed as."""
    from apps.customers.move_in_reopen_models import MoveInReopening

    if account is None or getattr(row, "pk", None) is None:
        return False
    return (
        MoveInReopening.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account.pk,
            move_record__created_at__gt=row.created_at,
        )
        .exclude(move_record_id=row.pk)
        .exists()
    )


def _reopened(record: Any) -> dict[str, Any] | None:
    if record is None:
        return None
    from apps.customers import move_in_reopen

    return move_in_reopen.for_move_records([record.pk]).get(str(record.pk))


def _completed(row: Any, cmodels: Any, User: Any) -> dict[str, Any]:
    """A move that HAS happened — every fact the blueprint draws."""
    account = cmodels.Account.objects.filter(
        tenant_id=_tenant_id(), pk=row.account_id
    ).first()
    from_account = (
        cmodels.Account.objects.filter(tenant_id=_tenant_id(), pk=row.from_account_id).first()
        if row.from_account_id
        else None
    )
    actor = (
        User.objects.filter(pk=row.performed_by_id).first() if row.performed_by_id else None
    )
    earliest, earliest_absence = _earliest_legal_start(account)
    reads = _opening_reads(account, effective_on=row.effective_on, kind=row.kind)
    unread = [r for r in (reads.get("rows") or ()) if r.get("how") == HOW_NOT_ESTIMATED]
    moved_on = move_in_date_of(row, account)  # `DEF-CUS-9790`
    return {
        "state": STATE_COMPLETED,
        "kind": row.kind,
        "move_no": row.move_no,
        "move_no_unavailable": (
            None if row.move_no else dict(moves_number_absence(row.kind))
        ),
        "title": _title_name(account, None),
        "address_line": _unit_label(getattr(account, "unit_id", None)),
        "effective_on": moved_on.isoformat() if moved_on else None,
        # ── the six facts of WHAT HAPPENED ──────────────────────────────────
        "what_happened": {
            "account_opened": _fact(
                getattr(account, "account_no", None), NO_ACCOUNT_UNTIL_IT_COMPLETES
            ),
            "from_account": _fact(_account_label(from_account), NOT_A_CHAINED_MOVE),
            "unit": _fact(_unit_label(getattr(account, "unit_id", None))),
            "moved_in_on": _fact(moved_on.isoformat() if moved_on else None),
            "earliest_legal_start": _fact(
                earliest.isoformat() if earliest else None, earliest_absence
            ),
            # **WHY THIS TENANCY ENDED** (PO ruling 2026-09-20 item 3). Served
            # on BOTH kinds so one payload shape reads either — a move-IN row
            # always carries the *not asked* absence, because a move-in ends no
            # tenancy and its account is still open. The SCREEN draws it on the
            # move-out only, exactly as it already does for `unit_now`.
            "close_reason": _close_reason_fact(account),
            "committed_by": _fact(
                {
                    "name": (getattr(actor, "full_name", "") or "").strip() or None,
                    "at": row.performed_at.isoformat() if row.performed_at else None,
                }
                if actor is not None or row.performed_at
                else None,
                NOT_COMMITTED_YET,
            ),
        },
        "opening_reads": reads,
        "money_taken": _money_taken(account),
        "still_owed": _still_owed(account, reads, kind=row.kind, move_no=row.move_no),
        # CR-185-BRC10 — the tie-back to the owner, if a clerk chose one:
        # pending until the final bill is sent, then posted (or nothing owed).
        # None on a move-in and on a move-out nobody tied back.
        "balance_to_owner": _balance_to_owner(account, kind=row.kind),
        # ── the TWO doors, and nothing else (§1) ────────────────────────────
        "doors": {
            "account": _fact(
                {"account_id": str(account.pk), "account_no": account.account_no}
                if account is not None
                else None,
                NO_ACCOUNT_UNTIL_IT_COMPLETES,
            ),
            "customer": _customer_door(account),
        },
        # The head's chips. `estimated_registers` counts registers that opened
        # with NO figure — the amber `1 register estimated` the blueprint draws
        # is this count, and it is 0 rather than absent when everything read.
        "chips": {
            "unread_registers": len(unread),
            "reads_committed": row.reads_committed,
        },
    }


def _balance_to_owner(account: Any, *, kind: str) -> dict[str, Any] | None:
    """`CR-185-BRC10` — the move-out's tie-back as the record shows it, or None."""
    if account is None or kind != "move_out":
        return None
    from apps.customers import move_out_settlement

    return move_out_settlement.balance_to_owner_for(account)


def moves_number_absence(kind: str) -> dict[str, Any]:
    from apps.customers import moves

    return moves.MOVE_NUMBER_UNAVAILABLE[kind]


def _approved(job: Any) -> dict[str, Any]:
    """An APPROVED move-in nobody has started — `BR-CUS-1090`, PO 2026-09-22.

    ⚠ **IT CARRIES EVERY KEY `_in_flight` CARRIES, PLUS THREE OF ITS OWN, AND
    THE SCREEN BRANCHES ON `state` — WHICH IS THE POSTURE THIS PAGE ALREADY
    HAD.** `_completed` and `_in_flight` were never key-for-key identical
    either (`step`, `park_id` and `is_draft` exist on one and not the other),
    so this follows the file rather than inventing a rule for it. What IS
    carried whole is the absence discipline: wherever an approved job genuinely
    cannot answer, a NAMED absence is served rather than nothing. A payload
    that simply omitted `money_taken` would render as an empty box, and an
    empty box and an absent fact are indistinguishable once drawn (`DEF-127`).
    The three extra keys are `request`, `services` and `documents_outstanding`
    — the walk back and the two details this state is the only one that can
    answer.

    ⚠ **THIS IS WHERE THE PO'S *"add all details from servcies request to it"*
    IS ANSWERED, AND EVERY ONE OF THEM IS READ THROUGH THE LINK.** The
    applicant, the address, the requested start and the services asked for all
    live on the request, which is NOT NULL and `PROTECT`ed, so they are walked
    to at the moment anybody asks rather than copied onto the job —
    `move_in_jobs` §2 and §4 carry the whole argument, and CLAUDE.md hard rule 8
    forbids the address half outright.

    ⛔ **NO STEP.** Nothing in this product writes one for a job, so
    `move_reads.STEP_HAS_NO_STORE` rides here exactly as it rides on the list
    row — B18 §5.5.2's footnote survives in that one half and this page does not
    move it.
    """
    request = job.request
    from apps.customers import move_in_jobs

    unit_line = _unit_label(request.resolved_unit_id) if request.resolved_unit_id else None
    return {
        "state": STATE_APPROVED,
        "kind": "move_in",
        "move_no": job.move_no or None,
        "move_no_unavailable": None if job.move_no else moves_number_absence("move_in"),
        # The applicant, from the application. ⛔ NOT a customer record — an
        # approval creates nobody, which is what `move_reads`'s own
        # `customer_source: "request_applicant"` says one file over.
        "title": (request.applicant_name or "").strip() or (job.move_no or None),
        # Hard rule 8 — WALKED to the premises through the unit, never stored.
        "address_line": unit_line,
        # What the applicant ASKED FOR. It is not a date anybody has agreed:
        # the wizard's third step settles that, and it is what the account is
        # opened with.
        "effective_on": (
            request.requested_start.isoformat() if request.requested_start else None
        ),
        "step": None,
        # ⛔ NO RESUME HANDLE. `park_id` is what `_in_flight` hands the wizard,
        # and there is no draft here to resume — the door an approved job needs
        # is *the wizard opened FROM the job, carrying the request*, which
        # `move_in_jobs` §3 files rather than fakes. Served as `None` rather
        # than omitted so one screen reads all three states.
        "park_id": None,
        "is_draft": False,
        "waiting_on": (request.waiting_on or None),
        "park_note": (request.park_note or None),
        "remind_on": None,
        # ── THE WALK BACK TO THE APPLICATION ────────────────────────────────
        # ⚠ **THE CONNECTION IS KEPT AND ONLY ITS PLACE MOVES** (`CR-133-BRC07`
        # §3). Until this ruling the Move-ins tab quoted `SR-26-0011` IN the
        # column headed `Reference` and linked back to the request, so the
        # application's number was the job's identity. The identity is the
        # `MVI-` now and the link lives here, where a door belongs.
        # B14 rule 31 — the id rides in an href, the NUMBER is what is read.
        "request": {
            "id": str(request.id),
            "request_no": request.request_no,
            "state": request.state,
        },
        # The services the application asked for — the one detail the PO named
        # that no surface was showing. `[]` is a real answer.
        "services": move_in_jobs.services_asked_for(request),
        # What the clerk still owes this job, read back LIVE through the link
        # (PO 2026-09-16, *"lets not make it mandetory"*): a document that
        # arrives tomorrow makes this `None` tomorrow, with nothing to keep in
        # step.
        "documents_outstanding": move_in_jobs.outstanding_documents(request),
        "what_happened": {
            "account_opened": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
            "from_account": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
            "unit": _fact(unit_line),
            "moved_in_on": _fact(
                request.requested_start.isoformat() if request.requested_start else None,
                NOT_CHOSEN_YET,
            ),
            "earliest_legal_start": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
            "close_reason": _fact(None, NOT_COMMITTED_YET),
            "committed_by": _fact(None, NOT_COMMITTED_YET),
        },
        "opening_reads": {"rows": [], "unavailable": dict(NOTHING_HAS_BEEN_DONE_YET)},
        "money_taken": _money_taken(None),
        "still_owed": {
            "demand_register": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
            "visit": _fact(None, NO_VISIT_RAISED),
            "carry_forward": _fact(None, CARRY_FORWARD_HAS_NO_MECHANISM),
        },
        "doors": {
            "account": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
            "customer": _fact(None, NOTHING_HAS_BEEN_DONE_YET),
        },
        "chips": {"unread_registers": 0, "reads_committed": 0},
    }


def _in_flight(park: Any) -> dict[str, Any]:
    """A move STILL IN FLIGHT — the head, and a stated absence for everything
    the commit has not produced (§2).

    ⚠ **EVERY ONE OF THESE IS A LIFECYCLE ABSENCE AND SAYS SO.** None of them is
    a missing column, a broken seam or a job somebody failed to do, and a screen
    that rendered a dash for them would be telling a clerk the opposite.
    """
    values = park.values if isinstance(park.values, dict) else {}
    return {
        "state": STATE_IN_FLIGHT,
        "kind": "move_in" if park.flow == "move_in" else park.flow,
        "move_no": park.reference or None,
        "move_no_unavailable": None,
        "title": _title_name(None, park),
        "address_line": (park.subject_label or "").strip() or None,
        # ⚠ **`moved_out_on` JOINED THIS CHAIN ON 2026-09-20 AND ITS ABSENCE WAS
        # HALF OF `DEF-CUS-5922`.** Each wizard stores the date under the name
        # its OWN screen uses — `MoveInWizard` writes `moved_in_on`,
        # `MoveOutWizard` writes `moved_out_on` — and this read knew only the
        # first two spellings. So the day a parked move-out became openable at
        # all, it would have opened showing no date, and the clerk would have
        # been told *"not chosen yet"* about a date they had typed themselves.
        # A flow-agnostic read of three keys is deliberate: the draft store is
        # schemaless by design (BR-SHL-048 (a) — *"copies ids and joins to
        # nothing"*), so the alternative is a branch per flow that has to be
        # extended every time a wizard is added, and forgetting to extend it
        # fails exactly this silently.
        "effective_on": (
            values.get("moved_in_on")
            or values.get("moved_out_on")
            or values.get("effective_on")
            or None
        ),
        "step": park.step,
        # ── THE RESUME HANDLE, AND IT IS THE ONLY THING THE DOOR NEEDED ──────
        #
        # ⚠ **THIS RECORD IS ADDRESSED BY REFERENCE AND THE WIZARD IS RESUMED
        # BY ID, SO WITHOUT THIS FIELD THE TWO CANNOT BE JOINED AT ALL** (PO
        # ruling 2026-09-19, *"We will need this action on details page - 4 ·
        # Close or complete it"*). `/moves/{ref}` is keyed on `MVI-26-0114`
        # because that is the number a clerk quotes (B14 rule 31), while
        # `resumePath()` builds `/move-ins/new?parked=<id>` and the wizard reads
        # that id back through `port.read()`. The record page had the reference
        # and nothing else, so it could name the draft and could not open it.
        #
        # ⚠ **IT IS A PROJECTION OF THE ROW IN HAND, NEVER A LOOKUP.** `_in_flight`
        # is handed the `WizardPark` that `_park_by_reference` already resolved,
        # so this costs no query and introduces no join. Matching a draft to a
        # record by address and date — the shape a join would have taken — would
        # pick the wrong draft the first time one unit has two.
        #
        # ⚠ **`str(park.id)` IS THE SAME EXPRESSION `wizard_parks.row_dict` USES**
        # for the same field, deliberately: the parked-drafts panel and this page
        # must hand the wizard a byte-identical handle or they are two doors onto
        # one act that can disagree. This is the ONE id this payload carries and
        # it rides in an href, never as a field's visible value (rule 31).
        "park_id": str(park.id),
        "is_draft": park.waiting_on == "",
        "waiting_on": park.waiting_on or None,
        "park_note": park.park_note or None,
        "remind_on": park.remind_on.isoformat() if park.remind_on else None,
        "what_happened": {
            "account_opened": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "from_account": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "unit": _fact((park.subject_label or "").strip() or None),
            "moved_in_on": _fact(
                values.get("moved_in_on") or values.get("effective_on") or None,
                NOT_CHOSEN_YET,
            ),
            "earliest_legal_start": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            # **WHY THIS TENANCY ENDED** — not yet, and for the plainest of
            # reasons: the reason is written by the COMMIT, in the same
            # transaction as the close (PO ruling 2026-09-20 item 3). A draft
            # holds what was typed and touches no records (BR-SHL-048), so the
            # clerk may well have picked one and it is not a fact about the
            # account until they finish. `NOT_COMMITTED_YET` is the same
            # absence `committed_by` beside it carries, for the same reason.
            "close_reason": _fact(None, NOT_COMMITTED_YET),
            "committed_by": _fact(None, NOT_COMMITTED_YET),
        },
        "opening_reads": {"rows": [], "unavailable": dict(NO_ACCOUNT_UNTIL_IT_COMPLETES)},
        "money_taken": _money_taken(None),
        "still_owed": {
            "demand_register": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "visit": _fact(None, NO_VISIT_RAISED),
            "carry_forward": _fact(None, CARRY_FORWARD_HAS_NO_MECHANISM),
        },
        "doors": {
            "account": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
            "customer": _fact(None, NO_ACCOUNT_UNTIL_IT_COMPLETES),
        },
        "chips": {"unread_registers": 0, "reads_committed": 0},
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-171-BRC10 P1.05 — the redesigned details view (images 03–17)
# ═══════════════════════════════════════════════════════════════════════════
#: Every key this section adds, on every state, so a screen can branch on
#: `status` and read one shape: `status` (the list's ONE function,
#: `move_in_list`), `reference`, `actions` (a request's buttons — REQ's
#: `request_actions`; a move's buttons are drawn by `moveRecordActions.ts` from
#: `status`), `step` (the four-step cell), `tiles`, `facts`, `tab_counts`,
#: `still_open`. The keys the page already read are untouched.
#:
#: ⛔ Why a figure is not served — each is a LIFECYCLE or an OWNERSHIP absence,
#: named so a tile renders a reason and never a zero.
MESSAGES_HAVE_NO_MOVE_READ: dict[str, Any] = {
    "code": "move_messages_have_no_read_yet",
    "br_ref": "CR-171 P1.25",
    "detail": "The move-in's own Messages tab is built with P1.25.",
}
PAYMENT_AT_COMPLETE_NOT_READ_YET: dict[str, Any] = {
    "code": "move_in_payment_is_not_read_here_yet",
    "br_ref": "CR-171 P1.13",
    "detail": "What was paid at Complete is written and read by P1.13.",
}
NOTHING_TAKEN_BEFORE_COMPLETE: dict[str, Any] = {
    "code": "nothing_is_taken_before_complete",
    "br_ref": "CR-171 §6.1",
    "detail": "Reads, fees and payments are written when the move-in is completed.",
}


def _move_in_request_by_reference(key: str) -> dict[str, Any] | None:
    """An `SR-` reference → the move-in view, or None when it is not one.

    A request that is still a Move-ins REQUEST ROW (`move_in_list`'s window:
    to approve, waiting on the customer, declined) answers the request view.
    One that has gone on to be a job or a committed move-in answers THAT view,
    because the list shows it under its `MVI-` from then on and a clerk who
    quotes the old `SR-` number must still land on the move-in. Anything else
    — a new connection, a move-out — is not this page's and is a 404.
    """
    from apps.customers import models as cmodels
    from apps.customers import move_in_jobs, move_in_list, moves
    from apps.identity.models import User

    request = (
        cmodels.ServiceRequest.objects.filter(tenant_id=_tenant_id(), request_no__iexact=key)
        .order_by("-created_at")
        .first()
    )
    if request is None:
        return None
    if move_in_list._requests_base().filter(pk=request.pk).exists():
        return _request_view(request)
    record = (
        moves.MoveRecord.objects.filter(
            tenant_id=_tenant_id(), kind=moves.KIND_MOVE_IN, request_id=request.pk
        )
        .order_by("-created_at")
        .first()
    )
    if record is not None:
        return redesign(_completed(record, cmodels, User), record=record)
    job = (
        move_in_jobs.MoveInJob.objects.filter(tenant_id=_tenant_id(), request_id=request.pk)
        .select_related("request")
        .first()
    )
    if job is not None:
        return redesign(_approved(job), job=job)
    return None


def _unit_facts(unit_id: Any) -> dict[str, Any]:
    """Unit and building, walked (hard rule 8) — ids for links, numbers to show."""
    from apps.customers import seams, selectors

    if not unit_id:
        return {"unit": None, "building": None, "vacant": None, "plan": None}
    ref = seams.unit_refs([str(unit_id)]).get(str(unit_id)) or {}
    occupant = selectors.active_account_for_unit(unit_id)
    return {
        "unit": {
            "id": str(unit_id),
            "label": ref.get("label"),
            # `DEF-CUS-9763` — drawn before the label (`SCW-U-311 · Unit 4A`).
            "unit_no": ref.get("unit_no"),
            "line": _unit_label(unit_id),
        },
        "building": (
            {
                "id": ref.get("premises_id"),
                "premise_no": ref.get("premise_no"),
                "address": ref.get("premise_address"),
            }
            if ref
            else None
        ),
        "vacant": occupant is None,
        "plan": seams.unit_plan_in_force(unit_id),
    }


def _request_view(request: Any) -> dict[str, Any]:
    """Images 03–08: a REQUEST on the move-in details view."""
    from apps.customers import models as cmodels
    from apps.customers import move_in_jobs, move_in_list, move_in_request, notifications_seam
    from apps.customers import service_request_reads as sr_reads

    status = move_in_list.status_of_request(request)
    services = move_in_jobs.services_asked_for(request)
    unit = _unit_facts(request.resolved_unit_id)
    documents = cmodels.ServiceRequestDocument.objects.filter(
        tenant_id=_tenant_id(), request_id=request.pk
    ).count()
    found = notifications_seam.request_messages(sr_reads.message_source_ids(request))
    messages = found[0].count() if found is not None else None
    matched = None
    if request.matched_customer_id:
        customer = cmodels.Customer.objects.filter(
            tenant_id=_tenant_id(), pk=request.matched_customer_id
        ).first()
        if customer is not None:
            matched = {
                "id": str(customer.pk),
                "customer_no": customer.customer_no,
                "name": customer.display_name,
            }
    requested = request.requested_start.isoformat() if request.requested_start else None
    submitted = request.submitted_at.date().isoformat() if request.submitted_at else None
    return {
        "state": "request",
        "kind": "move_in",
        "status": status,
        "reference": request.request_no,
        "move_no": None,
        "title": (request.applicant_name or "").strip() or request.request_no,
        "address_line": unit["unit"]["line"] if unit["unit"] else None,
        "effective_on": requested,
        "request": {"id": str(request.pk), "request_no": request.request_no, "state": request.state},
        "actions": list(move_in_request.request_actions(request.state)),
        "step": None,
        "chips": {"requested_on": submitted, "moves_in_on": requested},
        "tiles": {
            "move_in_date": {"value": requested, "basis": "requested"},
            "services": {"count": len(services), "codes": [s.get("code") for s in services]},
            "documents": {
                "attached": documents,
                "outstanding": move_in_jobs.outstanding_documents(request),
            },
            "unit": {
                "vacant": unit["vacant"],
                "unit_label": unit["unit"]["label"] if unit["unit"] else None,
                # `DEF-CUS-9763` — image 03's tile caption is the NUMBER.
                "unit_no": unit["unit"]["unit_no"] if unit["unit"] else None,
            },
        },
        "facts": {
            "request": {
                "request_no": request.request_no,
                "channel": request.channel,
                "submitted_on": submitted,
                "move_in_date": requested,
                "unit": unit["unit"],
                "building": unit["building"],
                "unit_is_vacant": unit["vacant"],
                "services": services,
                "plan": unit["plan"],
                "customer_type": {
                    "account_type": getattr(request.account_type, "code", None),
                    "account_type_name": getattr(request.account_type, "name", None),
                    "account_subtype": getattr(request.account_subtype, "name", None),
                },
            },
            "who": {
                "kind": "company" if request.applicant_kind == "business" else "person",
                "name": request.applicant_name,
                "matched": matched,
                "matched_absence": (
                    None
                    if matched
                    else {"code": "no_existing_customer" if request.match_confirmed_at else "not_searched"}
                ),
                "email": request.applicant_email,
                "phone": request.applicant_phone,
                "mailing_same": bool(request.billing_address_same),
                "mailing": (
                    None
                    if request.billing_address_same
                    else {
                        "line1": request.billing_address_as_given,
                        "city": request.billing_city_as_given,
                        "state": request.billing_state_as_given,
                        "postal_code": request.billing_postal_code_as_given,
                    }
                ),
            },
        },
        "tab_counts": {
            "documents": documents,
            "messages": messages,
            "audit": sr_reads.timeline_queryset(request, kind="all").count(),
        },
        "still_open": [],
    }


def _reads_tile(reads: dict[str, Any] | None, effective_on: Any) -> dict[str, Any]:
    if reads is None:
        return {"taken": None, "of": None, "recorded_on": None,
                "unavailable": dict(NOTHING_TAKEN_BEFORE_COMPLETE)}
    rows = list(reads.get("rows") or ())
    if reads.get("unavailable"):
        return {"taken": None, "of": None, "recorded_on": None,
                "unavailable": dict(reads["unavailable"])}
    taken = [row for row in rows if row.get("how") == HOW_READ]
    return {
        "taken": len(taken),
        "of": len(rows),
        "recorded_on": max((row["read_at"] for row in taken if row.get("read_at")), default=None),
        "unavailable": None,
    }


def _fees_tile(record: Any) -> dict[str, Any]:
    from apps.customers.move_in_extras import MoveFeeLine

    if record is None:
        return {"total": None, "currency": None, "lines": 0,
                "paid": None, "unavailable": dict(NOTHING_TAKEN_BEFORE_COMPLETE)}
    lines = list(
        MoveFeeLine.objects.filter(tenant_id=_tenant_id(), move_record_id=record.pk).values_list(
            "amount", "currency"
        )
    )
    total = sum((Decimal(str(amount)) for amount, _c in lines), Decimal("0"))
    return {
        "total": _money(total) if lines else None,
        "currency": lines[0][1] if lines else None,
        "lines": len(lines),
        "paid": None,
        "paid_unavailable": dict(PAYMENT_AT_COMPLETE_NOT_READ_YET),
        "unavailable": None,
    }


def _work_tile(move_no: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from apps.customers import seams

    if not move_no:
        return {"raised": 0, "open": 0, "unavailable": dict(NO_VISIT_RAISED)}, []
    answer = seams.flow_work_visits(flow_kind="move_in", source_ref=move_no)
    if answer is None:
        return {"raised": None, "open": None, "unavailable": dict(VISIT_NOT_READABLE)}, []
    orders = list(answer.get("orders") or ())
    still = [order for order in orders if not order.get("done")]
    return {"raised": len(orders), "open": len(still), "unavailable": None}, still


def _fee_lines(record: Any) -> list[dict[str, Any]]:
    """The fee lines a committed move recorded (image 26's *Fees* table).

    CR-171 P2.11 (lane MVI-DETAIL): the Billing tab draws each line, and the
    tile above served only their total and count. Read-only, the rows MONEY's
    `move_fees` wrote at Complete, in their own order; money as a 4-place
    string (hard rule 2 — the screen displays 2).
    """
    from apps.customers.move_in_extras import MoveFeeLine

    if record is None:
        return []
    return [
        {
            "seq": row.seq,
            "kind": row.kind,
            "source": row.source,
            "code": row.code,
            "description": row.description,
            "amount": _money(row.amount),
            "currency": row.currency,
        }
        for row in MoveFeeLine.objects.filter(
            tenant_id=_tenant_id(), move_record_id=record.pk
        ).order_by("seq")
    ]


def _co_owners(account: Any) -> list[dict[str, Any]]:
    """Co-owners / owners and officers on the account (image 25's table).

    CR-171 P2.10 (lane MVI-DETAIL). Written by IDN's `move_in_people` at
    Complete; read here so the Account tab can draw them. **Never an
    identifier** — no SSN, no licence, not even their last four (BR-CUS-092
    keeps those off a list); `photo_id` is whether a file is on record.
    """
    from apps.customers.co_owner_models import AccountCoOwner

    if account is None:
        return []
    return [
        {
            # CR-171 P2.24 (lane MVI-WIZ-CUST) — the handle the Account tab's
            # *Photo ID* upload addresses; never shown (B14 rule 31).
            "id": str(row.pk),
            "kind": row.kind,
            "full_name": row.full_name,
            "relationship": row.relationship,
            "title": row.title,
            "phone": row.phone,
            "email": row.email,
            "contact_by": row.contact_by,
            "responsible_for_bills": bool(row.responsible_for_bills),
            "photo_id": row.photo_id_document_id is not None,
        }
        for row in AccountCoOwner.objects.filter(
            tenant_id=_tenant_id(), account_id=account.pk
        ).order_by("created_at")
    ]


def redesign(payload: dict[str, Any], *, record: Any = None, park: Any = None,
             job: Any = None) -> dict[str, Any]:
    """Add the redesign's keys to a move's existing payload (see the head)."""
    from apps.customers import models as cmodels
    from apps.customers import move_in_jobs, move_in_list, move_reads

    if payload.get("kind") != "move_in":
        return payload
    account = None
    request = None
    if record is not None:
        account = cmodels.Account.objects.filter(tenant_id=_tenant_id(), pk=record.account_id).first()
        status = move_in_list.status_of_record(record, account)
        reference = record.move_no
        if record.request_id:
            request = cmodels.ServiceRequest.objects.filter(
                tenant_id=_tenant_id(), pk=record.request_id
            ).first()
        step = None
    elif job is not None:
        status = move_in_list.status_of_job(job)
        reference = job.move_no or None
        request = job.request
        step = None
    else:
        status = move_in_list.STATUS_DRAFT
        reference = (park.reference or "").strip() or None
        step = move_reads.move_in_step_cell(move_reads.move_in_park_step(park))
    unit_id = (
        getattr(account, "unit_id", None)
        or getattr(request, "resolved_unit_id", None)
        or ((park.subject_ref or {}).get("unit_id") if park is not None and isinstance(park.subject_ref, dict) else None)
    )
    unit = _unit_facts(unit_id)
    reads = payload.get("opening_reads") if record is not None else None
    work, still_orders = _work_tile(reference if record is not None or job is not None else None)
    from_account = (payload.get("what_happened") or {}).get("from_account")
    services = (
        move_in_jobs.services_asked_for(request) if request is not None and record is None else None
    )
    if record is not None and account is not None:
        from apps.customers import selectors

        services = [
            {"code": code} for code in selectors.service_codes_for_accounts([account]).get(str(account.pk), [])
        ]
    customer = None
    if account is not None:
        names = move_reads._customer_names([account.pk]).get(str(account.pk)) or {}
        customer = {
            "id": names.get("customer_id"),
            "customer_no": names.get("customer_no"),
            "name": names.get("customer"),
        }
    still_open: list[dict[str, Any]] = [
        {"kind": "work_order", "order": order} for order in still_orders
    ]
    for row in (reads or {}).get("rows") or ():
        if row.get("how") == HOW_NOT_ESTIMATED:
            still_open.append({"kind": "opening_read", "register": row.get("register")})
    payload.update(
        {
            "status": status,
            "reference": reference,
            "actions": [],
            "step": step if step is not None else payload.get("step"),
            "tiles": {
                "opening_reads": _reads_tile(reads, getattr(record, "effective_on", None)),
                "fees": _fees_tile(record),
                "work_orders": work,
                "messages": {"count": None, "unavailable": dict(MESSAGES_HAVE_NO_MOVE_READ)},
            },
            "facts": {
                "details": {
                    "move_no": reference,
                    "from_request": (
                        {"id": str(request.pk), "request_no": request.request_no}
                        if request is not None
                        else None
                    ),
                    "moved_in_on": payload.get("effective_on"),
                    "customer": customer,
                    "account": (
                        {"id": str(account.pk), "account_no": account.account_no}
                        if account is not None
                        else None
                    ),
                    "plan": unit["plan"],
                    "unit": unit["unit"],
                    "building": unit["building"],
                    "services": services,
                    "from_account": from_account,
                    "earliest_legal_start": (payload.get("what_happened") or {}).get(
                        "earliest_legal_start"
                    ),
                    "committed_by": (payload.get("what_happened") or {}).get("committed_by"),
                },
            },
            "tab_counts": {
                "work": work.get("raised"),
                "messages": None,
            },
            "still_open": still_open,
            "fee_lines": _fee_lines(record),
            "co_owners": _co_owners(account),
            # CR-181-BRC10 F3 — the account this move-in REOPENED and the
            # clerk's balance choice; None for a move-in that opened a new one.
            "reopened": _reopened(record),
        }
    )
    if job is not None and status == move_in_list.STATUS_DRAFT:
        park_id = move_in_list._linked_request_ids().get(str(job.request_id))
        payload["park_id"] = park_id
        drafted = move_in_list._parks().filter(id=park_id).first() if park_id else None
        if drafted is not None:
            payload["step"] = move_reads.move_in_step_cell(move_reads.move_in_park_step(drafted))
    return payload


# ── Lifecycle ─────────────────────────────────────────────
# packet: the MOVE RECORD, blueprint p074 + the PO's approval of 2026-09-19 +
#         the conformance file's "The Move-ins LIST and the MOVE RECORD —
#         blueprint pages 073–074" + the PO's action-bar ruling of the same day
#         (two doors; `Raise a visit` and `Record the reading` refused by name)
# generated: 2026-09-19, the move-record lane
# exceptions: E1 the deposit TENDER is stated rather than served — payments
#             publishes no read for it and B1 forbids the join (§3) · E2 `Visit`
#             is stated — work publishes no reciprocal read · E3 ⚠ **AMENDED
#             2026-09-19, the day it was written: no action is offered ON A
#             COMPLETED RECORD, which is the blueprint's own ruling (§1). An
#             IN-FLIGHT record now carries one — the PO's *"We will need this
#             action on details page - 4 · Close or complete it"* — and
#             `park_id` above is the only field this read adds to serve it.**
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
