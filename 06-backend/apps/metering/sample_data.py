# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S14, S15,
#           S16 (premises, units, the guided add) · S25/S28/S29 (the reads this
#           writes) · S8 (Sample data panel, BR-TEN-069)
# Rules:    BR-TEN-056 (the sample set) · BR-TEN-057 (`is_sample` on the owning
#           row) · BR-TEN-061 (removal order) · BR-TEN-062 (sample reads are
#           the ONE deletion path in metering) · BR-TEN-063 (idempotent,
#           audited) · BR-MET-002 (unit labels) · BR-MET-003 (services ⊆
#           enabled) · BR-MET-012/015/017/018 (stage → validate → disposition →
#           atomic commit) · BR-MET-033 (route membership stamps the service
#           point) · CLAUDE.md rule 3 (consumption carries its unit)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py ·
#           06-backend/tests/test_cr030_w1_import_seed.py (CR-030 W1 T1.23)
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves both seams
#           below) · apps/assets (meters land on these units) · apps/customers
#           (accounts occupy them, and its sample block resolves
#           `sample_account_cutover_seat` below — CR-030 W1 T1.23)
# ───────────────────────────────────────────────────────
"""metering's half of the sample set: the premises, units, service points —
and, separately, the three months of meter reads (DEF-153).

TWO SEAMS, NOT ONE, AND THE SPLIT IS DELIBERATE
------------------------------------------------
`seed_sample_records` writes the PLACES; `seed_sample_reads` writes the
MEASUREMENTS. They are named separately in `apps/tenancy/seams.py` because a
read cannot exist before the meter it is taken from, and the meter belongs to
apps/assets, which runs between them. Merging the two would force metering to
create assets, which B1 forbids.

EVERY ROW GOES THROUGH THE SCREEN'S OWN SERVICE
------------------------------------------------
Premises and units through `create_premises` — the S16 guided add, units and
service points in the same transaction. Reads through the FULL S28 pipeline:
`stage_read_batch` → `validate_read_batch` → `set_row_disposition` →
`commit_read_batch`. Nothing writes a `meter_reads` row directly, which matters
more here than anywhere else in the fixture: the validation engine is what
decides whether a reading is plausible, and a fixture that inserted around it
would seed reads no clerk could have entered.

THE AWKWARD CASES THIS MODULE OWNS (spec §4)
---------------------------------------------
* **3 unreadable meters in August** — the batch simply carries no row for them,
  which is what a clerk who could not get to the meter actually produces. That
  is what makes the S25 "Estimate a missing read" screen have something to do.
* **1 disputed read** — flagged through metering's own dispute marker, so the
  counter on the reads screen is not stuck at zero.
* **1 meter replaced mid-history** — the June read is on the old serial and the
  July and August reads are on the new one, so a read chain crosses two
  registers and still totals correctly.

WHY AUGUST IS READ AND NOT BILLED
----------------------------------
Spec §3, and it is the whole point of the fixture: *"August is left UNBILLED on
purpose, so the PO can run a billing run themselves and watch it work. A fixture
that arrives with everything done leaves nothing to evaluate."* This module
therefore seeds the August READS and nothing in this repository bills them.
"""

from __future__ import annotations

import logging
import uuid
import zlib
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count
from django.utils import timezone as django_timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models, seams, selectors, services
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.metering")

# ── W5-T1 · THE SAMPLE PLANT USES THE PRODUCT'S OWN GRAMMAR (D5) ───────────
#
# ⚠ **THESE TWO CONSTANTS USED TO BE THE CODES THEMSELVES — `"SCW-M"` and
# `"SCW-R1"` — AND THAT WAS A SECOND NAMING GRAMMAR SHIPPING BESIDE THE RULED
# ONE.** The PO ruled D5 *"Rt-001 is good"*, the demo command obeys it, and this
# seam — which runs for EVERY tenant that opts into sample data, not only the
# demo — kept minting the old one. On the seeded tenant Settings → Routes &
# Cycles drew `RT-001 … RT-006` beside `SCW-R1`, and `SCW-R1` was the row
# holding 41 of the 44 premises and all 48 accounts while `CY-001` read 0.
# Found by W5-T8's browser walkthrough and by nothing else (hard-won law 6).
#
# **THE CODE NOW COMES FROM THE NUMBER SERIES**, like every other route and
# cycle: `create_route`/`create_cycle` allocate `RT-###`/`CY-###` when no code
# is given (BR-MET-073 / BR-MET-077). So idempotency (BR-TEN-063) can no longer
# key on the code — a series-allocated code differs on every call and a naive
# fix would mint a new route on every replay. It keys on the sample rows' own
# stable NAMES instead, and still recognises the historical `SCW-*` codes so a
# tenant seeded before this change is not seeded a second time.
SAMPLE_CYCLE_NAME = "Silver Creek — monthly"
SAMPLE_ROUTE_NAME = "Silver Creek — monthly walk"
#: The codes this seam minted before W5-T1. Kept ONLY so an already-seeded
#: tenant is still recognised as seeded; nothing writes them any more.
LEGACY_SAMPLE_CYCLE_CODE = "SCW-M"
LEGACY_SAMPLE_ROUTE_CODE = "SCW-R1"

# ── DEF-256 · the districts the demo utility is actually laid out in ────────
#
# THE DEFECT, in one line from the live database: `select count(*) from
# premises where area_id is null` returned **50 of 50**, on a tenant that had
# just been seeded four districts. The Settings card showed North / Downtown /
# East / Industrial corridor and every premises row on the demo read "—", so a
# Product Owner reviewing the seeded product saw a vocabulary that looked
# configured and was used by nothing. Nothing broke, nothing warned, and the
# suite was green — which is the definition the failure-mode map applies:
# **an object whose absence fails silently is a defect.**
#
# WHY A STREET MAP AND NOT A COUNTER. `unit_index % 4` would fill every column
# and prove nothing: districts are geography, and a demo whose neighbours sit
# in different districts is a demo nobody can reason about. Silver Creek's five
# streets map onto the four seeded districts, so every district is exercised
# and the two premises on one street are always in one district — which is what
# makes the SET-06 area filter and BR-MET-083's route cascade demonstrable on
# seeded data rather than only in a test.
#
# ⚠ THE CODES ARE THE PLATFORM FIXTURE'S, NOT NEW VOCABULARY. NORTH / DTWN /
# EAST / IND are `lookup_defaults.json`'s own four rows. This file invents no
# area; if a tenant renamed or removed one, `_area_code_for` below simply
# leaves that premises without an area rather than refusing the whole plant.
#
# ── CR-039 wave E task 22 · EACH STREET NOW NAMES ITS FINEST AREA ───────────
#
# PO, 2026-08-26, looking at a provisioned tenant: *"Why you dont have sub
# areas below - Areas metering 4 North district · Downtown · East district ·
# Industrial corridor"*. Four flat rows was the whole hierarchy any tenant had
# ever received, so the filter BR-MET-066b was written for had nothing to
# filter and nobody could discover that the second level works at all.
#
# **THE VALUE IS A CHAIN, FINEST FIRST**, because a tenant may hold the
# district and not the sub-area: `areas` is SAMPLE content (BR-TEN-067), the
# S111 toggle can suppress it, a tenant provisioned before fixture V2.48.0.1
# has the four districts and none of the three sub-areas, and BR-TEN-036
# protects a seeded row from deletion but not from never having arrived.
# `_area_code_for` walks the chain and takes the first code the tenant
# ACTUALLY HOLDS — so a tenant with sub-areas gets `North district · NW` and a
# tenant without gets `North district`, which is strictly what it got before.
# **A one-element chain is a street whose district has no sub-area**, and two
# of the five are deliberately that way: the demo has to show a premises tagged
# at the top level and the "this area has no sub-areas" help text, or half of
# BR-MET-066b is undemonstrable on seeded data.
#
# ⚠ WHICH QUADRANT A STREET SITS IN IS ARBITRARY-BUT-FIXED, exactly as its
# DISTRICT already was (see DEF-256 above): the fixture's streets are fictional
# and no source assigns them a compass position. What is NOT arbitrary is the
# property that made DEF-256 pick a street map over `unit_index % 4` — the two
# premises on one street stay together, so a person can reason about the demo.
AREA_BY_STREET: dict[str, tuple[str, ...]] = {
    "Silver Creek Rd": ("NORTH-NW", "NORTH"),
    "Willow Bend Dr": ("NORTH-NE", "NORTH"),
    "Cedar Ridge Way": ("EAST-SE", "EAST"),
    "Mill Pond Ln": ("DTWN",),
    "Quarry Hill Ct": ("IND",),
}

# ── CR-028 AST-W5 T3 (§10-D6): seeded coordinates, DETERMINISTIC, NO NETWORK ─
#
# The AST-03 map needs the demo plant on real-looking streets, and seeding must
# never call the geocoder: a network dependency in a seed path fails on every
# air-gapped or proxied deploy and makes the fixture non-deterministic. So each
# fixture street gets an ANCHOR in r10's own Austin-area ballpark (assets-map.js
# draws 30.22–30.31 / −97.77…−97.70) and each address a small, STABLE jitter
# derived from crc32 of the address string — crc32, not hash(), because
# PYTHONHASHSEED would otherwise move every pin per process. A replay computes
# the same coordinates and writes nothing (BR-TEN-063), and a coordinate an
# operator has set is NEVER overwritten (the geocode.py law, applied here too).
#
# The map's AREA facts ride the EXISTING BR-MET-071 area link seeded above —
# no coordinate-derived area, no second vocabulary.
#: ⚠ **EVERY STREET THIS FIXTURE INVENTS NEEDS A LINE HERE, AND FOR ELEVEN DAYS
#: TWENTY-THREE OF THEM DID NOT HAVE ONE (`DEF-MET-4288`).** The first five are
#: `premises_plan()`'s and were the only ones anchored; everything below is an
#: estate that arrived later — `cr030_premises_plan()`, then `W6_SEATS`, then
#: `W7_SEATS` — and **every seeded work order stands on one of those**. Their
#: premises kept `lat`/`lng` NULL, so `WRK-09`, the work map, put **17 of 17
#: open jobs** in *not on the map* and drew nothing at all. Nothing read as
#: broken, because `dispatch.map_pins` walks to the premises exactly as hard
#: rule 8 requires and names its reason for every order it cannot place: the
#: screen was telling the truth about data that could not be drawn.
#:
#: ⚠ **THE REAL LESSON IS THAT THE FILL PASS USED AN ALLOW-LIST OF ADDRESSES,
#: SO EVERY ESTATE ADDED AFTER IT WAS EXCLUDED BY CONSTRUCTION AND IN SILENCE.**
#: Widening the list would have bought exactly one more estate's worth of time.
#: `apply_premises_geo` now walks the tenant's SAMPLE premises and asks this
#: table, so a new estate on an anchored street is covered with no edit at all
#: — and one on a NEW street is REPORTED by `premises_geo_report()` rather than
#: quietly skipped.
#:
#: Latitude and longitude in **WGS 84 decimal degrees**, the frame
#: `premises.lat` / `premises.lng` are declared in and the only one Leaflet and
#: a tile server read (hard rule 3's spirit — a number carries its frame).
#: Every anchor sits inside the same Austin box as the original five, so one
#: `fitBounds` still frames the whole demo estate.
#:
#: ⚠ **`Kestrel Park ph. 2` IS A WHOLE ADDRESS AND NOT A STREET**, because that
#: is what the fixture calls the place — a phase of a development with no house
#: number. The lookup is a suffix match, so a full address is a lawful key here;
#: it is called out rather than left to look like a typo.
STREET_GEO: dict[str, tuple[str, str]] = {
    "Silver Creek Rd": ("30.245200", "-97.765100"),
    "Willow Bend Dr": ("30.260300", "-97.760200"),
    "Cedar Ridge Way": ("30.290100", "-97.700300"),
    "Mill Pond Ln": ("30.268100", "-97.742300"),
    "Quarry Hill Ct": ("30.222100", "-97.752400"),
    # ── the CR-030 estate — `cr030_premises_plan()` (`DEF-MET-4288`) ─────────
    "Elm Street": ("30.251400", "-97.748600"),
    "Sable Court": ("30.238900", "-97.733200"),
    "Hillside Ave": ("30.276400", "-97.756900"),
    "Industrial Way": ("30.231700", "-97.712500"),
    "Pine Vista": ("30.284200", "-97.727800"),
    "Oak Ridge Dr": ("30.271900", "-97.717400"),
    "Main St": ("30.258600", "-97.744100"),
    "Larkspur Way": ("30.246300", "-97.723600"),
    # ── the new-connection and move seats — `W6_SEATS` · `W7_SEATS` ──────────
    "Foundry Row": ("30.264800", "-97.755400"),
    "Willow Bend": ("30.255100", "-97.762700"),
    "Quarry Lane": ("30.228400", "-97.749100"),
    "Cedar Ct": ("30.287300", "-97.706200"),
    "Harbour View": ("30.241700", "-97.719800"),
    "Kestrel Park ph. 2": ("30.279600", "-97.735500"),
    "Marten Row": ("30.233900", "-97.740600"),
    "Kestrel Close": ("30.281200", "-97.731400"),
    "Alder Street": ("30.249800", "-97.709700"),
    "Meadowbank Rise": ("30.266500", "-97.703800"),
    "Tanner Street": ("30.253300", "-97.714900"),
    "Bakers Row": ("30.243100", "-97.757800"),
    "Selby Drive": ("30.273400", "-97.746200"),
    "Poplar Grove": ("30.226700", "-97.723100"),
    "Winterton Close": ("30.288900", "-97.741700"),
}


#: The address that deliberately offers LESS than the tenant sells (DEF-780), so
#: a demo can show BR-MET-119 refusing a meter rather than only ever allowing
#: one. Chosen as a single-family premises with no sub-metering, so holding it
#: back strands no seeded meter, plan or bill line.
NARROW_OFFER_PREMISE_NO = "P-00044"
NARROW_OFFER_SERVICES = ("water",)


def _offer_for(entry: dict, services_for_units: tuple[str, ...]) -> list[str]:
    """What this sample ADDRESS offers — BR-MET-119's first link.

    Every address offers what the tenant sells, EXCEPT the one held back above.
    Offering the tenant's own enabled set is the honest default for a fixture: a
    demo estate is meant to be workable, and an address that offers less than
    the utility sells is the exception a real utility records deliberately, not
    the norm.

    ⚠ Falls back to `services_for_units` when the seam is unwired, because a
    premises that offers LESS than its own units already use is a fixture that
    contradicts itself, and that is worse than a narrow offer.
    """
    if str(entry.get("premise_no") or "") == NARROW_OFFER_PREMISE_NO:
        return list(NARROW_OFFER_SERVICES)
    enabled = tuple(seams.enabled_service_codes())
    return list(enabled or services_for_units)


def _coords_for(address_line: str) -> tuple[Decimal, Decimal] | None:
    """The address's deterministic seed coordinates, or None off-plan.

    ⚠ **LONGEST ANCHOR FIRST.** The match is a suffix, and two anchors can both
    end an address — `Willow Bend` and `Willow Bend Dr` are two different places
    in this fixture. Iterating a dict would hand the answer to whichever was
    typed first, which is a coin toss that would read as a correct lookup for as
    long as nobody noticed a pin in the wrong street.
    """
    import zlib

    for street in sorted(STREET_GEO, key=len, reverse=True):
        lat, lng = STREET_GEO[street]
        if address_line.endswith(street):
            stamp = zlib.crc32(address_line.encode("utf-8"))
            # ±0.0032° of jitter (~350 m) — houses spread along their street,
            # every pin stays inside the anchors' Austin box.
            lat_offset = Decimal(((stamp & 0xFF) - 128)) * Decimal("0.000025")
            lng_offset = Decimal((((stamp >> 8) & 0xFF) - 128)) * Decimal("0.000025")
            return (Decimal(lat) + lat_offset, Decimal(lng) + lng_offset)
    return None


def fixture_addresses() -> list[str]:
    """Every address the SAMPLE SEEDERS invent, across all four plans.

    `premises_plan()` (44) · `cr030_premises_plan()` (8) · `W6_SEATS` and
    `W7_SEATS`, which are declared in this module because premises are
    metering's table (B2 r4). Used by the no-database guard that asks whether
    every address the fixture invents can be placed at all; the fill pass itself
    does NOT filter on this list — see `apply_premises_geo`.
    """
    return (
        [entry["address_line"] for entry in fixture.premises_plan()]
        + [entry["address_line"] for entry in fixture.cr030_premises_plan()]
        + [entry["address_line"] for entry in (*W6_SEATS, *W7_SEATS)]
    )


def premises_geo_report() -> dict[str, Any]:
    """What this tenant's sample premises can and cannot be placed. No writes.

    ⚠ **A COUNT OF WHAT WAS FILLED IS INDISTINGUISHABLE FROM A COMPLETE JOB
    UNLESS IT SAYS WHAT IT SKIPPED (hard-won law 7).** `apply_premises_geo`
    returned only a number, so every run reported a healthy figure over three
    whole estates it was never looking at. `unanchored` names each sample
    address whose street has no line in `STREET_GEO`, so an estate added on a
    new street produces a LIST rather than a blank map somebody has to explain.

    ⚠ **`unplaceable_addresses` IS DERIVED FROM THE FIXTURE AND NEEDS NO
    DATABASE**, which is what lets the cheapest guard against this defect run in
    under a second; the other two counts read the tenant in context.
    """
    rows = models.Premises.objects.filter(tenant_id=_tenant_id(), is_sample=True)
    blank = [row.address_line for row in rows.filter(lat__isnull=True)]
    return {
        "sample_premises": rows.count(),
        "without_coordinates": len(blank),
        "unanchored": sorted({one for one in blank if _coords_for(one) is None}),
        "unplaceable_addresses": sorted(
            {one for one in fixture_addresses() if _coords_for(one) is None}
        ),
    }


def apply_premises_gis_states(actor: Any) -> int:
    """CR-089 wave A — give the demo estate the THREE GIS states a screen draws.

    ⚠ **WITHOUT THIS PASS TWO OF WAVE A'S NINE TASKS CANNOT BE DEMONSTRATED AT
    ALL, AND CR-089 §3 SAYS SO IN ITS OWN WORDS:** *"The fixture must be
    re-seeded or three waves cannot be demonstrated"* — `premises.gis_unchecked`
    *"is set on **none** of the 673 properties"*, so the flag had **no true
    case** anywhere in the product, and `external_ref` is *"empty on all 673"*,
    so the field `BR-MET-1163` relabels **Parcel ID** had nothing to show.

    A column that means something and has never held a value is indistinguishable
    from a column nothing writes: the screen looks finished and the state nobody
    has seen is the one that is wrong in production (hard-won law 2's shape).

    THREE STATES, ONE PER GROUP, ALL DETERMINISTIC AND ALL IDEMPOTENT:

      * **Not placed** — the properties with no coordinates. `apply_premises_geo`
        leaves 6 of the 79 on this plant unanchored, and those are exactly the
        rows a clerk typed past a City that could not answer, so `gis_unchecked`
        is set TRUE on them. That is the `OQ-INT-1471` branch, stated rather
        than simulated, and it is what **Needs a location** finds.
      * **Checked** — every fourth placed property is stamped with a person and
        a date, so *Checked against GIS · Checked · <name>, <date>* has a case.
      * **Not checked yet** — everything else: placed, flag false, no stamp.
        This is the majority and it is the honest reading of the estate as it
        stands, because `gis_unchecked=false` is a DEFAULT and not an answer.

    ⚠ **THE PARCEL NUMBERS ARE INVENTED, AND THAT IS LAWFUL HERE AND NOWHERE
    ELSE.** CR-089 §4 rules that backfilling the 673 real properties is OUT OF
    SCOPE — *"inventing them is not available to us"*. This writes only rows
    `is_sample` marks as the fixture's own, the same fence `apply_premises_geo`
    uses and for the same reason: a REAL address a clerk typed must never be
    given a fictional parcel, and `BR-TEN-061` deletes exactly this set.

    ⚠ **IT NEVER OVERWRITES.** Guarded on `external_ref IS NULL` and on the
    stamp being absent, so a replay, a City-picked parcel and an operator's own
    edit all survive — the posture `apply_premises_geo` already takes for a pin.

    Returns how many rows were written.
    """
    written = 0
    tenant_id = _tenant_id()
    rows = list(
        models.Premises.objects.filter(tenant_id=tenant_id, is_sample=True).order_by(
            "premise_no", "id"
        )
    )
    # The person who did the checking, from the tenant's own staff — never an
    # invented name. `None` is survivable: the stamp then reads as a date with
    # no name rather than failing the seed.
    checker = _identity_user_id(actor)
    confirmed_seen = 0
    for index, row in enumerate(rows):
        fields: list[str] = []
        # ⚠ **EVERY SEVENTH IS THE `OQ-INT-1471` BRANCH, AND THE TWO HALVES GO
        # TOGETHER BECAUSE THAT IS WHAT THE COLUMN MEANS.** The model says it in
        # terms: *"A property created from a picked candidate carries the City's
        # parcel key in `external_ref`; one typed past an unreachable City
        # carries nothing"*. So a row marked unchecked gets NO parcel — marking
        # the flag while handing it a parcel key would seed a state the product
        # cannot produce, and a fixture that contradicts the code is worse than
        # a thin one.
        # ⚠ It KEEPS its geocoded pin, and that pair is correct rather than
        # sloppy: `geocode_premises` asks the US Census Bureau for a POINT, the
        # City confirms the ADDRESS and its parcel, and one is not the other.
        # Placed-but-unconfirmed is a real state and a common one.
        typed_past_the_city = index % 7 == 6
        if typed_past_the_city:
            if not row.gis_unchecked:
                row.gis_unchecked = True
                fields.append("gis_unchecked")
        else:
            if not row.external_ref and row.premise_no:
                # The assessor's format CR-089 `A2` names — `R-114-0082-004` —
                # with the last groups taken from this property's own number, so
                # it is deterministic, unique per tenant (the partial CI index)
                # and obviously fictional to anybody reading the demo.
                digits = "".join(ch for ch in row.premise_no if ch.isdigit()) or "0"
                row.external_ref = f"R-114-{int(digits):04d}-{int(digits) % 1000:03d}"
                fields.append("external_ref")
            confirmed_seen += 1
            if confirmed_seen % 4 == 0 and row.gis_checked_at is None:
                row.gis_checked_by_id = checker
                row.gis_checked_at = django_timezone.now()
                fields.extend(["gis_checked_by", "gis_checked_at"])
        if fields:
            row.save(update_fields=[*fields, "updated_at"])
            written += 1
    return written


def apply_premises_geo() -> int:
    """Fill lat/lng on this tenant's SAMPLE premises that have none.

    A direct write on this module's own rows (the `_tag` disposition — no
    service accepts coordinates), guarded on `lat IS NULL` so a replay and an
    operator's hand-set pin are both safe. Returns how many rows gained
    coordinates.

    ⚠ **IT SELECTS BY `is_sample`, NOT BY AN ADDRESS ALLOW-LIST, AND THAT IS THE
    HEART OF `DEF-MET-4288`.** It used to filter `address_line__in
    premises_plan()` — 44 addresses of the four estates this fixture now plants
    — so `cr030_premises_plan()`, `W6_SEATS` and `W7_SEATS` were excluded **by
    construction and in silence**, and every seeded WORK ORDER stands on one of
    those. Widening the list would have bought one estate's worth of time;
    asking *is this one of ours* buys every estate that ever arrives.
    ⚠ **AND `is_sample` IS THE RIGHT FENCE RATHER THAN A CONVENIENT ONE:** a
    REAL premises a clerk typed must never be given a fictional Austin pin — it
    is geocoded by `manage.py geocode_premises`, which asks the US Census
    Bureau. This writes only rows the sample seeder planted and the sample
    remover would take away (`BR-TEN-057`).

    ⚠ **IT MUST ALSO RUN AFTER EVERY ESTATE HAS BEEN PLANTED, AND THAT IS THE
    OTHER HALF.** The call used to sit beside `_ensure_cycle_and_route`, which
    is BEFORE `_seed_cr030_estate` and the `_seed_w6_*` blocks — so even with
    the selection fixed, those rows did not exist yet and a fill pass could not
    have seen them. Two independent causes of one empty map; fixing either alone
    changes nothing. It is now the last write of `seed_sample_records` before
    the owner passes.
    """
    written = 0
    unanchored: set[str] = set()
    for row in models.Premises.objects.filter(
        tenant_id=_tenant_id(), is_sample=True, lat__isnull=True
    ):
        coords = _coords_for(row.address_line)
        if coords is None:
            unanchored.add(row.address_line)
            continue
        row.lat, row.lng = coords
        row.save(update_fields=["lat", "lng", "updated_at"])
        written += 1
    if unanchored:
        # NAMED, never a silent skip — see `premises_geo_report` above.
        logger.warning(
            "sample data (DEF-MET-4288): %d sample address(es) have no street anchor "
            "in STREET_GEO and will have no place on any map: %s",
            len(unanchored),
            ", ".join(sorted(unanchored)),
        )
    return written


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _tag(queryset: Any) -> int:
    """BR-TEN-057 — the tag is written by THIS module's own service on the
    sample path and by nobody else (tenancy may not, B1/BR-TEN-013)."""
    return int(queryset.update(is_sample=True))


#: ── BR-MET-401 / DEF-650 — every seeded premises names an OWNER ───────────
#: PO 2026-08-27: *"without owner how you can create premsies"*. Since that rule
#: the seed cannot create an address without a party, and the whole demo estate
#: is created through `create_premises` on purpose (this module's own header:
#: *"through create_premises, the S16 guided add"*).
#:
#: ⚠⚠ **AN EARLIER DRAFT INVENTED A PARTY HERE AND A RATIFIED GUARD CAUGHT IT,
#: WHICH IS WHY THIS COMMENT IS LONG.** It created *"Unrecorded owner (sample)"*
#: with a `landlord` category to hold the link, and
#: `test_cr039_c14__no_seeded_owner_has_an_INVENTED_category` failed exactly as
#: it was written to: *"A category is a claim about a real party; state its basis
#: in the fixture or leave the premises unmatched."* That guard is right and this
#: code was wrong — BR-MET-151 clause 3 forbids a category nothing states, and a
#: seeder is not exempt from it.
#:
#: **So no party is invented.** `sample_fixture.owner_category_for` answers None
#: for names the corpus deliberately does not categorise — *"what leaves a fresh
#: demo with real rows on BR-MET-151's matching review list"* — and those
#: addresses are created holding a party the fixture DOES state, then have the
#: link CLEARED. Every party on a seeded tenant therefore traces back to a name
#: `OWNER_CATEGORY_BY_NAME` names, and the review list still has rows on it.


def _sample_owner_id(actor: Any, owner_manager: Any) -> str:
    """A typed owner id for a seeded premises. Reuses the party by name.

    Where the corpus states no category, this answers the HOLDER below rather
    than minting anything — see the block comment above for why that matters.
    """
    from apps.metering import premises_owners as owner_services

    name = str(owner_manager or "").strip()
    category = fixture.owner_category_for(name) if name else None
    if category is None:
        return _sample_holder_owner_id(actor)
    found = owner_services.resolve_owner_name(name)
    if found["match"] == "exact":
        return str(found["owner"]["id"])
    return str(
        owner_services.create_premises_owner(
            actor,
            {
                "name": name,
                "category": category,
                # BR-MET-151 clause 4 — which free-text string became this party,
                # so a seeded party is indistinguishable in SHAPE from one a
                # clerk matched by hand.
                "source_owner_manager": name,
            },
        )["id"]
    )


def _sample_holder_owner_id(actor: Any) -> str:
    """A party that ALREADY EXISTS IN THE CORPUS, borrowed for one moment.

    ⚠ **IT IS DETERMINISTIC AND IT IS NOT A DEFAULT OWNER.** The link it holds is
    cleared before the seed returns (`_restore_unmatched_premises`), so no seeded
    address ends up owned by it; picking the alphabetically-first stated name
    means the same tenant seeded twice borrows the same party, which is BR-TEN-063
    idempotency rather than a preference about landlords.
    """
    name = sorted(fixture.OWNER_CATEGORY_BY_NAME)[0]
    return _sample_owner_id(actor, name)


def _restore_unmatched_premises(actor: Any) -> int:
    """Put the un-categorised addresses back on the matching review list.

    ⚠ **THROUGH `update_premises`, NEVER `.update()`** — this module's own rule,
    and `_resolve_owner` reads an empty string as *clear the link*, which is a
    lawful clerk act. The free text is untouched (BR-MET-151 clause 4), so the
    address reads exactly as a migrated tenant's does: a name in a box and no
    party behind it.

    ⚠ **IT KEYS OFF THE FREE TEXT, NOT OFF WHICH PARTY IS LINKED.** Keying off
    the holder party would clear an address whose own name happens to be that
    party's, which on a demo estate is a real case.
    """
    tenant_id = _tenant_id()
    cleared = 0
    for premises_id, owner_manager in models.Premises.objects.filter(
        tenant_id=tenant_id, deleted_at__isnull=True, owner_id__isnull=False
    ).values_list("id", "owner_manager"):
        if fixture.owner_category_for(str(owner_manager or "").strip() or None) is not None:
            continue
        services.update_premises(actor, premises_id, {"owner_id": ""})
        cleared += 1
    return cleared


def estate() -> fixture.EstatePlan:
    """THE ESTATE THIS TENANT CAN BE GIVEN — CR-039 wave A, DEF-795.

    ⛔ **WHAT THIS REPLACED, AND WHY IT WAS THE DEFECT.** `_fixture_services()`
    read `fixture.FIXTURE_SERVICES ∩ enabled` — a literal `water · sewer ·
    trash` intersected with what the utility sells. An **electric + gas** tenant
    intersected to the EMPTY SET, the premises block returned an honest `0`
    ("nothing this fixture prices is enabled"), the reads block returned early
    on `if "water" not in enabled`, and the utility received a correctly
    provisioned tenant with nothing in it. The PO met it on 2–3 real tenants.

    The refusal was never the bug — a seeder must not plant a service the
    utility does not sell (BR-MET-003) — the FIXTURE was. So this resolves the
    tenant's own enabled set and its own declared units and hands back an estate
    SHAPED for it: an electric utility gets electric meters in kWh, a gas
    utility gas meters in ccf, and a water utility gets water in kgal exactly as
    before.

    ⚠ **AND SINCE `CR-062` C1 (PO statement (8), 2026-09-02) IT IS EVERY METERED
    SERVICE THE TENANT SELLS, NOT ONE.** `EstatePlan.metered` is a row per
    service with that service's own unit and factor; `plan.primary` is the first
    of them and is what the awkward-case demonstrations hang on. A utility
    selling electric + water used to receive a water estate and an electric
    refusal — 95 bills with electric on none of them — which the PO ruled not
    acceptable.

    Two reads, both through this module's published seam (B1), resolved ONCE per
    block rather than per premises — DEF-256's lesson.

    ⚠ **FOUR READS SINCE BR-MET-143 (2026-08-27), AND THE EXTRA TWO ARE HERE
    FOR AGREEMENT RATHER THAN FOR THIS MODULE'S OWN USE.** metering seeds no
    meter, so `EstatePlan.multiplier` is not a number this block writes. But
    `apps/assets/sample_data._estate()` resolves the SAME plan, and under
    BR-MET-143 a backbone whose register unit and billed unit no multiplier can
    reconcile is REFUSED. If this call did not pass the same inputs, the two
    modules would disagree about the backbone — metering would seed premises,
    units and read batches for a service assets planted no meter in, and the
    disagreement would surface as `unknown_meter` on 49 rows, which is exactly
    the failure the docstring above warns about.
    """
    return fixture.estate_plan(
        seams.enabled_service_codes(),
        seams.service_default_uoms(),
        seams.service_billed_uoms(),
        seams.unit_reconciliation,
    )


def _fixture_services() -> list[str]:
    """The services each seeded UNIT receives (BR-MET-003).

    On a tenant that sells water this is `water · sewer · trash` ∩ enabled — the
    same list, in the same order, that the pre-CR-039 intersection produced.
    """
    return list(estate().services)


def unseeded_services() -> list[str]:
    """Services this tenant SELLS that the seeded estate does not speak.

    ⚠ **THE QUESTION CHANGED WITH CR-039 AND THE NAME DID NOT.** It used to
    answer *"which of water/sewer/trash did this tenant not enable"* — which on
    an electric tenant listed all three and told them nothing, because the
    fixture had no electric estate to offer either way. It now answers the
    question a utility actually asks: *"I sell gas — where is it?"* Each code
    here has a sentence in `estate().refused` saying why.

    ⚠ **AND NOTHING CALLS IT — measured 2026-08-26, `grep -rn "unseeded_services"
    apps/ tests/` returns this definition and no consumer.** It was written as
    BR-TEN-060's report-by-name and no screen, endpoint or log line has ever read
    it, so a utility has never been told which of its services the demo skipped
    (hard-won law 2: built is not wired). This lane makes the ANSWER correct and
    does not wire it: the surface that shows a seeding outcome is CR-039 wave
    B's task 6, and inventing a second one here would be two places to keep in
    step. What DOES reach a human today is the `logger.info` in
    `seed_sample_records` and the `BlockCannotRun` sentence on a refusal —
    both carry the same `estate().refused` text.
    """
    return [code for code, _reason in estate().refused]


