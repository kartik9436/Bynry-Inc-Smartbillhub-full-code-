# ── Trace ──────────────────────────────────────────────
# Question: OQ-1164 — CLOSED 2026-08-30. Twenty of the forty-one template
#           classes had no ruled document kind and the dispatcher HELD every one
#           of them rather than guessing. PO ruling, verbatim, answering the
#           recommendation put to them in plain English: *"My recommendation is
#           to keep all of them. - OKY KEEP THEM"*.
# Rules:    BR-NOT-027 (a sent legal document is FROZEN as the document — PO
#           2026-08-30) · the in-app channel ruling (PO 2026-08-26) ·
#           NFR-33 / NFR-35 (the seven-year record and its object lock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (immutability) ·
#           hard-won law 3 (defaults fail closed) · law 7 (prove it RED first) ·
#           law 13 (a ruling on a list does not overturn a ruling on a channel)
# Tests:    06-backend/tests/test_oq1164_every_customer_document_freezes.py
# ───────────────────────────────────────────────────────
"""tenancy 0028 — nineteen more customer documents may be kept: 16 kinds → 33.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path
and this widens a CHECK constraint on a table that holds the seven-year legal
record. AI-authored 2026-08-30 under the PO ruling of 2026-08-09 (*"AI will do
it; we will review it later as human"*); row owed in
`12-governance/09-human-review-ledger.md`.

WHAT WAS TRUE BEFORE THIS, IN ONE SENTENCE A PERSON CAN ACT ON
────────────────────────────────────────────────────────────────────────────
When this product sent a customer their statement, a refund confirmation, an
account-closed letter or fifteen other kinds of message, the dispatcher REFUSED
to send it at all — because it had nowhere lawful to file the copy, and it would
not invent a filing category for a document that has to survive seven years.
Nineteen kinds of customer message could not go out. After this migration they
can, and every one of them is kept exactly as the customer read it.

⚠ NINETEEN CLASSES, SEVENTEEN KINDS — AND THAT IS NOT A MISCOUNT
────────────────────────────────────────────────────────────────────────────
`kind` names the DOCUMENT; `channel` is a separate column on the same row. The
twelve kinds this table shipped with already collapse 21 template classes that
way — `sms_disconnect` and `disconnect_notice_48_hour` are both
`disconnect_notice`; `email_past_due` and `sms_past_due` are both
`dunning_letter`. Two of the nineteen collapse identically:

  * the printed **statement** and the statement **email** are one document —
    A19 rule 1 legislates for both in one sentence (*"both the printed statement
    and the statement email must say nothing is due"*);
  * **bill-ready** on email and bill-ready on SMS are one document.

So nineteen classes need seventeen values, and the list goes from **16 to 33**.
Splitting either pair would encode the CHANNEL into the KIND and leave a
regulator asking for "the statement" having to know to ask for it twice. The
ruling, both figures and this reasoning are in
`12-governance/02-decision-log.md` (2026-08-30).

⚠ THE TWENTIETH CLASS IS NOT HERE, DELIBERATELY
────────────────────────────────────────────────────────────────────────────
`staff_bulk_summary` — the in-app summary a clerk sees after a bulk action — is
the twentieth unmapped class and it stays out. The same PO ruled the in-app
channel out of the freeze on 2026-08-26 (*"we dont have to worry about in-app
message those are mostly FYI ; hence we dont have worry about them"*), and **a
ruling on a LIST does not overturn a ruling on a CHANNEL**. `in_app` is likewise
absent from `ck_stored_documents_channel`, which this migration does not touch.

⚠ FOUR OF THE SEVENTEEN ARE WORDING AHEAD OF A FLOW (OQ-249)
────────────────────────────────────────────────────────────────────────────
`service_appointment`, `service_work_completed`, `service_outage_notice` and
`service_door_hanger` have catalogued wording and **no writer that queues them**
— the work-order flow is R5 scope. This ruling says only that when one of them
is sent it is kept, and **it does not authorise building that flow.** A kind on
this list was the whole of what honouring it required, so nothing else was
built. A later lane that finds it needs more than a kind stops there and raises
`NotImplementedError("OQ-249")`.

WHICH WAY THIS FAILS — the question a 🔒 path has to answer
────────────────────────────────────────────────────────────────────────────
**It fails CLOSED, and it fails closed in the only direction that exists.** This
migration WIDENS a whitelist: it can make a previously-refused `kind` writable
and it can never make a previously-writable one refused, so no row that this
table already holds can become invalid. Every value added is a literal in
`document_models.DOCUMENT_KINDS`, and `document_store.store` reads that same
tuple, so the Python door and the database door are the same list — a kind that
gets past one meets the other.

The constraint is the FLOOR, not the rule. What actually decides whether a
document is kept is `frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS`, and a
class absent from THAT still holds on `OQ-1164` even though the constraint would
now accept a value for it. Widening the floor did not widen the decision.

**RLS is untouched and stays FORCE-scoped.** No policy, trigger or grant is
altered here; `0026`'s `tenancy_stored_document_write_once` trigger still refuses
every UPDATE and every DELETE on this table, so nothing about this change lets an
existing frozen document be edited or removed. This migration only says which
NEW rows may be written.

WHY `RemoveConstraint` + `AddConstraint` AND NOT RAW SQL
────────────────────────────────────────────────────────────────────────────
`ck_stored_documents_kind` is a Django `CheckConstraint` declared on the model,
so the model state and the database must move together or `makemigrations`
reports the table as changed forever. That rules out the `PostgresOnlySQL` shape
`billing/0025` and `notifications/0017` use for their triggers: those add
PostgreSQL objects Django does not model, and are correctly invisible to the
SQLite suite. **This constraint is the opposite case — it must exist on SQLite
too**, because `config/settings/test.py` hardcodes in-memory SQLite and a
whitelist that silently vanishes on the database every developer actually runs is
not a whitelist (hard-won law 1, and `StoredDocumentImmutable`'s docstring makes
the same argument about the write-once guard).

⚠ **AND THAT IS WHY THE CONSTRAINT PATH WAS PROVED ON REAL POSTGRESQL (law 14).**
A refused `kind` raises `IntegrityError` on both vendors, but only PostgreSQL
aborts the surrounding transaction with it. Verified on live PostgreSQL 16 rather
than assumed — see the test file's transcript.

LOCK COST, MEASURED RATHER THAN GUESSED
────────────────────────────────────────────────────────────────────────────
`DROP CONSTRAINT` + `ADD CONSTRAINT` takes an ACCESS EXCLUSIVE lock and the ADD
performs a full validation scan of `stored_documents`. That is acceptable HERE
and the reason is a measurement, not a preference: **the table is empty or nearly
so on every deployment** — the document store shipped on 2026-08-30 and no
provider adapter exists for print, email or SMS, so nothing has ever been sent
and frozen. The same operation on `invoices` would need `NOT VALID` + `VALIDATE
CONSTRAINT`; it does not need it here, and a future lane widening this list on a
grown table should reach for that shape instead.

REVERSIBLE: yes, and it is a genuine reversal rather than a no-op — `reverse`
restores the sixteen-value list. ⚠ It will REFUSE to run if any row already
carries one of the seventeen new kinds, which is correct: rolling back would
otherwise leave rows the constraint forbids, and `0026`'s trigger means they
could not be deleted to make room.
"""

