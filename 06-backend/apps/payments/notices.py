# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 (manual reminder + disconnect-notice modals — bulk,
#           queue-writes, notice_history) · US-PAY-018 (plan notices: reminder
#           −3d · missed day+1 · second notice)
#           Screens: S35 · S34 · S21 · S33
# Rules:    BR-NOT-005 (EVERY notice is WRITTEN to the outbound table first —
#           never sent inline; the dispatcher sends) · BR-PAY-017 (manual sends
#           use the same tier ladder, channels and exclusions as the sequence
#           engine, and advance the same state) · BR-PAY-029 (reminder/notice
#           are S34 bulk actions) · BR-PAY-016 (plan notices at tenant-config
#           cadence; ⚠ its "2nd miss VOIDS plan" clause is SUPERSEDED — PO
#           2026-08-11 "nodrop we chase for payments until write off") ·
#           BR-PAY-021 (a missed instalment is judged on the POSTING date) ·
#           BR-CUS-039 (notice tiers/content per A19 §2; certified mail on the
#           final tier; medical-hold accounts excluded) · BR-BIL-007 (the
#           reconnect fee is DISPLAYED from the tenant charge code, read-only) ·
#           BR-TEN-043 (event time is an argument) · CLAUDE.md rule 7
# Change:   CR-048 wave B task B10 — *"the missed payment-plan instalment,
#           the one a utility most needs to send"*. The trigger existed; it
#           pinned a NOTICE-HISTORY type as a template code and keyed every
#           plan notice on the PLAN, so the letter rendered from wording
#           nothing seeds and the second notice deduped into the first.
# Tests:    06-backend/tests/test_us_pay_015_notice_modals.py ·
#           06-backend/tests/test_us_pay_018_plan_notices.py ·
#           06-backend/tests/test_cr048_b6_b10.py (CR-048 B10)
# Impacts:  apps/notifications/services.queue_document (the ONLY writer of the
#           outbound queue — resolved BY NAME, never bypassed) ·
#           apps/notifications/rule_catalog.py (owns the event key this now
#           names) · apps/notifications/seed_templates.py (owns the body it
#           now pins) · apps/payments/dunning.py (asked before every send) ·
#           apps/payments/collections_models.py
# ───────────────────────────────────────────────────────
"""Notices: every one a queue-write, every send AND skip recorded.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides which customers are
told they are about to be disconnected. AI-authored 2026-08-11 under the PO
ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  NOTHING HERE SENDS ANYTHING. IT WRITES QUEUE ROWS. (BR-NOT-005)         ║
╚══════════════════════════════════════════════════════════════════════════╝
There is no SMTP call, no ESP call and no Twilio call in this file and there
must not be one. Every notice goes through
`apps.notifications.services.queue_document` — the ONE write path into
`outbound_messages` (B1, and B2 r16 #7 makes that table the single cross-module
write exception). It is resolved **by name** so payments imports nothing of
notifications', which is the same idiom `apps/billing/delivery_seam.py` uses.

A caller reaching for `OutboundMessage.objects.create` would bypass the print
floor (BR-BIL-036), the idempotency key (rule 6), the recipient resolution and
the audit row — all of which are the point. US-PAY-015 TC-6 and US-PAY-018 TC-7
are that refusal, from the manual modal and from the scheduled job.

════════════════════════════════════════════════════════════════════════════
EVERY SEND *AND EVERY SKIP* IS APPENDED (J4 step-2 contract)
════════════════════════════════════════════════════════════════════════════
A medical hold, a plan-paused ladder, a suppressed address: each is a reason a
customer was NOT told something, and each writes a `notice_history` row with its
reason. A skip that left no trace is a silent exclusion, and the S34 "Notice
history" column would read the same for an account nobody ever chased as for one
deliberately excluded. `record_notice` is the only writer, and the table is
append-only in Postgres.

════════════════════════════════════════════════════════════════════════════
US-PAY-018: THE THIRD PLAN NOTICE IS A SECOND NOTICE, NOT A VOID
════════════════════════════════════════════════════════════════════════════
BR-PAY-016's cadence was *reminder −3 days · missed notice day+1 · **2nd miss
VOIDS the plan***. The PO superseded the third one on 2026-08-11 — *"nodrop we
chase for payments until write off"* — so what remains is a SECOND NOTICE: a
stronger letter, and nothing else happens.

**There is no miss counter here and nothing transitions.** `plans.
outstanding_installments` returns the instalment ROWS that came due and were not
met — facts, computed on demand — and the second notice fires when more than one
of them is outstanding, which is a statement about the customer's position and
not a tally kept against them. No column counts, no status changes, and a test
asserts that ten missed instalments leave the plan ACTIVE with no `missed_count`
attribute anywhere on the model.

What DOES change when a plan falls behind is the dunning PAUSE, and that lives
in `dunning.py`: the plan stays active and the ladder resumes over the arrears
(BR-CUS-043's *"active AND current"*). Notices may still be sent; nothing drops.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import transaction

from apps.payments import billing_seam, dunning, plans, settings_seam
from apps.payments.collections_models import (
    DISCONNECT_TIERS,
    NOTICE_DISCONNECT,
    NOTICE_PLAN_MISSED,
    NOTICE_PLAN_REMINDER,
    NOTICE_PLAN_SECOND,
    NOTICE_REMINDER,
    NOTICE_TYPES,
    OUTCOME_SENT,
    OUTCOME_SKIPPED,
    TIER_FINAL_48_HOUR,
    AccountCollectionState,
    NoticeHistory,
    PaymentPlan,
)
from apps.payments.exceptions import PaymentRuleError
from core import audit
from core import tenancy as core_tenancy

#: The queue, resolved BY NAME. Nothing in this module imports notifications.
QUEUE_MODULE = "notifications"
QUEUE_WRITE = "queue_document"

# ══════════════════════════════════════════════════════════════════════════
# WHICH WORDING EACH DISCONNECT TIER RENDERS FROM — `DEF-PAY-4451`
# ══════════════════════════════════════════════════════════════════════════
# **WHAT WAS WRONG, AND IT IS THE WHOLE LETTER RATHER THAN A FIELD ON IT.**
# `send_disconnect_notices` built its template code as
# `f"{template_code}_{tier}"` — `"disconnect_notice"` plus the tier constant —
# and the tier constants are `first_10_day`, `second_5_day`, `final_48_hour`.
# So it asked for `disconnect_notice_first_10_day`, and the three classes this
# platform seeds are `disconnect_notice_10_day`, `disconnect_notice_5_day` and
# `disconnect_notice_48_hour`. **Not one of the three composed codes has ever
# existed.**
#
# Measured on the seeded utility before the fix: sending the 10-day notice to a
# real debtor queued a row, reported `template_pin_unresolved` naming the whole
# known set, wrote its `notice_history` row, ADVANCED THE ACCOUNT'S TIER — and
# left a queue row that `render_for_dispatch` refuses forever, because the pin
# is stamped at queue time and re-queueing after publishing a template would not
# help either. **The ladder therefore records that a customer was warned, moves
# them one step closer to disconnection, and produces no letter.**
#
# ⚠ **`apps/notifications/notices.py` WROTE THIS EXACT WARNING DOWN ON
# 2026-08-17 AND THIS MODULE WENT ON DOING IT.** `TIER_TO_CLASS`'s own comment:
# *"Written as an explicit map, not a f-string on the tier name: a name-derived
# class would silently invent `disconnect_notice_<anything>` for a tier."* One
# module took the lesson; its sibling, which is the one the S35 modal and
# `ladder.run_ladder` actually call, never heard it.
#
# ⚠ **IT IS ALSO `CR-048` WAVE B TASK B10's FAULT, A SECOND TIME.** That task
# found this module pinning a NOTICE-HISTORY type (`plan_installment_missed`) as
# a template code and fixed it for the plan notices — see `MISSED_TEMPLATE_CODE`
# below, which exists for that reason and says so. The disconnect branch has the
# same disease and was not looked at.
#
# **STRINGS AND NOT SYMBOLS, AND AN EXPLICIT MAP AND NOT A FORMAT.** Payments
# must not import notifications (B1), so these are spelled out here — which is
# precisely why `test_def_pay_4451_disconnect_tiers_name_seeded_wording`
# resolves every one of them against the tenant's own published templates rather
# than trusting this comment.
#: The default value of `send_disconnect_notices(template_code=...)`. Named so
#: the map above is used for the PLATFORM's own wording and a caller that
#: deliberately passes its own prefix still gets the old composition.
DEFAULT_DISCONNECT_PREFIX = "disconnect_notice"

TIER_TEMPLATE_CODES: dict[str, str] = {
    "first_10_day": "disconnect_notice_10_day",
    "second_5_day": "disconnect_notice_5_day",
    "final_48_hour": "disconnect_notice_48_hour",
}

# ── CR-048 wave B task B10 · the missed-instalment message ─────────────────
#: The SET-12 event key, spelled here ONCE. Checked against
#: `rule_catalog.EVENT_KEYS` before it was written down and re-checked by a
#: test, because `queue_document` REFUSES an event this platform cannot fire and
#: the refusal would land inside a nightly plan-notice run.
#:
#: ⚠ Payments must not import notifications (B1), so this is a STRING and not a
#: symbol — which is exactly why the test that pins it exists.
EVENT_PLAN_INSTALMENT_MISSED = "payment_plan_instalment_missed"

#: The template class the missed notice renders from — `seed_templates` plants
#: this body on every tenant and `catalogs.CATALOGS` owns its token whitelist.
#:
#: ⚠ **IT IS NOT `NOTICE_PLAN_MISSED`.** That constant is `plan_installment_
#: missed`, a NOTICE-HISTORY type: it names a row in the regulator's trail, and
#: nothing in the template catalogue has ever declared it. This module pinned it
#: as a template code from 2026-08-11 to 2026-08-30, so every missed-instalment
#: message was queued against wording that does not exist. The two vocabularies
#: look alike and are not the same set; that resemblance is the whole reason the
#: fault survived nineteen days.
MISSED_TEMPLATE_CODE = "plan_notice_missed"

# ── CR-048 wave B task B11 · the REMINDER, the second of "two more plan notices"
#: ⚠ **B10 LEFT THIS ONE BROKEN ON PURPOSE AND SAID SO IN WRITING**, twelve lines
#: down in `send_plan_notices`: *"THE REMINDER IS DELIBERATELY LEFT AS IT WAS,
#: both faults included … adopting it here would take a class out of B9's
#: coverage count that B11 is about to report on."* This is B11 and this is that
#: adoption. Both faults are closed on this commit and they are the same two:
#:
#:  1 · **THE TEMPLATE CODE WAS A NOTICE TYPE** (DEF-2511). The reminder pinned
#:      `template_code=notice_type` — `plan_installment_reminder`, a
#:      `collections_models.NOTICE_TYPES` value naming a row in the regulator's
#:      trail. Nothing in `catalogs.LISTINGS` or `seed_templates.SEEDABLE` has
#:      ever declared that code, so every reminder since 2026-08-11 was queued
#:      against wording that does not exist. The body a customer would have read
#:      is `plan_notice_upcoming`, seeded on every tenant since 2026-08-16.
#:  2 · **EVERY REMINDER SHARED ONE IDEMPOTENCY KEY** (DEF-2512). `source_id` was
#:      the PLAN, so (tenant, "plan", plan_id, "pdf_print", 0) is the same tuple
#:      for the reminder before instalment 1 and the reminder before instalment
#:      12. The second write finds the first row and returns `created=False`: no
#:      error, no gap in the trail, **and a customer on a twelve-month plan is
#:      reminded once.** Keyed on the INSTALMENT, the reminder for instalment 3
#:      cannot collide with the reminder for instalment 4, and a re-run of the
#:      same day still writes nothing.
#:
#: ⚠ Payments must not import notifications (B1), so the event key is a STRING
#: and not a symbol — which is exactly why a test pins it against
#: `rule_catalog.EVENT_KEYS`. `queue_document` REFUSES an event this platform
#: cannot fire, and that refusal would land inside a nightly plan-notice run.
EVENT_PLAN_INSTALMENT_UPCOMING = "payment_plan_instalment_upcoming"

#: The wording the reminder renders from. Seeded on every tenant; its token
#: whitelist is `catalogs.CATALOGS["plan_notice_upcoming"]`, and it is the SAME
#: five tokens the missed notice uses — C-14's own instruction was that the
#: three plan notices reuse one vocabulary, so one context serves all three.
UPCOMING_TEMPLATE_CODE = "plan_notice_upcoming"

#: ⚠⚠ **THE REMINDER CANNOT BE KEYED ON THE INSTALMENT, AND WORKING OUT WHY IS
#: THE WHOLE OF RULE 6 FOR THIS MESSAGE.**
#:
#: The queue's key is (tenant, source_type, source_id, channel, copy_no) — five
#: columns, and **not one of them says WHICH DOCUMENT.** B10 keyed the missed
#: notice on `installment.pk`, correctly: one letter per instalment, and the
#: letter about instalment 3 can no longer collide with the letter about
#: instalment 4. But the reminder and the missed notice are **two different
#: documents about the SAME instalment** — the reminder three days before its
#: due date, the missed notice the day after it went unmet — so keying the
#: reminder on `installment.pk` as well would put both on one tuple, and the
#: missed notice (written four days later) would find the reminder's row and
#: return `created=False`. **The customer would be reminded and then never
#: chased**, with no error, no gap in the trail and nothing to notice. That is
#: DEF-2512 exactly, re-created by the fix for DEF-2512.
#:
#: So the reminder's id NAMES THE OCCASION rather than the row: a version-5 UUID
#: over the instalment's id and the notice type. It is deterministic, so a
#: re-run of the same night finds its own row and writes nothing; it is distinct
#: from `installment.pk`, so the two documents can never share a tuple; and it
#: is distinct per instalment, so twelve reminders are twelve rows.
#:
#: **THE COST IS STATED RATHER THAN HIDDEN:** `source_id` on a reminder row
#: points at NO row in any table, which is a step away from what
#: `models.OutboundMessage.source_id` says it is for. The instalment is still
#: recoverable — `notice_history` records `installment_seq` for every notice on
#: the same pass — and the derivation is one function anyone can run forward.
#: **The durable fix is a column, not a hash**: a queue that carried WHICH
#: DOCUMENT alongside which row would need none of this, and every writer
#: sending two documents about one row has the same problem waiting. Filed.
#:
#: ⚠ Only the reminder derives. The missed and second notices keep
#: `installment.pk` exactly as B10 shipped and tested it — the asymmetry has a
#: reason and it is this: two documents about one row cannot both hold that
#: row's own id, and the one that took it first keeps it.
PLAN_NOTICE_NAMESPACE = uuid.UUID("8f3c1d52-6a41-5f7e-9b20-4c8e1a7d3f60")


def plan_notice_source_id(installment_id: Any, notice_type: str) -> uuid.UUID:
    """The occasion this plan notice is about, as a stable id. See above.

    Published (not `_`-prefixed) because a test asserts the reminder's key and
    a support question — *"where is the row this message points at?"* — is
    answered by running this rather than by reading a comment (hard-won law 1).
    """
    return uuid.uuid5(PLAN_NOTICE_NAMESPACE, f"{installment_id}:{notice_type}")


#: ⚠⚠ **THE LADDER'S OWN NOTICES HAD DEF-2512's BUG AND NOBODY HAD LOOKED
#: (`DEF-PAY-4357`, 2026-09-07).** Every paragraph above works out, for PLAN
#: notices, that the queue's key `(tenant, source_type, source_id, channel,
#: copy_no)` **says nothing about WHICH DOCUMENT** — and then `send_reminders`
#: and `send_disconnect_notices` twenty lines below both passed
#: `source_id=account_id` for a `source_type` of `notice`. So the reminder, the
#: 10-day notice, the 5-day notice and the 48-hour certified final for ONE
#: account are **four different documents on one tuple.**
#:
#: **Measured on a real database, not inferred:** send the 10-day notice, then
#: the 5-day, and `outbound_messages` goes `1 → 1`. The second call finds the
#: first row, returns `created=False`, and **the customer keeps the 10-day
#: letter for ever.** `notice_history` records the 5-day as SENT and
#: `account_collection_state` climbs to `second_5_day`, so every screen in the
#: product agrees the customer was told — and the only row that would ever be
#: printed still carries `disconnect_notice_first_10_day`.
#:
#: **It is worse than the plan-notice version because the ladder is a SEQUENCE.**
#: One account walks four rungs by design, so the collision is not an edge case
#: reachable by an unlucky tenant; it is what happens to every account that is
#: chased more than once.
#:
#: **Why nobody saw it:** `US-PAY-015` TC-1 sends ONE tier to four accounts and
#: counts four rows — four different accounts, four different tuples, green. No
#: case in the suite sent two tiers to one account, which is the only shape that
#: fails. Wave `M`'s dry cycle could not see it either: a dry run reaches no
#: writer at all.
#:
#: The fix is the same one B11 applied to the reminder — **name the occasion,
#: not the row.** The tier is in the id, so four rungs are four tuples; it is
#: deterministic, so a re-run of the same tier finds its own row and writes
#: nothing, which is what `TC-4`'s no-double-send depends on.
LADDER_NOTICE_NAMESPACE = uuid.UUID("2d7b4e91-3c05-5a68-8f14-6b9d2e0a7c53")


def ladder_notice_source_id(
    account_id: Any,
    notice_type: str,
    tier: str | None = None,
    *,
    occasion: date | None = None,
) -> uuid.UUID:
    """The occasion this collections notice is about — account, kind AND tier.

    ⚠ **`tier` IS LOAD-BEARING AND `None` IS A REAL VALUE, NOT A MISSING ONE.**
    A friendly reminder has no tier, so it hashes `""` and gets its own id,
    distinct from every disconnect tier. Dropping the tier from the string would
    put the whole disconnect sequence back on one tuple, which is the defect
    this exists to close.

    ⚠ **`occasion` — THE REMINDER'S BUSINESS DATE (`DEF-PAY-10651`).** Without
    it a reminder's id was the account and the kind and nothing else, so the
    SECOND cycle's reminder — next month's debt, or the restart after a bounced
    cheque (OQ-133) — found the first cycle's row, wrote nothing, and was
    reported as sent. With the date in the id the same day twice is one
    reminder (rule 6) and another day is another document. Omitted, the string
    is byte-identical to what it always was, so every disconnect tier keeps its
    id.
    """
    suffix = f":{occasion.isoformat()}" if occasion is not None else ""
    return uuid.uuid5(LADDER_NOTICE_NAMESPACE, f"{account_id}:{notice_type}:{tier or ''}{suffix}")


#: BR-PAY-016's cadence defaults. **Config, not constants** (US-PAY-018 TC-6:
#: *"defaults are config, not constants"*) — they are the seeded values of the
#: tenant plan-notice settings and every function takes them as arguments. The
#: settings themselves live in tenancy (S66) and are NOT duplicated here.
DEFAULT_REMINDER_DAYS_BEFORE = 3
DEFAULT_MISSED_NOTICE_DAY_AFTER = 1

#: Skip reasons. CODES, because the S34 column and the collections report group
#: on them and a screen cannot group on a sentence.
SKIP_MEDICAL_HOLD = "medical_hold"
SKIP_TIER_ALREADY_SENT = "tier_already_sent"
SKIP_PLAN_PAUSE = "collections_paused_by_active_plan"
#: `DEF-PAY-10651` — the friendly reminder's own reasons. The first is
#: `ladder.SKIP_ALREADY_NOTICED_TODAY`'s spelling (one word for one fact); the
#: other five are `notifications.past_due_reminder.REASONS`.
SKIP_ALREADY_NOTICED_TODAY = "already_noticed_today"
SKIP_REMINDER_RULE_OFF = "rule_off"
SKIP_REMINDER_NO_CONTACT = "no_contact"
SKIP_REMINDER_NO_SMS_CONSENT = "no_sms_consent"
SKIP_REMINDER_TEMPLATE_MISSING = "template_missing"
SKIP_REMINDER_QUEUE_PROBLEM = "queue_problem"


@dataclass(frozen=True)
class _Pin:
    """The template pin `queue_document` reads, in payments' own vocabulary.

    Structurally the notifications `TemplatePin` and deliberately NOT an import
    of it: the seam is resolved by name and stays one-way, so payments carries
    no dependency on another module's dataclass. A notice needs only the CODE —
    `PIN_REQUIRED_SOURCES` there is `invoice` alone, because BR-BIL-026's
    version pin is a rule about BILLS.
    """

    code: str
    template_id: Any = None
    version: int | None = None
    language: str | None = None


@dataclass(frozen=True)
class NoticeOutcome:
    """One account's result from one bulk send."""

    account_id: str
    outcome: str
    channels: tuple[str, ...] = ()
    skip_reason: str | None = None
    queued_message_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BulkNoticeResult:
    """ "Sent N ✓" — and the accounts behind both numbers (IS-6, TC-1/TC-2)."""

    notice_type: str
    tier: str | None
    sent: tuple[NoticeOutcome, ...] = ()
    skipped: tuple[NoticeOutcome, ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def toast(self) -> str:
        return f"Sent {len(self.sent)} ✓" + (
            f" · {len(self.skipped)} skipped" if self.skipped else ""
        )


def _tenant_id() -> Any:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _queue() -> Any:
    """`apps.notifications.services.queue_document`, or None while unwired."""
    try:
        module = import_module(f"apps.{QUEUE_MODULE}.services")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(module, QUEUE_WRITE, None)
    return found if callable(found) else None


def record_notice(
    *,
    account_id: Any,
    notice_type: str,
    outcome: str,
    on_date: date,
    tier: str | None = None,
    channel: str | None = None,
    skip_reason: str | None = None,
    outbound_message_id: Any = None,
    plan: PaymentPlan | None = None,
    detail: dict[str, Any] | None = None,
    actor: Any = None,
) -> NoticeHistory:
    """The ONLY writer of `notice_history`. Append-only, sends and skips alike.

    `on_date` is the business date and is an argument, never a clock
    (BR-TEN-043): a job re-run for last Tuesday records last Tuesday.
    """
    if notice_type not in NOTICE_TYPES:
        raise PaymentRuleError(
            f"unknown notice type {notice_type!r}; this module writes "
            f"{', '.join(NOTICE_TYPES)}. A history row nothing recognises is a row no "
            "screen will ever group and no report will ever count.",
            br_ref="BR-PAY-017",
        )
    if outcome == OUTCOME_SKIPPED and not skip_reason:
        raise PaymentRuleError(
            "a skipped notice records WHY it was skipped (J4 step 2). A skip with no "
            "reason is indistinguishable from an account nobody ever chased.",
            br_ref="BR-PAY-017",
        )
    return NoticeHistory.objects.create(
        tenant_id=_tenant_id(),
        account_id=account_id,
        plan=plan,
        notice_type=notice_type,
        tier=tier,
        channel=channel,
        outcome=outcome,
        skip_reason=skip_reason,
        outbound_message_id=outbound_message_id,
        detail=dict(detail or {}),
        actor_id=getattr(actor, "id", None),
        occurred_on=on_date,
    )


def _notice_history_queryset(
    *,
    account_id: Any = None,
    notice_type: str | None = None,
    tier: str | None = None,
    outcome: str | None = None,
):
    """The filtered, ordered `notice_history` read — LAZY, and sliced by nobody here.

    ⚠ **EXTRACTED 2026-09-19 BY THE `DEF-NOT-5750` LANE.** Every filter and the
    ordering below were `notice_history_for`'s and are unchanged, character for
    character; what changed is that they are now expressed ONCE and three
    published reads stand on them, so a fourth filter cannot arrive on the list
    and be missing from the count. A list and its own total disagreeing about
    which rows exist is a worse defect than the one that lane was fixing.

    PRIVATE. It returns payments' own `QuerySet`, and no other module may hold
    one (B1 / BR-TEN-013): `notice_history_page` and `notice_history_count`
    below are what crosses the boundary, and they hand back dicts and an int.

    `-occurred_on` is the BUSINESS date and `-created_at` breaks its ties,
    because a bulk run of 1,200 letters shares one business date and a list
    that reordered itself between two reads is a list nobody trusts. **The
    ordering is load-bearing now in a way it was not before**: a page taken in
    SQL over an unstable order shows the same notice on page 1 and page 2 and
    hides another entirely.

    Tenant scoping is the manager's (`_tenant_id()` under RLS FORCE, hard rule
    1). No caller can widen it — there is no tenant parameter to pass.
    """
    rows = NoticeHistory.objects.filter(tenant_id=_tenant_id())
    if account_id is not None:
        rows = rows.filter(account_id=account_id)
    if notice_type:
        rows = rows.filter(notice_type=notice_type)
    if tier:
        rows = rows.filter(tier=tier)
    if outcome:
        rows = rows.filter(outcome=outcome)
    return rows.order_by("-occurred_on", "-created_at")


def notice_history_row(row: NoticeHistory) -> dict[str, Any]:
    """ONE `notice_history` row as the published dict — the shape every reader gets.

    ⚠ **EXTRACTED 2026-09-19 (`DEF-NOT-5750`) AND NOT ONE MEMBER MOVED.** It was
    the comprehension body inside `notice_history_for`; it is a function so that
    the paged read and the whole-account read cannot drift into serving two
    shapes of the same row.
    """
    return {
        "id": str(row.pk),
        "account_id": str(row.account_id),
        "notice_type": row.notice_type,
        "tier": row.tier,
        "channel": row.channel,
        "outcome": row.outcome,
        "skip_reason": row.skip_reason,
        "outbound_message_id": (str(row.outbound_message_id) if row.outbound_message_id else None),
        # The generator's own detail payload, forwarded whole rather than
        # cherry-picked: `certified_mail`, `cut_date`, `template_version`
        # and `reconnect_fee` all live in it (see
        # `apps.notifications.notices.HistoryAppend`), and a read that
        # picked three of the four would silently drop the fourth the day a
        # generator started writing it.
        "detail": dict(row.detail or {}),
        "occurred_on": row.occurred_on.isoformat() if row.occurred_on else None,
        "actor_id": str(row.actor_id) if row.actor_id else None,
    }


def notice_history_count(
    *,
    account_id: Any = None,
    notice_type: str | None = None,
    tier: str | None = None,
    outcome: str | None = None,
) -> int:
    """HOW MANY notices this filter matches — a `COUNT(*)`, never a built list.

    ⚠ **ADDED 2026-09-19 (`DEF-NOT-5750`), AND IT IS HALF OF WHY THE CAP COULD
    GO.** `GET /notices` used to serve a `count` that was the length of what had
    already been built — so with a 2,000-row ceiling on the build, `count` was a
    FLOOR rather than a total and the response had to say so. This answers the
    question the database can answer cheaply, so the total is a total again.

    PUBLISHED, because `apps/notifications/payments_seam.py` resolves it by name
    (B1): the table is payments' and the count is taken here, in the module that
    owns it, under its own tenant scope.
    """
    return _notice_history_queryset(
        account_id=account_id,
        notice_type=notice_type,
        tier=tier,
        outcome=outcome,
    ).count()


def notice_history_page(
    *,
    offset: int = 0,
    limit: int,
    account_id: Any = None,
    notice_type: str | None = None,
    tier: str | None = None,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    """ONE PAGE of the record, taken in the DATABASE — `LIMIT`/`OFFSET`, never in Python.

    ⚠ **ADDED 2026-09-19 (`DEF-NOT-5750`) AND IT IS THE OTHER HALF.** Until
    today `GET /notices` asked for 2,000 rows, built 2,000 dicts and let DRF
    slice fifty of them — so **the 2,001st notice was unreachable on every page
    of the list**, which `NFR-5` forbids outright and which a single dunning
    cycle over 40,000 accounts passes in one night. The cap could not simply be
    deleted: without a page in the SQL, deleting it converts a bounded 2,000-row
    build into an UNBOUNDED one, which is a worse defect than the one it fixes.
    So the cap and the page moved together, and this is where the page lands.

    `limit` IS A PAGE SIZE AND NOT A CAP, which is the whole distinction `NFR-5`
    turns on: it is required rather than defaulted, it is the size of the window
    the caller asked for, and `offset` reaches every row behind it. There is no
    number here that any row can be beyond.

    ⚠ **NEGATIVE OR ZERO `limit` RETURNS `[]` AND ISSUES NO QUERY.** Django
    refuses a negative slice bound and an empty page is a real state (a filter
    that matches nothing), so it is answered rather than raised.
    """
    if limit <= 0:
        return []
    start = max(int(offset), 0)
    rows = _notice_history_queryset(
        account_id=account_id,
        notice_type=notice_type,
        tier=tier,
        outcome=outcome,
    )
    return [notice_history_row(row) for row in rows[start : start + int(limit)]]


def notice_history_for(
    *,
    account_id: Any = None,
    notice_type: str | None = None,
    tier: str | None = None,
    outcome: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """THE PUBLISHED READ of `notice_history` — the regulator's record.

    ⚠ ADDED 2026-08-16 by the DEF-128 lane, and it is the half that made a
    notice history reachable at all. `record_notice` above has been the ONLY
    writer of this table since 2026-08-11 and **nothing published a read**, so
    every notice this platform generated — every disconnect letter, every skip
    for a medical hold, every certified 48-hour final — was recorded in a table
    no surface could open. This is the record a utility shows a regulator when a
    customer says they were never told, and the answer to "show me" was a
    database console.

    IT IS PUBLISHED HERE, IN THE OWNING MODULE, ON PURPOSE. B1 forbids another
    module touching this table's ORM; `apps/notifications/payments_seam.py`
    resolves this function by NAME at call time and serves it on `GET /notices`.
    The notice CONTENT is notifications' and the notice RECORD is payments' —
    the boundary the whole notice flow is built around (see
    `apps/notifications/notices.py`'s box), and it holds in both directions.

    ⚠ **THIS IS NO LONGER WHAT `GET /notices` CALLS, AND THE DIFFERENCE MATTERS
    (`DEF-NOT-5750`, 2026-09-19).** `limit` here is a *last N on one subject*
    bound, for a PANEL — `collections_read.collection_context` draws the last
    100 notices on a single account beside its ladder. A LIST, which has to be
    able to reach every row, asks `notice_history_page` + `notice_history_count`
    instead, and those have no ceiling at all. **Do not reach for this function
    to serve a list**: a caller that pages by raising `limit` is re-creating the
    exact defect, because the rows beyond it stay unreachable however high it is
    set. It is expressed in terms of `notice_history_page` below so the two can
    never serve different shapes of the same row.

    Rows come back oldest-LAST — newest first — because "what have we told them
    lately?" is the question a clerk on the phone is actually asking.

    **SENDS AND SKIPS BOTH.** J4 step 2 requires every skip on the trail, and a
    read that quietly filtered them would make an account excluded for a medical
    hold indistinguishable from one nobody ever chased. `outcome` narrows it for
    a caller that wants one or the other, and defaults to neither.

    Tenant scoping is the manager's (`_tenant_id()` under RLS FORCE, hard rule
    1). No caller can widen it — there is no tenant parameter to pass.
    """
    return notice_history_page(
        offset=0,
        limit=limit,
        account_id=account_id,
        notice_type=notice_type,
        tier=tier,
        outcome=outcome,
    )


def _queue_for(
    *,
    account_id: Any,
    source_type: str,
    source_id: Any,
    template_code: str,
    channels: tuple[str, ...],
    actor: Any,
    event_key: str | None = None,
    render_context: dict[str, Any] | None = None,
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    """One queue-write, or an honest problem row. Never an inline send.

    ⚠ `event_key` ADDED 2026-08-30 (CR-048 wave B task B10). Name a SET-12 event
    and this utility's own notification rule is read on the way to the queue —
    switching *Payment plan · instalment missed* off on Settings → Notifications
    stops the email, and BR-NOT-024's print floor keeps the letter. **Omit it
    and nothing changes**: no rule is read and the write is byte-identical to
    what shipped before, which is what keeps every other caller in this module
    meaning exactly what it meant.
    """
    queue = _queue()
    if queue is None:  # pragma: no cover - notifications ships in this repo
        return (), (
            {
                "code": "queue_unpublished",
                "br_ref": "BR-NOT-005",
                "detail": f"apps.{QUEUE_MODULE}.services.{QUEUE_WRITE} is not published, "
                "so nothing was queued and nothing was sent. A notice this module could "
                "not queue is reported, never delivered by another route.",
            },
        )
    written = queue(
        source_type=source_type,
        source_id=source_id,
        channels=channels,
        template=_Pin(code=template_code),
        account_id=account_id,
        actor=actor,
        event_key=event_key,
        render_context=render_context,
    )
    return tuple(message.id for message in written.messages), tuple(written.problems)


# ══════════════════════════════════════════════════════════════════════════
# THE FIGURES ON A COLLECTIONS LETTER — ADDED 2026-09-07 (`DEF-PAY-4450`)
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THE DEFECT WAS.** `send_reminders` and `send_disconnect_notices` named
# no merge values, so every letter this ladder produced read:
#
#     ——
#     ——
#     Account ——
#     PAST-DUE NOTICE
#     Your account is past due in the amount of ——. Please pay by —— (10 days)
#     to avoid service interruption.
#
# — on a document that is the legal step before switching somebody's water off.
# `DEF-PAY-4409`'s exact shape: the template is right, the renderer is right,
# and the caller never said what the letter is about.
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  THE BALANCE IS THE BOARD'S OWN FIGURE, AND THAT IS THE POINT.           ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# `billing_seam.outstanding_positions` is what `collections_read.ladder_board`
# sums to draw the number a clerk reads before pressing *Send*. Taking the same
# read means the letter and the screen that authorised it cannot state
# different amounts — which is `DEF-127`'s lesson (`accounts.balance` is a cache
# nothing writes, and serving it once told a customer owing $108.88 that they
# owed nothing).
#
# **AND IT IS ONE READ FOR THE WHOLE BATCH, NOT ONE PER LETTER.** These two
# functions are bulk senders reached from the S35 modal over a selection and
# from `ladder.run_ladder` over a night's work. `outstanding_positions` answers
# a whole account list in TWO queries and the two customers reads beside it are
# one each, so a 400-account run costs four reads rather than 1,600.
#
# **WHAT IS DELIBERATELY ABSENT, each named so the guard reports a gap rather
# than an oversight, and each a different KIND of absence:**
#   * `{state_puc_ref}` — the commission reference. `rights_footer.py` records
#     that NOTHING IN THIS PRODUCT STORES ONE; `notifications.notices` takes it
#     as a caller argument for the same reason. A fabricated regulatory citation
#     on a disconnection notice is the worst thing on this page.
#   * `{late_fee}`, `{stage_day}`, `{account}` — the dunning class's tokens, and
#     that class is not what this ladder pins (see `send_reminders`).


def _batch_facts(account_ids: tuple[Any, ...]) -> dict[str, dict[str, Any]]:
    """Per account: the balance from the books, the number, and the name.

    THREE READS FOR THE WHOLE BATCH, all through reads the owning module
    published (B1) and all of them ones payments already makes for the
    collections board. Returns `{}` for an account nothing could be read for —
    every key is then stated with no value and the line prints as a named
    absence, which is true, rather than as a zero, which a customer would act
    on.

    Never raises: a figure that cannot be read must not stop a legal notice the
    ladder has already decided to send.
    """
    ids = [str(account_id) for account_id in account_ids]
    facts: dict[str, dict[str, Any]] = {account_id: {} for account_id in ids}
    if not ids:
        return facts
    try:
        positions, _ = billing_seam.outstanding_positions(account_ids=account_ids)
        for position in positions:
            entry = facts.setdefault(str(position.account_id), {})
            entry["balance"] = position.balance
            entry["oldest_due_on"] = position.oldest_due_on
    except Exception:  # noqa: BLE001 — a figure must not stop a notice
        pass
    try:
        queryset = billing_seam._resolve("customers", "account_queryset")
        if queryset is not None:
            accounts = list(queryset().filter(pk__in=ids))
            # ⚠ **WHERE THE SERVICE IS — CLAUDE.md hard rule 8's WALK, done by
            # the module that owns it.** `premise_cells_for` resolves an
            # account → its unit → its premises (or straight to the premises for
            # an owner's account, `BR-CUS-1010`) through customers' own metering
            # seam, in TWO queries for the whole batch. Payments declares no
            # address column, reads no premises table and composes no address
            # string: it asks the owner for the answer, exactly as it asks
            # billing for the balance.
            #
            # The cell is `"<address> · <unit label>"` where a unit exists, which
            # is what a disconnection notice has to name — the premises alone
            # would send the letter to a building rather than to the flat whose
            # water is being switched off.
            cells = billing_seam._resolve("customers", "premise_cells_for")
            if cells is not None:
                for account_id, (_label, address) in (cells(accounts) or {}).items():
                    facts.setdefault(str(account_id), {})["service_address"] = address or None
            for account in accounts:
                # `account_no` is a `TextField()`, so an unnumbered account holds
                # `""` and not NULL — `collections_read._account_no` normalises
                # the same way and for the same reason (B14 rule 31: where
                # neither a number nor a name exists the field says so, and an
                # empty string would slip past every `or None` downstream).
                facts.setdefault(str(account.pk), {})["account_no"] = (
                    str(account.account_no).strip() or None
                )
        names = billing_seam._resolve("customers", "primary_contact_names_for")
        if names is not None:
            for account_id, name in (names(ids) or {}).items():
                facts.setdefault(str(account_id), {})["customer_name"] = name or None
    except Exception:  # noqa: BLE001 — a name must not stop a notice
        pass
    return facts


def _notice_context(
    facts: dict[str, Any],
    *,
    cut_date: date | None = None,
    reconnect_fee: Decimal | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """Every token the collections wordings can name, for ONE account.

    The union of the three disconnect tiers and the reminder, so one context
    serves whichever tier this call is sending — a token a body does not use is
    never substituted.

    ⚠ **`{pay_by_date}` IS THE CUT DATE, and this is the one judgment here.**
    The 10-day body reads *"Please pay by {pay_by_date} (10 days) to avoid
    service interruption"* and carries no `{cut_date}` at all; tiers 2 and 3
    carry `{cut_date}` and no `{pay_by_date}`. This product holds ONE date for
    that ladder step — `ladder._send` computes it as `as_of + 10 days` and hands
    it in as `cut_date` — and the day service stops IS the day by which paying
    avoids it. Two spellings of one date, so both are stated with the same
    value. The alternative was a blank where the deadline goes on a legal
    notice, which is worse than a defensible reading. Recorded in the decision
    log with this reasoning; if a utility needs a grace day between the two,
    that is a second stored date and a ruling.

    ⚠ **`{48h}` COMES FROM THE TENANT'S OWN LADDER SETTING, NEVER THE CONSTANT
    48.** BR-REP-016's discipline — *"dunning day numbers render from the
    tenant's cadence config, never constants"* — applied to the one figure that
    is in hours. A utility whose final notice is 72 hours has that in
    `final_notice_hours` and its letter must say so.
    """
    try:
        hours = settings_seam.final_notice_hours()
    except Exception:  # noqa: BLE001 — an unreadable setting is a named absence
        hours = None
    balance = facts.get("balance")
    oldest_due_on = facts.get("oldest_due_on")
    return {
        # ── the books ───────────────────────────────────────────────────────
        "balance": balance if isinstance(balance, Decimal) else None,
        # ── who it is for ───────────────────────────────────────────────────
        "customer_name": facts.get("customer_name"),
        "first_name": (
            str(facts["customer_name"]).split()[0] if facts.get("customer_name") else None
        ),
        "account_no": facts.get("account_no"),
        # `DEF-PAY-10651` — the printed reminder letter (`dunning`) quotes A13,
        # whose token for the same number is `{account}`.
        "account": facts.get("account_no"),
        # ── the deadline ────────────────────────────────────────────────────
        "cut_date": cut_date,
        "pay_by_date": cut_date,
        "48h": (f"{hours} hours" if hours is not None else None),
        "reconnect_fee": reconnect_fee,
        "days_late": (
            (on_date - oldest_due_on).days
            if on_date is not None and isinstance(oldest_due_on, date)
            else None
        ),
        # ── where the service is, walked to the premises (hard rule 8) ──────
        "service_address": facts.get("service_address"),
        # ── stated with no value: see the block comment above ───────────────
        "state_puc_ref": None,
    }


#: Where the past-due reminder's channels are decided — `DEF-PAY-10651`.
#: Resolved BY NAME at call time, like the queue above.
REMINDER_MODULE = "notifications.past_due_reminder"
REMINDER_WRITE = "queue_past_due_reminder"


def _reminder_writer() -> Any:
    try:
        module = import_module(f"apps.{REMINDER_MODULE}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(module, REMINDER_WRITE, None)
    return found if callable(found) else None


def send_reminders(
    *,
    account_ids: tuple[Any, ...],
    on_date: date,
    medical_hold_account_ids: tuple[Any, ...] = (),
    actor: Any = None,
) -> BulkNoticeResult:
    """The friendly past-due reminder — ladder rung 1 — for a selection.

    ⚠⚠ **REWRITTEN 2026-10-29 (`DEF-PAY-10651`, PO *"1A 2A 3A 4B, start"*).**
    It took `channels` (defaulting to paper), `tone` and `template_code`, and
    queued `f"{template_code}_{tone}"` = `collections_reminder_friendly` — a
    class catalogued NOWHERE, so the row could never render — then recorded
    **Sent** for every channel it had been handed whatever was queued, and the
    ladder advanced on it. The nightly run passed no channels at all, so every
    automatic reminder was one unrenderable paper row and a history that said
    the customer had been told.

    **The channels are no longer the caller's to choose.** The Settings rule
    `past_due_reminder` and the customer's contacts and consent decide them, in
    `apps.notifications.past_due_reminder` (resolved by name): email if the
    account has an address, SMS only with SMS consent, the printed `dunning`
    letter only when nothing digital can reach them, nothing at all when the
    rule is off. `tone` is gone with the synthesised code — the friendly
    reminder has ONE wording set; firm and final were always disconnect tiers
    (`notifications.notices.TONE_TO_STEP`).

    **History says Sent per channel ONLY for a message THIS call queued.**
    Every channel the rule had on and that did not go gets a SKIPPED row with
    its reason (`rule_off`, `no_contact`, `no_sms_consent`, `template_missing`,
    `queue_problem`); the same reminder again the same day is
    `already_noticed_today` and writes no second Sent. An account with no
    message queued is reported in `skipped`, never in `sent` — which is what
    `ladder.run_ladder` and `ladder.step_one` read to decide the rung was NOT
    taken.

    Medical-hold accounts are SKIPPED with the skip recorded (A15 via
    BR-CUS-039); the hold is passed IN — a clinical fact customers owns.
    """
    writer = _reminder_writer()
    held = {str(account_id) for account_id in medical_hold_account_ids}
    sent: list[NoticeOutcome] = []
    skipped: list[NoticeOutcome] = []
    problems: list[dict[str, Any]] = []
    # `DEF-PAY-4450` — ONE read for the whole selection, before the loop.
    batch = _batch_facts(tuple(account_ids))
    for account_id in account_ids:
        if str(account_id) in held:
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_REMINDER,
                outcome=OUTCOME_SKIPPED,
                skip_reason=SKIP_MEDICAL_HOLD,
                on_date=on_date,
                actor=actor,
            )
            skipped.append(
                NoticeOutcome(
                    account_id=str(account_id),
                    outcome=OUTCOME_SKIPPED,
                    skip_reason=SKIP_MEDICAL_HOLD,
                )
            )
            continue
        if writer is None:  # pragma: no cover - notifications ships in this repo
            problems.append(
                {
                    "code": "queue_unpublished",
                    "br_ref": "BR-NOT-005",
                    "detail": f"apps.{REMINDER_MODULE}.{REMINDER_WRITE} is not published, so "
                    "nothing was queued and nothing was sent.",
                }
            )
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_REMINDER,
                outcome=OUTCOME_SKIPPED,
                skip_reason=SKIP_REMINDER_QUEUE_PROBLEM,
                on_date=on_date,
                actor=actor,
            )
            skipped.append(
                NoticeOutcome(
                    account_id=str(account_id),
                    outcome=OUTCOME_SKIPPED,
                    skip_reason=SKIP_REMINDER_QUEUE_PROBLEM,
                )
            )
            continue
        write = writer(
            account_id=account_id,
            # ⚠ NOT `account_id` — `DEF-PAY-4357`; and the DATE is in it —
            # `DEF-PAY-10651`. See `ladder_notice_source_id`.
            source_id=ladder_notice_source_id(account_id, NOTICE_REMINDER, occasion=on_date),
            # `DEF-PAY-4450` — what this reminder is ABOUT.
            render_context=_notice_context(batch.get(str(account_id), {}), on_date=on_date),
            actor=actor,
            on_date=on_date,
        )
        problems.extend(write.problems)
        queued = dict(write.queued)
        for channel, message_ids in queued.items():
            for message_id in message_ids:
                record_notice(
                    account_id=account_id,
                    notice_type=NOTICE_REMINDER,
                    outcome=OUTCOME_SENT,
                    channel=channel,
                    on_date=on_date,
                    outbound_message_id=message_id,
                    actor=actor,
                )
        for channel, why in write.not_sent.items():
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_REMINDER,
                outcome=OUTCOME_SKIPPED,
                skip_reason=why,
                channel=channel,
                on_date=on_date,
                actor=actor,
            )
        if queued:
            sent.append(
                NoticeOutcome(
                    account_id=str(account_id),
                    outcome=OUTCOME_SENT,
                    channels=tuple(queued),
                    queued_message_ids=tuple(
                        message_id for ids in queued.values() for message_id in ids
                    ),
                )
            )
            continue
        if write.already:
            # The same reminder, the same day: its rows exist and were recorded
            # when they were written. Said once, never a second Sent (rule 6).
            reason = SKIP_ALREADY_NOTICED_TODAY
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_REMINDER,
                outcome=OUTCOME_SKIPPED,
                skip_reason=reason,
                on_date=on_date,
                actor=actor,
            )
        else:
            # Nothing queued: the whole-reminder reason (`rule_off`) when there
            # is one, else the first channel's.
            reason = write.not_sent.get(None) or next(
                iter(write.not_sent.values()), SKIP_REMINDER_QUEUE_PROBLEM
            )
        skipped.append(
            NoticeOutcome(account_id=str(account_id), outcome=OUTCOME_SKIPPED, skip_reason=reason)
        )
    return BulkNoticeResult(
        notice_type=NOTICE_REMINDER,
        tier=None,
        sent=tuple(sent),
        skipped=tuple(skipped),
        problems=tuple(problems),
    )


def send_disconnect_notices(
    *,
    account_ids: tuple[Any, ...],
    tier: str,
    cut_date: date,
    on_date: date,
    channels: tuple[str, ...] = ("pdf_print",),
    template_code: str = DEFAULT_DISCONNECT_PREFIX,
    medical_hold_account_ids: tuple[Any, ...] = (),
    reconnect_fee: Decimal | None = None,
    actor: Any = None,
) -> BulkNoticeResult:
    """S35's *Send disconnect notices* (TC-2/TC-3/TC-4).

    Four rules meet on one modal and each is enforced here rather than on the
    screen:

    * **Certified mail is FORCED on the final tier** (A19 rule 3 / BR-CUS-039),
      and SMS never stands alone — a 48-hour final notice delivered only by text
      is not a notice.
    * **Medical-hold accounts are skipped** with the skip recorded (A15).
    * **A tier never double-sends** (TC-4): the manual modal and the automatic
      engine advance the SAME `account_collection_state`, so an account the
      ladder already put at tier 2 is skipped with "tier already sent" and the
      date it went.
    * **An active, current plan blocks disconnect** (BR-CUS-043, US-PAY-019
      TC-6) — server-side, whatever the UI offers.

    `reconnect_fee` is DISPLAY ONLY and is passed in from the tenant's RECONN
    charge code (BR-BIL-007). It is not read here and not defaulted: a fee this
    module invented would be printed on a legal notice.
    """
    if tier not in DISCONNECT_TIERS:
        raise PaymentRuleError(
            f"unknown disconnect tier {tier!r}; A19 §2 defines {', '.join(DISCONNECT_TIERS)}.",
            br_ref="BR-CUS-039",
        )
    if not channels:
        raise PaymentRuleError(
            "choose at least one channel (US-PAY-015 TC-5).", br_ref="BR-NOT-005"
        )
    certified = tier == TIER_FINAL_48_HOUR
    if certified and tuple(channels) == ("sms",):
        raise PaymentRuleError(
            "the 48-hour final notice requires certified mail and SMS never stands alone "
            "(A19 rule 3 / BR-CUS-039). A disconnection notice delivered only by text is "
            "not a notice a utility can rely on.",
            br_ref="BR-CUS-039",
        )
    held = {str(account_id) for account_id in medical_hold_account_ids}
    sent: list[NoticeOutcome] = []
    skipped: list[NoticeOutcome] = []
    problems: list[dict[str, Any]] = []
    # `DEF-PAY-4450` — ONE read for the whole selection, before the loop.
    batch = _batch_facts(tuple(account_ids))
    for account_id in account_ids:
        skip_reason = None
        if str(account_id) in held:
            skip_reason = SKIP_MEDICAL_HOLD
        else:
            blocked, why = dunning.disconnect_blocked(account_id, as_of=on_date)
            if blocked:
                skip_reason = SKIP_PLAN_PAUSE
                problems.append({"code": SKIP_PLAN_PAUSE, "br_ref": "BR-CUS-043", "detail": why})
            elif _tier_already_sent(account_id, tier=tier):
                skip_reason = SKIP_TIER_ALREADY_SENT
        if skip_reason:
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_DISCONNECT,
                outcome=OUTCOME_SKIPPED,
                tier=tier,
                skip_reason=skip_reason,
                on_date=on_date,
                detail={"cut_date": cut_date.isoformat()},
                actor=actor,
            )
            skipped.append(
                NoticeOutcome(
                    account_id=str(account_id), outcome=OUTCOME_SKIPPED, skip_reason=skip_reason
                )
            )
            continue
        message_ids, queue_problems = _queue_for(
            account_id=account_id,
            source_type="notice",
            # ⚠ NOT `account_id` — `DEF-PAY-4357`. The TIER is in the id, so the
            # 10-day notice and the 5-day notice are two rows and not one.
            source_id=ladder_notice_source_id(account_id, NOTICE_DISCONNECT, tier),
            # `DEF-PAY-4451` — THE MAP, never `f"{template_code}_{tier}"`. See
            # `TIER_TEMPLATE_CODES` for what the format string composed, why not
            # one of the three codes it produced has ever existed, and why the
            # sibling module wrote this warning down three weeks before this.
            # `template_code` is still honoured as the PREFIX a caller may
            # override, so a tenant on its own wording set is unaffected.
            template_code=(
                TIER_TEMPLATE_CODES[tier]
                if template_code == DEFAULT_DISCONNECT_PREFIX
                else f"{template_code}_{tier}"
            ),
            channels=channels,
            actor=actor,
            # `DEF-PAY-4450` — the amount, the deadline and the reconnect fee.
            # `reconnect_fee` is DISPLAY ONLY and is passed straight through: it
            # arrives from the tenant's RECONN charge code and is never read or
            # defaulted here (BR-BIL-007), so an absent fee stays absent on the
            # letter rather than printing as 0.00.
            render_context=_notice_context(
                batch.get(str(account_id), {}),
                cut_date=cut_date,
                reconnect_fee=reconnect_fee,
                on_date=on_date,
            ),
        )
        problems.extend(queue_problems)
        for channel in channels:
            record_notice(
                account_id=account_id,
                notice_type=NOTICE_DISCONNECT,
                outcome=OUTCOME_SENT,
                tier=tier,
                channel=channel,
                on_date=on_date,
                detail={
                    "cut_date": cut_date.isoformat(),
                    "certified_mail": certified,
                    # BR-BIL-007 — shown, never applied, and never invented: an
                    # absent fee is reported as absent rather than printed as 0.
                    "reconnect_fee": str(reconnect_fee) if reconnect_fee is not None else None,
                },
                actor=actor,
            )
        _advance_tier(account_id, tier=tier, on_date=on_date)
        sent.append(
            NoticeOutcome(
                account_id=str(account_id),
                outcome=OUTCOME_SENT,
                channels=tuple(channels),
                queued_message_ids=message_ids,
            )
        )
    if reconnect_fee is None:
        problems.append(
            {
                "code": "reconnect_fee_unavailable",
                "br_ref": "BR-BIL-007",
                "detail": "no reconnect fee was supplied, so the notice carries none. The "
                "figure comes from the tenant's RECONN charge code and is DISPLAY-ONLY; "
                "this module does not read rating's charges and will not print a fee "
                "nobody configured.",
            }
        )
    audit.money_action(
        actor,
        "notice.sent",
        "notice_history",
        None,
        after={
            "notice_type": NOTICE_DISCONNECT,
            "tier": tier,
            "sent": len(sent),
            "skipped": len(skipped),
            "cut_date": cut_date.isoformat(),
            "certified_mail": certified,
        },
    )
    return BulkNoticeResult(
        notice_type=NOTICE_DISCONNECT,
        tier=tier,
        sent=tuple(sent),
        skipped=tuple(skipped),
        problems=tuple(problems),
    )


def _tier_already_sent(account_id: Any, *, tier: str) -> bool:
    state = AccountCollectionState.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id
    ).first()
    return bool(state and state.tier == tier)


