# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-034 (EP-RBS-05) — CR-075 wave Q′: runbook 22, *Undeliverable
#           contacts* — six steps over the delivery feedback that landed, four
#           read and two write.
# Rules:    BR-RBS-004 (an Action always produces a PLAN first) · BR-RBS-002
#           (a Check is constructed with no writer — this is an Action and
#           holds two named ports, NEITHER of which binds one) · BR-RBS-009
#           (scope resolved ONCE and pinned) · BR-RBS-010 (every record states
#           the rule that decided it, in words a clerk can read) · BR-RBS-011
#           (a failure names its fix route) · BR-RBS-012 (a guard is absolute) ·
#           BR-RBS-019 (the declared unit of work) · BR-RBS-020 (the report is
#           composed at close and frozen) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-022 (a write is a named port; a work item is the ENGINE's) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-027 (a stopped run
#           reads *Never reached* on every later step) · BR-RBS-035 (a volume
#           runbook keeps a row for what it acted on and a COUNT for the rest) ·
#           BR-RBS-039 (every foreign read through a seam this module owns) ·
#           BR-NOT-005 (the status lifecycle is forward-only; retry ×3) ·
#           BR-PAY-018 (paper suppression on a bad address) · RBR-03 (policy
#           lives in Settings and is never duplicated on a card) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 shown, CHAR(3), never a
#           float) · hard rule 8 (an address lives on `premises`; `kind =
#           'mailing'` is the first stated exception) · hard-won law 2 · law 7 ·
#           B14 rules 31, 32
# Tests:    06-backend/tests/test_us_rbs_034_undeliverable_contacts.py ·
#           06-backend/tests/test_rbs_sync_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/notifications_seam.py ·
#           apps/runbooks/seams/customers_seam.py ·
#           apps/notifications/selectors.py · apps/customers/selectors.py
#           · 04-docs/05-modules/17-runbooks/11-catalogue/RB-122-undeliverable-contacts.md
# ───────────────────────────────────────────────────────
"""Runbook 22 — **Undeliverable contacts**.

A notice sent to a dead address is a notice that was never served, and today
nobody acts on the bounce. This takes the morning's delivery feedback,
suppresses the channel that keeps failing, **says where each suppressed channel
falls back to**, and names the accounts with nothing left — which is the
collections ladder's next problem, said before it becomes one.

WHO STARTS IT, AND WHY THAT IS NOT THE EVENT THE CARD NAMES
------------------------------------------------------------
`RB-122`'s trigger row reads ⚡ `feedback.landed(provider, batch_id)`. **A
person starts this runbook.** `feedback.landed` is emitted by nothing — zero
occurrences anywhere in the backend, verified 2026-09-06 — and it is `CR-069`'s
work, currently scoped to nobody. `models.py` already rules that *"a runbook
whose only trigger is an unbuilt event is not runnable, and a screen must SAY so
rather than offering a Run ▶ that refuses"*, so this declares **manual and
schedule**, both of which wait on nothing. The card's *rolled up once a day at
07:00* is the schedule half and is already true of this declaration.

"NO CONNECTION" IS AN ANSWER, AND IT IS STEP 1
-----------------------------------------------
PO ruling 2026-09-06, verbatim: *"we should complete our runbooks, if we need to
do a check of integration and APIs, we should do it, in absence of API
conenctions you will not find anything and you can stop the job saying APi or
conenct not available; that is a valid case and state for us"*. Step 1 asks
where today's feedback comes from and the run **STOPS** when the answer is
nowhere: one red chain cell naming what is missing and five honestly reading
*Never reached* (`BR-RBS-027`). A designed answer, not a crash.

⚠ **TWO DOORS, WHICH IS WAVE `P`'s LESSON APPLIED RATHER THAN REDISCOVERED.**
A clerk who has just marked forty returned letters does not need to be told the
email provider is not connected. So the doors are **a live delivery-feedback
connection** and **feedback already recorded in the product** — a bounce or a
failure a provider wrote, or a `returned_at` a clerk stamped on a paper letter
(`US-NOT-014` TC-1). The run stops only when BOTH are shut.

⚠ **AND ON THIS DEPLOYMENT THE FIRST DOOR IS SHUT FOR A REASON THE OWNING
MODULE ALREADY WROTE DOWN.** `notifications.delivery_ops.queue_health` records
it in as many words: *"`delivered` and `bounced` are PROVIDER facts — a delivery
confirmation and an ESP bounce webhook — and no provider adapter exists on any
channel, print included: delivery is out of this release by PO ruling
(2026-08-15). Their counts are structurally zero here and must be rendered as
NOT REPORTED, never as zero: '0 delivered of 142 sent' reads as a delivery
failure when the truth is that nobody is reporting."* This runbook carries that
sentence onto its own screen rather than printing a confident zero.

WHAT IT PLANS AND WHAT IT ACTUALLY DOES TODAY, STATED RATHER THAN IMPLIED
--------------------------------------------------------------------------
**Nothing is suppressed and no account is flagged**, and the reason is not that
a wave has not got to it. It is that **`customers` has nowhere to write either
fact** (`DEF-RBS-4331`, `CR-075` task `L2`):

* **`suppress_channel`** — `customers.Contact` carries `email` and `phone` as
  columns on a person. **There is no undeliverable-channel column and no date
  for one**, and dating it is the whole value: *this address bounced on the 4th*
  is actionable where *this address is bad* is a dead end.
* **`flag_account`** — `Account` carries only `cash_only`, whose own signed rule
  is that nothing auto-clears it. ⚠ **And the obvious substitute is forbidden**:
  `BR-RBS-040` (CONFIRMED, PO 2026-09-06) makes a NOTE an ENGINE act rather than
  a port, precisely so a Check can cause one while holding no writer. Binding
  `flag_account` to `create_account_note` would make `BR-RBS-002` false and
  **nothing in the suite would notice** — the note would still be written and
  every count would still agree.

So the ports are held, called, and their **own refusals are recorded as the
outcome**. There is no `if is_bound` branch here: `BR-RBS-003` makes dry and
live one code path, and a branch would be a second path proving nothing about
the first.

WHAT THIS RUNBOOK NEEDS THAT THE PRODUCT DOES NOT HOLD, NAMED WITH ITS FIGURE
------------------------------------------------------------------------------
Hard-won law 7: **a declared blind spot with no number attached is
indistinguishable from an empty one.** Three, and each is reported on the screen
rather than left to be inferred:

1. **No provider adapter writes `bounced` or `failed` on any channel**, so the
   provider half of the feedback is structurally empty. `not_reported` carries
   the statuses by name.
2. **No column records a suppression**, so *"31 suppressed"* is what this run
   WOULD suppress. The KPI tile says *To suppress* until a writer is bound.
3. **`Re-enable when the contact is updated`** — the card's own parameter — has
   nothing to re-enable and nothing to watch, so it is declared and its absence
   is stated. It is not a stub awaiting an open question; it is a schema gap
   with a defect row.

THE ONE GUARD THAT MATTERS
----------------------------
**One soft bounce suppresses nothing.** A mailbox full on Tuesday is not a dead
address, and suppressing on it would take a customer's only working channel away
over a transient failure. `BR-NOT-005`'s retry ×3 is the product's own answer to
a soft failure, so a row that has not used its attempts is *retrying* and is
counted separately — a tile of its own, so *nine soft* never hides inside
*thirty-one suppressed*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_DAYS,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_REF_SETTING,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import (
    customers_seam,
    integrations_seam,
    notifications_seam,
    payments_seam,
    tenancy_seam,
)

KEY = "undeliverable_contacts"

# ── the two doors work arrives through ────────────────────────────────────
#
# The delivery manifests, verified against
# `06-backend/apps/integrations/manifests/` on 2026-09-06 and named as VALUES
# rather than imported: a manifest key crossing the seam is data, and importing
# `apps.integrations.manifests` is exactly what `G115` refuses (`BR-RBS-039`).
#
# ⚠ **ALL THREE CHANNELS, BECAUSE THE CARD'S SCOPE IS ALL THREE.** *Waits on
# postal delivery feedback if runbook 12 is to trust it* — runbook 12 step 2
# says *"a returned letter is not a served notice"*, and that needs post in this
# feed. So `print_vendor` is looked for beside the four email providers and the
# text one; a utility on paper alone must not be told there is no feedback door.
# ⚠ **`email_bulk` BECAME `sendgrid` AND `postmark` JOINED IT ON 2026-09-17**
# (`CR-115-BRC05`). These are VALUES rather than imports by design — see above —
# **and that is exactly why a rename does not reach them and cannot go red.**
# A key that no longer exists matches no connection, so this card would have
# gone on reporting *no feedback door* for a utility that had one, truthfully
# counting everything it could see (hard-won law 7's *reporting zero over a
# scope it silently excludes*). `test_cr115__the_runbook_names_every_delivery_
# manifest` now checks this tuple against the registry, so the next rename
# fails a test instead of a customer.
DELIVERY_PROVIDER_KEYS = (
    "sendgrid",
    "postmark",
    "email_google",
    "email_microsoft",
    "email_smtp",
    "sms_twilio",
    "print_vendor",
)

# ── the channels, in the fall-back order the card fixes ───────────────────
#
# ⚠ **THE ORDER IS THE POLICY** — *email → text → post → none* (`RB-122` step 4,
# and `Fall back to: Next channel on file` is Settings-owned). It is written
# once, here, so a step cannot re-order it into a different policy on the way
# past.
CHANNEL_EMAIL = "email"
CHANNEL_TEXT = "text"
CHANNEL_POST = "post"
FALLBACK_ORDER = (CHANNEL_EMAIL, CHANNEL_TEXT, CHANNEL_POST)

CHANNEL_LABELS = {
    CHANNEL_EMAIL: "Email",
    CHANNEL_TEXT: "Text",
    CHANNEL_POST: "Post",
}

#: What `notifications` calls a channel, mapped to what a clerk calls one.
#: `pdf_print` is the product's own value for paper; `in_app` is a message
#: inside the product and cannot be undeliverable, so it maps to nothing and is
#: counted as *not a contact channel* rather than dropped.
CHANNEL_FROM_NOTIFICATIONS = {
    "email": CHANNEL_EMAIL,
    "sms": CHANNEL_TEXT,
    "pdf_print": CHANNEL_POST,
}

# ── the four kinds of failure, in the card's own order ────────────────────

KIND_HARD_BOUNCE = "hard_bounce"
KIND_SOFT_BOUNCE = "soft_bounce"
KIND_FAILED_TEXT = "failed_text"
KIND_RETURNED_POST = "returned_post"
KIND_NOT_A_CHANNEL = "not_a_contact_channel"

KIND_LABELS = {
    KIND_HARD_BOUNCE: "Hard bounce",
    KIND_SOFT_BOUNCE: "Soft bounce",
    KIND_FAILED_TEXT: "Failed text",
    KIND_RETURNED_POST: "Returned post",
    KIND_NOT_A_CHANNEL: "Not a contact channel",
}

#: Which kinds count towards suppressing a channel. A soft bounce does NOT —
#: see the module docstring's guard.
HARD_KINDS = (KIND_HARD_BOUNCE, KIND_FAILED_TEXT, KIND_RETURNED_POST)

# ── the outcomes one feedback item can reach ──────────────────────────────
#
# ⚠ **`planned` IS NOT `skipped` AND `retrying` IS NEITHER.** A planned
# suppression is one this run WOULD make; a retrying item is one the product is
# still trying to deliver; a skipped one is one nothing is going to do.
# `BR-RBS-035` counts every outcome including the ones with no record row.
OUTCOME_SUPPRESSED = "suppressed"
OUTCOME_PLANNED = "planned"
OUTCOME_RETRYING = "retrying"
OUTCOME_NOTHING_LEFT = "nothing_left"
OUTCOME_NEEDS_A_PERSON = "needs_a_person"
OUTCOME_SKIPPED = "skipped"

# ── the steps, in the card's own order ────────────────────────────────────

STEP_GATHER = "gather_the_landed_feedback"
STEP_CLASSIFY = "classify_each_item"
STEP_SUPPRESSION = "apply_the_suppression_rule"
STEP_FALLBACK = "find_the_next_channel_on_file"
STEP_SUPPRESS = "suppress_and_fall_back"
STEP_FLAG = "flag_the_address_and_raise_work_items"

STEP_LABELS = {
    STEP_GATHER: "Gather the landed feedback",
    STEP_CLASSIFY: "Classify each item",
    STEP_SUPPRESSION: "Apply the suppression rule",
    STEP_FALLBACK: "Find the next channel on file",
    STEP_SUPPRESS: "Suppress and fall back",
    STEP_FLAG: "Flag the address, raise work items",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-06.** A fix route resolving to nothing is
# a dead button over a live finding — hard-won law 2's mirror, the shape that
# left the customer portal with two working doors out of eight — and nothing in
# the backend suite can see it, because a string is a string. Tenant-relative:
# the shell prefixes `/:tenant/`.
FIX_ACCOUNTS = "accounts"
FIX_NOTIFICATIONS = "notifications"
FIX_INTEGRATIONS = "settings/integrations"

ZERO = Decimal("0")


@dataclass(frozen=True)
class Feedback:
    """One thing that did not arrive, and what this run decided about it.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `item_id` and `account_id` are handles the engine and the port need;
    `account_label` is what a clerk can act on.

    ⚠ **`reason` IS A SENTENCE AND NEVER A RULE ID** (`BR-RBS-010`, B14 rule
    32). The rule travels in `decided_by_rule`, carried in `ReportRow.meta` and
    drawn by no block.
    """

    item_id: str
    account_id: str | None
    account_label: str
    channel: str
    channel_label: str
    kind: str
    told_by: str
    at: str | None
    falls_back_to: str | None
    outcome: str
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a feedback item with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"feedback item {self.item_id!r} names no fix route. BR-RBS-011: a failure "
                "names its fix route, and a failure with no route is a defect in the runbook "
                "— a clerk reads what is wrong and has nowhere to go."
            )

    def as_row(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "account_id": self.account_id,
            "account_label": self.account_label,
            "channel": self.channel,
            "channel_label": self.channel_label,
            "kind": self.kind,
            "told_by": self.told_by,
            "at": self.at,
            "falls_back_to": self.falls_back_to,
            "outcome": self.outcome,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration. A step reporting nothing because no feedback
    landed and a step reporting nothing because nothing bounced are the same
    sentence with very different meanings, and a check whose output cannot tell
    a reader which is which is worse than no check at all (hard-won law 7).

    `reached` is `False` on every step after a stop — what the chain draws as
    `notReached`, rather than a blank cell, which reads as *nothing wrong*.
    """

    reached: bool = True
    stop: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "plan": list(self.plan),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── helpers ───────────────────────────────────────────────────────────────


