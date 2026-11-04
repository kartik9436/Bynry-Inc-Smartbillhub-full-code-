# ── Trace ──────────────────────────────────────────────
# Change:  CR-054 W1 task 7 — the generated reading sheet's ROW KEY survives
#          the round trip, so a row whose meter no longer matches the row it
#          was written for is caught by name.   Screens: RDS-03 stages 2–3
# Rules:   BR-MET-032 (ONE published template, ONE parser — the sheet must
#          re-upload through the importer that already exists, so the key is a
#          column on that template and not a second file format) ·
#          BR-MET-122's SHAPE (a disagreement between the file and the registry
#          is a WARNING the clerk accepts with a reason — never silent, never a
#          hard refusal) · BR-MET-054 (staged rows are the only rows this table
#          ever holds; nothing here touches a committed read) ·
#          CLAUDE.md hard rule 4 (no committed read is altered — `meter_reads`
#          is not touched by this migration at all)
# Tests:   06-backend/tests/test_cr054_w1_reading_sheet.py
# Impacts: apps/metering/models.py (ReadImportRow.row_key) ·
#          apps/metering/read_import.py (the `row_key` template column) ·
#          apps/metering/services.py (staging writes it; _build_context reads
#          it onto the ReadContext) · apps/metering/validation.py (RULE_ROW_KEY)
# ───────────────────────────────────────────────────────
"""metering 0043 — `read_import_rows.row_key`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-30 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

**WHY A COLUMN AND NOT A PARSE-TIME CHECK.** The obvious cheaper design is to
compare the key against the meter while the file is being parsed and never
store it. It does not work, and the reason is worth writing down because the
next lane will think of it too: **the validation engine runs from the STAGED
ROWS, not from the file.** `services.validate_read_batch` re-reads
`ReadImportRow` — by then the uploaded bytes are gone and no `ParsedRow`
exists — so a key that lived only in the parser would have evaporated before
any rule could see it, and re-validating a batch (which a clerk does after
fixing rows) would silently stop judging it.

**WHAT IT HOLDS.** The key the generated reading sheet stamped on the row,
verbatim: `<cycle code>|<channel code>|<meter number>`, e.g.
`CY-001|tou_on|M-4021`. It is never parsed into parts on the way in — the
grammar lives once, in `read_import.parse_row_key`.

**NULLABLE, AND EVERY EXISTING ROW KEEPS NULL.** There is no backfill and there
must not be one: a row staged before this column existed was never generated
from a sheet, so any value written into it would be a claim about a file nobody
produced. `validation._row_key_outcome` reads NULL as *"there is no key to
judge"* and emits nothing at all — a hand-built file's report is unchanged.

**ROLLBACK** is a clean drop of the column. It carries no constraint, no index
and no foreign key; nothing downstream reads it except one rule, which answers
"no key" the moment it is gone. Staged rows are hard-deletable by BR-MET-054
and no committed read is touched, so there is no immutability question here at
all (CLAUDE.md hard rule 4).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0042_cr046_c5_external_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="readimportrow",
            name="row_key",
            field=models.TextField(blank=True, null=True),
        ),
    ]
