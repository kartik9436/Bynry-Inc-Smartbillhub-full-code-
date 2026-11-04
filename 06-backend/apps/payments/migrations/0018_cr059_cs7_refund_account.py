# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-7 (task 60) — "Refund a credit built from several
#           payments". Done looks like S58: *"a credit built from two
#           overpayments can be refunded, listing the payments behind it."*
# Story:    US-PAY-011 (refunds)   Screens: S58 · S21
# Rules:    BR-PAY-014 (refunds only from a real credit balance; Admin
#           approval; immutable row) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           rule 2 (money + CHAR(3)) · rule 4 (financial immutability — and see
#           the BACKFILL section, which is the one place this migration touches
#           rows that already stand)
# Ruling:   **`OQ-167` CLOSED 2026-08-12** — PO verbatim: *"user can do a refund
#           or issue a credit - it will be manula decision, provide a mecahnism
#           to complete the tasks"*, worked on **$40.00 (June) + $17.13 (July)
#           = $57.13**. **`OQ-195` CLOSED 2026-09-01 — option (a)**: make
#           `refunds.payment_id` NULLABLE and add `refunds.account_id`.
# Tests:    06-backend/tests/test_cr059_cs7_account_refund.py
# ───────────────────────────────────────────────────────
"""payments 0018 — a refund belongs to the ACCOUNT (CR-059 CS-7).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and `refunds` records
money paid out). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO
ruling of 2026-08-09.

⚠ **THIS REVERSES A SIGNED SCHEMA STATEMENT, AND THE SUPERSESSION IS STATED
RATHER THAN ASSUMED.** `B2 §2` types `refunds.payment_id uuid NOT NULL` and
gives the table no account column at all, so a refund could name exactly ONE
source payment. **The PO ruled otherwise on 2026-09-01** (`OQ-195`, option (a)),
closing a schema question raised against a mechanism they had already ruled on
2026-08-12 (`OQ-167`). This migration is that ruling and nothing else.

THE CASE, WITH THE FIGURE
=========================
An account overpays **$40.00** in June and **$17.13** in July and rings up
asking for the **$57.13** back. It is ONE cheque and ONE decision. Before this
the table could not say so: a refund row names one payment, so the only
expressible answers were two cheques for one decision, or a refusal. The
product chose the refusal — `apps/payments/credit.refund_from_credit_balance`
has raised `NotImplementedError("OQ-195")` since 2026-08-15 — which was right,
and is now answered.

WHAT MOVES, IN THREE STEPS, AND WHY IT IS THREE
===============================================
1. **`account_id` is added NULLABLE.** A NOT NULL column cannot be added to a
   table with rows unless every row is given a value in the same statement, and
   the value is different for every row.
2. **Every existing refund is backfilled from its own payment's account.** That
   is not a guess: until today `refunds.payment_id` was NOT NULL, so every
   historic row HAS a payment, and that payment's account is the account the
   refund was always against — `refunds.py` computed exactly this, every time,
   as `refund.payment.account_id`.
3. **`account_id` is tightened to NOT NULL and `payment_id` is loosened.** In
   that order: tightening first means the table is never in a state where a row
   could be written with neither.

⚠ **THE BACKFILL DISABLES THE `refunds` FREEZE TRIGGER FOR THE LENGTH OF ONE
STATEMENT, AND THAT NEEDS SAYING OUT LOUD.** `payments/0006`'s
`trg_refund_immutable` refuses **every** column change outside the status walk —
correctly, it is hard rule 4 — so an ordinary `UPDATE refunds SET account_id`
would be refused for every row. This is a SCHEMA migration filling in a column
the schema is adding, not an application write path amending a financial fact:
the value written is the one the row already implied through its FK, and no
figure, date, status or amount moves. It is disabled and re-enabled inside the
same transaction, so no application statement can ever run while it is off.

**MEASURED, NOT ASSUMED:** if a historic refund's payment cannot be read the
UPDATE leaves that row NULL and step 3's `SET NOT NULL` **fails the migration**
rather than filling in a default. A default here would be a refund pointed at
an account it was never against, on a row hard rule 4 freezes forever.

WHAT THIS MIGRATION DOES **NOT** DO
===================================
* **It does not drop `payment_id`.** The column is still true and still useful
  wherever a refund really does draw ONE overpayment back — PE-9's $350.00 →
  $57.13 is exactly that, and S58 showing *"this came from PMT-2608-000412"* is
  better than S58 unable to. What changed is that its ABSENCE is now lawful.
* **It does not touch the freeze's permanent behaviour.** The trigger is
  restored byte-for-byte; `payment_id` and `account_id` are both still frozen on
  a row that exists, so a refund cannot be re-pointed at another account after
  the fact.
* **It writes no RLS policy.** `refunds` has carried one since `payments/0006`
  and it filters on `tenant_id`, which this migration does not touch.
"""