def _money(raw: Any) -> Decimal | None:
    """A stored money string as a `Decimal`, or `None` where it will not parse.

    ⚠ **NEVER `float(...)`** — hard rule 2, and the seam hands the stored
    four-place value across as a STRING for exactly this reason.
    """
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """A money figure as it is STORED — four decimals (hard rule 2).

    The renderer displays two; what is written is four, and the two are
    different jobs. A sum of `Decimal("0")` reaches a screen as `0.0000` rather
    than as `0`.
    """
    return str(amount.quantize(Decimal("0.0001")))


def _window_start(ctx):
    """The first day this run's feedback may come from — the tenant's OWN today.

    ⚠ **`BR-TEN-043`: THE BUSINESS DATE IS AN INPUT AND NOT A CLOCK A RUNBOOK
    READS.** `tenancy_seam.today()` is the tenant's own today, so a run re-read
    tomorrow shows the same set it showed today unless somebody moved the date.
    """
    days = int(ctx.params.get("window") or 1)
    return tenancy_seam.today() - timedelta(days=max(days, 0))


def _in_window(item: dict[str, Any], start) -> bool:
    """Is this failure inside the run's window?

    ⚠ **AN ITEM WITH NO DATE IS INCLUDED AND COUNTED, NEVER DROPPED.** A provider
    failure carries `last_attempt_at` and a row that has never been attempted
    carries nothing; excluding it would quietly shrink the morning's work, and a
    filter with nothing to filter on is a filter that guesses. Step 1 reports how
    many arrived undated beside how many were in the window.
    """
    at = item.get("at")
    if not at:
        return True
    try:
        return date.fromisoformat(str(at)[:10]) >= start
    except ValueError:
        return True


