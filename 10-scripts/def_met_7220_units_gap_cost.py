"""**WHAT THE *Missing services* FILTER COSTS AT THE TOP OF THE ICP — MEASURED.**

PO ruling 2026-09-28: the Units screen's separate gap block becomes a FILTER on
the units list, and *"the read must stay paged and sorted in SQL"* (`NFR-3`)
with *"no per-tenant cap"* (`NFR-5`). The ceiling is **40,000 accounts — T5**,
not the 3,000 the old block was sized against.

⚠ **THE FIGURE THAT DECIDES IT IS `GUNICORN_TIMEOUT:-60`** (`docker-entrypoint.sh`).
A web worker gets sixty seconds. `CR-138` `P4` is the worked precedent: a read
that took **3.089s at 2,046 rows took 61.539s at 40,046** and was therefore not
slow at the top of the tier — it was **killed before it answered**. So the
question here is not *is the filter fast*; it is *does the units list still
answer inside a worker's life when the tenant is 40,000 units and the filter is
engaged*.

WHAT IS MEASURED, AND WHY THESE FOUR
------------------------------------
  1. the units list **unfiltered** — the baseline, and the read a clerk opens;
  2. the units list **with the filter engaged** — `_short_of_offer`'s narrowing
     inside the same `LIMIT`;
  3. `units_gap_count` — the figure the toolbar draws on EVERY read, engaged or
     not, so it is added to (1) as well as to (2);
  4. the **whole** envelope as the endpoint serves it: (1)+(3) and (2)+(3).

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY.** A gap filter that matched NOTHING at
scale would be fast and useless, so the row count is printed beside every
timing — a zero there means the seed, not the read, is what was measured. A
warm cache would flatter every figure, so the median of three is taken after a
DISCARDED warm-up, which is `cr138_p4_debtor_cost.py`'s own method.

HOW TO RUN IT
-------------
    createdb sbh_gapcost
    cd 06-backend && DATABASE_URL=postgres://…/sbh_gapcost \
      DJANGO_SETTINGS_MODULE=config.settings.local python3 manage.py migrate
    # then seed a tenant (seed_demo), then:
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://…/sbh_gapcost \
      python3 manage.py shell < ../10-scripts/def_met_7220_units_gap_cost.py

MEASURED 2026-09-28, real PostgreSQL 16, `brazosbend` seeded from `seed_demo` +
`load_sample_data`, median of 3 after a discarded warm-up:

    ── 2,000 units ───────────────────────────────────────────────────
      units list, filter OFF (page 1 of 50)     1.211s   (2,000 match, 50 drawn)
      units list, filter ON  (page 1 of 50)     0.590s   (  666 match, 50 drawn)
      service_gap_count (the toolbar figure)    0.020s   (  666 short)
      ENVELOPE, filter OFF                      1.231s
      ENVELOPE, filter ON                       0.609s

    ── 40,000 units — THE TOP OF T5 ──────────────────────────────────
      units list, filter OFF (page 1 of 50)     1.204s   (40,000 match, 50 drawn)
      units list, filter ON  (page 1 of 50)     1.017s   (13,339 match, 50 drawn)
      service_gap_count (the toolbar figure)    0.174s   (13,339 short)
      ENVELOPE, filter OFF                      1.378s
      ENVELOPE, filter ON                       1.191s

**THE WHOLE ENVELOPE AT THE TOP OF THE ICP IS 1.4 SECONDS AGAINST A SIXTY-SECOND
WORKER**, and it is FLAT from 2,000 to 40,000 — 1.231s to 1.378s for a tenant
twenty times the size. That is the `LIMIT` doing its job: the number of rows
BUILT is fifty either way, and the only thing that grows is the two `COUNT(*)`s.
**The toolbar figure costs 0.174s of it**, which is what the count on every read
buys, engaged or not.

Compare `CR-138` `P4`'s debtor read, which went 3.089s → **61.539s** over the
same span and was killed rather than slow. This read does not have that shape,
and the measurement is what says so rather than the design.

It SEEDS what it needs (premises, units, service points) with `bulk_create` and
leaves them behind — run it against a throwaway database, never a shared one.
"""

import statistics
import time
import uuid

from django.utils import timezone

from apps.metering import models as met
from apps.metering import selectors
from apps.tenancy import models as ten
from core import tenancy
from core.pagination import ListParams

TENANT = "brazosbend"
#: T7's old ceiling and T5's real one. The pair is the point: a read correct at
#: the first and killed at the second is the shape `DEF-PAY-4221` records.
SIZES = [2_000, 40_000]
#: Two thirds short, which is roughly what the seeded utility shows (43 of 131).
SHORT_EVERY = 3
UNITS_PER_PREMISES = 4

tenant_id = str(ten.Tenant.objects.get(subdomain=TENANT).id)


