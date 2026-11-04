# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (the multi-property tender — task 49) · CR-059 CS-27
#           (a master pays its units' bills — task 51)
#           Screens: S21 · S22 · S33 · S35 (tasks 50 and 52 — ANOTHER LANE)
# Rules:    BR-PAY-1126 (one tender, N payments) · BR-PAY-1127 (the parts sum
#           EXACTLY or nothing commits) · BR-PAY-1128 (a duplicate-guard key
#           PER ACCOUNT) · BR-PAY-1129 (a master may pay a unit on its own
#           premises; the authority is recorded) · BR-PAY-1130 (the leftover is
#           the MASTER's credit, never a tenant's) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money 4 dp into an 18,6 container + CHAR(3)) ·
#           rule 4 (financial immutability) · rule 6 (idempotency)
# ───────────────────────────────────────────────────────
"""payments 0021 — `payment_tenders`, and the nullable link from `payments`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and this table is the
parent of money rows). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*);
row in 12-governance/09-human-review-ledger.md.

**TWO PIECES, AND CS-12 SPELLS BOTH OUT:** *"One new table plus RLS, and a
nullable tender link on `payments`. The payment row is otherwise untouched —
same immutability, same audit, same batch behaviour."*

  * `payment_tenders` — what was handed over: the amount, the tender, the
    reference, BOTH of BR-PAY-021's dates, and the scope that says whether this
    cheque was grouped by CUSTOMER (CS-12) or by PREMISES (CS-27).
  * `payments.tender_id` — **NULLABLE, and nothing backfills it.** Every payment
    taken before today was handed over on its own and says so by holding NULL.

**RLS AND THE WRITE-ONCE TRIGGER ARE 0022, NOT THIS MIGRATION** — policy SQL and
immutability triggers are their own 🔒 review surface, which is the split
0004/0005, 0007/0008, 0009/0010 and 0012/0013 all use. Until 0022 runs the new
table has NO tenant isolation; the two migrations ship in one commit and neither
is deployable alone.

⚠ **`payments.tender_id` NEEDS NO CHANGE TO HARD RULE 4's TRIGGER, AND THAT IS
WORTH SAYING RATHER THAN LEAVING TO BE NOTICED.** `payments_payment_immutable`
(0002, as narrowed by 0014) governs UPDATE and DELETE. This column is written in
the INSERT that creates the row and never afterwards — `services.record_payment`
takes it as an argument for exactly that reason — so the allow-list the PO
opened on 2026-09-02 (`confirmation`, `memo`, `method_id`, and nothing else)
does not move for it.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0039_def2847_mailing_address_line2_country"),
        ("payments", "0020_cr060_c21_webhook_events"),
        ("tenancy", "0036_def3422_drop_bell_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTender",
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
                ("scope", models.TextField(default="customer")),
                ("customer_id", models.UUIDField(blank=True, null=True)),
                ("premises_id", models.UUIDField(blank=True, null=True)),
                ("authority", models.TextField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("reference", models.TextField(blank=True, null=True)),
                ("posted_at", models.DateTimeField()),
                ("cleared_at", models.DateTimeField(blank=True, null=True)),
                ("submission_key", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "method",
                    models.ForeignKey(
                        blank=True,
                        db_column="method_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.paymentmethod",
                    ),
                ),
                (
                    "payer_account",
                    models.ForeignKey(
                        blank=True,
                        db_column="payer_account_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tenders_paid",
                        to="customers.account",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "payment_tenders",
            },
        ),
        migrations.AddField(
            model_name="payment",
            name="tender",
            field=models.ForeignKey(
                blank=True,
                db_column="tender_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="payments.paymenttender",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["tenant", "tender"], name="ix_payments_tender"),
        ),
        migrations.AddIndex(
            model_name="paymenttender",
            index=models.Index(fields=["tenant", "payer_account"], name="ix_tenders_payer"),
        ),
        migrations.AddIndex(
            model_name="paymenttender",
            index=models.Index(fields=["tenant", "customer_id"], name="ix_tenders_customer"),
        ),
        migrations.AddIndex(
            model_name="paymenttender",
            index=models.Index(fields=["tenant", "-posted_at"], name="ix_tenders_posted"),
        ),
        migrations.AddConstraint(
            model_name="paymenttender",
            constraint=models.UniqueConstraint(
                fields=("tenant", "submission_key"), name="uq_payment_tenders_submission"
            ),
        ),
        migrations.AddConstraint(
            model_name="paymenttender",
            constraint=models.CheckConstraint(
                condition=models.Q(("scope__in", ("customer", "premises"))), name="ck_tenders_scope"
            ),
        ),
        migrations.AddConstraint(
            model_name="paymenttender",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("authority__in", ("account_holder", "premises_owner_master")),
                    ("authority__isnull", True),
                    _connector="OR",
                ),
                name="ck_tenders_authority",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymenttender",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("scope", "customer"),
                        ("customer_id__isnull", False),
                        ("payer_account__isnull", True),
                    ),
                    models.Q(
                        ("scope", "premises"),
                        ("payer_account__isnull", False),
                        ("premises_id__isnull", False),
                        ("customer_id__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="ck_tenders_scope_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymenttender",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)), name="ck_tenders_amount_positive"
            ),
        ),
    ]
