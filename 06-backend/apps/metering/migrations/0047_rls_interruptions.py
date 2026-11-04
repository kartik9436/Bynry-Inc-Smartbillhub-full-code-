# ── Trace ──────────────────────────────────────────────
# Change:   CR-068 wave B (US-CWP-008 — the interruption record)  Screens: CWP-006/007/012
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker) · BR-CWP-005 (the tenant is
#           resolved from the path BEFORE anything is read — on the guest edge
#           this policy is the only thing standing between an anonymous request
#           and another utility's rows)
# Tests:    06-backend/tests/test_us_cwp_008_pg.py (the live-PostgreSQL probe) ·
#           06-backend/tests/test_us_cwp_008_interruption.py (app-layer scoping)
# ───────────────────────────────────────────────────────
"""metering 0047 — RLS ENABLE+FORCE on `interruptions`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template with `DEF-639`'s cast repair. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

⚠ **THE DOOR IN FRONT OF THIS TABLE NARROWED ON 2026-09-04 (`CR-072`), AND THE
POLICY MATTERS AS MUCH AS EVER.** A passer-by's report no longer writes here —
it writes `service_requests`, whose own policy is proved in
`tests/test_cr072_pg.py` — and this table is now written by a CLERK. The
paragraph below is kept because it is why the policy exists and because the
rollback in `CR-072` §7 is a code revert, which would put the anonymous door
back in one commit.

⚠ **THIS ONE MATTERED MORE THAN THE THIRTY-FIVE BEFORE IT, AND THE REASON WAS THE
DOOR IN FRONT OF IT.** Every other tenant table in this product is reached by a
signed-in member of one tenant. This table is written by an ANONYMOUS request
from the public internet (`apps/portal/guest_api.py`, `POST /public/reports`)
and read by another (`POST /public/track`). The application resolves the tenant
from the first path segment and sets `app.tenant_id` before anything runs
(`BR-CWP-005`); this policy is what makes that a guarantee rather than a habit.

    ALTER TABLE interruptions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE interruptions FORCE ROW LEVEL SECURITY;  -- the owner too
    CREATE POLICY interruptions_tenant_isolation ON interruptions
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

The predicate is `NULLIF(current_setting('app.tenant_id', true), '')::uuid` and
not B2 §3's literal cast — `DEF-639`. The deny-by-default guarantee is
IDENTICAL (`NULL = tenant_id` is NULL, and a policy evaluating to NULL admits
nothing) and the cast can no longer poison a deferred FK validation scan inside
`migrate`.

⚠ THE TABLE IS NOT PARTITIONED, so the `meter_reads` hazard metering 0004
documents — a partition queried DIRECTLY consults only its own policies — does
not arise here. Named rather than omitted, because it is invisible until it is
written down.

⚠ FOR THE REVIEWER — the same hosting call metering 0004/0015/0025, customers
0002, identity 0004 and tenancy 0004 each flagged: the policy SQL is INLINE
rather than in `06-backend/db/`, because that directory is outside this lane's
territory. That is now SEVEN files wanting the same relocation, as one edit, by
whoever owns it.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is `tests/test_us_cwp_008_pg.py`, run
under `DJANGO_SETTINGS_MODULE=config.settings.local` (CLAUDE.md law 14).

⚠ **THAT PATH READ `tests/test_us_cwp_pg.py` — A FILE THAT HAS NEVER EXISTED —
UNTIL `DEF-CWP-3743` (2026-09-04), IN THIS DOCSTRING AND IN THREE OTHER
CITATIONS.** The proof is real and the pointer to it was not, which is hard-won
law 1 in its exact form and the same shape as `DEF-524`. Nothing in this repo
resolves a `# Tests:` path against the tree, so a reviewer following it would
have found nothing and had no way to tell a typo from an unwritten proof.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "interruptions"

#: B2 §3 template with DEF-639's cast repair — see the docstring.
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      ({PREDICATE})
  WITH CHECK ({PREDICATE});
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0046_cwp_interruptions"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICY,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@d6d31c46 (EP-CWP-03 story + CLAUDE.md hard rule 1)
# generated: 2026-09-04 by the CR-068 wave B build lane
# checklist: A✔ B=deferred(policy half) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=PENDING(review-ledger row written by this wave, in plain English with a figure)
# gates: makemigrations --check clean · migrate applied on PostgreSQL 16 · tests/test_us_cwp_008_pg.py proved RED first with the policy dropped
# exceptions: policy SQL inline rather than in 06-backend/db/ (seventh file to flag the same relocation — REPORTED, not resolved here)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
