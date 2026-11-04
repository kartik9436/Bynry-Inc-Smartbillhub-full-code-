# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page — CR-009 · the SERVICE half)   Screens: S8
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — PO 2026-08-17) ·
#           BR-NOT-018 (an event with no trigger is drawn and REFUSED by name) ·
#           BR-NOT-005 (PLATFORM-WIDE queue; the dispatcher is the ONLY sender
#           and NO synchronous send endpoint may exist anywhere) ·
#           BR-NOT-013 (delivery is out of this release on every channel) ·
#           BR-NOT-009 (quiet hours) · BR-NOT-010 (v1 channels) ·
#           BR-IDN-009 (server-enforced role gating IS the gating) ·
#           BR-TEN-016 (a settings edit is audited, before→after) ·
#           BR-SHL-025 (a control that may not act renders WITH its reason) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audited)
# Tests:    06-backend/tests/test_cr_009_notification_rules.py ·
#           06-backend/tests/test_cr_009_notification_rules_isolation.py ·
#           06-backend/tests/test_cr048_a1_rule_at_queue_time.py
#           (`channel_switches`, the read the queue joins on)
# Impacts:  apps/notifications/rules_api.py (the only caller) ·
#           apps/notifications/services.py (`queue_document` — the test send;
#           and, from CR-048 A1, `channel_decision`, which reads
#           `channel_switches` on every queue write that names an event) ·
#           07-frontend/src/features/notifications/NotificationRules.tsx
# ───────────────────────────────────────────────────────
"""Read and change a tenant's notification rules — the ONE write path.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides WHICH customers a
utility contacts and on which channel, which is a compliance surface
(BR-NOT-009's send window, BR-PAY-017's regulated ladder). AI-authored
2026-08-17 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"); row in 12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  "SEND TEST" ENQUEUES. NOTHING IN THIS FILE TRANSMITS.                   ║
╚══════════════════════════════════════════════════════════════════════════╝
**PO ruling 2026-08-17, verbatim:** *"I got it; lets build the infra and
capabilities; the moment we take the decison on ESP or SMTP from existing email
of Utilities, we just need to plug it ; rest of the infra will work"*.

**AND BR-NOT-005 STILL STANDS.** *"Queue only, no synchronous send endpoint"* is
not in tension with that ruling: a test send WRITES A QUEUE ROW addressed to the
signed-in user's own address, and the dispatcher drains it through whichever
adapter is one day plugged into `provider_seam`. The forbidden thing is a route
that transmits inside the request, and nothing here needs one. `queue_test`
therefore calls `services.queue_document` — the same and only write path every
bill, receipt and notice uses — and makes no provider call of any kind.

`provider_seam.channel_route()`'s deferred verdict is LEFT EXACTLY AS IT IS. No
adapter has been chosen (SMTP against a utility's own mailbox, or a
transactional ESP — still owed from the PO), so `dispatchable` stays False, the
row rests queued, and `queue_test` returns that verdict so the screen can say
so. Turning it green here to make a test send look like it worked would be the
one thing BR-NOT-013 names: *"no lane is to build or fake an adapter to turn a
test green"*.

────────────────────────────────────────────────────────────────────────────
WHAT THIS SERVICE REFUSES, AND WHY EACH REFUSAL IS BETTER THAN A DEFAULT
────────────────────────────────────────────────────────────────────────────
* **A staff recipient — [AMENDED 2026-08-18] now because it is RULED, not
  because it is open.** OQ-261 closed on 2026-08-17 (PO verbatim: *"the user
  who started the action, plus all System Admins for failures"* → BR-NOT-021).
  The recipient is a PLATFORM POLICY implemented in `staff_recipients.py`, not
  a per-rule setting, so `update_rule` still refuses every spelling of "send
  it to X" — with the ruling quoted, where it used to raise
  `NotImplementedError("OQ-261")`. Accepting a recipient column now would
  build the per-rule picker the PO chose NOT to have.
* **A channel the platform does not have.** Portal, Mail and In-app are named
  in the requirement and implemented nowhere; the catalogue carries them with
  a reason each and this service never writes a row for one.
* **A template variant that is deactivated.** The requirement: *"A channel
  can't be enabled if its variant is deactivated."* Enforced here rather than
  on the screen, because BR-SHL-025 is explicit that the screen is not the
  enforcement.

────────────────────────────────────────────────────────────────────────────
THE ESCALATION LADDER IS NOT STORED HERE. READ `rule_models.py`'s DOCSTRING.
────────────────────────────────────────────────────────────────────────────
The five figures the PO's *"one place"* ruling names — reminder at **3 days**
after due, notice tiers at **10** then **5** days, final notice at **48
hours**, the **$25** balance floor and the **25%** partial-payment pause — stay
in `apps.tenancy.settings_families.COLLECTIONS`, where the live collections
engine already reads them. SET-12D becomes their ONE SCREEN. `ladder_for`
below READS them through tenancy's own published seam so the rule page can draw
them; the WRITE goes over the existing `PUT /settings/collections` contract,
which is tenancy's and is already System-Admin-gated and audited. One home for
the rule; one store for the figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

from django.db import transaction

from apps.notifications import (
    in_app,
    models,
    rule_catalog,
    rule_models,
    services,
    tenancy_seam,
)
from apps.notifications import provider_seam

# CR-048 B7 — SET-10's send test resolves the SAME published version a real
# message would (BR-BIL-025's ladder). Safe at module level: `template_service`
# imports `catalogs`, `models`, `rendering` and `template_models` and reaches
# nothing here, so there is no cycle to break with a deferred import.
from apps.notifications import template_preview, template_service
from core import audit, errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

#: Hard rule 7 · the dotted `entity.action` grammar `core.audit` documents.
AUDIT_ACTION = "notification_rule.updated"
AUDIT_ACTION_TOGGLE = "notification_rule.toggled"
AUDIT_ACTION_TEST = "notification_rule.test_queued"
AUDIT_ENTITY = "notification_rule"
#: CR-048 B7 — the template screen's own test. A SEPARATE action and entity from
#: the two above, because the two buttons queue rows against different things:
#: one is keyed on the rule that was being tested, the other on the template
#: variant. One name for both would make the audit trail unable to answer which
#: screen a row came from.
AUDIT_ACTION_TEMPLATE_TEST = "notification_template.test_queued"
AUDIT_ENTITY_TEMPLATE = "notification_template"

#: The rule fields SET-12D may change. Named once so the audit diff, the
#: validation and the read all walk the same list — a field added to one and
#: forgotten in another is how a setting becomes editable and unaudited.
EDITABLE_RULE_FIELDS: tuple[str, ...] = (
    "enabled",
    "customer_scope",
    "service_scope",
    "plan_class",
    "skip_accounts_on_payment_plan",
    "trigger_mode",
    "offset_days",
    "fixed_time",
    "quiet_hours_mode",
    "failure_policy",
)

#: Per-channel fields, same discipline.
EDITABLE_CHANNEL_FIELDS: tuple[str, ...] = ("enabled", "template_code", "language_mode")

#: The source kind a test message is queued under. See `models.SOURCE_TYPES`.
TEST_SOURCE_TYPE = "test"


class RuleRefused(Exception):
    """This rule cannot be saved, and here is why — in a System Admin's words.

    Deliberately NOT a `core.errors` catalog exception: those carry an HTTP
    status and this service is callable from a shell and from provisioning.
    `rules_api` translates it into the one catalog exception G9 allows, which
    is the same split `dispatch_config.DispatchConfigRefused` documents.
    """


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _seeded_rule_kwargs(event: rule_catalog.EventClass) -> dict[str, Any]:
    """The rule a tenant HAS before they have ever opened SET-12.

    Every value here is the catalogue's, not a preference: a tenant who never
    visits the screen and a tenant who visits and saves nothing must behave
    identically, or something has to interpret the difference (the same
    reasoning `NotificationSettings` records).

    **Two seeded values are rules rather than conveniences.**
    `enabled=False` for an event whose trigger does not exist — hard-won law 3,
    defaults fail closed, and the unsafe option here is a switch that reads as
    *"this now happens"*. And `skip_accounts_on_payment_plan=True` on the
    past-due reminder, which is the CR's own words: *"Collections events default
    to their protective filters (past-due skips payment plans)"*.
    """
    return {
        "enabled": event.trigger_blocked_by is None,
        "skip_accounts_on_payment_plan": event.key == "past_due_reminder",
    }


def _seeded_channel_enabled(event: rule_catalog.EventClass, channel: str) -> bool:
    """Whether a channel row ships ON — the ONE expression, used twice.

    ON by default only when the platform can actually render something on that
    channel. A channel with no template class renders nothing, so an enabled
    toggle over it would be a promise (BR-SHL-025, hard-won law 3).

    ⚠ FACTORED OUT 2026-08-29 (CR-048 A1) and it is not tidying. `_ensure_rules`
    WRITES this default and `channel_switches` READS it for a tenant whose row
    has not been materialised yet, so the two must agree exactly or the queue
    would suppress a channel the screen draws as on. Two copies of one default
    is the shape that drifts, and this one would drift into a customer's bill
    silently not being emailed.
    """
    # ⚠ **AMENDED 2026-09-07 (`CR-084`) — THE TEST IS "CAN THE PLATFORM DELIVER
    # ON IT", AND A TEMPLATE CLASS IS ONLY ONE WAY OF ANSWERING YES.** Email and
    # SMS have nothing to send without wording, so `template_classes` decides
    # for them. The customer portal PUBLISHES A DOCUMENT — `CWP-031` names it
    # from facts and needs no body of its own — so a portal row with no template
    # class delivers a real thing, and leaving it OFF by default would have
    # answered the Product Owner's *"can you swithc on this now"* with a switch
    # they still had to find and flip on every event.
    #
    # ⚠ **NAMED, NOT DERIVED FROM `provider_seam.PLATFORM_ADAPTERS`** — which
    # was the first draft and was wrong. `in_app` has an adapter too, and three
    # staff events (`sla_breach`, `daily_digest`, `security_alerts`) offer that
    # channel with no template class BECAUSE they have nothing to render yet;
    # deriving from the adapter map would have drawn all three ON. `CR-084` ruled
    # ONE channel on, so exactly one is named here, and a third joining is a
    # deliberate line rather than a side effect.
    return channel in event.template_classes or channel == models.CHANNEL_PORTAL


def template_usage() -> dict[str, bool]:
    """THIS TENANT's answer to *"is anything set to send this wording"*.

    ⚠ **PO RULING 2026-09-07, verbatim: *"it should be dynamic and based on
    actual usage by notifications - can you fix it"* (`DEF-NOT-4531`).** The
    decision row of that day names four facts and this function is fact 2, the
    only one that is a property of THE UTILITY rather than of the platform:

      1. does any notification rule REFERENCE this template — the catalogue
         answers that (`catalogs.firing_events`);
      2. **is that rule's CHANNEL switched on — this;**
      3. has wording been AUTHORED — `catalogs.has_wording`;
      4. has anything ever been SENT — **deliberately not asked**, and the
         ruling says why: nothing is reporting sends back on this deployment,
         so silence here would render as absence and ship the same lie in a new
         coat.

    Returns `code → True/False`: True where a rule the tenant has ENABLED
    carries this template on a channel they have ENABLED. A code absent from
    the map is a code no rule of theirs names at all.

    `_ensure_rules` is deliberately NOT called: this is a read on a screen that
    lists 38 templates, and materialising up to 45 rows to answer it would make
    a catalogue GET write. A tenant who has never opened the settings screen
    has no rows and gets an empty map, which is the correct answer to *"what
    have you switched on"* for somebody who has switched nothing.
    """
    rows = rule_models.NotificationRuleChannel.objects.filter(
        tenant_id=_tenant_id(), template_code__isnull=False
    ).select_related("rule")
    usage: dict[str, bool] = {}
    for row in rows:
        code = (row.template_code or "").strip()
        if not code:
            continue
        live = bool(row.enabled and row.rule.enabled)
        usage[code] = usage.get(code, False) or live
    return usage


def seed_rules() -> dict[str, int]:
    """CR-010 item 7's SECOND HALF, written at PROVISIONING (DEF-258).

    The Product Owner's sentence pairs two rows and only one of them landed:
    *"the NotificationSettings row is to be WRITTEN at provisioning (today it is
    created on first read), so the dispatch home opens populated, **and the
    SET-12 rule rows with it**"*. `services.seed_notification_settings` did the
    first half on 2026-08-17; the matrix stayed materialise-on-read.

    ⚠ THE EVIDENCE THAT THIS WAS NOT A COSMETIC GAP, measured on the running
    `sbh_e2e` database of the only tenant on the system:

        notification_settings  min(created_at) = 2026-08-18 08:19:26  ← provisioning
        notification_rules     min(created_at) = 2026-08-19 04:21:17  ← twenty hours
                                                                       later, when a
                                                                       lane opened S8

    Twenty hours in which the answer to *"has this utility configured its
    notifications?"* was **zero rows**, which is indistinguishable from *"nobody
    has ever opened the screen"* — the exact ambiguity CR-010 item 7 removed for
    the dispatch row and left standing here.

    Returns what it wrote so provisioning and the repair door can REPORT rather
    than claim (BR-TEN-060). Idempotent by `get_or_create`, so a replay writes
    nothing and a tenant that has tuned its matrix keeps every value.

    **This does not make anything send.** BR-NOT-005 and BR-NOT-013 stand, and
    the larger half of DEF-258 — that no queue writer consults these rows — is
    still open and is a wiring story, not a seeding one.
    """
    return _ensure_rules()


def _ensure_rules() -> dict[str, int]:
    """Create this tenant's missing rule rows from the catalogue. Idempotent.

    Called at the top of every read AND, since DEF-258, at provisioning through
    `seed_rules()`. `get_or_create` per event rather than a bulk insert, so a
    catalogue that GAINS an event (the day OQ-262 or OQ-249 closes) lands on
    every existing tenant at their next read instead of needing a data migration
    nobody remembers to write.

    Returns the counts it created. The first-read call sites ignore them; the
    seeding call sites print them, because a repair door that says "0 created,
    already present" is telling an operator something different from one that
    says "15 created".
    """
    tenant_id = _tenant_id()
    made = {"rules_created": 0, "channels_created": 0}
    for event in rule_catalog.EVENTS:
        rule, rule_created = rule_models.NotificationRule.objects.get_or_create(
            tenant_id=tenant_id,
            event_key=event.key,
            defaults=_seeded_rule_kwargs(event),
        )
        made["rules_created"] += int(rule_created)
        for channel in event.channels:
            _row, channel_created = (
                rule_models.NotificationRuleChannel.objects.get_or_create(
                    rule=rule,
                    channel=channel,
                    defaults={
                        "tenant_id": tenant_id,
                        "enabled": _seeded_channel_enabled(event, channel),
                        "template_code": event.template_classes.get(channel),
                    },
                )
            )
            made["channels_created"] += int(channel_created)
    return made


@dataclass(frozen=True)
class ChannelSwitches:
    """ONE event's on/off switches, in the narrowest form the QUEUE needs.

    ⚠ ADDED 2026-08-29 for CR-048 A1 — *"the queue never reads the notification
    rule"*. `services.channel_decision` is the only caller and the only thing
    this shape is for: which channels may this event go out on, right now, for
    this tenant.

    ────────────────────────────────────────────────────────────────────────
    WHY THIS EXISTS BESIDE `rule()`, WHICH ALREADY ANSWERS THE SAME QUESTION
    ────────────────────────────────────────────────────────────────────────
    `rule(event_key)` is the SCREEN's read and it is right for the screen: it
    calls `rules()`, which calls `_ensure_rules()`, which walks all fifteen
    events and issues a `get_or_create` per event and per channel. That is
    forty-five statements and up to forty-five WRITES, and it is exactly what
    the settings page should do when a person opens it.

    The queue write path is the other extreme. It runs once per document inside
    the caller's transaction — a bill run over five hundred bills would pay that
    cost five hundred times, and would perform lazy SEEDING WRITES inside
    billing's own transaction, which is a surprise nobody asked for. So this
    read is TWO SELECTs and writes nothing.

    **It does not become a second answer**, which is the hazard a narrower read
    always carries. When the tenant's rows exist it reports them verbatim. When
    they do not — a tenant provisioned before DEF-258 who has never opened
    SET-12 — it falls back to `_seeded_rule_kwargs` and `_seeded_channel_enabled`,
    the same two expressions `_ensure_rules` would have written. There is no
    third spelling of the default anywhere.
    """

    event_key: str
    #: SET-12's master On switch for the event.
    event_enabled: bool
    #: channel → on/off, for the channels the EVENT offers (`rule_catalog`) and
    #: no others. A channel absent from this map has no toggle on any screen.
    channels: dict[str, bool]
    #: True when the tenant's own rows answered; False when the catalogue
    #: defaults did because the rows have not been materialised yet. Carried so
    #: a caller can REPORT which it read rather than have to assume.
    stored: bool

    def permits(self, channel: str) -> bool | None:
        """True, False, or **None when this event has no toggle for it at all**.

        The three-valued answer is the point. `bill_ready` draws email and SMS
        and has no print switch, so "is print permitted?" has no answer rather
        than the answer False — and a caller that collapsed the two would
        suppress a channel no utility could ever switch back on.
        """
        return self.channels.get(channel)


def channel_switches(event_key: str) -> ChannelSwitches:
    """This tenant's switches for one event. Two SELECTs, no writes, no clock.

    Hard rule 1: both reads are filtered by `app.tenant_id`'s tenant. The event
    KEY is a platform constant shared by every utility, so an unfiltered read
    here would answer one tenant's queue with another tenant's settings and
    nothing about the result would look wrong.

    Raises `KeyError` naming the whole vocabulary for an event this platform
    cannot fire — `rule_catalog.event`'s own refusal, not re-worded here.
    """
    event = rule_catalog.event(event_key)
    tenant_id = _tenant_id()
    row = (
        rule_models.NotificationRule.objects.filter(
            tenant_id=tenant_id, event_key=event_key
        )
        .only("id", "enabled")
        .first()
    )
    if row is None:
        return ChannelSwitches(
            event_key=event_key,
            event_enabled=bool(_seeded_rule_kwargs(event)["enabled"]),
            channels={
                channel: _seeded_channel_enabled(event, channel)
                for channel in event.channels
            },
            stored=False,
        )
    stored = {
        channel.channel: bool(channel.enabled)
        for channel in rule_models.NotificationRuleChannel.objects.filter(
            tenant_id=tenant_id, rule_id=row.pk
        ).only("channel", "enabled")
    }
    return ChannelSwitches(
        event_key=event_key,
        event_enabled=bool(row.enabled),
        channels={
            channel: stored.get(channel, _seeded_channel_enabled(event, channel))
            for channel in event.channels
        },
        stored=True,
    )


@dataclass(frozen=True)
class LadderView:
    """BR-PAY-017's chasing schedule, READ from where it actually lives.

    Frozen and read-only. SET-12D draws it and writes it back through
    `PUT /settings/collections` — see the module docstring for why this service
    does not own the store.
    """

    reminder_days_after_due: int | None
    notice_tier_days: tuple[int, ...]
    final_notice_hours: int | None
    balance_floor_amount: str | None
    partial_payment_pause_percent: str | None
    unavailable_reason: str | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "reminder_days_after_due": self.reminder_days_after_due,
            "notice_tier_days": list(self.notice_tier_days),
            "final_notice_hours": self.final_notice_hours,
            # Money and percentages travel as canonical STRINGS end to end
            # (CLAUDE.md rule 2) — nothing on this path parses one into a float.
            "balance_floor_amount": self.balance_floor_amount,
            "partial_payment_pause_percent": self.partial_payment_pause_percent,
            "unavailable_reason": self.unavailable_reason,
            # The settings family this screen edits, so the client posts to the
            # ONE contract rather than to a route this module would have to mint.
            "write_endpoint": "/settings/collections",
        }


def ladder_for(event_key: str) -> LadderView | None:
    """The escalation ladder for a collections event, or None for every other.

    Reads `apps.tenancy.settings_families.COLLECTIONS` through the seam this
    module already uses for the notice tiers. When the family cannot be read the
    view reports the REASON and every figure is None — never zero, because "we
    could not read the tenant's ladder" and "the tenant chases from day 0" are
    different facts and a screen that spells them the same sends a person to the
    wrong fix.
    """
    event = rule_catalog.event(event_key)
    if not event.has_ladder:
        return None
    try:
        config = tenancy_seam.collections_config()
    except tenancy_seam.CollectionsConfigUnavailable as refusal:
        return LadderView(None, (), None, None, None, unavailable_reason=str(refusal))
    tiers = tuple(int(day) for day in (config.get("notice_tier_days") or ()))
    return LadderView(
        reminder_days_after_due=config.get("reminder_days_after_due"),
        notice_tier_days=tiers,
        final_notice_hours=config.get("final_notice_hours"),
        balance_floor_amount=_as_decimal_string(
            config.get("ladder_balance_floor_amount")
        ),
        partial_payment_pause_percent=_as_decimal_string(
            config.get("partial_payment_pause_percent")
        ),
    )


def _as_decimal_string(value: Any) -> str | None:
    """A stored decimal as a canonical string, or None. Never a float."""
    return None if value is None else str(value)


@dataclass(frozen=True)
class RuleView:
    """One event's rule, as the matrix row and the detail page both need it."""

    event: rule_catalog.EventClass
    row: rule_models.NotificationRule
    channels: tuple[rule_models.NotificationRuleChannel, ...]

    def as_wire(self, *, include_ladder: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self.event.as_wire(),
            "enabled": bool(self.row.enabled),
            "customer_scope": self.row.customer_scope,
            "service_scope": self.row.service_scope,
            "plan_class": self.row.plan_class,
            "skip_accounts_on_payment_plan": bool(
                self.row.skip_accounts_on_payment_plan
            ),
            "trigger_mode": self.row.trigger_mode,
            # `DEF-PAY-10651` — whether BR-NOT-024's print floor reaches this
            # event, from the ONE floor table rather than a screen's copy of
            # it. An event whose queue kind is unrecorded keeps the floor.
            "print_is_floor": (
                self.event.source_type is None
                or self.event.source_type in services.CHANNEL_FLOOR_BY_SOURCE
            ),
            "offset_days": self.row.offset_days,
            "fixed_time": (
                self.row.fixed_time.isoformat(timespec="minutes")
                if self.row.fixed_time
                else None
            ),
            "quiet_hours_mode": self.row.quiet_hours_mode,
            "failure_policy": self.row.failure_policy,
            "channel_rules": [
                {
                    "channel": channel.channel,
                    "enabled": bool(channel.enabled),
                    "template_code": channel.template_code,
                    "language_mode": channel.language_mode,
                    # The one channel fact the dispatcher owns. Carried per row
                    # so a screen never infers "will this go out?" from a flag
                    # that only means "is this configured?".
                    **_channel_dispatch_facts(channel.channel),
                }
                for channel in self.channels
            ],
            # BR-NOT-021 (OQ-261 CLOSED 2026-08-17) — the recipient is a ruled
            # platform policy, stated per row; it is still not a settable field
            # and `staff_recipient` stays None so no client mistakes the policy
            # for a stored per-rule value. (`staff_recipient_blocked_by` left
            # the wire with the question it carried.)
            "staff_recipient": None,
            "staff_recipient_policy": (
                # `CR-188-BRC10` — a staff sign-in email states its own recipient.
                (self.event.staff_recipient_policy_override or rule_catalog.STAFF_RECIPIENT_POLICY)
                if self.event.audience == rule_catalog.AUDIENCE_STAFF
                else None
            ),
        }
        if include_ladder:
            ladder = ladder_for(self.event.key)
            payload["ladder"] = ladder.as_wire() if ladder else None
        return payload


