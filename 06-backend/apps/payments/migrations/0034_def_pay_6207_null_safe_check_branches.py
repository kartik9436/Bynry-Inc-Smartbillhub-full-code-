# ── Trace ──────────────────────────────────────────────
# Change:  DEF-PAY-6207 — `payments/0033` added a branch to two OR'd CHECK
#          constraints, and each branch begins by comparing the NULLABLE
#          `close_kind` to a literal. A CHECK passes when its expression is
#          NULL, so both constraints were switched OFF for every row where
#          `close_kind` is NULL.
# Story:   no story — a defect fix on phase 0's schema. Filed by LANE P0-DB,
#          fixed here because `payments/0033` is LANE P0-BATCH-3's file and
#          changing another lane's in-flight money migration is how two lanes
#          revert each other.
# Rules:   CLAUDE.md hard rule 7 (a forced close is a money action and its
#          record is what this restores) · BR-PAY-1160 · BR-SHL-025 · hard-won
#          law 7 (proved RED first, in the harness that will run it, on
#          PostgreSQL) · hard-won law 14 (SQLite cannot show this)
# Tests:   06-backend/tests/test_cr135_p0_foundations.py::
#          test_p0_3_a_till_cannot_be_sealed_with_no_record_of_how (left RED on
#          the branch on purpose by the lane that filed it) ·
#          06-backend/tests/test_cr135_p06_deposit_batch_rekey.py ·
#          10-scripts/def_pay_6207_null_branch_readback.py (PostgreSQL)
# Impacts: apps/payments/counter_session_models.CounterSession — both
#          constraints · nothing else: no column, no index and no trigger moves
# ───────────────────────────────────────────────────────
"""payments 0034 — `DEF-PAY-6207`: two CHECK branches that were never checking.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling
of 2026-08-09. Migration ordering is a CLAUDE.md 🔒 sensitive path, so there is
a row in `12-governance/09-human-review-ledger.md`.

╔══════════════════════════════════════════════════════════════════════════╗
║  A CHECK CONSTRAINT REFUSES A ROW ONLY WHEN ITS EXPRESSION IS **FALSE**, ║
║  AND **PASSES WHEN THE EXPRESSION IS NULL**.                             ║
║                                                                          ║
║  So: adding a branch to an OR'd CHECK can only ever make it **WEAKER**,  ║
║  and a branch that compares a **NULLABLE** column to a literal weakens   ║
║  it to **nothing** for every row where that column is NULL.              ║
╚══════════════════════════════════════════════════════════════════════════╝

That rule is new to this repo and is the part worth keeping. The two fixes
below are one clause each.

WHAT WENT WRONG
----------------
`payments/0033` (`P0.6`, the deposit-batch re-key) needed the system till — a
till nobody sat at — to be storable, so it added a third branch to
`ck_counter_sessions_closed_together`:

    closed_at IS NOT NULL AND closed_by IS NULL AND close_kind = 'system'

With `close_kind` NULL that last term is `NULL = 'system'` → NULL, the whole
chain becomes `FALSE OR FALSE OR NULL` = NULL, **and the row is accepted.**

⚠ **THE FILED DEFECT NAMES ONE CONSTRAINT. THERE WERE TWO.**
`ck_counter_sessions_system_is_nobodys`, added by the same migration, opens
with the identical comparison and had the identical fault. It was found by
doing what the rule above tells you to do — checking the other branches — and
it is fixed here alongside, so neither can come back alone.

WHAT EACH HOLE COST, MEASURED ON POSTGRESQL 16 AT `payments/0033`
------------------------------------------------------------------
  1. **A till sealed with no record of how or by whom** — `closed_at` set,
     `close_kind` NULL, `closed_by` NULL: **ACCEPTED**. That is the exact
     outcome the PO's ruling of 2026-09-22 exists to prevent: *"(b) A System
     Admin can close it, recorded as a forced close"*. The pair `close_kind` +
     `closed_by` is what keeps a forced close distinguishable from a counted
     one for ever, because somebody other than the owner has counted — or
     declined to count — a drawer the owner is accountable for.
  2. **An OPEN system till** — `system_day` set, `close_kind` NULL, no owner:
     **ACCEPTED**. `closed_at` is NULL on that row, so it answers
     `ix_counter_sessions_open` and appears on the *"which tills are open"*
     screen. A system till is born closed precisely so a supervisor is never
     shown a drawer nobody ever sat at.

**Nothing a clerk can do reaches either today** — phase 0 ships no close
service and `counter_sessions` holds no rows — which is why this is a defect
fixed before the screens arrive rather than an incident.

⚠ WHY THIS IS A NEW MIGRATION AND NOT AN EDIT TO `payments/0033`
-----------------------------------------------------------------
`0033` is already APPLIED — the proof templates carry it and other lanes have
cloned them. Editing an applied migration leaves `django_migrations` saying it
ran while the broken constraint stays in the database for ever, on precisely
the hosts that already have it. A forward migration is the only shape that
reaches them.

⚠ HOW IT WAS PROVED, AND THE ORDER MATTERS (law 7)
----------------------------------------------------
RED first, at `0033`, on PostgreSQL 16, by
`10-scripts/def_pay_6207_null_branch_readback.py`: both rows **ACCEPTED**, each
named. Then this migration, then the same script GREEN: both refused **by
constraint name**, and all three lawful shapes — a normal counted close, a
closed system till, an open till belonging to a person — still accepted,
because a fix that refuses everything is not a fix.

**SQLite cannot show any of this** (hard-won law 14) and the suite runs there,
which is why the one test that asks the question went red when `0033` landed
and was pushed red rather than caught.
"""

