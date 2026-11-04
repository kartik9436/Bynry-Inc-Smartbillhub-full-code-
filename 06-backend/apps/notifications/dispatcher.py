# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-002 (the dispatcher: tenant-config batches, provider pacing,
#           retry ×3 with backoff, idempotent dispatch)
#           Screens: S8 · S30
#           US-NOT-003's channel routing lives in `provider_seam.py` and
#           US-NOT-004's config in `dispatch_config.py`, each with its own
#           Trace header — G10 reads a Trace US-ID as "this file ships that
#           story's test cases", and this file ships the dispatcher.
# Rules:    BR-NOT-005 (the dispatcher sends in tenant-config batches at the
#           provider's pace; statuses queued→sent→delivered/failed/bounced,
#           forward-only; retry ×3 with backoff; nothing is ever sent inline) ·
#           BR-BIL-016 (batch default 500, tenant-config; mass sends are never
#           synchronous) · BR-NOT-009 (quiet hours: email/SMS hold outside the
#           tenant's send window; print/PDF generation is EXEMPT) ·
#           BR-NOT-010 (v1 channels are print/email/SMS) · BR-BIL-026 (a
#           dispatch renders the PINNED template version) · BR-TEN-043 (event
#           time is named by the caller, never read from a clock) ·
#           BR-AUD-006 (no PII in the audit trail) · BR-NOT-027 (a sent legal
#           document is FROZEN as the document — the artefact is stored BEFORE
#           the provider is contacted and a row cannot reach `sent` without it;
#           CR-049 task 2, PO 2026-08-30) · CLAUDE.md rule 1 (tenant
#           scoping; RLS FORCE) · rule 6 (idempotency — a replayed or crashed
#           dispatch never sends a message twice) · rule 7 (audited)
# Tests:    06-backend/tests/test_us_not_002_dispatcher.py
# Impacts:  apps/notifications/services.queue_document (writes the rows this
#           drains) · the dispatch home and per-run delivery dashboards, which
#           read the statuses this advances.
#           THEIR US-IDs ARE DELIBERATELY NOT WRITTEN HERE — G10 reads any
#           US-ID inside this block as "this file ships that story's test
#           cases", including on an Impacts line, and it caught exactly that on
#           the first version of this header. The IDs are in the docstring
#           below, where the gate reads prose rather than a claim;
#           `apps/notifications/models.py` records making the same mistake, and
#           `apps/billing/models.py` and `late_fee.py` record it before that.
# ───────────────────────────────────────────────────────
"""The dispatcher — the ONLY thing on this platform that sends a message.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file is where CLAUDE.md rule 6 is
honoured for OUTBOUND traffic (a crashed or replayed cycle must never send a
message twice), it holds the retry and backoff mechanics B2 r12 #17 delegates to
the Eng-Lead, and it enforces BR-NOT-009's send window, which is a compliance
control. AI-authored 2026-08-15 under the PO ruling of 2026-08-09 ("AI will do
it; we will review it later as human"); row in
12-governance/09-human-review-ledger.md.

BR-NOT-005, verbatim: *"A dispatcher service on top sends in tenant-config
batches at the provider's pace (ESP/Twilio cannot absorb platform-speed bulk
generation); statuses queued→sent→delivered/failed/bounced, retry ×3 backoff,
per-run dashboard + re-queue."* This is that service. `services.queue_document`
writes rows; nothing else sends; this drains.

⚠ **THE BOXED PARAGRAPH BELOW IS HISTORY (amended 2026-10-22, law 1).** Email
adapters, the in-app and portal adapters and the template store all exist now;
what still sends nothing is print. And a row whose template cannot be rendered
no longer always *holds*: on email, text and in-app it FAILS with
`template_not_resolved` (`DEF-BIL-10530`, see `_dispatch_channel`).

╔══════════════════════════════════════════════════════════════════════════╗
║  ON THIS DEPLOYMENT THIS DISPATCHER SENDS NOTHING, AND THAT IS NOT A     ║
║  BUG IN IT. TWO THINGS ARE MISSING AND BOTH ARE NAMED ON EVERY RESULT.   ║
╚══════════════════════════════════════════════════════════════════════════╝

1. **No provider adapter exists for ANY channel.** `apps/integrations` holds
   three docstrings and no code, so `provider_seam.channel_route` answers
   `provider_status_unknown` for print as well as for the deferred channels.
   US-NOT-003 TC-1 expects a print batch to reach `sent`; it cannot, and the
   blocker is a missing print-vendor integration.
2. **No template store exists, so nothing renders.** The pin on a row points at
   `notification_templates` version rows, which are US-NOT-006 and are not
   built. `rendering.render_for_dispatch` refuses every row, which is the
   RATIFIED hold — field map N-1: *"dispatch holds safely on missing published
   template; content never invented."*

Both absences travel on `CycleResult.problems`, both are asserted by tests, and
`CycleResult.dispatched` is a value a caller can read rather than an inference.
A queued row today is the correct finished state of a bill run, not a backlog of
failures.

────────────────────────────────────────────────────────────────────────────
IDEMPOTENT DISPATCH (CLAUDE.md rule 6, US-NOT-002 TC-4) — THE CLAIM IS AN
ATOMIC UPDATE, AND A CRASHED BATCH IS NEVER RE-SENT
────────────────────────────────────────────────────────────────────────────
TC-4: *"Dispatcher crashes mid-batch and re-runs → No row sent twice —
idempotent dispatch via batch/status guards; unsent remainder picked up
cleanly."*

A cycle CLAIMS its batch with one UPDATE before any provider is contacted:

    UPDATE outbound_messages
       SET batch_id = <fresh uuid>, attempts = attempts + 1, last_attempt_at = now,
           next_attempt_at = NULL
     WHERE tenant = … AND id IN (…) AND status = 'queued'
       AND (   (batch_id IS NULL AND next_attempt_at IS NULL)   -- never attempted
            OR  next_attempt_at <= now )                        -- a scheduled retry

The UPDATE takes row locks, and after it the rows match NEITHER branch — so a
second dispatcher racing on the same rows claims zero of them and there is no
window in which two cycles both hand the same row to a provider. Only the rows
this UPDATE actually claimed are handed over; `.update()`'s own row count is the
proof, and re-selecting on the fresh `batch_id` is what names them.

**A crash between the claim and the result leaves the row claimed and `queued`,
and it is NEVER selected again.** That is deliberate: after a crash nobody knows
whether the provider accepted the batch, and rule 6 is absolute — *"a replayed
dispatch must send nothing twice."* Re-sending on the chance it did not arrive
would mean posting a second disconnect notice to a customer who already has one.

⚠ **THE COST OF THAT CHOICE, STATED RATHER THAN LEFT TO BE DISCOVERED:** such a
row is stuck. It shows on the dashboard as `queued` with a batch id and an
attempt count, and the operator action that would move it — the re-queue of
US-NOT-013 — is not built, and when it IS built it must clear `batch_id` for
this to be recoverable. Reported in the lane report; the alternative was a
silent double-send.

────────────────────────────────────────────────────────────────────────────
PACING (T5-24, the rule's whole reason to exist)
────────────────────────────────────────────────────────────────────────────
One cycle per channel takes ONE batch of at most the tenant's batch size and
hands it over in ONE call. It does not loop until the queue is empty: draining
10,000 rows is 20 cycles of 500, run by the scheduler at whatever spacing the
tenant's provider tolerates, and a loop here would be the platform-speed blast
BR-NOT-005 exists to forbid. T5-24 step 2 measures exactly this — *"Max messages
per provider hand-off ≤ 500"*.

The batch size is re-read at the top of every cycle (T7-17 step 4, *"config read
per dispatch cycle"*), and a batch already handed over is a fact: nothing here
claws one back or re-cuts it when the config changes mid-drain (step 3).

────────────────────────────────────────────────────────────────────────────
THE FREEZE (BR-NOT-027, CR-049 task 2) — STORED BEFORE SENT, NO EXCEPTIONS
────────────────────────────────────────────────────────────────────────────
PO, 2026-08-30: *"any legal document when send - it is freezed … actual leter
and PDF should be freeze … otherwie everytime we reproduce it using data in
table, we might change something about it and that is not correct"*.

So this dispatcher renders, then **FREEZES what it is about to send**
(`frozen_documents.freeze_for_dispatch`), and only then hands the batch over.
A row that could not be frozen is RELEASED and never reaches a provider, and
`_mark_sent` takes the freeze answer as a required argument so no future call
site can advance a row without one.

**It is a precondition and not a cutover**, which is a choice available exactly
once: `provider_seam.PLATFORM_ADAPTERS` carries `in_app` and nothing else, so
print, email and SMS have reached no customer and there is no earlier era to
grandfather. The option expires at go-live.

⚠ **THE PIN IS NOT SUPERSEDED.** BR-BIL-026's `template_version` on the row is
now PROVENANCE — *which authored wording was in force* — and the frozen artefact
is *what the customer read*. **They answer different questions and a reader who
collapses them will delete one.**

Two channels do not freeze and both are ruled: `in_app` (PO — *"we dont have to
worry about in-app message those are mostly FYI"*, and `in_app_messages.body`
already stores its render) and a `test` source row (a rehearsal addressed to the
signed-in user, BR-NOT-024). A template class the PO's scope table does not name
HOLDS on `OQ-1164` rather than being assigned a kind.

────────────────────────────────────────────────────────────────────────────
RETRY ×3 WITH BACKOFF — AND WHAT IS **NOT** A RETRY
────────────────────────────────────────────────────────────────────────────
`attempts` counts PROVIDER attempts. After the third failed attempt the row
rests `failed` with the provider's error stored (US-NOT-002 TC-3), where the
dashboard's re-queue can pick it up. The backoff SCHEDULE
(`BACKOFF_MINUTES`) is engineering mechanics that B2 r12 #17 delegates to the
Eng-Lead — no signed document names an interval, and this one is stated here so
it is reviewable rather than buried.

Three things are deliberately NOT provider attempts and never touch the counter:

  * **A channel that is deferred or unconnected** — nothing was attempted.
  * **A row that could not be RENDERED** — a missing published template is a
    configuration gap, not a provider failure; burning its three attempts would
    move it to `failed` and put a template problem on a delivery dashboard as
    an outage.
  * **A row held by quiet hours** — T5-23 step 3 says it in as many words:
    *"retry counters untouched (nothing was attempted)"*.

────────────────────────────────────────────────────────────────────────────
QUIET HOURS (BR-NOT-009) — AND WHY THE CLOCK REFUSES RATHER THAN DEFAULTS
────────────────────────────────────────────────────────────────────────────
Email and SMS may only leave inside the tenant's send window, evaluated in the
TENANT's timezone. Print/PDF is exempt (BR-NOT-009, T5-23 step 2). The window in
force at DISPATCH time governs — T5-23 step 6 and T7-16 both make a window edit
future-dispatch-only, never a retroactive send and never a re-hold of anything
already sent — which falls out of reading the config every cycle.

If the tenant's timezone cannot be read, `tenancy_seam.tenant_timezone` raises
and the non-exempt channels are HELD for the cycle with that message. It does
not fall back to UTC: a utility in America/Chicago evaluated against UTC has a
window that is 03:00–16:00 on its own clock, so it would refuse a 09:00 Tuesday
send and cheerfully text at 22:00 — T5-23's incident, produced by a fallback.

────────────────────────────────────────────────────────────────────────────
WHAT THIS FILE DOES NOT DO
────────────────────────────────────────────────────────────────────────────
* **It never sets `delivered` or `bounced`.** Those are the PROVIDER's facts,
  arriving by webhook (US-NOT-014, *"bounced status (W6) — webhook-driven"*).
  A dispatcher that marked its own sends `delivered` would be reporting a
  confirmation nobody gave.
* **It never resets a status.** The re-queue ACTION (US-NOT-013 / US-BIL-024) is
  the only reset, and it is not built. `forward_only` below is the guard that
  makes US-NOT-002 TC-5 real from this side.
* **It does not skip HELD rows, because no held marker exists.** BR-PAY-018's
  paper suppression and its held flag are US-NOT-014's columns; the absence is
  reported on every cycle rather than implied to be handled (hard-won law 1).
* **It does not decide what happens to a row with no recipient address.** Such
  rows are never selected — there is nowhere to send them — and they are counted
  and reported. Whether they should rest, fail, or wait for an address is
  **OQ-206's sibling OQ-208**, minted rather than answered; migration
  `0001_w3_outbound_queue` named this gap as US-NOT-002's when the table landed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.db import models as dj_models
from django.db import transaction
from django.db.models import F, Q

from apps.notifications import (
    delivery_ops,
    dispatch_config,
    frozen_documents,
    models,
    provider_seam,
    rendering,
    suppression,
    tenancy_seam,
)
from core import audit, errors
from core import tenancy as core_tenancy

#: BR-NOT-005, verbatim: *"retry ×3 backoff"*. Three PROVIDER attempts, then the
#: row rests `failed` with the error stored (US-NOT-002 TC-3).
MAX_ATTEMPTS = 3

#: The backoff schedule, in minutes, indexed by the attempt that just failed.
#: ⚠ NO SIGNED DOCUMENT NAMES AN INTERVAL. BR-NOT-005 says "backoff" and B2 r12
#: #17 delegates the dispatcher's mechanics to the Eng-Lead, so this is
#: engineering vocabulary and is stated as data rather than buried in a formula
#: — a reviewer can change three numbers. Exponential-ish and deliberately
#: unhurried: the failure this schedule is for is a provider rate-limiting us
#: (T5-24 step 3's 429), and retrying a rate-limited provider quickly is how a
#: backoff becomes a second burst.
BACKOFF_MINUTES: tuple[int, ...] = (5, 15, 45)

#: BR-NOT-009: *"print/PDF generation exempt"*. A letter is put in an envelope
#: at 23:00 and posted in the morning; a text message arrives at 23:00.
#:
#: ⚠ IN-APP IS EXEMPT TOO, ADDED 2026-08-17 (CR-009 in-app lane), and this is a
#: reading of BR-NOT-009 rather than a quotation of it — so it is written down
#: here and in the decision log rather than assumed. The rule's own words are
#: *"tenant-config send window for EMAIL/SMS"*, and its stated harm (T5-23) is
#: *"a utility texting late-payment reminders at 23:00"* — a message that wakes
#: somebody up. An in-app message wakes nobody: it is a number on a bell that a
#: staff member sees when they next open the product, and it goes to the
#: UTILITY'S OWN STAFF rather than to a customer. Holding it overnight would
#: mean a billing run that failed at 22:00 is reported at 08:00 the next
#: morning, which is the one thing this channel exists to prevent.
#: ⚠ THE CUSTOMER PORTAL IS EXEMPT TOO, ADDED 2026-09-07 (`CR-084`), and it is
#: the same reading of BR-NOT-009 the in-app clause above records rather than a
#: new rule. The rule's words are *"tenant-config send window for EMAIL/SMS"*
#: and its stated harm (T5-23) is *"a utility texting late-payment reminders at
#: 23:00"* — a message that wakes somebody up. **Publishing a document to a
#: portal wakes nobody**: nothing rings, nothing arrives, and the customer sees
#: it when they next choose to sign in — which is what a printed bill sitting in
#: a mail room overnight already does, and print has been exempt from the first
#: day for exactly that reason. Holding a portal copy until 08:00 would delay
#: the one route on a bill this platform can actually complete, to protect a
#: customer from an interruption that does not happen.
QUIET_HOURS_EXEMPT_CHANNELS: frozenset[str] = frozenset(
    {models.CHANNEL_PRINT, models.CHANNEL_IN_APP, models.CHANNEL_PORTAL}
)

#: The forward-only lifecycle (BR-NOT-005, r10 #8). Explicit pairs rather than
#: an ordering, because `failed` and `bounced` are not "further along" than
#: `sent` — they are ends, and only the re-queue ACTION (US-NOT-013) reopens
#: one. US-NOT-002 TC-5: a direct `sent → queued` write is rejected.
#:
#: ⚠ **WIDENED 2026-09-17 FOR THE FOUR NORMALISED PROVIDER OUTCOMES
#: (`DEF-NOT-5626`).** `bounced_hard`, `bounced_soft`, `complained` and
#: `unsubscribed` are reachable from `sent`, like `bounced` before them, because
#: a provider can only report on a message we handed it.
#:
#: ⚠ **AND TWO OF THEM ARE REACHABLE FROM `delivered`, WHICH IS THE ONE PAIR
#: WORTH ARGUING ABOUT.** A spam complaint and an unsubscribe BOTH require the
#: consumer to have received and opened the mail, so the provider reports
#: `delivered` first and the complaint minutes or days later. Refusing that move
#: would mean a complaint on a successfully delivered message has nowhere to go —
#: which is the gap this whole slice exists to close, arriving one layer down.
#:
#: **The delivery fact is NOT destroyed by the move, and that is what makes it
#: lawful under BR-NOT-005.** `sent_at` is stamped when the row leaves and is
#: never cleared, `attempts` is never reset, and the provider's own payload
#: stays in `provider_response`. The status says *the last thing we were told*;
#: the columns say *what happened*. That is the same reading `returned_at`
#: already uses for a paper letter that came back — `delivery_ops.mark_returned`
#: deliberately does NOT move the status, because *"a returned letter WAS sent;
#: overwriting that would destroy the fact an auditor needs."*
#:
#: ⚠ **A BOUNCE IS NOT REACHABLE FROM `delivered` AND THAT IS NOT AN OVERSIGHT.**
#: A mailbox cannot both accept a message and refuse it. A provider reporting
#: both about one message is a provider we have misread, and the refusal is how
#: we find out rather than silently overwriting a delivery with a bounce.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    models.STATUS_QUEUED: frozenset({models.STATUS_SENT, models.STATUS_FAILED}),
    models.STATUS_SENT: frozenset(
        {
            models.STATUS_DELIVERED,
            models.STATUS_FAILED,
            models.STATUS_BOUNCED,
            models.STATUS_BOUNCED_HARD,
            models.STATUS_BOUNCED_SOFT,
            models.STATUS_COMPLAINED,
            models.STATUS_UNSUBSCRIBED,
        }
    ),
    models.STATUS_DELIVERED: frozenset({models.STATUS_COMPLAINED, models.STATUS_UNSUBSCRIBED}),
    models.STATUS_FAILED: frozenset(),
    models.STATUS_BOUNCED: frozenset(),
    models.STATUS_BOUNCED_HARD: frozenset(),
    models.STATUS_BOUNCED_SOFT: frozenset(),
    models.STATUS_COMPLAINED: frozenset(),
    models.STATUS_UNSUBSCRIBED: frozenset(),
}

#: Problem codes carried on a cycle result. CODES, never prose — the dispatch
#: home (US-NOT-013) groups on them and a screen cannot group on a sentence.
CYCLE_QUIET_HOURS_HOLD = "quiet_hours_hold"
CYCLE_CLOCK_UNAVAILABLE = "tenant_clock_unavailable"
CYCLE_RENDER_HELD = "render_held_missing_template"
#: `DEF-BIL-10530` (PO 2026-10-22) — a row on a WORDING channel whose pinned
#: notification template cannot be loaded. It FAILS rather than holds: the pin
#: is frozen at queue time and versions are append-only, so it can never
#: render. `RENDER_FAILED_REASON` is what rests in the row's `last_error`.
CYCLE_RENDER_FAILED = "render_failed_template_not_resolved"
RENDER_FAILED_REASON = "template_not_resolved"
#: The channels that render from the notification template store. Print and the
#: portal carry the DOCUMENT (a bill is pinned to its layout there by design),
#: so a render refusal on them is still released, unchanged.
RENDER_FAILS_CHANNELS: frozenset[str] = frozenset(
    {models.CHANNEL_EMAIL, models.CHANNEL_SMS, models.CHANNEL_IN_APP}
)
CYCLE_NO_RECIPIENT = "row_has_no_recipient_address"
#: ⚠ SUPERSEDED 2026-08-15 — the held marker EXISTS now (US-NOT-014, migration
#: 0007). Kept as a name so a reader grepping for the old code finds this line
#: and the replacement rather than nothing: the cycle now reports
#: `CYCLE_HELD_ROWS_SKIPPED` with a COUNT of what it actually held back.
CYCLE_HELD_MARKER_ABSENT = "held_marker_not_implemented"
CYCLE_HELD_ROWS_SKIPPED = "held_rows_skipped"
CYCLE_PROVIDER_SILENT = "provider_did_not_answer_for_row"
CYCLE_ADAPTER_RAISED = "provider_call_raised"
#: ⚠ THE FREEZE'S REFUSALS ARE **NOT** RESPELLED HERE (CR-049 task 2,
#: 2026-08-30). A row that could not be frozen is held exactly as a row that
#: could not be rendered is, and its problem travels UNCHANGED from
#: `frozen_documents` — `document_kind_not_ruled`,
#: `frozen_artefact_differs_from_todays_render` and their siblings, each already
#: carrying `br_ref: BR-NOT-027` and the message id. A second bucket code here
#: would be a second vocabulary for one fact, free to disagree with the first,
#: and the dispatch home would then have to know both.

#: Hard rule 7. `entity.action`, the dotted grammar `core.audit` documents. One
#: row per HAND-OFF, not per message: the per-message evidence is on the queue
#: row itself (`sent_at`, `provider_reference`, `attempts`), and a trail row per
#: message would put 10,000 rows in `audit_log` for one bill run's delivery
#: while saying nothing the queue does not already say.
AUDIT_ACTION = "outbound_batch.dispatched"
AUDIT_ENTITY = "outbound_batch"


class ForwardOnlyViolation(Exception):
    """A status move this lifecycle does not allow (US-NOT-002 TC-5).

    Raised rather than silently ignored: a caller trying to move a `sent` row
    back to `queued` believes it is re-sending something, and letting it fail
    quietly would produce a message the customer never receives and a screen
    that says it was re-queued.
    """


@dataclass(frozen=True)
class BatchOutcome:
    """One hand-off to one channel's provider, as it ended."""

    channel: str
    batch_id: str | None
    claimed: int = 0
    sent: int = 0
    failed: int = 0
    retrying: int = 0
    problems: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CycleResult:
    """What ONE dispatch cycle did for one tenant — and everything it could not.

    `dispatched` is stated as a VALUE and not only in prose, the same discipline
    `services.QueueWrite.dispatched` and `issue.ISSUE_UNAVAILABLE` follow: a
    caller must be able to ASSERT that nothing was sent rather than infer it
    from a docstring (hard-won law 1).
    """

    batch_size: int
    batches: tuple[BatchOutcome, ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def dispatched(self) -> bool:
        return any(batch.sent for batch in self.batches)

    @property
    def sent(self) -> int:
        return sum(batch.sent for batch in self.batches)

    @property
    def claimed(self) -> int:
        return sum(batch.claimed for batch in self.batches)


def forward_only(current: str, target: str) -> None:
    """Guard every status write against the ratified lifecycle (BR-NOT-005).

    The re-queue ACTION (US-NOT-013 / US-BIL-024) is the ONE ratified reset and
    it is not built; when it is, it belongs beside this function as a documented
    exception rather than as a caller that skips the guard.
    """
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ForwardOnlyViolation(
            f"a queue row cannot move {current} → {target}. The lifecycle is forward-only "
            "(BR-NOT-005): queued → sent → delivered | failed | bounced, and the re-queue "
            "ACTION (US-NOT-013) is the only reset there is. A backwards write would let "
            "a message that has already reached a customer be sent to them again."
        )


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    It matters more here than almost anywhere: a dispatcher runs as a JOB, which
    is exactly the caller that runs outside a request and forgets to enter a
    tenant context — and an unscoped drain would hand one utility's letters to
    another utility's provider.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _within_send_window(now: datetime, settings: dispatch_config.DispatchSettings) -> bool:
    """Is this moment inside the tenant's send window, on the TENANT's clock?

    Half-open — `start <= t < end`. T5-23 step 5 makes the opening edge
    inclusive (*"first provider call timestamp ≥ 08:00 tenant time"*) and says
    nothing about the closing edge; half-open is the convention that makes two
    adjacent windows tile without an overlapping second, and the choice is
    stated because it is a choice.

    Raises `TenantClockUnavailable` rather than assuming a zone — see the module
    docstring and `apps/notifications/tenancy_seam.py`.
    """
    local = now.astimezone(tenancy_seam.tenant_timezone()).time()
    return settings.quiet_hours_start <= local < settings.quiet_hours_end


def _selectable(now: datetime) -> Q:
    """The rows a cycle may claim — the predicate the claim UPDATE repeats.

    Written once and used twice on purpose: the SELECT that picks candidates and
    the UPDATE that claims them must agree, and two hand-maintained copies of a
    filter are how a row gets claimed that should not have been.
    """
    return (
        Q(status=models.STATUS_QUEUED)
        # Its scheduled time has come (US-BIL-023 step 6's send-now vs
        # scheduled; US-NOT-002 TC-6: a Sep 1 row is skipped in an Aug 9 cycle).
        & (Q(dispatch_not_before__isnull=True) | Q(dispatch_not_before__lte=now))
        # Never attempted, or a retry whose backoff has elapsed. A row with a
        # batch id and NO next-attempt time is a CRASHED hand-off and is
        # deliberately not here — see the module docstring.
        & (Q(batch_id__isnull=True, next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        # A row with no address has nowhere to go (OQ-208). Never selected,
        # always counted.
        & Q(recipient_address__isnull=False)
        # BR-PAY-018's paper suppression. ⚠ ADDED 2026-08-15 by the CONTENT
        # lane: this predicate used to carry nothing for it and the cycle
        # reported `held_marker_not_implemented` on every run, because the
        # column was US-NOT-014's and unbuilt. It is built now
        # (`apps/notifications/delivery_ops.py`, migration 0007) and the rule
        # lives with the story that owns it rather than being restated here.
        & delivery_ops.selectable_filter()
        # The do-not-send list (DEF-NOT-5632). ⚠ ADDED 2026-09-17. Same shape
        # and same reasoning as the line above it: the rule lives with the story
        # that owns it and this ANDs it in.
        #
        # ⚠ **THIS IS THE THIRD LAYER AND IT SHOULD NEVER BE THE ONE THAT
        # FIRES** — `services.queue_document` holds a new row addressed to a
        # suppressed address and `suppression.suppress` holds the ones already
        # queued, so the `held` predicate above has normally excluded it
        # already. It is here because those two are WRITERS and this is the
        # READER: a writer added later that forgets, or a row written before
        # that slice landed, would otherwise be handed to a provider. Sending
        # again to a hard-bounced mailbox cannot succeed and degrades the
        # sending reputation every utility on this platform shares.
        & suppression.selectable_filter()
    )


def _claim(
    *,
    tenant_id: Any,
    channel: str,
    now: datetime,
    limit: int,
    only_ids: tuple[Any, ...] | None = None,
) -> tuple[str | None, list[models.OutboundMessage], int]:
    """Take at most `limit` rows for this channel, atomically. Rule 6 lives here.

    Returns `(batch_id, rows, candidates_seen)`. The UPDATE's own predicate is
    the guarantee — see the module docstring's SQL. Nothing has been rendered or
    sent at this point; claiming is what stops a second cycle from touching
    these rows, and it happens before any provider is contacted.
    """
    base = models.OutboundMessage.objects.filter(tenant_id=tenant_id, channel=channel)
    if only_ids is not None:
        # `CR-188-BRC10` — `dispatch_messages` names its rows; the SAME
        # `_selectable` predicate still decides whether each may go.
        base = base.filter(pk__in=list(only_ids))
    candidate_ids = list(
        base.filter(_selectable(now))
        # FIFO. The dashboard sorts "failed first, then queued_at" for a HUMAN
        # (S30 capability matrix); a dispatcher sends in the order the messages
        # were made, so a bill queued on the 1st is not overtaken by one queued
        # on the 8th.
        # `CR-188-BRC10` — highest priority first (an account-access email
        # the immediate send could not deliver goes first on the next cycle),
        # then FIFO.
        .order_by("-priority", "created_at", "id").values_list("id", flat=True)[:limit]
    )
    if not candidate_ids:
        return None, [], 0

    batch_id = uuid.uuid4()
    claimed = (
        base.filter(pk__in=candidate_ids)
        .filter(_selectable(now))
        .update(
            batch_id=batch_id,
            attempts=F("attempts") + 1,
            last_attempt_at=now,
            next_attempt_at=None,
        )
    )
    if not claimed:  # pragma: no cover - another cycle won the race
        return None, [], len(candidate_ids)
    rows = list(base.filter(batch_id=batch_id))
    return str(batch_id), rows, len(candidate_ids)


def _mark_sent(
    row: models.OutboundMessage,
    *,
    now: datetime,
    answer: dict[str, Any],
    freeze: frozen_documents.FreezeOutcome | None,
) -> None:
    """queued → sent. The dispatcher's ONLY forward move — see the docstring.

    ⚠ **`freeze` HAS NO DEFAULT, AND THAT IS THE POINT (CR-049 task 2,
    BR-NOT-027).** A row may not reach `sent` unless the artefact the customer
    will read was stored first, and making the freeze answer a REQUIRED argument
    is what stops a future call site from quietly not having one. The ordering in
    `_dispatch_channel` already guarantees it — an unfrozen row is released and
    never handed to a provider — so `require_frozen` is the second guarantee,
    kept because a guarantee enforced only by the order of two statements is one
    refactor away from being gone (hard-won law 1).

    **It is a precondition and not a cutover, and that is only available because
    nothing has ever been sent:** `provider_seam.PLATFORM_ADAPTERS` carries
    `in_app` alone, so print, email and SMS have reached no customer and there is
    no era before this rule to grandfather. The option expires at go-live.
    """
    frozen_documents.require_frozen(row, freeze)
    forward_only(row.status, models.STATUS_SENT)
    row.status = models.STATUS_SENT
    row.sent_at = now
    row.provider_reference = answer.get("provider_reference")
    row.provider_response = answer.get("response")
    row.last_error = None
    row.save(
        update_fields=[
            "status",
            "sent_at",
            "provider_reference",
            "provider_response",
            "last_error",
            "updated_at",
        ]
    )


def _mark_attempt_failed(
    row: models.OutboundMessage,
    *,
    now: datetime,
    error: str,
    response: Any = None,
    retryable: bool = True,
) -> bool:
    """A failed provider attempt. Returns True if the row will be retried.

    `attempts` was already incremented at the claim, so the row's counter is the
    number of attempts MADE. At `MAX_ATTEMPTS` the row rests `failed` with the
    provider error stored (US-NOT-002 TC-3) and the dashboard's re-queue is the
    only thing that moves it again.

    A NON-retryable failure rests immediately: retrying a rejected address three
    times is three rejections and a longer wait before a human sees it.
    """
    exhausted = (not retryable) or row.attempts >= MAX_ATTEMPTS
    row.last_error = error
    row.provider_response = response
    if exhausted:
        forward_only(row.status, models.STATUS_FAILED)
        row.status = models.STATUS_FAILED
        row.next_attempt_at = None
        row.save(
            update_fields=[
                "status",
                "last_error",
                "provider_response",
                "next_attempt_at",
                "updated_at",
            ]
        )
        return False
    index = min(max(row.attempts, 1), len(BACKOFF_MINUTES)) - 1
    row.next_attempt_at = now + timedelta(minutes=BACKOFF_MINUTES[index])
    row.save(update_fields=["last_error", "provider_response", "next_attempt_at", "updated_at"])
    return True


def _audit_batch(outcome: BatchOutcome, *, actor: Any, job: str | None) -> None:
    """Hard rule 7 for a hand-off. NO PII (BR-AUD-006).

    The trail records that a batch of N messages went to a channel's provider,
    which batch it was and how it ended — never an address, a phone number or a
    customer's name. Those are on the rows, for anyone entitled to read them.
    """
    audit.money_action(
        actor,
        AUDIT_ACTION,
        AUDIT_ENTITY,
        str(outcome.batch_id),
        before=None,
        after={
            "channel": outcome.channel,
            "claimed": outcome.claimed,
            "sent": outcome.sent,
            "failed": outcome.failed,
            "retrying": outcome.retrying,
            "job": job if actor is None else None,
        },
    )


def _payload(row: models.OutboundMessage, artifact: rendering.RenderedArtifact) -> dict[str, Any]:
    """One message as the provider adapter receives it (provider_seam's contract).

    The recipient is the SNAPSHOT taken at queue time and is never re-resolved
    (BR-TEN-017): what the envelope says is what the record said when the
    message was made, which is what makes a delivery auditable a year later.
    """
    return {
        "id": str(row.pk),
        "channel": row.channel,
        "address": row.recipient_address,
        "snapshot": row.recipient_snapshot,
        # ⚠ **WHICH DOCUMENT THIS IS, ADDED 2026-09-07 (`CR-084`).** Every
        # adapter before the portal one delivered a RENDER and needed nothing
        # else; the portal publishes a DOCUMENT, so its adapter has to be able
        # to ask whether a copy of that document was kept. Additive and ignored
        # by the two adapters that came first — a payload that named only the
        # render would have forced the portal adapter to re-read the queue row
        # it was just handed, which is the shape a second source of truth takes.
        "source_type": row.source_type,
        "source_id": str(row.source_id),
        "account_id": str(row.account_id) if row.account_id else None,
        "artifact": {
            "subject": artifact.subject,
            "body": artifact.body,
            # CR-199-BRC10 S6 — EMAIL only: the branded HTML document the
            # renderer built from the closed markup. `body` is its plain-text
            # alternative. None on every other channel.
            "html": artifact.html,
            "template_code": artifact.template_code,
            "template_version": artifact.template_version,
            "language": artifact.language,
        },
    }


def _dispatch_channel(
    *,
    tenant_id: Any,
    channel: str,
    now: datetime,
    settings: dispatch_config.DispatchSettings,
    actor: Any,
    job: str | None,
    only_ids: tuple[Any, ...] | None = None,
    honour_quiet_hours: bool = True,
) -> BatchOutcome:
    """ONE hand-off for ONE channel. At most `batch_size` messages, one call.

    `only_ids` / `honour_quiet_hours=False` are `dispatch_messages`' — the
    immediate send of an account-access email (`CR-188-BRC10`), which quiet
    hours do not hold (PO 2026-10-22: *"this should be instant email"*)."""
    problems: list[dict[str, Any]] = []

    route = provider_seam.channel_route(channel, active=settings.channel_is_active(channel))
    if not route.dispatchable:
        # Zero provider calls. US-NOT-003 TC-2/TC-3: rows persist `queued` with
        # the deferred marker and nothing is attempted, so no counter moves.
        return BatchOutcome(channel=channel, batch_id=None, problems=(route.problem,))

    if honour_quiet_hours and channel not in QUIET_HOURS_EXEMPT_CHANNELS:
        try:
            if not _within_send_window(now, settings):
                return BatchOutcome(
                    channel=channel,
                    batch_id=None,
                    problems=(
                        {
                            "code": CYCLE_QUIET_HOURS_HOLD,
                            "br_ref": "BR-NOT-009",
                            "channel": channel,
                            "detail": f"outside this tenant's send window "
                            f"({settings.quiet_hours_start:%H:%M}–"
                            f"{settings.quiet_hours_end:%H:%M} tenant time), so "
                            f"{channel} rows hold. Nothing was attempted and no retry "
                            "counter moved (T5-23 step 3). The window IN FORCE AT "
                            "DISPATCH governs, so an edit tonight changes what leaves "
                            "tomorrow and never re-sends anything.",
                        },
                    ),
                )
        except tenancy_seam.TenantClockUnavailable as unreadable:
            return BatchOutcome(
                channel=channel,
                batch_id=None,
                problems=(
                    {
                        "code": CYCLE_CLOCK_UNAVAILABLE,
                        "br_ref": "BR-NOT-009",
                        "channel": channel,
                        "detail": str(unreadable),
                    },
                ),
            )

    batch_id, rows, candidates = _claim(
        tenant_id=tenant_id,
        channel=channel,
        now=now,
        limit=provider_seam.batch_limit(channel, settings.dispatch_batch_size),  # CR-198-BRC10
        only_ids=only_ids,
    )
    if not rows:
        return BatchOutcome(channel=channel, batch_id=batch_id, problems=tuple(problems))

    # RENDER FIRST, FREEZE SECOND, HAND OVER THIRD. A row that cannot be rendered
    # is released rather than sent: the pin points at a template version that is
    # not stored, and a message with no body is a blank letter. Releasing (rather
    # than failing) keeps it selectable once the template lands — a missing
    # template is configuration, not a provider outage, and must not burn three
    # attempts.
    #
    # ⚠ **THE FREEZE SITS BETWEEN THEM, AND THE ORDER IS THE GUARANTEE (CR-049
    # task 2, BR-NOT-027, PO 2026-08-30).** What the customer will read is stored
    # BEFORE the provider is contacted, so there is no window in which a letter
    # exists in the world and not in this product. Freezing after the hand-off
    # would create the one state the rule cannot describe — a posted letter with
    # no copy of it, and a row that must either be marked `sent` (breaking the
    # guarantee) or left `queued` (lying about a message the customer is
    # holding). A row that cannot be frozen is released exactly like one that
    # cannot be rendered: nothing attempted, no counter moved, the reason
    # reported unchanged.
    #
    # ⚠ **AMENDED 2026-10-22 (`DEF-BIL-10530`, PO: *"mark them failed"*) — ON A
    # WORDING CHANNEL A RENDER REFUSAL IS A FAILURE, NOT A RELEASE.** The
    # paragraph above argued that a missing template is configuration that may
    # yet land, so the row should stay selectable. **That is false for a pinned
    # row:** the pin is stamped at QUEUE time and versions are append-only, so a
    # row whose pinned notification version cannot be loaded today can never be
    # loaded. Releasing it reset its try and put it back every cycle — a bill's
    # email sat at *Waiting · 0 tries* for days with nothing anywhere saying why.
    # So on email, text and in-app (the channels that render from the
    # notification store) the row now rests `failed` with
    # `RENDER_FAILED_REASON` and its try counted. Print and the portal are NOT
    # changed: they carry the DOCUMENT, a bill's row there is pinned to its
    # layout by design, and they are still released exactly as before — as is
    # a freeze refusal on any channel. Those releases are left as they were on
    # purpose: they show *Waiting* with nothing in *What went wrong*, which is
    # what a print or portal copy of a bill has always shown, and changing what
    # the portal shows was not this defect.
    payloads: list[dict[str, Any]] = []
    renderable: list[models.OutboundMessage] = []
    unrenderable: list[models.OutboundMessage] = []
    released: list[models.OutboundMessage] = []
    freezes: dict[Any, frozen_documents.FreezeOutcome] = {}
    for row in rows:
        try:
            artifact = rendering.render_for_dispatch(row)
        except rendering.RenderRefused as held:
            fails = channel in RENDER_FAILS_CHANNELS
            problems.append(
                {
                    "code": CYCLE_RENDER_FAILED if fails else CYCLE_RENDER_HELD,
                    "br_ref": "BR-BIL-026",
                    "channel": channel,
                    "message_id": str(row.pk),
                    "detail": str(held),
                }
            )
            if fails:
                unrenderable.append(row)
            else:
                released.append(row)
            continue
        freeze = frozen_documents.freeze_for_dispatch(
            row, artifact, moment=now, actor=actor, job=job
        )
        if not freeze.may_send:
            problems.append(freeze.problem)
            released.append(row)
            continue
        freezes[row.pk] = freeze
        renderable.append(row)
        payloads.append(_payload(row, artifact))

    _release(released, reason=None)

    sent = failed = retrying = 0
    for row in unrenderable:
        # Non-retryable: the same pin fails the same way on every attempt. The
        # try the claim counted STAYS counted — it was made and it failed.
        _mark_attempt_failed(row, now=now, error=RENDER_FAILED_REASON, retryable=False)
        failed += 1

    if not payloads:
        if not unrenderable:
            return BatchOutcome(
                channel=channel,
                batch_id=None,
                claimed=0,
                problems=tuple(problems),
            )
        outcome = BatchOutcome(
            channel=channel,
            batch_id=batch_id,
            claimed=len(unrenderable),
            failed=failed,
            problems=tuple(problems),
        )
        _audit_batch(outcome, actor=actor, job=job)
        return outcome

    try:
        answers = provider_seam.dispatch_batch(channel, tuple(payloads))
    except Exception as raised:  # noqa: BLE001 — a provider is arbitrary code
        # T5-24 step 3: a 429 on a batch backs the WHOLE batch off. It does not
        # drop it, does not hammer the provider and does not fail the run.
        problems.append(
            {
                "code": CYCLE_ADAPTER_RAISED,
                "br_ref": "BR-NOT-005",
                "channel": channel,
                "detail": f"the provider call raised {type(raised).__name__}: {raised}. "
                "Every row in this hand-off is treated as a retryable failure and backs "
                "off — a raised adapter tells us nothing about which messages the "
                "provider accepted, and the safe reading of 'unknown' is 'not sent yet' "
                "only because the retry is itself bounded at three.",
            }
        )
        for row in renderable:
            if _mark_attempt_failed(row, now=now, error=str(raised)):
                retrying += 1
            else:
                failed += 1
        outcome = BatchOutcome(
            channel=channel,
            batch_id=batch_id,
            claimed=len(renderable) + len(unrenderable),
            failed=failed,
            retrying=retrying,
            problems=tuple(problems),
        )
        _audit_batch(outcome, actor=actor, job=job)
        return outcome

    for row in renderable:
        answer = answers.get(str(row.pk))
        if answer is None:
            # Silence is not success. An adapter that did not answer for a row
            # has told us nothing, and treating that as `sent` would mark a
            # message delivered on the strength of a missing dictionary key.
            problems.append(
                {
                    "code": CYCLE_PROVIDER_SILENT,
                    "br_ref": "BR-NOT-005",
                    "channel": channel,
                    "message_id": str(row.pk),
                    "detail": "the provider adapter returned no result for this message. "
                    "It is counted as a retryable failure, never as a send.",
                }
            )
            if _mark_attempt_failed(row, now=now, error="provider returned no result"):
                retrying += 1
            else:
                failed += 1
            continue
        if answer.get("status") == models.STATUS_SENT:
            _mark_sent(row, now=now, answer=answer, freeze=freezes.get(row.pk))
            sent += 1
            continue
        if _mark_attempt_failed(
            row,
            now=now,
            error=str(answer.get("error") or "provider reported a failure"),
            response=answer.get("response"),
            retryable=bool(answer.get("retryable", True)),
        ):
            retrying += 1
        else:
            failed += 1

    outcome = BatchOutcome(
        channel=channel,
        batch_id=batch_id,
        claimed=len(renderable) + len(unrenderable),
        sent=sent,
        failed=failed,
        retrying=retrying,
        problems=tuple(problems),
    )
    _audit_batch(outcome, actor=actor, job=job)
    return outcome


def _release(rows: list[models.OutboundMessage], *, reason: str | None) -> None:
    """Give claimed rows back: no batch, no attempt, unchanged place in the queue.

    Used only when NOTHING was attempted for them. The attempt increment made at
    the claim is undone, because a row that never reached a provider has not
    been attempted.

    ⚠ **AMENDED 2026-10-22 (`DEF-BIL-10530`).** This read *"today, every time,
    because nothing renders"* and was the path for a missing template on EVERY
    channel — which is how a bill's email, pinned to the bill layout, was handed
    back with its try reset every cycle and sat at *Waiting · 0 tries* forever.
    A render refusal on email, text or in-app now FAILS (`RENDER_FAILS_CHANNELS`,
    `_mark_attempt_failed(retryable=False)`). What still comes here: a render
    refusal on print or the portal (the document channels) and a freeze refusal
    (`BR-NOT-027`) on any channel. The genuinely transient holds — no provider,
    quiet hours, an unreadable tenant clock — never claim a row at all, so they
    never reach this function.
    """
    if not rows:
        return
    models.OutboundMessage.objects.filter(pk__in=[row.pk for row in rows]).update(
        batch_id=None,
        attempts=dj_models.Case(
            dj_models.When(attempts__gt=0, then=F("attempts") - 1),
            default=0,
            output_field=dj_models.IntegerField(),
        ),
        last_attempt_at=None,
        last_error=reason,
    )


def dispatch_cycle(
    *,
    now: datetime,
    channels: tuple[str, ...] = models.CHANNELS,
    actor: Any = None,
    job: str | None = None,
) -> CycleResult:
    """Run ONE dispatch cycle for the tenant in context. One batch per channel.

    `now` is a PARAMETER and never a clock read (BR-TEN-043; G6 greps for it),
    which is also what makes the quiet-hours window and the scheduled-send
    boundary testable at a named moment rather than at whatever time the suite
    happens to run.

    Returns a `CycleResult` naming every hand-off and every reason a row did not
    move. `result.dispatched` is False on this deployment, every time, and a
    test asserts it rather than trusting this paragraph.
    """
    tenant_id = _tenant_id()
    settings = dispatch_config.dispatch_settings()  # re-read every cycle (T7-17 step 4)

    # ⚠ AMENDED 2026-08-15 (notifications CONTENT lane). This list used to OPEN
    # with `held_marker_not_implemented` on every single cycle, saying the held
    # marker was US-NOT-014's column and unbuilt. It is built now (migration
    # 0007) and `_selectable` skips held rows through
    # `delivery_ops.selectable_filter()`, so the problem is REPLACED by a count
    # of what was actually skipped rather than deleted — a suppression that
    # holds letters silently is only marginally better than one that does not
    # exist (hard-won law 1).
    problems: list[dict[str, Any]] = []
    held = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id, status=models.STATUS_QUEUED, held=True
    ).count()
    if held:
        problems.append(
            {
                "code": CYCLE_HELD_ROWS_SKIPPED,
                "br_ref": "BR-PAY-018",
                "count": held,
                "detail": f"{held} queued row(s) are HELD and were not selected — the "
                "account's address is known to be bad and this tenant has "
                "`suppress_paper_on_bad_address` ON. The rows are written, kept and "
                "never dispatched; ADDRESS VERIFICATION releases them "
                "(`delivery_ops.release_held_for_accounts`) and a re-queue never can "
                "(US-NOT-013 TC-4).",
            }
        )

    unaddressed = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id,
        status=models.STATUS_QUEUED,
        recipient_address__isnull=True,
    ).count()
    if unaddressed:
        problems.append(
            {
                "code": CYCLE_NO_RECIPIENT,
                "br_ref": "BR-BIL-036",
                "count": unaddressed,
                "detail": f"{unaddressed} queued row(s) carry no recipient address and "
                "were not selected — there is nowhere to send them. Each states WHY on "
                "its own `unavailable_reason`, which distinguishes a customer who has no "
                "address on file from a platform that could not look one up. What should "
                "become of such a row — rest, fail, or wait for an address to arrive — is "
                "OQ-208 and is not decided here; migration 0001 named this gap as the "
                "dispatcher's when the table landed.",
            }
        )

    outcomes: list[BatchOutcome] = []
    for channel in channels:
        if channel not in models.CHANNELS:
            raise ValueError(
                f"{channel!r} is not a delivery channel. v1 is "
                f"{', '.join(models.CHANNELS)} (r12 #16); BR-NOT-010 keeps door-hanger "
                "out until v2."
            )
        with transaction.atomic():
            outcomes.append(
                _dispatch_channel(
                    tenant_id=tenant_id,
                    channel=channel,
                    now=now,
                    settings=settings,
                    actor=actor,
                    job=job,
                )
            )

    for outcome in outcomes:
        problems.extend(outcome.problems)

    return CycleResult(
        batch_size=settings.dispatch_batch_size,
        batches=tuple(outcomes),
        problems=tuple(problems),
    )


def dispatch_messages(
    message_ids: tuple[Any, ...],
    *,
    now: datetime,
    actor: Any = None,
    job: str | None = None,
) -> CycleResult:
    """Dispatch exactly THESE rows now — `CR-188-BRC10`'s immediate send.

    PO 2026-10-22, verbatim: *"this should be on highest priority in quesu this
    should be instant email … no latency"*. The SAME path as a cycle — route,
    claim (with `_selectable`), render, freeze, hand-off, outcome, audit — for
    the named rows only, and **without the quiet-hours hold** (the ruling's
    stated narrowing of BR-NOT-009: a sign-in link a person is waiting for is
    not a notice). A row this cannot send — no provider, a refusal, a provider
    failure — is left exactly as the cycle would leave it, with its reason, and
    the next ordinary cycle retries it. It never raises a provider error.
    """
    tenant_id = _tenant_id()
    settings = dispatch_config.dispatch_settings()
    ids = tuple(message_ids)
    channels = tuple(
        models.OutboundMessage.objects.filter(tenant_id=tenant_id, pk__in=list(ids))
        .values_list("channel", flat=True)
        .distinct()
    )
    outcomes: list[BatchOutcome] = []
    for channel in sorted(channels):
        with transaction.atomic():
            outcomes.append(
                _dispatch_channel(
                    tenant_id=tenant_id,
                    channel=channel,
                    now=now,
                    settings=settings,
                    actor=actor,
                    job=job,
                    only_ids=ids,
                    honour_quiet_hours=False,
                )
            )
    problems: list[dict[str, Any]] = []
    for outcome in outcomes:
        problems.extend(outcome.problems)
    return CycleResult(
        batch_size=settings.dispatch_batch_size,
        batches=tuple(outcomes),
        problems=tuple(problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-002@7d4e0c5 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md — US-NOT-002 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-005/009/010 — · 10-notifications/04-flows.md §1 (the queue-row lifecycle) · 08-qa/01-e2e/journeys/T5-24-dispatch-burst-pacing.md + T5-23-quiet-hours-hold.md + J17-delivery-life.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the dispatcher)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a dispatch cycle is a JOB, and the S8/S30 dashboards that read its statuses are US-NOT-013/US-BIL-024) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_002_dispatcher.py 18 passed ·
#         FOUR guards were each proved RED before being trusted green (hard-won
#         law 7), and one of the four proofs CORRECTED THIS TRAILER'S FIRST
#         DRAFT, which is the reason law 7 exists:
#         · batch CAP — slice removed ⇒ `assert [1200] == [500]`
#         · quiet hours — every channel exempted ⇒
#           `assert ['pdf_print', 'email'] == ['pdf_print']`
#         · forward-only — transition table bypassed ⇒
#           `Failed: DID NOT RAISE ForwardOnlyViolation`
#         · the CLAIM — the claim UPDATE's `_selectable` predicate is a RACE
#           guard and removing it alone changes NOTHING single-threaded, because
#           the SELECT carries the same predicate. The first draft of this line
#           claimed it broke the replay case; it does not. What breaks a replay
#           is neutering the SELECT's `status = queued` and batch-id branches
#           together, and then a SECOND guard catches it —
#           `ForwardOnlyViolation: a queue row cannot move sent → sent`. The
#           crash case is where the batch-id branch stands alone: replaced with
#           `Q(pk__isnull=False)`, the crashed row was handed over a second time.
#         Verbatim transcripts in the lane report
# exceptions: (1) NOTHING IS DISPATCHED ON THIS DEPLOYMENT and two independent
#         absences cause it: no provider adapter for ANY channel
#         (`apps/integrations` is three docstrings) and no template store to
#         render from (US-NOT-006). Both are on `CycleResult.problems` every
#         cycle and both are asserted by tests. `CycleResult.dispatched` is a
#         value, not a claim in prose.
#         (2) A CRASHED HAND-OFF LEAVES ITS ROWS CLAIMED AND UNSENT, FOREVER.
#         Rule 6 outranks liveness: nobody knows whether the provider accepted a
#         batch the process died inside, and re-sending on the chance it did not
#         would post a second disconnect notice. The recovery is US-NOT-013's
#         re-queue, which is NOT built and which must clear `batch_id` when it
#         is. REPORTED — this is the one place this design trades a stuck row
#         for a guarantee, and it should be reviewed as such.
#         (3) THE BACKOFF SCHEDULE (5/15/45 minutes) IS ENGINEERING VOCABULARY.
#         BR-NOT-005 says "backoff" and names no interval; B2 r12 #17 delegates
#         dispatcher mechanics to the Eng-Lead. Stated as data so a reviewer
#         changes three numbers.
#         (4) NEITHER `delivered` NOR `bounced` IS EVER WRITTEN HERE. Both are
#         provider facts arriving by webhook (US-NOT-014, W6). A dispatcher that
#         marked its own sends delivered would report a confirmation nobody gave
#         — which is why J17 step 2's "queued → sent → delivered" is only half
#         satisfiable today, and it is the half that does not invent a fact.
#         (5) HELD ROWS ARE NOT SKIPPED because no held marker exists
#         (BR-PAY-018 / US-NOT-014). Reported on EVERY cycle.
#         (6) ROWS WITH NO RECIPIENT ADDRESS ARE NEVER SELECTED and are counted;
#         their terminal disposition is OQ-208, minted rather than chosen.
#         (7) ONE BATCH PER CHANNEL PER CYCLE, deliberately: draining is the
#         SCHEDULER's job at the provider's pace, and a loop here would be the
#         platform-speed blast BR-NOT-005 forbids. There is no scheduler in this
#         repo, so nothing calls this function on a timer yet — REPORTED (hard-won
#         law 2: built is not wired).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
