# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — two PO answers of 2026-10-21 (decision log
#           *"Field app: ten PO answers"*, answers 9 and 11)
# Rules:    BR-WRK-034 (the push on assignment) · BR-FLD-00028 (R28 — an
#           emergency is acknowledged within five minutes) · BR-WRK-050 (a
#           report is frozen; a correction is the next version beside it) ·
#           BR-TEN-012 (a utility's own answer is never overwritten) ·
#           CLAUDE.md hard rules 1 and 4
# Tests:    06-backend/tests/test_cr187_priority_push.py ·
#           tests/test_cr187_order_reopen.py · tests/test_cr187_priority_push_pg.py
# ───────────────────────────────────────────────────────
"""work 0045 — a priority says how an assignment rings; a report has versions.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Not RATIFIED without a
recorded sign-off.

⚠ **NUMBERED 0045 AFTER `0044_cr187_device_registration`. ANOTHER LANE MAY ALSO
TAKE 0045** — whichever lands second renumbers and re-points its dependency;
neither operation here depends on anything another 0045 could add.

1. `work_priorities.push_kind` (PO answer 9: *"yes"* — a job may be pushed as
   urgent or emergency AUTOMATICALLY). Our judgment for HOW, recorded in the
   decision log the same day: a tenant setting per priority, seeded so the
   tenant's MOST URGENT ACTIVE priority (lowest `rank`) pushes as `emergency`,
   the next as `urgent_assignment`, the rest as `new_job`. The column is new,
   so the backfill overwrites no utility's answer (BR-TEN-012); an inactive
   priority keeps `new_job`. A CHECK holds the three tokens.
   ⚠ **AND THE PO CORRECTED ANSWER 9 THE SAME DAY: IT IS AN OPTION.**
   `work_settings.push_by_priority` switches the mapping on; it is seeded OFF
   for EVERY tenant (column default, and a tenant with no row reads OFF), so
   until a utility turns it on only a dispatcher's explicit choice sends
   urgent or emergency. The mapping is seeded anyway, ready for the day a
   utility turns it on.
2. `work_order_cost_lines.report_version` (PO answer 11: *"yes"* — the office
   may reopen an ACCEPTED job). The next acceptance writes `-v2` with its own
   lines beside `-v1`'s, so each line says which version it adds up to. Every
   existing line is `v1`'s — the only version that could exist before today —
   and that is the column DEFAULT: `ADD COLUMN … DEFAULT 1` fills the rows
   without an UPDATE, so `work/0011`'s freeze trigger (BEFORE UPDATE OR DELETE)
   never fires and no frozen row is rewritten.

RLS: `work_priorities` carries ENABLE + FORCE, so each tenant is visited under
its own `app.tenant_id` and the GUC is restored to its arrival state —
`work/0027`'s shape, followed rather than re-derived.
"""

from django.db import migrations, models

#: The seeded mapping by POSITION among a tenant's active priorities, most
#: urgent first. Pinned here (not read from `models.SEED_PRIORITIES`) so a later
#: change to the seed never re-applies itself under this migration's name.
BY_POSITION: tuple[str, ...] = ("emergency", "urgent_assignment")


def _apply_tenant(apps_registry, tenant_id) -> int:
    WorkPriority = apps_registry.get_model("work", "WorkPriority")
    ids = list(
        WorkPriority.objects.filter(tenant_id=tenant_id, active=True)
        .order_by("rank", "id")
        .values_list("id", flat=True)[: len(BY_POSITION)]
    )
    written = 0
    for priority_id, kind in zip(ids, BY_POSITION):
        written += WorkPriority.objects.filter(pk=priority_id).update(push_kind=kind)
    return written


def seed_push_kinds(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    written = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            written += _apply_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"cr187 priority push kinds: {tenants} tenant(s) — {written} priority(ies) "
            "set to emergency / urgent_assignment (PO answer 9, 2026-10-21)"
        )


def undo(apps_registry, schema_editor):
    """Nothing to undo row by row: reversing the AddField drops the column."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0044_cr187_device_registration"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="workpriority",
            name="push_kind",
            field=models.TextField(default="new_job"),
        ),
        migrations.AddConstraint(
            model_name="workpriority",
            constraint=models.CheckConstraint(
                condition=models.Q(push_kind__in=("new_job", "urgent_assignment", "emergency")),
                name="ck_work_priorities_push_kind",
            ),
        ),
        migrations.RunPython(seed_push_kinds, undo),
        migrations.AddField(
            model_name="worksettings",
            name="push_by_priority",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="workordercostline",
            name="report_version",
            field=models.IntegerField(default=1),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-10-21 "Field app: ten PO answers" (9, 11) · BR-WRK-034 · BR-WRK-050
# generated: 2026-10-21 by the CR-187-BRC10 PO-answers lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H✔(🔒 migration ordering — HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · pytest tests/test_cr187_priority_push*.py on SQLite and PostgreSQL 16
# exceptions: none
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