from django.db import migrations, models

import apps.payments.models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0033_cr135_p0_6_deposit_batch_rekey"),
    ]

    operations = [
        # ── 1 · a sealed till always records HOW and WHO ────────────────────
        migrations.RemoveConstraint(
            model_name="countersession",
            name="ck_counter_sessions_closed_together",
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    closed_at__isnull=True, closed_by__isnull=True, close_kind__isnull=True
                )
                | models.Q(
                    closed_at__isnull=False, closed_by__isnull=False, close_kind__isnull=False
                )
                | (
                    # `close_kind IS NOT NULL` FIRST. Without it this branch is
                    # NULL for every row with a NULL close_kind, and NULL is
                    # accepted — which switched the whole constraint off.
                    models.Q(close_kind__isnull=False)
                    & models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=True,
                        close_kind=apps.payments.models.COUNTER_CLOSE_SYSTEM,
                    )
                ),
                name="ck_counter_sessions_closed_together",
            ),
        ),
        # ── 2 · a system till is nobody's, and nobody's till is a system one ─
        migrations.RemoveConstraint(
            model_name="countersession",
            name="ck_counter_sessions_system_is_nobodys",
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(close_kind__isnull=False)
                    & models.Q(
                        close_kind=apps.payments.models.COUNTER_CLOSE_SYSTEM,
                        closed_by__isnull=True,
                        opening_float=0,
                        owner__isnull=True,
                        service_centre__isnull=True,
                        system_day__isnull=False,
                    )
                )
                | (
                    (
                        models.Q(close_kind__isnull=True)
                        | models.Q(
                            close_kind__in=apps.payments.models.COUNTER_CLOSE_KINDS_BY_A_PERSON
                        )
                    )
                    & models.Q(
                        owner__isnull=False,
                        service_centre__isnull=False,
                        system_day__isnull=True,
                    )
                ),
                name="ck_counter_sessions_system_is_nobodys",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/10-defect-log.csv DEF-PAY-6207 (filed by LANE P0-DB, fixed here) · 12-governance/02-decision-log.md 2026-09-22 · apps/payments/migrations/0033_cr135_p0_6_deposit_batch_rekey.py (the migration that introduced both branches) · CLAUDE.md hard rule 7 · hard-won laws 7 and 14
# generated: 2026-09-22 by LANE P0-BATCH-3
# checklist: A✔ B=n/a(no screen) C✔ D=n/a(a migration) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a PostgreSQL 16 clone at payments/0033 — both rows ACCEPTED, each named by the constraint that should have refused it; GREEN at 0034 with both refused BY NAME and all three lawful shapes still accepted. `test_p0_3_a_till_cannot_be_sealed_with_no_record_of_how`, left red on the branch on purpose, goes green on the fix rather than being weakened. makemigrations --check clean · ruff clean · FORWARDS, BACKWARDS, FORWARDS AGAIN on a PostgreSQL 16 clone, measured rather than assumed: after the round trip both constraint definitions still contain `IS NOT NULL`, read back from `pg_get_constraintdef` rather than inferred from the migration state
# exceptions:
