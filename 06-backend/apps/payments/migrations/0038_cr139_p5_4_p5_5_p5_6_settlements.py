# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, tasks `P5.4`
#          (`settlements`), `P5.5` (`settlement_members`) and `P5.6`
#          (`payments.settlement_id`). Drawing:
#          `05-prototype/06 Payments Page Blueprint.pdf` p024.
# Rules:   CLAUDE.md hard rule 1 (isolation is `payments/0039`, its own file) ·
#          hard rule 2 (a NEW money column declares FOUR decimals — the drawing
#          says six and the signed rule wins; PO re-sign 2026-08-22) · hard
#          rule 4 (nothing here rewrites an issued payment's money; the one
#          column added to `payments` is a nullable pointer) · hard rule 6
#          (`uq_settlements_provider_code` is `P5.3`'s database half)
# Tests:   06-backend/tests/test_cr139_p5_settlements.py ·
#          06-backend/tests/test_cr139_p5_rls_pg.py (PostgreSQL only)
# Impacts: apps/payments/settlement_models.py (the column-by-column reasoning,
#          which is where a reader looking at the model will be) ·
#          apps/payments/models.Payment.settlement_id ·
#          apps/payments/apps.py (`ready()` registers the new module) ·
#          apps/payments/settlements.py (the ONLY write path for both tables)
# ───────────────────────────────────────────────────────
"""payments 0038 — `settlements`, `settlement_members`, and the third state.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09. **Migration ordering is a CLAUDE.md 🔒 sensitive path**, so a row
in `12-governance/09-human-review-ledger.md` states in plain English, with a
figure, what would be put to the Product Owner.

⚠ THE MONEY COLUMNS ARE `NUMERIC(18,4)` AND THE DRAWING SAYS `NUMERIC(18,6)`
-----------------------------------------------------------------------------
`P5.4`, verbatim: *"Money at `NUMERIC(18,6)`, currency `CHAR(3)`"*. **The first
half is not followed and the second is.** CLAUDE.md hard rule 2, PO re-sign
2026-08-22, verbatim: *"We already confirmed this - MOney 4 decimal, percentage
6 decimal , display both 2 decimal"* — and that re-sign explicitly supersedes
the rule's own original `NUMERIC(18,6)`. **Existing 18,6 columns stay lawful
containers; what a NEW column DECLARES is four.**

`payments/0031` took the same reading for `counter_sessions.opening_float` on
2026-09-22, so this is the second time and the precedent is on the branch. It is
B14 rule 37 one level down — *a figure drawn in a wireframe is an illustration,
never a fact to build to* — and a signed rule is not an illustration.

**WHAT FOUR DECIMALS COSTS AND WHY IT COSTS NOTHING HERE.** A payout's three
figures are sums of payment amounts, and `payments.amount` is itself an existing
`NUMERIC(18,6)` container holding values rounded at finalisation to four (B4).
So no representable figure is lost: `$4,972.90` is `4972.9000` either way. What
four decimals removes is the ability to WRITE a figure the money rules forbid.

⚠ THIS MIGRATION IS REVERSIBLE AND THE REVERSE IS THE DEFAULT ONE
-----------------------------------------------------------------------------
The blueprint's p025 risk table names *"a migration with no way back"* and
points at phase 0's deposit re-key and phase 3's CHECK alteration. **This one is
neither.** Every operation is a CreateModel, an AddField of a NULLABLE column,
an AddIndex or an AddConstraint on a table created in this same file — Django's
own reverse drops them all and **no existing row is read, rewritten or
deleted**, so a rollback loses only rows written after it ran. There is no
data migration here at all, which is the whole reason it needs no hand-written
reverse.

⚠ WHAT IS DELIBERATELY *NOT* IN THIS FILE
-----------------------------------------------------------------------------
  * **RLS.** `payments/0039` is its own file, exactly as `payments/0032` is for
    `counter_sessions`. A policy in the same migration as its table is a policy
    whose failure to apply on SQLite looks identical to it not existing.
  * **An index on `payments.settlement_id`.** The drawing asks for none, the
    payout→members read is served by `ix_settlement_members_set`, and `P2.5`
    measured what an unmeasured index on this table is worth: **264 kB at the
    top of tier T5, which decides nothing.** An index nobody measured is an
    index nobody can defend.
  * **A foreign key from `payments` to `settlements`.** See
    `apps/payments/models.Payment.settlement_id` — the reason is consistency
    with the two sibling pointer columns, and the cost (no referential
    integrity) is stated there rather than left to be discovered.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.expressions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0037_cr137_p3_7_corrects_payment"),
        ("tenancy", "0046_cr122_brc06_move_in_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="settlement_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="Settlement",
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
                ("provider", models.TextField()),
                ("paid_out_at", models.DateTimeField()),
                ("gross", models.DecimalField(decimal_places=4, max_digits=18)),
                ("fees", models.DecimalField(decimal_places=4, max_digits=18)),
                ("net", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "status",
                    models.TextField(
                        choices=[("received", "received"), ("matched", "matched")],
                        default="received",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bank_line",
                    models.ForeignKey(
                        blank=True,
                        db_column="bank_line_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settlements",
                        to="payments.bankline",
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
                "db_table": "settlements",
            },
        ),
        migrations.CreateModel(
            name="SettlementMember",
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
                ("gross", models.DecimalField(decimal_places=4, max_digits=18)),
                ("fee", models.DecimalField(decimal_places=4, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "payment",
                    models.ForeignKey(
                        db_column="payment_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settlement_memberships",
                        to="payments.payment",
                    ),
                ),
                (
                    "settlement",
                    models.ForeignKey(
                        db_column="settlement_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="members",
                        to="payments.settlement",
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
                "db_table": "settlement_members",
            },
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["tenant", "-paid_out_at"], name="ix_settlements_paid_out"),
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["tenant", "status"], name="ix_settlements_status"),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.UniqueConstraint(
                fields=("tenant", "provider", "code"), name="uq_settlements_provider_code"
            ),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "net",
                        django.db.models.expressions.CombinedExpression(
                            models.F("gross"), "-", models.F("fees")
                        ),
                    )
                ),
                name="ck_settlements_net_ties",
            ),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                condition=models.Q(("fees__gte", 0)), name="ck_settlements_fees_not_negative"
            ),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("bank_line__isnull", False), ("status", "matched")),
                    models.Q(("bank_line__isnull", True), ("status", "received")),
                    _connector="OR",
                ),
                name="ck_settlements_matched_has_line",
            ),
        ),
        migrations.AddIndex(
            model_name="settlementmember",
            index=models.Index(fields=["tenant", "settlement"], name="ix_settlement_members_set"),
        ),
        migrations.AddConstraint(
            model_name="settlementmember",
            constraint=models.UniqueConstraint(
                fields=("tenant", "payment"), name="uq_settlement_members_payment"
            ),
        ),
        migrations.AddConstraint(
            model_name="settlementmember",
            constraint=models.CheckConstraint(
                condition=models.Q(("fee__gte", 0)), name="ck_settlement_members_fee_not_negative"
            ),
        ),
    ]
