# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-TEN-4446 — `implementation_orders` and `tenant_addons` carry a
#           tenant_id and no row-level security policy, and the allocator that
#           numbers implementation orders scans that table ACROSS TENANTS.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE is on) · B2 §3 ("No RLS (platform)" —
#           this table has no tenant_id and joins that list) ·
#           BR-TEN-043 (the caller names the date; nothing reads a clock) ·
#           🔒 migration ordering (CLAUDE.md sensitive paths)
# Tests:    06-backend/tests/test_def_ten_4446_commercial_rls.py
# ───────────────────────────────────────────────────────
"""tenancy 0041 — Bynry's own order counter, and the numbers already issued.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHY THIS EXISTS AT ALL — IT IS THE PRICE OF THE POLICY IN `0042`
-----------------------------------------------------------------
`0042` applies the signed B2 §3 tenant policy to `implementation_orders`.
`apps/tenancy/platform_numbering.py` used to answer *"what is the next
implementation-order number?"* with a `MAX` over every row of that table, across
every tenant, because `0021` had left it unprotected. Under the policy that scan
runs inside the signing-up tenant's own context and sees only that tenant's
orders — **none**, for a tenant being created — so every signup would propose
`IMPL-26-0001`, collide with `uq_implementation_orders_order_no` (`0025`), retry
three times and raise. The signup would fail, and it would fail **only on
PostgreSQL**: sqlite has no row-level security, so the default suite would have
stayed green through the whole thing (CLAUDE.md hard-won law 14).

So the count moves off the rows and onto a row of its own, here.

WHY THIS MIGRATION RUNS BEFORE `0042` AND NOT AFTER
----------------------------------------------------
The backfill below READS `implementation_orders`. `FORCE ROW LEVEL SECURITY`
applies to the table owner too, so once `0042` has run, a data migration with no
`app.tenant_id` set would read **zero rows** — silently, because a deny is an
empty result and not an error. It would seed every year's counter at 1 and hand
the next signup a number that is already taken. Ordering is the whole guard: the
high-water mark is taken while the table is still readable end to end.

WHY THIS TABLE CARRIES NO POLICY OF ITS OWN
--------------------------------------------
It has no `tenant_id`. It is not exempt by exception, it is platform data by
construction: there is one Bynry, one `IMPL-` series, and no tenant has an
opinion about what the next number is. B2 §3's "No RLS (platform)" list names it
beside `plans` and `tenants` from 2026-09-07. The G5 sweep asks for a policy on
every table that HAS a `tenant_id`, so it never sees this one — which is the
correct behaviour and not a hole: a table with no tenant column has no
cross-tenant row to leak.

THE PARSE BELOW IS A FROZEN COPY, ON PURPOSE
---------------------------------------------
`IMPL-{YY}-{0000}` is read here by a regex written out in full rather than by
importing `platform_numbering`. A migration is a record of what was done; if the
format is ever changed, this file must go on reading the numbers that existed on
2026-09-07, and an import would silently re-read history through a new grammar.
`0038` states the same rule for its table list.

`{YY}` is two digits, so the year is reconstructed as `2000 + YY`. That is exact
for every order this product can have issued and stays exact until 2100; a
four-digit year in the format would be a change to a reference customers quote,
which is not this defect's to make.
"""

import re

import core.dbfields
from django.db import migrations, models

#: The one series this product allocates today. Must equal
#: `platform_numbering.IMPLEMENTATION_ORDER_SERIES` — a different spelling here
#: would open a second, empty counter and every signup would start again at 1.
IMPLEMENTATION_ORDER_SERIES = "implementation_order"

#: `IMPL-26-0007` → year `26`, sequence `0007`. Anchored at both ends so a
#: hand-typed reference that merely CONTAINS one cannot be counted.
ORDER_NO_RE = re.compile(r"^IMPL-(\d{2})-(\d{4,})$")


def seed_counter_from_existing_orders(apps_registry, schema_editor):
    """Set each year's counter one past the highest number that year already holds.

    A no-op on a fresh database — there are no orders — and the only thing
    standing between a live database and a duplicate reference on the next
    signup. Rows with a NULL or unparseable `order_no` are skipped rather than
    guessed at: `0021` made the column nullable and several NULLs are not a
    series (`uq_implementation_orders_order_no` is partial for the same reason).
    """
    ImplementationOrder = apps_registry.get_model("tenancy", "ImplementationOrder")
    PlatformNumberSeries = apps_registry.get_model("tenancy", "PlatformNumberSeries")

    highest: dict[int, int] = {}
    for value in ImplementationOrder.objects.values_list("order_no", flat=True):
        match = ORDER_NO_RE.match(value or "")
        if match is None:
            continue
        year = 2000 + int(match.group(1))
        sequence = int(match.group(2))
        if sequence > highest.get(year, 0):
            highest[year] = sequence

    for year, top in sorted(highest.items()):
        PlatformNumberSeries.objects.update_or_create(
            series=IMPLEMENTATION_ORDER_SERIES,
            year=year,
            defaults={"next_sequence": top + 1},
        )


def unseed(apps_registry, schema_editor):
    """Reverse of the backfill. The table itself is dropped by the CreateModel's
    own reversal; this only has to leave nothing behind if that is run alone."""
    PlatformNumberSeries = apps_registry.get_model("tenancy", "PlatformNumberSeries")
    PlatformNumberSeries.objects.filter(series=IMPLEMENTATION_ORDER_SERIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0040_cr070_k_attachment_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformNumberSeries",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("series", models.TextField()),
                ("year", models.IntegerField()),
                ("next_sequence", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "platform_number_series"},
        ),
        migrations.AddConstraint(
            model_name="platformnumberseries",
            constraint=models.UniqueConstraint(
                fields=("series", "year"),
                name="uq_platform_number_series_series_year",
            ),
        ),
        migrations.RunPython(seed_counter_from_existing_orders, unseed),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-TEN-4446 (the isolation receipt of 2026-09-07 + B2 §3 lines 1001-1002)
# generated: 2026-09-07 by the DEF-TEN-4446 lane
# checklist: A✔ (r11 step 0 against 01-open-questions, 02-decision-log, 10-defect-log, 11-change-requests) B✔ C✔ (no tenant-scoped query: this table has no tenant_id and is platform data by construction) D=n/a(no API half — nothing outside the allocator reads a counter) E=n/a(no screen shows Bynry's counter) F✔ G✔ H=PENDING(🔒 migration ordering — ledger row in 09-human-review-ledger.md, plain English with the figure: one order-number series, still unique across all utilities, and zero rows of either priced table visible without a tenant context)
# gates: makemigrations --check --dry-run · pytest tests/test_def_ten_4446_commercial_rls.py + tests/test_cr039_wave_f_task27_numbering.py · 10-scripts/prove_isolation.py on PostgreSQL 16 under the NOSUPERUSER NOBYPASSRLS probe role
# exceptions: the `IMPL-{YY}-{0000}` parse is duplicated here rather than imported — a migration is a record of what was done (the rule `0038` states for its table list)
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
