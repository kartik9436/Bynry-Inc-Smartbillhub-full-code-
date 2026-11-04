"""RLS policy template applied by migrations. HUMAN-OWNED (CLAUDE.md).

HUMAN-REVIEW-PENDING — this file stopped being a docstring-only stub on
2026-08-10 (DEF-027, second half) under the PO ruling of 2026-08-09 ("AI will
do it; we will review it later as human"). What it holds is the SIGNED B2 §3
template and nothing else: the same text as `06-backend/db/rls_audit_w0.sql`
and `db/rls_metering_w1.sql`, with the table name parameterised and ONE
idempotency line added (`DROP POLICY IF EXISTS` before `CREATE POLICY`,
exactly as `apps/audit/0003` and `apps/metering/0004` already write it). No new
policy shape is invented here, and
`tests/test_be10_partitioning.py::test_be10_tc11_policy_text_matches_the_signed_b2_sql`
asserts statement-for-statement that what this module emits still equals the
signed SQL file. Row in 12-governance/09-human-review-ledger.md; never RATIFIED
without a recorded human sign-off.

Template per B2 §3 (repeat per tenant-scoped table):
    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

Table list: B2 §3. No-RLS (platform) tables are enumerated there too.

WHY THE TEMPLATE ALSO EXISTS AS CODE, not only as .sql files
------------------------------------------------------------
A PARTITION's name is computed at RUN TIME — `audit_log_2031_03` does not exist
when anyone is writing SQL by hand — so its policy cannot be written down ahead
of time in `db/rls_*.sql` the way a fixed table's can. `core/partitioning.py`
therefore builds the partition's policy from this one template, in the SAME
statement batch that creates the partition (DEF-027: a partition queried
DIRECTLY consults only its own policies, so a partition born without one is a
cross-tenant leak until something notices).

Fixed tables keep using the .sql files. This is the template for the names that
are not knowable until the create-ahead job runs.
"""

import re

#: Only registry constants and computed `<table>_YYYY_MM` names ever reach DDL.
_SAFE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class RlsError(RuntimeError):
    """Misuse of the RLS policy contract — fails the caller loudly."""


#: The SIGNED B2 §3 template. `{table}` is the ONLY substitution; changing any
#: other character here changes a finance/human-signed rule and needs a re-sign
#: (HUMAN-GUIDE §6), never an inline edit.
TENANT_ISOLATION_TEMPLATE = """\
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def tenant_isolation_policy_sql(table: str) -> str:
    """ENABLE + FORCE + the B2 §3 tenant policy for one table or partition.

    Idempotent by construction (drop-if-exists before create), so re-running it
    is safe and is the intended remediation path for a table found unguarded.
    Deny-by-default: with `app.tenant_id` unset or empty the predicate is NULL,
    which is not TRUE, so NO row is visible.

    ⚠ AMENDED 2026-08-24 (DEF-639, PO ruling *"Change the security rule instead,
    in a new step"*). This used to read `current_setting('app.tenant_id')::uuid`
    and the docstring used to say the cast of '' FAILS — it did, and that
    loudness is precisely what made a fresh database un-buildable. The same
    policy is evaluated during FOREIGN KEY VALIDATION, and three committed
    migrations clear tenant context before their own deferred FKs are validated,
    so the scan died on `invalid input syntax for type uuid: ""`. `NULLIF(...,
    true)` returns NULL for an unset GUC instead of raising, `NULLIF(…, '')`
    turns the empty string into NULL, and `tenant_id = NULL` is NULL — denied.
    **Hard rule 1 is unchanged: absence of context still sees nothing.** What
    changed is that absence is SILENT on reads; writes are still refused loudly
    by WITH CHECK. THIS TEMPLATE IS LOAD-BEARING FOR PARTITIONS — `audit_log`
    and `meter_reads` mint a policy per partition at names nobody can write down
    in advance, so a template left in the old form would give next month's
    partition the erroring predicate again.

    The table must carry a `tenant_id` column — a table that does not will fail
    LOUDLY at `CREATE POLICY`, which is the correct outcome: B2 §3 enumerates
    the RLS-exempt platform tables, and they must never be passed here.
    """
    if not _SAFE_NAME_RE.match(table):
        raise RlsError(f"unsafe SQL identifier {table!r}")
    return TENANT_ISOLATION_TEMPLATE.format(table=table)