def _feedback(ctx) -> dict[str, Any]:
    """The morning's feedback, read once per step that needs it — WINDOWED.

    ⚠ **THE WINDOW IS NOT A CONVENIENCE; WITHOUT IT THIS RUNBOOK RE-SUPPRESSES
    THE SAME CHANNELS FOR EVER.** `notifications` holds every bounce and every
    returned letter it has ever been told about, so an unwindowed read would
    plan the same suppression every morning and *"31 suppressed"* would climb
    without a customer's situation changing. `RB-122`'s scope is *the landed
    feedback, rolled up once a day* and its own count line reads **Yesterday**,
    so the window is the card's, not an invention.
    """
    answer = dict(notifications_seam.undeliverable_feedback())
    start = _window_start(ctx)
    everything = list(answer.get("items") or [])
    answer["items"] = [one for one in everything if _in_window(one, start)]
    answer["items_outside_the_window"] = len(everything) - len(answer["items"])
    answer["window_starts"] = start.isoformat()
    answer["items_with_no_date"] = len([one for one in everything if not one.get("at")])
    return answer


def _items(answer: dict[str, Any]) -> list[dict[str, Any]]:
    return list(answer.get("items") or [])


def _stopped(ctx) -> dict[str, Any] | None:
    """The stop step 1 recorded, or `None`. Read by every step after it."""
    first = ctx.set_results.get(STEP_GATHER) or {}
    stop = first.get("stop")
    return dict(stop) if stop else None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _plan(ctx) -> list[dict[str, Any]]:
    """The plan as the LAST step that touched it left it.

    Steps 2 to 4 each rewrite the whole plan rather than annotating rows in
    place, so the plan a later step reads is always one object with one author.
    """
    for key in (STEP_FALLBACK, STEP_SUPPRESSION, STEP_CLASSIFY):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


# ── step 1 · where today's feedback comes from ────────────────────────────


