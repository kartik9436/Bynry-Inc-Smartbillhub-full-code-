# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007, as amended by the PO ruling of 2026-09-07 evening
# Defect:   DEF-WRK-4512 — `work/0024` switches OFF eleven rows the PO has
#           since ruled common to every utility
# Rules:    BR-WRK-058 (a sub-type follows its service) · BR-TEN-036 (a SEEDED
#           row is deactivatable, never deletable) · BR-TEN-012 (insert-missing
#           — a utility's own decision is never undone) · CLAUDE.md hard rule 1
#           (every write under `app.tenant_id`) · hard-won law 4 (a change that
#           does not reach an already-deployed host must SAY SO — or reach it)
# Tests:    06-backend/tests/test_cr070_work_order_type_levels.py
# ───────────────────────────────────────────────────────
"""work 0026 — the eleven service-neutral sub-types come back, on every utility.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT THIS UNDOES, AND WHY THE FILE IT UNDOES WAS NOT WRONG
------------------------------------------------------------
`work/0023` gave every tenant the PO's eighteen sub-types. Hours later the PO
said *"gas onlyutility carry only gas meters"*, the eighteen became WATER's, and
`work/0024` deactivated them on every utility that sells no water — 17 off, 1
left alone because it had been renamed, **0 deleted**. That was correct on the
reading it was given.

**The same evening the PO gave a different reading**, and it is the one that
stands: asked whether *Billing Issues*, *Meter Change*, *Re-read*, *Connection*
and the rest are common to every utility, they answered *"yes that is correct;
but we will ahve to see which Utility service they do"*. So **eleven of those
seventeen must come back on**, and `models.SEED_TYPES` no longer tags them.

⚠ **THE ONLY REASON THIS IS RECOVERABLE AT ALL IS THAT `0024` DEACTIVATED
RATHER THAN DELETED**, and that was a judgment its author made rather than a
rule they were given. Worth saying out loud: had it deleted, `work_orders.
type_id` would have been orphaned or the delete refused, and the rows a utility
had already renamed would be gone. **The general lesson is `BR-TEN-036`'s: a
seeded row is deactivatable, never deletable — and a "correction" is exactly
the moment somebody reaches for a delete.**

WHAT IT DOES, AND THE TWO THINGS IT REFUSES TO DO
---------------------------------------------------
For each tenant, it **RE-ACTIVATES** a sub-type that is

  * one of the ELEVEN below, and
  * still `is_system` and still carrying its SEEDED NAME, and
  * currently inactive.

**It does not touch a row a utility RENAMED.** `0023` and `0024` both take a
renamed row as one the utility has made their own, and so does this: the name
test is what separates *"we switched this off"* from *"we turned this into
something else"*.

**It does not create anything.** A tenant provisioned after this ruling gets the
eleven from `SEED_TYPES` through the ordinary seeder; a tenant that never had
them (there is none — `0023` gave all eighteen to everybody) would need the
reference sweep, not a migration.

⚠ **AND IT IS NOT THE MIRROR OF `0024`'s `undo_ruling`, WHICH DELIBERATELY DOES
NOTHING.** That function refuses to reverse because it *"cannot tell a row it
deactivated from one a utility deactivated themselves the same day"* — a true
statement about a blind rollback of ALL EIGHTEEN. This is not blind: it names
ELEVEN specific codes that a PO ruling has since made common, so the set is
decided by the ruling rather than by guessing what `0024` touched. The other
seven stay exactly as `0024` left them.

⚠ **THE RISK THAT REMAINS, NAMED RATHER THAN HIDDEN:** a utility that sells no
water and had ALREADY deactivated one of these eleven themselves, by hand,
between `0023` and now, gets it switched back on. The window is one day, the row
is one click from off again, and the alternative — leaving eleven rows off on
every non-water utility for ever — is the failure this file exists to fix.

⚠ **IT IS DELIBERATELY NOT IDEMPOTENT-BY-LATCH.** A second run finds every
affected row already active and updates nothing, so a replay prints 0, which is
what `BR-TEN-010` asks a replay to look like.

RLS
---
`work_order_types` carries ENABLE + FORCE (work/0002) and FORCE binds the
migration role, so every tenant is visited under its own `app.tenant_id` and the
GUC is restored to exactly its arrival state — `work/0024`'s shape, followed
rather than re-derived. On SQLite the loop runs and sets no GUC.
"""

