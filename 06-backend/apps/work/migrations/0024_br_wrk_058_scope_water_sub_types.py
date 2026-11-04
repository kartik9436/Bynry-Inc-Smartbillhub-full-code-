# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007, as amended twice by the Product Owner on 2026-09-07
# Rules:    BR-WRK-058 (a sub-type follows its service) · BR-TEN-036 (a SEEDED
#           row is deactivatable, never deletable) · CLAUDE.md hard rule 1
#           (every write under `app.tenant_id`) · hard-won law 4 (a change that
#           does not reach an already-deployed host must SAY SO — or reach it)
# Tests:    06-backend/tests/test_cr070_work_order_type_levels.py
# ───────────────────────────────────────────────────────
"""work 0024 — the water sub-types taken back off a utility that sells no water.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY THIS EXISTS AT ALL — A TWO-HOUR WINDOW, AND THE HABIT IT COMES FROM
-----------------------------------------------------------------------
`work/0023` delivered the Product Owner's list to every existing tenant this
morning, and at that moment the eighteen sub-types they had given us carried no
service tag: every utility received all eighteen, whatever it sold. **That was
seeded exactly as ruled and it was the right call** — carving the PO's own list
up on a lane's judgment is the mistake the decision log of that day exists to
avoid. Hours later the PO answered the question it raised: *"gas onlyutility
carry only gas meters"*. The eighteen are water's.

`models.SEED_TYPES` now says so, so every tenant provisioned from here on is
correct and `0023` on a host that has not yet migrated is correct too. **The
hosts that migrated inside that window are not**, and nothing else would ever
put them right: the seeder is insert-missing by design and has no retraction
path, the reference sweep only ever adds, and a version bump adds nothing here.

Hard-won law 4's shape: a change that cannot reach an already-deployed host must
SAY SO. It is cheap to reach them, so this reaches them.

WHAT IT DOES, AND THE THREE THINGS IT REFUSES TO DO
----------------------------------------------------
For each tenant, it **DEACTIVATES** — never deletes — a sub-type that is

  * still `is_system` and still carrying its SEEDED NAME (a row a utility has
    RENAMED is one they have made their own, exactly as `0023` treats the eight
    retired types), and
  * tagged `water` in `models.SEED_TYPES`, and
  * on a tenant with no ENABLED water service.

**It does not delete.** `work_orders.type_id` can point at any of them and
`BR-TEN-036` forbids deleting a seeded row; a deactivated row keeps every job
that names it and is one click from coming back.

**It does not touch any other service's rows.** A tenant that enabled gas, took
gas's four and later switched gas off keeps them. That is a different question
from the one the PO answered and nobody has asked it — narrowing this migration
to water is what keeps it a correction rather than a new rule.

**It does not run on a tenant that sells water**, which is every tenant the
eighteen were written for.

⚠ **AND IT IS DELIBERATELY NOT IDEMPOTENT-BY-LATCH.** It has no run row and no
guard beyond the conditions above, because those conditions are self-limiting: a
second run finds every affected row already inactive and updates nothing. The
count it prints on a replay is therefore 0, which is what `BR-TEN-010` asks a
replay to look like.

RLS
---
`work_order_types` carries ENABLE + FORCE (work/0002) and FORCE binds the
migration role, so every tenant is visited under its own `app.tenant_id` and the
GUC is restored to exactly its arrival state — `metering/_0031_helpers.
run_backfill`'s shape, followed rather than re-derived. On SQLite the loop runs
and sets no GUC; the suite builds from empty, so it visits no tenant at all.
"""

from django.db import migrations


def _water_codes():
    """The sub-type codes tagged `water`, read LIVE from the seed constant.

    Live rather than pinned, and the opposite choice from `0023`'s eight: what
    that file deactivates is a historical fact about a superseded list, while
    this one asks *"which rows does this product consider water's"* — a
    question whose answer should move if `OQ-WRK-1764` later makes some of them
    common. A host migrating after that ruling should retract the narrower set,
    not the set as it stood today.
    """
    from apps.work.models import SEED_TYPES

    return {
        str(entry["code"]).strip(): str(entry["name"]).strip()
        for entry in SEED_TYPES
        if entry.get("service") == "water"
    }


def _retract_tenant(apps_registry, tenant_id) -> int:
    WorkOrderType = apps_registry.get_model("work", "WorkOrderType")
    TenantService = apps_registry.get_model("tenancy", "TenantService")
    sells_water = TenantService.objects.filter(
        tenant_id=tenant_id, enabled=True, service__code="water", service__active=True
    ).exists()
    if sells_water:
        return 0
    retracted = 0
    for code, seeded_name in _water_codes().items():
        retracted += WorkOrderType.objects.filter(
            tenant_id=tenant_id, code=code, name=seeded_name, is_system=True, active=True
        ).update(active=False)
    return retracted


def apply_ruling(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    retracted = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            retracted += _retract_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"br-wrk-058 scoping: {tenants} tenant(s) — {retracted} water sub-type(s) "
            "deactivated on utilities that sell no water"
        )


def undo_ruling(apps_registry, schema_editor):
    """A NO-OP, and stated rather than silent.

    Reversing would mean re-activating rows, and this migration cannot tell a
    row it deactivated from one a utility deactivated themselves the same day.
    Re-activating both would overwrite somebody's decision to satisfy a
    rollback; leaving them off costs one click per row to a person who wants
    them back. The rows are all still there either way.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0023_br_wrk_058_retire_and_seed"),
        # `tenancy.TenantService` — read to ask whether this utility sells
        # water. Its creation migration, not a recent one: migration ORDERING
        # is a 🔒 path and depending on another app's latest node couples this
        # file to whichever lane pushed last.
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_ruling, undo_ruling),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 ("TWO PO RULINGS ON WORK ORDER TYPES") · BR-WRK-058
# generated: 2026-09-07 by the BR-WRK-058 two-level work order types lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a (no RLS policy written; the GUC is
#         SET per tenant because the existing policy binds this writer)
# gates: pytest tests/test_cr070_work_order_type_levels.py · makemigrations
#         --check --dry-run · migrate against real PostgreSQL 16
# exceptions: reads `SEED_TYPES` live rather than pinning it — argued in
#         `_water_codes`, and the opposite choice from 0023's pinned eight
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