def _channel_dispatch_facts(channel: str) -> dict[str, Any]:
    """Whether this channel would actually reach anybody, and why not.

    `provider_seam.channel_route` is the platform's ONE answer to that and its
    verdict is left exactly as it is (see the module docstring). Reproducing the
    reasoning here would be a second copy free to disagree with the dispatcher's.
    """
    if channel in (models.CHANNEL_PRINT, models.CHANNEL_IN_APP):
        # Print is the floor (BR-BIL-036) and in-app is always on with no
        # column (BR-NOT-019 — `dispatch_config.channel_is_active` states the
        # reasoning at length). Neither has an activation flag to read.
        is_active = True
    else:
        active = models.NotificationSettings.objects.filter(
            tenant_id=_tenant_id()
        ).values_list(
            (
                "email_dispatch_active"
                if channel == models.CHANNEL_EMAIL
                else "sms_dispatch_active"
            ),
            flat=True,
        )
        is_active = bool(active[0]) if active else False
    route = provider_seam.channel_route(channel, active=is_active)
    return {"dispatchable": route.dispatchable, "dispatch_problem": route.problem}


#: The channels a rule can go out on, in the order `dispatchable_channels`
#: reports them.
_ROUTED_CHANNELS = (
    models.CHANNEL_PRINT,
    models.CHANNEL_EMAIL,
    models.CHANNEL_SMS,
    models.CHANNEL_IN_APP,
)


