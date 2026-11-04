# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6376 — a service request's *Record what was handed over*
#           was not the Record-a-payment form: no posting date, no memo, no
#           reference. PO, on SR-26-0016, verbatim: *"this screens takes the
#           payment it should be similar to record payment form so pasting
#           date, type of payment , memo and it will take only application
#           fee"*.
# Rules:    CLAUDE.md hard rule 2 · hard rule 4's spirit on `counter_receipts`
#           (payments/0028's freeze) · BR-TEN-081 (a typed date is the TENANT's
#           day) · decision log 2026-09-19 OPTION A2 (no payment row until the
#           account exists — so these facts wait on the receipt)
# Tests:    06-backend/tests/test_def_cus_6376_request_fee_like_record_payment.py
#           (SQLite) and the PostgreSQL proof named in that file's header
# Impacts:  apps/payments/counter_receipt_models.py · apps/payments/
#           counter_receipts.py (the only writer)
# ───────────────────────────────────────────────────────
"""payments 0042 — THREE write-once columns on `counter_receipts`, and nothing else.

HUMAN-OWNED (migration ordering and financial immutability are CLAUDE.md 🔒
paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
A counter receipt now carries Record a payment's three facts — **`posted_on`**
(the business day it counts for), **`confirmation`** (the instrument's own
number) and **`memo`** — each written at INSERT and **frozen from then on**, the
same as every other fact about what was handed over.

**Worked:** Dana takes $70.00 cash for SR-26-0016 on 22 September and posts it
for the 21st → the receipt reads `posted_on = 2026-09-21`, the collection entry
`DR 1010 70.0000 · CR 2400 70.0000` is dated **2026-09-21**, and when the
approved application's account finally exists the `Payment` is dated midnight
on the 21st in the utility's own zone (BR-TEN-081).

═══════════════════════════════════════════════════════════════════════════════
WHY THE FREEZE FUNCTION IS REDEFINED, AND WHY THAT NARROWS RATHER THAN WIDENS
═══════════════════════════════════════════════════════════════════════════════
`payments/0028`'s trigger freezes a NAMED LIST of columns (it is a deny list of
what may not change, with the release columns left writable). A column added
after it is therefore **writable by default** — the opposite of `payments`'
whole-row trigger, where a new column is frozen the day it exists. So adding
these three without touching the function would have left a posting date, a
reference and a memo that anything with a database connection could rewrite
after the money was booked.

The body below is 0028's **byte for byte** with three lines added to the frozen
list. It widens nothing: the release columns are exactly as writable as they
were, DELETE is still refused in every state, the collection entry is still
write-once, and the state walk is still one-way. **Hard rule 4's own allow list
(`payments/0014`, the `payments` table) is not touched** — this is
`counter_receipts`, which hard rule 4 does not name and which 0028 froze on its
own authority.

REVERSE restores 0028's body exactly, read from 0028 itself, so unapplying this
leaves the function as it was before rather than as somebody remembered it.

SQLite has no triggers; the freeze is proved on PostgreSQL (hard-won law 14).
"""

from importlib import import_module

from django.db import migrations, models

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
     OR NEW.posted_on IS DISTINCT FROM OLD.posted_on
     OR NEW.confirmation IS DISTINCT FROM OLD.confirmation
     OR NEW.memo IS DISTINCT FROM OLD.memo
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
"""


def _previous_freeze_sql() -> str:
    """0028's own body — the function exactly as it stood before this file."""
    return import_module("apps.payments.migrations.0028_rls_cr094_counter_receipts").FREEZE_SQL


def apply_freeze(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FREEZE_SQL)


def restore_freeze(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_previous_freeze_sql())


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0041_def_pay_6331_cheque_number_at_issue"),
    ]

    operations = [
        migrations.AddField(
            model_name="counterreceipt",
            name="posted_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="counterreceipt",
            name="confirmation",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="counterreceipt",
            name="memo",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(apply_freeze, restore_freeze),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-6376 · payments/0028 (the freeze this narrows) · decision log
#   2026-09-19 (A2) · BR-TEN-081
# generated: 2026-09-23 by LANE REQ-FEE
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · migrate forwards and backwards on PostgreSQL ·
#   the freeze refusing an UPDATE of each new column, on PostgreSQL
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