from django.db import migrations

#: **THE ELEVEN, PINNED HERE AND NOT READ FROM `SEED_TYPES`.**
#:
#: `0024` reads the tag LIVE and argues for it: it asks *"which rows does this
#: product consider water's"*, an answer that should move. **This file asks a
#: different question — *"which rows did the PO rule common on 2026-09-07"* —
#: and that is a historical fact that must NOT move.** If `OQ-WRK-1764` later
#: scopes `METER_CHANGE` and `RE_READ` to the metered services, a host migrating
#: afterwards must still restore what THIS ruling restored and then let the
#: later one narrow it; a live read would silently skip the rows the newer
#: ruling had re-tagged, and the two corrections would fight each other on
#: whichever host happened to migrate in between. Pinned, with the same
#: reasoning `0023` gives for pinning its eight.
COMMON_SUB_TYPES: tuple[tuple[str, str], ...] = (
    ("BILLING_ISSUES", "Billing Issues"),
    ("METER_CHANGE", "Meter Change"),
    ("METER_DISPOSE", "Meter Dispose"),
    ("METER_REPLACEMENT", "Meter Replacement"),
    ("ROUTINE_INSPECTION", "Routine Inspection"),
    ("DISCONNECT_RECONNECT", "Disconnection/Reconnection"),
    ("RE_READ", "Re-read"),
    ("NEW_CONN_SURVEY", "Survey for New Connection"),
    ("RESIDENTIAL_CONN", "Residential Connection"),
    ("COMMERCIAL_CONN", "Commercial Connection"),
    ("INDUSTRIAL_CONN", "Industrial Connection"),
)


def _restore_tenant(apps_registry, tenant_id) -> int:
    WorkOrderType = apps_registry.get_model("work", "WorkOrderType")
    restored = 0
    for code, seeded_name in COMMON_SUB_TYPES:
        restored += WorkOrderType.objects.filter(
            tenant_id=tenant_id,
            code=code,
            name=seeded_name,
            is_system=True,
            active=False,
        ).update(active=True)
    return restored


def apply_ruling(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    restored = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            restored += _restore_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"br-wrk-058 common sub-types: {tenants} tenant(s) — {restored} row(s) "
            "switched back on (DEF-WRK-4512)"
        )


def undo_ruling(apps_registry, schema_editor):
    """A NO-OP, and stated rather than silent — `0024`'s own reasoning.

    Reversing would mean deactivating these eleven again, and by then this
    migration cannot tell a row IT re-activated from one a utility switched on
    themselves. Turning both off would overwrite somebody's decision to satisfy
    a rollback. The rows are all still there either way.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0025_cr070_workforce_is_sample"),
        # `tenancy.Tenant` — the loop's subject. Its creation migration, not a
        # recent one: migration ORDERING is a 🔒 path and depending on another
        # app's latest node couples this file to whichever lane pushed last.
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_ruling, undo_ruling),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 evening ("TWO MORE PO RULINGS ON WORK ORDER
#         TYPES") · BR-WRK-058 · DEF-WRK-4512
# generated: 2026-09-07 by the CR-070 work sample-data lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a (no RLS policy written; the
#         GUC is SET per tenant because the existing policy binds this writer)
# gates: pytest tests/test_cr070_work_order_type_levels.py · makemigrations
#         --check --dry-run · migrate against real PostgreSQL 16
# exceptions: PINS the eleven rather than reading SEED_TYPES live — the opposite
#         choice from 0024, argued at COMMON_SUB_TYPES
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
