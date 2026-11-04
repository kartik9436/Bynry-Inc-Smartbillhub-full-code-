# ── Trace ──────────────────────────────────────────────
# Change:   G3 (PO 2026-10-14, decision log "G1–G4 APPROVED" item 3) —
#           *"existing cases are numbered once, oldest first"*. `DEF-BIL-10147`.
# Rules:    BR-TEN-035 (numbers come from the tenant series and the counter is
#           advanced with them; a number is never reused) · BR-TEN-043 (the
#           issue date is the record's own date, never a clock) · CLAUDE.md
#           hard rule 1 (one tenant at a time, under its own context)
# Tests:    06-backend/tests/test_def_bil_10147_correction_case_numbers.py
# ───────────────────────────────────────────────────────
"""billing 0043 — **number every existing correction case, once, oldest first.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored 2026-10-14 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); ledger row in
`12-governance/09-human-review-ledger.md`, *"The number a correction case is
given at Send"*.

WHAT IT DOES. For each tenant with an unnumbered case: read its
`correction_case` series row (seeded for every tenant by `tenancy/0062`, which
this depends on), and give each unnumbered case the next number in
`created_at, id` order — the moment the case was opened, which for every case
written since CR-180 is its Send. The counter on the series row is ADVANCED
with them, so the first case sent after this migration takes the next number
rather than one already printed on an old case (`customers/0014`'s reason for
allocating row by row rather than with `row_number()`).

THE YEARLY RESTART IS HONOURED, EXACTLY AS THE SINK DOES IT. The series is
seeded `yearly` with `period_counted` empty: the first number ADOPTS its year
without resetting, and a later case in a later year starts again at 1
(`tenancy.services.allocate_series_number`). Oldest-first order means no case
is ever numbered backwards, so the sink's backdated refusal cannot arise here.
On a tenant whose cases all date from 2026: CC-2026-001, CC-2026-002, …

THE DATE. `created_at` in the tenant's own timezone (`tenant_settings.timezone`,
UTC when unset) — `{YYYY}` is "issue date, tenant timezone" in the format
grammar, and a case opened at 19:00 on 31 December in Chicago is a December
case. It is the record's own date, so re-running on a restored dump gives the
same numbers.

A MISSING SERIES ROW is skipped, never invented here: the cases stay
unnumbered — the state the ruling allows for a deleted series — rather than
this migration creating a row the tenant may have deliberately deleted.

THE FORMAT IS THE TENANT'S ROW, and `render` is `core.numbering`'s pure
kernel function (`customers/0014` uses it the same way). It reads no catalogue
default, so a future change to the seeded default changes nothing here.

RLS. `correction_cases` and `number_series` are both ENABLE + FORCE, so the
tenant is set transaction-locally before each tenant's work (`tenancy/0048`'s
loop). Tenant ids come from `tenants`, which carries no RLS.

REVERSE IS A NO-OP, DELIBERATELY. A number once printed on a case is a number
a clerk may already have quoted, and BR-TEN-035 never reuses one. Rolling the
code back leaves the numbers in place; nothing reads them differently.
"""

from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import migrations

SERIES = "correction_case"


def _tenant_ids(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT id FROM tenants ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


def _scope(schema_editor, tenant_id) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])


def _zone(TenantSettings, tenant_id):
    name = (
        TenantSettings.objects.filter(tenant_id=tenant_id)
        .values_list("timezone", flat=True)
        .first()
    )
    try:
        return ZoneInfo(name) if name else dt_timezone.utc
    except (KeyError, ValueError):  # an unknown IANA name: the record's UTC date
        return dt_timezone.utc


def _period(restart_period: str, day) -> str:
    """`core.numbering.period_key`, frozen here so this migration means today
    what it meant when it was written."""
    if restart_period == "yearly":
        return f"{day.year:04d}"
    if restart_period == "monthly":
        return f"{day.year:04d}-{day.month:02d}"
    return ""


def forwards(apps, schema_editor):
    from core import numbering as core_numbering

    CorrectionCase = apps.get_model("billing", "CorrectionCase")
    NumberSeries = apps.get_model("tenancy", "NumberSeries")
    TenantSettings = apps.get_model("tenancy", "TenantSettings")

    for tenant_id in _tenant_ids(schema_editor):
        _scope(schema_editor, tenant_id)
        cases = list(
            CorrectionCase.objects.filter(tenant_id=tenant_id, case_no__isnull=True)
            .order_by("created_at", "id")
            .values_list("id", "created_at")
        )
        if not cases:
            continue
        row = NumberSeries.objects.filter(tenant_id=tenant_id, series=SERIES).first()
        if row is None:
            continue  # a deleted series: the cases stay unnumbered (G3)
        zone = _zone(TenantSettings, tenant_id)
        for case_id, created_at in cases:
            day = created_at.astimezone(zone).date()
            if row.restart_period != "never":
                key = _period(row.restart_period, day)
                if not row.period_counted:
                    row.period_counted = key  # adopt, do not reset (the sink's rule)
                elif key != row.period_counted:
                    row.next_number = 1
                    row.period_counted = key
            CorrectionCase.objects.filter(pk=case_id).update(
                case_no=core_numbering.render(row.format, row.next_number, day)
            )
            row.next_number += 1
        row.save(update_fields=["next_number", "period_counted"])


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("billing", "0042_def_bil_10091_correction_jobs"),
        # The series row this numbers from is seeded there. Naming the
        # dependency rather than assuming ordering is the point of the 🔒 flag.
        ("tenancy", "0063_def_bil_10147_correction_case_series"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
