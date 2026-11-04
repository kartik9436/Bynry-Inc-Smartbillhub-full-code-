# ── Trace ──────────────────────────────────────────────
# Change:   CR-065 task A3 — the DATA half of 0034. Every tenant provisioned
#           before today holds sixty untagged platform size classes, and a
#           fixture only ever reaches a NEW tenant; without this migration the
#           Fire schedule keeps offering Electric CT-metered to everybody who
#           already exists.
# Rules:    BR-TEN-012 (insert-if-absent seeding — a tenant's OWN row is never
#           rewritten, which is the whole shape of this backfill) · BR-TEN-071
#           (seed data never deletes) · BR-TEN-078 as SUPERSEDED 2026-09-02 ·
#           CLAUDE.md law 14 (a real PostgreSQL is the only place this class of
#           failure appears)
# Tests:    06-backend/tests/test_cr065_size_class_service.py
# ───────────────────────────────────────────────────────
"""tenancy 0035 — the size-class service BACKFILL, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **WHY THIS IS A SEPARATE MIGRATION FROM `0034` — see `0031`'s docstring for
the measurement.** A migration is EITHER schema or data, never both, on any
table whose rows it touches: an UPDATE queues deferred trigger events that
PostgreSQL will not let an ALTER run past, and the combined version passes the
whole SQLite suite before failing on the first real deployment.

WHAT IT FILLS, AND WHAT IT DELIBERATELY DOES NOT
------------------------------------------------
**PLATFORM ROWS ONLY, IDENTIFIED TWO WAYS AT ONCE**, and both conditions are
load-bearing:

  1. `is_system = TRUE` — the flag the seeder sets and a tenant's own `create`
     never does. This is `BR-TEN-012`'s line between "the platform put this
     here" and "a person here typed it".
  2. the code is one the RATIFIED MAP knows. Sixty codes across ten services
     (sewer is ruled to have none — `BR-RAT-015`), listed below.

**A TENANT-CREATED ROW IS NEVER TOUCHED, AND THAT IS THE POINT OF THE COLUMN
BEING NULLABLE.** A utility that added *"Fire line 14 inch"* last week keeps a
blank tag, keeps listing on every service, and can set the tag itself on
Settings → Utility service size classes. Nothing here guesses on its behalf: a
guess would be this migration inventing which service somebody else's row
belongs to.

**A SEEDED CODE THE MAP DOES NOT KNOW IS ALSO LEFT ALONE.** `E-3P`
*"Electric 3φ"* is the live example — withdrawn from the ratified electric list
on 2026-08-27, still held by every tenant provisioned before then because
`BR-TEN-071` deletes it from nobody. It stays untagged and stays visible, which
is the honest answer: nobody has ruled what it is now.

⚠ **THE MAP IS RE-DECLARED HERE RATHER THAN IMPORTED FROM
`apps.tenancy.service_size_classes`**, the same way `0031` re-declares its three
basis constants and for the same reason: a migration must keep running when the
module moves on. Importing the live constant would let this file's behaviour
change under it — a later CR that retires a code would silently change what this
migration did to databases it has already run against.

⚠ **NO `try/except` AROUND A WRITE, DELIBERATELY (CLAUDE.md law 14).** Nothing
here can fail per row and be skipped: no unique constraint is touched and the
column was created nullable in `0034`, so every row already holds a legal value.
A caught `IntegrityError` would poison the migration's own transaction on
PostgreSQL and pass on the SQLite suite — the exact trap law 14 records. If a
statement here fails, the migration must fail.

⚠ **ONE `.update()` PER SERVICE, NOT A PYTHON LOOP OVER ROWS.** These are set
operations over every tenant at once and are written as set operations; ten
statements, not sixty per tenant.
"""

from django.db import migrations