from django.db import migrations, models

#: The sixteen values `ck_stored_documents_kind` held before this migration —
#: `CR-049` step 5b's twelve plus `NFR-33`'s four stored artifacts. Written out
#: rather than imported so that `reverse` keeps working when
#: `document_models.DOCUMENT_KINDS` moves again (a migration is a historical
#: record and must not follow the model).
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
)

#: The seventeen `OQ-1164` adds, for the nineteen classes the PO ruled in.
#: Grouped as they were described to the PO in plain English.
KINDS_ADDED = (
    # "Your bill is ready" (email + SMS), the statement (print + email), the
    # corrected-bill notice and the bill insert.
    "statement",
    "bill_ready_notice",
    "corrected_bill_notice",
    "bill_insert",
    # Money the customer is told about in writing.
    "refund_confirmation",
    "credit_note_confirmation",
    "deposit_notice",
    "writeoff_notice",
    # Account lifecycle.
    "account_closed_letter",
    "autopay_confirmation",
    # Signed instruments. ⚠ `deposit_agreement` is the SIGNED CONTRACT and
    # `deposit_notice` above is the LETTER about a deposit — two documents, two
    # kinds, so a regulator can be told which one they were shown.
    "service_agreement",
    "deposit_agreement",
    "autopay_authorization",
    # Field service — wording ahead of a flow (OQ-249, R5). See the docstring.
    "service_appointment",
    "service_work_completed",
    "service_outage_notice",
    "service_door_hanger",
)

KINDS_AFTER = KINDS_BEFORE + KINDS_ADDED

# The arithmetic the PO's signature was given against, asserted at import time so
# a careless edit to either tuple fails the migration rather than the record.
assert len(KINDS_BEFORE) == 16, "the kind list held sixteen values before OQ-1164"
assert len(KINDS_ADDED) == 17, "nineteen ruled classes need seventeen kinds — see the docstring"
assert len(KINDS_AFTER) == len(set(KINDS_AFTER)) == 33, "the widened list is 33 distinct kinds"


def refuse_rollback_over_live_rows(apps, schema_editor):
    """Refuse to narrow the list while a row still uses one of the new kinds.

    ⚠ **THIS IS A REVERSE-ONLY GUARD AND IT IS NOT DECORATION.** `0026`'s
    write-once trigger refuses every DELETE on this table, so a rollback that
    left rows violating the restored constraint could not be cleaned up
    afterwards — the operator would have a table that cannot be repaired and
    cannot be emptied. Failing here, before the constraint moves, is the only
    outcome that leaves a recoverable database.

    It reads across every tenant deliberately: this asks whether the SCHEMA may
    move, which is not a per-tenant question, and a rollback blocked by another
    tenant's row is exactly the answer the operator needs.
    """
    stored_document = apps.get_model("tenancy", "StoredDocument")
    blocking = stored_document.objects.filter(kind__in=KINDS_ADDED).count()
    if blocking:
        raise RuntimeError(
            f"{blocking} frozen document(s) are filed under one of the seventeen kinds "
            "this rollback would remove from the allowed list, and migration 0026's "
            "write-once trigger means they can never be deleted to make room. Rolling "
            "back now would leave rows the database itself forbids and no way to repair "
            "them. Move those documents' kind values first — which, because a frozen "
            "document is never updated, means deciding what should happen to the "
            "documents themselves (BR-NOT-027, PO 2026-08-30)."
        )


class Migration(migrations.Migration):
    dependencies = [
        # `0027` renamed the storage-backend value and added `display_name`; the
        # constraint being replaced here was created in `0026`. Named explicitly
        # rather than assumed — the ordering IS the 🔒 path.
        ("tenancy", "0027_cr049_export_manifest"),
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
