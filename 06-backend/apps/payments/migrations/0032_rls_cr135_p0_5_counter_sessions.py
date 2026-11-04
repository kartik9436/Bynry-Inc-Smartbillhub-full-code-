# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, task `P0.5`:
#          *"Its own migration, as 0028 is for counter receipts: FORCE ROW
#          LEVEL SECURITY and the tenant policy."* Outcome, verbatim: *"A
#          tenant table with no RLS migration is hard rule 1 broken."*
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#          template) · DEF-639 / `payments/0025` (deny on UNSET — the
#          `NULLIF(…, '')` form, never the bare `::uuid` cast)
# Tests:   06-backend/tests/test_cr135_p0_rls_pg.py — `P0.14`, both
#          directions, on real PostgreSQL under a role RLS applies to.
# Impacts: counter_sessions (the table `payments/0031` creates)
# ───────────────────────────────────────────────────────
"""payments 0032 — isolation for `counter_sessions`. HUMAN-OWNED.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09. RLS policies are a CLAUDE.md 🔒 rule-1 path, so there is a row in
`12-governance/09-human-review-ledger.md`. It applies the SIGNED B2 §3 template
VERBATIM and invents no new policy shape — the same template `payments/0022`
carries for `payment_tenders` and `payments/0028` for `counter_receipts`.

╔══════════════════════════════════════════════════════════════════════════╗
║  A COUNTER SESSION NAMES A NAMED EMPLOYEE, THE DESK THEY WERE AT, AND    ║
║  WHAT WAS IN THEIR DRAWER AT THE END OF THE DAY — INCLUDING WHETHER IT   ║
║  WAS SHORT. A CROSS-TENANT READ IS ANOTHER UTILITY'S PAYROLL PROBLEM.    ║
╚══════════════════════════════════════════════════════════════════════════╝

TWO FLAGS, AND `ENABLE` ALONE IS NOT THE GUARANTEE
----------------------------------------------------
`ENABLE ROW LEVEL SECURITY` exempts the table's OWNER, and the application's
migration role owns every table in this schema — so a table with `ENABLE` and
no `FORCE` has no policy for the process that matters. Both are set below and
`test_cr135_p0_rls_pg.py` reads them back out of `pg_class` rather than out of
this file, because a migration that ran, a policy somebody dropped by hand and
a policy that was never written all look identical in the source tree.

⚠ THE PREDICATE IS THE DENY-ON-UNSET FORM, WRITTEN THAT WAY FROM BIRTH
------------------------------------------------------------------------
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid

**Not** the bare `current_setting('app.tenant_id', true)::uuid`. `payments/0025`
had to sweep four payments policies out of that older form (`DEF-PAY-4054`) and
its docstring says in capitals that a policy created AFTER it is not rewritten.
The difference is not a leak either way — both scope correctly — it is the
SHAPE OF THE REFUSAL: `core/tenancy.py::clear_current_tenant` writes the EMPTY
STRING, and `''::uuid` cannot be parsed, so the old form RAISES *invalid input
syntax for type uuid: ""* where this one quietly returns zero rows. An error is
not a denial; it is a denial that also takes down whatever else was in the
statement — including foreign-key validation, which is how the old form once
stopped a fresh database at step 12 of 168.

**So `P0.5`'s two halves and the brief's third are one predicate**: FORCE, the
tenant policy, and deny-on-unset. There is nothing to sweep later.

⚠ AND THIS IS THE GUARANTEE TODAY'S OTHER TWO DEFECTS TURNED ON
----------------------------------------------------------------
`DEF-PAY-6166`: `payments` carries this same policy, a migration runs with no
tenant set, and `payments/0029`'s backfill therefore matched **zero rows of
seventy-four and printed `OK`**. That is this policy working exactly as
written. Any future data migration against `counter_sessions` must walk tenants
with `set_config('app.tenant_id', id, true)` for the same reason, and
`payments/0030` is the worked example one file back.

NO FREEZE TRIGGER, AND THAT IS A JUDGMENT RATHER THAN AN OMISSION
-------------------------------------------------------------------
`counter_receipts` got `trg_counter_receipt_freeze` in `payments/0028` because
a receipt is evidence of money handed over and hard rule 4's spirit reaches it.
A counter session is different in kind: **it is a row that is DESIGNED to be
updated once** — it opens with a float and later takes `closed_at`,
`closed_by`, `close_kind`, `counted_totals` and `difference` — and phase 2 adds
a third write when a till closed by a supervisor is DECLARED after the fact
(`3·3d`). Writing a freeze now would be guessing which of those columns phase 2
may move, and a freeze that has to be widened later is worse than one written
when the write paths exist.

**What holds the row meanwhile is `ck_counter_sessions_closed_together`**
(`payments/0031`): the three closing facts move together or not at all, so a
till cannot be sealed with no record of HOW — which is the forced close
becoming indistinguishable from a normal one, the exact thing the PO's ruling
of 2026-09-22 exists to prevent. The freeze is `BR-PAY-1160`'s open half and is
named in the review-ledger row rather than left for somebody to notice.
"""

from django.db import migrations

TABLE = "counter_sessions"

RLS_SQL = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        # SQLite has no row-level security of any kind. ⚠ That is why `P0.14`
        # is a separate PostgreSQL file and why *"192 skips once read as a
        # pass"* is in the task's own text.
        return
    schema_editor.execute(RLS_SQL)


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0031_cr135_p0_3_p0_4_counter_sessions"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
