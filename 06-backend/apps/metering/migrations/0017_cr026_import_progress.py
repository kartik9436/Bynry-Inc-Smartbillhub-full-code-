# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 runner)   Change: CR-026 (PO 2026-08-22 —
#           *"the sizes of CSV file scan be 50,000 or 100,000 units or premises
#           at a time; how you will hnadle such volume in upload"*), second half
#           Screens: WFL-01.premises.2-4 (the stage rail's progress line), PRM-04
# Rules:    BR-MET-090 (a run's record is what it DID — this table is a live
#           gauge and is never read by the receipt) · BR-MET-096 (ONE runner,
#           several targets — every target inherits this table) · CLAUDE.md
#           rule 1 (tenant scoping; RLS FORCE) · B2 §3 (the policy template)
# Tests:    06-backend/tests/test_cr026_background_stages.py
# Impacts:  apps/metering/import_progress.py (the only writer) ·
#           apps/metering/import_runs.py (reports; serves it in run_dict)
# ───────────────────────────────────────────────────────
"""metering 0017 — CR-026's `import_run_progress`, the live stage gauge.

HUMAN-OWNED (migration ordering AND the RLS policy below are 🔒 paths).
🔒 HUMAN-REVIEW-PENDING (migration ordering is a CLAUDE.md sensitive path).

AI-authored 2026-08-22 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). Row in 12-governance/09-human-review-ledger.md;
not RATIFIED without a recorded human sign-off.

WHAT IT IS FOR, IN ONE LINE: three import stages take **77.9s, 50.8s and
101.5s** at 50,000 rows (measured on this tree, 2026-08-22), they now run in a
worker, and a screen that waits on them has to be able to ask *"how far?"*.

WHY A TABLE AND NOT A COLUMN ON `import_runs` — the reason is a LOCK, and it is
the whole justification for this migration existing at all. Each stage holds
`SELECT … FOR UPDATE` on its own run row for the entire stage (DEF-529 put that
lock inside the transaction, correctly). An UPDATE of that row from the progress
writer's connection would block until the stage committed, so a column could
report 0% and then 100% and nothing in between. A row nobody else locks can be
written while the stage runs. `ImportRunProgress`'s docstring carries the same
note for the reader who arrives from the model side.

ORDERING — WHY THIS IS SAFE TO APPLY IN ANY ORDER RELATIVE TO OTHER LANES: it
CREATES a table and touches no existing one. It depends on `metering.0016` (the
migration it follows in this app) and on the `tenancy` leaf Django resolved for
the `tenant` FK; it alters no column, backfills nothing, and drops nothing, so
there is no data state it can arrive too early or too late for. Reversing it
drops a table whose entire contents are a progress bar (see the model docstring:
nothing audited and nothing financial reads it).

RLS IS IN **THIS** MIGRATION, NOT A FOLLOWING ONE, AND DELIBERATELY SO. The
CR-023 pair split create (0014) from policy (0015), which leaves a window — one
applied migration — in which a tenant table exists with no policy on it. Every
row of this table carries `tenant_id` and the B2 §3 template is applied in the
same operation list, so the table is never reachable across tenants, not even
for the length of one deploy. B15 §5's ER diagram draws child tables without a
tenant column; 0015 already recorded why that shape is a rule-1 violation and
this table follows the corrected one.

Postgres only for the policy half — `PostgresOnlySQL` skips honestly on the
sqlite test database, where RLS does not exist. The live proofs are the G5
isolation suite (NFR-10, zero tolerance, release blocker).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: B2 §3 template, verbatim — the same block metering 0015 applied to the five
#: CR-023 tables, for the sixth.
POLICY = """
ALTER TABLE import_run_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_run_progress FORCE ROW LEVEL SECURITY;
CREATE POLICY import_run_progress_tenant_isolation ON import_run_progress
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0016_br_met_101_common_area"),
        ("tenancy", "0016_br_rat_081_service_metered"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportRunProgress",
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
                ("stage", models.TextField()),
                ("done", models.IntegerField(default=0)),
                ("total", models.IntegerField(blank=True, null=True)),
                ("state", models.TextField(default="queued")),
                ("message", models.TextField(blank=True, null=True)),
                ("job_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "run",
                    models.ForeignKey(
                        db_column="run_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.importrun",
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
                "db_table": "import_run_progress",
                "indexes": [
                    models.Index(fields=["tenant", "run"], name="ix_import_run_progress_run")
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("run",), name="uq_import_run_progress_run")
                ],
            },
        ),
        PostgresOnlySQL(sql=POLICY, reverse_sql=migrations.RunSQL.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@8bf4be8 (the runner it extends) — extended by CR-026 second half (PO 2026-08-22)
# generated: 2026-08-22 by the CR-026 background-stages lane
# checklist: A✔ B=deferred(table-half only — the service/API TCs are in the lane's own test module) C✔ D=deferred(no-API-half — a migration) E=deferred(no-frontend-half — the polling screen is the frontend lane's; this lane serves the payload) F✔ G✔ H=deferred(PO 2026-08-09 — migration ordering + RLS are 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: makemigrations --check clean · migrate from empty✔ · pytest tests/test_cr026_background_stages.py + the 79 CR-023/025 import tests✔ · golden 33/33✔ · ruff✔ black✔
# exceptions: policy SQL inline rather than in 06-backend/db/ (the sixth file to flag that relocation — REPORTED, not resolved here) · create + policy in ONE migration, unlike the 0014/0015 pair, so the table is never reachable un-policied (stated in the docstring)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
