# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2409 · DEF-3230 — see 0030 for the full trace. This is the DATA
#           half of that change and it exists as its own migration for a reason
#           PostgreSQL enforces; the module docstring is that reason.
# Rules:    BR-TEN-1180 · BR-RAT-015 (sewer is a share) · BR-RAT-090 (capacity
#           is a COUNT) · CLAUDE.md law 14 (a real PostgreSQL is the only place
#           this class of failure appears)
# Tests:    06-backend/tests/test_br_ten_1180_billing_basis.py
# ───────────────────────────────────────────────────────
"""tenancy 0031 — the billing-basis BACKFILL, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **WHY THIS IS A SEPARATE MIGRATION, AND WHY MERGING IT BACK INTO `0030` WILL
BREAK PRODUCTION WHILE PASSING EVERY TEST — CLAUDE.md law 14, MEASURED.**

The first draft did the whole change in one atomic migration: `AddField` →
`RunPython` backfill → `RemoveField`. **On the default test suite it passed.** On
a real PostgreSQL 16.13 with three rows planted in `tenant_services` it failed:

    django.db.utils.OperationalError: cannot ALTER TABLE "tenant_services"
    because it has pending trigger events

`tenant_services` carries FOREIGN KEY constraints declared `DEFERRABLE INITIALLY
DEFERRED` (tenant, service, three UoMs, two ledger accounts). An UPDATE against
those rows queues deferred trigger events that are not flushed until COMMIT, and
PostgreSQL refuses to ALTER a table while any are outstanding. So **a migration
that writes rows and then alters the same table cannot work on PostgreSQL**, in
either direction.

⚠ **AND THE FIRST ATTEMPT TO PROVE IT REPORTED OK, WHICH IS THE MORE USEFUL HALF
OF THIS NOTE.** The proof script's planting SQL was refused (it named a
`tenants.status` column that does not exist), `psql` was not run with
`ON_ERROR_STOP`, and the migration therefore ran over **zero rows** — no writes,
no pending triggers, "Applying… OK". A green run over an empty table is not
evidence about a backfill. The proof now asserts the planted count BEFORE it
migrates, and refuses rather than passing.

**THE RULE THIS SPLIT ENCODES, and it is the thing to keep:** a migration is
EITHER schema or data, never both, on any table whose rows it touches.
`0030` adds the column, `0031` (this one) fills it, `0032` drops the old one.
Each is atomic on its own and each is safe in reverse, because no single one of
them both writes rows and alters the table.

THE BACKFILL, AND WHY IT IS NOT A STRAIGHT TRANSLATION
-------------------------------------------------------
  1. `metered = TRUE`   → `'metered'`     — every row that ever held it.
  2. `metered = FALSE`  → `'capacity'`    — the false side's only meaning
     (`BR-RAT-090`: a COUNT of the unit's assets; 3 carts × $15.00 = $45.00).
  3. **`service.code = 'sewer'` → `'share'`, whichever side it was on.**

Rule 3 is the reason this is a data migration at all. It runs AFTER 1 and 2 so
it wins, and it is keyed on the SERVICE CODE rather than on the old boolean,
because **sewer was wrong in both directions**: a tenant that never touched the
setting has sewer `metered=True` (the default), and a tenant that made the
Settings screen honest has it `False`. One statement corrects both, and neither
was a preference anybody expressed. Sewer is a percentage of the water usage
charge (`BR-RAT-015`) and has no assets to count, so `capacity` would price it
at `$0.00` — which is the mispricing `DEF-2409` was filed about.

Rules 1 and 2 are what the PO's ruling of 2026-09-02 says about the OTHER nine
services, no more. `storm_water`, `trash`, `solar`, `broadband` and `battery` are
all `capacity` by that ruling, and this moves them **only where a tenant had
already said `metered=False`**. The rest are moved by `SERVICE_DEFAULT_UOMS` at
provisioning, forward. Re-basing a live tenant's storm water from a read to an
asset count would change what its next bill charges, and the ruling did not say
to do that to bills already in flight.
"""

from django.db import migrations

# ⚠ Re-declared rather than imported from `apps.tenancy.models`: a migration must
# keep running when the model moves on, and importing the live constant would let
# this file's behaviour change under it.
BILLING_BASIS_METERED = "metered"
BILLING_BASIS_SHARE = "share"
BILLING_BASIS_CAPACITY = "capacity"


def backfill(apps, schema_editor):
    """metered → basis, with sewer corrected from the SERVICE CODE.

    ⚠ **`.update()` in three statements, not a Python loop.** These are set
    operations and are written as set operations; a loop would be a round trip
    per row on a table every tenant has ten rows in.

    ⚠ **NO `try/except` AROUND A WRITE, DELIBERATELY (CLAUDE.md law 14).** There
    is nothing here that can fail per-row and be skipped: no unique constraint is
    touched, no FK is followed, and the column being written was created with a
    default in `0030`, so every row already holds a legal value. A caught
    `IntegrityError` here would poison the migration's own transaction on
    PostgreSQL and pass on the SQLite suite — the exact trap law 14 records. If a
    statement here fails, the migration must fail.
    """
    TenantService = apps.get_model("tenancy", "TenantService")
    TenantService.objects.filter(metered=True).update(billing_basis=BILLING_BASIS_METERED)
    TenantService.objects.filter(metered=False).update(billing_basis=BILLING_BASIS_CAPACITY)
    # LAST, so it wins; keyed on the service, because sewer was wrong on BOTH
    # sides of the boolean. `service__code` crosses to the platform catalog,
    # which is RLS-exempt (BR-TEN-025) and identical for every tenant.
    TenantService.objects.filter(service__code="sewer").update(billing_basis=BILLING_BASIS_SHARE)


def unbackfill(apps, schema_editor):
    """basis → metered. **LOSSY, and it says so rather than pretending.**

    `share` and `capacity` both become FALSE, because that is the only false the
    old column had. A database reversed and re-applied keeps `capacity` and would
    lose `share` — except that `backfill` re-derives sewer from the SERVICE CODE
    rather than from the boolean, so the round trip lands where it started. That
    is the second reason rule 3 is keyed on the code.
    """
    TenantService = apps.get_model("tenancy", "TenantService")
    TenantService.objects.filter(billing_basis=BILLING_BASIS_METERED).update(metered=True)
    TenantService.objects.exclude(billing_basis=BILLING_BASIS_METERED).update(metered=False)


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0030_br_ten_1180_billing_basis"),
    ]

    operations = [
        # DATA ONLY. Adding an `AddField` or a `RemoveField` beside this is what
        # the module docstring exists to prevent.
        migrations.RunPython(backfill, unbackfill),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2409@billing-basis — see 0030's trailer for the full authority list
# generated: 2026-09-02 by the billing-basis lane (DEF-2409)
# checklist: A✔ B✔ C✔ D✔ E=deferred(the S8 control is a sibling lane's, built against the same contract) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 with three
#         rows planted — water metered=true, trash metered=false, sewer
#         metered=true — and the planted count ASSERTED before the run, because
#         the first attempt migrated an empty table and reported OK
# exceptions: THE REVERSE IS LOSSY and says so in its own docstring · this
#         migration performs NO schema change, by rule, and merging it into 0030
#         reproduces `cannot ALTER TABLE … because it has pending trigger events`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