def _plan_id_for(unit_index: int) -> str | None:
    """The plan this unit's account will derive from (PO: *"the account derives
    its plan from the unit"*).

    Resolved through the seam BY CODE, never by taking the first plan in the
    list. That shortcut is how a lane once put every unit in a fixture onto a
    water-only Small Commercial plan — a wrong-cohort fixture that passed every
    gate because nothing checked WHICH plan.

    ⚠ **THREE CLASSES SINCE `CR-062` ADDENDUM J4, AND THE FALLBACK IS THE
    CAREFUL PART.** `fixture.plan_class_for` replaced a boolean, because *"not
    commercial"* is a perfectly well-formed answer that would have put the
    industrial plant on the household ladder and billed it the `$12.00`
    residential electric base instead of the signed `$180.00`. The INDUSTRIAL
    plan is seeded only where it prices something the commercial one does not
    — electricity — so on a water-only utility `industrial_plan_id()` is
    `None`; the seat then takes the commercial plan rather than NO plan, since
    a unit with no `rate_plan_id` refuses activation outright (`BR-MET-040`)
    and one seat lost is a worse answer than one seat on a near-enough plan.
    """
    from apps.rating import sample_data as rating_sample  # documented seam target

    plan_class = fixture.plan_class_for(unit_index)
    if plan_class == "industrial":
        return rating_sample.sample_plan_id(
            rating_sample.PLAN_INDUSTRIAL
        ) or rating_sample.sample_plan_id(rating_sample.PLAN_COMMERCIAL)
    code = (
        rating_sample.PLAN_COMMERCIAL
        if plan_class == "commercial"
        else rating_sample.PLAN_RESIDENTIAL
    )
    return rating_sample.sample_plan_id(code)


def _seeded_area_codes() -> set[str]:
    """The area codes this tenant actually holds, upper-cased for matching.

    Read through tenancy's ORM the same way `services._resolve_area` does —
    `areas` is tenancy's table and metering resolves against it by code, which
    is a reviewed cross-module read (B2 §2), not a cross-module WRITE.
    """
    from apps.tenancy import models as tenancy_models

    return {
        str(code).upper()
        for code in tenancy_models.Area.objects.filter(tenant_id=_tenant_id()).values_list(
            "code", flat=True
        )
    }


def _area_code_for(address_line: str, available: set[str]) -> str | None:
    """This address's FINEST area — its sub-area if the tenant holds one, its
    district otherwise, or None if the tenant holds neither.

    **NONE IS A REAL ANSWER, and it is why this returns rather than refuses.**
    A tenant may have renamed, deactivated or deleted any seeded area — the
    lookup laws entitle them to (BR-TEN-036 protects seeded rows from DELETION,
    not from a tenant who never received them because the S111 toggle was off).
    A sample plant that refused the whole premises block over a missing
    district would turn a cosmetic gap into "the demo utility is empty", which
    is a far worse failure than a premises reading "—".

    **THE FALLBACK DOWN THE CHAIN IS THE SAME ARGUMENT ONE LEVEL IN** (CR-039
    wave E task 22). Every tenant provisioned before fixture V2.48.0.1 holds
    the four districts and none of the three sub-areas, and a lookup that
    demanded the sub-area would have UNTAGGED those premises — turning a
    hierarchy improvement into DEF-256 all over again on every existing
    tenant. Finest-available, never all-or-nothing.
    """
    for street, chain in AREA_BY_STREET.items():
        if not address_line.endswith(street):
            continue
        for code in chain:
            if code.upper() in available:
                return code
        return None
    return None


def _existing_sample_row(rows: list[dict[str, Any]], name: str, legacy_code: str) -> str | None:
    """This seam's own cycle/route id, however it was named when it was seeded.

    Two ways to be already-seeded, and both must be recognised or a replay
    doubles the plant (BR-TEN-063):
      · the NAME this seam writes now — the stable key, because the CODE is
        allocated from the number series and differs on every call;
      · the historical `SCW-*` CODE, for a tenant seeded before W5-T1.
    """
    for row in rows:
        if (row.get("name") or "") == name or row.get("code") == legacy_code:
            return str(row["id"])
    return None


def sample_cycle_row(cycles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """This seam's cycle, out of a list somebody else already read.

    PUBLIC because `apps/billing/sample_data.py` needs the same answer and used
    to get it by comparing against `SAMPLE_CYCLE_CODE`. That constant is gone —
    the code is series-allocated now (W5-T1) — so the recogniser lives in ONE
    place and both callers ask it, rather than two files agreeing about a
    string until one of them stops.
    """
    for row in cycles:
        if (row.get("name") or "") == SAMPLE_CYCLE_NAME or row.get("code") == (
            LEGACY_SAMPLE_CYCLE_CODE
        ):
            return row
    return None


def _walk_route_id(walk_offset: int) -> str | None:
    """The id of the route this walk offset belongs to, or None where the
    tenant does not hold it (a tenant seeded before 2026-09-07 and never
    re-plumbed holds route 1 only).

    Looked up BY NAME through the published selector, never cached across a
    call — `_ensure_cycle_and_route` may have created it moments ago.
    """
    wanted = fixture.READ_ROUTES[walk_offset]["name"]
    for row in selectors.routes_list():
        if (row.get("name") or "") == wanted:
            return str(row["id"])
    return None


def sample_walk_days(close_day: int) -> tuple[int, int]:
    """`(start_day, days_to_complete)` of the sample cycle whose walk CLOSES on
    `close_day` — the open period's read day, clamped to today by
    `core.sample_fixture.build_calendar`.

    `DEF-MET-8693`: this was `close_day − (WALK_DAYS_TO_COMPLETE − 1)`, so a
    utility signing up on the 1st to the 4th of a month got a start day of
    0, −1, −2 or −3, `create_cycle` refused it (`metering.cycle.
    day_of_month_range`), and premises, meters, accounts, reads and payments
    all failed behind it.

    **CLAMPED TO THE 1st, NEVER WRAPPED INTO THE PREVIOUS MONTH — and the
    length shrinks with it so the window still closes on `close_day`.** Worked:
    signed up 1 October → `(1, 1)`, window 1–1 October, bill day 2; on the
    3rd → `(1, 3)`; from the 5th on → `(close − 4, 5)`, the anchor's `(10, 5)`.
    Why not wrap to 27 September: a cycle is a DAY-OF-MONTH definition and
    BR-MET-077 compares the bill day with the window's close as days of one
    month — a window starting the 27th closes (clamped) on the 31st, so the
    bill day of the 2nd is refused as `bill_day_before_read`. And the walk
    itself does not wrap either: `fixture.route_read_on` keeps every round of
    the OPEN month on or after its 1st (same defect), so on the 1st to the 4th
    `(1, close)` is exactly the days the crew is out. (Weekends are not
    counted here and never were — the walk steps back WORKING days — which is
    unchanged by this fix and moves no money: proration reads the run's period.)
    """
    walk = fixture.WALK_DAYS_TO_COMPLETE
    start_day = max(1, close_day - (walk - 1))
    return start_day, close_day - start_day + 1


def _ensure_cycle_and_route(actor: Any, premises_ids: list[tuple[str, str]]) -> None:
    """One monthly cycle and FIVE walk routes, so the reads screens and the bill
    run have a scope to work in (BR-MET-010/033). Idempotent — see
    `_existing_sample_row` for what "already seeded" means now.

    ── PO 2026-09-07 · FIVE ROUTES, BECAUSE ONE CANNOT VARY ─────────────────
    ⚠ **THIS CREATED EXACTLY ONE ROUTE UNTIL 2026-09-07 AND IT IS WHY EVERY
    METER ON THE TENANT WAS READ ON THE SAME DAY.** Measured before the change:
    427 readings over 8 distinct dates on a seeded `brazosbend`, with
    `days_since_prior` taking only the values **14, 30 and 31**. The ruling —
    *"you will have to do some variation for datys"* — cannot be met by a
    fixture with one route, because a walk date is a fact about a ROUND.

    So the estate's five streets are five rounds (`fixture.READ_ROUTES`), each
    walked on its own day through the last working week of the cycle. The
    premises of a street go on that street's route and on no other.

    ⚠ **ROUTE 1 KEEPS THE NAME THIS FIXTURE HAS ALWAYS USED**, so a tenant
    seeded before today is recognised as already holding it and gains the other
    four rather than a sixth beside it. `BR-MET-074` makes a membership
    conflict a MOVE and not a refusal, so on a replay the four new routes take
    their own streets' units off route 1 — which is the right answer and is why
    this is safe to run over an existing estate.

    ── W5-T1 · THE CYCLE IS A DEFINITION, NOT ONE MONTH'S DATES (D2) ─────────
    This used to create the cycle with `window_start` / `window_end` /
    `bill_date` — three of the six columns CR-029 D2 superseded and W5-T2
    drops — and with **no frequency, no start day and no days to complete.**
    The consequences were all visible on the running product and none of them
    failed a test:

      · `next_cycle_date` was null, so the dashboard countdown SKIPPED the one
        cycle that held every account on the tenant;
      · `proposed_windows` was empty, so SET-07D's Schedule card had nothing to
        offer and the bill-run wizard pre-filled nothing;
      · `read_window_source` read `"stored"`, the last row in the product still
        reading a window out of a column instead of deriving it.

    **The three ruled fields, and they now say what the fixture actually does.**
    ⚠ **THEY READ `start_day 14, days_to_complete 1` — one crew, one day, one
    walk — AND THAT SENTENCE STOPPED BEING TRUE THE MOMENT THE WALK WAS SPREAD
    OVER FIVE ROUNDS.** The August walk, which is the cycle this fixture's own
    "today" sits in, runs **10–14 August**: so `start_day` is **10** and
    `days_to_complete` is **5**, and the derived read window is exactly the days
    the crew is out. Leaving the old pair would have been a cycle definition
    that disagreed with every batch posted against it — hard-won law 1, a
    statement claiming a guarantee the code does not keep.

    ⚠ **`bill_day` IS 15, NOT 2, AND THE REASON IS A RULE THIS FIXTURE CANNOT
    BEND.** `2026-09-02` is *the 2nd of the month AFTER the 14 Aug walk* — a
    perfectly real arrangement that a DAY-OF-MONTH column cannot say, and
    BR-MET-077's own check refuses it by name (`bill_day_before_read`: a bill
    day earlier in the month than the read close). So the sample plant takes the
    honest day-of-month reading of the same intent — *the walk closes on the
    14th and the bill goes out the day after* — and nothing downstream moves,
    because billing's sample runs carry their own `bill_date` from the fixture's
    periods (`apps/billing/sample_data.py`) and D9 makes the cycle's value a
    default the run overrides. It is unchanged by the pair above: the walk still
    CLOSES on the 14th, it simply starts four days earlier.
    """
    anchor = fixture.PERIODS[-1]["read_on"]
    start_day, days_to_complete = sample_walk_days(anchor.day)
    existing_cycle = sample_cycle_row(selectors.cycles_list())
    cycle_id = None if existing_cycle is None else str(existing_cycle["id"])
    if cycle_id is None:
        cycle_id = services.create_cycle(
            actor,
            {
                # No `code` — the CY- series allocates it (D5, BR-MET-077).
                "name": SAMPLE_CYCLE_NAME,
                "frequency": "Monthly",
                # The walk STARTS `WALK_DAYS_TO_COMPLETE - 1` days before it
                # closes and closes on the anchor, so the derived window is the
                # days the crew is actually out.
                # `DEF-MET-8693` — never below the 1st; see `sample_walk_days`.
                "start_day": start_day,
                "days_to_complete": days_to_complete,
                "first_run_date": anchor.isoformat(),
                "bill_day": anchor.day + 1,
                "due_days": 20,
            },
        )["id"]
    existing_names = {(row.get("name") or "") for row in selectors.routes_list()}
    for route in fixture.READ_ROUTES:
        # Route 1 is also recognised by the legacy code a very early tenant
        # carries, which is what `_existing_sample_row` is for.
        if route["walk_offset"] == 0 and _existing_sample_row(
            selectors.routes_list(), route["name"], LEGACY_SAMPLE_ROUTE_CODE
        ):
            continue
        if route["name"] in existing_names:
            continue
        on_this_street = [
            premises_id for street, premises_id in premises_ids if street == route["street"]
        ]
        if not on_this_street:
            # A tenant whose estate does not reach this street gets no empty
            # round. Named rather than silent: an empty route reads on the
            # Routes screen exactly like a round nobody has walked yet.
            logger.info(
                "sample data: no premises on %s, so its walk route was not created",
                route["street"],
            )
            continue
        services.create_route(
            actor,
            {
                # No `code` — the RT- series allocates it (D5, BR-MET-073).
                "name": route["name"],
                "route_type": "walk",
                # D10 — a route serves a service SET. An all-services route is
                # not "convenient": DEF-227 records that it TAKES a service
                # point which already belongs to a route drawn for its own
                # service and stamps its own cycle over the top, so the unit
                # drops out of the bill run. The set is the fixture's own
                # services ∩ the tenant's enabled ones, which is the same list
                # the units were given.
                "service_codes": _fixture_services(),
                "cycle_id": cycle_id,
                "premises_ids": on_this_street,
            },
        )


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W1 · TASK 1.23 — THE ACCOUNTS-IMPORT DEMO SEED (B18 §5.9.6)
# ══════════════════════════════════════════════════════════════════════════
#
# WHAT THE PROTOTYPE DRAWS AND THIS SEEDS. r10's Accounts → Imports tab
# (`[shot: ACC-02]`, B18 §5.9.4/§5.9.6) shows a run history of THREE runs on
# the `accounts` target. They are seeded here because `import_runs` is
# METERING's table — B2/B1: customers may not write it, and the ONE ETL runner
# (BR-MET-096) lives in this module.
#
# ⚠ **THESE THREE ARE HISTORY ROWS, WRITTEN DIRECTLY, AND THAT IS A DELIBERATE
# EXCEPTION TO THE FIXTURE'S OWN "seed through the service a clerk's click
# uses" RULE.** Every other block in this file goes through `create_premises` /
# the S28 read pipeline, and the reason it can is that a clerk's click and the
# fixture want the SAME rows. Here they do not: B18 §5.9.6 pins RUN-2814 at
# **1,251 rows in / 1,247 loaded / 4 rejected** because the Accounts KPI strip
# reports the same 1,247 (§5.1.1), and a demo tenant that holds 48 units
# (`core/sample_fixture.UNIT_COUNT`) cannot produce 1,247 loaded accounts by
# actually running the runner. The choice is between a run row that states the
# reference figure and a run row that states 48 — and a fixture whose Imports
# tab contradicts its own KPI strip teaches the wrong number. So the run rows
# are DECLARED, the one row whose per-account figures are ❄️ FROZEN (GT-16's
# A-12103) is genuinely LOADED through the product's own seam by
# `apps/customers/sample_data.py`, and the gap between them is written down
# here rather than discovered later.
#
# ⚠ **`file_hash` IS LEFT NULL ON ALL THREE, ON PURPOSE.** `ImportRun`'s own
# docstring makes it *"COMPUTED SERVER-SIDE, FROM THE BYTES (TC-2)"*. The
# fixture holds no file, so any value here would be a hash of nothing — a
# figure the receipt prints as if it attested to something. An absent hash is
# the honest answer and the unique index (`uq_import_runs_no_dupe_load`) is
# scoped to non-null hashes, so nothing depends on one.

#: B18 §5.9.6 — the three `[shot]` runs, verbatim from the table, plus the two
#: ❄️ GT-16 batch figures RUN-2814 is the demo's carrier for (see below).
#: Dates are 2026, the fixture's own year (`core/sample_fixture.PERIODS`).
ACCOUNT_IMPORT_RUNS: tuple[dict[str, Any], ...] = (
    {
        "run_no": "RUN-2801",
        "file_name": "contact_updates.csv",
        "started_at": datetime(2026, 7, 20, 10, 44, tzinfo=dt_timezone.utc),
        "rows_in": 88,
        "loaded": 88,
        "rejected": 0,
        "session_ref": "sess_2801",
    },
    {
        "run_no": "RUN-2814",
        "file_name": "customer_accounts_migration.csv",
        "started_at": datetime(2026, 7, 28, 12, 5, tzinfo=dt_timezone.utc),
        "rows_in": 1251,
        "loaded": 1247,
        "rejected": 4,
        "session_ref": "sess_2814",
        # ── ❄️ GT-16, B5 line 56, finance-signed 2026-08-08 ──────────────────
        # *"batch check: Σ of all opening JEs = Σ of all imported buckets
        # (fixture batch: 1,213 accounts → clearing credit = total migrated AR
        # $184,320.55)"*. This is the migration run, so it is the run that
        # carries the tie-out — and B18 §5.9.3a records that this same figure
        # is the Accounts tab's `OUTSTANDING $184,320` tile.
        #
        # ⚠ **THE 1,213 ENTRIES ARE NOT POSTED AND MUST NOT BE INVENTED.** The
        # Product Owner ruled on 2026-08-11 (decision log): *"The
        # opening-balance import verifies a single account only; the
        # 1,213-account batch total stays illustrative."*
        # `10-scripts/03-golden-verify.py` says the same in its own words —
        # *"the batch tie-out ($184,320.55 across 1,213 accounts) states no
        # per-account fixture, so that sum cannot be recomputed"*. Composing
        # 1,212 per-account figures to make the total come out would be a
        # fixture proving the fixture, and posting them against account ids no
        # `accounts` row carries would put phantom AR into
        # `ledger.reporting.ar_positions` — hard-won law 1, a fabricated KPI.
        # So the figure is RECORDED here as what the migration declared, and
        # the PROPERTY it rests on (Σ AR debits = Σ clearing credits) is proved
        # by the entry that IS posted, on GT-16's own account.
        "opening_accounts": 1213,
        "opening_ar": "184320.55",
    },
    {
        "run_no": "RUN-2822",
        "file_name": "autopay_enrolments.csv",
        "started_at": datetime(2026, 8, 1, 14, 18, tzinfo=dt_timezone.utc),
        "rows_in": 312,
        "loaded": 310,
        "rejected": 2,
        "session_ref": "sess_2822",
        # §5.9.4's KPI reads `REJECTED 6 · 2 still open`: 4 + 2 = 6, and the
        # two still open are this run's. They are seeded as real
        # `import_run_rows` so the tab's `🔧 fix` row action has a subject —
        # a row action with nothing to act on is dead UI (hard-won law 2).
        "open_rejects": (
            {
                "row_no": 118,
                "source_key": "A-13207",
                "problem": "This row names no unit that is on file.",
                "fix_hint": (
                    "Import premises and units first (BR-CUS-047), then re-run. "
                    "An account import never creates a unit."
                ),
            },
            {
                "row_no": 264,
                "source_key": "A-13390",
                "problem": "That unit already has a live account.",
                "fix_hint": (
                    "One account occupies a unit at a time (BR-CUS-017). Close the "
                    "existing account first, or correct the unit on this row."
                ),
            },
        ),
    },
)

#: The migration run — the one B18 §5.9.6 says *"loads 1,247, the exact figure
#: the Accounts KPI strip reports"*, and the batch GT-16's opening entry is
#: keyed to (`opening_balance|<account>|cutover:<batch>`).
MIGRATION_RUN_NO = "RUN-2814"

#: ❄️ B5 GT-16 line 55: *"cutover 2026-08-31"*. The BOOK date of the opening
#: journal entry — never a clock read (BR-TEN-043, BR-CUS-049).
GT16_CUTOVER_ON = date(2026, 8, 31)

#: The seat the migrated account occupies. All 48 fixture units already carry
#: an occupying account (`core/sample_fixture.account_plan()` is one per unit,
#: BR-CUS-017 allows exactly one), so the cutover account needs a unit of its
#: own — it lands on one of the three fixture premises the plan deliberately
#: leaves EMPTY, so no premises is invented and DEF-256's district assignment
#: is inherited rather than re-derived.
#:
#: ⚠ **IT IS SEEDED WITH NO SERVICES, AND THAT IS THE POINT.** A service point
#: here would put a 49th unit into the July batch with no read behind it — a
#: phantom missing-read in the READY-TO-RUN month, which is the acceptance
#: test the fixture spec exists to protect (the same argument
#: `apps/assets/sample_data.py` makes for leaving the net meter in inventory).
#: It is also the truthful shape: BR-CUS-047's migration order ends *"→
#: Accounts → opening reads"*, and this account's opening read has not been
#: taken yet.
#:
#: ⚠ **AND THAT LAST SENTENCE IS NOW THE PROBLEM, NOT THE JUSTIFICATION
#: (2026-08-27, DEF-982).** The PO ruled that day, closing OQ-530: *"so when we
#: run first bill; we have to take opening balance into account. you will
#: generate first bill and against previous balance you will mention the
#: opening balance."* That rule is BUILT (BR-BIL-160,
#: `apps/billing/customers_seam.py`) and **no seeded tenant can demonstrate
#: it**, because this seat — the demo's only migrated account, ❄️ GT-16's
#: `A-12103` at **267.30** — joins no route and appears in no bill run. Every
#: bill the demo produces shows an opening balance of 0.00.
#:
#: **DO NOT "just add a service point here."** The reasoning above still holds
#: and the wall is measured in DEF-982: `core/sample_fixture.meter_plan()`
#: (49), `_rows_for()` (48/48/45) and `_opening_rows()` (48) are ALL derived
#: from `units_flat()` (48), so a seat outside that list can get no meter and
#: no read through the fixture's own path — and this module may not create the
#: asset itself (B1; see this file's own docstring, *"the meter belongs to
#: apps/assets … Merging the two would force metering to create assets, which
#: B1 forbids"*). Three routes were measured and every one either moves a count
#: a test asserts or is a product judgment; the OQ-530 lane STOPPED rather than
#: adjusting a number. **The decision is the PO's and it is in DEF-982's own
#: prevention column:** is the demo's **48** a number to protect, or should it
#: grow by one so the product can show a migrated customer's first bill?
CUTOVER_UNIT_NO = "SCW-U-101"
CUTOVER_UNIT_LABEL = "Unit 101"
CUTOVER_UNIT_TYPE = "residential"


def _identity_user_id(actor: Any) -> Any:
    """`import_runs.run_by` is an FK into `users` — a synthetic uuid would
    break the reviewed cross-module FK set (B2 §2), so an actor that is not a
    real user row yields NULL and the run reads *"—"* rather than refusing."""
    from apps.identity import models as identity_models

    candidate = getattr(actor, "id", None) or getattr(actor, "pk", None)
    if candidate is None:
        return None
    return identity_models.User.objects.filter(pk=candidate).values_list("id", flat=True).first()


def _counts_for(entry: dict[str, Any]) -> dict[str, Any]:
    """`ImportRun.counts`, reconciling — the model's own TC-3 discipline:
    *"in − duplicates_dropped − skipped = forward"*, and loaded + rejected =
    forward. A denormalised count that cannot be checked against its own
    addends is a number nobody can defend."""
    rows_in = entry["rows_in"]
    counts: dict[str, Any] = {
        "in": rows_in,
        "duplicates_dropped": 0,
        "skipped": 0,
        "forward": rows_in,
        "checked": rows_in,
        "clean": entry["loaded"],
        "errors": entry["rejected"],
        "warnings": 0,
        "loaded": entry["loaded"],
        "rejected": entry["rejected"],
        "flagged": 0,
        "created": entry["loaded"],
        "updated": 0,
        "skipped_existing": 0,
    }
    if "opening_accounts" in entry:
        # The same two keys `_load_accounts_rows` writes on a real accounts
        # run, so the Imports tab and the receipt read ONE shape (hard-won law
        # 5: one source, derived views).
        counts["with_opening_balance"] = entry["opening_accounts"]
        counts["opening_ar"] = entry["opening_ar"]
    return counts


def _seed_account_import_history(actor: Any) -> int:
    """B18 §5.9.6 — the three `[shot]` runs on the `accounts` target.

    Idempotent (BR-TEN-063): a run already carrying the fixture's `run_no` is
    skipped, so a replay writes nothing. Tagged `is_sample` on the OWNING row
    (BR-TEN-057) — B15 §15 requires exactly this, so BR-TEN-061 can remove
    them again.
    """
    from apps.metering import import_runs

    tenant_id = _tenant_id()
    wanted = [entry["run_no"] for entry in ACCOUNT_IMPORT_RUNS]
    existing = set(
        models.ImportRun.objects.filter(tenant_id=tenant_id, run_no__in=wanted).values_list(
            "run_no", flat=True
        )
    )
    run_by = _identity_user_id(actor)
    written = 0
    for entry in ACCOUNT_IMPORT_RUNS:
        if entry["run_no"] in existing:
            continue
        run = models.ImportRun.objects.create(
            tenant_id=tenant_id,
            run_no=entry["run_no"],
            target=import_runs.TARGET_ACCOUNTS,
            source_kind="file",
            file_name=entry["file_name"],
            # file_hash stays NULL — see the ⚠ above.
            encoding_delimiter="UTF-8 · comma (detected)",
            mapping_spec=(
                {"options": {"cutover_on": GT16_CUTOVER_ON.isoformat()}}
                if entry["run_no"] == MIGRATION_RUN_NO
                else None
            ),
            counts=_counts_for(entry),
            status="loaded",
            write_mode="insert",
            run_by_id=run_by,
            session_ref=entry["session_ref"],
            started_at=entry["started_at"],
            finished_at=entry["started_at"],
            is_sample=True,
        )
        written += 1
        for reject in entry.get("open_rejects", ()):
            models.ImportRunRow.objects.create(
                tenant_id=tenant_id,
                run=run,
                row_no=reject["row_no"],
                source_key=reject["source_key"],
                outcome="rejected",
                problem=reject["problem"],
                fix_hint=reject["fix_hint"],
                is_sample=True,
            )
            written += 1
    return written


def _empty_fixture_premises_id() -> str | None:
    """The first fixture premises the plan leaves without a unit.

    DERIVED from `premises_plan()` rather than named here, so a change to the
    fixture's mix cannot silently point the cutover seat at somebody's house.
    """
    empty = [entry["address_line"] for entry in fixture.premises_plan() if not entry["units"]]
    if not empty:
        return None
    by_address = {row.address_line: row for row in selectors.premises_list()}
    for address in empty:
        row = by_address.get(address)
        if row is not None:
            return str(row.id)
    return None


def _seed_cutover_seat(actor: Any) -> int:
    """ONE unit for the migrated GT-16 account — see `CUTOVER_UNIT_NO` above.

    Through `create_unit`, the S16 wizard's own call, with the residential plan
    the account will derive from: `create_account` REFUSES to activate an
    account on a planless unit (BR-CUS-014/BR-MET-040), so the plan is not
    decoration. Idempotent on the unit number (BR-TEN-063).
    """
    tenant_id = _tenant_id()
    if models.Unit.objects.filter(tenant_id=tenant_id, unit_no=CUTOVER_UNIT_NO).exists():
        return 0
    premises_id = _empty_fixture_premises_id()
    if premises_id is None:
        logger.info(
            "sample data (CR-030 W1): no empty fixture premises is seeded, so the "
            "migrated account %s has no seat and is not planted",
            CUTOVER_UNIT_NO,
        )
        return 0
    plan_id = _plan_id_for(0)  # residential — `is_commercial(0)` is False
    payload: dict[str, Any] = {
        "premises_id": premises_id,
        "label": CUTOVER_UNIT_LABEL,
        "unit_no": CUTOVER_UNIT_NO,
        "unit_type": CUTOVER_UNIT_TYPE,
        # No `services` — see the ⚠ on CUTOVER_UNIT_NO.
    }
    if plan_id:
        payload["plan"] = {
            "plan_id": plan_id,
            "effective_from": fixture.PERIODS[0]["start"].isoformat(),
        }
    services.create_unit(actor, payload)
    _tag(models.Unit.objects.filter(tenant_id=tenant_id, unit_no=CUTOVER_UNIT_NO, is_sample=False))
    return 1


def sample_account_cutover_seat() -> dict[str, Any] | None:
    """PUBLISHED READ — what `apps/customers/sample_data.py` needs to plant the
    ❄️ GT-16 account, and the only thing it needs from this module.

    Customers never reads `import_runs` (metering's table, B1) and never
    imports this module directly; it resolves this function through its own
    `seams.resolve("metering", …)` edge, exactly as `_unit_no_to_id()` resolves
    `units_list`. Returning the run id, the unit number and the cutover date
    together keeps ONE copy of each literal: the batch key
    (`opening_balance|<account>|cutover:<batch>`) and the run the buckets cite
    are the same RUN-2814 seeded above, not a second spelling of it.

    None = the history has not been seeded (metering's block has not run, or
    the tenant took no sample data), and the caller SKIPS rather than inventing
    a batch id.
    """
    run = (
        models.ImportRun.objects.filter(tenant_id=_tenant_id(), run_no=MIGRATION_RUN_NO)
        .values("id")
        .first()
    )
    if run is None:
        return None
    return {
        "run_id": run["id"],
        "run_no": MIGRATION_RUN_NO,
        "unit_no": CUTOVER_UNIT_NO,
        "cutover_on": GT16_CUTOVER_ON,
    }


def _reconcile_estate_services(
    actor: Any, row: Any, entry: dict, services_for_units: tuple[str, ...]
) -> int:
    """Give an ALREADY-SEEDED sample address the services it is missing — `DEF-1250`.

    ⚠ **THE SAME GRAIN MISMATCH AS `rating.sample_data._reconcile_plan_services`,
    ONE MODULE OVER, AND IT IS THE HALF THAT DECIDES WHETHER A BILL HAPPENS AT
    ALL.** This block is idempotent per PREMISES — `if row is None:` creates and
    the `else` branch appended the id and did nothing else — so an address that
    exists is never revisited. A service switched on after the estate was
    planted therefore reaches no address's OFFER and no unit's SERVICE POINT,
    and under `BR-BIL-300` the service points are what decide which services a
    bill charges. So the utility switches trash on, reloads the sample data, and
    **nothing at all happens on the estate**: no offer, no point, no cart, no
    line.

    **MEASURED before this existed**, provisioning water + sewer, loading, then
    switching trash on at Settings and loading again: `service points: {water:
    75, sewer: 49}` — identical to the first run, on a tenant that now sells
    trash.

    ⚠ **THE OFFER IS THE LOCK, NOT THE POINT.** `assets.sample_data` plants the
    four `container_cart` assets through `create_asset`, which calls
    `metering.ensure_service_point` — and that refuses with
    `metering.service_not_at_premises` unless the ADDRESS offers the service
    (`BR-MET-119`, `_refuse_service_not_at_premises`). The asset block is
    idempotent per asset NUMBER, so it would happily plant the carts on a
    replay; it could not, because the address it plants them at still offered
    water and sewer. Extending the offer is what unlocks the whole chain.

    THREE GUARDS
    ------------
    1. **SAMPLE ROWS ONLY** (`is_sample`), for the reason BR-TEN-068 gives one
       module over: an address the operator has since made their own is not a
       fixture's to widen.
    2. **ADDITIVE.** The offer is a UNION with what is already stored, never a
       replacement — an operator who narrowed an address deliberately keeps
       every service they removed, and `NARROW_OFFER_PREMISE_NO` keeps the one
       this fixture holds back so BR-MET-119's refusal stays demonstrable on a
       demo tenant.
    3. **THROUGH THE PRODUCT'S OWN WRITES** — `update_premises` and
       `ensure_service_point`, the same two calls S16 and the assets lane make.
       `ensure_service_point` is a get-or-create, so it is the idempotency
       rather than a check in front of it.

    Returns the number of rows written (offers widened + service points added).
    """
    if not getattr(row, "is_sample", False):
        return 0
    written = 0
    wanted_offer = _offer_for(entry, services_for_units)
    stored_offer = list(row.services_available or [])
    # A UNION, in the offer's own order first so a stored order is not churned.
    merged = list(
        dict.fromkeys([*stored_offer, *[c for c in wanted_offer if c not in stored_offer]])
    )
    if merged != stored_offer:
        services.update_premises(actor, str(row.id), {"services_available": merged})
        written += 1
    for unit in models.Unit.objects.filter(
        tenant_id=_tenant_id(), premises=row, is_sample=True, deleted_at__isnull=True
    ):
        held = set(
            models.ServicePoint.objects.filter(tenant_id=_tenant_id(), unit=unit).values_list(
                "service__code", flat=True
            )
        )
        for code in services_for_units:
            if code in held or code not in merged:
                continue
            try:
                # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
                # (this block runs inside tenancy's per-module `atomic`), so without it the
                # work already done is lost at COMMIT. NOT tidiness — do not remove.
                with transaction.atomic():
                    services.ensure_service_point(str(unit.id), code)
            except Exception as exc:  # noqa: BLE001 — named, never a silent skip
                # BR-TEN-060: one refusal must not stop the other 47 units, and
                # a skip nobody can see is the defect this whole row is about.
                logger.info(
                    "sample data: unit %s took no %s service point (%s) — DEF-1250 "
                    "reconciliation",
                    unit.unit_no,
                    code,
                    type(exc).__name__,
                )
                continue
            written += 1
    return written


def seed_sample_records(actor: Any) -> int:
    """THE SEAM `apps/tenancy/seams.py` has documented since 2026-08-15.

    44 premises and the 48 units on them, each unit carrying its service points
    and the rate plan its account will derive from. Idempotent (BR-TEN-063):
    every premises is looked up by address through this module's own selector
    first, so a replay writes nothing.
    """
    plan = estate()
    services_for_units = list(plan.services)
    if not services_for_units:
        # ⛔ **THIS USED TO `return 0` AND THAT ZERO IS DEF-795.** Nothing the
        # fixture could express was enabled, the block recorded `seeded · 0
        # rows`, and a tenant whose estate was refused looked exactly like one
        # that never asked for sample data. `BlockCannotRun`'s own contract
        # already said what to do here — *"COULD NOT RUN — raise this, naming
        # the reason … Never a 0"* — and this block was answering 0.
        #
        # The refusal itself is UNCHANGED and must stay: a premises that claims
        # to receive a service the utility does not sell is worse than no
        # premises (BR-MET-003). What changed is that it now says which service
        # and why, in a sentence the Sample data panel renders.
        raise fixture.BlockCannotRun(
            "no premises were seeded: this tenant sells nothing the sample estate can "
            "be built in. "
            + (
                plan.refusal_sentence
                or "the tenant has no enabled service at all — turn one on at "
                "Settings -> Services & UoM and load the sample data again"
            )
        )
    if plan.refused:
        # BR-TEN-060 — named, never a silent gap. The estate IS being seeded;
        # these are the services the utility sells that it will not appear in,
        # and a utility that cannot see gas in its demo will ask why.
        logger.info(
            # CR-062 C1 — the estate is metered in one service OR SEVERAL, so
            # the line names each with its own unit rather than one pair.
            "sample data: the estate is metered in %s; not seeded: %s",
            ", ".join(f"{row.code} ({row.uom})" for row in plan.metered) or "nothing",
            plan.refusal_sentence,
        )

    by_address = {row.address_line: row for row in selectors.premises_list()}
    written = 0
    # ⚠ **THE STREET TRAVELS WITH THE ID (PO 2026-09-07).** The estate is walked
    # by five routes now, one per street, so the route builder has to know which
    # premises belongs to which round. Pairing them here rather than zipping two
    # lists by position later is the difference between a mismatch that REFUSES
    # and one that silently puts nine premises on the wrong crew's sheet.
    premises_ids: list[tuple[str, str]] = []
    # DEF-256 — resolved ONCE for the whole plant rather than per premises: 44
    # identical queries is 44 identical queries.
    areas_available = _seeded_area_codes()
    # CR-039 wave E task 23 (BR-MET-139): the tenant's OWN declared state, read
    # once for the block. `None` when they have named none, and that stays
    # None — see `seams.tenant_state` for why a plausible guess would be worse
    # than the blank it replaces.
    state = seams.tenant_state()

    for entry in fixture.premises_plan():
        address = entry["address_line"]
        row = by_address.get(address)
        unit_payloads = [
            {
                "label": unit["label"],
                "unit_no": unit["unit_no"],
                "unit_type": unit["unit_type"],
                "services": list(services_for_units),
                "plan": (
                    {
                        "plan_id": _plan_id_for(unit["unit_index"]),
                        "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                    }
                    if _plan_id_for(unit["unit_index"])
                    else None
                ),
            }
            for unit in entry["units"]
        ]
        for payload in unit_payloads:
            if payload["plan"] is None:
                payload.pop("plan")
        if row is None:
            payload = {
                "address_line": address,
                "city": fixture.CITY,
                # CR-039 wave E task 23 · BR-MET-139. This was a hardcoded
                # `None` while `tenants.state` held the answer — the premises
                # importer OFFERS this column (aliases `state` / `province`)
                # and the seeded demo exercised it on zero of 44 rows, so a
                # seeded tenant read THINNER than an imported one on a field
                # every real customer's file carries. Resolved ONCE for the
                # block above, never per row (DEF-324). The tenant's OWN
                # declaration or nothing: this fixture invents no state.
                "state": state,
                "postal_code": fixture.POSTAL,
                "premises_type": entry["premises_type"],
                "owner_manager": entry["owner_manager"],
                # ⚠ **WHAT THE ADDRESS OFFERS, NOT WHAT ITS UNITS HAPPEN TO USE
                # (DEF-780).** This read `list(services_for_units)` — the
                # services the seeded units are given — which is the wrong
                # LEVEL under BR-MET-119: a premises DECLARES what is available
                # at the address, a unit inherits that, and a meter attaches
                # against one of them. Seeding the offer FROM the usage made
                # every sample address offer exactly what it already had, so
                # the asset fixture's electric meters became illegal the day
                # the rule was enforced — 6 test failures, all one cause, and
                # the sentence they printed was DEF-772's own: *"P-00101 offers
                # water, sewer, trash, not electric."* The fixture was arguing
                # with the rule and the rule was right.
                #
                # ⚠ **AND `_offer_for` DELIBERATELY DOES NOT RETURN EVERYTHING.**
                # The obvious repair — offer every service the tenant sells —
                # would make the refusal UNDEMONSTRABLE on a demo tenant, which
                # is the one place a utility would meet it before meeting it on
                # their own data. So one address is held back, and the demo can
                # show both halves of BR-MET-119.
                "services_available": _offer_for(entry, services_for_units),
                # ── CR-039 wave C task 11 · BR-RAT-101's flag, SEEDED ────────
                # 42 inside, 2 outside, derived from r10's own 1,186-of-1,247
                # ratio (see `fixture.OUTSIDE_CITY_PREMISES_INDEXES`). It goes
                # through `create_premises` like every other field on this
                # payload, so the seed exercises the write path task 10 built
                # rather than reaching past it to the ORM — the rule this
                # module's own header states as *"through create_premises, the
                # S16 guided add"*.
                #
                # ⚠ **STATED ON ALL 44, NOT ONLY ON THE TWO.** The residential
                # plan now states an outside-city factor, and BR-RAT-102 refuses
                # an account whose premises flag is `None` rather than pricing
                # it inside-city by default. An unstated estate would be 42
                # exception rows on the demo's ready-to-run billing month.
                "inside_city_limits": entry["inside_city_limits"],
                "status": entry["status"],
                "units": unit_payloads,
            }
            # DEF-256. Sent only when the tenant HAS the district: omitting the
            # key entirely is the documented "leave it alone" signal
            # (`_resolve_area` returns presence, not truth), whereas sending an
            # unknown code would refuse the premises by name.
            area_code = _area_code_for(address, areas_available)
            if area_code is not None:
                payload["area_code"] = area_code
            payload["owner_id"] = _sample_owner_id(actor, payload.get("owner_manager"))
            result = services.create_premises(actor, payload)
            written += 1 + len(result.get("units", []))
            premises_ids.append((entry["street"], result["id"]))
        else:
            # ── DEF-1250 · THE ADDRESS EXISTS, SO ITS SERVICES ARE RECONCILED
            # RATHER THAN SKIPPED. This branch appended the id and did nothing
            # else, which is why switching a service on after the estate was
            # planted reached no offer and no service point — and therefore no
            # bill, because BR-BIL-300 derives a bill's services from the
            # unit's points. Additive, sample rows only; see the function.
            written += _reconcile_estate_services(actor, row, entry, tuple(services_for_units))
            premises_ids.append((entry["street"], str(row.id)))

    tenant_id = _tenant_id()
    addresses = [entry["address_line"] for entry in fixture.premises_plan()]
    premises_qs = models.Premises.objects.filter(tenant_id=tenant_id, address_line__in=addresses)
    _tag(premises_qs.filter(is_sample=False))
    unit_qs = models.Unit.objects.filter(tenant_id=tenant_id, premises__in=premises_qs)
    _tag(unit_qs.filter(is_sample=False))
    _tag(models.ServicePoint.objects.filter(tenant_id=tenant_id, unit__in=unit_qs, is_sample=False))

    written += _backfill_missing_unit_plans(actor)
    # CR-062 D6 (PO ruling 2026-09-02) — storm water's capacity is a fact on the
    # UNIT, so it is recorded here rather than planted as equipment. AFTER the
    # `_tag` pass above, deliberately: `set_characteristic` copies the unit's
    # `is_sample` onto the row, and a characteristic the remover cannot take
    # away is a demo row that outlives the demo (BR-TEN-057).
    written += _seed_cr062_storm_water_assessments(actor)
    # CR-080 (PO ruling 2026-09-07) — thermal/heat's connected tonnage is a
    # fact on the UNIT for storm water's own reason: nobody installs a ton.
    # Same placement and the same `_tag` argument as the line above.
    written += _seed_cr080_thermal_tonnage(actor)
    _ensure_cycle_and_route(actor, premises_ids)
    # CR-030 W1 T1.23 — the accounts-import history (B18 §5.9.6) and the seat
    # the ❄️ GT-16 migrated account occupies. BOTH after `_ensure_cycle_and_
    # route`, deliberately: the cutover unit carries no service point, so it
    # joins no route and adds no phantom missing-read to the ready-to-run July
    # batch, and running it before the route would only make that accidental.
    written += _seed_account_import_history(actor)
    written += _seed_cutover_seat(actor)
    # CR-030 W2 T2.10 — the demo estate's SEATS (PO 2026-08-24, "so add them").
    # LAST, and after the route for the reason the block's own header gives: the
    # estate must join no route and no bill run.
    written += _seed_cr030_estate(actor)
    # CR-030 W6 T6.3 / T6.15 — the work-order template STARTERS (BR-MET-109),
    # the eight New Connect builds and the seats they and W7 stand on. AFTER
    # the estate, because `CON-26-0110` stands on `3450 Oak Ridge Dr` and
    # `CON-26-0117` on `500 Main St` — both of them the estate's premises — and
    # after `_ensure_cycle_and_route` for the estate's own reason: a build joins
    # no route and no bill run.
    written += _seed_work_order_template_starters(actor)
    # CR-070 wave M — the template the nightly asset-age rule RAISES. Right
    # after the starters because it is published through the same three
    # `templates_svc` calls; its `sequence` is 0, which is what keeps it out
    # of New Connect step 6's proposal (`BR-WRK-016`, `DEF-WRK-3573`).
    written += _seed_work_order_exchange_template(actor)
    written += _seed_flow_visit_templates(actor)
    written += _seed_w6_w7_seats(actor)
    # DEF-709 — CON-26-0117's COMMON AREA, the 26th unit of BR-MET-116's own
    # manifest (`Units 26` = 25 apartments + 1 common area). AFTER the seats,
    # because it stands on the same `500 Main St` premises they do, and it is
    # the anchor BR-CUS-068's master account needs: without it the demo held no
    # `is_common_area` unit at all and no master account could be created.
    written += _seed_w6_common_area(actor)
    written += _seed_w6_connections(actor)
    # CR-028 AST-W5 T3: deterministic map coordinates on the plant — offline,
    # idempotent, never overwriting a set pin (see apply_premises_geo above).
    # ⚠ **MOVED HERE FROM BESIDE `_ensure_cycle_and_route` ON 2026-09-06
    # (`DEF-MET-4288`).** Up there it ran BEFORE `_seed_cr030_estate` and the
    # W6 seats, so the eight premises every seeded WORK ORDER stands on did not
    # exist yet and could not be filled — the work map had 19 of 19 jobs with
    # nowhere to go. A fill pass has to be after the last block that plants a
    # premises, and this is it.
    written += apply_premises_geo()
    # CR-089 wave A — the three GIS states, immediately AFTER the fill pass and
    # for the reason the fill pass moved down here: it reads which premises ended
    # up with a pin, so it cannot run before the last block that plants one.
    written += apply_premises_gis_states(actor)
    # CR-039 wave C task 14 — the TYPED owners (BR-MET-150/152). LAST, because
    # it matches whatever premises the blocks above actually planted: the
    # estate's own addresses, the CR-030 estate's and the W6/W7 seats'. Running
    # it earlier would type the owners of half a demo.
    written += _seed_premises_owners(actor)
    # ⚠ **LAST, AND AFTER THE MATCHING PASS ABOVE ON PURPOSE (DEF-650).** Since
    # BR-MET-401 every seeded address is created WITH a party, so the
    # un-categorised ones would otherwise arrive already matched and the demo
    # would lose BR-MET-151's review list entirely — the thing
    # `sample_fixture.owner_category_for` returns `None` in order to show.
    _restore_unmatched_premises(actor)
    return written


def _seed_cr062_storm_water_assessments(actor: Any) -> int:
    """**CR-062 D6 — the storm-water assessment, recorded on the UNIT.**

    **PO ruling 2026-09-02, verbatim:** *"In case of strom water - we have to
    take it from Unit - B ⭐ Take the size from the property, not from
    equipment. Storm water becomes the one capacity service whose quantity comes
    from the premises"* — option B of three, **corrected in the same sentence
    from the property to the UNIT**.

    **WHY THIS BLOCK LOOKS NOTHING LIKE `_seed_cr062_capacity_equipment`.** That
    one plants DEVICES, because solar, battery, broadband and trash each carry
    their size on a thing somebody installs. **Storm water has no such thing** —
    an ERU measures hard surface and nobody installs one — so D6 could not be
    built at all and was filed as `DEF-2388`. The ruled answer is a
    `service_characteristics` row on the unit (`BR-MET-108`'s shape), and
    metering's capacity reader takes the quantity from there.

    ⚠ **THE ASSESSMENT IS SPREAD EQUALLY ACROSS A PREMISES' UNITS** — the
    posture `MASTER_METER`'s `allocation_rule: "equal"` already takes for a
    block's water. **The apartment block's 6 ERU is 1 ERU on each of its six
    flats, not 6 on each**, which is the difference between billing that block
    `$27.00` a month and `$162.00`.

    **Worked, and asserted live:** a house **1 × $4.50 = `$4.50`**; the block
    **`$27.00`**; a commercial suite **4 × $4.50 = `$18.00`**; the estate
    **59 ERU = `$265.50`** a month.

    ⚠ **THE UTILITY COLLECTS `$270.00`, AND THE DIFFERENCE IS NOT THIS BLOCK'S.**
    `BR-RAT-101`/`BR-RAT-102` surcharge every base and variable line on a
    premises outside the city limits by **1.5**, and two of these houses are
    (`OUTSIDE_CITY_PREMISES_INDEXES`), so their storm-water lines read `$6.75`.
    The assessment this block writes is 59 ERU either way — a surcharge
    multiplies the price, never the measurement.

    ⚠ **THE ESTATE FIGURES ABOVE READ `54 ERU`, `$243.00` AND `$247.50` UNTIL
    2026-09-02 (`DEF-2368`).** `CR-062`'s addendum appended two seats — the
    municipal depot (`SW-SF`, 1 ERU, unit 48) and the industrial plant
    (`SW-COM-S`, 4 ERU, unit 49) — and this block picked both up on its next run
    because it reads the PLAN; the written totals beside it did not, and nothing
    said so for a day. `10-scripts/gates/g73_storm_water_estate.py` now makes
    that comparison with no database. **Nothing in what this block WRITES
    changed**, and no ❄️ frozen figure moved.

    ⚠ **THE NUMBER COMES FROM `BR-TEN-171` AND NEVER FROM THE FIXTURE.** The
    fixture states WHICH ratified property size each premises is; what that code
    is WORTH is read through `seams.total_installed_capacity` — the same
    function the BILL uses to turn a size class into a capacity, so the seed and
    the bill cannot disagree about what `SW-APT` means. A code the platform
    ladder does not hold is SKIPPED with the reason logged, never written blind:
    the unit then keeps `BR-MET-108`'s ruled `$0.00`, which is the safe
    direction.

    A tenant that does not sell storm water gets nothing and is told so
    (`BR-MET-003` — never a characteristic for a service it does not sell), and
    the gate is the unit's own SERVICE POINT rather than a list this function
    keeps. Idempotent (`BR-TEN-063`): `set_characteristic` is an
    `update_or_create` on `(tenant, unit, service, key)`.
    """
    key = w6.unit_capacity_key("storm_water")
    if key is None:  # pragma: no cover — defensive; the map above declares it
        return 0
    if "storm_water" not in seams.enabled_service_codes():
        logger.info(
            "sample data (CR-062 D6): no storm-water assessments — this tenant "
            "does not sell storm water"
        )
        return 0
    uom = seams.capacity_uom_for_service("storm_water")
    if uom != fixture.STORM_WATER_UOM:
        # Hard rule 3. If the ratified ladder ever stops summing in ERU, the
        # seeded $4.5000-per-ERU price is quoted in a unit the quantity is not
        # in, and writing anyway would be DEF-497 on a demo bill.
        logger.warning(
            "sample data (CR-062 D6): no storm-water assessments — the ratified "
            "size classes sum in %r and the seeded price is quoted per %r",
            uom,
            fixture.STORM_WATER_UOM,
        )
        return 0
    ratified = set(seams.ratified_size_class_codes("storm_water"))

    tenant_id = _tenant_id()
    unit_no_for = {row["unit_index"]: row["unit_no"] for row in fixture.units_flat()}
    unit_ids = {
        row.unit_no: row.id
        for row in models.Unit.objects.filter(
            tenant_id=tenant_id, unit_no__in=list(unit_no_for.values())
        ).only("id", "unit_no")
    }
    # The gate is the unit's OWN storm-water service point: a characteristic on
    # a unit that does not take the service would be this block deciding what
    # the tenant sells (BR-MET-108 — a missing row means *no characteristic
    # recorded*, never *does not take this service*).
    takes_storm_water = set(
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id,
            unit_id__in=list(unit_ids.values()),
            service__code="storm_water",
            deleted_at__isnull=True,
        ).values_list("unit_id", flat=True)
    )

    written = 0
    for row in fixture.storm_water_assessment_plan():
        code = row["size_class"]
        if code not in ratified:
            logger.warning(
                "sample data (CR-062 D6): %s not assessed — %r is not one of "
                "BR-TEN-171's ratified storm-water size classes. The units keep "
                "0 ERU and bill BR-MET-108's ruled $0.00",
                row["address_line"],
                code,
            )
            continue
        total = seams.total_installed_capacity("storm_water", [code])
        if total is None:
            logger.warning(
                "sample data (CR-062 D6): %s not assessed — %r states no "
                "capacity, so there is nothing to spread across its units",
                row["address_line"],
                code,
            )
            continue
        indexes = row["unit_indexes"]
        # THE EQUAL SPLIT. Four decimal places, CLAUDE.md hard rule 2 — the
        # money grid, because this number is multiplied by a price.
        share = (Decimal(str(total)) / Decimal(len(indexes))).quantize(Decimal("0.0001"))
        if share * Decimal(len(indexes)) != Decimal(str(total)):
            # Every seeded premises divides exactly (1/1, 2/2, 6/6, 4/1) and a
            # pure case asserts it, so this is a statement about a fixture that
            # has CHANGED rather than a rounding policy: an inexact split would
            # quietly lose or gain ERU across the premises, and the honest
            # answer is to say so rather than to absorb it.
            logger.warning(
                "sample data (CR-062 D6): %s assesses %s %s across %d units, "
                "which does not divide evenly; each unit is recorded at %s and "
                "the premises total no longer sums to its assessment",
                row["address_line"],
                total,
                uom,
                len(indexes),
                share,
            )
        for index in indexes:
            unit_id = unit_ids.get(unit_no_for[index])
            if unit_id is None or unit_id not in takes_storm_water:
                continue
            w6.set_characteristic(
                actor,
                unit_id,
                service_code="storm_water",
                key=key,
                value=str(share),
                # Hard rule 3 — the unit is DATA and never part of the key name.
                unit_of_measure=uom,
            )
            written += 1
    return written


def _seed_cr080_thermal_tonnage(actor: Any) -> int:
    """**CR-080 — THE CONNECTED TONNAGE ON EACH UNIT THAT TAKES THERMAL/HEAT.**
    🔒 rating math (it decides a billable quantity). HUMAN-REVIEW-PENDING.

    **PO ruling 2026-09-07, verbatim:** *"connected tonnage - it is capacity
    not metering; i will ahve 100 tonne or 200 tonne etc"*, confirmed the same
    day in their eleven-service walk: *"Thermal — basis disputed - this si
    correct"*.

    ⚠ **IT IS THE STORM-WATER BLOCK'S SHAPE AND NOT AN IMITATION OF IT.** A
    capacity service normally carries its size on a DEVICE somebody installs —
    solar has panels, battery has batteries, broadband has modems, fire has
    lines. **Thermal has no such thing.** The chiller is the utility's, in the
    plant, serving hundreds of buildings; what a customer has is a CONNECTION
    of an agreed size. Route it down the equipment path and
    `billable_asset_size_classes` returns an empty list on every unit,
    `total_installed_capacity` sums to `0`, and every thermal line prints
    `$0.00` on a document that foots perfectly — `DEF-2388`, one service over,
    and no gate in this repo can see it.

    ⚠ **AND UNLIKE STORM WATER, NOTHING IS SPREAD.** An ERU is assessed on a
    PREMISES and divided equally across its units, because hard surface belongs
    to the property. A chilled-water connection is made to a UNIT and is that
    unit's whole capacity: the apartment block's six flats each carry their own
    connection rather than a sixth of one. So this function takes a plan keyed
    by UNIT and writes it straight through, with no division and therefore no
    remainder to explain.

    **Worked, and asserted live on a seeded thermal tenant:** a house is
    **5 tons × $12.50 = `$62.50`** a month; each of the two commercial units is
    **100 tons = `$1,250.00`** (the PO's own figure); the municipal depot is
    **200 tons = `$2,500.00`** (their other one); the mill is **400 tons =
    `$5,000.00`**; and one unit — `fixture.THERMAL_UNIT_WITH_NONE` — has no
    connection recorded and bills `BR-MET-108`'s ruled **`$0.00`** beside them.
    The estate is **1,025 connected tons**, `$12,812.50` a month before
    `BR-RAT-101`'s outside-city 1.5x reaches two of the houses.

    ⚠ **THE NUMBER COMES FROM `BR-TEN-171` AND NEVER FROM THE FIXTURE**, the
    storm-water block's own rule: the fixture states WHICH ratified capacity a
    unit is connected at, and what that code is WORTH is read through
    `seams.total_installed_capacity` — the same call the BILL makes — so the
    seed and the bill cannot disagree about what `TH-T100` means. A code the
    platform ladder does not hold is SKIPPED with the reason logged, never
    written blind; the unit then keeps the ruled `$0.00`, which is the safe
    direction.

    A tenant that does not sell thermal gets nothing and is told so
    (`BR-MET-003`), and the gate is the unit's own thermal SERVICE POINT rather
    than a list this function keeps. Idempotent (`BR-TEN-063`):
    `set_characteristic` is an `update_or_create` on
    `(tenant, unit, service, key)`.
    """
    key = w6.unit_capacity_key("thermal_heat")
    if key is None:  # pragma: no cover — defensive; connections.py declares it
        return 0
    if "thermal_heat" not in seams.enabled_service_codes():
        logger.info(
            "sample data (CR-080): no thermal tonnage — this tenant does not "
            "sell thermal/heat"
        )
        return 0
    uom = seams.capacity_uom_for_service("thermal_heat")
    if uom != fixture.THERMAL_UOM:
        # Hard rule 3, and the storm-water block's own guard. If the ratified
        # ladder ever stops summing in `ton`, the seeded $12.5000-per-ton price
        # is quoted in a unit the quantity is not in, and writing anyway would
        # be DEF-497 on a demo bill.
        logger.warning(
            "sample data (CR-080): no thermal tonnage — the ratified size "
            "classes sum in %r and the seeded price is quoted per %r",
            uom,
            fixture.THERMAL_UOM,
        )
        return 0
    ratified = set(seams.ratified_size_class_codes("thermal_heat"))

    tenant_id = _tenant_id()
    unit_no_for = {row["unit_index"]: row["unit_no"] for row in fixture.units_flat()}
    unit_ids = {
        row.unit_no: row.id
        for row in models.Unit.objects.filter(
            tenant_id=tenant_id, unit_no__in=list(unit_no_for.values())
        ).only("id", "unit_no")
    }
    # The gate is the unit's OWN thermal service point: a characteristic on a
    # unit that does not take the service would be this block deciding what the
    # tenant sells (BR-MET-108 — a missing row means *no characteristic
    # recorded*, never *does not take this service*).
    takes_thermal = set(
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id,
            unit_id__in=list(unit_ids.values()),
            service__code="thermal_heat",
            deleted_at__isnull=True,
        ).values_list("unit_id", flat=True)
    )

    written = 0
    for row in fixture.thermal_tonnage_plan():
        code = row["size_class"]
        if code not in ratified:
            logger.warning(
                "sample data (CR-080): unit %s not connected — %r is not one "
                "of BR-TEN-171's ratified thermal size classes. The unit keeps "
                "0 ton and bills BR-MET-108's ruled $0.00",
                row["unit_index"],
                code,
            )
            continue
        tons = seams.total_installed_capacity("thermal_heat", [code])
        if tons is None:
            logger.warning(
                "sample data (CR-080): unit %s not connected — %r states no "
                "capacity, so there is no tonnage to record",
                row["unit_index"],
                code,
            )
            continue
        unit_id = unit_ids.get(unit_no_for[row["unit_index"]])
        if unit_id is None or unit_id not in takes_thermal:
            continue
        w6.set_characteristic(
            actor,
            unit_id,
            service_code="thermal_heat",
            key=key,
            value=str(tons),
            # Hard rule 3 — the unit is DATA and never part of the key name.
            unit_of_measure=uom,
        )
        written += 1
    return written


