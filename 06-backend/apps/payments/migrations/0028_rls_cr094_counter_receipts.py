# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15.
# Story:    US-LED-001   Screens: capture step 5 · the finance books
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS **FORCE**) · hard rule 4
#           (financial immutability — corrections are new rows) · BR-PAY-1140
# Tests:    06-backend/tests/test_cr094_counter_receipt_posts.py
# ───────────────────────────────────────────────────────
"""payments 0028 — isolation for `counter_receipts`, and its FREEZE law.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths) ·
HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. It applies the
SIGNED B2 §3 policy template VERBATIM and invents no new policy shape — the
same template `payments/0022` carries for `payment_tenders`.

╔══════════════════════════════════════════════════════════════════════════╗
║  A COUNTER RECEIPT NAMES A PERSON, AN ADDRESS THEY ARE APPLYING FOR, AND ║
║  THE LAST FOUR DIGITS OF THEIR CARD. A CROSS-TENANT READ IS SOMEBODY     ║
║  ELSE'S CUSTOMER.                                                       ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
THE FREEZE, AND WHY IT IS A COLUMN LIST RATHER THAN A FLAT BAN
────────────────────────────────────────────────────────────────────────────
Hard rule 4 names `payments`, `invoice_lines`, `payments` and `journal_entries`
and says nothing about this table, so it gets a trigger of its own. But unlike
`payment_tenders` this row has a genuine SECOND act — the release, which turns a
held liability into revenue and must be recorded ON the row so a reader can tell
`held` from `earned` without re-deriving it from a request that may since have
been reopened.

So the trigger takes the shape hard rule 4 itself took when the PO narrowed it
on 2026-09-02: **a named allow list and nothing else.**

  FROZEN FOREVER — what was handed over, which is the evidence:
    tenant_id · source_type · source_id · source_ref · receipt_no · amount ·
    currency · method_id · card_last4 · card_brand · card_auth_code ·
    cheque_no · drawer_bank · cheque_date · taken_at · taken_by ·
    collection_entry_id · created_at

  WRITABLE ONCE, BY `apps/payments/counter_receipts.py` AND NOTHING ELSE:
    state · released_at · released_by · earned_amount · revenue_postings ·
    release_entry_id · release_error · payment_id · attached_at · updated_at

**DELETE IS REFUSED IN EVERY STATE**, exactly as it is on `payments`. A receipt
that could be deleted is a cash drawer that stops reconciling, which is the
sentence from p085 this whole change was built on.

⚠ **THE STATE WALK IS ONE-WAY AND THE TRIGGER, NOT THE SERVICE, IS WHAT MAKES
IT TRUE.** `held → applied` and `held → earned` are the only moves. A request
that is refused and later REOPENED (B18 §5.3.3 keeps it, TC-REQ-10 requires it)
says `under_review` again while the $25.00 has been revenue for a fortnight —
the books do not reopen, and this refuses the write that would say they did.

────────────────────────────────────────────────────────────────────────────
NOTE ON `%%`
────────────────────────────────────────────────────────────────────────────
`schema_editor.execute(sql)` passes `params=()` to psycopg, which then treats
the string as a format template, so a lone `%` in a RAISE aborts the migration.
Every placeholder below is doubled and arrives at the server as a single `%`.
Same reason as payments/0002, 0005, 0013 and 0022.
"""

from django.db import migrations

TABLE = "counter_receipts"

RLS_SQL = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""

FREEZE_SQL = """
CREATE OR REPLACE FUNCTION payments_counter_receipt_freeze() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'hard rule 4: a counter receipt is never deleted. %% holds what a clerk took at a desk and a receipt that could be deleted is a cash drawer that stops reconciling. Unwind money by posting, never by removing the evidence.',
      OLD.receipt_no;
  END IF;

  IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
     OR NEW.source_type IS DISTINCT FROM OLD.source_type
     OR NEW.source_id IS DISTINCT FROM OLD.source_id
     OR NEW.source_ref IS DISTINCT FROM OLD.source_ref
     OR NEW.receipt_no IS DISTINCT FROM OLD.receipt_no
     OR NEW.amount IS DISTINCT FROM OLD.amount
     OR NEW.currency IS DISTINCT FROM OLD.currency
     OR NEW.method_id IS DISTINCT FROM OLD.method_id
     OR NEW.card_last4 IS DISTINCT FROM OLD.card_last4
     OR NEW.card_brand IS DISTINCT FROM OLD.card_brand
     OR NEW.card_auth_code IS DISTINCT FROM OLD.card_auth_code
     OR NEW.cheque_no IS DISTINCT FROM OLD.cheque_no
     OR NEW.drawer_bank IS DISTINCT FROM OLD.drawer_bank
     OR NEW.cheque_date IS DISTINCT FROM OLD.cheque_date
     OR NEW.taken_at IS DISTINCT FROM OLD.taken_at
     OR NEW.taken_by IS DISTINCT FROM OLD.taken_by
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'hard rule 4: counter receipt %% records what was handed over and that half is frozen. Only the RELEASE columns move (state, released_at, released_by, earned_amount, revenue_postings, release_entry_id, release_error, payment_id, attached_at). Correct money by posting a new entry, never by editing this row.',
      OLD.receipt_no;
  END IF;

  IF OLD.collection_entry_id IS NOT NULL
     AND NEW.collection_entry_id IS DISTINCT FROM OLD.collection_entry_id THEN
    RAISE EXCEPTION 'hard rule 4: counter receipt %% already names the journal entry it is evidence for. Re-pointing it would rewrite which entry this money made.',
      OLD.receipt_no;
  END IF;

  IF OLD.state <> 'held' AND NEW.state IS DISTINCT FROM OLD.state THEN
    RAISE EXCEPTION 'hard rule 4: counter receipt %% is already %%; the liability is released once. A reopened request does not reopen the books.',
      OLD.receipt_no, OLD.state;
  END IF;

  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_counter_receipt_freeze ON counter_receipts;
CREATE TRIGGER trg_counter_receipt_freeze
  BEFORE UPDATE OR DELETE ON counter_receipts
  FOR EACH ROW EXECUTE FUNCTION payments_counter_receipt_freeze();
"""

DROP_FREEZE_SQL = """
DROP TRIGGER IF EXISTS trg_counter_receipt_freeze ON counter_receipts;
DROP FUNCTION IF EXISTS payments_counter_receipt_freeze();
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL)


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


def apply_freeze(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FREEZE_SQL)


def drop_freeze(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_FREEZE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0027_cr094_counter_receipts"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_freeze, drop_freeze),
    ]
