# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007, as amended by the Product Owner's ruling of 2026-09-07
# Rules:    BR-WRK-058 (two levels; the seeding follows what the utility sells)
#           · BR-TEN-036 (a SEEDED row is deactivatable, never deletable) ·
#           BR-TEN-012 (insert-missing; a tenant-touched row is never
#           overwritten) · CLAUDE.md hard rule 1 (every write under
#           `app.tenant_id` — RLS FORCE is on this table)
# Tests:    06-backend/tests/test_cr070_work_order_type_levels.py
#           (`_retire_tenant` and `_seed_tenant` are driven directly)
# Impacts:  apps/work/models.py (SEED_TYPES, RETIRED_SEED_TYPES)
# ───────────────────────────────────────────────────────
"""work 0023 — the eight flat rows retired, and the PO's list delivered.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

⚠ **THE COLUMN IS `0022` AND THESE TWO CANNOT BE ONE FILE.** Django opens one
schema editor per migration and runs its `deferred_sql` — the FK constraint and
the index for `parent_id` — when that editor CLOSES, after any `RunPython`. Put
them together and real PostgreSQL 16 refuses the whole migration with *"cannot
CREATE INDEX \"work_order_types\" because it has pending trigger events"*, while
the SQLite suite applies it cleanly and every test passes. `0022`'s docstring
carries the full reading; this line exists so a lane tidying the tree does not
merge them back.

WHAT HAPPENS TO THE EIGHT ROWS THAT ARE ALREADY ON LIVE TENANTS
---------------------------------------------------------------
**They are DEACTIVATED. Not deleted, not renamed, not remapped.** Three
reasons, and each on its own is sufficient:

  1. `work_orders.type_id` points at them. Deleting a row a job names either
     fails on the FK or orphans work somebody actually did.
  2. `BR-TEN-036` already rules that a seeded row is deactivatable and never
     deletable, and this table's own handler enforces it. A migration that
     deleted what the API refuses to delete would be a second, contradictory
     statement of the rule.
  3. **REMAPPING WOULD BE A GUESS ABOUT A CUSTOMER'S DATA.** *Meter exchange*
     reads like *Meter Maintenance → Meter Change*; *Read verification* like
     *Reading → Re-read*; *Reconnect after payment* and *Disconnect —
     non-payment* both like *Consumer Services → Disconnection/Reconnection* —
     and *Main repair* and *Move-in activation* read like nothing on the new
     list at all. `US-WRK-007` TC-6 already refuses exactly this move for the
     free-text column, in as many words: matching one name to another *"would
     be a guess about a customer's data"*. Two of the eight cannot be mapped
     even by guessing, which settles it for all eight.

A deactivated row keeps every order that names it, disappears from every
picker, and can be switched back on by a utility that was using it. **Nothing
is lost and nothing is decided on the tenant's behalf.**

⚠ **ONLY A ROW STILL AT ITS SEEDED NAME IS RETIRED.** `is_system` stays True
when a tenant renames a row, so the name is the only evidence that nobody has
adopted it. A utility that renamed *Main repair* to *Watermain break* has made
that row theirs, and this migration leaves it alone and active.

THE EIGHT CODES ARE WRITTEN OUT HERE AND NOT IMPORTED
-----------------------------------------------------
`apps.work.models.RETIRED_SEED_TYPES` says the same thing, and this file does
NOT read it. A migration is a statement about a moment: what it deactivates
must not change because a constant was later edited.

AND THE NEW ROWS ARE IMPORTED, WHICH IS THE OPPOSITE CHOICE ON PURPOSE
----------------------------------------------------------------------
The seeding half reads `apps.work.models.SEED_TYPES` live. Its job is to bring
a tenant provisioned BEFORE today level with one provisioned after, so it must
deliver *the list as it stands* rather than *the list as it stood on
2026-09-07*. If the Product Owner adds a tenth type in December, a host
migrating for the first time in December should receive it — that is the
outcome we want, not a drift to guard against. (`metering/_0031_helpers`
mirrors its constant and equality-tests the mirror; that file's job was to
preserve a tenant's OWN tuned figures, which is a statement about the past, so
the opposite choice was right there.)

RLS, AND WHY EVERY WRITE IS INSIDE A TENANT CONTEXT
----------------------------------------------------
`work_order_types` carries `ENABLE` + `FORCE ROW LEVEL SECURITY` (work/0002),
and `FORCE` applies to the table's OWNER — which is the migration role. So a
bare `objects.create()` here would be REFUSED by the policy rather than
silently mis-scoped. Each tenant is handled under its own `app.tenant_id`, and
the GUC is restored to EXACTLY its arrival state afterwards, which is
`metering/_0031_helpers.run_backfill`'s shape followed rather than re-derived.
`tenants` is RLS-exempt by signed law (B2 §3), so the registry scan itself
needs no context.

On SQLite the loop still runs and simply sets no GUC — the suite builds its
database from empty, so there is no tenant to visit and it does nothing at all.
"""

from django.db import migrations

