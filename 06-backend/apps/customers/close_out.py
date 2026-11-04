# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (the only story that owns any part of an account's
#           terminal path today — it owns the MOVE-OUT wizard, S20).
#           Screens: S21/S22 (the account, where the act is offered) · S90 (the
#           disconnects worklist, where a cut account is worked).
#           ⚠ **NO STORY OWNS THE CLOSE-OUT.** The PO ruled the ACT on
#           2026-08-27 and `04-docs/05-modules/03-customers/06-epics/` carries
#           no epic for it — hard-won law 8, the same finding `disconnects.py`
#           filed for S90 and `move_reads.py` for the two move tabs. A story is
#           OWED and is REPORTED here rather than invented.
# Change:   DEF-724 — *"A disconnected customer can never be closed - Add a
#           separate close-out act — Cleaner in the record"* (PO 2026-08-27).
# Rules:    **BR-CUS-430** (the act is SEPARATE from a move-out, and the two
#           doors are disjoint in both directions — PO 2026-08-27) ·
#           **BR-CUS-431** (what it writes: `accounts.closed_at` takes the CUT
#           date, not the day the clerk performed it — the BUILD's derivation,
#           not the PO's) · BR-CUS-110 (a cut ENDS OCCUPANCY and the debt
#           follows the person — PO 2026-08-26, which is what made move-out a
#           dead end) · BR-CUS-030 (move-out: `closed_at`, terminal status,
#           `service_agreements.ended_on`) · BR-CUS-056 (the boundary day — the
#           outgoing account pays the move day; the incoming starts the next) ·
#           BR-CUS-103 (base charges STOP at the cut) · BR-CUS-082 (a debt
#           surviving closure is STILL CHASED and the ladder RESTARTS AT TIER 1
#           as a COLLECTIONS sequence, never a service one) · BR-CUS-097 as
#           qualified 2026-08-27 (the residue transfer is CLERK-INITIATED, in
#           the S20 wizard — this act does not collect that consent) ·
#           BR-CUS-055 (billing and occupancy key off the behaviour CLASS,
#           never the tenant's label) · BR-CUS-107 (the `Disconnected` status,
#           seeded and ASSIGNED AT THE CUT since 2026-08-30 — see
#           `DISCONNECTED_IS_NOT_CLOSED`)
#           · BR-CUS-017 (one occupying account per unit) · BR-MET-036
#           (occupancy is DERIVED from the class) · BR-TEN-043 (the event date
#           is an argument, never a wall clock) · BR-SHL-025 (who may do it) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (corrections are new
#           rows) · rule 7 (audit)
# Tests:    06-backend/tests/test_def724_close_out.py
# Impacts:  apps/customers/disconnects.py (`STATE_CLOSED_OUT`,
#           `CLOSED_CASE_STATES`, the three close-out columns, and
#           `restart_after_closure`, which this module CONSUMES rather than
#           restates) · apps/customers/services.py (`_end_service_agreements`,
#           `is_occupying`, `CLASS_TERMINAL` — all resolved BY NAME) ·
#           apps/customers/migrations/0032_def724_close_out.py ·
#           apps/customers/api.py (the two routes) ·
#           07-frontend/src/features/customers/CloseOutPage.tsx
# ───────────────────────────────────────────────────────
"""THE CLOSE-OUT — how an account whose service was cut reaches a terminal state.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-27 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). A row in
`12-governance/09-human-review-ledger.md` is OWED; this lane does not own that
file and REPORTS the row rather than writing it. Not RATIFIED without a recorded
human sign-off.

════════════════════════════════════════════════════════════════════════════
1 · WHY THIS IS A SECOND DOOR AND NOT A RELAXED `move_out`
════════════════════════════════════════════════════════════════════════════
PO ruling 2026-08-27, verbatim and in full: *"A disconnected customer can never
be closed - Add a separate close-out act — Cleaner in the record"*.

The reasoning is PART OF THE RULING and an implementation may not drop it: a
close-out writes a date **nobody can un-write**. Once an account is closed,
correcting it means new rows and never an edit (CLAUDE.md hard rule 4).
Relaxing `services.move_out`'s occupancy check to admit a cut customer would
file **a disconnection as a move-out** in the permanent record, and to a
regulator those are not the same event.

⚠ **SO THE TWO DOORS ARE DISJOINT IN BOTH DIRECTIONS, AND THE SECOND HALF IS
THE ONE A LATER LANE WILL BE TEMPTED TO DELETE.** `move_out` keeps refusing a
non-occupant (`customers.account.not_an_occupant`) — untouched by this module.
`close_out` refuses an OCCUPANT (`customers.account.close_out_still_occupying`).
An occupant leaving IS a move-out, and letting them through here would file a
departure as a disconnection, which is the same falsification pointing the
other way. A door that accepts everybody is not a separate act; it is `move_out`
with a longer name.

════════════════════════════════════════════════════════════════════════════
2 · WHAT IT WRITES, AND THE ONE FIGURE THAT DECIDED THE DATE
════════════════════════════════════════════════════════════════════════════
    accounts.closed_at            ← the CUT date   (BR-CUS-431)
    accounts.status               ← a TERMINAL status (default the seeded `closed`)
    service_agreements.ended_on   ← the CUT date, on every open agreement
    disconnect_cases.state        ← `closed_out`
    disconnect_cases.closed_out_on / _by / close_out_reason  ← the ACT
    audit_log                     ← `account.closed_out`, never `account.closed`

**`closed_at` IS THE CUT DATE AND NOT THE DAY THE CLERK CLICKED.** This is the
one thing `DEF-724`'s triage said could not be got wrong — *"the wrong choice
writes a `closed_at` for a tenancy that actually ended at the cut, which is a
date on a customer's record that no correction row can un-say"* — and it is
DERIVED rather than preferred:

`accounts.closed_at` is the ONLY thing `BR-CUS-056` measures the next occupant's
start day against. `selectors.last_closed_account_for_unit` takes the greatest
`closed_at` among terminal accounts on the unit, and
`services._refuse_if_start_lands_on_the_prior_move_day` refuses any incoming
start on or before it. `BR-CUS-110` releases the unit **at the cut**.

  Worked, on the account both rules were put with: `A-11488` is cut
  **2026-08-18** and closed out **2026-09-30**.
    · writing `2026-09-30` → the next occupant's `earliest_start` is
      **2026-10-01**, so a lawful start on any of the **43 days** from
      2026-08-19 to 2026-09-30 is REFUSED for a unit the utility was entitled
      to re-let the whole time;
    · writing `2026-08-18` → `earliest_start` is **2026-08-19**, which is
      exactly what `BR-CUS-110` grants.

`BR-CUS-103` agrees from the money side: base charges stop at the cut, so the
cut day IS the last day the outgoing account is charged for — which is precisely
`BR-CUS-056`'s *"the outgoing account pays the move day"*.

**THE ACT'S OWN DATE IS NOT LOST.** It goes to `disconnect_cases.closed_out_on`
with `closed_out_by` beside it, so the record reads *the service ended on the
cut date and the account was closed out on this later day, by this person*. Two
dates on purpose. That IS *"cleaner in the record"*.

⛔ **NOTHING IS WRITTEN TO `move_records`.** A close-out is not a move, and a
`kind="move_out"` row would be the exact falsification §1 forbids — written by
the module whose whole purpose is to avoid it. `moves.KINDS` is deliberately
left at two.

⛔ **`accounts.final_read_state` IS NOT WRITTEN EITHER.** `move_out` derives it
from the readings that flow takes. A close-out takes no reading: the meter was
read, or was not, at the CUT, months earlier. Writing a value here would claim a
reading this act did not take (hard-won law 1 — a claim is not the guarantee).

════════════════════════════════════════════════════════════════════════════
3 · AN OUTSTANDING BALANCE DOES NOT BLOCK A CLOSE-OUT, AND THAT IS NOT A NEW
    RULE — IT IS `BR-CUS-082`, ALREADY SIGNED
════════════════════════════════════════════════════════════════════════════
`BR-CUS-082` (CONFIRMED, PO 2026-08-24, verbatim *"(b) continue, ladder
restarts"*) rules that **a debt surviving closure is STILL CHASED and the ladder
RESTARTS FROM TIER 1**, as a COLLECTIONS sequence and never a service one — *"a
closed account cannot be escalated to disconnection; there is nothing left to
disconnect"*. Closure-with-a-balance is the case that rule was written for, so
this module asks the PO nothing about it (CLAUDE.md law 13) and adds no rule of
its own. It CONSUMES `disconnects.restart_after_closure`, which already holds
the TIER-1 write, the `SEQ_COLLECTIONS` sequence and the two independent guards
that make a cut on it impossible.

  Worked, on `A-11488`: cut 2026-08-18 owing **$612.75**, closed out
  2026-09-30. The account reaches `closed`, the **$612.75** stays owed, and a
  TIER-1 COLLECTIONS case opens against **the account itself**.

⚠ **AND IT TIES NOTHING BACK TO A MASTER.** `BR-CUS-097` as qualified
2026-08-27 makes the residue transfer **clerk-initiated** — *"if clark tied back
to A during move out process"* — a deliberate act in the S20 move-out wizard,
with an actor recorded. This act does not collect that consent and therefore
must not have that effect: `move_out_settlement._dunning_for(None)` says it in
the words of the rule, *"A residue nobody tied back does not become the
landlord's problem, and therefore does not become the landlord's letters"*, and
that sentence is CONSUMED here rather than restated.

  A cut sub-account whose residue SHOULD go to its master is closed through the
  move-out settlement path where the clerk can tie it back — not here. That is
  a boundary, not a gap, and `SHORTFALL_NOT_TIED_BACK` states it on every
  response so no screen can imply otherwise.

════════════════════════════════════════════════════════════════════════════
4 · WHAT THIS ACT DOES NOT CHECK, NAMED RATHER THAN IMPLIED
════════════════════════════════════════════════════════════════════════════
`OQ-680` is OPEN: whether an active payment plan, an open dispute or an unbilled
cycle must BLOCK a terminal act or merely warn was never put to the PO
(`DEF-744`). This module therefore performs **no clearance** and says so on
every response — the posture `TransferWizard` and `DisconnectWizard` step 1
already take. It does not refuse on any of the three, because inventing a
blocker would give the product a dead end with no documented way past it, which
is `DEF-744`'s own warning and `DEF-724`'s failure one flow over.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.customers import disconnects
from core import audit as core_audit
from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")

#: The only three keys this door accepts. `closed_at`, `status_code`, a final
#: read, a deposit disposition and a shortfall path are all REFUSED by omission:
#: `closed_at` is derived (BR-CUS-431) and the rest belong to flows that collect
#: a consent this act does not.
CLOSE_OUT_FIELDS: frozenset[str] = frozenset({"closed_out_on", "reason", "status"})

#: The audit action. **DELIBERATELY NOT `account.closed`**, which is what
#: `services.move_out` writes. One string is the difference between a permanent
#: record that says *this customer moved out* and one that says *this customer's
#: service was cut and the account was afterwards closed out*, and BR-CUS-430
#: exists because those are not the same event.
AUDIT_CLOSED_OUT = "account.closed_out"


#: ⛔ **THE ENGLISH FOR EVERY REFUSAL THIS MODULE RAISES, AND IT IS HERE BECAUSE
#: THERE IS NOWHERE ELSE A LANE MAY PUT IT.**
#:
#: `G32` is a RATCHET at **0** with no register: *"no `message_key` may be
#: raised that does not resolve"*, and it is a MERGE gate — the six keys below
#: resolve to nothing in the eleven catalogues, so this work cannot merge until
#: somebody lands them. But a lane is BANNED from editing those catalogues
#: (`10-scripts/i18n_extract_defaults.py`'s own header) and a `BizError` has no
#: `defaultValue` slot the way a `t()` call does — which is the whole of
#: `DEF-1650`.
#:
#: So the copy lives HERE, in the repo, next to the raise, in the one form that
#: is both durable and directly usable: `10-scripts/i18n_fanin.py` takes
#: `{key: {lang: text}}` and this is the `en` column of exactly that batch. It
#: is not a translation and it does not pretend to be one — it is the sentence
#: the owning lane owes, written by the lane that owes it, so the translation
#: lane has something to translate rather than a key and a shrug.
#:
#: ⚠ **EVERY SENTENCE IS WITHIN G33's TWELVE-WORD CAP**, checked by hand at the
#: time of writing, because a refusal that lands in the catalogue and then fails
#: G33 has moved the problem rather than fixed it.
#:
#: ⚠ **TWO OF THE SIX ARE INVISIBLE TO BOTH G32 AND G18** and are listed anyway:
#: `close_out_date_required` and `close_out_reason_required` reach
#: `services._field_error` as a POSITIONAL argument to a helper declared in
#: ANOTHER file, and both gates resolve positional `message_key` parameters only
#: for helpers declared in the file they are reading (`DEF-1650`). They are
#: missing from the catalogues just as surely; they simply have nothing
#: reporting them.
REFUSAL_COPY: dict[str, str] = {
    "customers.account.close_out_already_terminal": (
        "This account is already closed. Correcting a close-out means a new record."
    ),
    "customers.account.close_out_still_occupying": (
        "This customer still occupies the unit, so use Move-out instead."
    ),
    "customers.account.close_out_not_a_cut_account": (
        "Only an account whose service was cut can be closed out."
    ),
    "customers.account.close_out_before_cut": (
        "The close-out date cannot be earlier than the cut date."
    ),
    "customers.account.close_out_date_required": (
        "Enter the date you are closing this account out."
    ),
    "customers.account.close_out_reason_required": ("Say why this account is being closed out."),
}


# ════════════════════════════════════════════════════════════════════════════
# STATED ABSENCES — what a screen may NOT imply about this act
# ════════════════════════════════════════════════════════════════════════════
#: `OQ-830`. The reason is a sentence the clerk types, and nothing counts it.
REASON_VOCABULARY_UNRULED: dict[str, Any] = {
    "code": "close_out_reason_vocabulary_unruled",
    "br_ref": "BR-CUS-430 · OQ-830",
    "tracks": "OQ-830",
    "detail": "the close-out reason is FREE TEXT and no fixed list exists. `accounts.close_reason` "
    "has been PROPOSED-SCHEMA since 2026-08-08 with no ruled vocabulary, and the three words that "
    "keep appearing in defect rows — settled, written off, gone — are a lane's phrasing, not a "
    "ruling. A list invented here would be a permanent record of a category nobody signed, so the "
    "sentence is required and the classification is asked as OQ-830. Nothing is stubbed: the "
    "close-out works, and what is missing is the ability to COUNT closures by reason.",
}

#: `OQ-680` / `DEF-744`. The same posture the transfer and disconnect wizards
#: take at step 1, for the same unanswered question.
NO_CLEARANCE_PERFORMED: dict[str, Any] = {
    "code": "close_out_clearance_not_performed",
    "br_ref": "DEF-744 · OQ-680",
    "tracks": "OQ-680",
    "detail": "this act does not look up an active payment plan, an open dispute or an unbilled "
    "cycle, and it is not telling you they are clear. Whether any of the three must BLOCK a "
    "terminal act or merely warn was never put to the Product Owner (OQ-680, OPEN). Refusing on a "
    "blocker nobody ruled would give the product a dead end with no documented way past it — "
    "which is the failure DEF-724 exists to fix, one flow over.",
}

#: `BR-CUS-097` as qualified 2026-08-27 — the consent this act does not collect.
SHORTFALL_NOT_TIED_BACK: dict[str, Any] = {
    "code": "close_out_shortfall_not_tied_back",
    "br_ref": "BR-CUS-097 (qualified 2026-08-27) · BR-CUS-082 · OQ-366 (CLOSED)",
    "detail": "no residue is transferred to a master account here. BR-CUS-097 makes the tie-back "
    "CLERK-INITIATED — *'if clark tied back to A during move out process'* — a deliberate act in "
    "the S20 move-out wizard with an actor recorded, and this door does not collect that consent. "
    "So the restarted TIER-1 ladder runs against THIS account, per BR-CUS-082. A sub-account whose "
    "residue should follow its master is settled through the move-out settlement path instead.",
}

#: BR-CUS-107, still true after this change and reported so nobody reads the
#: close-out as having closed DEF-701 outright.
#:
#: ✅ **CLOSED 2026-08-31 — THE STATUS IS ASSIGNED AT THE CUT, SO THIS CONSTANT
#: IS NO LONGER AN ABSENCE.** It was `DISCONNECTED_STATUS_STILL_UNASSIGNED` and
#: it reported that `commit_cut` wrote no `accounts` column; before that it named
#: the wrong module for the blocker (`DEF-2640`). Both sentences are deleted
#: rather than reworded — hard-won law 1, a stated absence outlives its subject
#: faster than anything else in this repo.
#:
#: **PO ruling 2026-08-30 — the disconnect is the WHOLE event**, verbatim: *"when
#: we disconnect - we generate final bill at that time itself - so later bill is
#: not required ... entire workflow including all settlement and status update is
#: taken care at time of disconnect or move out - so account status changes and
#: outstanding is pending on account if any"*, closing `OQ-1170`. So a cut
#: account now READS `Disconnected` / `non_billable`, and this module's own
#: eligibility question is unchanged by it: `close_out` accepts a cut customer
#: exactly as it did, and `DEF-724`'s terminal path is still the second door the
#: PO ruled.
#:
#: **WHAT THIS CONSTANT SAYS NOW** is the one thing a close-out reader still
#: needs: the status a cut wrote is `non_billable`, NOT terminal, and this door
#: is what makes it terminal. The two must not be confused — a `Disconnected`
#: account is an OPEN account that owes money (`DSC-02.4`: the cut *"leaves the
#: account open"*), and only `close_out` ends it.
DISCONNECTED_IS_NOT_CLOSED: dict[str, Any] = {
    "code": "disconnected_is_not_a_closed_account",
    "br_ref": "BR-CUS-107 · BR-CUS-430/431 · `DSC-02.4` · PO ruling 2026-08-30",
    "detail": "since 2026-08-30 a cut writes BR-CUS-107's `Disconnected` status on the account, "
    "in behaviour class `non_billable`, together with the final metered bill for the days "
    "before the cut ($23.23 of a $40.00 base on `A-11488`, 18 days of 31) and whatever is left "
    "outstanding. **That is not a closed account.** `DSC-02.4` is explicit that a cut *'leaves "
    "the account open'* and is *'not a move-out'*, so a `Disconnected` customer is one who still "
    "owes money, can still pay it, and can still be reconnected. This door — BR-CUS-430/431, "
    "DEF-724 — is the only thing that makes such an account TERMINAL, and it writes the CUT date "
    "into `accounts.closed_at` rather than the day the clerk performed it.",
}

CLOSE_OUT_STATED_ABSENCES: tuple[dict[str, Any], ...] = (
    REASON_VOCABULARY_UNRULED,
    NO_CLEARANCE_PERFORMED,
    SHORTFALL_NOT_TIED_BACK,
    DISCONNECTED_IS_NOT_CLOSED,
)


# ════════════════════════════════════════════════════════════════════════════
# THE ELIGIBILITY QUESTION, ASKED ONCE
# ════════════════════════════════════════════════════════════════════════════
def _terminal_case(account_id: Any) -> Any:
    """The account's open disconnect case, or None.

    Resolved through `disconnects.open_case_for` BY NAME rather than by a query
    of my own: `uq_one_open_disconnect_case_per_account` is what makes "the one"
    a fact, and a second reader with its own `.exclude(...)` is a second answer
    to *which case is open* — exactly the drift `CLOSED_CASE_STATES` was named
    to stop.
    """
    return disconnects.open_case_for(account_id)


def eligibility(account_id: Any) -> dict[str, Any]:
    """Can this account be closed out, and — when it cannot — WHY, in the words
    of the rule that refuses it.

    The screen calls this before it draws anything, so a clerk is never offered
    a button that will refuse them. It writes nothing and takes no lock; the
    committing path re-asks every question under `account_or_404(lock=True)`,
    because a preview is a preview and two clerks are two clerks.
    """
    from apps.customers import selectors, services

    account = selectors.account_or_404(account_id)
    case = _terminal_case(account.pk)
    cut_on = getattr(case, "cut_on", None)
    balance = disconnects._balance_for(account.pk)

    blocker: dict[str, Any] | None = None
    if account.status.behavior_class == services.CLASS_TERMINAL:
        blocker = {
            "code": "already_terminal",
            "message_key": "customers.account.close_out_already_terminal",
            "br_ref": "BR-CUS-430",
            "detail": "this account has already reached a terminal state. Correcting a close-out "
            "is a NEW row, never an edit (CLAUDE.md hard rule 4).",
        }
    elif services.is_occupying(account.status):
        blocker = {
            "code": "still_occupying",
            "message_key": "customers.account.close_out_still_occupying",
            "br_ref": "BR-CUS-430 · BR-CUS-030",
            "detail": "this account still occupies its unit, so its departure is a MOVE-OUT and "
            "must be filed as one. A close-out records that a customer whose service was CUT has "
            "been finished with; filing an occupant's departure through it would put a move-out "
            "into the record as a disconnection, which is the same falsification BR-CUS-430 "
            "forbids in the other direction.",
        }
    elif case is None or getattr(case, "state", None) != disconnects.STATE_CUT or cut_on is None:
        blocker = {
            "code": "not_a_cut_account",
            "message_key": "customers.account.close_out_not_a_cut_account",
            "br_ref": "BR-CUS-430 · BR-CUS-431",
            "detail": "a close-out needs a service that was CUT, because BR-CUS-431 writes the "
            "CUT DATE into `accounts.closed_at` and there is no such date here. This account has "
            + (
                "no open disconnect case at all."
                if case is None
                else f"a case in state `{getattr(case, 'state', None)}`"
                + ("" if cut_on is not None else " and no recorded cut date")
                + "."
            ),
        }

    return {
        "account_id": str(account.pk),
        "account_no": account.account_no,
        "eligible": blocker is None,
        "blocked_by": blocker,
        # BR-CUS-431 — the date that WILL be written, shown before it is, because
        # it is the one thing no correction row can un-say.
        "closed_at_will_be": cut_on.isoformat() if cut_on else None,
        "cut_on": cut_on.isoformat() if cut_on else None,
        "case_no": getattr(case, "case_no", None),
        # ── WHAT WAS CUT, AND WHEN — added 2026-09-13 by lane A ─────────────
        # The blueprint's second panel on this screen (pages 107–111) asks for
        # the case, the REASON, the SERVICES CUT, the cut date and the balance.
        # Four of the five were already on `DisconnectCase` and none of them was
        # in this payload, so the screen could not draw the panel at all and a
        # clerk closing an account out could not see what they were finishing.
        #
        # ⚠ **READS ONLY, AND FROM THE CASE THIS FUNCTION ALREADY RESOLVED.**
        # No second query, no second answer to *which case is open* — that is
        # `_terminal_case`'s whole reason for existing. `cut_reason` is free text
        # a clerk typed at the cut and `services_cut` is a JSON list of service
        # CODES; the screen turns the codes into the tenant's own service names
        # (B14 rule 31 — a code is not a value a person reads).
        "cut_reason": getattr(case, "cut_reason", None),
        "services_cut": list(getattr(case, "services_cut", None) or []),
        "case_opened_on": (
            case.opened_on.isoformat() if case is not None and case.opened_on else None
        ),
        # What was owed WHEN THE SUPPLY WAS CUT, so the drawn *"unchanged since
        # the cut"* is a comparison the screen can actually make rather than a
        # sentence it asserts. `None` is a real answer on a case opened before
        # the column existed, and the screen says which — it never fills the gap
        # with the live balance, because two figures under one label is how a
        # clerk reads a payment that never happened (DEF-628's neighbourhood).
        "outstanding_at_cut": (
            None
            if getattr(case, "outstanding_at_cut", None) is None
            else disconnects._money(case.outstanding_at_cut)
        ),
        # BR-CUS-015: `accounts.balance` is a CACHE and is never read. This is
        # AR through the published seam, and None means the READING FAILED — it
        # is never rendered as $0.00 (DEF-628's shape).
        "balance": None if balance is None else disconnects._money(balance),
        "balance_unreadable": balance is None,
        "currency": account.currency,
        "dunning_if_closed": _dunning_preview(balance),
        "absences": [dict(entry) for entry in CLOSE_OUT_STATED_ABSENCES],
    }


def _dunning_preview(balance: Decimal | None) -> dict[str, Any]:
    """BR-CUS-082, shown to the clerk BEFORE they commit.

    CONSUMED from `move_out_settlement.DUNNING_AFTER_CLOSE` — the same constant
    `disconnects._dunning_after_close()` reads — rather than restated, because a
    second copy of a sentence about a rule is free to be "tidied" into a
    different answer (its own words, and this module inherits the reasoning).
    """
    from apps.customers import move_out_settlement

    dunning = dict(move_out_settlement.DUNNING_AFTER_CLOSE)
    if balance is None:
        dunning["will_restart"] = None
        dunning["reason"] = (
            "the balance could not be read, so whether a ladder restarts cannot be answered. It "
            "is not reported as zero: a fabricated $0.00 on an account in arrears is DEF-628."
        )
    elif balance > ZERO:
        dunning["will_restart"] = True
        dunning["reason"] = (
            "a debt survives this closure, so BR-CUS-082 restarts the ladder at TIER 1 as a "
            "COLLECTIONS sequence — it can never escalate to a disconnection, because there is "
            "nothing left to disconnect."
        )
    else:
        dunning["will_restart"] = False
        dunning["reason"] = (
            "this account closes owing nothing, so BR-CUS-030's `dunning stops` applies unchanged "
            "and no ladder runs. BR-CUS-082 supersedes that clause ONLY for the "
            "closed-with-balance case, and reading it wider would start a ladder against a "
            "settled customer."
        )
    dunning["subject"] = "the closed account itself"
    dunning["subject_detail"] = dict(SHORTFALL_NOT_TIED_BACK)["detail"]
    return dunning


# ════════════════════════════════════════════════════════════════════════════
# THE ACT
# ════════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def close_out(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """POST /accounts/{id}/close-out — BR-CUS-430 / BR-CUS-431 (DEF-724).

    The account whose service was cut is finished with: a TERMINAL status,
    `closed_at` = **the cut date**, every open service agreement ended on the
    same date, the disconnect case moved to `closed_out` carrying WHO did it and
    WHEN, one `account.closed_out` audit row — and, when a debt survives, the
    BR-CUS-082 TIER-1 collections ladder against this account.

    ONE transaction; audited (CLAUDE.md rule 7).

    NO advisory scope lock, for `move_out`'s stated reason: this decides about
    ONE existing row, so `account_or_404(lock=True)` IS the mutual exclusion. A
    second close-out waits on the row, then reads the terminal status and is
    refused `already_terminal`. A move-in racing the same unit blocks on the
    same row inside its own occupancy check.
    """
    from apps.customers import notifications_seam, selectors, services

    data = services._payload_dict(payload or {})
    services._reject_unknown(data, CLOSE_OUT_FIELDS)
    fe: list[dict[str, Any]] = []

    # BR-TEN-043 — the event date is an ARGUMENT, never a wall clock. This is
    # the date of the ACT, and it is the only date this payload may carry:
    # `closed_at` is DERIVED (BR-CUS-431) and is not offered as a field at all.
    if data.get("closed_out_on") in (None, ""):
        fe.append(
            services._field_error(
                "closed_out_on",
                errors.VAL_REQUIRED,
                "customers.account.close_out_date_required",
            )
        )
    closed_out_on = services._date(data.get("closed_out_on"), "closed_out_on", fe)

    # OQ-830 — a REQUIRED sentence rather than a picked category. The record of
    # why a household's account was ended has to say something, and what it may
    # say is not this lane's to fix.
    reason = services._text(data.get("reason"))
    if not reason:
        fe.append(
            services._field_error(
                "reason",
                errors.VAL_REQUIRED,
                "customers.account.close_out_reason_required",
            )
        )

    status = services._resolve_status(data["status"], fe) if "status" in data else None
    services._refuse_fields(fe)

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        if status is None:
            status = services._default_closed_status()
        if status.behavior_class != services.CLASS_TERMINAL:
            # A close-out that left the account non-terminal would close
            # nothing — BR-CUS-055 keys every downstream off the CLASS.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-430",
                message_key="customers.account.status_does_not_close",
                params={"status": status.code, "behavior_class": status.behavior_class},
            )

        # Every eligibility question, re-asked UNDER THE LOCK. `eligibility()`
        # answered them a moment ago for the screen; a preview is not a
        # decision, and two clerks are two clerks.
        answer = eligibility(account.pk)
        blocker = answer["blocked_by"]
        if blocker is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref=str(blocker["br_ref"]),
                message_key=str(blocker["message_key"]),
                params={
                    "account_no": account.account_no,
                    "status": account.status.code,
                    "detail": str(blocker["detail"]),
                },
            )

        case = _terminal_case(account.pk)
        cut_on: date = case.cut_on
        if closed_out_on is not None and closed_out_on < cut_on:
            # The act cannot predate the event it closes. Anything else would
            # write a `closed_out_on` before the `closed_at` it explains.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-431",
                message_key="customers.account.close_out_before_cut",
                params={
                    "closed_out_on": closed_out_on.isoformat(),
                    "cut_on": cut_on.isoformat(),
                },
            )

        # BR-CUS-015: the CACHE is never the balance. AR through the seam, and
        # `None` means the reading FAILED — which must not become a $0.00 that
        # quietly stops a ladder BR-CUS-082 requires (DEF-628's shape).
        balance = disconnects._balance_for(account.pk)

        # ── THE WRITES ──────────────────────────────────────────────────────
        # BR-CUS-431: the CUT date, and the derivation is in §2 of the module
        # docstring. Getting this wrong costs 43 days of a lawfully re-lettable
        # unit on the worked case, and no correction row can un-say it.
        account.closed_at = cut_on
        account.status = status
        account.save(update_fields=["closed_at", "status", "updated_at"])
        agreements = services._end_service_agreements(account, cut_on)

        case.state = disconnects.STATE_CLOSED_OUT
        case.closed_out_on = closed_out_on
        case.closed_out_by = str(getattr(actor, "id", None) or getattr(actor, "pk", None) or "")
        case.close_out_reason = reason
        case.save(
            update_fields=[
                "state",
                "closed_out_on",
                "closed_out_by",
                "close_out_reason",
                "updated_at",
            ]
        )

        account.refresh_from_db()
        after = selectors.account_detail_dict(account)
        record = {
            "case_id": str(case.pk),
            "case_no": case.case_no,
            "closed_out_on": closed_out_on.isoformat() if closed_out_on else None,
            "closed_out_by": case.closed_out_by or None,
            "reason": reason,
            # The two dates, side by side, because the whole point of the act is
            # that they are DIFFERENT and the record has to show both.
            "cut_on": cut_on.isoformat(),
            "closed_at": cut_on.isoformat(),
            "service_agreements_ended": len(agreements),
        }
        _audit(
            actor, AUDIT_CLOSED_OUT, account.pk, before=before, after={**after, "close_out": record}
        )

        # ── BR-CUS-082 — THE DEBT THAT SURVIVED ─────────────────────────────
        # CONSUMED, not restated. `restart_after_closure` holds the TIER-1
        # write, refuses a zero shortfall by name, and writes
        # `sequence=SEQ_COLLECTIONS` so `ck_collections_sequence_never_cuts`
        # makes a cut on it impossible in the database as well as in Python.
        #
        # ⚠ It runs INSIDE this transaction, after the audit row, for
        # `move_out`'s stated reason: there must never be a collections case
        # for a close-out that rolled back.
        dunning = _dunning_preview(balance)
        if balance is not None and balance > ZERO:
            restart = disconnects.restart_after_closure(
                actor,
                account.pk,
                as_of=closed_out_on or cut_on,
                shortfall=balance,
                currency=account.currency,
            )
            # ONE shape for the screen. `restart_after_closure` answers a CASE
            # payload with the dunning block nested inside it, so flattening
            # it here would give the close-out response two different shapes
            # depending on whether a debt survived — and the screen would need
            # to know which one it was holding.
            dunning["collections_case"] = {
                "case_id": restart.get("case_id"),
                "case_no": restart.get("case_no"),
                "tier": restart.get("tier"),
                "amount_chased": restart.get("amount_chased"),
            }

    # ── CR-048 wave B task B11 — THE CUSTOMER IS TOLD ──────────────────────
    # `catalogs.LISTINGS["email_account_closed"]` has read *"Not in use yet —
    # closing an account does not send this."* since 2026-08-16. It sends now.
    #
    # ⚠ **OUTSIDE THE TRANSACTION, DELIBERATELY**, exactly as `move_out` places
    # its own message: an account that has been made TERMINAL, whose service
    # agreements are ended and whose case is closed, must not be rolled back
    # because a letter could not be queued. `notifications_seam` raises nothing
    # and runs its write inside its own savepoint (hard-won law 14), so this
    # call cannot reach the work above it by either route.
    #
    # The BALANCE is passed as the same string the response states, so the
    # letter and the screen cannot disagree — and as `None` when the AR read
    # failed, because BR-CUS-015 forbids a failed read becoming a $0.00 and a
    # departing customer being told they owe nothing is the worst place for it.
    message = notifications_seam.queue_account_closed(
        case_id=case.pk,
        account_id=account.pk,
        closed_on=closed_out_on or cut_on,
        # ⚠ THE **DISPLAY** LEG, 2dp. `_money` labels both shapes and the
        # customer's letter takes the one a customer reads: CLAUDE.md rule 2 —
        # money is STORED to four decimals and DISPLAYED at two. The `stored`
        # leg would print `142.5000` on a closing statement.
        closing_balance=None if balance is None else disconnects._money(balance)["display"],
        actor=actor,
    )

    warnings = [dict(entry) for entry in CLOSE_OUT_STATED_ABSENCES]
    return {
        **after,
        "close_out": record,
        "balance_at_close_out": None if balance is None else disconnects._money(balance),
        "dunning": dunning,
        "warnings": warnings,
        # CR-048 B11 — queued, already queued, suppressed by this utility's own
        # switch, refused, or broken outright: every one of those is a fact
        # about this close-out, and a fact the response does not carry is a
        # fact nobody sees (hard-won law 2).
        "account_closed_message": [dict(row) for row in message],
    }


def _audit(
    actor: Any,
    action: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> None:
    """CLAUDE.md rule 7. `disconnects._audit`'s shape, and its reasoning: ending
    a household's account is not a money action, and the record is the same
    record."""
    core_audit.write_row(
        action=action,
        entity_type="account",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=before,
        after=after,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-724 (PO ruling 2026-08-27) + BR-CUS-430/431 + BR-CUS-082/097/110/103/056
# generated: 2026-08-27 by the close-out lane
# checklist: A✔ B✔ C✔ D✔ E✔(CloseOutPage.tsx + the two routes) F✔ G✔ H=OWED(🔒 human-review-ledger row)
# gates: ruff✔ black✔ pytest tests/test_def724_close_out.py · customers suite
# exceptions: NO `move_records` row is written and that is BR-CUS-431's own clause, not an omission — a close-out is not a move and `moves.KINDS` stays at two · NO `final_read_state` is written: this act takes no reading and the meter was read (or was not) at the CUT · NO deposit settlement, NO final bill and NO refund — those are `move_out_settlement`'s, they collect a clerk's consent this door does not, and a cut sub-account whose residue must follow its master is closed through that path instead (SHORTFALL_NOT_TIED_BACK) · NO clearance check on a payment plan, a dispute or an unbilled cycle: OQ-680 is OPEN and NO_CLEARANCE_PERFORMED says so on every response rather than implying one was performed · the close-out REASON is free text because OQ-830 is unanswered; nothing is stubbed, because a stub would break the act the PO ruled · `accounts.close_reason` is still PROPOSED-SCHEMA and is NOT written — the reason lives on the case, where a column exists · the `Disconnected` status (BR-CUS-107) is STILL not assigned by anything: DEF-701's billing half (`CLASSES_THAT_BILL`) was re-verified on this tree on 2026-08-27 and still excludes `non_billable`, and customers may not change it (B2 §2) · a story is OWED for this act (hard-won law 8) and a human-review-ledger row is OWED (🔒 sensitive path); both REPORTED, neither invented
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
