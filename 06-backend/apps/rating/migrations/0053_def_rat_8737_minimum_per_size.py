# ── Trace ──────────────────────────────────────────────
# Change:   DEF-RAT-8737 · PO ruling 2026-10-01, decision log "RATE SCHEDULES:
#           THE MINIMUM IS SET PER METER SIZE AND BILLING CHARGES IT; THE
#           PER-VERSION MINIMUM RATE ON THIS VERSION IS REMOVED" (option A) ·
#           CR-157-BRC10
# Rules:    BR-RAT-028 mode (A) (AMENDED again — the source moves from the
#           version to the size row, the arithmetic does not) · CLAUDE.md hard
#           rule 1 · hard rule 2 · law 14
# Tests:    06-backend/tests/test_def_rat_8737_minimum_per_size.py
# ───────────────────────────────────────────────────────
"""rating 0053 — each version's minimum MOVES onto that version's size rows.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-01 under the PO ruling of
2026-08-09. Row *"2026-10-01 · MINIMUM PER METER SIZE"* in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

**THE RULING, verbatim (PO, 2026-10-01):** *"The question: should a service's
minimum charge be set per meter size or once for the whole schedule? Or should
rate schedules have no minimum at all? A · Minimum per size - this is
correct"*. From that day billing reads the per-size minimum
(`rating.selectors._size_minimum`) and no longer reads
`tariff_versions.minimum_bill` at all.

⚠ **THIS MIGRATION IS THE SAFETY STEP, AND WITHOUT IT A REAL BILL LOSES ITS
FLOOR.** On the shipped fixture the `$15.00` residential water minimum (WE-3)
lives on the VERSION and every one of that version's size rows says *no
minimum* (`sample_data.sample_size_rows` writes `size_class` only). Ship the
code without this and a `0.4 kgal` household prices `$9.60` and stops there,
`$5.40` short every month, with every check green.

**WHAT IT DOES, per tenant, per version that states a minimum:**

  * every size row of that version that states NO minimum gets the version's
    figure — so a schedule that floored every size before floors every size it
    names after;
  * a size row that already states its OWN figure is left alone — a human
    typed that one (and it was never billed, which is the defect); where it
    DISAGREES with the version's it is counted and named, never reconciled;
  * the version's own figure is then cleared, because the ruling removes it
    and a figure nothing bills must not go on being shown as if it did;
  * ⚠ **EXCEPT where the version has NO size rows at all.** There is nowhere
    to put the figure, so it is LEFT on the version — unbilled, but stored —
    and listed by name. That stored column IS the clerk's list (a version with
    `minimum_bill` set after this migration is exactly a figure that had
    nowhere to go), which the ruling allows: *"migrated to every size row that
    has none … or listed for the clerk; the build decides which and records
    it"*.

**HOW TO KNOW IT WORKED, AND IT IS NOT THE `OK`:** it prints, per tenant, the
versions that stated a minimum, the size rows it filled, the rows that already
stated a different figure, and the versions it could not place. A migration
whose only output is `OK` cannot tell 12 rows from 0.

⚠ **IT WALKS THE TENANTS AND SETS `app.tenant_id` (hard rule 1;
`DEF-RAT-4620` is what skipping it looks like)** — both tables carry `FORCE ROW
LEVEL SECURITY`, so without it every row is invisible and the update matches
nothing and prints nothing wrong. **Per-tenant savepoint (law 14):** on
PostgreSQL one failed statement aborts the whole transaction; the suite's
sqlite has no such state, so the version without the savepoint is green
everywhere and fails the first time a real row refuses.

**REVERSIBLE, and honest about what it cannot restore.** Rows it filled are
not recorded across a `migrate` boundary, so the reverse restores a version's
figure only where that version's figure is empty and EVERY one of its size
rows states one and the same amount — exactly the set this pass produces from
a version whose rows had no figures of their own. It does not empty any size
row. A schedule whose clerk typed one figure on every size by hand is
indistinguishable from that, and the reverse would restore it too; that is
stated, and harmless under the pre-ruling code, which billed the version
figure and nothing else.
"""

