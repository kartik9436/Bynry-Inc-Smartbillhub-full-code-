"""rating 0009 — the DISCOUNT object CR-013 part 3 describes and the product
could not express at all.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — migration ordering AND the RLS policies
applied here are CLAUDE.md sensitive paths, AI-authored under the PO ruling of
2026-08-09 ("AI will do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT WAS THERE BEFORE THIS MIGRATION: NOTHING. Verified three ways on
2026-08-19 — `\\dt *discount*` on the live database returned 0 rows, a grep for
a Discount model across every `models.py` in `apps/` returned no match, and r10
draws five discounts on Plans & Rates with no object behind them. So this is not
a column being added to something; it is the first storage the product has for a
reduction it has been drawing for months.

SIX TABLES, AND WHY IT IS SIX AND NOT ONE
------------------------------------------
  `discounts`                     the identity — code, bill-line name, owner,
                                  funding source, status
  `discount_versions`             the dated, approvable content — type, value,
                                  scope, caps, floor, precedence, eligibility,
                                  verification, budget, approval
  `plan_discount_rules`           AVAILABILITY on a plan. **No value column** —
                                  PO ruling 2026-08-19, *"no plan cannot
                                  override prices"*
  `discount_enrolments`           THE GRANT. Part 3: *"plan attachment makes a
                                  discount available, not granted"*
  `discount_enrolment_documents`  the proof, with `restricted` derived from the
                                  document KIND (income and medical proof are
                                  role-restricted — part 3)
  `discount_grants`               append-only subsidy actually given, stamped
                                  with the version that priced it

RLS IS CREATED IN THIS MIGRATION, NOT A LATER ONE
--------------------------------------------------
CLAUDE.md rule 1 asks that a migration which CREATES a tenant table create its
policy in the SAME migration, and `rating 0003_rls_w1_policies` is the standing
reminder of what happens otherwise: nine tables shipped unprotected because the
schema lane documented the policies and ended before writing them. `db/
rls_rating_discounts.sql` is applied below, Postgres-only, through the same
`PostgresOnlySQL` wrapper every other RLS migration in this app uses. On sqlite
(the test database) it is a no-op and isolation is proved by the G5 suite
against Postgres.

WHAT THIS MIGRATION DELIBERATELY DOES NOT DO, so each reads as a decision
-------------------------------------------------------------------------
  * **It backfills nothing and converts nothing.** There is no prior discount
    data anywhere in the product to convert, and there is no per-plan discount
    flag to migrate away from — `plan_charge_rules`' negative `amount_override`
    (BR-RAT-043, OQ-055's old answer) is a CHARGE rule and is left exactly as it
    is. Nothing in this migration changes what any existing bill would compute.
  * **It creates no FK from `discount_grants` to `invoices`.** Billing is
    another lane's territory this session and R6 is not yet wired into the bill
    run, so `invoice_id` is a plain uuid and the constraint lands with the
    wiring (B11 F-3's deferred-FK pattern, as `charges.gl_account_id` did).
  * **It adds no `discount_treatment` column to `taxes`.** r10's DIS-02 step 2
    draws a *"Taxes computed on the discounted amount"* checkbox, but CR-013
    part 4 makes that treatment statutory and PER TAX — some authorities levy on
    the pre-discount amount. The column belongs on `taxes` and is EP-RAT-13's;
    putting one flag on the discount would hard-code one authority's answer for
    every authority in the product.
  * **It creates no column for the five stored impact figures** (§A7.6 —
    eligible accounts, projected monthly/annual subsidy, average bill effect,
    revenue impact, computed at SUBMIT and stored so an approver sees what the
    submitter saw). That is EP-RAT-16's approval slice and is named here rather
    than half-built: `second_approval_required` and `second_approval_threshold`
    ARE stored, because the PO ruled the threshold on 2026-08-19 and a rule with
    a ruling behind it is not a placeholder.

MONEY COLUMNS ARE `NUMERIC(18,6)` WITH A `CHAR(3)` BESIDE THEM (hard rule 2) —
`value`, `cap_per_bill`, `cap_per_year`, `cap_lifetime`, `bill_floor_amount`,
`budget_cap`, `second_approval_threshold`, `lifetime_subsidy_amount` and
`amount`. A percent lives in the same `NUMERIC(18,6)` as money because AUTOPAY
is −0.5% and CR-013 says rates store to six decimals.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0011_cr010_account_subtype_parent"),
        ("identity", "0004_rls_security_policies"),
        ("rating", "0008_def277_base_charge_nullable"),
        ("tenancy", "0015_cr008_payment_method_gl"),
    ]

    operations = [
        migrations.CreateModel(
            name="Discount",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("programme_owner", models.TextField(blank=True, null=True)),
                ("funding_source", models.TextField(blank=True, null=True)),
                ("report_in_assistance_filing", models.BooleanField(default=False)),
                ("status", models.TextField(default="draft")),
                ("funding_exhausted_at", models.DateTimeField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "discounts",
            },
        ),
        migrations.CreateModel(
            name="DiscountEnrolment",
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
                ("enrolled_on", models.DateField()),
                ("ended_on", models.DateField(blank=True, null=True)),
                ("end_reason", models.TextField(blank=True, null=True)),
                ("verification_status", models.TextField(default="pending")),
                ("verified_on", models.DateField(blank=True, null=True)),
                ("recertification_due_on", models.DateField(blank=True, null=True)),
                (
                    "lifetime_subsidy_amount",
                    models.DecimalField(decimal_places=6, default=0, max_digits=18),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("is_sample", models.BooleanField(default=False)),
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
                    "discount",
                    models.ForeignKey(
                        db_column="discount_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discount",
                    ),
                ),
                (
                    "enrolled_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="enrolled_by_user_id",
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
                (
                    "verified_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="verified_by_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "discount_enrolments",
            },
        ),
        migrations.CreateModel(
            name="DiscountEnrolmentDocument",
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
                ("reference", models.TextField(blank=True, null=True)),
                ("received_on", models.DateField()),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("restricted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "enrolment",
                    models.ForeignKey(
                        db_column="enrolment_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discountenrolment",
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
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="uploaded_by_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "discount_enrolment_documents",
            },
        ),
        migrations.CreateModel(
            name="DiscountVersion",
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
                ("version_no", models.IntegerField(default=1)),
                ("status", models.TextField(default="draft")),
                ("discount_type", models.TextField()),
                ("value", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("applies_to", models.TextField(default="whole_bill")),
                ("applies_to_charge_codes", models.JSONField(blank=True, null=True)),
                (
                    "cap_per_bill",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "cap_per_year",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "cap_lifetime",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "bill_floor_amount",
                    models.DecimalField(decimal_places=6, default=0, max_digits=18),
                ),
                ("stacking_precedence", models.IntegerField(default=100)),
                ("stacks_with_others", models.BooleanField(default=True)),
                ("exclusivity_group", models.TextField(blank=True, null=True)),
                ("eligibility_rule", models.JSONField(blank=True, null=True)),
                ("eligibility_summary", models.TextField(blank=True, null=True)),
                ("enrolment_mode", models.TextField(default="apply_and_approve")),
                ("verification_method", models.TextField(default="one_time_proof")),
                ("proof_required", models.BooleanField(default=False)),
                ("accepted_proof_kinds", models.JSONField(blank=True, null=True)),
                ("proof_before_first_reduction", models.BooleanField(default=True)),
                ("recertification_months", models.IntegerField(blank=True, null=True)),
                ("recertification_notice_days", models.IntegerField(default=60)),
                ("recertification_grace_days", models.IntegerField(default=0)),
                ("lapse_behaviour", models.TextField(default="notify_then_drop")),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                (
                    "budget_cap",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("budget_period", models.TextField(default="annual")),
                ("exhaustion_behaviour", models.TextField(default="suspend")),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("second_approval_required", models.BooleanField(default=False)),
                (
                    "second_approval_threshold",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("second_approved_at", models.DateTimeField(blank=True, null=True)),
                ("self_approved", models.BooleanField(default=False)),
                ("rejection_reason", models.TextField(blank=True, null=True)),
                ("change_reason", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "applies_to_service",
                    models.ForeignKey(
                        blank=True,
                        db_column="applies_to_service_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="approved_by_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "discount",
                    models.ForeignKey(
                        db_column="discount_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discount",
                    ),
                ),
                (
                    "second_approved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="second_approved_by_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="submitted_by_user_id",
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
                "db_table": "discount_versions",
            },
        ),
        migrations.CreateModel(
            name="DiscountGrant",
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
                ("invoice_id", models.UUIDField(blank=True, null=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "discount",
                    models.ForeignKey(
                        db_column="discount_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discount",
                    ),
                ),
                (
                    "enrolment",
                    models.ForeignKey(
                        db_column="enrolment_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discountenrolment",
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
                    "discount_version",
                    models.ForeignKey(
                        db_column="discount_version_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discountversion",
                    ),
                ),
            ],
            options={
                "db_table": "discount_grants",
            },
        ),
        migrations.CreateModel(
            name="PlanDiscountRule",
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
                ("available_from", models.DateField(blank=True, null=True)),
                ("available_to", models.DateField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "discount",
                    models.ForeignKey(
                        db_column="discount_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.discount",
                    ),
                ),
                (
                    "rate_plan",
                    models.ForeignKey(
                        db_column="rate_plan_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rating.rateplan",
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
                "db_table": "plan_discount_rules",
            },
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_discounts_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status__in", ("draft", "active", "retired", "suspended_funding_exhausted"))
                ),
                name="ck_discounts_status",
            ),
        ),
        migrations.AddIndex(
            model_name="discountenrolment",
            index=models.Index(fields=["tenant", "account"], name="ix_discount_enrol_account"),
        ),
        migrations.AddIndex(
            model_name="discountenrolment",
            index=models.Index(fields=["tenant", "discount"], name="ix_discount_enrol_discount"),
        ),
        migrations.AddIndex(
            model_name="discountenrolment",
            index=models.Index(
                fields=["tenant", "recertification_due_on"], name="ix_discount_enrol_recert"
            ),
        ),
        migrations.AddConstraint(
            model_name="discountenrolment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("ended_on__isnull", True)),
                fields=("account", "discount"),
                name="uq_discount_enrolments_current",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountenrolment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "verification_status__in",
                        ("not_required", "pending", "verified", "expired", "rejected"),
                    )
                ),
                name="ck_discount_enrolments_verification_status",
            ),
        ),
        migrations.AddIndex(
            model_name="discountenrolmentdocument",
            index=models.Index(fields=["tenant", "enrolment"], name="ix_discount_docs_enrolment"),
        ),
        migrations.AddIndex(
            model_name="discountversion",
            index=models.Index(fields=["tenant", "discount"], name="ix_discount_versions_discount"),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.UniqueConstraint(
                fields=("discount", "version_no"), name="uq_discount_versions_discount_no"
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "draft")),
                fields=("discount",),
                name="uq_discount_versions_one_draft",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "status__in",
                        (
                            "draft",
                            "pending_approval",
                            "scheduled",
                            "active",
                            "superseded",
                            "rejected",
                        ),
                    )
                ),
                name="ck_discount_versions_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "discount_type__in",
                        (
                            "percentage",
                            "fixed_amount",
                            "rate_override",
                            "charge_waiver",
                            "usage_allowance",
                        ),
                    )
                ),
                name="ck_discount_versions_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "applies_to__in",
                        ("whole_bill", "one_service", "usage_only", "base_only", "named_codes"),
                    )
                ),
                name="ck_discount_versions_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("value__gte", 0)),
                name="ck_discount_versions_value_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("bill_floor_amount__gte", 0)),
                name="ck_discount_versions_floor_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="discountgrant",
            index=models.Index(fields=["tenant", "discount"], name="ix_discount_grants_discount"),
        ),
        migrations.AddIndex(
            model_name="discountgrant",
            index=models.Index(fields=["tenant", "enrolment"], name="ix_discount_grants_enrolment"),
        ),
        migrations.AddConstraint(
            model_name="discountgrant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("invoice_id__isnull", True)),
                fields=("enrolment", "discount_version", "period_start", "period_end"),
                name="uq_discount_grants_period_no_invoice",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountgrant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("invoice_id__isnull", False)),
                fields=("enrolment", "invoice_id"),
                name="uq_discount_grants_enrolment_invoice",
            ),
        ),
        migrations.AddConstraint(
            model_name="plandiscountrule",
            constraint=models.UniqueConstraint(
                fields=("rate_plan", "discount"), name="uq_plan_discount_rules_plan_discount"
            ),
        ),
        # ── RLS, in the SAME migration that creates the tables (hard rule 1) ──
        PostgresOnlySQL(
            sql=load_db_sql("rls_rating_discounts.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
