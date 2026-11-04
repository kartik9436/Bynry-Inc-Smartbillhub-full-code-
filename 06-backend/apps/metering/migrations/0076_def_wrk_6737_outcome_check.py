# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-6737 — `work_orders.outcome` had no CHECK, and live data held
#           `completed` (a STATE word) on 1 of 39 rows
# Change:   CR-168-BRC10 (lane FIN-S, final round)
# Rules:    B18 §8.3 (the five outcomes) · CLAUDE.md hard rule 1 (every write
#           under `app.tenant_id`) · hard rule 7 (the cleared value is audited) ·
#           hard-won law 4 (a change that does not reach an already-deployed
#           host must reach it — this runs on every host that migrates)
# Tests:    06-backend/tests/test_def_wrk_6737_outcome_check_pg.py
# ───────────────────────────────────────────────────────
"""metering 0076 — `work_orders.outcome` is one of the five, or empty.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt` guards
every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-05 (`CR-168-BRC10`, lane FIN-S)
under the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*). Its row is in `12-governance/09-human-review-ledger.md`; not RATIFIED
without a recorded sign-off.

WHAT IT DOES
------------
1. **Clears an outcome that is not one of B18 §8.3's five** — sets it NULL, one
   `audit_log` row per order naming the value it held (`work_order.outcome_cleared`,
   `before = {"outcome": "completed"}`). Measured on the clone the defect was
   filed from: **1 row of 39**, `completed`.
2. **Adds `ck_work_orders_outcome`**: `outcome IS NULL OR outcome IN (the five)`.

THE DATA DECISION, AND WHY IT IS NULL
-------------------------------------
The register put three readings to whoever fixes this: a mis-set state to be
corrected, a sixth outcome to be declared, or a row to be nulled. **NULL is the
only one that invents nothing.** `completed` is `WO_COMPLETED` from the sibling
STATE vocabulary — the row's `state` column already says the job is completed,
so the word carries no fact the row does not hold elsewhere. Mapping it to
`passed` would assert a result nobody recorded; declaring a sixth outcome would
widen a signed list to fit one bad write. An empty outcome reads as *we cannot
say*, which is true. Decision log, 2026-10-05.

⚠ **THE OLD VALUE THEN LIVES ONLY IN `audit_log`**, which has one retention
rule and no exempt row type (`OQ-1340`, PO 2026-09-23). Nothing here claims it
is kept for ever.

RLS
---
`work_orders` carries ENABLE + FORCE, which binds the migration role, so every
tenant is visited under its own `app.tenant_id` and the GUC is restored to its
arrival state (`work/0026`'s shape). On SQLite the loop runs and sets no GUC.

ROLLBACK
--------
`migrate metering 0075` drops the constraint. The cleared values are NOT put
back (the reverse is a no-op, stated): the audit rows say what they were.
"""

from __future__ import annotations

from django.db import migrations, models

OUTCOMES: tuple[str, ...] = (
    "passed",
    "failed",
    "partially_done",
    "cancelled",
    "waiting_on_someone_else",
)


def _set_tenant(connection, tenant_id) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def clear_outside_values(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    WorkOrder = apps_registry.get_model("metering", "WorkOrder")
    AuditLog = apps_registry.get_model("audit", "AuditLog")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    cleared = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            _set_tenant(connection, tenant_id)
            rows = list(
                WorkOrder.objects.filter(tenant_id=tenant_id, outcome__isnull=False)
                .exclude(outcome__in=OUTCOMES)
                .values_list("id", "outcome", "order_no")
            )
            for order_id, outcome, order_no in rows:
                AuditLog.objects.create(
                    tenant_id=tenant_id,
                    actor_user_id=None,  # an unnamed system job (BR-AUD-003)
                    action="work_order.outcome_cleared",
                    entity_type="work_order",
                    entity_id=order_id,
                    before={"outcome": outcome},
                    after={
                        "outcome": None,
                        "order_no": order_no,
                        "by": "metering/0076 (DEF-WRK-6737)",
                    },
                )
            if rows:
                WorkOrder.objects.filter(
                    tenant_id=tenant_id, id__in=[row[0] for row in rows]
                ).update(outcome=None)
            cleared += len(rows)
        if is_postgres:
            # ⚠ `work_orders` carries DEFERRED constraint triggers, so the
            # UPDATE above leaves pending trigger events and the ALTER TABLE
            # this migration's next operation issues would be refused —
            # *"cannot ALTER TABLE because it has pending trigger events"*,
            # measured. Firing them now, inside the same transaction, is what
            # lets both operations share one atomic migration.
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])
    if cleared:
        print(f"def-wrk-6737: {cleared} work order outcome(s) outside the five cleared")


def keep_cleared(apps_registry, schema_editor):
    """A NO-OP, stated: the audit rows say what each cleared outcome was."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0075_def_cus_9631_disconnect_source"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_outside_values, keep_cleared),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=models.Q(outcome__isnull=True) | models.Q(outcome__in=OUTCOMES),
                name="ck_work_orders_outcome",
            ),
        ),
    ]