def dispatchable_channels() -> list[str]:
    """The channels the dispatcher would send on today, asked of it per channel.

    `DEF-NOT-10537`: the rules matrix served the literal `["in_app"]` while
    email sent through the utility's Custom SMTP connector. Derived from the
    same `_channel_dispatch_facts` the test button reads, so the two agree.
    """
    return [c for c in _ROUTED_CHANNELS if _channel_dispatch_facts(c)["dispatchable"]]


def rules() -> tuple[RuleView, ...]:
    """The whole matrix for this tenant, in the catalogue's order."""
    _ensure_rules()
    tenant_id = _tenant_id()
    rows = {
        row.event_key: row
        for row in rule_models.NotificationRule.objects.filter(tenant_id=tenant_id)
    }
    channels: dict[Any, list[rule_models.NotificationRuleChannel]] = {}
    for channel in rule_models.NotificationRuleChannel.objects.filter(
        tenant_id=tenant_id
    ).order_by("channel"):
        channels.setdefault(channel.rule_id, []).append(channel)
    views: list[RuleView] = []
    for event in rule_catalog.EVENTS:
        row = rows[event.key]
        views.append(
            RuleView(event=event, row=row, channels=tuple(channels.get(row.pk, ())))
        )
    return tuple(views)


def rule(event_key: str) -> RuleView:
    """One event's rule. Raises KeyError naming the vocabulary for an unknown."""
    rule_catalog.event(event_key)  # refuses an event this platform cannot fire
    for view in rules():
        if view.event.key == event_key:
            return view
    raise RuleRefused(  # pragma: no cover - `_ensure_rules` makes this unreachable
        f"no rule row exists for {event_key!r} after seeding, which should be impossible."
    )


