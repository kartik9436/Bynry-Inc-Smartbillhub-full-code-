# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-007 (the retention job's run record) · US-MET-020 (the same
#           record for `meter_reads` — "one mechanism, two tables", US-AUD-007 §5)
# Rules:    BR-AUD-012 (2 yr hot → cold, 7 yr total, AUTOMATIC, audited) ·
#           BR-MET-055 (the identical reads rule this one is patterned on) ·
#           BR-AUD-002 (archival MOVES partitions; it never mutates rows) ·
#           CLAUDE.md rule 1 (why this table carries NO tenant policy — it has
#           no tenant column; see the docstring)
# ───────────────────────────────────────────────────────
"""audit 0004 — `archive_job_runs`, the retention job's append-only run record.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-15 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). A row is requested in 12-governance/09-human-review-ledger.md.

WHY THIS TABLE HAS NO `tenant_id` AND NO RLS POLICY
---------------------------------------------------
Every other table in this product is tenant-scoped and the reflex is right. This
one is not, deliberately, and the reason is physical: `audit_log` and
`meter_reads` are partitioned by MONTH, not by tenant (B2 §5), so one partition
holds every tenant's rows and detaching it is a platform storage operation
belonging to no tenant. A `tenant_id` column here would have to be invented,
and inventing one would either duplicate the run per tenant (a lie about what
happened once) or pick one arbitrarily (a lie about whose it was).

The tenant-visible record of the same event is NOT missing: `core.archival`
writes one `audit_log` row per tenant whose rows were in the partition
(`meter_reads.partition_archived` / `audit_log.partition_archived`), under that
tenant's own context, which is where BR-AUD-012's "audited" clause lands and
where RLS applies. This table is the operator's record; it carries partition
names, counts and SHA-256 digests and no tenant data at all.

That is why it is absent from the B2 §3 RLS apply-list and why
tests/test_tenant_isolation.py's exempt-list sweep does not name it: the sweep
looks for tables that HAVE a `tenant_id` column and no policy, and this one has
no such column.
"""

from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_rls_audit_partitions"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchiveJobRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("table_name", models.TextField()),
                ("run_date", models.DateField()),
                ("hot_window_months", models.IntegerField()),
                ("retention_months", models.IntegerField()),
                ("archived", models.JSONField(blank=True, default=list)),
                ("purged", models.JSONField(blank=True, default=list)),
                ("status", models.TextField(default="success")),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "archive_job_runs",
                "indexes": [
                    models.Index(
                        fields=["table_name", "run_date"], name="ix_archive_runs_table_date"
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-007@6b3d915 (EP-AUD-03 retention story; co-packet US-MET-020@f4a1c02 — EP-MET-03)
# generated: 2026-08-15 by story-coder v1 (metering + assets + audit lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row requested)
# gates: ruff✔ black✔ · makemigrations --check clean for apps.audit · migrate from empty on sqlite and on a live Postgres cluster
# exceptions: no tenant column and therefore no RLS policy — the reason is in the docstring and is a property of month-partitioning, not an omission · no unique constraint on (table_name, run_date): a rerun is a LAWFUL no-op run that must still be recorded (US-MET-020 TC-5 / US-AUD-007 TC-5), so two rows for one date is the correct outcome, not a duplicate
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
