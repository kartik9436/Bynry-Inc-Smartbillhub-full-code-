# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — RLS on the one table round 3
#           creates (work/0032)
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE on) · B2 §3 · DEF-639 (the NULLIF form)
# Tests:    06-backend/tests/test_cr168_srv2_bulk_raise_pg.py (reads
#           relrowsecurity AND relforcerowsecurity from pg_class)
# ───────────────────────────────────────────────────────
"""work 0033 — RLS ENABLE + FORCE on `work_bulk_raises`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`work/0030`'s policy character for character — the `NULLIF` form (`DEF-639`),
deny-by-default without erroring on an unset GUC — and FORCE as well as ENABLE
because the migration role owns the table and ENABLE alone exempts the owner.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLE = "work_bulk_raises"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("work", "0032_cr168_bulk_raises")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (bulk raise) · §8 R3 SRV-2
# generated: 2026-10-04 by CR-168 round 3 lane SRV-2
# checklist: A✔ B=n/a C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 RLS → review-ledger row)
# gates: migrate up → down → up on PostgreSQL 16 · pg_class flags read back
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
