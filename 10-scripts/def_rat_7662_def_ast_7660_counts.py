#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-RAT-7662 (the signed EXCLUDE USING gist no-overlap constraint on
#          `tariff_versions` was never materialized — `btree_gist` is absent
#          from `06-backend/db/000_extensions.sql` — so two ACTIVATED versions
#          of one schedule can be in force on one date and `R2` refuses the
#          bill with `AmbiguousSchedule`, `apps/rating/resolution.py:963`) ·
#          DEF-AST-7660 (a meter can be installed with `size_class` NULL, and
#          `BR-RAT-108` prices the base charge on that fact)
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set) · hard rule 4 (financial immutability — this
#          script writes NOTHING, see the banner below) · hard-won law 7's
#          fifth shape (a check reporting zero over a scope it silently
#          excludes: every skip is printed beside every count) · law 14 (run it
#          on PostgreSQL, never on the sqlite test settings)
# Tests:   none, deliberately — this is a MEASUREMENT for a human, not a guard.
#          Its two questions are answered by production code it imports rather
#          than re-implements (`apps.rating.resolution.service_prices_by_size_
#          class`, `ScheduleVersion.in_force_on`'s inclusive `effective_to`).
# ───────────────────────────────────────────────────────
"""⛔ **READ-ONLY. THIS SCRIPT WRITES NOTHING, ANYWHERE, EVER.**

It opens no transaction, calls no service, issues no `INSERT`, `UPDATE` or
`DELETE`, and runs no migration. It exists because the Product Owner asked for
**two numbers before anyone touches live data**, and a repair performed before
those numbers are read is a decision nobody made.

⚠ **IT IS ALSO NOT A REPAIR PLAN.** It prints what is wrong and where; which
version wins an overlap, and what a size-less meter's size should be, are
judgments with money attached and they are not made here.

WHAT IT COUNTS
--------------
**(a) OVERLAPPING RATE WINDOWS** — how many `(tenant, schedule, service)`
triples have **two or more ACTIVATED versions in force on the same date**, with
the overlap's dates and the version ids, and whether live accounts sit on the
schedule.

  *ACTIVATED* is `effective_from IS NOT NULL`. `rating/0004` made the column
  nullable and said so in terms: *"a version with NULL effective_from IS the
  draft"*. A draft is not in force on any date and is excluded.

  *IN FORCE ON D* is `effective_from <= D <= coalesce(effective_to, infinity)`.
  ⚠ **`effective_to` IS INCLUSIVE — the LAST day the version prices**
  (`DEF-2889`, 2026-09-01: the exclusive form was wrong by exactly one day, in
  the direction that stops a bill). So two versions overlap when
  `a.effective_from <= coalesce(b.effective_to, 'infinity')` **and**
  `b.effective_from <= coalesce(a.effective_to, 'infinity')` — `<=`, not `<`,
  and a pair that merely touches at one day IS an overlap here because both
  price that day.

**(b) SIZE-LESS METERS** — assets with `size_class` NULL or empty, **split by
whether the unit they are installed on takes a service that prices by size**.
The second group is the one that cannot be billed.

  ⚠ **"PRICES BY SIZE" IS ASKED OF
  `apps.rating.resolution.service_prices_by_size_class` AND IS NOT REWRITTEN
  HERE.** That function's own docstring records `DEF-3098`: three places in
  this product needed to know whether a service is priced BY BAND and all three
  asked *"does this service have any size class rows?"* instead — a proxy that
  `CR-062` broke when solar, battery, storm water and broadband gained a
  CATALOGUE of installable equipment. A fourth place asking the old question
  would be that defect a fourth time.

TENANT SCOPING — WHICH OF THE TWO LAWFUL FORMS THIS USES
--------------------------------------------------------
**Every read runs inside `core.tenancy.tenant_context(tenant.id)`, one tenant
at a time** (hard rule 1). The tenant LIST itself is read once outside that
context, from `tenants`, which is the platform table and carries no
`tenant_id`.

⚠ **SAY THIS OUT LOUD IN ANY REPORT BUILT FROM THIS SCRIPT: on this container
the app role is a PostgreSQL SUPERUSER, so RLS is bypassed and the policies are
NOT what is keeping the counts apart — the `tenant_context` loop is.** The
script prints the role's `rolsuper` / `rolbypassrls` so the reader can see which
guarantee they are actually getting. A number whose scope is unstated is worse
than no number.

WHAT IT SKIPS, AND IT PRINTS EVERY ONE
---------------------------------------
* a service code `service_prices_by_size_class` refuses to answer for —
  `SizeClassNotRuled` (a dimension nobody has ruled) or `KeyError`
  (a code that is not one of the eleven). Neither is resolved by choosing a
  value; both are counted and named under `not_ruled`.
* an asset with no unit at all — on the shelf, retired, or never assigned. It
  has no service and cannot be judged, so it is counted separately and never
  folded into either half of (b).
* a unit that offers no service — it takes nothing, so nothing prices by size.

RUN
---
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local \\
      /root/.venvs/sbh312/bin/python 10-scripts/def_rat_7662_def_ast_7660_counts.py

⚠ **NEVER against `config.settings.test`** — that module hardcodes in-memory
sqlite and ignores `DATABASE_URL` (CLAUDE.md law 14), so it would answer about
an empty database and look exactly like a clean estate.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from core.tenancy import tenant_context  # noqa: E402

INFINITY = date(9999, 12, 31)


def _rows(sql: str, params: tuple = ()) -> list[tuple]:
    """One read. `connection.cursor()` and nothing else — no ORM write path is
    even imported, so there is no code here that COULD write a row."""
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _role_facts() -> tuple[str, bool, bool, str]:
    rows = _rows(
        "select current_user, rolsuper, rolbypassrls, current_database() "
        "from pg_roles where rolname = current_user"
    )
    return rows[0] if rows else ("?", False, False, "?")


def _banded_services() -> tuple[dict[str, bool], dict[str, str]]:
    """`service code -> does it price by BAND`, plus the codes nobody can answer.

    Asked of the production function, once per code, so this script cannot
    disagree with the bill run about what a banded service is.
    """
    from apps.rating.resolution import service_prices_by_size_class
    from apps.tenancy import service_size_classes

    answer: dict[str, bool] = {}
    unanswerable: dict[str, str] = {}
    for code in service_size_classes.SERVICE_ORDER:
        try:
            answer[code] = bool(service_prices_by_size_class(code))
        except service_size_classes.SizeClassNotRuled as unruled:
            unanswerable[code] = f"not ruled — {unruled}"
        except KeyError as unknown:  # pragma: no cover - SERVICE_ORDER is the list
            unanswerable[code] = f"unknown service — {unknown}"
    return answer, unanswerable


# ── (a) OVERLAPPING RATE WINDOWS ───────────────────────────────────────────

OVERLAP_SQL = """
select
    a.tariff_id,
    t.name,
    s.code,
    a.id, a.effective_from, a.effective_to, a.version_label,
    b.id, b.effective_from, b.effective_to, b.version_label
from tariff_versions a
join tariff_versions b
  on b.tariff_id = a.tariff_id
 and b.tenant_id = a.tenant_id
 and b.id > a.id
join tariffs  t on t.id = a.tariff_id
join services s on s.id = t.service_id
where a.effective_from is not null
  and b.effective_from is not null
  and a.effective_from <= coalesce(b.effective_to, date '9999-12-31')
  and b.effective_from <= coalesce(a.effective_to, date '9999-12-31')
order by s.code, t.name, a.effective_from
"""

# Live accounts on the schedule: the account derives its plan from the UNIT
# (CLAUDE.md hard-won law 10's own example), the plan binds the schedule
# through `plan_rate_schedules`, and "live" is the account-status codes that
# still take a bill.
LIVE_ON_TARIFF_SQL = """
select count(*)
from accounts acc
join units u          on u.id = acc.unit_id
join plan_rate_schedules prs on prs.rate_plan_id = u.rate_plan_id
join account_statuses st on st.id = acc.status_id
where prs.tariff_id = %s
  and st.code in ('active', 'pending_activation', 'marked_disconnect', 'vacation_hold')
"""


def overlaps_for_tenant() -> tuple[list[dict], int]:
    """Every overlapping PAIR, folded into `(schedule, service)` triples."""
    triples: dict[tuple, list[dict]] = defaultdict(list)
    for row in _rows(OVERLAP_SQL):
        (
            tariff_id,
            tariff_name,
            service_code,
            a_id,
            a_from,
            a_to,
            a_label,
            b_id,
            b_from,
            b_to,
            b_label,
        ) = row
        start = max(a_from, b_from)
        end = min(a_to or INFINITY, b_to or INFINITY)
        triples[(tariff_id, tariff_name, service_code)].append(
            {
                "a": (str(a_id), a_from, a_to, a_label),
                "b": (str(b_id), b_from, b_to, b_label),
                "overlap_from": start,
                "overlap_to": None if end == INFINITY else end,
            }
        )
    out = []
    pair_count = 0
    for (tariff_id, tariff_name, service_code), pairs in sorted(
        triples.items(), key=lambda kv: (kv[0][2], kv[0][1])
    ):
        pair_count += len(pairs)
        live = _rows(LIVE_ON_TARIFF_SQL, (tariff_id,))[0][0]
        out.append(
            {
                "tariff_id": str(tariff_id),
                "schedule": tariff_name,
                "service": service_code,
                "pairs": pairs,
                "live_accounts": live,
            }
        )
    return out, pair_count


# ── (b) SIZE-LESS METERS ───────────────────────────────────────────────────

# `size_class` is NULL or blank. `assets.service_point_id` names the connection
# the device stands on when it has one; the UNIT it is installed on comes from
# the CURRENT assignment row (`asset_assignments.to_date IS NULL`), which is
# what "installed on" means — an asset can carry a stale service point and no
# current assignment.
SIZELESS_SQL = """
select
    a.id,
    a.asset_no,
    ty.code                              as type_code,
    ty.category                          as type_category,
    asn.unit_id,
    own.code                             as own_service
from assets a
join asset_types ty on ty.id = a.type_id
left join asset_assignments asn
       on asn.asset_id = a.id and asn.to_date is null
left join service_points sp on sp.id = a.service_point_id
left join services own      on own.id = sp.service_id
where (a.size_class is null or btrim(a.size_class) = '')
order by a.asset_no
"""

# What the UNIT takes: every service with a service point on it. That is the
# same list the unit's own Assets tab reads and the bound `ensure_service_point`
# enforces, so a service the address does not offer cannot appear here.
UNIT_SERVICES_SQL = """
select sp.unit_id, s.code
from service_points sp
join services s on s.id = sp.service_id
where sp.deleted_at is null
"""


def sizeless_for_tenant(banded: dict[str, bool], unanswerable: dict[str, str]) -> dict:
    from apps.assets.services import MEASURING_TYPES

    unit_services: dict[str, set[str]] = defaultdict(set)
    for unit_id, code in _rows(UNIT_SERVICES_SQL):
        unit_services[str(unit_id)].add(code)

    buckets = {
        # ⚠ **THE BANDED HALF IS SPLIT BY MEASURING TYPE, AND THAT SPLIT IS THE
        # DIFFERENCE BETWEEN A NUMBER AND A HEADLINE.** `BR-AST-530` offers the
        # connection size for METERS, so a meter on a banded service with no
        # size is a row nobody can bill. A BACKFLOW PREVENTER on the same unit
        # is not: nothing prices it by size and no surface asks it for one.
        # The first draft folded the two together and reported nine where the
        # billable gap is eight — an overstatement of one on a demo tenant, and
        # of whatever the estate's non-measuring count is on a real one.
        "banded_measuring": [],  # CANNOT BE BILLED — the number that matters
        "banded_other": [],  # on a banded service, but not priced by size
        "not_banded": [],  # lawful blank: a capacity service, or sewer
        "no_unit": [],  # on the shelf / retired — no service to judge
        "unit_offers_nothing": [],
        "not_ruled": [],  # bands never ruled — skipped, never guessed
    }
    for asset_id, asset_no, type_code, category, unit_id, own_service in _rows(SIZELESS_SQL):
        entry = {
            "asset_no": asset_no,
            "type": type_code,
            "category": category,
            "own_service": own_service,
        }
        if unit_id is None:
            buckets["no_unit"].append(entry)
            continue
        codes = unit_services.get(str(unit_id), set())
        if not codes:
            buckets["unit_offers_nothing"].append(entry)
            continue
        entry["unit_services"] = sorted(codes)
        if any(banded.get(code) for code in codes):
            entry["banded_services"] = sorted(c for c in codes if banded.get(c))
            # `MEASURING_TYPES` is imported rather than re-listed, for the
            # reason `selectors.metered_service_codes` states about the same
            # set: a tenant-added meter type must land on the same side as the
            # seeded ones, and a hardcoded list here would answer wrongly for
            # it (`BR-AST-009` / `BR-AST-044`).
            key = "banded_measuring" if type_code in MEASURING_TYPES else "banded_other"
            buckets[key].append(entry)
        elif any(code in unanswerable for code in codes):
            buckets["not_ruled"].append(entry)
        else:
            buckets["not_banded"].append(entry)
    return buckets


# ── report ─────────────────────────────────────────────────────────────────


def main() -> int:
    user, is_super, bypass, db = _role_facts()
    banded, unanswerable = _banded_services()

    print("=" * 78)
    print("DEF-RAT-7662 (a) overlapping rate windows · DEF-AST-7660 (b) size-less meters")
    print("READ-ONLY — this run wrote nothing. No INSERT, UPDATE, DELETE or migration.")
    print("=" * 78)
    print(f"database        : {db}")
    print(f"role            : {user}  superuser={is_super}  bypassrls={bypass}")
    if is_super or bypass:
        print(
            "  ⚠ SCOPE NOTE: this role BYPASSES row-level security, so RLS is not what\n"
            "    keeps these counts apart — every read below still runs inside\n"
            "    core.tenancy.tenant_context(<tenant>), one tenant at a time (hard rule 1)."
        )
    else:
        print("  scoping: RLS policies AND an explicit tenant_context per tenant.")
    print()
    print("services that price BY SIZE BAND (asked of rating.resolution, not re-derived):")
    print("  banded     : " + ", ".join(sorted(c for c, v in banded.items() if v)))
    print("  not banded : " + ", ".join(sorted(c for c, v in banded.items() if not v)))
    if unanswerable:
        print("  ⚠ UNANSWERABLE — counted separately below, never guessed:")
        for code, why in sorted(unanswerable.items()):
            print(f"      {code}: {why}")
    print()

    tenants = _rows("select id, subdomain, name from tenants order by subdomain")
    print(f"tenants on this database: {len(tenants)}")
    print()

    total_triples = 0
    total_pairs = 0
    total_live_on_overlap = 0
    totals_b = defaultdict(int)

    for tenant_id, subdomain, name in tenants:
        with tenant_context(tenant_id):
            triples, pairs = overlaps_for_tenant()
            buckets = sizeless_for_tenant(banded, unanswerable)

        print("-" * 78)
        print(f"TENANT {subdomain}  ({name})")
        print("-" * 78)

        print(f"(a) overlapping rate windows: {len(triples)} (tenant, schedule, service) triple(s)")
        total_triples += len(triples)
        total_pairs += pairs
        for triple in triples:
            live = triple["live_accounts"]
            total_live_on_overlap += live
            print(
                f"    · {triple['service']} · {triple['schedule']}"
                f"   live accounts on this schedule: {live}"
            )
            for pair in triple["pairs"]:
                a_id, a_from, a_to, a_label = pair["a"]
                b_id, b_from, b_to, b_label = pair["b"]
                to_text = pair["overlap_to"].isoformat() if pair["overlap_to"] else "open-ended"
                print(f"        in force together {pair['overlap_from'].isoformat()} .. {to_text}")
                print(
                    f"          {a_id}  {a_from} .. {a_to or '(open)'}"
                    f"  {a_label or '(no label)'}"
                )
                print(
                    f"          {b_id}  {b_from} .. {b_to or '(open)'}"
                    f"  {b_label or '(no label)'}"
                )
        if not triples:
            print("    none")

        print("(b) meters with no connection size:")
        for key, label in (
            ("banded_measuring", "A METER ON A SIZE-BANDED SERVICE — CANNOT BE BILLED"),
            ("banded_other", "on a banded service but NOT a meter — no surface asks it a size"),
            ("not_banded", "on a unit whose services do not band — a lawful blank"),
            ("no_unit", "not installed on any unit (shelf / retired) — no service to judge"),
            ("unit_offers_nothing", "on a unit with no service point at all — skipped"),
            ("not_ruled", "on a unit whose services have no ruled bands — skipped"),
        ):
            rows = buckets[key]
            totals_b[key] += len(rows)
            print(f"    {len(rows):5d}  {label}")
            for entry in rows[:20]:
                extra = (
                    "  banded: " + ", ".join(entry["banded_services"])
                    if "banded_services" in entry
                    else ""
                )
                print(f"           {entry['asset_no']}  ({entry['type']}/{entry['category']}){extra}")
            if len(rows) > 20:
                print(f"           … and {len(rows) - 20} more")
        print()

    print("=" * 78)
    print("TOTALS — every tenant on this database")
    print("=" * 78)
    print(f"(a) overlapping (tenant, schedule, service) triples : {total_triples}")
    print(f"    overlapping version PAIRS inside them           : {total_pairs}")
    print(f"    live accounts sitting on an overlapping schedule: {total_live_on_overlap}")
    print(f"(b) size-less METERS on a banded service, UNBILLABLE: {totals_b['banded_measuring']}")
    print(f"    size-less non-meters on a banded service        : {totals_b['banded_other']}")
    print(f"    size-less, service does not band (lawful)       : {totals_b['not_banded']}")
    print(f"    size-less, not installed on a unit              : {totals_b['no_unit']}")
    print(f"    size-less, unit offers no service   [SKIPPED]   : {totals_b['unit_offers_nothing']}")
    print(f"    size-less, service bands not ruled  [SKIPPED]   : {totals_b['not_ruled']}")
    print()
    print("Nothing was written. To repair either finding, a separate change is required")
    print("and the Product Owner sees these numbers first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
