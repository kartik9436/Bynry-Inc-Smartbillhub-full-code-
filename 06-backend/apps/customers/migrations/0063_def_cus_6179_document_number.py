# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-22 — *"Yes, last four only"*, and the lane
#           judgment taken the same day (option (a): a `Document number` field
#           of its own, with `What it proves` kept for words).
# Rules:    BR-CUS-092(c) — every read path renders last four only
# Defect:   DEF-CUS-6179 — a driving licence number in plain text on a list
# ───────────────────────────────────────────────────────
"""`service_request_documents.document_number` — the number ON the paper.

**WHY A COLUMN AND NOT A RE-USE.** The capture form asked one free-text
question, *what does this document prove*, and the Documents tab's column
carried the same three words. A clerk holding a driving licence had nowhere to
put `865554556` and typed it into the words box, where it printed in full on a
list screen — which `BR-CUS-092(c)` has forbidden on every read path since
2026-08-24.

**NULLABLE, NO BACKFILL, NO DEFAULT.** Nothing can derive this number for a row
written before today: the digits that are in `what_it_proves` on some rows are
there by accident and the words on the rest are not numbers. A backfill would
have to guess which is which, and a guess on a government identifier is the
defect running forwards. Existing rows carry NULL and the cell reads as an
absence, which is true.

⚠ **PLAIN TEXT, DELIBERATELY AND NARROWLY.** `BR-CUS-092` names two identifiers
this product encrypts — the SSN and the driving licence — and both have their
own encrypted columns on `service_requests`, with a blind index beside the
licence. This is the reference number of whatever paper was handed over, and it
is protected by the MASK on the way out rather than by a cipher at rest. If a
later ruling says a licence number stored here must be encrypted, that is a
second migration and a second decision; it is not silently assumed here.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0062_br_cus_1083_disconnect_visits"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequestdocument",
            name="document_number",
            field=models.TextField(blank=True, null=True),
        ),
    ]
