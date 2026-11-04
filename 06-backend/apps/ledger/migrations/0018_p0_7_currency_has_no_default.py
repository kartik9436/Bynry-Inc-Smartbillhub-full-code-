# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.7` (2026-09-24) — *"Entry currency must equal
#           the tenant's configured currency. Stamped, not joined — hard rule 4
#           means a posted entry keeps its currency for ever, and BR-TEN-021
#           makes a currency change forward-only."* Outcome: *"A CAD tenant's
#           books cannot quietly become USD."* Blueprint p083 row D2:
#           *"models.py still says default='USD'"*.
# Rules:    CLAUDE.md hard rule 2 (`CHAR(3)`, never a float) · hard rule 4 (a
#           posted entry is immutable, so its currency is permanent) ·
#           `BR-TEN-021` (a currency change is forward-only)
# Tests:    06-backend/tests/test_p0_6_currency_lookup.py
# ───────────────────────────────────────────────────────
"""ledger 0018 — **the currency has no default, in Python either.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering, on a money column.
Ledger row: `12-governance/09-human-review-ledger.md`, *"What a currency is,
written down once"*.

WHAT THIS CHANGES — AND IT IS SMALLER AND SHARPER THAN IT LOOKS
----------------------------------------------------------------
`JournalEntry.currency` carried `default="USD"`. **The DATABASE column has been
`NOT NULL` with no default for as long as it has existed** — measured on
PostgreSQL 16.13 on 2026-09-24, `column_default` is `NULL` — so this default
lived only in Python, where it meant exactly one thing:

    a caller that forgets the currency silently gets US dollars.

For a CAD utility that is its books quietly becoming USD, one entry at a time,
with every total still footing. `journal_entries.currency` is `NOT NULL` and
`tenancy/0050` makes it a foreign key into `currencies`, so **the database
would accept it too** — `USD` is a real currency, it is simply not that
utility's — and hard rule 4 means the row could never be corrected, only
reversed.

`PostingRequest.currency` has never had a default, deliberately, and its
docstring gives this exact reason: *"the source document always has one, and a
defaulted currency is how a CAD tenant's books quietly become USD"*. The model
now agrees with the request.

⚠ **THE DEFAULT WAS NEVER THE WHOLE GUARD, AND REMOVING IT IS NOT THE WHOLE
FIX.** A caller that passes the WRONG currency explicitly was never defaulting.
`posting._refuse_unless_the_tenants_currency` is the half that catches that,
on `post()` and on `save_draft()`, and it is where `P0.7`'s outcome sentence
actually lives.

REVERSIBLE, AND IT TOUCHES NO ROW AND NO COLUMN
------------------------------------------------
A Django `default` is applied by Python at INSERT and is never written into the
schema, so this operation emits **no DDL on PostgreSQL** and changes no stored
value. The reverse puts the default back. Proved forward → back → forward with
the column's `is_nullable` and `column_default` observed unchanged throughout —
because there is nothing there to change, which is the point.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0017_p0_1_customer_on_the_journal_line"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journalentry",
            name="currency",
            field=models.CharField(max_length=3),
        ),
    ]
