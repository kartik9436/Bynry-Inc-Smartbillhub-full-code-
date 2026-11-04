"""ledger 0022 — `CR-197-BRC10`: a revenue account per customer class, and a
refund account role.

TWO THINGS, both additive, both from the PO's GL mapping rulings of 2026-10-29:

1. **`ledger_service_class_revenue_accounts`** (BR-LED-801) — service × part
   (usage / base) × customer class → account. A NEW table, ENABLE + FORCE row
   level security under the signed B2 §3 template (`db/rls_ledger_class_revenue.sql`).
   It starts EMPTY on every database, so no orphan sweep is owed before its
   foreign keys: there are no rows to sweep.
2. **`refunds_payable` joins the designation CHECK** (BR-LED-803). The set only
   GROWS, so every existing row already satisfies the new constraint; no row is
   read, written or deleted. Nothing is seeded: no account carries the role until
   a tenant gives it one, and until then a refund posts exactly as it did.

🔒 Migration ordering is a sensitive path: both dependencies are named. `0021`
is CR-196-BRC10's (the latest ledger migration when this was written).

ROLLBACK: drops the table (its override rows go with it — every bill already
issued keeps its stamped account, hard rule 4) and narrows the CHECK back. The
narrowing FAILS if an account still carries `refunds_payable`; clear it on the
chart first. That refusal is the database protecting a pointer someone chose.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — row in `12-governance/09-human-review-ledger.md`.
"""

from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_ledger_class_revenue.sql"
TABLE = "ledger_service_class_revenue_accounts"

#: Spelled out rather than imported, for the reason `ledger/0016` gives: a
#: migration describes the database as it was when it was written.
DESIGNATIONS_AFTER = (
    "accounts_receivable",
    "deposit_liability",
    "opening_clearing",
    "write_off",
    "minimum_bill_adjustment",
    "customer_credit_balance",
    "cash",
    "undeposited_funds",
    "unbilled_ar",
    "bank_fees",
    "deposit_interest_expense",
    "budget_variance",
    "discount_contra_revenue",
    "accrued_expenses",
    "depreciation_expense",
    "accumulated_depreciation",
    "allowance_doubtful_accounts",
    "cash_over_short",
    "refunds_payable",
)
DESIGNATIONS_BEFORE = DESIGNATIONS_AFTER[:-1]


def _check(designations):
    return models.CheckConstraint(
        condition=models.Q(
            ("designation__isnull", True),
            ("designation__in", designations),
            _connector="OR",
        ),
        name="ck_ledger_accounts_designation",
    )


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0021_cr196_account_seed_key_and_code_history"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceClassRevenueAccount",
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
                ("service_code", models.TextField()),
                ("part", models.TextField()),
                ("customer_class", models.TextField()),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ledger_account",
                    models.ForeignKey(
                        db_column="ledger_account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="ledger.ledgeraccount",
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
            options={"db_table": TABLE},
        ),
        migrations.AddConstraint(
            model_name="serviceclassrevenueaccount",
            constraint=models.CheckConstraint(
                condition=models.Q(("part__in", ("usage", "base"))),
                name="ck_ledger_class_revenue_part",
            ),
        ),
        migrations.AddConstraint(
            model_name="serviceclassrevenueaccount",
            constraint=models.CheckConstraint(
                condition=models.Q(("customer_class", ""), _negated=True),
                name="ck_ledger_class_revenue_class",
            ),
        ),
        migrations.AddConstraint(
            model_name="serviceclassrevenueaccount",
            constraint=models.UniqueConstraint(
                fields=("tenant", "service_code", "part", "customer_class"),
                name="uq_ledger_class_revenue",
            ),
        ),
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RemoveConstraint(
            model_name="ledgeraccount",
            name="ck_ledger_accounts_designation",
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=_check(DESIGNATIONS_AFTER),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-197-BRC10 (12-governance/change-requests/CR-197-BRC10-gl-mapping-one-list.md) · decision log 2026-10-29 (four GL mapping entries) · BR-LED-801 · BR-LED-803 · B2 §3 RLS template
# generated: 2026-10-29 by the CR-197-BRC10 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row)
# gates: makemigrations --check clean after this file; tests/test_cr197_gl_mapping_list.py
# exceptions: no seed row and no back-fill — both halves start empty by design
# status: HUMAN-REVIEW-PENDING · VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
