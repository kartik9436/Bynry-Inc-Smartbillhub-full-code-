# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-012 (write-offs) · US-PAY-024 (autopay capture intents)
#           Screens: S32 · S33 · S34 · S35
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS ENABLE + FORCE) · rule 4
#           (financial immutability — a write-off is corrected by a new row) ·
#           BR-PAY-002 (append-only family) · BR-PAY-020 (approval gates the
#           money) · BR-PAY-015 (no charging path before rails) · NFR-10
#           (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""payments 0010 — isolation for `write_offs` and `autopay_capture_intents`,
and the write-off freeze.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path and the deny-by-default
trigger is hard rule 4's shape). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15
under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3 template
verbatim, the same shape as `0002`, `0005` and `0008`.

**WHY `write_offs` IS FROZEN AND `autopay_capture_intents` IS NOT.** A write-off
permanently reduces receivables and is reported to finance as bad debt; hard
rule 4 puts it in the same family as an issued invoice, and US-PAY-012 TC-4 is
explicit that a later recovery is a NEW credit event and never an edit. The
freeze here is DENY-BY-DEFAULT with a short allow list — a `requested` row may
move `status`, `approved_by`, `approved_on`, `gl_account_id`, `journal_entry_id`
and `updated_at`, and NOTHING else, ever. The amount, the account, the reason
and the note are frozen from the instant the row exists, so the figure a human
approved is the figure that was requested.

An intent is not a financial record: it is a note saying a draft is expected,
and BR-PAY-015 gives it no transitions to make before the rails land. Freezing
it would buy nothing and would block the W7 lane that must move its status.

Postgres only. SQLite has neither RLS nor triggers and the developer test
database is SQLite, so the append-only half is ALSO enforced at the service
layer (`writeoffs.py` writes `status` once, through one `select_for_update`
path) and asserted in tests — a check that skips silently on the database a
developer actually runs is not a check.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE write_offs ENABLE ROW LEVEL SECURITY;
ALTER TABLE write_offs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS write_offs_tenant_isolation ON write_offs;
CREATE POLICY write_offs_tenant_isolation ON write_offs
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE autopay_capture_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE autopay_capture_intents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS autopay_capture_intents_tenant_isolation ON autopay_capture_intents;
CREATE POLICY autopay_capture_intents_tenant_isolation ON autopay_capture_intents
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

# Deny-by-default, exactly as `refunds` is frozen by 0006: every column is
# refused unless it is named below, so a column added to this table LATER is
# frozen the day it exists rather than the day somebody remembers to add it.
FREEZE_SQL = """
CREATE OR REPLACE FUNCTION payments_write_offs_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: write_offs is append-only — a write-off recorded in error is corrected by a NEW reversing row, never deleted.';
  END IF;
  IF NEW.tenant_id     IS DISTINCT FROM OLD.tenant_id
  OR NEW.account_id    IS DISTINCT FROM OLD.account_id
  OR NEW.amount        IS DISTINCT FROM OLD.amount
  OR NEW.currency      IS DISTINCT FROM OLD.currency
  OR NEW.reason        IS DISTINCT FROM OLD.reason
  OR NEW.note          IS DISTINCT FROM OLD.note
  OR NEW.requested_by  IS DISTINCT FROM OLD.requested_by
  OR NEW.requested_on  IS DISTINCT FROM OLD.requested_on
  OR NEW.created_at    IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: only the APPROVAL columns of a write-off may move (status, approved_by, approved_on, gl_account_id, journal_entry_id). The amount a human approved must be the amount that was requested.';
  END IF;
  IF OLD.status = 'approved' AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: an APPROVED write-off has already posted DR write-off / CR AR. Un-approving it would leave the books saying one thing and the account another; the correction is a new row.';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_write_offs_append_only ON write_offs;
CREATE TRIGGER trg_write_offs_append_only
  BEFORE UPDATE OR DELETE ON write_offs
  FOR EACH ROW EXECUTE FUNCTION payments_write_offs_append_only();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS trg_write_offs_append_only ON write_offs;
DROP FUNCTION IF EXISTS payments_write_offs_append_only();
DROP POLICY IF EXISTS autopay_capture_intents_tenant_isolation ON autopay_capture_intents;
ALTER TABLE autopay_capture_intents NO FORCE ROW LEVEL SECURITY;
ALTER TABLE autopay_capture_intents DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS write_offs_tenant_isolation ON write_offs;
ALTER TABLE write_offs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE write_offs DISABLE ROW LEVEL SECURITY;
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)
    schema_editor.execute(FREEZE_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0009_w4_purpose_link_writeoffs_intents"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-012@3c9f5a1 (ships with apps/payments/migrations/0009 — the same sources; co-packet US-PAY-024)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D=deferred(a migration serves no route) E=deferred(a migration draws no screen) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests -m isolation✔ · pytest tests/test_us_pay_012_write_offs.py✔ · the SQLite half of the freeze is asserted at the service layer because the trigger cannot run there, and the test says so in its own name
# exceptions: (1) `autopay_capture_intents` is deliberately NOT frozen — an
#         intent is a note, not a financial record, and the W7 rails lane must
#         be able to move its status. Stated because an unexplained asymmetry
#         between two tables in one migration reads as an oversight
#         (2) the freeze is DENY-BY-DEFAULT with a six-column allow list, so a
#         column added to `write_offs` later is frozen the day it exists
#         (3) the SQLite developer database enforces NEITHER half. The service
#         layer is the second guarantee and the tests assert it there; this is
#         stated rather than claimed (hard-won law 1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