# ── validation ─────────────────────────────────────────────────────────────
_CHOICES: dict[str, tuple[str, ...]] = {
    "customer_scope": rule_catalog.CUSTOMER_SCOPES,
    "plan_class": rule_catalog.PLAN_CLASSES,
    "trigger_mode": rule_catalog.TRIGGER_MODES,
    "quiet_hours_mode": rule_catalog.QUIET_HOURS_MODES,
    "failure_policy": rule_catalog.FAILURE_POLICIES,
}


def _validated(field: str, value: Any, *, event: rule_catalog.EventClass) -> Any:
    """One submitted value → its stored form, or the refusal explaining why not."""
    if field in _CHOICES:
        if value not in _CHOICES[field]:
            raise RuleRefused(
                f"{value!r} is not a value {field} may take. The set is "
                f"{', '.join(_CHOICES[field])} — it is platform vocabulary, not a tenant "
                "lookup, because each value is a behaviour something in this codebase "
                "implements."
            )
        if field == "customer_scope" and event.audience == rule_catalog.AUDIENCE_STAFF:
            raise RuleRefused(
                f"{event.key!r} is a STAFF notification, so 'which of the customer's "
                "contacts' does not apply to it. Who receives a staff notification is "
                f"ruled ({rule_catalog.STAFF_RECIPIENT_BR}: "
                f"{rule_catalog.STAFF_RECIPIENT_POLICY}) and is not per-rule settable — "
                "storing a customer scope on it would look like a second answer."
            )
        return value
    if field in ("enabled", "skip_accounts_on_payment_plan"):
        if not isinstance(value, bool):
            raise RuleRefused(f"{field} is on or off, not {value!r}.")
        return value
    if field == "offset_days":
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuleRefused(
                f"the offset must be a whole number of days, not {value!r}."
            )
        if value < 0:
            raise RuleRefused(
                f"an offset of {value} days would schedule a message before the event "
                "that causes it. A negative offset is a different rule — 'N days BEFORE "
                "the due date' is the escalation ladder, which SET-12D edits separately."
            )
        return value
    if field == "fixed_time":
        if value is None:
            return None
        if not isinstance(value, time):
            raise RuleRefused(
                f"the send time must be a time of day, not {value!r}. It is WALL-CLOCK "
                "tenant time, the same as BR-NOT-009's send window."
            )
        return value
    if field == "service_scope":
        if not isinstance(value, str) or not value:
            raise RuleRefused("the service scope is a service code, or 'all'.")
        return value
    raise RuleRefused(  # pragma: no cover - unreachable via update_rule
        f"{field!r} is not a rule field. The editable set is "
        f"{', '.join(EDITABLE_RULE_FIELDS)}."
    )


def _refuse_staff_recipient(payload: dict[str, Any]) -> None:
    """BR-NOT-021 — the recipient is RULED, and it is a policy, not a field.

    ⚠ [AMENDED 2026-08-18] This guard used to raise
    `NotImplementedError("OQ-261")` because the question was OPEN. The PO
    closed it (2026-08-17, verbatim: *"the user who started the action, plus
    all System Admins for failures"*), choosing a platform policy over every
    per-rule picker option — so any spelling of "send it to X" is STILL
    refused, now as a rule refusal quoting the ruling: accepting one would
    build the picker the PO decided against.
    """
    for key in ("staff_recipient", "staff_role", "recipient_role", "owner"):
        if key in payload:
            raise RuleRefused(
                f"a staff notification's recipient is not a per-rule setting. It is "
                f"ruled platform-wide ({rule_catalog.STAFF_RECIPIENT_BR}): "
                f"{rule_catalog.STAFF_RECIPIENT_POLICY} Storing {key!r} here would be a "
                "second, per-rule answer free to disagree with the ruled one."
            )


@require_role(SYSTEM_ADMIN, br_ref="BR-NOT-017")
def update_rule(
    *,
    event_key: str,
    actor: Any,
    channels: dict[str, dict[str, Any]] | None = None,
    **changes: Any,
) -> RuleView:
    """Save a SET-12D edit. Admin-gated, validated, audited, ONE transaction.

    The requirement: *"Save is one transaction; toast confirmation; returns to
    matrix"*. Every field and every channel row move together or none does, so a
    save that fails halfway cannot leave a rule that sends on a channel whose
    template it never got round to changing.

    Pass only what is changing. A field submitted with the value it already
    holds is not a change and does not enter the audit payload — the same shape
    `dispatch_config.update_dispatch_settings` keeps and for the same reason: a
    payload padded with unchanged fields makes the next reader hunt for the edit.
    """
    _refuse_staff_recipient(changes)
    view = rule(event_key)
    event = view.event

    unknown = sorted(set(changes) - set(EDITABLE_RULE_FIELDS))
    if unknown:
        raise RuleRefused(
            f"{', '.join(unknown)} is not a notification-rule field. The editable set is "
            f"{', '.join(EDITABLE_RULE_FIELDS)}. The escalation ladder is edited through "
            "/settings/collections — it has ONE store and this is not it (see the module "
            "docstring). Who receives a staff notification is ruled platform-wide "
            f"({rule_catalog.STAFF_RECIPIENT_BR}), not a rule field."
        )
    if not changes and not channels:
        raise RuleRefused(
            "no rule field and no channel was named, so there is nothing to save. An "
            "empty save would write an audit row saying a System Admin changed how this "
            "utility contacts its customers and leave no way to see that they did not."
        )

    with transaction.atomic():
        row = view.row
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field, raw in changes.items():
            value = _validated(field, raw, event=event)
            current = getattr(row, field)
            if current == value:
                continue
            before[field] = _audit_value(current)
            after[field] = _audit_value(value)
            setattr(row, field, value)

        # The trigger mode and its argument are validated as a PAIR, after both
        # are applied — the same reason the quiet-hours window is. An edit that
        # switches to `offset_days` arrives as two fields and neither alone is
        # lawful.
        _refuse_incoherent_timing(row)

        if before:
            row.save(update_fields=[*before.keys(), "updated_at"])

        channel_before, channel_after = _apply_channel_changes(view, channels or {})
        if channel_before:
            before["channels"] = channel_before
            after["channels"] = channel_after

        if not before:
            # Every submitted value already held its submitted value. Nothing is
            # written and nothing is audited: the trail records CHANGES.
            return rule(event_key)

        # Hard rule 7, in the SAME transaction — a changed contact rule cannot
        # stand without its trail row (core.audit fails loudly).
        audit.money_action(
            actor, AUDIT_ACTION, AUDIT_ENTITY, str(row.pk), before=before, after=after
        )
    return rule(event_key)


