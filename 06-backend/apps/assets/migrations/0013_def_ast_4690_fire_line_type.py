"""assets 0013 — the fire service line, on the tenants that already existed.

`DEF-AST-4690` · `CR-089` wave C task `C5` (`PUJ-15`).

`CR-063` (PO 2026-09-02, verbatim: *"We will need Fire as utility Service -
Capacity based - this will behave exactly like trash"*, and *"we need it for one
of the customer we want to go live"*) made fire the eleventh utility service and
`OQ-1361`'s build appended `fire_line` to `services.SEED_ASSET_TYPES` as the
THIRTEENTH asset type. **A fixture reaches new tenants only.** Measured on the
development estate on 2026-09-09, with `app.tenant_id` set per tenant:

    brazosbend           2 meters · 1 sub-meter · 10 behind the meter · fire yes
    oak-ridge            2 meters · 1 sub-meter ·  9 behind the meter · fire NO
    silver-creek-water2  2 meters · 1 sub-meter ·  9 behind the meter · fire NO
    (the other seven)    2 meters · 1 sub-meter · 10 behind the meter · fire yes

A tenant without the type **cannot tag a fire line at all** — no asset can be
created against a type row that is not there — so a utility being onboarded onto
fire has service points nothing can stand on. That is the defect.

⚠ **WHY A MIGRATION WHEN `ensure_reference_catalogs()` IS `get_or_create` BY
CODE, WHICH LOOKS LIKE IT WOULD HEAL THIS ON ITS OWN.** It would, eventually,
and that is precisely the problem: it runs LAZILY, off whatever request happens
to touch it, so the row's arrival is a side effect of unrelated traffic. That is
how `brazosbend` came to hold the row on 2026-09-08 while two siblings still do
not — same code, same fixture, three different catalogues, and no screen
anywhere says which. `assets/0011` recorded the same asymmetry from the other
direction, and its statement holds here: whoever takes a reference-data change
*"must decide and state whether live rows are migrated"*. They are, and this is
the statement. After this runs, every tenant in the database holds the row on
the same day rather than on the day somebody happened to open the right screen.

⚠ **UNCONDITIONAL, AND NOT NARROWED TO TENANTS THAT SELL FIRE.** `CR-089`'s task
line reads *"seeded for every tenant that sells fire"*, and the seeded catalogue
this backfill is catching up to is not service-gated: every tenant already holds
`pv`, `ev_charger` and `container_cart` whether or not it sells solar, EV or
trash, because an asset TYPE is a vocabulary and not a product decision. Gating
on the enabled services would (a) make the catalogue's size depend on the
service list, which no other type does, and (b) re-open this very defect the
first time a utility enables fire, since nothing would run again. A superset of
what the task asks for, chosen deliberately and stated here.

⚠ **INSERT-IF-ABSENT, BY CODE, AND NOTHING ELSE.** A tenant that already holds a
`fire_line` row is left exactly alone — its name, category, `active` and
`is_system` are untouched, whether the row came from the fixture or from a
utility that typed its own. `BR-TEN-012` (a tenant-touched row is never
overwritten) and `BR-TEN-036` (seeded rows are deactivatable, never deletable)
both hold: a tenant that has DEACTIVATED its fire type keeps it deactivated,
because the row exists and this migration only ever creates.

⚠ **THE REVERSE DELETES ONLY WHAT THE FORWARD PASS WOULD HAVE WRITTEN** — a
`fire_line` row that is `is_system`, still byte-identical to the seeded name,
still in the seeded category, and **with no asset standing on it**. An asset
against the type is the evidence that a utility has started using it, and a
rollback that took the type would take the assets' `PROTECT`ed parent with it;
it refuses instead, per tenant, and says so in the log.

HUMAN-OWNED (CLAUDE.md 🔒 "migration ordering"). HUMAN-REVIEW-PENDING —
AI-authored under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Row in `12-governance/09-human-review-ledger.md`.
"""

