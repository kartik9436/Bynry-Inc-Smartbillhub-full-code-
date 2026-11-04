# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6370 — "A supervisor's deposit waive leaves no mark on the
#           account: who waived, when, the figure and why live only in the
#           account-opening audit_log row, which is pruned".
# Rules:    BR-CUS-1050 (as amended 2026-09-23 — the waive is kept ON THE
#           ACCOUNT) · OQ-1340 (closed 2026-09-23: audit_log has one retention
#           rule and no row is exempt) · CLAUDE.md hard rule 2 (money stored to
#           4 decimals) · hard rule 1 (RLS — untouched here, see ORDERING)
# Decision: 12-governance/02-decision-log.md, 2026-09-23 — *THE DEPOSIT IS THE
#           PLAN'S FIGURE FOR THE CUSTOMER'S CATEGORY, WITH NO OVERRIDE*
# Tests:    06-backend/tests/test_cr094_wh_deposit.py (the waive is read back
#           off the account row)
# ───────────────────────────────────────────────────────
"""customers 0066 — **a waived deposit is kept on the account.**

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-09-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Ledger row: `12-governance/09-human-review-ledger.md`.

WHAT WAS WRONG, WITH THE FIGURE
-------------------------------
A supervisor waives Rosa Pemberton's **$150.00** Residential deposit at the
counter. Until this migration the account kept nothing of it:
`deposit_on_file` stays 0 and `deposit_assessed` stays NULL — exactly what an
account on a plan that asks no deposit holds. The only record was the
account-opening row in `audit_log`, and `OQ-1340` was closed on 2026-09-23 with
*"when audit log is delete - it is deleted thats okay"*. So a year on, nobody
could say that $150.00 was forgiven, by whom, or why.

WHAT THIS DOES
--------------
FOUR nullable columns on `accounts`, all NULL together or all set together:

  deposit_waived_amount   NUMERIC(18,4)  the plan's figure at the moment of the waive
  deposit_waived_at       timestamptz    when it was recorded
  deposit_waived_by       uuid → users   who (a System Admin or Executive)
  deposit_waive_reason    text           the one short sentence they typed

Written on exactly one path, `apps/customers/deposit.take()`, inside the
account's own creating transaction. No payload vocabulary names them.

⚠ **NO BACKFILL, DELIBERATELY.** An account waived before today has no record
of it anywhere this migration could read — the audit rows that might have held
it are on a retention schedule and some are already gone — so deriving one
would be inventing a money decision. Existing rows read NULL, which means *no
waive is recorded on this account*.

⚠ **FOUR DECIMALS AND NOT SIX** — CLAUDE.md hard rule 2 as re-signed on
2026-08-22 governs what a NEW money column declares.

⚠ **NO CHECK CONSTRAINT for all-or-none.** The one writer sets all four in one
`save(update_fields=…)`, and 0059 declined the same kind of constraint for the
same reason: a check whose only reachable violation is a bug in the one writer
makes every later correction migration heavier while tripping nothing.

REVERSIBLE, AND WHAT REVERSING COSTS
------------------------------------
`AddField` reverses to `RemoveField` cleanly. **Reversing DROPS every recorded
waive** — real data loss, not a schema change — so dump
`accounts (id, deposit_waived_amount, deposit_waived_at, deposit_waived_by,
deposit_waive_reason)` first. Safe on day one, when no row has a value.

ORDERING
--------
Depends on `0065_br_cus_1091_address_parts_as_given` (the customers leaf at the
tip on 2026-09-23) and on `identity 0005_cr070_f_field_technician` (the users
table's current leaf — Django names it because of the FK). It touches only
`accounts`, a table customers owns outright. **RLS IS UNTOUCHED:** `accounts`
already carries its tenant policy with `FORCE`, and a column added to a table
inherits the table's row policy — nothing here creates, alters or drops a
policy. No other module's migration references these columns.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0065_br_cus_1091_address_parts_as_given"),
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="deposit_waive_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="deposit_waived_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="deposit_waived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="deposit_waived_by",
            field=models.ForeignKey(
                blank=True,
                db_column="deposit_waived_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
    ]
