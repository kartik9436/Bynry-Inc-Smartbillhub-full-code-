# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15, *"payemnt should
#           show in payments, in ledge and in fiannce books"*.
# Story:    US-LED-001   Screens: capture step 5 · the finance books
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — isolation is 0028) · hard
#           rule 2 (money 4 dp in an 18,6 container + CHAR(3)) · hard rule 4
#           (financial immutability — the freeze trigger is 0028) · hard rule 6
#           (one source, one receipt: `uq_counter_receipts_source`)
# Tests:    06-backend/tests/test_cr094_counter_receipt_posts.py
# ───────────────────────────────────────────────────────
"""payments 0027 — `counter_receipts`, the table the counter takings land in.

HUMAN-OWNED (migration ordering, and this table holds money) ·
HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHY A TABLE RATHER THAN A NULLABLE `payments.account_id`
--------------------------------------------------------
Measured before it was decided, and written up in the decision log of
2026-09-15: `apps/payments` reads `account_id` in **161 places across 40
files**, 27 of them `select_related`/`values` clauses that would begin yielding
a `None` nobody has branched for. It is a REVIEWED cross-module FK under B2 §2
and widening it is a one-way door. A `Payment` in this product IS a payment by
an account; this is money handed over by somebody applying to BECOME one, and
the blueprint's surviving sentence (p079, *"no account — there is no account
yet"*) says the same thing from the other side.

THE ONE GUARD IN THIS FILE, AND IT IS THE DRAWING'S RULE
--------------------------------------------------------
`uq_counter_receipts_source` — one source, one receipt. p079: *"Collecting
twice is refused by name. The same receipt number again answers with what is
already recorded; a DIFFERENT one on a request that has already been collected
is refused and names the receipt it already holds."* The service answers the
first case and refuses the second; this constraint is what holds when two
requests race, which a counter with two terminals can do.

ISOLATION AND IMMUTABILITY ARE **0028**, deliberately in their own migration —
the same split `payment_tenders` uses (0021 table, 0022 policies), so a reader
looking for the 🔒 guarantees finds them in a file whose name says so.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0005_cr070_f_field_technician"),
        ("payments", "0026_cpb85_plan_offered_by"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="CounterReceipt",
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
                ("source_type", models.TextField(default="service_request")),
                ("source_id", models.UUIDField()),
                ("source_ref", models.TextField(blank=True, null=True)),
                ("receipt_no", models.TextField()),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("card_last4", models.TextField(blank=True, null=True)),
                ("card_brand", models.TextField(blank=True, null=True)),
                ("card_auth_code", models.TextField(blank=True, null=True)),
                ("cheque_no", models.TextField(blank=True, null=True)),
                ("drawer_bank", models.TextField(blank=True, null=True)),
                ("cheque_date", models.DateField(blank=True, null=True)),
                ("taken_at", models.DateTimeField()),
                ("collection_entry_id", models.UUIDField(blank=True, null=True)),
                ("state", models.TextField(default="held")),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                (
                    "earned_amount",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("revenue_postings", models.JSONField(blank=True, null=True)),
                ("release_entry_id", models.UUIDField(blank=True, null=True)),
                ("release_error", models.TextField(blank=True, null=True)),
                ("payment_id", models.UUIDField(blank=True, null=True)),
                ("attached_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "method",
                    models.ForeignKey(
                        blank=True,
                        db_column="method_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counter_receipts",
                        to="tenancy.paymentmethod",
                    ),
                ),
                (
                    "released_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="released_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "taken_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="taken_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
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
                "db_table": "counter_receipts",
                "indexes": [
                    models.Index(fields=["tenant", "-taken_at"], name="ix_counter_receipts_taken"),
                    models.Index(fields=["tenant", "state"], name="ix_counter_receipts_state"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "source_type", "source_id"),
                        name="uq_counter_receipts_source",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("amount__gte", 0)),
                        name="ck_counter_receipts_amount_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("state__in", ("held", "applied", "earned"))),
                        name="ck_counter_receipts_state",
                    ),
                ],
            },
        ),
    ]
