"""metering 0063 — hard rule 6 reaches the New Connect commit (`DEF-CUS-8021`).

HUMAN-OWNED (migration ordering AND idempotency keys are both CLAUDE.md 🔒
paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-29 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

──────────────────────────────────────────────────────────────────────────────
WHAT WAS MEASURED, AND WHY THIS IS A MIGRATION RATHER THAN A CODE CHANGE
──────────────────────────────────────────────────────────────────────────────
On 2026-09-29 the identical New Connect payload was posted TWICE, with the
parcel box EMPTY, against real PostgreSQL. Both presses answered **200**:

    CON-26-0130   and   CON-26-0131

— two connections, two customers, two master accounts, two properties at one
address, and **two payments of $250.00, each posting its own balanced ledger
pair.** CLAUDE.md hard rule 6 requires idempotency on this path and it did not
hold.

⚠ **THE PARCEL NUMBER WAS HIDING IT, AND THAT IS WHY THIS MIGRATION EXISTS
RATHER THAN A TEST ALONE.** With a parcel typed, the second press is refused
`409 premises.external_ref_taken` — which is a UNIQUENESS CONSTRAINT on a
different column, refusing by accident of a different rule. It fires only on
the minority of builds that type a parcel, and it answers an ERROR where rule 6
asks for the FIRST RESULT. The first walk of this check PASSED for exactly that
reason. **The idempotency test in `tests/test_def_cus_8021_commit_once.py`
therefore runs with NO parcel number**, by name, in its own docstring.

──────────────────────────────────────────────────────────────────────────────
TWO COLUMNS AND ONE PARTIAL UNIQUE INDEX
──────────────────────────────────────────────────────────────────────────────
  * `connections.commit_key` — `core.idempotency.new_connect_commit_key`'s
    string, `"new-connect|<the wizard's per-build submit token>"`. The shape is
    argued in that function's docstring and is not restated here.
  * `connections.commit_result` — the FIRST press's whole answer, returned
    verbatim to the second. Rule 6 asks for the first result and not for an
    error, and the commit's answer is not re-derivable: `manifest` counts what
    THAT press MADE, and a recount later answers what EXISTS, which stops being
    the same fact the moment anybody adds a unit. `bill_runs` is the precedent
    — its replay returns the persisted RUN ROW — and a persisted response is
    the same move for a door whose answer no table already holds.
  * `uq_connections_commit_key` — `UNIQUE (tenant_id, commit_key)` WHERE
    `commit_key IS NOT NULL`. This is the layer that actually ensures the
    guarantee; the lookup in `commit_new_connect` is the ordinary path and this
    is what holds when two presses race past it in the same millisecond.

⚠ **PARTIAL ON PURPOSE, AND IT IS THE REASON THIS MIGRATION NEEDS NO BACKFILL.**
Every connection already in the product has `commit_key` NULL, and two NULLs are
not a duplicate of each other in PostgreSQL — so the index is satisfied by every
existing row and by every future caller that sends no token (the seeder, the
tests, an approval raising a draft). Adding the column NOT NULL, or the index
total, would have required inventing a key for 130 historical builds that were
never protected by one.

⚠ **THE TENANT IS THE FIRST COLUMN AND IS NOT IN THE KEY STRING**, the same
split `bill_runs` and `payments.webhook_key` already use: the same fact in two
places is a fact that can drift, and a token a clerk at one utility invents can
therefore never reach another utility's build (BR-TEN-003, hard rule 1).

──────────────────────────────────────────────────────────────────────────────
REVERSIBLE, AND PROVED SO
──────────────────────────────────────────────────────────────────────────────
`AddField`'s reverse is `RemoveField` and `AddConstraint`'s is
`RemoveConstraint`; `migrate metering 0062` and back to `0063` were both run
against real PostgreSQL 16 and both applied cleanly. Nothing is backfilled, so
the down migration loses only keys written after it was applied.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0062_def_met_6881_work_orders_raised"),
    ]

    operations = [
        migrations.AddField(
            model_name="connection",
            name="commit_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connection",
            name="commit_result",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="connection",
            constraint=models.UniqueConstraint(
                condition=Q(commit_key__isnull=False),
                fields=("tenant", "commit_key"),
                name="uq_connections_commit_key",
            ),
        ),
    ]
