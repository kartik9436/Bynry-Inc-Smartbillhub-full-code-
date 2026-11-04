# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22 Add note) · US-CUS-011 (S21 Notes tab)
#           Screens: S21 · S22
# Rules:    CLAUDE.md rule 1 / DB-1 (RLS ENABLE + FORCE on every tenant table) ·
#           BR-CUS-035 (notes are customers-owned) · BR-CUS-045 (a note body is
#           written by staff about a named person and is treated as PII)
# ───────────────────────────────────────────────────────
"""customers 0008 — RLS ENABLE+FORCE on `account_notes`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM. Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without human sign-off.

The B2 §3 template — deny-by-default: with `app.tenant_id` unset the `::uuid`
cast of '' fails and NO row is visible:

    ALTER TABLE account_notes ENABLE ROW LEVEL SECURITY;
    ALTER TABLE account_notes FORCE ROW LEVEL SECURITY;   -- owner included
    CREATE POLICY account_notes_tenant_isolation ON account_notes
      USING      (tenant_id = current_setting('app.tenant_id')::uuid)
      WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

WHY THIS TABLE IS NOT "JUST NOTES". A note body is free text a clerk typed about
a named customer — "called about the leak", "disputes the July read", "spouse
handles the account". It is at least as sensitive as the columns BR-CUS-045
guards, and a staging table full of the same shape is exactly what migration
0006 argued about. There is no reading on which this table is exempt.

⚠ FOR THE REVIEWER — the same hosting call migrations 0002 and 0006 flagged: the
policy SQL is INLINE here rather than in `06-backend/db/rls_customers_*.sql`,
because `06-backend/db/` is outside this lane's stated territory. That makes
FIVE files wanting to move into `db/` together, as one edit, by whoever owns
that directory. The policy TEXT is the B2 §3 template either way.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite (NFR-10,
zero tolerance, release blocker), and this lane ran it against a live
PostgreSQL 16 database — see the lane report.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim.
POLICIES = """
ALTER TABLE account_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_notes_tenant_isolation ON account_notes;
CREATE POLICY account_notes_tenant_isolation ON account_notes
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0007_us_cus_015_account_notes"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-015@f7c1a20 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packet US-CUS-011, same four sources)
# generated: 2026-08-11 by story-coder (W4 customers ACTION lane — the S22 modals and the S23 wizard)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — RLS policies 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — makemigrations --check clean · migrate from empty on sqlite AND on a live PostgreSQL 16 database · pytest tests -m isolation (live Postgres) with the new cross-tenant note probe
# exceptions: the policy SQL is INLINE rather than in `06-backend/db/` — the fifth file to make that call and to flag it for one relocation edit by that directory's owner; the policy TEXT is the B2 §3 template verbatim either way
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