def step_gather_the_landed_feedback(ctx, subjects) -> dict[str, Any]:
    """1 · Two doors, and the run STOPS when both are shut.

    `RB-122` step 1 reads *"Gather the landed feedback — from the notification
    provider, once, pinned"*. The Product Owner's ruling of 2026-09-06 makes
    that one step with two halves: a **connection** may report a bounce, and a
    **person** may stamp a returned letter. This looks for both and says which
    it found.

    ⚠ **`not_reported` TRAVELS EVEN WHEN THE RUN CARRIES ON.** The two statuses
    no adapter on this deployment can write are named on every run, not only on
    a stop — because a morning with four returned letters and no bounces is not
    a morning on which nothing bounced.
    """
    connections = integrations_seam.live_connections(DELIVERY_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    answer = _feedback(ctx)
    items = _items(answer)

    checked: dict[str, Any] = {
        "delivery_connections_looked_for": len(DELIVERY_PROVIDER_KEYS),
        "delivery_connections_found": len(connections),
        "delivery_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "feedback_items": len(items),
        "told_by_a_provider": len([one for one in items if one.get("told_by") == "provider"]),
        "told_by_a_person": len([one for one in items if one.get("told_by") == "a person"]),
        "messages_on_file": answer.get("messages_on_file"),
        "window_starts": answer.get("window_starts"),
        "items_outside_the_window": answer.get("items_outside_the_window"),
        "items_with_no_date": answer.get("items_with_no_date"),
        # ⚠ THE NUMBER BESIDE THE BLIND SPOT (hard-won law 7). These statuses are
        # structurally zero here and must never be drawn as a clean result.
        "not_reported": list(answer.get("not_reported") or []),
        "channels_with_traffic": list(answer.get("channels_with_traffic") or []),
    }

    if not items and not working:
        # ⚠ BOTH DOORS SHUT. The headline names both, in the order a clerk can
        # act on them: marking a returned letter is a two-second job and
        # connecting an email provider is an afternoon.
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "A delivery provider is set up and switched off."
            if offline
            else "No delivery provider is set up, so nothing reports a bounce."
        )
        return _StepResult(
            stop={
                "headline": "Nothing has come back.",
                "detail": (
                    f"{detail} No returned letters have been marked either, so there is no "
                    "feedback to act on. Mark the letters that came back, or connect a "
                    "delivery provider."
                ),
                "fix_route": FIX_NOTIFICATIONS,
                "fix_label": "Open the message queue",
            },
            checked=checked,
        ).as_dict()

    if not items:
        # A provider is connected and it has reported nothing. A different
        # sentence and a different stop — and on this deployment it is the
        # honest one, because no adapter writes a bounce on any channel.
        return _StepResult(
            stop={
                "headline": "Nothing has come back yet.",
                "detail": (
                    f"{', '.join(str(one) for one in checked['connection_names'])} is connected "
                    "and has reported nothing that failed. Start this again when feedback "
                    "arrives, or mark the letters that came back."
                ),
                "fix_route": FIX_NOTIFICATIONS,
                "fix_label": "Open the message queue",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(checked=checked).as_dict()


# ── step 2 · what kind of failure each one is ─────────────────────────────


def _kind_of(item: dict[str, Any], channel: str | None, retry_limit: int) -> str:
    """Hard bounce · soft bounce · failed text · returned post.

    ⚠ **A SOFT BOUNCE IS A FAILURE THE PRODUCT IS STILL RETRYING, AND THAT IS
    THE PRODUCT'S OWN DEFINITION** (`BR-NOT-005`: retry ×3 with backoff). A row
    that has not used its attempts is soft; one that has is hard, which is the
    card's *retry for 3 days, then treat as hard* expressed in the units this
    product actually holds. **Attempts, not days** — and the difference is
    stated rather than hidden, because `outbound_messages` has an attempt count
    and no age column, and `BR-TEN-043` makes the business date an input rather
    than a clock a runbook may read.
    """
    if channel is None:
        return KIND_NOT_A_CHANNEL
    if channel == CHANNEL_POST:
        return KIND_RETURNED_POST
    if channel == CHANNEL_TEXT:
        return KIND_FAILED_TEXT
    if str(item.get("status")) == "bounced":
        return KIND_HARD_BOUNCE
    attempts = item.get("attempts")
    if attempts is None or int(attempts) >= retry_limit:
        return KIND_HARD_BOUNCE
    return KIND_SOFT_BOUNCE


def step_classify_each_item(ctx, subjects) -> dict[str, Any]:
    """2 · Hard bounce · soft bounce · failed text · returned post.

    The whole plan is built here, in one pass over the landed feedback, and the
    later steps rewrite it. Splitting the classification across two steps that
    each walked the feedback would ask `notifications` the same question twice
    and let the two answers drift within one run.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    in_scope = {str(one.subject_id) for one in subjects}
    items = [one for one in _items(_feedback(ctx)) if str(one.get("message_id")) in in_scope]
    account_ids = sorted({one["account_id"] for one in items if one.get("account_id")})
    facts = {
        account_id: customers_seam.account_facts(account_id) for account_id in account_ids
    }
    retry_limit = int(ctx.params.get("retry_attempts") or 3)

    plan: list[Feedback] = []
    unnamed = 0
    for item in items:
        channel = CHANNEL_FROM_NOTIFICATIONS.get(str(item.get("channel")))
        kind = _kind_of(item, channel, retry_limit)
        account_id = item.get("account_id")
        fact = facts.get(account_id) or {}
        label = fact.get("label") or fact.get("account_no")
        if not label:
            # ⚠ NAMED, NEVER DROPPED. A staff report or a bookkeeper message is
            # addressed to nobody's account (`outbound_messages.account_id` is
            # nullable by design), and a bounce on one is real feedback that
            # suppresses no customer channel. Counting it is what keeps
            # *"nothing to suppress"* apart from *"nothing came back"*.
            unnamed += 1
            label = "Not a customer's message"
        plan.append(
            Feedback(
                item_id=str(item.get("message_id")),
                account_id=str(account_id) if account_id else None,
                account_label=str(label),
                channel=channel or "",
                channel_label=CHANNEL_LABELS.get(channel or "", "Other"),
                kind=kind,
                told_by=str(item.get("told_by") or ""),
                at=item.get("at"),
                falls_back_to=None,
                outcome=OUTCOME_NEEDS_A_PERSON,
                reason=f"{KIND_LABELS[kind]} on {CHANNEL_LABELS.get(channel or '', 'another channel')}.",
                decided_by_rule="Every failure is classified before anything is suppressed",
                fix_route=FIX_ACCOUNTS,
                fix_label="Open account →",
            )
        )

    by_kind: dict[str, int] = {}
    for one in plan:
        by_kind[one.kind] = by_kind.get(one.kind, 0) + 1

    return _StepResult(
        plan=[one.as_row() for one in plan],
        checked={
            "feedback_classified": len(plan),
            "retry_attempts_before_hard": retry_limit,
            "accounts_named": len(account_ids),
            "items_with_no_customer_account": unnamed,
            "by_kind": by_kind,
        },
    ).as_dict()


# ── step 3 · the suppression rule ─────────────────────────────────────────


def step_apply_the_suppression_rule(ctx, subjects) -> dict[str, Any]:
    """3 · The thresholds, and **one soft bounce suppresses nothing**.

    `RB-122`'s own guard, and it is the one that protects a customer: a mailbox
    full on Tuesday is not a dead address, and suppressing on it would take away
    the only channel that works.

    ⚠ **A RETURNED LETTER SUPPRESSES ON ONE AND AN EMAIL TAKES TWO**, which is
    the card's *Suppress after: 2 hard bounces, or 1 returned letter*. The
    asymmetry is deliberate: an envelope physically came back, which is a fact
    somebody held in their hand, while one bounce message can be a mail server
    having a bad afternoon.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    after_bounces = int(ctx.params.get("suppress_after_bounces") or 2)
    after_returns = int(ctx.params.get("suppress_after_returned_letters") or 1)

    hard_counts: dict[tuple[str, str], int] = {}
    for one in plan:
        if one["kind"] in HARD_KINDS and one["account_id"] and one["channel"]:
            key = (one["account_id"], one["channel"])
            hard_counts[key] = hard_counts.get(key, 0) + 1

    suppress: set[tuple[str, str]] = set()
    for (account_id, channel), count in hard_counts.items():
        threshold = after_returns if channel == CHANNEL_POST else after_bounces
        if count >= threshold:
            suppress.add((account_id, channel))

    out: list[dict[str, Any]] = []
    retrying = below = 0
    for one in plan:
        row = dict(one)
        key = (row["account_id"], row["channel"])
        if row["kind"] == KIND_SOFT_BOUNCE:
            retrying += 1
            row["outcome"] = OUTCOME_RETRYING
            row["reason"] = (
                "Still being retried. One soft bounce suppresses nothing."
            )
            row["decided_by_rule"] = "A soft bounce is retried before it counts against a channel"
            row["fix_route"] = FIX_NOTIFICATIONS
            row["fix_label"] = "Open the message queue →"
        elif row["kind"] == KIND_NOT_A_CHANNEL:
            row["outcome"] = OUTCOME_SKIPPED
            row["reason"] = "This message is not addressed to a contact channel."
            row["decided_by_rule"] = "Only a customer's own channel can be suppressed"
            row["fix_route"] = FIX_NOTIFICATIONS
            row["fix_label"] = "Open the message queue →"
        elif key in suppress:
            row["outcome"] = OUTCOME_PLANNED
            row["reason"] = (
                f"{hard_counts[key]} failure(s) on this account's {row['channel_label'].lower()}."
            )
            row["decided_by_rule"] = "A channel is suppressed after the utility's own threshold"
            row["fix_route"] = FIX_ACCOUNTS
            row["fix_label"] = "Open account →"
        else:
            below += 1
            threshold = after_returns if row["channel"] == CHANNEL_POST else after_bounces
            row["outcome"] = OUTCOME_NEEDS_A_PERSON
            row["reason"] = (
                f"{hard_counts.get(key, 0)} of {threshold} failures needed to suppress "
                f"{row['channel_label'].lower()}."
            )
            row["decided_by_rule"] = "A channel is suppressed after the utility's own threshold"
            row["fix_route"] = FIX_ACCOUNTS
            row["fix_label"] = "Open account →"
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "suppress_after_bounces": after_bounces,
            "suppress_after_returned_letters": after_returns,
            "channels_to_suppress": len(suppress),
            "still_retrying": retrying,
            "below_the_threshold": below,
        },
    ).as_dict()


