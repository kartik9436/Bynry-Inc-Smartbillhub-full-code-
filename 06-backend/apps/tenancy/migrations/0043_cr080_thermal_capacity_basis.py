# ── Trace ──────────────────────────────────────────────
# Change:   CR-080 — 2026-09-07. THERMAL/HEAT stops being a metered service and
#           becomes a CAPACITY one, billed on CONNECTED TONNAGE. PO verbatim:
#           *"connected tonnage - it is capacity not metering; i will ahve 100
#           tonne or 200 tonne etc"*. This is the DATA half — the seed map,
#           the size classes and the fixture are the rest of the CR.
# Rules:    BR-TEN-1180 (a service is metered, a share, or capacity-based) ·
#           BR-TEN-171 (the ratified size classes) · CLAUDE.md law 14 (a real
#           PostgreSQL is the only place this class of failure appears) ·
#           CLAUDE.md hard rule 4 (nothing already issued is rewritten — see
#           the docstring's measurement: nothing has been)
# Tests:    06-backend/tests/test_cr080_thermal_capacity.py
# ───────────────────────────────────────────────────────
"""tenancy 0043 — thermal/heat's stored billing basis, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **DATA ONLY, AND `0031`'s DOCSTRING IS WHY.** That file records, measured on
PostgreSQL 16.13, that a migration which writes rows and then ALTERs the same
table fails outright —

    django.db.utils.OperationalError: cannot ALTER TABLE "tenant_services"
    because it has pending trigger events

— because `tenant_services` carries `DEFERRABLE INITIALLY DEFERRED` foreign
keys whose trigger events are not flushed until COMMIT. **And the entire SQLite
test suite passes over the broken version**, because SQLite has no such state.
So the rule it encodes is kept here without re-deriving it: **a migration is
EITHER schema or data, never both, on any table whose rows it touches.** This
one adds no column, drops none and alters nothing; it writes one UPDATE.

WHAT IT MOVES, AND WHAT THAT COSTS — MEASURED, NOT ESTIMATED
--------------------------------------------------------------
Every `tenant_services` row for `thermal_heat` goes `'metered'` → `'capacity'`.

Measured on a seeded development database at the tip on 2026-09-07, and
re-measured immediately before this migration was written: **every thermal row
is `metered` and every one is `enabled = false`**, with **0 thermal service
points, 0 thermal assets and 0 thermal invoice lines**. **Nothing bills thermal
today, so no customer is re-billed and no issued invoice is contradicted**
(CLAUDE.md hard rule 4 is not engaged — there is nothing issued to engage it).
That is the cheapest this change will ever be, and it is the argument for
making it now rather than after a thermal utility goes live.

WHY IT IS UNCONDITIONAL, WHICH IS THE OPPOSITE OF WHAT `0031` DID
------------------------------------------------------------------
`0031` moved a tenant's basis **only where the tenant had already said
`metered=False`**, and its docstring gives the reason: *"Re-basing a live
tenant's storm water from a read to an asset count would change what its next
bill charges, and the ruling did not say to do that to bills already in
flight."*

**That reasoning does not apply here and its own premise is what settles it.**
The PO's ruling is about THIS SERVICE by name — *"connected tonnage - it is
capacity not metering"* — not about a default for services enabled from now;
and the measurement above says there are no bills in flight to protect. A
conditional move would leave a tenant that had explicitly ticked *metered* for
thermal sitting on a basis the PO has ruled wrong, with no screen telling
anyone. **If a real thermal tariff ever were in flight this would have to be a
conversation instead of a migration**, and the measurement is recorded here so
the next reader can check whether that is still true rather than trusting this
sentence.

⚠ **THE UNIT IS NOT TOUCHED, DELIBERATELY.** `tenant_services` also stores the
tenant's chosen UoMs, and `SERVICE_DEFAULT_UOMS["thermal_heat"]` moved from
`ton-hr` to `ton` in the same commit. **A seeded default is never a backfill**
(BR-TEN-1180 clause 6): the map governs services enabled FROM NOW, no stored
unit is rewritten, and a utility changes its own on S8 → Services & UoM.
Rewriting a stored unit here would be this migration deciding what a tenant
sells. The one thing that MUST move is the basis, because a basis every tenant
got wrong is not a preference anybody expressed — `0031`'s own argument.

⚠ **AND THE COST OF THAT CHOICE IS STATED RATHER THAN LEFT TO BE DISCOVERED.**
A tenant that had already enabled thermal keeps `primary_uom = 'ton-hr'` while
its basis becomes `capacity`, and `rating.sample_data._capacity_uom` reads the
TENANT's unit — so a seeded schedule on such a tenant would quote the
`$12.5000` per `ton-hr` against a quantity measured in `ton`. **That is
`DEF-497`'s shape**, and three things hold it:

  * **there is no such tenant.** Measured above: thermal is `enabled = false`
    everywhere, with no service points and no lines. This is a hazard for a
    tenant that does not exist;
  * **`BR-RAT-038`'s unit gate refuses at bill time** rather than mispricing —
    the schedule's unit and the quantity's unit are compared and a mismatch
    stops the bill by name, which is the safe direction;
  * **it is the posture already accepted for storm water** on 2026-09-02, which
    moved `kgal → ERU` under the same no-backfill rule.

A utility that genuinely bills chilled-water ENERGY changes its own unit on
S8 → Services & UoM, which is what a seeded default is for.

THE REVERSE IS EXACT, NOT LOSSY
--------------------------------
`capacity` → `metered` for `thermal_heat` and for nothing else. Unlike `0031`'s
`unbackfill` — which collapses `share` and `capacity` into one boolean — this
migration moves one service between two named values, so reversing it restores
exactly what was there. A database reversed and re-applied lands where it
started.

RLS — AND THE FIRST DRAFT OF THIS FILE WAS A SILENT NO-OP BECAUSE OF IT
------------------------------------------------------------------------
⚠ **READ THIS BEFORE "SIMPLIFYING" THE LOOP BELOW BACK INTO ONE `.update()`.**
`tenant_services` carries `ENABLE` + `FORCE ROW LEVEL SECURITY`, and **FORCE
binds the migration role too**. A bare `TenantService.objects.filter(...)
.update(...)` therefore runs with `app.tenant_id` unset, matches **zero rows on
every tenant**, and Django prints `Applying tenancy.0043… OK`.

That is exactly what the first draft did, and it was caught only because the
forward run was followed by a `SELECT` under a tenant context that still read
`metered`. **Nothing else would have caught it**: no exception, no warning, a
clean exit, and `0031` — the file this one was modelled on — has the same shape
and is correct only because it runs on a database that has no tenants yet.
CLAUDE.md law 7's *"a check that cannot fail"* in migration form.

So every tenant is visited under its **own** `app.tenant_id` and the GUC is
restored to exactly its arrival state — `work/0024_br_wrk_058_scope_water_sub_
types` and `metering/_0031_helpers.run_backfill`'s shape, followed rather than
re-derived. On SQLite the loop runs and sets no GUC; the suite builds from
empty, so it visits no tenant at all — **which is the second half of the same
trap: the entire test suite passes over the broken version.**
"""

