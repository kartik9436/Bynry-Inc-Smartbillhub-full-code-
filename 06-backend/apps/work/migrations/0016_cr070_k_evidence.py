"""work 0016 — `work_order_attachments` and `work_order_signatures`.

`CR-070` wave K · `K1` · `US-WRK-048` · `US-WRK-036` · `US-WRK-049`.

WHAT THIS CREATES
────────────────────────────────────────────────────────────────────────────
Two tables and one append-only trigger apiece. `work_order_attachments` is one
row per file the phone sent — which job, which checklist row, which handset,
when the shutter closed, and the idempotency key that makes a re-sync a no-op.
`work_order_signatures` is one row per job saying what the customer did:
signed, or refused with a reason and a photograph of the door hanger.

⚠ **BOTH TABLES ARE APPEND-ONLY AND THE TRIGGER IS WHY.** Neither is a
financial row, so CLAUDE.md hard rule 4 does not reach them — they are
append-only because they are EVIDENCE, and the worth of a photograph of a meter
dial is that it is what the camera saw at 16:02 on 15 March. A model docstring
saying so would be a comment claiming a guarantee (hard-won law 1); the trigger
is the guarantee. The correction path is a NEW row: another photograph, with a
later `taken_at`, and the checklist row pointing at it. The mistake stays in the
record, which is the point.

⚠ **`attachment_ref` IS DROPPED FROM `work_orders`** (`connections.py`). It was
a lone `TextField` that predated any of this, was written by nobody and read by
nobody, and leaving it beside a real attachments table is an invitation for the
next lane to write a filename into it and believe they have attached something.
Its removal is a **metering** `AlterField`/`RemoveField` and therefore NOT in
this file — see the note at the foot of this docstring.

WHY THE TRIGGER IS `PostgresOnlySQL` AND THE CHECK CONSTRAINTS ARE NOT
────────────────────────────────────────────────────────────────────────────
The two are opposite cases and the distinction has cost this repo real time.
A TRIGGER is a PostgreSQL object Django does not model, so it is correctly
invisible to the SQLite suite (`billing/0025` and `notifications/0017` use the
same shape). The CHECK constraints are declared on the model, so they must
exist on SQLite too — `config/settings/test.py` hardcodes in-memory SQLite
(hard-won law 14), and a whitelist that vanishes on the database every lane
actually runs is not a whitelist.

⚠ **NO `%%` ANYWHERE IN THIS FILE, AND THAT IS DELIBERATE (`DEF-WRK-4027`).**
The SQL below runs through `PostgresOnlySQL`, which reaches psycopg with
`params=None` — so psycopg substitutes NOTHING and a `%%` written here would
arrive at PostgreSQL as a literal percent sign. That is exactly what stopped
every PostgreSQL migration on this branch at `work/0009` on 2026-09-05. The
convention documented in `integrations/0001_initial.py` (*double every `%`*) is
true only of `schema_editor.execute(sql)`, whose default `params=()` makes
psycopg substitute. Restated so it travels: **double a `%` only where psycopg
will substitute.** This file contains no `%` at all, so the question does not
arise — and the sentence is here because the neighbouring files look identical
and disagree.

WHY `reading_id` AND `task_id` ARE PLAIN UUIDS
────────────────────────────────────────────────────────────────────────────
The B11 F-3 deferred-FK convention `work_orders.rule_id` and wave H's own
`photo_attachment_id` already use. The obvious objection is that a foreign key
would guarantee the row exists — it would, and it would NOT guarantee the row
belongs to THIS ORDER, which is the mistake a phone actually makes when it syncs
nine jobs at once. `evidence._checklist_target()` checks all three (exists,
this tenant, this order) before writing, so converting these to foreign keys
later is an addition rather than a replacement.

⚠ **AND WAVE H's `photo_attachment_id` COLUMNS ARE DELIBERATELY LEFT AS UUIDS.**
`WorkOrderTask` and `WorkOrderReading` each carry one, with a docstring saying
*the FK is added by the migration that creates the table it points at* — this
one. It is not added, and the reason is a trade rather than an oversight: the
conversion is an `AlterField` on two model classes inside `apps/work/models.py`,
a 1,900-line file that three CR-070 lanes are editing right now, and law 11's
mechanism two turns any whole-file write there into a silent revert of somebody
else's work. The integrity the FK would buy is already bought by the
three-way check above, which is strictly stronger. **Owed and recorded**: a
later lane working in a quiet models.py should make it, and nothing depends on
it meanwhile.

TENANT SCOPING
────────────────────────────────────────────────────────────────────────────
Both tables carry `tenant_id` and both get RLS `ENABLE` + `FORCE` in
`work/0017`, which is the 🔒 file and carries its own review-ledger row (`K4`).
This migration creates the tables; it does not secure them, and the two are
split so the security file is small enough to read in one sitting.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models

import django.db.models.deletion

import core.dbfields
from core.migrationtools import PostgresOnlySQL

#: One trigger function, two tables. A shared function rather than two copies
#: because the sentence a developer sees when they try an UPDATE is the thing
#: that has to be right, and two copies drift.
APPEND_ONLY = """
CREATE OR REPLACE FUNCTION work_evidence_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION
    'work-order evidence is append-only: % on % is refused. A photograph or a '
    'signature is a record of what happened at a moment, so it is never edited '
    'and never deleted. To correct one, capture another - a new row with a '
    'later taken_at - and point the checklist row at it. The mistake stays in '
    'the record, which is the point.',
    TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER work_order_attachments_append_only
  BEFORE UPDATE OR DELETE ON work_order_attachments
  FOR EACH ROW EXECUTE FUNCTION work_evidence_append_only();