def _seed_premises_owners(actor: Any) -> int:
    """CR-039 wave C task 14 — *"seed several owner kinds"* (BR-MET-152).

    PO ruling 2026-08-27, verbatim: *"category is okay, no richer text"*.

    **THREE KINDS ARE SEEDED AND TWO ARE REFUSED BY NAME**, and the refusal is
    the part worth reading. `fixture.owner_category_for` states a category ONLY
    where the corpus already holds a fact — the developer at `500 Main St`
    (BR-CUS-083's own words), the two businesses trading at the commercial
    addresses they own, the two owners of let residential units. It returns
    `None` for everything else, and this function then leaves that premises with
    its free text and NO typed owner.

    ⚠ **THOSE UNMATCHED ROWS ARE THE POINT, NOT AN OMISSION.** BR-MET-151 says
    the free-text names migrate by MATCHING, on a review surface, one at a time
    — and a review surface with nothing on it is a promise nobody can check.
    This is the same reasoning task 11 used to leave the sample COMMERCIAL plan
    deliberately stating no outside-city factor: the demo shows BOTH halves.

    ⚠ **THROUGH THE VALIDATED WRITE PATHS, NEVER `.update()`.** Both
    `create_premises_owner` and `match_premises_owner` are used exactly as a
    clerk would use them, so the seed exercises the code task 12 built rather
    than reaching past it to the ORM — the rule this module's own header states,
    and the same one task 11 applied to the jurisdiction flag.

    ⚠ **NO PREMISES' `owner_manager` IS CLEARED** (BR-MET-151 clause 4). It is
    the provenance of the match and it is what `customers.services.open_account`
    reads for the default payer; clearing it here would take `OQ-500`'s money
    decision by accident, inside a seeder.

    Idempotent (BR-TEN-063): an owner is looked up by name first and a premises
    that already points at one is skipped, so a replay writes nothing.
    """
    from apps.metering import premises_owners as owner_services

    tenant_id = _tenant_id()
    unmatched = list(
        models.Premises.objects.filter(tenant_id=tenant_id, owner_id__isnull=True).exclude(
            owner_manager__isnull=True
        )
    )
    if not unmatched:
        # ⚠ **THE TAG STILL HAS TO RUN, AND SKIPPING IT IS A REAL DEFECT THIS
        # LINE ONCE HAD (DEF-650).** Since BR-MET-401 every seeded premises is
        # created WITH a party, so `unmatched` is normally empty here — and the
        # early return used to jump straight past `_tag`, leaving seven seeded
        # parties with `is_sample=False`. `BR-TEN-061` deletes sample data ON
        # THAT FLAG, so a "remove sample data" would have left the landlords
        # behind on a live tenant. Caught by
        # `test_cr039_c14__the_seeded_parties_are_tagged_sample_so_remove_takes_them`,
        # which is exactly what that test is for.
        _tag(models.PremisesOwner.objects.filter(tenant_id=tenant_id, is_sample=False))
        return 0

    by_name: dict[str, Any] = {
        row.name: row for row in models.PremisesOwner.objects.filter(tenant_id=tenant_id)
    }
    written = 0
    for premises in unmatched:
        name = (premises.owner_manager or "").strip()
        category = fixture.owner_category_for(name)
        if category is None:
            # BR-MET-152 clause 4. Nothing in the corpus says what kind of party
            # this is, so nothing is written and the address joins the review
            # list a person works through.
            continue
        owner = by_name.get(name)
        if owner is None:
            created = owner_services.create_premises_owner(
                actor,
                {
                    "name": name,
                    "category": category,
                    # BR-MET-151 clause 4 — which free-text string became this
                    # party. On the seed it is the same string, and recording it
                    # is what makes a seeded party indistinguishable in SHAPE
                    # from one a clerk matched by hand.
                    "source_owner_manager": name,
                },
            )
            owner = models.PremisesOwner.objects.get(tenant_id=tenant_id, pk=created["id"])
            by_name[name] = owner
            written += 1
        owner_services.match_premises_owner(actor, premises.id, {"owner_id": str(owner.id)})
    _tag(models.PremisesOwner.objects.filter(tenant_id=tenant_id, is_sample=False))
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W2 · TASK 2.10 — THE DEMO ESTATE'S SEATS (B18 §5.1.5 · §6.6)
# ══════════════════════════════════════════════════════════════════════════
#
# PO AUTHORISATION, 2026-08-24: ***"so add them"***.
#
# WHY METERING SEEDS THIS AT ALL. The eight `[shot]` account shapes need eight
# unit SEATS and the fixture has none free: 48 units carry 48 occupying
# accounts and BR-CUS-017 allows exactly one each, ever. `premises` and `units`
# are METERING's tables (B2 r4), so customers cannot make itself a seat — the
# decision log's own sentence for why 2.10 sat blocked: *"seven of the eight
# need a UNIT and the fixture has no free one; units are metering's table"*.
#
# ⚠ **THE ESTATE JOINS NO ROUTE, AND THAT IS LOAD-BEARING.** It is seeded AFTER
# `_ensure_cycle_and_route`, so its premises are in no route and its units are
# in no bill run. The PO's READY-TO-RUN July batch keeps exactly the 48 rows it
# had and gains no phantom missing-read — the same argument `CUTOVER_UNIT_NO`
# makes above, and the same one `apps/assets/sample_data.py` makes for leaving
# the net meter in inventory. The estate's units DO carry service points,
# because the chips on the Accounts list are read from them.
#
# ⚠ **SERVICES ARE INTERSECTED WITH WHAT THE TENANT HAS ENABLED, AND THE REST
# IS NAMED.** BR-MET-003 forbids a unit taking a service the tenant does not
# sell and BR-RAT-024 forbids the schedule behind it; enabling one is
# `apps.tenancy.services.update_tenant_service`, which is another module's
# write (B2 §2) and not a seeder's to make. So a tenant selling two services
# gets two chips and `cr030_unseeded_services()` says which eight it did not
# get. **On such a tenant the `+3` overflow chip does not appear, and that is
# the truth about the tenant rather than a fixture failure** — one visit to
# Settings → Services fixes it.


def cr030_wanted_services() -> tuple[str, ...]:
    """Every service the CR-030 estate asks for, deduplicated, in seed order."""
    wanted: list[str] = []
    for unit in fixture.cr030_units_flat():
        for code in unit.get("services") or ():
            if code not in wanted:
                wanted.append(code)
    return tuple(wanted)


def cr030_unseeded_services() -> list[str]:
    """The estate's services this tenant has NOT enabled — reported by name.

    The BR-TEN-060 posture, applied to the one thing this block cannot fix for
    itself: an unloaded thing is a NAMED line, never a silent skip.
    """
    enabled = seams.enabled_service_codes()
    return [code for code in cr030_wanted_services() if code not in enabled]


def _cr030_services_for(unit: dict[str, Any], enabled: set[str]) -> list[str]:
    return [code for code in (unit.get("services") or ()) if code in enabled]


