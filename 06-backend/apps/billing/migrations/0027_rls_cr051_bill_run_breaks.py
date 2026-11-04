# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-004 (phase 2 calculate + phase 3 breaks)   Screens: S31 step 4
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · NFR-10 (isolation,
#           release blocker) · BR-BIL-053 (the break list) · DEF-639 (an unset
#           tenant marker must DENY, never raise)
# ───────────────────────────────────────────────────────
"""billing 0027 — tenant isolation for `bill_run_breaks`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-30 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md.

A separate migration rather than an edit to `0026`, for the reason `0004`
records: editing a migration that has already run changes nothing on the
cluster it ran against.

This row names a customer's account, the reason we could not bill them and the
sentence a clerk reads about it. It is one tenant's operating position for a
period; it is not metadata.

⚠ **THE POLICY IS THE `NULLIF` FORM, NOT THE BARE CAST, AND THE FIRST DRAFT OF
THIS FILE GOT IT WRONG — `DEF-2558`.** It was copied verbatim from
`0008_rls_release_gate.py`, which is one of the 34 policies written before
`DEF-639`: those cast the raw GUC to uuid with no `NULLIF` and no second
argument to `current_setting`. That shape **ERRORS** on an unset or empty GUC
rather than denying — `invalid input syntax for type uuid: ""` — which is what
made a fresh database un-buildable (OQ-354 / DEF-622: a deferred FK validation
at a migration's exit is evaluated against `''` and dies). Copying the nearest
neighbour is exactly how a retired form outlives its retirement, and only `G41`
caught it. **The retired shape is described here and deliberately not written
out**, because G41 greps for it and a gate cannot tell a retraction from the
claim it retracts — the same trap this lane's `tc1` hit on the first draft. The
form used here —

    NULLIF(current_setting('app.tenant_id', true), '')::uuid

— is deny-by-default WITHOUT the error: `current_setting`'s second argument
makes a missing parameter return NULL instead of raising, `NULLIF` turns `''`
into NULL, and `tenant_id = NULL` is NULL, which is not TRUE, so no row is
visible and no row may be written. Same guarantee, one fewer way to brick a
deploy. This table is born in the new form and never needs the rewrite the
existing 34 are waiting on.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The G5 isolation suite proves a policy under a
NON-SUPERUSER probe role, because the app connects as a superuser and
superusers bypass RLS unconditionally; `tests/test_cr051_run_jobs_and_breaks.py
::tc13` additionally asserts that the policy reached the CLUSTER at all, which
is a claim a migration file cannot make about itself.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "bill_run_breaks"

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
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

    dependencies = [
        ("billing", "0026_cr051_bill_run_breaks"),
    ]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051@task5 (ships with 0026)
# generated: 2026-08-30 by the CR-051 W0/W1/W2 backend lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: G41 tenant-guc-form PASS (it was RED on the first draft's bare cast and
#         named this file — DEF-2558) · tests/test_cr051_run_jobs_and_breaks.py
#         ::tc13 asserts the policy is on the CLUSTER, read from pg_class rather
#         than from this file · G5's repo-wide sweep picks the table up
#         automatically from the same catalog read
# exceptions: separate migration rather than editing 0026, for the reason 0004
#         records · the cross-tenant PROBE half of G5 SKIPS in this environment
#         because the app role has no CREATEROLE and `rls_probe_role` refuses to
#         pretend; recorded rather than worked around
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
