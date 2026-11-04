# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1 — the document store
# Rules:    CLAUDE.md rule 1 (tenant scoping — RLS ENABLE + FORCE, in the SAME
#           migration that creates the table) · rule 4 (financial immutability
#           — corrections are new rows) · BR-NOT-027 (a sent legal document is
#           frozen AS THE DOCUMENT) · NFR-35 (write-once, 7-year retention) ·
#           B2 §3 (the signed RLS template) · DEF-639 (the unset-tenant
#           predicate form)
# Tests:    06-backend/tests/test_cr049_t1_document_store.py
# ───────────────────────────────────────────────────────
"""tenancy 0026 — the stored-document table, its isolation and its freeze.

HUMAN-OWNED (RLS policies AND migration ordering are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-30 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

ONE MIGRATION, AND THE ORDER INSIDE IT IS THE POINT
----------------------------------------------------
The table, the RLS policy and the write-once trigger land TOGETHER. A table
that exists for even one migration without its policy is a table any tenant can
read, and this repo has a defect for exactly that shape (DEF-027 — a partition
born without a policy is a cross-tenant leak until something notices).
CLAUDE.md rule 1 says the policy comes with the table; this file is that
sentence made literal.

The policy text is the SIGNED B2 §3 template, taken from
`core.rls.tenant_isolation_policy_sql` rather than pasted. Not one character of
the predicate is this lane's: it is
`NULLIF(current_setting('app.tenant_id', true), '')::uuid` — the DEF-639 form,
which reads an unset tenant as ABSENT (deny, silently, on reads) rather than as
BROKEN (raise, which made a fresh database unbuildable at step 12 of 168).

THE FREEZE IS A TRIGGER, NOT A PYTHON GUARD
--------------------------------------------
`tenancy_stored_document_write_once` refuses **every** UPDATE and **every**
DELETE on `stored_documents`. There is no `IF OLD.status = 'draft'` escape and
no column-by-column comparison, and that is the one way it differs from
`billing/migrations/0006`'s `billing_invoice_immutable`, which it is otherwise
modelled on: an invoice has a lawful pre-frozen state (a draft) and may still
move status after issue. **A stored document has neither.** It is written once,
at the moment the bytes reach the object store, and from then on it is
evidence.

**It is at the database because a Python guard is bypassed by the next
`.save()`** — and by a shell, a data migration, and any endpoint a future lane
writes. `apps/tenancy/document_store.py` also refuses; that refusal is a better
error message, never the guarantee.

⚠ WHAT THIS TRIGGER DOES **NOT** DO, said plainly rather than left to be
assumed: **it does not protect the BYTES.** Deleting the object out of the
bucket leaves this row pointing at nothing, and no trigger in PostgreSQL can
see an S3 bucket. That is what `NFR-35`'s object lock (WORM, seven-year
retention) is for — beside this trigger, never instead of it. The deployment
checklist for it is in `apps/tenancy/document_storage.py`.

POSTGRES ONLY, AND SAID OUT LOUD
---------------------------------
`config/settings/test.py` hardcodes in-memory SQLite, which has neither RLS nor
triggers. So both guarantees are ALSO held in `document_store.py`, which
refuses an update and a delete in Python and is asserted on every vendor; the
database half carries `requires_postgres` and is proved on a live cluster under
a `NOSUPERUSER NOBYPASSRLS` role. A check that skips silently on the database a
developer actually runs is not a check.
"""

from django.db import migrations, models

import core.dbfields
from core.migrationtools import PostgresOnlySQL
from core.rls import tenant_isolation_policy_sql

POLICY_SQL = tenant_isolation_policy_sql("stored_documents")

REVERSE_POLICY_SQL = """
DROP POLICY IF EXISTS stored_documents_tenant_isolation ON stored_documents;
ALTER TABLE stored_documents NO FORCE ROW LEVEL SECURITY;
ALTER TABLE stored_documents DISABLE ROW LEVEL SECURITY;
"""

#: ⚠ `%` IS SINGLE HERE, and that is not an oversight of CLAUDE.md's "escape a
#: literal `%` as `%%`" note. `PostgresOnlySQL` is a `RunSQL` and passes the
#: statement with NO params, so PL/pgSQL receives it verbatim; a doubled `%%`
#: would hand RAISE four placeholders for two arguments. `billing/0019` records
#: the measured failure (`too many parameters specified for RAISE`);
#: `billing/0006` doubles them correctly because it travels through
#: `schema_editor.execute`, which performs %-substitution.
WRITE_ONCE_SQL = """
CREATE OR REPLACE FUNCTION tenancy_stored_document_write_once() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-NOT-027 / NFR-35: stored document % (%) cannot be deleted. It is the document a customer was sent, kept as evidence for seven years; there is no lawful edit and no lawful deletion, and a document that changed is a NEW row.',
      OLD.id, OLD.kind;
  END IF;
  RAISE EXCEPTION 'BR-NOT-027 / NFR-35: stored document % (%) cannot be updated. What the customer read is frozen at the moment it was stored; amending or re-rendering it is the exact thing the freeze exists to prevent, and a correction is a NEW row.',
    OLD.id, OLD.kind;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS stored_documents_write_once ON stored_documents;
CREATE TRIGGER stored_documents_write_once
  BEFORE UPDATE OR DELETE ON stored_documents
  FOR EACH ROW EXECUTE FUNCTION tenancy_stored_document_write_once();
"""

