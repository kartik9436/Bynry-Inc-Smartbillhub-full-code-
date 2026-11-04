# ── Trace ──────────────────────────────────────────────
# Story:   CR-115-BRC05 §1.6 R31 — *"i dont have Run button here"*. The control
#          that answers it offers **Preview** and **Apply**, and every run
#          records which it was and who started it.
# Rules:   BR-INT-039 (every attempt is a durable record — a preview is an
#          attempt) · BR-INT-074 (a preview writes nothing THAT IS BEING
#          RECONCILED; see the decision log of 2026-09-17) · 🔒 migration
#          ordering (CLAUDE.md sensitive paths)
# Tests:   06-backend/tests/test_cr115_run_now.py
# Impacts: apps/integrations/models.IntegrationRun · apps/integrations/runs.row
#          (both columns travel on the LIST shape) · 06-backend/openapi/schema.json
# ───────────────────────────────────────────────────────
"""integrations 0012 — two nullable columns on `integration_run`: `mode` and `started_by_name`.

HUMAN-OWNED (🔒 migration ordering). HUMAN-REVIEW-PENDING — AI-authored
2026-09-17 under the PO ruling of 2026-08-09; the review-ledger row is in
`12-governance/09-human-review-ledger.md`.

⚠ **TWO COLUMNS AND NOT THREE, AND THE THIRD WAS THE TEMPTING ONE.** The brief
asks a run to record `started_by` as *schedule | person + their name*. `trigger`
is already `("manual", "scheduled", …)` on this same row and already answers the
*schedule or a person* half; a `started_by` column beside it would be one fact
written twice, and the copy nobody reads is the one that drifts. So only the
fact the existing columns cannot carry gets a column: **which person**.

⚠ **BOTH ARE NULLABLE AND NEITHER HAS A DEFAULT.** `integration_run` is a
PostgreSQL partitioned parent; a `NOT NULL DEFAULT` on it rewrites every
partition. More importantly, an operation with no preview/apply choice to make
has no honest value to put in `mode` — a default of `apply` would be the unsafe
option arriving without anybody typing it (hard-won law 3), and a default of
`preview` would claim of 30,000 historical rows that somebody chose it.

⚠ **THE APPEND-ONLY TRIGGER IS UNTOUCHED.** It refuses UPDATE and DELETE on a
run whose `finished_at` is set (migration 0001); these columns are written while
the row is still open, exactly as `attempted` is.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0011_cr110_partner_key_directory"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationrun",
            name="mode",
            field=models.TextField(
                blank=True,
                null=True,
                choices=[("preview", "preview"), ("apply", "apply")],
            ),
        ),
        migrations.AddField(
            model_name="integrationrun",
            name="started_by_name",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §1.6 (R31 verbatim) + BR-INT-039/074
# generated: 2026-09-17 by the CR-115 Run-now lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_run_now.py · makemigrations --check
# exceptions: none
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