def _cr030_plan_id() -> str | None:
    """The estate's units carry the RESIDENTIAL plan, for the reason every
    fixture unit carries one: `create_account` refuses to activate an account on
    a planless unit (BR-CUS-014/BR-MET-040), so the plan is not decoration.

    ⚠ It is the residential plan for the commercial suites too, and that is a
    stated compromise rather than an oversight: the fixture's Small Commercial
    plan is WATER-ONLY (`seed_demo`'s closing summary says so — *"Plan COM-SM is
    water-only"*), so putting the `+3` overflow unit on it would price seven of
    its eight services at nothing. The estate is a REGISTER demo, not a billing
    one — it joins no bill run — so the plan it carries only has to exist.
    """
    from apps.rating import sample_data as rating_sample

    return rating_sample.sample_plan_id(rating_sample.PLAN_RESIDENTIAL)


def _cr030_area_for(address_line: str, available: set[str]) -> str | None:
    """An AREA for an estate address, chosen deterministically from the ones the
    tenant HOLDS — never invented, and never None when the tenant has any.

    ⚠ **THIS SAID "a district" UNTIL 2026-08-27 AND THAT IS NO LONGER TRUE
    (CR-039 wave E task 22).** `available` is every area code the tenant holds,
    and since fixture V2.48.0.1 that includes the three SUB-AREAS as well as the
    four districts — so this now spreads the estate across BOTH levels. The
    behaviour is unchanged (pick one of what exists); the sentence describing it
    had drifted, and a comment claiming a guarantee it does not give is
    hard-won law 1.

    **It is also why NORTH is a strict superset of NORTH-NW ∪ NORTH-NE on a
    seeded tenant**, and that is a better demo than a clean partition: a
    reviewer sees premises tagged AT a district and premises tagged BELOW one,
    on the same tenant. The 44-premises estate is the other half — its
    addresses match the fixture's five streets, so `_area_code_for` gives them
    the finest area rather than a spread.

    `zlib.crc32` rather than `hash()`: Python's string hash is salted per
    process, so a fixture keyed on it would put the same address in a different
    area on every run (the same argument `apply_premises_geo` makes for its
    own jitter).
    """
    if not available:
        return None
    codes = sorted(available)
    return codes[zlib.crc32(address_line.encode("utf-8")) % len(codes)]


def _seed_cr030_estate(actor: Any) -> int:
    """The eight premises and thirteen units B18's screens name.

    Through `create_premises`, the S14 wizard's own call, so every rule a clerk
    meets applies. Idempotent (BR-TEN-063): a premises already on file by
    address is skipped and a replay writes nothing.
    """
    enabled = set(seams.enabled_service_codes())
    if not enabled:
        logger.info(
            "sample data (CR-030 W2): the tenant has no enabled service, so no estate "
            "unit can take one (BR-MET-003) and the eight account shapes have no seat"
        )
        return 0
    by_address = {row.address_line: row for row in selectors.premises_list()}
    areas_available = _seeded_area_codes()
    # CR-039 wave E task 23 · BR-MET-139 — once for the block, not per row.
    estate_state = seams.tenant_state()
    plan_id = _cr030_plan_id()
    written = 0
    for entry in fixture.cr030_premises_plan():
        address = entry["address_line"]
        if address in by_address:
            continue
        unit_payloads: list[dict[str, Any]] = []
        for unit in entry["units"]:
            payload: dict[str, Any] = {
                "label": unit["label"],
                "unit_no": unit["unit_no"],
                "unit_type": unit["unit_type"],
                "services": _cr030_services_for(unit, enabled),
            }
            if plan_id:
                payload["plan"] = {
                    "plan_id": plan_id,
                    "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                }
            unit_payloads.append(payload)
        premises_payload: dict[str, Any] = {
            "address_line": address,
            "city": fixture.CITY,
            # CR-039 wave E task 23 · BR-MET-139 — the tenant's OWN declared
            # state, never a hardcoded None. See `seams.tenant_state` for why
            # a plausible guess is worse than the blank it would replace.
            "state": estate_state,
            "postal_code": fixture.POSTAL,
            "premises_type": entry["premises_type"],
            "owner_manager": entry["owner_manager"],
            "services_available": sorted(
                {code for payload in unit_payloads for code in payload["services"]}
            ),
            "status": entry["status"],
            "units": unit_payloads,
            # CR-039 wave C task 11 — BR-RAT-101's flag, STATED. This estate's
            # units carry the RESIDENTIAL plan (`_cr030_plan_id` says so in its
            # own docstring), and that plan now states r10's outside-city
            # factor — so an address left unstated here is a bill BR-RAT-102
            # refuses by name, landing as one quiet exception row (BR-BIL-055)
            # rather than as a failed run. `fixture.default_jurisdiction` is
            # where the reasoning lives and why it is `True` and not `None`.
            "inside_city_limits": fixture.default_jurisdiction(),
        }
        # DEF-256 — EVERY sample premises lands in one of the tenant's districts.
        # `_area_code_for` matches the fixture's five street names and the
        # estate's addresses are the DESIGN's (1408 Elm Street, 500 Main St…),
        # so it finds none of them; a NULL `area_id` would leave eight rows out
        # of the district a screen filters by, which is the defect that test
        # names. The fallback is DETERMINISTIC on the address, so the same
        # tenant seeded twice puts the same premises in the same district.
        area_code = _area_code_for(address, areas_available) or _cr030_area_for(
            address, areas_available
        )
        if area_code is not None:
            premises_payload["area_code"] = area_code
        premises_payload["owner_id"] = _sample_owner_id(
            actor, premises_payload.get("owner_manager")
        )
        result = services.create_premises(actor, premises_payload)
        written += 1 + len(result.get("units", []))

    tenant_id = _tenant_id()
    addresses = [entry["address_line"] for entry in fixture.cr030_premises_plan()]
    premises_qs = models.Premises.objects.filter(tenant_id=tenant_id, address_line__in=addresses)
    _tag(premises_qs.filter(is_sample=False))
    unit_qs = models.Unit.objects.filter(tenant_id=tenant_id, premises__in=premises_qs)
    _tag(unit_qs.filter(is_sample=False))
    _tag(models.ServicePoint.objects.filter(tenant_id=tenant_id, unit__in=unit_qs, is_sample=False))
    missing = cr030_unseeded_services()
    if missing:
        logger.info(
            "sample data (CR-030 W2): the estate asked for services this tenant has not "
            "enabled and they are NOT seeded — %s. The `+3` chip overflow needs eight on "
            "one unit (B18 TC-ACC-4); enabling them is Settings → Services",
            ", ".join(missing),
        )
    return written


def _backfill_missing_unit_plans(actor: Any) -> int:
    """Give every sample unit the plan its account will derive from.

    ⚠ THIS IS NOT BELT-AND-BRACES, it is the repair path working. A unit
    created before rating's plans existed carries no `rate_plan_id`, and
    `create_account` REFUSES to activate an account on a planless unit
    (BR-CUS-014 — *"the account derives its plan from the unit"*). Without this
    a partially-failed first run leaves a tenant that can never be repaired by
    running the load again, which is exactly what a repair path is for: the
    second run has to be able to finish what the first one could not.
    """
    fixed = 0
    by_no = {unit["unit_no"]: unit["unit_index"] for unit in fixture.units_flat()}
    for unit in models.Unit.objects.filter(
        tenant_id=_tenant_id(), is_sample=True, rate_plan_id__isnull=True
    ):
        index = by_no.get(unit.unit_no)
        if index is None:
            continue
        plan_id = _plan_id_for(index)
        if plan_id is None:
            continue
        try:
            # ITS OWN SAVEPOINT. One unit whose plan cannot be recorded — an
            # actor the `users` table does not carry, a plan withdrawn since —
            # must not abort the transaction the other 47 are being written in.
            # PostgreSQL aborts a WHOLE transaction on any error, so without a
            # savepoint here the first failure would take the block with it.
            with transaction.atomic():
                services.assign_unit_plan(
                    actor,
                    str(unit.id),
                    {
                        "plan_id": plan_id,
                        "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                        "source": "new_connection",
                        "reason": "sample data load (BR-TEN-056)",
                    },
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data: unit %s kept no plan (%s) — its account will refuse "
                "to activate until a plan is assigned",
                unit.unit_no,
                type(exc).__name__,
            )
            continue
        fixed += 1
    return fixed


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W6 · TASKS 6.3 + 6.15 — THE TEMPLATE STARTERS, THE EIGHT BUILDS,
# THEIR FORTY-THREE UNITS AND THEIR FIFTY-THREE WORK ORDERS
# (and the W7 seats task 7.12 stands on — see `W7_SEATS`)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **TASK 6.3 IS NOT WHAT §11 SAYS IT IS — `BR-MET-109` CHANGED IT (PO
# 2026-08-25), AND THIS BLOCK IMPLEMENTS THE RULE, NOT THE TASK LINE.**
# §11 asks for *"`work_order_templates` seeded with the ten per-service sets and
# their gates"*, which reads as a POLICY the product imposes. The PO ruled the
# opposite, verbatim:
#
#   *"We are making it flexible ; utility users can issue as many work order
#   they want to execute this job; we will give them ready to use tempaltes -
#   they will develope these templats in work order section; then they can add
#   as many they want - they can do single or group"*
#
# So `work_order_templates` is a **TENANT-AUTHORED CATALOGUE** — the same shape
# as the document checklist (BR-CUS-095) and the discount programmes — and what
# ships is a set of **STARTERS the utility edits**. Two consequences this block
# obeys and a reader can check:
#
#   1. **Every starter row is `is_sample = True`,** so `--remove` sweeps them
#      like any other sample row (BR-TEN-057/061). A policy would not be
#      removable, and that difference is the rule made visible in the schema.
#   2. **NO BATCHING RULE IS SEEDED OR DERIVED.** BR-MET-109: *"`CON-26-0117`'s
#      5 of 7 orders across 25 units is an OUTCOME of that tenant's templates,
#      not a figure the engine derives. A different utility with different
#      templates gets a different number for the identical build, and both are
#      correct."* The seven orders below are DECLARED, one by one, exactly as
#      §8.2 draws them — **this module contains no arithmetic that turns 25
#      units into 7 orders**, and a lane looking for one must not find it here.
#
# ⚠ **THE PRODUCT'S WORDS ARE `activated` / `partly_activated`, NOT
# `energised` (CR-032).** B18 §5.4.8 and §5.4.9 still print the old word; the
# code's vocabulary (`connections.ACTIVATED`, `PARTLY_ACTIVATED`) is the ruled
# one and is what this seed writes. Nothing here spells `energised`.
#
# ════════════════════════════════════════════════════════════════════════════
# WHAT THE EIGHT ROWS HAVE TO REPRODUCE, AND WHY THAT IS THE ACCEPTANCE TEST
# ════════════════════════════════════════════════════════════════════════════
# `apps/metering/connection_reads._kpis` already computes B18 §5.4.1's five
# tiles, and its own docstring pins each figure to §5.4.8's eight rows. A seed
# that does not make those tiles foot is the wrong seed, so the arithmetic is
# stated here BEFORE the data:
#
#     row           units  waiting_on   state              open?
#     CON-26-0110     1    —            activated            no
#     CON-26-0119     1    permit       on_hold             yes
#     CON-26-0121     1    materials    in_progress         yes
#     CON-26-0126     1    inspection   partly_activated    yes
#     CON-26-0117    25    inspection   partly_activated    yes
#     CON-26-0128     1    —            partly_activated    yes
#     CON-26-0124     1    —            requested           yes
#     CON-26-0122    12    site access  in_progress         yes
#
#   OPEN 7 · WAITING ON INSPECTION 2 · PARTLY ACTIVATED 3 ·
#   UNITS AWAITING ACTIVATION 1+1+1+25+1+1+12 = 42 ·
#   OLDEST 19 days · CON-26-0119 · permit
#
# **`UNITS` IS COUNTED FROM `connection_services.unit_id`, NOT FROM THE
# PREMISES** (`connection_reads._unit_counts`), so the 25 apartments of
# `CON-26-0117` have to be real `units` rows carrying real per-unit service
# rows. That is the whole reason this block creates units at all.
#
# ⚠ **AND `core/sample_fixture.py` ASKS FOR EXACTLY THAT.** Its `500 Main St`
# entry says *"25 UNITS ARE NOT SEEDED AND MUST NOT BE … the 25 are the
# `SR-26-0043` NEW CONNECTION's future — `CON-26-0117` builds them (W6, not
# built)"*. This is that lane. The five estate units at that address are left
# untouched and **none of them joins the build** (`_w6_units_for` names the
# build's seats explicitly), so `Ridge Coffee Co.`'s four suites and the `+3`
# overflow unit cannot silently turn `UNITS 25` into 30.
#
# ════════════════════════════════════════════════════════════════════════════
# THE DATES ARE DECIDED WHEN THE SEED RUNS — DEF-629's POSTURE, APPLIED AGAIN
# ════════════════════════════════════════════════════════════════════════════
# `OLDEST · 19 days` is a figure the drawing took on the day it was drawn, and
# `_kpis` computes it as `now - submitted_at`. A literal `2026-08-05` would read
# 19 days for one day and drift for ever — the exact failure DEF-629 records for
# opening buckets, and the PO's ruling on it applies here unchanged: *"whenever
# you do the migration cant you devcide the date at that time"*.
#
# So every date below is an OFFSET from the tenant's own today and the drawn
# date rides beside it. The anchor is `DRAWN_AS_OF` (2026-08-24) and it is
# DERIVED, not picked: the drawn tiles constrain the day the screens were taken
# to `Aug 21 … Aug 24` — `DUE TO CUT THIS WEEK 2` needs `Aug 26 ≤ today + 7`,
# `MOVING THIS WEEK 1` needs `Aug 28 ≤ today + 7`, `COMPLETED THIS MONTH 3`
# needs Aug 02/05/09 to have happened, and §5.8.2's *"`CUT DATE` renders in the
# accent when it is this week"* needs `Aug 24 ≥ today`. **Aug 24 is the only day
# in that window**, so it is the anchor. The arithmetic is written down because
# a reader who disagrees with it can check it.
#
# BR-TEN-043 is satisfied for DEF-629's own reason: the clock is read ONCE, at
# the moment the fixture is planted, and the answer is STAMPED into the rows. A
# replay writes nothing (BR-TEN-063) and re-dates nothing.

#: The day B18's New Connect, Transfers and Disconnects screens were drawn — see
#: the block header for the derivation. Every offset below is measured from it.
DRAWN_AS_OF = date(2026, 8, 24)

#: B18 §8.1's per-service order sets, VERBATIM in their drawn order, each with
#: the scope §5.4.9's third structural fact gives it (*"`scope` takes three
#: values and they all appear in one connection — Premise (service drop; site
#: inspection), Unit (tap & service line), Asset (both meter sets)"*).
#:
#: ⚠ **GAS IS THE ONE THAT CATCHES PEOPLE OUT AND ITS FLAG IS ON THE LIGHT-UP.**
#: B18 §8.1: *"Every other metered service is billable once the meter is set;
#: gas is not billable until the light-up, and a lane that gates gas on the
#: meter set will bill a customer with no gas."*
#:
#: ⚠ **THREE SERVICES CARRY NO GATE ROW AND NONE OF THE THREE IS AN OVERSIGHT
#: — see `W6_UNGATED_STARTERS`, which carries the reasons as DATA so a test can
#: assert them rather than a reader having to trust a comment.**
#: `CR-070` wave M — the ONE template a seeded tenant carries that is not a
#: New Connect starter. Named here rather than typed in the seeder because
#: `tests/test_cr070_m_sample_data.py` asserts the seeded rule points at it,
#: and two spellings of an em-dashed name are a bug nobody sees until a demo.
EXCHANGE_TEMPLATE_NAME = "Meter exchange \u2014 residential"

W6_TEMPLATE_STARTERS: tuple[tuple[str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "electric",
        (
            ("Service drop", work_tables.SCOPE_PREMISE, False),
            ("Meter set", work_tables.SCOPE_ASSET, True),
        ),
    ),
    (
        "water",
        (
            ("Site inspection & mark-out", work_tables.SCOPE_PREMISE, False),
            ("Tap and service line", work_tables.SCOPE_UNIT, False),
            ("Meter set", work_tables.SCOPE_ASSET, True),
        ),
    ),
    (
        "gas",
        (
            ("Inspection", work_tables.SCOPE_PREMISE, False),
            ("Service line and tap", work_tables.SCOPE_UNIT, False),
            # NOT the gate. This is the row a copying lane gets wrong.
            ("Meter set", work_tables.SCOPE_ASSET, False),
            # ⚠ THE GATE.
            ("Pressure test and light-up", work_tables.SCOPE_PREMISE, True),
        ),
    ),
    ("sewer", (("Tap and connection inspection", work_tables.SCOPE_UNIT, False),)),
    ("trash", (("Container delivery", work_tables.SCOPE_PREMISE, True),)),
    # storm_water: ZERO orders by design — see `W6_UNGATED_STARTERS`.
    ("storm_water", ()),
    # ⊖ **`DEF-WRK-9266` — NO *Net meter swap* (2026-10-03).** PO 2026-10-02
    # (`DEF-MET-9037`): *"we are not doing net metering right now … Capacity is
    # the panels or battery only."* Create fits no net meter on a solar build,
    # so a swap was a job for hardware nobody installs; §8.1 itself draws
    # solar as *"3–4"* orders. *Commissioning* stays per-asset: it is done on
    # the PANELS, which Create does fit. A tenant already holding the untouched
    # starter is repaired by `metering/0070`.
    (
        "solar",
        (
            ("Interconnection application", work_tables.SCOPE_PREMISE, False),
            ("Inspection", work_tables.SCOPE_PREMISE, False),
            ("Commissioning and witness test", work_tables.SCOPE_ASSET, False),
        ),
    ),
    (
        "broadband",
        (
            ("Drop or equipment install", work_tables.SCOPE_PREMISE, False),
            ("Activate", work_tables.SCOPE_PREMISE, True),
        ),
    ),
    # ⊖ **`DEF-WRK-9266` — NO *Meter set*, AND THE GATE MOVES TO THE SERVICE
    # CONNECTION (2026-10-03).** `CR-080` (PO 2026-09-07, *"connected tonnage -
    # it is capacity not metering"*) took the meter off a thermal unit; the
    # tonnage is recorded on the unit and nothing is fitted. §8.1's gate was
    # the meter set because that was the step that finished the connection;
    # with no meter, the last physical step is the service connection — fire's
    # own shape below for the same kind of device-less, unit-scoped service.
    # A judgment with that reasoning, recorded in the decision log 2026-10-03.
    (
        "thermal_heat",
        (
            ("Inspection", work_tables.SCOPE_PREMISE, False),
            ("Service connection", work_tables.SCOPE_UNIT, True),
        ),
    ),
    (
        "battery",
        (
            ("Electrical inspection", work_tables.SCOPE_PREMISE, False),
            ("Commissioning", work_tables.SCOPE_ASSET, True),
        ),
    ),
    # ── CR-063 · FIRE, the ELEVENTH service (PO 2026-09-02) ─────────────────
    # ⚠ **THE TWO STEPS ARE THIS LANE'S READING OF THE SAME §8.1 SHAPE THE TEN
    # ABOVE FOLLOW, NOT A RULING**, and they are here rather than in
    # `W6_UNGATED_STARTERS` because fire IS installed work a crew does: a fire
    # line is tapped and a hydrant is set, and both are inspected before the
    # service is turned on. Every neighbour with physical equipment carries the
    # same pair — an inspection scoped to the PREMISE and an install scoped to
    # the thing installed, with the second flagged as the one that completes the
    # connection.
    #
    # The install is SCOPE_UNIT and not SCOPE_ASSET deliberately: a fire line
    # serves the UNIT, and unlike a meter or an inverter there is no register or
    # serial for the row to hang on. That matches `thermal_heat`'s
    # *"Service connection"* rather than `battery`'s *"Commissioning"*.
    (
        "fire",
        (
            ("Fire marshal inspection", work_tables.SCOPE_PREMISE, False),
            ("Service connection", work_tables.SCOPE_UNIT, True),
        ),
    ),
)

#: The three services whose §8.1 gate names no starter row of their own, and why
#: — carried as DATA so `tests/test_w6_w7_seed.py` can assert the absence.
W6_UNGATED_STARTERS: dict[str, str] = {
    "sewer": (
        "B18 §8.1 gates sewer on *'the water service it derives from'*, which is not one of "
        "sewer's own orders. `work_order_templates.is_gate` marks an order of THIS service, so "
        "no starter carries it; the cross-service gate is task 6.8's "
        "(`connection_services.gate_order_id`), never a template's."
    ),
    "solar": (
        "B18 §8.1 gates solar on *'permission to operate'*, and PTO names NONE of the steps "
        "its own set draws (interconnection application · inspection · commissioning and "
        "witness test; the net meter swap left on 2026-10-03, DEF-WRK-9266, because no net "
        "meter is fitted). Flagging one would be this seeder deciding what "
        "authorises a customer's export. REPORTED; under BR-MET-109 the utility flags it."
    ),
    "storm_water": (
        "B18 §8.1 gives storm water **0** orders — *'assessed from records — no visit'* — so "
        "there is nothing to flag and no starter is seeded. Its gate is *'assessment recorded'*, "
        "which is a characteristic on the UNIT (BR-MET-104), not a work order."
    ),
}

#: ── CR-070 wave E · the same three absences, in the words a CLERK reads ────
#:
#: `W6_UNGATED_STARTERS` above is the ENGINEERING reason and is where a lane
#: goes to understand the decision — it quotes B18 §8.1, names `BR-MET-104` and
#: points at task 6.8. **None of that may appear on a screen** (B14 rule 32: no
#: rule id and no internal code in clerk-facing copy), and `no_gate_reason` IS
#: shown — it is what `Work-013`'s GATE column has to say when the cell is
#: empty and somebody asks why.
#:
#: So the same three facts are carried twice, on purpose, and the short form is
#: quoted verbatim from `US-WRK-019` TC-3 rather than paraphrased here.
#:
#: ⚠ **STORM WATER'S REASON IS STORED ON NO ROW AND CANNOT BE**, because storm
#: water seeds ZERO starters (§8.1: *"assessed from records — no visit"*).
#: `no_gate_reason` is a column on a template and storm water has no template
#: to put it on; the fact lives here and in `W6_UNGATED_STARTERS`, and
#: `US-WRK-019` TC-3's third clause is met by the declaration rather than by a
#: row. Written down because an absence nobody explains reads as an omission.
W6_NO_GATE_REASON: dict[str, str] = {
    "sewer": "gated on the water service it derives from",
    "storm_water": "assessed from records, no visit",
    "solar": "the gate is permission to operate, which names no step",
}

#: The seats the eight builds stand on. `existing: True` names a premises the
#: estate already seeded — never re-created, never re-addressed.
#:
#: ⚠ `12 Harbour View` CARRIES TWO UNITS AND THE SECOND IS W7's. B18 draws that
#: address three times — `CON-26-0124` (a build), `A-12041 · Reyes, Antonio` (a
#: move-in, §5.5.7) and `A-11109 · Osei, Grace` (a transfer's FROM address,
#: §5.7.6) — and a build ends with its unit **vacant, service off and no
#: account** (§5.4.9). One unit cannot be all three. Two units at one address is
#: the fixture's own answer to exactly this, already used at `88 Pine Vista`
#: (*"Two units, so both are lawful at one address (BR-CUS-017 is per UNIT)"*).
#: The build takes unit 1; the transfer's live account takes unit 2.
W6_SEATS: tuple[dict[str, Any], ...] = (
    {
        # CON-26-0110 · the ACTIVATED build. The estate already seeds this
        # premises and its single unit carries `leave_vacant` — which is exactly
        # what a finished new connect leaves behind (§5.4.9: *"A NEW CONNECT
        # ENDS WITH UNITS VACANT, SERVICE OFF AND NO ACCOUNT. That is the
        # terminal state, not an incomplete one"*). Nothing is created here.
        "address_line": "3450 Oak Ridge Dr",
        "existing": True,
        "unit_nos": ("SCW-U-207",),
    },
    {
        "address_line": "77 Foundry Row",
        "premises_type": "single_family",
        "units": (("Unit 1", "SCW-U-301"),),
    },
    {
        "address_line": "14 Willow Bend",
        "premises_type": "single_family",
        "units": (("Unit 1", "SCW-U-302"),),
    },
    {
        "address_line": "8 Quarry Lane",
        "premises_type": "single_family",
        "units": (("Unit 1", "SCW-U-303"),),
    },
    {
        # CON-26-0117 · the batching proof. The premises EXISTS (five estate
        # units); the twenty-five apartments are this build's. `SCW-U-325…349`
        # keeps them clear of the estate's `SCW-U-2xx` block so a reader can
        # tell at a glance which seed planted which seat.
        "address_line": "500 Main St",
        "existing": True,
        "units": tuple((f"Unit {300 + n}", f"SCW-U-{324 + n}") for n in range(1, 26)),
    },
    {
        "address_line": "240 Sable Court",
        "premises_type": "single_family",
        "units": (("Unit 1", "SCW-U-304"),),
    },
    {
        # CR-070 wave A (2026-09-03) · US-WRK-006's phase-0 slice — `77 Cedar
        # Ct`, the premises with an existing meter and NO new-connection build
        # that a leak investigation is raised on (US-WRK-001 §4, J62's
        # upstream). A SEAT and not a build on purpose: no row in
        # `W6_CONNECTIONS` names it, so it takes a unit and no connection, and
        # the Work module's one phase-0 act — an order with no connection — has
        # an address to stand on in the demo. It is metering's row because
        # premises are metering's table (BR-WRK-002: Work writes none of them);
        # the account the story also names (`A-10891`) arrives with the wave
        # that builds the account-anchored door (wave M) and is not seeded
        # here. Tagged `is_sample` with the rest of the seats, removed with them.
        "address_line": "77 Cedar Ct",
        "premises_type": "single_family",
        "units": (("Unit 1", "SCW-U-319"),),
    },
    {
        "address_line": "12 Harbour View",
        "premises_type": "single_family",
        # unit 2 is the W7 transfer seat — see the note above. It takes an
        # account, so it takes a plan and its service points.
        "units": (("Unit 1", "SCW-U-305"),),
        "account_units": (("Unit 2", "SCW-U-306"),),
    },
    {
        "address_line": "Kestrel Park ph. 2",
        "premises_type": "apartment_complex",
        "owner_manager": "Kestrel Park Developments",
        "units": tuple((f"Unit {n}", f"SCW-U-{306 + n}") for n in range(1, 13)),
    },
)

#: The seats **task 7.12** stands on — declared HERE because `premises` and
#: `units` are metering's tables (B2 r4) and `apps/customers/sample_data.py` may
#: not create one. Every unit here TAKES AN ACCOUNT, so unlike a build's seat it
#: carries the residential plan (`create_account` refuses to activate an account
#: on a planless unit — BR-CUS-014 / BR-MET-040) and its service points.
#:
#: ⚠ **THE ADDRESSES OF THE FIVE DISCONNECT SEATS ARE FIXTURE-NAMED AND SAY SO.**
#: B18 §5.8.6 draws an `ADDRESS` column and prints no address in any of its nine
#: rows, so there is nothing to copy. The fixture names them, exactly as
#: `core/sample_fixture.CR030_PREMISES` names `61 Larkspur Way` — *"THE ONE ROW
#: B18 DRAWS AS A SHAPE AND NEVER NAMES … The fixture names it — and says so
#: here rather than letting a later reader assume it was copied from a
#: screenshot"*. The seven TRANSFER addresses are B18 §5.7.6's own.
W7_SEATS: tuple[dict[str, Any], ...] = (
    # ── B18 §5.7.6's five transfers: three FROM/TO pairs, one TO ────────────
    {"address_line": "18 Marten Row", "units": (("Unit 1", "SCW-U-350"),)},
    {"address_line": "204 Quarry Lane", "units": (("Unit 1", "SCW-U-351"),)},
    {"address_line": "3 Kestrel Close", "units": (("Unit 1", "SCW-U-352"),)},
    {"address_line": "71 Alder Street", "units": (("Unit 1", "SCW-U-353"),)},
    {"address_line": "44 Larkspur Way", "units": (("Unit 1", "SCW-U-354"),)},
    {"address_line": "88 Foundry Row", "units": (("Unit 1", "SCW-U-355"),)},
    {"address_line": "26 Meadowbank Rise", "units": (("Unit 1", "SCW-U-356"),)},
    # ── B18 §5.8.6's five plantable disconnect rows (addresses fixture-named) ─
    {"address_line": "9 Tanner Street", "units": (("Unit 1", "SCW-U-357"),)},
    {
        "address_line": "142 Bakers Row",
        "premises_type": "commercial_building",
        "unit_type": "commercial",
        "units": (("Suite 1", "SCW-U-358"),),
    },
    {"address_line": "27 Selby Drive", "units": (("Unit 1", "SCW-U-359"),)},
    {"address_line": "16 Poplar Grove", "units": (("Unit 1", "SCW-U-360"),)},
    {"address_line": "5 Winterton Close", "units": (("Unit 1", "SCW-U-361"),)},
)

#: B18 §5.4.8's eight rows, declared so a reader can go and count them.
#:
#: `target_offset` / `open_days` are offsets from `DRAWN_AS_OF`; the drawn date
#: rides beside each as `drawn_target`, so anchoring loses nothing.
#: `services` maps a service code to the units it is taken at — `None` means
#: PER-PREMISE (§5.4.6: *"`unit` is nullable because not every service is
#: per-unit — a per-premise main tap belongs to the build, not to any one of its
#: 25 units"*), an integer `n` means the build's first `n` seats.
#: `orders` is `(type, service, scope, done)`, DECLARED and never derived
#: (BR-MET-109).
W6_CONNECTIONS: tuple[dict[str, Any], ...] = (
    {
        "connection_no": "CON-26-0110",
        "sequence": 110,
        "address_line": "3450 Oak Ridge Dr",
        "drawn_target": date(2026, 8, 14),
        "target_offset": -10,
        "open_days": 17,
        "waiting_on": None,
        "state": work_tables.ACTIVATED,
        "units": 1,
        "drawn_request_no": "SR-26-0018",
        "services": {"electric": 1, "water": 1},
        "activated": ("electric", "water"),
        "in_progress": (),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, True),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, True),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, True),
            ("Meter set", "water", work_tables.SCOPE_ASSET, True),
        ),
    },
    {
        # THE OLDEST OPEN BUILD — the `OLDEST · 19 days` tile is this row, and
        # nothing else may be older. ⚠ `5 of 9` AND `On hold` at once: a hold
        # outranks progress and does not erase it (§5.4.9).
        "connection_no": "CON-26-0119",
        "sequence": 119,
        "address_line": "77 Foundry Row",
        "drawn_target": date(2026, 9, 8),
        "target_offset": 15,
        "open_days": 19,
        "waiting_on": "permit",
        "held": True,
        "state": work_tables.ON_HOLD,
        "units": 1,
        "services": {"electric": 1, "water": 1, "gas": 1},
        "activated": ("electric", "water"),
        "in_progress": (),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, True),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, True),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, True),
            ("Meter set", "water", work_tables.SCOPE_ASSET, True),
            ("Inspection", "gas", work_tables.SCOPE_PREMISE, False),
            ("Service line and tap", "gas", work_tables.SCOPE_UNIT, False),
            ("Meter set", "gas", work_tables.SCOPE_ASSET, False),
            ("Pressure test and light-up", "gas", work_tables.SCOPE_PREMISE, False),
        ),
    },
    {
        "connection_no": "CON-26-0121",
        "sequence": 121,
        "address_line": "14 Willow Bend",
        "drawn_target": date(2026, 9, 15),
        "target_offset": 22,
        "open_days": 15,
        # In progress AND waiting — the two axes §5.4.9 fact 1a separates.
        "waiting_on": "materials",
        "state": work_tables.IN_PROGRESS,
        "units": 1,
        "drawn_request_no": "SR-26-0042",
        "services": {"electric": 1, "water": 1},
        "activated": (),
        "in_progress": ("electric", "water"),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, False),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, True),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, False),
            ("Meter set", "water", work_tables.SCOPE_ASSET, False),
        ),
    },
    {
        "connection_no": "CON-26-0126",
        "sequence": 126,
        "address_line": "8 Quarry Lane",
        "drawn_target": date(2026, 9, 22),
        "target_offset": 29,
        "open_days": 13,
        "waiting_on": "inspection",
        "state": work_tables.PARTLY_ACTIVATED,
        "units": 1,
        "services": {"electric": 1, "water": 1, "gas": 1},
        "activated": ("electric",),
        "in_progress": ("water",),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, True),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, True),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, False),
            ("Meter set", "water", work_tables.SCOPE_ASSET, False),
            ("Inspection", "gas", work_tables.SCOPE_PREMISE, False),
            ("Service line and tap", "gas", work_tables.SCOPE_UNIT, False),
            ("Meter set", "gas", work_tables.SCOPE_ASSET, False),
            ("Pressure test and light-up", "gas", work_tables.SCOPE_PREMISE, False),
        ),
    },
    {
        # ⚠ **THE BATCHING PROOF, AND IT MUST STAY EXACTLY AS IT IS** (B18
        # §5.4.8): *"25 units, 5 services, and SEVEN orders. A lane that
        # produces 76 has broken §8."* The seven below are §8.2's own
        # breakdown, one row per line of it:
        #     per-premise : service drop · main tap · sewer connection    = 3
        #     per-unit    : meter set ×25 batched into 2 crew days        = 2
        #     per-premise : pressure test · trash container delivery      = 2
        # They are DECLARED because BR-MET-109 makes the split the utility's
        # choice and not an engine derivation.
        "connection_no": "CON-26-0117",
        "sequence": 117,
        "address_line": "500 Main St",
        "drawn_target": date(2026, 9, 30),
        "target_offset": 37,
        "open_days": 11,
        "waiting_on": "inspection",
        "state": work_tables.PARTLY_ACTIVATED,
        "units": 25,
        "drawn_request_no": "SR-26-0043",
        # Electric and water are taken AT EACH of the 25 apartments — that is
        # what makes `UNITS 25` and the `42` tile true. Gas, sewer and trash are
        # per-premise: a main tap, a sewer connection and a bin store belong to
        # the building and to no one flat.
        "services": {
            "electric": 25,
            "water": 25,
            "gas": None,
            "sewer": None,
            "trash": None,
        },
        "activated": ("electric", "water", "sewer"),
        "in_progress": (),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Main tap", "water", work_tables.SCOPE_PREMISE, True),
            ("Sewer connection", "sewer", work_tables.SCOPE_PREMISE, True),
            ("Meter set — crew day 1", "electric", work_tables.SCOPE_UNIT, True),
            ("Meter set — crew day 2", "water", work_tables.SCOPE_UNIT, True),
            ("Pressure test and light-up", "gas", work_tables.SCOPE_PREMISE, False),
            ("Container delivery", "trash", work_tables.SCOPE_PREMISE, False),
        ),
    },
    {
        "connection_no": "CON-26-0128",
        "sequence": 128,
        "address_line": "240 Sable Court",
        "drawn_target": date(2026, 10, 2),
        "target_offset": 39,
        "open_days": 9,
        "waiting_on": None,
        "state": work_tables.PARTLY_ACTIVATED,
        "units": 1,
        "services": {"electric": 1, "water": 1},
        "activated": ("electric",),
        "in_progress": (),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, True),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, False),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, False),
            ("Meter set", "water", work_tables.SCOPE_ASSET, False),
        ),
    },
    {
        "connection_no": "CON-26-0124",
        "sequence": 124,
        "address_line": "12 Harbour View",
        "drawn_target": date(2026, 10, 12),
        "target_offset": 49,
        "open_days": 7,
        "waiting_on": None,
        "state": work_tables.REQUESTED,
        "units": 1,
        "services": {"electric": 1, "water": 1, "broadband": 1},
        "activated": (),
        "in_progress": (),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, False),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, False),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, False),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, False),
            ("Meter set", "water", work_tables.SCOPE_ASSET, False),
            ("Drop or equipment install", "broadband", work_tables.SCOPE_PREMISE, False),
            ("Activate", "broadband", work_tables.SCOPE_PREMISE, False),
        ),
    },
    {
        "connection_no": "CON-26-0122",
        "sequence": 122,
        "address_line": "Kestrel Park ph. 2",
        "drawn_target": date(2026, 11, 1),
        "target_offset": 69,
        "open_days": 5,
        "waiting_on": "site access",
        "state": work_tables.IN_PROGRESS,
        "units": 12,
        "services": {"electric": 12, "water": 12, "sewer": None},
        "activated": (),
        "in_progress": ("electric",),
        "orders": (
            ("Service drop", "electric", work_tables.SCOPE_PREMISE, True),
            ("Meter set", "electric", work_tables.SCOPE_ASSET, False),
            ("Site inspection & mark-out", "water", work_tables.SCOPE_PREMISE, False),
            ("Tap and service line", "water", work_tables.SCOPE_UNIT, False),
            ("Meter set", "water", work_tables.SCOPE_ASSET, False),
            ("Tap and connection inspection", "sewer", work_tables.SCOPE_UNIT, False),
        ),
    },
)