def seed(target: int) -> None:
    """Top the tenant up to `target` units, every third one short of its offer."""
    have = met.Unit.objects.filter(tenant_id=tenant_id).count()
    if have >= target:
        print(f"  already {have:,} units — nothing seeded")
        return
    need = target - have
    # ⚠ **THE PRINTED REFERENCES ARE OFFSET BY WHAT IS ALREADY THERE.** This
    # function runs once per size against ONE database, so a counter that
    # restarted at zero for the second size collided with the first size's
    # `premise_no` on `uq_premises_tenant_premise_no` — which is the seed
    # failing, not the read.
    base = have
    # ⚠ **THE OFFER IS TAKEN FROM AN ADDRESS THIS TENANT ALREADY HAS, NOT
    # INVENTED.** `Service` is a platform CATALOG and carries no `tenant_id`;
    # what a tenant sells is `TenantService`, and what an ADDRESS offers is the
    # `services_available` list on `premises`. Seeding a code this tenant does
    # not sell would measure a filter over rows the product cannot produce.
    offer = (
        met.Premises.objects.filter(tenant_id=tenant_id)
        .exclude(services_available=None)
        .exclude(services_available=[])
        .values_list("services_available", flat=True)
        .first()
    )
    assert offer, "seed a tenant with at least one address offering a service first"
    by_code = {row.code: row for row in ten.Service.objects.filter(code__in=offer)}
    now = timezone.now()
    made = 0
    while made < need:
        batch = min(4_000, need - made)
        premises = [
            met.Premises(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                premise_no=f"PX-{base + made + i:06d}",
                address_line=f"{base + made + i} Scale Row",
                city="Katy",
                state="TX",
                postal_code="77494",
                services_available=offer,
                created_at=now,
                updated_at=now,
            )
            for i in range(0, batch, UNITS_PER_PREMISES)
        ]
        met.Premises.objects.bulk_create(premises, batch_size=1_000)
        units = []
        for i in range(batch):
            units.append(
                met.Unit(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    premises=premises[i // UNITS_PER_PREMISES],
                    unit_no=f"UX-{base + made + i:06d}",
                    label=f"Scale {base + made + i}",
                    unit_type="residential",
                    created_at=now,
                    updated_at=now,
                )
            )
        met.Unit.objects.bulk_create(units, batch_size=1_000)
        points = []
        for i, unit in enumerate(units):
            # Every third unit holds NOTHING — short of both. The rest hold the
            # whole offer, so they are not short and the filter has to narrow.
            if i % SHORT_EVERY == 0:
                continue
            for code in offer:
                points.append(
                    met.ServicePoint(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        unit=unit,
                        service=by_code[code],
                        created_at=now,
                        updated_at=now,
                    )
                )
        met.ServicePoint.objects.bulk_create(points, batch_size=2_000)
        made += batch
        print(f"  seeded {made:,}/{need:,}")


def timed(label: str, call, rows_of) -> float:
    """Median of three after a DISCARDED warm-up, with the row count beside it.

    The count is not decoration: a narrowing that matched nothing would be the
    fastest figure here and would mean nothing at all.
    """
    call()  # warm-up, discarded
    runs = []
    rows = None
    for _ in range(3):
        started = time.perf_counter()
        result = call()
        runs.append(time.perf_counter() - started)
        rows = rows_of(result)
    median = statistics.median(runs)
    print(f"    {label:<44} {median:8.3f}s   ({rows})")
    return median


with tenancy.tenant_context(tenant_id):
    for size in SIZES:
        print(f"\n── {size:,} units ─────────────────────────────────────────")
        seed(size)
        total_units = met.Unit.objects.filter(tenant_id=tenant_id).count()
        plain = ListParams(q="", sort=None, dir="asc", page=1, per=50, filters={})
        filtered = ListParams(
            q="", sort=None, dir="asc", page=1, per=50, filters={"missing_services": "yes"}
        )
        print(f"  tenant holds {total_units:,} units")
        a = timed(
            "units list, filter OFF (page 1 of 50)",
            lambda: selectors.units_page(plain),
            lambda r: f"{r[1]:,} match, {len(r[0])} drawn",
        )
        b = timed(
            "units list, filter ON (page 1 of 50)",
            lambda: selectors.units_page(filtered),
            lambda r: f"{r[1]:,} match, {len(r[0])} drawn",
        )
        c = timed(
            "service_gap_count (the toolbar figure)",
            lambda: selectors.units_gap_count(plain),
            lambda r: f"{r:,} short",
        )
        print(f"    {'ENVELOPE, filter OFF  (list + count)':<44} {a + c:8.3f}s")
        print(f"    {'ENVELOPE, filter ON   (list + count)':<44} {b + c:8.3f}s")
        print(f"    a web worker is given 60s (GUNICORN_TIMEOUT:-60)")
