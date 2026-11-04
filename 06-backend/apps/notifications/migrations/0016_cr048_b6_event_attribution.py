# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 / SET-12D — the event matrix and the rule page)
#           Screens: S8 (Settings → Notifications) · SET-12D's right rail
# Rules:    BR-NOT-013 (delivery is out of this release on EVERY channel — so
#           `delivered` and `bounced` stay UNREPORTED and are not what these
#           columns are for) · BR-NOT-017 (one home for every rule) ·
#           BR-NOT-024 (print is the floor on every customer document — which
#           is why a suppression always has a surviving row to ride) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (the five-column
#           idempotency key is UNCHANGED by this migration)
# Change:   CR-048 wave B task B6 — *"per-event delivery counts, last thirty
#           days … real numbers instead of zeroes"*
# ───────────────────────────────────────────────────────
"""notifications 0016 — `outbound_messages.event_key` + `.rule_suppressed_channels`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-30 under the PO ruling of 2026-08-09; the row in
12-governance/09-human-review-ledger.md is owed by the merge lane, because a
CR-048 backend lane is forbidden from writing a shared governance register while
siblings are live in it. **Reported, not skipped** — see the lane report.

WHAT THIS IS FOR, in one sentence a System Admin would recognise: the rule page
can say *"12 queued in the last 30 days, 3 of them held, and your email switch
stopped 5"* instead of drawing three zeros.

TWO COLUMNS, AND NEITHER IS A DELIVERY COUNT
────────────────────────────────────────────────────────────────────────────
`delivered` and `bounced` are PROVIDER facts. No adapter exists on any channel
(BR-NOT-013), so nothing in this repo can write them and nothing here tries.
A queued row is NOT a delivered one, and turning one into the other is the
single most tempting lie this module has available. The rail keeps saying NOT
REPORTED for both, with its reason, exactly as it does today.

WHY A COLUMN RATHER THAN A DERIVATION
────────────────────────────────────────────────────────────────────────────
`rule_models.py` already rules that per-event counts are *"computed from
`outbound_messages`, never stored"* — so the only open question was how a queue
row states which event it belongs to, and it cannot be inferred.
`services.channel_decision` measured all three candidates before wave A and
refused each one: `source_type` is one-to-MANY onto events, `category` is the
CONSUMER category, and the template pin is ambiguous in both directions. So the
writer that KNOWS the event stamps it, and the count is arithmetic over a fact
rather than a reverse map.

BOTH ARE NULLABLE AND NOTHING ALREADY QUEUED CHANGED
────────────────────────────────────────────────────────────────────────────
Every row written before CR-048 wave B carries NULL in both, and every writer
that names no event still writes NULL. The idempotency key — (tenant,
source_type, source_id, channel, copy_no) — is untouched: neither column is in
it, so no message that was refused as a duplicate yesterday is accepted today
and none that was accepted is refused.

THE INDEX IS PARTIAL, on `event_key IS NOT NULL`, for the reason the dispatch
index gives about itself: the un-attributed rows are the bulk of the table and
the rail's query never returns one.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0015_cr009_sender_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="outboundmessage",
            name="event_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="outboundmessage",
            name="rule_suppressed_channels",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="outboundmessage",
            index=models.Index(
                condition=Q(event_key__isnull=False),
                fields=["tenant", "event_key", "-created_at"],
                name="ix_outbound_msgs_event",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B task B6 (12-governance/11-change-requests.md → CR-048 · apps/notifications/rule_models.py (the ruling that counts are computed, never stored) · apps/notifications/services.py channel_decision (the three rejected derivations) · apps/notifications/rules_api.py RELEASE_POSTURE (the delivery_counts_available posture this does NOT change) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-013)
# generated: 2026-08-30 by story-coder (CR-048 wave B tasks B6 + B10 lane)
# checklist: A✔ B=deferred(no frontend half — the rail that READS these counts is NotificationRules.tsx and a sibling lane is building it) C✔ D=deferred(no API call — a migration; the counts are served on the existing GET /notification-rules routes) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr048_b6_b10.py under PostgreSQL — RED PROVED FIRST: with the columns absent the rail could not name a single event's rows, and the per-event count query has no column to group on. Quoted in the lane report.
# exceptions: (1) NULLABLE, AND NO PRE-EXISTING WRITER SETS EITHER — nothing already queued changed and the rule-6 key is untouched. (2) NO DELIVERED / BOUNCED COLUMN AND NO DERIVATION OF ONE — BR-NOT-013; both stay reported as unavailable with their reason. (3) THE REVIEW-LEDGER ROW IS OWED BY THE MERGE LANE, not written here: this lane may not touch a shared governance register while siblings are live in it. G7 will FAIL until that row lands, and that is the correct signal rather than a silent gap.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