#: What this block could NOT plant, by name, so a report never has to guess.
W6_ABSENCES: dict[str, str] = {
    "service_request_link": (
        "B18 §5.4.8 links `CON-26-0117` to `SR-26-0043` and §5.4.9 heads `CON-26-0110` *'from "
        "request SR-26-0018'*, and `connections.service_request_id` is the column for it. "
        "`apps/metering/seams.py` publishes NO service-request read (measured 2026-08-25: the "
        "customers seam set is `create_account_from_import`, `import_lookup_indexes`, "
        "`post_account_opening_batch`, `active_account_for_unit`, `account_reference_count`), and "
        "metering may not reach into `customers`' ORM (B1/B8: no foreign ORM). So the seeded "
        "builds carry NO request link and the list's `request #` search leg finds none of them. "
        "A seam is OWED."
    ),
    "charges_and_deposit_policy": (
        "§5.4.9's Charges tab draws four coded lines and a `$150.00 per residential unit` "
        "deposit POLICY badged *'Policy, not a collection'*. `connections.quote_total` is the "
        "only money column on the build and task 6.10's charge path posts nothing (OQ-379: "
        "*'the total is recorded on the connection and posted by nothing'*), so no charge line "
        "and no deposit policy is seeded — a figure with no posting path behind it would read "
        "as money that moved."
    ),
    "assets_and_sub_meter_links": (
        "§5.4.9's Assets tab draws `M-5001`/`M-5002` on `CON-26-0110` and a sub-meter link "
        "count. `work_orders.asset_id` exists; the WRITE is `apps/assets`' and "
        "`connections.py` states it has *'no seam that writes one'*. No asset is attached to a "
        "seeded order — REPORTED, not counted as zero."
    ),
    "outstanding_work_items": (
        "BR-MET-114 makes `connection_todos` a list a HUMAN marks (*'human will mark everything "
        "to start with'*). §5.4.9 draws one on `CON-26-0110` (*'Occupancy set per unit'*) and "
        "`NCT-03.9` draws three on the 26-unit build. A seeder is not a human and marking them "
        "here would put the system's own words in a person's mouth, which is the half of "
        "BR-MET-114 the ruling exists to protect. None is seeded."
    ),
}


def w6_anchor_on() -> date:
    """The day the W6/W7 fixture's offsets are measured from — DECIDED AT SEED
    TIME and then PERSISTED. `demo_cutover_on()`'s shape exactly.

    * **First run** — the tenant's own today (`seams.tenant_today()`, the
      utility's own day per BR-TEN-081).
    * **Every run after** — recovered from `CON-26-0110`'s stored target, which
      this fixture wrote at a known offset. A replay therefore re-dates nothing
      (BR-TEN-063) and every later reader still ages from a STORED date rather
      than from a clock (BR-TEN-043).
    """
    anchor = next(row for row in W6_CONNECTIONS if row["connection_no"] == "CON-26-0110")
    stored = (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), connection_no=anchor["connection_no"])
        .values_list("target_activation", flat=True)
        .first()
    )
    if stored is not None:
        return stored - timedelta(days=anchor["target_offset"])
    return seams.tenant_today()


def _w6_service_codes() -> tuple[str, ...]:
    """Every service the eight builds ask for, deduplicated, in seed order."""
    wanted: list[str] = []
    for row in W6_CONNECTIONS:
        for code in row["services"]:
            if code not in wanted:
                wanted.append(code)
    return tuple(wanted)


def w6_unseeded_services() -> list[str]:
    """The builds' services this tenant has NOT enabled — reported BY NAME.

    BR-MET-003 forbids a unit taking a service the tenant does not sell and
    `add_connection_service` refuses one through metering's own seam; enabling a
    service is `apps.tenancy.services.update_tenant_service`, another module's
    write (B2 §2) and not a seeder's to make. **On such a tenant the ORDERS
    fractions and the SERVICES badges are smaller than B18 §5.4.8 draws**, and
    that is the truth about the tenant rather than a fixture failure. The UNITS
    and STATE tiles are unaffected: they read units and service STATES, not
    service codes.
    """
    enabled = set(seams.enabled_service_codes())
    return [code for code in _w6_service_codes() if code not in enabled]


def _seat_premises_by_address() -> dict[str, Any]:
    addresses = [entry["address_line"] for entry in (*W6_SEATS, *W7_SEATS)]
    return {
        row.address_line: row
        for row in models.Premises.objects.filter(
            tenant_id=_tenant_id(), address_line__in=addresses
        )
    }


def _seed_work_order_exchange_template(actor: Any) -> int:
    """**`Meter exchange — residential`** — the job the asset-age rule raises.

    `CR-070` wave M. `work_order_rules.template` is NOT NULL and refused with a
    sentence when it is missing (`rules._clean_rule`), so the seven seeded rules
    need published templates to point at — and until this landed the only
    published templates on a seeded tenant were the eight NEW-CONNECT starters
    (*Service drop*, *Meter set*, *Tap and service line* …). A rule that raises
    *Meter set* on a meter that is already in the ground is not the demo, and
    `M7` asserts the raised orders read **Meter exchange**.

    ⚠ **`sequence` IS 0, AND THAT IS THE WHOLE SAFETY OF THIS FUNCTION.**
    `BR-WRK-016` proposes New Connect step 6's jobs from published templates
    with `sequence >= 1`; `selectors.proposed_work_orders` says so in the query
    and `DEF-WRK-3573` is the defect that put the clause there, naming *Meter
    exchange — residential* by name as the template that must NOT appear. So a
    published exchange template adds nothing to any build's proposal, and the
    eight seeded builds keep proposing exactly what they proposed before.

    ⚠ **IT NAMES NO ASSET TYPES, WHICH MEANS IT APPLIES TO EVERY ASSET.**
    `asset_door.templates_for_asset`: *"a template that names NO asset types is
    not a template that applies to none — it is one nobody has restricted"*.
    Restricting it here would be inventing a policy for a utility that has not
    opened the asset-types tab yet.

    ⚠ **ON THE TENANT'S OWN BACKBONE SERVICE, NOT ON WATER** (`DEF-2397`). A
    template on a service the tenant does not sell is refused by the service.

    ⚠ **IDEMPOTENT ON `(service, sequence=0, name)`** (`BR-TEN-063`), and the
    `wot_details` row is written only when it is MISSING for the same reason the
    starters do it that way: `replace_collection` moves `updated_at`, `publish`
    reads that to tell *"the bundle changed"* from *"somebody pressed the button
    twice"*, and writing it unconditionally would publish an identical v2 on
    every replay.
    """
    from apps.work import templates_svc
    from apps.work.models import WorkOrderTemplateDetail

    tenant_id = _tenant_id()
    plan = estate()
    if plan.primary is None:
        logger.info(
            "sample data (CR-070 wave M): no %r template was seeded — this tenant has no "
            "metered service to hang one on, so the asset-age rule has nothing to raise",
            EXCHANGE_TEMPLATE_NAME,
        )
        return 0
    code = plan.primary.code
    service_id = seams.service_row_id(code)
    if service_id is None:
        return 0

    row = work_tables.WorkOrderTemplate.objects.filter(
        tenant_id=tenant_id, service_id=service_id, name=EXCHANGE_TEMPLATE_NAME
    ).first()
    written = 0
    if row is None:
        header = templates_svc.create_draft(
            actor,
            {
                "name": EXCHANGE_TEMPLATE_NAME,
                "service": code,
                "scope": work_tables.SCOPE_ASSET,
                # ⚠ 0 — see the docstring. Not `max + 1`.
                "sequence": 0,
                "is_gate": False,
            },
        )
        template_id = header["id"]
        version = int(header["version"] or 0)
        written += 1
    else:
        template_id = str(row.id)
        version = int(row.version or 0)

    if not WorkOrderTemplateDetail.objects.filter(
        tenant_id=tenant_id, template_id=template_id
    ).exists():
        templates_svc.replace_collection(actor, template_id, "details", {})
    if version < 1:
        templates_svc.publish(actor, template_id, change_note="First publish")

    # BR-TEN-057 — metering's own write of its own tag, on this one row.
    _tag(
        work_tables.WorkOrderTemplate.objects.filter(
            tenant_id=tenant_id, pk=template_id, is_sample=False
        )
    )
    return written


#: `DEF-WRK-9626` (`CR-168-BRC10` §F) — one published template per FLOW
#: MOMENT, under the job type that fits it (`from_flows.FLOW_JOB_TYPE_CODES`,
#: decision log 2026-10-04). Before this the demo offered a move-out, a
#: move-in, a transfer, a reconnect and a short read ONE job — *Meter exchange
#: — residential* — because it was the only sequence-0 template there was.
FLOW_VISIT_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("Final read", "RE_READ"),
    ("Opening read", "RE_READ"),
    ("Changeover read", "RE_READ"),
    ("Re-read", "RE_READ"),
    ("Reconnect visit", "DISCONNECT_RECONNECT"),
    # `DEF-CUS-9631` — the disconnect wizard's cut visit (`from_flows.
    # FLOW_DISCONNECT`); named as `FLOW_VISIT_TEMPLATE_NAMES` names it.
    ("Disconnect visit", "DISCONNECT_RECONNECT"),
)


#: `DEF-WRK-9694` (`CR-168-BRC10` round 8) — what each visit template asks the
#: technician to DO. The five above were published with a details row and
#: nothing else, so even a job raised FROM one gave the phone nothing to tick.
#: Sample data, the utility's to edit; no reading here posts as a meter read,
#: because a visit raised on an account names no meter (`DEF-WRK-9683`).
FLOW_VISIT_TASKS: dict[str, tuple[str, ...]] = {
    "Final read": ("Read the meter and note the register", "Check the meter for damage"),
    "Opening read": ("Read the meter and note the register", "Confirm the service is on"),
    "Changeover read": ("Read the meter at the changeover",),
    "Re-read": ("Read the meter again and note the register",),
    "Reconnect visit": ("Restore the service", "Confirm the meter is turning"),
    "Disconnect visit": ("Cut the service as the instruction says", "Read the meter and seal it"),
}

#: FB-013 (`DEF-WRK-10641`, PO rulings 2026-10-28) — the visit steps that check
#: the account's money first, and how fresh the figure must be (minutes). DATA
#: on the step, like the photo rule (R18: no code knows what a cut is). The cut
#: step is stopped on the phone when a fresh read shows the balance cleared;
#: the restore step's check is the R17 warning when the figure is stale. Only
#: a template not yet published gets them — a published one changes by a new
#: version, which is the utility's act (decision log judgment 8).
FLOW_VISIT_MONEY_STEPS: dict[tuple[str, str], int] = {
    ("Disconnect visit", "Cut the service as the instruction says"): 5,
    ("Reconnect visit", "Restore the service"): 5,
}


def _flow_visit_task_rows(name: str) -> list[dict[str, Any]]:
    """One template's task rows, with a money check where the step declares one."""
    rows: list[dict[str, Any]] = []
    for title in FLOW_VISIT_TASKS.get(name, ()):
        row: dict[str, Any] = {"title": title}
        minutes = FLOW_VISIT_MONEY_STEPS.get((name, title))
        if minutes is not None:
            row["money_fresh_minutes"] = minutes
        rows.append(row)
    return rows


def _seed_flow_visit_templates(actor: Any) -> int:
    """The six field visits a customer flow raises (the sixth, the cut, `DEF-CUS-9631`), each typed — `DEF-WRK-9626`.

    The exchange template's posture, row for row: `sequence` 0 (so no build's
    step 6 proposes them — `DEF-WRK-3573`), through `templates_svc` (Work's own
    door), published once, idempotent on `(service, name)`, tagged as sample.
    The job type is looked up by its seeded CODE; a tenant without that row gets
    the template untyped rather than none.

    ⚠ **ONE SET PER METERED SERVICE, NOT ONE FOR THE BACKBONE (`DEF-WRK-9784`,
    2026-10-06).** Until then this seeded `plan.primary` alone, so on a utility
    selling electric, gas and water every visit template was WATER's: a move-in
    booking an *Opening read* on an electric meter was offered water's, Work
    refused it as the wrong service, and the move-in completed with no work
    order. A visit is done TO a meter, so the answer is per service —
    `CR-062` C3's split between `plan.metered` and `plan.primary`, and this is
    the per-service side of it. The primary is `metered[0]` and is seeded
    first, so its template numbers are the ones it always had.
    """
    from apps.work import models as work_models

    tenant_id = _tenant_id()
    plan = estate()
    types = dict(
        work_models.WorkOrderType.objects.filter(
            tenant_id=tenant_id, code__in={type_code for _, type_code in FLOW_VISIT_TEMPLATES}
        ).values_list("code", "id")
    )
    written = 0
    for metered in plan.metered:
        written += _seed_flow_visit_templates_for(actor, tenant_id, metered.code, types)
    return written


def _seed_flow_visit_templates_for(
    actor: Any, tenant_id: Any, code: str, types: dict[str, Any]
) -> int:
    """`_seed_flow_visit_templates` for ONE metered service."""
    from apps.work import models as work_models
    from apps.work import templates_svc
    from apps.work.models import WorkOrderTemplateDetail

    service_id = seams.service_row_id(code)
    if service_id is None:
        return 0
    written = 0
    for name, type_code in FLOW_VISIT_TEMPLATES:
        row = work_tables.WorkOrderTemplate.objects.filter(
            tenant_id=tenant_id, service_id=service_id, name=name
        ).first()
        if row is None:
            payload: dict[str, Any] = {
                "name": name,
                "service": code,
                "scope": work_tables.SCOPE_ASSET,
                "sequence": 0,
                "is_gate": False,
            }
            if types.get(type_code):
                payload["type_id"] = str(types[type_code])
            header = templates_svc.create_draft(actor, payload)
            template_id, version = header["id"], int(header["version"] or 0)
            written += 1
        else:
            template_id, version = str(row.id), int(row.version or 0)
        if not WorkOrderTemplateDetail.objects.filter(
            tenant_id=tenant_id, template_id=template_id
        ).exists():
            # `DEF-WRK-10652` (PO 2026-10-29, ruling 4A) — the sample disconnect
            # and reconnect visits send the customer NO visit message: the
            # disconnect notices speak for them. Seed data naming its own rows;
            # at run time only the template's switch is read, never a type.
            templates_svc.replace_collection(
                actor,
                template_id,
                "details",
                {
                    "send_customer_visit_messages": type_code != "DISCONNECT_RECONNECT",
                    # FB-028 (PO 2026-10-31) — a template with a payment check
                    # carries the Reconnect limit, the PO's $25.00 by default.
                    **(
                        {"reconnect_limit": "25.0000"}
                        if any(n == name for n, _t in FLOW_VISIT_MONEY_STEPS)
                        else {}
                    ),
                },
            )
        # Only on a template that has not been published yet: a published one
        # changes through a new version, which is the utility's act.
        if version < 1 and not work_models.WorkOrderTemplateTask.objects.filter(
            tenant_id=tenant_id, template_id=template_id
        ).exists():
            templates_svc.replace_collection(actor, template_id, "tasks", _flow_visit_task_rows(name))
        if version < 1:
            templates_svc.publish(actor, template_id, change_note="First publish")
        _tag(
            work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=tenant_id, pk=template_id, is_sample=False
            )
        )
    return written


def _seed_w6_w7_seats(actor: Any) -> int:
    """The new premises and units the eight builds and the fourteen W7 rows need.

    Through `create_premises` / `create_unit` — the S14 and S16 wizards' own
    calls — so every rule a clerk meets applies here too. Idempotent
    (BR-TEN-063): a premises already on file by address is not re-created, and a
    unit already on file by `unit_no` is not re-added.

    ⚠ **THESE SEATS JOIN NO ROUTE AND NO BILL RUN**, which is the same
    load-bearing fact `_seed_cr030_estate` states one screen up: this runs AFTER
    `_ensure_cycle_and_route`, so the PO's ready-to-run July batch keeps exactly
    the rows it had and gains no phantom missing-read.

    ⚠ **A BUILD'S UNIT CARRIES NO SERVICE POINT AND NO PLAN; A W7 SEAT CARRIES
    BOTH, AND THE DIFFERENCE IS THE PRODUCT'S.** §5.4.9: *"A NEW CONNECT ENDS
    WITH UNITS VACANT, SERVICE OFF AND NO ACCOUNT."* A build's unit has no
    account, so BR-MET-040's *"an active account on an unpriced unit is an
    unbillable bill waiting to happen"* has nothing to refuse. Every W7 seat DOES
    take an account, so it gets the plan and the service points the account needs.
    """
    tenant_id = _tenant_id()
    by_address = _seat_premises_by_address()
    existing_unit_nos = set(
        models.Unit.objects.filter(tenant_id=tenant_id).values_list("unit_no", flat=True)
    )
    areas_available = _seeded_area_codes()
    # CR-039 wave E task 23 · BR-MET-139 — once for the block, not per row.
    seat_state = seams.tenant_state()
    enabled = set(seams.enabled_service_codes())
    account_services = [code for code in fixture.CR030_A10432_SERVICES if code in enabled]
    plan_id = _cr030_plan_id()
    written = 0

    def _unit_payload(label: str, unit_no: str, entry: dict[str, Any], *, for_account: bool):
        payload: dict[str, Any] = {
            "label": label,
            "unit_no": unit_no,
            "unit_type": entry.get("unit_type", "residential"),
            "services": list(account_services) if for_account else [],
        }
        if for_account and plan_id:
            payload["plan"] = {
                "plan_id": plan_id,
                "effective_from": fixture.PERIODS[0]["start"].isoformat(),
            }
        return payload

    for entry, for_account in (
        *((seat, False) for seat in W6_SEATS),
        *((seat, True) for seat in W7_SEATS),
    ):
        address = entry["address_line"]
        premises = by_address.get(address)
        wanted = [(label, unit_no, for_account) for label, unit_no in entry.get("units", ())] + [
            (label, unit_no, True) for label, unit_no in entry.get("account_units", ())
        ]
        if premises is None:
            if entry.get("existing"):
                logger.info(
                    "sample data (CR-030 W6/W7): %s is declared as an EXISTING estate premises "
                    "and is not on file, so the rows standing on it are skipped",
                    address,
                )
                continue
            payload: dict[str, Any] = {
                "address_line": address,
                "city": fixture.CITY,
                # CR-039 wave E task 23 · BR-MET-139 — as above.
                "state": seat_state,
                "postal_code": fixture.POSTAL,
                "premises_type": entry.get("premises_type", "single_family"),
                "owner_manager": entry.get("owner_manager"),
                "services_available": list(account_services),
                "status": "active",
                # CR-039 wave C task 11 — same reason as the block above: these
                # units are on the residential plan and that plan surcharges.
                "inside_city_limits": fixture.default_jurisdiction(),
                "units": [
                    _unit_payload(label, unit_no, entry, for_account=takes_account)
                    for label, unit_no, takes_account in wanted
                    if unit_no not in existing_unit_nos
                ],
            }
            # DEF-256 — every sample premises lands in one of the tenant's own
            # districts, deterministically on the address (never invented).
            area_code = _area_code_for(address, areas_available) or _cr030_area_for(
                address, areas_available
            )
            if area_code is not None:
                payload["area_code"] = area_code
            payload["owner_id"] = _sample_owner_id(actor, payload.get("owner_manager"))
            result = services.create_premises(actor, payload)
            written += 1 + len(result.get("units", ()))
            existing_unit_nos.update(unit_no for _l, unit_no, _a in wanted)
            by_address[address] = models.Premises.objects.get(tenant_id=tenant_id, pk=result["id"])
            continue
        for label, unit_no, takes_account in wanted:
            if unit_no in existing_unit_nos:
                continue
            services.create_unit(
                actor,
                {
                    "premises_id": str(premises.id),
                    **_unit_payload(label, unit_no, entry, for_account=takes_account),
                },
            )
            existing_unit_nos.add(unit_no)
            written += 1

    premises_qs = models.Premises.objects.filter(
        tenant_id=tenant_id,
        address_line__in=[entry["address_line"] for entry in (*W6_SEATS, *W7_SEATS)],
    )
    _tag(premises_qs.filter(is_sample=False))
    unit_qs = models.Unit.objects.filter(tenant_id=tenant_id, premises__in=premises_qs)
    _tag(unit_qs.filter(is_sample=False))
    _tag(models.ServicePoint.objects.filter(tenant_id=tenant_id, unit__in=unit_qs, is_sample=False))
    return written


def _seed_work_order_template_starters(actor: Any) -> int:
    """**Task 6.3, as BR-MET-109 reframed it — READY-TO-USE STARTERS**, and
    since CR-070 wave E they are PUBLISHED BUNDLES rather than inert rows.

    Not a policy: `is_sample = True` on every row, so `--remove` sweeps them
    like any other sample row, and the utility edits, renames, deletes or
    replaces them in the Work order section.

    ⚠ **THE DEBT THIS FUNCTION RECORDED FOR ELEVEN DAYS IS PAID (`US-WRK-019`,
    `E4`).** Its own words, from 2026-08-25 until 2026-09-05, were *"WRITTEN
    THROUGH THE MODEL BECAUSE THERE IS NO SERVICE TO WRITE IT THROUGH"* and
    *"a `create_work_order_template` service is OWED"*. There is one now —
    `apps/work/templates_svc.py`, built by wave D — and this writes through it:
    `create_draft` for the header, `replace_collection` for the `wot_details`
    row every template needs, and **`publish`, which is the ONE write**
    (`BR-WRK-011`) and the only thing that allocates `ST-{0000}` and sets
    version 1. The sentence in the module trailer went with it, because a
    stated absence must go in the commit that makes it untrue (hard-won law 1).

    ⚠ **WHY A SEEDED STARTER IS PUBLISHED AND NOT LEFT A DRAFT.** Wave D's own
    stamp recorded that the 24 rows read *Draft* — honestly, because `version`
    defaults to 0 and 0 is a draft. But `BR-WRK-016` proposes from PUBLISHED
    templates only, so a drafted starter is a starter New Connect step 6 will
    never offer, and the whole point of seeding them (`BR-MET-109`: *"ready to
    use"*) is that the utility's first build proposes its jobs. They are
    published as v1 with the change note *First publish*.

    ⚠ **IDEMPOTENT, AND THE ORDER OF THE THREE CALLS IS WHAT MAKES IT SO**
    (`BR-TEN-063`). The identity is still `(service, sequence)` — the seeded
    row's own natural key — so a tenant that RENAMED a starter keeps its name
    and a replay writes nothing. The `wot_details` row is written ONLY when it
    is missing, because `replace_collection` moves the header's `updated_at`
    and `publish` reads that timestamp to tell *"the bundle changed"* from
    *"somebody pressed the button twice"*: writing it unconditionally would
    make every replay publish a v2 that is identical to v1.

    ⚠ **AND A TENANT SEEDED BEFORE WAVE E IS REPAIRED BY THE SAME PATH.** Those
    tenants hold 24 rows at version 0 with no bundle; the branch below finds
    them, gives each a `wot_details` row and publishes it. No migration and no
    backfill script: the seeder IS the repair, and running it is something an
    operator already does.

    ⚠ **THE DIRECTION OF THE IMPORT.** This is metering calling `apps/work`,
    and it is the same direction `apps/tenancy/services.py` already takes to
    seed Work's reference lists. It is a PROVISIONING call rather than a
    runtime ring: the header still lands through metering's own
    `create_work_order_template` (Work's seam calls it by name), so no module
    writes another's table and `G78` has nothing to see. The import is local to
    the function so that importing this module never pulls Work in.
    """
    from apps.work import templates_svc
    from apps.work.models import WorkOrderTemplateDetail

    tenant_id = _tenant_id()
    enabled = set(seams.enabled_service_codes())
    written = 0
    published = 0
    skipped: list[str] = []
    seeded_ids: list[Any] = []
    for code, rows in W6_TEMPLATE_STARTERS:
        if not rows:
            continue
        service_id = seams.service_row_id(code) if code in enabled else None
        if service_id is None:
            skipped.append(code)
            continue
        # The clerk-facing sentence for a service whose §8.1 gate names none of
        # its own steps. `None` for every gated service, so the column says
        # something only where there is something to say.
        no_gate_reason = W6_NO_GATE_REASON.get(code)
        for sequence, (name, scope, is_gate) in enumerate(rows, start=1):
            row = work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=tenant_id, service_id=service_id, sequence=sequence
            ).first()
            if row is None:
                header = templates_svc.create_draft(
                    actor,
                    {
                        "name": name,
                        "service": code,
                        "scope": scope,
                        "sequence": sequence,
                        "is_gate": is_gate,
                        "no_gate_reason": no_gate_reason,
                    },
                )
                template_id = header["id"]
                version = int(header["version"] or 0)
                written += 1
            else:
                template_id = str(row.id)
                version = int(row.version or 0)
            seeded_ids.append(template_id)
            if not WorkOrderTemplateDetail.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).exists():
                # Four ticks on, which is what `Work-014` draws. A starter with
                # no `wot_details` row would show a technician nothing.
                templates_svc.replace_collection(actor, template_id, "details", {})
            if version < 1:
                templates_svc.publish(actor, template_id, change_note="First publish")
                published += 1
    # BR-TEN-057 — the tag is written by this module's own service and by
    # nobody else. `templates_svc` cannot set it and must not be able to: a
    # utility marking its own template as sample data would make `--remove`
    # take work it authored.
    #
    # ⚠ **THE ROWS THIS RUN TOUCHED, BY ID — NEVER A `filter(is_sample=False)`
    # SWEEP.** A sweep would tag a template the UTILITY authored, and the tag is
    # what `--remove` deletes by; the old `get_or_create(defaults=…)` form only
    # ever marked rows it had created, and this keeps that property explicit
    # rather than as a side effect of the call it replaced.
    if seeded_ids:
        _tag(
            work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=tenant_id, pk__in=seeded_ids, is_sample=False
            )
        )
    if skipped:
        logger.info(
            "sample data (CR-030 W6 task 6.3): no starter templates for %s — the tenant does "
            "not sell them (BR-MET-003). Enabling a service is Settings > Services",
            ", ".join(skipped),
        )
    if published:
        logger.info(
            "sample data (CR-070 wave E, US-WRK-019): %s starter template(s) published as v1 "
            "through apps/work/templates_svc.publish — each has an ST- number and can be "
            "proposed by New Connect step 6 (BR-WRK-016)",
            published,
        )
    for code, reason in W6_UNGATED_STARTERS.items():
        logger.info("sample data (CR-030 W6 task 6.3): %s carries NO gate row — %s", code, reason)
    return written


def _seed_w6_common_area(actor: Any) -> int:
    """**DEF-709 — the estate's ONE common-area unit, and the only one there is.**

    `BR-MET-116` (PO 2026-08-25, closing OQ-373) states the manifest this row
    completes: *"the drawn manifest's `Units 26` = 25 apartments + 1 common
    area"*, and the reason it must exist at all — *"if there is common area you
    can add that in premises"*. `BR-MET-101` is what makes it a UNIT rather than
    a table: *a common area is a unit with a FLAG*.

    ⚠ **THIS UNIT CARRIES A PLAN, AND EVERY OTHER W6 BUILD SEAT DOES NOT.**
    That is not an inconsistency, it is `BR-MET-116`'s closing paragraph:
    *"the owner's master account CANNOT be created before the common area has a
    plan"* — `create_master_account` creates the account ACTIVE (BR-CUS-068)
    and `BR-MET-040` refuses to activate an account on an unpriced unit. A
    build's ordinary unit takes no account, so it needs no plan; this one is
    the anchor of the developer's master account (`BR-CUS-083`), so it does.

    ⚠ **AND IT CARRIES SERVICE POINTS FOR THE SAME REASON.** Without them
    `create_master_account` succeeds with a `unit_has_no_service_points`
    warning and opens no service agreement, so the master account would render
    with no service chips and cover nothing. The two services are
    `BR-MET-101`'s own — hallway lighting (electric) and shared irrigation
    (water) — intersected with what the tenant sells (BR-MET-003).

    ⚠ **IT JOINS NO ROUTE AND NO BILL RUN.** Same load-bearing fact as its
    neighbours: `500 Main St` is an estate premises, seeded after
    `_ensure_cycle_and_route`, so `cascade_premises_routes_to_unit` finds no
    membership to inherit and the PO's ready-to-run July batch is untouched.

    Idempotent (BR-TEN-063): the unit is looked up by `unit_no` first, so a
    replay writes nothing.
    """
    tenant_id = _tenant_id()
    unit_no = fixture.CR030_COMMON_AREA_UNIT_NO
    if models.Unit.objects.filter(tenant_id=tenant_id, unit_no=unit_no).exists():
        return 0
    premises = models.Premises.objects.filter(
        tenant_id=tenant_id, address_line=fixture.CR030_COMMON_AREA_ADDRESS
    ).first()
    if premises is None:
        # BR-TEN-060's posture: an unloaded thing is a NAMED line, never a
        # silent skip. The estate block above plants this premises; if it did
        # not run, the common area has nowhere to stand.
        logger.info(
            "sample data (DEF-709): %s is not on file, so the estate's common area and the "
            "master account that anchors on it are not seeded",
            fixture.CR030_COMMON_AREA_ADDRESS,
        )
        return 0
    enabled = set(seams.enabled_service_codes())
    services_for_area = [code for code in fixture.CR030_COMMON_AREA_SERVICES if code in enabled]
    if not services_for_area:
        logger.info(
            "sample data (DEF-709): the tenant sells neither %s, so the common area takes no "
            "service point (BR-MET-003) and its master account will cover no service",
            " nor ".join(fixture.CR030_COMMON_AREA_SERVICES),
        )
    payload: dict[str, Any] = {
        "premises_id": str(premises.id),
        "label": fixture.CR030_COMMON_AREA_LABEL,
        "unit_no": unit_no,
        # BR-MET-084's own seeded code (`SEED_UNIT_TYPES`), not new vocabulary.
        "unit_type": "common_area",
        # BR-MET-101's flag — the whole point of the row.
        "is_common_area": True,
        "services": services_for_area,
    }
    plan_id = _cr030_plan_id()
    if plan_id:
        payload["plan"] = {
            "plan_id": plan_id,
            "effective_from": fixture.PERIODS[0]["start"].isoformat(),
        }
    else:
        # Stated, not swallowed: with no plan BR-MET-040 refuses the master
        # account's activation and DEF-709 stays open on this tenant.
        logger.info(
            "sample data (DEF-709): no sample rate plan is on file, so the common area is "
            "unpriced and BR-MET-040 will refuse the master account (BR-MET-116)"
        )
    services.create_unit(actor, payload)
    unit_qs = models.Unit.objects.filter(tenant_id=tenant_id, unit_no=unit_no)
    _tag(unit_qs.filter(is_sample=False))
    _tag(models.ServicePoint.objects.filter(tenant_id=tenant_id, unit__in=unit_qs, is_sample=False))
    return 1