@transaction.atomic
def _advance_tier(account_id: Any, *, tier: str, on_date: date) -> None:
    """The ONE collection state the manual modal and the engine share (TC-4)."""
    state, _ = AccountCollectionState.objects.get_or_create(
        tenant_id=_tenant_id(), account_id=account_id
    )
    state.tier = tier
    state.tier_sent_on = on_date
    state.last_notice_on = on_date
    state.save(update_fields=["tier", "tier_sent_on", "last_notice_on", "updated_at"])


def plan_notices_due(
    plan: PaymentPlan,
    *,
    as_of: date,
    reminder_days_before: int = DEFAULT_REMINDER_DAYS_BEFORE,
    missed_notice_day_after: int = DEFAULT_MISSED_NOTICE_DAY_AFTER,
) -> tuple[tuple[str, Any], ...]:
    """Which plan notices fall due today (BR-PAY-016 as the PO left it).

    Three kinds, and the third is a SECOND NOTICE and not a void:

    * **reminder**, `reminder_days_before` days before an instalment's due date;
    * **missed**, `missed_notice_day_after` days after an unmet due date;
    * **second notice**, on a missed instalment when an EARLIER one is still
      outstanding too.

    The third is deliberately expressed as *"more than one instalment is
    outstanding"* rather than as *"the miss count reached 2"*. It is the same
    moment in the customer's story and a different thing in the code: a count is
    a thing kept against somebody and a threshold is what it gets compared to,
    and the PO removed the threshold on 2026-08-11. Nothing here is stored,
    nothing increments, and the plan's status is untouched whichever notice goes.

    Both cadences are ARGUMENTS (TC-6: *"defaults are config, not constants"*).
    """
    due: list[tuple[str, Any]] = []
    outstanding = plans.outstanding_installments(plan, as_of=as_of)
    outstanding_seqs = {row.seq for row in outstanding}
    for installment in plan.installments.all().order_by("seq"):
        if installment.due_date - timedelta(days=reminder_days_before) == as_of:
            due.append((NOTICE_PLAN_REMINDER, installment))
        if (
            installment.seq in outstanding_seqs
            and installment.due_date + timedelta(days=missed_notice_day_after) == as_of
        ):
            earlier_outstanding = [row for row in outstanding if row.seq < installment.seq]
            due.append(
                (
                    NOTICE_PLAN_SECOND if earlier_outstanding else NOTICE_PLAN_MISSED,
                    installment,
                )
            )
    return tuple(due)