# ── step 4 · the next channel on file ─────────────────────────────────────


def step_find_the_next_channel_on_file(ctx, subjects) -> dict[str, Any]:
    """4 · Email → text → post → none, and **where each one lands is the answer**.

    `US-RBS-034`'s acceptance sentence asks for *where each suppressed channel
    fell back to*, so this is not a yes/no: every planned suppression carries
    the channel it hands over to, by name, and an account with nothing left says
    so in the same column.

    ⚠ **A CHANNEL ALREADY BEING SUPPRESSED IN THIS RUN IS NOT A FALL-BACK.** An
    account whose email and post both came back would otherwise be told to fall
    back to the post that just came back — which reads as a plan and is a loop.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    account_ids = sorted({one["account_id"] for one in plan if one["account_id"]})
    on_file = customers_seam.contact_channels_for(account_ids)

    suppressed_by_account: dict[str, set[str]] = {}
    for one in plan:
        if one["outcome"] == OUTCOME_PLANNED and one["account_id"]:
            suppressed_by_account.setdefault(one["account_id"], set()).add(one["channel"])

    out: list[dict[str, Any]] = []
    fell_back = nothing_left = 0
    for one in plan:
        row = dict(one)
        if row["outcome"] != OUTCOME_PLANNED:
            out.append(row)
            continue
        account_id = row["account_id"]
        entry = on_file.get(str(account_id)) or {}
        held = [name for name in FALLBACK_ORDER if entry.get(name)]
        gone = suppressed_by_account.get(account_id, set())
        left = [name for name in held if name not in gone]
        if left:
            fell_back += 1
            row["falls_back_to"] = left[0]
            row["reason"] = (
                f"{row['reason']} Falls back to {CHANNEL_LABELS[left[0]].lower()}."
            )
            row["decided_by_rule"] = "The fall-back is the next channel on file, in order"
        else:
            nothing_left += 1
            row["outcome"] = OUTCOME_NOTHING_LEFT
            row["falls_back_to"] = None
            row["reason"] = (
                f"{row['reason']} Nothing is left on file to reach this account on."
            )
            row["decided_by_rule"] = "An account nobody can reach is raised, never left quiet"
            row["fix_route"] = FIX_ACCOUNTS
            row["fix_label"] = "Add a contact →"
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "accounts_looked_up": len(account_ids),
            "accounts_with_no_channel_at_all": len(
                [one for one, entry in on_file.items() if not entry.get("channels")]
            ),
            "fall_backs_found": fell_back,
            "nothing_left": nothing_left,
            "fall_back_order": list(FALLBACK_ORDER),
        },
    ).as_dict()


# ── step 5 · suppress and fall back ───────────────────────────────────────


def step_suppress_and_fall_back(ctx, subject) -> dict[str, Any]:
    """5 · Through the customers service, dated (`BR-RBS-022`).

    ⚠ **THE RUNBOOK NEVER WRITES A CONTACT ROW.** `suppress_channel` is a named
    port into `customers`' own service — and **it binds no writer**, because
    `customers.Contact` has no undeliverable-channel column and no date for one
    (`DEF-RBS-4331`). The port is called anyway and its own refusal is recorded
    as the outcome: `BR-RBS-003` makes dry and live one code path, and an
    `if is_bound` branch would be a second path proving nothing about the first.

    ⚠ **PER-RECORD, SO EACH ITEM RUNS INSIDE ITS OWN SAVEPOINT.** The executor
    opens a nested `transaction.atomic()` around this call. On PostgreSQL that
    is the ONLY thing that lets the run continue after one refused row —
    without it the first `IntegrityError` aborts the whole transaction and every
    later suppression is lost at COMMIT, and the suite's in-memory SQLite cannot
    see the difference (hard-won law 14).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A required step failing makes every later step Never reached",
            "fix_route": FIX_NOTIFICATIONS,
        }

    by_id = {one["item_id"]: one for one in _plan(ctx)}
    row = by_id.get(str(subject.subject_id))
    if row is None:
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "This message is not in the plan.",
            "decided_by_rule": "Only the pinned set is walked",
            "fix_route": FIX_NOTIFICATIONS,
        }
    data = {
        "label": subject.label,
        "account": row["account_label"],
        "channel": row["channel_label"],
        "falls_back_to": row["falls_back_to"],
    }
    if row["outcome"] not in (OUTCOME_PLANNED, OUTCOME_NOTHING_LEFT):
        return {
            "outcome": row["outcome"],
            "reason": row["reason"],
            "decided_by_rule": row["decided_by_rule"],
            "fix_route": row["fix_route"],
            "data": data,
        }

    try:
        ctx.port("suppress_channel").call(
            account_id=row["account_id"],
            channel=row["channel"],
            reason=row["reason"],
        )
    except PortNotBound as refusal:
        return {
            "outcome": row["outcome"],
            "reason": row["reason"],
            "decided_by_rule": str(refusal),
            "fix_route": row["fix_route"],
            "data": data,
        }
    suppressed = ctx.set_results.setdefault("suppressed", [])
    suppressed.append(row["item_id"])
    return {
        "outcome": OUTCOME_SUPPRESSED,
        "reason": row["reason"],
        "decided_by_rule": "A channel is suppressed after the utility's own threshold",
        "fix_route": row["fix_route"],
        "data": data,
    }


