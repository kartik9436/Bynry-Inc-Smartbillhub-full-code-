# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1, second pass — two PO rulings that arrived AFTER 0026
#           was committed. (a) 2026-08-30: "if we want to just download all
#           documents for given utility - we should able to do it quickly".
#           (b) 2026-08-30: "curently we will start with AWS, but we need to
#           keep it multi cloud - google or any other cloud - in future we mght
#           have differnt requirements".
# Rules:    BR-NOT-027 · NFR-33 · NFR-35 · CLAUDE.md rule 1 · rule 4
# Tests:    06-backend/tests/test_cr049_t1_document_store.py
# ───────────────────────────────────────────────────────
"""tenancy 0027 — the export manifest's two columns, and the cloud's name.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-30 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md.

WHY THIS IS A SECOND MIGRATION AND NOT AN EDIT TO 0026
-------------------------------------------------------
`0026` was committed and pushed before either ruling arrived, and
`.github/workflows/migration-guard.yml` blocks edits to a committed migration —
correctly, and with only two content-pinned exceptions in the repo's history,
each its own PO ruling. Nothing has ever written a row into `stored_documents`,
so folding these into `0026` would have been *tidier* and would have hidden the
fact that the requirement arrived after the table. It arrived after the table.

THREE CHANGES
-------------
1. **`display_name`** — the human name an export unpacks to. Required and
   non-empty. **Written by the module storing the document, never composed
   here**, because a usable name needs the account number and the invoice
   number and those live in `customers` and `billing`; composing it in tenancy
   would be the cross-module read B2 §2 forbids. The argument is in
   `document_models.py`.

   It is added with a one-off `""` default and `preserve_default=False`, the
   ordinary Django shape for a NOT NULL column on an existing table. **On this
   table it back-fills nothing**: the table is empty, which is also why the
   non-empty CHECK can be added in the same migration without a data step.

2. **`ix_stored_docs_all` on `(tenant, stored_at)`** — the export's manifest
   query. Worked, because the number is the whole argument: a
   3,000-connection utility seven years in holds about **532,000 documents**,
   and enumerating them serially at ~30 ms each is **4.4 hours** before a byte
   moves. The export is answered from THIS INDEX and fetched in parallel, which
   is ~2.7 minutes. An unindexed scan of half a million rows is where those
   hours come back.

   There is deliberately no separate `(tenant, kind)` index:
   `ix_stored_docs_kind` is `(tenant, kind, stored_at)` and PostgreSQL serves
   any `(tenant, kind)` lookup from its leftmost columns, so a second index
   over the same prefix would never be chosen and would still be written on
   every insert.

3. **`storage_backend` accepts `aws_s3` instead of `s3`.** The value names the
   CLOUD, not the protocol. The S3 API is portable for put, get, pre-sign and
   checksum; **the compliance features this whole rule depends on are not** —
   object lock, lifecycle transitions and customer-managed keys are spelled
   differently on every cloud. A row saying `s3` could not tell a later reader
   whether its seven-year guarantee was held by S3 Object Lock, a GCS bucket
   retention policy or nothing at all. `gcs` and `azure_blob` are new values
   when an adapter for either exists, and each is its own migration.

   Safe because no row exists. If one ever did, this would need a data step
   first — said here because the next person adding a value will read this
   file to find out how.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0026_rls_document_store"),
    ]

    operations = [
        migrations.AddField(
            model_name="storeddocument",
            name="display_name",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=~models.Q(display_name=""), name="ck_stored_documents_name"
            ),
        ),
        migrations.AddIndex(
            model_name="storeddocument",
            index=models.Index(fields=["tenant", "stored_at"], name="ix_stored_docs_all"),
        ),
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_backend",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(storage_backend__in=("aws_s3", "filesystem")),
                name="ck_stored_documents_backend",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 step 5d(e) as amended 2026-08-30 · 12-governance/02-decision-log.md 2026-08-30 · BR-NOT-027 · NFR-33/NFR-35)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · migrate from empty on live PostgreSQL · the non-empty display-name CHECK proved RED (an INSERT with display_name='' refused) — transcript in the lane report
# exceptions: (1) A SECOND MIGRATION rather than an edit to 0026 — migration-guard blocks editing a committed migration, and the requirement genuinely arrived after the table. (2) The `s3` → `aws_s3` value change is safe ONLY because no row exists; a populated table would need a data step first, said in the docstring for the next person adding a value. (3) NO separate `(tenant, kind)` index — `ix_stored_docs_kind` already serves that prefix.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