def _audit_value(value: Any) -> Any:
    """A rule value in a form the audit payload can carry losslessly."""
    return value.isoformat() if isinstance(value, time) else value


def _refuse_incoherent_timing(row: rule_models.NotificationRule) -> None:
    """The trigger mode and its argument must agree — the CHECK, said in words.

    Refused in the service as well as in the DDL because a constraint violation
    reaches a System Admin as a database error, and this is a sentence they can
    act on (BR-SHL-020).
    """
    if row.trigger_mode == rule_catalog.TRIGGER_OFFSET_DAYS and row.offset_days is None:
        raise RuleRefused(
            "'a number of days after the event' needs the number. Without it the rule "
            "says when to send relative to nothing."
        )
    if (
        row.trigger_mode != rule_catalog.TRIGGER_OFFSET_DAYS
        and row.offset_days is not None
    ):
        raise RuleRefused(
            f"this rule sends {row.trigger_mode.replace('_', ' ')} and also carries an "
            f"offset of {row.offset_days} days. Two instructions, and nothing rules on "
            "which wins — clear the offset or choose the offset trigger."
        )
    if row.trigger_mode == rule_catalog.TRIGGER_FIXED_TIME and row.fixed_time is None:
        raise RuleRefused("'at a fixed time of day' needs the time.")
    if (
        row.trigger_mode != rule_catalog.TRIGGER_FIXED_TIME
        and row.fixed_time is not None
    ):
        raise RuleRefused(
            f"this rule sends {row.trigger_mode.replace('_', ' ')} and also carries a "
            "fixed send time. Clear the time or choose the fixed-time trigger."
        )


def _apply_channel_changes(
    view: RuleView, submitted: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Per-channel edits, inside the caller's transaction. Returns the diff."""
    by_channel = {channel.channel: channel for channel in view.channels}
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for channel_key, patch in submitted.items():
        if channel_key in rule_catalog.UNAVAILABLE_CHANNELS:
            raise RuleRefused(
                f"{channel_key!r} is not a channel this platform has: "
                f"{rule_catalog.UNAVAILABLE_CHANNELS[channel_key]}"
            )
        if channel_key not in by_channel:
            raise RuleRefused(
                f"{view.event.key!r} does not go out on {channel_key!r}. Its channels are "
                f"{', '.join(channel.channel for channel in view.channels) or 'none'}; the "
                "set is the event's, not the tenant's, because only a writer in this "
                "codebase can put a message on a channel."
            )
        row = by_channel[channel_key]
        unknown = sorted(set(patch) - set(EDITABLE_CHANNEL_FIELDS))
        if unknown:
            raise RuleRefused(
                f"{', '.join(unknown)} is not a channel setting. The editable set is "
                f"{', '.join(EDITABLE_CHANNEL_FIELDS)}."
            )
        moved: dict[str, Any] = {}
        was: dict[str, Any] = {}
        for field, value in patch.items():
            validated = _validated_channel(field, value, channel=channel_key)
            current = getattr(row, field)
            if current == validated:
                continue
            was[field] = current
            moved[field] = validated
            setattr(row, field, validated)
        if moved:
            if row.enabled and not row.template_code:
                raise RuleRefused(
                    f"{channel_key!r} cannot be switched on for {view.event.key!r} while it "
                    "has no template. The requirement is explicit — *'a channel can't be "
                    "enabled if its variant is deactivated'* — and a channel with nothing "
                    "to render is a queue row the dispatcher will hold forever."
                )
            row.save(update_fields=[*moved.keys(), "updated_at"])
            before[channel_key] = was
            after[channel_key] = moved
    return before, after


def _validated_channel(field: str, value: Any, *, channel: str) -> Any:
    if field == "enabled":
        if not isinstance(value, bool):
            raise RuleRefused(f"{channel} enabled is on or off, not {value!r}.")
        return value
    if field == "language_mode":
        if value not in rule_catalog.LANGUAGE_MODES:
            raise RuleRefused(
                f"{value!r} is not a language mode. The set is "
                f"{', '.join(rule_catalog.LANGUAGE_MODES)} (BR-NOT-006)."
            )
        return value
    if field == "template_code":
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise RuleRefused("a template code is a class from the Templates catalog.")
        return value
    raise RuleRefused(  # pragma: no cover - unreachable via _apply_channel_changes
        f"{field!r} is not a channel setting."
    )


# ── the test send: it ENQUEUES (PO 2026-08-17) ─────────────────────────────
@dataclass(frozen=True)
class TestQueueResult:
    """What a "Send test" actually did, said precisely enough to render.

    `queued` and `will_be_delivered` are separate, and the screen must be able
    to say both. A result that reported only "queued: true" would read, to a
    System Admin who just clicked the button, as "a test email is on its way"
    whether or not the dispatcher will send it. ⚠ AMENDED 2026-10-22
    (`DEF-NOT-10537`): this said `will_be_delivered` is FALSE on every channel,
    and the wire hardcoded it; email sends now, so it is the dispatcher's
    verdict (`dispatchable`), exactly as `TemplateTestResult` already reads.
    """

    event_key: str
    channel: str
    queued: bool
    recipient_address: str | None
    dispatchable: bool
    problem: dict[str, Any] | None
    message_id: str | None
    unavailable_reason: str | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "channel": self.channel,
            "queued": self.queued,
            "recipient_address": self.recipient_address,
            # The two halves a person needs, spelled separately on purpose.
            # The dispatcher's verdict, never a literal (`DEF-NOT-10537`).
            "will_be_delivered": self.dispatchable,
            "dispatchable": self.dispatchable,
            "problem": self.problem,
            "message_id": self.message_id,
            "unavailable_reason": self.unavailable_reason,
        }