from django.db import migrations, models
import django.db.models.deletion

BACKFILL = """
ALTER TABLE refunds DISABLE TRIGGER trg_refund_immutable;
UPDATE refunds AS r
   SET account_id = p.account_id
  FROM payments AS p
 WHERE p.id = r.payment_id
   AND r.account_id IS NULL;
ALTER TABLE refunds ENABLE TRIGGER trg_refund_immutable;
"""

#: SQLite has no such trigger and no `ALTER TABLE … DISABLE TRIGGER`, so the
#: same backfill is the bare UPDATE. Split by vendor rather than written once,
#: because a statement that is a no-op on one engine and load-bearing on the
#: other is the shape CLAUDE.md hard-won law 14 is about.
BACKFILL_SQLITE = """
UPDATE refunds
   SET account_id = (SELECT p.account_id FROM payments p WHERE p.id = refunds.payment_id)
 WHERE account_id IS NULL;
"""


def backfill_account_from_payment(apps_registry, schema_editor):
    """Give every refund that already exists the account it was always against.

    Raw SQL rather than an ORM loop for two reasons and both matter here: the
    ORM's `.save()` would be refused by the freeze trigger one row at a time,
    and a `.update()` through the ORM cannot reach across the FK in one
    statement on PostgreSQL. One statement also means one transaction with the
    trigger off, rather than N.
    """
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(BACKFILL if vendor == "postgresql" else BACKFILL_SQLITE)


def clear_account(apps_registry, schema_editor):
    """The reverse: blank the column before it is dropped.

    The trigger has to come off for this too, for the same reason. Nothing is
    lost — the column is about to cease to exist and every row's payment link is
    still there, which is where the value came from.
    """
    vendor = schema_editor.connection.vendor
    sql = (
        "ALTER TABLE refunds DISABLE TRIGGER trg_refund_immutable;\n"
        "UPDATE refunds SET account_id = NULL;\n"
        "ALTER TABLE refunds ENABLE TRIGGER trg_refund_immutable;\n"
        if vendor == "postgresql"
        else "UPDATE refunds SET account_id = NULL;\n"
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0017_cr059_cs8_cs32_cs30_columns"),
        ("customers", "0001_initial"),
    ]

    operations = [
        # 1 · nullable, so it can be added to a table that has rows at all.
        migrations.AddField(
            model_name="refund",
            name="account",
            field=models.ForeignKey(
                blank=True,
                db_column="account_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="refunds",
                to="customers.account",
            ),
        ),
        # 2 · every historic row, from its own payment. See the docstring.
        migrations.RunPython(backfill_account_from_payment, clear_account),
        # 3a · NOT NULL. Fails the migration if step 2 could not fill a row,
        #      which is the intended outcome: a refund with no account is a
        #      cheque with no addressee.
        migrations.AlterField(
            model_name="refund",
            name="account",
            field=models.ForeignKey(
                db_column="account_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="refunds",
                to="customers.account",
            ),
        ),
        # 3b · and only now may a refund exist without a payment behind it.
        migrations.AlterField(
            model_name="refund",
            name="payment",
            field=models.ForeignKey(
                blank=True,
                db_column="payment_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="refunds",
                to="payments.payment",
            ),
        ),
        # The read S58 makes on every open: *"what has this account had back?"*
        # Without it that is a sequential scan of every refund the tenant has
        # ever paid out.
        migrations.AddIndex(
            model_name="refund",
            index=models.Index(fields=["tenant", "account"], name="ix_refunds_account"),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-7 · §11 task 60 · `OQ-167` (CLOSED 2026-08-12) ·
#         `OQ-195` (CLOSED 2026-09-01, option (a)) · B2 §2 `refunds` ·
#         apps/payments/migrations/0006 (the freeze this suspends for one
#         statement and restores) · apps/payments/credit.refund_from_credit_balance
#         (the stub this unblocks)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S58's *"listing the
#            payments behind it"* is the screen lane's) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 this REVERSES `B2 §2`'s `refunds.payment_id uuid NOT NULL`. It is the
#      PO's ruling of 2026-09-01 (`OQ-195`, option (a)) and the supersession is
#      stated above rather than assumed. B2 itself is a contracts-lane document
#      and is NOT edited here; the amendment is owed and is REPORTED.
#   E2 `OQ-195` still reads OPEN in `12-governance/01-open-questions.md`
#      (`DEF-2350`). That file is outside this lane's write scope; the ruling and
#      its implementation are recorded in `12-governance/02-decision-log.md`
#      instead, and flipping the register row is REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
