# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-039 (EP-RBS-05) — CR-075 wave T: the place a tenant's INPUT
#           VALUES are kept. `DEF-RBS-4338` is the finding this closes — a
#           signed rule said a utility sets a runbook's inputs and there was
#           nowhere to save one.
# Rules:    BR-RBS-042 (a tenant sets input values and nothing else; *all* is
#           stored as the WORD and resolved at run start) · BR-RBS-038 (every
#           edit makes a new version) · BR-RBS-036 (an edited Action is dry-run
#           only until one clean dry run is reviewed) · CLAUDE.md hard rule 1
#           (tenant scoping; RLS FORCE) · NFR-5 (no hard caps)
# Tests:    06-backend/tests/test_us_rbs_039_inputs.py (the column, the
#           validation and the run-start expansion, on SQLite) ·
#           06-backend/tests/test_us_rbs_039_pg.py (RLS and the aborted-
#           transaction case — PostgreSQL only, and it SKIPS rather than
#           passing vacuously)
# Impacts:  apps/runbooks/models.py · apps/runbooks/services.py ·
#           apps/runbooks/selectors.py · apps/runbooks/api.py
# ───────────────────────────────────────────────────────
"""runbooks 0004 — ONE column: what this tenant set its inputs to.

HUMAN-OWNED (**migration ordering** is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md.

WHAT IT ADDS, IN ONE SENTENCE
-----------------------------
`runbooks.parameters` — a `jsonb` document, `{}` by default, holding the input
values a utility chose: `{"services": "all", "past_due_more_than": "5.0000"}`.
**A parameter name that is absent means *the declared default*.** Nothing is
backfilled and no existing row changes behaviour: every runbook in every tenant
starts with an empty document and runs exactly what it ran yesterday.

WHY A COLUMN ON `runbooks` AND NOT A TABLE OF ITS OWN
------------------------------------------------------
This was the wave's one real schema decision and the reasoning is recorded in
`12-governance/02-decision-log.md`, 2026-09-07, rather than left to be inferred:

1. **It is the TENANT's half of the runbook, and that half already exists.**
   `cap`, `cron`, `gate_mode`, `timezone` and `visible_to_roles` are columns on
   this table for exactly the same reason, and `services.settings_document()` is
   the ONE function that copies them into a version document. Adding this to
   `EDITABLE_SETTINGS` means the version document, the edit allow-list and the
   Activity tab all learn about input values in the same commit and cannot
   drift — which is what that function's own docstring says it exists for.
2. **`BR-RBS-038` and `BR-RBS-036` then come for free, and they are the wave's
   own acceptance.** An input change writes a version, shows on the Activity
   tab, and moves `current_version` past `trusted_version` — so an edited Action
   is dry-run only until one clean dry run is reviewed, with no new code and no
   second place for the ratchet to be got wrong.
3. **A separate table could not be pinned by a run.** `runbook_runs.version`
   points at a `runbook_versions` row and that row IS what the run used. Input
   values living outside the version document would mean a past run could not
   say what it ran with — and `runbook_versions` is append-only by trigger
   (`0003`), so the pin is a fact about the database rather than a convention.
4. **A row-per-parameter table would need its own RLS policy, its own
   uniqueness and its own cascade**, to hold at most a handful of rows per
   runbook that are only ever read and written together, as one document.

⚠ **AND THE COST IS STATED, BECAUSE THERE IS ONE.** `jsonb` cannot hold a value
to its type: no `NUMERIC(18,4)` on a money input, no foreign key on a service
code. Hard rule 2 and `BR-RBS-042`'s domains are therefore
`services._validated_parameters`' to keep, exactly as `contract.Parameter`
already keeps a money default off a float — `03-field-map.md` D-3 records this
as the standing consequence of parameters living in a document at all, and this
column inherits it rather than introducing it.

RLS, AND WHY THIS MIGRATION ADDS NO POLICY
-------------------------------------------
`runbooks` already carries its policy and `FORCE` from `0002_rls_force`. A
policy is per TABLE, not per column, so a new column on a protected table is
protected the moment it exists. **Nothing here weakens that and nothing here
needs to restate it** — a second policy would be a second description of one
guarantee, which is how two descriptions come to disagree.

ORDERING
--------
After `0003`, which is this module's own head, and it depends on nothing outside
`runbooks`. There is no data migration, no backfill and no reordering of
anything already applied: a `jsonb` column with a constant default is a metadata
change on PostgreSQL 16 and takes no table rewrite and no long lock, so it is
safe against a live table of any size (`NFR-5` — no ceiling is assumed anywhere).

⚠ **THE REVERSE IS A DATA LOSS AND IT IS SAID PLAINLY.** `RemoveField` drops
every tenant's input choices. It is lawful because nothing has been written to
this column before this migration exists; **after a tenant has set an input, a
reverse is a decision a person takes, not a rollback that costs nothing.**
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("runbooks", "0003_cr075_wave_e_definition_surface"),
    ]

    operations = [
        migrations.AddField(
            model_name="runbook",
            name="parameters",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
