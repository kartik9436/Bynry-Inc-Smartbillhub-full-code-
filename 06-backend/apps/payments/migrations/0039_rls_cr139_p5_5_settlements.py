# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, task `P5.5`'s
#          second half: *"Plus its own RLS migration."* Outcome, verbatim:
#          *"Every tenant table has a policy."*
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS `FORCE` is on) · G5 (the isolation probe
#          that must not be allowed to count skips as a pass)
# Tests:   06-backend/tests/test_cr139_p5_rls_pg.py — PostgreSQL ONLY, and it
#          is a separate file for the reason `test_cr135_p0_rls_pg.py` is.
# Impacts: apps/payments/settlement_models.py (the two tables this covers) ·
#          apps/payments/migrations/0038_cr139_p5_4_p5_5_p5_6_settlements.py
# ───────────────────────────────────────────────────────
"""payments 0039 — row-level security on `settlements` and `settlement_members`.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — RLS policies are named by CLAUDE.md's 🔒
list. AI-authored 2026-09-23 under the PO ruling of 2026-08-09; a row in
`12-governance/09-human-review-ledger.md` states what a reviewer is owed.

⚠ **IT IS ITS OWN FILE, AND THAT IS NOT TIDINESS.** `payments/0032` set the
precedent for `counter_sessions` and the reason is the same: a policy applied
inside the migration that creates the table is a policy whose absence on SQLite
looks exactly like the table simply not having one. Separating them makes the
PostgreSQL-only step visible in the graph and gives it a name a probe can cite.

⚠ **BOTH TABLES, AND THE SECOND ONE IS THE EASY ONE TO FORGET.**
`settlement_members` carries no obvious identity of its own — it is a join row —
and a join row with no policy is a hole that reads exactly like a working table:
every query a lane writes goes through `settlement`, which IS filtered, so the
gap never shows in normal use and shows instantly to anyone who queries the
members directly. **G85's *fails a fourth home* shape, one table over.**

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠ `app.tenant_id` UNSET MATCHES **ZERO ROWS AND REPORTS SUCCESS**.      ║
╚══════════════════════════════════════════════════════════════════════════╝
That is this branch's own hard-won finding, from a lane that stamped **0 of 74
payments** and was told it had succeeded. The policy below is the reason: with
`app.tenant_id` unset, `NULLIF(current_setting('app.tenant_id', true), '')::uuid`
is NULL, every `tenant_id = NULL` comparison is NULL, and **an UPDATE that
matches nothing is not an error.** So a caller that forgets to set the GUC does
not get a refusal, it gets a silent no-op — which is why `core.tenancy` refuses
before the query rather than relying on the policy to complain.

**`FORCE` is what makes the policy apply to the table's OWNER too.** Without it
the application role — which owns these tables — bypasses the policy entirely
and the whole file is decoration.
"""

from django.db import migrations

TABLES = ("settlements", "settlement_members")


def _enable(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        # SQLite has no row-level security of any kind. ⚠ This early return is
        # exactly why the test is a separate PostgreSQL-only file: a suite that
        # runs here and reports green has proved that the migration did not
        # crash, and nothing whatever about isolation (hard-won law 7 —
        # *"192 skips once read as a pass"*).
        return
    for table in TABLES:
        schema_editor.execute(_enable(table))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0038_cr139_p5_4_p5_5_p5_6_settlements"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
