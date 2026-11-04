# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W5 — Payments carry the utility's own fields,
#           captured at entry only. PO 2026-10-02 (commit `aa4d30f8b`), R3:
#           *"Payments IN as capture-at-entry only"*; Part 2 row 14: *"Record
#           payment (at entry only) · Payment detail · Can't be corrected
#           afterwards; never used to apply the payment to bills"*.
# Rules:    BR-TEN-046 (as amended 2026-10-02 — `payments` joins the entity
#           list) · BR-TEN-048 (UNCHANGED — never allocation, deposit, refund,
#           dunning, rating, tax or a ledger posting) · CLAUDE.md hard rule 4
#           (the allow list in `payments/0014` does NOT move) · hard rule 1
# Tests:    06-backend/tests/test_cr161_w5_payment_custom_fields.py
# Impacts:  apps/payments/models.Payment.custom_data ·
#           apps/payments/custom_values.py (the only reader and writer)
# ───────────────────────────────────────────────────────
"""payments 0046 — ONE jsonb column on `payments`, `NOT NULL DEFAULT '{}'`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this adds a column
to a table hard rule 4 freezes). HUMAN-REVIEW-PENDING — AI-authored 2026-10-02
under the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*); row in 12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
A payment can hold the answers to the utility's own custom fields — e.g. a
cashier records *Drawer = 2* on a $120.00 cheque — written by the INSERT that
records the payment and by nothing afterwards.

═══════════════════════════════════════════════════════════════════════════════
WHAT DOES NOT CHANGE, AND IT IS THE POINT OF THE FILE
═══════════════════════════════════════════════════════════════════════════════
**`payments_payment_immutable()` is NOT redefined here and its allow list does
not move.** CLAUDE.md hard rule 4: *"`payments/0014` is the ONLY place the
database's allow list moves; widening it anywhere else is a new ruling, not
this one."* The trigger compares `to_jsonb(OLD) - <allow list>` with
`to_jsonb(NEW) - <allow list>`, so **a column added to `payments` is frozen the
day it is created** — `custom_data` is refused on UPDATE in every status with no
line of SQL from this file. That is exactly what the PO ruled (*"Can't be
corrected afterwards"*), and `tests/test_cr161_w5_payment_custom_fields.py`
proves it against PostgreSQL 16 (the SQLite suite has no trigger, law 14).

**Nothing about money moves.** The column is read by `custom_values.py` for the
Payment detail screen and nothing else; G6 (DB-17) fails any other read under
`apps/payments/`, including allocation, deposit batching, refunds and the
ledger handoff.

WHY THE DATABASE DEFAULT IS SET BY HAND
---------------------------------------
`JSONField(default=dict)` is a PYTHON default. `customers/0004` records the
same gap: an INSERT from a fixture, a repair script or a raw `INSERT` (several
payment paths are bulk inserts in tests and seeds) would hit NOT NULL instead
of getting `{}`. Adding a column with a constant default on PostgreSQL 11+ is a
catalogue change, not a table rewrite, so no UPDATE runs and the immutability
trigger is not fired by this migration.

ROLLBACK
--------
Reverse drops the default and the column. Answers already captured are lost
with it — they are captured-and-shown only, so no money figure depends on them.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

SET_DEFAULT_SQL = "ALTER TABLE payments ALTER COLUMN custom_data SET DEFAULT '{}'::jsonb;"
DROP_DEFAULT_SQL = "ALTER TABLE payments ALTER COLUMN custom_data DROP DEFAULT;"


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0045_oq_pay_12621_counter_receipt_names_its_till"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        PostgresOnlySQL(sql=SET_DEFAULT_SQL, reverse_sql=DROP_DEFAULT_SQL),
    ]
