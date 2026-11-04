# ── Trace ──────────────────────────────────────────────
# Change:   CR-125-BRC07 — THE DISCONNECT CASE RECORD, blueprint
#           `02 Accounts Menu Blueprint.pdf` **p143**, with its two dialogs on
#           **p144** (hold) and **p145** (mark as cut). The page's own red
#           banner reads *"TODAY: no disconnect case page exists"* — no route,
#           no component, no endpoint — so this is the read half of a screen
#           that has never existed.
#           PO ruling, verbatim: *"okay build it as per specification and as
#           per what you ahve mentioned - Disconnect details view — every
#           section - i will consolidate actions - too many actions - keep
#           critical ones"*.
# Rules:    BR-CUS-039 (the ladder and its tiers) · BR-CUS-043 (an active and
#           current plan pauses the ladder) · BR-CUS-082 (a closed account
#           cannot be escalated) · BR-CUS-100 (proof of service; a tier-3 cut
#           is not schedulable on an unrecorded service) · BR-CUS-103 (base
#           charges STOP at the cut) · BR-CUS-104 (the fee is owed at the cut)
#           · BR-CUS-107 (`Disconnected` is the sixth status) · BR-BIL-007 (a
#           fee is the tenant's charge code, never a literal) ·
#           **BR-MET-1161 / hard rule 8** (an address lives on `premises`; the
#           record WALKS to it and declares none) · B14 rule 31 (no database id
#           is ever a field's visible value — this record is addressed by CASE
#           NUMBER) · B14 rules 32/33 (the copy budget) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money 4dp stored / 2dp displayed)
# Screens:  the DISCONNECT CASE RECORD, `/disconnects/{ref}` — a NEW top-level
#           route beside `/disconnects/new`, never under `/accounts/`
# Tests:    06-backend/tests/test_disconnect_record_page.py
# Impacts:  config/urls.py (ONE include line) ·
#           07-frontend/src/features/customers/disconnect/record/**
# ───────────────────────────────────────────────────────
"""The DISCONNECT CASE RECORD, assembled for one screen — `GET /disconnects/{ref}`.

═══════════════════════════════════════════════════════════════════════════
1 · THIS MODULE ASSEMBLES AND IT WRITES NOTHING
═══════════════════════════════════════════════════════════════════════════
Every figure on p143 already has an owner. `apps/customers/disconnects.py` owns
the ladder, the tiers, the protections, the notices, the proof and the cut;
`apps/customers/disconnect_reads.py` owns the list. **Neither is touched.** This
module CALLS them and arranges the answers in the order the drawing puts them,
so the record and the register cannot disagree about one case.

The three actions the record carries are the PO's ruling and not a reading of
the drawing's affordances:

  * **Hold the case** — `POST /accounts/{id}/protections`, which exists.
  * **Open the account** — a door, and nothing else.
  * **Mark as cut** — `POST /accounts/{id}/disconnect-case/cut`, which exists.

⛔ **TEN FURTHER WRITE PATHS EXIST ON THE SERVER AND ARE DELIBERATELY NOT GIVEN
A DOOR HERE** — stop the ladder, advance a tier, lift a protection, mark
reconnecting, restore service and the rest. The PO has seen that list and ruled
*"too many actions - keep critical ones"*, and is consolidating. Adding one now
is building the thing they said is too much. **`ACTIONS` below is the whole set
and a fourth entry is a ruling, not a commit.**

═══════════════════════════════════════════════════════════════════════════
2 · THE TWO FACTS p143 DRAWS THAT NOTHING IN THIS REPOSITORY HOLDS
═══════════════════════════════════════════════════════════════════════════
Both are rendered as a STATED ABSENCE and neither is derived from something
near it, because a plausible substitute on a page that authorises taking away
a household's water is worse than a blank.

  * **`Oldest debt · 62 days past due`.** No column, no read, no seam answers
    *how old the oldest unpaid item is*. `amount_owed_at_open` is a figure and
    not an age; `opened_on` is when the CASE opened, which is a different date
    from when the money fell due. Deriving it would mean ageing the AR ledger,
    which is `payments`' to do and nothing publishes.
  * **`Raised by · S. Ortiz · 04/14/2026`.** `disconnect_cases` carries
    `opened_on` and **no actor column at all**. The DATE half is served (it is
    `opened_on`); the NAME half is absent. `audit_log` holds a
    `disconnect.case.opened` row with an actor on it, and reading that here
    would make a screen depend on a table that is PRUNED ON A RETENTION
    SCHEDULE — the same trap CLAUDE.md hard rule 4 names for a corrected
    payment reference. A record that says *"raised by nobody"* after ninety
    days is worse than one that never claimed to know.

**Adding either column is a schema change and needs a ruling.** They are
reported, not invented.

═══════════════════════════════════════════════════════════════════════════
3 · `NOTICES SENT` IS TWO COLUMNS AND THE DRAWING DRAWS FOUR
═══════════════════════════════════════════════════════════════════════════
p143 draws `NOTICE · SENT · CHANNEL · STATE`, and **two of those four cannot be
filled by this product today — which is correct behaviour rather than a gap:**

  * **`STATE`** reads `delivery_state`, which `disconnects.DisconnectNotice`
    writes **NULL on every row, by a deliberate rule**: there is no email, SMS
    or print adapter, so a `Sent` here would be this product telling a regulator
    it delivered a letter it cannot deliver. The drawing's own red note says
    *"Queued is not sent"* and `disconnects.DELIVERY_UNAVAILABLE` is that
    sentence, already written, already travelling on every case payload.
  * **`CHANNEL`** reads `service_channel`, which is the **proof-of-service**
    channel — NULL until a clerk attests to how a posted item went out. It is
    not *"how we sent it"*; it is *"how a person says it was served"*, and on a
    notice nobody has attested to there is nothing to show.

So the honest table is `NOTICE · SENT`, and the two absent columns travel as
`columns_unavailable` so the screen states the absence once rather than drawing
two columns of dashes. **PROVED rows carry their channel** — a notice that HAS
been attested to has a real channel — so the column is served per row and the
table simply does not draw a header for a column that is empty on every row.

═══════════════════════════════════════════════════════════════════════════
4 · `WHAT A CUT WOULD DO` REFUSES ON EVERY TENANT IN THIS TREE, AND SAYS SO
═══════════════════════════════════════════════════════════════════════════
`disconnects.commit_cut` prices the reconnection from the tenant's
`CC-RECON` charge code (`BR-BIL-007` — never a literal). **No seed creates that
code**: the catalogue spells its sibling `RECON` at `$45.00` while the drawing
and the signed worked figure both say `$75.00`. Three sources, two
disagreements, and `CR-125-BRC07` §4 has it as the one number the PO must
settle.

**This module quotes `reconnection_terms` and NOTHING ELSE.** No literal, no
fallback, no "or $75.00". When the code is missing the server's own
`fee_absence` travels to the screen and the screen renders it. A record that
printed a price the product cannot charge would be worse than one that says it
cannot price the act.

═══════════════════════════════════════════════════════════════════════════
5 · `Mark as cut` IS DRAWN GREYED, AND THE GREY CARRIES THE SERVER'S REASON
═══════════════════════════════════════════════════════════════════════════
`cut_readiness()` below re-runs, READ-ONLY, every precondition
`disconnects.commit_cut` enforces, in `commit_cut`'s own order, and answers with
**the first one that refuses and the sentence that module wrote for it**. The
screen greys the button and prints that sentence BESIDE it — never on a hover
title, because a touch or keyboard user never sees a tooltip and the whole
point of the refusal is that it is READ. That is the pattern
`serviceRequestDecisions.tsx` already ratified for the Approve dialog.

⚠ **IT IS A PREVIEW AND NEVER A SECOND GATE.** Nothing here decides whether a
cut may happen: `commit_cut` re-runs all of it inside its own transaction, and
it must, because days pass between a screen being drawn and a button being
pressed. If the two ever disagree the SERVER is right and this is stale — which
is why every sentence below is lifted from `disconnects`' own exception rather
than restated, and why `ready` is computed from the list of refusals rather
than stored.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.customers import disconnects
from core import errors

# ═══════════════════════════════════════════════════════════════════════════
# THE STATED ABSENCES — §2, declared once each
# ═══════════════════════════════════════════════════════════════════════════
#: §2. The drawn `62 days past due` has no source of any kind.
OLDEST_DEBT_HAS_NO_SOURCE: dict[str, Any] = {
    "code": "oldest_debt_age_has_no_source",
    "br_ref": "BR-CUS-039",
    "detail": (
        "nothing in this repository records how old the oldest unpaid item on an account is. "
        "`disconnect_cases.amount_owed_at_open` is a FIGURE and not an age, and `opened_on` is "
        "when the case opened rather than when the money fell due. Ageing the AR ledger is "
        "payments' work and it publishes no such read. The blueprint draws `62 days past due` on "
        "p143; that number is an ILLUSTRATION (B14 rule 37) and there is no column behind it. "
        "Adding one is a schema change and needs a ruling."
    ),
}

#: §2. `disconnect_cases` has `opened_on` and no actor column.
RAISED_BY_HAS_NO_SOURCE: dict[str, Any] = {
    "code": "case_opener_not_recorded",
    "br_ref": "BR-CUS-039",
    "detail": (
        "`disconnect_cases` records WHEN a case was opened and never WHO opened it — there is no "
        "actor column on the table. `audit_log` holds a `disconnect.case.opened` row with an "
        "actor, and reading it here would make this record depend on a table that is PRUNED on a "
        "retention schedule, so the name would vanish from a regulator-facing record after "
        "ninety days. The date half IS served, as `opened_on`."
    ),
}

#: §3. Why the drawn `STATE` column is not drawn.
NOTICE_STATE_COLUMN_UNAVAILABLE: dict[str, Any] = {
    "code": "notice_delivery_state_is_null_by_rule",
    "br_ref": "BR-NOT-005",
    "detail": (
        "`disconnect_notices.delivery_state` is written NULL on every row by a deliberate rule: "
        "there is no email, SMS or print adapter in this release, so a delivery claim here would "
        "be this product telling a regulator it delivered something it cannot deliver. The "
        "blueprint's own red note on p143 says the same — queued is not sent."
    ),
}

#: §3. Why the drawn `CHANNEL` column has no header until a proof exists.
NOTICE_CHANNEL_COLUMN_EMPTY: dict[str, Any] = {
    "code": "service_channel_is_the_proof_channel",
    "br_ref": "BR-CUS-100",
    "detail": (
        "`disconnect_notices.service_channel` is the PROOF-OF-SERVICE channel and not a send "
        "channel: it is NULL until a person attests to how a posted item was served. No notice "
        "on this case has been attested to, so the column is empty on every row."
    ),
}

#: A case below tier 3 has no cut date, which is an ABSENCE and not a fault.
#:
#: ⚠ **DECLARED ONCE BECAUSE IT IS READ IN TWO PLACES** — the head chip and
#: `THE CASE`'s row — and the first draft gave the head one no reason at all.
#: `test_disconnect_record_page` caught it as *"cut_date carries neither a
#: value nor a reason"*, which is the invariant doing exactly what it is for:
#: a cell with neither renders an empty row that reads as a rendering bug, and
#: nothing else in this repository can see one.
NO_CUT_SCHEDULED: dict[str, Any] = {
    "code": "no_cut_scheduled",
    "br_ref": "BR-CUS-039",
    "detail": (
        "no cut is scheduled on this case. A cut date is written by `schedule_cut`, which "
        "serves the final notice and computes the earliest lawful date; a case at an earlier "
        "tier has not reached it."
    ),
}

#: A case that has entered no tier yet — nothing has been sent.
NO_TIER_YET: dict[str, Any] = {
    "code": "no_tier_reached",
    "br_ref": "BR-CUS-039",
    "detail": (
        "nothing has been sent on this case yet, so it sits on no rung of the ladder. "
        "`disconnect_cases.tier` is NULL and `ladder_tier_of` answers the same."
    ),
}

#: The account's own type row cannot be read.
NO_CUSTOMER_CLASS: dict[str, Any] = {
    "code": "account_type_not_readable",
    "br_ref": "BR-CUS-067",
    "detail": (
        "this account's `account_types` row cannot be read, so there is no class to name. The "
        "column is NOT NULL, so this is a row that has gone rather than a fact nobody gave."
    ),
}

#: §5. There is no case at all behind this reference's account.
NO_OPEN_CASE: dict[str, Any] = {
    "code": "no_open_case",
    "br_ref": "BR-CUS-039",
    "detail": "there is no open disconnect case on this account, so there is nothing to cut.",
}


# ═══════════════════════════════════════════════════════════════════════════
# THE THREE ACTIONS — the PO's ruling, and the whole set
# ═══════════════════════════════════════════════════════════════════════════
ACTION_HOLD = "hold"
ACTION_OPEN_ACCOUNT = "open_account"
ACTION_MARK_AS_CUT = "mark_as_cut"
#: ⚠ **p143's THREE, AND FOR 26 DAYS THIS WAS THE WHOLE SET.** PO ruling on
#: `CR-125-BRC07`: *"i will consolidate actions - too many actions - keep
#: critical ones"*. Ten further disconnect writes were mounted on the server and
#: none of them is drawn on p143.
DRAWN_ACTIONS: tuple[str, ...] = (ACTION_HOLD, ACTION_OPEN_ACCOUNT, ACTION_MARK_AS_CUT)
#: Kept under its old name because tests and a screen both read it.
ACTIONS: tuple[str, ...] = DRAWN_ACTIONS

# ═══════════════════════════════════════════════════════════════════════════
# AND THREE MORE, RULED 2026-09-20 — THE OTHER HALF OF THE JOB
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **THE SET ABOVE IS NO LONGER THE WHOLE SET, AND THAT IS A PO RULING RATHER
#: THAN A LANE DECIDING IT HAD A BETTER IDEA.** PO, 2026-09-20, verbatim:
#: *"The other half of the job. Today a utility can cut supply and cannot
#: restore it from the product."* and, of a failed visit, *"The register
#: reflects reality. Today a failed visit is invisible and the case looks
#: untouched."*
#:
#: ⚠ **IT DOES NOT REOPEN *"too many actions"*, BECAUSE THE HEADER STILL SHOWS
#: THREE.** The three added here are **STATE-EXCLUSIVE with `mark_as_cut` and
#: with each other**: a case is `scheduled` OR `cut` OR `reconnecting`, never
#: two of them, so exactly ONE commit is ever offered. What changed is not how
#: many controls a clerk sees; it is that the control they see is the one this
#: case can actually take. `Mark as cut` on a case cut last Tuesday can never
#: become pressable again — `cut_readiness` returns `already_cut` for ever —
#: and a permanently dead control over a live screen is the mirror of hard-won
#: law 2, which cost the customer portal six of its eight doors.
ACTION_RECORD_VISIT = "record_visit"
ACTION_MARK_RECONNECTING = "mark_reconnecting"
ACTION_RESTORE_SERVICE = "restore_service"
RECONNECT_ACTIONS: tuple[str, ...] = (ACTION_MARK_RECONNECTING, ACTION_RESTORE_SERVICE)

#: ⚠ **AND ONE MORE, WHICH IS `mark_as_cut` FINISHING RATHER THAN A NEW ACT
#: (`DEF-CUS-6063`).** Every other entry above starts something a clerk chose
#: to do. This one does not: `Mark as cut` promises three things on this very
#: page — *"Status becomes Disconnected"*, the final bill and the settlement —
#: and delivers two of them when billing refuses the bill, because the status
#: is written ONLY when the days up to the cut are billed. Until 2026-09-20
#: nothing in the product could ever deliver the third, on any case, ever.
#:
#: It is offered on ONE state: a case that is `cut` and whose account still
#: carries its old status. Everywhere else it is ABSENT rather than greyed,
#: for `available_actions`' own stated reason.
ACTION_FINISH_CUT = "finish_cut"



def available_actions(case: Any, account: Any = None) -> tuple[str, ...]:
    """What THIS case's state admits — two doors and exactly one commit.

    `hold` and `open_account` are on every case: holding a case is lawful in
    every state `record_protection` accepts, and the account is always there.

    The commit is the one the state is on:

      * `cut`          → `mark_reconnecting` (§5.8.4's *payment confirmed*)
      * `reconnecting` → `restore_service` (§5.8.4's *restored*)
      * anything else  → `mark_as_cut`, greyed with its reason where it is not
        ready — which is exactly what p143 draws on a `notice_sent` case.

    `record_visit` rides beside the commit on a SCHEDULED case only: a crew is
    dispatched against a cut date, so a case with no date on the calendar had
    nobody at its meter (`disconnect_visits.record_outcome` refuses it by name).

    ⚠ **A CLOSED CASE OFFERS NO COMMIT AT ALL.** `stopped`, `restored` and
    `closed_out` are finished; the only honest answer there is the two doors.

    ⚠ **`account` IS OPTIONAL AND ONLY ONE ANSWER NEEDS IT (`DEF-CUS-6063`).**
    Whether a cut is FINISHED cannot be read off the case: the status a cut
    writes lives on the account, and `disconnect_cases.status_before_cut` is
    NULL both when the status was held and on every case cut before the ruling
    of 2026-08-30 — one column, two meanings. A caller with no account in hand
    gets the pre-2026-09-20 answer rather than a guess.
    """
    state = getattr(case, "state", None)
    if state in disconnects.CLOSED_CASE_STATES:
        return (ACTION_HOLD, ACTION_OPEN_ACCOUNT)
    if state == disconnects.STATE_CUT:
        if account is not None and disconnects.cut_is_unfinished(case, account):
            return (
                ACTION_HOLD,
                ACTION_OPEN_ACCOUNT,
                ACTION_FINISH_CUT,
                ACTION_MARK_RECONNECTING,
            )
        return (ACTION_HOLD, ACTION_OPEN_ACCOUNT, ACTION_MARK_RECONNECTING)
    if state == disconnects.STATE_RECONNECTING:
        return (ACTION_HOLD, ACTION_OPEN_ACCOUNT, ACTION_RESTORE_SERVICE)
    if state == disconnects.STATE_SCHEDULED:
        return (ACTION_HOLD, ACTION_OPEN_ACCOUNT, ACTION_RECORD_VISIT, ACTION_MARK_AS_CUT)
    return DRAWN_ACTIONS

#: ⚠ **THE FACT THE RECORD NEVER STATED (`DEF-CUS-6064`).** `commit_cut` has
#: returned `cut_bill` and `account_status_held` on its payload since
#: 2026-08-30 and NOTHING has ever read either — not this module, not one file
#: under `07-frontend`. So a cut whose final bill was refused drew a cut case
#: beside an account still reading `active`, with no sentence anywhere saying
#: why, and the person who could fix the data was the one person never told
#: there was data to fix.
#:
#: The engine's ORIGINAL sentence is deliberately NOT quoted here. It survives
#: only on an `audit_log` row, and `audit_log` is PRUNED on a retention
#: schedule — §2 of this module's docstring refuses `Raised by` for exactly
#: that reason, and a record that says *"refused because …"* after ninety days
#: is worse than one that never claimed to know. What is served is the state,
#: which is derived from rows that do not expire, and the reason is produced
#: FRESH by the server when the clerk presses (§5's posture: the server is
#: right and a screen is stale).
#:
#: ⚠ **AMENDED 2026-09-21 — ITS LAST SENTENCE NAMED THE ONLY WAY OUT THERE WAS,
#: AND THERE ARE NOW TWO.** PO ruling 1 of 2026-09-21: *"in single bill we have
#: final bill workflow - so if clark want to complete the bill he can do it from
#: there - we will need to allow clark to complete the cut request later without
#: bill."* Completing the cut request and raising its final bill are two acts,
#: so *"fix what billing named, then finish the cut"* is now one option beside
#: completing the request with no bill at all.
CUT_NOT_FINISHED: dict[str, Any] = {
    "code": "cut_bill_was_refused_so_the_status_was_held",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · PO ruling 2026-08-30 · PO ruling 2026-09-21 · "
    "`DEF-CUS-6063`",
    "detail": "the supply is off and this account never took the `Disconnected` status, which "
    "means billing refused the final bill for the days before the cut. Two things can happen "
    "now: fix what billing named and finish the cut, or COMPLETE the cut request with no bill "
    "at all and raise the final bill afterwards from billing's own single-bill workflow (PO "
    "ruling 2026-09-21). Completing it without a bill takes the account out of the bill run, so "
    "the days nobody billed are stated on `days_not_billed` and stay stated until that bill "
    "exists.",
}

HOLD_KIND_DISPUTE = "dispute"

#: **THE ORDER p143 AND p144 DRAW, AND IT IS NOT THE SERVER'S.**
#: `disconnects.PROTECTIONS` is `(medical, payment_plan, weather_moratorium)`
#: and both drawings read `Medical certificate · Weather · A payment plan`. B14
#: rule 41 says the product matches the blueprint, and an ORDER is exactly the
#: kind of thing the drawing owns.
#:
#: ⚠ **IT IS A SORT KEY AND NEVER A LIST (CLAUDE.md law 12 / B14 rule 12's
#: shape).** Re-typing the three here would mean a fourth protection added to
#: `disconnects.PROTECTIONS` simply never reaching either surface — the
#: eleventh-service failure, which is silent: the row exists, the API serves
#: it, every test passes, and the screen never offers it. So anything this map
#: does not name keeps its server position, AFTER the ones it does.
DRAWN_ORDER: dict[str, int] = {
    disconnects.PROTECTION_MEDICAL: 0,
    disconnects.PROTECTION_MORATORIUM: 1,
    disconnects.PROTECTION_PLAN: 2,
    HOLD_KIND_DISPUTE: 3,
}


def _as_drawn(codes: Any, key: Any = None) -> list[Any]:
    """Sort by the drawing's order, keeping anything unknown in server order.

    A stable sort on `(drawn_position, server_position)`, so a fourth
    protection the drawing does not know about lands after the three it does
    rather than vanishing.
    """
    rows = list(codes)
    read = key or (lambda row: row)
    return sorted(
        rows,
        key=lambda row: (DRAWN_ORDER.get(str(read(row)), len(DRAWN_ORDER)), rows.index(row)),
    )


#: `record_protection` takes exactly these three (`disconnects.PROTECTIONS`),
#: carried through so the dialog's radio list cannot drift from the writer's.
HOLD_KINDS: tuple[str, ...] = tuple(disconnects.PROTECTIONS)  # re-ordered by `_as_drawn` below

#: p144 draws a FOURTH reason — *"A bill is disputed"* — and there is no fourth
#: protection. `protection_check` already refuses to call it `pass`: nothing in
#: this repository stores a disputed AMOUNT.
#:
#: ⛔ **IT IS NO LONGER OFFERED ON THE DIALOG — `DEF-CUS-6757`, 2026-09-25, lane
#: CUTPATH.** It was drawn DISABLED with this sentence as visible text, on
#: `BR-SHL-025`'s authority, and that was the wrong rule for this control.
#: `BR-SHL-025` is about a control **this deployment** cannot honour — a thing
#: some tenant could switch on, which a clerk deserves to see and be told about.
#: There is no deployment, tenant setting or future flag that makes this one
#: pressable: `disconnects.record_protection` refuses a fourth kind BY NAME and
#: nothing anywhere stores what it would need. **A permanent impossibility
#: offered beside its own refusal is the worst of both** — it is the mirror of
#: hard-won law 2, a dead control over a live screen, and on a dialog with three
#: real choices it costs a clerk a decision every time.
#:
#: ⚠ **THE CONSTANT STAYS AND IS STILL SERVED**, because the REASON is what the
#: next lane needs and because `protection_check`'s fourth row still answers
#: `unavailable` on the record's own protections panel — where the drawn
#: question *"Disputed bill open?"* is a READ and not an offer to act.
#: `DEF-CUS-6792` is the open row on whether that read is answerable at all, and
#: `OQ-CUS-12737` asks whether a disputed bill becomes a fourth hold kind.
#: Neither is decided here.
HOLD_DISPUTE_UNRECORDABLE: dict[str, Any] = {
    "code": "dispute_is_not_a_protection",
    "br_ref": "BR-CUS-096",
    "detail": (
        "nothing in this repository stores a disputed AMOUNT — no model, no table, no seam — so "
        "a dispute cannot be recorded as a hold. `disconnects.record_protection` names three "
        "protections and refuses a fourth by name: a fourth protection freezes a real debt and "
        "needs a ruling, not a string."
    ),
}

#: Which kinds take the drawn `Review on` date, and which refuse it. Both halves
#: are `record_protection`'s own rules and neither is restated here — a medical
#: certificate MUST carry its expiry, a moratorium is a date WINDOW and carries
#: both ends, and a payment-plan protection takes NO expiry because BR-CUS-043
#: holds it while the plan is active and current.
HOLD_REVIEW_DATE: dict[str, str] = {
    disconnects.PROTECTION_MEDICAL: "required",
    disconnects.PROTECTION_MORATORIUM: "required",
    disconnects.PROTECTION_PLAN: "refused",
}


# ═══════════════════════════════════════════════════════════════════════════
# WHAT HOLDING ACTUALLY DOES — and the two promises p144 makes that it does not
# ═══════════════════════════════════════════════════════════════════════════
#: p144's `WHAT HOLDING WILL DO` table draws four rows and promises three
#: immediate effects: the cut date is cleared, the ladder stops, and the case
#: moves to `On hold`.
#:
#: ⛔ **ONLY ONE OF THE THREE IS TRUE IN THIS PRODUCT TODAY**, measured against
#: `disconnects.record_protection`, which writes an `AccountProtection` row and
#: **touches the case not at all**:
#:
#:   * *the ladder stops* — **TRUE, and it is the design.** `halt_reason` is
#:     COMPUTED on every call and answers `HALT_PROTECTED` while a protection is
#:     in force. Nothing stores *"the ladder is running"* on purpose: the
#:     writer's own words are that *"a RUN cached on a row outlives the debt"*.
#:     ⚠ **THAT IS THE UNATTENDED LADDER AND IT IS UNCHANGED. IT IS NOT A CLERK
#:     BEING STOPPED**, and under `BR-CUS-1096` (PO 2026-09-25, closing
#:     `OQ-680`) a protection WARNS a clerk and never refuses their act. Do not
#:     read this bullet as licence for a screen to disable a control.
#:   * *the cut date is cleared* — **FALSE.** `cut_scheduled_for` is not
#:     written. A held case keeps its date.
#:   * *the case moves to `On hold`* — ✅ **TRUE SINCE 2026-09-25
#:     (`DEF-CUS-6755`, lane CUTPATH).** This bullet read **FALSE** while
#:     `STATE_ON_HOLD` was assigned by nothing anywhere in the repository.
#:     `disconnects.displayed_state` now DERIVES it from the protections in
#:     force, which is the design this repository had already chosen and written
#:     down twice — a hold cached on a row outlives the thing that caused it,
#:     and a payment plan's protection has no expiry to un-write it by. The
#:     drawn word is **segment**, and a derivation is what a segment reads.
#:
#: **SO THE TABLE BELOW IS THE TRUE CONSEQUENCE SET AND IT IS TWO OF THREE.**
#: The remaining false promise — the cut date being cleared — is stated as a
#: consequence in its own right, in the `not_now` half: the cut date STAYS. That
#: is a fact a clerk needs before they press the button, and silence about it is
#: the dangerous version. It is NOT quietly made true here: clearing a scheduled
#: cut date is a write on the household's enforcement dates, and `commit_cut`
#: already refuses a case that is not `scheduled`, so the date does no harm
#: where it sits.
HOLD_EFFECT_NOW = "now"
HOLD_EFFECT_NOT_NOW = "not_now"
HOLD_EFFECTS: tuple[dict[str, str], ...] = (
    {"when": HOLD_EFFECT_NOW, "code": "ladder_stops"},
    # `DEF-CUS-6755` — p144's third drawn promise, kept at last.
    {"when": HOLD_EFFECT_NOW, "code": "case_moves_to_on_hold"},
    {"when": HOLD_EFFECT_NOT_NOW, "code": "cut_date_stays"},
    {"when": HOLD_EFFECT_NOT_NOW, "code": "debt_stays_and_ages"},
)

#: Carried on every payload so the screen can never quietly re-acquire the two
#: promises, and so the next lane reads WHY the drawn table is two rows short.
HOLD_PROMISES_NOT_KEPT: dict[str, Any] = {
    "code": "hold_clears_no_date_and_moves_no_state",
    "br_ref": "BR-CUS-039",
    "detail": (
        "p144 promises that holding clears the cut date and moves the case to `On hold`. The "
        "SECOND is kept as of 2026-09-25 (`DEF-CUS-6755`): `disconnects.displayed_state` "
        "derives `on_hold` from the protections in force, which is the segment the drawing "
        "names. The FIRST is still not kept — `record_protection` writes a protection row and "
        "`cut_scheduled_for` is unchanged — so this dialog states the cut date STAYING as its "
        "own consequence rather than leaving a clerk to find it on the record afterwards."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A CUT WOULD DO — the drawn rows that are RULES rather than reads
# ═══════════════════════════════════════════════════════════════════════════
#: p143's `Base charges · stop at the cut — the balance goes static`. This is
#: **BR-CUS-103** (PO 2026-08-25, OQ-380, *"no"*) and `disconnects.CUT_STOPS_BASE`
#: is that ruling already written down. Carried by reference, never restated.
CUT_STOPS_BASE = disconnects.CUT_STOPS_BASE
#: p143's `Account status becomes · Disconnected`. **BR-CUS-107**, and
#: `disconnects.DISCONNECTED_STATUS_ASSIGNED` is the record of it.
CUT_WRITES_STATUS = disconnects.DISCONNECTED_STATUS_ASSIGNED
#: p143's red banner — *"A disconnect is not a close-out."*
CUT_IS_NOT_A_CLOSE_OUT: dict[str, Any] = {
    "code": "a_cut_is_not_a_close_out",
    "br_ref": "BR-CUS-091",
    "detail": (
        "the account stays open, the ladder stops, and the debt stays exactly where it is. "
        "Closing an account is a move-out, on a different screen, by somebody deciding the "
        "customer has gone."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════
def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _fact(value: Any, absence: dict[str, Any] | None = None) -> dict[str, Any]:
    """One label→value row, or the reason there is no value.

    ⚠ **NEVER BOTH, AND NEVER NEITHER.** `move_record_reads._fact`'s contract,
    restated rather than imported so this module takes no dependency on a file
    a different screen owns — the two shapes are identical on the wire and
    `test_disconnect_record_page.py` asserts the invariant over the WHOLE
    payload rather than cell by cell.
    """
    # ⚠ **AN EMPTY LIST IS AN ABSENCE, NOT A VALUE.** `services_affected` is the
    # row this bit: a case with no service chosen served `value: []` with no
    # reason beside it, which renders as a blank cell on the panel that
    # previews taking a household's supply away. `0` is NOT caught here — a
    # zero is a figure somebody measured and `DEF-127`'s whole point is that it
    # must never be substituted for an absence, nor an absence for it.
    if value is not None and value != "" and value != [] and value != ():
        return {"value": value, "unavailable": None}
    return {"value": None, "unavailable": dict(absence) if absence else None}


def _as_of(as_of: date | None) -> date:
    """BR-TEN-043 — the event date is an argument, never a wall clock, and the
    ONE place a default is taken is here."""
    from django.utils import timezone

    return as_of or timezone.localdate()


def _case_by_reference(ref: str) -> Any:
    """The case this URL names — **by CASE NUMBER and never by uuid** (B14 rule
    31).

    `DSC-26-0003` is what a clerk reads back to a customer holding a notice, and
    it is what the blueprint's own URL carries:
    `/brazosbend/disconnects/dsc-26-0003`. Matching is case-INSENSITIVE for
    exactly that reason — the drawn address is lower and the quoted number is
    upper — which is `move_record_reads.record_detail`'s precedent.
    """
    key = (ref or "").strip()
    if not key:
        return None
    return (
        disconnects.DisconnectCase.objects.filter(tenant_id=_tenant_id(), case_no__iexact=key)
        .select_related("account")
        .first()
    )


def _account_of(case: Any) -> Any:
    from apps.customers import models as cmodels

    return cmodels.Account.objects.filter(tenant_id=_tenant_id(), pk=case.account_id).first()


def _owed(account: Any) -> dict[str, Any]:
    """The LIVE ledger position — never `amount_owed_at_open`.

    `disconnect_cases.amount_owed_at_open` is *what was owed when the case was
    opened*, which is a fact ABOUT the case and is wrong on the day somebody
    pays. p143's `Owed` row is the figure a clerk is about to act on, so it is
    read from AR every time, through the seam the register already uses.

    ⚠ **A FAILED READ IS `None` WITH ITS REASON, NEVER `$0.00`** — `DEF-127`, in
    `disconnect_reads.owed_cell`'s own words: a fabricated zero *"looks exactly
    like a settled account"*, and on THIS page it would look like a household
    nobody should be cutting.
    """
    from apps.customers import seams

    positions = seams.ar_positions([account.id])
    amount = positions.amount_for(account.id) if positions.available else None
    if amount is None:
        return {
            "stored": None,
            "display": None,
            "currency": account.currency,
            "unavailable": positions.unavailable,
        }
    money = disconnects._money(Decimal(str(amount)))
    return {
        "stored": money["stored"],
        "display": money["display"],
        "currency": positions.currency or account.currency,
        "unavailable": None,
    }


def _premise_line(account: Any) -> str | None:
    """`142 Bakers Row · Suite 1 · Silver Creek, TX 78611` — WALKED.

    **Hard rule 8 / `BR-MET-1161`:** an address is stored on `premises` and
    NOWHERE else; a unit refines it by LABEL. So this record declares no address
    column, copies none onto the case, and reaches the premises the way every
    other entity does — through `selectors._premise_cell`, which is the same
    cell the register's `ADDRESS` column draws. One walk, so an envelope and
    this page cannot disagree.
    """
    from apps.customers import seams, selectors

    _label, premise = selectors._premise_cell(account.unit_id, account=account)
    if not premise:
        return None
    # ⚠ **THE TOWN IS A SECOND WALK AND IT IS NOT OPTIONAL HERE.**
    # `_premise_cell` composes `street · unit`, which is what a LIST column has
    # room for. p143 draws the whole address under the title, and a
    # disconnection notice that names a street and no town is not an address.
    # `seams.premises_locality` is the read `DEF-CUS-3653` landed when the
    # account header's locality was found composed from the RETIRED
    # `customers.addresses` `kind='service'` row — so this is the walk, through
    # the module that owns those three columns, and this record declares none.
    locality = None
    premises_id = getattr(account, "premises_id", None)
    if premises_id in (None, "") and account.unit_id not in (None, ""):
        try:
            premises_id = seams.unit_dict(seams.unit_row(account.unit_id)).get("premises_id")
        except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
            premises_id = None
    if premises_id:
        locality = seams.premises_locality(premises_id)
    town = _locality_line(locality)
    return f"{premise} · {town}" if town else premise


def _locality_line(locality: Any) -> str | None:
    """`Silver Creek, TX 78611` — the premises' own three columns, or nothing.

    A partial locality is rendered from whatever parts exist rather than
    refused: a premises with a town and no postcode is a real row, and printing
    the town is more use to a clerk than printing nothing.
    """
    if not isinstance(locality, dict):
        return None
    city = (locality.get("city") or "").strip()
    region = (locality.get("state") or locality.get("region") or "").strip()
    postcode = (locality.get("postal_code") or locality.get("zip") or "").strip()
    tail = " ".join(part for part in (region, postcode) if part)
    if city and tail:
        return f"{city}, {tail}"
    return city or tail or None


def _customer_class(account: Any) -> str | None:
    """p143's fourth head chip — `Commercial`.

    The tenant's own `account_types` row, by NAME (B14 rule 31 — the visible
    value is never the stored code and never the id). It was served by nothing
    on this surface before this screen; the COLUMN has always been there and is
    NOT NULL, so this is a read that was missing rather than a fact that is.
    """
    account_type = getattr(account, "account_type", None)
    return getattr(account_type, "name", None)


# ═══════════════════════════════════════════════════════════════════════════
# THE SECTIONS — p143, in the order the page draws them
# ═══════════════════════════════════════════════════════════════════════════
def _the_case(case: Any, account: Any) -> dict[str, Any]:
    """p143's first panel: account · owed · oldest debt · tier · cut date ·
    raised by. **Six drawn rows and two of them have no source** — §2."""
    return {
        # B14 rule 31 — the account NUMBER, never its id.
        "account_no": _fact(account.account_no),
        "owed": _owed(account),
        "oldest_debt": _fact(None, OLDEST_DEBT_HAS_NO_SOURCE),
        "tier": _fact(disconnects.ladder_tier_of(case), NO_TIER_YET),
        "cut_date": _fact(
            case.cut_scheduled_for.isoformat() if case.cut_scheduled_for else None,
            NO_CUT_SCHEDULED,
        ),
        # §2 — the DATE half is real and the NAME half is not.
        "opened_on": _fact(case.opened_on.isoformat() if case.opened_on else None),
        "raised_by": _fact(None, RAISED_BY_HAS_NO_SOURCE),
    }


def _notices(case: Any) -> dict[str, Any]:
    """p143's `NOTICES SENT` — §3's honest two columns, newest first.

    Every notice raised on this CASE, which is narrower than
    `disconnects.notices_for_account` (that one spans every case the account has
    ever had, because step 3 of the wizard needs the account's whole history).
    A record of ONE case shows that case's letters.
    """
    rows = (
        disconnects.DisconnectNotice.objects.filter(tenant_id=_tenant_id(), case_id=case.pk)
        .select_related("case")
        .order_by("-issued_on", "-created_at")
    )
    served = [disconnects.proof_payload(row) for row in rows]
    return {
        "rows": tuple(
            {
                "tier": row["tier"],
                "issued_on": row["issued_on"],
                # §3 — the PROOF channel, present only where a person attested.
                "channel": row["channel"],
                "proved": row["recorded"],
            }
            for row in served
        ),
        # §3. Both are absences about COLUMNS rather than about rows, so they
        # are stated once for the table instead of once per cell.
        "state_column_unavailable": dict(NOTICE_STATE_COLUMN_UNAVAILABLE),
        "channel_column_empty": (
            None if any(row["channel"] for row in served) else dict(NOTICE_CHANNEL_COLUMN_EMPTY)
        ),
        "delivery": dict(disconnects.DELIVERY_UNAVAILABLE),
    }


def _protections(account: Any, *, as_of: date) -> dict[str, Any]:
    """p143's `PROTECTIONS CHECKED` — four questions, three answerable.

    `disconnects.protection_check` is the ONE read and it already answers with
    three-valued outcomes: `pass` · `fail` · **`unavailable`**, the last of which
    is the drawn *disputed bill* row. Nothing in this repository stores a
    disputed AMOUNT, so a green clearance there would be fabricated on the
    screen that authorises a cut.

    ⚠ **THE DRAWING GIVES A `CHECKED` DATE PER ROW AND THE PAYLOAD CARRIES ONE
    `as_of` FOR ALL FOUR.** A protection is not *checked* on a date and stored;
    it is COMPUTED, now, from the rows in force. So every drawn per-row date
    would be today's, four times — which reads as four separate attestations
    and is one read. The date is served ONCE, for the section, and the screen
    draws it once. Storing a per-row checked-at would be inventing an
    attestation nobody made.
    """
    check = disconnects.protection_check(account.id, as_of=as_of)
    return {
        "as_of": str(check["as_of"]),
        # p143's drawn order — `Medical · Weather · A payment plan · Disputed`
        # — which is NOT `disconnects.PROTECTIONS`'. See `DRAWN_ORDER`.
        "checks": tuple(
            {
                "check": row["check"],
                "outcome": row["outcome"],
                "reason": row["reason"],
            }
            for row in _as_drawn(check["checks"], key=lambda row: row["check"])
        ),
        # ⚠ NOT the drawn `All clear` chip. `all_clear` is computed over the
        # THREE protections that exist and `DSC-02.2` draws TEN questions, six
        # of them unbuilt (`BR-CUS-101`). A green summary over six unasked
        # questions is a fabricated clearance, so it travels under its own name
        # and the screen renders the four rows instead.
        "all_clear": check["all_clear"],
    }


def _what_a_cut_would_do(case: Any, account: Any) -> dict[str, Any]:
    """p143's right-hand panel — §4.

    Five drawn rows. The fee is QUOTED from the tenant's charge code and never
    from a literal; the two consequence rows are RULES and travel by reference.

    ⛔ **`To clear first` IS `disconnects._to_clear`'S ANSWER AND THIS FILE DOES
    NO ARITHMETIC ON IT — `DEF-CUS-6050`.** It used to add `Owed` and the fee
    here, which is right only until a cut commits: `commit_cut` ISSUES the fee
    bill, so from that instant the position already contains it and the addition
    quotes one fee too much. On 2026-09-21 this panel read **`$8,390.00`**
    beside its own **`Owed $8,315.00`**, against BR-CUS-104's signed
    **`$8,315.00`**. The owning module now decides the basis from `case.cut_on`
    and reads the position once after the cut; a second copy of the arithmetic
    on this side is exactly how the two came to disagree, so there is none.
    """
    terms = disconnects.reconnection_terms(account.id, case=case)
    services = tuple(case.services_cut or ())
    owed = _owed(account)
    fee = terms["fee"]
    figure = terms["to_clear"]
    total = figure["total"]
    to_clear: dict[str, Any] = {
        "stored": None if total is None else total["stored"],
        "display": None if total is None else total["display"],
        # ⚠ The CURRENCY is still this page's, because `_money` carries only the
        # two SHAPES and a figure never travels without its currency (rule 2).
        "currency": owed["currency"],
        "unavailable": (
            None
            if total is not None
            else (owed["unavailable"] or terms["fee_absence"] or figure["total_absence"])
        ),
    }
    return {
        "services_affected": _fact(
            list(services),
            {
                "code": "no_services_chosen",
                "br_ref": "B18 §5.8.7",
                "detail": (
                    "no service on this case is marked for full disconnection. `DSC-02.1` is "
                    "explicit that this is one decision per service, not all or nothing, so a "
                    "cut that names no service cannot fall back on cutting everything."
                ),
            },
        ),
        # §4 — the tenant's `CC-RECON` row or its stated absence. NEVER a
        # literal and never a fallback.
        "reconnection_fee": {
            "charge_code_configured": fee is not None,
            "stored": fee["stored"] if fee else None,
            "display": fee["display"] if fee else None,
            "currency": account.currency,
            "unavailable": terms["fee_absence"],
            "timing": dict(disconnects.FEE_TIMING_RULED),
        },
        "account_status_becomes": dict(CUT_WRITES_STATUS),
        "to_clear_before_reconnection": to_clear,
        "base_charges": dict(CUT_STOPS_BASE),
        "not_a_close_out": dict(CUT_IS_NOT_A_CLOSE_OUT),
        # `DEF-CUS-6064` — the panel promises *"Status becomes Disconnected"*
        # two rows up. On a cut where that did not happen, it now says so.
        "cut_unfinished": (
            dict(CUT_NOT_FINISHED)
            if disconnects.cut_is_unfinished(case, account)
            else None
        ),
        # ⚠ **THE DAYS NOBODY HAS BILLED — PO RULING 2026-09-21.** A cut may be
        # COMPLETED with no bill, and a `disconnected` account leaves
        # `accounts_for_bill_run`, so these days would otherwise stop being
        # anywhere the day the status was written. This row is what the ruling's
        # *"the days must remain visible to somebody"* buys, and it is DERIVED
        # on every read: it disappears by itself the moment billing's
        # single-bill workflow covers the cut day. It is served on a FINISHED
        # cut as well as a held one — that is precisely the case it exists for.
        "days_not_billed": (
            disconnects.unbilled_days_at_cut(case)
            if getattr(case, "state", None) == disconnects.STATE_CUT
            else None
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# §5 · IS `Mark as cut` PRESSABLE, AND IF NOT, WHY — IN THE SERVER'S OWN WORDS
# ═══════════════════════════════════════════════════════════════════════════
def cut_readiness(case: Any, account: Any, *, as_of: date) -> dict[str, Any]:
    """Every precondition `commit_cut` enforces, run READ-ONLY, in its order.

    ⚠ **THE SENTENCES ARE LIFTED, NEVER RESTATED.** Each branch below calls the
    guard `commit_cut` calls and catches `DisconnectRuleError`, so the words a
    clerk reads beside a greyed button are the words the refusal would have
    carried. A paraphrase here is a second answer to a question the writer
    already answers, and it drifts the moment that module is edited.

    ⚠ **IT IS A PREVIEW, NOT A GATE** — §5 of the module docstring. `commit_cut`
    re-runs all of it inside its transaction, because days pass between a screen
    being drawn and a button being pressed.

    ⚠ **ALL OF THEM ARE COLLECTED, NOT THE FIRST.** `commit_cut` stops at the
    first refusal because it is performing an act; a screen is answering *what
    would I have to do*, and a clerk told one thing at a time makes four trips.
    The FIRST is what the button carries; the rest travel beside it.
    """
    blockers: list[dict[str, Any]] = []

    def _refused(fn: Any) -> None:
        try:
            fn()
        except disconnects.DisconnectRuleError as refusal:
            blockers.append(
                {
                    "code": refusal.code,
                    "br_ref": refusal.br_ref,
                    "detail": str(refusal),
                }
            )

    # ⚠ **`already_cut`, NOT `state == STATE_CUT` — `DEF-CUS-6062`.** The screen
    # asks the writer's own question through the writer's own predicate, so a
    # row that reads `scheduled` while carrying a `cut_on` — the record the
    # walk-around left behind on a real case — greys `Mark as cut` with the
    # sentence the server would have raised, instead of offering a household a
    # second $75.00. The refusal CODE is unchanged, so the catalogue sentence
    # (`customers.disconnectRecord.refused.already_cut`) already covers it.
    if disconnects.already_cut(case):
        blockers.append(
            {
                "code": "already_cut",
                "br_ref": "BR-CUS-039",
                "detail": (
                    f"this account was already cut on {case.cut_on}. A cut is recorded once: "
                    "re-recording it would re-quote the reconnection fee and re-date the "
                    "enforcement."
                ),
            }
        )
    elif case.state != disconnects.STATE_SCHEDULED:
        blockers.append(
            {
                "code": "cut_not_scheduled",
                "br_ref": "B18 §5.8.7",
                "detail": (
                    f"this case is {case.state!r} and no cut is scheduled on it. Nothing is cut "
                    "until the scheduled date, and the scheduling is what serves the notice, "
                    "computes the earliest lawful date and records the services chosen."
                ),
            }
        )

    _refused(lambda: disconnects.assert_cut_reachable(case))

    if case.cut_scheduled_for is None:
        # Folded into `cut_not_scheduled` above on a non-scheduled case; stated
        # on its own when a scheduled case somehow carries no date.
        if case.state == disconnects.STATE_SCHEDULED:
            blockers.append(
                {
                    "code": "cut_before_the_scheduled_date",
                    "br_ref": "BR-CUS-039",
                    "detail": "this case carries no earliest lawful cut date.",
                }
            )
    elif as_of < case.cut_scheduled_for:
        blockers.append(
            {
                "code": "cut_before_the_scheduled_date",
                "br_ref": "BR-CUS-039",
                "detail": (
                    f"the earliest lawful cut on this case is {case.cut_scheduled_for}. That "
                    "date is the notice period the customer was given, and cutting before it is "
                    "cutting without the notice."
                ),
            }
        )

    if not tuple(case.services_cut or ()):
        blockers.append(
            {
                "code": "no_services_chosen",
                "br_ref": "B18 §5.8.7",
                "detail": (
                    "no service on this case is marked for full disconnection. One decision per "
                    "service, not all or nothing."
                ),
            }
        )

    # ⚠ **`for_cut=True`, WHICH IS NOT A DETAIL.** `commit_cut` calls
    # `_require_running(..., for_cut=True)`, and that flag drops ONE test —
    # *"is the ladder already at the top"* — because reaching tier 3 is the
    # precondition of a cut rather than a reason to refuse one. A preview run
    # without it would grey the button on every case that is actually ready.
    halt = disconnects.halt_reason(account.id, as_of=as_of, case=case, for_cut=True)
    if halt is not None:
        blockers.append(
            {
                "code": str(halt["code"]),
                "br_ref": str(halt["br_ref"]),
                "detail": f"the ladder is not running for this account: {halt['detail']}",
            }
        )

    # ⛔ **ONE OF THE TWO REFUSALS THIS USED TO COLLECT IS NOW A WARNING —
    # `BR-CUS-1099`, PO 2026-09-25.** `assert_service_proved` no longer raises
    # on an UNRECORDED proof; it still raises on a proof recorded through a
    # non-certified channel, which the ruling does not reach. The absence
    # travels as a warning instead, so the screen still asks for the proof and
    # no longer greys the button over it.
    _refused(lambda: disconnects.assert_service_proved(case))
    warnings = list(disconnects.service_proof_warnings(case))

    terms = disconnects.reconnection_terms(account.id, case=case)
    if terms["fee"] is None:
        absence = terms["fee_absence"] or dict(disconnects.CHARGE_CODE_SPELLING_UNRULED)
        blockers.append(
            {
                "code": str(absence["code"]),
                "br_ref": str(absence["br_ref"]),
                "detail": (
                    "the reconnection fee cannot be read from this tenant's charge code. A cut "
                    "nobody can price is a cut the customer cannot undo. "
                    + str(absence["detail"])
                ),
            }
        )

    return {
        "ready": not blockers,
        "refusal": blockers[0] if blockers else None,
        "blockers": tuple(blockers),
        # ⚠ **`ready` DOES NOT READ THESE.** A screen that greyed its button on
        # a warning would be `BR-CUS-1099`'s refusal restored under another
        # name, which is exactly what the PO ruled against.
        "warnings": tuple(warnings),
    }


# ═══════════════════════════════════════════════════════════════════════════
# §6 · THE WAY BACK — what the two reconnection steps need on screen
# ═══════════════════════════════════════════════════════════════════════════
def reconnect_panel(case: Any, account: Any) -> dict[str, Any]:
    """`mark_reconnecting` / `restore_service`, previewed — and the money.

    ⚠ **NOT DRAWN ANYWHERE.** The Accounts blueprint's disconnect section
    (p135–p144 of `02 Accounts Menu Blueprint.pdf`, read as images per B14 rule
    42) draws the five wizard steps, the register, the case record and its two
    dialogs — and **no reconnection screen and no visit screen at all.** Its own
    `Why Blocked` note says as much: *"what happens when a crew attends and does
    not cut … those are rulings, not code."* The register DOES draw the states
    (`CUT, AWAITING RECONNECT`, a `Reconnections` filter chip and a
    `RECONNECTIONS` KPI), so the shape the drawing commits to is the one built:
    the case record carries the act, exactly where `Mark as cut` already is.
    Reported rather than claimed as drawn (rule 41's honest half).

    ⚠ **THE FIGURE IS `reconnection_terms`' AND IS NOT RE-DERIVED HERE.** That
    read is what the tier-3 letter prints and what the wizard's step 4 quotes,
    so the price a customer was told and the price this screen shows cannot
    disagree (`BR-BIL-007`). ⚠ And `to_clear` is the QUOTE while `balance` is
    what the GATE reads — `disconnects.reconnection_readiness` carries the
    second, so a clerk reading *"$0.00 to clear"* beside a refusal knows which
    number refused them.
    """
    readiness = disconnects.reconnection_readiness(account.id, case=case)
    terms = disconnects.reconnection_terms(account.id, case=case)
    return {
        "step": readiness["step"],
        "ready": readiness["ready"],
        "refusal": readiness["refusal"],
        "blockers": list(readiness["blockers"]),
        # `BR-CUS-1097` — what is still owed, STATED. It was a blocker until
        # 2026-09-25 and is a warning now; `ready` does not read it.
        "warnings": list(readiness["warnings"]),
        "paid_absence": readiness["paid_absence"],
        "balance": readiness["balance"],
        "status_before_cut": readiness["status_before_cut"],
        # `DEF-CUS-10668` — what a restoration writes: Active.
        "status_restored_to": readiness["status_restored_to"],
        "status_absence": readiness["status_absence"],
        # p143's own `To clear before reconnection`, from the one read that owns
        # it. ⚠ Lane DFX-1 is correcting a double-count in `_to_clear`; this
        # screen shows whatever that read answers and computes nothing of its
        # own, which is why the correction reaches it for free.
        "to_clear": terms["to_clear"],
        "fee": terms["fee"],
        "fee_absence": terms["fee_absence"],
        "deposit": terms["deposit"],
        # `DSC-02.4`'s consequence, carried rather than restated: an APPLIED
        # deposit leaves nothing held, so a new one is required to reconnect —
        # and nothing in this product collects it.
        "cut_on": str(case.cut_on) if case.cut_on else None,
        "reconnected_on": str(case.reconnected_on) if case.reconnected_on else None,
        "visit": dict(disconnects.VISIT_NOT_SCHEDULED),
    }


# ═══════════════════════════════════════════════════════════════════════════
# §7 · THE CREW ATTENDED AND DID NOT CUT — the four outcomes and their moves
# ═══════════════════════════════════════════════════════════════════════════
#: Where each outcome sends the case, as a CODE the screen translates. The
#: mapping is `disconnect_visits`' and is DERIVED from it rather than re-typed,
#: so a fifth outcome cannot reach this screen with no destination beside it —
#: the eleventh-service failure, which is silent (the row exists, the API serves
#: it, every test passes, and the screen never offers it).
MOVE_CLEARS_THE_DATE = "clears_the_cut_date"
MOVE_STOPS_THE_LADDER = "stops_the_ladder"


def visit_panel(case: Any) -> dict[str, Any]:
    """p143 draws no such control. `BR-CUS-1083` is why there is one.

    PO ruling 2026-09-20: *"The register reflects reality. Today a failed visit
    is invisible and the case looks untouched."*

    Every outcome carries WHERE IT SENDS THE CASE, because that is the half a
    clerk has to know before pressing — three of the four take the case off the
    cut calendar and one stops the ladder, and a dialog that listed four words
    with no consequences would be asking somebody to guess.
    """
    from apps.customers import disconnect_visits

    return {
        "outcomes": [
            {
                "code": code,
                "move": (
                    MOVE_CLEARS_THE_DATE
                    if code in disconnect_visits.OUTCOMES_THAT_CLEAR_THE_DATE
                    else MOVE_STOPS_THE_LADDER
                ),
            }
            for code in disconnect_visits.VISIT_OUTCOMES
        ],
        # ⛔ **A VISIT IS RECORDED ON A SCHEDULED CASE AND NOWHERE ELSE** — the
        # service refuses the rest by name, and the screen must not offer a
        # control that will always be refused (BR-SHL-025).
        "can_record": getattr(case, "state", None) == disconnects.STATE_SCHEDULED,
        "refusal": (
            None
            if getattr(case, "state", None) == disconnects.STATE_SCHEDULED
            else {
                "code": "visit_not_scheduled",
                "br_ref": "BR-CUS-1083 · B18 §5.8.3",
                "detail": (
                    f"this case is {getattr(case, 'state', None)!r}, and a crew attends a case "
                    "that is SCHEDULED for a cut. A case with no date on the calendar had "
                    "nobody at its meter."
                ),
            }
        ),
        "recorded": list(disconnect_visits.visits_for(case)),
        "follow_up": dict(disconnect_visits.VISIT_RAISES_NO_FOLLOW_UP),
        "money": dict(disconnect_visits.PAID_AT_DOOR_TAKES_NO_MONEY),
    }


#: ⛔ Work answered, and this case raised no field job — the wizard's *Who goes*
#: was not *Work order* for any service, or the case predates 2.520.2.
NO_WORK_ORDER_RAISED: dict[str, Any] = {
    "code": "no_work_order_raised",
    "br_ref": "BR-CUS-1098",
    "detail": "This case raised no field job.",
}

#: ⛔ Work is not installed, so whether a crew was sent is not answerable here.
WORK_ORDERS_NOT_READABLE: dict[str, Any] = {
    "code": "work_orders_not_readable_from_customers",
    "br_ref": "B1 · CR-070",
    "detail": "Which field jobs this case raised is a `work` fact, and Work publishes no read.",
}


def work_orders_panel(case: Any) -> dict[str, Any]:
    """**The cut visits this case raised — `DEF-CUS-9696`.**

    Since `DEF-CUS-9631` (2.520.2) the wizard's *Who goes: Work order* rows
    become jobs with `source = disconnect` and `source_ref = the case number`,
    and this record read none of them, so a clerk on the case could not see
    the visit or whether the crew had been. Read through
    `seams.flow_work_visits` by the CASE NUMBER — the same read the move and
    transfer records use — so `raised · done · accepted` and each job's own
    `WO-` number and state come from Work, and nothing is derived here.
    """
    from apps.customers import seams

    if not getattr(case, "case_no", None):
        return _fact(None, NO_WORK_ORDER_RAISED)
    answer = seams.flow_work_visits(flow_kind="disconnect", source_ref=case.case_no)
    if answer is None:
        return _fact(None, WORK_ORDERS_NOT_READABLE)
    if not answer.get("raised"):
        return _fact(None, NO_WORK_ORDER_RAISED)
    return _fact(answer)


def reconnect_work_orders_panel(case: Any) -> dict[str, Any] | None:
    """**The reconnect REQUEST's jobs — `DEF-CUS-10657`, PO C1 2026-10-29.**

    *"Restore = Reconnect request"*: once a clerk confirms *Put service back
    on* the case is `reconnecting` and the request's status is the reconnect
    jobs it raised — `raised · done · accepted` and each `WO-` number — read
    through `seams.flow_work_visits` by the CASE NUMBER exactly as
    `work_orders_panel` reads the cut visit (`from_flows` stamps the same
    `source_ref`). `None` on a case that was never asked to come back: a
    *none yet* line on every notified or scheduled case is a fact with no
    reader (B14 rule 32).
    """
    from apps.customers import seams

    if case.state not in (disconnects.STATE_RECONNECTING, disconnects.STATE_RESTORED):
        return None
    if not getattr(case, "case_no", None):
        return _fact(None, NO_WORK_ORDER_RAISED)
    answer = seams.flow_work_visits(flow_kind="reconnect", source_ref=case.case_no)
    if answer is None:
        return _fact(None, WORK_ORDERS_NOT_READABLE)
    if not answer.get("raised"):
        return _fact(None, NO_WORK_ORDER_RAISED)
    return _fact(answer)


# ═══════════════════════════════════════════════════════════════════════════
# THE RECORD
# ═══════════════════════════════════════════════════════════════════════════
def closing_read_meters(case: Any, account: Any) -> list[dict[str, Any]]:
    """**THE METERS `Mark as cut` TAKES A CLOSING READING FOR — `DEF-CUS-10166`.**

    PO ruling 2026-10-17 (decision log *"WHERE A USER ENTERS A METER
    READING"*, gap 3): *Disconnect → Mark as cut — closing reading + read date
    + Fetch (server already accepts `final_reads`); no estimate.*

    The rows are move-in step 1's own (`move_in_unit_read.services_and_meters`
    — one reader of *which assets on a unit are read*, `DEF-CUS-9753`), cut
    down to READ devices on a service this case cuts. A meter whose service
    point names no offered service is kept: dropping it would hide a register
    the crew may well have read. Each row carries the meter NUMBER (never an
    id, B14 rule 31), its unit (hard rule 3) and its last reading, whose date
    is the lower bound the dialog and `_refuse_bad_read_dates` both hold.

    `[]` for an account with no unit or no read devices — the dialog then
    shows no reading table and the cut posts no reading, exactly as before.
    """
    if getattr(account, "unit_id", None) is None:
        return []
    from apps.customers import move_in_unit_read

    answer = move_in_unit_read.services_and_meters(account.unit_id)
    cut = set(case.services_cut or ())

    def _walk(rows: list[dict[str, Any]], service: str | None):
        for row in rows:
            yield service, row
            yield from _walk(row.get("children") or [], service)

    pairs = [pair for block in answer.get("services") or [] for pair in _walk(block["meters"], block["service"])]
    pairs += list(_walk(answer.get("unplaced") or [], None))
    out: list[dict[str, Any]] = []
    for service, row in pairs:
        if not row.get("needs_opening_read") or not row.get("asset_no"):
            continue
        if service is not None and cut and service not in cut:
            continue
        last = row.get("last_read") or None
        out.append(
            {
                "asset_no": row["asset_no"],
                "service": service,
                "kind": row.get("kind"),
                "unit": row.get("unit") or (last or {}).get("unit"),
                "last_read": None
                if last is None
                else {"value": last.get("value"), "read_at": last.get("read_at")},
            }
        )
    return out


def record_detail(ref: str, *, as_of: date | None = None) -> dict[str, Any]:
    """One disconnect case, as `/disconnects/{ref}` draws it — p143, in order.

    ⚠ **THE REFERENCE IS THE CASE NUMBER, NEVER THE UUID** (B14 rule 31), and
    the id is served under `account_id` only so the three ACTIONS have an
    address to post to — it is never a field's visible value.
    """
    day = _as_of(as_of)
    case = _case_by_reference(ref)
    if case is None:
        # A reference this tenant does not hold is a 404 and never a 403 (HR-1):
        # the boundary must not confirm that the row exists somewhere else.
        raise errors.deny_as_not_found("BR-CUS-039")
    account = _account_of(case)
    if account is None:  # pragma: no cover — a PROTECTed FK cannot dangle
        raise errors.deny_as_not_found("BR-CUS-039")

    from apps.customers import selectors

    return {
        # ── the head ────────────────────────────────────────────────────────
        "case_no": _fact(case.case_no, disconnects.CASE_NUMBER_UNAVAILABLE),
        "customer_name": _fact(
            selectors.primary_contact_name(account),
            {
                "code": "no_primary_contact",
                "br_ref": "BR-CUS-054",
                "detail": "this account records no primary contact to name.",
            },
        ),
        "address": _fact(
            _premise_line(account),
            {
                "code": "premises_not_readable",
                "br_ref": "BR-MET-1161",
                "detail": (
                    "an address is stored on `premises` and this account's unit does not resolve "
                    "to one. Nothing on this record declares an address of its own."
                ),
            },
        ),
        "customer_class": _fact(_customer_class(account), NO_CUSTOMER_CLASS),
        # A CODE, translated by the screen; B14 rule 31 keeps it off the page.
        #
        # ⚠ **`displayed_state`, NOT `case.state` — `DEF-CUS-6755`.** A case with
        # a protection in force read `At notice` here while the same record's
        # protections panel showed the hold, so one screen said two things at
        # once. The derivation is `disconnects`', not this module's, so the
        # register and this record cannot drift apart.
        "state": _fact(disconnects.displayed_state(case, as_of=day)),
        # The STORED state, for anything that must reason about the case rather
        # than describe it. Served under its own name so a reader can never
        # mistake one for the other.
        "state_stored": _fact(case.state),
        "tier": _fact(disconnects.ladder_tier_of(case), NO_TIER_YET),
        "cut_date": _fact(
            case.cut_scheduled_for.isoformat() if case.cut_scheduled_for else None,
            NO_CUT_SCHEDULED,
        ),
        # ── the five sections, p143's own order ─────────────────────────────
        "the_case": _the_case(case, account),
        "notices": _notices(case),
        "protections": _protections(account, as_of=day),
        "what_a_cut_would_do": _what_a_cut_would_do(case, account),
        # `DEF-CUS-9696` — the jobs the wizard raised for this case.
        "work_orders": work_orders_panel(case),
        # `DEF-CUS-10657` — the reconnect request's jobs; `None` before one.
        "reconnect_work_orders": reconnect_work_orders_panel(case),
        # ── the three actions ───────────────────────────────────────────────
        "actions": {
            # ⚠ **STATE-DEPENDENT SINCE 2026-09-20, AND IT USED TO BE THE FLAT
            # THREE.** `available_actions` is why; the short version is that a
            # `Mark as cut` on a case cut last Tuesday can never become
            # pressable and a permanently dead control over a live screen is
            # the mirror of hard-won law 2.
            # `DEF-CUS-6063` — the account goes in because ONE of the answers is
            # "this cut never finished", and that is written on the account.
            "available": list(available_actions(case, account)),
            # NOT a visible value — the address the two write actions post to.
            "account_id": str(account.id),
            "hold": {
                # p144's drawn order, not the writer's — see `DRAWN_ORDER`.
                "kinds": _as_drawn(HOLD_KINDS),
                "review_date": dict(HOLD_REVIEW_DATE),
                "dispute_unrecordable": dict(HOLD_DISPUTE_UNRECORDABLE),
                "effects": [dict(row) for row in HOLD_EFFECTS],
                "promises_not_kept": dict(HOLD_PROMISES_NOT_KEPT),
            },
            "mark_as_cut": cut_readiness(case, account, as_of=day),
            # `DEF-CUS-10166` — the meters the cut takes a closing reading for.
            "closing_reads": {"meters": closing_read_meters(case, account)},
            # ── the other half of the job (PO 2026-09-20) ────────────────────
            "reconnect": reconnect_panel(case, account),
            "visit": visit_panel(case),
        },
        "scheduler": dict(disconnects.NO_SCHEDULER),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTE — one GET, and this module exports its own `urlpatterns`
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **ITS OWN MODULE RATHER THAN A VIEW IN `api.py`**, on the precedent
# `communication_api.py` states in its own words: *"`transfer_disconnect_api.py`
# are the precedent: a module may export its own urlpatterns"*, and the reason
# is hard-won law 11 mechanism five — `api.py` is a file several lanes hold at
# once, and a pathspec commit naming it publishes whatever else is sitting in
# it.
#
# ⚠ **IT IS INCLUDED *AFTER* `transfer_disconnect_api`, AND THE ORDER IS
# LOAD-BEARING.** That module mounts `disconnects/schedule`, which
# `disconnects/<str:ref>` would otherwise swallow — Django resolves the FIRST
# match and stops, so a cut scheduled from the wizard would arrive here as a
# case reference spelled *"schedule"*. It is the same trap `api.py` carries a
# comment about on `accounts/master` and the one `DEF-520` cost the premises
# runner. `tests/test_disconnect_record_page.py` resolves BOTH paths through
# `config/urls.py` so a future lane cannot reorder the includes silently.
from django.urls import path  # noqa: E402
from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.response import Response  # noqa: E402

from core.permissions import AdminOrClerk  # noqa: E402
from core.tenancy import require_tenant  # noqa: E402


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def disconnect_record(request: Any, ref: str) -> Response:
    """`GET /disconnects/{ref}` — the DISCONNECT CASE RECORD (blueprint p143).

    The assembly is `record_detail` and this view adds nothing to it: no figure
    is computed here, no absence is defaulted, and **nothing is written.** The
    record's three actions post to endpoints that already exist on
    `transfer_disconnect_api` — this module mounts no write of its own.

    ⚠ **`ref` IS THE CASE NUMBER, NEVER A UUID** (B14 rule 31). `DSC-26-0003` is
    what a clerk reads back to a customer holding a disconnection notice, and
    it is the address the blueprint itself draws.

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`.** Every write this page can reach
    is gated to those two roles by `transfer_disconnect_api`, and a page that
    hands an Executive the whole cut preview and then refuses every button is
    the mismatch that rule exists to prevent.
    """
    require_tenant(request)
    return Response(record_detail(ref, as_of=_query_as_of(request)))


def _query_as_of(request: Any) -> date | None:
    """`?as_of=` — BR-TEN-043's event date as an ARGUMENT, never a wall clock.

    It exists for the same reason `transfer_disconnect_api._as_of` does: this
    page previews a cut, and a preview that can only be taken *today* cannot be
    tested against a scheduled date without moving the machine's clock.
    """
    raw = (request.query_params.get("as_of") or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.disconnectRecord.asOf.not_a_date",
            params={"as_of": raw},
        ) from bad


urlpatterns = [
    path("disconnects/<str:ref>", disconnect_record),
]
