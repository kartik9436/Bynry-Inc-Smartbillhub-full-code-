# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3: all seven tables
#           under RLS FORCE, in their own migration. TC-RBS-7: with no
#           `app.tenant_id`, zero rows on all seven.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#           template, verbatim, one per table) · 🔒 RLS policies (CLAUDE.md
#           sensitive paths — `human_owned.txt` glob `**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_rbs_041_pg.py (TC-RBS-7 — the probe role
#           sees nothing without context; nothing of Brazos Bend under Lone Star
#           Ridge's context; a cross-tenant write refused by the policy)
# Impacts:  every read and write in apps/runbooks — all run under the tenant
#           context or see nothing
# ───────────────────────────────────────────────────────
"""runbooks 0002 — RLS ENABLE + FORCE on the seven tables, and nothing else.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. It applies the SIGNED B2 §3
template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHY ITS OWN MIGRATION
---------------------
A policy is a statement about WHO may see a row, separate from WHAT the row is.
A reviewer of the sensitive path reads one short file with seven identical
blocks rather than hunting seven `ALTER TABLE`s through six hundred lines of
column definitions. Every RLS migration in this repository records the same
reason, and `integrations/0002_rls_force` is the closest precedent.

WHAT IT GUARANTEES, MEASURED ON POSTGRESQL AND NOWHERE ELSE
-----------------------------------------------------------
Deny-by-default: with `app.tenant_id` unset or empty, `NULLIF(…, '')::uuid` is
NULL, the predicate is NULL, and **no row of any of the seven is visible or
writable** — `SELECT count(*)` answers 0 on every one. Under Lone Star Ridge's
context, not one of Brazos Bend's runbooks, versions, runs, records, work items
or cutover rows is reachable. `FORCE` makes that true for the table owner too,
which is the half a plain `ENABLE` leaves open.

⚠ **SQLITE HAS NO RLS AT ALL, SO A TEST THAT RUNS THERE PROVES NOTHING.** The
tests for this migration carry `requires_postgres` and SKIP on the default suite
rather than passing vacuously (hard-won law 14). This repository has already
paid for the alternative: `G5` once ran the tenant-isolation suite on SQLite and
**called 192 skips a pass**. The suite here runs under the NON-SUPERUSER probe
role from `tests/isolation_helpers.py`, because the connected role may bypass
row security and a green under a superuser would prove nothing either.

⚠ **`work_items` IS THIS MODULE'S TABLE.** The name reads like a collision with
`apps/work` and is not one (`17-runbooks/03-field-map.md` D-4): the work module
owns crews, technicians, parts and WORK ORDERS. Nothing else in the product has
a `work_items` table, so this policy guards one table and shadows none.
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: The seven, as B2 §2's `### Module: runbooks` lists them. Kept as a LITERAL
#: here rather than imported from `models.TENANT_TABLES`, so this migration
#: reads the same in a year when the model module has moved on — a migration is
#: a record of what was done, not a view of what is true now. Every other RLS
#: migration in this repository takes the same posture.
TENANT_TABLES = (
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "work_items",
    "cutover_plans",
    "cutover_plan_items",
)


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(tenant_isolation_policy_sql(table))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):
    dependencies = [
        ("runbooks", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