def _w6_units_for(premises: Any, wanted: int | None, seat: dict[str, Any]) -> list[Any]:
    """The BUILD's own seats at this premises, in `unit_no` order.

    ⚠ **THE ESTATE'S UNITS AT `500 Main St` ARE NOT THE BUILD'S.** The seat entry
    names the build's units explicitly, so `Ridge Coffee Co.`'s four suites and
    the `+3` overflow unit never join `CON-26-0117` and the drawn `UNITS 25`
    cannot silently become 30.
    """
    if wanted is None:
        return []
    unit_nos = [unit_no for _label, unit_no in seat.get("units", ())]
    unit_nos += list(seat.get("unit_nos", ()))
    rows = list(
        models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises=premises, unit_no__in=unit_nos
        ).order_by("unit_no")
    )
    return rows[:wanted]


def _normal_priority_id(tenant_id: Any) -> str | None:
    """The tenant's `NORMAL` work priority, or None where it has none (then the
    raise carries no priority, exactly as before). Work's reference row, read."""
    from apps.work import models as work_models

    row = work_models.WorkPriority.objects.filter(tenant_id=tenant_id, code__iexact="NORMAL").first()
    return str(row.id) if row is not None else None


def _w6_template_of(service_code: str, name: str) -> dict[str, Any]:
    """`DEF-WRK-9676` — the PUBLISHED starter template a build job is named
    after (`W6_TEMPLATE_STARTERS`, seeded earlier in the same run), as the two
    keys `create_work_order` reads. `is_gate` is passed explicitly so linking
    the template moves NO gate: the demo's gates are the ones it had.

    Empty when the tenant has no such published template (it renamed or
    retired the starter): the job is then raised by name, as before.
    """
    row = (
        work_tables.WorkOrderTemplate.objects.filter(
            tenant_id=_tenant_id(),
            service__code=service_code,
            name=name,
            active=True,
            version__gte=1,
        )
        .order_by("sequence", "id")
        .first()
    )
    if row is None:
        return {}
    return {"template_id": str(row.id), "is_gate": False}


def _seed_w6_connections(actor: Any) -> int:
    """**Task 6.15 — B18 §5.4.8's eight builds, their services and their orders.**

    Every row goes through `apps/metering/connections.py`'s own doors:
    `create_connection` → `add_connection_service` → `create_work_order` →
    `submit_field_result` / `accept_field_result` (BR-MET-110's three steps) →
    `transition_service` → `submit_connection` → `set_waiting_on` /
    `hold_connection`. **Nothing writes `connections.state`** —
    `refresh_connection_state` is its only writer and every door above calls it.

    ⚠ **ONE COLUMN IS STAMPED DIRECTLY AFTERWARDS AND IT IS A DATE.**
    `submitted_at` is written by `_stamp` from the wall clock, and `OLDEST · 19
    days` is a figure the drawing took on a day that has passed — so the seed
    back-dates it (see the block header for why an offset and not a literal).
    There is no service that takes a submission date, it is not a state, and it
    is the only column here that is written outside a door.

    Idempotent (BR-TEN-063): a build already on file under its drawn number is
    skipped whole, so a replay writes nothing and re-dates nothing.
    """
    tenant_id = _tenant_id()
    enabled = set(seams.enabled_service_codes())
    if not enabled:
        logger.info(
            "sample data (CR-030 W6 task 6.15): the tenant sells no service, so no build can "
            "take one (BR-MET-003) and the eight New Connect rows are not seeded"
        )
        return 0
    anchor = w6_anchor_on()
    now = django_timezone.now()
    seats = {entry["address_line"]: entry for entry in W6_SEATS}
    by_address = _seat_premises_by_address()
    written = 0
    # ⚠ **SEEDED IN ASCENDING SEQUENCE, NOT IN THE ORDER THEY ARE DECLARED, AND
    # THE DIFFERENCE IS A REAL BUG THIS CAUGHT.** `W6_CONNECTIONS` is written in
    # B18 §5.4.8's own order, which is TARGET-DATE order (*"Sorted by target
    # date, soonest first"*) — and in that order the drawn numbers run
    # 110 · 119 · 121 · 126 · **117** · 128 · **124** · **122**. A number series
    # moves FORWARD ONLY (BR-TEN-035), so seeding in the declared order asks the
    # counter to go back to 117 after it has reached 126, the move is refused,
    # and the build silently takes `CON-26-0127` instead. Measured, not feared:
    # the first run of this seeder produced `CON-26-0127`, `CON-26-0129` and
    # `CON-26-0130` for the three rows whose numbers run backwards.
    for row in sorted(W6_CONNECTIONS, key=lambda entry: entry["sequence"]):
        if work_tables.Connection.objects.filter(
            tenant_id=tenant_id, connection_no=row["connection_no"]
        ).exists():
            continue
        premises = by_address.get(row["address_line"])
        if premises is None:
            logger.info(
                "sample data (CR-030 W6 task 6.15): %s has no premises at %s and is not seeded",
                row["connection_no"],
                row["address_line"],
            )
            continue
        seat = seats.get(row["address_line"], {})
        # THE DRAWN NUMBER, THROUGH THE PRODUCT'S OWN SERIES. `CON-26-0110` is
        # `CON-{YY}-{0000}` standing at 110, so the counter is moved forward to
        # it — BR-TEN-035 forward-only, through tenancy's own service via the
        # seam (`advance_number_series`, DEF-577's repair path) — and
        # `create_connection` then allocates it in the ordinary way. The eight
        # rows are declared in ascending sequence for exactly that reason.
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
            # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
            # (this block runs inside tenancy's per-module `atomic`), so without it the
            # work already done is lost at COMMIT. NOT tidiness — do not remove.
            with transaction.atomic():
                seams.advance_number_series(actor, "connection", row["sequence"])
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W6 task 6.15): the connection series could not be moved to "
                "%s (%s: %s), so %s will carry whatever number the series hands out",
                row["sequence"],
                type(exc).__name__,
                exc,
                row["connection_no"],
            )
        created = w6.create_connection(
            actor,
            {
                "premises_id": str(premises.id),
                "target_activation": anchor + timedelta(days=row["target_offset"]),
                "is_sample": True,
            },
        )
        connection = work_tables.Connection.objects.get(tenant_id=tenant_id, pk=created["id"])
        written += 1

        # ── step 4 · the services, at their units or at the premise ──────────
        service_rows: dict[str, list[dict[str, Any]]] = {}
        for code, at_units in row["services"].items():
            if code not in enabled:
                continue
            units = _w6_units_for(premises, at_units, seat)
            if at_units is not None and len(units) < at_units:
                logger.info(
                    "sample data (CR-030 W6 task 6.15): %s wanted %s at %s seat(s) and found "
                    "%s, so its UNITS figure is smaller than B18 §5.4.8 draws",
                    row["connection_no"],
                    code,
                    at_units,
                    len(units),
                )
            made = [
                w6.add_connection_service(
                    actor,
                    connection.id,
                    service_code=code,
                    unit_id=None if unit is None else unit.id,
                )
                for unit in (units or [None])
            ]
            service_rows[code] = made
            written += len(made)

        # ── step 5 · the work plan. DECLARED, never batched (BR-MET-109) ─────
        for order_type, code, scope, done in row["orders"]:
            if code not in enabled:
                continue
            unit_id = None
            if scope == work_tables.SCOPE_UNIT:
                units = _w6_units_for(premises, row["services"].get(code), seat)
                unit_id = str(units[0].id) if units else None
            order = w6.create_work_order(
                actor,
                connection.id,
                {
                    "type": order_type,
                    "service": code,
                    "scope": scope,
                    "unit_id": unit_id,
                    # `DEF-WRK-9676` (`CR-168-BRC10` round 8): the build's job
                    # is raised FROM its starter template — the one the
                    # commit's own raise would stamp (`BR-WRK-008`) — so it
                    # carries that template's checklist and skill, and the
                    # assign advice has something to say. Before this, 35 of
                    # 39 seeded orders had no template at all.
                    **_w6_template_of(code, order_type),
                    # `DEF-WRK-9571` (`CR-168-BRC10` P0.1): these starter
                    # names are not catalogue job types, so no type default
                    # applies and every demo order was raised with NO
                    # priority — the Orders list's Priority filter then read
                    # as broken. The demo raises at Normal, the default
                    # target the PO ruled for an undated job (2026-10-04).
                    "priority_id": _normal_priority_id(connection.tenant_id),
                    # `DEF-WRK-9627` (`CR-168-BRC10` §F): RAISED BY read *—* on
                    # all 39 seeded build jobs. They are the New Connect's own
                    # work plan, so they say so (`BR-WRK-024`), and carry the
                    # build's number the way the commit's raise does.
                    "source": work_tables.SOURCE_NEW_CONNECT,
                    "source_ref": connection.connection_no,
                },
            )
            written += 1
            if not done:
                continue
            # BR-MET-110's three steps, in order: the field sends its data, a
            # PERSON accepts it, and only then may the data activate anything.
            # ⚠ `CR-168-BRC10` P1.34 (ruling 18): the public close admits only
            # the technician the job was given to, and these builds' orders were
            # finished before the demo had any technician. This is the demo's
            # PAST being written, not a door, so it records the field result
            # through the guard-free private half — see its docstring.
            w6._record_field_result(
                actor,
                work_tables.WorkOrder.objects.get(pk=order["id"]),
                field_data={"seeded_by": "CR-030 W6 task 6.15", "step": order_type},
                outcome=work_tables.OUTCOME_PASSED,
            )
            try:
                # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
                # (this block runs inside tenancy's per-module `atomic`), so without it the
                # work already done is lost at COMMIT. NOT tidiness — do not remove.
                with transaction.atomic():
                    w6.accept_field_result(actor, order["id"])
            except Exception as exc:  # noqa: BLE001 — named, never swallowed
                logger.info(
                    "sample data (CR-030 W6 task 6.15): %s could not be ACCEPTED (%s: %s), so "
                    "it stays in BR-MET-110's review queue with `accepted_by` NULL",
                    order["order_no"],
                    type(exc).__name__,
                    exc,
                )

        # ── the per-service states the drawn STATE cell derives from ─────────
        for code in row["activated"]:
            for made in service_rows.get(code, ()):
                w6.transition_service(actor, made["id"], work_tables.SVC_ACTIVATED)
        for code in row["in_progress"]:
            for made in service_rows.get(code, ()):
                w6.transition_service(actor, made["id"], work_tables.SVC_IN_PROGRESS)

        # ── step 8 · `Review & request`, then the two INDEPENDENT axes ───────
        w6.submit_connection(actor, connection.id)
        if row.get("held"):
            # `hold_connection` writes `waiting_on` itself — §5.4.9 fact 1a:
            # only `CON-26-0119` is both held AND waiting, and the other two
            # waiting rows are not held.
            w6.hold_connection(actor, connection.id, reason=row["waiting_on"])
        elif row.get("waiting_on"):
            w6.set_waiting_on(actor, connection.id, waiting_on=row["waiting_on"])

        # THE ONE BACK-DATED COLUMN — see the docstring.
        work_tables.Connection.objects.filter(tenant_id=tenant_id, pk=connection.id).update(
            submitted_at=now - timedelta(days=row["open_days"])
        )
        connection.refresh_from_db()
        w6.refresh_connection_state(connection)

    missing = w6_unseeded_services()
    if missing:
        logger.info(
            "sample data (CR-030 W6 task 6.15): the eight builds asked for services this tenant "
            "has not enabled and they are NOT seeded — %s. The ORDERS fractions and the "
            "SERVICES badges are smaller than B18 §5.4.8 draws; UNITS and STATE are unaffected",
            ", ".join(missing),
        )
    for name, reason in W6_ABSENCES.items():
        logger.info("sample data (CR-030 W6 task 6.15): %s is NOT seeded — %s", name, reason)
    return written


def w6_connection_report() -> list[dict[str, Any]]:
    """Every drawn build and what it became on THIS tree — data, not a log line,
    so `tests/test_w6_w7_seed.py` asserts dispositions instead of re-deriving
    them (the `w5_move_fixture_report` posture)."""
    tenant_id = _tenant_id()
    anchor = w6_anchor_on()
    out: list[dict[str, Any]] = []
    for row in W6_CONNECTIONS:
        found = work_tables.Connection.objects.filter(
            tenant_id=tenant_id, connection_no=row["connection_no"]
        ).first()
        out.append(
            {
                "connection_no": row["connection_no"],
                "address_line": row["address_line"],
                "drawn_units": row["units"],
                "drawn_orders": len(row["orders"]),
                "drawn_orders_done": sum(1 for order in row["orders"] if order[3]),
                "drawn_state": row["state"],
                "drawn_target": row["drawn_target"].isoformat(),
                "drawn_request_no": row.get("drawn_request_no"),
                "planted": found is not None,
                "seeded_state": None if found is None else w6.connection_state(found),
                "seeded_orders": None if found is None else list(w6.order_progress(found)),
                "seeded_target": (
                    None
                    if found is None or found.target_activation is None
                    else found.target_activation.isoformat()
                ),
                "waiting_on": None if found is None else found.waiting_on,
                # What the drawn date became once anchored on the tenant's own
                # today (see the block header) — so a reader can check the
                # offset instead of wondering why the two dates differ.
                "target_offset": row["target_offset"],
                "expected_target": (anchor + timedelta(days=row["target_offset"])).isoformat(),
                # Every W6 absence rides the report; see `W6_ABSENCES`.
                "request_link": None,
            }
        )
    return out


# ══════════════════════════════════════════════════════════════════════════
# The reads (the SECOND seam)
# ══════════════════════════════════════════════════════════════════════════


def _meter_for(
    unit_index: int, period_key: str, service: str = "water", replacement: bool = True
) -> str:
    """Which SERIAL this unit's read lands on for this period.

    Case 3 of the spec — a meter replaced mid-history — is the only reason this
    is a function: unit 11's June read is on the old register and its July and
    August reads are on the new one, so a chain crosses two serials.

    CR-039 A2: the serial is the BACKBONE's (`W-5011` on a water tenant,
    `E-5011` on an electric one) — resolved from `core.sample_fixture` so this
    function and `apps/assets/sample_data` cannot disagree about a number.
    """
    # ⚠ **CR-062 C8 — `replacement` IS THE CALLER'S FACT AND NOT AN ORM READ.**
    # Only the FIRST metered service plants a swap (judgment 4), so only its
    # chain crosses two serials; `meter_plan(..., replacement=False)` plants no
    # `*-9011` for any later service, and naming one here would stage a read for
    # a meter that does not exist. The flag is threaded from the blocks, which
    # already hold the plan, rather than resolved here: this is a PURE row
    # builder called from tests with no tenant context, and reaching for
    # `estate()` inside it made it need a database.
    if unit_index == fixture.CASE_METER_REPLACED and period_key != "june" and replacement:
        return fixture.replacement_meter_no(service)
    return fixture.meter_no(service, unit_index)


# ── PO 2026-09-07 · THE WALK IS SPREAD, AND THE DIAL IS NOT ALWAYS ONE ──────
#
# Two of the three parts of the confirmed reading model land in this file (the
# third, the consumption curve, is `core.sample_fixture._shaped`):
#
#   (a) **A PERIOD'S WALK IS FIVE DAYS AND FIVE BATCHES, NOT ONE.** The estate
#       is laid out on five streets and `fixture.READ_ROUTES` makes each one a
#       route with its own walk day. Every route hands in its OWN sheet — one
#       crew, one round, one file — which is what a utility of this size does
#       and what makes `days_since_prior` mean something.
#   (b) **AN ELECTRIC METER CARRIES THE REGISTERS ITS OWN TARIFF NEEDS.** A
#       time-of-use customer's file has three window rows that sum to the total;
#       a demand customer's has the month's PEAK beside the total; a solar
#       household's has the grid-push register `BR-AST-029` requires. Which
#       customer is which is `fixture.electric_tariff_shape`'s answer and this
#       module states none of it.
#
# ⚠ **THE DEMAND ROW IS A MAXIMUM AND NOT A COUNTER (`BR-MET-051`).** It is
# written as the month's peak VALUE, not as a running total — `DEF-797` is what
# a running total there costs: **$154.00 billed where the correct charge was
# $4,532.00**, on a live product. `_register_value` refuses to accumulate it.


#: Where each register's dial STARTS, before a single month is added:
#: `(offset, per-unit step)`. Authorship, exactly as the `total` line always
#: was — an opening baseline prices nothing, it is the number a dial happened to
#: be standing at. The steps differ per channel so two registers on one meter
#: never read the same number, which would make a screenshot ambiguous.
_REGISTER_BASELINE: dict[str, tuple[int, int]] = {
    fixture.CHANNEL_TOTAL: (1000, 37),
    fixture.CHANNEL_TOU_ON: (400, 17),
    fixture.CHANNEL_TOU_MID: (220, 11),
    fixture.CHANNEL_TOU_OFF: (180, 9),
    fixture.CHANNEL_EXPORT: (90, 7),
}


def _walk_offset(unit_index: int) -> int:
    """Which of the five walk routes this unit is read on."""
    for unit in fixture.units_flat():
        if unit["unit_index"] == unit_index:
            return fixture.walk_route_index(unit["street"])
    return 0


def _read_on(period: dict[str, Any], walk_offset: int) -> Any:
    """The day THIS route walks in THIS period. Offset 0 is the period's own
    date, unshifted, so route 1 and everything pinned to it do not move."""
    if period["key"] == "opening":
        return fixture.opening_read_on(walk_offset)
    return fixture.route_read_on(period["key"], walk_offset)


def _walk_dates(period: dict[str, Any]) -> list[Any]:
    """Every date this period's walk touches — five, one per route.

    ⚠ **EVERY `read_at__date=period["read_on"]` IN THIS FILE HAD TO BECOME THIS
    LIST**, and a missed one is not a crash: it is a replay guard that stops
    matching, a coverage check that reports meters missing when they are read,
    and a tag that leaves four fifths of a walk untagged and therefore
    unremovable (`BR-TEN-061`). They are enumerated rather than left to be
    found — `_period_already_seeded`, `_post_periods`'s tag, `_assert_read_
    coverage` and `next_cycle_read_coverage`.
    """
    return [_read_on(period, route["walk_offset"]) for route in fixture.READ_ROUTES]


def _units_on_route(walk_offset: int) -> tuple[dict[str, Any], ...]:
    """The estate's units this route walks, in fixture order."""
    return tuple(
        unit
        for unit in fixture.units_flat()
        if fixture.walk_route_index(unit["street"]) == walk_offset
    )


def _opening_rows(
    service: str = "water", replacement: bool = True, walk_offset: int = 0
) -> list[dict[str, Any]]:
    """The register baseline — see `fixture.OPENING_READ_ON`.

    A meter's FIRST read measures nothing: there is no prior value to subtract,
    so metering emits `consumption = NULL`, which is correct and which the bill
    run correctly reports as "no usable read". Every real utility has this
    problem exactly once per meter and solves it the same way — an opening read
    taken when the meter went in. The fixture takes one, dated before the first
    billed period, and it is never billed.

    ⚠ **THE OPENING BATCH CARRIES NO `demand` ROW, AND THAT IS THE RULE RATHER
    THAN AN OMISSION.** A demand register is a MAXIMUM read at the cycle read
    (`BR-MET-051`); it has no baseline to be measured from, so an opening peak
    would be a reading that means nothing. Every COUNTER — the total, the three
    time-of-use windows, the export dial — does need one, and gets one.
    """
    rows: list[dict[str, Any]] = []
    for unit in _units_on_route(walk_offset):
        index = unit["unit_index"]
        for channel in fixture.read_channels(index, service):
            if channel == fixture.CHANNEL_DEMAND:
                continue
            rows.append(
                {
                    "meter_id": _meter_for(index, "june", service, replacement),
                    "read_date": _read_on({"key": "opening"}, walk_offset).isoformat(),
                    "reading": str(_register_value(index, "opening", service, replacement, channel)),
                    "channel": channel,
                    "service": service,
                }
            )
    return rows


def _channel_delta(
    unit_index: int, period_key: str, service: str, channel: str
) -> Decimal:
    """How much THIS register moved in THIS period.

    The total register moves by the month's consumption; the three time-of-use
    windows move by `fixture.tou_window_split`'s three shares, which sum to that
    same consumption EXACTLY (off-peak is the remainder), so
    `validation.tou_sum_sanity` reads a 0.000000 % deviation and not a rounding
    wobble; the export dial moves by what the household pushed back.

    A MAXIMUM register has no delta at all and never reaches this function —
    `_register_value` answers it before asking (`BR-MET-051`, `DEF-797`).
    """
    total = Decimal(fixture.consumption(unit_index, period_key, service))
    if channel == fixture.CHANNEL_TOTAL:
        return total
    if channel in fixture.TOU_WINDOW_CHANNELS:
        return fixture.tou_window_split(total)[channel]
    if channel == fixture.CHANNEL_EXPORT:
        return fixture.export_kwh(total)
    raise ValueError(f"no delta is defined for the {channel!r} register")


def _register_value(
    unit_index: int,
    period_key: str,
    service: str = "water",
    replacement: bool = True,
    channel: str = fixture.CHANNEL_TOTAL,
) -> Decimal:
    """The cumulative register reading a clerk would write down, in the
    backbone service's own unit (kgal on a water tenant, kWh on an electric).

    A meter reads a running total, not a consumption — so the fixture computes
    the total and lets the product derive consumption from it, which is the
    only way the S29 read detail can show its own arithmetic (BR-MET-056).

    The replacement register starts again at zero, exactly as a new meter does;
    that is what makes case 3 worth seeding.

    ⚠ **THE OPENING BASELINE IS NOT SCALED AND THAT IS DELIBERATE.** `start` is
    the serial-derived number the opening read wrote down; scaling it would move
    the opening read too and change nothing about the consumptions derived
    between the periods. What IS scaled is `fixture.consumption` — see
    `CONSUMPTION_SCALE` for why an electric estate reads in hundreds of kWh
    rather than in single figures, and for the fact that it prices nothing.

    ⚠ **A `demand` REGISTER IS ANSWERED BEFORE ANY OF THAT AND IS NOT A RUNNING
    TOTAL — `BR-MET-051`, PO 2026-09-07's own clause (c).** It carries the
    month's PEAK, in kW, and `register_units.billable_quantity` bills that VALUE
    rather than a delta. A seeder that accumulated it would be re-committing
    `DEF-797` — **$154.00 billed against a correct $4,532.00**, on a running
    product — from the fixture side, where every test would still pass because
    the arithmetic would be internally consistent and simply wrong.
    """
    if channel == fixture.CHANNEL_DEMAND:
        if period_key == "opening":
            raise ValueError("a demand register has no opening baseline (BR-MET-051)")
        return fixture.demand_peak_kw(
            Decimal(fixture.consumption(unit_index, period_key, service))
        )
    offset, step = _REGISTER_BASELINE[channel]
    start = Decimal(offset + unit_index * step)
    if period_key == "opening":
        return start
    keys = [period["key"] for period in fixture.PERIODS]
    total = Decimal("0")
    for key in keys[: keys.index(period_key) + 1]:
        total += _channel_delta(unit_index, key, service, channel)
    # ⚠ **`CR-062` C8 / `DEF-3260` — WITHOUT `replacement` THE SECOND SERVICE'S
    # JULY WALK IS REFUSED, WHICH IS WHAT IT DID.** Only the FIRST metered
    # service plants a swap (judgment 4), so on every other service unit 11's
    # meter is the SAME continuous register all three months. This branch
    # subtracts June's consumption to start the new register at zero; applied to
    # a meter that was never swapped it hands in a reading LOWER than the month
    # before, and `validate_read_batch` refuses it as a rollback — measured on
    # PostgreSQL 16: *"the july read batch will not post: 1 of 48 row(s) failed
    # validation"*, with the second and third billing cycles falling over behind
    # it. **This function and `_meter_for` are a PAIR** — one decides which
    # serial a read lands on and the other what number is written on it — and
    # `DEF-3260` is what it costs when only one of them is told.
    if unit_index == fixture.CASE_METER_REPLACED and period_key != "june" and replacement:
        # New register, new serial, reading from zero: June's consumption is
        # NOT on it.
        june = _channel_delta(unit_index, "june", service, channel)
        return total - june
    return start + total


def _rows_for(
    period: dict[str, Any],
    service: str = "water",
    replacement: bool = True,
    walk_offset: int = 0,
) -> list[dict[str, Any]]:
    """ONE ROUTE's sheet for ONE period — the rows that crew hands in.

    ⚠ **A ROW PER REGISTER, NOT A ROW PER METER (PO 2026-09-07 clause (c)).** A
    tiered or flat customer still hands in one line, which is every water meter
    and 41 of the 50 electric ones. A time-of-use customer hands in four — the
    three windows and the total they must sum to — a demand customer hands in
    the total and the month's peak, and a solar household adds the grid-push
    register. `fixture.read_channels` decides which, from the customer's own
    tariff shape, and this function decides nothing.
    """
    rows: list[dict[str, Any]] = []
    read_on = _read_on(period, walk_offset)
    for unit in _units_on_route(walk_offset):
        index = unit["unit_index"]
        if period["key"] == "august" and index in fixture.CASE_UNREADABLE:
            # Spec §4 case 1: THREE meters nobody could read in August. The row
            # is ABSENT — which is what a clerk who could not get to the meter
            # actually hands in, and what gives the estimation screen its work.
            continue
        for channel in fixture.read_channels(index, service):
            rows.append(
                {
                    "meter_id": _meter_for(index, period["key"], service, replacement),
                    "read_date": read_on.isoformat(),
                    "reading": str(
                        _register_value(index, period["key"], service, replacement, channel)
                    ),
                    "channel": channel,
                    "service": service,
                }
            )
    return rows


def _validated_rows(batch_id: Any, *, staged: int, where: str) -> list[dict[str, Any]]:
    """The batch's rows AFTER validation — from the batch, and never from a dict.

    ⛔ **DEF-659's loud half, and it needs no ruling to land.** The consumer this
    replaces read `validate_read_batch`'s return value with
    `report.get("rows", [])`. That function answers `selectors.read_batch_dict`
    and has never carried a `rows` key, so the default silently won: zero rows,
    zero dispositions, zero blocking errors found, and `commit_read_batch` then
    posted nothing while the batch reported `posted`.

    Two functions in ONE module disagreed about a contract and nothing could
    fail, because `.get(k, default)` cannot. So this reads metering's own
    published selector and then **asserts the count against what the fixture
    staged**. That check is the one that survives a future reshaping: whatever
    the mechanism, a fixture that cannot see the rows it just wrote refuses
    instead of quietly accepting an empty list.

    What this does NOT decide: whether the sample path should auto-disposition
    warnings at all, or whether a batch carrying undispositioned warnings should
    REFUSE (BR-MET-015 says that for errors). Both are rulings, both are asked
    in DEF-659's row, and neither is a lane's — the behaviour here is the
    behaviour the code has always intended and `_seed_cr030_demo_reads` already
    performs.
    """
    rows = selectors.read_batch_rows(_batch_row_for(batch_id))
    if len(rows) != staged:
        raise fixture.BlockCannotRun(
            f"{where} staged {staged} row(s) and metering reports {len(rows)} back — the "
            "fixture will not disposition, judge or post rows it cannot see. This is the "
            "shape of DEF-659: a consumer reading an empty list where the rows are, "
            "dispositioning nothing, and letting the batch report `posted` over reads that "
            "never landed."
        )
    return rows


def _post_batch(
    actor: Any,
    period: dict[str, Any],
    service: str = "water",
    replacement: bool = True,
    walk_offset: int = 0,
) -> int:
    """ONE ROUTE's reads for one period, through the S28 pipeline a clerk drives
    by hand.

    ⚠ **`service` IS THE BATCH TAG AND `stage_read_batch` REFUSES A DISABLED
    ONE** — `metering.service_not_enabled`, `_validate_batch_tags`. That refusal
    is the second half of DEF-795: with `water` hardcoded here, an electric
    tenant's reads block did not merely seed nothing, it could not have staged a
    batch at all. The tag now names the estate's own backbone, so the batch is
    lawful on whatever the utility sells.

    ⚠ **AND THE ROUTE IS A TAG TOO, SINCE 2026-09-07.** A period's walk is five
    batches now, one per route, so *which round is this* is a question the
    batch list has to be able to answer — and `read_import_batches.route_id` is
    the column that answers it. It is set from the route this fixture actually
    walked, never inferred: `stage_read_batch` validates it the same way it
    validates the service tag, so a fixture naming a route the tenant does not
    hold is refused rather than silently untagged.
    """
    rows = (
        _opening_rows(service, replacement, walk_offset)
        if period["key"] == "opening"
        else _rows_for(period, service, replacement, walk_offset)
    )
    read_on = _read_on(period, walk_offset)
    route_id = _walk_route_id(walk_offset)
    batch = services.stage_read_batch(
        actor,
        {
            "source_kind": "manual",
            "source_detail": "walk_by",
            # CR-038 W3 — the read METHOD, the tag BR-MET-123 makes the one
            # that travels onto every reading. Seeded so the demo's reads say
            # `recorded` rather than falling back to the derived translation of
            # the legacy detail beside it.
            "read_method": "walk_by",
            "period_month": read_on.replace(day=1).isoformat(),
            "service": service,
            **({"route_id": route_id} if route_id else {}),
            "file_name": (
                f"sample-{period['key']}-{service}-"
                f"rt{walk_offset + 1}.csv"
            ),
            "rows": rows,
        },
    )
    batch_id = batch["id"]
    services.validate_read_batch(actor, batch_id)
    # ⛔ **DEF-659 — THE ROWS ARE READ FROM THE BATCH, NOT FROM `report`, AND A
    # DISAGREEMENT NOW RAISES.** This loop read `report.get("rows", [])`, and
    # `validate_read_batch` answers `selectors.read_batch_dict` — id, status,
    # counts, compliance, and **no `rows` key at all**. So the list was empty on
    # every run since the return shape changed: nothing was ever dispositioned,
    # the blocking check below could never find a row, `commit_read_batch`
    # skipped every undispositioned warning, and the batch still reported
    # `posted`. Reproduced verbatim: `{'status': 'posted', …}` with
    # `posted_reads: 0`.
    # `.get(key, default)` over a same-module contract IS the escape: a missing
    # key degrades to doing nothing, silently, forever, and nothing objects.
    # `_seed_cr030_demo_reads` below already reads the rows the right way; this
    # is now the same call, and `_validated_rows` REFUSES when the row count it
    # gets back does not match the row count this fixture staged, so the same
    # bug in any future shape is loud instead of empty.
    rows_now = _validated_rows(batch_id, staged=len(rows), where=f"the {period['key']} batch")
    # AMENDED 2026-08-26 (CR-038 W2): this loop's original reason — "BR-MET-015:
    # a WARNING row does not post until somebody dispositions it" — is
    # SUPERSEDED by BR-MET-129 (PO 2026-08-26): a warned reading now posts
    # WITHOUT a disposition, flags carried onto the committed read. The loop
    # STAYS, deliberately: BR-MET-129's own text says the seeder's *"explicit
    # accept-with-reason trail may stay as documentation of the demo"* — the
    # accepts are still recorded when given, and "the seeder accepted 41
    # flagged reads" remains a fact an operator can see, now as provenance
    # rather than as a posting requirement.
    for row in rows_now:
        if row.get("severity") == "warning" and not row.get("disposition"):
            services.set_row_disposition(
                actor,
                batch_id,
                row["row_no"],
                {
                    "disposition": "accept",
                    "reason": "sample data — accepted by the sample-data load (BR-TEN-056)",
                },
            )
    # ── ERROR ROWS ARE NOT DISPOSITIONED HERE, AND THEY ARE NOT IGNORED ────────
    # AMENDED 2026-08-16. The loop above handles `warning` and nothing handled
    # `error`, so `commit_read_batch` refused the batch with
    # `BizError: BIZ-COMPLETENESS (metering.read_batch.errors_need_resolution)`
    # — accurate, and it reached the operator as the single word `BizError`
    # with no row and no reason attached.
    #
    # ⚠ **AMENDED AGAIN 2026-08-30 — `commit_read_batch` NO LONGER REFUSES, AND
    # THAT MAKES THE CHECK BELOW MORE LOAD-BEARING RATHER THAN LESS
    # (`BR-MET-940`, CR-054 task 14).** Under the PO's ruling — *"all or nothing
    # will not work - we accept what is correct and rejct what i not correct"* —
    # a batch with unresolved errors now POSTS its good rows and holds the rest
    # with a reason. So the sentence above describes what the service did until
    # today, and the fixture's own `BlockCannotRun` below is now the ONLY thing
    # standing between a broken fixture and a sample utility quietly seeded with
    # fewer readings than it claims. **Do not delete it as redundant.** Its
    # argument is unchanged and is still exactly right: BR-MET-015's ROW half
    # stands, an error is resolved only by a human's judgment, and a fixture
    # that auto-resolved its own would be posting readings the product had just
    # held.
    #
    # The fixture does NOT dispose of them. BR-MET-015 resolves an error by
    # override / reject / field visit / skip, and every one of those is a
    # judgment about a real meter: a fixture that auto-overrode its own errors
    # would post readings the product had just refused, and a fixture that
    # auto-skipped them would quietly seed fewer reads than it claims. What was
    # missing was not a disposition — it was the SENTENCE. An erroring sample
    # batch means the fixture disagrees with the data it just wrote (measured
    # cause on 2026-08-16: the premises/units block had failed first, so the
    # reads named meters that did not exist), and that is a fault to be read,
    # not resolved.
    blocking = [
        row
        for row in _validated_rows(batch_id, staged=len(rows), where=f"the {period['key']} batch")
        if row.get("severity") == "error" and not row.get("disposition")
    ]
    if blocking:
        raise fixture.BlockCannotRun(
            f"the {period['key']} read batch will not post: "
            f"{len(blocking)} of {len(rows)} row(s) failed validation "
            "and BR-MET-015 resolves an error only by a human's override, reject, field "
            "visit or skip — never by a fixture. First: "
            + "; ".join(
                f"row {row.get('row_no')} {row.get('message') or row.get('code') or ''}".strip()
                for row in blocking[:3]
            )
            + ". Usually this means the meters these reads name were never seeded — "
            "check the Meters and Premises blocks above."
        )
    # DEF-MET-8106 — posted INLINE: the plant builds on these readings next.
    result = services.commit_read_batch(actor, batch_id, {"certified": True}, defer=False)
    return int(result.get("posted_reads") or 0)