def send_plan_notices(
    plan: PaymentPlan,
    *,
    as_of: date,
    reminder_days_before: int = DEFAULT_REMINDER_DAYS_BEFORE,
    missed_notice_day_after: int = DEFAULT_MISSED_NOTICE_DAY_AFTER,
    channels: tuple[str, ...] = ("pdf_print",),
    actor: Any = None,
) -> BulkNoticeResult:
    """Queue today's plan notices. **The plan's status is never changed here.**

    US-PAY-018 as the PO's ruling of 2026-08-11 leaves it: notices go out, the
    plan stays ACTIVE, no counter is written and no state moves. A test sends
    the missed notice ten times over and asserts the plan is still active with
    no `missed_count` on the model — the guard that keeps a drop-off from being
    re-introduced by the next lane that reads BR-PAY-016 without its supersession.
    """
    sent: list[NoticeOutcome] = []
    problems: list[dict[str, Any]] = []
    status_before = plan.status
    for notice_type, installment in plan_notices_due(
        plan,
        as_of=as_of,
        reminder_days_before=reminder_days_before,
        missed_notice_day_after=missed_notice_day_after,
    ):
        # -- CR-048 wave B task B10 - THE MISSED-INSTALMENT NOTICE, FIXED -----
        # The CR calls this *"the one a utility most needs to send"* and lists
        # it as a real omission. The TRIGGER was never missing; what was missing
        # was everything it pointed at. Two faults, both invisible:
        #
        #  1 - **THE TEMPLATE CODE WAS A NOTICE TYPE.** This line pinned
        #      `template_code=notice_type` - `plan_installment_missed` - and no
        #      row in `catalogs.LISTINGS` or `seed_templates.SEEDABLE` has ever
        #      carried that code. The wording a customer would have read is
        #      `plan_notice_missed`, seeded on every tenant since 2026-08-16 and
        #      counted by CR-048 B9 as wording with no rule. A queue row pinned
        #      to a class nobody seeds renders as nothing anybody wrote.
        #  2 - **EVERY PLAN NOTICE SHARED ONE IDEMPOTENCY KEY.** `source_id` was
        #      the PLAN, so (tenant, "plan", plan_id, channel, copy_no) is the
        #      same tuple for the reminder, the missed notice and the second
        #      notice - and for every instalment of a twelve-month plan. The
        #      second write finds the first row and returns `created=False`: no
        #      error, no gap in the trail, and a customer who is chased once and
        #      never again. Keyed on the INSTALMENT, the letter about instalment
        #      3 cannot collide with the letter about instalment 4, and a re-run
        #      of the same day writes nothing.
        #
        # (!) B10 LEFT THE REMINDER AS IT WAS, both faults included, and named
        # the reason: adopting `plan_notice_upcoming` would have taken a class
        # out of B9's coverage count that B11 was about to report on. **CR-048
        # wave B task B11, 2026-08-30, IS THAT ADOPTION** - so all three plan
        # notices now name their own seeded wording and key on their own row,
        # and neither fault survives on any branch of this loop. See
        # `EVENT_PLAN_INSTALMENT_UPCOMING` at the top of the module for both
        # faults in full.
        #
        # ⚠ **THE THREE NOTICE TYPES COLLAPSE TO TWO MESSAGES, ON PURPOSE.**
        # `NOTICE_PLAN_SECOND` is a STRONGER LETTER about a missed instalment,
        # not a third document: BR-PAY-016's void was superseded on 2026-08-11
        # (*"nodrop we chase for payments until write off"*), so it renders from
        # `plan_notice_missed` and rides the missed event, exactly as B10 left
        # it. The `notice_history` row below still records all three types
        # separately, because the trail must say WHICH letter went.
        missed = notice_type in (NOTICE_PLAN_MISSED, NOTICE_PLAN_SECOND)
        message_ids, queue_problems = _queue_for(
            account_id=plan.account_id,
            source_type="plan",
            # ⚠ **PER INSTALMENT ON BOTH BRANCHES, AND BY TWO DIFFERENT
            # ROUTES.** This read `installment.pk if missed else plan.pk` until
            # 2026-08-30, and the `else` half is DEF-2512: the plan is ONE row
            # for a twelve-month schedule, so twelve reminders shared one
            # idempotency tuple and eleven of them deduped into the first with
            # `created=False` and no failure anywhere.
            # The missed notice keeps the instalment's OWN id. The reminder
            # takes a derived one, because a reminder and a missed notice are
            # two documents about the SAME instalment and the queue's key has
            # no column for which document - `plan_notice_source_id` above
            # carries that reasoning in full, including what it costs.
            source_id=(
                installment.pk if missed else plan_notice_source_id(installment.pk, notice_type)
            ),
            template_code=MISSED_TEMPLATE_CODE if missed else UPCOMING_TEMPLATE_CODE,
            channels=channels,
            actor=actor,
            # CR-048 wave A's join, wave B's caller. The utility's own switch is
            # read on the way in; BR-NOT-024's print floor on `plan` means the
            # LETTER still goes even when they switch the email off.
            event_key=(EVENT_PLAN_INSTALMENT_MISSED if missed else EVENT_PLAN_INSTALMENT_UPCOMING),
            # The facts `catalogs.CATALOGS` whitelists for these classes and that
            # this loop already holds - the SAME five tokens on all three plan
            # notices (C-14: they reuse one vocabulary), so one context serves
            # both branches and there is nothing to keep in step.
            # `{plan_balance}` is NOT passed and its absence is deliberate: no
            # signed rule says whether a plan balance is the unpaid instalments
            # or the whole account balance, and a money figure this module chose
            # between two meanings is worse on a customer's letter than the
            # named absence `rendering` prints.
            # The two figures that ARE passed are the same strings the
            # `notice_history` row below records, so the letter and the
            # trail cannot state different numbers.
            render_context={
                "installment_amount": str(installment.amount),
                "installment_due_date": installment.due_date,
                "installment_no": installment.seq,
                "installments_total": plan.installment_count,
            },
        )
        problems.extend(queue_problems)
        for channel in channels:
            record_notice(
                account_id=plan.account_id,
                notice_type=notice_type,
                outcome=OUTCOME_SENT,
                channel=channel,
                on_date=as_of,
                plan=plan,
                detail={
                    "installment_seq": installment.seq,
                    "installment_amount": str(installment.amount),
                    "due_date": installment.due_date.isoformat(),
                    # Recorded on the row so a year-old trail says what did NOT
                    # happen — the rule is an absence and absences are invisible.
                    "plan_status_after": status_before,
                    "dropped_off": False,
                },
                actor=actor,
            )
        sent.append(
            NoticeOutcome(
                account_id=str(plan.account_id),
                outcome=OUTCOME_SENT,
                channels=tuple(channels),
                queued_message_ids=message_ids,
            )
        )
    plan.refresh_from_db(fields=["status"])
    if plan.status != status_before:  # pragma: no cover - nothing here changes it
        raise PaymentRuleError(
            f"a plan notice changed the plan's status from {status_before!r} to "
            f"{plan.status!r}. Nobody is dropped off a plan (PO 2026-08-11) — notices "
            "are sent and the plan is untouched.",
            br_ref="BR-PAY-016",
        )
    return BulkNoticeResult(
        notice_type=NOTICE_PLAN_REMINDER, tier=None, sent=tuple(sent), problems=tuple(problems)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-015@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources; co-packet US-PAY-018@7b2ce54)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S35's modals have no endpoint yet) E=deferred(no-frontend-half — S35 is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim RED transcript — the "a plan
#         notice path may not drop an account" guard was proved RED by
#         reinstating BR-PAY-016's void, RUN, and the failure quoted
# exceptions: (1) NOTHING SENDS. Every notice is a `queue_document` write
#         (BR-NOT-005); there is no provider call in this module.
#         (2) THE THIRD PLAN NOTICE IS A SECOND NOTICE, NOT A VOID — PO
#         2026-08-11. No counter, no threshold, no state change.
#         (3) MEDICAL HOLD IS PASSED IN, NOT READ. `apps/customers` publishes no
#         medical-hold selector; inferring a clinical fact here would put it in
#         the wrong module. REPORTED.
#         (4) THE RECONNECT FEE IS PASSED IN AND DISPLAY-ONLY (BR-BIL-007). An
#         absent fee is reported as absent, never printed as 0.00 on a legal
#         notice.
#         (5) `notice_history` rows are written per CHANNEL, matching the queue's
#         own one-row-per-channel shape (BR-BIL-016), so "what was sent" and
#         "what we told them we sent" can be reconciled row for row.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
