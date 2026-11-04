"""metering 0048 — the templates table becomes the HEADER OF A BUNDLE.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`CR-070` wave D task D1 · `US-WRK-013` · `BR-WRK-010` · `BR-WRK-012` ·
`BR-WRK-013` · `03-field-map.md` §3 rows 22–25, 27.

WHY A METERING MIGRATION IN A WORK WAVE
---------------------------------------
The same reading `metering/0045` records: `work_order_templates` is METERING's
table today, Work owns it by the ruling of 2026-09-03, and `03-field-map.md` §4
records the choice of HOW to move it as PENDING the blueprint's §16 — a section
this repo has never been able to read (the 16.3 MB PDF is over the download cap
and is not in the tree at all). Wave D does not move it either: eight NEW
tables land in `work/0003`, and five columns on an OLD one land here.

⚠ **THE KEY CHANGE IS THE WHOLE POINT OF THE WAVE, AND IT IS NOT THE KEY THE
RULE NAMES.**
`uq(tenant, service, sequence)` is dropped. It is the blueprint's structural
blocker for templates: a utility that wants *New connection* AND *Leak
investigation* for Water cannot have both, because the second has to take a
number in a list that is about the order of a CONNECTION.

`BR-WRK-010` (status PROPOSED) and `US-WRK-013` TC-2 name the replacement as
`(tenant, name, version)`. **Measured against the 24 CONFIRMED seeded starters
(`BR-WRK-013`, `apps/metering/sample_data.py:1889`), that key cannot be created
at all:**

    Meter set            × 4   electric · water · gas · thermal heat
    Inspection           × 3   gas · solar · thermal heat
    Service connection   × 2   thermal heat · fire

A tenant-wide name key refuses the seeder on a fresh database and refuses this
migration on any database that has run it. The rule's stated PURPOSE — *"a
utility holds New connection and Leak investigation for Water at once"* — is
met exactly by **`(tenant, service, name, version)`**, and TC-2's refusal (a
second *Leak investigation* v1 for the same service) still refuses. Recorded as
a judgment, with these three figures, in the decision log of 2026-09-05.

⚠ **`skill` IS DROPPED AND `skill_id` REPLACES IT — AND THE MIGRATION REFUSES
RATHER THAN GUESSES.** `03-field-map.md` §3 row 22 says *replacing*, not
*beside*, and `US-WRK-013` TC-3 says the free text goes *"only after a summary
shows zero non-null values"*. Nothing in this product has ever written that
column — the seeder does not set it and no service exists to — so on every
database in existence the summary is zero. `_refuse_if_skill_written` below IS
that summary, run as a migration step: if a row anywhere carries a non-null
`skill`, the migration STOPS with the count in the message instead of deleting
a utility's typed words. That is wave C's posture for `type` reached by a
different road: wave C kept the free text because orders carry it and matching
it would be guessing; here there is nothing to match.

RLS: `work_order_templates` already carries ENABLE + FORCE from `metering/0026`.
A policy is on the TABLE and not on its columns, so adding or dropping one
changes nothing about it — and `tests/test_us_wrk_rls_pg.py` re-reads
`pg_class` rather than trusting that any migration ran.

⚠ **`version` DEFAULTS TO 0 AND 0 IS A DRAFT, NOT A VERSION** (`BR-WRK-011`:
publish is the one write). The 24 starters land on 0 and read as *Draft* on
`Work-013` until `US-WRK-019` republishes them through the service in wave E —
which is honest rather than a regression: they carry no bundle, no
`template_no`, and nothing in this product has ever raised an order from one.
"""

import django.db.models.deletion
from django.db import migrations, models


def _refuse_if_skill_written(apps, schema_editor):
    """`US-WRK-013` TC-3's summary, as a migration step that can say no."""
    template = apps.get_model("metering", "WorkOrderTemplate")
    written = template.objects.exclude(skill__isnull=True).exclude(skill="").count()
    if written:
        raise RuntimeError(
            f"{written} work_order_templates row(s) carry a free-text skill. "
            "metering/0048 replaces that column with skill_id and will not "
            "discard typed words — file the rows, map them to work_skills, "
            "then re-run (US-WRK-013 TC-3)."
        )


def _noop(apps, schema_editor):
    """Reversing drops nothing, so there is nothing to check on the way back."""


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0047_rls_interruptions"),
        ("tenancy", "0038_rls_cr068_d_published_content"),
        ("work", "0002_rls_force"),
    ]

    operations = [
        # ⚠ THE OLD KEY GOES FIRST. Dropping it before the new one is added is
        # not tidiness: `(tenant, service, sequence)` and the seeded rows are
        # compatible with the new key, but a database part-way through a
        # rename would otherwise briefly hold two unique keys over the same
        # rows for no reason.
        migrations.RemoveConstraint(
            model_name="workordertemplate",
            name="uq_work_order_templates_seq",
        ),
        migrations.RunPython(_refuse_if_skill_written, _noop),
        # REMOVE + ADD, never AlterField. `makemigrations` offers an
        # `AlterField` here because the model attribute keeps its name, and it
        # would emit `ALTER COLUMN skill TYPE uuid USING skill::uuid` — which
        # on PostgreSQL is a cast error on any non-empty value and a silent
        # column swap on an empty one. The two operations say what is
        # happening: a text column is dropped, a foreign key is added.
        migrations.RemoveField(model_name="workordertemplate", name="skill"),
        migrations.AddField(
            model_name="workordertemplate",
            name="skill",
            field=models.ForeignKey(
                blank=True,
                db_column="skill_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="templates",
                to="work.workskill",
            ),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="safety_kit",
            field=models.ForeignKey(
                blank=True,
                db_column="safety_kit_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="templates",
                to="work.worksafetykit",
            ),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="crew_size",
            field=models.SmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="version",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="no_gate_reason",
            field=models.TextField(blank=True, null=True),
        ),
        # `US-WRK-018` — WHICH VERSION an order was raised from. NULL on every
        # order that predates it and on every ad-hoc order, and stamped once at
        # the raise thereafter (`BR-WRK-008`: copy, never link). Nothing
        # backfills it: an order raised in January was raised from whatever the
        # template said in January, and this product cannot know what that was.
        migrations.AddField(
            model_name="workorder",
            name="template_version",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="workordertemplate",
            constraint=models.UniqueConstraint(
                fields=("tenant", "service", "name", "version"),
                name="uq_work_order_templates_name_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="workordertemplate",
            constraint=models.CheckConstraint(
                condition=models.Q(("crew_size__gte", 1)),
                name="ck_work_order_templates_crew_size",
            ),
        ),
    ]