REVERSE_WRITE_ONCE_SQL = """
DROP TRIGGER IF EXISTS stored_documents_write_once ON stored_documents;
DROP FUNCTION IF EXISTS tenancy_stored_document_write_once();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0025_cr039_f27_order_no_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoredDocument",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("kind", models.TextField()),
                ("source_type", models.TextField()),
                ("source_id", models.UUIDField()),
                ("channel", models.TextField(blank=True, null=True)),
                ("storage_key", models.TextField()),
                ("storage_backend", models.TextField()),
                ("content_hash", models.TextField()),
                ("byte_length", models.IntegerField()),
                ("content_type", models.TextField()),
                ("stored_at", models.DateTimeField(auto_now_add=True)),
                ("stored_by_user_id", models.UUIDField(blank=True, null=True)),
                ("stored_by_process", models.TextField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "stored_documents"},
        ),
        migrations.AddIndex(
            model_name="storeddocument",
            index=models.Index(
                fields=["tenant", "source_type", "source_id"], name="ix_stored_docs_source"
            ),
        ),
        migrations.AddIndex(
            model_name="storeddocument",
            index=models.Index(fields=["tenant", "kind", "stored_at"], name="ix_stored_docs_kind"),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    kind__in=(
                        "bill",
                        "disconnect_notice",
                        "dunning_letter",
                        "payment_receipt",
                        "failed_payment_notice",
                        "payment_plan_instalment_due",
                        "payment_plan_instalment_missed",
                        "payment_plan_voided",
                        "move_in_welcome",
                        "move_out_final_bill",
                        "plan_change_confirmation",
                        "payment_plan_agreement",
                        "exemption_certificate",
                        "remittance_receipt",
                        "account_document",
                        "import_source_file",
                    )
                ),
                name="ck_stored_documents_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    source_type__in=(
                        "invoice",
                        "outbound_message",
                        "payment",
                        "payment_plan",
                        "customer_account",
                        "import_batch",
                    )
                ),
                name="ck_stored_documents_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(channel__in=("pdf_print", "email", "sms"))
                | models.Q(channel__isnull=True),
                name="ck_stored_documents_channel",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(storage_backend__in=("s3", "filesystem")),
                name="ck_stored_documents_backend",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(byte_length__gt=0), name="ck_stored_documents_length"
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(stored_by_user_id__isnull=False)
                | (models.Q(stored_by_process__isnull=False) & ~models.Q(stored_by_process="")),
                name="ck_stored_documents_actor",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.UniqueConstraint(
                fields=("tenant", "storage_key"), name="uq_stored_documents_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(channel__isnull=False),
                fields=("tenant", "source_type", "source_id", "channel", "content_type"),
                name="uq_stored_documents_sent",
            ),
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(channel__isnull=True),
                fields=("tenant", "source_type", "source_id", "content_type"),
                name="uq_stored_documents_filed",
            ),
        ),
        # CLAUDE.md rule 1 — the policy lands WITH the table, never a migration
        # later. B2 §3's signed template via core.rls; no character of the
        # predicate is this lane's.
        PostgresOnlySQL(sql=POLICY_SQL, reverse_sql=REVERSE_POLICY_SQL),
        # Hard rule 4 / BR-NOT-027 / NFR-35 — write-once, at the database.
        PostgresOnlySQL(sql=WRITE_ONCE_SQL, reverse_sql=REVERSE_WRITE_ONCE_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 step 5d(a)/(e) · BR-NOT-027 · NFR-33/NFR-35 · 04-docs/03-contracts B2 §3 · 06-backend/apps/billing/migrations/0006_w3_bill_payload.py, the write-once precedent)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST on a live PostgreSQL cluster — with the trigger dropped an UPDATE of content_hash and a DELETE both SUCCEEDED; with it in place both raise the messages above. With the policy dropped a second tenant read the row; with it in place the read returns nothing. Verbatim transcripts in the lane report.
# exceptions: (1) POSTGRES ONLY for the policy and the trigger — sqlite is the developer database and has neither; the same two refusals are ALSO held in document_store.py and asserted on every vendor, and the database half carries requires_postgres rather than a bare skip. (2) The trigger refuses UNCONDITIONALLY, unlike billing/0006 which permits a status transition — a stored document has no lawful pre-frozen state. (3) It does not protect the BYTES; NFR-35's object lock does, and the deployment checklist is in apps/tenancy/document_storage.py.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
