# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page — CR-009 · the TABLES half)   Screens: S8
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — PO 2026-08-17) ·
#           BR-NOT-018 (an event with no trigger is drawn and refused by name) ·
#           BR-NOT-005 (queue only) · BR-NOT-006 (language variants) ·
#           BR-NOT-009 (quiet hours are the tenant's window) ·
#           BR-TEN-016 (a settings edit is audited, before→after) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE lands in migration 0009)
# Tests:    06-backend/tests/test_cr_009_notification_rules.py ·
#           06-backend/tests/test_cr_009_notification_rules_isolation.py
# Impacts:  apps/notifications/rule_service.py (the ONLY write path) ·
#           apps/notifications/apps.py (registration)
# ───────────────────────────────────────────────────────
"""The per-event notification rule — the table CR-009's event matrix stands on.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — these rows decide WHICH customers are
contacted, on which channel, and how a collections message escalates, which is
a compliance surface (BR-NOT-009 quiet hours, BR-PAY-017's regulated ladder).
AI-authored 2026-08-17 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"); row in 12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE EVENT IS A CONSTANT. THE RULE IS THE TENANT'S. ONE ROW PER PAIR.    ║
╚══════════════════════════════════════════════════════════════════════════╝
`rule_catalog.EVENTS` is platform vocabulary — a utility cannot invent an event,
because only a writer in this codebase can fire one. This table holds what a
utility DECIDES about each: on or off, who, which channels, when. `event_key`
is therefore a plain TextField validated against the catalogue in the service
and NOT a foreign key: there is no event table to point at, and inventing one
would put a migration between the platform and its own vocabulary.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT A COLUMN, AND WHY — read this before adding one
────────────────────────────────────────────────────────────────────────────
* **`staff_recipient`.** [AMENDED 2026-08-18] STILL not a column, and no
  longer because the question is open: OQ-261 CLOSED (PO 2026-08-17, verbatim
  *"the user who started the action, plus all System Admins for failures"* →
  BR-NOT-021). The recipient is a ruled PLATFORM POLICY, implemented once in
  `staff_recipients.py` — a column here would be a per-rule second answer free
  to disagree with it, and `rule_service.update_rule` refuses one with the
  ruling quoted (where it used to raise `NotImplementedError("OQ-261")`).
* **A medical / life-support filter.** PO ruling 2026-08-17, verbatim: *"Skip
  it ; not required as this point of time"*. Absent BY RULING. Written down
  here because the clause IS in the PO's own requirement text, so a later
  reader diffing the CR against the schema would otherwise file the absence as
  a defect and rebuild it.
* **THE ESCALATION LADDER'S DAY NUMBERS AND MONEY THRESHOLDS.** This is the
  important one, and it is a decision rather than an omission. PO ruling
  2026-08-17, verbatim: *"we bring all internal external ntification rule sat
  one place and they are part of notification settings"* — SET-12D owns the
  chasing schedule. **It owns it as a SCREEN. It does not re-store it.** The
  five figures the ruling names — reminder at 3 days after due, notice tiers
  at 10 then 5 days, final notice at 48 hours, the $25 balance floor and the
  25% partial-payment pause — are stored today in
  `apps.tenancy.settings_families.COLLECTIONS` and are read there by the LIVE
  engine (`apps/payments/settings_seam.py`, `apps/notifications/notices.py`).
  Copying them into a second table is exactly the *"second home for the same
  rule"* the CR warned against, and the copy that drifts is the one a customer's
  disconnect notice is scheduled from. So SET-12D's ladder card reads and
  writes the EXISTING store through the existing `GET|PUT /settings/collections`
  contract, and the collections rule-page card gives those rows up. **ONE HOME
  for the rule; ONE STORE for the figure; no migration on a live ladder.**
  Recorded as a judgment in `12-governance/02-decision-log.md`, 2026-08-17.
* **`last_30_days_sent/delivered/failed`.** Counts are computed from
  `outbound_messages`, never stored — and `delivered`/`failed` cannot be
  computed at all: BR-NOT-013 makes both PROVIDER facts and no adapter exists
  on any channel, so `delivery_ops` never writes them. The rail reports NOT
  REPORTED rather than zero, which is the discipline the delivery dashboard
  already keeps.

────────────────────────────────────────────────────────────────────────────
ONE ROW PER TENANT × EVENT, CREATED ON FIRST READ WITH THE CATALOGUE DEFAULTS
────────────────────────────────────────────────────────────────────────────
Like `NotificationSettings`, there is no "unset" state: a tenant that has never
opened SET-12 still has a complete configuration, and it is the one the
catalogue declares. An absent row and a defaulted row must not be two
behaviours, because something would then have to interpret the difference and
nothing rules on what it means.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.notifications.rule_catalog import (
    CUSTOMER_SCOPE_ALL_CONTACTS,
    FAILURE_RETRY_THEN_EMAIL,
    LANGUAGE_AUTO,
    PLAN_CLASS_ALL,
    QUIET_HOURS_RESPECT,
    TRIGGER_IMMEDIATE,
)
from core.dbfields import uuid7_pk


class NotificationRule(models.Model):
    """What this tenant has decided about ONE event. SET-12 row, SET-12D page."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: A key of `rule_catalog.EVENTS_BY_KEY`. Validated in the service against
    #: that constant — see the docstring for why it is not an FK.
    event_key = models.TextField()

    #: SET-12's On toggle. Ships TRUE for events with a real trigger and FALSE
    #: for the six that have none (OQ-249 field work, OQ-262 the three with no
    #: writer at all) — the unsafe option is the one you type (hard-won law 3),
    #: and the unsafe option here is a switch that reads as "this now happens".
    enabled = models.BooleanField(default=True)

    # ── Audience (SET-12D card 1) ───────────────────────────────────────
    #: `rule_catalog.CUSTOMER_SCOPES`. Meaningless on a staff event and the
    #: service refuses to change it there rather than storing a value nothing
    #: reads.
    customer_scope = models.TextField(default=CUSTOMER_SCOPE_ALL_CONTACTS)
    #: The service scope — `"all"` or one service code from the tenant's own
    #: seeded ten (BR-RAT-024). A code, not an FK: services are tenancy's
    #: lookup and B11 F-3's deferred-FK convention is what this repo uses
    #: across module lines.
    service_scope = models.TextField(default="all")
    #: `rule_catalog.PLAN_CLASSES`.
    plan_class = models.TextField(default=PLAN_CLASS_ALL)
    #: The requirement's *"skip accounts on payment plans"*. Ships TRUE on
    #: `past_due_reminder` — the CR's own words, *"Collections events default to
    #: their protective filters (past-due skips payment plans)"* — and FALSE
    #: everywhere else.
    skip_accounts_on_payment_plan = models.BooleanField(default=False)

    # ── Timing (SET-12D card 3) ─────────────────────────────────────────
    trigger_mode = models.TextField(default=TRIGGER_IMMEDIATE)
    #: Only with `trigger_mode = offset_days`. NULL otherwise, and NULL is not
    #: zero: zero would be a same-day send, which is a different rule.
    offset_days = models.IntegerField(null=True, blank=True)
    #: Only with `trigger_mode = fixed_time`. A TENANT-LOCAL wall clock time,
    #: the same discipline `NotificationSettings.quiet_hours_start` documents —
    #: storing a UTC instant would move the daily digest twice a year.
    fixed_time = models.TimeField(null=True, blank=True)
    #: BR-NOT-009. `respect` holds SMS until the window opens; `override` is the
    #: requirement's *"override for emergencies"*.
    quiet_hours_mode = models.TextField(default=QUIET_HOURS_RESPECT)
    failure_policy = models.TextField(default=FAILURE_RETRY_THEN_EMAIL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_rules"
        constraints = [
            # ONE rule per event per tenant. Two rows for one event is two
            # answers to "does this send?", and whichever the engine read first
            # would be the product's behaviour.
            models.UniqueConstraint(
                fields=["tenant", "event_key"], name="uq_notification_rules_tenant_event"
            ),
            # `offset_days` belongs to exactly one trigger mode. Without this a
            # rule can carry "immediate, offset 7 days" — two instructions, and
            # nothing says which wins.
            models.CheckConstraint(
                condition=Q(trigger_mode="offset_days", offset_days__isnull=False)
                | (~Q(trigger_mode="offset_days") & Q(offset_days__isnull=True)),
                name="ck_notification_rules_offset_days",
            ),
            models.CheckConstraint(
                condition=Q(trigger_mode="fixed_time", fixed_time__isnull=False)
                | (~Q(trigger_mode="fixed_time") & Q(fixed_time__isnull=True)),
                name="ck_notification_rules_fixed_time",
            ),
        ]
        indexes = [
            # SET-12 reads the whole matrix for one tenant, every time.
            models.Index(fields=["tenant", "event_key"], name="ix_notification_rules_tenant"),
        ]


class NotificationRuleChannel(models.Model):
    """One channel of one rule — SET-12D card 2, one row per channel.

    A row exists for every channel the EVENT offers (`rule_catalog`), whether
    the tenant has it on or off, so the screen draws the same rows for every
    tenant and an absent row never has to be read as "off".

    ⚠ Only `models.CHANNELS` values ever reach this table. Portal, Mail and
    In-app are named in the requirement and have no implementation; they are
    carried in the catalogue as `unavailable_channels` with a reason and are
    drawn disabled (BR-SHL-025). A row here for a channel nothing can queue
    would be a setting whose only effect is to look like one.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rule = models.ForeignKey(
        NotificationRule, on_delete=models.CASCADE, related_name="channels", db_column="rule_id"
    )
    channel = models.TextField()  # models.CHANNELS
    enabled = models.BooleanField(default=True)
    #: The `catalogs.py` class this channel renders from, when the event has
    #: one. NULL means the platform has no template class for this event on
    #: this channel — SET-12D states that rather than offering a variant picker
    #: over nothing (BR-SHL-025).
    template_code = models.TextField(null=True, blank=True)
    #: BR-NOT-006, AS AMENDED 2026-09-23 (`OQ-CUS-12619`): `auto` means the
    #: UTILITY's default language, never the account's `preferred_language` —
    #: PO, verbatim, *"(a) Portal only; emails in English."* `english_only`
    #: means English. ⚠ **THIS COMMENT READ *"`auto` resolves the account's
    #: `preferred_language` … `english_only` pins it"*, AND NEITHER HALF WAS
    #: EVER TRUE: nothing that queues a message reads this column** — it is
    #: saved, served and validated by `rule_service` and read by no writer
    #: (`DEF-NOT-6355`). Every message's language is chosen by its writer,
    #: which passes the utility's default whatever is saved here.
    language_mode = models.TextField(default=LANGUAGE_AUTO)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_rule_channels"
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "channel"], name="uq_notification_rule_channels_rule_channel"
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-017@cr009a17 (the same packet apps/notifications/rule_catalog.py was cut from — 12-governance/11-change-requests.md → CR-009 in full including the three PO ruling sets of 2026-08-17 · 04-docs/05-modules/10-notifications/02-business-rules.md · apps/notifications/models.py · apps/tenancy/settings_families.py COLLECTIONS)
# generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only; the routes are rules_api.py) E=deferred(no-frontend-half in this file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ship with migrations 0008/0009 — see their trailers
# exceptions: (1) NO `staff_recipient` COLUMN — [AMENDED 2026-08-18] the recipient is RULED platform-wide (BR-NOT-021, OQ-261 closed) and lives in `staff_recipients.py`, never per rule. (2) NO MEDICAL/LIFE-SUPPORT FILTER — PO ruling 2026-08-17, absent by ruling. (3) NO LADDER TABLE: the five ruled figures stay in `settings_families.COLLECTIONS` where the live engine reads them, and SET-12D becomes their ONE SCREEN rather than a second store — the judgment and its reasoning are in the docstring and in the decision log. (4) NO DELIVERY COUNTERS — `delivered`/`failed` are provider facts nothing in this repo can write (BR-NOT-013).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
