# ── Trace ──────────────────────────────────────────────
# Change:   G3 (PO 2026-10-14, decision log "G1–G4 APPROVED" item 3) — a
#           correction case takes its number at Send from a new tenant series
#           "Correction case", default `CC-{YYYY}-{000}`. `DEF-BIL-10147`.
# Rules:    BR-TEN-035 (a series row per tenant; every seeded default is
#           tenant-editable) · CLAUDE.md hard rule 1 (the RLS policy on
#           `number_series` is untouched and honoured, one tenant at a time)
# Tests:    06-backend/tests/test_def_bil_10147_correction_case_numbers.py
# ───────────────────────────────────────────────────────
"""tenancy 0063 — **every existing tenant gets a `correction_case` series row.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, so the marker is here because the PATH is the category.
Ledger row: `12-governance/09-human-review-ledger.md`, *"The number a
correction case is given at Send"*.

WHY. `core.numbering.SERIES_CATALOG` gained `correction_case` today, so a tenant
provisioned from now on is seeded with it by `_seed_number_series`. A tenant
provisioned BEFORE today has no row, and `allocate_series_number` would answer
every Send with `numbering_series_missing` — the case would open, correctly,
unnumbered, which is exactly the defect. This is the other half.

WHAT IT WRITES. One row per tenant that has none: format `CC-{YYYY}-{000}`,
counter 1, restart YEARLY, `period_counted` empty (the first allocation adopts
its year — `allocate_series_number`). A tenant that already has a row (none can
today; the migration is re-runnable) keeps it untouched.

FROZEN VALUES, NOT READ FROM THE CATALOGUE. `tenancy/0048`'s reasoning: a
migration that consulted the live catalogue would silently change meaning the
next time the catalogue moves.

RLS. `number_series` is ENABLE + FORCE, and FORCE applies to the owner who runs
migrations, so with no `app.tenant_id` a read sees no rows and an insert is
refused by the policy's WITH CHECK. The tenant is therefore set, transaction-
locally, before each tenant's write — `tenancy/0048`'s loop. `tenants` carries
no RLS and is enumerated without context. SQLite has neither, so the loop runs
without `set_config` there and means the same thing.

REVERSE. Deletes the rows this seeded only where they have NEVER ISSUED a
number (`next_number = 1`); a consumed series is a record of numbers already on
cases and is left alone, as `tenancy/0048`'s reverse is guarded.
"""

from django.db import migrations

SERIES = "correction_case"
DEFAULT_FORMAT = "CC-{YYYY}-{000}"
RESTART = "yearly"


def _tenant_ids(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT id FROM tenants ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


def _scope(schema_editor, tenant_id) -> None:
    """SET LOCAL the tenant (CLAUDE.md hard rule 1) — discarded at commit, so
    the migration leaks no context into whatever runs next."""
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])


def forwards(apps, schema_editor):
    NumberSeries = apps.get_model("tenancy", "NumberSeries")
    for tenant_id in _tenant_ids(schema_editor):
        _scope(schema_editor, tenant_id)
        NumberSeries.objects.get_or_create(
            tenant_id=tenant_id,
            series=SERIES,
            defaults={
                "format": DEFAULT_FORMAT,
                "next_number": 1,
                "restart_period": RESTART,
                "period_counted": "",
            },
        )


def backwards(apps, schema_editor):
    NumberSeries = apps.get_model("tenancy", "NumberSeries")
    for tenant_id in _tenant_ids(schema_editor):
        _scope(schema_editor, tenant_id)
        NumberSeries.objects.filter(tenant_id=tenant_id, series=SERIES, next_number=1).delete()


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0062_cr182_high_usage_alert_document_kind")]

    operations = [migrations.RunPython(forwards, backwards)]