CREATE TRIGGER work_order_signatures_append_only
  BEFORE UPDATE OR DELETE ON work_order_signatures
  FOR EACH ROW EXECUTE FUNCTION work_evidence_append_only();
"""

APPEND_ONLY_REVERSE = """
DROP TRIGGER IF EXISTS work_order_signatures_append_only ON work_order_signatures;
DROP TRIGGER IF EXISTS work_order_attachments_append_only ON work_order_attachments;
DROP FUNCTION IF EXISTS work_evidence_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [
        # `0015` is wave J's RLS file — the latest in this app. Named explicitly
        # rather than inferred: migration ORDERING is a CLAUDE.md 🔒 path.
        ("work", "0015_rls_force_mobile"),
        # `stored_documents` must exist and must already accept the three Work
        # kinds and the `work_order` source, or the first row written through
        # `document_store.store()` is refused by a CHECK constraint.
        ("tenancy", "0039_cr070_k_work_document_kinds"),
        # `work_orders` is metering's table; `work_order_readings` and
        # `work_order_tasks` came with wave H's `0012` in THIS app, so only the
        # metering end needs naming here. ⚠ The SAME node wave H's `0012`
        # names, deliberately — depending on a LATER metering migration would
        # couple this file to whichever lane pushed last, and `work_orders`
        # itself is older than any of them.
        ("metering", "0050_cr070_g_dispatch"),
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderAttachment",
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
                ("taken_at", models.DateTimeField()),
                ("device", models.TextField(blank=True, default="")),
                ("reading_id", models.UUIDField(blank=True, null=True)),
                ("task_id", models.UUIDField(blank=True, null=True)),
                ("idempotency_key", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachment_rows",
                        to="metering.workorder",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenancy.storeddocument",
                    ),
                ),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="added_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
            ],
            options={"db_table": "work_order_attachments"},
        ),
        migrations.CreateModel(
            name="WorkOrderSignature",
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
                ("refused", models.BooleanField(default=False)),
                ("printed_name", models.TextField(blank=True, null=True)),
                ("decline_reason", models.TextField(blank=True, null=True)),
                ("signed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signature_rows",
                        to="metering.workorder",
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        blank=True,
                        db_column="image_document_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenancy.storeddocument",
                    ),
                ),
                (
                    "door_hanger",
                    models.ForeignKey(
                        blank=True,
                        db_column="door_hanger_attachment_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="work.workorderattachment",
                    ),
                ),
                (
                    "captured_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="captured_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
            ],
            options={"db_table": "work_order_signatures"},
        ),
        migrations.AddConstraint(
            model_name="workorderattachment",
            constraint=models.UniqueConstraint(
                fields=("tenant", "work_order", "idempotency_key"),
                name="uq_work_order_attachments_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderattachment",
            constraint=models.CheckConstraint(
                condition=models.Q(reading_id__isnull=True) | models.Q(task_id__isnull=True),
                name="ck_work_order_attachments_one_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderattachment",
            constraint=models.CheckConstraint(
                condition=models.Q(_negated=True, idempotency_key=""),
                name="ck_work_order_attachments_key_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderattachment",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=("work_order_photo", "work_order_signature")),
                name="ck_work_order_attachments_kind",
            ),
        ),
        migrations.AddIndex(
            model_name="workorderattachment",
            index=models.Index(
                fields=["tenant", "work_order", "taken_at"], name="ix_wo_attach_order_taken"
            ),
        ),
        migrations.AddConstraint(
            model_name="workordersignature",
            constraint=models.UniqueConstraint(
                fields=("tenant", "work_order"), name="uq_work_order_signatures_order"
            ),
        ),
        migrations.AddConstraint(
            model_name="workordersignature",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        refused=False,
                        printed_name__isnull=False,
                        image__isnull=False,
                        decline_reason__isnull=True,
                        door_hanger__isnull=True,
                    )
                    | models.Q(
                        refused=True,
                        printed_name__isnull=True,
                        image__isnull=True,
                        decline_reason__isnull=False,
                        door_hanger__isnull=False,
                    )
                ),
                name="ck_work_order_signatures_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="workordersignature",
            constraint=models.CheckConstraint(
                condition=models.Q(_negated=True, printed_name="")
                & models.Q(_negated=True, decline_reason=""),
                name="ck_work_order_signatures_not_blank",
            ),
        ),
        migrations.AddIndex(
            model_name="workordersignature",
            index=models.Index(fields=["tenant", "work_order"], name="ix_wo_signature_order"),
        ),
        PostgresOnlySQL(APPEND_ONLY, reverse_sql=APPEND_ONLY_REVERSE),
    ]
