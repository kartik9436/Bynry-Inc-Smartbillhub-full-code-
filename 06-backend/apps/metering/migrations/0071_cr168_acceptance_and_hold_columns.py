# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P0.2 (the technician's own
#           acceptance columns), P0.3 (hold reason, expected return, held time),
#           P1.6 (an accepted order stays findable — the index), P2.17 (the
#           premises walk — the index)
# Rules:    CR-168-BRC10 §7.3 (migrations table, row metering/0071) · judgment
#           J1 (a hold reason is a lookup FK) · BR-MET-110 (`accepted_by` is the
#           OFFICE's act and is not touched) · CLAUDE.md hard rule 1 · rule 3
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py
# ───────────────────────────────────────────────────────
"""metering 0071 — the technician's acceptance, the hold's reason, and two indexes.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

⚠ **`work_orders` IS METERING'S TABLE, SO THE MIGRATION IS METERING'S** — the
`metering/0050` reasoning: Django resolves `model_name` inside the migration's
own app. ⚠ **AND IT RUNS AFTER `work/0028`**, because `hold_reason_id` points at
`work_hold_reasons`, which that file creates.

**No money column moves.** `work_orders` is the table the acceptance money path
writes (cost lines, meter reads), and every column here is NULL or defaulted to
0, so no existing order reads differently after it. `accepted_by` /
`accepted_at` — the office's acceptance (`BR-MET-110`) — are untouched; the
technician's acceptance is a DIFFERENT act by a different person and gets
columns of its own (see the model's comment).

THE REVERSE drops the eight columns and three indexes (the third, on
`work_order_templates`, is P3.23's — moved here from §7.3's `work/0031` row
because that table is metering's model).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0070_def_wrk_9266_jobs_match_hardware"),
        ("work", "0028_cr168_hold_reasons_and_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="accepted_at_technician",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="accepted_by_technician",
            field=models.ForeignKey(
                blank=True,
                db_column="accepted_by_technician_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="work.technician",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="declined_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="declined_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="hold_reason",
            field=models.ForeignKey(
                blank=True,
                db_column="hold_reason_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="work.workholdreason",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="hold_expected_return_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="held_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="held_seconds",
            field=models.IntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(
                fields=["tenant", "state", "completed_at"], name="ix_work_orders_completed"
            ),
        ),
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(fields=["tenant", "premises"], name="ix_work_orders_premises"),
        ),
        # P3.23 — the templates list pages in SQL. §7.3 listed this under
        # `work/0031`; `work_order_templates` is METERING's model, so the index
        # is declared here (a work migration cannot name a metering model).
        migrations.AddIndex(
            model_name="workordertemplate",
            index=models.Index(
                fields=["tenant", "active", "name"], name="ix_wo_templates_active_name"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (row metering/0071) · §7.4 J1
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
