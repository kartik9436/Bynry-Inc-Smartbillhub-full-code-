# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (the invoice stamp this registry feeds)   Screens: S8
# Rules:    BR-TEN-046 (no tenant can see or alter another tenant's field set;
#           the table is tenant-scoped with RLS FORCE like every other tenant
#           table) · CLAUDE.md rule 1 · B2 §3 policy template · NFR-10
# ───────────────────────────────────────────────────────
"""tenancy 0008 — RLS ENABLE+FORCE on `custom_field`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under PO ruling 2026-08-09 ("AI
will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template verbatim from 06-backend/db/rls_tenancy_custom_field.sql (the
policy text lives there, reviewable in one place — the posture tenancy 0003
established and which customers 0002 flagged its own inline SQL against). Row
in 12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Postgres only: the sqlite test DB cannot exercise RLS — skipped honestly. The
live cross-tenant probes are the G5 isolation suite's job (NFR-10, zero
tolerance, release blocker); see
tests/test_us_bil_028_custom_snapshot.py::test_us_bil_028_tc10_* and
tests/test_tenant_isolation.py's table sweep, which would have caught this
table's absence from any policy file on its own.

Depends on 0007 so the table exists before its policy applies — B2 §7: RLS
after each table, one boring pattern repeated (LAW 0).

The VALUES this registry describes need no policy of their own: `custom_data`
is a column on eight tables that already carry ENABLE + FORCE from their own
modules' migrations. That is the second, unadvertised benefit of r17.2's
"column on the owning row, never a shared value table".
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0007_custom_field_registry"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_tenancy_custom_field.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17 · B2 §3 policy
#         template · 01-tenancy/02-business-rules.md BR-TEN-046)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved on a LIVE Postgres cluster through the non-superuser probe role
#         — with the policy DROPPED, one tenant's definitions were visible to
#         the other and the isolation case went RED; re-created, it passes.
#         Transcript in 12-governance/09-human-review-ledger.md
# exceptions: sqlite skips honestly (no RLS there) — the assertion lives in the
#         G5 isolation suite, never in the sqlite tier
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
