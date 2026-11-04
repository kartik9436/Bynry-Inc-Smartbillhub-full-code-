# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 (enrolment + the level) · US-BIL-019 (the budget bill and
#           its settle-up) · US-BIL-020 (re-level + override)
#           Screens: S30 · S66/S69
# Rules:    BR-BIL-017 (budget billing; ⚠ its two-missed-payments DROP-OFF is
#           SUPERSEDED — PO 2026-08-11 "nodrop we chase for payments until write
#           off") · BR-BIL-021 (every parameter tenant config — the settings
#           half lives in tenancy S69 and is NOT duplicated here) · B2 Addendum
#           r10 #5 (`account_budget_status` columns) · r12 #14 D-5 (`status`
#           incl. off_budget) · r10 #15 (exact DDL = Eng-Lead-owned) ·
#           CLAUDE.md rule 2 (money NUMERIC(18,6) + CHAR(3))
# ───────────────────────────────────────────────────────
"""billing 0012 — budget billing's two tables (Addendum r10 #5).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and both tables hold
money). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

`account_budget_status` is r10 #5 column for column. `account_budget_events` is
NOT in r10 — it is an Eng-Lead DDL call under r10 #15, made because US-BIL-019
TC-6 requires that the variance balance *"derives from bill events
append-only"*, and a balance stored only as a number is a balance an UPDATE can
invent. The call is recorded in 12-governance/02-decision-log.md rather than
only here.

WHAT IS DELIBERATELY ABSENT: a `missed_count` column. B2 Addendum r12 #9 adds
one to `payment_plans` and BR-BIL-017 counted misses for budget billing too —
and the PO ruled on 2026-08-11, verbatim *"nodrop we chase for payments until
write off"*. There is no drop-off, so there is nothing to count. A column
sitting there would be an invitation to wire it back up.

RLS is 0013, not this migration: policy SQL is its own 🔒 review surface and
mixing DDL with policy in one file has meant, twice in this repo, that a table
shipped and its policy did not.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0011_bill_run_bill_date"),
        ("customers", "0001_initial"),
        ("identity", "0001_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountBudgetStatus",
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
                ("status", models.TextField(default="enrolled")),
                ("level", models.DecimalField(decimal_places=6, max_digits=18)),
                (
                    "level_override",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("level_override_reason", models.TextField(blank=True, null=True)),
                ("currency", models.CharField(max_length=3)),
                (
                    "variance_balance",
                    models.DecimalField(decimal_places=6, default=0, max_digits=18),
                ),
                ("last_leveled_at", models.DateField(blank=True, null=True)),
                ("settle_up_month", models.IntegerField(blank=True, null=True)),
                ("enrolled_on", models.DateField()),
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
            options={"db_table": "account_budget_status"},
        ),
        migrations.CreateModel(
            name="AccountBudgetEvent",
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
                ("event", models.TextField()),
                (
                    "level",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "actual",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("movement", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("balance_after", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("currency", models.CharField(max_length=3)),
                ("reason", models.TextField(blank=True, null=True)),
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
                    "budget_status",
                    models.ForeignKey(
                        db_column="account_budget_status_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="billing.accountbudgetstatus",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        db_column="invoice_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="billing.invoice",
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
            options={"db_table": "account_budget_events"},
        ),
        migrations.AddIndex(
            model_name="accountbudgetstatus",
            index=models.Index(fields=["tenant", "status"], name="ix_budget_status"),
        ),
        migrations.AddIndex(
            model_name="accountbudgetstatus",
            index=models.Index(fields=["tenant", "settle_up_month"], name="ix_budget_settle_month"),
        ),
        migrations.AddConstraint(
            model_name="accountbudgetstatus",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "enrolled")),
                fields=("tenant", "account"),
                name="uq_budget_one_live_per_account",
            ),
        ),
        migrations.AddIndex(
            model_name="accountbudgetevent",
            index=models.Index(
                fields=["tenant", "budget_status", "occurred_on"], name="ix_budget_ev_status"
            ),
        ),
        migrations.AddIndex(
            model_name="accountbudgetevent",
            index=models.Index(fields=["tenant", "account"], name="ix_budget_ev_account"),
        ),
        migrations.AddConstraint(
            model_name="accountbudgetevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("invoice__isnull", False)),
                fields=("tenant", "invoice", "event"),
                name="uq_budget_event_once_per_invoice",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@e9d5a48 (ships with apps/billing/budget.py — co-packets US-BIL-019@e9d5a48 · US-BIL-020@e9d5a48)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(S30's Budget Bills tab is not built; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) `account_budget_events` is NOT in Addendum r10 — an Eng-Lead
#         DDL call under r10 #15, taken because US-BIL-019 TC-6 makes the
#         balance a DERIVATION and recorded in 12-governance/02-decision-log.md.
#         (2) NO `missed_count`: PO 2026-08-11 "nodrop we chase for payments
#         until write off" SUPERSEDES BR-BIL-017's drop-off, so counting misses
#         is storage for a deleted rule. (3) The tenant PARAMETERS (r10 #5's
#         "+ tenant budget settings") are NOT created here — they already exist
#         as apps.tenancy.settings_families.BUDGET_BILLING (S69), and a second
#         copy of a ratified default is exactly the drift the settings_seam
#         docstring refuses. (4) RLS is 0013.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
