"""customers 0056 — `service_request_documents.original_size`, so a shrunk file
can say so.
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT ADDS AND WHY IT IS NULLABLE
────────────────────────────────────────────────────────────────────────────
One column, `original_size BIGINT NULL`, beside the `size` that has been there
since `0017`.

`size` is what is ON DISK. `original_size` is what the clerk CHOSE, and it is
written **only when the two differ** — that is, only when
`core.document_shrink` losslessly re-deflated an oversized image on the way in.
A PDF is stored byte for byte and this column stays NULL for it.

⚠ **NULL IS A REAL ANSWER HERE AND IT IS NOT "UNKNOWN".** It means *nothing was
done to this file; `size` is what arrived*. That is why the column is nullable
rather than backfilled to equal `size`: a column that always equalled `size`
could not tell an untouched file from a shrunk one, and the question this
column exists to answer is precisely *why is this 400 KB when I chose a 3.1 MB
file?*

⚠ **NO BACKFILL, AND THE REASON IS THAT THERE IS NOTHING TO BACK-FILL.**
`service_request_documents` holds **6 rows on the beta cluster and not one of
them has a file**, so not one has an original size and NULL is already the
correct value for all six.

⚠ **THIS PARAGRAPH SAID THOSE SIX ROWS HAVE A NULL `storage_ref` AND THAT WAS
WRITTEN WITHOUT MEASURING IT. IT IS FALSE — `DEF-CUS-5872`, filed the same
day.** Measured properly: every one of the six carries a `storage_ref` shaped
`sample-data://cr030/osei-move-in/tenancy-agreement.pdf`, **none of the six
resolves to any `stored_documents` row**, every `size` is NULL, and **four of
them read `verified`** — a clerk having certified a file that does not exist.
They are seeded sample rows, not clerks' ticks.

**The conclusion this paragraph drew is unaffected and the migration is
unchanged**: those refs point at nothing, so no row has a real original size
and there is still nothing to back-fill. **What the correction costs is a
belief about the data**, and it is written out here rather than quietly fixed
because it is the same shape as the defect it describes — a reference that
looks set and resolves to nothing, believed because nobody followed it.

⚠ **THE ROWS ARE NOT IMMUTABLE AND THIS DOES NOT MAKE THEM SO.**
`service_request_documents` is not one of the tables CLAUDE.md hard rule 4
freezes — that list is issued invoices, invoice lines, payments and journal
entries. A tick may later be given the file it was waiting for, which is the
`document_id` branch of `service_request_documents.attach_file`. **The BYTES are
still write-once**: they live in `stored_documents` under `0026`'s trigger and a
seven-year object lock, and nothing in this product can replace the file behind
a row that already has one.

LOCK COST
────────────────────────────────────────────────────────────────────────────
`ADD COLUMN` with a NULL default and no constraint is a catalogue-only change
on PostgreSQL 11+: no table rewrite, no validation scan, an ACCESS EXCLUSIVE
lock held for microseconds. Six rows regardless.

REVERSIBLE, AND THE REVERSAL LOSES ONLY A DERIVED FACT
────────────────────────────────────────────────────────────────────────────
`RemoveField` is a plain `DROP COLUMN`. Unlike `tenancy/0045` this reversal
needs no refusal: dropping it destroys no document and strands no row — the
bytes and their true length are in `stored_documents.byte_length`, which is
where the store keeps them and which nothing here duplicates for safety. What
is lost is the record of what the file measured BEFORE it was shrunk, and that
is not recoverable from anywhere else. A rollback should therefore be a
deliberate act, not a tidy-up.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("customers", "0055_rls_br_cus_1079_account_types")]

    operations = [
        migrations.AddField(
            model_name="servicerequestdocument",
            name="original_size",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