#: The period spec §4 case 2's dispute is ABOUT. Named once so this function and
#: `_meter_for` cannot end up asking about two different months.
DISPUTED_READ_PERIOD_KEY = "august"


def _flag_disputed_read(actor: Any, service: str = "water") -> None:
    """Spec §4 case 2 — one disputed read, so the dispute flag actually renders
    instead of a counter stuck at zero.

    ⛔ **THIS USED TO ASK FOR "THE MOST RECENT READING THAT IS NOT YET DISPUTED",
    AND THAT FILTER IS WHAT MADE IT WALK BACKWARDS (DEF-2970).** On the first
    run it correctly flagged the August reading; on every run after that the
    August one was EXCLUDED BY THAT SAME FILTER and the next most recent was
    taken instead. Measured 2026-09-01: after one load the tenant held one
    disputed reading, `W-5007` on 2026-08-14; after a second load it held two,
    `W-5007` on 2026-07-31 as well, and a third run would have taken June's.

    It mattered beyond tidiness. A disputed reading holds its account out of a
    bill run (`account_held_by_disputed_read`), so each replay quietly removed
    that customer from one more month's billing — and the enclosing block went
    on reporting `0 row(s)`, honestly, because a dispute is an UPDATE on a
    reading that already exists.

    ⚠ **SO THE LESSON IS WORTH MORE THAN THE FIX: A STEP THAT REPORTS 0 ROWS CAN
    STILL MUTATE.** BR-TEN-063's *"a replay changes no count"* is a weaker claim
    than *"a replay changes nothing"*, and only the second one is what an
    operator pressing the button twice actually needs.

    It asks for the reading the case is ABOUT now — the period's own read date —
    and returns when that reading is already disputed, so a second call is a
    no-op instead of a walk.
    """
    asset_no = _meter_for(fixture.CASE_DISPUTED_READ, DISPUTED_READ_PERIOD_KEY, service)
    asset_id = _asset_id_for(asset_no)
    if asset_id is None:
        return
    period = next(
        (row for row in fixture.PERIODS if row["key"] == DISPUTED_READ_PERIOD_KEY),
        fixture.PERIODS[-1],
    )
    # ⚠ **THE DATE IS THIS UNIT'S OWN WALK DAY, NOT THE PERIOD'S (PO
    # 2026-09-07).** `CASE_DISPUTED_READ` (unit 7) is on Cedar Ridge Way, which
    # is walked two working days before the cycle closes — so the period's own
    # `read_on` names a day this meter was never read on, and a filter on it
    # would find nothing and return in silence. That is `DEF-2970`'s shape (a
    # step that reports nothing and has done nothing), so the absence is now
    # LOGGED as well as returned.
    walk_day = _read_on(period, _walk_offset(fixture.CASE_DISPUTED_READ))
    read = (
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset_id=asset_id,
            superseded_by_id__isnull=True,
            read_at__date=walk_day,
        )
        .order_by("-read_at")
        .first()
    )
    if read is None:
        logger.info(
            "sample data: spec case 2 not seeded — no reading on %s for %s on %s, so there "
            "is nothing to dispute",
            asset_no,
            DISPUTED_READ_PERIOD_KEY,
            walk_day.isoformat(),
        )
        return
    if read.disputed_at is not None:
        return  # BR-TEN-063 — already flagged; a replay changes NOTHING, not just no count
    dispute = getattr(services, "dispute_read", None)
    if dispute is None:
        # No dispute WRITE service is published, so the flag is not set by a
        # back-door UPDATE — the absence is reported rather than faked.
        logger.info("sample data: metering publishes no dispute_read service; case 2 not seeded")
        return
    dispute(
        actor,
        str(read.id),
        {"reason": "customer says the reading is too high — sample data (spec §4 case 2)"},
    )


def _asset_id_for(asset_no: str) -> Any | None:
    meter = seams.meter_by_no(asset_no)
    return getattr(meter, "id", None) if meter is not None else None


def seed_sample_reads(actor: Any) -> int:
    """THE SECOND SEAM: three months of reads in the estate's OWN service and
    the tenant's OWN unit — kgal on a water utility, kWh on an electric one,
    ccf on a gas one, and never a bare number (CLAUDE.md rule 3).

    ⚠ **THIS PROMISED *"therm on a gas one"* UNTIL 2026-09-07 AND EVERY SEEDED
    GAS READ HAS CARRIED `ccf` SINCE 2026-09-02 (`DEF-MET-4502`).** The unit is
    never a literal here — it is the tenant's own declared primary, read through
    the owning module's seam — so the CODE was right the whole time and only
    this sentence was wrong. Measured on the dev database at the time of filing:
    all 198 seeded gas reads, across the four batches, carry `ccf` and not one
    carries `therm`. `BR-TEN-1180` / the PO-filed `DEF-3230` swapped the seeded
    gas register so it would agree with the workbook's signed `$1.15/ccf`.

    June and July are billed by apps/billing's own sample block. **August is
    READ AND LEFT UNBILLED** — spec §3, and the reason is the Product Owner's:
    a fixture that arrives with everything done leaves nothing to evaluate.

    CR-039 A2. Every row still goes through the FULL S28 pipeline a clerk drives
    by hand — `stage_read_batch` → `validate_read_batch` → `set_row_disposition`
    → `commit_read_batch`. Nothing here inserts a `meter_reads` row, and making
    the service a parameter did not open a shortcut: the batch carries the
    service tag `stage_read_batch` validates against the tenant's enabled set,
    so a fixture in a service the utility does not sell is refused by the
    product rather than waved through by the seeder.
    """
    # ⚠ **CR-030's TWO DEMO METERS ARE READ FIRST, AND THE ORDER IS DELIBERATE.**
    # `_post_batch` RAISES when the fixture's own batch will not commit
    # (BR-MET-015: an error row is resolved by a human, never by a fixture), and
    # that refusal is correct — but it would take A-10432's four-reads-a-meter
    # with it, and the account detail's Meters and Usage tabs are a different
    # demo from the July bill run. They share no meter and no batch, so nothing
    # is being ordered around a dependency: this is one block that must not lose
    # the other's data. They are keyed on the ASSET rather than the date,
    # because the two sets share read dates on purpose (one utility, one
    # reading calendar).
    posted = _seed_cr030_demo_reads(actor)
    # ⛔ **THIS READ `if "water" not in enabled: return posted` — DEF-795's
    # second half.** A tenant that did not sell water got its three months of
    # reads skipped in silence, and the block reported the CR-030 demo count as
    # though the estate had been read. The estate is now metered in whatever the
    # utility sells, so the question is not "is water on" but "does this tenant
    # have a metered backbone at all" — and when it does not, the block REFUSES
    # by name rather than answering a number it did not earn.
    plan = estate()
    if not plan.metered:
        raise fixture.BlockCannotRun(
            "no meter reads were seeded: this tenant has no service the sample estate can "
            "put a register on, so there are no meters to read. "
            + plan.no_register_reason  # DEF-2396 — a capacity-only estate is not "nothing enabled"
        )
    periods = (_opening_period(), *_first_cycle_periods())
    # ── CR-062 C6/C7 · ONE WALK PER METERED SERVICE ────────────────────────
    # This read `service = plan.backbone` and walked ONE. A tenant selling
    # electric + water got three months of water readings and not one electric
    # reading, so its electric meters — when they finally existed — would have
    # had nothing to bill (`DEF-3224`, PO statement (8)).
    #
    # Each service gets its OWN batch, tagged with that service, because
    # `stage_read_batch` validates the tag against the tenant's enabled set and
    # a batch carries one service by contract. The file name carries the
    # service too (`sample-june-electric.csv`), so a person looking at the
    # batch list sees which walk is which.
    posted += _post_periods(actor, periods, plan.metered_codes)
    for code in plan.metered_codes:
        _assert_read_coverage(periods, code, replacement=code == plan.primary.code)
    # CR-062 C8 — the swap is the FIRST metered service's demonstration, so the
    # retirement is asked of that service and of no other.
    _retire_the_case3_meter_now_its_reads_exist(actor, plan.primary.code)
    return posted


def _opening_period() -> dict[str, Any]:
    """The register baseline, shaped like a period so it walks the same loop."""
    return {
        "key": "opening",
        "read_on": fixture.OPENING_READ_ON,
        "start": fixture.OPENING_READ_ON,
        "end": fixture.OPENING_READ_ON,
    }


def _period_already_seeded(period: dict[str, Any], service: str, walk_offset: int = 0) -> bool:
    """Has this ROUND of this period's walk already been posted FOR THIS
    SERVICE? Asked by date, by service and — since 2026-09-07 — by route.

    ⚠ **`walk_offset` JOINED IT WITH THE FIVE ROUTES AND IS LOAD-BEARING FOR
    THE SAME REASON `service` WAS.** A period is five batches on five dates now.
    Ask only *"is any sample reading on file for this period"* and the first
    round answers YES for the other four, which post nothing while the block
    reports a healthy count — `DEF-166`'s shape, one axis further on. Each round
    has its own date, so asking by date IS asking by route.

    ⚠ **THE CR-030 DEMO METERS ARE EXCLUDED FROM THIS GUARD ON PURPOSE.** It
    asks *"has this PERIOD been seeded"* by date, and `A-10432`'s own reads land
    on the SAME four dates — one utility reads on one calendar. Without this
    exclusion the guard would make the fixture's 48-meter batch look
    already-seeded and skip it, which is a seeder reporting `0 row(s)` over work
    it never did (DEF-166's shape).

    ⚠ **`service` JOINED IT UNDER `CR-062` C7 AND IT IS LOAD-BEARING, NOT
    TIDINESS.** The estate now walks several services on ONE reading calendar,
    so a guard asking only *"is any sample reading on file for this date"* would
    answer YES for every service after the first: the water walk would post, the
    electric walk would skip in silence, and the block would report a healthy
    count over readings that were never taken. That is the same shape as
    `DEF-166`, one register along. The read is matched through the meter's own
    SERVICE POINT (`assets.Asset.service_point.service`), which is the point
    `create_asset` minted from the meter plan's declared service — the asset row
    itself holds no service column.
    """
    return (
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            is_sample=True,
            read_at__date=_read_on(period, walk_offset),
            asset__service_point__service__code=service,
        )
        .exclude(asset__asset_no__in=[m["asset_no"] for m in fixture.CR030_A10432_READS])
        .exists()
    )


def _post_periods(
    actor: Any, periods: tuple[dict[str, Any], ...], services_: tuple[str, ...]
) -> int:
    """Post each period's walk, once, FOR EACH METERED SERVICE. Shared by all
    three reads blocks so the three cannot drift into three spellings of one
    loop.

    ⚠ **`services_` WAS A SINGLE `service` UNTIL `CR-062` C7 (2026-09-02).** The
    estate now holds a register per metered service, so a period's walk is one
    BATCH PER SERVICE — a batch carries one service tag by contract
    (`stage_read_batch` validates it against the tenant's enabled set), and a
    single batch mixing water and electric rows could not be staged at all.

    ⚠ **THE REPLAY GUARD IS ASKED PER SERVICE AND NOT PER PERIOD, WHICH IS THE
    ONE THING THAT HAD TO CHANGE WITH IT.** `_period_already_seeded` asks *"is
    any sample reading on file for this DATE"*, and with two services on one
    reading calendar the water walk would answer YES for the electric one and
    the electric walk would silently post nothing — a seeder reporting a
    healthy count over work it never did, which is `DEF-166`'s own shape. So the
    question is now *"has THIS SERVICE been walked on this date"*.
    """
    posted = 0
    for period in periods:
        for code in services_:
            # PO 2026-09-07 — one batch PER ROUTE, each on its own walk day, so
            # a period's reads land across the last working week of the cycle
            # instead of all on the close date.
            for route in fixture.READ_ROUTES:
                offset = route["walk_offset"]
                if _period_already_seeded(period, code, offset):
                    continue  # BR-TEN-063: a replay changes no count
                # CR-062 C8 — the FIRST metered service carries the case-3 swap
                # and no other does, so it is the only one whose chain crosses
                # two serials. `services_` is `EstatePlan.metered_codes`,
                # already in the plan's own order, so `[0]` IS `plan.primary`.
                posted += _post_batch(
                    actor, period, code, replacement=code == services_[0], walk_offset=offset
                )
        # ⚠ **TAGGED OVER EVERY DATE THE WALK TOUCHED, NOT ONE.** `BR-TEN-057`'s
        # tag is what makes a seeded reading removable; tagging only
        # `period["read_on"]` after the walk was spread would have left four
        # rounds out of five untagged and therefore permanent.
        _tag(
            models.MeterRead.objects.filter(
                tenant_id=_tenant_id(), read_at__date__in=_walk_dates(period), is_sample=False
            )
        )
    return posted


def _billed_periods() -> tuple[dict[str, Any], ...]:
    """The periods a bill run has already issued for — this block's own scope.

    ⚠ **THIS USED TO BE `fixture.PERIODS` AND THE DIFFERENCE IS THE PO'S OWN
    ORDERING (2026-09-01).** Verbatim: *"after second bill is generated, I want
    to add another step which will add - meter reads and payment data - so that
    We can run the next bill cycle on our own and see how it is working"*, and
    then, when it was put to them again: *"Without meter reads for 3rd cycle
    billing cycle will not run - hence you have to add meter reads also."*

    The rows are the same rows and their register values are byte-identical;
    what moves is WHEN they are written. Until today the walk for the cycle the
    PO runs was posted **before June was billed** — three months of readings
    handed in on the same morning, which is not a thing any utility does and,
    more to the point, is not a step the PO could point at and say *that one
    prepares my run*. `seed_sample_next_cycle_reads` below is that step.
    """
    return tuple(period for period in fixture.PERIODS if period["billed"])


def _first_cycle_periods() -> tuple[dict[str, Any], ...]:
    """The FIRST billed period — the only one `seed_sample_reads` walks.

    ⚠ **THIS WAS EVERY BILLED PERIOD UNTIL 2026-09-01, AND THE PO CAUGHT IT
    (`DEF-2968`).** Verbatim: *"reading data when you seed first time add reading
    then bill it, then add reading data again, then bill it and then again add
    reading data - you can not add reading data once for 3 months"*. The walk for
    the third cycle had already been moved out that morning; June and July were
    still handed in on the same morning, before either had been billed, which is
    the same fault one period earlier. The order is now reads → bill → reads →
    bill → reads, which is the order a utility actually works in.
    """
    return _billed_periods()[:1]


def _second_cycle_periods() -> tuple[dict[str, Any], ...]:
    """Every billed period after the first — the walk that feeds cycle two.

    A slice rather than an index, so a fixture that ever declares three billed
    periods walks the third here instead of dropping it silently (the shape
    `apps/billing/sample_data._second_cycle_periods` already uses, and it is
    deliberately the same slice so the reads and the bills cannot disagree about
    which periods belong to cycle two).
    """
    return _billed_periods()[1:]


def _next_cycle_periods() -> tuple[dict[str, Any], ...]:
    """Everything the fixture declares and has NOT billed — the walk the PO's
    own run bills. A slice rather than an index, so a fixture that ever
    declares two unbilled periods prepares both instead of dropping one
    silently (the shape `apps/billing/sample_data._second_cycle_periods` already
    uses, for the same reason)."""
    return tuple(period for period in fixture.PERIODS if not period["billed"])


def seed_sample_next_cycle_reads(actor: Any) -> int:
    """**THE THIRD-CYCLE WALK — the step the Product Owner asked for on
    2026-09-01, and the reason it is a step of its own.**

    PO verbatim: *"after second bill is generated, I want to add another step
    which will add - meter reads and payment data - so that We can run the next
    bill cycle on our own and see how it is working"*, and *"Without meter reads
    for 3rd cycle billing cycle will not run - hence you have to add meter reads
    also."*

    So: it runs AFTER `billing:seed_sample_second_cycle`, it posts the readings
    for every period the fixture declares and does not bill, and **it then
    counts its own coverage and refuses if the count is short.** A seeder that
    plants 44 readings on 48 meters does not fail — it hands four accounts to
    the run's exception tab, where they look like a billing problem. That is
    the failure this block exists to make loud.

    ⚠ **NOTHING HERE IS A NEW ROW, A NEW DATE OR A NEW FIGURE.** Every reading
    is `_rows_for`'s, at `_register_value`'s cumulative register, on
    `fixture.PERIODS`' own read date — the same rows `seed_sample_reads` posted
    until today. What changed is the STEP they belong to. A fourth period was
    considered and rejected: `water_consumption_kgal` prices exactly three
    period keys, the sample cycle reads on the 14th of the month so its next
    window is 14 September, and seeding a reading dated after the wall clock
    would be a walk nobody has taken (the fixture's own objection to an August
    read on the 31st).

    ⚠ **THE THREE UNREADABLE METERS STAY UNREADABLE.** Spec §4 case 1 leaves
    `CASE_UNREADABLE` out of the August batch deliberately, so the estimation
    screen has work; this block does not quietly fill them in, it DECLARES them
    and subtracts them from what it expects. `CASE_DISPUTED_READ`'s reading IS
    posted and is then flagged — a disputed read is a read.

    ⚠ **EVERY METER ON THE SAMPLE CYCLE CARRIES ONE REGISTER, AND THE TENANT'S
    MULTI-REGISTER METERS ARE NOT ON IT.** Measured on a freshly seeded tenant,
    2026-09-01: 48 metered service points on the sample cycle, 48 assets, every
    reading on the `total` channel — and three multi-register meters elsewhere
    (`M-7302` with 5 registers, `M-7450` with 4, `M-7210` with 2). Those are
    `seed_demo`'s CR-054 validation demonstration, they sit on `CY-001` and
    `CY-004`, they carry NO account, and `seed_demo` says in as many words that
    the meters outside its demonstration set *"still carry no reading, which is
    what makes the S25 Missing chip and the chase list have something to show"*.
    So this block does not read them: they are outside the run it prepares, and
    reading them would delete another fixture's exhibit. `next_cycle_read_
    coverage` reports them by serial rather than leaving the absence to be
    rediscovered.

    Idempotent (BR-TEN-063): a period already on file for its read date is
    skipped, and a replay writes nothing and returns 0.
    """
    plan = estate()
    if not plan.metered:
        raise fixture.BlockCannotRun(
            "no next-cycle reads were seeded: this tenant has no service the sample estate "
            "can put a register on, so there are no meters to read. "
            + plan.no_register_reason  # DEF-2396 — a capacity-only estate is not "nothing enabled"
        )
    periods = _next_cycle_periods()
    if not periods:
        # A fixture that bills every period it declares leaves this seam with
        # nothing to prepare. That is a fixture stating a shape, not a failure
        # (the wording `billing:seed_sample_second_cycle` already uses).
        return 0
    posted = _post_periods(actor, periods, plan.metered_codes)
    # CR-062 C8 — ONE disputed read, on the first metered service. A dispute per
    # service is three copies of one exhibit, which makes the S29 dispute chip
    # harder to read rather than richer (judgment 4).
    _flag_disputed_read(actor, plan.primary.code)
    for code in plan.metered_codes:
        _assert_read_coverage(periods, code, replacement=code == plan.primary.code)
    return posted


def seed_sample_second_cycle_reads(actor: Any) -> int:
    """**THE SECOND CYCLE'S WALK** — PO 2026-09-01, and it is the other half of
    the same instruction that produced `seed_sample_next_cycle_reads`.

    PO verbatim: *"reading data when you seed first time add reading then bill
    it, then add reading data again, then bill it and then again add reading
    data - you can not add reading data once for 3 months"*.

    ⚠ **THE POSITION IS THE WHOLE FEATURE.** This block sits between the
    overcharge correction and `billing:seed_sample_second_cycle`, so the order a
    seeded tenant is built in is now **reads → bill → money → reads → bill →
    reads**, which is the order a utility actually works in. Until today all
    three months were walked in one pass BEFORE June was billed — three months
    of readings handed in on the same morning, which no meter reader has ever
    done and which no screen could show as a cycle.

    ⚠ **NOT ONE READING, DATE OR FIGURE MOVES.** Every row is `_rows_for`'s, at
    `_register_value`'s cumulative register, on the fixture's own read date. The
    three reads blocks partition `fixture.PERIODS` — opening + first billed,
    then the rest of the billed ones, then the unbilled ones — so the same rows
    are written, and each is written by exactly one block.

    Idempotent (BR-TEN-063): a period already on file for its read date is
    skipped, so a replay writes nothing and returns 0.
    """
    plan = estate()
    if not plan.metered:
        raise fixture.BlockCannotRun(
            "no second-cycle reads were seeded: this tenant has no service the sample estate "
            "can put a register on, so there are no meters to read. "
            + plan.no_register_reason  # DEF-2396 — a capacity-only estate is not "nothing enabled"
        )
    periods = _second_cycle_periods()
    if not periods:
        return 0
    posted = _post_periods(actor, periods, plan.metered_codes)
    for code in plan.metered_codes:
        _assert_read_coverage(periods, code, replacement=code == plan.primary.code)
    return posted


def _expected_meter_nos(
    period: dict[str, Any], service: str, replacement: bool = True
) -> set[str]:
    """The serials this period's batch actually stages.

    ⚠ **ASKED OF THE SAME FUNCTION THAT BUILDS THE ROWS, never re-derived.** The
    first draft of this check rebuilt the expected set from `units_flat()` and
    subtracted `CASE_UNREADABLE` itself — a second copy of a rule that already
    lives in `_rows_for`, and one that would have gone quietly wrong the day
    either changed. It also got the OPENING period wrong, because
    `_opening_rows` writes every unit's ORIGINAL serial while `_meter_for` hands
    back the replacement one for any key that is not `june`.
    """
    rows: list[dict[str, Any]] = []
    for route in fixture.READ_ROUTES:
        offset = route["walk_offset"]
        rows += (
            _opening_rows(service, replacement, offset)
            if period["key"] == "opening"
            else _rows_for(period, service, replacement, offset)
        )
    return {str(row["meter_id"]) for row in rows}


def _assert_read_coverage(
    periods: tuple[dict[str, Any], ...], service: str, replacement: bool = True
) -> None:
    """Every meter this walk staged carries a reading, or the block says which
    ones do not — BY SERIAL, per period.

    ⚠ **THIS IS THE HALF THAT MAKES A READS BLOCK WORTH BEING A BLOCK.** A
    missing reading does not fail a bill run; it puts the account on the
    exceptions tab as `missing_read`, where it is indistinguishable from a meter
    the clerk genuinely could not reach. So a run can be half empty and still
    report itself healthy, which is the shape of every "built is not wired"
    defect in this repo (hard-won law 2). Counting here, at the moment the rows
    are written, is the only place the difference is still visible.

    The DECLARED absences need no special case: spec §4 case 1's three
    unreadable meters are already absent from `_rows_for`'s August batch, so
    they are never expected here in the first place.
    """
    tenant_id = _tenant_id()
    for period in periods:
        wanted = _expected_meter_nos(period, service, replacement)
        if not wanted:
            continue
        on_file = set(
            models.MeterRead.objects.filter(
                tenant_id=tenant_id,
                # PO 2026-09-07 — five rounds, five dates. Asking about one of
                # them would report four fifths of the estate as missing.
                read_at__date__in=_walk_dates(period),
                superseded_by_id__isnull=True,
                asset__asset_no__in=list(wanted),
            ).values_list("asset__asset_no", flat=True)
        )
        missing = sorted(wanted - on_file)
        if missing:
            raise fixture.BlockCannotRun(
                f"the {period['key']} walk is SHORT: {len(on_file)} reading(s) on file for "
                f"{len(wanted)} meter(s) that should have one, and the missing meters are "
                f"{', '.join(missing[:8])}"
                + (f" (+{len(missing) - 8} more)" if len(missing) > 8 else "")
                + ". Each one holds its account out of the next bill run as `missing_read`, "
                "where it reads as a billing problem rather than as a walk that did not "
                "finish. Any meter the fixture deliberately leaves unread is already absent "
                "from what this batch staged, so these are NOT those."
            )


def next_cycle_read_coverage(service: str | None = None) -> dict[str, Any]:
    """What the next cycle's walk covers, as figures a person can quote.

    Published so the report a lane writes and the check the block makes read the
    SAME arithmetic — two places computing "did every meter get read" would
    disagree the first day one of them was edited.
    """
    plan = estate()
    # CR-062 — `service` names ONE metered service to report on; with none
    # given it is the first, which is what every existing caller means and what
    # keeps a water tenant's report byte-identical.
    backbone = service or (plan.primary.code if plan.primary else None)
    out: dict[str, Any] = {
        "service": backbone,
        "periods": [],
        # NAMED, never silently absent: a multi-register meter that this walk
        # does not read is a fact somebody will otherwise rediscover from an
        # empty column. These are `seed_demo`'s validation demonstration and
        # sit on cycles this run never bills — see the block's docstring.
        "multi_register_meters_outside_the_cycle": [],
    }
    if backbone is None:
        return out
    tenant_id = _tenant_id()
    cycle = sample_cycle_row(selectors.cycles_list())
    if cycle is not None:
        out["metered_service_points_on_the_cycle"] = models.ServicePoint.objects.filter(
            tenant_id=tenant_id, cycle_id=cycle["id"], deleted_at__isnull=True
        ).count()
    out["multi_register_meters_outside_the_cycle"] = sorted(
        row["asset__asset_no"]
        for row in models.MeterRead.objects.filter(tenant_id=tenant_id)
        .values("asset__asset_no")
        .annotate(registers=Count("channel", distinct=True))
        .filter(registers__gt=1)
    )
    for period in (*_first_cycle_periods(), *_second_cycle_periods(), *_next_cycle_periods()):
        declared_absent = sorted(fixture.CASE_UNREADABLE) if period["key"] == "august" else []
        wanted = _expected_meter_nos(period, backbone)
        walk_dates = _walk_dates(period)
        on_file = set(
            models.MeterRead.objects.filter(
                tenant_id=tenant_id,
                read_at__date__in=walk_dates,
                superseded_by_id__isnull=True,
                asset__asset_no__in=list(wanted),
            ).values_list("asset__asset_no", flat=True)
        )
        out["periods"].append(
            {
                "key": period["key"],
                "read_on": period["read_on"].isoformat(),
                # PO 2026-09-07 — the walk is five rounds over five days, so a
                # report that quoted one date would be quoting a fifth of it.
                "walk_dates": [day.isoformat() for day in walk_dates],
                "meters_expecting_a_reading": len(wanted),
                "readings_on_file": len(on_file),
                "declared_absent": [
                    _meter_for(index, period["key"], backbone) for index in declared_absent
                ],
                "missing": sorted(wanted - on_file),
            }
        )
    return out


def _retire_the_case3_meter_now_its_reads_exist(actor: Any, service: str = "water") -> None:
    """Spec §4 case 3's SECOND half — DEF-660, and the ORDER is the fix.

    The assets block used to retire `W-5011` while creating the meters, which is
    the block BEFORE this one. `validation.retired_meter` errors on any read for
    a retired meter regardless of the read's DATE, so the fixture's own June read
    on that serial could never post: the opening batch refused with
    `BIZ-COMPLETENESS (metering.read_batch.errors_need_resolution)`, this whole
    block rolled back, and a fresh tenant ended with **0 reads, 0 bills and 0
    payments** — five downstream failures from one ordering.

    The reads exist now, so the meter can come off. Assets does the write; this
    only asks (B1 — nothing here touches the `assets` table).

    ⚠ **THE RULE UNDERNEATH IS NOT SETTLED AND THIS DOES NOT SETTLE IT.** Whether
    `retired_meter` should error for a read DATED BEFORE the retirement is
    OQ-361: a meter retired in June must still accept the May read somebody
    enters in July, and BR-MET-052 (CONFIRMED) says only *"read on retired meter
    = error"* with no date clause. Re-ordering the fixture is a fixture fix; the
    rule stays exactly as ratified until the PO rules.
    """
    outcome = seams.retire_sample_replaced_meter(actor)
    old_no = fixture.meter_no(service, fixture.CASE_METER_REPLACED)
    if outcome is None:
        logger.info(
            "sample data: assets publishes no retire_sample_replaced_meter, so the case-3 "
            "meter %s stays ACTIVE — the read chain still crosses two registers, but the "
            "old serial is not retired",
            old_no,
        )
    elif outcome:
        logger.info(
            "sample data: case 3 — %s retired now that its reads are posted (DEF-660 order)",
            old_no,
        )


def _seed_cr030_demo_reads(actor: Any) -> int:
    """`M-4021` (electric) and `M-4022` (water) — four reads each, one flagged
    *Partial cycle*, through the same S28 stage → validate → commit pipeline a
    clerk drives by hand.

    ⚠ **REGISTER VALUES, NOT CONSUMPTIONS.** The fixture declares what the dial
    read; the product derives usage from consecutive registers, so nothing here
    types a kWh figure and CLAUDE.md rule 3's unit travels on the batch.

    Then **BR-MET-106**: *"based on meter reading calculate monthly useage and
    save them and display them"* (PO 2026-08-24). `recompute_account` is the
    sole writer and is idempotent on the lineage; without this call the account
    detail's Usage tab renders every month ABSENT, which would be a true but
    useless demo.
    """
    enabled = seams.enabled_service_codes()
    posted = 0
    for meter in fixture.CR030_A10432_READS:
        if meter["service"] not in enabled:
            logger.info(
                "sample data (CR-030 W3): %s's reads are not posted — the tenant does not "
                "sell %s, so neither the meter nor its reads exist",
                meter["asset_no"],
                meter["service"],
            )
            continue
        for read in meter["reads"]:
            # BR-TEN-063 keyed on (asset, read date) rather than on the METER:
            # a per-meter guard cannot tell "already seeded" from "three of four
            # landed and one was refused", so a partial run could never be
            # completed by running the load again — which is the repair path
            # this command exists to be (`load_sample_data`'s own docstring).
            if models.MeterRead.objects.filter(
                tenant_id=_tenant_id(),
                asset__asset_no=meter["asset_no"],
                read_at__date=read["read_on"],
            ).exists():
                continue
            row = {
                "meter_id": meter["asset_no"],
                "read_date": read["read_on"].isoformat(),
                "reading": read["register"],
                "service": meter["service"],
            }
            if read.get("note"):
                row["note"] = read["note"]
            try:
                # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
                # (this block runs inside tenancy's per-module `atomic`), so without it the
                # work already done is lost at COMMIT. NOT tidiness — do not remove.
                with transaction.atomic():
                    posted += _post_cr030_read_batch(actor, meter, read, row)
            except Exception as exc:  # noqa: BLE001 — named, never swallowed
                logger.info(
                    "sample data (CR-030 W3): %s's %s read did not post — %s: %s",
                    meter["asset_no"],
                    read["read_on"].isoformat(),
                    type(exc).__name__,
                    exc,
                )
        _tag(
            models.MeterRead.objects.filter(
                tenant_id=_tenant_id(), asset__asset_no=meter["asset_no"], is_sample=False
            )
        )
    _recompute_cr030_monthly_usage(actor)
    return posted


