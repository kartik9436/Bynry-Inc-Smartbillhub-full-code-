# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-002 (payment purpose — the plan-down LINKAGE column B2 never
#           anchored) · US-PAY-012 (write-offs — `write_offs`) · US-PAY-024
#           (autopay capture intents — `autopay_capture_intents`)
#           Screens: S22 · S32 · S33 · S34 · S35
# Rules:    BR-PAY-012 (every payment carries a purpose; plan-down links to its
#           plan) · BR-PAY-015 (autopay v1 = capture INTENT; no charging path
#           before rails) · BR-PAY-020 (write-offs INITIATED in payments,
#           APPROVED in finance) · BR-PAY-037 (one user may initiate AND approve
#           in v1 — both acts recorded distinctly) · B2 Addendum r12 #6
#           (autopay_capture_intents) · r12 #11 (write_offs) · r12 #17 ("exact
#           DDL = Eng-Lead 🔒") · CLAUDE.md rule 1 (tenant scoping) · rule 2
#           (money NUMERIC(18,6) + CHAR(3)) · rule 4 (financial immutability)
# ───────────────────────────────────────────────────────
"""payments 0009 — the purpose link, `write_offs` and `autopay_capture_intents`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and two of these three
tables carry money). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*); row
in 12-governance/09-human-review-ledger.md.

**`payments.plan_id` CLOSES FIELD-MAP P-12.** BR-PAY-012 has been CONFIRMED
since 2026-08-08 — *"plan-down links to its plan"* — and the field map records
that the column it needs *"needs its r12/Eng-Lead anchor named"*. Until today a
plan down payment could not be recorded at all: `services.record_payment`
refused `purpose=plan_down` by name because the linkage did not exist. It is a
REAL FK, not a deferred uuid, because `payment_plans` is this module's own table
(0007) and there is no boundary to defer across.

**WHAT IS DELIBERATELY ABSENT FROM `autopay_capture_intents`: any status that
could express a charge.** r12 #6 stores *"status awaiting-rails v1"* and
BR-PAY-015 puts real charging behind W7. A `captured` or `failed` value would
be a value some path is eventually written against; the FULFILLED state is
COMPUTED from invoice settlement (BR-PAY-034 / field-map P-7) and stored
nowhere.

**WHAT IS DELIBERATELY ABSENT FROM `write_offs`: the agency and deposit-flag
columns.** The prototype's *"Send to collections agency instead"* and *"Flag
these accounts so future service requires a deposit"* checkboxes have NO
ratified rule (field-map P-4/P-5) and US-PAY-012 §1 excludes them from v1 by
name. A column here would be an invitation to wire them up.

RLS and the write-off freeze are 0010, not this migration: policy SQL and
immutability triggers are their own 🔒 review surface, the same split 0007/0008
and 0004/0005 use.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0008_rls_account_notes"),
        ("identity", "0004_rls_security_policies"),
        ("payments", "0008_rls_plans_and_collections"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutopayCaptureIntent",
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
                ("invoice_id", models.UUIDField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("scheduled_on", models.DateField()),
                ("status", models.TextField(default="awaiting_rails")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "autopay_capture_intents",
            },
        ),
        migrations.CreateModel(
            name="WriteOff",
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
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("reason", models.TextField()),
                ("note", models.TextField()),
                ("status", models.TextField(default="requested")),
                ("requested_on", models.DateField()),
                ("approved_on", models.DateField(blank=True, null=True)),
                ("gl_account_id", models.UUIDField(blank=True, null=True)),
                ("journal_entry_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "write_offs",
            },
        ),
        migrations.AddField(
            model_name="payment",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                db_column="plan_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="payments.paymentplan",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("plan__isnull", True), ("purpose", "plan_down"), _connector="OR"
                ),
                name="ck_payments_plan_only_on_plan_down",
            ),
        ),
        migrations.AddField(
            model_name="autopaycaptureintent",
            name="account",
            field=models.ForeignKey(
                db_column="account_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="customers.account",
            ),
        ),
        migrations.AddField(
            model_name="autopaycaptureintent",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="account",
            field=models.ForeignKey(
                db_column="account_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="customers.account",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                db_column="approved_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="write_offs_approved",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                db_column="requested_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="write_offs_requested",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="autopaycaptureintent",
            index=models.Index(
                fields=["tenant", "status", "scheduled_on"], name="ix_autopay_intent_open"
            ),
        ),
        migrations.AddIndex(
            model_name="autopaycaptureintent",
            index=models.Index(fields=["tenant", "account"], name="ix_autopay_intent_acct"),
        ),
        migrations.AddConstraint(
            model_name="autopaycaptureintent",
            constraint=models.UniqueConstraint(
                fields=("tenant", "invoice_id"), name="uq_autopay_intent_per_invoice"
            ),
        ),
        migrations.AddConstraint(
            model_name="autopaycaptureintent",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("awaiting_rails",))),
                name="ck_autopay_intent_status",
            ),
        ),
        migrations.AddIndex(
            model_name="writeoff",
            index=models.Index(fields=["tenant", "account"], name="ix_write_offs_account"),
        ),
        migrations.AddIndex(
            model_name="writeoff",
            index=models.Index(
                fields=["tenant", "status", "-requested_on"], name="ix_write_offs_status"
            ),
        ),
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("requested", "approved"))),
                name="ck_write_offs_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "reason__in",
                        (
                            "uncollectible_120_days",
                            "customer_bankruptcy",
                            "deceased_no_estate",
                            "below_write_off_threshold",
                        ),
                    )
                ),
                name="ck_write_offs_reason",
            ),
        ),
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)), name="ck_write_offs_amount_positive"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-002@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md §2 + Addendum r12 #2/#6/#11/#17 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md US-PAY-002 · EP-PAY-03-exceptions.md US-PAY-012 · EP-PAY-07-autopay-receipts.md US-PAY-024 · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md P-4/P-5/P-7/P-12)
# generated: 2026-08-15 by story-coder (payments visible-half lane — purpose, credit, outstandings, ladder, summary, write-offs, autopay)
# checklist: A✔ B✔ C✔ D=deferred(a migration serves no route) E=deferred(a migration draws no screen) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check✔ (no drift) · migrate on SQLite✔ · pytest tests/test_us_pay_002_purpose.py tests/test_us_pay_012_write_offs.py tests/test_us_pay_024_autopay_intents.py✔ · the `ck_payments_plan_only_on_plan_down` constraint was proved RED before it was trusted (see the lane report)
# exceptions: (1) `payments.plan_id` is a REAL FK where `deposit_batch_id` and
#         `journal_entry_id` are deferred uuids — `payment_plans` is this
#         module's own table, so the B11 F-3 convention does not apply
#         (2) `autopay_capture_intents.invoice_id` IS a deferred uuid: `invoices`
#         is billing's, and the reviewed cross-module FK set (B2 §2) contains
#         payments→invoices only through `allocations`. Nothing here widens it
#         (3) NO `write_offs.agency_referred` and NO `write_offs.deposit_required`
#         — field-map P-4/P-5, excluded from v1 by US-PAY-012 §1
#         (4) `write_offs.gl_account_id` is NULLABLE and stays NULL until
#         approval: nothing money-bearing exists before a human approves
#         (US-PAY-012 TC-1), and a GL stamped at request time would say
#         otherwise on every pending row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