def _test_recipient(actor: Any, channel: str) -> tuple[str | None, str | None]:
    """The signed-in user's OWN address — the CR's own words, *"sends a test to
    the signed-in user's email/phone"*.

    Returns (address, unavailable_reason). Never another person's address: a
    test send that reached a customer would be a real message with the word
    "test" in it.

    The actor arrives in either of the two shapes this codebase uses — the raw
    session user, or the B12 §6a `SimpleNamespace(id, role, user)` the API layer
    builds. The address lives on the USER in both, so it is resolved through
    `.user` first and falls back to the object itself. Reading `actor.email` off
    the namespace would silently return None and report "you hold no email
    address" to a System Admin whose address is on file.
    """
    actor = getattr(actor, "user", None) or actor
    if channel == models.CHANNEL_EMAIL:
        address = getattr(actor, "email", None)
        if not address:
            return None, (
                "your user account holds no email address, so there is nowhere to send "
                "the test. A test goes to YOU and to nobody else."
            )
        return str(address), None
    if channel == models.CHANNEL_SMS:
        address = getattr(actor, "phone", None)
        if not address:
            return None, (
                "your user account holds no mobile number, so there is nowhere to send "
                "the test. Add one under Settings → Users first."
            )
        return str(address), None
    if channel == models.CHANNEL_IN_APP:
        # ⚠ **DEFECT FIXED 2026-08-18 (DEF-265).** In-app fell through to the
        # PRINT sentence below, so the ONE channel with a real adapter
        # (`apps.notifications.in_app`, BR-NOT-019) was the one channel the test
        # button refused — a button whose whole job is to prove the pipeline,
        # refusing on the only pipeline that runs. Its address is the signed-in
        # user's own id, so there is nothing to look up and nobody else it could
        # reach.
        #
        # The spelling is `in_app.address_for`'s and is not re-derived here:
        # `str(actor.id)` would read the MEMBERSHIP's id off the B12 §6a
        # namespace on one call path and the USER's on the other, and a message
        # queued to the wrong one of those sits in an inbox nobody opens
        # (`in_app.user_id_of` records the same hazard).
        #
        # This adds NO send path and BR-NOT-013 is untouched: the row is still
        # only ENQUEUED, and it still waits for `manage.py dispatch_outbound` to
        # become a message in the bell (DEF-266 is a separate, open gap).
        try:
            return in_app.address_for(actor), None
        except in_app.InboxRefused as refusal:
            return None, str(refusal)
    return None, (
        "a test can only be sent to you, and the only addresses this platform holds for "
        "a user are an email address and a mobile number. There is no way to post a test "
        "letter to yourself."
    )


