# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — PO answer (3) of 2026-10-04 (a
#           template task carries an instruction text, shown on the checklist)
#           and PO ruling 6 of 24 Sep (help can be a video LINK, P3.25)
# Rules:    BR-WRK-008 (a job COPIES its template, never links it) · CLAUDE.md
#           🔒 migration ordering
# Tests:    06-backend/tests/test_cr168_srv3_templates.py
# ───────────────────────────────────────────────────────
"""work 0034 — a job's task copy carries the instruction; help gains `link`.

* `work_order_tasks.instruction TEXT NULL` — the template side
  (`wot_tasks.instruction`) is SRV-1's `work/0028`; this is the JOB's copy, so
  the checklist reads what the technician was told when the job was raised and
  a later template edit does not re-word it (`BR-WRK-008`, copy never link).
  No backfill: a job raised before today was raised from tasks that had no
  instruction, and NULL is that fact.
* `ck_wot_help_kind` and `ck_work_order_help_kind` widen from three kinds to
  four: `document · phone · note · link`. ⚠ The blueprint's P3.25 says *"No
  migration"* — true of the screen, false of the database: both CHECKs name the
  three kinds and refuse a fourth.

**Down:** drops the column and restores the three-kind CHECKs. The reverse of
the CHECK change is REFUSED with a count while any help row (template or job)
is a `link`, rather than failing halfway on the constraint.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models

KINDS_BEFORE = ("document", "phone", "note")
KINDS_AFTER = (*KINDS_BEFORE, "link")


def refuse_rollback_over_links(apps, schema_editor):
    stuck = sum(
        apps.get_model("work", name).objects.filter(kind="link").count()
        for name in ("WorkOrderTemplateHelp", "WorkOrderHelp")
    )
    if stuck:
        raise RuntimeError(
            f"refusing to roll back work/0034: {stuck} help row(s) are links. The three-kind "
            "CHECK would refuse them; remove or re-kind those rows first."
        )


class Migration(migrations.Migration):
    dependencies = [("work", "0033_rls_force_bulk_raises")]

    operations = [
        migrations.AddField(
            model_name="workordertask",
            name="instruction",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(model_name="workordertemplatehelp", name="ck_wot_help_kind"),
        migrations.AddConstraint(
            model_name="workordertemplatehelp",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER), name="ck_wot_help_kind"
            ),
        ),
        migrations.RemoveConstraint(model_name="workorderhelp", name="ck_work_order_help_kind"),
        migrations.AddConstraint(
            model_name="workorderhelp",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER), name="ck_work_order_help_kind"
            ),
        ),
        # ⚠ DEF-TEN-9655 (2026-10-04, lane CREWS-2): the refusal is the LAST
        # operation, so it is the FIRST to run on the way back. Django reverses
        # operations; placed first it ran after the narrower CHECK had been
        # restored and the rollback failed on a raw IntegrityError instead of
        # the counted sentence. Forward it is a no-op, so nothing forward moved.
        migrations.RunPython(migrations.RunPython.noop, refuse_rollback_over_links),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (PUT /work/templates/{id}/tasks, help rows) · §16
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
