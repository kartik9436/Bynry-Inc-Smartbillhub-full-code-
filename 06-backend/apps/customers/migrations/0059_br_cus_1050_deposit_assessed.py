"""customers 0059 — **the deposit the clerk ASSESSED finally has a column.**

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-09-20 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Ledger row: `12-governance/09-human-review-ledger.md`.

`BR-CUS-1050` (CONFIRMED 2026-09-12) · `DEF-CUS-5909` (high, money-math) ·
blueprint **p075**, the move record's `Deposit` review block.

WHAT WAS WRONG, WITH THE FIGURE
-------------------------------
The move record's `Still to collect` is **assessed minus taken**. p075 draws
the three lines in order — `Amount $150.00` · `Amount taken $150.00` ·
`Still to collect $0.00` — so the drawing itself requires BOTH sides to be
readable afterwards.

`accounts` held only ONE of them. `deposit_on_file` is what ARRIVED
(`BR-CUS-670`, written when the payment clears) and nothing at all held what
the clerk ASSESSED, so `move_record_reads._money_taken` reached for
`plan_deposit_rules` — which `BR-CUS-1050` is explicit is a REFERENCE figure
*"reported beside what was typed"* and never enforced.

**Worked, and it is `DEF-CUS-5909`'s own case:** a **`$150.00`** deposit with
**`$25.00`** handed over, against a plan standard of **`$120.00`**, read
**`$95.00`** where the review screen computes **`$125.00`**. Right arithmetic
over the wrong pair — which is why every existing test passed: they all
asserted the deposit REGISTER, and that was correct all along. None asserted
the difference.

WHAT THIS DOES
--------------
ONE nullable `NUMERIC(18,4)` column. No index (nothing sorts or pages on it —
the move record reads it by primary key), no default, no backfill, no data
migration of any kind.

⚠ **THE ABSENCE OF A BACKFILL IS DELIBERATE AND IS HARD RULE 4.** An account
opened before today was assessed a figure this product never stored; deriving
one now from `plan_deposit_rules` would write the very number the defect exists
because we read. Every existing row reads NULL, and **NULL means *no deposit is
owed***, not *nobody typed one* — see the model's own note. The move record of
such an account states the absence rather than a figure nobody chose.

⚠ **NO CHECK CONSTRAINT, AND THAT IS A CHOICE RATHER THAN AN OMISSION.** A
`>= 0` check was considered and declined: the column is written on exactly one
path, `deposit.take()`, behind `deposit.clean()`, which already refuses a
negative or non-decimal amount BY NAME with its own field error — and a check
whose only reachable violation is a bug in the one writer buys a constraint
nobody can trip while making every future correction migration heavier. The
narrow guarantee this table already leans on (`BR-CUS-023`: the figure is not a
free-text input on any door) is what actually holds it.

⚠ **FOUR DECIMALS AND NOT SIX.** CLAUDE.md hard rule 2 as re-signed by the PO
on 2026-08-22 — *"MOney 4 decimal, percentage 6 decimal, display both 2
decimal"* — governs what a NEW column declares. `deposit_on_file` beside it
stays `18,6`; the same rule says an existing `18,6` column is a lawful
container and is not to be rewritten.

REVERSIBLE, AND WHAT REVERSING COSTS
------------------------------------
`AddField` reverses to `RemoveField` cleanly. **Reversing DROPS every assessed
figure**, which is real data loss rather than a schema change, and the move
record then silently goes back to computing the shortfall against the plan
standard — the defect, restored, with no test going red. So the rollback note
says to dump `accounts (id, deposit_assessed)` first. It is safe on day one,
when no row has a value.

ORDERING
--------
Depends on `0058_br_cus_030_close_reason`, the current leaf. It touches only
`accounts`, a table this module owns outright (B1/B8), and no other module's
migration references the column — so there is no cross-module ordering hazard
to state.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0058_br_cus_030_close_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="deposit_assessed",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=18, null=True
            ),
        ),
    ]
