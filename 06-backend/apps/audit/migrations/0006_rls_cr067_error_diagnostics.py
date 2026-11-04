# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 task A1 — the diagnostic record: table + migration, its own
#           retention, no FK into `audit_log`
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — RLS ENABLE + FORCE in the
#           SAME migration that creates the table) · B2 §3 (the signed RLS
#           template, taken from core.rls and not pasted) · DEF-639 (the
#           unset-tenant predicate form) · DEF-027 (a table born without its
#           policy is a cross-tenant leak until something notices) ·
#           BR-AUD-002 (why this is a table beside `audit_log`, not columns on it)
# Tests:    06-backend/tests/test_cr067_diagnostics.py
# ───────────────────────────────────────────────────────
"""audit 0006 — `error_diagnostics`, and its isolation, together.

⚠ **`rls` IS IN THE FILENAME ON PURPOSE AND IT IS LOAD-BEARING. THIS FILE IS
GUARDED TODAY** — `06-backend/**/migrations/*rls*` in
`10-scripts/gates/human_owned.txt` covers it, which is exactly why the name was
chosen. A file that invokes the 🔒 human-review protocol in its own docstring
must be inside the guarded set, and EXTENDING that set is a PROCESS EVENT and
the Product Owner's call, never a lane's. So the name matches the glob that
already exists rather than a glob being added for the file, exactly as
`tenancy/0026_rls_document_store.py` and `metering/0015_rls_cr023_import_runs.py`
do.

HUMAN-OWNED (RLS policies AND migration ordering are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md.

ONE MIGRATION, AND THE ORDER INSIDE IT IS THE POINT
----------------------------------------------------
The table and its policy land TOGETHER, exactly as `tenancy/0026` does and for
the reason DEF-027 records: a table that exists for even one migration without
its policy is readable by every tenant until somebody notices. The policy text
is the SIGNED B2 §3 template through `core.rls.tenant_isolation_policy_sql`;
not one character of the predicate is this lane's.

WHAT IS DELIBERATELY ABSENT
----------------------------
**No append-only trigger.** `audit_log` has one because it is permanent
evidence; this table is the opposite — it is written once and then DELETED by a
retention sweep (CR-067 task A5). A write-once trigger here would refuse the
sweep that is the whole point of the table.

**No foreign key, in either direction.** Not into `audit_log`, whose retention
would then govern this table's; not into `tenants`, for BR-AUD-015's reason.
The join to the permanent row is `reference`, a VALUE.

POSTGRES ONLY FOR THE POLICY, AND SAID OUT LOUD
------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite, which has no RLS. So the
policy carries `PostgresOnlySQL` and is proved on a live cluster under a
`NOSUPERUSER NOBYPASSRLS` role; the Python side (`apps/audit/diagnostics.py`)
filters by `tenant_id` on every read on every vendor. A check that skips
silently on the database a developer actually runs is not a check.
"""

from django.db import migrations, models

import core.dbfields
from core.migrationtools import PostgresOnlySQL
from core.rls import tenant_isolation_policy_sql

POLICY_SQL = tenant_isolation_policy_sql("error_diagnostics")

REVERSE_POLICY_SQL = """
DROP POLICY IF EXISTS error_diagnostics_tenant_isolation ON error_diagnostics;
ALTER TABLE error_diagnostics NO FORCE ROW LEVEL SECURITY;
ALTER TABLE error_diagnostics DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0005_rls_deny_on_unset_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="ErrorDiagnostic",
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
                ("tenant_id", models.UUIDField()),
                ("reference", models.TextField()),
                ("trace_id", models.TextField()),
                ("error_code", models.TextField()),
                ("component", models.TextField()),
                ("exception_type", models.TextField()),
                ("exception_module", models.TextField()),
                ("exception_chain", models.JSONField(blank=True, default=list)),
                ("frames", models.JSONField(blank=True, default=list)),
                ("settings_in_force", models.JSONField(blank=True, default=dict)),
                ("request_fields", models.JSONField(blank=True, default=list)),
                ("job_kind", models.TextField(blank=True, null=True)),
                ("job_id", models.TextField(blank=True, null=True)),
                ("step", models.IntegerField(blank=True, null=True)),
                ("step_total", models.IntegerField(blank=True, null=True)),
                ("audit_action", models.TextField(blank=True, null=True)),
                ("release", models.TextField()),
                ("created_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
            ],
            options={"db_table": "error_diagnostics"},
        ),
        migrations.AddIndex(
            model_name="errordiagnostic",
            index=models.Index(fields=["tenant_id", "reference"], name="ix_err_diag_reference"),
        ),
        migrations.AddIndex(
            model_name="errordiagnostic",
            index=models.Index(fields=["tenant_id", "created_at"], name="ix_err_diag_recent"),
        ),
        migrations.AddIndex(
            model_name="errordiagnostic",
            index=models.Index(fields=["tenant_id", "expires_at"], name="ix_err_diag_expiry"),
        ),
        # CLAUDE.md rule 1 — the policy lands WITH the table, never a migration
        # later. B2 §3's signed template via core.rls.
        PostgresOnlySQL(sql=POLICY_SQL, reverse_sql=REVERSE_POLICY_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 task A1 (12-governance/11-change-requests.md) + 04-docs/03-contracts B2 §3 (the signed RLS template) + 06-backend/apps/tenancy/migrations/0026_rls_document_store.py (the table-and-policy-together precedent)
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B=deferred(a migration draws nothing) C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 migration ordering + RLS, review-ledger row appended)
# gates: ⚠ **THE DATABASE HALF OF THE ISOLATION IS NOT PROVED IN THIS ENVIRONMENT AND THIS LINE SAYS SO RATHER THAN CLAIMING IT (hard-won law 1).** The app-layer half IS proved RED: with the `tenant_id=` filter dropped from `by_reference`, tenant B read tenant A's record — `AssertionError: tenant B read tenant A's diagnostic … assert <ErrorDiagnostic …> is None` — and with the filter in place the same read returns None, on SQLite and on live PostgreSQL 16 (26/26). The POLICY, however, cannot be shown to bite on this container: `tests/test_def2722_sample_plant_survives.py::test_def2722_tc0` measured `role smartbillhub has rolsuper=True` on 2026-09-02, and a superuser bypasses row-level security, so removing the policy here would change nothing and 'proving' it would be a check that cannot fail. What IS verified about the policy is that it is the SIGNED B2 §3 text, character for character, through `core.rls.tenant_isolation_policy_sql` — asserted by `tests/test_be10_partitioning.py::test_be10_tc11_policy_text_matches_the_signed_b2_sql` — and that it is applied in the same migration as the table. The behavioural proof belongs to the G5 isolation suite under a `NOSUPERUSER NOBYPASSRLS` role, and is OWED.
# exceptions: (1) NO append-only trigger, unlike audit/0001 and tenancy/0026 — this table is DELETED by its own retention sweep and a write-once trigger would refuse it. (2) NO FK in either direction (see the model docstring). (3) POSTGRES ONLY for the policy; the Python side filters by tenant_id on every vendor.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