from django.db import migrations

# ⚠ Re-declared rather than imported from `apps.tenancy.models`: a migration
# must keep running when the model moves on, and importing the live constant
# would let this file's behaviour change under it. `0031` does the same and for
# the same reason.
BILLING_BASIS_METERED = "metered"
BILLING_BASIS_CAPACITY = "capacity"
THERMAL = "thermal_heat"


def _move(apps_registry, schema_editor, *, to: str, label: str) -> None:
    """Set every tenant's thermal basis to `to`, one tenant context at a time.

    ⚠ **ONE `.update()` PER TENANT, NOT A PYTHON LOOP OVER ROWS** — `0031`'s
    rule: this is a set operation within a tenant and is written as one. The
    outer loop exists for RLS and for nothing else.

    ⚠ **NO `try/except` AROUND THE WRITE (CLAUDE.md law 14).** Nothing here can
    fail per row and be skipped: no unique constraint is touched, no FK is
    followed, and `billing_basis` already holds a legal value on every row. A
    caught `IntegrityError` would poison this migration's own transaction on
    PostgreSQL and pass on the SQLite suite, which is exactly the trap law 14
    records. If a statement here fails, the migration must fail.

    `service__code` crosses to the platform `services` catalog, which is
    RLS-exempt (BR-TEN-025) and identical for every tenant — the same join
    `0031`'s sewer rule makes.
    """
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    TenantService = apps_registry.get_model("tenancy", "TenantService")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    moved = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            moved += TenantService.objects.filter(
                tenant_id=tenant_id, service__code=THERMAL
            ).update(billing_basis=to)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [arrival]
                    )

    if tenants:
        print(
            f"cr-080 thermal basis: {tenants} tenant(s) — {moved} thermal row(s) "
            f"set to {label}"
        )


def to_capacity(apps_registry, schema_editor):
    """thermal_heat → `capacity`, on every tenant, whatever it held."""
    _move(apps_registry, schema_editor, to=BILLING_BASIS_CAPACITY, label="capacity")


def to_metered(apps_registry, schema_editor):
    """The exact reverse — thermal_heat → `metered`, and no other service."""
    _move(apps_registry, schema_editor, to=BILLING_BASIS_METERED, label="metered")


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0042_rls_def_ten_4446_commercial_tables"),
    ]

    operations = [
        # DATA ONLY. Adding an `AddField` or a `RemoveField` beside this is what
        # the module docstring — and `0031`'s — exist to prevent.
        migrations.RunPython(to_capacity, to_metered),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-080@thermal-capacity
# generated: 2026-09-07 by the CR-080 lane
# checklist: A✔ B✔ C✔ (no new table, no new column, no money column; every write
#         is under its own `app.tenant_id` and the only join is to the RLS-exempt
#         platform catalog) D=deferred(no API half — the basis is already served
#         and written through the S8 contract BR-TEN-1180 shipped)
#         E=deferred(no screen change — S8 renders whatever basis the row holds)
#         F✔ G✔ (CR row, BR-TEN-1180, BR-TEN-171 and the decision log all
#         amended in the same commit) H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING, ledger row appended naming in plain English what
#         moves and what it costs)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 with a
#         thermal row present, and the row's basis READ BACK under a tenant
#         context after each direction — 0031's own hard-won clause, because its
#         first proof migrated an empty table and reported OK. ⚠ **THIS FILE'S
#         FIRST DRAFT FAILED THAT CHECK AND LOOKED PERFECT**: a bare `.update()`
#         under RLS FORCE matched zero rows, exited clean and left the row
#         `metered`. See the RLS section of the docstring.
# exceptions: this migration performs NO schema change, by rule (see 0031) · it
#         moves the BASIS and deliberately NOT the stored UoM, because a seeded
#         default is never a backfill (BR-TEN-1180 clause 6), and the cost of
#         that choice is stated in the docstring rather than left to be found
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
