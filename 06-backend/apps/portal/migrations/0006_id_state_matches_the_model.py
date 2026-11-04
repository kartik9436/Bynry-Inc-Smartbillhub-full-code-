# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) · US-CWP-014 — housekeeping on the two
#           tables those stories added.
# Rules:    CLAUDE.md hard-won law 1 (a state Django disagrees with is a claim,
#           not a guarantee) · migration ordering is a 🔒 sensitive path
# Tests:    `manage.py makemigrations --check --dry-run` finds nothing to make
#           for `portal` — which is the whole assertion.
# Impacts:  nothing at run time; no SQL is issued.
# ───────────────────────────────────────────────────────
"""portal 0006 — the recorded id field now matches the model (DEF-CWP-3711).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHAT WAS WRONG, AND WHY IT IS WORTH A MIGRATION
------------------------------------------------
`portal 0003` wrote its two primary keys as `("id", uuid7_pk())` — the same
helper the models use, which reads well and is exactly the trap. Inside a
`CreateModel`, Django writes a primary key with `serialize=False`; the helper
returns the field with `serialize` at its default. **`serialize` produces no
SQL at all** — it governs `dumpdata`/`loaddata` and nothing else — so the
database is correct and has always been correct.

**The cost is entirely to the next person.** `manage.py migrate` ended with:

    Your models in app(s): 'portal' have changes that are not yet reflected in
    a migration, and so won't be applied.

on a clean checkout, for a difference that is not a difference. A lane that
meets that line has to prove it is harmless before it can trust anything else
it is told about migrations, and a lane that does not read it carefully makes a
schema migration out of it.

This aligns the recorded state and issues NO database operation — it is
`SeparateDatabaseAndState` with an empty database half, so that the absence of
SQL is a statement in the file rather than something a reader has to infer.
"""

import core.dbfields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_consent_not_future_by_the_wall_clock"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="portalapplicationdraft",
                    name="id",
                    field=models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="portalconsent",
                    name="id",
                    field=models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-013@6725ba9b · US-CWP-014@6725ba9b (EP-CWP-04)
# generated: 2026-09-04 by the CR-068 wave C build lane, from DEF-CWP-3711
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · `makemigrations --check --dry-run` clean on portal · migrate on PostgreSQL 16 and on the SQLite suite
# exceptions: none — this migration issues no SQL by construction
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
