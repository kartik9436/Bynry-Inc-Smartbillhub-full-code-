"""customers 0027 — STATE ONLY for the unmanaged `Transfer` model (DEF-801).

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, and the ledger row for this file is in
`12-governance/09-human-review-ledger.md`. ⚠ The marker is here because the
PATH is the category, not because the body is large: this migration's whole
body is one `CreateModel` with `managed = False`. DEF-808 is the gate gap that
observation comes from — G7 reads a small body as stub-only — and the answer to
it is that a migration's risk is WHICH TABLE IT TOUCHES AND WHEN IT RUNS.

⚠ **THIS MIGRATION CREATES NO TABLE.** `managed = False` in the options below
is what says so: the `transfers` DDL — columns, indexes, RLS policy — is
`0021_cr030_w7_transfers.py`'s and stays there, and the introspection test
`tests/test_w7_transfers.py::test_tc_trf_12_*` still holds the model and that
DDL together. All this migration does is put the model into migration STATE so
the autodetector stops proposing it.

**Why it is needed now, when 0021 deliberately left it out.** 0021's docstring
records a measured reading: Django imports `apps/customers/models.py` and
nothing else, so a model defined in `transfers.py` is invisible to the
autodetector, and a `CreateModel` would have left state holding a model the app
registry lacks — answered with a `DeleteModel`. That was true when it was
written. It stopped being true silently, because an import graph is not a
decision anybody makes: `config/urls.py` imports `apps/customers/api.py`, which
imports `move_reads.py` (CR-038 W9), which imports `transfers`. `makemigrations`
runs the system checks, the checks load the URLconf, and by the time the
autodetector runs the model IS registered — with no state. `--check` answered
`+ Create model Transfer` and went red.

**Both halves land together, and that is the point.** `apps/customers/models.py`
now carries `from apps.customers import transfers` at its foot — the line 0021
itself named as the one that retires its workaround, and the same line
`models.py` already carries for `disconnects` and `apps/rating/models.py` for
`discounts.py`. With the import DELIBERATE the registration no longer depends
on whether some unrelated module happens to import `move_reads`, and with this
migration the state matches it.

**Measured, both halves, because a claim about a guard is worth nothing
un-run (hard-won law 7).** Delete THIS FILE and `--check` goes red at once —
`+ Create model Transfer`, verified 2026-08-26. Delete the `models.py` import
and it stays GREEN today, because `move_reads` is still importing `transfers`
through the URLconf; that line is therefore not what makes the check pass now,
it is what stops the check flipping red the day somebody untangles that chain.
Saying it "would go red" would have been the comment-claiming-a-guarantee this
repo has been bitten by (hard-won law 1), so it is written down as what it is.
"""

import core.dbfields
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0026_cr038_w9_final_read_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transfer",
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
                ("to_unit_id", models.UUIDField(null=True)),
                ("out_date", models.DateField(null=True)),
                ("in_date", models.DateField(null=True)),
                ("step", models.SmallIntegerField(default=1)),
                ("state", models.TextField(default="scheduled")),
                ("deposit_carry_elected", models.BooleanField(null=True)),
                ("arrears_follow_elected", models.BooleanField(null=True)),
                ("money_decided_at", models.DateTimeField(null=True)),
                ("committed_at", models.DateTimeField(null=True)),
                ("cancelled_at", models.DateTimeField(null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "db_table": "transfers",
                "managed": False,
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-801 (12-governance/10-defect-log.csv) + migration 0021's own
#         docstring, which NAMED the retirement this file performs — not a
#         story packet, because no story owns a repair to a gate. ⚠ G1 wants
#         `US-XXX-###@<hex>` and this line cannot honestly supply one; see
#         DEF-810, which records that the packet grammar has no form for
#         CR- or DEF-driven work and that 277 files are in this position.
# generated: 2026-08-26 by the CR-038/CR-039 merge lane, closing DEF-801
# checklist: A✔ B=n/a(no service half — this migration adds STATE and nothing
#         calls it) C=n/a D=n/a E=n/a(no frontend half) F✔ G✔
#         H=PENDING(🔒 migration ordering — ledger row written the same day)
# gates: `makemigrations --check --dry-run` → "No changes detected", which is
#         the whole point of the file — it was `+ Create model Transfer` before
#         it existed. PROVEN RED by deleting this file and re-running (hard-won
#         law 7). ⚠ The `models.py` half does NOT go red on its own today and
#         the docstring above says so rather than claiming a guarantee it does
#         not give. NO POSTGRES IN THIS CONTAINER; `managed = False` means the
#         migration issues no DDL at all, so there is nothing a live database
#         would prove that sqlite does not.
# exceptions: this migration creates NO TABLE — the `transfers` DDL is still
#         migration 0021's and the introspection test still holds the model and
#         that DDL together. A future lane that drops `managed = False` would
#         make this file try to CREATE a table that already exists and break a
#         fresh-database build; that is the one thing a reviewer should check.
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
