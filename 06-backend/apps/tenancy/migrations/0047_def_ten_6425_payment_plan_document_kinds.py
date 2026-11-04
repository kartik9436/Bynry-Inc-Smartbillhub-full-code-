"""tenancy 0047 — **the three payment-plan document kinds are spelled the way
the model spells them again**, so PostgreSQL stops refusing them.
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-24 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`DEF-TEN-6425` · `DEF-TEN-6107` (the same drift, filed twice by two lanes).

WHAT WAS WRONG
────────────────────────────────────────────────────────────────────────────
`0045` writes its kind list out by hand — correctly, a migration is a
historical record and must not import the model — and its hand-written copy
spells three kinds without their `payment_` prefix:

    0045 wrote              the model, 0026, 0028 and 0039 all say
    plan_instalment_due     payment_plan_instalment_due
    plan_instalment_missed  payment_plan_instalment_missed
    plan_voided             payment_plan_voided

So `0045` did not only ADD `service_request_document`; it silently
**narrowed** the constraint. Since it ran, a payment-plan instalment-due
notice, a missed-instalment letter or a voided-plan notice could not be frozen
into the document store on PostgreSQL — the CHECK refuses the row. SQLite, where
the default suite runs, does not enforce it, so nothing went red.
`makemigrations` has offered this exact drop-and-recreate on every run since,
and `0046` stripped it out of its own change (correctly — it was not that CR's
edit) and cited a defect id that was never issued.

WHAT THIS DOES
────────────────────────────────────────────────────────────────────────────
Drops `ck_stored_documents_kind` and adds it back with the model's 37 kinds,
written out here for the same reason `0045` wrote them out. It is exactly the
migration `makemigrations` generates, with the list spelled literally.

THE THREE MISSPELLED VALUES LEAVE THE CONSTRAINT, AND THAT IS SAFE
────────────────────────────────────────────────────────────────────────────
Nothing in the codebase writes `plan_instalment_due`, `plan_instalment_missed`
or `plan_voided` as a kind — grepped on 2026-09-24; the only occurrence is
`0045` itself. So no row can carry them.

WHY THERE IS NO `RunPython` COUNT BEFORE EACH DIRECTION, UNLIKE `0039`–`0045`
────────────────────────────────────────────────────────────────────────────
Those migrations count rows through the ORM before rolling back. On
PostgreSQL `stored_documents` is `FORCE ROW LEVEL SECURITY` and a migration runs
with no `app.tenant_id`, so a non-superuser migration role counts **zero rows
whatever is there** — measured 2026-09-24 as the `smartbillhub` role
(`rolsuper = f`, `rolbypassrls = f`). That count cannot fail (law 7).
**The refusal that CAN fail is the database's own:** `ADD CONSTRAINT` validates
every row of the table and row security does not apply to it, so a row the new
list forbids aborts the migration inside its transaction, and nothing changes.
Reversing over a stored `payment_plan_*` notice is refused that way — proved on
PostgreSQL 16, quoted in the commit message.

LOCK COST: `0045`'s note holds. `DROP` + `ADD CONSTRAINT` takes an ACCESS
EXCLUSIVE lock and validates the table; a few hundred rows is instant.
"""

from django.db import migrations, models

KINDS = (
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
    "work_order_photo",
    "work_order_signature",
    "work_order_report",
    "service_request_document",
)


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0046_cr122_brc06_move_in_draft")]

    operations = [
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_kind",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS),
                name="ck_stored_documents_kind",
            ),
        ),
    ]
