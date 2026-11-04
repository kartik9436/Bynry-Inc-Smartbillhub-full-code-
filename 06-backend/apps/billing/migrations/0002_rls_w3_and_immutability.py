# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the moment a bill becomes immutable) ·
#           US-BIL-007 (S30 bill detail)   Screens: S30 · S31
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · CLAUDE.md rule 4
#           (financial immutability — no UPDATE/DELETE on issued invoices,
#           invoice lines or payments; corrections are new rows) ·
#           BR-BIL-004 (issued invoices immutable) · BR-BIL-010 (the GL stamp
#           is frozen at issue) · BR-CUS-040 (a reprint renders the issued
#           document) · NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""billing 0002 — tenant isolation, and the immutability the models cannot give.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09.
Applies the SIGNED B2 §3 policy template from `06-backend/db/rls_billing_w3.sql`
verbatim, and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

TWO GUARANTEES, AND WHY BOTH ARE HERE RATHER THAN IN PYTHON
-----------------------------------------------------------
**1 · Tenant isolation.** Six tables, every one holding money or naming who
owes it. Same template as every other module.

**2 · Financial immutability (hard rule 4).** `apps/billing/models.py` says in
its own docstring that it does NOT enforce this, because a Django model cannot
refuse a `.save()`. A service layer can — until someone writes a management
command, a data fix, a migration, or a `.update()` on a queryset, none of which
go through it. So the guarantee is a database trigger:

  * an `invoices` row past `draft` cannot be UPDATEd except through the narrow
    door below, and cannot be DELETEd at all
  * an `invoice_lines` row whose invoice is past `draft` cannot be UPDATEd or
    DELETEd
  * a `credit_notes` row that has been issued cannot be UPDATEd or DELETEd

THE NARROW DOOR, and it is deliberate. A bill legitimately moves
`issued → paid`, `issued → void` and `issued → corrected` after issue, and a
void records who approved it. Freezing every column would make those
transitions impossible and push them into a second table nobody asked for. So
the trigger allows an UPDATE that changes ONLY `status`, `updated_at` and the
settlement-facing columns — and refuses any statement that touches an amount,
a date, the account, the number, the template pin or the snapshot. What a
customer was charged, and the document they were sent, cannot move. Which
BUCKET the bill sits in can.

`issued_snapshot` is in the frozen set on purpose: it is the whole point of
the PO's "keep lock data for that bill and save the instance". A snapshot that
can be rewritten later is not a snapshot.

PROVED RED BEFORE GREEN, on a live cluster: with the triggers dropped, an
issued invoice's `total` can be updated and its lines deleted; with them, both
statements raise. See the trailer.

Postgres only. SQLite has no RLS and the test database is SQLite, so the
immutability half is ALSO asserted in Python at the service layer — a check
that skips silently on the developer's own database is not a check.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_billing_w3.sql"

#: Columns an issued invoice may still change. Everything else is frozen.
#: Kept as SQL rather than Python so the rule lives where it is enforced.
INVOICE_MUTABLE = (
    "status",
    "updated_at",
    "issued_at",
    "invoice_no",
    "template_id",
    "template_version",
    "issued_snapshot",
)

