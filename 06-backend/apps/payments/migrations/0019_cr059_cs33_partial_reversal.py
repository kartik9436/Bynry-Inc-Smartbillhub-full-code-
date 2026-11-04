# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-33 (task 66) — "Reverse part of a payment: a schema and
#           concurrency change on a money path". The CR's own words: *"⚠ THE
#           BLOCKER IS NOT THE ARITHMETIC, IT IS THE INDEX. A unique constraint
#           (`uq_payments_reverses`) permits exactly one reversal per payment.
#           Partial reversal needs many, which means replacing that guarantee
#           with a summed check — and the unique index is what currently makes a
#           retried request and a lost race indistinguishable, so the
#           idempotency guard has to be re-established a different way."*
# Story:    US-PAY-009 · US-PAY-010   Screens: S35
# Rules:    BR-PAY-884 (NEW — the sum of all reversals against one payment may
#           never exceed it) · BR-PAY-885 (NEW — a partial reversal unwinds
#           allocations newest-bill-first unless the clerk names the bill) ·
#           BR-PAY-013 · BR-PAY-028 + CLAUDE.md hard rule 6 (idempotency) ·
#           hard rule 4 (a correction is NEW ROWS) · CLAUDE.md hard-won law 14
#           (proved on PostgreSQL, not on the SQLite suite)
# Tests:    06-backend/tests/test_cr059_cs33_partial_reversal.py
# ───────────────────────────────────────────────────────
"""payments 0019 — one reversal per payment becomes MANY, summing to no more.

HUMAN-OWNED (migration ordering AND idempotency keys are both CLAUDE.md 🔒
paths, and this file moves the guarantee that stands between a retried bounce
and a doubled debt). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO
ruling of 2026-08-09.

⚠ **THIS IS A SIGNED-SCHEMA CHANGE AND CR-059 SAYS SO** — *"Drop or narrow
`uq_payments_reverses`; add the summed constraint. A signed-schema change —
contracts lane, not payments."* This lane's brief names CS-33 as its own, so it
is built here; the contracts-lane review is OWED and is REPORTED in the lane
report and in `12-governance/02-decision-log.md`. **B2 is not edited by this
lane** — that document belongs to contracts.

════════════════════════════════════════════════════════════════════════════
WHAT THE INDEX WAS DOING, AND IT WAS DOING TWO JOBS
════════════════════════════════════════════════════════════════════════════
`uq_payments_reverses` is `UNIQUE (tenant_id, reverses_payment_id)` and it has
been carrying **two guarantees at once**:

  1. **A payment cannot be over-reversed** — because it can only be reversed
     once at all, and one reversal is the whole amount.
  2. **A LOST RACE AND A REPLAY ARE THE SAME FACT** — two requests to reverse
     one payment, arriving together, and exactly one row lands.

Dropping it drops both, and only the first is what CS-33 wants moved. **The
second has to be re-established or a retried bounce doubles a customer's debt**,
which is what hard rule 6 exists to prevent. So this migration replaces one
index with THREE things, and each answers exactly one of the questions the index
was answering:

    ── over-reversal ──────────────────────────────────────────────────────
    `payments_reversal_sum_guard()`  a BEFORE INSERT trigger that sums every
    reversal against the original, INCLUDING the row being inserted, and raises
    when the total exceeds what the original stands for. **In the database**,
    because a Python check and a database check are two independent guards on
    one arithmetic fact and a posting that is wrong here is wrong forever.

    ── the lost race ──────────────────────────────────────────────────────
    `uq_payments_webhook_key` — ALREADY THERE, unchanged, and now load-bearing.
    `reversal_api.payment_reverse` has REQUIRED an `idempotency_key` since
    2026-09-01 and its own docstring says why in advance: *"When [CS-33] lands,
    this required key becomes the only per-submit guard left standing, so it is
    required from the first day rather than added after the index is gone."*
    Two identical submits carry one token, the second INSERT hits that unique
    index, and `reverse_payment`'s existing `IntegrityError` handler answers
    with the first reversal.

    ── two DIFFERENT partial reversals racing ─────────────────────────────
    A `SELECT … FOR UPDATE` on the ORIGINAL payment row, taken by
    `reversal.reverse_payment` inside its transaction before it sums. Two
    partials of one payment then serialise, so the second reads the first's row
    and the trigger above sees a true total. **Without it both could pass their
    own check and commit, and the sum of two lawful halves can exceed the
    whole.** The lock is in the service because a trigger cannot take one for a
    statement that has not run yet.

════════════════════════════════════════════════════════════════════════════
⚠ THE TRIGGER IS THE ONLY HALF THAT CANNOT BE PROVED ON THE DEFAULT SUITE
════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard-won law 14: `config/settings/test.py` hardcodes in-memory SQLite.
**SQLite has no `FOR UPDATE` and this trigger is plpgsql**, so on the default
suite the summed check simply is not there — the service's own Python check
carries the whole file and every test passes whether the database half exists or
not. `tests/test_cr059_cs33_partial_reversal.py` marks the concurrency cases
`requires_postgres` and they are the ones that matter.

**The narrowing is a NARROWING, not a drop.** `uq_payments_reverses` is replaced
by a PARTIAL unique index over FULL reversals only — a payment may still carry
at most one whole-amount reversal — so every bounce that exists today is
governed exactly as it was, and only partials are newly possible.
"""

