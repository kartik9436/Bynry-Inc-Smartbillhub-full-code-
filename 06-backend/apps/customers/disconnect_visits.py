# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-20, verbatim: *"The register reflects reality.
#           Today a failed visit is invisible and the case looks untouched."*
#           The four outcomes are the PO's own words — **locked gate, paid at
#           the door, disputed, access refused** — and so is the requirement
#           that *"each must move the case somewhere, not merely annotate it"*.
# Closes:   `OQ-383` (raised 2026-08-25) — *"A CREW ATTENDS, AND DOES NOT CUT —
#           WHAT IS RECORDED?"*. The PO answered the vocabulary half; WHERE each
#           outcome sends the case is derived below and recorded in the decision
#           log rather than put back to them (CLAUDE.md hard-won law 13).
# Rules:    **BR-CUS-1083** (this file) · BR-CUS-039 (the ladder and its stops) ·
#           BR-CUS-100 (proof of service) · CLAUDE.md hard rule 1 (tenant
#           scoping, RLS FORCE) · hard rule 4 (nothing here updates an issued
#           money row — this table is append-only by service) · hard rule 7 (a
#           service action against a customer writes `audit_log`) · hard rule 8
#           (no address column — the premises is walked to)
# Screens:  `/disconnects/{ref}` — the case record's `Record visit` action
#           (`07-frontend/src/features/customers/disconnect/record/RecordVisitDialog.tsx`)
# Tests:    06-backend/tests/test_br_cus_1083_visit_outcomes.py
# Impacts:  apps/customers/disconnects.py (`CREW_OUTCOME_UNRECORDABLE` amended —
#           it was true for 26 days and is not any more) ·
#           apps/customers/disconnect_record.py (`actions.visit`) ·
#           apps/customers/transfer_disconnect_api.py (one route) ·
#           apps/customers/models.py (imports this module at its foot so the
#           model registers) ·
#           apps/customers/migrations/0062_br_cus_1083_disconnect_visits.py
# ───────────────────────────────────────────────────────
"""**A crew attended and did not cut — the row that records it, and the move.**

Until today this product could record a cut that HAPPENED and nothing else. A
crew that drove out, found a padlock and drove back left **no trace at all**:
the case stayed `scheduled` with a date in the past, which reads on every list
as *a cut still pending* and is indistinguishable from a job nobody has got to
yet. `disconnects.CREW_OUTCOME_UNRECORDABLE` has said so, by name, on every cut
payload since 2026-08-25.

═══════════════════════════════════════════════════════════════════════════
1 · THE FOUR OUTCOMES ARE THE PO'S, AND THE SET IS CLOSED
═══════════════════════════════════════════════════════════════════════════
PO, 2026-09-20: **locked gate · paid at the door · disputed · access refused**.

The set is CLOSED and a fifth is refused BY NAME, for the reason
`disconnects.STOP_REASONS` is closed one function over: each of these ends with
a household either keeping or losing supply, and a fifth way to arrive there is
a decision, not a string.

⚠ **`locked_gate` AND `access_refused` ARE NOT ONE OUTCOME WEARING TWO WORDS.**
They make the same move and they are different FACTS: a padlock is an obstacle,
a person standing in the doorway is a refusal, and a regulator reading the
record a year later is asking which one happened. Folding them together would
save a row of a CHECK constraint and destroy the only distinction the record is
being kept for.

═══════════════════════════════════════════════════════════════════════════
2 · SET A STATE, OR DERIVE IT? — SET, AND HERE IS WHY IT IS THE OPPOSITE
    ANSWER TO `on_hold`
═══════════════════════════════════════════════════════════════════════════
This product already has one state that **the schema declares and nothing ever
sets**: `disconnects.STATE_ON_HOLD`. Recording a protection writes an
`AccountProtection` row and touches the case not at all; the register works
`On hold` out on every read (`disconnect_reads.state_cell`), and
`disconnect_record.HOLD_PROMISES_NOT_KEPT` carries the fact that p144's drawn
promise is two-thirds unkept.

**That is the right answer there and the wrong answer here, and the difference
is whether the fact has a CLOCK in it.**

A protection EXPIRES. A medical certificate runs out, a moratorium window
closes, a payment plan is missed — so *is this case held* is a question whose
answer changes while nobody is looking, and a state stored on the case would be
stale from the moment the certificate lapsed with nothing to re-read it. The
register's own words for deriving it are the right ones: *"a RUN cached on a row
outlives the debt."*

**A visit has no clock.** A crew attended on a day and found a padlock; that
never stops being true and never becomes true later. There is nothing to
re-derive, so deriving it would mean asking *what is the most recent visit and
what did it imply* on every read of every list — which is a computation over
history, not a fact about now, and it would give the wrong answer the moment a
clerk re-schedules the cut (the visit is still the latest one; the case is not
where it sent it any more).

**So: the OUTCOME is an immutable row here, and the MOVE is an explicit write on
the case, both in one transaction.** The row is the evidence; the case's own
`state` and `cut_scheduled_for` are where the case IS. Nothing downstream has to
reconstruct one from the other.

⚠ **THE NEXT LANE WILL WANT TO "SIMPLIFY" THIS INTO A DERIVED STATE, BECAUSE
`on_hold` IS RIGHT THERE AS A PRECEDENT.** It is not a precedent. Read the two
paragraphs above before changing it, and if the change still looks right, the
thing to change is the DECISION — in the decision log — and not this file.

═══════════════════════════════════════════════════════════════════════════
3 · WHERE EACH OUTCOME SENDS THE CASE — DERIVED, AND WRITTEN DOWN
═══════════════════════════════════════════════════════════════════════════
The PO ruled *"each must move the case somewhere"*. WHICH somewhere is ours
(law 13: a judgment recorded with its reasoning is the deliverable; a question
is the failure to make one). There are two destinations and four outcomes:

| Outcome | Where the case goes | Why |
|---|---|---|
| `locked_gate` | cut date **cleared**, state → `notice_sent` | The cut is still lawful and still owed; what failed was the visit. The case must stop advertising a date that has passed, and it must be re-schedulable. |
| `access_refused` | the same move | Same operational position, different fact (§1). |
| `paid_at_door` | the same move | The money is **not in this product yet** — a crew holding a cheque is not a posted payment, and `apps/customers` writes no financial table (`BR-CUS-037`). Clearing the date is the most this may honestly claim. When the payment posts, `halt_reason` answers `nothing_owed` by itself and `schedule_cut` refuses — the ladder stops itself, which is the design (`BR-PAY-036`). |
| `disputed` | **`stopped`**, reason `dispute` | This one already has a ruled home. Blueprint p137 draws `Disputed · The customer is contesting the bill` as one of the three reasons a ladder is stopped by hand, and `disconnects.STOP_REASONS` carries it. A doorstep dispute is that dispute. |

⚠ **`notice_sent` AND NOT A FOURTH STATE.** The tempting alternative is a new
`attended_not_cut` state. It was refused: it would need a migration to the
`ck_disconnect_case_state` CHECK, a segment on the register, a chip in eleven
catalogues and a rule about what may leave it — for a position the existing
vocabulary already describes exactly. `notice_sent` means *the ladder has served
notice and no cut is on the calendar*, which is precisely where a failed visit
leaves a case. The TIER is untouched, so a re-schedule resumes rather than
restarts.

⚠ **AND THE DATE IS CLEARED RATHER THAN MOVED.** Nothing here invents a new cut
date: a date is what `schedule_cut` computes from the notice period, and a lane
guessing *"try again next Tuesday"* would be writing a notice period nobody
served.

⚠ **`paid_at_door` DOES NOT WRITE `stopped`, AND THAT IS THE ONE TO ARGUE
WITH.** Stopping needs a reason from a closed set of three and none of them is
*they paid*; widening that set is explicitly *"a fourth way to stop chasing a
real debt"* and needs a ruling. More importantly, a stop on an unposted payment
is a claim this product cannot back — if the cheque bounces, the case has been
closed on the strength of a crew's word. The date is gone, the outcome is on the
record, and the money decides the rest.

═══════════════════════════════════════════════════════════════════════════
4 · ONE TRANSACTION, AUDIT ROW INCLUDED
═══════════════════════════════════════════════════════════════════════════
`commit_cut` is the shape this matches: the visit row, the case move and the
`audit_log` row are one act. Two unwrapped writes leave a case moved with nobody
named as having moved it — which is hard rule 7 resting on an insert never
failing (hard-won law 1: a comment claiming a guarantee is not the guarantee).

⚠ **`disputed` WRITES TWO AUDIT ROWS AND THAT IS CORRECT.** It calls
`disconnects.stop_by_hand`, which writes its own `disconnect.stopped` row inside
a savepoint of this transaction. Two acts happened — a visit was recorded and a
ladder was stopped — and a record that showed one would be short.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import models, transaction
from django.utils import timezone

from core.dbfields import uuid7_pk
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

# ═══════════════════════════════════════════════════════════════════════════
# THE VOCABULARY — §1, CHECK-constrained in the migration
# ═══════════════════════════════════════════════════════════════════════════
#: The meter could not be reached. Nothing about the debt changed.
OUTCOME_LOCKED_GATE = "locked_gate"
#: Somebody refused the crew entry. A person, not a padlock — see §1.
OUTCOME_ACCESS_REFUSED = "access_refused"
#: The customer paid the crew on the doorstep. **The money is not in this
#: product yet** — §3's third row is the whole of why this is not a stop.
OUTCOME_PAID_AT_DOOR = "paid_at_door"
#: The customer contested the bill at the door. §3's fourth row: this one has a
#: ruled home already and goes through `stop_by_hand`.
OUTCOME_DISPUTED = "disputed"
VISIT_OUTCOMES: tuple[str, ...] = (
    OUTCOME_LOCKED_GATE,
    OUTCOME_ACCESS_REFUSED,
    OUTCOME_PAID_AT_DOOR,
    OUTCOME_DISPUTED,
)

#: The outcomes that CLEAR the cut date and return the case to `notice_sent`.
#: Named as a set rather than written as `!= OUTCOME_DISPUTED`, so a fifth
#: outcome cannot silently inherit a move nobody decided for it — the
#: eleventh-service failure, which is silent.
OUTCOMES_THAT_CLEAR_THE_DATE: tuple[str, ...] = (
    OUTCOME_LOCKED_GATE,
    OUTCOME_ACCESS_REFUSED,
    OUTCOME_PAID_AT_DOOR,
)

#: hard rule 7, widened the way `disconnects._audit` widens it: a crew standing
#: at somebody's meter is a service action against a named customer.
AUDIT_VISIT_RECORDED = "disconnect.visit.recorded"

#: ⚠ **WHAT A RECORDED VISIT STILL DOES NOT DO**, carried on every payload so
#: no screen quietly acquires the claim. A visit outcome moves the CASE. It
#: raises no work order, re-dispatches no crew and notifies nobody: `apps/work`
#: owns dispatch and `apps/notifications` owns the letter, and this module
#: writes to neither (`BR-WRK-002`, cross-module writes are forbidden).
VISIT_RAISES_NO_FOLLOW_UP: dict[str, Any] = {
    "code": "visit_outcome_raises_no_follow_up",
    "br_ref": "BR-CUS-1083 · BR-WRK-002",
    "detail": (
        "recording what the crew found moves the case and writes the record. It does not "
        "re-dispatch a crew, raise a work order or send the customer anything — a new visit is "
        "a new cut date, scheduled by a clerk through the wizard, and that is the act that "
        "serves the notice the date is counted from."
    ),
}

#: ⚠ **`paid_at_door` RECORDS NO AMOUNT, ON PURPOSE.** §3's third row: the money
#: is a payments act and `apps/customers` writes no financial table
#: (`BR-CUS-037`). An amount typed here would be a receivable nobody posted,
#: readable on a screen beside a ledger that has never heard of it.
PAID_AT_DOOR_TAKES_NO_MONEY: dict[str, Any] = {
    "code": "paid_at_door_records_no_amount",
    "br_ref": "BR-CUS-1083 · BR-CUS-037 · BR-PAY-036",
    "detail": (
        "what the crew was handed is recorded as a fact and never as money. `apps/customers` "
        "writes no financial table, so an amount here would sit on the case beside a ledger "
        "that never received it. Take the payment on the payments screen; the ladder stops "
        "itself the moment it posts, and the case is already off the cut calendar."
    ),
}


class DisconnectVisit(models.Model):
    """One attendance that did not become a cut.

    ⚠ **MANAGED, and registered by `models.py`'s import at its foot** — the
    pattern `moves.MoveRecord`, `disconnects.DisconnectCase` and
    `move_in_jobs.MoveInJob` all follow: one capability, one module, with each
    column's reasoning beside the column.

    ⛔ **NO AMOUNT, NO CREW, NO ADDRESS.** Each is refused by name: the money is
    `PAID_AT_DOOR_TAKES_NO_MONEY`, WHO attended is `apps/work`'s (this module
    writes nothing there and the actor is in `audit_log`), and an address is
    `premises`' and is walked to (hard rule 8).

    ⚠ **APPEND-ONLY BY SERVICE AND NOT BY CONSTRAINT.** `record_outcome` is the
    only writer and it only ever INSERTs. There is no database trigger stopping
    an UPDATE, and there deliberately is not one: hard rule 4's immutability
    trigger covers issued invoices, invoice lines, payments and journal entries,
    and widening that list is a ruling rather than a lane's choice. What this row
    IS, is a statement about a day that has happened — a correction is a new row
    and the service offers no other door.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The case the crew was sent out on. NOT NULL: a visit with no case is a
    #: visit to nowhere, and every door to this table starts from a case.
    case = models.ForeignKey(
        "customers.DisconnectCase",
        on_delete=models.PROTECT,
        db_column="case_id",
        related_name="+",
    )
    #: The day the crew attended. Given by the clerk and never defaulted to
    #: today: a failed visit is often recorded the following morning, and a date
    #: this module invented would put a crew at a meter on a day nobody was
    #: there.
    visited_on = models.DateField()
    #: One of `VISIT_OUTCOMES` — §1. CHECK-constrained in the migration as well
    #: as guarded in the service, for `ck_disconnect_case_state`'s reason: an
    #: import or a fixture must not be able to introduce a fifth.
    outcome = models.TextField()
    #: The crew's own sentence. The `DisconnectCase.stopped_note` shape and the
    #: same reasoning, one act over: a code says WHAT, a note says what a person
    #: would need to read a year later.
    #:
    #: ⚠ **OPTIONAL. A required note would refuse a recording**, and a refused
    #: recording means the case goes on showing a cut date in the past — which
    #: is the exact defect this table exists to end.
    note = models.TextField(null=True, blank=True)
    #: WHO recorded it. The `MoveInJob.raised_by` posture: NULL only where the
    #: actor carries no `identity.User` row (a system or seeded actor), which is
    #: a real state and is not read as *nobody*.
    recorded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="recorded_by",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # EXPLICIT, as every model defined outside `models.py` in this app
        # declares it.
        app_label = "customers"
        db_table = "disconnect_visits"
        indexes = [
            # The record page asks *"what happened on this case"*, newest first.
            models.Index(fields=["tenant", "case", "-visited_on"], name="ix_dsc_visit_case"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome__in=VISIT_OUTCOMES),
                name="ck_disconnect_visit_outcome",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/repr convenience
        return f"{self.outcome} on {self.visited_on}"


def _payload(visit: DisconnectVisit) -> dict[str, Any]:
    """One visit row, as the record page and the audit trail both need it."""
    return {
        "visit_id": str(visit.pk),
        "case_id": str(visit.case_id),
        "visited_on": str(visit.visited_on),
        "outcome": visit.outcome,
        "note": visit.note,
        "clears_the_cut_date": visit.outcome in OUTCOMES_THAT_CLEAR_THE_DATE,
    }


def visits_for(case: Any) -> tuple[dict[str, Any], ...]:
    """Every attendance recorded on one case, newest first.

    A READ, and the only one. Tenant scoping is the queryset's own
    (`tenant_id`), which every read in this app relies on beside RLS rather
    than instead of it (hard rule 1).
    """
    rows = DisconnectVisit.objects.filter(tenant_id=case.tenant_id, case_id=case.pk).order_by(
        "-visited_on", "-created_at"
    )
    return tuple(_payload(row) for row in rows)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-1083")
def record_outcome(
    actor: Any,
    account_id: Any,
    *,
    on_date: date,
    outcome: str,
    note: str | None = None,
) -> dict[str, Any]:
    """The crew attended and did not cut. Record it, and move the case.

    ONE transaction — §4. The visit row, the case's move and the `audit_log`
    row are one act.

    ⛔ **ONLY A SCHEDULED CASE.** A crew is dispatched against a cut date, so a
    case with no date on the calendar had nobody at its meter. A case already
    `cut` is refused by name too: the supply is off, and a failed visit after
    the fact is a different event this vocabulary does not describe.

    ⚠ **THE OUTCOME IS CHECKED BEFORE THE CASE IS READ.** A fifth outcome is a
    programming error and it should say so before it says anything about the
    account — the order `stop_by_hand` uses, for the same reason.
    """
    from apps.customers import disconnects

    if outcome not in VISIT_OUTCOMES:
        raise disconnects.DisconnectRuleError(
            f"{outcome!r} is not one of the four outcomes a crew may record "
            f"({', '.join(VISIT_OUTCOMES)}). The set is closed: each of these ends with a "
            "household either keeping or losing supply, and a fifth way to arrive there is a "
            "decision rather than a string.",
            code="visit_outcome_unknown",
            br_ref="BR-CUS-1083",
        )
    case = disconnects.open_case_for(account_id)
    if case is None:
        raise disconnects.DisconnectRuleError(
            "there is no open disconnect case on this account to record a visit against.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    if case.state != disconnects.STATE_SCHEDULED:
        raise disconnects.DisconnectRuleError(
            f"this case is {case.state!r}, and a crew attends a case that is SCHEDULED for a "
            "cut. A case with no date on the calendar had nobody at its meter, and a case "
            "already cut has its supply off — an attendance after that is a different event "
            "and this vocabulary does not describe it.",
            code="visit_not_scheduled",
            br_ref="BR-CUS-1083 · B18 §5.8.3",
        )

    # An empty or whitespace note is stored as NULL, never as `""` — the
    # `stopped_note` rule, for its reason: *nobody wrote a note* and *somebody
    # wrote nothing* are the same fact, and two spellings of one fact is how a
    # screen renders a blank line where it meant to render an absence.
    clean_note = str(note).strip() if note and str(note).strip() else None

    with transaction.atomic():
        visit = DisconnectVisit.objects.create(
            tenant_id=case.tenant_id,
            case=case,
            visited_on=on_date,
            outcome=outcome,
            note=clean_note,
            recorded_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        )
        if outcome == OUTCOME_DISPUTED:
            # §3's fourth row — the one outcome with a ruled home already.
            # A SAVEPOINT of this transaction (a nested `atomic()` inside
            # `stop_by_hand`), so the stop and the visit commit together or not
            # at all. It writes its own audit row; §4 says why that is right.
            case_payload = disconnects.stop_by_hand(
                actor,
                account_id,
                on_date=on_date,
                reason=disconnects.STOP_DISPUTE,
                note=clean_note,
            )
        else:
            case.cut_scheduled_for = None
            case.state = disconnects.STATE_NOTICE_SENT
            case.save(update_fields=["cut_scheduled_for", "state", "updated_at"])
            case_payload = disconnects.case_payload(case)
        payload = {
            "visit": _payload(visit),
            "case": case_payload,
            "follow_up": dict(VISIT_RAISES_NO_FOLLOW_UP),
        }
        if outcome == OUTCOME_PAID_AT_DOOR:
            payload["money"] = dict(PAID_AT_DOOR_TAKES_NO_MONEY)
        disconnects._audit(actor, AUDIT_VISIT_RECORDED, account_id, after=payload)
    return payload


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-20 (the four outcomes, verbatim) · `OQ-383` ·
#         B18 §5.8.3 · `DSC-02.3`'s CREW banner ·
#         apps/customers/disconnects.py · 12-governance/02-decision-log.md
# generated: 2026-09-20 by lane DBLD-2
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — the migration is
#         🔒 HUMAN-REVIEW-PENDING with a ledger row)
# exceptions:
#   E1 the four outcomes make TWO moves, not four. The PO ruled *"each must
#      move the case somewhere"* and that is satisfied — every one of them takes
#      the case off the cut calendar — but three of them land in the same place.
#      §3 is the reasoning and the alternative (a fifth state) is refused there
#      by name. REPORTED rather than assumed.
#   E2 nothing re-dispatches a crew (`VISIT_RAISES_NO_FOLLOW_UP`). A new visit
#      is a new cut date, and that is the wizard's act.
#   E3 `paid_at_door` records no amount (`PAID_AT_DOOR_TAKES_NO_MONEY`).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