# ── step 6 · the accounts with nothing left ───────────────────────────────


def step_flag_the_address_and_raise_work_items(ctx, subjects) -> dict[str, Any]:
    """6 · For the accounts with nothing left, with **what they owe beside them**.

    `RB-122`'s design note: an account nobody can reach with money outstanding
    is the dunning runbook's next problem, and the row says so before it becomes
    one. So this prices exactly the accounts with nothing left — never the whole
    plan, which would be one balance read per bounce.

    ⚠ **`flag_account` BINDS NO WRITER AND THE SUBSTITUTE IS FORBIDDEN.**
    `Account` carries only `cash_only`, whose own rule is that nothing
    auto-clears it, and `BR-RBS-040` makes a NOTE an ENGINE act rather than a
    fourteenth port — binding this to `create_account_note` would make
    `BR-RBS-002` false and nothing in the suite would notice. So the port is
    called, its refusal is recorded, and the accounts are listed.

    ⚠ **A WORK ITEM IS AN ENGINE ACT AND NOT A PORT** (`BR-RBS-022`). The
    engine's upsert-by-fingerprint is `CR-075` task `H1`, which is **phase 4**;
    until it lands these rows are readable on this run's own result screen and
    are not yet gathered into `RBS-007`. The rows are not lost, only ungathered.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    stranded = [one for one in plan if one["outcome"] == OUTCOME_NOTHING_LEFT]
    accounts = sorted({one["account_id"] for one in stranded if one["account_id"]})
    currency = payments_seam.tenant_currency()

    owed: dict[str, str] = {}
    unreadable = 0
    for account_id in accounts:
        position = payments_seam.open_bill_position(account_id)
        if position is None:
            # ⚠ AN ACCOUNT WHOSE BOOKS WILL NOT OPEN IS NAMED, NOT SKIPPED. A
            # step that passed over it silently would report a clean list over
            # an account nobody could price — `G32`'s shape, which reported
            # `0 unresolved` truthfully over 21 live refusals.
            unreadable += 1
            continue
        owed[account_id] = _stored(_money(position.get("total_open")) or ZERO)

    # ⚠ **`flag_state` MUST NOT READ *flagged* OVER AN EMPTY LIST.** A loop that
    # never runs leaves the word at its optimistic default, and *"flagged"* over
    # nought accounts is the shape hard-won law 7 calls a check that reports a
    # clean result over a scope it never entered. The absence gets its own word.
    refused = "" if accounts else "nothing to flag"
    flagged = 0
    for account_id in accounts:
        try:
            ctx.port("flag_account").call(
                account_id=account_id,
                reason="Nobody can be reached at this account.",
            )
            flagged += 1
        except PortNotBound as refusal:
            refused = str(refusal)
            break

    return _StepResult(
        plan=[dict(one, owed=owed.get(one["account_id"] or "")) for one in plan],
        checked={
            "accounts_with_nothing_left": len(accounts),
            "balances_read": len(owed),
            "balances_that_would_not_read": unreadable,
            "accounts_flagged": flagged,
            "flag_state": refused or "flagged",
            "work_items_raised": 0,
            "work_list_state": (
                "The work list is built in a later wave; these are on this run's own screen."
            ),
            "currency": currency,
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_FLAG, STEP_FALLBACK, STEP_SUPPRESSION, STEP_CLASSIFY):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    """Six cells: the one that stopped the run, and five that never ran."""
    cells = []
    for index, key in enumerate(STEP_LABELS, start=1):
        first = index == 1
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": "bad" if first else "notReached",
                "note": stop["headline"] if first else "Never reached",
            }
        )
    return Block(block="chain", payload={"label": "The run stopped at step 1.", "cells": cells})


def _records_columns() -> list[dict[str, Any]]:
    return [
        {"key": "account", "label": "Account"},
        {"key": "was", "label": "Was"},
        {"key": "now", "label": "Now"},
        {"key": "owed", "label": "Owed", "numeric": True},
        {"key": "fix", "label": "Fix"},
    ]


def _record_row(index: int, row: dict[str, Any], currency: str) -> dict[str, Any]:
    owed = _money(row.get("owed"))
    return {
        "id": f"row-{index}",
        "cells": {
            "account": {"kind": "text", "text": row["account_label"]},
            "was": {"kind": "text", "text": row["channel_label"]},
            # ⚠ *Now* READS `—` ON EVERY NOTHING-LEFT ROW — `RB-122`'s own note.
            # An em dash is the honest cell: there is no channel, and a blank
            # would read as *not looked at*.
            "now": {
                "kind": "text",
                "text": (
                    CHANNEL_LABELS[row["falls_back_to"]] if row["falls_back_to"] else "—"
                ),
            },
            "owed": (
                # ⚠ MONEY IS STORED TO FOUR AND SHOWN TO TWO (hard rule 2). The
                # cell carries the stored figure and its CHAR(3) code; the
                # renderer does the rounding and the symbol, so a six-place
                # container's value can never reach clerk-facing copy — which is
                # the defect wave `P` had to fix (*"182.400000 more than this
                # account owes"*).
                {"kind": "money", "amount": _stored(owed), "currency": currency}
                if owed is not None
                else {"kind": "text", "text": "—"}
            ),
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        # ⚠ CARRIED, NEVER DRAWN — the renderer walks `columns`, so nothing here
        # reaches a screen. `decided_by_rule` MUST NOT: B14 rule 32 forbids a
        # rule id in clerk-facing copy. It is here because the result file and
        # the conformance test both read it, and the report is the only frozen
        # artefact.
        "meta": {
            "decided_by_rule": row["decided_by_rule"],
            "outcome": row["outcome"],
            "kind": row["kind"],
        },
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states
    and one shape cannot say both:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). The
      chain draws *Never reached* on the five steps that did not run, and the
      KPI strip is deliberately ABSENT: a strip reading *0 suppressed · 0 fell
      back · 0 nothing left* over a run that examined nothing is
      indistinguishable from a morning on which everything arrived, which is
      precisely the failure hard-won law 7 is about.
    * **finished** — `Verdict` · `KPIs` · `Breakdown` · `Records` ·
      `Downloads`, which is `RB-122`'s own block list plus the verdict the
      header consumes.

    Every name is one of the twelve (`BR-RBS-021`); no thirteenth is minted.
    """
    stop = (view.set_results.get(STEP_GATHER) or {}).get("stop")
    if stop:
        return [
            Block(
                block="verdict",
                payload={
                    "word": "Stopped",
                    "tone": "warning",
                    "count": stop["headline"],
                    "detail": stop["detail"],
                },
            ),
            Block(
                block="sentence",
                payload={"tone": "muted", "label": "What to do", "text": stop["detail"]},
            ),
            _chain(view, stop),
            Block(
                block="records",
                payload={
                    "columns": _records_columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    plan = _plan_from_view(view)
    acted = any(record.outcome == OUTCOME_SUPPRESSED for record in view.records)
    gathered = (view.set_results.get(STEP_GATHER) or {}).get("checked") or {}
    flagged = (view.set_results.get(STEP_FLAG) or {}).get("checked") or {}
    currency = str(flagged.get("currency") or "USD")

    suppressed = [
        one for one in plan if one["outcome"] in (OUTCOME_PLANNED, OUTCOME_SUPPRESSED)
    ]
    fell_back = [one for one in suppressed if one["falls_back_to"]]
    stranded = [one for one in plan if one["outcome"] == OUTCOME_NOTHING_LEFT]
    retrying = [one for one in plan if one["outcome"] == OUTCOME_RETRYING]
    word = "Suppressed" if acted else "To suppress"

    by_channel: dict[str, dict[str, Any]] = {}
    for one in plan:
        name = one["channel_label"] or "Other"
        tally = by_channel.setdefault(name, {"feedback": 0, "suppressed": 0, "to": {}})
        tally["feedback"] += 1
        if one["outcome"] in (OUTCOME_PLANNED, OUTCOME_SUPPRESSED, OUTCOME_NOTHING_LEFT):
            tally["suppressed"] += 1
            destination = (
                CHANNEL_LABELS[one["falls_back_to"]] if one["falls_back_to"] else "none"
            )
            tally["to"][destination] = tally["to"].get(destination, 0) + 1

    return [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": "success" if not stranded else "warning",
                "count": (
                    f"{len(suppressed) + len(stranded)} "
                    f"{'suppressed' if acted else 'to suppress'}. "
                    f"{len(stranded)} have nothing left."
                ),
                "detail": (
                    f"{gathered.get('feedback_items', 0)} items of feedback landed."
                    if acted
                    else "Nothing is suppressed until a writer is bound for this runbook."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "suppressed",
                        "label": word,
                        "value": {
                            "kind": "text",
                            "text": str(len(suppressed) + len(stranded)),
                        },
                        "detail": None if acted else "Planned — nothing is changed yet",
                    },
                    {
                        "id": "fell_back",
                        "label": "Fell back" if acted else "Would fall back",
                        "value": {"kind": "text", "text": str(len(fell_back))},
                    },
                    {
                        "id": "nothing_left",
                        "label": "Nothing left",
                        "value": {"kind": "text", "text": str(len(stranded))},
                        "detail": "Nobody can be reached",
                    },
                    {
                        "id": "retrying",
                        "label": "Soft · retrying",
                        "value": {"kind": "text", "text": str(len(retrying))},
                        "detail": "One soft bounce suppresses nothing",
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By channel",
                "columns": [
                    {"key": "channel", "label": "Channel"},
                    {"key": "feedback", "label": "Feedback", "numeric": True},
                    {"key": "suppressed", "label": word, "numeric": True},
                    {"key": "to", "label": "Fell back to" if acted else "Would fall back to"},
                ],
                "rows": [
                    {
                        "id": f"channel-{name}",
                        "cells": {
                            "channel": {"kind": "text", "text": name},
                            "feedback": {"kind": "text", "text": str(tally["feedback"])},
                            "suppressed": {"kind": "text", "text": str(tally["suppressed"])},
                            "to": {
                                "kind": "text",
                                "text": " · ".join(
                                    f"{where} {count}"
                                    for where, count in sorted(tally["to"].items())
                                )
                                or "—",
                            },
                        },
                    }
                    for name, tally in sorted(by_channel.items())
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [
                    _record_row(index, row, currency)
                    for index, row in enumerate(stranded, start=1)
                ],
                "total": len(stranded),
                "chips": [
                    {"id": "nothing_left", "label": "Nothing left", "count": len(stranded)},
                    {"id": "fell_back", "label": "Fell back", "count": len(fell_back)},
                    {"id": "retrying", "label": "Soft · retrying", "count": len(retrying)},
                ],
                "empty": {
                    "title": "Everybody can still be reached.",
                    "helper": (
                        f"{gathered.get('feedback_items', 0)} items of feedback, and every "
                        "account has a channel left on file."
                    ),
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "suppressed", "label": word, "format": "csv"},
                    {"id": "nothing_left", "label": "Nothing left", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────

#: Where `resolve()` leaves the guard its answer, so the guard costs no query.
SAMPLE_KEYS = "_sample_feedback_ids"


def _is_sample(ctx, subject) -> bool:
    """`RB-122`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    ⚠ **IT IS A GUARD AND NOT A FILTER INSIDE A READ, WHICH IS THE WHOLE
    DIFFERENCE.** A guarded subject is still pinned and still counted
    (`BR-RBS-035`), and `RBS-004.4` draws the control disabled WITH its reason
    rather than hiding it; a row quietly dropped inside `resolve()` is invisible
    on every screen and its guard is a check that can never fire.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per piece of feedback** (`BR-RBS-019`).

    ⚠ **THE UNIT IS THE FEEDBACK ITEM AND NOT THE ACCOUNT.** The card's *subject
    and unit of work* row reads *Contact feedback*: the day's roll-up is what
    lands and each failure is what gets decided, one record row and one savepoint
    each. An account with three bounces is three items and one suppression, and
    the counts say both.

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`). A bounce that arrives while
    the run is going is not in this run's set and is not acted on; the
    fingerprint the executor computes is how a later reader proves the set did
    not move.

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP**, and
    it is not an error. Step 1 says why in a sentence a clerk can read; a
    `resolve()` that raised would turn a designed outcome into a stack trace.
    """
    items = _items(_feedback(ctx))
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        str(one.get("message_id")) for one in items if one.get("is_sample")
    )
    return [
        SubjectRef(
            subject_type="contact_feedback",
            subject_id=str(one.get("message_id")),
            label=(
                f"{CHANNEL_LABELS.get(CHANNEL_FROM_NOTIFICATIONS.get(str(one.get('channel')), ''), 'Other')}"
                f" · {one.get('at') or 'no date'}"
            ),
        )
        for one in items
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Undeliverable contacts",
    kind=models.KIND_ACTION,
    category="data_sync",
    subject_type="contact_feedback",
    unit_of_work="a piece of delivery feedback",
    # ⚠ MANUAL AND SCHEDULE, NOT `feedback.landed` — see the module docstring. A
    # person starts it, and the event is emitted by nothing (`CR-069`).
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Accounts", "Data Hygiene"),
    parameters=(
        Parameter(
            name="channels",
            type=PARAM_ENUM,
            label="Channels",
            default=CHANNEL_EMAIL,
            choices=FALLBACK_ORDER,
        ),
        Parameter(
            name="window",
            type=PARAM_DAYS,
            label="Feedback from the last",
            # `RB-122`'s scope — *the landed feedback, rolled up once a day at
            # 07:00* — and its count line reads **Yesterday**. See `_feedback`
            # for why an unwindowed read re-suppresses for ever.
            default=1,
        ),
        Parameter(
            name="suppress_after_bounces",
            type=PARAM_INTEGER,
            label="Suppress after",
            default=2,
        ),
        Parameter(
            name="suppress_after_returned_letters",
            type=PARAM_INTEGER,
            label="Suppress after, returned letters",
            default=1,
        ),
        Parameter(
            name="retry_attempts",
            type=PARAM_INTEGER,
            label="Soft bounce — retries before it counts",
            # `BR-NOT-005`'s retry ×3, in the units this product holds. The
            # card says *3 days*; `outbound_messages` counts ATTEMPTS and has no
            # age column, and `BR-TEN-043` makes the business date an input
            # rather than a clock a runbook may read. Stated in the step.
            default=3,
        ),
        Parameter(
            name="soft_bounce_window",
            type=PARAM_DAYS,
            label="Soft bounce — retry window",
            default=3,
        ),
        Parameter(
            name="fall_back_to",
            type=PARAM_REF_SETTING,
            label="Fall back to",
            setting_key="notifications.channel_fallback",
        ),
        Parameter(
            name="re_enable_when",
            type=PARAM_REF_SETTING,
            label="Re-enable when",
            # ⚠ **DECLARED, AND THERE IS NOTHING TO RE-ENABLE.** No column
            # records a suppression, so nothing can be lifted and nothing
            # watches a contact for an edit (`DEF-RBS-4331`). It is declared
            # because the card declares it and because a parameter that appears
            # the day the column does is a smaller change than a parameter
            # nobody remembered.
            setting_key="notifications.suppression_re_enable",
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=_is_sample),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_GATHER,
            label=STEP_LABELS[STEP_GATHER],
            mode=MODE_SET,
            run=step_gather_the_landed_feedback,
        ),
        Step(
            key=STEP_CLASSIFY,
            label=STEP_LABELS[STEP_CLASSIFY],
            mode=MODE_SET,
            run=step_classify_each_item,
        ),
        Step(
            key=STEP_SUPPRESSION,
            label=STEP_LABELS[STEP_SUPPRESSION],
            mode=MODE_SET,
            run=step_apply_the_suppression_rule,
        ),
        Step(
            key=STEP_FALLBACK,
            label=STEP_LABELS[STEP_FALLBACK],
            mode=MODE_SET,
            run=step_find_the_next_channel_on_file,
        ),
        # ⚠ THE ONLY PER-RECORD STEP. One item, one savepoint (hard-won law 14),
        # one record row carrying the plan and the outcome together.
        Step(
            key=STEP_SUPPRESS,
            label=STEP_LABELS[STEP_SUPPRESS],
            mode=MODE_PER_RECORD,
            run=step_suppress_and_fall_back,
            writes=True,
        ),
        Step(
            key=STEP_FLAG,
            label=STEP_LABELS[STEP_FLAG],
            mode=MODE_SET,
            run=step_flag_the_address_and_raise_work_items,
            writes=True,
        ),
    ),
    ports=("suppress_channel", "flag_account"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-034 (EP-RBS-05; CR-075 wave Q′)
# generated: 2026-09-06 by the CR-075 wave Q′ integration-runbooks lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_034_undeliverable_contacts.py · pytest tests/test_rbs_sync_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing is suppressed and no account is flagged — `suppress_channel` and `flag_account` bind NO writer because `customers` has no column for either fact (DEF-RBS-4331); no provider adapter writes `bounced` or `failed` on any channel, so the provider half of the feedback is structurally empty and `not_reported` carries the two statuses by name; the soft-bounce window is counted in ATTEMPTS, not days, because `outbound_messages` has an attempt count and no age column; `Re-enable when` is declared with nothing to re-enable
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
