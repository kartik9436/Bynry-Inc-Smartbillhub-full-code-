# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-017 (plan rows) · US-PAY-018 (plan notices) · US-PAY-015
#           (manual notice modals) · US-PAY-016 (returned mail)
#           Screens: S21 · S24 · S33 · S34 · S35
# Rules:    BR-CUS-043 (one live plan per account) · BR-CUS-044 (activation on
#           the customer's signature alone; ⚠ `defaulted` SUPERSEDED) ·
#           BR-PAY-016 (plan notices; ⚠ "2nd miss VOIDS" SUPERSEDED — PO
#           2026-08-11 "nodrop we chase for payments until write off") ·
#           BR-PAY-017 (the ladder + notice_history) · BR-PAY-018 (returned
#           mail → bad address → needs attention) · BR-PAY-021 (posting-date
#           on-time-ness) · B2 §2 (`payment_plans`, `payment_plan_installments`)
#           · Addendum r12 #7 (notice_history + collection state) · r12 #8
#           (delivery-return events) · r12 #15 (exact DDL = Eng-Lead-owned) ·
#           CLAUDE.md rule 2 (money NUMERIC(18,6) + CHAR(3))
# ───────────────────────────────────────────────────────
"""payments 0007 — the plan and collections tables (B2 §2 + r12 #7/#8/#9).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and `payment_plans`
carries what a customer in arrears is asked to pay). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

**`payment_plans` IS THE TABLE THE S24 WIZARD HAS BEEN REFUSING TO SAVE INTO.**
`apps/customers/payment_plan_service.send_agreement` raises
`PaymentPlanUnavailable` on every call today because payments published no
service and this table did not exist — the wizard's arithmetic is live, tested
and frozen as GT-47, and its persistence was honestly absent. This migration and
`apps/payments/plans.py` close that (hard-won law 2: built is not wired).

**WHAT IS DELIBERATELY ABSENT: `payment_plans.missed_count`.** Addendum r12 #9
adds it and the PO ruled on 2026-08-11, verbatim *"nodrop we chase for payments
until write off"*. There is no drop-off, so there is nothing to count, and a
column sitting there would be an invitation to wire it back up — the same
disposition and the same words `apps/billing/migrations/0012` records for
budget billing.

**`accounts.bad_address` (r12 #8) IS NOT IN THIS MIGRATION** and could not be:
it is a column on a customers-owned table and B1 forbids the cross-module write.
The flag is derived from unresolved `delivery_return_events`; the difference
from B2 is REPORTED in the lane report, not quietly substituted.

RLS is 0008, not this migration: policy SQL is its own 🔒 review surface.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0008_rls_account_notes"),
        ("identity", "0004_rls_security_policies"),
        ("payments", "0006_w4_reversal_and_refunds"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentPlan",
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
                ("total_amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("down_payment", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("installment_count", models.IntegerField()),
                ("cadence", models.TextField(default="monthly")),
                ("status", models.TextField(default="proposed")),
                ("suspend_late_fees", models.BooleanField(default=False)),
                ("suspend_disconnect", models.BooleanField(default=True)),
                ("autopay_enabled", models.BooleanField(default=True)),
                ("proposed_on", models.DateField()),
                ("agreement_sent_on", models.DateField(blank=True, null=True)),
                ("signed_on", models.DateField(blank=True, null=True)),
                ("closed_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
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
                "db_table": "payment_plans",
            },
        ),
        migrations.CreateModel(
            name="NoticeHistory",
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
                ("notice_type", models.TextField()),
                ("tier", models.TextField(blank=True, null=True)),
                ("channel", models.TextField(blank=True, null=True)),
                ("outcome", models.TextField(default="sent")),
                ("skip_reason", models.TextField(blank=True, null=True)),
                ("outbound_message_id", models.UUIDField(blank=True, null=True)),
                ("detail", models.JSONField(default=dict)),
                ("occurred_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_column="actor_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
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
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        db_column="plan_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="payments.paymentplan",
                    ),
                ),
            ],
            options={
                "db_table": "notice_history",
            },
        ),
        migrations.CreateModel(
            name="PaymentPlanInstallment",
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
                ("seq", models.IntegerField()),
                ("due_date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("paid_posted_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "paid_payment",
                    models.ForeignKey(
                        blank=True,
                        db_column="paid_payment_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="payments.payment",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        db_column="plan_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="installments",
                        to="payments.paymentplan",
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
                "db_table": "payment_plan_installments",
            },
        ),
        migrations.CreateModel(
            name="AccountCollectionState",
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
                ("tier", models.TextField(blank=True, null=True)),
                ("tier_sent_on", models.DateField(blank=True, null=True)),
                ("last_notice_on", models.DateField(blank=True, null=True)),
                ("next_step_due", models.DateField(blank=True, null=True)),
                ("paused_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
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
                "db_table": "account_collection_state",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "account"), name="uq_collection_state_per_account"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="DeliveryReturnEvent",
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
                ("outbound_message_id", models.UUIDField(blank=True, null=True)),
                ("source_type", models.TextField(default="invoice")),
                ("source_id", models.UUIDField(blank=True, null=True)),
                ("returned_on", models.DateField()),
                ("reason", models.TextField(blank=True, null=True)),
                ("resolved_on", models.DateField(blank=True, null=True)),
                ("resolution", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "marked_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="marked_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="delivery_returns_marked",
                        to="identity.user",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="resolved_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="delivery_returns_resolved",
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
                "db_table": "delivery_return_events",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "resolved_on"], name="ix_returns_account"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("outbound_message_id__isnull", False)),
                        fields=("tenant", "outbound_message_id"),
                        name="uq_return_per_delivery",
                    )
                ],
            },
        ),
        migrations.AddIndex(
            model_name="paymentplan",
            index=models.Index(fields=["tenant", "account", "status"], name="ix_plans_account"),
        ),
        migrations.AddConstraint(
            model_name="paymentplan",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ("proposed", "agreement_sent", "active"))),
                fields=("tenant", "account"),
                name="uq_one_live_plan_per_account",
            ),
        ),
        migrations.AddIndex(
            model_name="noticehistory",
            index=models.Index(
                fields=["tenant", "account", "occurred_on"], name="ix_notice_hist_acct"
            ),
        ),
        migrations.AddIndex(
            model_name="noticehistory",
            index=models.Index(
                fields=["tenant", "notice_type", "tier"], name="ix_notice_hist_tier"
            ),
        ),
        migrations.AddIndex(
            model_name="paymentplaninstallment",
            index=models.Index(fields=["tenant", "plan", "due_date"], name="ix_plan_inst_due"),
        ),
        migrations.AddConstraint(
            model_name="paymentplaninstallment",
            constraint=models.UniqueConstraint(
                fields=("tenant", "plan", "seq"), name="uq_plan_installment"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-017@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — DDL only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: APPLIED TO POSTGRES, not only to the SQLite test tier (DEF-064) — see
#         the lane report for the verbatim `migrate` output
# exceptions: (1) NO `missed_count` (r12 #9) — superseded by the PO's ruling of
#         2026-08-11. (2) NO `accounts.bad_address` (r12 #8) — customers-owned;
#         the flag is derived from unresolved delivery-return rows. Both
#         REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
