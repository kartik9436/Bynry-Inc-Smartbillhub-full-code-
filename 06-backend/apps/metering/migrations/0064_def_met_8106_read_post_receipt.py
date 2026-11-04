"""metering 0064 — a read batch keeps the receipt of its own post (`DEF-MET-8106`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-30 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

WHY A COLUMN
------------
Posting 480 readings took 42-60 seconds inside the request, and the web worker
is killed at 60: the readings were saved, the clerk saw *Internal Server
Error*, and the receipt — how many posted, which rows were held and why — was
lost with the response. The PO's fix (A), ruled 2026-09-30, posts a large batch
as a BACKGROUND JOB with a progress bar. A job's answer cannot travel back on
the request that started it, so the receipt has to be KEPT somewhere the screen
can ask for it when the bar reaches the end: `GET /read-batches/{id}/post-receipt`.

`read_import_batches.post_receipt` is that place. It holds the post's own
figures (posted, held, superseded, the held rows' reasons, the cycle shortfall,
the usage rebuild's job) exactly as the synchronous post answers them, so the
two paths print one receipt. It is written once, in the post's own
transaction, and is NULL on every batch that has not posted — including every
batch that exists today, so there is nothing to backfill.

⚠ **NOT RE-DERIVED ON READ, DELIBERATELY.** Most of the receipt could be
recounted from `meter_reads` and the staged rows, but *"superseded 41"* cannot:
the heads it closed are closed inside the post's transaction, and afterwards no
query tells "closed by this batch" from "closed earlier". The same argument
`connections.commit_result` (metering 0063) makes for the New Connect answer.

ROLLBACK: `manage.py migrate metering 0063` drops the column; the only reader is
the post-receipt endpoint, which then answers 404 for a deferred post's receipt
and the screen falls back to the batch's own counts.
"""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0063_def_cus_8021_commit_idempotency"),
    ]

    operations = [
        migrations.AddField(
            model_name="readimportbatch",
            name="post_receipt",
            field=models.JSONField(blank=True, null=True, encoder=DjangoJSONEncoder),
        ),
    ]
