"""customers 0086 — pre-2.580 portal stop asks get their temporary-stop row.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-14 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

DEF-CUS-10161. `0084` added `temporary_stops` and the 2.580.0 portal ask writes
a row there; an ask raised on 2.575.1 or earlier wrote only the clerk's
sentence, so after the upgrade it stays *Not yet classified* and the clerk
cannot approve it as a temporary stop. On WDMWW Loader Test that is
`SR-26-0017` (`AC-2026-00551`, 13 Oct → 16 Oct) and `SR-26-0022` (14 Oct →
28 Oct, *vacation*).

**Data only, no schema.** It runs
`customers.temporary_stop_backfill.backfill_all_tenants()` — the SAME function
`manage.py backfill_temporary_stops` runs, so there is one implementation — and
that function writes each row through `temporary_stop.record_from_portal`, the
live portal path, with its audit row (hard rule 7). Each tenant is visited
under its own `app.tenant_id` (hard rule 1; `temporary_stops` and
`service_requests` are FORCE RLS), each row in its own savepoint (law 14).

WHAT IT TOUCHES: only requests still awaiting a decision whose sentence opens
with the portal's stop marker and have no row. Refused, approved, completed,
withdrawn and closed requests are history and are not touched. A sentence it
cannot read, or one naming an account the utility does not hold, is left as it
is and COUNTED in the printed line. Nothing on any account moves — the row is
`requested` and a clerk still decides (BR-CWP-026). Idempotent: a second run
writes nothing.

⚠ **IT CALLS LIVE CODE, SO IT FIRST ASKS — WITH THE HISTORICAL MODEL — WHETHER
THERE IS ANYTHING TO DO.** A fresh database, and every host with no open
pre-upgrade stop ask, returns before importing the service, so a later schema
change to these tables cannot break this migration there. A host that skips
from 2.575.x straight past a later change to `service_requests` or
`temporary_stops` would run live models over an older schema; if that ever
bites, run `manage.py backfill_temporary_stops` after `migrate` instead —
the same function, against the schema it was written for. (`tenancy/0061`'s
shape, followed rather than re-derived.)

REVERSE: a no-op, stated rather than silent. Deleting the rows would also delete
every clerk decision made on them since, and a `requested` row a previous build
does not read harms nothing.
"""

from django.db import migrations

MARKER = "Asked through the customer portal to stop service on account"
OPEN_STATES = ("submitted", "under_review", "more_info")


def _anything_to_do(apps_registry, connection) -> bool:
    """Is there ANY open stop ask without a row, in any tenant? Historical
    models only, each tenant under its own GUC (FORCE RLS binds this role)."""
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    ServiceRequest = apps_registry.get_model("customers", "ServiceRequest")
    TemporaryStop = apps_registry.get_model("customers", "TemporaryStop")
    is_postgres = connection.vendor == "postgresql"
    arrival = ""
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0] or ""
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            taken = TemporaryStop.objects.filter(tenant_id=tenant_id).values("request_id")
            if (
                ServiceRequest.objects.filter(
                    tenant_id=tenant_id, state__in=OPEN_STATES, what_they_said__startswith=MARKER
                )
                .exclude(id__in=taken)
                .exists()
            ):
                return True
        return False
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])


def backfill(apps_registry, schema_editor):
    if not _anything_to_do(apps_registry, schema_editor.connection):
        return
    from apps.customers import temporary_stop_backfill

    report = temporary_stop_backfill.backfill_all_tenants()
    print("\n    " + temporary_stop_backfill.summary(report))


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0085_cr185_balance_tie_backs"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-10161 · CR-183-BRC10 · BR-CUS-1120 · BR-CWP-026
# generated: 2026-10-14 by the temporary-stop backfill maintenance lane
# gates: pytest tests/test_def_cus_10161_temporary_stop_backfill.py (SQLite and
#         PostgreSQL 16) · makemigrations --check --dry-run
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
