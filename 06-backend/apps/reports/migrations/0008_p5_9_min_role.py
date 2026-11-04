"""reports 0008 — `report_definitions.min_role`, and the one row that uses it.
HUMAN-OWNED (this migration lifts `FORCE ROW LEVEL SECURITY`, which is a
CLAUDE.md hard-rule-1 🔒 path, and migration ordering is a second).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-27 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`CR-142-BRC07` Phase 5 · `P5.9`. Role gating on a DEFINITION, resolved
server-side: `apps/reports/role_gate.py` is the only file that reads this
column and its docstring carries the reasoning.

⚠ **THE COLUMN IS NULLABLE AND 45 OF THE 46 PLATFORM ROWS STAY NULL.** NULL
means *no restriction beyond the route's own* — `GET /reports` and
`GET /reports/{key}` already run behind `AnyTenantRole`, so the floor is a
staff member of this tenant. This column only RAISES that floor.

⚠ **NOT A CHECK CONSTRAINT, AND THAT IS A JUDGMENT WITH A REASON.**
`visibility` next door IS a CHECK, deliberately, because its two values are a
security statement. This one is different in kind: the lawful values are ROLE
CODES, they live in `apps/identity`, and `identity.Role.code` is a tenant-
extensible table. A CHECK here would freeze a copy of another module's
vocabulary into this module's schema, and adding a role would then be a
migration in Reports. `role_gate.MIN_ROLES` is the declared set instead, and it
FAILS CLOSED on a value it does not know — an unreadable restriction refuses
everybody rather than admitting everybody, which is the direction that matters.

⚠ **THE DATA HALF IS WHY THIS MIGRATION EXISTS AT ALL.** `BR-REP-023` has been
signed since 2026-08-08 — *"Access-review report (SC-2): System Admin +
Executive only — Billing Clerk excluded"* — and was enforced by nothing:
measured 2026-09-27, `GET /reports/access_review` ran for a Billing Clerk and
the card was drawn on their catalogue. `access_review` is the ONLY row this
product restricts today, so the backfill below names exactly one key.

⚠⚠ **`FORCE` IS LIFTED ROUND THE BACKFILL, EXACTLY AS `0003` LIFTS IT, AND FOR
THE SAME REASON RATHER THAN BY IMITATION.** A platform row carries
`tenant_id IS NULL`; `0002`'s `WITH CHECK` is `tenant_id = <the session's
tenant>` **without** the `OR tenant_id IS NULL` its `USING` clause carries, so
a platform row is readable by every tenant and writable by none — including by
the migration role, because `FORCE` applies to the table's OWNER. **There is
no `app.tenant_id` this migration could set to get past that wall.** Measured
on PostgreSQL 16.13, 2026-09-27, on the first attempt at this file, verbatim:

    django.db.utils.ProgrammingError: new row violates row-level security
    policy for table "report_definitions"

⚠ **AND IT PASSES ON SQLITE, WHICH IS THE ENTIRE UNIT SUITE** (law 14's
neighbour): SQLite has no row-level security, `PostgresOnlySQL` skips, and the
broken version was green on 17 cases before a real database was asked.

⚠ **`SET CONSTRAINTS ALL IMMEDIATE` IS LOAD-BEARING** — the three operations
run in ONE transaction, so the `ALTER TABLE` that restores `FORCE` would
otherwise meet *"cannot ALTER TABLE … because it has pending trigger events"*.
`0003` paid for that finding on a second PostgreSQL run; this file inherits it.

**Rollback:** reverse this migration. The column goes and with it the one
restriction; `role_gate.may_run` then answers True for every row, which is the
behaviour of every build before 2026-09-27. Nothing else reads the column.
"""

from __future__ import annotations

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: The one table this migration backfills. `report_categories` is untouched.
PLATFORM_TABLES = ("report_definitions",)

NO_FORCE = "\n".join(
    f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)
FORCE = "SET CONSTRAINTS ALL IMMEDIATE;\n" + "\n".join(
    f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)

#: `BR-REP-023`'s report. One key, named rather than looked up by group, so a
#: later group rename cannot silently unrestrict it.
RESTRICTED = (("access_review", "executive"),)


def _restrict(apps, schema_editor):
    """Set `min_role` on the PLATFORM rows `BR-REP-023` names.

    ⚠ **PLATFORM ROWS ONLY (`tenant_id IS NULL`).** A tenant's own copy of a
    report is its own row under copy-on-write, and a tenant that copied the
    access-review report before today holds a row this migration deliberately
    does not touch: reaching into tenant data to add a restriction the tenant
    never asked for is a different decision, and `reports/0002`'s policy would
    refuse the write from the migration role anyway. Counted at write time:
    `apps/reports/migrations/0003_seed_catalogue.py` seeds `access_review` as a
    platform row and nothing copies it.
    """
    model = apps.get_model("reports", "ReportDefinition")
    for key, min_role in RESTRICTED:
        model.objects.filter(key=key, tenant_id=None).update(min_role=min_role)


def _unrestrict(apps, schema_editor):
    model = apps.get_model("reports", "ReportDefinition")
    for key, _ in RESTRICTED:
        model.objects.filter(key=key, tenant_id=None).update(min_role=None)


class Migration(migrations.Migration):
    # ⚠ **THIS WAS `0007` UNTIL PUSH TIME AND IT WAS RENUMBERED, NOT REBASED.**
    # A sibling lane landed `0007_br_rep_038_statement_on_ledger` while this
    # file was being tested; two `0007`s under `reports` is two LEAF NODES in
    # the migration graph, and Django then refuses **every test in the
    # process** with *"Conflicting migrations detected; multiple leaf nodes"* —
    # which names neither lane and reads like a broken tree
    # (`a47280585` fixed exactly that once already, and `DEF-REP-6906` was
    # filed by the sibling the same afternoon for this very collision).
    # Re-derived at push time, which is what CLAUDE.md law 11 prescribes for an
    # allocated id — a migration NUMBER is an allocated id like any other.
    dependencies = [("reports", "0007_br_rep_038_statement_on_ledger")]

    operations = [
        migrations.AddField(
            model_name="reportdefinition",
            name="min_role",
            field=models.TextField(blank=True, null=True),
        ),
        # ⚠ The lift, the write and the restore are ONE transaction — see the
        # module docstring. Reversing runs them in reverse, so `reverse_sql`
        # on each half is what keeps the table FORCEd after a rollback too.
        PostgresOnlySQL(NO_FORCE, reverse_sql=FORCE),
        migrations.RunPython(_restrict, _unrestrict),
        PostgresOnlySQL(FORCE, reverse_sql=NO_FORCE),
    ]
