# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail — the store the flow has never
#           had)   Screens: S8 · S30
# Rules:    BR-NOT-005 (forward-only lifecycle; retry ×3 IS the answer to a
#           transient failure, so a soft bounce never reaches this table) ·
#           BR-NOT-013 (provider facts; this ships a STORE, not a writer of
#           one) · BR-PAY-018 (the paper half of the same idea, already built)
#           · CLAUDE.md rule 1 (tenant scoping — the RLS policy is 0020) ·
#           rule 6 (the partial unique IS the idempotency guarantee)
# Change:   DEF-NOT-5632, 2026-09-17 — a hard bounce and a spam complaint had
#           nowhere to be recorded, so the address was sent to again.
# ───────────────────────────────────────────────────────
"""notifications 0019 — `suppressed_addresses`, the do-not-send list.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

WHAT THIS TABLE IS FOR, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
`apps/notifications/models.py` has stated since the outcome vocabulary landed
that *"a hard bounce SUPPRESSES the address and the consumer keeps getting their
bill on paper"* — and nothing recorded a suppression, so the next bill run
queued to the same dead mailbox. This is the column that makes the sentence
true. The reasoning for the key, the shape and the release path is in
`apps/notifications/suppression_models.py`; this file is the DDL and the two
things about it that are decisions rather than transcription.

THE UNIQUE CONSTRAINT IS PARTIAL, AND IT IS DOING TWO JOBS
────────────────────────────────────────────────────────────────────────────
`UNIQUE (tenant_id, channel, address) WHERE released_at IS NULL`.

  * **Idempotency (CLAUDE.md rule 6).** A provider's feedback webhook is
    delivered twice — every ESP documents at-least-once delivery — and two
    workers can handle one morning's batch. Both reach the INSERT; the DATABASE
    refuses the second. That is the only guarantee that survives a retry our own
    code never saw, which is the same argument `uq_outbound_msgs_source_channel`
    makes one table over.
  * **It is what lets a RELEASE keep the row.** A plain `UNIQUE (tenant_id,
    channel, address)` would force a release to DELETE, and the record of why a
    customer stopped receiving email would be gone. `audit_log` is pruned on a
    retention schedule, so there would eventually be no answer anywhere — the
    cost `OQ-1340` is open about on the payments correction path. With the
    predicate, a released row is history and the third time an address goes bad
    there are three rows and a clerk can see the pattern.

No separate index is declared on `(tenant_id, channel, address)` for the
dispatcher's lookup: this constraint's index already leads on exactly those
three columns, and a second index on the same prefix is write cost for nothing
(`outbound_messages` makes the same call in its own `Meta`).

NO CHECK CONSTRAINT ON `reason`, AND THAT MATCHES THE MODULE
────────────────────────────────────────────────────────────────────────────
`reason` is a plain `text`, exactly as `outbound_messages.status` is. Migration
0018 states the module's reasoning and it holds here: the vocabulary lives in
Python (`suppression_models.REASONS`), so adding a lawful value is not a DDL
change and does not put a migration between the product and its own words. The
guard that actually matters — **a soft bounce can never produce a row** — is at
the single writer (`suppression.suppress`), where it can carry a sentence a
person can read, rather than in a constraint that can only say `23514`.

⚠ **NOTHING WRITES A ROW HERE TODAY, AND THAT IS STATED RATHER THAN IMPLIED**
(hard-won law 2). `BR-NOT-013` still holds: no provider adapter with a feedback
door exists on any channel, so no `bounced_hard`, `complained` or `unsubscribed`
is ever written, so nothing calls `suppression.suppress_for_outcome`. **The READ
half is live from this commit** — `dispatcher._selectable` consults the list on
every cycle and `services.queue_document` holds a new row addressed to a
suppressed address — so on the day an adapter lands, the guarantee is already
enforced instead of still to be wired.

REVERSIBLE, AND THE REVERSE LOSES THE LIST
────────────────────────────────────────────────────────────────────────────
`DeleteModel` drops the table and everything on it. That is honest for a table
whose rows are all written after this migration, and there is no data migration
in either direction: nothing existing is read, rewritten or interpreted.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0018_def_not_5626_normalised_outcomes"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SuppressedAddress",
            fields=[
                # Spelled out rather than calling `core.dbfields.uuid7_pk()`,
                # which is how `0011_cr009_in_app_messages` writes the same
                # field. A migration is a record of what the schema was asked to
                # become ON THIS DATE (0018 states the module's reasoning), and
                # a helper that returns a field is free to change shape under
                # this file afterwards.
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("channel", models.TextField()),
                ("address", models.TextField()),
                ("reason", models.TextField()),
                ("reason_detail", models.TextField(blank=True, null=True)),
                ("suppressed_at", models.DateTimeField()),
                ("suppressed_by", models.UUIDField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("released_by", models.UUIDField(blank=True, null=True)),
                ("released_note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_message",
                    models.ForeignKey(
                        blank=True,
                        db_column="source_message_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="notifications.outboundmessage",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "suppressed_addresses",
            },
        ),
        migrations.AddIndex(
            model_name="suppressedaddress",
            index=models.Index(
                condition=Q(released_at__isnull=True),
                fields=["tenant", "-suppressed_at"],
                name="ix_suppressed_addrs_active",
            ),
        ),
        migrations.AddIndex(
            model_name="suppressedaddress",
            index=models.Index(
                fields=["tenant", "channel", "address"],
                name="ix_suppressed_addrs_address",
            ),
        ),
        migrations.AddConstraint(
            model_name="suppressedaddress",
            constraint=models.UniqueConstraint(
                condition=Q(released_at__isnull=True),
                fields=["tenant", "channel", "address"],
                name="uq_suppressed_addrs_active",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5632 (12-governance/10-defect-log.csv) · apps/notifications/suppression_models.py (the whole design argument) · apps/notifications/models.py (the guarantee this makes true) · apps/runbooks/definitions/undeliverable_contacts.py (the policy, deliberately not duplicated) · 04-docs/02-decisions/02-database-design-brief.md DB-16 + §3
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 4 — the do-not-send list)
# checklist: A✔ B=deferred(no frontend half — the blocked-addresses SCREEN is DEF-NOT-5637) C✔ D=deferred(no API call — a migration) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_def_not_5632_suppression.py, applied and exercised against a real PostgreSQL 16; the partial unique was proved by inserting the same address twice and reading the IntegrityError, and proved NOT to fire once the first row is released
# exceptions: (1) NOTHING WRITES A ROW TODAY — BR-NOT-013 holds and no adapter exists; the READ half IS live. Stated out loud (law 2). (2) NO CHECK CONSTRAINT on `reason` — the module's own precedent, see the docstring. (3) `DEF-RBS-4331` IS NOT CLOSED by this table: the customers-side "this contact's channel is undeliverable, dated" is a different fact with a different key and is still owed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