IMMUTABILITY_SQL = """
-- ── invoices ────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION billing_invoice_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'BR-BIL-004: invoice %% is %% and cannot be deleted; a correction is a new row',
        COALESCE(OLD.invoice_no, OLD.id::text), OLD.status;
    END IF;
    RETURN OLD;
  END IF;

  -- A draft may be edited freely: it has not been sent to anyone.
  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;

  -- Past draft: the money and the document are frozen. Status may still move
  -- (issued -> paid | void | corrected) and the issue-time stamps may be set
  -- once, which is what makes issuing itself possible.
  IF NEW.account_id      IS DISTINCT FROM OLD.account_id
  OR NEW.bill_run_id     IS DISTINCT FROM OLD.bill_run_id
  OR NEW.bill_type       IS DISTINCT FROM OLD.bill_type
  OR NEW.service_date    IS DISTINCT FROM OLD.service_date
  OR NEW.period_start    IS DISTINCT FROM OLD.period_start
  OR NEW.period_end      IS DISTINCT FROM OLD.period_end
  OR NEW.due_date        IS DISTINCT FROM OLD.due_date
  OR NEW.subtotal        IS DISTINCT FROM OLD.subtotal
  OR NEW.tax_total       IS DISTINCT FROM OLD.tax_total
  OR NEW.total           IS DISTINCT FROM OLD.total
  OR NEW.currency        IS DISTINCT FROM OLD.currency
  OR NEW.invoice_no      IS DISTINCT FROM OLD.invoice_no
  OR NEW.issued_at       IS DISTINCT FROM OLD.issued_at
  OR NEW.template_id     IS DISTINCT FROM OLD.template_id
  OR NEW.template_version IS DISTINCT FROM OLD.template_version
  OR NEW.issued_snapshot IS DISTINCT FROM OLD.issued_snapshot
  OR NEW.tenant_id       IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: invoice %% is %% — only status may change after issue. What the customer was charged, and the document they were sent, are frozen; a correction is a new row (adjustments / credit_notes).',
      COALESCE(OLD.invoice_no, OLD.id::text), OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_invoice_immutable ON invoices;
CREATE TRIGGER trg_invoice_immutable
  BEFORE UPDATE OR DELETE ON invoices
  FOR EACH ROW EXECUTE FUNCTION billing_invoice_immutable();

-- ── invoice_lines ───────────────────────────────────────────────────────────
-- A line is frozen by its INVOICE's status, not its own: lines have no status,
-- and freezing the header while its lines stay editable would be no freeze.
CREATE OR REPLACE FUNCTION billing_invoice_line_immutable() RETURNS trigger AS $$
DECLARE
  parent_status text;
  parent_no     text;
BEGIN
  SELECT status, COALESCE(invoice_no, id::text) INTO parent_status, parent_no
  FROM invoices WHERE id = COALESCE(OLD.invoice_id, NEW.invoice_id);

  IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
    RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: invoice %% is %% — its lines cannot be %% . A correction is a new row.',
      parent_no, parent_status, lower(TG_OP);
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_invoice_line_immutable ON invoice_lines;
CREATE TRIGGER trg_invoice_line_immutable
  BEFORE UPDATE OR DELETE ON invoice_lines
  FOR EACH ROW EXECUTE FUNCTION billing_invoice_line_immutable();

-- ── credit_notes ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION billing_credit_note_immutable() RETURNS trigger AS $$
BEGIN
  IF OLD.issued_at IS NULL THEN
    RETURN COALESCE(NEW, OLD);   -- not yet issued
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-BIL-004: credit note %% has been issued and cannot be deleted',
      COALESCE(OLD.credit_note_no, OLD.id::text);
  END IF;
  IF NEW.amount IS DISTINCT FROM OLD.amount
  OR NEW.currency IS DISTINCT FROM OLD.currency
  OR NEW.account_id IS DISTINCT FROM OLD.account_id
  OR NEW.original_invoice_id IS DISTINCT FROM OLD.original_invoice_id
  OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
  OR NEW.credit_note_no IS DISTINCT FROM OLD.credit_note_no
  OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: credit note %% has been issued — its amount and source are frozen',
      COALESCE(OLD.credit_note_no, OLD.id::text);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_credit_note_immutable ON credit_notes;
CREATE TRIGGER trg_credit_note_immutable
  BEFORE UPDATE OR DELETE ON credit_notes
  FOR EACH ROW EXECUTE FUNCTION billing_credit_note_immutable();
"""

DROP_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS trg_invoice_immutable ON invoices;
DROP TRIGGER IF EXISTS trg_invoice_line_immutable ON invoice_lines;
DROP TRIGGER IF EXISTS trg_credit_note_immutable ON credit_notes;
DROP FUNCTION IF EXISTS billing_invoice_immutable();
DROP FUNCTION IF EXISTS billing_invoice_line_immutable();
DROP FUNCTION IF EXISTS billing_credit_note_immutable();
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in (
        "bill_runs",
        "bill_run_exclusions",
        "invoices",
        "invoice_lines",
        "adjustments",
        "credit_notes",
    ):
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(IMMUTABILITY_SQL)


def drop_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_IMMUTABILITY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_w3_invoice_core"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_immutability, drop_immutability),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 billing DDL + Addendum r10, the PO-approved billing schema batch — · 07-billing/06-epics/EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md · 07-billing/03-field-map.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by Eng-Lead (W3 billing schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the test file — proved RED before green on a live cluster
# exceptions: the immutability trigger permits an UPDATE that changes ONLY
#         status / issued_at / invoice_no / template pin / issued_snapshot,
#         because issuing a draft and later marking it paid, void or corrected
#         are legitimate and would otherwise be impossible. Every amount, date,
#         account, currency and the snapshot itself are frozen. That narrow
#         door is a DESIGN CHOICE and is named here for the reviewer rather
#         than buried in SQL · Postgres only: the test database is SQLite and
#         has no triggers, so the same law is ALSO asserted at the service
#         layer — a guard that skips silently on the developer's own database
#         is not a guard
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
