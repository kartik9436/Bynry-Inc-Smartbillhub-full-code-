"""assets 0011 — the two lifecycle stages the Product Owner shortened.

PO ruling 2026-09-07, verbatim: *"use only Inventory and Installed"*.
`Inventory/Spare` becomes **Inventory** and `Installed/Active` becomes
**Installed**. Needs repair, In repair and Retired are untouched, no code moves,
no row is added or removed.

HUMAN-OWNED (CLAUDE.md 🔒 "migration ordering"). HUMAN-REVIEW-PENDING —
AI-authored under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*), implementing a ruling made in plain words on a screen the
PO was reading. Row in 12-governance/09-human-review-ledger.md.

⚠ **WHY A MIGRATION AND NOT ONLY A FIXTURE EDIT.** Reference seeding is
insert-if-absent BY CODE (BR-TEN-071): a tenant provisioned yesterday already
holds a row with code `inventory`, so every future seed run — a replay, a
version bump, the `--tenant` repair door — finds it present and writes nothing.
**No fixture bump can ever change a NAME on a tenant that already exists.** That
is the same asymmetry V2.48.0.8 recorded from the other direction for a row the
PO REMOVED, and it is why the decision-log entry for this ruling says in so many
words that whoever takes it *"must decide and state whether live rows are
migrated"*. They are, and this is the statement.

⚠ **IT RENAMES ONLY A ROW WHOSE NAME IS STILL BYTE-IDENTICAL TO THE SUPERSEDED
SEEDED STRING.** BR-AST-031 says the tenant *"may rename and add stages"*, and
BR-TEN-012 says a tenant-touched row is never overwritten — and there is no
touch-tracking column anywhere that can tell a pristine seeded row from an
edited one. So the CONTENT is the only evidence available and it is used as the
whole test: a row still reading `Inventory/Spare` was written by the seeder and
nobody has touched it; a row reading anything else is somebody's own word for
their own process and is left exactly alone. `is_system` is checked too, so a
tenant who deleted the seeded row and typed the same name back as their own is
also left alone.

⚠ **IT IS REVERSIBLE, AND THE REVERSE IS NARROW IN THE SAME WAY** — it puts the
long names back only on rows this migration would itself have written. A tenant
who renames a stage to `Inventory` AFTER this runs keeps that name through a
rollback, because the reverse checks `is_system` and the exact new string and
cannot tell those two apart any better than the forward pass can. Stated rather
than hidden: the pair is as symmetrical as the available evidence allows and no
more.

⚠ **NOTHING IN THE PRODUCT BRANCHES ON EITHER STRING.** BR-AST-031 gives every
stage a `behavior_class` (available | in_service | out_of_service | terminal)
*"so list filters and billing/rating logic stay sound regardless of tenant
labels"*, and every seeded row is resolved by CODE (`assets.services
.stage_by_code`). This migration therefore changes what is PRINTED and nothing
else — which is exactly what the ruling asked for.
"""

import logging

from django.db import migrations

logger = logging.getLogger("smartbillhub.assets")

#: (code, the superseded seeded name, the ruled name). Duplicated here rather
#: than imported from `apps.assets.services` for the reason assets/0003 already
#: gives: a migration must keep working when the service's constants later
#: change. Both copies carry the same ruled values; if they ever diverge, the
#: ruling is the tiebreaker and not either copy.
RENAMES: tuple[tuple[str, str, str], ...] = (
    ("inventory", "Inventory/Spare", "Inventory"),
    ("active", "Installed/Active", "Installed"),
)

#: The nil sentinel, never `''` — assets/0003's own note (OQ-354, PO ruling
#: 2026-08-24, option A) explains at length why the empty string poisons every
#: later migration in the same `migrate` run. Castable, matches nothing.
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


def _rename(apps, connection, pairs):
    """One UPDATE per (tenant, stage), narrowed by code AND by the exact name we
    are replacing AND by `is_system`.

    ⚠ **EACH TENANT IS ITS OWN SAVEPOINT (CLAUDE.md hard-won law 14).** On
    PostgreSQL a single failed statement aborts the WHOLE transaction, so one
    tenant whose row cannot be updated would take every other tenant's rename
    with it and the whole `migrate` would roll back. The test suite runs on
    in-memory sqlite, which has no aborted-transaction state, so the version
    without this is green everywhere and fails the first time a real row
    refuses. The savepoint is not the tidy option here, it is the only one —
    do not "simplify" it away.
    """
    from django.db import transaction

    Stage = apps.get_model("assets", "AssetLifecycleStage")
    renamed = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        for code, was, now in pairs:
            try:
                with transaction.atomic():
                    renamed += Stage.objects.filter(
                        tenant_id=tenant_id, code=code, name=was, is_system=True
                    ).update(name=now)
            except Exception:  # pragma: no cover — reported, never swallowed silently
                logger.exception(
                    "assets 0011: tenant %s stage %r could not be renamed from %r to %r; "
                    "every other tenant is unaffected (per-tenant savepoint)",
                    tenant_id,
                    code,
                    was,
                    now,
                )
    _leave_tenant(connection)
    logger.info("assets 0011: renamed %d lifecycle-stage row(s) (PO ruling 2026-09-07)", renamed)


def shorten_stage_names(apps, schema_editor):
    _rename(apps, schema_editor.connection, RENAMES)


def restore_stage_names(apps, schema_editor):
    _rename(
        apps,
        schema_editor.connection,
        tuple((code, now, was) for code, was, now in RENAMES),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0010_br_ast_500_size_class"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(shorten_stage_names, restore_stage_names),
    ]
