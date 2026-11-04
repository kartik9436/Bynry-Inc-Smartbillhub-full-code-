# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-GOV-7821 — `account_attribute_history_tenant_isolation` casts the
#          raw tenant GUC, so it ERRORS instead of DENYING when `app.tenant_id`
#          is unset or cleared. Found by the FIRST run of the tenant-isolation
#          suite on this machine as a role RLS genuinely applies to
#          (`sbh_gate_iso`, NOSUPERUSER NOBYPASSRLS) — every earlier recorded
#          proof was taken as a SUPERUSER, which PostgreSQL exempts from every
#          policy, so none of those passes had ever evaluated a single deny.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE) · IS-7's empty
#          posture — a foreign row is INVISIBLE, not forbidden · DEF-622 /
#          DEF-639 (the cast repair) · B2 §3 (the policy template)
# Tests:   06-backend/tests/test_def639_unset_tenant_denies.py::
#          test_def639_tc6__every_policy_in_the_schema_carries_the_deny_on_unset_form
#          — it reads `pg_policies` for the WHOLE public schema, so it names
#          this table without being told about it, and it fails in 1.43s with
#          no fixtures, no seeding and no broker.
# ───────────────────────────────────────────────────────
"""customers 0074 — `account_attribute_history` DENIES on an unset tenant.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-29 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

WHAT WAS WRONG, AND WHY IT IS A LEAK EVEN THOUGH NO DATA CROSSES
----------------------------------------------------------------
`customers/0073` created the policy as

    tenant_id = current_setting('app.tenant_id')::uuid

With `app.tenant_id` UNSET or cleared, `current_setting` returns `''` and the
cast raises `DataError: invalid input syntax for type uuid: ""`. So the query
does not return zero rows — **it errors**, and the caller gets a 500.

**IS-7's posture is that a foreign row is INVISIBLE**: zero rows, not forbidden
and not an exception. The difference is not cosmetic. A 500 where a 200-with-no-
rows was promised is an ORACLE: it tells a caller that the statement reached a
policy at all, and it distinguishes "no tenant context" from "no such row" for
anyone probing. No row crosses a tenant boundary, and it is still hard rule 1's
own table answering a question it should refuse to acknowledge.

THE REPAIR, COPIED RATHER THAN RE-DERIVED
------------------------------------------
`NULLIF(…, '')` turns the empty string into NULL; `tenant_id = NULL` is NULL;
and a policy evaluating to NULL admits NOTHING. **The guarantee is identical and
the cast can no longer raise.** This is DEF-622 / DEF-639's form, taken verbatim
from `metering/0034_rls_cr038_w6_submeter_reconciliation`, which is one of nine
tables already carrying it.

⚠ **THE ROOT CAUSE IS NOT THIS MIGRATION AND FIXING ONLY THIS TABLE LEAVES THE
TRAP LOADED.** `0073`'s own docstring says it applied *"the SIGNED B2 §3 policy
template VERBATIM"* — and it did. **B2 §3's template still carries the raw
cast** (`02-database-design-brief.md`, the code block in §3), while line 1395 of
that same document states the `NULLIF` form is the rule, citing DEF-622/DEF-639.
The document contradicts itself, and the half people COPY is the wrong half.
Every sibling that got it right did so by patching the template locally — see
`metering/0034`'s own comment, *"B2 §3 template with DEF-639's cast repair"*.
So the template is corrected in the same commit as this migration; otherwise the
next tenant table repeats this exactly, as this one did on 2026-09-26.

WHY A NEW MIGRATION AND NOT AN EDIT TO `0073`
----------------------------------------------
Migrations are append-only: `0073` has been applied on every database that has
run since 2026-09-26, and editing it would change nothing already applied while
making the file disagree with the schema it produced (hard-won law 4's shape for
the database). `audit/0005` swept every policy carrying the old predicate when
it ran; `0073` landed AFTER it, which is precisely the gap the drift test exists
to catch and did.

Postgres only — `PostgresOnlySQL` skips honestly on the SQLite test database,
where RLS does not exist and a probe therefore proves nothing (hard-won law 7's
*incapable of failing*).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "account_attribute_history"
POLICY = f"{TABLE}_tenant_isolation"

#: B2 §3's template with DEF-639's cast repair, verbatim from `metering/0034`.
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

#: The broken form `0073` created, kept only so the reverse can restore it.
OLD_PREDICATE = "tenant_id = current_setting('app.tenant_id')::uuid"

FORWARD = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {POLICY} ON {TABLE};
CREATE POLICY {POLICY} ON {TABLE}
  USING      ({PREDICATE})
  WITH CHECK ({PREDICATE});
"""

# ⚠ THE REVERSE RESTORES THE BROKEN FORM ON PURPOSE. A reverse migration must
# put the schema back as it was, not as we wish it had been — a `reverse_sql`
# that quietly leaves an improvement behind makes `migrate` non-invertible and
# the next reader cannot tell what `0073` actually produced.
REVERSE = f"""
DROP POLICY IF EXISTS {POLICY} ON {TABLE};
CREATE POLICY {POLICY} ON {TABLE}
  USING      ({OLD_PREDICATE})
  WITH CHECK ({OLD_PREDICATE});
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0073_rls_cr142_p0_18_attribute_history"),
    ]

    operations = [PostgresOnlySQL(FORWARD, reverse_sql=REVERSE)]