from django.db import migrations, models
from django.db.models import Q

#: ⚠ **SINGLE `%`, NOT `%%` — AND THE DIFFERENCE IS A MIGRATION THAT WILL NOT
#: APPLY.** Every other trigger in this module is installed through
#: `migrations.RunSQL`, which passes the string to the driver as a QUERY and
#: therefore needs `%` doubled. These are executed through
#: `schema_editor.connection.cursor().execute(sql)` with **no parameters**, so
#: no interpolation happens and `%%` survives into plpgsql — where it reads as
#: an escaped literal `%` rather than a placeholder, leaving the RAISE with
#: three arguments and nowhere to put them:
#:
#:     psycopg.errors.SyntaxError: too many parameters specified for RAISE
#:     CONTEXT: compilation of PL/pgSQL function …
#:
#: **It is invisible on the default suite**, which is CLAUDE.md hard-won law 14
#: exactly: SQLite installs neither of these, so every test passed and the
#: migration failed the first time it met a real PostgreSQL.
#: The summed check, in the database. It reads the ORIGINAL's amount and the Σ
#: of every reversal already against it, adds the row being inserted, and
#: refuses the excess by name.
#:
#: ⚠ **`ABS()` ON BOTH SIDES, BECAUSE A REVERSING ROW IS NEGATIVE.** The
#: original is +292.87 and its reversals are −100.00 and −192.87; the rule is
#: about SIZE, and comparing signed values would let a reversal of −1000.00 pass
#: a `<=` test against +292.87 on every engine that does arithmetic correctly.
SUM_GUARD = """
CREATE OR REPLACE FUNCTION payments_reversal_sum_guard() RETURNS trigger AS $$
DECLARE
  original_amount numeric(18,6);
  already        numeric(18,6);
BEGIN
  IF NEW.reverses_payment_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT amount INTO original_amount
    FROM payments
   WHERE id = NEW.reverses_payment_id
   FOR UPDATE;

  IF original_amount IS NULL THEN
    RAISE EXCEPTION 'BR-PAY-884: payment % reverses %, which does not exist. A reversal that names nothing is a row nobody can explain and money nobody can trace.',
      COALESCE(NEW.payment_no, NEW.id::text), NEW.reverses_payment_id::text;
  END IF;

  SELECT COALESCE(SUM(ABS(amount)), 0) INTO already
    FROM payments
   WHERE reverses_payment_id = NEW.reverses_payment_id
     AND id <> NEW.id;

  IF already + ABS(NEW.amount) > ABS(original_amount) THEN
    RAISE EXCEPTION 'BR-PAY-884 / hard rule 6: this reversal of % would take the total reversed against that payment to %, and the payment is only %. The sum of every reversal against one payment may never exceed it — anything more is money the customer never paid being taken back twice.',
      ABS(NEW.amount), already + ABS(NEW.amount), ABS(original_amount);
  END IF;

  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_reversal_sum ON payments;
CREATE TRIGGER trg_payment_reversal_sum
  BEFORE INSERT ON payments
  FOR EACH ROW EXECUTE FUNCTION payments_reversal_sum_guard();
"""