#: The eight rows this table seeded until 2026-09-07, PINNED — see the
#: docstring. Code and the exact seeded NAME: a row whose name has been edited
#: has been adopted by its tenant and is left active.
RETIRED = (
    ("RECONNECT", "Reconnect after payment"),
    ("MAIN_REPAIR", "Main repair"),
    ("DISCONNECT_NONPAY", "Disconnect — non-payment"),
    ("LEAK_INVESTIGATION", "Leak investigation"),
    ("METER_EXCHANGE", "Meter exchange"),
    ("BACKFLOW_INSPECTION", "Backflow inspection"),
    ("READ_VERIFICATION", "Read verification"),
    ("MOVE_IN_ACTIVATION", "Move-in activation"),
)


def _tenant_entries(apps_registry, tenant_id):
    """The rows THIS tenant should have: the nine types, the eighteen base
    sub-types, and the per-service sub-types for the services it SELLS.

    The service filter IS the ruling (*"a water-only utility gets exactly the
    eighteen and nothing else"*), and it is read here rather than stored: this
    list carries no `service` column, by design.
    """
    from apps.work.models import SEED_TYPES

    TenantService = apps_registry.get_model("tenancy", "TenantService")
    sells = set(
        TenantService.objects.filter(
            tenant_id=tenant_id, enabled=True, service__active=True
        ).values_list("service__code", flat=True)
    )
    return [
        dict(entry)
        for entry in SEED_TYPES
        if not entry.get("service") or entry["service"] in sells
    ]


def _seed_tenant(apps_registry, tenant_id) -> int:
    """Insert-missing, parents first. Returns rows created.

    TWO PASSES, and the order is the whole mechanism: a child's parent must be
    a row before the child can point at it. This duplicates
    `WorkOrderTypeLookupHandler.seed` rather than calling it, which is the
    ordinary migration rule — the handler talks to the LIVE model and this file
    must keep working against the historical one, whatever the model becomes.
    The depth cap is not re-implemented at all: every `parent_code` here names
    an entry of `SEED_TYPE_SPINE`, which has no parent, so no row this file
    writes can be a grandchild.
    """
    WorkOrderType = apps_registry.get_model("work", "WorkOrderType")
    entries = _tenant_entries(apps_registry, tenant_id)
    created = 0
    for wants_parent in (False, True):
        for entry in entries:
            parent_code = str(entry.get("parent_code") or "").strip()
            if bool(parent_code) is not wants_parent:
                continue
            code = str(entry["code"]).strip()
            if WorkOrderType.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
                continue
            parent = None
            if parent_code:
                parent = WorkOrderType.objects.filter(
                    tenant_id=tenant_id, code__iexact=parent_code
                ).first()
                if parent is None:
                    # Cannot happen with the shipped list (pass 1 creates every
                    # spine row first). Skipped rather than crashed if it ever
                    # does: a missing sub-type is recoverable from the repair
                    # door, a failed migration on a live host is not.
                    continue
            WorkOrderType.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=str(entry["name"]).strip(),
                parent=parent,
                is_system=True,
                active=True,
            )
            created += 1
    return created


def _retire_tenant(apps_registry, tenant_id) -> int:
    """Deactivate the eight, where they are still seeded AND still named as
    they were seeded. Returns rows deactivated. Never deletes, never renames."""
    WorkOrderType = apps_registry.get_model("work", "WorkOrderType")
    retired = 0
    for code, seeded_name in RETIRED:
        retired += WorkOrderType.objects.filter(
            tenant_id=tenant_id, code=code, name=seeded_name, is_system=True, active=True
        ).update(active=False)
    return retired


def apply_ruling(apps_registry, schema_editor):
    """Every tenant, each under its own `app.tenant_id`."""
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    seeded = retired = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            retired += _retire_tenant(apps_registry, tenant_id)
            seeded += _seed_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                # Restore EXACTLY the arrival state: a value goes back verbatim;
                # a never-set GUC is RESET.
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"br-wrk-058: {tenants} tenant(s) — {retired} flat type(s) deactivated, "
            f"{seeded} type/sub-type row(s) created"
        )


def undo_ruling(apps_registry, schema_editor):
    """Reverse is a NO-OP on the data, and that is stated rather than silent.

    `0022` drops the column, which is the half a rollback needs: with no
    `parent_id` the sub-types are indistinguishable from types and the
    two-level product cannot run. The ROWS stay. Deleting them would delete
    rows a tenant may have edited and orders may name; re-activating the eight
    would overwrite a decision a utility has since made about them. A rollback
    that leaves extra deactivatable reference rows behind is recoverable by a
    person in one click per row; one that deletes live vocabulary is not.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0022_br_wrk_058_type_levels"),
        # `tenancy.TenantService` — read to decide which service sub-types this
        # tenant receives. Its creation migration, not a recent one: migration
        # ORDERING is a CLAUDE.md 🔒 path, and depending on the latest node of
        # another app couples this file to whichever lane pushed last.
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_ruling, undo_ruling),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 (12-governance/02-decision-log.md, three entries) ·
#         BR-WRK-058 · US-WRK-007
# generated: 2026-09-07 by the BR-WRK-058 two-level work order types lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a (no RLS policy written; the GUC
#         is SET per tenant because the existing policy applies to this writer)
# gates: pytest tests/test_cr070_work_order_type_levels.py · migrate against
#         real PostgreSQL 16 on a database that already holds the eight rows
# exceptions: the data pass duplicates the handler's two-pass seed rather than
#         calling it (historical vs live models — the ordinary migration rule)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
