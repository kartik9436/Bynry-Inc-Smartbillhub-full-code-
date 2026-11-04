# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002/003 (units)   Change: CR-023 follow-on (PO rulings 2026-08-21)
# Rules:    BR-MET-101 (a common area is a UNIT WITH A FLAG — no new table) ·
#           BR-MET-094 (a vacant unit billed to the owner is a DIFFERENT thing,
#           and the flag is what separates them) · CLAUDE.md rule 1 (tenant
#           scoping / RLS)
# ───────────────────────────────────────────────────────
"""metering 0016 — BR-MET-101's `units.is_common_area` flag.

WHY A COLUMN AND NOT A TABLE. BR-MET-101 (PO ruling 2026-08-21, option A of
three): *"A COMMON AREA IS A UNIT WITH A FLAG. A MASTER ACCOUNT IS AN ACCOUNT
WHOSE PAYER IS THE OWNER. NEITHER NEEDS A NEW TABLE."* Everything a common area
needs already works for units and only for units — meters, service points,
reads, plans, routes, cycles and bill assembly all key off a unit — so this
migration adds one boolean and nothing else.

RLS: NOTHING TO RE-POLICE. `units` has had ENABLE+FORCE row-level security and
the B2 §3 tenant-isolation policy since metering 0002 (`db/rls_metering_w1.sql`
lines 66-71), and that policy is row-scoped (`tenant_id =
current_setting('app.tenant_id')::uuid`), not column-scoped — a new column on an
already-policed table is covered the moment it exists. Stated here so nobody
goes looking for the missing policy change: there isn't one, by design.

DB DEFAULT false, EXPLICITLY. Django's `BooleanField(default=False)` applies its
default in Python only; the column itself would carry no DEFAULT, so an INSERT
from a repair script or a COPY would hit NOT NULL. Same correction metering
0008 made for `is_sample` — the DEFAULT is set below on Postgres.

BACKFILL, PER TENANT, WITH `app.tenant_id` SET. `unit_type = 'common_area'` is
one of US-MET-002 §5's five ratified types and predates the flag, so a row
already typed that way IS a common area by the tenant's own declaration —
leaving it flag-false would make r10's "3 + common" tile undercount the day the
flag ships. The backfill follows assets 0003's pattern exactly: enumerate the
RLS-exempt `tenants` table, `set_config('app.tenant_id', ...)` per tenant
(CLAUDE.md rule 1 — never touch a tenant table without it; FORCE RLS would
refuse anyway), update, clear the setting. On sqlite (the test DB) there is no
RLS and no set_config — skipped honestly.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this file
declares schema that money is priced, posted or scoped against.

HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human."*). The standing record of that deferred
review is 12-governance/09-human-review-ledger.md; no 🔒 file reaches lifecycle
RATIFIED without a human sign-off recorded there.

⚠ **BOTH MARKERS WERE MISSING UNTIL 2026-09-02 AND G7 HAD BEEN RED ON THIS FILE
EVER SINCE IT LANDED (DEF-3229).** 198 of this repository's 218 migrations carry
them and 20 did not — so the gate that enforces the 🔒 protocol could not go green
for anybody, and every lane that ran it truthfully reported the failure as
"pre-existing, not mine". Nothing about the migration itself changed here.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

COLUMN_DEFAULT_SQL = """
ALTER TABLE units ALTER COLUMN is_common_area SET DEFAULT false;
"""


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (db/rls_tenancy_w0.sql), so it
    can be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


# ⚠ AMENDED 2026-08-24 — OQ-354, RULED BY THE PO, OPTION (A). Second of three
# identical call sites; the full reasoning is in
# `apps/assets/migrations/0003_meter_types_and_read_methods.py`, which is the one
# a fresh run reaches first. In short: `set_config(..., false)` is SESSION level,
# so clearing to the EMPTY STRING here outlived this migration and every later
# one inherited it, and a deferred FOREIGN KEY validation scan is evaluated
# against the B2 §3 policy — where `''::uuid` raises `invalid input syntax for
# type uuid: ""` and blocks a first deploy outright.
#
# The nil sentinel casts under BOTH the original policy and DEF-639's repaired
# one, and matches no row under either, so deny-by-default is unchanged. It is
# also the default `db/001_tenant_context_default.sql` installs.
#
# Runtime is untouched: `core/tenancy.py` still clears a REQUEST's context to
# `''` deliberately, because there a failed cast is the desired denial.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    # The nil sentinel, NOT '' — see the note above. Castable, matches nothing.
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def backfill_flag_from_unit_type(apps, schema_editor):
    """A row a tenant already typed `common_area` becomes flag-true; nothing
    else moves. The reverse is a no-op — dropping the column drops the fact."""
    Unit = apps.get_model("metering", "Unit")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            Unit.objects.filter(
                tenant_id=tenant_id, unit_type="common_area", is_common_area=False
            ).update(is_common_area=True)
        finally:
            _leave_tenant(connection)


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0015_rls_cr023_import_runs"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="unit",
            name="is_common_area",
            field=models.BooleanField(default=False),
        ),
        PostgresOnlySQL(COLUMN_DEFAULT_SQL),
        migrations.RunPython(backfill_flag_from_unit_type, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-002@947cf31 (W3 common-areas lane — BR-MET-101)
# generated: 2026-08-22 by story-coder (W3 lane)
# checklist: A✔ B✔ C✔ (tests/test_br_met_101_common_area.py) D=deferred(no-API-half — the units routes serve it) E=deferred(frontend half in the same lane commit) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · full metering suite green (see lane report)
# exceptions: the backfill's reverse is a noop — un-flagging on rollback would erase a fact the tenant may have set by hand after migrating forward
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