@require_role(SYSTEM_ADMIN, br_ref="BR-NOT-005")
def queue_test(*, event_key: str, channel: str, actor: Any) -> TestQueueResult:
    """Queue ONE test message for this rule, addressed to the person clicking.

    ⚠ **THIS ENQUEUES. IT DOES NOT SEND, AND NO ROUTE ANYWHERE MAY.** BR-NOT-005
    and A11 Addendum r2 §4 make a synchronous send endpoint a gate failure, and
    a test asserts that neither `send` nor `test-send` resolves on this surface.
    The PO's ruling of 2026-08-17 asked for the INFRASTRUCTURE — *"the moment we
    take the decison on ESP or SMTP … we just need to plug it; rest of the infra
    will work"* — and this is that infrastructure: a real queue row, through the
    real single write path, rendered from the real template pin, waiting for an
    adapter that has not been chosen.

    The returned verdict carries `provider_seam`'s own answer unchanged, so the
    screen tells the truth about what will happen next.
    """
    view = rule(event_key)
    if channel not in {row.channel for row in view.channels}:
        raise RuleRefused(
            f"{view.event.key!r} does not go out on {channel!r}, so there is nothing to "
            "test there."
        )
    channel_row = next(row for row in view.channels if row.channel == channel)
    if not channel_row.template_code:
        raise RuleRefused(
            f"{view.event.key!r} has no template on {channel!r}, so a test would have "
            "nothing to render. The Templates catalog owns what it says; this screen owns "
            "when it goes (Settings → Configure → Templates)."
        )

    address, unavailable = _test_recipient(actor, channel)
    facts = _channel_dispatch_facts(channel)
    if unavailable is not None:
        return TestQueueResult(
            event_key=event_key,
            channel=channel,
            queued=False,
            recipient_address=None,
            dispatchable=bool(facts["dispatchable"]),
            problem=facts["dispatch_problem"],
            message_id=None,
            unavailable_reason=unavailable,
        )

    # `copy_no` is the documented escape hatch for a DELIBERATE extra copy
    # (`OutboundMessage.copy_no`: *"0 = the delivery record … > 0 = a deliberate,
    # human-requested extra copy"*). A second click on "Send test" is exactly
    # that, so it gets the next copy number rather than colliding with the
    # first on the idempotency key and returning `already_queued`.
    existing = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(),
        source_type=TEST_SOURCE_TYPE,
        source_id=view.row.pk,
        channel=channel,
    ).count()

    with transaction.atomic():
        write = services.queue_document(
            source_type=TEST_SOURCE_TYPE,
            # The SOURCE of a test message is the rule whose button was pressed.
            # There is no document, and inventing a fake invoice id to satisfy
            # the column would put a row on the queue pointing at a bill that
            # does not exist.
            source_id=view.row.pk,
            channels=(channel,),
            template=services.TemplatePin(code=channel_row.template_code),
            recipients=(services.Recipient(channel=channel, address=address),),
            copy_no=existing,
            actor=actor,
            job="notification_rule_test",
            # ⚠ `DEF-NOT-4449` — **A TEST WITH NO VALUES IN IT IS NOT A TEST.**
            # Until 2026-09-07 this queued the real wording with no context, so
            # the System Admin checking their bill-ready email received *"Your
            # bill is ready — —— due ——"* and learned nothing about the thing
            # they pressed the button to check.
            #
            # **THE VALUES ARE THE PREVIEW SCREEN'S OWN SAMPLES, NOT NEW ONES.**
            # `template_preview.sample_context` is the ratified set SET-10's
            # pane already renders from — `SAMPLE-ACCOUNT`, `Sample Customer`,
            # `123.45`, a FIXED `2026-01-31` (BR-TEN-043: a preview that read a
            # clock could never be reproduced from a screenshot). Reusing it is
            # the point: a test message and the preview of the same class now
            # say the same thing, where two sample sets would eventually
            # disagree and the admin could not tell which was the letter.
            #
            # **NOTHING IS INVENTED AND NOTHING REAL IS USED.** There is no
            # document behind a test — no bill, no payment, no account — so a
            # figure here could only be fabricated or sampled, and the samples
            # are visibly samples. The four tokens the preview deliberately does
            # NOT sample stay unsampled here too, because they are the tenant's
            # own Settings → Company identity: a test is the one message where
            # seeing `——` for the support phone is USEFUL, since it tells the
            # admin their real letters will print it blank (`DEF-TEN-4412`).
            render_context=template_preview.sample_context(channel_row.template_code),
        )
        audit.money_action(
            actor,
            AUDIT_ACTION_TEST,
            AUDIT_ENTITY,
            str(view.row.pk),
            before={},
            after={"event_key": event_key, "channel": channel, "copy_no": existing},
        )

    message = write.messages[0] if getattr(write, "messages", ()) else None
    return TestQueueResult(
        event_key=event_key,
        channel=channel,
        queued=True,
        recipient_address=address,
        dispatchable=bool(facts["dispatchable"]),
        problem=facts["dispatch_problem"],
        message_id=str(getattr(message, "id", "")) or None,
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-048 B7 · THE SAME TEST, FROM THE TEMPLATE SCREEN
# ══════════════════════════════════════════════════════════════════════════
# The rules screen tests an EVENT — *"does Bill ready go out by email, and what
# does it say?"*. SET-10 tests a TEMPLATE — *"does this wording I have just
# published actually render?"*. Two questions, two screens, and they must not
# become two send-test implementations: the recipient rule (`_test_recipient`),
# the dispatch verdict (`_channel_dispatch_facts`), the source kind
# (`TEST_SOURCE_TYPE`) and the audit action are shared here BY REUSE, because a
# second copy of "where does a test go" is free to disagree with the first and
# nothing would notice until a test message reached somebody it should not.
#
# ⚠ **IT LIVES IN THIS FILE RATHER THAN IN `template_service` FOR THAT REASON
# ALONE.** `template_service` owns wording and versions and imports neither
# `provider_seam` nor `services`; moving the shared four across would have put
# the second copy exactly where this comment says not to put it. The judgment is
# recorded in the decision log so a later lane can dispute it there.
#
# ⚠ **AND NEITHER OF THESE ROWS IS A DOCUMENT ANYBODY WILL EVER ASK TO SEE.**
# `BR-NOT-024` gives the `test` source kind no print floor — *"a rehearsal
# addressed to the signed-in user; posting it would spend a stamp to prove
# nothing"* — and `BR-NOT-027` (PO 2026-08-30) is now the SECOND reason a test
# row is different: a sent legal document must be kept as the document the
# customer read, and a rehearsal addressed to the person who pressed the button
# is not a legal document. A later lane sweeping "freeze every outbound row"
# through this module is looking for this sentence.
@dataclass(frozen=True)
class TemplateTestOffer:
    """Whether SET-10 may offer "Send test to me" for one template, and why not.

    `reason` is populated EITHER WAY and is the sentence drawn beside the
    control (BR-SHL-025 — disabled with its reason, never hidden). When the test
    CAN be queued it says where it goes and that nothing will leave the
    building; when it cannot, it says what stops it. Those are different facts
    with different fixes and the screen must be able to show both.
    """

    can_test_send: bool
    reason: str
    channel: str | None = None
    recipient_address: str | None = None
    #: CR-048 wave I — the THREE OR FOUR WORDS the screen draws under the
    #: control. `reason` above is the control's tooltip and is unchanged; this
    #: is what a person reads without hovering. PO, 2026-08-30, on the deployed
    #: v2.83.0: *"just use 3 or 4 wrods and fix the UI"*. Defaulted rather than
    #: required so a branch that forgets one degrades to the honest generic
    #: label instead of to an empty cell.
    label: str = "Test send unavailable"


@dataclass(frozen=True)
class TemplateTestResult:
    """What SET-10's "Send test" actually did. `TestQueueResult`, keyed on the
    template instead of on the event."""

    template_code: str
    channel: str
    queued: bool
    recipient_address: str | None
    dispatchable: bool
    problem: dict[str, Any] | None
    message_id: str | None

    def as_wire(self) -> dict[str, Any]:
        return {
            "template_code": self.template_code,
            "channel": self.channel,
            "queued": self.queued,
            "recipient_address": self.recipient_address,
            # BOTH halves, spelled separately. "Queued" alone reads, to the
            # person who just clicked, as "a test email is on its way".
            #
            # ⚠ **IT WAS THE LITERAL `False` UNTIL 2026-09-07 AND THAT WAS A
            # CLAIM, NOT A COMPUTATION (`DEF-NOT-4525`).** True of mail, text
            # message and print, where no provider is connected — and false of
            # `in_app`, where this application IS the provider (BR-NOT-019) and
            # the rehearsal really does land in the clerk's own messages. Read
            # off `dispatchable` so the two halves of one answer cannot
            # contradict each other, and so the day an email provider is
            # connected this line does not have to be remembered.
            "will_be_delivered": self.dispatchable,
            "dispatchable": self.dispatchable,
            "problem": self.problem,
            "message_id": self.message_id,
        }


#: The sentence a System Admin reads once the test HAS been offered. It carries
#: no rule id and no file path: this string is drawn on a utility's screen and
#: DEF-335 is what happens when provenance is put in the copy instead of in the
#: comment beside it. The provenance, for us: BR-NOT-005 and A11 Addendum r2 §4
#: make the queue the only way out and a synchronous send endpoint a gate
#: failure. ⚠ AMENDED 2026-10-22 (`DEF-NOT-10537`): this read *"no mail,
#: text-message or print provider is connected yet"* — false once the Custom
#: SMTP adapter went live. It is now only the sentence for a channel the
#: dispatcher will NOT send on, and it names no provider either way; the
#: channel's own reason is the Channel status card's line.
TEST_WILL_QUEUE = (
    "A test goes to you at {address}, and to nobody else. It waits on the queue "
    "until this channel can send."
)

#: A channel with a third party behind it that the dispatcher WILL send on —
#: email through the utility's connector, today (`DEF-NOT-10537`). It reached
#: `TEST_WILL_ARRIVE` below until then, which told the admin to look in their
#: in-app messages for an email.
TEST_WILL_SEND = (
    "A test goes to you at {address}, and to nobody else. It goes out with the next "
    "send."
)

#: ⚠ **THE SAME SENTENCE WAS SERVED FOR IN-APP AND WAS NOT TRUE THERE
#: (`DEF-NOT-4525`, 2026-09-07).** The Product Owner asked of the note under
#: *Send test to me* — *"Queues, does not send"* — *"do you need this"*. It IS
#: needed and it IS true on mail, text message and print: no provider is
#: connected, so the row sits on the queue. It was never true on `in_app`,
#: where **this application is the provider** (`provider_seam.PLATFORM_ADAPTERS`,
#: BR-NOT-019) — the test arrives in the clerk's own in-app messages, and the
#: screen told them it would not. One live class reaches it: `staff_bulk_summary`.
#: That is hard-won law 1 in one sentence of copy, so the label is decided from
#: the SAME dispatch verdict the dispatcher uses rather than assumed.
#: ⚠ AMENDED 2026-10-22 (`DEF-NOT-10537`): it printed `{address}`, which for
#: in-app is the user's id — a database id on screen (B14 rule 31).
TEST_WILL_ARRIVE = (
    "A test goes to you, and to nobody else. It arrives in your own messages."
)

#: Why this template cannot be rehearsed at all. One per cause, because each has
#: a different fix and a screen that spells them the same way sends a System
#: Admin to look at the wrong thing.
TEST_NEEDS_ADMIN = (
    "Only a System Admin can queue a test message. You can read this template and "
    "its preview."
)
TEST_NEEDS_A_PUBLISHED_BODY = (
    "There is no published wording for this template yet, so a test would have "
    "nothing to render. Publish a version first and the test becomes available."
)
#: ⚠ **A FOURTH SENTENCE, AND IT IS HERE BECAUSE THE THIRD NEARLY COVERED IT.**
#: A class with no catalogue entry has no channel, so the first draft handed it
#: the "publish a version first" sentence above — which would send a System
#: Admin to publish wording that could never be published, because the class has
#: no merge-field whitelist to validate a body against. Two different causes
#: with two different fixes must not share a sentence; that is the whole lesson
#: of the refusal this task replaced.
TEST_NEEDS_A_CHANNEL = (
    "This template has no delivery channel set up yet, so there is nowhere to "
    "send a test. The note above the editor says what is missing for it."
)

#: ── CR-048 wave I · THE SHORT LABEL FOR EACH OF THE FIVE ────────────────────
#: One per sentence above, in the same order and for the same reason those
#: sentences are separate: each has a DIFFERENT FIX, and a label that spelled
#: two of them the same way would send a System Admin to look at the wrong
#: thing. Three or four words each — the sentence itself is one hover away.
TEST_WILL_QUEUE_LABEL = "Queues, does not send"
#: The honest label for a channel this product delivers itself — see
#: `TEST_WILL_ARRIVE` for why there are two.
TEST_WILL_ARRIVE_LABEL = "Sends to you"
TEST_NEEDS_ADMIN_LABEL = "System Admin only"
TEST_NEEDS_A_PUBLISHED_BODY_LABEL = "Publish a version first"
TEST_NEEDS_A_CHANNEL_LABEL = "No delivery channel"
#: `_test_recipient`'s own refusal — this platform holds no postal address, so a
#: printed template's rehearsal has nowhere to go. A statement about ADDRESSES,
#: never about providers; the two must not be spelled the same way.
TEST_NEEDS_AN_ADDRESS_LABEL = "No address to send to"


def template_test_offer(
    *, code: str, channel: str | None, actor: Any, can_edit: bool
) -> TemplateTestOffer:
    """SET-10's `can_test_send` + `test_send_reason`, decided in one place.

    Read-only and side-effect free: it is called while DRAWING the screen, and a
    read that queued anything would put a message on a utility's queue every
    time somebody opened a template.

    ⚠ **THE OFFER AND THE ACTION ASK THE SAME QUESTIONS IN THE SAME ORDER**, so
    a control this returns `True` for cannot then be refused by the route it
    opens — the *"enabled over a route that would refuse"* BR-SHL-025 forbids
    and the exact thing the wave-E lane declined to build rather than fake.
    """
    if not can_edit:
        return TemplateTestOffer(
            can_test_send=False, reason=TEST_NEEDS_ADMIN, label=TEST_NEEDS_ADMIN_LABEL
        )
    if channel is None:
        # A class with no catalogue entry has no channel to test on, and the
        # same payload already carries its own `catalog_unavailable` sentence
        # saying what is missing — so this points at that rather than repeating
        # it in words that could drift from it.
        return TemplateTestOffer(
            can_test_send=False,
            reason=TEST_NEEDS_A_CHANNEL,
            channel=None,
            label=TEST_NEEDS_A_CHANNEL_LABEL,
        )
    address, unavailable = _test_recipient(actor, channel)
    if unavailable is not None:
        # PRINT lands here, always and correctly: this platform holds an email
        # address and a mobile number for a user and no postal address, so a
        # printed template's rehearsal has nowhere to go. That is a statement
        # about ADDRESSES, not about providers, and the two must not be spelled
        # the same way.
        return TemplateTestOffer(
            can_test_send=False,
            reason=unavailable,
            channel=channel,
            label=TEST_NEEDS_AN_ADDRESS_LABEL,
        )
    try:
        template_service.resolve(code=code)
    except template_service.TemplateRefused:
        # The SAME resolution a real message uses (BR-BIL-025's ladder), so the
        # button is offered exactly when a real send would find a body.
        return TemplateTestOffer(
            can_test_send=False,
            reason=TEST_NEEDS_A_PUBLISHED_BODY,
            channel=channel,
            label=TEST_NEEDS_A_PUBLISHED_BODY_LABEL,
        )
    # ⚠ **WHICH OF THE TWO SENTENCES, ASKED OF THE DISPATCHER RATHER THAN
    # ASSUMED (`DEF-NOT-4525`).** `_channel_dispatch_facts` is this module's one
    # call on `provider_seam.channel_route`; reading the verdict here instead of
    # deciding again is what stops the label drifting from what actually happens
    # the day an email provider is connected. It costs at most one small SELECT
    # on a screen draw, and no query at all for print or in-app.
    if _channel_dispatch_facts(channel)["dispatchable"]:
        sentence = TEST_WILL_ARRIVE if channel == models.CHANNEL_IN_APP else TEST_WILL_SEND
        return TemplateTestOffer(
            can_test_send=True,
            reason=sentence.format(address=address),
            channel=channel,
            recipient_address=address,
            label=TEST_WILL_ARRIVE_LABEL,
        )
    return TemplateTestOffer(
        can_test_send=True,
        reason=TEST_WILL_QUEUE.format(address=address),
        channel=channel,
        recipient_address=address,
        label=TEST_WILL_QUEUE_LABEL,
    )


def queue_template_test(*, code: str, channel: str, actor: Any) -> TemplateTestResult:
    """Queue ONE real test message for this template, to the person clicking.

    ⚠ **THIS ENQUEUES AND NOTHING HERE SENDS.** No provider is called and no
    route in this product may offer one (BR-NOT-005); `provider_seam`'s verdict
    travels back untouched so the screen can say whether the dispatcher will
    send the row (amended 2026-10-22, `DEF-NOT-10537`: it read *"the row will
    not leave"*).

    ⚠ **THE ROLE GATE IS ON THE ROUTE AND DELIBERATELY NOT HERE (DEF-2515).** A
    role check inside a service refuses a background worker, because a job actor
    carries no role by design — and a second check behind the door can only ever
    produce a FALSE refusal, never catch a real one. A send test is user-
    initiated and is reached from exactly one door, which is where it is gated.

    **THE IDEMPOTENCY TUPLE IS `(tenant, source_type, source_id, channel,
    copy_no)`** — `outbound_messages`' own unique key — and here it reads
    `(this utility, "test", THIS TEMPLATE VARIANT, this channel, the next copy
    number)`. The source is the template VARIANT row rather than the class code,
    because that is the thing whose button was pressed and the thing the pin
    resolves to; inventing a document id to satisfy the column would put a queue
    row on the screen pointing at a bill that does not exist.

    **A SECOND CLICK MUST GIVE A SECOND ROW, WHICH IS THE OPPOSITE OF RULE 6's
    USUAL ANSWER, AND IT IS DELIBERATE.** `copy_no` is the documented escape
    hatch for *"a deliberate, human-requested extra copy"*, so the count of rows
    already on this tuple becomes the next copy number. Collapsing the two would
    return `created=False`, which is indistinguishable from a replay — the
    person who pressed the button twice would be told nothing happened.
    `DEF-2512` is that mistake made the other way round on payment-plan notices,
    where it cost a customer being chased once and never again.
    """
    resolved = template_service.resolve(code=code)
    address, unavailable = _test_recipient(actor, channel)
    if unavailable is not None:  # pragma: no cover - the route checks the offer first
        raise RuleRefused(unavailable)
    facts = _channel_dispatch_facts(channel)

    existing = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(),
        source_type=TEST_SOURCE_TYPE,
        source_id=resolved.template_id,
        channel=channel,
    ).count()

    with transaction.atomic():
        write = services.queue_document(
            source_type=TEST_SOURCE_TYPE,
            source_id=resolved.template_id,
            channels=(channel,),
            template=services.TemplatePin(
                code=code, template_id=resolved.template_id, version=resolved.version
            ),
            recipients=(services.Recipient(channel=channel, address=address),),
            copy_no=existing,
            actor=actor,
            job="template_send_test",
            # `DEF-NOT-4449` — the SET-10 designer's send-test, the same sample
            # values its preview pane renders from. The whole argument is on the
            # SET-12 test-send in `queue_test` above; the two are one behaviour
            # reached by two buttons and must not diverge.
            render_context=template_preview.sample_context(code),
        )
        # Hard rule 7. The action NAMES the rehearsal, so nobody reading this
        # trail later takes the row for a message sent to a customer — which is
        # the same reason `account_id` is left null on the row itself.
        audit.money_action(
            actor,
            AUDIT_ACTION_TEMPLATE_TEST,
            AUDIT_ENTITY_TEMPLATE,
            str(resolved.template_id),
            before={},
            after={"template_code": code, "channel": channel, "copy_no": existing},
        )

    message = write.messages[0] if getattr(write, "messages", ()) else None
    return TemplateTestResult(
        template_code=code,
        channel=channel,
        queued=True,
        recipient_address=address,
        dispatchable=bool(facts["dispatchable"]),
        problem=facts["dispatch_problem"],
        message_id=str(getattr(message, "id", "")) or None,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-017@cr009a17 (12-governance/11-change-requests.md → CR-009 in full including the three PO ruling sets of 2026-08-17 · 04-docs/05-modules/10-notifications/02-business-rules.md · apps/notifications/services.py (`queue_document`, the ONE write path) · apps/notifications/provider_seam.py (`channel_route`, whose deferred verdict is left untouched) · apps/tenancy/settings_families.py COLLECTIONS)
# generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
# checklist: A✔ B✔ C✔ D=deferred(the HTTP half is rules_api.py) E=deferred(the screen is NotificationRules.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see rules_api.py's trailer — the RED proofs for this packet are recorded there
# exceptions: (0) [CR-048 A1, 2026-08-29] THIS FILE GAINED ONE READ AND NO NEW RULE. `channel_switches` is a narrow, write-free, two-SELECT view of one event's on/off switches, added because the QUEUE has to ask this question once per document and `rule()` is the screen's read (fifteen events, up to forty-five `get_or_create` writes, inside the caller's transaction). It states no default of its own: the tenant's rows answer when they exist and `_seeded_rule_kwargs` / `_seeded_channel_enabled` answer when they do not — the same two expressions `_ensure_rules` writes, which is why `_seeded_channel_enabled` was factored out rather than copied. The DECIDING is all in `services.channel_decision`; this file only reports what a System Admin saved. (1) NO SEND. `queue_test` writes a queue row through `services.queue_document` and makes no provider call; `provider_seam.channel_route`'s deferred verdict is returned UNCHANGED so the screen can say the row will not leave. A11 r2 §4's no-synchronous-send rule is asserted against this surface by name. (2) OQ-261 IS RAISED, NEVER ANSWERED — `_refuse_staff_recipient` refuses every spelling of "send it to X" with the open question's id. (3) THE LADDER IS READ, NOT STORED. Its five ruled figures stay in `settings_families.COLLECTIONS` where the live engine reads them; SET-12D writes them through the existing `PUT /settings/collections`. One home for the rule, one store for the figure — the judgment is in the module docstring and in the decision log. (4) NO DELIVERY COUNTS — `delivered`/`failed` are provider facts nothing in this repo can write (BR-NOT-013), so the "last 30 days" rail is served as SENT-only with the other two reported unavailable.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
