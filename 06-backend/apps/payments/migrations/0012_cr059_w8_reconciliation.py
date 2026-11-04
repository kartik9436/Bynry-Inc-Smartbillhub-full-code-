# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 wave W8 — reconciliation. Task 43 (CS-14, the two statement
#           balances) · task 44 (CS-16, a resolution may hang off a LINE) ·
#           task 45 (CS-17, the match SET) · task 46 (CS-18, the difference-
#           reason lookup)
#           Screens: S8 (a new Reference-data card, no new screen ID) · S37 ·
#           S38 · S39 · S40 — all four screen halves are CR-059 task 48's
# Rules:    BR-PAY-019 (bank rec: every exception explained with a reason AND a
#           GL) · BR-PAY-004 (a reconciled batch LOCKS) · BR-PAY-035 ("Force
#           match anyway" permanently SUPERSEDED) · BR-TEN-030 (lookup identity
#           unique per tenant, case-insensitive) · BR-TEN-034 (deactivate,
#           never delete) · BR-TEN-036 (a seeded row is not deletable) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4dp written on a
#           NUMERIC(18,6) container + CHAR(3)) · rule 4 (immutability)
# Ruling:   OQ-161 CLOSED 2026-08-12, PO verbatim *"Build many-to-one
#           matching"* — $2,840.00 + $14,280.00 posted by the bank as ONE
#           credit of $17,120.00. CS-17 is EXECUTION of a signed ruling.
# ───────────────────────────────────────────────────────
"""payments 0012 — the four W8 reconciliation tables and columns.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and three of these four
carry money). HUMAN-REVIEW-PENDING — AI-authored 2026-09-01 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

**WHAT EACH PIECE IS FOR, IN ONE LINE EACH.**

  * `bank_statement_imports.opening_balance` / `.closing_balance` (CS-14) —
    NULLABLE, and **nothing backfills them**. A reconciliation is only PROVED
    when book + reconciling items = the bank's own closing figure, and today no
    closing balance is stored anywhere, so the two sides are compared batch by
    batch and never as totals. A statement imported before today has NULL in
    both and the period read says so rather than serving `0.00`.
  * `bank_rec_resolutions.batch` becomes NULLABLE and `.bank_line_id` arrives
    (CS-16) — a resolution could only hang off a BATCH, so a line that is
    genuinely not a deposit of ours could only be left alone. The check
    constraint makes "exactly one parent" structural rather than a convention.
  * `bank_rec_match_sets` + `bank_rec_match_members` (CS-17) — many lines to one
    batch and one to many, which is the PO's own 2026-08-12 ruling and unbuilt
    code until today.
  * `bank_rec_difference_reasons` (CS-18) — the reason on a resolution was free
    text, so nobody could report on cause.

**WHY `bank_lines.deposit_batch_id` IS NOT DROPPED.** It is B2 §2's own column,
it is WRITE-ONCE by the trigger in migration 0005, and every batch reconciled
since 2026-08-11 was tied through it. Dropping it to "replace the single link"
would rewrite settled financial history to make room for a new shape. The set is
the SECOND way to tie and the service refuses a member already tied the other
way — see `apps/payments/reconciliation.match_set`.

**RLS AND THE APPEND-ONLY TRIGGERS ARE 0013, NOT THIS MIGRATION** — policy SQL
and immutability triggers are their own 🔒 review surface, which is the split
0004/0005, 0007/0008 and 0009/0010 all use. Until 0013 runs, the three new
tables have NO tenant isolation; the two migrations ship in one commit and
neither is deployable alone.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_rls_security_policies"),
        # ⚠ **THIS READ `0010_rls_writeoffs_and_intents` AND HAD TO MOVE.** It was
        # generated against a tip where 0010 was the leaf; the CR-059 W11
        # write-off lane pushed `0011_cr059_cs25_write_off_states` while this one
        # was working, and a dependency on 0010 leaves TWO leaf nodes in the
        # payments graph — which is DEF-2872's symptom, not a test failure:
        # Django refuses every test in the process with "Conflicting migrations
        # detected", names neither lane, and looks like a broken tree. Re-derived
        # at push time (law 11's id clause — a migration number is an id too).
        ("payments", "0011_cr059_cs25_write_off_states"),
        ("tenancy", "0029_cr060_t2_organisation_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankRecDifferenceReason",
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
                ("default_gl_account_id", models.UUIDField(blank=True, null=True)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "bank_rec_difference_reasons",
            },
        ),
        migrations.CreateModel(
            name="BankRecMatchMember",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "bank_rec_match_members",
            },
        ),
        migrations.CreateModel(
            name="BankRecMatchSet",
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
                ("matched_total", models.DecimalField(decimal_places=6, max_digits=18)),
                ("matched_at", models.DateTimeField()),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "bank_rec_match_sets",
            },
        ),
        migrations.AddField(
            model_name="bankrecresolution",
            name="bank_line",
            field=models.ForeignKey(
                blank=True,
                db_column="bank_line_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="resolutions",
                to="payments.bankline",
            ),
        ),
        migrations.AddField(
            model_name="bankstatementimport",
            name="closing_balance",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="bankstatementimport",
            name="opening_balance",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AlterField(
            model_name="bankrecresolution",
            name="batch",
            field=models.ForeignKey(
                blank=True,
                db_column="batch_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="resolutions",
                to="payments.depositbatch",
            ),
        ),
        migrations.AddIndex(
            model_name="bankrecresolution",
            index=models.Index(fields=["tenant", "bank_line"], name="ix_bank_rec_resolutions_line"),
        ),
        migrations.AddConstraint(
            model_name="bankrecresolution",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("bank_line__isnull", True), ("batch__isnull", False)),
                    models.Q(("bank_line__isnull", False), ("batch__isnull", True)),
                    _connector="OR",
                ),
                name="ck_bank_rec_resolutions_one_parent",
            ),
        ),
        migrations.AddField(
            model_name="bankrecdifferencereason",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchmember",
            name="bank_line",
            field=models.ForeignKey(
                blank=True,
                db_column="bank_line_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="match_members",
                to="payments.bankline",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchmember",
            name="batch",
            field=models.ForeignKey(
                blank=True,
                db_column="batch_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="match_members",
                to="payments.depositbatch",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchmember",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchset",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                db_column="actor_user_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchset",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="bankrecmatchmember",
            name="match_set",
            field=models.ForeignKey(
                db_column="match_set_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="members",
                to="payments.bankrecmatchset",
            ),
        ),
        migrations.AddIndex(
            model_name="bankrecdifferencereason",
            index=models.Index(fields=["tenant", "active"], name="ix_bankrec_diff_reason_live"),
        ),
        migrations.AddConstraint(
            model_name="bankrecdifferencereason",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_bank_rec_diff_reasons_code_ci",
            ),
        ),
        migrations.AddIndex(
            model_name="bankrecmatchset",
            index=models.Index(fields=["tenant", "matched_at"], name="ix_bank_rec_match_sets_when"),
        ),
        migrations.AddIndex(
            model_name="bankrecmatchmember",
            index=models.Index(
                fields=["tenant", "match_set"], name="ix_bank_rec_match_members_set"
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecmatchmember",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("bank_line__isnull", False), ("batch__isnull", True)),
                    models.Q(("bank_line__isnull", True), ("batch__isnull", False)),
                    _connector="OR",
                ),
                name="ck_bank_rec_match_members_one_side",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecmatchmember",
            constraint=models.UniqueConstraint(
                condition=models.Q(("bank_line__isnull", False)),
                fields=("tenant", "bank_line"),
                name="uq_bank_rec_match_members_line",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankrecmatchmember",
            constraint=models.UniqueConstraint(
                condition=models.Q(("batch__isnull", False)),
                fields=("tenant", "batch"),
                name="uq_bank_rec_match_members_batch",
            ),
        ),
    ]
