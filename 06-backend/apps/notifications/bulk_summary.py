# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — ONE message per bulk action, whatever the item
#           count)   Screens: shell-chrome (the bell) · S8
# Rules:    BR-NOT-020 (*"for single notification send 1 message and for bulk
#           action also send 1 message only saying nulk action is completed"* —
#           and where the operation had failures the summary must say HOW MANY) ·
#           BR-NOT-019 (in-app is a real channel) · BR-NOT-005 (queue only — this
#           writes a queue row and sends nothing) · CLAUDE.md rule 6 (the queue's
#           five-column unique key is what makes "exactly one" structural)
# Change:   CR-048 wave B task B4 — *"Fire the two staff events in-app — the
#           one channel that already delivers, so this is visibly working from
#           day one"*. The summary now carries its SET-12 EVENT, so the
#           utility's own rule is read on the way to the queue (wave A's join).
# Defect:   DEF-3422 (PO 2026-09-02, *"this says - staff notification - but we
#           dont get any notification"*) — `queue_staff_alert` at the foot of
#           this file is the seam `apps/tenancy/sample_data.py` had resolved by
#           name since C-15 landed and never found.
# Tests:    06-backend/tests/test_cr_009_bulk_one_message.py ·
#           06-backend/tests/test_cr048_b_engine_on.py (CR-048 B4) ·
#           06-backend/tests/test_def3422_bell_staff_alert.py (DEF-3422)
# Impacts:  every module that runs a bulk operation — apps/billing (the bill
#           run), apps/payments (imports, reconciliation), apps/reports — which
#           call this ONE function instead of queueing per item. THREE NAMED
#           entry points now exist for them: `queue_billing_run_summary` and
#           `queue_reconciliation_summary` (both wired by CR-048's follow-up,
#           `apps/billing/run_alert_seam.py` and `apps/payments/run_alert_seam.py`)
#           and `queue_staff_alert`, whose caller is
#           `apps/tenancy/sample_data.completeness_check` through
#           `apps.notifications.services`. · apps/notifications/rule_catalog.py
#           (owns the two event keys; the alert names none — see its own note)
# ───────────────────────────────────────────────────────
"""ONE message per bulk action — the rule, and the only way to obey it.

╔══════════════════════════════════════════════════════════════════════════╗
║  PO, 2026-08-17, verbatim:                                              ║
║  "for single notification send 1 message and for bulk action also send  ║
║   1 message only saying nulk action is completed"                       ║
╚══════════════════════════════════════════════════════════════════════════╝

**WHY THIS IS A PRODUCT RULE AND NOT TIDINESS**, in the CR's own reasoning: the
staff events on SET-12 are precisely the bulk ones — billing run completed and
failed, reconciliation exceptions, the daily digest. Without this rule a bill
run over a thousand accounts is a thousand notifications, so the first thing any
clerk does is switch the whole event off — *"at which point the failure they
needed to see is the one they never get. A notification nobody can bear to leave
on is worse than none."*

────────────────────────────────────────────────────────────────────────────
WHAT MAKES "EXACTLY ONE" STRUCTURAL RATHER THAN A HABIT
────────────────────────────────────────────────────────────────────────────
Three things, and only the third is a promise this file makes:

1. **This function writes ONE queue row per call**, on one channel. It takes
   totals, never a list of items; there is no loop in it and nothing to give it
   one. A caller cannot accidentally use it per-item, because it has no
   per-item shape to call.
2. **`source_id` is the BULK OPERATION's own id** — the bill run, the import
   batch. So the queue's unique key `(tenant, source_type, source_id, channel,
   copy_no)` refuses a SECOND summary for the same operation at the database.
   A retried job, a resumed batch and a double-clicked button all find the row
   already there and write nothing (CLAUDE.md rule 6).
3. **The test that guards it counts.** `test_cr_009_bulk_one_message.py` drives
   a real bulk operation over many items through the real queue-write path and
   asserts `OutboundMessage.objects.count()` grew by exactly one — a COUNT, not
   a shape assertion, because a shape assertion passes on a hundred rows that
   all look right.

────────────────────────────────────────────────────────────────────────────
AND THE OTHER HALF OF THE RULING, WHICH IS THE EASY ONE TO LOSE
────────────────────────────────────────────────────────────────────────────
*"the message states COMPLETION, and where the operation had failures it must
say HOW MANY — a summary that hides a failure count is the same failure as
sending a thousand messages, in the opposite direction."*

So `failed_count` is a REQUIRED argument with no default. Not `= 0`: a default
means a caller that never counted its failures produces a message reading
*"0 failed"* over a run that failed eighty-seven times, and that message is
worse than no message at all. And the template class makes `{failed_count}`
non-removable content, so a utility cannot edit the wording down to *"Bulk
action completed."* either (`catalogs.CATALOGS["staff_bulk_summary"]`).

────────────────────────────────────────────────────────────────────────────
WHO RECEIVES IT — **OQ-261 IS CLOSED (PO 2026-08-17), AND THIS IS THE RULING**
────────────────────────────────────────────────────────────────────────────
⚠ **THIS SECTION WAS REWRITTEN ON 2026-08-18.** It used to say the summary goes
to `actor` *"and to nobody else … the one that needs no ruling"*, and it
promised: *"When OQ-261 closes, the audience here widens from 'the actor' to
whatever the PO names, `deliver_batch` grows a second inbox row per recipient,
and the one-message rule is untouched."* **The PO ruled, verbatim: "the user
who started the action, plus all System Admins for failures"** (2026-08-17,
decision log C-11 → BR-NOT-021), and this file now does exactly what it
promised:

  * a CLEAN run's summary goes to the actor who started it, as before;
  * a run with `failed_count > 0` ALSO reaches every active System Admin —
    one queue row, one mailbox per person (`staff_recipients.py` resolves the
    list, `recipient_snapshot["recipients"]` carries it, `in_app.deliver_batch`
    fans it out). **The one-message rule is untouched: one message, more
    mailboxes.**

⚠ **A JOB WITH NO ACTOR now has an addressee exactly when the ruling gives it
one.** A failed scheduled run reaches the System Admins (the primary address is
the first of them); a CLEAN scheduled run with no signed-in user reaches nobody
under the ruling, and THAT call is still refused — no longer with an open
question's id, but with the ruling itself quoted, because "the ruling names no
recipient for this event" is the honest state and it is findable.

────────────────────────────────────────────────────────────────────────────
NOTHING CALLS THIS YET, AND THAT IS STATED RATHER THAN LEFT TO A GREP
────────────────────────────────────────────────────────────────────────────
The bill run does not call it (BR-NOT-018: three of the staff events have no
trigger anywhere in this codebase — OQ-262 — and *"billing run completed"* is
fired by nobody). This file is the RULE and the mechanism, built with the
channel so that the wiring is one line when the trigger lands, and proven
end-to-end by its own tests and by the operator command
`manage.py send_in_app_demo`. Hard-won law 2 says built is not wired; this
docstring says which of the two this is.

────────────────────────────────────────────────────────────────────────────
⚠ AMENDED 2026-08-29 (CR-048 WAVE B, TASK B4) — TWO THINGS CHANGED, AND THE
PARAGRAPH ABOVE IS STILL TRUE
────────────────────────────────────────────────────────────────────────────
**1 · A summary now names its EVENT, so the rule is read.** CR-048's finding
was that *"the queue never reads the notification rule"* — wave A gave
`services.queue_document` an `event_key` and this file passes one. A System
Admin who switches *Billing run completed* off on Settings → Notifications now
stops receiving it, and the run is TOLD so on `BulkSummary.problems` rather than
the message vanishing. That is CR-048's headline applied to the one channel
where a person can actually watch it happen.

**2 · Two NAMED entry points**, `queue_billing_run_summary` and
`queue_reconciliation_summary`, one per staff event. The generic function still
exists and still defaults `event_key` to None, so every pre-B4 caller means
exactly what it meant.

**And the paragraph above is STILL TRUE: nothing calls either of them yet.** The
bill run lives in `apps/billing` and the reconciliation run in `apps/payments`,
neither of which this lane owns; both resolve this module BY NAME (B1). So the
trigger is now a one-line call from each, against a seam proved end to end —
queued, dispatched, and read out of the bell — by `test_cr048_b_engine_on.py`.
Hard-won law 2 again, and the honest half of *"visibly working from day one"*.

────────────────────────────────────────────────────────────────────────────
⚠ AMENDED 2026-09-03 (DEF-3422) — BOTH PARAGRAPHS ABOVE ARE NOW OUT OF DATE,
AND A THIRD ENTRY POINT EXISTS
────────────────────────────────────────────────────────────────────────────
**1 · "Nothing calls either of them yet" IS NO LONGER TRUE.** CR-048's wave-B
follow-up gave both named entry points their callers —
`apps/billing/run_alert_seam.py` from the bill run's phase 5, and
`apps/payments/run_alert_seam.py` from the reconciliation run. The sentence is
kept above rather than deleted because it is the record of what the file
promised and when the promise came due.

**2 · A THIRD ENTRY POINT, `queue_staff_alert`, is at the foot of this file.**
It is the staff ALERT — *something the platform ran came up short* — and its
caller is `apps/tenancy/sample_data.completeness_check`, which had been
resolving its published name and finding nothing since C-15 landed. The
Product Owner reported the consequence on 2026-09-02: *"this says - staff
notification - but we dont get any notification"*, with the bell reading
*"You're all caught up."* Its own block explains what it adds and what it
deliberately does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction

from apps.notifications import catalogs, models, services, staff_recipients

#: The class every bulk summary renders from. One class, so a utility editing
#: the wording edits it once and every bulk action in the product says the same
#: thing in the same voice.
TEMPLATE_CODE = "staff_bulk_summary"

#: ⚠ RENAMED IN MEANING, 2026-08-18: this used to be the OPEN question's id
#: ("OQ-261"). The question is CLOSED and the constant now carries the ruling,
#: so every refusal that used to cite the question cites its answer.
STAFF_RECIPIENT_RULING = staff_recipients.RULING

# ── CR-048 B4 · the two staff events this file can fire ────────────────────
#: The KEYS ARE `rule_catalog`'s, spelled here once and never invented. Both
#: were checked against `rule_catalog.EVENTS` before being written down and a
#: test re-checks them, because `queue_document` refuses an event key this
#: platform cannot fire and the refusal would land inside a bill run.
#:
#: ⚠ The bill-run event is `billing_run_completed`. It is **not**
#: `billing_run_finished`, which is the name the CR's own task list uses and
#: which no row on SET-12 carries; a lane that took the CR's spelling literally
#: would have queued nothing and been told so at the end of a thousand-account
#: run. The one place the vocabulary lives is `rule_catalog.EVENT_KEYS`.
EVENT_BILLING_RUN = "billing_run_completed"
EVENT_RECONCILIATION = "reconciliation_exceptions"
#: `CR-136-BRC07` `P2.11` — a counter nobody closed. The event is named for the
#: TILL rather than for the sweep, so the row on Settings → Notifications reads
#: as a thing that happened and not as a job that ran.
EVENT_COUNTER_LEFT_OPEN = "counter_left_open"

#: The `operation` phrase each event's summary carries — a clerk's words, not
#: an event key. Fixed per event so two callers of the same event cannot put two
#: different nouns in the same clerk's bell.
OPERATION_BILLING_RUN = "Billing run"
OPERATION_RECONCILIATION = "Payment reconciliation"
#: Renders as *"Counter check finished. 17 processed · 3 failed"* in the bell.
#: The noun is the CHECK and not the tills, because `BULK_SUMMARY_BODY` puts
#: the word "finished" after it and *"Counters left open finished"* is not a
#: sentence anybody would read twice.
OPERATION_COUNTER_WATCH = "Counter check"


class BulkSummaryRefused(Exception):
    """This bulk summary cannot be queued, and here is why — in a clerk's words.

    Not a `core.errors` catalog exception, for `services.QueueWriteRefused`'s
    reason: a bulk operation is the caller, and the right handling of "the
    summary could not be addressed" is to record it against the RUN and let the
    run finish. A failed notification must never fail the work it describes.
    """


@dataclass(frozen=True)
class BulkSummary:
    """What one `queue_bulk_summary` call left on the queue."""

    operation: str
    total_count: int
    failed_count: int
    #: The queue row. One, always.
    message_id: str | None
    #: False when this call found the summary already queued — a retried job, a
    #: resumed batch. The caller is never told it queued a message twice.
    created: bool
    channel: str = models.CHANNEL_IN_APP
    #: CR-048 B4. The SET-12 event this summary was queued AS, or None for a
    #: caller that named none. When it is set, this utility's rule was read and
    #: could have suppressed the message — which is the whole of CR-048's
    #: headline, and the reason the next field exists.
    event_key: str | None = None
    #: What the rule join had to say, `services.QueueWrite.problems` verbatim.
    #: Carried rather than swallowed: a bulk action whose summary was suppressed
    #: by a setting must be able to say so in its own run report, or the settings
    #: screen becomes decoration in the other direction — obeyed, and silent.
    problems: tuple[dict[str, Any], ...] = ()

    @property
    def suppressed_by_rule(self) -> bool:
        """True when the rule left no channel and nothing was queued.

        A value, not an inference from `message_id is None` — a refused address
        also leaves no message and is a different thing entirely.
        """
        return self.message_id is None and bool(self.problems)

    def as_wire(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "total_count": self.total_count,
            "failed_count": self.failed_count,
            "message_id": self.message_id,
            "created": self.created,
            "channel": self.channel,
            "event_key": self.event_key,
            "suppressed_by_rule": self.suppressed_by_rule,
            "problems": [dict(problem) for problem in self.problems],
        }


def queue_bulk_summary(
    *,
    operation: str,
    operation_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any,
    job: str | None = None,
    event_key: str | None = None,
) -> BulkSummary:
    """Queue THE ONE message a bulk action sends. BR-NOT-020.

    `operation` is a human phrase a clerk reads — *"Billing run"*, *"Payment
    import"* — not an event key. `operation_id` is the run's own id and is what
    makes a second call for the same run a no-op at the database.

    `failed_count` has no default; `finished_at` is a PARAMETER and never a
    clock read, because nothing in this module reads a wall clock (BR-TEN-043,
    and G6 greps for it).

    `event_key` names the SET-12 event this summary IS (CR-048 B4). Pass it and
    the utility's own rule is read and obeyed: a System Admin who switches
    *Billing run completed* off on Settings → Notifications stops getting the
    message, which is the whole of CR-048's headline applied to the one channel
    that delivers. **Omit it and nothing changes** — the write is byte-identical
    to what shipped before, which is what keeps `manage.py send_bulk_summary`
    and every pre-B4 test meaning exactly what they meant. Prefer the two named
    entry points below to passing a key by hand.

    Returns the one summary. When the rule leaves no channel the summary is
    returned with `message_id=None` and `suppressed_by_rule` True, carrying the
    reason — it does NOT raise, because a utility switching a setting off is not
    a fault a bulk action should report as one.

    Raises `BulkSummaryRefused` when the RULED audience is empty (BR-NOT-021: a
    clean scheduled run with no signed-in user reaches nobody) — see the module
    docstring's recipient section.
    """
    if total_count < 0 or failed_count < 0:
        raise BulkSummaryRefused(
            f"a bulk summary cannot report {total_count} processed and {failed_count} "
            "failed — neither is a count. A summary that states a nonsense figure is "
            "worse than one that is not sent, because a clerk will believe it."
        )
    if failed_count > total_count:
        raise BulkSummaryRefused(
            f"this summary says {failed_count} of {total_count} failed, which is more "
            "failures than items. The two figures come from the same run and must be "
            "counted from the same set; publishing them as they stand would make a "
            "clerk distrust every summary after it."
        )

    # BR-NOT-021 — the ruled audience: the initiator, plus every active System
    # Admin when the run had failures. `failure` is THIS event's own fact.
    audience = staff_recipients.resolve_staff_recipients(actor=actor, failure=failed_count > 0)
    if audience.primary is None:
        raise BulkSummaryRefused(
            "this bulk action was started by a scheduled job (no signed-in user) and "
            f"reported no failures, so under the ruled recipient policy — {STAFF_RECIPIENT_RULING} "
            "— there is nobody to address the summary to. Nothing is queued and nothing "
            "is guessed; a failed run WOULD reach every active System Admin."
        )

    # The tokens the class whitelists, and nothing else. `catalogs` is asked for
    # the class rather than trusted from memory so that a token removed from the
    # whitelist becomes a save refusal here rather than a `——` in an inbox.
    if catalogs.catalog_for(TEMPLATE_CODE) is None:  # pragma: no cover - defensive
        raise BulkSummaryRefused(
            f"{TEMPLATE_CODE!r} has no template class, so a bulk summary has no token "
            "whitelist to render against and no mandatory failure count to enforce. "
            "Nothing is queued."
        )
    context = {
        "operation": operation,
        "total_count": total_count,
        # Passed even when it is zero — the body prints it either way, and the
        # reason a printed zero beats an omitted sentence is on BULK_SUMMARY_BODY.
        "failed_count": failed_count,
        "finished_at": finished_at,
    }

    write = services.queue_document(
        source_type="bulk_action",
        # The RUN's id. This is the whole of rule 6 for this message class: a
        # retried job finds its own row and writes nothing.
        source_id=operation_id,
        channels=(models.CHANNEL_IN_APP,),
        template=services.TemplatePin(code=TEMPLATE_CODE),
        recipients=(
            services.Recipient(
                channel=models.CHANNEL_IN_APP,
                # The PRIMARY recipient — the initiator, or the first System
                # Admin for an actor-less failure. ONE queue row either way.
                address=audience.primary.user_id,
                snapshot={
                    # BR-TEN-017 — snapshotted at queue time so a delivery record
                    # can still say who it went to after a rename or a leaver.
                    "user_id": audience.primary.user_id,
                    "display_name": audience.primary.display_name,
                    # BR-NOT-021's WHOLE audience: one mailbox row per entry,
                    # written by `in_app.deliver_batch`. One message, more
                    # mailboxes — BR-NOT-020 untouched.
                    "recipients": audience.snapshot_entries(),
                    # An identity-seam break rides the snapshot so the dispatch
                    # home can say WHY a failure reached fewer people than the
                    # ruling names, instead of the shortfall being invisible.
                    "recipient_problems": list(audience.problems),
                },
            ),
        ),
        render_context=context,
        actor=actor,
        job=job or "bulk_action_summary",
        # CR-048 B4 — the rule join. `None` here is the pre-B4 behaviour,
        # deliberately preserved (see the docstring).
        event_key=event_key,
    )

    message = write.messages[0] if write.messages else None
    return BulkSummary(
        operation=operation,
        total_count=total_count,
        failed_count=failed_count,
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        event_key=event_key,
        problems=tuple(write.problems),
    )


# ── CR-048 B4 · the two named entry points ─────────────────────────────────
#
# WHY TWO NAMED FUNCTIONS AND NOT ONE PARAMETER THE CALLER FILLS IN. The bill
# run and the reconciliation run live in `apps/billing` and `apps/payments`,
# which resolve this module BY NAME (B1 — nothing imports notifications). A
# seam a caller reaches by name is a seam whose argument list is a contract
# nobody type-checks: the difference between `billing_run_completed` and the
# CR's own `billing_run_finished` is one word, and the second one refuses at
# run time inside a finished bill run. Naming the two events in FUNCTION NAMES
# moves that from a string a caller types to a symbol they resolve — and if
# they resolve the wrong one, they get `None` and know immediately.
#
# Each takes exactly what a run already holds: its id, its two counts, and the
# moment it finished. None of them reads a clock (BR-TEN-043).


def queue_billing_run_summary(
    *,
    run_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any,
    job: str | None = None,
) -> BulkSummary:
    """ONE in-app message when a bill run finishes. SET-12 `billing_run_completed`.

    *"1,124 processed · 3 failed"* — one row in the bell, whatever the run
    touched. `run_id` is the bill run's own id, which is what makes a retried or
    resumed run find its own message and write nothing (CLAUDE.md rule 6).

    Called by the bill run's own completion step; this module never reaches into
    billing to find out that a run ended.
    """
    return queue_bulk_summary(
        operation=OPERATION_BILLING_RUN,
        operation_id=run_id,
        total_count=total_count,
        failed_count=failed_count,
        finished_at=finished_at,
        actor=actor,
        job=job or "billing_run_summary",
        event_key=EVENT_BILLING_RUN,
    )


def queue_reconciliation_summary(
    *,
    run_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any,
    job: str | None = None,
) -> BulkSummary:
    """ONE in-app message when a reconciliation run finishes. `reconciliation_exceptions`.

    `failed_count` is the EXCEPTION count — the items this run could not match —
    and it is what puts the message in front of every System Admin as well as
    the person who started it (BR-NOT-021). Zero exceptions is still one message
    saying so, because a clerk who sees nothing cannot tell a clean run from a
    run that never happened.
    """
    return queue_bulk_summary(
        operation=OPERATION_RECONCILIATION,
        operation_id=run_id,
        total_count=total_count,
        failed_count=failed_count,
        finished_at=finished_at,
        actor=actor,
        job=job or "reconciliation_summary",
        event_key=EVENT_RECONCILIATION,
    )


def queue_counter_watch_summary(
    *,
    sweep_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any = None,
    job: str | None = None,
) -> BulkSummary:
    """ONE in-app message when tills were left open. SET-12 `counter_left_open`.

    `CR-136-BRC07` `P2.11`. `failed_count` is **how many counters nobody
    closed**; `total_count` is how many were still running when the banking day
    ended, so a supervisor reads *"17 processed · 3 failed"* as *seventeen
    tills were open at midnight and three of them still are*.

    ⚠ **IT TELLS. IT NEVER CLOSES** (PO 2026-09-23 §3.1). Nothing downstream of
    this call writes to `counter_sessions`, and nothing may be added that does:
    the blueprint's midnight auto-close was struck and a System Admin is the
    only one who may seal somebody else's till.

    ⚠ **A CLEAN NIGHT SENDS NOTHING, AND THAT IS THE OPPOSITE CHOICE FROM
    `queue_reconciliation_summary` ABOVE — deliberately.** That one is a run a
    clerk just started, so silence would be indistinguishable from a run that
    never happened. This one is unattended and runs every morning of the year,
    and this module's own header says what a daily message nobody needs does:
    *"the first thing any clerk does is switch the whole event off, at which
    point the failure they needed to see is the one they never get."* It comes
    out of the machinery rather than out of an `if` here — with no signed-in
    user and no failures, `resolve_staff_recipients` has nobody to address and
    `queue_bulk_summary` raises `BulkSummaryRefused`. **A person who runs the
    sweep by hand IS the actor and does get the clean answer they asked for.**

    `sweep_id` is derived from the tenant and the day (see
    `apps/payments/counter_watch.sweep_id`), which is what makes a re-run that
    morning find its own message and write nothing (CLAUDE.md rule 6).
    """
    return queue_bulk_summary(
        operation=OPERATION_COUNTER_WATCH,
        operation_id=sweep_id,
        total_count=total_count,
        failed_count=failed_count,
        finished_at=finished_at,
        actor=actor,
        job=job or "counter_watch_summary",
        event_key=EVENT_COUNTER_LEFT_OPEN,
    )


# ── DEF-3422 · THE STAFF **ALERT** — the seam another module already resolves ─
#
# WHY A THIRD ENTRY POINT AND NOT A THIRD ARGUMENT. `apps/tenancy/sample_data.py`
# has resolved `apps.notifications.services.queue_staff_alert` BY NAME since C-15
# landed (PO 2026-08-17, ruling 15: *"soft: flag on the S62 checklist + alert
# support, tenant still opens"*) and got `None` every time, so its own audit row
# recorded the gap in its own words — *"support_alert: not delivered —
# apps.notifications.services publishes no staff-alert seam"*. The name, the
# argument spelling and the caller were all already decided; what was missing was
# the function. This is that function, and it is deliberately built out of the
# same `queue_bulk_summary` every other staff message goes through rather than
# beside it — DEF-3422's own finding is that a second feed is two answers to
# *"what is in my bell"*, and the one with no writer and no reader is the one
# that went.
#
# THREE THINGS IT ADDS TO `queue_bulk_summary`, and nothing else:
#
#   1. **It never raises.** Every outcome — queued, already queued, refused,
#      broken — comes back as a row the caller carries on its own result. C-15 is
#      SOFT: an alert that could not be sent must never take the tenant down with
#      it, and a `raise` inside a provisioning job would do exactly that.
#   2. **It runs inside its own SAVEPOINT** (CLAUDE.md hard-won law 14). A
#      `try/except` alone is not enough on PostgreSQL: a statement that errors
#      inside a transaction ABORTS it, so the `except` catches an exception whose
#      work is already doomed and the COMMIT fails afterwards with *"current
#      transaction is aborted"*. On SQLite — which `config/settings/test.py`
#      hardcodes — the naive version passes every test on every machine. The
#      caller writes its `sample.seed_incomplete` audit row AFTER this call, and
#      that row is C-15's whole guarantee.
#   3. **It is always a FAILURE under BR-NOT-021**, which is what makes it an
#      alert rather than a summary. `queue_bulk_summary` reads the ruling's second
#      clause off `failed_count > 0`; an alert with nothing wrong is not an alert,
#      so `failed_count` must be at least one and every active System Admin is
#      therefore always on the envelope — including when a scheduled job with no
#      signed-in user raised it, which is the shape the provisioning plant has.
#
# ⚠ **AND ON TD-16, BECAUSE THE NEXT READER WILL ASK.** TD-16 says prose never
# leaves the server: the server sends a message KEY and its params, and the UI
# renders the language. The deleted `core/bell.py` was built to that contract and
# its item carried `summary_key` + `params`. **What this path sends is a RENDERED
# subject and body, and that is not a breach of TD-16 — it is the other side of
# it.** The wording of an in-app message is the UTILITY'S OWN TEMPLATE, edited by
# a System Admin on Settings → Templates, versioned, published and audited
# (`staff_bulk_summary`). It is tenant DATA, not product copy: no locale
# catalogue in `07-frontend/src/i18n/locales/` could hold it, because it does not
# exist until a tenant writes it, and shipping a key for it would mean the
# platform choosing words a utility has already chosen for itself. TD-16 governs
# what the PRODUCT says — labels, refusals, screen text — and every one of those
# on the bell (its title, its empty state, *"Mark all read"*) is still a key.
# This is the same split `template_service` has always drawn, and it is why the
# bell was matched to the inbox rather than the inbox to the bell.
#
# ⚠ **IT NAMES NO SET-12 EVENT, AND THAT IS A DECISION.** `event_key=None` is the
# pre-CR-048-B4 behaviour: no tenant rule is read and none can suppress the
# message. There is no SET-12 row for *"the product's own setup did not finish"*
# and inventing one would make an operational failure switch-off-able by a
# utility that has no reason to know it exists. Both closed vocabularies stay
# closed — BR-SHL-026's five for the bell, `rule_catalog.EVENTS` for the settings
# screen — and this path adds nothing to either.

#: Outcome CODES. A code, because a caller groups on the difference between
#: "sent", "already sent" and "could not"; the `note` beside it is the same fact
#: in a sentence, for the audit row a person reads (G71 — no ids in a payload).
STAFF_ALERT_QUEUED = "staff_alert_queued"
STAFF_ALERT_ALREADY_QUEUED = "staff_alert_already_queued"
STAFF_ALERT_REFUSED = "staff_alert_refused"
STAFF_ALERT_ERROR = "staff_alert_error"

#: The queue row's `job` when the caller names none — one spelling, so a dispatch
#: home can group every staff alert whatever raised it.
STAFF_ALERT_JOB = "staff_alert"

BR_REF_STAFF_ALERT = "BR-NOT-021"


def queue_staff_alert(
    *,
    actor: Any,
    operation: str,
    operation_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    job: str | None = None,
) -> dict[str, Any]:
    """ONE in-app alert when something the platform ran came up short.

    `operation` is the human phrase a clerk reads — *"Sample data setup"* — and
    never an event key, a module name or a reason code (B14 rule 32). The names
    of the parts that did not load belong on the setup screen, which lists them
    in a clerk's words; the bell says what happened and how many.

    `operation_id` is the RUN's own id and is what makes a retried job find its
    own message and write nothing (CLAUDE.md rule 6). `finished_at` is a
    PARAMETER and never a clock read (BR-TEN-043).

    Returns ONE outcome row: `code` for a caller that groups, `note` for the
    audit trail a person reads, `message_id` when there is one. **It raises
    nothing** — see the block above.
    """
    # ⚠ COERCED INSIDE A GUARD, not by a bare `int(...)` on the way into the
    # comparison. A caller that passes None or a string would raise a TypeError
    # from the one function in this module that promises to raise nothing — and
    # it would raise it BEFORE the savepoint below, which is the one place the
    # promise actually matters.
    try:
        failures = int(failed_count)
    except (TypeError, ValueError):
        return {
            "code": STAFF_ALERT_REFUSED,
            "br_ref": BR_REF_STAFF_ALERT,
            "message_id": None,
            "note": (
                "no alert was raised because the number of things that went wrong was "
                "not a number. A figure a clerk cannot trust is worse than no message."
            ),
        }
    if failures < 1:
        return {
            "code": STAFF_ALERT_REFUSED,
            "br_ref": BR_REF_STAFF_ALERT,
            "message_id": None,
            "note": (
                "nothing was reported as having gone wrong, so no alert was raised. "
                "An alert that says nothing failed is one a clerk learns to ignore."
            ),
        }

    try:
        # ⚠ THE SAVEPOINT IS THE POINT — see clause 2 above. Removing it passes
        # the whole suite on SQLite and loses the caller's audit row on
        # PostgreSQL the first time this write is refused.
        with transaction.atomic():
            summary = queue_bulk_summary(
                operation=operation,
                operation_id=operation_id,
                total_count=total_count,
                failed_count=failed_count,
                finished_at=finished_at,
                actor=actor,
                job=job or STAFF_ALERT_JOB,
                # No SET-12 event. See the ⚠ note above.
                event_key=None,
            )
    except BulkSummaryRefused as refusal:
        return {
            "code": STAFF_ALERT_REFUSED,
            "br_ref": BR_REF_STAFF_ALERT,
            "message_id": None,
            "note": f"no alert could be addressed to anybody: {refusal}",
        }
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return {
            "code": STAFF_ALERT_ERROR,
            "br_ref": BR_REF_STAFF_ALERT,
            "message_id": None,
            "note": (
                f"the alert could not be raised: {failure} The work it describes "
                "stands — a failed notification must never fail the thing it reports."
            ),
        }

    if summary.message_id is None:  # pragma: no cover - no rule is read on this path
        return {
            "code": STAFF_ALERT_ERROR,
            "br_ref": BR_REF_STAFF_ALERT,
            "message_id": None,
            "note": "no alert was written and no reason was given for it.",
        }

    created = bool(summary.created)
    return {
        "code": STAFF_ALERT_QUEUED if created else STAFF_ALERT_ALREADY_QUEUED,
        "br_ref": BR_REF_STAFF_ALERT,
        "message_id": summary.message_id,
        "total_count": total_count,
        "failed_count": failed_count,
        "note": (
            "the people who look after this utility have been told; it reaches their "
            "notifications on the next sending round."
            if created
            else "they had already been told, so nothing was written a second time."
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 "PO RULINGS 2026-08-17 (fourth set)" ruling 2 in full · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-020 · apps/notifications/services.py queue_document (the ONE write path) · apps/notifications/catalogs.py staff_bulk_summary)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane) · AMENDED 2026-09-03 by story-coder (DEF-3422 bell lane — `queue_staff_alert`, the seam apps/tenancy/sample_data.py had resolved by name and never found)
# checklist: A✔ B✔ C✔ D=deferred(no HTTP surface — this is called by a bulk operation, never by a request) E=deferred(the message is READ in AppShell.tsx's bell) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr_009_bulk_one_message.py — the COUNT guard was red-proved by replacing the single call with a per-item loop over 200 items and reading `assert 200 == 1`
# exceptions: (0) [CR-048 B4, 2026-08-29] THE SUMMARY NOW NAMES ITS SET-12 EVENT, so the utility's rule is read at queue time (wave A's join) and a switched-off notification is not queued — with the reason carried on `BulkSummary.problems` rather than swallowed. `event_key` defaults to None so every pre-B4 caller, `manage.py send_bulk_summary` included, is byte-identically unaffected. The two named entry points exist because the callers resolve this module BY NAME and a mistyped event key would refuse at the END of a thousand-account run; the CR's own spelling, `billing_run_finished`, is NOT a row on SET-12 and a test asserts that. (1) NOTHING CALLS THIS YET. The bill run fires no staff event (BR-NOT-018, OQ-262) so the rule and its mechanism ship ahead of the trigger, deliberately and stated — hard-won law 2 is about a component nothing passes a prop to, and this is a service with a named future caller, a test that drives it and an operator command that demonstrates it. (2) [AMENDED 2026-08-18] THE AUDIENCE IS THE RULED ONE — OQ-261 CLOSED (PO 2026-08-17, BR-NOT-021): the initiator, plus every active System Admin when `failed_count > 0`, resolved by `staff_recipients.py`; a clean job with no signed-in user is still refused, now citing the ruling rather than the question. (3) `failed_count` HAS NO DEFAULT, on purpose: a defaulted zero is how a run that failed 87 times reports success. (4) [DEF-3422, 2026-09-03] `queue_staff_alert` NAMES NO SET-12 EVENT and therefore reads no tenant rule: there is no SET-12 row for "the product's own setup did not finish", and inventing one would let a utility switch off an operational failure it has no reason to know exists. It NEVER RAISES and it runs in its own SAVEPOINT — C-15 is soft, and on PostgreSQL a bare try/except loses the caller's audit row at COMMIT (law 14). It treats every alert as a FAILURE under BR-NOT-021, which is what puts the System Admins on the envelope even when a scheduled job with no signed-in user raised it. (5) [DEF-3422] EXCEPTION (1) ABOVE IS OUT OF DATE and is kept as the record: CR-048 wave B's follow-up wired both named entry points, and `queue_staff_alert`'s caller is apps/tenancy/sample_data.completeness_check.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