DROP_SUM_GUARD = """
DROP TRIGGER IF EXISTS trg_payment_reversal_sum ON payments;
DROP FUNCTION IF EXISTS payments_reversal_sum_guard();
"""


def install_sum_guard(apps_registry, schema_editor):
    """The database half of BR-PAY-884, on PostgreSQL only.

    ⚠ **SQLite gets NOTHING and that is law 3 rather than an omission.** The
    developer tier has no plpgsql and no `FOR UPDATE`; installing a weaker
    approximation there would make the default suite green over a guard that is
    not the one production runs, which is precisely CLAUDE.md hard-won law 14's
    shape. The service's Python check runs on both engines and the
    `requires_postgres` cases prove THIS one.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SUM_GUARD)


def remove_sum_guard(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DROP_SUM_GUARD)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0018_cr059_cs7_refund_account"),
    ]

    operations = [
        # 1 · the old guarantee comes off. It permitted exactly ONE reversal per
        #     payment, which is the thing CS-33 exists to change.
        migrations.RemoveConstraint(
            model_name="payment",
            name="uq_payments_reverses",
        ),
        # 2 · the column the narrower constraint is written against. ⚠ **IT
        #     COMES FIRST, AND THE ORDER IS NOT COSMETIC:** a partial index whose
        #     condition names a field the migration state does not have yet
        #     fails to resolve, and the failure surfaces as
        #     `FieldError: Cannot resolve keyword 'is_partial_reversal'` on
        #     EVERY test in the process — which reads like a broken tree rather
        #     than like a migration written in the wrong order.
        migrations.AddField(
            model_name="payment",
            name="is_partial_reversal",
            field=models.BooleanField(default=False),
        ),
        # 3 · and a NARROWER guarantee goes back: at most one FULL reversal per
        #     payment. Every bounce that exists today is a full reversal, so
        #     nothing already recorded changes its guarantees; what becomes
        #     possible is a payment carrying several PARTIAL reversals.
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                fields=["tenant", "reverses_payment"],
                condition=Q(reverses_payment__isnull=False) & Q(is_partial_reversal=False),
                name="uq_payments_full_reverses",
            ),
        ),
        # 4 · the summed check, in the database, on PostgreSQL.
        migrations.RunPython(install_sum_guard, remove_sum_guard),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-33 · §11 tasks 66 and 67 · §7 (the three guards) ·
#         BR-PAY-884 · BR-PAY-885 · BR-PAY-013 · BR-PAY-028 ·
#         apps/payments/reversal.py (the FOR UPDATE and the Python half) ·
#         apps/payments/reversal_api.py (the required idempotency key, which
#         that module's docstring already names as this change's last guard)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 task 67 owns the
#            S35 amount field) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 CR-059 assigns this to the CONTRACTS lane because it changes signed
#      schema. This lane's brief names CS-33 as its own, so it is built here and
#      the contracts review is OWED and REPORTED. `B2` itself is NOT edited.
#   E2 the summed trigger exists on PostgreSQL ONLY. SQLite has no plpgsql and
#      no row locking; a weaker approximation there would make the default suite
#      green over a guard production does not run (law 14).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