import logging

from django.db import migrations

logger = logging.getLogger("smartbillhub.assets")

#: The row, duplicated here rather than imported from `apps.assets.services` for
#: the reason `assets/0003` and `assets/0011` both give: a migration must keep
#: working when the service's constants later change. `CR-063` is the tiebreaker
#: if the two ever diverge.
FIRE_CODE = "fire_line"
FIRE_NAME = "Fire service line"
FIRE_CATEGORY = "behind_the_meter"

#: The nil sentinel, never `''` — `assets/0003`'s note (`OQ-354`, PO ruling
#: 2026-08-24, option A) explains why the empty string poisons every later
#: migration in the same `migrate` run. Castable, matches nothing.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (db/rls_tenancy_w0.sql), so it
    can be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1: never touch a tenant table without
    `app.tenant_id` set. On sqlite there is no RLS and no `set_config` —
    skipped honestly, and the same ORM path runs."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def add_fire_line_type(apps, schema_editor):
    """One insert-if-absent per tenant, each in its own SAVEPOINT.

    ⚠ **EACH TENANT IS ITS OWN SAVEPOINT (CLAUDE.md hard-won law 14).** On
    PostgreSQL a single failed statement aborts the WHOLE transaction, so one
    tenant whose insert is refused — a utility that typed its own row with a
    clashing case-insensitive code, which `uq_asset_types_tenant_code_ci`
    refuses — would take every other tenant's row with it and roll the whole
    `migrate` back. The suite runs on in-memory sqlite, which has NO
    aborted-transaction state, so the version without this is green on every
    machine and fails the first time a real row refuses. The savepoint is not
    the tidy option, it is the only one — do not "simplify" it away.
    """
    from django.db import transaction

    connection = schema_editor.connection
    AssetType = apps.get_model("assets", "AssetType")
    added = 0
    present = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                _, created = AssetType.objects.get_or_create(
                    tenant_id=tenant_id,
                    code=FIRE_CODE,
                    defaults={
                        "name": FIRE_NAME,
                        "category": FIRE_CATEGORY,
                        "is_system": True,
                        "active": True,
                    },
                )
            added += int(created)
            present += int(not created)
        except Exception:  # pragma: no cover — reported, never swallowed silently
            logger.exception(
                "assets 0013: tenant %s could not be given the %r asset type; "
                "every other tenant is unaffected (per-tenant savepoint)",
                tenant_id,
                FIRE_CODE,
            )
    _leave_tenant(connection)
    logger.info(
        "assets 0013: %d tenant(s) gained the fire service line, %d already had it "
        "(DEF-AST-4690 · CR-063)",
        added,
        present,
    )


def remove_fire_line_type(apps, schema_editor):
    """Narrow, and it REFUSES where the type is in use — see the module note."""
    from django.db import transaction

    connection = schema_editor.connection
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")
    removed = 0
    kept = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        rows = AssetType.objects.filter(
            tenant_id=tenant_id,
            code=FIRE_CODE,
            name=FIRE_NAME,
            category=FIRE_CATEGORY,
            is_system=True,
        )
        for row in rows:
            if Asset.objects.filter(tenant_id=tenant_id, type_id=row.id).exists():
                # A utility has started tagging fire lines. The type is theirs
                # now; a rollback does not take it, and it does not take their
                # assets with it either.
                kept += 1
                continue
            try:
                with transaction.atomic():
                    removed += AssetType.objects.filter(id=row.id).delete()[0]
            except Exception:  # pragma: no cover
                logger.exception(
                    "assets 0013 (reverse): tenant %s kept its %r asset type",
                    tenant_id,
                    FIRE_CODE,
                )
                kept += 1
    _leave_tenant(connection)
    logger.info(
        "assets 0013 (reverse): removed %d unused fire service line row(s), kept %d in use",
        removed,
        kept,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0012_cpb10_maintained_by"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_fire_line_type, remove_fire_line_type),
    ]
