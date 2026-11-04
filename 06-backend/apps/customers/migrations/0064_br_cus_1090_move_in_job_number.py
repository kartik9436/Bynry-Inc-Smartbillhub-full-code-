"""customers 0064 — a move-in job carries the `MVI-` number a clerk quotes.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list and this file is one. The ledger row is in
`12-governance/09-human-review-ledger.md`; AI-authored under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*) and not
RATIFIED without a recorded sign-off.

`BR-CUS-1090` · `CR-133-BRC07`. PO ruling 2026-09-22, verbatim: *"you would
ahve created a new move In request ID and add all details from servcies request
to it and save it as a draft - do you ahve move in request ID in numbering?"*,
and *"fix all these issues"* over a table whose row 16 reads *A move-in gets
`MVI-…` at creation and its own page*.

The reasoning for the COLUMN is in `apps/customers/move_in_jobs.py` beside the
column it governs, rather than restated here. What belongs in a migration is
what a migration decides, and there are three things.

════════════════════════════════════════════════════════════════════════════
1 · WHY NULLABLE, WHEN THE WHOLE POINT IS THAT EVERY JOB HAS A NUMBER
════════════════════════════════════════════════════════════════════════════
Two reasons, and neither is laziness.

**A tenant with no `move_in` series row gets NULL and a stated reason.**
`moves._allocate_move_no`'s own words: *"A household must not be refused a
move-in because nobody configured numbering. The move is the regulated act; its
reference is not."* A NOT NULL column would turn a missing lookup row into a
refused approval.

**And the rows already on the branch have no number and cannot be given one.**
Every `move_in_jobs` row written between 2026-09-16 and today was raised by an
approval that allocated nothing. **THERE IS NO BACK-FILL AND THAT IS A
DECISION**, the same one `0053` took over the same table: allocating numbers now
would spend a tenant's counter on jobs nobody was ever told a number for, and
would do it inside a migration running under RLS FORCE where the failure mode is
seeing no rows and reporting success. The screen states the absence instead
(`moves.MOVE_NUMBER_UNAVAILABLE['move_in']`), which is what that pair of keys
has always been for.

════════════════════════════════════════════════════════════════════════════
2 · WHY A PARTIAL, CASE-INSENSITIVE UNIQUE — the shape `0030` already chose
════════════════════════════════════════════════════════════════════════════
`uq_move_in_jobs_tenant_move_no_ci` is `uq_move_records_tenant_move_no_ci` one
table over, character for character in its reasoning:

* **partial on `move_no IS NOT NULL`**, because the NULLs of §1 must not collide
  with each other — a tenant with no series would otherwise be able to hold
  exactly one unnumbered job;
* **`LOWER(move_no)`**, because a clerk typing `mvi-26-0115` means the row that
  reads `MVI-26-0115`. That is one number to a person and two to a plain index,
  and `/moves/{ref}` resolves case-insensitively for exactly this reason.

⚠ **IT IS AN IDEMPOTENCY GUARANTEE AND NOT A TIDINESS ONE** (CLAUDE.md hard rule
6). `uq_move_in_jobs_tenant_request` already makes one decision raise one job;
this one makes one number mean one job, which is the guarantee that survives a
future door raising a job by some other route. `move_in_jobs.raise_for_request`
checks the request first so a clerk reads a sentence rather than a stack trace —
both are kept, because a check without the constraint is a race and a constraint
without the check is a traceback.

⚠ **IT DOES NOT — AND CANNOT — SPAN `move_records` AND `wizard_parks`.**
PostgreSQL has no unique index across three tables, so the fact that one move-in
carries ONE number through all three is held by the code path
(`BR-CUS-1090`'s chain: allocate at approval → carry into the park → adopt at
the commit) and by `test_br_cus_1090_move_in_job_number.py`, not by this index.
**Saying so out loud is the point** — a comment claiming a guarantee is not the
guarantee (hard-won law 1), and the guarantee here is narrower than the rule.

════════════════════════════════════════════════════════════════════════════
3 · RLS
════════════════════════════════════════════════════════════════════════════
Untouched, deliberately. `move_in_jobs_tenant_isolation` was created by `0053`
with `ENABLE` and `FORCE`, and adding a column to a table does not disturb a
policy. There is nothing to re-apply and re-applying it would be a second
spelling of one policy, free to drift from the first.

**Rollback (change-process step 8):** reverses cleanly — the index drops and the
column drops, and `move_in_jobs` returns to exactly what `0053` created. Nothing
else reads the column: `move_records` and `wizard_parks` are untouched by this
migration in both directions. **What does NOT roll back is the counter** —
numbers issued to jobs are spent — and `BR-TEN-035` already permits that gap and
prefers it to a number issued twice.
"""

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0063_def_cus_6179_document_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="moveinjob",
            name="move_no",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="moveinjob",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("move_no"),
                condition=models.Q(("move_no__isnull", False)),
                name="uq_move_in_jobs_tenant_move_no_ci",
            ),
        ),
    ]