def _batch_row_for(batch_id: Any) -> Any:
    """The `ReadImportBatch` row behind a staged batch id — metering's own table,
    read by metering's own seeder."""
    return models.ReadImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id).first()


def _post_cr030_read_batch(
    actor: Any, meter: dict[str, Any], read: dict[str, Any], row: dict[str, Any]
) -> int:
    """ONE read, staged, validated and committed — the pipeline, not an INSERT.

    A batch per read because `read_batches` carry ONE `period_month` and these
    four reads span four of them; a fixture that stuffed them into one batch
    would be describing a month the utility never read.
    """
    batch = services.stage_read_batch(
        actor,
        {
            # AMI reads arrive from the head-end; `source_kind` stays `manual`
            # because this batch IS a hand-staged one (the `ami_replay` kind is
            # disabled until the B7 head-end seam exists, and accepting it would
            # promise a replay nothing can perform).
            "source_kind": "manual",
            "source_detail": meter["source_detail"],
            # BR-MET-123's tag, from the same fixture row — `ami` for the AMI
            # electric meter, `drive_by` for the AMR water meter's drive-by
            # round, each agreeing with the meter's own `read_method`.
            # ⚠ The water meter read `mobile` here until 2026-08-27, on the
            # strength of a fixture COMMENT rather than a ruling; BR-MET-142
            # gave `drive_by` a category of its own and the fixture says so.
            "read_method": meter["read_method"],
            "period_month": read["read_on"].replace(day=1).isoformat(),
            "service": meter["service"],
            "file_name": f"sample-cr030-{meter['asset_no']}-{read['read_on']}.csv",
            "rows": [row],
        },
    )
    batch_id = batch["id"]
    services.validate_read_batch(actor, batch_id)
    # ⚠ **THE ROWS ARE READ FROM THE BATCH, NOT FROM `validate_read_batch`'s
    # RETURN VALUE.** That function returns `read_batch_dict` — id, status,
    # counts, compliance — and **no `rows` key at all**, so the older
    # `report.get("rows", [])` loop three screens up iterates an empty list
    # every time: it dispositions nothing, and its error check can never find a
    # blocking row. A WARNING row with no disposition was then SILENTLY SKIPPED
    # by `commit_read_batch` (`disposition = row.disposition or ("accept" if
    # severity == OK else None)`) while the batch still marked itself `posted` —
    # a batch reporting success over reads that did not land. REPORTED as a
    # defect on `_post_batch`; this function reads the rows through metering's
    # own published selector instead. (Historical account — since 2026-08-26,
    # BR-MET-129, an undispositioned warning POSTS, so that skip no longer
    # exists; the read-from-the-batch discipline stands regardless.)
    rows_now = _validated_rows(
        batch_id, staged=1, where=f"{meter['asset_no']}'s {read['read_on']} batch"
    )
    for entry in rows_now:
        if entry.get("severity") == "warning" and not entry.get("disposition"):
            services.set_row_disposition(
                actor,
                batch_id,
                entry["row_no"],
                {
                    "disposition": "accept",
                    "reason": "sample data — accepted by the sample-data load (BR-TEN-056)",
                },
            )
    blocking = [
        entry
        for entry in rows_now
        if entry.get("severity") == "error" and not entry.get("disposition")
    ]
    if blocking:
        # The same posture as `_post_batch`: an erroring sample batch is a fault
        # to be READ, never one a fixture resolves on a human's behalf.
        first = blocking[0]
        logger.info(
            "sample data (CR-030 W3): %s's %s read failed validation (%s) and BR-MET-015 "
            "resolves an error only by a human's override, reject, field visit or skip",
            meter["asset_no"],
            read["read_on"].isoformat(),
            first.get("message") or first.get("code"),
        )
        return 0
    # DEF-MET-8106 — posted INLINE: the plant builds on these readings next.
    result = services.commit_read_batch(actor, batch_id, {"certified": True}, defer=False)
    return int(result.get("posted_reads") or 0)


def _recompute_cr030_monthly_usage(actor: Any) -> None:
    """BR-MET-106 — state every month the SAMPLE reads support, for every
    account they belong to. Idempotent; a second call writes nothing.

    ⚠ **IT WAS SCOPED TO `CR030_A10432_READS` AND THAT LEFT THE USAGE SCREENS
    EMPTY ON EVERY OTHER ACCOUNT (`DEF-CWP-3780`, 2026-09-04).** The filter
    named one demo meter set, so a freshly seeded utility carrying **604 meter
    reads across 200 meters stated 9 months of usage** — enough for the CR-030
    walkthrough it was written for, and nothing for the customer portal's
    `CWP-033`, `CWP-034` and the home page's usage tile, which are built on
    exactly this read. A lane opening those screens on the demo would have
    found them honestly empty and reasonably concluded the screens were broken.

    **The scope is now every sample read**, which is what `BR-MET-106` says
    anyway — a month a read supports is a month that exists. The CR-030 set is
    a subset of it, so that walkthrough is unchanged.

    ⚠ **AND IT IS STILL ONLY THE SAMPLE READS.** `is_sample` is what makes
    these rows removable (`BR-TEN-062`); widening this to every read in the
    tenant would restate months over a real utility's data from a fixture
    seeder, which is not this function's business.
    """
    from apps.metering import monthly_usage_service

    account_ids = list(
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            is_sample=True,
            account_id__isnull=False,
        )
        .values_list("account_id", flat=True)
        .distinct()
    )
    for account_id in account_ids:
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
            # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
            # (this block runs inside tenancy's per-module `atomic`), so without it the
            # work already done is lost at COMMIT. NOT tidiness — do not remove.
            with transaction.atomic():
                monthly_usage_service.recompute_account(account_id, actor=actor)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W3): monthly usage was not stated for account %s "
                "(%s: %s), so the Usage tab renders those months ABSENT",
                account_id,
                type(exc).__name__,
                exc,
            )


# ── CR-068 WAVE H · ONE NAMED ACCOUNT'S OWN READING HISTORY ──────────────────
# Story:  US-CWP-040 · US-CWP-041 · US-CWP-043 — the customer portal's Usage,
#         Every reading and Meters-and-equipment screens.
#
# WHY THIS LIVES HERE AND NOT IN `apps/portal/sample_data.py`, WHICH IS WHAT
# WANTED IT:
#   1. `meter_reads` is metering's table. `apps/portal/write_points.py`'s
#      `STAFF_WRITE_MODULES` lets the portal fixture write *"through the owning
#      modules' services (never a raw write)"*, and `G81` enforces it.
#   2. `BR-TEN-057`'s tag is stricter still — *"the tag is written by THIS
#      module's own service on the sample path and by nobody else"*. A caller in
#      another app therefore cannot set `is_sample` on a metering row, so a
#      fixture that created reads from outside would create rows `BR-TEN-061`
#      can never remove. That is `DEF-WRK-4117`'s shape, avoided by
#      construction.
#
# ⚠ **IT KNOWS NOTHING ABOUT THE PORTAL.** Every figure is a parameter: the
# caller names the meter and the dial values, and this posts them through the
# pipeline a clerk drives by hand and tags what it wrote.


def seed_account_read_history(
    actor: Any,
    *,
    asset_no: str,
    service: str,
    read_method: str,
    source_detail: str,
    reads: Sequence[dict[str, Any]],
    require_all: bool = True,
) -> int:
    """Post a named meter's reading history through the FULL S28 pipeline.

    `reads` is a sequence of ``{"read_on": date, "register": str}`` — REGISTER
    VALUES, never consumptions, for the reason `_seed_cr030_demo_reads` already
    records: the product derives usage from consecutive dials, so a fixture that
    typed a consumption would be asserting its own arithmetic instead of the
    product's.

    Returns the number of reads posted. Idempotent per (asset, date), so a
    replay completes a partial run rather than double-posting it — the same key
    `_seed_cr030_demo_reads` uses, and for the same reason.

    ⚠ **`require_all` REFUSES A PARTIAL PLANT RATHER THAN REPORTING A SMALLER
    NUMBER, AND THAT IS THE POINT OF IT.** `commit_read_batch` can answer
    `status: posted_nothing` with `skipped_rows: [{reason:
    "database_refused"}]` while `batch_status` still reads `posted` — a read
    the database itself rejected, inside a batch that looks fine. The shared
    `_post_cr030_read_batch` returns only `posted_reads`, so the skip arrives
    here as a `0` and a caller that merely adds it up plants a shorter history
    and says so in a number nobody is checking against anything. On this
    fixture that silently cost a month of usage and the year-on-year figure
    built on it. A fixture that cannot plant what it planned is a fault to be
    READ (`BR-MET-015`'s posture), so it is raised by name.
    """
    posted = 0
    wanted = 0
    for read in reads:
        if models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset__asset_no=asset_no,
            read_at__date=read["read_on"],
        ).exists():
            continue
        wanted += 1
        meter = {
            "asset_no": asset_no,
            "service": service,
            "read_method": read_method,
            "source_detail": source_detail,
        }
        row = {
            "meter_id": asset_no,
            "read_date": read["read_on"].isoformat(),
            "reading": read["register"],
            "service": service,
        }
        if read.get("note"):
            row["note"] = read["note"]
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really
            # can continue. On PostgreSQL the failed statement aborts the WHOLE
            # transaction, so without it the work already done is lost at COMMIT.
            with transaction.atomic():
                landed = _post_cr030_read_batch(actor, meter, read, row)
            posted += landed
            if not landed:
                # ⚠ **A ZERO HERE IS SILENT UNLESS SOMEBODY SAYS SO.** The
                # helper logs when a row FAILS VALIDATION and says nothing when
                # the batch commits and posts nothing — which is what a
                # `database_refused` skip looks like from out here.
                logger.warning(
                    "sample data (CR-068 wave H): %s's %s reading committed a batch and "
                    "posted NO read. The likeliest cause is a date the `meter_reads` "
                    "partitions do not cover (the earliest is 2024-09).",
                    asset_no,
                    read["read_on"].isoformat(),
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.warning(
                "sample data (CR-068 wave H): %s's %s read did not post — %s: %s",
                asset_no,
                read["read_on"].isoformat(),
                type(exc).__name__,
                exc,
            )
    # ⚠ **TAGGED BEFORE ANY MONTH IS STATED, AND THE ORDER IS LOAD-BEARING.**
    # `monthly_usage_service` derives a month's own `is_sample` from its source
    # reads — `all(sample.get(rid, False) for rid in figure.source_read_ids)`.
    # Tag AFTER the restatement and the reads come out removable while the
    # twelve months they support do not, which is a half-removable fixture and
    # worse than an untagged one because it looks finished.
    _tag(
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(), asset__asset_no=asset_no, is_sample=False
        )
    )
    if require_all and posted != wanted:
        raise fixture.BlockCannotRun(
            f"{asset_no}: {posted} of {wanted} reading(s) were planted. The rest were "
            "refused — a batch can answer `posted_nothing` with a `database_refused` "
            "skip while still marking itself `posted`, and the commonest cause is a "
            "read dated before the earliest `meter_reads` partition. The history this "
            "fixture planted is SHORTER than the one it describes, so nothing built on "
            "it should be trusted; see the INFO log above for the dates."
        )
    return posted


def mark_sample_read_estimated(*, asset_no: str, read_on: Any) -> bool:
    """Say that this reading was ESTIMATED rather than walked.

    ⚠ **WHY THIS IS NOT `estimate_missing_read`, WHICH WOULD OTHERWISE BE THE
    RIGHT DOOR.** That service computes the figure from the meter's own history
    (`BR-MET-026/027/058/062`) and takes no value, so a fixture cannot ask it
    for a particular one. `US-CWP-041` §4 names the estimate exactly —
    `144,600`, corrected to `144,130` — and those two figures are what the
    story, the epic and `test_us_cwp_041_readings.py` all assert. A demo whose
    estimate was whatever the estimator happened to produce would show the right
    SHAPE under the wrong numbers, and the walkthrough could then assert nothing
    about either.
    So the reading is posted through the real pipeline like every other, and
    this states the one fact the pipeline has no way to accept: that nobody read
    the dial. It is exactly what `test_us_cwp_041_readings.four_readings` does
    (`status="estimated"`), in the module that owns the table.

    ⚠ **AND IT HAS TO RUN BEFORE THE CORRECTION.** `portal_reads` surfaces a
    correction by looking through the SUPERSEDED rows for an estimated one, so a
    row marked after it is superseded is a correction the screen will not draw —
    which is precisely the state this fixture was in when the walkthrough first
    ran, and `CWP-034` showed the corrected June as an ordinary walked reading.

    Returns whether a row was marked. It touches `status` only, on a row this
    seeder planted; the figures are not rewritten.
    """
    return bool(
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset__asset_no=asset_no,
            read_at__date=read_on,
            superseded_by_id__isnull=True,
            is_sample=True,
        ).update(status="estimated", read_method=None, source_detail=None)
    )


def correct_sample_read(
    actor: Any,
    *,
    asset_no: str,
    read_on: Any,
    value: str,
    reason: str,
    corrected_on: Any = None,
) -> dict[str, Any] | None:
    """The estimate a clerk replaced when somebody finally read the dial.

    ⚠ **THROUGH `supersede_read`, WHICH IS THE PRODUCT'S OWN DOOR**, so the
    fixture produces the shape the screen has to render rather than a shape a
    fixture invented. `BR-MET-024/053` — a correction is a NEW ROW; the original
    stays fully readable and only its two closure columns change. That door also
    restates the account's months on its way out (`BR-MET-106`: *"corrections
    RESTATE, they never edit"*), so the chart and the reading list cannot
    disagree about what the month was worth.

    Returns None when there is nothing to correct — the read is absent, or an
    earlier run already superseded it (idempotency).
    """
    original = (
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset__asset_no=asset_no,
            read_at__date=read_on,
            superseded_by_id__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if original is None:
        return None
    #: ⚠ **`.id` AND NOT `.pk`.** `meter_reads` is PARTITIONED, so its primary
    #: key is the composite `(tenant, read_at, id)` and `.pk` answers a
    #: three-tuple. `services._read_row` filters on `id=`, a plain `UUIDField`,
    #: so passing `.pk` raises *"… is not a valid UUID"* from deep inside the
    #: query builder with nothing in the message naming this call.
    result = services.supersede_read(actor, original.id, {"value": value, "reason": reason})
    if corrected_on is not None:
        # ⚠ **THE DAY SOMEBODY WENT AND LOOKED, NOT THE DAY THE SEED RAN.**
        # `supersede_read` stamps `superseded_at = now()`, which is right for a
        # clerk and wrong for a fixture: `portal_reads` composes `corrected_on`
        # from that stamp, so a demo seeded today tells the customer their June
        # estimate was corrected TODAY. `US-CWP-041` §4's sentence is *"corrected
        # to 144,130 when the meter was read on 3 July"*, and this column is the
        # only place that fact can live.
        # `superseded_at` is one of the exactly three columns B2 r8 permits
        # UPDATEing on a committed read, and this writes it in the module that
        # owns the table — the same latitude `test_us_cwp_041_readings` takes.
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(), asset__asset_no=asset_no, read_at__date=read_on
        ).exclude(superseded_by_id=None).update(
            superseded_at=datetime(
                corrected_on.year, corrected_on.month, corrected_on.day, 9, 0,
                tzinfo=dt_timezone.utc,
            )
        )
    _tag(
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(), asset__asset_no=asset_no, is_sample=False
        )
    )
    return result


def restate_sample_months(actor: Any, account_id: Any) -> Any:
    """`BR-MET-106` — state every month this account's reads support, and tag
    them.

    The sole writer, and idempotent on the lineage. Without it `CWP-033` draws
    every month ABSENT, which is true and useless — the exact state
    `DEF-CWP-3780` left the portal's usage screens in.

    ⚠ **THE TAG HAS TO BE WRITTEN HERE, BECAUSE A MONTH DECIDES ITS OWN
    `is_sample` ONCE AND NEVER REVISITS IT (`DEF-CWP-4165`).**
    `monthly_usage_service` derives a month's flag from its source reads at the
    moment it states the month — `all(sample.get(rid, False) for rid in
    figure.source_read_ids)` — and a month is stated by `commit_read_batch`, on
    its way past, from reads that by definition cannot have been tagged yet
    (the newest of them did not exist a statement earlier). Recomputing later
    does not help: `recompute_account` is idempotent on the lineage
    fingerprint, so an unchanged month is not rewritten and its stale `false`
    survives.
    **Measured on the portal demo tenant: 774 of 775 `monthly_usage` rows were
    `is_sample = false`** — every month the standard sample plant states is
    invisible to `BR-TEN-061` and can never be removed.
    So the months this account's SAMPLE reads support are tagged explicitly,
    after the restatement. Scoped to one account, and only ever to rows whose
    every source read is itself sample — a month a real read contributed to is
    left alone, which is the same predicate `monthly_usage_service` would have
    applied if it had been asked a second time.
    """
    from apps.metering import monthly_usage_service

    result = monthly_usage_service.recompute_account(account_id, actor=actor)
    sample_reads = set(
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, is_sample=True
        ).values_list("id", flat=True)
    )
    stale = models.MonthlyUsage.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id, is_sample=False
    )
    tagged = [
        row.id
        for row in stale
        if row.source_read_ids
        and all(uuid.UUID(str(rid)) in sample_reads for rid in row.source_read_ids)
    ]
    if tagged:
        _tag(models.MonthlyUsage.objects.filter(tenant_id=_tenant_id(), id__in=tagged))
    return result


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/062/066 — a HARD delete of this module's `is_sample = true`
    rows, in reverse dependency order, reporting what it RETAINED and why.

    BR-TEN-062 is what makes the reads deletable at all: *"Sample reads are the
    ONE deletion path in metering"*, and its predicate is `is_sample = true`.
    A read that has been BILLED is retained by name — hard rule 4 makes the
    invoice line that priced it immutable, so deleting the read underneath it
    would leave a bill nobody could explain.
    """
    tenant_id = _tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []

    billed = models.MeterRead.objects.filter(
        tenant_id=tenant_id, is_sample=True, lifecycle="billed"
    ).count()
    if billed:
        retained.append(
            {
                "label": f"{billed} meter read(s)",
                "reason": (
                    "already billed — the invoice line that priced them can never be "
                    "changed or deleted (CLAUDE.md hard rule 4), so deleting the read "
                    "underneath it would leave a bill nobody could explain"
                ),
            }
        )
    # ⚠ BR-TEN-062 SAYS SAMPLE READS ARE REMOVABLE AND THE DATABASE SAYS THEY
    # ARE NOT — DEF-162, filed rather than worked around.
    #
    # BR-TEN-062: *"Sample reads are the ONE deletion path in metering … the
    # metering service exposes exactly one delete entry point and its predicate
    # is `is_sample = true`."* The immutability trigger that landed with
    # BR-MET-053/054 has NO `is_sample` exception, so the DELETE is refused by
    # PostgreSQL with its own sentence: *"meter_reads is append-only: a
    # committed read is corrected by a superseding row, never deleted"*.
    #
    # The trigger wins — it is the money-adjacent guarantee and a rule doc does
    # not override a signed immutability trigger. So the reads are RETAINED and
    # NAMED (BR-TEN-066) and the contradiction is a defect somebody has to
    # rule on, not something this seeder quietly routes around.
    #
    # `meter_reads` is also PARTITIONED with a composite primary key (B2 r8 /
    # DB-7), so a queryset `.delete()` cannot collect the rows the ORM way; the
    # attempt is made as ONE statement over exactly the predicate BR-TEN-062
    # names and over nothing else.
    from django.db import connection as _connection

    removable = models.MeterRead.objects.filter(tenant_id=tenant_id, is_sample=True).exclude(
        lifecycle="billed"
    )
    pending = removable.count()
    if pending:
        try:
            with transaction.atomic():
                with _connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM meter_reads WHERE tenant_id = %s AND is_sample = true "
                        "AND lifecycle <> 'billed'",
                        [str(tenant_id)],
                    )
                    removed += int(cursor.rowcount or 0)
        except Exception as exc:  # noqa: BLE001 — DEF-162: named, never swallowed
            retained.append(
                {
                    "label": f"{pending} meter read(s)",
                    "reason": (
                        "the database refuses to delete a committed read — it is "
                        "append-only, and a correction is a superseding row "
                        "(BR-MET-053/054). BR-TEN-062 says a SAMPLE read is the one "
                        "exception and the trigger carries no such exception; the "
                        "trigger wins and the contradiction is DEF-162 — "
                        f"{type(exc).__name__}"
                    ),
                }
            )

    # CR-030 W1 T1.23 — the seeded import history goes FIRST, because
    # `import_run_rows.run_id` is `on_delete=PROTECT` and `RollbackPoint.run`
    # would hold a run open the same way (BR-TEN-061's reverse-dependency
    # order, applied to the rows this lane added).
    # CR-030 W6 T6.15 — the builds come out BEFORE the seats they stand on.
    # `work_orders.unit_id`, `connection_services.unit_id` and
    # `connections.premises_id` are all `on_delete=PROTECT`, so a unit whose
    # build is still on file cannot be deleted and would be RETAINED by name
    # (BR-TEN-066) — correct, but wrong: the build is sample data too. The
    # order inside the block is the reverse of the creation order as well:
    # orders → services → connections, and the templates last of the four
    # because `work_orders.template_id` is PROTECT.
    for label, queryset in (
        (
            "import run row",
            models.ImportRunRow.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
        ("import run", models.ImportRun.objects.filter(tenant_id=tenant_id, is_sample=True)),
        ("work order", work_tables.WorkOrder.objects.filter(tenant_id=tenant_id, is_sample=True)),
        (
            "connection service",
            work_tables.ConnectionService.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
        ("connection todo", work_tables.ConnectionTodo.objects.filter(tenant_id=tenant_id, is_sample=True)),
        ("connection", work_tables.Connection.objects.filter(tenant_id=tenant_id, is_sample=True)),
        (
            "work order template",
            work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
        (
            "service characteristic",
            work_tables.ServiceCharacteristic.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
        ("service point", models.ServicePoint.objects.filter(tenant_id=tenant_id, is_sample=True)),
        ("unit", models.Unit.objects.filter(tenant_id=tenant_id, is_sample=True)),
        ("premises", models.Premises.objects.filter(tenant_id=tenant_id, is_sample=True)),
        # CR-039 wave C task 14 — the typed owners come out AFTER the premises
        # that point at them. `premises.owner_id` is `on_delete=PROTECT`
        # (BR-MET-150: deleting a party twelve addresses point at must refuse,
        # never silently untype twelve premises), so an owner listed before its
        # premises would be RETAINED by name — correct behaviour, wrong result,
        # because the owner is sample data too. BR-TEN-061's reverse-dependency
        # order, applied to this lane's table.
        (
            "premises owner",
            models.PremisesOwner.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
    ):
        for row in list(queryset):
            try:
                with transaction.atomic():
                    row.delete()
                removed += 1
            except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
                retained.append(
                    {
                        "label": f"{label} {getattr(row, 'label', None) or getattr(row, 'address_line', row.pk)}",
                        "reason": (
                            "something you kept still references it — " f"{type(exc).__name__}"
                        ),
                    }
                )
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    tenant_id = _tenant_id()
    return int(
        models.Premises.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        # CR-039 wave C task 14 — the S8 Sample data panel counts what
        # `--remove` would take, and `--remove` takes these.
        + models.PremisesOwner.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + models.Unit.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + models.ServicePoint.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        # CR-030 W6 T6.3/T6.15 — the S8 Sample data panel counts what `--remove`
        # would take, so the four W6 tables belong in the same sum.
        + work_tables.Connection.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_tables.ConnectionService.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_tables.WorkOrder.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant_id, is_sample=True).count()
    )


def sample_read_count() -> int:
    return int(models.MeterRead.objects.filter(tenant_id=_tenant_id(), is_sample=True).count())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-256: every sample premises lands in one of the four seeded districts — `premises.area_id` was NULL on 50 of 50 live rows) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (STREET_GEO + apply_premises_geo — deterministic Austin-ballpark coordinates on the fixture plant, crc32-jittered per address, offline, isnull-guarded so an operator's pin and a replay are both safe; called at the end of seed_sample_records) · AMENDED 2026-08-24 by story-coder (CR-030 W1 T1.23 demo-seed lane — B18 §5.9.6's three `[shot]` accounts-import runs, RUN-2822's two open rejects, and the cutover seat ❄️ GT-16's migrated account occupies; `sample_account_cutover_seat` published for apps/customers' half) · AMENDED 2026-08-26 by the CR-039 wave A lane (DEF-795 — estate() resolves the tenant's backbone service + UoM through the seams; the premises block RAISES BlockCannotRun with the named reason instead of the 0 that made the defect invisible; the reads pipeline is per-service end to end and the batch tag is the tenant's own) · AMENDED 2026-08-28 by the DEF-1250 seed-reconciliation lane (a replay reconciles an already-seeded SAMPLE address's OFFER and its units' SERVICE POINTS to what the tenant now sells — BR-MET-830)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: [CR-030 W1 T1.23] the three `[shot]` import runs are DECLARED rows, not runs of the real runner — B18 §5.9.6 pins RUN-2814 at 1,251 in / 1,247 loaded because the Accounts KPI reports the same 1,247, and a 48-unit fixture cannot produce 1,247 loaded accounts by actually running the ETL; the one row whose per-account figures are ❄️ frozen (GT-16's A-12103) IS loaded through the product's own seam by apps/customers/sample_data.py · [CR-030 W1 T1.23] `file_hash` is left NULL on all three: ImportRun's own docstring makes it server-computed FROM THE BYTES (TC-2) and the fixture holds no file, so any value would be a hash of nothing · [CR-030 W1 T1.23] the cutover seat carries NO service point, so the 49th unit adds no phantom missing-read to the READY-TO-RUN July batch (the assets seeder's own argument for leaving the net meter in inventory) and BR-CUS-047's order ends '→ Accounts → opening reads' · the three UNREADABLE August meters are seeded as an ABSENCE — no row in the batch — because that is what a clerk who could not reach the meter actually hands in, and it is what gives the S25 estimation screen work to do · the DISPUTE flag is set only if metering publishes a dispute WRITE service; where it does not, the case is REPORTED and no back-door UPDATE is made · a BILLED sample read is RETAINED by name on removal (hard rule 4 makes the invoice line immutable) rather than deleted underneath its bill
# AMENDED 2026-08-25 by the SEED lane (CR-030 W6 tasks 6.3 + 6.15) — the work-order template STARTERS as BR-MET-109 reframed them (PO 2026-08-25: *"we will give them ready to use tempaltes - they will develope these templats in work order section"*), B18 §5.4.8's eight builds with their 43 units and 53 work orders, and the seats W7 task 7.12 stands on. Proved through `connection_reads.list_connections` — §5.4.1's five tiles come out of the data as `OPEN 7 · WAITING ON INSPECTION 2 · PARTLY ACTIVATED 3 · UNITS AWAITING ACTIVATION 42 · OLDEST 19 days · CON-26-0119 · permit`.
# exceptions [DEF-1250]: the premises block is no longer idempotent PER PREMISES but per SERVICE — a replay widens an already-seeded SAMPLE address's `services_available` (a UNION, never a replacement, so an operator's narrowing survives and NARROW_OFFER_PREMISE_NO keeps the hold-back that demonstrates BR-MET-119) and calls `ensure_service_point` for each sample unit's missing service. THE OFFER IS THE LOCK: assets' four container_cart assets were being refused with `metering.service_not_at_premises`, which is why the carts never landed on a later-enabled trash either. Guarded on `is_sample`. ⚠ DEF-1250's own register row says this module *seeds trash service points regardless of the flag* — untrue since CR-039 wave A (DEF-795); the row is corrected in the register.
# exceptions [CR-030 W6 T6.3/T6.15]:
#   (1) RETIRED 2026-09-05 (CR-070 wave E, `US-WRK-019` task `E4`). This exception read *"THE STARTERS ARE WRITTEN THROUGH THE MODEL, BECAUSE NO SERVICE WRITES THEM … a `create_work_order_template` service is OWED"* from 2026-08-25, and it was true for eleven days. Wave D built the service; the starters now go through `apps/work/templates_svc` — `create_draft` for the header, `replace_collection` for the `wot_details` row, and `publish`, which is the ONE write (`BR-WRK-011`) and the only thing that allocates `ST-{0000}`. The 24 rows are PUBLISHED v1 bundles, not inert drafts, because `BR-WRK-016` proposes only from published templates and a drafted starter is one New Connect step 6 would never offer. **The sentence is retired here rather than left standing**, because a stated absence goes in the commit that makes it untrue (hard-won law 1).
#   (2) THREE SERVICES CARRY NO GATE STARTER AND EACH SAYS WHY (`W6_UNGATED_STARTERS`, asserted as data): sewer gates on the WATER service it derives from, which is not one of its own orders; solar gates on *permission to operate*, which names NONE of the four steps §8.1 draws for it, so flagging one would be this seeder deciding what authorises a customer's export; storm water has **0** orders at all. ⚠ Solar is therefore UNGATED in the seeded catalogue and a ruling is owed — REPORTED, not chosen.
#   (3) NO BATCHING RULE IS SHIPPED. BR-MET-109 makes `CON-26-0117`'s 5-of-7 an OUTCOME of the tenant's templates, so the seven orders are DECLARED one per line of §8.2's breakdown and this module holds no arithmetic that turns 25 units into 7.
#   (4) THE DATES ARE OFFSETS FROM THE TENANT'S OWN TODAY, decided at seed time and persisted (`w6_anchor_on()`) — DEF-629's ruling applied again, because `OLDEST · 19 days` is `now - submitted_at` and a literal date would be right for one day and drift for ever. `DRAWN_AS_OF` (2026-08-24) is DERIVED from the four time-windowed tiles, not picked; the arithmetic is in the block header.
#   (5) `submitted_at` IS THE ONE COLUMN WRITTEN OUTSIDE A DOOR. `_stamp` takes it from the wall clock, no service accepts a submission date, and the drawn `19 days` needs one. It is a date and not a state; `connections.state` is never written here — `refresh_connection_state` is its only writer and every door called above calls it.
#   (6) THE EIGHT ARE SEEDED IN ASCENDING SEQUENCE, NOT IN B18's ORDER, AND THAT IS A BUG THIS CAUGHT. §5.4.8 is sorted by TARGET DATE, so its numbers run 110·119·121·126·**117**·128·**124**·**122**; a number series moves FORWARD only (BR-TEN-035), so seeding in the drawn order produced `CON-26-0127`/`CON-26-0129`/`CON-26-0130` on the first run.
#   (7) NO BUILD CARRIES ITS SERVICE-REQUEST LINK. §5.4.8 links `CON-26-0117` to `SR-26-0043` and §5.4.9 heads `CON-26-0110` *"from request SR-26-0018"*; `apps/metering/seams.py` publishes no service-request read and metering may not reach into customers' ORM (B1/B8). **A seam is OWED**, and until it exists the list's `request #` search leg finds none of these rows.
#   (8) FOUR MORE DRAWN THINGS ARE NOT SEEDED AND EACH NAMES ITS OWNER (`W6_ABSENCES`): the Charges tab's four coded lines and the `$150.00 per residential unit` deposit POLICY (no posting path — OQ-379); the Assets tab's installed meters and sub-meter links (assets' write, no seam from here); and BR-MET-114's `Outstanding work` items, which a HUMAN marks — a seeder is not a human and marking them would put the system's words in a person's mouth, which is the half of that ruling worth protecting.
#   (9) THE W6/W7 SEATS JOIN NO ROUTE AND NO BILL RUN (seeded after `_ensure_cycle_and_route`, the estate's own argument), and a BUILD's unit carries no service point and no plan — §5.4.9: *"A NEW CONNECT ENDS WITH UNITS VACANT, SERVICE OFF AND NO ACCOUNT."* The W7 seats that take an account carry both.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
