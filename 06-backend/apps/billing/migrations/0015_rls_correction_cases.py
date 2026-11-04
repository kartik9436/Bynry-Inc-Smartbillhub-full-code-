# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 · US-BIL-031   Screens: S30
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS ENABLE + FORCE) · rule 4
#           (financial immutability, applied to a document instance:
#           BR-BIL-030's own argument — a snapshot that can be edited later is
#           not a snapshot — carried onto the artifact it created) · BR-BIL-047
#           (a per-bill result that could be edited is not a result) · NFR-10
#           (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""billing 0015 — isolation for the corrections tables, and the reissue's freeze.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path, and the append-only trigger
is hard rule 4's shape). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the
PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies
the SIGNED B2 §3 template verbatim, the same shape as `0002`, `0004` and `0013`,
and invents no policy of its own.

WHY EACH TABLE NEEDS THE POLICY. `correction_cases` names which of a utility's
bills are being changed and by how much; `correction_case_bills` carries the
money delta per bill; `invoice_document_instances` carries a customer's name and
address. None is metadata.

THE APPEND-ONLY TRIGGER ON `invoice_document_instances` IS THE POINT OF THE
TABLE. BR-BIL-030 froze `invoices.bill_payload` because *a snapshot that can be
edited later is not a snapshot* — and a REISSUED document is a snapshot for
exactly the same reason: it is what the customer was sent the second time. If a
row here could be updated, the correction workflow would have re-created the
editable historical document that BR-BIL-030 exists to prevent, one table to the
left. A correction to a reissue is a THIRD instance, which is why `instance_no`
counts.

Postgres only. SQLite has neither RLS nor triggers and the developer test
database is SQLite, so the append-only half is ALSO enforced at the service
layer (`document_correction.execute_document_correction` is the only writer and
never updates) and asserted in tests — a check that skips silently on the
database a developer actually runs is not a check.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE correction_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_cases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS correction_cases_tenant_isolation ON correction_cases;
CREATE POLICY correction_cases_tenant_isolation ON correction_cases
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE correction_case_bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_case_bills FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS correction_case_bills_tenant_isolation ON correction_case_bills;
CREATE POLICY correction_case_bills_tenant_isolation ON correction_case_bills
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE invoice_document_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_document_instances FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invoice_document_instances_tenant_isolation ON invoice_document_instances;
CREATE POLICY invoice_document_instances_tenant_isolation ON invoice_document_instances
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION billing_document_instance_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-BIL-030: invoice_document_instances is APPEND-ONLY — a reissued document is what the customer was sent, so %% is refused. Correcting a reissue is a NEW instance.',
    lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_document_instance_append_only ON invoice_document_instances;
CREATE TRIGGER trg_document_instance_append_only
  BEFORE UPDATE OR DELETE ON invoice_document_instances
  FOR EACH ROW EXECUTE FUNCTION billing_document_instance_append_only();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS trg_document_instance_append_only ON invoice_document_instances;
DROP FUNCTION IF EXISTS billing_document_instance_append_only();
DROP POLICY IF EXISTS invoice_document_instances_tenant_isolation ON invoice_document_instances;
ALTER TABLE invoice_document_instances NO FORCE ROW LEVEL SECURITY;
ALTER TABLE invoice_document_instances DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS correction_case_bills_tenant_isolation ON correction_case_bills;
ALTER TABLE correction_case_bills NO FORCE ROW LEVEL SECURITY;
ALTER TABLE correction_case_bills DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS correction_cases_tenant_isolation ON correction_cases;
ALTER TABLE correction_cases NO FORCE ROW LEVEL SECURITY;
ALTER TABLE correction_cases DISABLE ROW LEVEL SECURITY;
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)
    schema_editor.execute(APPEND_ONLY_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0014_w5_correction_cases"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — policy SQL) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: APPLIED TO POSTGRES, not only to the SQLite test tier (DEF-064) — see
#         the lane report for the verbatim `migrate` output and the isolation run
# exceptions: Postgres-only, like every RLS migration here — the RunPython
#         guard returns early on any other vendor, so the SQLite developer tier
#         asserts the service-layer half and the isolation suite asserts the
#         policy half on a real database. Stated rather than implied: a
#         docstring claiming a guarantee the schema does not have is hard-won
#         law 1, and this repo has paid for it once.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
