# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-10, decision log entries 13 and 14. THE SCHEMA
#           HALF of the pair `0030`/`0031`; see `0030`'s docstring for the
#           ruling and for why the two are separate files.
# Rules:    BR-RAT-028 (AMENDED — the source moves, the arithmetic does not)
# Tests:    06-backend/tests/test_cr090_minimum_reads_from_the_schedule.py
# ───────────────────────────────────────────────────────
"""rating 0031 — `plan_services.minimum_amount` is removed.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-10 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **RUN ORDER IS THE WHOLE SAFETY ARGUMENT AND IT IS NOT NEGOTIABLE.** `0030`
copies every stated figure onto the attached schedule's versions FIRST. This file
then deletes the plan's column. Run this one alone against a database `0030` has
not touched and every per-service floor in the product silently stops being
charged — the shipped fixture's `RES-STD` water line is **$5.40 a month** short
on `WE-3`'s worked case, with `tsc`, the golden harness and every suite green,
because the arithmetic over whatever figure arrives is still correct. Django's
dependency graph enforces the order; this note exists for the human who is
tempted to squash them.

⚠ **THE PER-SERVICE MINIMUM IS NOT DELETED AS A CAPABILITY.** `BR-RAT-028` mode
(A) still exists, still applies before the plan floor, and `GT-13`/`GT-19` still
describe the same arithmetic — the PO's own reading, recorded in the decision log
of 2026-09-10: *"the per-service minimum still exists and still applies first; it
is READ FROM THE SCHEDULE instead of from the plan."* What moves is the SOURCE.
A lane that reads this file as *minimums are gone* has read it backwards.

**IRREVERSIBLE IN THE ONLY SENSE THAT MATTERS.** The reverse re-adds the column,
nullable, EMPTY. The figures are on the rate schedule versions and are not copied
back — `0030`'s reverse is the one that clears those, and it can only recognise
them while this column still holds the original. So reversing this migration
gives you the column and not the data, and a deployment that reverses BOTH in
order gets its data back. Reverting the CODE alone is the documented rollback
(`22-product-maintenance-process.md` §7) and needs neither.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0030_plan_minimum_moves_to_the_schedule"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="planservice",
            name="minimum_amount",
        ),
    ]

