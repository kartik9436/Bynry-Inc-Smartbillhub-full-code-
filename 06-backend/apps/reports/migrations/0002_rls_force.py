"""reports 0002 — RLS ENABLE + FORCE on all three Reports tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-26 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`, shared with `0001` and `0003`; not
RATIFIED without a sign-off.

⚠ THIS FILE IS THE ONE PLACE IN THE PRODUCT WHERE A TENANT TABLE'S POLICY LETS
A SESSION SEE A ROW THAT IS NOT ITS OWN, AND THAT IS WHY IT NEEDS A HUMAN
────────────────────────────────────────────────────────────────────────────
Every other tenant table in this product takes one policy: `tenant_id =
current_tenant`, on both USING and WITH CHECK. **Two of these three do not.**

`report_definitions` and `report_categories` carry a NULLABLE `tenant_id`, and
a NULL means a PLATFORM row — the 46 reports and the 25 catalogue groups we
ship. Every tenant must READ those; no tenant may WRITE them. So:

    USING      (tenant_id = <tenant> OR tenant_id IS NULL)
    WITH CHECK (tenant_id = <tenant>)

The asymmetry IS the rule, stated in the brief's §7.7 in exactly those words:
*"`tenant_id IS NULL` is readable by every tenant and writable by none. A
utility editing a shipped report gets a copy."* A tenant that wants a shipped
report changed does not edit it — the row is copied, the copy carries that
tenant's id, and the platform original is untouched. That is copy-on-write.

**WHAT A REVIEWER SHOULD CHECK, IN ONE SENTENCE:** that the USING clause admits
`tenant_id IS NULL` and the WITH CHECK clause does NOT — because a WITH CHECK
that admitted it would let any tenant write a report every other tenant reads,
and PostgreSQL would report nothing wrong.

`report_tenant_settings` takes the ORDINARY policy on both clauses. An overlay
on a platform definition is always the tenant's own row, so there is no platform
row here to admit and admitting one would be a hole with no purpose.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

The pre-`DEF-639` form — a bare `current_setting` on the same key, cast straight
to uuid, with neither the `, true` nor the `NULLIF` — ERRORS on an unset or
empty GUC rather than denying, which is what makes a fresh database un-buildable
(`OQ-354` / `DEF-622`). This form is deny-by-default WITHOUT the error: the
second argument makes a missing parameter return NULL instead of raising,
`NULLIF` turns `''` into NULL, and `tenant_id = NULL` is NULL — which is not
TRUE, so no row is visible and no row may be written.

⚠ **THE OLD PREDICATE IS DESCRIBED HERE RATHER THAN QUOTED, AND THAT IS ON
PURPOSE.** `G41` is a RATCHET over the literal string: every scanned file's
count of it may fall and never rise, and a file not in its baseline may not
introduce it at all. Quoting it — even inside a docstring explaining why it is
wrong — fails that gate, which is how this paragraph was written the first time
and how the gate caught it. Adding this file to a shrink-only baseline to keep a
nicer sentence would have been weakening a guard for prose.

⚠ **AND WITH AN UNSET GUC THE PLATFORM ROWS ARE STILL READABLE**, because
`tenant_id IS NULL` does not depend on the setting. That is correct and it is
worth stating rather than discovering: the 46 shipped definitions are not
secret, they are the same on every deployment, and the thing RLS is protecting
here is a tenant's OWN reports and its own overlay.

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE ROW LEVEL SECURITY` alone exempts the table's OWNER, and the
application's migration role owns every table in this schema. `FORCE` is what
makes the policy apply to the owner too. B2 §3 requires both.

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
────────────────────────────────────────────────────
`config/settings/test.py` hardcodes in-memory SQLite, **which has no row-level
security of any kind** — every assertion about a policy passes there by vacuum.
That is hard-won law 14's shape one rule along, and it is `P0.10`'s whole point:
the probe runs under `config.settings.local` against real PostgreSQL 16 and
under a NOLOGIN NOSUPERUSER NOBYPASSRLS role, because PostgreSQL exempts
superusers from RLS unconditionally, `FORCE` included, and the development role
IS a superuser (`DEF-2717`). **`P0.10` is a sibling lane's task; this migration
is what makes it passable.**

`PostgresOnlySQL` skips honestly on sqlite rather than pretending to apply.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

#: The two tables that carry PLATFORM rows. Read your own PLUS the platform's;
#: write only your own.
PLATFORM_TABLES = ("report_definitions", "report_categories")

#: The overlay. Ordinary tenant isolation, both clauses.
TENANT_ONLY_TABLES = ("report_tenant_settings",)

PLATFORM_POLICY = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT} OR tenant_id IS NULL)
  WITH CHECK (tenant_id = {TENANT});
"""
    for table in PLATFORM_TABLES
)

TENANT_ONLY_POLICY = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for table in TENANT_ONLY_TABLES
)

POLICY = PLATFORM_POLICY + TENANT_ONLY_POLICY

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""
    for table in PLATFORM_TABLES + TENANT_ONLY_TABLES
)


class Migration(migrations.Migration):
    dependencies = [("reports", "0001_initial")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
