# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-038 · US-RBS-040 (EP-RBS-01) — CR-075 wave E tasks E1/E2 and
#           wave D task D5: the columns the definition surface needs, and the
#           append-only guarantee `runbook_versions` claimed and did not have.
# Rules:    BR-RBS-038 (every edit makes a new version; a run pins the version
#           that produced it and its stored plan and report NEVER change) ·
#           BR-RBS-036 (an edited Action is dry-run only until one clean dry run
#           is reviewed) · BR-RBS-024 clause 2 / RB-050 (role visibility
#           defaults from the category, widenable per runbook by an admin) ·
#           DEF-RBS-4285 (the Activity tab draws a change summary no column
#           held) · CLAUDE.md hard rule 4's SHAPE (a record of the past is not
#           edited in place; a correction is a new row)
# Tests:    06-backend/tests/test_us_rbs_038_definition_surface.py (the columns
#           and the service behaviour, on SQLite) ·
#           06-backend/tests/test_us_rbs_038_pg.py (the trigger — PostgreSQL
#           only, and it SKIPS rather than passing vacuously)
# Impacts:  apps/runbooks/models.py · apps/runbooks/services.py ·
#           apps/runbooks/selectors.py · apps/runbooks/api.py
# ───────────────────────────────────────────────────────
"""runbooks 0003 — three columns, and the trigger that makes a version immutable.

HUMAN-OWNED (**migration ordering** is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md.

WHY A TRIGGER AND NOT A SERVICE RULE
------------------------------------
`RunbookVersion`'s own docstring already claims the guarantee: *"An immutable
snapshot of the definition… a run stores the version it used, so a later edit
never rewrites history."* **Nothing enforced it.** A `.save()`, a
`.update()` on a queryset, a management command, a data fix or a migration all
reach the table directly, and hard-won law 1 is exactly this — *a comment
claiming a guarantee is not the guarantee*. `apps/billing/0002` records the same
reasoning for issued invoices and is the precedent this follows.

So: **no UPDATE and no DELETE on `runbook_versions`, ever, by anybody.** There
is no narrow door of the kind `invoices` needs, because a version has no
lifecycle — it is written once and read for ever. A correction is a NEW version,
which is `BR-RBS-038` word for word.

⚠ **THE DELETE HALF IS NARROWER THAN THE OBVIOUS ONE, AND THE OBVIOUS ONE WAS
WRITTEN FIRST AND PROVED WRONG ON THE LIVE CLUSTER.** The first draft refused a
DELETE *while the parent runbook still exists*, reasoning that a `CASCADE` from a
deleted runbook is a teardown rather than a rewrite. **On PostgreSQL that
sentence is true and on Django it is useless**, because `on_delete=CASCADE` is
emulated in Python: Django deletes the CHILD rows first, in their own statement,
**while the parent is still there** — so the guard fired on exactly the teardown
it was written to allow, and `Runbook.objects.delete()` answered

    ERROR: update or delete on table "runbooks" violates foreign key constraint
           "runbook_versions_runbook_id_..." — Key is still referenced

That is hard-won law 7's second habit — *ask what would make this check fail
wrongly* — answered by running it rather than by reading it.

**So the rule is stated as what it actually protects: a version A RUN HAS
PINNED.** `BR-RBS-038` is *a run pins the version that produced it and its
stored plan and report never change*; a version no run ever pinned is not
history anybody reads. And it costs nothing, because `RunbookRun.runbook` is
`on_delete=PROTECT`: a runbook with runs cannot be deleted at all, so this
refusal can never be the thing standing in front of a legitimate teardown.

WHAT THE THREE COLUMNS ARE FOR — each is read by code in the same commit
------------------------------------------------------------------------
* `runbooks.visible_to_roles` — `RB-050`. NULL = the category decides
  (`models.ROLE_VISIBILITY_BY_CATEGORY`); a list = an admin's own answer for
  this runbook. Read by `selectors.catalogue_page` and `templates_page`,
  written by `PUT /runbooks/{key}`.
* `runbooks.trusted_version` — `BR-RBS-036`, the trust ratchet. The version
  whose dry run has been reviewed. Read by `services.open_run`, written by
  `services.add_template`, `clone_runbook` and `update_runbook`.
* `runbook_versions.summary` — `DEF-RBS-4285`. A list of `{field, from, to}`
  facts, never an English sentence, so `RBS-004.7` can say *Cap raised to 400*
  in eleven languages. Written by every version writer, read by
  `selectors.runbook_activity`.

WHY THIS FILE IS 🔒 — AND THE FIRST DRAFT OF THIS PARAGRAPH SAID THE OPPOSITE
------------------------------------------------------------------------------
⚠ **THIS PARAGRAPH READ *"WHY THIS FILE IS NOT 🔒 HUMAN-OWNED"* AND IT WAS
WRONG, WHICH IS WORTH LEAVING ON THE RECORD.** It argued that
`10-scripts/gates/human_owned.txt` carries `06-backend/**/migrations/*rls*` for
migrations *"and nothing broader"* — a claim about a guard, made by reading the
first lines of its list rather than by RUNNING it. The list also carries
**`06-backend/apps/*/migrations/0*.py` — "Migration ordering — 🔒"**, which is
CLAUDE.md's sensitive-paths line word for word, and it matches EVERY migration
in the product including this one. `G07` said so in one line the moment it was
run: *"holds real logic without HUMAN-REVIEW-PENDING marker … no row in the
human-review ledger"*.

Hard-won law 1 exactly — a comment claiming a guarantee is not the guarantee —
and the general form is the more useful one: **a paragraph asserting that a
guard does not apply is a claim the guard itself can settle in one command, so
settle it there.** The correction costs three lines and a ledger row; shipping
the claim would have cost a merge-blocking red for whoever ran the suite next.

What it actually is: three `AddField`s, one `AlterField` that adds `choices` to
an existing column, and one PostgreSQL trigger. It lays no RLS policy (0002 did,
and it IS marked), touches no rating math, composes no idempotency key, posts no
ledger line, rounds no money and holds no webhook key — **and it is 🔒 anyway,
because migration ORDERING is its own listed hazard and every migration carries
it.**

⚠ **SQLITE GETS THE COLUMNS AND NOT THE TRIGGER.** `config/settings/test.py`
hardcodes in-memory SQLite (hard-won law 14), so the append-only half is proved
in `tests/test_us_rbs_038_pg.py` under the non-superuser probe role on real
PostgreSQL, and it SKIPS on the default suite rather than passing vacuously —
`G5` once ran the isolation suite on SQLite and called 192 skips a pass. The
service layer refuses the same edits in Python, so the default suite proves the
rule and PostgreSQL proves the floor under it.

PROVED RED BEFORE GREEN (hard-won law 7), on the live cluster:
    UPDATE runbook_versions SET definition = '{}'::jsonb WHERE version = 1;
without the trigger → `UPDATE 1`; with it → the exception below, naming
`BR-RBS-038`. Both runs are quoted in the wave E walkthrough.
"""

