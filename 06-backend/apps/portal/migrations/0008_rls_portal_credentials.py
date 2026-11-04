# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-021 (🔒, EP-CWP-03) TC-7 — the isolation only PostgreSQL can
#           prove. Screens: every signed-in portal screen stands on this.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS `FORCE` is on) · BR-CWP-005 (the tenant is
#           resolved from the path and RLS forced BEFORE the credential is
#           read) · BR-CWP-004 (a credential resolves to a customer, never to a
#           staff role) · B2 §3 (the signed policy template, verbatim, one per
#           table) · 🔒 RLS policies (CLAUDE.md sensitive paths —
#           `human_owned.txt` glob `06-backend/**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_cwp_021_pg.py — zero rows without context
#           under the NON-SUPERUSER probe role; Pine Hill's credential
#           invisible under Oak Ridge; a cross-tenant re-stamp refused by the
#           policy; `relrowsecurity` AND `relforcerowsecurity` both asserted
# Impacts:  every read of the three tables — under BE-01's context or nothing
# ───────────────────────────────────────────────────────
"""portal 0008 — RLS ENABLE + FORCE on the credential, the session and the code.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3
template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHAT A REVIEWER IS BEING ASKED ABOUT, IN PLAIN ENGLISH WITH A FIGURE
---------------------------------------------------------------------
Three new tables hold what a customer signs in with. **If this policy is wrong,
a customer of one utility can read another utility's customers' login rows.**
It is proved on PostgreSQL 16 under a role that row security actually applies
to: with no utility set, `SELECT count(*)` over each of the three answers
**zero**; under Oak Ridge's context, Pine Hill's one credential row is **not
among the rows returned**; and an UPDATE that re-stamps a Pine Hill row with
Oak Ridge's id is refused by the policy itself, in the database's own words.

⚠ **THE PROOF READS `relrowsecurity` AND `relforcerowsecurity`, BOTH.** An
empty table looks exactly like a table nobody may read, so a count of zero
proves nothing on its own; and ENABLE without FORCE leaves the table's OWNER
exempt, which is the account the application connects as. The test asserts the
two flags in `pg_class` as well as the counts, and it runs under
`rls_probe_role` — a non-superuser — because the developer role bypasses row
security and a green under it would be a green over nothing.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: Kept as literals here rather than imported from models.py, so this migration
#: reads the same in a year when the model module has moved on — a migration is
#: a record of what was done.
TENANT_TABLES = ("portal_credential", "portal_session", "portal_one_time_code")


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
        ("portal", "0007_cr068_e_credential_session_code"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-021@c05e4dd4 (EP-CWP-03 story + BR-CWP-004/005 + B2 §3 template)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 RLS policies — ledger row 09-human-review-ledger.md, plain English with the figure: three tables, ZERO rows without a utility set, and Pine Hill's credential unreadable under Oak Ridge)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_us_cwp_021_pg.py on PostgreSQL 16 under the non-superuser probe role · G5 isolation suite
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