import logging
from decimal import Decimal

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenants(apps):
    """`tenants` is an RLS-exempt platform table, so it can be enumerated
    before any tenant context exists (`rating/0030`)."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", "subdomain"))


def _enter_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _say(line):
    """Both the log and the `migrate` console: the numbers are the deliverable."""
    logger.info(line)
    print(f"  {line}")


def move_version_minimums_onto_sizes(apps, schema_editor):
    TariffVersion = apps.get_model("rating", "TariffVersion")
    RateSizeRow = apps.get_model("rating", "RateSizeRow")
    connection = schema_editor.connection

    for tenant_id, subdomain in _tenants(apps):
        _enter_tenant(connection, tenant_id)
        stated = filled = disagree = 0
        unplaced = []
        try:
            with transaction.atomic():
                versions = TariffVersion.objects.filter(
                    tenant_id=tenant_id, minimum_bill__isnull=False
                ).select_related("tariff")
                for version in versions:
                    stated += 1
                    figure = Decimal(version.minimum_bill)
                    rows = RateSizeRow.objects.filter(tenant_id=tenant_id, tariff_version=version)
                    if not rows.exists():
                        unplaced.append(
                            f"{version.tariff.name} (version {version.id}) {figure:.2f}"
                        )
                        continue
                    for own in rows.exclude(minimum_bill__isnull=True):
                        if Decimal(own.minimum_bill) != figure:
                            disagree += 1
                    filled += rows.filter(minimum_bill__isnull=True).update(
                        minimum_bill=version.minimum_bill
                    )
                    TariffVersion.objects.filter(pk=version.pk).update(minimum_bill=None)
        except Exception:  # pragma: no cover — reported, never silently swallowed
            logger.exception(
                "rating 0053: tenant %s (%s) could not have its version minimums moved onto "
                "its size rows — its floors would stop being charged. Every other tenant is "
                "unaffected (per-tenant savepoint).",
                subdomain,
                tenant_id,
            )
            continue
        if stated:
            _say(
                f"rating 0053 (DEF-RAT-8737, PO 2026-10-01): tenant {subdomain}: "
                f"{stated} version(s) stated a minimum; {filled} size row(s) given it; "
                f"{disagree} size row(s) already stated a DIFFERENT figure and were left; "
                f"{len(unplaced)} version(s) have no size rows, figure LEFT on the version, "
                f"unbilled, for the clerk: {unplaced or 'none'}"
            )
    _leave_tenant(connection)


def restore_uniform_version_minimums(apps, schema_editor):
    TariffVersion = apps.get_model("rating", "TariffVersion")
    RateSizeRow = apps.get_model("rating", "RateSizeRow")
    connection = schema_editor.connection
    restored = 0
    for tenant_id, subdomain in _tenants(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                for version in TariffVersion.objects.filter(
                    tenant_id=tenant_id, minimum_bill__isnull=True
                ):
                    figures = list(
                        RateSizeRow.objects.filter(
                            tenant_id=tenant_id, tariff_version=version
                        ).values_list("minimum_bill", flat=True)
                    )
                    if not figures or any(value is None for value in figures):
                        continue
                    if len({Decimal(value) for value in figures}) != 1:
                        continue
                    TariffVersion.objects.filter(pk=version.pk).update(minimum_bill=figures[0])
                    restored += 1
        except Exception:  # pragma: no cover
            logger.exception("rating 0053 reverse: tenant %s could not be restored", subdomain)
    _leave_tenant(connection)
    _say(f"rating 0053 reverse: restored {restored} version minimum(s)")


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0052_cr156_price_rows_no_overlap"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(move_version_minimums_onto_sizes, restore_uniform_version_minimums),
    ]