from django.db import migrations, models

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION runbook_version_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    -- Refused when a RUN PINNED this version. Django emulates CASCADE by
    -- deleting children first, so "while the runbook exists" would fire on
    -- every legitimate teardown; and RunbookRun.runbook is PROTECT, so a
    -- runbook with runs cannot be torn down anyway. This wording therefore
    -- refuses exactly the rewrite of history and nothing else.
    IF EXISTS (
      SELECT 1 FROM runbook_runs
       WHERE runbook_id = OLD.runbook_id AND version = OLD.version
    ) THEN
      RAISE EXCEPTION 'BR-RBS-038: runbook version %% cannot be deleted — a run pinned it. Its stored plan and report never change; a correction is a NEW version.',
        OLD.version;
    END IF;
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'BR-RBS-038: runbook version %% cannot be updated. A run pins the version that produced it and its stored definition never changes; edit the runbook and a new version is written.',
    OLD.version;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_runbook_version_append_only ON runbook_versions;
CREATE TRIGGER trg_runbook_version_append_only
  BEFORE UPDATE OR DELETE ON runbook_versions
  FOR EACH ROW EXECUTE FUNCTION runbook_version_append_only();
"""

APPEND_ONLY_DROP_SQL = """
DROP TRIGGER IF EXISTS trg_runbook_version_append_only ON runbook_versions;
DROP FUNCTION IF EXISTS runbook_version_append_only();
"""


def apply_trigger(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(APPEND_ONLY_SQL)


def drop_trigger(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(APPEND_ONLY_DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("runbooks", "0002_rls_force"),
    ]

    operations = [
        migrations.AddField(
            model_name="runbook",
            name="visible_to_roles",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="runbook",
            name="trusted_version",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="runbookversion",
            name="summary",
            field=models.JSONField(blank=True, default=list),
        ),
        # `BR-RBS-041` gave `gate_mode` its two values (`approve_each_run` ·
        # `approved_up_front`) and the column had no `choices` at all, so
        # `PUT /runbooks/{key}` had no vocabulary to validate a gate against.
        # A `choices` change is metadata on PostgreSQL — no table rewrite — and
        # the validation that matters is `services._validated_setting`; this
        # keeps the model and the migration state in step so
        # `makemigrations --check` stays quiet for the next lane.
        migrations.AlterField(
            model_name="runbook",
            name="gate_mode",
            field=models.TextField(
                choices=[
                    ("approve_each_run", "approve_each_run"),
                    ("approved_up_front", "approved_up_front"),
                ],
                default="approve_each_run",
            ),
        ),
        migrations.RunPython(apply_trigger, drop_trigger),
    ]
