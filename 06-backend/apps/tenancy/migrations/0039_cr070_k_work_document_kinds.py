"""tenancy 0039 — three Work document kinds, and the source type they hang off.

`CR-070` wave K · `K1` · `US-WRK-048` · `BR-WRK-047`.

WHY THIS MIGRATION IS IN **TENANCY** AND NOT IN **WORK**
────────────────────────────────────────────────────────────────────────────
`stored_documents` is tenancy's table and `ck_stored_documents_kind` is a Django
`CheckConstraint` declared on `tenancy.StoredDocument`. Django resolves a
migration's `model_name` inside its OWN app, so an `AddConstraint` written into
`apps/work/migrations` naming `storeddocument` raises before it can run — the
correction `metering/0049` had to make for wave `P` and `metering/0050` for wave
`G`, twice in one change. Written here so it does not have to be made a third
time.

TWO CONSTRAINTS MOVE, NOT ONE
────────────────────────────────────────────────────────────────────────────
The execution plan's `K1` row names only the kind list, and that is one half of
the answer. A stored document carries a `kind` AND a `source_type`, both under
CHECK constraints, and a work-order photograph needs a new value in each: the
kind says *what this file is* and the source type says *what it belongs to*.
Widening only the kinds would let the row be written with `source_type =
'customer_account'`, which is the wrong answer to *which visit was this*, or
refuse it outright — so both lists move together, in one migration, because a
half-widened whitelist is a table that cannot store the thing it was widened
for.

  * `ck_stored_documents_kind`   — 33 → 36
  * `ck_stored_documents_source` —  6 →  7

WHY THE LISTS ARE WRITTEN OUT AND NOT IMPORTED
────────────────────────────────────────────────────────────────────────────
`0028` argues this and it holds here: a migration is a HISTORICAL RECORD and
must not follow the model. Importing `document_models.DOCUMENT_KINDS` would make
`reverse` restore whatever the list happens to be on the day somebody rolls
back, which is not a reversal of THIS migration.

WHY `RemoveConstraint` + `AddConstraint` AND NOT `PostgresOnlySQL`
────────────────────────────────────────────────────────────────────────────
Both constraints are declared on the model, so the model state and the database
must move together or `makemigrations` reports the table as changed forever.
⚠ **AND THEY MUST EXIST ON SQLITE TOO** — `config/settings/test.py` hardcodes
in-memory SQLite (hard-won law 14), and a whitelist that silently vanishes on
the database every lane actually runs is not a whitelist (law 1). That is the
opposite case from a trigger, which is correctly PostgreSQL-only.

LOCK COST
────────────────────────────────────────────────────────────────────────────
`DROP CONSTRAINT` + `ADD CONSTRAINT` takes an ACCESS EXCLUSIVE lock and the ADD
validates the whole table. `0028` measured this as acceptable because
`stored_documents` is empty or nearly so on every deployment — no provider
adapter exists for print, email or SMS — and that is still true today. A lane
widening this list once the table has grown should reach for `NOT VALID` +
`VALIDATE CONSTRAINT` instead.

REVERSIBLE, AND THE REVERSAL REFUSES RATHER THAN ORPHANS
────────────────────────────────────────────────────────────────────────────
`reverse` restores the 33 and the 6. It REFUSES to run if any row already
carries one of the new values, which is correct and not merely cautious:
`0026`'s `tenancy_stored_document_write_once` trigger refuses every UPDATE and
every DELETE on this table, so a row the restored constraint forbids could not
be edited or removed to make room. The database would be left holding rows its
own CHECK rejects, with no lawful way out.

NOTHING HERE SAYS HOW LONG A WORK DOCUMENT IS KEPT
────────────────────────────────────────────────────────────────────────────
Twelve months, then an export before deletion (`BR-WRK-048`, PO 2026-09-04). The
regime lives in `apps/work/work_documents.py` and nothing prunes yet, because
the export does not exist. This migration only says which rows may be WRITTEN.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored under the PO ruling of 2026-08-09; the deferred
human review is its row in `12-governance/09-human-review-ledger.md`
(`DEF-GOV-8547`).
"""

from django.db import migrations, models

#: The 33 values `ck_stored_documents_kind` held before this migration — the 16
#: of `0026`/`CR-049` plus `0028`'s 17 (`OQ-1164`).
KINDS_BEFORE = (
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
    "statement",
    "bill_ready_notice",
    "corrected_bill_notice",
    "bill_insert",
    "refund_confirmation",
    "credit_note_confirmation",
    "deposit_notice",
    "writeoff_notice",
    "account_closed_letter",
    "autopay_confirmation",
    "service_agreement",
    "deposit_agreement",
    "autopay_authorization",
    "service_appointment",
    "service_work_completed",
    "service_outage_notice",
    "service_door_hanger",
)

#: ⚠ The three are APPENDED and nothing is renumbered or reordered — the same
#: discipline `CR-063` applied to the eleventh utility service. A CHECK
#: constraint is order-independent, but the model tuple beside it is read by
#: people, and a list that reshuffles on every addition stops being diffable.
NEW_KINDS = (
    "work_order_photo",
    "work_order_signature",
    "work_order_report",
)

KINDS_AFTER = KINDS_BEFORE + NEW_KINDS

SOURCES_BEFORE = (
    "invoice",
    "outbound_message",
    "payment",
    "payment_plan",
    "customer_account",
    "import_batch",
)

SOURCES_AFTER = SOURCES_BEFORE + ("work_order",)


def refuse_rollback_over_live_rows(apps, schema_editor):
    """Refuse to roll back while any row carries one of the new values.

    Runs as the REVERSE half of a no-op `RunPython`, so it fires on the way
    DOWN and never on the way up. `0028` established the shape and the reason
    is the write-once trigger: a row the restored constraint forbids cannot be
    updated or deleted to make room, so the rollback would strand it.
    """
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(kind__in=NEW_KINDS).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0039: {stuck} stored_documents row(s) already "
            f"carry one of {', '.join(NEW_KINDS)}. Restoring the 33-value constraint would "
            "leave rows the CHECK forbids, and tenancy/0026's write-once trigger means they "
            "could be neither edited nor deleted to make room. Remove the work-order "
            "evidence first, or stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        # `0038` is the latest tenancy migration at the time of writing (CR-068
        # wave D's published-content RLS). Named explicitly rather than inferred
        # — migration ORDERING is a CLAUDE.md 🔒 path.
        ("tenancy", "0038_rls_cr068_d_published_content"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_kind",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER),
                name="ck_stored_documents_kind",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_source",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(source_type__in=SOURCES_AFTER),
                name="ck_stored_documents_source",
            ),
        ),
        # ⚠ DEF-TEN-9655 (2026-10-04, lane CREWS-2): the refusal is the LAST
        # operation, so it is the FIRST to run on the way back. Django reverses
        # operations; placed first it ran after the narrower CHECK had been
        # restored and the rollback failed on a raw IntegrityError instead of
        # the counted sentence. Forward it is a no-op, so nothing forward moved.
        migrations.RunPython(
            migrations.RunPython.noop,
            refuse_rollback_over_live_rows,
        ),
    ]