#: service code → the codes the RATIFIED map gives it, transcribed from
#: `apps.tenancy.service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES` on
#: 2026-09-02 and FROZEN here (see the module docstring for why it is copied
#: rather than imported). `sewer` is absent because it is ruled to have NONE
#: (BR-RAT-015 — it is a share of the water usage charge and reads no register),
#: and thermal STEAM is absent because it was never ruled at all (OQ-560).
RATIFIED_CODES: dict[str, tuple[str, ...]] = {
    "electric": ("E-1P-100", "E-1P-200", "E-1P-400", "E-3P-200", "E-3P-400", "E-CT"),
    "water": ("W-58", "W-34", "W-1", "W-112", "W-2", "W-3", "W-4", "W-5", "W-6"),
    "gas": ("G-250", "G-425", "G-630", "G-1000"),
    "trash": ("CART-35", "CART-64", "CART-96", "DUMP-2", "DUMP-4", "DUMP-6", "DUMP-8"),
    "storm_water": ("SW-SF", "SW-DUP", "SW-APT", "SW-COM-S", "SW-COM-L"),
    "solar": (
        "SOL-P1",
        "SOL-P2",
        "SOL-P3",
        "SOL-P4",
        "SOL-P5",
        "SOL-P6",
        "SOL-P7",
        "SOL-P8",
        "SOL-P9",
        "SOL-P10",
    ),
    "broadband": ("BB-100", "BB-500", "BB-1000"),
    "thermal_heat": ("TH-CW-25", "TH-CW-25-100", "TH-CW-100P"),
    "battery": ("BAT-5", "BAT-10", "BAT-15", "BAT-20", "BAT-25", "BAT-30"),
    "fire": ("FL-2", "FL-4", "FL-6", "FL-8", "FL-10", "FL-12", "HYD"),
}


def backfill(apps, schema_editor):
    """Tag every PLATFORM-SEEDED size class the ratified map knows.

    `is_system=True` AND a known code, both. A tenant's own row and a seeded
    code the map has withdrawn are left NULL — see the module docstring.
    """
    MeterSizeClass = apps.get_model("tenancy", "MeterSizeClass")
    Service = apps.get_model("tenancy", "Service")
    for service_code, codes in RATIFIED_CODES.items():
        service = Service.objects.filter(code=service_code).first()
        if service is None:
            # A catalogue this old does not have the service yet (`fire` arrived
            # in 0033). Skipping is correct rather than defensive: there can be
            # no seeded rows for a service the catalogue has never held.
            continue
        MeterSizeClass.objects.filter(
            is_system=True, service__isnull=True, code__in=codes
        ).update(service=service)


def unbackfill(apps, schema_editor):
    """Clear every tag this migration could have set — and ONLY those.

    Reversing clears the tag on `is_system` rows whose code the map knows, which
    is exactly the set `backfill` wrote. **A tenant's own tag survives a
    reverse**: a row a person tagged themselves on Settings has `is_system=False`
    and is not in this filter, so a database reversed and re-applied lands where
    it started rather than losing somebody's work.
    """
    MeterSizeClass = apps.get_model("tenancy", "MeterSizeClass")
    known = [code for codes in RATIFIED_CODES.values() for code in codes]
    MeterSizeClass.objects.filter(is_system=True, code__in=known).update(service=None)


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0034_cr065_size_class_service"),
    ]

    operations = [
        # DATA ONLY. Adding an `AddField` beside this reproduces
        # `cannot ALTER TABLE … because it has pending trigger events`.
        migrations.RunPython(backfill, unbackfill),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-065 task A3
# generated: 2026-09-02 by the CR-065 lane
# checklist: A✔ B✔ (BR-TEN-012 → platform rows only; the tenant-row case and the untagged-`E-3P` case are both asserted in test_cr065_size_class_service.py and both were shown RED against the pre-CR-065 code) C✔ (a set UPDATE per service across every tenant; the write touches no money column, nothing append-only, and no RLS policy — `Service` is RLS-exempt platform reference data) D=deferred(no-API-half — this migration writes rows) E=deferred(no-screen-half) F✔ (see gates:) G✔ (the supersession of BR-TEN-078 is in the business rules and the decision log, dated, in the same change) H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16 with rows planted — a seeded FL-2, a seeded E-3P (withdrawn, so unknown to the map) and a tenant-created row — and the planted state ASSERTED BEFORE the run, because 0031's first proof migrated an empty table and reported OK
# exceptions: the ratified map is RE-DECLARED here rather than imported, so a later CR retiring a code cannot change what this migration already did · the reverse is NOT lossy for a tenant's own tag, deliberately, and its docstring says which set it clears
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
