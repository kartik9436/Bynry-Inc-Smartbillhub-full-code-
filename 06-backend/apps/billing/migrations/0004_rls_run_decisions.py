# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 exception step)   Screens: S31.3
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · BR-BIL-015 ·
#           NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""billing 0004 — tenant isolation for `bill_run_decisions`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 template verbatim, the same shape as the six tables in `0002`.

A separate migration rather than an edit to `0002`, because `0002` has already
been applied to a live database: editing an applied migration changes nothing
on the cluster it already ran against, which is the "a template change never
reaches a host that already has one" trap in a different costume.

Why this table needs it as much as the money ones: a decision row names an
account, a service and a person, and says what was done about a customer's
bill. It is not metadata.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE bill_run_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_run_decisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_run_decisions_tenant_isolation ON bill_run_decisions;
CREATE POLICY bill_run_decisions_tenant_isolation ON bill_run_decisions
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP POLICY IF EXISTS bill_run_decisions_tenant_isolation ON bill_run_decisions;"
        "ALTER TABLE bill_run_decisions NO FORCE ROW LEVEL SECURITY;"
        "ALTER TABLE bill_run_decisions DISABLE ROW LEVEL SECURITY;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0003_w3_run_decisions"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-003@e9d5a48 (ships with 0003)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — with `apply_policy` made a no-op, the G5
#         catalog sweep FAILS naming this table verbatim:
#             Extra items in the left set: 'bill_run_decisions'
#         Restored: 59 passed / 12 skipped on live Postgres.
#         ⚠ AN EARLIER DRAFT OF THIS TRAILER CLAIMED the sweep "named it before
#         this migration existed". IT DID NOT, and the check said so: the
#         isolation suite builds its OWN test database from the FULL migration
#         set, so a table and its policy always arrive together there and the
#         unguarded state is unreachable by simply not having written the
#         policy yet. The sweep catches a migration that CREATES a table and
#         never guards it — which is the real failure mode — but it cannot
#         catch work not yet done. Corrected rather than left as the stronger
#         claim it read as (hard-won law 1).
# exceptions: separate migration rather than editing the already-applied 0002 —
#         an edit to an applied migration reaches no cluster that already ran it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
