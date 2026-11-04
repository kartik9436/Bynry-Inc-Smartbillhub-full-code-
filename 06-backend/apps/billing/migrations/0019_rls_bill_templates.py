# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template CRUD, append-only versions, publish rights)
#           Screens: S8 · S91 · S92 · S93
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS ENABLE + FORCE) · BR-BIL-026
#           (edit = a NEW version — so a PUBLISHED version's content is frozen,
#           which is the same argument BR-BIL-030 makes about a bill payload) ·
#           BR-BIL-027 (a pinned version can never be deleted — the audit-lock,
#           enforced in the service because the pin is not an FK) · NFR-10
#           (isolation — release blocker)
# Tests:    06-backend/tests/test_us_bil_021_templates.py
# ───────────────────────────────────────────────────────
"""billing 0019 — isolation for the template tables, and the version freeze.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path, and the freeze trigger is
hard rule 4's shape applied to a document template). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; row owed in
12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3 template
verbatim — the same shape as `0002`, `0004`, `0013` and `0015` — and invents no
policy of its own.

WHY EACH TABLE NEEDS THE POLICY. `bill_templates` names which layout a utility
sends to which class of customer, and `bill_template_versions` carries the
tenant's own bill messages and footer copy. Neither is metadata: the second is
text the tenant wrote and every customer reads.

THE FREEZE ON A PUBLISHED VERSION IS THE POINT OF THE TABLE
------------------------------------------------------------
BR-BIL-026 says an edit is a NEW version. That rule protects something specific:
`invoices.template_version` is stamped at issue and frozen with the money, and
`documents.render_invoice` resolves the layout from that pin and from nothing
else. If a PUBLISHED version's `layout_key` or `options` could change, every
bill already pinned to it would silently start rendering differently — history
rewritten without a single UPDATE to an invoice row, and every existing gate
still green.

So once a version leaves `draft`, its CONTENT is refused by the database:
`layout_key`, `options`, `template_id` and `version_no` are immutable, and
`status` may still move (published → archived is the lifecycle). This is exactly
the shape `0015` gives `invoice_document_instances`, for the reason BR-BIL-030
gives about payloads — *a snapshot that can be edited later is not a snapshot* —
carried onto the template a snapshot was rendered from.

⚠ WHAT THIS TRIGGER DOES **NOT** DO, said plainly rather than assumed: it does
not stop a DELETE. The audit-lock (BR-BIL-027 — a version pinned by any bill can
never be deleted) is enforced in `templates_service.delete_version`, which counts
`invoices` carrying the pin. It could not be a trigger and could not be a
foreign key: `invoices.template_id` / `.template_version` are PLAIN COLUMNS
because r10 #3 pinned them before this table existed (`models.Invoice` records
that), so an FK added now would refuse every invoice issued in the meantime. A
trigger could count the pins, but it would then be a second implementation of
the rule — and the service's version can name the count in its refusal, which is
what stops somebody looking for a way round it.

**PROVED RED (hard-won law 7).** Applied WITHOUT the trigger, a published
version's `layout_key` was UPDATEd and Postgres accepted it; only then was the
trigger added and the same UPDATE refused. Transcript in the lane report.

Postgres only. SQLite has neither RLS nor triggers and the developer test
database is SQLite, so the append-only half is ALSO enforced at the service
layer (`templates_service` creates versions and transitions status; no function
there edits published content) and asserted in tests — a check that skips
silently on the database a developer actually runs is not a check.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

POLICY_SQL = """
ALTER TABLE bill_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_templates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_templates_tenant_isolation ON bill_templates;
CREATE POLICY bill_templates_tenant_isolation ON bill_templates
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE bill_template_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_template_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_template_versions_tenant_isolation ON bill_template_versions;
CREATE POLICY bill_template_versions_tenant_isolation ON bill_template_versions
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

REVERSE_POLICY_SQL = """
DROP POLICY IF EXISTS bill_templates_tenant_isolation ON bill_templates;
ALTER TABLE bill_templates NO FORCE ROW LEVEL SECURITY;
ALTER TABLE bill_templates DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_template_versions_tenant_isolation ON bill_template_versions;
ALTER TABLE bill_template_versions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE bill_template_versions DISABLE ROW LEVEL SECURITY;
"""

#: ⚠ `%` IS **SINGLE** HERE, AND THAT IS NOT AN OVERSIGHT OF CLAUDE.md's
#: "escape literal `%` as `%%`" note — the note applies where the SQL travels
#: through `schema_editor.execute` with params (`0009`'s `RunPython` shape),
#: where Django performs %-substitution and a lone `%` reads as a parameter
#: marker. `RunSQL` / `PostgresOnlySQL` pass the statement with NO params and
#: perform no substitution, so a doubled `%%` reaches PL/pgSQL verbatim and the
#: RAISE sees four placeholders for two arguments. MEASURED, not reasoned:
#: written with `%%` first, this migration failed at apply time with
#: `psycopg.errors.SyntaxError: too many parameters specified for RAISE`.
#: `apps/metering/migrations/0007_read_corrections.py` takes the same posture.
FREEZE_SQL = """
CREATE OR REPLACE FUNCTION billing_template_version_frozen() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;

  IF NEW.layout_key  IS DISTINCT FROM OLD.layout_key
  OR NEW.options     IS DISTINCT FROM OLD.options
  OR NEW.template_id IS DISTINCT FROM OLD.template_id
  OR NEW.version_no  IS DISTINCT FROM OLD.version_no
  OR NEW.tenant_id   IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-026: bill template version % is % -- only status may change once a version leaves draft. An edit is a NEW version: every bill already pinned to this one renders from it whenever it is reprinted, so changing it here would rewrite what those customers were sent without touching a single invoice row.',
      OLD.version_no, OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bill_template_versions_frozen ON bill_template_versions;
CREATE TRIGGER bill_template_versions_frozen
  BEFORE UPDATE ON bill_template_versions
  FOR EACH ROW EXECUTE FUNCTION billing_template_version_frozen();
"""

REVERSE_FREEZE_SQL = """
DROP TRIGGER IF EXISTS bill_template_versions_frozen ON bill_template_versions;
DROP FUNCTION IF EXISTS billing_template_version_frozen();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0018_w3_bill_templates"),
    ]

    operations = [
        # `PostgresOnlySQL`, the posture every DDL migration in this repo
        # takes: sqlite is the developer database and has neither RLS nor
        # triggers, so it honestly skips rather than failing on syntax it will
        # never support. The guarantees are ALSO held in `templates_service`,
        # and the tests that prove the database half carry `requires_postgres`.
        PostgresOnlySQL(sql=POLICY_SQL, reverse_sql=REVERSE_POLICY_SQL),
        PostgresOnlySQL(sql=FREEZE_SQL, reverse_sql=REVERSE_FREEZE_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (ships with apps/billing/template_models.py — the same four sources)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — policy/DDL only) E=deferred(no-frontend-half — S8 Templates tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run_gates · pytest — see the lane report for the verbatim RED
#         transcript of a published version's `layout_key` being UPDATEd
#         successfully before this trigger existed.
# exceptions: (1) THE TRIGGER FREEZES CONTENT, NOT DELETION. BR-BIL-027's
#         audit-lock lives in `templates_service.delete_version` because the pin
#         (`invoices.template_id` + `.template_version`) is a pair of plain
#         columns, not an FK — r10 #3 pinned them before this table existed and
#         an FK now would refuse every historical invoice.
#         (2) POSTGRES ONLY. sqlite is the developer database and has neither
#         RLS nor triggers; the service layer holds the same guarantees and the
#         tests carry `requires_postgres`, never a bare skip.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
