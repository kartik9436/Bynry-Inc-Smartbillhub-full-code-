# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
#           it, remove it)   Screens: S8 (Sample data panel), S62
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 (the sample set reaches money) ·
#           BR-TEN-057 (the tag is a column on the owning row) · BR-TEN-058
#           (reference vocabulary is NOT sample data) · BR-TEN-061 (removal
#           order) · BR-TEN-063 (atomic per module, idempotent, audited) ·
#           BR-TEN-065 as AMENDED 2026-08-16 (sample accounts are ACTIVE) ·
#           BR-RAT-015 (sewer = % of water usage-charge dollars) · BR-RAT-025
#           (plan-as-bundle) · BR-MET-002/003 (unit labels · services ⊆
#           enabled) · BR-RAT-090 (cart count observed — CR-028 carts, DEF-496)
#           · BR-AST-047 (valuation on the device record — CR-028) ·
#           CLAUDE.md rule 2 (money) · rule 3 (consumption carries
#           its unit)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  apps/rating · apps/metering · apps/assets · apps/customers ·
#           apps/billing · apps/payments — each reads THIS declaration and
#           creates only its OWN rows through its OWN service functions.
# ───────────────────────────────────────────────────────
"""The demo tenant, DECLARED — 08-qa/04-fixtures/02-demo-tenant-spec.md as data.

WHY THIS LIVES IN `core/` AND NOT IN A MODULE
---------------------------------------------
Six modules have to agree about one utility. Metering owns the premises and
units, assets owns the meters that sit on them, customers owns the accounts
that occupy them, rating owns the plans they are billed on, billing owns their
bills and payments owns the money against those bills. Not one of those modules
may read another's tables (B1 / BR-TEN-013), so the SHAPE of the fixture cannot
live in any of them without every other one importing across a boundary.

What lives here is therefore a DECLARATION and nothing else: plain data, no
Django import, no ORM, no service call. Each module imports the part it owns
and creates its rows through its own audited service functions. The rule that
makes this fixture worth having is spec §rule 4:

    *"Seed through the services a clerk's click uses, never by writing rows
    directly. A fixture built by direct insert proves the tables exist and
    proves nothing about the product."*

WHERE EVERY MONEY FIGURE COMES FROM — none of them is invented
--------------------------------------------------------------
[W] `04-docs/05-modules/07-billing/08-worked-examples.md` §1, the PO-verified
    billing workbook. Residential Standard: water tiers 0–5 kgal $4.00 /
    5–15 $6.50 / 15+ $8.00 · water base $8 · **sewer 90% of the water VOLUME
    at $5.0000/kgal** (`CR-081`, PO re-sign 2026-09-08; it read *"sewer 40% of
    water usage-$"* until that date) · trash flat $18. Small Commercial: water
    flat $5.20/kgal · water base $15 · sewer 90% on the same rate.
[F] `apps/tenancy/fixtures/lookup_defaults.json` — the platform reference
    fixture: the two tax jurisdictions (6.25% state, 2.00% local) and the
    charge codes.
[GT] B5 ❄️ FROZEN, GT-17 RE-SIGNED 2026-09-08 (HUMAN-GUIDE §6). GT-17 (= WE-1)
    is the reference bill and this fixture REPRODUCES it on purpose: unit 1
    consumes exactly **8 kgal**, so its water lines are 5 × 4.00 = 20.00 and
    3 × 6.50 = 19.50, and **sewer is 90% × 8 kgal = 7.2 kgal at $5.0000 =
    $36.00**. `tests/test_us_ten_019_sample_records.py` asserts it, so a fixture
    that drifts off the frozen number goes RED.
    ⚠ It read *"the basis is 39.50 and sewer is 40% × 39.50 = 15.80 — the
    ratified figure the PO signed on 2026-08-16"* until `CR-081`. That figure
    was ratified and is now SUPERSEDED by a later signature from the same
    authority; it is quoted rather than deleted so a reader meeting `$15.80` in
    an older document can date it.

THREE PLACES THIS FIXTURE DEPARTS FROM THE SPEC AS WRITTEN, each with its reason
-------------------------------------------------------------------------------
1. **SEWER IS A TRUE PERCENTAGE OF WATER, not flat.** The spec says *"Until it
   lands, seed sewer FLAT and say so on the plan"*. It landed —
   `apps/rating/pricing/models/percent_of_service.py`, 2026-08-16 — and the PO
   ratified its figure the same day (**$15.80 on $39.50**, deliberately NOT
   counting the $8.00 base, which would give $19.00). The spec sentence is
   amended in the same commit as this file.
   ⚠ **AND THE SPEC'S SENTENCE IS HALF RIGHT AGAIN SINCE `CR-081`.** A sewer
   schedule is still a `percent_of_service` and still reads no register — but it
   now carries a FLAT RATE of its own ($5.0000/kgal) which it applies to 90% of
   the water volume. So it is a percentage AND a flat price, and neither half
   alone bills anything.
2. **48 water meters, not 96.** The spec's 96 is *"Water + sewer per unit"*,
   written when sewer was going to be FLAT and therefore metered. A sewer line
   priced as a percentage of water reads no register — it derives from
   water. (`CR-081` gives it a QUANTITY, 90% of water's, and still no meter:
   the quantity is borrowed, never measured.)
   Seeding 48 sewer meters that are never read would put 48 phantom
   missing-reads into every bill run and drown the THREE deliberately
   unreadable meters the spec asks for, which is acceptance item 8. So one
   water meter per unit, plus the one replacement the spec's case 3 needs.
3. **44 premises AND 48 units cannot both hold with the stated mix.** One
   6-unit block contributes +5 over its premises and two duplexes +1 each, so
   units would exceed premises by 7 and the spec asks for 4. Three premises are
   therefore seeded with NO unit yet — newly platted, no service — which is a
   real state of a growing utility and makes both headline counts true. The
   arithmetic is written down here so the next reader does not rediscover it.

WHAT IS NOT SEEDED, AND WHY — never a silent gap
-------------------------------------------------
The spec's third rate plan is *"Senior (a discounted variant)"*. **No signed
figure states the discount**, and spec rule 7 is explicit: *"Where a rule is
unsigned, the seeder stubs and mints a question rather than choosing a number
that then looks official."* So it is NOT seeded, the question is **OQ-240**, and
the two plans that ARE seeded are structurally different from each other
(inclining tiers vs a flat rate), which is what the third plan was there to
give — something to compare.
"""

from __future__ import annotations

import calendar
import os

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: Bumping this re-seeds nothing by itself — every seeder is idempotent on the
#: natural key. It exists so a run ledger can say WHICH fixture a tenant carries.
#: `.2` — CR-010 Part-10 (PO 2026-08-17): one month billed, July ready-to-run,
#: sub-meters + BTM devices, the live payment plan, two sample staff users.
#: `.3` — CR-028 AST-W0-T1 (PO 2026-08-22, B16 §9): the r10 registry shape —
#: trash carts (DEF-496 closed: 3 × $15.00 = $45.00 finally walks), a master
#: meter with subs, a net meter, all five BTM device kinds, aged inventory,
#: valuation on every new seed (BR-AST-047).
#: `.4` — CR-030 W2/W3/W4 (PO 2026-08-24, *"so add them"*): the DEMO ESTATE —
#: eight premises and thirteen units the design's own screens name, the eight
#: `[shot]` account shapes (2.10), `A-10432`'s detail (3.12) and the eight
#: cross-wired service requests (4.14). Additive: the 44/48/48 plan above is
#: untouched.
FIXTURE_VERSION = "silver-creek-2026.08.4"

UTILITY_NAME = "Silver Creek Water"


class BlockCannotRun(RuntimeError):
    """A seeder block that CANNOT DO ITS JOB, saying so in one sentence.

    Added 2026-08-16 for DEF-166 and DEF-167, which are the same mistake seen
    from two sides: billing reported *"Bills — 95 rows OK"* over 95 DRAFTS that
    the release had refused to issue, and payments then reported *"OK … 0
    row(s)"* because it could see no issued bill to pay. Both lines were green
    and neither was true.

    **The rule this type exists to enforce is already the repo's, for seams:**
    an unanswerable read REPORTS that it cannot answer and NEVER answers 0.
    A seeder block has exactly three states and they must render differently —

      * **wrote N** — N rows, by name;
      * **nothing to do** — the fixture asked for none, which is a 0 that is
        CORRECT and says so;
      * **COULD NOT RUN** — raise this, naming the reason and the UPSTREAM
        block responsible where there is one. Never a 0.

    The orchestrator renders the message, so the sentence carried here is what a
    human reads on the Sample data panel and on the command line. Write it for
    them: what could not happen, and what has to be true before it can.

    ⚠ **`code=` IS OPTIONAL AND IS NOT THE SENTENCE — CR-039, 2026-08-26.**
    The sentence is for a person; the code is for COUNTING, across tenants,
    later ("Can we write all failed job detialsin audit log of that tenant
    along wt=ith error code so that we can trace it back later?" — PO). A
    seeder that knows exactly WHICH precondition it lacked may declare a code
    from `apps.tenancy.sample_errors.CATALOGUE` here, at the raise site, where
    the fact is actually known. Leave it off and the orchestrator derives a
    coarse code from the exception TYPE, which is the honest default: the one
    thing it must never do is mine a code out of this message with a regex, and
    this parameter is what makes that unnecessary.

    An unregistered code is IGNORED rather than stored — a code with no entry
    in that catalogue has no audit-safe sentence, and `audit_log` is
    append-only (BR-AUD-002).
    """

    def __init__(self, *args: Any, code: str | None = None) -> None:
        super().__init__(*args)
        self.code = code


#: The three services this fixture prices. A tenant that has not enabled one
#: gets the rest and is TOLD which it did not get, by name — never a silent
#: skip (BR-TEN-060, DEF-016's prevention).
FIXTURE_SERVICES: tuple[str, ...] = ("water", "sewer", "trash")

#: CLAUDE.md rule 3 — consumption never travels without its unit.
WATER_UOM = "kgal"

# ══════════════════════════════════════════════════════════════════════════
# CR-039 WAVE A · THE ESTATE IS A SHAPE; THE SERVICE IS A PARAMETER (DEF-795)
# ══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THE DEFECT THIS CLOSES, MEASURED.** `FIXTURE_SERVICES` above is
# `water · sewer · trash` and every meter, every register value and every read
# batch below said `water` in a literal. `apps/metering/sample_data._fixture_
# services()` intersects that tuple with the tenant's ENABLED services, so an
# **electric + gas utility signed up successfully and received NOTHING**: the
# intersection was empty, the premises block returned an honest `0`, and
# `seed_sample_reads` returned early on `if "water" not in enabled`. Correct
# behaviour — a seeder must never plant a service the utility does not sell —
# and completely invisible, because a `0` with a reason nobody reads looks
# exactly like a tenant that never asked. The PO met it on 2–3 real tenants:
# *"this data is not getting updaloaded in the system"*.
#
# **THE FIX IS NOT TO WEAKEN THE REFUSAL. IT IS TO MAKE THE ESTATE FIT.** The
# 44 premises / 48 units / one-meter-per-unit / three-months-of-reads SHAPE is
# one description; WHICH service it is expressed in is a parameter resolved
# from the tenant. An electric utility gets 48 electric meters reading **kWh**,
# a gas utility gets 48 gas meters reading **ccf** (**it read `therm` until
# 2026-09-02** — `BR-TEN-1180` / the PO-filed `DEF-3230` swapped the seeded gas
# pair so the register agrees with the signed `$1.15/ccf`; corrected here
# 2026-09-07, `DEF-MET-4502`), and a water utility gets
# byte-for-byte what it got before this change — asserted, not hoped
# (`tests/test_cr039_wave_a_service_shaped_estate.py`).
#
# **NOTHING HERE INVENTS A UNIT.** The UoM is the tenant's own seeded default
# (`apps.tenancy.services.SERVICE_DEFAULT_UOMS` → the `tenant_services` row,
# read through the owning module's seam), never a literal chosen here. A
# service whose tenant declares no primary unit is **REPORTED BY NAME AND NOT
# SEEDED** — CLAUDE.md rule 3 has no branch that assumes one, and metering's
# own validation errors `unit_missing` on exactly that row.

#: The services this fixture hangs a REGISTER on. **EVERY ONE THE TENANT SELLS
#: GETS ITS OWN METER, ITS OWN READINGS AND ITS OWN BILL LINE (`CR-062` group C,
#: PO statement (8), 2026-09-02)** — the order below is the order they are
#: seeded in, and being second no longer means being dropped.
#:
#: ⛔ **WHAT THIS TUPLE MEANT UNTIL 2026-09-02, AND WHAT IT COST.** It was the
#: order this fixture PREFERRED a single backbone in: `estate_plan` took the
#: first enabled entry and refused every later one with `_NOT_THE_BACKBONE`
#: (*"this fixture declares ONE register per unit … seeding a second metered
#: service would double the ready-to-run billing month"*). Measured on
#: PostgreSQL 16: a tenant selling **electric + water + sewer** produced 95
#: issued invoices, 70 premises, 70 accounts and **0 of 17 failed seeding
#: blocks** — every count green — with **electric on none of those 95 bills**,
#: not even its signed `$12.00` monthly base. 48 units × `$12.00` is **`$576.00`
#: a month absent from the documents**. The PO was shown that finding and ruled:
#: *"this is not correct - you cannot drop electricty or gas - can you tell me
#: what corrections you will ahve to do"*. The demo-size argument was honest and
#: is overruled: a utility that sells electric and sees no electric anywhere has
#: a broken product, not a slow demo.
#:
#: ⚠ **WATER IS STILL FIRST AND STILL DELIBERATELY NOT IN CATALOG ORDER** (the
#: catalog seeds
#: electric first — `apps/tenancy/migrations/0001_initial.SERVICE_SEED`). Every
#: signed money figure this fixture reproduces is a WATER figure: GT-17 ❄️'s
#: `$39.50` usage basis and `$15.80` sewer line stand on unit 0 consuming
#: exactly 8 kgal. The FIRST entry is what the awkward cases hang on (three
#: unreadable meters, one disputed read, one meter replaced mid-history —
#: `CR-062` judgment 4) and what names the sample plan, so a water tenant's
#: demonstrations and its plan copy are byte for byte what they were. If catalog
#: order chose it, the very common `electric + water` tenant —
#: `tests/test_us_ten_helpers.brazosbend_payload`, and every test built on it —
#: would move its ❄️ figures onto an electric register. So: **if a tenant sells
#: water, water is the first metered service**, exactly as it has always been.
#:
#: `sewer` and `trash` are NOT here: sewer reads no register at all (BR-RAT-015
#: prices it as a percentage of the water usage charge) and trash is measured
#: by a COUNT of the unit's carts (BR-RAT-090), not by a dial.
#:
#: ⚠ **`storm_water` LEFT THIS TUPLE ON 2026-09-02 — `DEF-3231`, closed by
#: `CR-062` C9.** The PO ruled the same day that storm water is billed on the
#: SIZE OF THE PROPERTY and not on a dial — *"Storm water - it is capacity based
#: not unmetered , capaicyt is decided based on sizes of propoerty"* — and
#: `apps/tenancy/services.SERVICE_DEFAULT_UOMS` was corrected that morning to
#: seed it `billing_basis=capacity` in `ERU`. This file went on planting an
#: `SD-` meter and three months of readings for it, so the demo tenant
#: contradicted its own declaration: `selectors.unmetered_service_codes()`
#: returned storm water, the run priced it by an asset count, and the fixture
#: was still writing a register nobody would read. **No money moves** — the
#: storm-water usage line was `$0.00` on both paths, because nothing has priced
#: it yet — which is exactly why the contradiction was invisible to a bill
#: count and why `tests/test_cr062_c_every_metered_service_gets_its_meters.py`
#: asserts the two lists against the seed map instead.
#: ⚠ **`thermal_heat` LEFT THIS LIST ON 2026-09-07 (`CR-080`), AND IT IS THE
#: SECOND TIME A SERVICE HAS MOVED FROM HERE TO `CAPACITY_ESTATE_SERVICES` FOR
#: STORM WATER'S EXACT REASON.** PO verbatim: *"connected tonnage - it is
#: capacity not metering; i will ahve 100 tonne or 200 tonne etc"*. A thermal
#: tenant used to get **48 `TH-` meters, an opening read and three months of
#: readings**; it now gets a service point per unit with its connected tonnage
#: recorded on the unit, and no register at all. `SERVICE_METER_PREFIX`,
#: `CONSUMPTION_SCALE`, `METERED_USAGE_PRICES`, `BACKBONE_BASE` and
#: `SEASONAL_SHAPE` each lost their thermal entry in the same commit, for the
#: reason `storm_water` lost its four: a number describing a reading nobody
#: takes is worse than no number.
METERED_ESTATE_SERVICES: tuple[str, ...] = (
    "water",
    "electric",
    "gas",
)

#: The two services that ride ALONGSIDE a water backbone and are billed without
#: a register of their own. They are the rest of `FIXTURE_SERVICES`, and they
#: are listed separately because their relationship to the backbone is a RULE,
#: not a preference: `sewer` needs `water` (BR-RAT-015 — a percentage of the
#: water usage charge has no basis without one) and `trash` is priced by the
#: cart count `apps/assets/sample_data` seeds (BR-RAT-090).
COMPANION_ESTATE_SERVICES: tuple[str, ...] = ("sewer", "trash")

#: **THE CAPACITY SERVICES THE ESTATE CAN SHAPE — `DEF-2396`, closed by the PO's
#: three-value declaration of 2026-09-01.**
#:
#: ⚠ **MEASURED BEFORE THIS CONSTANT EXISTED, ON POSTGRESQL 16.13, one tenant
#: per service through the real signup service: a solar-only, a broadband-only
#: and a battery-only utility each received ZERO premises, ZERO units, ZERO
#: service points, ZERO accounts and ZERO bills, with 14 of 17 seeding blocks
#: failed.** The refusal was honest — `_NOT_IN_THE_SHAPE`, *"this fixture has no
#: estate shape for it"* — and it was the whole product for those three
#: utilities. Water on the same run gave 95 issued bills and 0 failed blocks.
#:
#: **WHAT MAKES THE SHAPE DERIVABLE RATHER THAN INVENTED.** The PO ruled on
#: 2026-09-01 (`DEF-2409`) that a service declares how it is billed in THREE
#: values — **metered · share of another service · capacity** — and the ruling
#: maps these three, with **trash**, to **CAPACITY**: they bill on a
#: CHARACTERISTIC rather than on consumption (`BR-MET-104`, `BR-MET-108`), and
#: `BR-TEN-170` names each one — *"broadband by the TIER BOUGHT (Mbps), solar by
#: INVERTER CAPACITY (kW DC), battery by ITS RATING (kW/kWh)"*.
#:
#: **SO THE SHAPE IS ALREADY IN THIS FILE AND IS TRASH'S.** A capacity service
#: rides on the unit with NO register of its own, exactly as trash does, and is
#: declared unmetered below so `BR-MET-710` answers `service_not_metered` rather
#: than demanding a read. Nothing new is described: `COMPANION_ESTATE_SERVICES`
#: is kept separate because its two members carry RULES about the backbone
#: (sewer needs water — `BR-RAT-015`; trash is priced by the cart count —
#: `BR-RAT-090`) and these three carry none. They ride on whatever estate the
#: tenant's own services produce, including none at all — a capacity-only tenant
#: gets an estate with no backbone, which is exactly what a trash-only tenant
#: has got since `DEF-2414` and what its 96 issued bills were measured on.
#:
#: ⚠ **NO PRICE, NO CHARACTERISTIC AND NO SIZE IS SEEDED FOR ANY OF THEM, AND
#: THAT IS THE RULING AND NOT A GAP.** `OQ-370` — *which characteristic keys
#: does each capacity service have, and in what units* — is OPEN, so a seeded
#: `kW DC` or `Mbps` figure would be this fixture choosing the answer. It does
#: not have to: `BR-MET-108` as amended by the PO on 2026-08-25 rules that an
#: absent characteristic **bills as ZERO** (*"Bill it as zero"*), never refuses,
#: and the mechanism that reaches a bill today is `BR-RAT-090`'s OBSERVED COUNT
#: — `assets.billable_asset_count` answers **0** for a unit that has a service
#: point and no assets, which `metering.selectors._stamp_asset_count` stamps on
#: the row as a real, billable quantity. That is the same branch that puts
#: `CART_UNIT_WITH_NONE`'s **$0.00 on an ISSUED bill**, and it is why the zero
#: is stamped and surfaced rather than silent. A count that is UNAVAILABLE still
#: stops the bill (`asset_count_unavailable`) — the two are different facts and
#: this change keeps them different.
#:
#: ⚠ **`storm_water` JOINED THEM ON 2026-09-02 (`CR-062` C9, closing
#: `DEF-3231`).** It was a METERED service in this fixture and a CAPACITY one in
#: the seed map, eight days apart in two modules, with nothing comparing them.
#: It rides here for the same reason the other three do and on the same terms:
#: no register, no reading, a service point on the unit, and its quantity
#: observed from what is installed. Its price and its per-property sizing are
#: `CR-062` groups D and E and are NOT this list's business.
CAPACITY_ESTATE_SERVICES: tuple[str, ...] = (
    "solar",
    "broadband",
    "battery",
    "storm_water",
    # ── CR-063 · FIRE, THE ELEVENTH SERVICE (PO 2026-09-02) ─────────────────
    # *"We will need Fire as utility Service - Capacity based - this will behave
    # exactly like trash"*. It rides here on the same terms as the other four:
    # no register, no reading, a service point on the unit, and its quantity
    # observed from what is installed.
    #
    # ⚠ **WITHOUT THIS LINE FIRE IS REFUSED BY NAME AND THE REFUSAL IS THE
    # CORRECT ONE**, which is why the line is the whole of task C1. A code in
    # the platform catalogue and in no list here meets `_NOT_IN_THE_SHAPE` —
    # *"this fixture has no estate shape for it"* — and `test_service_billing
    # _coverage` records that sentence as the one the ELEVENTH service would hit.
    # An honest named refusal, and a fire tenant with nothing to bill.
    #
    # ⚠ **FIRE IS NOT LIKE SOLAR HERE EVEN THOUGH IT SITS BESIDE IT.** Its four
    # neighbours are billed on the SUM of installed capacity; fire is billed on
    # the COUNT, exactly as trash is (`BR-RAT-090`, and see
    # `tenancy.service_size_classes` for the arithmetic). What this list decides
    # is only whether a service needs a metered backbone — fire does not — and
    # that question has the same answer for both shapes.
    "fire",
    # ── CR-080 · THERMAL/HEAT, ARRIVING FROM THE OTHER LIST (PO 2026-09-07) ──
    # *"connected tonnage - it is capacity not metering; i will ahve 100 tonne
    # or 200 tonne etc"*. It was in `METERED_ESTATE_SERVICES` until that day.
    #
    # ⚠ **IT SUMS LIKE SOLAR, AND ITS QUANTITY COMES OFF THE UNIT LIKE STORM
    # WATER'S — the only member here that does both.** `capacity_uom_for_
    # service("thermal_heat")` answers `"ton"` (so it sums rather than counts,
    # unlike trash and fire) and `connections.unit_capacity_key("thermal_
    # heat")` answers `"connected_capacity"` (so the tonnage is a unit fact
    # rather than a device, unlike solar, battery and broadband). Nobody
    # installs a ton: a connected tonnage is the size of the building's service
    # connection, and the chiller is the utility's, in the plant.
    "thermal_heat",
)

#: **WHICH OF THIS FIXTURE'S SERVICES THE SEEDED TENANT DECLARES UNMETERED —
#: `BR-RAT-081`, and the fix for `DEF-2414` (PO ruling 2026-09-01).**
#:
#: PO verbatim: *"we will ahve to set in seeder as well as in setting the sizes
#: also on Units - so it works properly - please evaluate and fix it"*. The
#: SETTINGS half already existed (`SettingsServicesTab`'s metered/unmetered
#: control writes `tenant_services.metered` through `set_service_metered`); the
#: SEEDER half did not, and this constant is it.
#:
#: ⚠ **WHAT IT COST TO LEAVE THIS UNSAID, MEASURED ON POSTGRESQL 16.** A utility
#: that ticked Trash at signup got **ZERO bills — not fewer, none.** 94 of 94
#: account/period pairs were refused `connection_size_unresolved` and **8 of the
#: 17 seeding blocks failed**, because `tenant_services.metered` ships `True`
#: for every service (deliberately — `BR-RAT-081` makes the safe default the one
#: you do NOT type) and NOTHING ever set it False for the one service this
#: fixture prices by counting equipment. The identical run with this declaration
#: in place produces **47 invoices and 0 failed blocks**.
#:
#: ⚠ **AND PLANTING BINS WOULD NOT HAVE FIXED IT — MEASURED, BECAUSE IT WAS THE
#: FIRST THING TRIED.** Giving the seeded carts a `size_class` moves the
#: refusal one branch down, from `connection_size_unresolved` to
#: `meter_multiplier_not_published_to_billing`: a cart on a trash service point
#: makes metering answer `no_read` rather than `no_meter`, so `DEF-2875`'s
#: no-meter tolerance does not fire and the adapter demands a multiplier from a
#: device that has no register. **Still zero bills.** The DECLARATION is what
#: routes trash away from both questions — `BR-MET-710` answers
#: `service_not_metered` for a declared-unmetered point whether or not carts
#: stand on it, and `BR-RAT-090`'s count becomes the quantity.
#:
#: **THE THREE RATIFIED CART CASES ALL LAND, AND THAT IS THE POINT:** the
#: walkthrough unit's `3 x $15.00 = $45.00` (`CART_UNIT_WITH_THREE`), its
#: neighbour's `$15.00`, and `CART_UNIT_WITH_NONE`'s **`$0.00` ON AN ISSUED
#: BILL** — `BR-RAT-090` in terms, *"'no carts recorded' and 'zero carts' are
#: different facts and only one of them is billable"*. The zero-cart unit is
#: preserved AND billable, which no arrangement of planted bins can deliver.
#: `GT-17`'s reference unit is untouched: water `$39.50`, sewer `$15.80`.
#:
#: ⚠ **`sewer` IS DELIBERATELY NOT HERE, AND THE OMISSION IS THE DECISION.**
#: Sewer reads no register either (`BR-RAT-015` — a percentage of the water
#: usage charge), so on the plain meaning of the word it belongs. It is left out
#: because it is already billed CORRECTLY through a different pair of branches
#: that were built for it and measured on it — `DEF-2851`'s ruled-sizeless
#: register and `DEF-2875`'s no-meter tolerance — and declaring it unmetered
#: would route it into `BR-RAT-090`'s ASSET COUNT instead, where a sewer
#: connection has no assets and the count is 0. Trash is priced by counting
#: things and sewer is priced by a percentage of other money; only the first is
#: what this declaration means. **No defect asks for sewer to move, so it does
#: not move.**
#:
#: ⚠ **THE THREE CAPACITY SERVICES JOINED 2026-09-01 (`DEF-2396`), AND FOR THE
#: SAME REASON TRASH IS HERE.** The PO's `DEF-2409` ruling maps solar, broadband
#: and battery to **CAPACITY**, and today's column is still `BR-RAT-081`'s
#: boolean, so the non-metered side is the value that mapping requires — the
#: enum lane inherits a correct row instead of one it has to migrate, which is
#: the argument `DEF-2414` already recorded for trash. Without it the three
#: would be seeded with a service point, declared METERED by the column's safe
#: default, and refused on every account for want of a read and a connection
#: size: an estate that exists and still bills nothing, which is a worse answer
#: than the honest refusal this change replaces.
UNMETERED_ESTATE_SERVICES: tuple[str, ...] = ("trash", *CAPACITY_ESTATE_SERVICES)

#: Asset-number prefix per backbone service. **`water` → `W` is load-bearing**:
#: `W-5000 … W-5047`, `W-9011` (the case-3 replacement) and `W-5100/W-5101` (the
#: inventory spares) are the numbers a water tenant already carries, are pinned
#: by `tests/test_us_ten_019_sample_records.py`, and are what `seed_sample_reads`
#: names in every staged row. A prefix change on water would re-seed every
#: existing tenant's register under new serials.
#:
#: ⚠ **EVERY PREFIX HERE IS NOW LIVE ON ONE TENANT AT ONCE (`CR-062` C4).** The
#: estate plants a meter per unit PER metered service, so an electric + water +
#: gas utility carries `W-5000…`, `E-5000…` and `G-5000…` side by side. The
#: numbers do not collide and nothing renumbers: the SERIAL is
#: `<prefix>-<5000 + unit index>`, so the prefix is what separates two meters on
#: one unit and it has been a parameter since CR-039 wave A.
#:
#: ⚠ **`storm_water` → `SD` WAS WITHDRAWN 2026-09-02 (`CR-062` C9,
#: `DEF-3231`).** Storm water is capacity-billed and reads no register, so a
#: meter serial for it named a device the fixture must not plant.
#: ⚠ **`thermal_heat` → `TH` WAS WITHDRAWN 2026-09-07 (`CR-080`)**, for the
#: same reason `SD` went: thermal is capacity-billed on connected tonnage now
#: and reads no register, so a meter serial for it named a device the fixture
#: must not plant. A thermal tenant used to receive 48 `TH-5000…TH-5047`
#: meters; it receives none.
SERVICE_METER_PREFIX: dict[str, str] = {
    "water": "W",
    "electric": "E",
    "gas": "G",
}

#: How many of the declared shape's units one unit of the backbone is worth.
#:
#: ⚠ **THIS IS FIXTURE AUTHORSHIP, NOT SIGNED LAW, AND IT PRICES NOTHING.** The
#: consumption SHAPE — unit 0's flat 8, the commercial units' larger draw, the
#: ±1 monthly drift — is declared once in `water_consumption_kgal` and scaled
#: by an integer here so that a demo estate reads in figures the utility
#: recognises: a household that uses 8 kgal of water a month uses roughly 800
#: kWh and 40 ccf of gas, and an electric utility handed a meter reading **8 kWh
#: a month** would rightly conclude the demo is broken. (**This said *"40
#: therm"* until 2026-09-07** — `DEF-MET-4502`. The seeded gas register has read
#: `ccf` since `BR-TEN-1180` on 2026-09-02; the NUMBER did not move, only the
#: unit it is quoted in.)
#:
#: **No money moves on any of these, and that sentence survived `DEF-2397`.**
#: ⚠ **AMENDED 2026-09-01 — IT USED TO READ *"`apps/rating/sample_data` seeds
#: schedules for water, sewer and trash and for nothing else"*, AND THAT WAS THE
#: DEFECT IT WAS DESCRIBING.** Rating is service-shaped now: a non-water
#: backbone gets a residential and a commercial schedule of its own. What has
#: NOT changed is the half this note was really about — the SHAPE is declared
#: once and scaled, and this scale still decides no money.
#: ⚠ **AMENDED 2026-09-07 (`DEF-RAT-4516`) — THE SENTENCE THAT WAS HERE IS NOW
#: FALSE OF EVERY METERED SERVICE.** It read *"there is still no signed USAGE
#: figure for an electric, gas or storm-water tariff that fits the single
#: register this fixture plants"*, and `OQ-1290` is CLOSED: electric took
#: `ELECTRIC_TIERS` and thermal `$0.045` under `CR-062` (2026-09-02), storm
#: water is capacity-billed at a RULED zero (`BR-MET-108`), and gas takes the
#: workbook's signed `$1.15/ccf` from 2026-09-07. All four metered services
#: price their usage now, so no backbone usage line is `$0.00` any more.
#: **Water is 1: the frozen numbers do not move.**
#: The day `OQ-1290` closes, this scale is part of what has to be ratified with
#: it — it is flagged, not silently official.
#: ⚠ **`storm_water` WAS WITHDRAWN 2026-09-02 (`CR-062` C9, `DEF-3231`).** A
#: consumption scale for a service that reads no register is a number describing
#: a reading nobody takes.
#:
#: ⚠ **AND THESE SCALES NOW APPLY SIDE BY SIDE ON ONE TENANT (`CR-062` C6).** An
#: electric + water utility's unit 0 reads **8 kgal** on `W-5000` and **800 kWh**
#: on `E-5000` in the same month, from one shape scaled twice — which is the
#: whole reason this constant exists, and it has never had two claimants at once
#: before. Water is still 1, so the ❄️ figures do not move.
#:
#: ⚠ **`thermal_heat` WENT 5 → 500 ON 2026-09-02 (`CR-062` ADDENDUM J1), AND
#: THAT IS THE FLAG ABOVE COMING DUE RATHER THAN A CORRECTION.** This docstring
#: has always said the scale *"prices nothing"* and that *"the day `OQ-1290`
#: closes, this scale is part of what has to be ratified with it"*. **Task E6
#: priced thermal at `$0.045` per ton-hour on the same day**, so the flag fell
#: due in the same change that caused it — and until it was raised a seeded
#: thermal customer read about **45 ton-hours** a month and billed **`$2.02`**,
#: where a real chilled-water building uses nearer **4,000 ton-hours**.
#:
#: **THE USAGE MOVES AND THE RATE DOES NOT, and that is the decided half.**
#: `$0.045` a ton-hour is a realistic price and `$4.50` would not be; raising
#: the price to make the demo look right would have put a wrong figure on a
#: signed money path. At 500 the reference thermal customer draws **4,500
#: ton-hours** and bills **`$202.50`** — the order of magnitude the building
#: this fixture describes actually has.
#:
#: ⚠ **`electric` AND `gas` WERE CHECKED AND DO NOT MOVE.** 800 kWh and 40 ccf
#: a month is a household a utility recognises; thermal was the only scale
#: nobody had checked, because nothing priced it. (**This said *"40 therm"*
#: until 2026-09-07**, `DEF-MET-4502` — the draw is unchanged, the unit is the
#: one the register has read since `BR-TEN-1180`. At the signed `$1.15/ccf`
#: those 40 ccf are **`$46.00`** a month, which is a gas bill a household
#: recognises too, so the scale is confirmed rather than merely unmoved.)
#: `tests/test_cr062_j_addendum.py::test_pure_j1_only_thermal_moves` is that
#: guard, so a later "tidy-up" of this map goes red rather than quiet.
#: ⚠ **AND `thermal_heat` LEFT ENTIRELY ON 2026-09-07 (`CR-080`) — THE WHOLE
#: OF THE PARAGRAPH ABOVE IS NOW HISTORY AND IS KEPT BECAUSE IT IS CITED.**
#: The PO ruled thermal capacity-based on connected tonnage, so it reads no
#: register: there is no ton-hour to scale and the `$0.045` that made the scale
#: matter has retired with it. `500` and `4,500 ton-hours` and `$202.50` are
#: all facts about a billing shape this product no longer has for thermal.
#: `tests/test_cr062_j_addendum.py::test_pure_j1_only_thermal_moves` moved with
#: it — see that file for what replaced it.
CONSUMPTION_SCALE: dict[str, int] = {
    "water": 1,
    "electric": 100,
    "gas": 5,
}

#: Why a service the tenant SELLS still gets no estate — the sentence a person
#: reads on the Sample data panel. A refusal that does not say WHY is DEF-016
#: again, so every one of these names the service and the rule.
_NO_DEFAULT_UOM = (
    "{service}: the tenant declares no primary unit of measure for it, so a meter "
    "would have to be created with a blank UoM. CLAUDE.md rule 3 has no branch that "
    "assumes one and metering's own validation errors `unit_missing` on exactly that "
    "row, so the fixture reports it instead of guessing. Set a primary UoM on "
    "Settings -> Services & UoM and load the sample data again"
)
#: ⛔ **`_NOT_THE_BACKBONE` STOOD HERE AND IS WITHDRAWN — `CR-062` C2, PO
#: statement (8), 2026-09-02.** It read: *"{service}: the estate is metered in
#: {backbone}. This fixture declares ONE register per unit — 48 meters and three
#: months of reads — and seeding a second metered service would double the
#: ready-to-run billing month the demo exists to let somebody press"*. It is
#: quoted here rather than deleted without trace because it is the sentence a
#: reader will find in old defect rows, and because it was TRUE of the fixture
#: and honest about its reason — the reason is simply no longer the ruling. The
#: PO overruled it after being shown that a utility selling Electric + Water +
#: Sewer got no electric line on any of its 95 bills: *"this is not correct -
#: you cannot drop electricty or gas"*. **Nothing may reinstate it without a new
#: ruling**, and `tests/test_cr062_c_every_metered_service_gets_its_meters.py`
#: asserts the name is gone from this module for exactly that reason.
_SEWER_NEEDS_WATER = (
    "sewer: CR-081 prices sewer as 90% of the WATER VOLUME (it was 40% of the water "
    "usage charge until 2026-09-08), and this "
    "tenant does not sell water — there is no basis for the percentage to be taken "
    "of, so a sewer service point here would bill nothing"
)
#: ⚠ **NO SERVICE IN TODAY'S TEN-SERVICE CATALOGUE CAN REACH THIS SENTENCE ANY
#: MORE (`DEF-2396`, 2026-09-01), AND IT IS KEPT ON PURPOSE.** It was solar,
#: broadband and battery's refusal until `CAPACITY_ESTATE_SERVICES` gave them a
#: shape, and `METERED ∪ COMPANION ∪ CAPACITY` now covers all ten
#: (`BR-RAT-024`). It stands for the ELEVENTH service: a code added to the
#: platform catalogue and to no list in this file must be refused BY NAME rather
#: than silently produce an estate that does not speak it. Deleting it would
#: make that day's failure a `KeyError` instead of a sentence a person reads.
#: ⚠ **THE FIRST CLAUSE SAID *"one metered service per unit"* UNTIL `CR-062` C1
#: (2026-09-02), AND IT IS THE SENTENCE A PERSON READS ON THE SAMPLE DATA
#: PANEL** — a refusal that describes the fixture wrongly sends the reader
#: looking for a limit that no longer exists (hard-won law 1: a comment claiming
#: a guarantee is not the guarantee, and a screen string is worse).
_NOT_IN_THE_SHAPE = (
    "{service}: this fixture has no estate shape for it. Its estate is a meter per "
    "unit for every metered service the utility sells, the sewer and trash lines "
    "that hang off a water one, and the capacity services that ride on the unit "
    "with no register; {service} is none of those, and inventing premises that "
    "receive it would be inventing a utility we were never told about"
)

# ══════════════════════════════════════════════════════════════════════════
# BR-MET-143 · THE SEEDED METER'S MULTIPLIER (PO 2026-08-27, closing OQ-391)
# ══════════════════════════════════════════════════════════════════════════
#
# PO verbatim: *"A demand reading carries kW - we have to match utility service
# unit and meter reading unit - if it does not match then we have intriduce
# multiplier factor on meter. **you will ahve to seed that data.**"*
#
# This is the seeding half. Every meter the estate plants gets a multiplier that
# is DERIVED from the tenant's own two declared units, never typed:
#
#   · register UoM  — `tenant_services.primary_uom`, which is also the UoM the
#     meter itself is created with (`estate_plan.uom`); and
#   · billed UoM    — `tenant_services.billed_uom`, B2 r6.4's register→billed
#     gate, with `tenant_services.conversion_factor` beside it.
#
# ⚠ **AND WHERE NO FIGURE IS DERIVABLE, NOTHING IS SEEDED AND THE REASON IS
# NAMED.** This is spec rule 7 applied to a factor (*"Where a rule is unsigned,
# the seeder stubs and mints a question rather than choosing a number that then
# looks official"*) and it is OQ-004's own closure applied verbatim: **"no
# silent conversion"**. A plausible 0.748052 typed here to make ccf→kgal come
# out would ride into every demo bill as though somebody had chosen it.
_MULTIPLIER_NO_FACTOR = (
    "{service}: its register reads {register} and it is billed in {billed}, and the "
    "tenant has configured no conversion factor between them (tenant_services."
    "conversion_factor is empty). OQ-004's closure is 'no silent conversion', so this "
    "fixture seeds NO multiplier rather than inventing one — set the factor on "
    "Settings -> Services & UoM and load the sample data again"
)
_MULTIPLIER_NOT_A_SCALE = (
    "{service}: its register reads {register} and it is billed in {billed}, and those "
    "measure DIFFERENT PHYSICAL QUANTITIES ({register_dim} against {billed_dim}). A "
    "multiplier is a SCALE factor (BR-MET-143) and no number turns one quantity into "
    "another, so this fixture seeds no meter for it — the two are priced by different "
    "charges or the service's units are misconfigured"
)
_MULTIPLIER_UNKNOWN_UNITS = (
    "{service}: its register reads {register} and it is billed in {billed}, and this "
    "product has not been told what kind of quantity at least one of them measures. "
    "Asserting that they differ only by scale would be exactly the silent conversion "
    "OQ-004's closure forbids, so this fixture seeds no multiplier for it"
)

#: The four verdicts `register_multiplier` understands — the same VALUES
#: `apps.metering.register_units` publishes, restated here rather than imported
#: because this file may hold no module import (see the module docstring), and
#: pinned against it by `tests/test_br_met_141_register_units.py`.
RECONCILE_MATCH = "match"
RECONCILE_SCALE = "scale"
RECONCILE_DIMENSION = "dimension"
RECONCILE_UNKNOWN = "unknown_dimension"


def register_multiplier(
    *,
    service: str,
    register_uom: str | None,
    billed_uom: str | None = None,
    conversion_factor: Any = None,
    kind: str = RECONCILE_UNKNOWN,
    register_dimension: str | None = None,
    billed_dimension: str | None = None,
) -> tuple[str | None, str | None]:
    """BR-MET-143's seeded factor: `(multiplier, refusal)`. PURE — no ORM.

    Exactly one of the pair is ever set:

      * `("1", None)`     — the register's unit and the billed unit are the SAME
        (or no billed unit is configured, so nothing disagrees). ×1 is not a
        placeholder here: it is the reconciliation, and it is what "match"
        means. BR-MET-019 multiplies by it and the figure is unchanged.
      * `(<factor>, None)` — they differ by SCALE and the tenant has configured
        a `conversion_factor`. The factor is the TENANT's own number read back,
        never one this file chose.
      * `(None, <sentence>)` — anything else. The caller reports the sentence on
        the Sample data panel and seeds no meter for that service.

    `kind` is the classification `apps.metering.register_units.reconciliation`
    produced, passed IN rather than computed here: `core/` holds no business
    rule and may not import a module, and the scale-versus-dimension rule is
    metering's (BR-MET-143). Called with no classifier the default is
    `unknown_dimension`, which REFUSES a mismatch — the safe direction, and the
    one hard-won law 3 asks for.
    """
    register = register_uom or "—"
    billed = billed_uom or "—"
    if kind == RECONCILE_MATCH:
        return "1", None
    if kind == RECONCILE_SCALE:
        if conversion_factor in (None, "", 0):
            return None, _MULTIPLIER_NO_FACTOR.format(
                service=service, register=register, billed=billed
            )
        return str(conversion_factor), None
    if kind == RECONCILE_DIMENSION:
        return None, _MULTIPLIER_NOT_A_SCALE.format(
            service=service,
            register=register,
            billed=billed,
            register_dim=register_dimension or "unstated",
            billed_dim=billed_dimension or "unstated",
        )
    return None, _MULTIPLIER_UNKNOWN_UNITS.format(service=service, register=register, billed=billed)



class MeteredService:
    """ONE metered service the seeded estate speaks, with its own unit and its
    own factor. Pure data.

    ⚠ **THIS TYPE EXISTS BECAUSE `CR-062` C1 MADE THE ESTATE PLURAL.** Until
    2026-09-02 the plan carried three scalars — `backbone`, `uom`, `multiplier`
    — because the fixture planted ONE register per unit and refused every later
    metered service by name. Those three are one service's three facts, so the
    honest shape once there are several is a ROW PER SERVICE rather than three
    parallel tuples that could fall out of step.

    * `code` — the service, e.g. `water`.
    * `uom` — the unit its register READS, which is the tenant's own
      `tenant_services.primary_uom` and the unit its meter is created with
      (CLAUDE.md rule 3: a consumption always carries its unit).
    * `multiplier` — `BR-MET-143`'s seeded factor reconciling `uom` with the
      unit THIS service is BILLED in. `"1"` where they are the same unit, which
      is what every estate holds today; the tenant's own `conversion_factor`
      where they differ by scale. A service whose pair no factor can reconcile
      never reaches this row at all — it is REFUSED by name, and only that
      service is (see `estate_plan`).
    """

    __slots__ = ("code", "uom", "multiplier")

    def __init__(self, code: str, uom: str, multiplier: str = "1") -> None:
        self.code = code
        self.uom = uom
        self.multiplier = multiplier

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MeteredService):
            return NotImplemented
        return (self.code, self.uom, self.multiplier) == (
            other.code,
            other.uom,
            other.multiplier,
        )

    def __hash__(self) -> int:
        return hash((self.code, self.uom, self.multiplier))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"MeteredService({self.code!r}, {self.uom!r}, x{self.multiplier})"


class EstatePlan:
    """WHICH services the seeded estate speaks, for ONE tenant. Pure data.

    Resolved once per block from the tenant's enabled set and its own declared
    units, then handed to every shape function below. Three fields answering
    three different questions, which is the whole point:

      * `metered` — a `MeteredService` PER enabled metered service, in
        `METERED_ESTATE_SERVICES` order. Each gets its own 48 meters, its own
        connection on every unit and its own three months of reads. `()` means
        no enabled service can hold a register, and the caller must RAISE
        `BlockCannotRun` rather than return a 0 — that 0 is DEF-795.
      * `companions` — services the units also receive with no register of
        their own: sewer and trash behind a water estate, and (since
        `DEF-2396`, joined by storm water under `CR-062` C9) the capacity
        services, which need no metered service at all.
      * `refused` — every enabled service that gets NOTHING, each with the
        sentence saying why. A service the tenant sells and cannot see in the
        demo is a question they will ask; this is the answer, written down
        before they ask it.

    ⛔ **`backbone`, `uom` AND `multiplier` WERE THE FIRST THREE FIELDS AND ARE
    GONE — `CR-062` C3, AND THE REMOVAL IS THE POINT (hard-won law 2).** They
    named ONE metered service, and about twenty-four call sites across
    `apps/assets`, `apps/metering` and `apps/rating` read them. A compatibility
    shim answering `plan.backbone` from `metered[0]` would have left every one
    of those call sites quietly seeding a single service while the plan
    correctly described several — code that goes on working, a second service
    that goes on being absent, and every gate green. That is exactly the shape
    that hid `DEF-3224` for weeks. So the names were RETIRED rather than
    aliased: `plan.backbone` is now an `AttributeError` at the moment a lane
    reads it, and each call site was moved deliberately — to `plan.metered`
    where the answer is per service, and to `plan.primary` where the fixture
    genuinely means *the first one* (the awkward-case demonstrations and the
    sample plan's name, `CR-062` judgment 4).
    """

    __slots__ = ("metered", "companions", "refused")

    def __init__(
        self,
        metered: tuple["MeteredService", ...],
        companions: tuple[str, ...],
        refused: tuple[tuple[str, str], ...],
    ) -> None:
        self.metered = tuple(metered)
        self.companions = companions
        self.refused = refused

    @property
    def primary(self) -> "MeteredService | None":
        """The FIRST metered service, or `None` when the estate has no register.

        ⚠ **THIS IS NOT `backbone` UNDER A NEW NAME AND MUST NOT BE USED AS
        ONE.** It answers exactly one question — *which service do the awkward
        cases and the plan's name hang on* — and `CR-062` judgment 4 is why that
        question exists at all: the three unreadable meters, the one disputed
        read and the one meter replaced mid-history are DEMONSTRATIONS, not
        coverage, and three copies of one story makes the demo harder to read
        rather than richer. Anything that is per-service — a meter, a
        connection, a reading, a read batch, a rate schedule — reads `metered`
        and loops.
        """
        return self.metered[0] if self.metered else None

    @property
    def metered_codes(self) -> tuple[str, ...]:
        """Just the codes, for the many callers that only need the names."""
        return tuple(row.code for row in self.metered)

    @property
    def services(self) -> tuple[str, ...]:
        """What each seeded UNIT receives — metered first, then companions.

        This is the tuple that used to be `FIXTURE_SERVICES ∩ enabled`. On a
        tenant that sells water it is IDENTICAL to that intersection, in the
        same order, which is what keeps every existing tenant unmoved — and on
        a tenant selling a second metered service it now names that service
        too, which is `CR-062` C5: a connection per unit per metered service
        follows from this tuple with no second decision anywhere.
        """
        return tuple(code for code in (*self.metered_codes, *self.companions) if code)

    @property
    def refusal_sentence(self) -> str:
        """Every refusal joined into one sentence, for `BlockCannotRun`."""
        return " · ".join(reason for _code, reason in self.refused)

    @property
    def no_register_reason(self) -> str:
        """WHY this estate has no register at all — the sentence a block raises
        with.

        ⚠ **THE THREE CALLERS USED TO FALL BACK TO *"the tenant has no enabled
        service at all"*, WHICH IS FALSE FOR A CAPACITY-ONLY UTILITY AND WAS
        ALREADY FALSE FOR A TRASH-ONLY ONE (`DEF-2396`, 2026-09-01).** A
        trash-only tenant bills 96 invoices and its meters, reads and
        second-cycle blocks all refused with that sentence, naming a cause that
        was not true. **BR-TEN-060 asks for the reason, and a reason that is
        WRONG is worse than a bare zero: it sends the reader to Settings to turn
        on a service that is already on.**

        Three states, three sentences, and only the first two are faults:

          * something was REFUSED — say what and why, verbatim;
          * services ARE enabled and none of them holds a register — **this is
            CORRECT and the sentence says so**, because a capacity service
            (`BR-RAT-090`, priced by counting what is installed) and a
            share-priced one (`BR-RAT-015`) have no dial by design;
          * nothing is enabled at all — the original sentence, now reachable
            only when it is true.
        """
        if self.refused:
            return self.refusal_sentence
        if self.services:
            return (
                "this tenant's enabled service(s) — "
                + ", ".join(self.services)
                + " — are all priced WITHOUT a register (a capacity service is priced by "
                "counting what is installed, BR-RAT-090; a share-priced one derives from "
                "another service's charge, BR-RAT-015), so there is no meter to create and "
                "nothing to read. That is CORRECT for these services and is not a fault: "
                "the bills they produce are priced from the unit's own equipment, not from "
                "a dial"
            )
        return (
            "the tenant has no enabled service at all — turn one on at Settings -> "
            "Services & UoM and load the sample data again"
        )

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (
            f"EstatePlan(metered={list(self.metered)!r}, "
            f"companions={self.companions!r}, refused={[c for c, _ in self.refused]!r})"
        )


def estate_plan(
    enabled: Any,
    default_uoms: Any = None,
    billed_uoms: Any = None,
    reconcile: Any = None,
) -> EstatePlan:
    """The estate this tenant can actually be given. PURE — no ORM, no seam.

    `enabled` is the tenant's enabled service codes; `default_uoms` maps a
    service code to the tenant's own primary UoM (`tenant_services.primary_uom`,
    seeded from `apps.tenancy.services.SERVICE_DEFAULT_UOMS`). Both arrive
    RESOLVED from the caller, because this file may not import Django — see the
    module docstring for why the declaration holds no ORM.

    ── `CR-062` C1/C2 (PO statement (8), 2026-09-02) ──────────────────────────
    **EVERY enabled metered service gets a register, not just the first.** This
    loop used to accept the first entry of `METERED_ESTATE_SERVICES` it found
    enabled and append `_NOT_THE_BACKBONE` for every later one, so a tenant
    selling electric + water + sewer received `('water', 'sewer')` and its
    electric was dropped from the estate, the reads, the tariff and every bill
    line. The refusal is withdrawn; the ORDER is kept, because the first entry
    is what the awkward cases and the plan's name hang on (`EstatePlan.primary`)
    and every ❄️ frozen figure this fixture reproduces is a water figure.

    **A REFUSAL IS NOW PER SERVICE RATHER THAN PER ESTATE, and that is the other
    half of the same change.** A metered service with no declared unit, or whose
    register unit and billed unit no factor can reconcile, is refused BY NAME
    and plants no meter — while every other metered service on the same tenant
    is seeded normally. Before this, whichever service came first decided the
    whole estate: one unreconcilable service either took the estate down or was
    silently skipped in favour of the next.

    ── BR-MET-143 (PO 2026-08-27, closing OQ-391; AMENDED 2026-09-02) ─────────
    `billed_uoms` maps a service code to `{"billed_uom", "conversion_factor"}`
    — B2 r6.4's register→billed gate as the TENANT holds it — and `reconcile` is
    a callable `(reading_unit, pricing_unit) -> {"kind", …}` that classifies the
    pair. Both are OPTIONAL and both arrive from the caller for the same reason
    the UoMs do: the scale-versus-dimension rule is METERING's (BR-MET-143,
    `apps.metering.register_units.reconciliation`) and `core/` holds no business
    rule. **With neither supplied the behaviour is byte-for-byte what it was
    before that rule** — every seeded meter carries `multiplier="1"` — because a
    tenant with no `billed_uom` configured has nothing to reconcile, which is
    every tenant this fixture has ever planted an estate for. The factor is
    resolved ONCE PER METERED SERVICE, which is what the rule always described.

    Deterministic on its inputs, so metering (premises, units, reads) and assets
    (meters) each call it and reach the same answer without either module
    reading the other's tables (B1).
    """
    enabled_set = {str(code) for code in (enabled or ())}
    uoms = {str(code): (unit or None) for code, unit in dict(default_uoms or {}).items()}
    billed = {str(code): dict(row or {}) for code, row in dict(billed_uoms or {}).items()}

    metered: list[MeteredService] = []
    refused: list[tuple[str, str]] = []

    for code in METERED_ESTATE_SERVICES:
        if code not in enabled_set:
            continue
        unit = uoms.get(code)
        if not unit:
            refused.append((code, _NO_DEFAULT_UOM.format(service=code)))
            continue
        # BR-MET-143 — the meter's multiplier is resolved BEFORE the service is
        # accepted, so a service whose register unit and billed unit cannot be
        # reconciled is REFUSED with its reason rather than seeded with a factor
        # nobody chose. `_resolve_multiplier` answers ("1", None) for every
        # tenant that has configured no billed unit, which is every tenant.
        factor, reason = _resolve_multiplier(code, unit, billed.get(code), reconcile)
        if reason is not None:
            refused.append((code, reason))
            continue
        metered.append(MeteredService(code, unit, factor or "1"))

    metered_codes = {row.code for row in metered}
    companions: list[str] = []
    for code in COMPANION_ESTATE_SERVICES:
        if code not in enabled_set:
            continue
        if code == "sewer" and "water" not in metered_codes:
            # CR-081 takes 90% of the WATER VOLUME (BR-RAT-015 ❄️ took 40% of
            # the water usage charge until 2026-09-08), so sewer needs
            # water to be METERED here — not merely enabled, and not merely
            # first. Under `CR-062` water is no longer "the backbone", so the
            # test is membership rather than identity; on every shape that
            # sells water it is the same answer it always was.
            refused.append((code, _SEWER_NEEDS_WATER))
            continue
        companions.append(code)

    # ── DEF-2396 · THE CAPACITY SERVICES (PO ruling 2026-09-01, DEF-2409) ────
    # They ride on the unit with no register of their own and carry NO rule
    # about which service is metered — which is why they are a separate loop
    # with no condition in it. A capacity-only tenant therefore gets an estate
    # with no register at all, which is what a trash-only tenant has had since
    # `DEF-2414`. `storm_water` joined them 2026-09-02 (`CR-062` C9).
    for code in CAPACITY_ESTATE_SERVICES:
        if code not in enabled_set:
            continue
        companions.append(code)

    shaped = (
        set(METERED_ESTATE_SERVICES)
        | set(COMPANION_ESTATE_SERVICES)
        | set(CAPACITY_ESTATE_SERVICES)
    )
    for code in sorted(enabled_set - shaped):
        refused.append((code, _NOT_IN_THE_SHAPE.format(service=code)))

    return EstatePlan(tuple(metered), tuple(companions), tuple(refused))


def _resolve_multiplier(
    service: str, register_uom: str, configured: Any, reconcile: Any
) -> tuple[str | None, str | None]:
    """`register_multiplier` with the classification resolved. See BR-MET-143.

    A tenant with no `billed_uom` on the service has nothing to reconcile, and
    that is the MATCH branch rather than an unknown: r6.4's gate is a per-service
    OPTION, and treating an unconfigured option as a mismatch would refuse an
    estate for every tenant in existence.
    """
    row = dict(configured or {})
    billed_uom = row.get("billed_uom") or None
    if billed_uom is None or reconcile is None:
        kind = RECONCILE_MATCH if billed_uom is None else RECONCILE_UNKNOWN
        return register_multiplier(
            service=service, register_uom=register_uom, billed_uom=billed_uom, kind=kind
        )
    verdict = dict(reconcile(register_uom, billed_uom) or {})
    return register_multiplier(
        service=service,
        register_uom=register_uom,
        billed_uom=billed_uom,
        conversion_factor=row.get("conversion_factor"),
        kind=str(verdict.get("kind") or RECONCILE_UNKNOWN),
        register_dimension=verdict.get("reading_dimension"),
        billed_dimension=verdict.get("pricing_dimension"),
    )


def meter_no(service: str, unit_index: int) -> str:
    """This unit's meter serial in `service`. `water` → `W-5000 … W-5047`,
    unchanged and unchangeable (see `SERVICE_METER_PREFIX`)."""
    return f"{SERVICE_METER_PREFIX.get(service, service[:2].upper())}-{5000 + unit_index:04d}"


def replacement_meter_no(service: str) -> str:
    """The NEW serial spec §4 case 3 puts on after the June read.
    `water` → `W-9011`."""
    prefix = SERVICE_METER_PREFIX.get(service, service[:2].upper())
    return f"{prefix}-{9000 + CASE_METER_REPLACED:04d}"


def consumption(unit_index: int, period_key: str, service: str = "water") -> Any:
    """This unit's use for the period, in the backbone's own unit.

    The SHAPE is `water_consumption_kgal`'s, scaled by `CONSUMPTION_SCALE` —
    see that constant for why the scale exists and what it is not. Water is
    scale 1, so `consumption(0, "june")` is still the frozen GT-17 **8**.

    ⚠ **ONE UNIT AND ONE SERVICE ESCAPE THE SHAPE ENTIRELY, AND THE ESCAPE IS
    THE POINT (`CR-062` addendum J4).** The industrial plant's ELECTRIC draw is
    stated outright rather than derived, because deriving it would tie a
    factory's kWh to a household's kgal: to reach an industrial plant's monthly
    energy through `CONSUMPTION_SCALE` the plant would have to draw **537 kgal**
    of water, which would then be its water bill on any tenant that sells water.
    **Two facts about one customer that have no arithmetic relationship must not
    be forced to share a multiplier.** See `UNIT_SERVICE_CONSUMPTION` for the
    figure and the load factor behind it.
    """
    override = UNIT_SERVICE_CONSUMPTION.get((unit_index, service))
    if override is not None:
        return override
    # ⚠ **THE SHAPE IS ASKED FOR THIS SERVICE, NOT FOR WATER (PO 2026-09-07).**
    # It read `water_consumption_kgal(...) * scale` until then, which was right
    # while there was one flat shape and became wrong the moment the shape grew
    # a SEASON: gas peaks in January and water in July, so multiplying water's
    # July peak by gas's scale would seed a gas utility whose demand is highest
    # in midsummer. `_shaped` takes the service and picks its own curve; water
    # is `_shaped(..., "water")`, which is exactly what
    # `water_consumption_kgal` returns, so the water estate is byte-identical
    # to what this line produced for it before.
    return _shaped(unit_index, period_key, service) * CONSUMPTION_SCALE.get(service, 1)


# ── BR-RAT-102 · THE OUTSIDE-CITY SURCHARGE, ON THE SEEDED ESTATE ───────────
#
# CR-039 wave C task 11 — *"seed it so the surcharge path is exercised"*. The
# provisioning trace found the flag unwritable (finding 3) and the trace's
# fix is only half the job: a jurisdiction column nothing PRICES is the
# built-not-wired shape one level down.
#
# ⚠ **TWO GATES HAVE TO OPEN, AND SEEDING ONE OF THEM DOES NOTHING.**
# BR-RAT-102: the PLAN states the factor, the PREMISES states the side, and a
# line is surcharged only when both are true. Before this, every seeded plan
# read NULL (`DEF-515`) and every seeded premises read NULL (`DEF-517`), so the
# multiplier this product has applied to every base and every usage line since
# it was written has always been exactly `1` and no test could tell.
#
# ⚠ **EVERY FIGURE HERE IS CITED. NONE IS THIS FIXTURE'S OPINION.**
#
#   1.5      r10's Residential Standard schedule, verbatim: *"Premises outside
#            city limits multiply base and variable by 1.5 — set on the premise
#            record."* Design §A4 S2 works the same number on its own estate —
#            `BASE-E $18.50 × 1.5 = $27.75` — so the value has a drawing AND a
#            worked example behind it. It is NOT B4/B5 frozen (neither file
#            mentions the surcharge), so nothing signed moves when it lands.
#
#   sewer    §A4 S2, verbatim: *"BASE-S $8.00 (flat everywhere — the multiplier
#            does NOT touch sewer)"*, and r10 in four words: *"sewer is flat
#            everywhere"*. The exemption is per-SERVICE and lives on the plan's
#            own service line (BR-RAT-102).
#
#   TWO      of 44. r10's tax scope answers *1,186 of 1,247* premises inside the
#            city, and BR-RAT-107 names the difference: *"the 61 outside-city
#            premises r10 exempts"*. 61/1,247 = 4.89%, and 4.89% of 44 is 2.15.
#            So the seeded estate is 42 inside and 2 outside — DERIVED from
#            r10's own ratio rather than picked because it looked about right.
#
# ⚠ **AND ALL FORTY-FOUR ARE STATED, WHICH IS NOT COSMETIC.** A plan that states
# a factor over a premises whose flag is `None` REFUSES that account's bill by
# name (BR-RAT-102's fourth case, `gather._jurisdiction_factor_for`). The
# residential plan states the factor, so leaving 42 addresses unrecorded would
# turn the demo's ready-to-run billing month into 42 exception rows. Stating
# *inside* on them is r10's own estate (its PRM-02 premises reads *"inside city
# limits"*), not an invention.
#
# ⚠ **THE COMMERCIAL PLAN DELIBERATELY STATES NO FACTOR.** BR-RAT-102's first
# gate is what protects a utility that does not price by jurisdiction, and a
# fixture where every plan surcharges cannot demonstrate it. So the demo shows
# both halves: one plan that consults the premises and one that never does.
#: 🔒 HUMAN-REVIEW-PENDING · HUMAN-OWNED — these three constants decide MONEY on
#: every seeded tenant (CR-039 wave C task 11, 2026-08-27). Row in
#: `12-governance/09-human-review-ledger.md`, with the worked figure and the two
#: questions the PO still has to answer (`OQ-423`, `OQ-424`). Every figure is
#: cited above; none is this fixture's opinion.
OUTSIDE_CITY_FACTOR = "1.5"
OUTSIDE_CITY_EXEMPT_SERVICES: tuple[str, ...] = ("sewer",)

#: WHICH two premises. Chosen as ordinals of `premises_plan()`, both in the
#: single-family run where a premises ordinal IS its unit's `unit_index`, and
#: both clear of every `CASE_*` index above — a premises that is also the
#: write-off case or the disputed read would make two demo stories argue over
#: one bill, and the first failure message anybody read would name the wrong
#: one.
OUTSIDE_CITY_PREMISES_INDEXES: tuple[int, ...] = (30, 34)


def default_jurisdiction() -> bool:
    """What every OTHER seeded address states: `True`, inside the city.

    ⚠ **THIS EXISTS BECAUSE LEAVING IT UNSTATED IS NOT THE NEUTRAL CHOICE ONCE
    A SEEDED PLAN SURCHARGES, AND A TEST CAUGHT EXACTLY THAT.** `premises_plan()`
    is not the only estate the metering seeder plants: the CR-030 onboarding
    estate and the CR-028 register shapes add ~21 more addresses, and
    `_cr030_plan_id`'s own docstring puts their units on **the residential
    plan** — the plan that now states r10's `1.5`. A premises there with
    `inside_city_limits = None` makes BR-RAT-102 refuse its account's bill by
    name, and BR-BIL-055 turns that into ONE exception row rather than a failed
    run: the demo would look healthy and quietly not bill 21 customers.
    `tests/test_cr039_c11_seeded_surcharge.py::…_no_seeded_premises_on_a_
    SURCHARGING_plan_is_left_unstated` is that test, and it went RED naming all
    21 addresses before this function existed.

    ⚠ **`True` IS A STATEMENT AND IT IS THE SAME ONE `premises_plan()` ALREADY
    MAKES ABOUT 42 ADDRESSES.** r10's own tax scope answers *1,186 of 1,247*
    premises inside the city, and its PRM-02 premises reads *"inside city
    limits"*, so a demo municipality whose addresses are overwhelmingly inside
    its own boundary is r10's estate rather than this fixture's invention. What
    would be an invention is `False` — that one adds a charge.

    A FUNCTION and not a constant, so every call site reads the same sentence
    and a future ruling changes one line. It is deliberately NOT a column
    default: BR-RAT-101 forbids `premises.inside_city_limits` a `default=`,
    because a default there would answer for every tenant's real data. This
    answers only for rows this fixture creates.
    """
    return True


# ── CR-039 wave C task 14 · WHAT KIND OF PARTY each seeded owner is ──────────
#
# PO ruling 2026-08-27, verbatim: *"category is okay, no richer text"* — a
# premises owner is a TYPED party record (BR-MET-150), and task 14 is *"seed
# several owner kinds"*.
#
# ⚠ **THIS MAP IS THE ONLY PLACE A SEEDED CATEGORY IS DECIDED, AND THE SEEDER
# NEVER DERIVES ONE FROM A STRING** (BR-MET-151 clause 3, BR-MET-152). There is
# no suffix table here and no heuristic anywhere: *LLC* is not evidence of a
# landlord and *Chen, David* is not evidence of an owner-occupier. A name absent
# from this map is seeded as free text with NO typed owner, and appears on
# BR-MET-151's matching review list exactly as a real customer's data does.
#
# ⚠ **AND THAT IS WHY IT IS SHORT.** Every entry cites a fact the corpus already
# holds; two of the five categories are REFUSED by name below rather than
# invented, which is CR-039 wave E's own posture (*"a seeded value nobody chose
# is worse than a blank, because a demo makes it look decided"*) applied to a
# category instead of a column.
#
#   · `builder` — *Ridge Property LLC* at `500 Main St`. BR-CUS-083 already
#     names the payer there *"the developer, via a master account"*, on a
#     25-unit build under development. The word *developer* is in the corpus;
#     this map only writes down which of the five it is.
#   · `owner_occupier` — the two commercial names. `premises_plan()` makes the
#     BUSINESS TRADING AT the address its own `owner_manager`, and each of those
#     premises holds exactly one commercial suite. Owner and occupant are the
#     same party BY CONSTRUCTION of the fixture, not by an inference about who
#     these parties are.
#   · `landlord` — *Mill Pond Apartments LP* (six let flats) and *Silver Creek
#     Duplex Holdings* (four let duplex halves). Each owns residential units it
#     lets and occupies none of them, which is what the word means.
#
# **REFUSED, per category, rather than invented:**
#   · `property_manager` asserts a managing AGENT acting for an owner. Nothing
#     in the corpus names an agent at any address, and seeding one would state a
#     SECOND party that has never been mentioned.
#   · `hoa` asserts an association. Nothing names one either.
# Both are reachable the moment a tenant records a real one — the vocabulary
# holds all five (BR-TEN-150) and only the SEED is short.
OWNER_CATEGORY_BY_NAME: dict[str, str] = {
    "Ridge Property LLC": "builder",
    "Creekside Laundromat": "owner_occupier",
    "Quarry Hill Diner": "owner_occupier",
    "Mill Pond Apartments LP": "landlord",
    "Silver Creek Duplex Holdings": "landlord",
}


def owner_category_for(owner_manager: str | None) -> str | None:
    """The seeded owner's category code, or `None` — *nothing states one*.

    `None` is the interesting return and it is not a gap: it is BR-MET-152
    clause 4 working, and it is what leaves a fresh demo with real rows on
    BR-MET-151's matching review list. A promise nobody can see demonstrated is
    a promise nobody checks — the same reasoning task 11 used to leave the
    sample COMMERCIAL plan deliberately stating no outside-city factor.

    Matched EXACTLY and case-sensitively, on purpose. A case-insensitive or
    fuzzy lookup here would be the string heuristic BR-MET-151 forbids, wearing
    a convenience's clothes: these are five literal names this fixture itself
    wrote, so an exact match is available and anything looser is a guess.
    """
    if not owner_manager:
        return None
    return OWNER_CATEGORY_BY_NAME.get(owner_manager.strip())


# ── Money (every figure cited; none invented) ────────────────────────────────
# [W] §1 Residential Standard.
WATER_TIERS: tuple[tuple[str, str | None, str], ...] = (
    ("0", "5", "4.00"),
    ("5", "15", "6.50"),
    ("15", None, "8.00"),
)
WATER_BASE = "8.00"  # [W] §1 "Base/mo … Water $8"
#: [W] §1 "Base/mo … Electric $12" — the same figure `RATE_PLANS` has always
#: carried on `plan_services.base_charge` for Residential Standard. It gets a
#: name here for the reason `WATER_BASE` has one: `BR-RAT-088` moved the base
#: onto a charge CODE, and a figure with two homes drifts. See `DEF-528` — the
#: seed declared a base code for water and not for electric, and because the
#: BR-RAT-088 guard self-activates on the first one, `seed_demo` could not
#: create a single electric schedule on a fresh database.
ELECTRIC_BASE = "12.00"
#: [W] §1 *"Industrial electric base $180"* — the figure `RATE_PLANS` has
#: always carried on `IND`'s `plan_services.base_charge`. It gets a name on
#: 2026-08-31 for exactly the reason `ELECTRIC_BASE` got one: `BR-RAT-088`
#: moved the base onto a charge CODE, so this figure needed a home there too.
#:
#: ⚠ **UNTIL IT HAD ONE, THE FIXTURE DISAGREED WITH ITSELF BY `$168.00`
#: (`DEF-2823`, measured 2026-08-31).** `IND` stated `$180.00` on the plan
#: while the only `is_base` electric code stated `$12.00`, and nothing could
#: see it: the live path read the plan and the ruled chain — which reads the
#: code — has no production caller. **0 accounts are on `IND`, so no bill ever
#: carried either figure**; the collision surfaced the moment both paths were
#: pointed at one source.
#: ⚠ **AND SINCE 2026-09-02 A BILL FINALLY CARRIES IT (`CR-062` addendum J4).**
#: `CASE_INDUSTRIAL_ACCOUNT` is the first `industrial` account this fixture has
#: ever seeded, so the sentence above — *"0 accounts are on `IND`, so no bill
#: ever carried either figure"* — is history rather than a live risk. That is
#: the whole reason the seat was added: a figure no bill carries is a figure
#: nothing can disagree with out loud.
INDUSTRIAL_ELECTRIC_BASE = "180.00"

#: **THE INDUSTRIAL USAGE RATE — `[W] §1`'s own `$0.085/kWh`, RULED ONTO THE
#: DEMO'S USAGE LINE BY THE PO ON 2026-09-02 (`CR-062` addendum J4).**
#:
#: PO verbatim: *"for usage line use $0.085/kWh"*, said after being shown the
#: `DEF-2397` reasoning three constants down — that `$0.085` is HALF of an
#: energy-plus-demand tariff (`+ $11.00/kW`) and that this estate takes no
#: demand read — and a `$0.00` alternative.
#:
#: ⚠ **SO THE DEMO CHARGES THE ENERGY HALF AND DOES NOT CHARGE THE DEMAND HALF,
#: AND THE COST OF THAT IS STATED HERE RATHER THAN LEFT TO BE DISCOVERED.** At
#: the seeded plant's **100 kW** peak the unbilled demand half is
#: `100 × $11.00` = **`$1,100.00`** a month, on a bill of **`$4,770.00`**. A
#: real utility configures both halves on Plans & Rates; this is the DEMO's
#: usage line, and the reasoning it supersedes is kept verbatim where it was
#: written because it is still true of a real tariff.
#:
#: ⚠ **FOUR DECIMAL PLACES, AND THEY ARE DOING REAL WORK** — CLAUDE.md hard
#: rule 2. `$0.085` at two decimals rounds to `$0.09`, which is a **5.9%
#: overcharge** on every industrial usage line; written `"0.0850"` the column
#: stores it exactly and DISPLAYS `$0.09` only where money is displayed.
#:
#: **Worked, on the seeded plant:** 54,000 kWh × `$0.0850` = **`$4,590.00`**,
#: plus the signed `$180.00` base = **`$4,770.00`** before taxes.
#: 🔒 HUMAN-REVIEW-PENDING — this rate decides MONEY on every seeded industrial
#: account. Row in `12-governance/09-human-review-ledger.md` with the worked
#: figure and the supersession it implements.
INDUSTRIAL_ELECTRIC_PER_KWH = "0.0850"

#: `[W] §1`'s DEMAND half, **RECORDED AND SEEDED NOWHERE** — the posture
#: `GAS_FLAT_PER_CCF` and `TRASH_FLAT` already hold, and for the same reason: a
#: signed figure is recorded, never deleted. It becomes usable the day this
#: estate takes a demand read (`kW`), which it does not: every seeded meter
#: holds ONE register. Reading it against an energy register would bill `kW`
#: against `kWh`, which is `DEF-497` on a money path.
INDUSTRIAL_DEMAND_PER_KW = "11.00"

# ── The water schedule's VERSION HISTORY (DEF-357) ───────────────────────────
# Three states at once against the fixture's 2026-08 clock: v1 (2026-06-01,
# seeded by the schedule payload) SUPERSEDED, v2 CURRENT, v3 DATED and not yet
# in force. Without them every Versions tab renders one row, SUPERSEDED is
# always an em-dash, and an assertion that billing picks the version in force on
# the usage date CANNOT FAIL because there is only one version to pick.
#
# ⚠ THE DATES ARE THE LOAD-BEARING PART, not the prices. v2 starts AFTER the
# billed June period (PERIODS[0]), so June still prices on v1 — BR-RAT-007, and
# r10's own sentence for it: *"a January bill for December usage uses v3 even
# after v4 activates."* A fixture that moved a billed period would be re-pricing
# history, which is the thing dated versions exist to prevent.
WATER_V2_FROM = "2026-08-01"
WATER_V3_FROM = "2027-01-01"

#: The uplifts, as multipliers. These are the fixture's own choice of a
#: plausible rate case — no worked example prescribes them — so the FIGURE that
#: is stated is the uplift, and the prices are DERIVED from `WATER_TIERS` below.
#: Writing 4.24 / 6.89 / 8.48 as literals would let them drift the moment the
#: base tiers changed, and nothing would notice: each row would still be
#: individually well-formed.
WATER_V2_UPLIFT = "1.06"  # +6%, the rate case r10 draws on Residential Water
WATER_V3_UPLIFT = "1.125"  # the 2027 filing, still a draft


def _uplift(tiers: tuple[tuple[str, str | None, str], ...], factor: str) -> tuple[str, ...]:
    """Every tier price scaled and rounded to the cent, in tier order.

    Two decimals because a tier price a tenant types is money they typed; the
    six-place column stores it exactly and B4 rounds at finalization, which this
    is not — this is the fixture stating what the filing said.
    """
    from decimal import ROUND_HALF_UP, Decimal

    scale = Decimal(factor)
    return tuple(
        str((Decimal(price) * scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        for _lo, _hi, price in tiers
    )


#: DEF-463 — the tiers the seeded DRAFT schedule carries.
#:
#: DERIVED from `WATER_TIERS` and `WATER_V3_UPLIFT`, never retyped, for the same
#: reason `WATER_VERSION_HISTORY` is derived below: when this fixture stated the
#: uplifted prices by hand it carried a typo for weeks (7.31 where the
#: arithmetic gives 7.30), and a fixture that disagrees with its own stated
#: uplift is a worked example nobody can check.
#:
#: The band edges come from `WATER_TIERS` unchanged — a filing raises PRICES;
#: moving the boundaries too would be a different change and would make the
#: comparison against the in-force version meaningless.
WATER_2027_FILING_TIERS: tuple[tuple[str, str | None, str], ...] = tuple(
    (lo, hi, price)
    for (lo, hi, _old), price in zip(WATER_TIERS, _uplift(WATER_TIERS, WATER_V3_UPLIFT))
)

#: `(effective_from, reason, tier prices)` — consumed by
#: `apps.rating.sample_data.seed_sample_schedule_versions`. The reason is the
#: sentence the Versions tab's CHANGE column shows: BR-RAT-037 refuses a version
#: without one, and DEF-280 is about capturing exactly this rather than
#: rendering a serialized diff.
WATER_VERSION_HISTORY: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (WATER_V2_FROM, "+6% across tiers · PUC #W-2025-1184", _uplift(WATER_TIERS, WATER_V2_UPLIFT)),
    (WATER_V3_FROM, "2027 filing (pending) · adds conservation pricing",
     _uplift(WATER_TIERS, WATER_V3_UPLIFT)),
)
TRASH_FLAT = "18.00"  # [W] §1 "Trash flat $18" — RETIRED 2026-08-27, see below.
#: ⚠ **`TRASH_FLAT` IS NOT THE CART PRICE AND MUST NEVER BE READ AS ONE.** It is
#: the workbook's signed monthly figure for having the service at all. Re-reading
#: it per-cart bills a three-cart household `$54.00`, which is three times what
#: any Silver Creek customer pays for trash today — OQ-303's option (B), offered
#: and NOT taken.
#:
#: ⛔ **RETIRED BY `OQ-317`, CLOSED 2026-08-27 ON OPTION A — IT IS NO LONGER
#: SEEDED ANYWHERE (`DEF-2490`).** PO verbatim: *"option A is correct; where do
#: you see the carts - they are not on accounts theya re on Units."* Option A
#: says in terms that with `$15.00` per cart *"the workbook's `$18` monthly base
#: is retired for trash"*. **Worked: a three-cart household is `3 x $15.00` =
#: `$45.00`, not `$63.00`; a one-cart household is `$15.00`, not `$33.00`.**
#: Across Silver Creek's 48 trash accounts the retirement is `$864.00` a month.
#:
#: **The constant STAYS because it is a signed `[W] §1` figure and a superseded
#: figure is recorded, never deleted** — `12-governance/02-decision-log.md`
#: 2026-08-27 carries the supersession. What changed is that nothing reads it:
#: the trash plan base and `BASE-T` both read `TRASH_BASE` below. Grep this name
#: before re-introducing it anywhere.
#:
#: **Why it sat unseeded for a day after the ruling, which is the transferable
#: half:** the closure reached `01-open-questions.md`, `02-decision-log.md` and
#: `BR-BIL-300` and did not reach the fixture, and nothing in this repo connects
#: a closed question to the code that was waiting on it (`DEF-491`'s finding,
#: unchanged). `TRASH_BASE` below therefore cites `OQ-317` AT the line the
#: figure sits on, which is the only form a later reader can act on.

#: **The trash plan's base charge, and it is `$0.00` — `OQ-317` option A.**
#:
#: ⚠ **`"0"` IS A PRICE AND AN OMISSION IS A REFUSAL — THE TWO ARE NOT
#: INTERCHANGEABLE.** CR-013 part 1 (PO 2026-08-19) makes a BLANK base mean
#: *this size is not served* and `gather._base_charge_for` stops the bill on it
#: (`DEF-277`); a stored zero prints `$0.00` (PO 2026-08-19, *"print $0.00"*).
#: Retiring the base means *trash has no base*, not *trash is not served*, so it
#: is STATED as zero — the same way sewer's own base has always been stated.
#:
#: 🔒 HUMAN-REVIEW-PENDING · HUMAN-OWNED — this constant decides MONEY on every
#: seeded tenant: it is the trash base charge on both sample plans and on
#: `BASE-T` (`DEF-2490`, 2026-08-28). Row in
#: `12-governance/09-human-review-ledger.md` with the worked figure. It
#: IMPLEMENTS a PO ruling already made (`OQ-317`, option A) rather than choosing
#: one, and what has NOT been shown to the PO is stated in that row.
TRASH_BASE = "0"

#: BR-RAT-090 · CR-019 · **the price of ONE cart, ruled by the PO on 2026-08-21
#: closing OQ-303**, verbatim: *"they are bill 1 trash can $15 - for example if
#: you have 3 you multiple by 3"*.
#:
#: **Worked, ratified: 3 carts × `$15.00` = `$45.00`; remove one and the next
#: bill is `$30.00`.** The quantity is the count of the unit's ACTIVE trash
#: assets, observed and never typed (BR-RAT-090, option A) — so this figure is a
#: RATE PER CART and the schedule that carries it is priced per cart, not per
#: month.
#:
#: ⚠ **THIS SAT UNSEEDED FOR A DAY AFTER IT WAS RULED (DEF-491)**, because the
#: placeholder it was waiting behind — a trash schedule priced `0.00` — named no
#: question anywhere a check could read, so closing OQ-303 moved nothing and
#: nothing noticed. That is the general lesson worth more than the figure: a
#: placeholder pending an answer must CITE the question at the place the
#: placeholder lives.
TRASH_PER_CART = "15.00"

#: The unit `TRASH_PER_CART` is quoted in — `lookup_defaults.json.uoms` seeds
#: `cart` scoped to trash, so this is the platform's own code and not one this
#: file invented (CLAUDE.md rule 3: a quantity always carries its unit, and a
#: PRICE carries the unit it is per).
#:
#: It is stated here rather than derived from the tenant's declared UoM because
#: nothing declares one for trash and `_trash_uom()` could never have read it if
#: it did (DEF-497) — the seeded schedule read `$0.00 per month`, which was
#: harmless only while the price was zero.
TRASH_UOM = "cart"

# ══════════════════════════════════════════════════════════════════════════
# DEF-3156 · WHAT A CAPACITY COMPANION COSTS ON A SEEDED TENANT
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A SOLAR, BROADBAND OR BATTERY UTILITY RECEIVED THE WHOLE SAMPLE ESTATE
# AND BILLED NOTHING, AND THAT WAS MEASURED RATHER THAN FEARED.** On
# PostgreSQL 16.13 through `tenancy.services.provision_tenant`, one tenant per
# service, `SBH_BILLING_RESOLUTION_STEPS=R3,R4` as shipped: each produced **70
# premises, 118 units, 48–49 service points** and then **0 rate schedules, 0
# plans, 0 accounts and 0 issued bills**, 13 of 17 seeding blocks failed, every
# one of the 48 seats refused `customers.account.plan_required_at_activation`.
# `DEF-2396` gave them the ESTATE; `DEF-2397` shaped the TARIFF around the
# metered backbone and the two water companions. Neither priced a CAPACITY
# companion, and a service rating has no payload for is simply absent — which
# is indistinguishable from a service the tenant does not sell.
#
# The three constants below are that payload's figures. They follow `trash`,
# the companion this fixture already prices without a register.


#: **WHAT A SEEDED CAPACITY SERVICE CHARGES PER UNIT OF ITS QUANTITY — A PRICE
#: PER SERVICE, SIGNED BY THE PRODUCT OWNER ON 2026-09-02 (`CR-062` E2–E5).**
#:
#: ⚠ **THIS CONSTANT REPLACES `CAPACITY_UNPRICED = "0"` AND `CAPACITY_UOM =
#: "month"`, AND THE TWO WERE RETIRED IN ONE COMMIT BECAUSE THE OLD ONE'S OWN
#: DOCSTRING REQUIRED IT** — *"the price and the unit are ONE decision and must
#: move in ONE commit … a lane that changes the price and leaves `month` here
#: has rebuilt `DEF-497` on a live money path"*. That is `CR-062` task **D8**,
#: and this is the day it names: `OQ-370` is ANSWERED by the PO's statements
#: (3)–(6), so the characteristic and its unit are no longer open and the zero
#: no longer stands for anything.
#:
#: **WHERE EACH FIGURE COMES FROM. NONE IS INVENTED AND NONE IS DERIVED.**
#: Solar's is the PO's own, verbatim: *"rate will be for 1 Kw = 14 $ per KW"*.
#: The other three were put to the PO in plain English with worked figures and
#: approved in the same conversation (`CR-062` step 5, judgment 3).
#:
#: ⚠ **THE ARITHMETIC IN THE PO'S OWN MESSAGE IS OFF AND THE CORRECT FIGURE IS
#: WHAT IS SEEDED HERE.** They wrote *"14 X 14 = 156 $"*. Fourteen kW at
#: `$14.00` is **`$196.00`**; the PO was told so in the same session and did not
#: dispute it. **`$156` appears nowhere in this repo's code or tests** — a wrong
#: figure copied into a fixture becomes a wrong figure asserted by a test, and
#: then it is the product's answer.
#:
#: ⚠ **THE UNIT IS NOT HERE, AND ITS ABSENCE IS THE `DEF-497` FIX.** Each price
#: is quoted per that service's OWN declared unit, resolved from
#: `tenancy.services.SERVICE_DEFAULT_UOMS` through the same expression the
#: `BR-RAT-038` gate uses (`rating.sample_data._capacity_uom`) — solar and
#: battery per `kW`, storm water per `ERU`, broadband per `Mbps`. There is no
#: longer a fallback to invent one: a capacity service that declares no unit is
#: REFUSED BY NAME rather than priced per `month`, because `$14.00 per month`
#: against a quantity of 14 kW is hard rule 3 satisfied in FORM and wrong in
#: SUBSTANCE — the trash schedule's `$15.00 per MONTH` against 3 CARTS, exactly.
#:
#: ⚠ **FOUR DECIMAL PLACES, WRITTEN OUT, NEVER A FLOAT** — CLAUDE.md hard rule 2
#: (money stored to 4, percentages to 6, both DISPLAYED to 2). `$0.10` per Mbps
#: is written `"0.1000"` for the same reason `$0.045` per ton-hour cannot be
#: written at two: the column is the contract, not the convenient spelling.
#:
#: ⚠ **`fire` IS DELIBERATELY UNPRICED AND STAYS THAT WAY.** It is `CR-063`'s
#: eleventh service, it arrived after these six were signed, and no price for it
#: has been put to the PO. Its stored `"0"` is the ORIGINAL kind of zero this
#: constant used to hold for all four — `BR-MET-108`'s ruled zero, *"Bill it as
#: zero"* — and `OQ-1360` (the going-live customer's real fire price list) is
#: where it is answered. Pricing it here would be this fixture answering an open
#: question, which spec rule 7 forbids.
#:
#: ⚠ **A STORED ZERO, NEVER AN OMISSION, AND THE DIFFERENCE IS A REFUSAL.**
#: `CR-013` part 1 (PO 2026-08-19) makes a BLANK figure mean *this size is not
#: served* and `gather._base_charge_for` stops the bill on it (`DEF-277`); a
#: stored zero is a PRICE and prints `$0.00` (PO 2026-08-19, *"print $0.00"*).
#: That is why `fire` is a stated `"0"` and not an absent key.
#:
#: **Worked, on the PO's own solar example:** three panels of 2 kW, 4 kW and
#: 8 kW on one unit sum to **14 kW**; `14 × $14.0000` = **`$196.00`**.
#:
#: ⚠ **THE QUANTITY HALF OF THAT SENTENCE IS NOT THIS CONSTANT'S AND IS NOT YET
#: TRUE.** `BR-RAT-090` still reaches the bill as an observed COUNT of assets,
#: so three panels bill as **3**, not as 14 kW, and the line comes out at
#: `$42.00` rather than `$196.00`. Making it a SUM is `CR-062` tasks **D1/H2**
#: (🔒 rating math), which is a separate lane. **Until that lands, this price is
#: correct and the quantity beside it is not** — recorded here rather than left
#: for the next reader to discover from a wrong bill.
#:
#: 🔒 HUMAN-REVIEW-PENDING — this map decides MONEY on every seeded solar,
#: battery, storm-water and broadband tenant. Row in
#: `12-governance/09-human-review-ledger.md` with the worked figures, in
#: plain English. It IMPLEMENTS the PO's own figures rather than choosing
#: any, and what has NOT been shown to them is stated in that row.
#:
#: `service → unit price`, as decimal STRINGS at 4 decimal places.
CAPACITY_UNIT_PRICES: dict[str, str] = {
    # PO verbatim, 2026-09-02: *"rate will be for 1 Kw = 14 $ per KW"*.
    "solar": "14.0000",
    # Put to the PO in plain English with a worked figure and approved.
    "battery": "3.0000",
    "storm_water": "4.5000",
    "broadband": "0.1000",
    # CR-063's eleventh service. NOT priced — see the paragraph above.
    "fire": "0",
    # ── CR-080 · THERMAL/HEAT, `$12.50` PER CONNECTED TON PER MONTH ─────────
    # ⚠ **THIS IS A LANE JUDGMENT MADE UNDER A STANDING PO DELEGATION, AND IT
    # REPLACES A FIGURE THE PO PERSONALLY APPROVED. READ BOTH HALVES.**
    #
    # **What retired.** `METERED_USAGE_PRICES["thermal_heat"] = "0.0450"` —
    # `$0.045` per TON-HOUR — was put to the PO in plain English with a worked
    # figure and approved (`CR-062` E6). The ruling of 2026-09-07 makes thermal
    # capacity-based on connected tonnage, and **a capacity service has no
    # ton-hour**, so that figure has nothing left to multiply. It is the one
    # genuinely approved number `CR-080` removes and the PO is shown the trade
    # explicitly in `12-governance/09-human-review-ledger.md`.
    #
    # **The delegation this figure is authored under, PO verbatim:** *"you can
    # research in amrket at Municiapl utility in north amrica and put it
    # there"*. So it is researched, cited, and recorded as a judgment — **never
    # presented as a signature.**
    #
    # **WHAT THE RESEARCH FOUND, WITH THE UTILITY AND THE YEAR ON EACH FIGURE:**
    #
    #   * **Lansing Board of Water & Light** (municipal, Lansing MI), Rate CW1
    #     Commercial Chilled Water Service, FY2024-25 effective 2024-10-01:
    #     **Contract Demand `$50.00` per ton**, Excess Demand `$70.00` per ton
    #     above 105% of contract; commodity `$0.15469` per ton-hour. FY2023-24
    #     was `$49.49` / `$69.30`. BWL's own rate sheets state that the
    #     Capacity Charge IS the minimum monthly charge.
    #   * **City of Mesa, Arizona** (municipal) District Cooling, FY2024/25 and
    #     FY2025/26 rate books: a monthly capacity charge per **Rated-Ton**
    #     plus a per **Ton-Hour** energy rate, where a Ton-Hour is defined as
    #     12,000 BTU and a Rated-Ton as the building's cooling need from its
    #     square footage and anticipated usage. **This is the exact billing
    #     model the PO described** — a monthly charge on RATED (connected)
    #     tonnage — and it is where the refrigeration-ton reading is confirmed.
    #   * **District Energy St. Paul** (Minnesota): demand is the building's
    #     peak capacity in TONS; demand charges recover infrastructure and O&M,
    #     energy charges recover production.
    #   * **JEA** (municipal, Jacksonville FL), District Energy System Tariff:
    #     the demand charge is set on **tons of billable demand** to recover
    #     debt service and capital renewal.
    #
    # ⚠ **WHY `$50.00` IS NOT COPIED ACROSS, AND THIS IS THE WHOLE JUDGMENT.**
    # Lansing bills its `$50.00` on **Billing Demand — "the maximum
    # instantaneous demand (tons) supplied during the billing period"** — a
    # MEASURED monthly peak, which in a Michigan January is near zero. The PO's
    # model is Mesa's: a charge on CONNECTED tonnage, **twelve months a year,
    # whatever the weather**. A rate levied every month on installed capacity
    # must be well below one levied on a summer peak or the same building pays
    # several times more for the same service. Taking a Great Lakes cooling
    # season as roughly three full-equivalent months of billed peak out of
    # twelve: `$50.00 × 3 ÷ 12` = **`$12.50` per connected ton per month**, or
    # `$150` per ton-year, which sits inside the ordinary North American
    # municipal district-cooling capacity band.
    #
    # ⚠ **THE ONE THING THAT COULD NOT BE VERIFIED, STATED RATHER THAN
    # SMOOTHED OVER:** the Lansing and Mesa rate PDFs are both blocked by this
    # environment's network egress policy, so the `$50.00`, the `$49.49` and
    # the Ton-Hour definition are quoted from search results rather than read
    # off the tariff. The STRUCTURE (a monthly per-ton capacity charge on
    # connected tonnage) is corroborated by four independent North American
    # municipal utilities; the exact cent is one utility's, read at one remove.
    #
    # **Worked, on the PO's own two numbers:** a **100-ton** connection bills
    # `100 × $12.5000` = **`$1,250.00`** a month; a **200-ton** connection
    # bills **`$2,500.00`**. A building with a 100-ton and a 25-ton connection
    # is **125 tons** = `$1,562.50`, because thermal SUMS.
    "thermal_heat": "12.5000",
}

#: **RETIRED 2026-09-02 (`CR-062` D8) — the two names this file used to carry.**
#:
#: `CAPACITY_UNPRICED = "0"` and `CAPACITY_UOM = "month"` are GONE, together, in
#: the commit that signed the prices. They are named here rather than deleted in
#: silence so a reader following an older defect row, docstring or review-ledger
#: entry finds where they went: the price is `CAPACITY_UNIT_PRICES` above, and
#: the unit is each service's own declaration, resolved by
#: `rating.sample_data._capacity_uom` and defaulted by nobody.
#:
#: **Grep either name and you should find only this comment.** A name that still
#: resolves is a name a lane can still reach for, and the whole point of `D8` is
#: that the price can no longer travel without its unit.
_CAPACITY_RETIRED_NAMES = ("CAPACITY_UNPRICED", "CAPACITY_UOM")


#: **The monthly BASE a seeded capacity service charges — `$0.00`.**
#:
#: The `BASE-S` / `TRASH_BASE` precedent, unchanged: *"a base nobody signed is a
#: base this fixture does not invent"*. The billing workbook `[W] §1` names a
#: base for electric, water and gas and none for solar, broadband or battery.
#:
#: ⚠ **`"0"` IS A PRICE AND AN OMISSION IS A REFUSAL**, exactly as two constants
#: up — a blank base means *this size is not served* and stops the bill
#: (`CR-013` part 1 / `DEF-277`).
#:
#: Read TWICE and deliberately so: `apps/rating/sample_data` states it on the
#: plan's `plan_services.base_charge` AND on `BR-RAT-088`'s `is_base` charge
#: code, and `DEF-455` requires those two *"agree to the cent by
#: construction"* — `DEF-2823` is what it costs when they do not.
CAPACITY_BASE = "0"

#: BR-RAT-015 ❄️ SUPERSEDED / GT-17 ❄️ RE-SIGNED 2026-09-08 — percent POINTS, as
#: `tariff_versions.percent` stores what the tenant typed on S11 (see
#: percent_of_service.py's own docstring).
#:
#: ⚠ **THIS READ `"40"` UNTIL 2026-09-08 AND IT WAS A DIFFERENT KIND OF NUMBER.**
#: The 40 was a PRICE RATIO — what sewer cost relative to water's money. The 90
#: is a **RETURN-TO-SEWER FACTOR**: the fraction of metered water that
#: physically reaches the sewer, sourced at 79–95% across North American
#: municipal utilities and clustering on 90%. PO, `CR-081`, verbatim: *"C —
#: factor 90%, rate $5.00 → $36.00, which is what a real sewer customer actually
#: pays"*.
#:
#: ⚠ **DO NOT LOWER IT TO ALLOW FOR GARDENS.** The irrigation allowance is made
#: by **winter-quarter averaging** — billing sewer on the cold-months water
#: average — which B4 has carried as *"winter-averaging v1.1"* since it was
#: written and which this product does not do. Lowering the factor instead would
#: under-bill every apartment and every commercial account that waters nothing.
SEWER_PERCENT_OF_WATER = "90"

#: `CR-081` — SEWER'S OWN RATE PER UNIT, which sewer has never had on any
#: tenant. Money is stored to 4 decimals (hard rule 2). The PO signed `$5.00`
#: with the factor, in one sentence, and it is the round municipal figure the
#: research clustered on; `$4.9375` — the rate that would have held `WE-1` at
#: its old `$15.80` — was shown to them and not chosen.
#:
#: **FLAT, NOT TIERED, AND THE REASON IS PHYSICAL.** 66 of 88 municipal
#: wastewater utilities surveyed bill a uniform rate, 13 incline and 9 are flat
#: monthly; inclining tiers exist to curb *outdoor* use, which is exactly the
#: water that never reaches the sewer. A sewer ladder would price the gallons a
#: sewer never sees.
SEWER_RATE_PER_UNIT = "5.0000"

#: `CR-130-BRC07` — **WHICH BASIS THE SEEDED SEWER SCHEDULE IS ON**, stated
#: rather than left to the column default (PO ruling 2026-09-22, `BR-RAT-1030`).
#: `'usage'` is `CR-081`'s volume basis: 90% of the metered water QUANTITY,
#: priced at `SEWER_RATE_PER_UNIT` above. ❄️ GT-17 = 90% x 8 kgal x $5.0000 =
#: **$36.00** and GT-25 = **$27.00** are both this basis.
#:
#: ⚠ **IT IS A CONSTANT SO THE FIXTURE SAYS IT OUT LOUD.** The other basis,
#: `'charge'`, would take 90% of the water MONEY and bill a completely
#: different number off the same two figures — `$35.55` on GT-17's own bill,
#: not `$36.00`. A seed that relied on the default would go on passing the day
#: somebody moved the default, which is the class of silence this repo keeps
#: paying for.
SEWER_PERCENT_BASIS = "usage"
# [W] §1 Small Commercial.
COMMERCIAL_WATER_FLAT = "5.20"
COMMERCIAL_WATER_BASE = "15.00"

# ══════════════════════════════════════════════════════════════════════════
# DEF-2397 · WHAT A NON-WATER BACKBONE COSTS — THE BASE IS SIGNED, THE USAGE
# IS NOT, AND THE TWO ARE STATED SEPARATELY BECAUSE THEY HAVE DIFFERENT
# EVIDENCE BEHIND THEM
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE ESTATE AND THE TARIFF WERE SHAPED BY TWO DIFFERENT RULES AND THAT
# COST EVERY BILL ON THREE SERVICES (`DEF-2397`, measured on PostgreSQL 16).**
# `estate_plan` above has given an electric utility an electric backbone since
# CR-039 wave A — 70 premises, 118 units, 75 service points, 70 `E-` meters and
# 193 kWh reads — and `apps/rating/sample_data` went on seeding schedules for
# `water`, `sewer` and `trash` in literals. No plan existed, every unit kept
# `rate_plan_id` NULL, all 48 seats were refused
# `customers.account.plan_required_at_activation` (`BR-MET-040`) and the tenant
# billed **ZERO**. Electric, gas and storm water, all three the same shape.
#
# ⚠ **AND THE FIX COULD NOT BE "PRICE THE USAGE", BECAUSE NO SIGNED FIGURE
# PRICES IT AGAINST THE REGISTER THIS FIXTURE PLANTS.** Spec rule 7 — *"where a
# rule is unsigned, the seeder stubs and mints a question rather than choosing a
# number that then looks official"* — so the split below is not a convenience,
# it is the only lawful shape. Service by service, with the evidence:
#
#   * **electric — the base IS signed and the usage shape does not fit.**
#     `ELECTRIC_BASE` is `[W] §1`'s *"Base/mo … Electric $12"*. The only
#     residential electric USAGE tariff the workbook states is TIME OF USE
#     (*"summer on $0.22 / mid $0.14 / off $0.09; winter $0.18/$0.12/$0.08"*),
#     and a TOU schedule prices per WINDOW: it needs `tou_on` / `tou_mid` /
#     `tou_off` registers. **Every meter this fixture plants carries ONE
#     REGISTER** — one channel, `total` — and `consumption()` returns one
#     monthly figure, so there is nothing for three windows to be taken from.
#     ⚠ **This is NOT the one-metered-service rule `CR-062` C1 withdrew**, and
#     the two sound alike: the estate now plants a meter per unit PER METERED
#     SERVICE, and each of those meters still holds a single register. Adding
#     electric to a water tenant does not give electric three TOU windows. The industrial `$0.085/kWh` is half of a
#     `demand` tariff (`+ $11.00/kW`) and needs a demand read this estate does
#     not take either. Re-reading either as a flat residential rate would be
#     inventing a tariff out of a figure signed for something else.
#     ⚠ **THE INDUSTRIAL HALF OF THAT SENTENCE IS SUPERSEDED FOR THE DEMO
#     ESTATE — PO RULING 2026-09-02, VERBATIM: *"for usage line use
#     $0.085/kWh"*** (`CR-062` addendum J4). It is kept and not deleted,
#     because **the reasoning above remains true of a real tariff**: `$0.085`
#     per kWh really is half of an energy-plus-demand pair, and a utility that
#     configured it alone on a real industrial customer would be under-billing.
#     What the ruling changes is what the DEMO does with it — the PO was shown
#     that reasoning and a `$0.00` alternative and chose the rate.
#     **THE COST IS STATED RATHER THAN HIDDEN, which is what is owed for a
#     ruling like this:** the seeded plant draws 54,000 kWh at a **100 kW**
#     peak, so the demand half this demo does not charge is
#     `100 kW × $11.00` = **`$1,100.00`** on a bill of **`$4,770.00`**. The
#     demand read that would justify it is still not taken, and seeding one
#     would be inventing a register. See `INDUSTRIAL_ELECTRIC_PER_KWH` for the
#     figure and `UNIT_SERVICE_CONSUMPTION` for the draw.
#   * **gas — the base AND the usage are both signed, and both are seeded.**
#     `[W] §1` states *"Gas add-on · Gas flat $1.15/ccf · $6"*. The base is
#     `GAS_BASE` below and the usage is `GAS_FLAT_PER_CCF`, carried into
#     `METERED_USAGE_PRICES` from 2026-09-07.
#     ⚠ **THIS BULLET SAID *"the usage is signed IN THE WRONG UNIT"* UNTIL
#     2026-09-07 (`DEF-MET-4502` for the prose, `DEF-RAT-4516` for the money),
#     AND THE REASON EXPIRED FIVE DAYS BEFORE THE SENTENCE DID.** It argued that
#     the `$1.15` is per `ccf` while the seeded register reads `therm`, so
#     pricing the read on it would be `OQ-004`'s forbidden silent conversion and
#     `OQ-303` option (B) — a signed figure quietly made to mean something else.
#     **That was true, and `BR-TEN-1180` / the PO-filed `DEF-3230` removed its
#     premise on 2026-09-02** by swapping `SERVICE_DEFAULT_UOMS["gas"]` to
#     `("ccf", "therm")`. The seeded register reads `ccf`, the signed price is
#     per `ccf`, no conversion is asked for and none is invented — so the figure
#     applies EXACTLY AS SIGNED. Nothing was reinterpreted to get here.
#   * **storm water — NOTHING is signed, and that is now the ruled answer.**
#     The workbook prices no storm water at all. The PO ruled on 2026-09-01
#     that storm water is a **CAPACITY** service (*"metered / share of another
#     service / capacity"*), sized by impervious area, and `BR-MET-108` rules
#     that **an absent characteristic bills as ZERO** — PO verbatim, *"Bill it
#     as zero"* — never refused. No unit carries an impervious-area
#     characteristic, so `$0.00` IS what this service costs today, and the
#     ruling requires the zero be **stamped and surfaced, never silent**, which
#     `apps/rating/sample_data.NOT_SEEDED` is where a person reads it.
#
#: **`[W] §1` Small Commercial — *"Elec $48"*, the commercial half of the same
#: Base/mo column `ELECTRIC_BASE` reads.**
#:
#: ⚠ **THE BASE IS SEPARABLE FROM THE TARIFF, AND THAT IS WHY THIS IS A CITATION
#: AND NOT AN INVENTION.** `seed_demo`'s omissions list leaves the Small
#: Commercial electric out — *"the workbook states the PRICES but no window
#: boundaries anywhere, and a TOU version cannot be stored without them"* — and
#: that omission is about the USAGE tariff. The Base/mo column is a separate,
#: complete statement, read here exactly as `COMMERCIAL_WATER_BASE` reads the
#: `$15` beside it on the very same row.
#:
#: `BR-RAT-108` separates one service's two amounts by CLASS and never by name,
#: so this is a second `is_base` charge code (`BASE-E-COM`), not a rename.
COMMERCIAL_ELECTRIC_BASE = "48.00"

#: **`[W] §1` — *"Gas add-on … $6"*, the monthly base for having gas.** It is a
#: signed figure with the same standing as `WATER_BASE` and `ELECTRIC_BASE`, and
#: it is what a seeded gas tenant's bill is made of.
#:
#: **ONE FIGURE FOR BOTH CLASSES, because the workbook states one.** Water and
#: electric each get a residential and a commercial row in `[W] §1`; the Gas
#: add-on row states a single base and names no class, so both seeded plans
#: carry it. Splitting it would be inventing the commercial half.
GAS_BASE = "6.00"

#: **`[W] §1` line 22 — *"Gas flat $1.15/ccf"*. SIGNED, AND SEEDED SINCE
#: 2026-09-07 (`DEF-RAT-4516`).**
#:
#: ⚠ **THIS NOTE SAID *"RECORDED AND SEEDED NOWHERE"* FOR AS LONG AS IT EXISTED,
#: AND ITS OWN STATED RELEASE CONDITION HAD BEEN MET FIVE DAYS EARLIER.** It
#: read: *"it becomes usable the day a gas tenant declares `ccf` as its primary
#: UoM, or a therm→ccf factor is ruled"*. **That day was 2026-09-02** —
#: `BR-TEN-1180` / the PO-filed `DEF-3230` swapped `SERVICE_DEFAULT_UOMS["gas"]`
#: from `("therm", "ccf")` to `("ccf", "therm")` so the seeded register would
#: agree with this very figure. The swap moved the seed map and the tests and
#: **did not move the paragraph that explains the figure**, so a lane reading
#: this was sent to rule a conversion factor nobody needs. That staleness is
#: `DEF-MET-4502`; this is hard-won law 1 in fixture form — *a comment claiming
#: a guarantee is not the guarantee* — and it cost a live customer-facing
#: `$0.00` usage line for five days.
#:
#: **WHY NO CONVERSION IS INVOLVED, since the old note spent a paragraph on it:**
#: `therm` is declared ENERGY and `ccf` VOLUME (`register_units.DIMENSION_OF`),
#: so `BR-MET-143`'s verdict for the pair is `dimension` and
#: `multiplier_can_reconcile` is **False** — no factor reconciles them and none
#: ever can, because the conversion needs a heating value, which is a physical
#: fact about the gas and not a column on `tenant_services`. The register was
#: therefore MOVED rather than converted, which is also the physically ordinary
#: shape: a gas meter's register is volumetric and a therm is computed from it.
#: `OQ-004`'s *"no silent conversion"* is satisfied because there is no
#: conversion at all — the read, the register, the tariff and the workbook all
#: say `ccf`.
#:
#: ⚠ **TWO SPELLINGS OF ONE FIGURE, ON PURPOSE.** This constant quotes the
#: WORKBOOK, so it is spelled the way the workbook states it. What is STORED is
#: `METERED_USAGE_PRICES["gas"]` at `"1.1500"`, because CLAUDE.md hard rule 2
#: stores money to four decimals and `CR-062` E8 asserts that spelling on every
#: seeded figure. `$1.15` is exact at two decimals so no precision is at stake;
#: the two are pinned to each other by a Decimal-equality assertion in
#: `tests/test_def2397_service_shaped_rating.py` so they cannot drift.
#:
#: **Worked, on the seeded gas tenant's reference customer:** meter `G-5000`
#: reads **40 ccf** in June (`CONSUMPTION_SCALE["gas"]` is 5, and unit 0 draws
#: 8 of the declared shape). Its usage line is `40 × $1.15` = **`$46.00`** and
#: its bill is `$46.00 + $6.00` base = **`$52.00`** before tax, where it was
#: `$6.00` and twelve cents of tax until 2026-09-07.
#: 🔒 HUMAN-REVIEW-PENDING — this figure decides MONEY on every seeded gas
#: tenant. Row in `12-governance/09-human-review-ledger.md` with the worked
#: figure above.
GAS_FLAT_PER_CCF = "1.15"

#: **THE BACKBONE USAGE PRICE WHERE NO SIGNED FIGURE FITS — `OQ-1290`.**
#:
#: ⚠ **THIS IS A PLACEHOLDER AND IT NAMES ITS QUESTION AT THE LINE THE FIGURE
#: SITS ON, WHICH IS `DEF-491`'s WHOLE LESSON.** A `0.00` under a comment
#: explaining itself is invisible to every check in this repo: the trash
#: schedule sat at zero for a day AFTER `OQ-303` was ruled because the
#: placeholder cited no question, so closing the question moved nothing and
#: nothing noticed. Close `OQ-1290` and this constant is the one line to change.
#:
#: ⚠ **A STORED ZERO, NEVER AN OMISSION, AND THE DIFFERENCE IS A REFUSAL.**
#: `CR-013` part 1 (PO 2026-08-19) makes a BLANK figure mean *this size is not
#: served* and `gather._base_charge_for` stops the bill on it (`DEF-277`); a
#: stored zero is a PRICE and prints `$0.00` (PO 2026-08-19, *"print $0.00"*).
#: `OQ-670` closed on the same reading for a service a plan prices nowhere —
#: PO verbatim, *"(b) Bill $0.00"* — because *"the zero line buys VISIBILITY,
#: putting the gap on the document instead of in a silence"*. That is the
#: choice being made here too: an electric demo bills its signed `$12.00` base
#: with a `$0.00` usage line naming the gap, rather than refusing 48 accounts.
#:
#: **Worked, on the seeded electric tenant:** unit 0 draws `8 × 100 = 800 kWh`
#: in June; its line is `800 kWh × $0.0000 = $0.00` and its bill is the
#: `$12.00` base plus tax. Under `[W] §1`'s TOU prices the same 800 kWh would
#: be roughly `$100` — which is the size of the question, and why it is asked
#: rather than guessed.
#:
#: ⚠ **AMENDED 2026-09-02 (`CR-062` E1/E6): THIS NO LONGER REACHES ELECTRIC OR
#: THERMAL, AND THE WORKED EXAMPLE ABOVE IS THEREFORE HISTORY.** The PO's
#: statement (7) — *"Electric $12.00 base kWh read - along with base you will
#: need rate schedule - Either Tiered or TOU"* — answers `OQ-1290` for electric,
#: and statement (5) prices thermal. Electric now takes `ELECTRIC_TIERS` below
#: and thermal takes `METERED_USAGE_PRICES`; that same 800 kWh line is now
#: **`$95.50`**, not `$0.00`, and the estimate of *"roughly `$100`"* written
#: here when the question was open turns out to have been a good one.
#:
#: ⚠ **AMENDED 2026-09-07 (`DEF-RAT-4516`) — GAS IS PRICED AND `OQ-1290` IS
#: CLOSED, SO NO SEEDED SERVICE LANDS ON THIS ZERO ANY MORE.** This clause read
#: *"IT IS KEPT, NOT DELETED, BECAUSE `gas` STILL NEEDS IT"* — seeding the
#: signed `$1.15/ccf` was `CR-062` group B's business and `E1`–`E6` named six
#: services without gas among them. That is done: `METERED_USAGE_PRICES["gas"]`
#: is `"1.1500"` and the reference gas bill went from `$6.00` to `$52.00`
#: before tax. **All four metered services now price their usage** — water and
#: electric from their own tiers, thermal at `$0.045`, gas at `$1.15`.
#:
#: ⚠ **IT IS STILL KEPT, AND THE REASON IS NOW A DIFFERENT ONE — SAY SO RATHER
#: THAN LEAVING THE OLD REASON TO BE RE-READ.** The rule this file states is
#: *"a constant that still has one live caller is not a constant to retire"*
#: (`CAPACITY_UNPRICED` had none left, which is exactly why it went). This one
#: still HAS a live caller: `rating.sample_data._backbone_schedule_payload`
#: reads it as the `.get()` default for a metered service with no signed price.
#: What changed is that no service currently LANDS on it — the four in
#: `METERED_ESTATE_SERVICES` are all priced — so it is a defensive fallback
#: rather than a shipped `$0.00`. **A fifth metered service arriving unpriced
#: would find a stored zero that prints `$0.00` and names its gap, instead of a
#: blank that stops the bill (`CR-013` part 1 / `DEF-277`), which is the whole
#: reason the constant exists.** Retiring it would delete that safety net and is
#: a larger judgment than the defect that priced gas; it is recorded here rather
#: than taken quietly.
BACKBONE_USAGE_UNPRICED = "0"

#: **ELECTRIC'S USAGE PRICE — A TIERED LADDER, SIGNED BY THE PO 2026-09-02
#: (`CR-062` E1), ANSWERING `OQ-1290` FOR ELECTRIC.**
#:
#: PO verbatim, statement (7): *"Electric $12.00 base kWh read - along with base
#: you will need rate schedule - Either Tiered or TOU"*. **TIERED was chosen and
#: the choice is recorded rather than assumed** (`CR-062` step 5, judgment 2):
#: the engine supports both, but TOU needs three registers per meter
#: (`tou_on`/`tou_mid`/`tou_off`) and the seeded estate plants ONE, so a TOU
#: ladder would seed a schedule no seeded meter could answer. A real utility can
#: still configure TOU on Plans & Rates; this is the DEMO's ladder.
#:
#: **THE SHAPE IS `WATER_TIERS`' AND THE BOUNDARY CONVENTION IS ITS TOO** —
#: `(from_qty, to_qty, unit_price)` with each tier's `to` being the next tier's
#: `from`, which is how `GT-17`'s water `$39.50` reproduces (5 kgal at `$4.00`
#: plus 3 at `$6.50`). Reading them as `0–500` and `501–1000` gives the same
#: money; the engine's own convention is what is written.
#:
#: **Worked, on the seeded electric tenant's reference unit:** unit 0 draws
#: `8 × 100 = 800 kWh` in June.
#: `500 × $0.1100` = `$55.00`, `300 × $0.1350` = `$40.50`, so the usage line is
#: **`$95.50`** and the bill is `$95.50 + $12.00` base = **`$107.50`** plus tax.
#:
#: ⚠ **FOUR DECIMAL PLACES** — CLAUDE.md hard rule 2. `$0.11` is written
#: `"0.1100"`; the column stores 4 and DISPLAYS 2.
#: 🔒 HUMAN-REVIEW-PENDING — this ladder decides MONEY on every seeded
#: electric tenant; it takes the reference bill from `$12.00` to `$107.50`.
#: Row in `12-governance/09-human-review-ledger.md` with the worked figure.
ELECTRIC_TIERS: tuple[tuple[str, str | None, str], ...] = (
    ("0", "500", "0.1100"),
    ("500", "1000", "0.1350"),
    ("1000", None, "0.1600"),
)

#: **THE USAGE PRICE FOR A METERED SERVICE THAT IS PRICED FLAT, PER SERVICE —
#: `CR-062` E6.**
#:
#: `thermal_heat` and `gas` are here, and the map exists rather than a bare
#: constant for the reason `BACKBONE_BASE` is a map: a second flat-priced
#: metered service is a row, not a branch — **and on 2026-09-07 that prediction
#: was paid off exactly, by a row.** `water` is tiered and has its own
#: constants, `electric` is tiered and has `ELECTRIC_TIERS`, and a service
#: missing from this map falls back to `BACKBONE_USAGE_UNPRICED`'s stored zero.
#:
#: ⚠ **`gas` WAS DELIBERATELY ABSENT UNTIL 2026-09-07 AND ITS ABSENCE WAS THE
#: DEFECT (`DEF-RAT-4516`, PO: *"please fix this gap - One real gap, and it is
#: money. Gas bills $0.00 usage"*).** The stated reason was scope — seeding the
#: signed figure was `CR-062` group B's business and `E1`–`E6` named six
#: services without gas — and behind that a real blocker: the seeded gas
#: register read `therm` while `[W] §1` signs the price per `ccf`. **The
#: blocker was removed on 2026-09-02** by `BR-TEN-1180` / the PO-filed
#: `DEF-3230`, which swapped the register to `ccf` for this exact purpose, and
#: the absence outlived it by five days on a live money path.
#:
#: **Thermal at `$0.045` per ton-hour** was put to the PO in plain English with
#: a worked figure and approved (`CR-062` step 5, judgment 3).
#:
#: ⚠ **`$0.045` IS WHY FOUR DECIMAL PLACES ARE NOT A FORMALITY HERE.** At two it
#: would round to `$0.05` — an **11% overcharge on every thermal line** — so the
#: figure is written `"0.0450"` and CLAUDE.md hard rule 2 is doing real work
#: rather than being observed for tidiness.
#:
#: **Worked, on the seeded thermal tenant:** unit 0 draws `8 × 5 = 40 ton-hr` in
#: June; its usage line is `40 × $0.0450` = **`$1.80`**.
#: ⚠ **AND `thermal_heat` RETIRED ON 2026-09-07 (`CR-080`), WHICH EMPTIES THIS
#: MAP AND RETIRES THE ONE PO-APPROVED FIGURE THIS CR REMOVES.** The PO ruled
#: thermal capacity-based on connected tonnage — *"connected tonnage - it is
#: capacity not metering"* — and **a capacity service has no ton-hour to
#: price**, so `$0.045 per ton-hour` has nothing left to multiply. Everything
#: above about four decimal places and the `$1.80` June line is TRUE OF A
#: BILLING SHAPE THIS PRODUCT NO LONGER HAS FOR THERMAL; it is kept because it
#: is the record of a figure the PO personally approved, and a retirement with
#: no trace reads exactly like a figure nobody ever signed.
#:
#: **What replaces it is `CAPACITY_UNIT_PRICES["thermal_heat"]`** — a per-ton
#: MONTHLY rate, researched rather than invented, and flagged there as this
#: lane's judgment under the PO's market-research delegation.
#:
#: ⚠ **AND THE MAP IS NOT EMPTY AFTER ALL — `gas` LANDED IN IT HOURS BEFORE
#: THERMAL LEFT IT, ON 2026-09-07 (`DEF-RAT-4516`, closing `OQ-1290`).**
#: The two changes are independent and both stand: the workbook's signed
#: `$1.15/ccf` is seeded for gas, and thermal's `$0.045` per ton-hour retires
#: because thermal no longer reads a register. **The map was written for a
#: flat-priced METERED service and gas is exactly that**, so the rule below
#: is doing its job rather than being preserved for its own sake.
#:
#: ⚠ **THE MAP STAYS EVEN IF ITS LAST ROW EVER LEAVES.** `apps/rating/sample_data`
#: reads it with `.get(...)` for every metered service, and the docstring above
#: states the rule that decides who belongs here — *"a second flat-priced
#: metered service is a row, not a branch"*. Deleting it would delete that
#: rule along with the row, and the next flat-priced metered service would
#: arrive as a branch.
METERED_USAGE_PRICES: dict[str, str] = {
    # ── [W] §1 line 22 · "Gas flat $1.15/ccf" (DEF-RAT-4516, 2026-09-07) ────
    # The workbook's own figure, applied in the unit it is signed in against a
    # register that reads that unit. `GAS_FLAT_PER_CCF` above quotes the
    # workbook at "1.15"; this is the STORED spelling at four decimals
    # (CLAUDE.md hard rule 2, asserted by CR-062 E8), and a Decimal-equality
    # test pins the two together so neither can drift.
    #
    # WORKED, and it is the acceptance figure: the reference gas customer's
    # meter G-5000 reads 40 ccf in June, so the usage line is 40 x $1.15 =
    # $46.00 and the bill is $46.00 + $6.00 base = $52.00 before tax. It was
    # $6.00 and twelve cents of tax the day before this row was added.
    "gas": "1.1500",
}

#: **The base charge for ONE seeded backbone service, and where each figure
#: comes from.** `apps/rating/sample_data` reads this to build both the plan's
#: `plan_services.base_charge` and `BR-RAT-088`'s `is_base` charge code, so the
#: two agree to the cent by construction (`DEF-455`'s own requirement).
#:
#: ⚠ **A SERVICE WITH NO SIGNED BASE IS STATED AS `"0"`, NOT OMITTED — the
#: sewer precedent, unchanged.** `BASE-S` has read `"0"` since it was written,
#: for exactly this reason: *"the workbook's §1 base column names one for
#: electric and water and none for sewer, and a base nobody signed is a base
#: this fixture does not invent."* Storm water is the same fact about a
#: different service.
#:
#: ⚠ **`water` IS NOT HERE ON PURPOSE.** It has TWO bases — residential `$8.00`
#: and commercial `$15.00`, `BR-RAT-108`'s one-service-two-classes shape — and
#: they are stated where they always were (`WATER_BASE` /
#: `COMMERCIAL_WATER_BASE`), so no water figure moves for this defect.
#:
#: 🔒 HUMAN-REVIEW-PENDING · this map decides MONEY on every seeded electric,
#: gas and storm-water tenant — it is the plan's `plan_services.base_charge` AND
#: `BR-RAT-088`'s `is_base` charge code, which is why it is ONE map and not two
#: literals. Row in `12-governance/09-human-review-ledger.md` with the worked
#: figure. Every entry CITES the billing workbook `[W] §1` rather than choosing
#: a number, exactly as `TRASH_BASE` above implements a ruling it did not make.
#:
#: `service → (residential base, commercial base)`, both as decimal STRINGS.
BACKBONE_BASE: dict[str, tuple[str, str]] = {
    # [W] §1 Residential Standard "Base/mo … Electric $12" · Small Commercial
    # "Elec $48". Two figures, two classes, BR-RAT-108's own shape.
    "electric": (ELECTRIC_BASE, COMMERCIAL_ELECTRIC_BASE),
    # [W] §1 "Gas add-on … $6" — one signed figure, no class named, so both.
    "gas": (GAS_BASE, GAS_BASE),
    # ⚠ **`storm_water` LEFT THIS MAP ON 2026-09-02 (`CR-062` C9, `DEF-3231`).**
    # It read `("0", "0")` — nothing signed — and it is gone rather than left as
    # a dead entry, because this map is what `apps/rating/sample_data` walks to
    # build a plan's `plan_services.base_charge` for a METERED service, and
    # storm water is capacity-billed now. Its base is `fixture.CAPACITY_BASE`,
    # which states the same `"0"` for the same reason and moves no money.
    # ⚠ **`thermal_heat` LEFT THIS MAP ON 2026-09-07 (`CR-080`), EXACTLY AS
    # `storm_water` LEFT IT ON 2026-09-02 AND FOR THE SAME REASON.** It read
    # `("0", "0")` — nothing signed — and it is gone rather than left as a dead
    # entry, because this map is what `apps/rating/sample_data` walks to build
    # a plan's `plan_services.base_charge` for a METERED service, and thermal
    # is capacity-billed now. Its base is `fixture.CAPACITY_BASE`, which states
    # the same `"0"` for the same reason and moves no money.
}

#: [F] `lookup_defaults.json.tax_jurisdictions.TX`, stored as FRACTIONS because
#: `taxes.rate` is a fraction (US-RAT-009 TC-1: 6.25% → "0.062500"). Two
#: authorities at different rates is spec §2's own requirement, so the
#: remittance report has more than one row.
#:
#: ⚠ `jurisdiction` AMENDED 2026-08-16 (DEF-166 lane) TO THE NAMES THE PLATFORM
#: REFERENCE CATALOGUE ACTUALLY SEEDS. It said `State` and `City`, and no tenant
#: has a jurisdiction by either name: `lookup_defaults.json.tax_jurisdictions.TX`
#: seeds **`Texas State`** (6.25%) and **`Local`** (2.00%). So the seeder found
#: no match and CREATED two more jurisdictions — a run writing into a REFERENCE
#: CATALOGUE, which BR-TEN-058 forbids outright (*"reference vocabulary is NOT
#: sample data"*), and `test_us_ten_019_tc4` is the test that says so.
#: **No money moves:** the rates are unchanged and are the same signed pair,
#: 6.25% and 2.00%, because the pair the fixture was inventing WAS this pair
#: under different labels. Spec rule 1 applied exactly as written — where the
#: fixture disagrees with signed law, THE FIXTURE CHANGES.
TAX_AUTHORITIES: tuple[dict[str, str], ...] = (
    {
        "name": "State water tax",
        "jurisdiction": "Texas State",
        "level": "state",
        "rate": "0.0625",
    },
    {"name": "City utility tax", "jurisdiction": "Local", "level": "city", "rate": "0.02"},
)

# ── The calendar (spec §3, AS AMENDED 2026-08-17) ───────────────────────────
# ⚠ AMENDED 2026-08-17 — CR-010 Part-10.4 (PO verbatim: *"do 1 month billed na
# dkeep other month ready"*). The 2026-08-16 spec said June AND July BILLED;
# the PO amended it to **JUNE issued and mostly paid, JULY READY-TO-RUN** —
# July's reads are staged and committed, nothing about July is billed — so the
# trial's FIRST bill run is July, on prepared data. August stays read-and-
# unbilled behind it, so a second run is also waiting once July has been
# watched working. The superseded sentence is stamped in
# 08-qa/04-fixtures/02-demo-tenant-spec.md §3 in the same commit.
#
# THE 70-DAY PAST-DUE CASE IS UNCHANGED BY THIS AMENDMENT, stated so nobody
# re-derives it: CASE_PAST_DUE_70's ageing always came from the JUNE bill being
# left unpaid (period start 1 June against the 8 August busy day), never from
# July's, so flipping July to ready-to-run moves no date and re-ages nothing.
# ── THE CALENDAR TRAVELS WITH THE CLOCK — DEF-LED-6640 (2026-09-25) ─────────
# ⚠ **EVERY DATE IN THIS SECTION USED TO BE A `date()` CONSTANT, AND THAT WAS
# THE DEFECT.** June billed, July billed, August read-and-unbilled — correct
# the day they were typed, and **wrong from 1 September onwards**, because the
# Finance screens show the CURRENT accounting period (`useFinancePeriod` →
# `GET /shell/display`, computed per `BR-TEN-022`) and there is no period
# picker to move off it. So on 2026-09-24 a clerk opened Finance on a database
# holding 80 invoices, 66 payments and 167 journal entries and read:
#
#     BILLED THIS MONTH  $0.00        COLLECTED  $0.00
#
# Nothing was broken and nothing was lying; the money was in a month the screen
# cannot show. **A demo fixture pinned to fixed months has an expiry date
# nobody wrote down** — hard-won law 2's *"a rule with a clock in it"*, which
# rots on the day the clock passes it rather than on the day it is written.
#
# ⚠ **THE SHAPE IS WHAT IS SIGNED, NOT THE MONTHS.** The three periods below
# are kept exactly as they were written and are now read as a shape stated
# RELATIVE TO THE FIXTURE'S OWN "TODAY", which the spec has always said is
# mid-August:
#
#     M-2  billed, ~95% collected      (canonically June)
#     M-1  billed, 0% collected        (canonically July)
#     M    READ AND UNBILLED — OPEN    (canonically August)  ← today is in here
#
# The whole table is shifted by a whole number of MONTHS so that **today always
# falls inside the open, unbilled period**. Nothing else about it moves: the
# day-of-month, the collected shares, the bill lag and the busy day are the
# figures that were signed, carried forward.
#
# ⚠⚠ **THE UNBILLED MONTH MUST SURVIVE THIS AND DOES.** `PERIODS` leaves a
# month unbilled because it is the Product Owner's own acceptance test —
# *"everything done leaves nothing to evaluate"* (CR-010 Part-10.4, and CR-040
# task C9 when the count of finished cycles rose from one to two). Shifting the
# calendar bills NOTHING new: **the last entry is still `billed: False`, so no
# bill covers the OPEN SERVICE PERIOD and the Product Owner's own run is still
# the one waiting.** What changes is that the two cycles BEHIND it, and the cash
# collected against them, are now in months a clerk can still see.
#
# ⚠⚠ **AND THE INVARIANT IS THE SERVICE PERIOD, NOT THE KPI — THIS COMMENT SAID
# *"BILLED THIS MONTH is still `$0.00`, deliberately"* FOR ABOUT AN HOUR AND IT
# IS WRONG.** Measured in a browser on the first tenant seeded with a travelling
# calendar (2026-09-25, build `2.351.86`): **BILLED THIS MONTH reads
# `$15,734.17`**, over the words *"Posted between 2026-09-01 and 2026-09-30"*.
# The tile counts by **POSTING DATE**; the acceptance test is about the
# **SERVICE PERIOD**. They are different questions.
#
# **Both are true at once, and both were measured on that tenant:**
#
#     bills covering a September SERVICE period        0
#     bills POSTED in September                       45, every one of them
#                                                     covering 2026-08-01
#                                                     to 2026-08-31
#     September reads, committed, awaiting the run   117
#
# That is bill run 2 going out on the 2nd, exactly as this fixture has always
# issued it. **On the old constants, at the fixture's own mid-August "today",
# the same tile showed July's bill posted on 2 August — it was never `$0.00`
# there either.** The `$0.00` was a SYMPTOM of the defect (a tenant whose newest
# bill had posted six weeks earlier), never a property of the design, and
# carrying it forward as a rule would have sent the next lane to "fix" a screen
# that is now correct.
#
# ⚠ **DETERMINISM: the wall clock is read ONCE, here, and every other date in
# this fixture is derived from it.** `SBH_FIXTURE_TODAY` overrides it with an
# ISO date, and the test suite pins it to the anchor below
# (`config/settings/test.py`), so every existing test sees exactly the constants
# it was written against and the travelling is proved by one test that names its
# dates out loud (`tests/test_def_led_6640_the_calendar_travels.py`). A fixture
# that reads the clock in twenty places is a fixture nobody can reproduce.
#
# ⚠ **G6's wall-clock ban is NOT being dodged.** `BR-TEN-043` bans a wall clock
# **in a money path**, and G6 scans `06-backend/apps/`. This file is a
# DECLARATION in `core/` with no Django import and no service call; it states
# what day the demo is set on, exactly as it states what a meter reads. A money
# path that needs that day reads `fixture.TODAY`, which is a declared figure,
# never `date.today()` of its own.

#: The day the hand-written calendar above was drawn around — the fixture's own
#: "today", and the `read_on` of its open period. The offset is measured FROM
#: here, so an offset of 0 reproduces the 2026 constants byte for byte.
FIXTURE_ANCHOR_TODAY = date(2026, 8, 14)

#: Environment override for the fixture's "today", as an ISO date. Set by the
#: test settings to `FIXTURE_ANCHOR_TODAY` so the suite is deterministic, and
#: by a lane that wants to see what the demo looks like in another month.
FIXTURE_TODAY_ENV = "SBH_FIXTURE_TODAY"


def fixture_today() -> date:
    """The day this fixture is set on: `SBH_FIXTURE_TODAY` if it is set and
    parseable, otherwise the real one.

    ⚠ **A MALFORMED OVERRIDE RAISES RATHER THAN FALLING BACK.** A typo that
    silently reverted to the wall clock would make a run that was asked to be
    deterministic non-deterministic without saying so — hard-won law 14's
    *"a flag that is silently ignored is worse than one that errors"*.
    """
    raw = os.environ.get(FIXTURE_TODAY_ENV, "").strip()
    if not raw:
        return date.today()
    return date.fromisoformat(raw)


def _shift_months(day: date, months: int) -> date:
    """`day` moved `months` whole calendar months, with MONTH-END STICKINESS.

    ⚠ **THE STICKINESS IS LOAD-BEARING AND THE FIRST DRAFT DID NOT HAVE IT.**
    The billed periods are WHOLE CALENDAR MONTHS — the 1st to the last day —
    and a naive day-preserving shift turns 30 June into 30 July, which is a
    31-day month ending a day early. The next period still starts on the 1st,
    so the fixture grows a **one-day hole** between two consecutive periods:
    a day of consumption that no bill covers, on a money path. So a date that
    is the last day of ITS month lands on the last day of the target month.
    """
    total = day.year * 12 + (day.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last_of_source = calendar.monthrange(day.year, day.month)[1]
    last_of_target = calendar.monthrange(year, month)[1]
    if day.day == last_of_source:
        return date(year, month, last_of_target)
    return date(year, month, min(day.day, last_of_target))


def calendar_offset_months(today: date | None = None) -> int:
    """How many whole months the canonical calendar is shifted by, so that the
    OPEN period is the month `today` is in. Zero on the anchor day."""
    today = today or fixture_today()
    return (today.year - FIXTURE_ANCHOR_TODAY.year) * 12 + (
        today.month - FIXTURE_ANCHOR_TODAY.month
    )


def build_calendar(today: date | None = None) -> dict[str, Any]:
    """The canonical calendar shifted onto `today`. Pure — no clock of its own
    once `today` is given, so a test can state the day it means.

    Returns `{"today", "offset_months", "opening_read_on", "periods",
    "busy_day"}`.

    ⚠ **EVERYTHING THAT MUST ALREADY HAVE HAPPENED IS CLAMPED TO `today`.** On
    the anchor day nothing clamps and the result is the 2026 constants. Run on
    the **3rd** of a month, though, the shifted busy day (the 8th) and the open
    period's read (the 14th) would both be in the FUTURE — a demo containing a
    payment banked next week and a meter read nobody has taken. So they are
    pulled back to today, and the open period is simply SHORT, which is what a
    month in progress actually looks like. The billed periods are never
    clamped: they are wholly in the past by construction.
    """
    today = today or fixture_today()
    offset = calendar_offset_months(today)
    periods: list[dict[str, Any]] = []
    for row in CANONICAL_PERIODS:
        moved = dict(row)
        moved["start"] = _shift_months(row["start"], offset)
        moved["end"] = _shift_months(row["end"], offset)
        moved["read_on"] = _shift_months(row["read_on"], offset)
        moved["bill_on"] = (
            _shift_months(row["bill_on"], offset) if row["bill_on"] else None
        )
        if moved["bill_on"] and moved["bill_on"] > today:
            moved["bill_on"] = today
        if not moved["billed"]:
            moved["end"] = min(moved["end"], today)
            moved["read_on"] = min(moved["read_on"], today)
        periods.append(moved)
    busy = min(_shift_months(CANONICAL_BUSY_DAY, offset), today)
    return {
        "today": today,
        "offset_months": offset,
        "opening_read_on": _shift_months(CANONICAL_OPENING_READ_ON, offset),
        "periods": tuple(periods),
        "busy_day": busy,
    }


#: The OPENING read — the register baseline every subsequent consumption is
#: measured FROM. Without it June's read has no prior value, so metering emits
#: `consumption = NULL` (correctly: a first read measures nothing) and the bill
#: run reports every account as having no usable read. It is dated before the
#: first billed period on purpose: it is not billed and never was.
CANONICAL_OPENING_READ_ON = date(2026, 5, 31)

CANONICAL_PERIODS: tuple[dict[str, Any], ...] = (
    {
        "key": "june",
        "start": date(2026, 6, 1),
        "end": date(2026, 6, 30),
        "read_on": date(2026, 6, 30),
        "bill_on": date(2026, 7, 2),
        "billed": True,
        "collected_share": Decimal("0.95"),  # spec §3 "~95% collected"
    },
    {
        "key": "july",
        "start": date(2026, 7, 1),
        "end": date(2026, 7, 31),
        "read_on": date(2026, 7, 31),
        # ⚠ **BILLED AGAIN SINCE 2026-08-27 — CR-040 task C9.** This entry read
        # `billed: False` from 2026-08-17 under CR-010 Part-10.4 (PO verbatim:
        # *"do 1 month billed na dkeep other month ready"*), and the comment
        # that stood here warned that anyone billing July was deleting the PO's
        # acceptance test. **The same author reversed it:** *"I want you to
        # complete 2 billing cycle and create data for 3rd billing cycle"*.
        #
        # ⚠ **AND THE ACCEPTANCE TEST IS NOT DELETED — IT MOVED ONE MONTH ON.**
        # *"everything done leaves nothing to evaluate"* is why a period stays
        # unbilled, and **August below is still `billed: False`**. The PO's own
        # run is the third one; the count of finished cycles rose, the thing
        # left to try did not go away. The old warning would have been right if
        # this change had billed all three.
        #
        # `bill_on` mirrors June's shape — the period closes on the 31st and the
        # bill goes out on the 2nd of the following month.
        "bill_on": date(2026, 8, 2),
        "billed": True,
        # ⚠ **ZERO, AND IT IS A CHOICE WITH A REASON — not an oversight.** The
        # superseded 2026-08-16 spec said *"July ~80% collected"* and it would
        # be easy to restore now that July bills again. It is NOT restored,
        # because the PO's own ordering puts the money BEFORE the second run:
        # *"first you will run first billing, then you will create payment
        # record, refunds, credit over charges records, add meter reading for
        # second month and then again run the billing"*. Collections against
        # July would have to come after run 2, which the sentence does not ask
        # for — and a bill issued on 2 August, with this fixture's "today" in
        # mid-August, is a bill nobody has paid yet. That is what a real second
        # cycle looks like, and it leaves the ageing report a live CURRENT
        # bucket beside June's aged one, which one billed month could not show.
        "collected_share": Decimal("0"),
    },
    {
        # Read on the 14th because "today" for this fixture is mid-August — a
        # read dated the 31st would be a reading nobody has taken yet.
        "key": "august",
        "start": date(2026, 8, 1),
        "end": date(2026, 8, 14),
        "read_on": date(2026, 8, 14),
        "bill_on": None,
        "billed": False,  # ⚠ THE PO RUNS THIS ONE. Do not bill it.
        "collected_share": Decimal("0"),
    },
)

def move_out_on() -> date:
    """The day `CASE_MOVED_OUT`'s tenancy ENDS — the last day of the last
    period this fixture has BILLED.

    ⚠ **IT READ A LITERAL `date(2026, 7, 15)` — "mid-July" — UNTIL 2026-09-07,
    AND THE PRODUCT WOULD HAVE REFUSED THAT DATE (`DEF-CUS-4628`).** The field
    was never once consumed, so nobody found out. Measured on a seeded tenant:

        services.move_out(actor, AC-2026-00042, {"moved_out_on": "2026-07-15"})
        → BIZ-STATE customers.account.move_out_behind_issued_bill
          (BR-BIL-004, issued_through 2026-07-31)

    `BR-BIL-004` is the reason and it is not a technicality: this estate bills
    WHOLE MONTHS, so `BL-2608-000088` covers 2026-07-01 → 2026-07-31 on that
    very account. A move-out dated the 15th would be a tenancy ending BEHIND a
    bill already issued for it, which is exactly what `US-CUS-005` TC-6 refuses
    — *"corrections route via J6, not move-out backdating"*.

    ⚠ **AND THE LAST BILLED DAY IS THE ONLY DATE THAT IS ALSO RIGHT ON THE
    MONEY SIDE.** `BR-CUS-056` — *"the outgoing account pays the move day"* —
    makes the July bill this tenancy's FINAL bill with nothing to prorate and
    nothing to reissue (CLAUDE.md hard rule 4: no issued invoice is touched).
    The month AFTER it is the unbilled one the Product Owner runs, and the
    fixture's own August oddity already says the house is empty by then.

    DERIVED rather than typed so that a fixture which bills a third cycle moves
    this with it: a literal here is the defect above, recreated.
    """
    return max(period["end"] for period in PERIODS if period["billed"])


def move_in_on() -> date:
    """The day `CASE_MOVED_IN`'s tenancy BEGINS — the 16th of the last BILLED
    period, so the new account is prorated by a bill that has actually issued.

    ⚠ **IT READ A LITERAL `date(2026, 7, 16)` UNTIL 2026-09-25 (`DEF-LED-6640`),
    DIRECTLY BELOW A FUNCTION WHOSE OWN DOCSTRING WARNS AGAINST EXACTLY THAT.**
    `move_out_on` above says *"DERIVED rather than typed so that a fixture which
    bills a third cycle moves this with it: a literal here is the defect above,
    recreated"* — and the very next line of the row it builds was a literal.
    **A warning in a docstring protects the function it is attached to and
    nothing else**, which is hard-won law 1 one step along: the note was true,
    was read, and the line beside it was still typed.

    It cost nothing while the calendar was constants and everything once the
    calendar travelled: spec §4 case 10 is *"1 new account — moved in mid-July …
    proration the other way"*, and a tenancy pinned to 16 July 2026 on an estate
    billing October and November is not a proration case at all, it is an
    account that has simply been there the whole time. Nothing would have gone
    red — the row exists, the account bills, and every count is unchanged.

    **The 16th of the last billed month** reproduces `2026-07-16` exactly at
    offset zero, and `CASE_MOVED_OUT`'s last day of that same period is its
    mirror: one tenancy ends as that bill closes, the other starts halfway
    through it, so one issued bill demonstrates proration in both directions.
    """
    last_billed = max(
        (period for period in PERIODS if period["billed"]), key=lambda p: p["end"]
    )
    return last_billed["start"] + timedelta(days=15)


#: Spec §5 — one busy day of mixed takings, so deposit batches and bank
#: reconciliation have something real to group.
CANONICAL_BUSY_DAY = date(2026, 8, 8)

# ── THE CALENDAR AS THIS RUN SEES IT (DEF-LED-6640) ────────────────────────
# The three names below are what the rest of the repo has always imported, and
# every one of them keeps its meaning exactly. They are DERIVED now instead of
# typed, off one reading of the clock, so that a demo seeded in any month puts
# its two billed cycles and its cash where a clerk can still see them.
#: The day this fixture is set on. A money seeder that needs to know whether
#: something has happened yet reads THIS, never `date.today()` of its own —
#: `BR-TEN-043` and G6 both want the day to be a declared figure on a money
#: path, and this is that figure.
TODAY: date = fixture_today()
_CALENDAR: dict[str, Any] = build_calendar(TODAY)
#: Whole months the canonical 2026 calendar is shifted by. 0 on the anchor day.
CALENDAR_OFFSET_MONTHS: int = _CALENDAR["offset_months"]
OPENING_READ_ON: date = _CALENDAR["opening_read_on"]
PERIODS: tuple[dict[str, Any], ...] = _CALENDAR["periods"]
#: Spec §5 — one busy day of mixed takings, inside the OPEN period, so deposit
#: batches and bank reconciliation have something real to group AND the money
#: lands in the accounting period the Finance screens actually show.
BUSY_DAY: date = _CALENDAR["busy_day"]

# ── `DEF-RAT-8757` · THE WATER VERSION DATES TRAVEL WITH THE CALENDAR ──────
# `WATER_V2_FROM` / `WATER_V3_FROM` above are the CANONICAL dates, typed for the
# anchor day — and DEF-LED-6640's audit of typed dates missed them. v1 is
# seeded at `PERIODS[0]["start"]`, which travels; v2 did not, so from a sign-up
# in November 2026 on, v1 opened AFTER v2 and rating refused the schedule
# (`BIZ-WINDOW rating.schedules.window_overlap`) — and every account, bill and
# payment of the sample set failed behind it. Measured on sign-ups dated
# 2027-02-28 and 2028-02-29: 4 accounts, 0 bills, 0 payments. They are shifted
# by the same whole months as `PERIODS` here, so the relation the comment above
# states — v2 opens AFTER the billed periods, with the open month — holds on
# every day. On the anchor day the offset is 0 and both are unchanged.
WATER_V2_FROM = _shift_months(date.fromisoformat(WATER_V2_FROM), CALENDAR_OFFSET_MONTHS).isoformat()
WATER_V3_FROM = _shift_months(date.fromisoformat(WATER_V3_FROM), CALENDAR_OFFSET_MONTHS).isoformat()
WATER_VERSION_HISTORY = tuple(
    (_shift_months(date.fromisoformat(effective), CALENDAR_OFFSET_MONTHS).isoformat(), reason, tiers)
    for effective, reason, tiers in WATER_VERSION_HISTORY
)


# ── The five named streets (spec §2) ────────────────────────────────────────
STREETS: tuple[str, ...] = (
    "Silver Creek Rd",
    "Willow Bend Dr",
    "Cedar Ridge Way",
    "Mill Pond Ln",
    "Quarry Hill Ct",
)
CITY = "Silver Creek"
#: ⚠ **NEW 2026-08-31 — `DEF-2848`. THE FIXTURE HAD A TOWN AND A POSTCODE AND NO
#: STATE, AND FOR ELEVEN WEEKS NOTHING NOTICED** because every screen that draws
#: a seeded address draws the street and the town. `CR-053` task 13's print
#: hand-over is the first consumer that needs all three parts, and on a freshly
#: seeded tenant it measured **49 mailing addresses, 49 with a town, 49 with a
#: postcode, ZERO with a state** — so `BR-NOT-029` clause (b) held every single
#: bill out of the file. The rule worked; the fixture was short.
#:
#: ⚠ **THE STATE WAS `NE` AND THE POSTCODE `68901` UNTIL 2026-09-08, AND BOTH
#: MOVED TOGETHER — `DEF-MET-4629`, PO ruling *"(a) Texas, fix the postcode"*.**
#: DEF-2848 chose Nebraska because `68901` is a Nebraska postcode and there is a
#: Silver Creek in it, which made the mailing address name one real place. It
#: was right about the half it could see and it never looked at `premises`,
#: where the same estate has said **Texas** since it was first seeded — so one
#: account's screen carried *Silver Creek, Texas 68901* in the header and
#: *Silver Creek, NE, 68901* in the mailing box, and `select distinct state from
#: premises` answered **both `Texas` and `TX`**.
#:
#: **`78611` is Burnet, Texas, and it is the postcode that serves Silver Creek
#: Village — the unincorporated community in Burnet County, on the eastern shore
#: of Lake Buchanan, about twelve miles north-west of Burnet.** It is looked up
#: rather than invented, which is the whole of the ruling's second clause: a
#: plausible-looking five digits would have left the fixture in exactly the
#: state DEF-2848 found it in. It also sits in the right part of the map — the
#: estate's coordinates are anchored in the Austin ballpark (`STREET_GEO`,
#: CR-028) and Burnet County is an hour up the road from Austin, where Hastings,
#: Nebraska is not.
#:
#: **`TX` and not `Texas`, and the spelling is settled here for the whole
#: estate.** The code is what a US envelope carries, it is what
#: `tenancy.selectors.US_STATES` is keyed BY, it is what `tax_jurisdictions`
#: keys its 53 entries by (`CR-077`), and it is what every other seeded address
#: in this repo already writes — `seed_demo.PREMISES`' six Katy rows,
#: `portal.sample_data`'s three Austin rows, `import_runs.SAMPLE_TEXT_VALUES`.
#: The one place the WORD got in is the tenant's own regional declaration
#: (`tenants.state = "Texas"`, which is the label a clerk picks in a dropdown
#: and is left alone); `metering.seams.tenant_state` now folds it to the code on
#: the way to an address column, so both spellings cannot exist again.
#:
#: This is fixture data for a fictional utility and it asserts nothing about
#: where any real person lives — `BR-CUS-674` is about a customer's own record.
STATE = "TX"
POSTAL = "78611"


# ── PO 2026-09-07 · THE WALK IS SPREAD ACROSS THE ROUTES ────────────────────
#
# **THE RULING, VERBATIM:** *"now your reading model is correct - add seed data
# accordingly"*, on a model whose first part was *"you will have to do some
# variation for datys"*. Decision log 2026-09-07, *"TWO RULINGS IN ONE BREATH"*,
# part (2)(a).
#
# **WHAT IT REPLACED, MEASURED ON A SEEDED `brazosbend` BEFORE THIS LANDED:**
# 427 readings over 8 distinct dates, with `days_since_prior` taking only the
# values **14, 30 and 31** — seven routes on the tenant and every meter of the
# estate walked on ONE day, because the estate had exactly one route and one
# read date per period.
#
# **THE SHAPE NOW: one crew, one route a day, the last working days of the
# cycle.** Route 1 is walked on the cycle's own close date, route 2 the working
# day before it, and so on back through the week. Weekends are skipped, which is
# what makes the spans move: a period is 29, 30, 31 or 33 days depending on
# which route you are on and which month it is, instead of always a calendar
# month.
#
# ⚠ **ROUTE 1 KEEPS TODAY'S DATES EXACTLY, AND THAT IS THE POINT OF ITS BEING
# ROUTE 1.** `walk_offset = 0` is the period's own `read_on`, unshifted — so
# `CASE_REFERENCE_BILL` (unit 0, `101 Silver Creek Rd`) is read on 30 June, 31
# July and 14 August exactly as it always has been, and every pinned date in the
# suite is untouched. The spread is applied to the four routes BEHIND it.
#
# ⚠ **AND IT MOVES NO MONEY, WHICH WAS MEASURED RATHER THAN ASSUMED.** An
# ordinary bill run takes its proration factor from the RUN's period
# (`apps/billing/gather._service_days` over `period_start`/`period_end`), never
# from the read's own `days_since_prior` — so a 33-day walk-to-walk span and a
# 30-day one price the same base charge. What the span reaches is the READING
# side: `BR-MET-121`'s span judgment, the bill run's Days tab
# (`apps/billing/read_analysis._days_row`) and estimation's `days_in_period`,
# every one of which had four distinct values to work with across the whole
# product and now has real ones. Recorded in the decision log because the
# briefing that ordered this work said proration would be exercised and,
# measured, it is not.
STREET_WALK_ORDER: tuple[str, ...] = STREETS

#: The five walk routes of the sample estate — one per street, in walk order.
#:
#: `walk_offset` is how many WORKING days before the cycle's close this route is
#: walked. A utility of this size has one crew; it cannot read 46 premises in a
#: day, so it reads a street a day through the last week of the cycle. That is
#: the honest shape and it is where the spread of period lengths comes from.
#:
#: ⚠ **THE FIRST NAME IS THE ONE THIS FIXTURE HAS ALWAYS USED**, so a tenant
#: seeded before 2026-09-07 is recognised as already having route 1 and the
#: other four are added to it rather than five new routes appearing beside a
#: sixth. `BR-MET-074` makes a membership conflict a MOVE and not a refusal, so
#: the four new routes take their own streets' units off route 1 on a replay.
READ_ROUTES: tuple[dict[str, Any], ...] = (
    {"name": "Silver Creek — monthly walk", "street": STREETS[0], "walk_offset": 0},
    {"name": "Willow Bend — monthly walk", "street": STREETS[1], "walk_offset": 1},
    {"name": "Cedar Ridge — monthly walk", "street": STREETS[2], "walk_offset": 2},
    {"name": "Mill Pond — monthly walk", "street": STREETS[3], "walk_offset": 3},
    {"name": "Quarry Hill — monthly walk", "street": STREETS[4], "walk_offset": 4},
)

#: The day of the month the FIRST route is walked and how many days the whole
#: walk takes, which is what the cycle definition states (`BR-MET-077`:
#: `start_day` + `days_to_complete`, derived into a read window).
#:
#: ⚠ **IT SAID `start_day 14, days_to_complete 1` UNTIL 2026-09-07** — one crew,
#: one day — and that sentence stopped being true the moment the walk was spread
#: over five. The August walk runs 10–14 August, which is the cycle the demo's
#: own "today" sits in, so `10` and `5` describe the walk this fixture actually
#: performs. `bill_day` stays one day after the close (`BR-MET-077` refuses a
#: bill day earlier in the month than the read close).
WALK_DAYS_TO_COMPLETE = len(READ_ROUTES)


def walk_route_index(street: str) -> int:
    """Which of the five walk routes this street belongs to."""
    return STREET_WALK_ORDER.index(street)


def _working_day_before(day: date) -> date:
    """The last Monday–Friday strictly before `day`."""
    cursor = day - timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def route_read_on(period_key: str, walk_offset: int) -> date:
    """The day THIS route's crew walks in THIS period.

    `walk_offset` 0 is the period's own `read_on` — unshifted, so route 1 and
    every date pinned to it are exactly as they were. Every offset after it
    steps back one WORKING day, so a walk never lands on a Saturday and the
    spans between two walks are 29–33 days rather than always 30 or 31.
    """
    row = period_row(period_key)
    day = row["read_on"]
    for _ in range(walk_offset):
        day = _working_day_before(day)
    if not row["billed"]:
        # `DEF-MET-8693` — THE OPEN MONTH'S WALK NEVER STARTS BEFORE THE MONTH.
        # `build_calendar` clamps the open period's read to today, so signed up
        # on 1 October the five rounds stepped back to 25–30 September: reads
        # labelled as October's, dated inside September's BILLED period, and a
        # cycle whose walk began in a month it does not describe. Early in a
        # month the walk is simply SHORT — every round not yet out is walked on
        # the 1st — exactly as `build_calendar` shortens the open period itself.
        # On or after the 8th nothing clamps, so the anchor day is unchanged.
        day = max(day, row["start"])
    return day


def opening_read_on(walk_offset: int) -> date:
    """The register baseline for a route, on the same walk pattern.

    The opening read is what June's consumption is measured FROM, so it has to
    move with the route or route 5's June period would be 35 days long against
    everybody else's 30. Offset 0 is `OPENING_READ_ON` unchanged.
    """
    day = OPENING_READ_ON
    for _ in range(walk_offset):
        day = _working_day_before(day)
    return day


def period_row(period_key: str) -> dict[str, Any]:
    """One entry of `PERIODS` by its key — so a caller states the month it means
    rather than an index into a tuple whose order it would then depend on."""
    for row in PERIODS:
        if row["key"] == period_key:
            return row
    raise KeyError(period_key)


def period_end_month(period_key: str) -> int:
    """The calendar month a period CLOSES in — which is the month a seasonal
    curve is asked about. The opening read closes May."""
    if period_key == "opening":
        return OPENING_READ_ON.month
    return period_row(period_key)["end"].month

# ── The awkward cases (spec §4) ─────────────────────────────────────────────
# "Roughly one account in four is deliberately awkward." Each entry names the
# UNIT INDEX it lands on (0-based over the 48 seeded units) so every module can
# find the same account without asking another module for it.
CASE_REFERENCE_BILL = 0  # 8 kgal exactly → GT-17's $39.50 water / $15.80 sewer
CASE_UNREADABLE = (5, 19, 33)  # 3 meters with NO August read
CASE_DISPUTED_READ = 7  # August read flagged disputed
CASE_METER_REPLACED = 11  # meter swapped after the June read
CASE_PARTIAL_PAYMENT = (13, 27)  # paid part of the JUNE bill (July is unbilled
#                                  since the 2026-08-17 amendment above)
CASE_BOUNCED_CHEQUE = 21  # cheque cleared then returned NSF
CASE_PAYMENT_PLAN = 9  # a LIVE plan, mid-schedule — see PAYMENT_PLAN below
CASE_WRITE_OFF = 35  # awaiting approval
CASE_PAST_DUE_70 = 3  # June bill never paid → 70+ days at 8 Aug
CASE_MOVED_OUT = 41  # the tenancy that ENDS — see `move_out_on()`
CASE_MOVED_IN = 42  # proration the other way
CASE_CREDIT_BALANCE = 15  # overpayment carried as credit
CASE_GOODWILL_CREDIT = 29  # the concession path
#: ⚠ **TWO UNTIL 2026-09-03, THREE FROM IT (`CR-059` CS-12, task 74).** The
#: case was *"ONE customer, TWO accounts"* and spec §4 case 13 still is; what
#: changed is that `CR-059` CS-12 asks the demo for *"one customer with three
#: properties"* — the multi-property TENDER, one cheque covering all three —
#: and a landlord with two properties cannot show a three-way split.
#:
#: **47 is the unit that joins, and it is not an arbitrary free index:** it is
#: already one of the two `_COMMERCIAL_UNIT_INDEXES` beside 46, so the third
#: property is the same KIND of property as the second and the landlord stays
#: one company holding commercial units rather than becoming a person who also
#: owns a flat. It carries no capacity equipment (`capacity_equipment_plan`
#: plants on 4, 8, 10, 12, 14 and 20), so nothing this widening touches was
#: already telling a different story on that unit.
#:
#: ⚠ **`AWKWARD_UNITS` GOES 20 → 21 WITH IT** and the count in
#: `tests/test_us_ten_019_sample_records.py` is RESTATED rather than the band
#: being loosened — that file's own reasoning for the 18 → 20 move of
#: 2026-08-27, applied again: the count is what catches a case being silently
#: DROPPED, and the band alone would absorb either direction.
CASE_LANDLORD = (45, 46, 47)  # ONE customer, THREE accounts (CR-059 CS-12)
# ── CR-040 wave D · spec §4 cases 14 and 15 (PO 2026-08-27) ────────────────
# *"you need credit and refunds cases, overcharge cases"*. Two indices, both
# drawn from the ORDINARY units — neither is one of the awkward ones above,
# because an account that is already a payment plan or already 70 days past
# due cannot also demonstrate a clean refund or a clean correction without
# the two stories interfering.
#
# ⚠ **CASE_REFUND IS NOT CASE_CREDIT_BALANCE, AND THAT IS DELIBERATE.**
# Case 11 exists to show a credit being CARRIED — a negative-owing account
# rendering sanely on the accounts list. A refund CONSUMES a credit. Seeding
# the refund onto case 11's account would pay case 11 out and leave the
# fixture with no carried credit at all, which is one case replacing another
# rather than a case being added.
CASE_REFUND = 23  # overpays, then asks for the surplus back — spec §4 case 14
CASE_OVERCHARGE = 31  # a wrong June read, corrected by restatement — case 15

# ── CR-062 ADDENDUM J3 / J4 · TWO CUSTOMER KINDS, NOT TWO AWKWARD CASES ────
#
# ⚠ **THESE ARE DELIBERATELY NOT IN `AWKWARD_UNITS` BELOW.** The awkward cases
# are a *story about a bill going wrong* — a disputed read, a bounced cheque, a
# write-off awaiting approval. These two are a story about **who the customer
# is**, and an account that was also the payment-plan case could not show a
# clean government bill without two demo stories arguing over one document
# (`CASE_REFUND`'s own reasoning, one section up).
#: ⚠ **THE NAME SAYS `GOVERNMENT` AND THE ACCOUNT TYPE IS `municipal`, WHICH IS
#: NOT A DISCREPANCY (`DEF-3283`).** The seat IS a government customer — that is
#: what the demo shows and what the Municipal discount is for — and `municipal`
#: is the code `BR-CUS-094` leaves selectable for exactly that customer, having
#: retired `government` to legacy on 2026-08-24. The constant keeps the word a
#: reader will search for; `DEMO_ACCOUNT_TYPES` holds the code the product
#: requires, and says why at the line the value sits on.
CASE_GOVERNMENT_ACCOUNT = 48  # the first government customer this seed has held
CASE_INDUSTRIAL_ACCOUNT = 49  # the first `industrial` one — `$180.00` lands here

#: The government building's water draw, flat in every period.
#:
#: **12 kgal is what makes `CR-062` addendum J2's worked subtotal come out**: on
#: the seeded inclining tiers 5 kgal at `$4.00` plus 7 at `$6.50` is **`$65.50`**
#: of usage, **sewer takes 90% of the 12 kgal at `$5.0000` (`$54.00`, `CR-081`)**,
#: the residential water base adds **`$8.00`** and two carts add **`$30.00`** —
#: **`$157.50`**, against which the Municipal discount takes **`$31.50`** and
#: leaves **`$126.00`**. ⚠ It read *"sewer takes 40% of that (`$26.20`) …
#: `$129.70` … `$25.94` … `$103.76`"* until 2026-09-08.
#:
#: ⚠ **FLAT FOR UNIT 0's REASON AND NOT A NEW ONE.** A demo figure the Product
#: Owner was shown and can check by hand must not be true in June and false in
#: July, which a ±1 kgal monthly drift would make it.
GOVERNMENT_WATER_KGAL = Decimal("12")

#: **THE INDUSTRIAL PLANT'S MONTHLY ELECTRICITY, STATED RATHER THAN DERIVED.**
#:
#: ⚠ **IT ESCAPES `CONSUMPTION_SCALE` ON PURPOSE, AND THIS IS THE REASON.** The
#: scale multiplies ONE shape — a household's kgal — into every other service's
#: unit. To reach an industrial plant's monthly energy through it the plant
#: would have to draw **537 kgal** of water, and that number would then be its
#: WATER bill on every tenant that sells water. A factory's kWh and its kgal
#: have no arithmetic relationship and must not be made to share a multiplier.
#:
#: **54,000 kWh, and where the figure comes from:** `CR-062` addendum J4 states
#: the unbilled demand half at a **100 kW peak**, and 54,000 kWh over a 730-hour
#: month is an average of **74 kW** — a 74% load factor, which is a two-shift
#: plant rather than an arithmetic convenience. At the `$0.0850` per kWh the
#: Product Owner ruled for the usage line (see `INDUSTRIAL_ELECTRIC_PER_KWH`)
#: that is **`$4,590.00`** of usage, and with the signed `$180.00` industrial
#: base a bill of **`$4,770.00`** before taxes.
#:
#: ⚠ **THE ADDENDUM ILLUSTRATES `$4,751.00` AND THIS SEED BILLS `$4,770.00`,
#: WHICH IS STATED RATHER THAN QUIETLY RECONCILED.** `$4,751.00` is not
#: reachable from a whole number of kWh: `($4,751.00 − $180.00) ÷ $0.0850` is
#: **53,776.47** kWh. So the seeded draw is the round 54,000 and the bill is
#: `$19.00` above the addendum's illustration. **Nothing the addendum decides
#: moves**: the rate, the base and the `$1,100.00` of unbilled demand at a
#: 100 kW peak are all exactly as ruled.
#:
#: `(unit index, service) → quantity`. A map rather than a branch for
#: `METERED_USAGE_PRICES`' reason: a second stated draw is a row, not a branch.
UNIT_SERVICE_CONSUMPTION: dict[tuple[int, str], Decimal] = {
    (CASE_INDUSTRIAL_ACCOUNT, "electric"): Decimal("54000"),
}

#: Every index the cases above touch, so a seeder can ask "is this one of the
#: interesting ones?" without re-deriving the list and getting it wrong.
AWKWARD_UNITS: frozenset[int] = frozenset(
    {CASE_REFERENCE_BILL, CASE_DISPUTED_READ, CASE_METER_REPLACED}
    | set(CASE_UNREADABLE)
    | set(CASE_PARTIAL_PAYMENT)
    | {
        CASE_BOUNCED_CHEQUE,
        CASE_PAYMENT_PLAN,
        CASE_WRITE_OFF,
        CASE_PAST_DUE_70,
        CASE_MOVED_OUT,
        CASE_MOVED_IN,
        CASE_CREDIT_BALANCE,
        CASE_GOODWILL_CREDIT,
        CASE_REFUND,
        CASE_OVERCHARGE,
    }
    | set(CASE_LANDLORD)
)

# ── Household names (no money, no rule — display text only) ─────────────────
_SURNAMES: tuple[str, ...] = (
    "Alvarez", "Bennett", "Castillo", "Duval", "Ellery", "Fontaine", "Gagnon",
    "Hollis", "Iversen", "Janssen", "Kowalski", "Lindqvist", "Marchetti",
    "Nakamura", "Okonkwo", "Petrov", "Quinlan", "Rasmussen", "Sandoval",
    "Thibault", "Ueda", "Valdez", "Whitmore", "Xanthos", "Yeardley", "Zabala",
    "Ashford", "Brandt", "Corrigan", "Delacroix", "Espinoza", "Faulkner",
    "Grimaldi", "Halvorsen", "Ibarra", "Jorgensen", "Kirchner", "Larkin",
    "Moreau", "Novotny", "Ortega", "Pemberton", "Rylance", "Stavros",
    "Tanaka", "Underhill", "Vasquez", "Wexler",
)
_GIVEN: tuple[str, ...] = (
    "Ana", "Ben", "Clara", "Dev", "Elena", "Farid", "Grace", "Hugo", "Ines",
    "Jonas", "Kaya", "Luca", "Mira", "Noor", "Omar", "Priya", "Quentin", "Rosa",
    "Sam", "Tessa", "Uma", "Viktor", "Wren", "Xander",
)

_COMMERCIAL_NAMES = ("Creekside Laundromat", "Quarry Hill Diner")

#: **THE TWO ORGANISATIONS `CR-062` ADDENDUM J3/J4 SEEDS, AND WHY EACH NAME
#: CARRIES THE WORD `Sample`.**
#:
#: The government seat is the ONE account this fixture enrols in a subsidy
#: (`CR-062` addendum J2), and the addendum makes the demonstration explicit in
#: terms: it *"must be obviously a demo (`government` type, fictional
#: identifiers) and must never be a real party"*. There is no township, mill or
#: public-works department of these names; the town, the streets and the
#: postcode are this fixture's own invention, the addresses are on them, and the
#: contact details use the reserved `example.invalid` domain and the `555`
#: telephone range every other seeded seat already uses.
DEMO_ORGANISATION_NAMES: dict[int, str] = {
    CASE_GOVERNMENT_ACCOUNT: "Silver Creek Sample Township",
    CASE_INDUSTRIAL_ACCOUNT: "Silver Creek Sample Millworks",
}

#: The seats whose `account_type` is NOT derived from the unit's commercial
#: flag. `industrial` and `municipal` have been valid `account_types` codes for
#: as long as the platform catalogue has existed and **no seeded account had
#: ever carried either**, so the product had never shown one and no bill stood
#: behind `INDUSTRIAL_ELECTRIC_BASE`'s `$180.00` (`DEF-2823`).
#:
#: ⚠ **THE GOVERNMENT SEAT IS `municipal` AND NOT `government`, AND THE PRODUCT
#: IS RIGHT ABOUT THAT (`DEF-3283`).** `CR-062` addendum J3 asks for a
#: `government` account in those words, and that sentence was already eight days
#: stale when it was written: **`BR-CUS-094` (PO 2026-08-24) made `government`
#: a LEGACY code** — *"stops being selectable and changes nothing else"* — so
#: `customers.services._resolve_account_type` refuses it on any NEW record and
#: refused this one by name, `VAL-005 customers.account.type_is_legacy`. The
#: only door that may still write it is the cutover import, which exists so a
#: real utility's existing records keep their code, and reaching through it to
#: seed a demo would put the product's own refusal in the wrong.
#:
#: **`municipal` is the same customer in the vocabulary the signed rule
#: requires, and it is the Product Owner's OWN WORD for it** — the ruling that
#: created this seat reads *"What is the government discount called? Municipal
#: account - yes"*. Nothing the addendum wanted is lost: a government customer
#: appears, the Municipal discount lands on it, and `BR-CUS-094` is obeyed
#: rather than worked around.
DEMO_ACCOUNT_TYPES: dict[int, str] = {
    CASE_GOVERNMENT_ACCOUNT: "municipal",
    CASE_INDUSTRIAL_ACCOUNT: "industrial",
}


def _street_for(index: int) -> str:
    return STREETS[index % len(STREETS)]


def premises_plan() -> tuple[dict[str, Any], ...]:
    """The 44 premises and the 48 units on them (spec §2).

    36 single-family (1 unit) · 3 newly platted with NO unit · 2 duplexes
    (2 units) · 1 apartment block (6 units) · 2 commercial (1 unit).
    44 premises, 48 units — see the module docstring for why three carry no
    unit.

    `unit_index` is the fixture-wide 0-based ordinal every other module keys
    on, so metering, assets, customers, billing and payments all mean the same
    unit by the same number without any of them reading another's tables.
    """
    rows: list[dict[str, Any]] = []
    unit_index = 0
    house_no = 101

    def _unit(label: str, unit_type: str) -> dict[str, Any]:
        nonlocal unit_index
        row = {
            "label": label,
            "unit_no": f"SCW-U-{unit_index + 1:03d}",
            "unit_type": unit_type,
            "unit_index": unit_index,
        }
        unit_index += 1
        return row

    # 36 single-family, one unit each.
    for i in range(36):
        street = _street_for(i)
        rows.append(
            {
                "address_line": f"{house_no + i * 2} {street}",
                "street": street,
                "premises_type": "single_family",
                "owner_manager": None,
                "status": "active",
                "units": (_unit("Unit 1", "residential"),),
            }
        )

    # 2 duplexes, two units each.
    for i in range(2):
        street = _street_for(36 + i)
        rows.append(
            {
                "address_line": f"{house_no + 80 + i * 2} {street}",
                "street": street,
                "premises_type": "single_family",
                "owner_manager": "Silver Creek Duplex Holdings",
                "status": "active",
                "units": (_unit("Unit A", "residential"), _unit("Unit B", "residential")),
            }
        )

    # 1 small apartment block of 6 units — the reason units exceed premises.
    apartment_street = _street_for(38)
    rows.append(
        {
            "address_line": f"{house_no + 200} {apartment_street}",
            "street": apartment_street,
            "premises_type": "apartment_complex",
            "owner_manager": "Mill Pond Apartments LP",
            "status": "active",
            "units": tuple(
                _unit(f"Apt {101 + n}", "residential_submetered") for n in range(6)
            ),
        }
    )

    # 2 commercial.
    for i in range(2):
        street = _street_for(39 + i)
        rows.append(
            {
                "address_line": f"{house_no + 300 + i * 2} {street}",
                "street": street,
                "premises_type": "commercial_building",
                "owner_manager": _COMMERCIAL_NAMES[i],
                "status": "active",
                "units": (_unit("Suite 1", "commercial"),),
            }
        )

    # 3 newly platted premises with NO unit yet — see the module docstring.
    for i in range(3):
        street = _street_for(41 + i)
        rows.append(
            {
                "address_line": f"{house_no + 400 + i * 2} {street}",
                "street": street,
                "premises_type": "single_family",
                "owner_manager": None,
                "status": "pending",
                "units": (),
            }
        )

    # ── CR-062 ADDENDUM J3 + J4 · THE TWO CUSTOMER KINDS THE DEMO HAS NEVER
    # HAD (2026-09-02) ──────────────────────────────────────────────────────
    #
    # **WHY THEY ARE HERE AND NOT IN A SIDE BLOCK.** `account_types` has carried
    # `government` since the platform catalogue was written and `industrial`
    # just as long, and **no seeded account had ever used either**. So nothing
    # in the product had shown what a government or an industrial customer
    # looks like, `INDUSTRIAL_ELECTRIC_BASE`'s `$180.00` stood behind no bill at
    # all — which is exactly how `DEF-2823`'s `$168.00` disagreement with
    # `ELECTRIC_BASE` hid for as long as it did (*"0 accounts are on `IND`, so
    # no bill ever carried either figure"*) — and `CR-062` addendum J2's
    # Municipal discount would have had nowhere to land.
    #
    # ⚠ **THE COUNTS MOVE: 44 → 46 PREMISES AND 48 → 50 UNITS**, and that is the
    # whole cost of this change. It is paid once, in one commit, with every
    # pinned count restated rather than loosened — a band would absorb a seat
    # being silently DROPPED, which is the thing those counts exist to catch.
    #
    # ⚠ **BOTH SEATS ARE APPENDED LAST, AND THE ORDER IS LOAD-BEARING.**
    # `unit_index` is the fixture-wide ordinal every other module keys on, so a
    # seat inserted anywhere but the end would renumber 48 existing units and
    # re-point every meter serial, every read, every awkward case and every ❄️
    # frozen figure with them. Appending adds indexes 48 and 49 and moves none.
    #
    # ⚠ **AND NEITHER IS AN AWKWARD UNIT** (`AWKWARD_UNITS`) — the same care
    # `CART_UNIT_WITH_THREE` takes. Unit 0 keeps `GT-17`'s ❄️ reference bill.
    #
    # **THE PARTIES ARE FICTIONAL AND OBVIOUSLY SO, WHICH `CR-062` ADDENDUM J2
    # REQUIRES IN TERMS**: the government seat is the one account this fixture
    # enrols in a subsidy, and *"it must be obviously a demo … and must never be
    # a real party"*. Both names carry the word **Sample**, both sit on this
    # fixture's own invented town and streets, and their contact details use the
    # reserved `example.invalid` domain and the `555` telephone range like every
    # other seeded seat.
    government_street = _street_for(44)
    rows.append(
        {
            "address_line": f"{house_no + 500} {government_street}",
            "street": government_street,
            # BR-MET-034's sixth seeded type, added by CR-010 item 4 on the PO's
            # own words (*"you can alos make them Govtment building also"*) and
            # used by no seeded premises until today.
            "premises_type": "government_building",
            "owner_manager": None,
            "status": "active",
            # `commercial` because `UNIT_TYPES` holds five values and none of
            # them is "civic": the depot is a non-dwelling building. The fact
            # that makes it a GOVERNMENT customer is the ACCOUNT TYPE, which is
            # where the platform records it (`account_plan` below).
            "units": (_unit("Public Works Depot", "commercial"),),
        }
    )
    industrial_street = _street_for(45)
    rows.append(
        {
            "address_line": f"{house_no + 502} {industrial_street}",
            "street": industrial_street,
            # `commercial_building` for the same reason: `SEED_PREMISES_TYPES`
            # holds six types and none of them is "industrial". Inventing a
            # seventh would be adding a platform lookup row from a fixture,
            # which BR-TEN-058 forbids outright.
            "premises_type": "commercial_building",
            "owner_manager": None,
            "status": "active",
            "units": (_unit("Mill Building", "commercial"),),
        }
    )

    # ── BR-RAT-101's flag, on EVERY row (CR-039 wave C task 11) ─────────────
    # Applied here rather than inside the five loops above so the ordinals in
    # `OUTSIDE_CITY_PREMISES_INDEXES` mean one thing — the position of the
    # premises in this tuple — and cannot drift when a loop is reordered.
    #
    # `True`/`False`, never `None`: see `OUTSIDE_CITY_PREMISES_INDEXES` for why
    # an unstated flag under a surcharging plan is 42 exception rows, and
    # `CONSUMPTION_SCALE` above for the same fixture rule about a figure with
    # nothing behind it. Three of these premises carry no unit and so no bill;
    # they are stated anyway, because *"which side of the line is it on"* is a
    # fact about an ADDRESS and does not wait for a tenant to move in.
    for index, row in enumerate(rows):
        row["inside_city_limits"] = index not in OUTSIDE_CITY_PREMISES_INDEXES

    return tuple(rows)


def units_flat() -> tuple[dict[str, Any], ...]:
    """Every seeded unit in fixture order, each carrying its premises address.

    ⚠ **`street` JOINED THE ROW ON 2026-09-07 AND IT IS NOT DECORATION** — it is
    what decides which of the five walk routes this unit is read on
    (`READ_ROUTES`, `walk_route_index`), and therefore which day its meter is
    walked and how long its period is. Deriving it by matching the address's
    suffix would be a second statement of a fact `premises_plan` already holds.
    """
    out: list[dict[str, Any]] = []
    for premises in premises_plan():
        for unit in premises["units"]:
            out.append(
                {
                    **unit,
                    "address_line": premises["address_line"],
                    "street": premises["street"],
                }
            )
    return tuple(out)


#: ⚠ **48 → 50 AND 44 → 46 ON 2026-09-02 (`CR-062` ADDENDUM J3/J4).** The two
#: new seats are the government building and the industrial plant appended at
#: the end of `premises_plan` above; every count in this repo that reads these
#: constants moves with them, and the handful written as literals was restated
#: in the same commit rather than loosened into a band.
UNIT_COUNT = 50
PREMISES_COUNT = 46


def is_commercial(unit_index: int) -> bool:
    """The two commercial suites bill on the Commercial plan; everything else
    is Residential. Kept as a function rather than a list because customers and
    rating both have to answer it and must answer it the same way.

    ⚠ **THIS IS NO LONGER THE WHOLE ANSWER — ASK `plan_class_for` INSTEAD WHEN
    WHAT YOU WANT IS A PLAN (`CR-062` addendum J4).** Since the industrial seat
    landed there are THREE classes, and a caller that reads this boolean gets
    *"not commercial"* for the industrial plant and puts it on the residential
    plan — where it would bill the `$12.00` residential electric base and leave
    `INDUSTRIAL_ELECTRIC_BASE`'s `$180.00` standing behind nothing, which is the
    exact gap J4 exists to close. This function is kept because it answers a
    different, still-true question — *is this one of the two commercial suites*
    — which `water_consumption_kgal` asks about the CONSUMPTION SHAPE.
    """
    return unit_index in _COMMERCIAL_UNIT_INDEXES


_COMMERCIAL_UNIT_INDEXES: frozenset[int] = frozenset({46, 47})


#: **WHICH ACCOUNT TYPES EACH SEEDED PLAN CLASS BILLS FOR — `CR-062` addendum
#: J3/J4, and it is the line that decides whether the two new seats get a bill
#: at all (`DEF-3282`).**
#:
#: ⚠ **A CONSUMER CATEGORY THAT NO `is_base` CHARGE CODE COVERS BILLS NOTHING,
#: SILENTLY, AND THIS WAS MEASURED RATHER THAN REASONED.** `BR-RAT-108` makes
#: `charges.applies_to_customer_classes` an INCLUSION list and
#: `resolution.resolve_charge_codes` narrows on it — *"its customer classes
#: include the account's"* — so the seeded `BASE-W` (`residential`) and
#: `BASE-W-COM` (`commercial`) both drop out for a `municipal` account. On
#: PostgreSQL 16 the municipal and industrial seats landed with a plan, an
#: active account, three service points, a meter and four committed reads, sat
#: in the run's scope alongside all 50, **and issued 0 invoices** while unit 0
#: issued 2. Nothing failed and nothing was reported: it is `BR-BIL-1024`'s *"no
#: lines, no document"* arrived at by a route nobody meant to take.
#:
#: **So the classes a base code covers are declared HERE, once, beside the plan
#: classes they belong to** — the same by-construction agreement `DEF-455`
#: requires of the plan's base and the code's amount, applied to the third field
#: that has to match.
#:
#: ⚠ **`industrial` RIDES THE COMMERCIAL CODE EXCEPT WHERE AN INDUSTRIAL ONE
#: EXISTS.** `[W] §1` states an industrial figure for ELECTRICITY and for
#: nothing else, so a plant on this demo's water system is a commercial water
#: customer — and saying `("0", "0")` instead would mean *this size is not
#: served* and stop its bill outright (`CR-013` part 1 / `DEF-277`). Where an
#: industrial code DOES exist, the commercial one must drop `industrial` or two
#: codes would claim the same account and the bill refuses by name rather than
#: charging whichever a query reached first (`DEF-468`).
#:
#: ⚠ **THE THREE CATEGORIES THIS DOES NOT COVER ARE A KNOWN GAP, NOT AN
#: OVERSIGHT (`DEF-3282`).** `BR-CUS-094` ratifies SEVEN consumer categories and
#: this fixture seats four of them; an `agricultural`, `institutional` or
#: `builder_developer` account created by hand on a seeded tenant still matches
#: no base code and still bills nothing. That is a real utility's configuration
#: to make on Charge codes, and it is filed rather than pre-empted here.
PLAN_CLASS_ACCOUNT_TYPES: dict[str, tuple[str, ...]] = {
    "residential": ("residential", "municipal"),
    "commercial": ("commercial", "industrial"),
    "industrial": ("industrial",),
}


def base_code_classes(plan_class: str, *, industrial_code_exists: bool = False) -> list[str]:
    """The `applies_to_customer_classes` list for ONE seeded base charge code.

    `industrial_code_exists` is the electric case and only the electric case:
    when a service has its own industrial base, the commercial code must stop
    claiming industrial accounts or `DEF-468`'s two-codes-one-account refusal
    fires on every industrial bill.
    """
    classes = list(PLAN_CLASS_ACCOUNT_TYPES.get(plan_class, (plan_class,)))
    if plan_class == "commercial" and industrial_code_exists and "industrial" in classes:
        classes.remove("industrial")
    return classes


def plan_class_for(unit_index: int) -> str:
    """Which of the three seeded plan classes this unit's account derives from —
    `residential` · `commercial` · `industrial` (`CR-062` addendum J4).

    ⚠ **ONE FUNCTION, BECAUSE TWO WOULD DRIFT.** Metering resolves the unit's
    `rate_plan_id` from it and rating names its plans from it; before the
    industrial seat there were two classes and a boolean was enough, and the
    moment a third arrived a boolean started ANSWERING WRONG rather than
    refusing — *"not commercial"* is a perfectly well-formed reply that puts an
    industrial plant on a household ladder.
    **The account TYPE and the plan CLASS are the same word here and are not the
    same fact**: the government building is a `government` ACCOUNT and bills on
    the RESIDENTIAL plan, because the residential inclining ladder is the only
    non-flat water schedule this fixture seeds and it is the ladder `CR-062`
    addendum J2's `$129.70` subtotal is computed on. A utility that wants a
    government tariff configures one on Plans & Rates; this is the DEMO's.
    """
    if unit_index == CASE_INDUSTRIAL_ACCOUNT:
        return "industrial"
    if is_commercial(unit_index):
        return "commercial"
    return "residential"


# ── PO 2026-09-07 · THE CONSUMPTION CURVE, THE SPREAD AND THE ODDITIES ───────
#
# **THE RULING, VERBATIM:** *"now your reading model is correct - add seed data
# accordingly"*, asked for earlier in the same conversation as *"you will have
# to do some variation for datys, for consumptions"*. Decision log 2026-09-07,
# *"TWO RULINGS IN ONE BREATH"*, part (2)(b).
#
# **WHAT IT REPLACED, MEASURED:** one formula with a flat ±1 drift — EVERY
# customer's July was exactly one unit above their June and every August exactly
# one below, on every service at once. Fifty households whose usage moved in
# lock-step is not a demo of consumption; it is a demo of one addition.
#
# **THREE THINGS ARE NEW AND EACH IS A DIFFERENT FACT:**
#   1. a **SEASONAL** curve, stated per SERVICE over twelve months — water and
#      electric peak in the summer, gas peaks in the winter;
#   2. a **RESPONSE** per customer — how much of the season this household
#      actually feels. An apartment with no lawn barely moves; a bungalow with
#      an irrigation timer nearly doubles. This is what puts real spread
#      BETWEEN customers in the same month, which a single curve cannot;
#   3. three **ODDITIES**, each on one named customer in one named month — a
#      leak, a fortnight away, and an empty house. *"Deliberate oddities are
#      worth more than smooth data — they are what a clerk learns the exception
#      screens on."*
#
# ⚠ **THE SEASON IS PER SERVICE, WHICH IS WHY THE SHAPE MOVED OUT OF THIS
# FUNCTION AND INTO `_shaped`.** `consumption()` scales ONE shape into every
# service's unit through `CONSUMPTION_SCALE`, so a curve applied here would give
# GAS a summer peak — the exact opposite of what a gas utility sells. Water's
# curve is still what `water_consumption_kgal` returns, byte for byte, because
# that is the function's contract.
#
# ⚠ **NOTHING HERE PRICES ANYTHING AND NOTHING HERE IS SIGNED LAW.** It is the
# same fixture authorship `CONSUMPTION_SCALE` declares itself to be. The two
# customers whose consumption a ❄️ FROZEN figure is computed from are answered
# FIRST, before a single curve is consulted — see below.

#: month number → how much of an average month this service draws.
#:
#: Twelve months although the fixture seeds three, because the curve is a fact
#: about the SERVICE and not about the demo's calendar: `seed_account_read_history`
#: already plants a longer history, and a curve that existed only for June, July
#: and August would be a fact that stopped being true the day somebody seeded
#: September.
#:
#: **The shapes, and what each one is:** water rises with irrigation and peaks
#: in July; electric follows the air conditioning and peaks with it; gas is
#: heating, so it is the same curve upside down — highest in January, lowest in
#: midsummer; thermal heat is chilled water on this fixture's own reading
#: (`CONSUMPTION_SCALE`'s note calls it *"a real chilled-water building"*), so it
#: cools rather than heats and follows electric.
#:
#: A service with no entry gets water's curve, which is the fixture's backbone
#: and its most neutral shape.
#:
#: ⚠ **EACH ROW AVERAGES ABOUT 1 ACROSS ITS TWELVE MONTHS, AND THAT IS WHAT
#: MAKES `_baseline` STILL MEAN "THIS CUSTOMER'S AVERAGE MONTH".** Water sums to
#: 11.85, electric to 12.60, gas to 12.00 and thermal to 11.60 — so a curve
#: reshapes a customer's year without inflating it, and the size ordering the
#: old flat formula gave the estate is exactly the size ordering it still has.
SEASONAL_SHAPE: dict[str, tuple[str, ...]] = {
    #        Jan     Feb     Mar     Apr     May     Jun     Jul     Aug     Sep     Oct     Nov     Dec
    "water": ("0.78", "0.78", "0.85", "0.95", "1.05", "1.12", "1.38", "1.24", "1.10", "0.95", "0.85", "0.80"),
    "electric": ("1.08", "1.00", "0.88", "0.82", "0.95", "1.15", "1.45", "1.32", "1.15", "0.90", "0.88", "1.02"),
    "gas": ("1.85", "1.70", "1.30", "0.95", "0.65", "0.45", "0.40", "0.40", "0.50", "0.80", "1.30", "1.70"),
    # ⚠ **`thermal_heat`'s TWELVE FACTORS WERE WITHDRAWN 2026-09-07 (`CR-080`).**
    # A seasonal curve reshapes a REGISTER READING across the year; thermal is
    # capacity-billed on connected tonnage now and reads nothing, and a
    # building's connected tonnage does not shrink in January. They summed to
    # 11.60 and are quoted here rather than kept, because the sentence above
    # ("water sums to 11.85, electric to 12.60, gas to 12.00 and thermal to
    # 11.60") is cited by tests that had to move with them.
}

#: How much of the season a customer actually feels — `1` is the curve as
#: written, `0` is a customer whose draw does not move with the weather at all.
#:
#: ⚠ **THIS IS THE HALF THAT MAKES THE SPREAD, AND A SINGLE CURVE CANNOT DO IT.**
#: Multiply fifty customers by one seasonal factor and all fifty still move in
#: lock-step — the same defect this replaces, one multiplication further on. A
#: response per customer is what makes July a month where some bills doubled,
#: some barely moved, and a clerk has something to look at.
#:
#: The seven values run from a household with no outside tap (an apartment) to
#: one with a lawn, a pool and an irrigation timer. They are assigned by
#: `unit_index % 7` so the assignment is deterministic and a screenshot taken
#: twice is the same screenshot.
#:
#: ⚠ **SEVEN, AND THE COUNT IS DELIBERATE RATHER THAN AESTHETIC.** A premises
#: takes its STREET from `index % 5` (`_street_for`) and the first 36 units sit
#: one to a premises, so a response list of length 4 or 5 would be locked in
#: step with the walk routes — every customer on one crew's round would respond
#: to the season identically, and the spread would vanish exactly where a clerk
#: looks at it, one route at a time. Seven shares no factor with five, so the
#: two patterns take 35 units to repeat and every route carries a mix.
SEASONAL_RESPONSE: tuple[str, ...] = (
    "0.15",  # an apartment: no tap outside, the season barely reaches it
    "0.60",
    "1.00",  # the curve as written
    "1.45",
    "0.35",
    "1.20",
    "0.80",
)

#: ── THE THREE ODDITIES ──────────────────────────────────────────────────────
#: `(unit index, period key) → what happened, and the factor it did it by`.
#:
#: **NONE OF THE THREE LANDS ON A UNIT THAT ALREADY CARRIES A STORY** — the two
#: pinned customers are answered before this map is read, and `AWKWARD_UNITS`
#: was checked by hand: 26 and 30 are in neither. Stacking two demonstrations on
#: one customer makes both harder to read, which is the same care
#: `CART_UNIT_WITH_THREE` takes.
#:
#: **THE FOURTH IS NOT AN ODDITY — IT IS AN EXISTING STORY FINALLY BEING TRUE.**
#: `CASE_MOVED_OUT` (41) has a final bill in mid-July, so nobody lives there in
#: August, and the fixture went on drawing 4 kgal through an empty house every
#: single month. That is not a new case; it is the case the fixture already
#: claims, made honest.
#: ⚠ **THE THIRD FIELD IS THE SERVICES IT APPLIES TO, AND IT WAS ADDED BECAUSE
#: THE FIRST VERSION SPIKED A WATER LEAK'S ELECTRICITY BILL.** `consumption()`
#: scales ONE shape into every service, so an oddity applied inside that shape
#: reaches all of them — measured on PostgreSQL 16 before this field existed:
#: the leaking household's July read was **112 kgal of water AND 11,700 kWh of
#: electricity**, both flagged `high`, on a customer whose only fault was a
#: running toilet. **A burst pipe is a WATER fact.** Being away for a fortnight
#: and moving out are not: those two genuinely reduce everything the household
#: draws, so they name no service and apply to all of them.
CONSUMPTION_ODDITIES: dict[tuple[int, str], tuple[str, str, tuple[str, ...] | None]] = {
    (30, "july"): (
        "4.5",
        "a leak — a running toilet nobody heard, found by the July exception "
        "review and fixed before the August walk",
        ("water",),
    ),
    (26, "july"): (
        "0.35",
        "away for a fortnight over the holiday — a low-side exception, which is "
        "the one a clerk is least practised at reading",
        None,
    ),
    (41, "august"): (
        "0.08",
        "the house is EMPTY — the tenant's final bill was cut in mid-July "
        "(CASE_MOVED_OUT) and the meter has been standing still since",
        None,
    ),
}

#: The two units the oddities above name, so a caller can say *"is this one of
#: the interesting ones"* without re-deriving the map. `CASE_MOVED_OUT` is
#: deliberately NOT added — it is already in `AWKWARD_UNITS` under its own case.
CASE_LEAK = 30
CASE_HOLIDAY_DROP = 26


def _seasonal_factor(service: str, period_key: str) -> Decimal:
    """This service's seasonal multiplier in the month `period_key` closes in."""
    shape = SEASONAL_SHAPE.get(service) or SEASONAL_SHAPE["water"]
    month = period_end_month(period_key)
    return Decimal(shape[month - 1])


def _baseline(unit_index: int) -> Decimal:
    """This customer's own average month, before any season is applied.

    ⚠ **UNCHANGED FROM THE FORMULA THIS REPLACES, DELIBERATELY.** It is what
    gives one customer a bigger house than the next, and moving it would
    renumber every seeded customer's usage for no reason anybody asked for. The
    season and the response are applied ON TOP of it.
    """
    if is_commercial(unit_index):
        return Decimal(38 + (unit_index * 7) % 25)
    return Decimal(4 + (unit_index * 5) % 17)


def _shaped(unit_index: int, period_key: str, service: str) -> Decimal:
    """The consumption SHAPE — one customer, one month, one service, before
    `CONSUMPTION_SCALE` turns it into that service's own unit.

    ⚠ **THE TWO PINNED CUSTOMERS ARE ANSWERED FIRST AND NO CURVE IS CONSULTED
    FOR THEM.** Unit 0 draws ❄️ GT-17's own 8 and the government building draws
    `GOVERNMENT_WATER_KGAL`, in EVERY month and on EVERY service, exactly as
    they did before this curve existed. A drift of ±1 on either would make a
    figure the Product Owner was shown true in June and false in July — which
    is the sentence `GOVERNMENT_WATER_KGAL`'s own docstring already carries, and
    it is why these two lines are the first two lines of this function.
    """
    if unit_index == CASE_REFERENCE_BILL:
        return Decimal("8")
    if unit_index == CASE_GOVERNMENT_ACCOUNT:
        return GOVERNMENT_WATER_KGAL
    season = _seasonal_factor(service, period_key)
    response = Decimal(SEASONAL_RESPONSE[unit_index % len(SEASONAL_RESPONSE)])
    # 1 + response × (season − 1): a response of 0 leaves the customer flat all
    # year and a response of 1 gives them the curve as written.
    felt = Decimal("1") + response * (season - Decimal("1"))
    value = _baseline(unit_index) * felt
    oddity = CONSUMPTION_ODDITIES.get((unit_index, period_key))
    if oddity is not None and (oddity[2] is None or service in oddity[2]):
        value = value * Decimal(oddity[0])
    # A register never goes BACKWARDS between two reads: `validation`'s
    # `negative_usage` is a hard error and would refuse the batch, so a month
    # rounds to at least 1 of whatever this service measures.
    rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return rounded if rounded >= 1 else Decimal("1")


def water_consumption_kgal(unit_index: int, period_key: str) -> Decimal:
    """This unit's water use for the period, in **kgal** — never a bare number.

    Deterministic on purpose: the same tenant seeded twice gets the same
    figures, so a screenshot taken on Tuesday still matches on Friday.

    Unit 0 consumes exactly 8 kgal in every period, which is B5 GT-17's own
    consumption — the reference bill this fixture reproduces so a frozen figure
    stands behind at least one bill a human can open.

    ⚠ **THE GOVERNMENT BUILDING IS THE SECOND FLAT CASE, AND IT IS HERE FOR
    UNIT 0's REASON RATHER THAN A NEW ONE (`CR-062` addendum J2/J3).** Its
    subtotal — `$8.00` base + `$65.50` usage + **`$54.00` sewer (`CR-081`: 90% of
    12 kgal at `$5.0000`; it was `$26.20`)** + `$30.00` trash
    = **`$157.50`**, against which the Municipal discount takes **`$31.50`** and
    leaves **`$126.00`** — is a figure the Product Owner was shown and can check
    by hand, and a draw that drifted ±1 kgal by month would make it true in June
    and false in July. **12 kgal is what makes `$65.50` come out** on the seeded
    inclining tiers: 5 at `$4.00` plus 7 at `$6.50`.

    ⚠ **THE ±1 MONTHLY DRIFT IS GONE — PO 2026-09-07** (*"you will have to do
    some variation … for consumptions"*). The shape is `_shaped`'s: a seasonal
    curve per service, a response per customer, and three named oddities. Both
    flat cases above are answered BEFORE any of that, so neither ❄️ figure can
    move — see `_shaped`'s own first two lines.
    """
    return _shaped(unit_index, period_key, "water")


# ── `DEF-MET-4496` · THE CONNECTION SIZE A SEEDED METER IS ────────────────────
# **THE SEED USED TO GIVE EVERY METER OF EVERY SERVICE THE SMALLEST BAND**, and
# the line that did it was `seed_size_class = sizes[0] if sizes else None` in
# `apps/assets/sample_data.py`. It was correct code for one meter and wrong for
# an estate: 50 electric meters all `E-1P-100` against a SIX-size ladder and 51
# water meters all `W-58` against a NINE-size one, so a per-size base curve
# would be exercised at exactly ONE point and the other prices could be wrong
# with every test green.
#
# ⚠ **WHY THIS IS SAFE FOR THE ❄️ FROZEN FIGURES, AND IT IS NOT SAFE BY
# ACCIDENT.** `AWKWARD_UNITS` — `CASE_REFERENCE_BILL` (unit 0, `GT-17`'s water
# `$39.50` / sewer `$15.80`) and every other signed demonstration — KEEP THE
# SMALLEST BAND, which is the size they carry today. So every figure finance has
# signed is computed from an unchanged connection size, by construction rather
# than by inspection, and `test_*` over those cases cannot move. The spread
# applies to ORDINARY units only.
#
# ⚠ **IT MOVES NO MONEY TODAY AND IS INTENDED TO MOVE MONEY TOMORROW.** No rate
# schedule in the seed carries a per-size override yet, so `pricing_inputs`
# returns the same NULL every-size group whichever band a unit has and every
# seeded bill is byte-identical. The moment the rating lane seeds a per-size
# base curve, these bands are what make it REACHABLE — a residential 100A
# service and an industrial CT-metered one stop billing the same base, which is
# the whole point of a curve.
#
# The ladders are indexed positionally against each service's RATIFIED list
# (`BR-TEN-171`) and every code is checked against the tenant's own list before
# it is written, so a tenant that has renamed or removed a band falls back
# rather than receiving a code it does not hold.
METER_SIZE_BY_CLASS: dict[str, dict[str, tuple[str, ...]]] = {
    # Residential gets TWO bands so the commonest class alone proves the curve
    # has more than one point on it; the bigger classes climb from there.
    "water": {
        "residential": ("W-58", "W-34"),
        "commercial": ("W-1", "W-112", "W-2"),
        "government": ("W-3",),
        "industrial": ("W-4",),
    },
    "electric": {
        "residential": ("E-1P-100", "E-1P-200"),
        "commercial": ("E-1P-400", "E-3P-200"),
        "government": ("E-3P-400",),
        # A CT-metered service is the industrial case and is the one band that
        # exists purely to say "this connection is too big to meter directly".
        "industrial": ("E-CT",),
    },
    "gas": {
        "residential": ("G-250", "G-425"),
        "commercial": ("G-630",),
        "government": ("G-1000",),
        "industrial": ("G-1000",),
    },
    # ⚠ **`thermal_heat`'s FOUR CLASSES WERE WITHDRAWN 2026-09-07 (`CR-080`).**
    # This map answers *"which BAND is this unit's METER sized at"*, and
    # thermal has neither now: it is capacity-billed on connected tonnage, it
    # plants no meter, and its three `TH-CW-*` bands are withdrawn from
    # `BR-TEN-171` outright. Its tonnage per unit is `thermal_tonnage_plan()`
    # below, which is a different question with a different answer shape — a
    # CAPACITY the utility sums, not a band a meter sits in.
}


def meter_class_of(unit_index: int) -> str:
    """WHICH customer class a seeded unit's connection is sized for.

    The estate's own seats decide it — the government building, the industrial
    seat and the two commercial units are named constants already, and
    everything else is a household. This is the one place that mapping is
    written down, so the meters block and any later reader agree.
    """
    if unit_index == CASE_GOVERNMENT_ACCOUNT:
        return "government"
    if unit_index == CASE_INDUSTRIAL_ACCOUNT:
        return "industrial"
    if unit_index in _COMMERCIAL_UNIT_INDEXES:
        return "commercial"
    return "residential"


def meter_size_class_for(service: str, unit_index: int, ratified: Any = None) -> str | None:
    """**THE BAND THIS UNIT'S CONNECTION IS, or `None` when the vocabulary does
    not answer for the service** — `DEF-MET-4496`.

    `ratified` is the tenant's own ratified code list; when it is given, a code
    this fixture would have chosen but the tenant does not hold is skipped in
    favour of the next one it DOES hold, and the whole answer degrades to the
    first ratified code rather than to a band the tenant never received.
    Passing `None` skips that check and is for callers that have already done it.

    ⚠ **AN AWKWARD UNIT ALWAYS GETS THE FIRST RATIFIED BAND**, which is the size
    it carries today. Every ❄️ frozen figure in B4/B5 hangs off one of those
    units, so this is what makes the spread unable to move a signed number.
    """
    allowed = tuple(ratified) if ratified is not None else None

    def _first_allowed(codes: "tuple[str, ...]") -> str | None:
        for code in codes:
            if allowed is None or code in allowed:
                return code
        return None

    by_class = METER_SIZE_BY_CLASS.get(service)
    if not by_class:
        return _first_allowed(allowed) if allowed else None
    unit_class = meter_class_of(unit_index)
    if unit_index in AWKWARD_UNITS and unit_class == "residential":
        # ⚠ **THE PIN IS RESIDENTIAL-AWKWARD ONLY, AND THE NARROWING IS
        # DELIBERATE.** Every ❄️ frozen B4/B5 figure hangs off a RESIDENTIAL
        # demonstration unit — `GT-17`'s water `$39.50` on `CASE_REFERENCE_BILL`
        # above all — so pinning those to the band they already carry is what
        # makes this change unable to move a signed number.
        #
        # The estate's two COMMERCIAL seats (`_COMMERCIAL_UNIT_INDEXES`) are
        # also in `AWKWARD_UNITS`, but for `CASE_LANDLORD` — a multi-property
        # CHEQUE, which is a payments case and carries no signed per-size
        # rating figure. Pinning them too would have left the commercial bands
        # (`W-1`/`W-112`/`W-2`, `E-1P-400`/`E-3P-200`) unreachable by any unit
        # in the fixture, which is the exact defect this function exists to fix
        # — a curve with no commercial point on it. So they spread.
        return allowed[0] if allowed else by_class["residential"][0]
    codes = by_class.get(unit_class) or ()
    if not codes:
        return _first_allowed(allowed) if allowed else None
    # Deterministic and stable: the same unit gets the same band on every
    # re-seed, so an idempotent replay never rewrites a connection size.
    chosen = codes[unit_index % len(codes)]
    if allowed is not None and chosen not in allowed:
        return _first_allowed(codes) or (allowed[0] if allowed else None)
    return chosen


def meter_plan(
    service: str = "water",
    uom: str = WATER_UOM,
    multiplier: str = "1",
    replacement: bool = True,
) -> tuple[dict[str, Any], ...]:
    """One meter per unit (48), plus the ONE replacement the spec's case 3
    needs — a read chain that crosses two serials.

    `retired_after` names the period after which the meter comes off; the
    replacement carries `replaces` so the reads seeder knows which register the
    chain continues on.

    ⚠ **CR-039 A1 — `service` AND `uom` ARE PARAMETERS AND THE DEFAULTS ARE THE
    WATER ESTATE, BYTE FOR BYTE.** Called with no arguments this returns exactly
    what it returned before DEF-795: `W-5000 … W-5047` in `kgal`, plus `W-9011`.
    An electric tenant calls `meter_plan("electric", "kWh")` and gets the SAME
    48 units, the SAME replacement case and the SAME walk-by method with
    `E-5000 …` reading kWh. The shape is one description; the service is a
    parameter.

    **The UoM is never defaulted for a non-water service** — the caller resolves
    it from the tenant's own `tenant_services.primary_uom` and refuses when the
    tenant declares none (see `estate_plan`). The default here exists only so
    the water call site and the pinned tests read unchanged.

    ⚠ **`multiplier` IS BR-MET-143's SEEDED FACTOR (PO 2026-08-27) AND IT IS
    NOT TYPED HERE.** It was the literal `"1"` on both rows below until
    2026-08-27; it is now `EstatePlan.multiplier`, DERIVED by
    `register_multiplier` from the tenant's own register UoM and its billed UoM.
    The default `"1"` keeps every existing call site and every pinned test
    byte-identical — a tenant with no `billed_uom` configured has the same unit
    on both sides, and ×1 IS the reconciliation for that case.

    ⚠ **`replacement=False` PLANTS THE 48 AND NOT THE SWAP — `CR-062` C8,
    judgment 4 (2026-09-02).** The estate now plants a meter per unit PER
    metered service, and the case-3 swap is a DEMONSTRATION rather than
    coverage: it exists so the meter-change history and a read chain crossing
    two serials have something to show. Repeating it on every metered service
    would give an electric + water + gas utility three identical swaps on the
    same unit in the same month, which makes the demo harder to read, not
    richer. So the FIRST metered service (`EstatePlan.primary`) keeps the swap
    and the rest get `replacement=False`. **The default is `True`**, so every
    existing call site and every pinned test — including a water-only tenant's
    49 meters — is byte-identical.
    """
    rows: list[dict[str, Any]] = []
    for unit in units_flat():
        index = unit["unit_index"]
        rows.append(
            {
                "asset_no": meter_no(service, index),
                "unit_index": index,
                "service": service,
                "uom": uom,
                "meter_type": "walk_by",
                "read_method": "walk_by",
                "multiplier": multiplier,  # BR-MET-143 — derived, never typed
                "retired_after": (
                    "june" if replacement and index == CASE_METER_REPLACED else None
                ),
            }
        )
    if not replacement:
        # CR-062 C8 — no swap on this service, so nothing is retired and no
        # second serial exists. The unit still gets its ordinary meter above.
        return tuple(rows)
    rows.append(
        {
            "asset_no": replacement_meter_no(service),
            "unit_index": CASE_METER_REPLACED,
            "service": service,
            "uom": uom,
            "meter_type": "walk_by",
            "read_method": "walk_by",
            # BR-MET-143 — the SAME factor as the register it replaces: a swap
            # changes the serial, not the scale between the tenant's register
            # unit and the unit it bills in.
            "multiplier": multiplier,
            "retired_after": None,
            "replaces": meter_no(service, CASE_METER_REPLACED),
            "installed_for": "july",
        }
    )
    return tuple(rows)


def account_plan() -> tuple[dict[str, Any], ...]:
    """One account per unit — 48, which is spec acceptance item 2's own number.

    `customer_key` is what makes case 13 real: the landlord's two units share
    one key, so ONE customer holds TWO accounts and the S20 customer screen has
    something to show that is not one-to-one.

    ⚠ **THREE ACCOUNT TYPES SINCE `CR-062` ADDENDUM J3/J4, NOT TWO.** The last
    two seats are the government building and the industrial plant, and they are
    the first seeded accounts ever to carry `government` and `industrial` —
    codes the platform catalogue has held since it was written. Their names
    carry the word **Sample** and their addresses are this fixture's own
    invented town, because the government seat is the one account the fixture
    enrols in a subsidy and *"it must be obviously a demo … and must never be a
    real party"* (`CR-062` addendum J2).
    """
    rows: list[dict[str, Any]] = []
    for unit in units_flat():
        index = unit["unit_index"]
        commercial = is_commercial(index)
        if index in DEMO_ORGANISATION_NAMES:
            name = DEMO_ORGANISATION_NAMES[index]
            given, family = None, name
        elif commercial:
            name = _COMMERCIAL_NAMES[index - 46]
            given, family = None, name
        else:
            given = _GIVEN[index % len(_GIVEN)]
            family = _SURNAMES[index % len(_SURNAMES)]
            name = f"{given} {family}"
        customer_key = (
            f"landlord-{CASE_LANDLORD[0]}" if index in CASE_LANDLORD else f"unit-{index}"
        )
        account_type = DEMO_ACCOUNT_TYPES.get(
            index, "commercial" if commercial else "residential"
        )
        rows.append(
            {
                "unit_index": index,
                "unit_no": unit["unit_no"],
                "address_line": unit["address_line"],
                "display_name": name,
                "given_name": given,
                "family_name": family,
                "customer_key": customer_key,
                "account_type": account_type,
                "email": _email_for(index, family),
                "phone": f"+1 (402) 555-{1000 + index:04d}",
                # The landlord's own postal address, so the two accounts bill to
                # one place — which is the point of the case.
                "bill_to": (
                    "12 Quarry Hill Ct" if index in CASE_LANDLORD else unit["address_line"]
                ),
                "moved_out_on": move_out_on() if index == CASE_MOVED_OUT else None,
                "moved_in_on": move_in_on() if index == CASE_MOVED_IN else None,
            }
        )
    return tuple(rows)


def _email_for(index: int, family: str) -> str:
    return f"{family.lower().replace(' ', '')}{index}@example.invalid"


# ── Sub-meters + behind-the-meter devices (CR-010 Part-10.4, PO 2026-08-17) ─
# PO verbatim: *"please add sub meter and few bhend the meter devices"* — until
# this amendment the asset block seeded neither (measured: grep for
# sub_meter/BTM over apps/assets/sample_data.py returned nothing), so two of
# S49's three tabs were empty on every seeded tenant. The vocabulary is the
# SEEDED one (`asset_types`: sub_meter · backflow · pv · ev_charger; the
# tenancy `device_types` lookup names the same devices — BACKFLOW, INVERTER,
# EVCHG), never invented codes.


def apartment_unit_indexes() -> tuple[int, ...]:
    """The apartment block's six units — the `residential_submetered` ones.

    DERIVED from the premises plan rather than hard-coded 40..45, so a change
    to the mix above cannot silently point the sub-meters at houses.
    """
    return tuple(
        unit["unit_index"]
        for unit in units_flat()
        if unit["unit_type"] == "residential_submetered"
    )


def sub_meter_plan(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[dict[str, Any], ...]:
    """One SUB-METER per apartment unit, parented on that unit's own meter
    (BR-AST-003: a sub-meter requires a meter parent).

    ⚠ **CR-039 A3 — SERVICE-SHAPED, AND THAT IS THE SUBMETERING HALF OF
    DEF-795.** These rows said `water` in a literal, and `apps/assets/
    sample_data._seed_cr028_r10_shape` skips any entry naming a service the
    tenant has not enabled. So **a submetering utility that sells electricity —
    the business this product exists for — received no master meter and not one
    sub-meter**, on top of receiving no estate at all. The hierarchy is the same
    hierarchy in any service; only the register changes.

    ⚠ DELIBERATELY NEVER READ, and that is safe BY MEASUREMENT, not hope: a
    sub-meter created with a `unit_id` lands on the unit's EXISTING water
    service point (`ensure_service_point` is get-or-create), and
    `billing_reads_for_unit` takes the latest head ACROSS the point's assets —
    the parent meter's committed read — so a read-less sub-meter adds no
    missing-read to the July run the PO is going to press. Sub-metered detail
    reads are a metering story, not this fixture's.
    """
    return tuple(
        {
            "asset_no": f"SM-{7000 + index:04d}",
            "unit_index": index,
            "parent_asset_no": meter_no(service, index),
            "service": service,
            "uom": uom,
            "meter_type": "sub_meter",
            "read_method": "manual",
        }
        for index in apartment_unit_indexes()
    )


#: A few behind-the-meter devices (PO: backflow preventer, solar inverter, EV
#: charger). Non-measuring types (BR-AST-009), so they declare NO service and
#: NO UoM — a water-only tenant can hold a customer's solar inverter without
#: selling solar. Placement is deliberate: the backflow preventer guards the
#: laundromat's commercial connection (annual test, BR-AST-027 seeds 12
#: months), the inverter and charger sit on two ordinary houses.
BTM_DEVICE_PLAN: tuple[dict[str, Any], ...] = (
    # ⚠ **`certification_due` ADDED 2026-09-07 (`DEF-AST-4495`).** `BR-AST-027`
    # gives this device a TWELVE-MONTH test interval and `SEED_TEST_INTERVAL
    # _MONTHS` has carried it since the type existed — but
    # `selectors._interval_due_date` derives the due date from `last_test_date +
    # interval`, **no seeded asset has ever had a `last_test_date`**, and
    # `next_test_date` therefore answered `None` for every asset of every demo
    # tenant. The registry's *Next-test* column was a dash on every row, so a
    # working screen was indistinguishable from a broken one — the same shape
    # `DEF-CWP-3995` fixed for `location_note` three lines down.
    #
    # An EXPLICIT `certification_due` is the column that WINS in
    # `next_test_date`, so this puts a real date on the one device in the
    # fixture with a genuine annual statutory test: a backflow preventer
    # guarding a COMMERCIAL water connection.
    #
    # ⚠ **DELIBERATELY IN THE PAST RELATIVE TO THE FIXTURE'S OWN TIMELINE** (the
    # seeded cycles run June–August 2026). A date nothing has reached yet
    # exercises the column and nothing else; OVERDUE is what a certification
    # rule is FOR, and until now that rule had not one row to find on a demo
    # tenant.
    {"asset_no": "BF-0001", "type": "backflow", "unit_index": 46,
     "certification_due": "2026-06-15",
     "note": "backflow preventer on the Creekside Laundromat connection"},
    {"asset_no": "PV-0001", "type": "pv", "unit_index": 4,
     "note": "customer-owned solar inverter (device_types: INVERTER)"},
    {"asset_no": "EV-0001", "type": "ev_charger", "unit_index": 8,
     "note": "customer EV charger (device_types: EVCHG)"},
)


# ── CR-028 AST-W0 · the r10 registry shape (B16 §9, PO 2026-08-22) ──────────
# PO verbatim: *"You will have to update test cases and test data as well ;
# seed data as well include them in tasks and then start waves and complete
# waves"* — AST-W0-T1 is that seed. Everything in this section is ADDITIVE:
# meter_plan() / sub_meter_plan() / BTM_DEVICE_PLAN above are UNTOUCHED, so
# every count and shape a prior test pins still holds, and nothing existing is
# renumbered.
#
# WHAT THIS SECTION DELIVERS, and the ruling behind each piece:
#   · TRASH CARTS — closes DEF-496: CR-019's ruled walkthrough (*"they are
#     bill 1 trash can $15 - for example if you have 3 you multiple by 3"*,
#     PO 2026-08-21) could not be produced from the shipped tenant because no
#     cart asset existed anywhere. All three BR-RAT-090 cases land: THREE on
#     one unit, ONE on another, NONE on a third — so a zero is provably a real
#     answer beside real threes.
#   · A MASTER METER + SUBS — r10's `Master · N units` / `Sub → M-MASTER-…`
#     role tags (B16 §4.1) drawn from real rows: one meter_type=`master` on
#     the apartment block, three new sub-meters parented ON IT (BR-AST-003).
#   · A NET METER — BR-AST-010's locked-on flag, so the detail's net line
#     renders. Its EXPORT READS are metering's half (W2) and are not declared
#     here.
#   · THE TWO MISSING BTM KINDS — comms endpoint + battery storage, making
#     all five r10 device kinds real (B16 §4.3). In their OWN plan constant:
#     BTM_DEVICE_PLAN is pinned to three kinds by CR-010's test.
#   · INVENTORY STOCK — unassigned assets (created with NO unit, so they land
#     status `inventory`), one aged past 12 months, feeding the Inventory
#     tab's counts-and-costs launch scope (§10-D5).
#   · VALUATION ON EVERY NEW SEED — BR-AST-047: purchase cost (4dp string,
#     rule 2), purchase date, supplier, expected life. Suppliers are the four
#     r10 names; costs sit in the r10 $118–$412 ballpark.

#: The four supplier names r10 draws (B16 §4.4 / W0-T1). D5 ruled supplier a
#: FREE-TEXT column for now — this tuple is fixture vocabulary, not a lookup.
CR028_SUPPLIERS: tuple[str, ...] = ("Itron Inc", "Badger Meter", "Neptune", "Watts Water")

#: BR-AST-042's seeded non-measuring type the carts use — platform vocabulary,
#: never invented here (the DEF-496 row names it as already present).
TRASH_CART_TYPE = "container_cart"

#: The ratified `BR-TEN-171` band the seeded carts ARE — `BR-AST-500`,
#: `DEF-2414`, PO ruling 2026-09-01 (*"set in seeder … the sizes also on
#: Units"*). It is the code the fixture's own valuation line has claimed since
#: the carts were first seeded — *"r10 ballpark floor; a 96-gal cart"* — said
#: once here instead of implied in a comment.
#:
#: ⚠ **IT IS CHECKED AGAINST THE TENANT'S RATIFIED LIST AND NEVER TRUSTED ON ITS
#: OWN** (`assets.sample_data._container_size_class`): a tenant whose list does
#: not carry it takes the smallest band instead, and a service with no ratified
#: bands takes NULL, which is the honest answer and not a fallback.
#:
#: **It moves no money.** No seeded rate schedule carries a per-size override
#: and `BASE-T` is flat, so `pricing_inputs` returns the same every-size group
#: whichever band is stored — the value is a fact a utility records, not a
#: price. Trash's seven bands are `CART-35/64/96` and `DUMP-2/4/6/8`.
TRASH_CART_SIZE = "CART-96"

#: The three BR-RAT-090 cart cases, on deliberately ORDINARY units — none is in
#: AWKWARD_UNITS, so no frozen figure moves: unit 0 (GT-17's $39.50/$15.80
#: reference bill) keeps ZERO carts by construction and its trash line stays
#: what the schedule alone makes it.
CART_UNIT_WITH_THREE = 1  # ⚠ THE CR-019 WALKTHROUGH UNIT: 3 × $15.00 = $45.00
CART_UNIT_WITH_ONE = 2  # 1 × $15.00 = $15.00
CART_UNIT_WITH_NONE = 6  # 0 carts — "the utility looked and there are none"
#: ⚠ **THE FOURTH CART CASE, AND IT IS A MONEY FIGURE RATHER THAN A SHAPE
#: (`CR-062` addendum J2/J3).** Two carts on the government building is the
#: `$30.00` trash component of its **`$129.70`** subtotal, so unlike the three
#: above it cannot be moved without moving a figure the Product Owner was shown.
CART_UNIT_WITH_TWO = CASE_GOVERNMENT_ACCOUNT  # 2 × $15.00 = $30.00


def trash_cart_plan() -> tuple[dict[str, Any], ...]:
    """The six assigned carts: three on the walkthrough unit, one next door, and
    two on the government building.

    Non-measuring (BR-AST-009 — no meter_type, no register), but they DO
    declare `service: trash`: BR-RAT-090's count runs through the asset's
    SERVICE POINT, so a cart without one is invisible to billing — which is
    DEF-496 with extra rows. The seeder skips this block entirely (and says
    so) on a tenant that has not enabled trash.
    """
    def _cart(number: int, unit_index: int) -> dict[str, Any]:
        return {
            "asset_no": f"CART-{number:04d}",
            "type": TRASH_CART_TYPE,
            "unit_index": unit_index,
            "service": "trash",
            "valuation": {
                "purchase_cost": "118.0000",  # r10 ballpark floor; a 96-gal cart
                "purchase_date": "2026-01-05",
                "supplier": "Watts Water",
                "expected_life_years": 10,
            },
        }

    return (
        _cart(1, CART_UNIT_WITH_THREE),
        _cart(2, CART_UNIT_WITH_THREE),
        _cart(3, CART_UNIT_WITH_THREE),
        _cart(4, CART_UNIT_WITH_ONE),
        # CR-062 addendum J2/J3 — the government building's two, which are the
        # `$30.00` in its `$129.70` subtotal.
        _cart(5, CART_UNIT_WITH_TWO),
        _cart(6, CART_UNIT_WITH_TWO),
    )


# ── CR-062 D3–D7 · THE BILLABLE CAPACITY EQUIPMENT ─────────────────────────
# **WHY THIS BLOCK EXISTS, IN ONE SENTENCE: THE PRICE IS SEEDED AND THE
# ARITHMETIC IS WIRED, AND FOUR SERVICES STILL BILLED `$0.00` BECAUSE NOTHING
# WAS INSTALLED TO MULTIPLY THE PRICE BY.**
#
# Two lanes landed the other two thirds of this on 2026-09-02 and each recorded
# the same boundary in its own words. `CR-062` E3 seeded the Product Owner's own
# figures — solar **$14.0000 per kW**, battery `$3.0000`/kW, storm water
# `$4.5000`/ERU, broadband `$0.1000`/Mbps — and `CR-062` D1/H2 made the billable
# quantity the SUM of installed capacity, so three panels of 2 kW, 4 kW and 8 kW
# are **14 kW** and no longer **3**. The D1 lane wrote: *"the estate seeds no
# capacity equipment, so a seeded tenant exercises the sum with 0 on every unit
# until they land"*. This is that landing.
#
# **WHAT SHAPE, AND IT IS COPIED RATHER THAN INVENTED.** `trash_cart_plan` above
# is the one capacity service that already works end to end, and its three cases
# are deliberate: SEVERAL on one unit, ONE on another, NONE on a third — so a
# `$0.00` line is provably a real answer sitting beside real numbers rather than
# a gap nobody noticed. `CR-062` D7 asks for that shape on every capacity
# service and every service below keeps it.
#
# ⚠ **THE UNITS ARE ORDINARY ON PURPOSE, AND THAT IS THE SAME REASON
# `CART_UNIT_WITH_THREE` IS 1 AND NOT 0.** None of the indexes below is in
# `AWKWARD_UNITS`, so no frozen figure moves: unit 0 stays ❄️ `GT-17`'s
# reference bill (water **$39.50**, sewer **$15.80**) and carries no capacity
# equipment of any kind, by construction. `test_cr062_d3_d7_capacity_equipment`
# asserts that mechanically rather than by this comment.
#
# ⚠ **MIXED SIZES ON ONE CONNECTION ARE THE NORMAL CASE HERE AND NOT THE TRAP
# THEY ARE FOR TRASH AND FIRE** (decision log 2026-09-02, *"one connection, one
# size" is a rule about METERED connections*). Solar, battery, storm water and
# broadband SUM their capacity, so `2 + 4 + 8 kW` is one quantity of `14 kW` on
# ONE line and `metering.connection_size_for`'s refusal is never armed — what
# keeps it unarmed is that the seeded schedules carry no per-size override. A
# COUNTING service (trash, fire) is the opposite shape and bills one line per
# size. **If a lane finds itself needing per-size grouping for solar, it has
# misread the model.**

#: `pv` · `battery` · `modem_cpe` are three of `BR-AST-042`'s ratified asset
#: types. The vocabulary comes from the platform list exactly as
#: `TRASH_CART_SIZE`'s does, and the seeder checks every size code against the
#: tenant's own ratified ladder before writing it.
#:
#: ⚠ **THIS SAID *"NOTHING BELOW INVENTS A THIRTEENTH"* UNTIL 2026-09-07, AND A
#: THIRTEENTH IS EXACTLY WHAT `fire_line` IS.** The sentence was true when it was
#: written and it is amended here rather than worked around, because `OQ-1361`
#: asks for precisely this row and hands it to the lane that owns these files:
#: *"This is ours to decide and it is recorded as a question only because it
#: changes a PLATFORM CATALOGUE — a row in `SEED_ASSET_TYPES`, its mirror in
#: `lookup_defaults.json` and a fixture serial, which belongs with the lane that
#: owns those files rather than being taken by a billing lane on its way past."*
#: See `FIRE_ASSET_TYPE` below for why it is its own type rather than
#: `backflow`, which is the alternative that question names.
SOLAR_ASSET_TYPE = "pv"
BATTERY_ASSET_TYPE = "battery"
BROADBAND_ASSET_TYPE = "modem_cpe"

#: **D3 · THE PRODUCT OWNER'S OWN ARRAY.** PO verbatim, 2026-09-02: *"on given
#: Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw , it means the totla
#: capacity will be 14 Kw ; rate will be for 1 Kw = 14 $ per KW"*. At the seeded
#: `$14.0000` that bills **`$196.00`** — the figure `test_cr062_d1` proves from
#: its own fixture and this unit proves from the SEED.
#:
#: Unit 4 already holds `PV-0001`, the CUSTOMER-OWNED inverter, which declares
#: no service (`BR-AST-009`) and therefore stands on no solar service point and
#: adds nothing to this total. That is not a coincidence to be tidied away: the
#: demo now shows both kinds of thing on one roof — a device the utility records
#: and does not bill, and three panels it bills.
SOLAR_UNIT_WITH_THREE_PANELS = 4
SOLAR_THREE_PANEL_SIZES: tuple[str, ...] = ("SOL-P2", "SOL-P4", "SOL-P8")  # 2+4+8 = 14 kW
SOLAR_UNIT_WITH_ONE_PANEL = 12
SOLAR_ONE_PANEL_SIZE = "SOL-P5"  # 5 kW × $14.0000 = $70.00
#: The ruled zero (`BR-MET-108`): the utility looked and this roof has no
#: panels. `0 kW × $14.0000` is `$0.00` and the line goes on the document.
SOLAR_UNIT_WITH_NO_PANELS = 16


# ── PO 2026-09-07 · WHICH REGISTERS AN ELECTRIC METER CARRIES ────────────────
#
# **THE RULING, VERBATIM:** *"now your reading model is correct - add seed data
# accordingly"*, on a model whose third part was *"for Electric if rates
# scheudule is TOU, Seaosnal or Demadn then reading should be in like with
# that"*. Decision log 2026-09-07, *"TWO RULINGS IN ONE BREATH"*, part (2)(c).
#
# **WHAT IT REPLACED, MEASURED ACROSS EVERY SEEDED TENANT:** 4 on-peak, 4
# mid-peak, 4 off-peak, 2 demand and 2 export readings in the whole product,
# every one of them on three hand-authored meters of ONE tenant
# (`seed_demo.DEMO_CYCLE_READS`), while all fifty electric meters of the sample
# estate read a single `total` dial.
#
# ⚠ **TWO OF THE THREE SHAPES THE PO NAMED CHANGE THE READING AND ONE DOES
# NOT — PUT TO THEM AND NOT DISPUTED, AND IT IS WHY THERE IS NO SEASONAL
# REGISTER HERE.** Time-of-use splits the dial into three windows and demand
# adds a maximum register beside it; **seasonal changes only how the same single
# total is PRICED** (that is `OQ-234`'s closure, ruling (1) of the same
# breath — `apps/rating/pricing/models/seasonal.py`, not a register). A lane
# reading the sentence above without this paragraph would invent a `season`
# channel that nothing may ever write, so the paragraph is here rather than in
# a commit message.
#
# ⚠ **AND THE ESTATE'S OWN ELECTRIC SCHEDULE IS STILL `tiered` FOR EVERY UNIT
# — `DEF-MET-4512`, filed rather than papered over.** The three shapes below are
# a fact about the CUSTOMER (which tariff this utility has put them on), and
# `apps/rating/sample_data.py` seeds one electric schedule and it is tiered. So
# the six time-of-use customers' three window registers and the three demand
# customers' peaks are correct readings that the estate's own schedule does not
# yet price: `validation.plan_register_completeness` reports them as
# `unexpected` — informational, never a severity — and the bill prices the
# `total` beside them. **This is the wiring half of hard-won law 2 and it is
# named, dated and owed rather than left to be discovered.** It is declared HERE
# so that the day rating seeds a time-of-use and a demand schedule it reads
# `electric_tariff_shape` and the two cannot disagree — the same "ONE function,
# because two would drift" that `plan_class_for` already is.

#: **METERING'S OWN REGISTER VOCABULARY, TRANSCRIBED — NEVER IMPORTED.** This
#: module states no Django import and no ORM (see its own docstring), so the
#: six channel names `apps/metering/models.CHANNELS` declares are written out
#: here. They are B2 addendum r8's own values and `BR-MET-059`'s (PO RD-1
#: option B); a seventh is added there, not invented here.
CHANNEL_TOTAL = "total"
CHANNEL_TOU_ON = "tou_on"
CHANNEL_TOU_MID = "tou_mid"
CHANNEL_TOU_OFF = "tou_off"
CHANNEL_DEMAND = "demand"
CHANNEL_EXPORT = "export"
TOU_WINDOW_CHANNELS: tuple[str, ...] = (CHANNEL_TOU_ON, CHANNEL_TOU_MID, CHANNEL_TOU_OFF)

#: The three shapes an electric customer of this demo can be on.
SHAPE_TIERED = "tiered"
SHAPE_TIME_OF_USE = "time_of_use"
SHAPE_DEMAND = "demand"

#: The customers this utility has put on a TIME-OF-USE tariff — *"a handful"*.
#:
#: **Six of fifty, and three of them are the solar seats on purpose.**
#: `seed_demo`'s own net-metering note already states the pairing — *"a
#: residential solar household on a time-of-use tariff is the ordinary shape of
#: that customer"* — so 4 and 12 (`SOLAR_UNIT_WITH_THREE_PANELS`,
#: `SOLAR_UNIT_WITH_ONE_PANEL`) lead the list, 16 is the solar seat with NO
#: panels (a time-of-use household that exports nothing, which is the contrast
#: that makes the export register mean something), and the rest are ordinary.
#:
#: ⚠ **NONE IS IN `AWKWARD_UNITS`, NEITHER PINNED CUSTOMER IS HERE, AND THE SIX
#: CARRY SIX DIFFERENT SEASONAL RESPONSES AND SIT ON FOUR DIFFERENT WALK
#: ROUTES** (residues 4·5·0·2·6·1 of `SEASONAL_RESPONSE`; routes 5·3·5·2·1·3).
#: Chosen that way rather than found that way: six time-of-use customers who all
#: happened to be the flat-response ones would demonstrate three registers and
#: no variation at all, which is half the ruling.
TOU_UNITS: frozenset[int] = frozenset({4, 12, 14, 16, 20, 22})

#: The customers on a DEMAND tariff — *"the commercial ones"*.
#:
#: The two commercial suites and the industrial plant. `CASE_GOVERNMENT_ACCOUNT`
#: is deliberately NOT here: a public-works depot would be a perfectly ordinary
#: demand customer and it is the one seat a ❄️ frozen subtotal is computed from,
#: so it stays as plain as it can be. That is a choice, not an oversight.
DEMAND_UNITS: frozenset[int] = frozenset(set(_COMMERCIAL_UNIT_INDEXES) | {CASE_INDUSTRIAL_ACCOUNT})

#: The households with PV on the roof, which is what makes an export register
#: lawful (`BR-AST-029`; `validation.export_not_net` is a hard ERROR on a meter
#: whose `net_metering` flag is false). DERIVED from the panel plan rather than
#: listed again — `SOLAR_UNIT_WITH_NO_PANELS` is the third solar seat and has
#: none installed, so it exports nothing and must not appear here.
EXPORT_UNITS: frozenset[int] = frozenset({SOLAR_UNIT_WITH_THREE_PANELS, SOLAR_UNIT_WITH_ONE_PANEL})

#: How a time-of-use household's month divides between the three windows.
#:
#: ⚠ **NOT INVENTED — IT IS `EP-MET-03` §4's OWN SIGNED SHAPE, ROUNDED.** The
#: signed test data reads *"TOU M-7450 (E, kWh — deltas tou_on 210 / tou_mid 118
#: / tou_off 96 …)"*, which is 49.5 % / 27.8 % / 22.6 % of 424 kWh. On-peak and
#: mid-peak are taken at 50 % and 28 % and **off-peak is the REMAINDER**, so the
#: three windows sum to the total EXACTLY and `validation.tou_sum_sanity`
#: reports a 0.000000 % deviation rather than a rounding wobble against the
#: tenant's seeded 1 % tolerance.
TOU_ON_SHARE = Decimal("0.50")
TOU_MID_SHARE = Decimal("0.28")

#: A solar household's export as a share of what it draws in the same month.
#:
#: Fixture authorship and it prices nothing — no seeded schedule pays for an
#: export yet. It exists so the net-metering path has two records to show
#: (`BR-AST-029`: a net cycle is a consumption record AND an export record) on a
#: customer a clerk can open, instead of on one hand-authored meter.
EXPORT_SHARE = Decimal("0.30")

#: Peak kW per average kW — the ratio that turns a month's energy into the
#: maximum its demand register stood at.
#:
#: ⚠ **DERIVED FROM A FIGURE THIS FIXTURE ALREADY STATES, NOT CHOSEN.**
#: `UNIT_SERVICE_CONSUMPTION`'s own note works the industrial plant out at
#: *"54,000 kWh over a 730-hour month … an average of 74 kW"* against `CR-062`
#: addendum J4's stated **100 kW peak** — so peak ÷ average is 100 ÷ 74 ≈ 1.35,
#: and applying it back to the plant's own 54,000 kWh returns its own 100 kW.
#: Every other demand customer's peak is that same relationship at their own
#: size, which is a load factor rather than an arithmetic convenience.
HOURS_IN_A_MONTH = Decimal("730")
PEAK_TO_AVERAGE = Decimal("1.35")


def electric_tariff_shape(unit_index: int) -> str:
    """Which electric tariff shape this customer is on — and therefore which
    registers their meter carries.

    ⚠ **ONE FUNCTION, BECAUSE TWO WOULD DRIFT** — the same reason
    `plan_class_for` is one function. Metering seeds the registers from it and
    rating must seed the SCHEDULE from it; today rating seeds one tiered
    electric schedule for everybody and that gap is `DEF-MET-4512`, named in the
    block above rather than hidden behind an agreeable default here.
    """
    if unit_index in DEMAND_UNITS:
        return SHAPE_DEMAND
    if unit_index in TOU_UNITS:
        return SHAPE_TIME_OF_USE
    return SHAPE_TIERED


def read_channels(unit_index: int, service: str) -> tuple[str, ...]:
    """Every register this unit's meter reports for `service`, in file order.

    `("total",)` for every service that is not electricity and for every
    electric customer on a flat or tiered tariff, which is what this fixture has
    always seeded. The three shapes above add to it and never replace it: a
    time-of-use meter still reports its total (that is the number
    `tou_sum_sanity` checks the three windows against) and a demand meter still
    reports the energy its demand charge sits beside.
    """
    if service != "electric":
        return (CHANNEL_TOTAL,)
    channels = [CHANNEL_TOTAL]
    shape = electric_tariff_shape(unit_index)
    if shape == SHAPE_TIME_OF_USE:
        channels[:0] = list(TOU_WINDOW_CHANNELS)
    elif shape == SHAPE_DEMAND:
        channels.append(CHANNEL_DEMAND)
    if unit_index in EXPORT_UNITS:
        channels.append(CHANNEL_EXPORT)
    return tuple(channels)


def tou_window_split(total: Decimal) -> dict[str, Decimal]:
    """One month's energy divided across the three time-of-use windows.

    The three ALWAYS sum to `total` exactly — off-peak is the remainder — so the
    seeded meter is the healthy case `tou_sum_sanity` passes rather than the
    permanently-flagged one that teaches a clerk to dismiss the flag.
    """
    on = (total * TOU_ON_SHARE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    mid = (total * TOU_MID_SHARE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {
        CHANNEL_TOU_ON: on,
        CHANNEL_TOU_MID: mid,
        CHANNEL_TOU_OFF: total - on - mid,
    }


def demand_peak_kw(kwh_in_the_month: Decimal) -> Decimal:
    """The maximum this month's demand register stood at, in **kW**.

    ⚠ **THIS IS A PEAK AND NOT A COUNTER** — `BR-MET-051`, and
    `register_units.billable_quantity` bills its VALUE rather than a delta.
    Getting that wrong is `DEF-797`: **$154.00 where the correct charge was
    $4,532.00**, on a running product. A seeder that wrote a running total here
    would be the same defect entering by the front door.
    """
    peak = kwh_in_the_month / HOURS_IN_A_MONTH * PEAK_TO_AVERAGE
    # WHOLE kW, which is what makes the plant's own stated figure come back out:
    # 54,000 ÷ 730 × 1.35 is 99.86, and a peak read to one decimal would seed
    # `99.9` against `CR-062` addendum J4's **100 kW**. A demand dial is read in
    # whole kW here for that reason and no other.
    quantized = peak.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return quantized if quantized >= 1 else Decimal("1")


def export_kwh(kwh_in_the_month: Decimal) -> Decimal:
    """What a solar household pushed back to the grid this month, in kWh.

    NOT consumption and never added to it (`CLAUDE.md` rule 3, `BR-AST-029`) —
    it rides its own register on its own record.
    """
    value = (kwh_in_the_month * EXPORT_SHARE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return value if value >= 1 else Decimal("1")


#: **D4 · TWO BATTERIES.** `BAT-10` is 10 kW and `BAT-20` is 20 kW, at the
#: seeded `$3.0000` per kW: **`$30.00`** and **`$60.00`**. The 10 kW one stands
#: on unit 4 beside the solar array, which is what `CR028_DEVICE_PLAN` has said
#: in its own comment since the day `BAT-0001` was seeded — *"beside PV-0001 —
#: the solar household stores what it makes"*. `BAT-0001` itself is the
#: customer's own device and declares no service, so it is not in this total.
BATTERY_UNIT_WITH_TEN_KW = 4
BATTERY_TEN_KW_SIZE = "BAT-10"
BATTERY_UNIT_WITH_TWENTY_KW = 14
BATTERY_TWENTY_KW_SIZE = "BAT-20"
BATTERY_UNIT_WITH_NO_BATTERY = 18

#: **D5 · THREE BROADBAND TIERS, ONE PER UNIT.** `BB-100` · `BB-500` ·
#: `BB-1000`, at the seeded `$0.1000` per Mbps: **`$10.00`**, **`$50.00`** and
#: **`$100.00`**. A `modem_cpe` is the ratified asset type for customer-premises
#: broadband equipment (`BR-AST-042`) and the tier it is provisioned at is its
#: size class — which is what makes the speed a number the product can multiply
#: rather than a phrase in a display name.
BROADBAND_UNITS_BY_TIER: tuple[tuple[int, str], ...] = (
    (8, "BB-100"),
    (10, "BB-500"),
    (20, "BB-1000"),
)
BROADBAND_UNIT_WITH_NO_LINE = 22

# ── CR-063 · FIRE, THE ELEVENTH SERVICE, ON THE ESTATE (`OQ-1361`) ──────────
# **THE ONE CAPACITY SERVICE THAT COUNTS RATHER THAN SUMS, BESIDE TRASH.**
# `tenancy.service_size_classes.capacity_uom_for_service("fire")` answers `None`
# — fire diameters do not add up to anything — so `bills_one_line_per_size`
# answers `True` and `billing.gather` builds ONE TARIFF PER SIZE. That is the
# whole reason this block exists and is why its shape is trash's and not solar's.
#
# **THE RATIFIED ARITHMETIC, and it is the acceptance test for this lane.**
# `BR-RAT-024` / `CR-063`: the SIZE picks the price and the COUNT multiplies it.
# On `FIRE_UNIT_WITH_SIX_AND_TWO_TWOS`:
#
#     {"FL-6": 1, "FL-2": 2}  ->  1 × $60.00  +  2 × $12.00  =  $84.00
#
# **on TWO bill lines, never one line of `$84.00`** — they are different
# equipment at different prices and a single blended quantity would hide that
# (decision log 2026-09-02).
#
# ⚠ **THE COUNT IS THE NUMBER OF ASSET ROWS AND THERE IS NO `count` COLUMN
# ANYWHERE.** `assets.selectors.billable_asset_size_classes` returns ONE ENTRY
# PER `AssetAssignment`, and `metering.selectors.billable_asset_size_counts`
# groups them. So two 2" lines are TWO ROWS, exactly as
# `CART_UNIT_WITH_THREE`'s three carts are three rows. A `quantity` column was
# proposed as option B when `BR-RAT-090` was ruled and was REJECTED in terms —
# *"a typed number can disagree silently with the carts in the street"* — so
# adding one here would reverse a ruling rather than implement it.
#
# ⚠ **THREE PREDICATES MUST ALL HOLD OR THE ROW IS INVISIBLE TO BILLING**, and
# each has cost this fixture a defect before: the asset needs an
# `AssetAssignment` to the unit, a lifecycle stage whose `behavior_class` is
# `in_service`, and a SERVICE POINT of this service. A fire line with no service
# point is `DEF-496` again.
#
#: **`fire_line` IS ITS OWN ASSET TYPE AND NOT `backflow` — the judgment
#: `OQ-1361` delegates to this lane, recorded rather than asked (law 13).**
#: That question names `backflow` as *"the nearest"*, and it is genuinely a real
#: device on a fire connection. It is still the wrong row for three reasons, and
#: the third is money:
#:   1. **A backflow preventer is not the thing being sold.** The utility bills
#:      a fire SERVICE LINE by its diameter; the preventer is a device that sits
#:      ON that line and is inspected, which is a different fact about a
#:      different object.
#:   2. **The ladder would not fit.** `FL-2 … FL-12` are pipe diameters of a
#:      fire service. Hanging them on `backflow` would make a water backflow
#:      preventer and a fire line the same kind of thing with one size ladder
#:      between them.
#:   3. **It would MISPRICE, and this is the decisive one.** Fire's quantity is
#:      a COUNT of the unit's fire assets. Backflow preventers already stand on
#:      WATER connections in this fixture, so reusing the type would let a water
#:      device be counted as a fire line the moment anything put one on a fire
#:      point — a silent overcharge, which is exactly the direction
#:      `BR-RAT-090` refuses to guess in.
#: The hydrant stays out: the PO ruled 2026-09-03 that *"hydrants are assets not
#: utility service as of now"*, and its own type is `BR-AST-042`'s question and
#: not this one's.
FIRE_ASSET_TYPE = "fire_line"

#: **THE `$84.00` CASE — one 6" line and two 2" lines on ONE unit.** This is the
#: only unit in the fixture that proves the multiplication, and without it the
#: COUNT is exercised at 1 everywhere and a `× 2` bug is invisible.
FIRE_UNIT_WITH_SIX_AND_TWO_TWOS = 24
FIRE_SIX_AND_TWO_TWOS_SIZES: tuple[str, ...] = ("FL-6", "FL-2", "FL-2")
#: **A HOUSE WITH A SPRINKLER SYSTEM** — PO 2026-09-07, verbatim: *"even provide
#: it on residential units"*. Fire is not a commercial-only service and the
#: estate said it was until this row.
FIRE_UNIT_RESIDENTIAL = 26
FIRE_RESIDENTIAL_SIZE = "FL-4"  # 1 × $30.00
#: The government building and the industrial seat, so the ladder is exercised
#: across premises types and not only across sizes (PO 2026-09-07).
FIRE_UNIT_GOVERNMENT = CASE_GOVERNMENT_ACCOUNT
FIRE_GOVERNMENT_SIZE = "FL-6"  # 1 × $60.00
FIRE_UNIT_INDUSTRIAL = CASE_INDUSTRIAL_ACCOUNT
FIRE_INDUSTRIAL_SIZE = "FL-8"  # 1 × $100.00
#: The ruled zero (`BR-MET-108`): the utility looked and this unit has no fire
#: connection. `{}` is *"looked and there is nothing"* and bills `$0.00`; it is
#: NOT `None`, which is *"nobody looked"* and stops the account.
FIRE_UNIT_WITH_NONE = 28


def fire_line_plan() -> tuple[dict[str, Any], ...]:
    """`CR-063` — the fire service lines, in seeding order.

    Six rows across five units: the `$84.00` pair-and-a-six, a residential
    sprinkler, a government 6" and an industrial 8". `FIRE_UNIT_WITH_NONE` is
    deliberately absent — a unit with a fire service point and no line bills the
    ruled `$0.00`, which is a real answer standing beside real numbers.

    Non-measuring (`BR-AST-009` — no meter type, no register), but every row
    DECLARES `service: fire`, because the count runs through the asset's SERVICE
    POINT (`assets.billable_asset_size_classes`) and a line without one is
    invisible to billing — `DEF-496`, one service across.

    ⚠ **THE SERIAL PREFIX IS `FS-` AND NOT `FL-`, ON PURPOSE.** `FL-2` … `FL-12`
    are the ratified SIZE CLASS codes for this service, and an asset numbered
    `FL-0001` beside a size class `FL-6` in the same table reads as one
    vocabulary when it is two. The prefix is the only thing here that was free
    to choose, so it was chosen to keep those two apart on screen.
    """
    rows: list[dict[str, Any]] = [
        {
            "asset_no": f"FS-{1001 + n:04d}",
            "type": FIRE_ASSET_TYPE,
            "unit_index": FIRE_UNIT_WITH_SIX_AND_TWO_TWOS,
            "service": "fire",
            "size_class": size,
        }
        for n, size in enumerate(FIRE_SIX_AND_TWO_TWOS_SIZES)
    ]
    for number, unit_index, size in (
        (1004, FIRE_UNIT_RESIDENTIAL, FIRE_RESIDENTIAL_SIZE),
        (1005, FIRE_UNIT_GOVERNMENT, FIRE_GOVERNMENT_SIZE),
        (1006, FIRE_UNIT_INDUSTRIAL, FIRE_INDUSTRIAL_SIZE),
    ):
        rows.append(
            {
                "asset_no": f"FS-{number:04d}",
                "type": FIRE_ASSET_TYPE,
                "unit_index": unit_index,
                "service": "fire",
                "size_class": size,
            }
        )
    return tuple(rows)


def solar_panel_plan() -> tuple[dict[str, Any], ...]:
    """`CR-062` D3 — four panels: three on one roof, one on another, none on a
    third.

    Non-measuring (`BR-AST-009` — no meter type, no register), but every row
    DECLARES `service: solar`, because the capacity sum runs through the asset's
    SERVICE POINT (`assets.billable_asset_size_classes`) and a panel without one
    is invisible to billing. That is `DEF-496` — the defect that left the trash
    walkthrough unproducible — one service across.

    ⚠ **THE NUMBERS START AT 1001 AND NOT AT 0001 BECAUSE `PV-0001` IS TAKEN.**
    It is `BTM_DEVICE_PLAN`'s customer-owned inverter and
    `test_us_ten_019_sample_records` pins that tuple; a collision would be
    refused by `BR-AST-033`'s hard block at seed time, on a tenant, at the worst
    possible moment.
    """
    rows: list[dict[str, Any]] = [
        {
            "asset_no": f"PV-{1001 + n:04d}",
            "type": SOLAR_ASSET_TYPE,
            "unit_index": SOLAR_UNIT_WITH_THREE_PANELS,
            "service": "solar",
            "size_class": size,
        }
        for n, size in enumerate(SOLAR_THREE_PANEL_SIZES)
    ]
    rows.append(
        {
            "asset_no": "PV-1004",
            "type": SOLAR_ASSET_TYPE,
            "unit_index": SOLAR_UNIT_WITH_ONE_PANEL,
            "service": "solar",
            "size_class": SOLAR_ONE_PANEL_SIZE,
        }
    )
    return tuple(rows)


def battery_plan() -> tuple[dict[str, Any], ...]:
    """`CR-062` D4 — a 10 kW battery on one unit and a 20 kW on another.

    `BAT-0001` (the customer's own storage, declaring no service) keeps its
    number; these two start at 1001 for the reason the panels do.
    """
    return (
        {
            "asset_no": "BAT-1001",
            "type": BATTERY_ASSET_TYPE,
            "unit_index": BATTERY_UNIT_WITH_TEN_KW,
            "service": "battery",
            "size_class": BATTERY_TEN_KW_SIZE,
        },
        {
            "asset_no": "BAT-1002",
            "type": BATTERY_ASSET_TYPE,
            "unit_index": BATTERY_UNIT_WITH_TWENTY_KW,
            "service": "battery",
            "size_class": BATTERY_TWENTY_KW_SIZE,
        },
    )


def broadband_plan() -> tuple[dict[str, Any], ...]:
    """`CR-062` D5 — one line each on three units, at 100, 500 and 1,000 Mbps."""
    return tuple(
        {
            "asset_no": f"CPE-{1001 + n:04d}",
            "type": BROADBAND_ASSET_TYPE,
            "unit_index": unit_index,
            "service": "broadband",
            "size_class": size,
        }
        for n, (unit_index, size) in enumerate(BROADBAND_UNITS_BY_TIER)
    )


def capacity_equipment_plan() -> tuple[dict[str, Any], ...]:
    """`CR-062` D3–D5 in seeding order — one flat view so the seeder writes, the
    remover deletes and the tests assert over the SAME set.

    ⚠ **DELIBERATELY NOT PART OF `cr028_asset_plan()`, AND THE REASON IS A
    VALUATION AND NOT TIDINESS.** Every CR-028 row carries a `BR-AST-047`
    purchase cost in r10's `$118`–`$412` ballpark, and `test_cr028_seed` asserts
    that over the whole plan. **These are CUSTOMER-owned installations** — a
    utility bills a rooftop array, it does not buy it — so a purchase cost here
    would be the utility claiming it paid for a customer's panels, and would
    mean inventing nine money figures to fit a range they do not belong in. The
    column stays NULL, which is the honest answer and the same posture
    `_container_size_class` takes about a size the vocabulary cannot answer for.
    """
    return (*solar_panel_plan(), *battery_plan(), *broadband_plan(), *fire_line_plan())


def capacity_equipment_numbers() -> tuple[str, ...]:
    return tuple(entry["asset_no"] for entry in capacity_equipment_plan())


#: Every unit this block deliberately leaves EMPTY, per service — `CR-062` D7.
#: Published as data rather than left implicit so a test can assert the ruled
#: `$0.00` (`BR-MET-108`) on a NAMED unit instead of hunting for one, and so a
#: later lane that plants equipment there has to delete a line saying why it is
#: empty rather than quietly filling a gap nobody recorded.
CAPACITY_UNITS_WITH_NONE: dict[str, int] = {
    "solar": SOLAR_UNIT_WITH_NO_PANELS,
    "battery": BATTERY_UNIT_WITH_NO_BATTERY,
    "broadband": BROADBAND_UNIT_WITH_NO_LINE,
    "trash": CART_UNIT_WITH_NONE,
    # `CR-063` — fire keeps the same three-case shape as its four neighbours:
    # several on one unit (the `$84.00` pair-and-a-six), one on another, and
    # NONE here, so `BR-MET-108`'s ruled `$0.00` sits beside real fire money
    # rather than being a gap nobody noticed.
    "fire": FIRE_UNIT_WITH_NONE,
}
#: ⚠ **STORM WATER IS DELIBERATELY NOT IN THAT MAP, AND THE REASON IS THE
#: ESTATE TOTAL (`CR-062` D6).** The other four capacity services are carried by
#: EQUIPMENT, and a unit with no equipment is an ordinary state of the world. An
#: ERU assessment is a fact about the ground a unit stands on: every one of the
#: `UNIT_COUNT` units has hard surface, the estate total of **59 ERU** assigns
#: an assessment to every one of them, and leaving one out to make a demo case
#: would move `$265.50`. **The ruled `$0.00` is still proved** — on a unit whose
#: row is deleted inside the test itself, which is the same fact without
#: rewriting a demo figure to show it.
#:
#: ⚠ **THIS SAID *48 units*, *54 ERU* and *$243.00* UNTIL 2026-09-02
#: (`DEF-2368`).** It was true when it was written and the `CR-062` addendum
#: appended two seats the same day — see `STORM_WATER_ESTATE_ERU` below for the
#: measurement and for why the count is now named rather than typed.


# ── CR-062 D6 · STORM WATER'S ASSESSMENT, RECORDED ON THE UNIT ─────────────
# **PO RULING 2026-09-02, verbatim: *"In case of strom water - we have to take
# it from Unit - B ⭐ Take the size from the property, not from equipment. Storm
# water becomes the one capacity service whose quantity comes from the
# premises"*.** They chose option B of three and CORRECTED IT IN THE SAME
# SENTENCE: the option as written said *from the property*; the ruling says
# **from the UNIT**. That correction is the substance and must not be flattened
# back — a bill is for an account, an account serves a unit, and on the premises
# storm water would be the only line needing to be divided down before it could
# be charged.
#
# **WHY THERE IS NO EQUIPMENT HERE AND NOTHING IS MISSING.** Solar has panels,
# battery has batteries, broadband has modems, trash has carts, and each carries
# its size on the device. **Storm water has nothing** — an ERU measures hard
# surface and nobody installs one — so `CR-062` D6 could not be built at all and
# was filed as `DEF-2388`. This block is D6 built the ruled way: the assessment
# is a `service_characteristics` row on the UNIT (`BR-MET-108`'s shape, keyed by
# unit and service), and metering's capacity reader takes the quantity from
# there instead of from an asset.
#
# ⚠ **THE ALLOCATION IS EQUAL ACROSS A PREMISES' UNITS, decided by the session
# that took the ruling and recorded rather than asked (law 13)** — the same
# posture `MASTER_METER`'s `allocation_rule: "equal"` already takes for a
# block's water. **The apartment block's 6 ERU is 1 ERU on each of its six
# flats, NOT 6 on each**, which is the case that would otherwise bill the block
# `$162.00` a month instead of `$27.00`.
#
# **Worked, and every figure is asserted live:** a house **1 × $4.50 = $4.50**;
# the block **$27.00**; a commercial suite **4 × $4.50 = $18.00**; the estate
# **59 ERU = $265.50** a month.
#
# ⚠ **AND THE UTILITY ACTUALLY COLLECTS `$270.00`, WHICH WAS FOUND BY MEASURING
# AND NOT BY DERIVING.** `BR-RAT-101`/`BR-RAT-102` multiply every base and
# variable line on a premises OUTSIDE the city limits by **1.5** — r10's
# Residential Standard, *"Premises outside city limits multiply base and
# variable by 1.5"* — and `OUTSIDE_CITY_PREMISES_INDEXES` puts two houses there,
# so their storm-water lines read **$6.75**. **The ruled figure is the QUANTITY,
# 59 ERU**, and a surcharge multiplies the price and never the measurement; the
# live case asserts both, separately, rather than adjusting one to fit.
#
# ⚠ **`CR-062` D6's OWN TEXT SAID "57 ERU ACROSS 44 PREMISES" AND ITS ROWS ADD
# TO 54.** The missing 3 are the three newly-platted premises, which have no
# unit, no account and no bill. On this ruling that dissolves rather than
# needing a fix — a premises with no unit has nowhere to record an ERU and
# nothing to bill — so **the billable figure has always been the estate minus
# the premises with no unit**, and the CR's text is amended to say so.
#
# ⚠ **AND THAT FIGURE WAS "54 ACROSS 41" UNTIL 2026-09-02, WHEN THE ESTATE
# GREW UNDER IT (`DEF-2368`).** The `CR-062` addendum appended two seats the
# same day — `601 Quarry Hill Ct` (the municipal depot, `SW-SF`, 1 ERU, unit
# 48) and `603 Silver Creek Rd` (the industrial plant, `SW-COM-S`, 4 ERU, unit
# 49) — which is exactly `+5 ERU` and `+2 premises`. The PLAN below is derived
# and picked both up; the two totals were LITERALS and did not. Measured on
# real PostgreSQL 16.13: **43 assessed premises, 59.0000 ERU, `$265.50`** of
# assessment against the `41`/`54`/`$243.00` that stood here. **No ❄️ FROZEN
# figure moved** — `GT-17`'s `$39.50` and `$15.80` and `GT-15`'s `$40.00` and
# `$24.00` are untouched; what moved is a demo total nobody re-measured.

#: The characteristic's unit of measure, stated here so a seeder never assumes
#: one (hard rule 3). It is `BR-TEN-171`'s own unit for every storm-water size
#: class and the unit the seeded `$4.5000` price is quoted per.
STORM_WATER_UOM = "ERU"

#: **THE PROPERTY SIZE, AS ONE OF `BR-TEN-171`'s FIVE RATIFIED CODES — never a
#: number.** What each code is WORTH in ERU is the tenant's own ratified ladder
#: and is read from it at seed time, exactly as `capacity_equipment_plan`'s size
#: codes are: a figure typed here would be this fixture teaching a vocabulary
#: the product already owns, and it would drift the day the ladder moves.
STORM_WATER_SIZE_SINGLE_FAMILY = "SW-SF"  # 1 ERU
STORM_WATER_SIZE_TWO_UNIT = "SW-DUP"  # 2 ERU
STORM_WATER_SIZE_APARTMENT = "SW-APT"  # 6 ERU
STORM_WATER_SIZE_COMMERCIAL = "SW-COM-S"  # 4 ERU

#: The estate's billable total, stated so a test can assert a figure a person
#: read rather than one it recomputed from the same code it is checking. A pure
#: case re-derives it from `BR-TEN-171`'s ladder and this plan, so the two can
#: never quietly disagree.
#:
#: ⚠ **THIS IS THE ONE FIGURE HERE THAT STAYS A LITERAL, AND THE REASON IS THIS
#: MODULE'S OWN BOUNDARY (`DEF-2368`, 2026-09-02).** `STORM_WATER_ASSESSED_
#: PREMISES` below is now DERIVED, because counting the plan's rows needs
#: nothing but the plan. Totalling ERU needs to know **what each size code is
#: WORTH**, and that lives in the tenant's ratified ladder in
#: `apps/tenancy/service_size_classes` — which this module may not import: it is
#: *"a DECLARATION and nothing else: plain data, no Django import, no ORM, no
#: service call"* (module docstring), and `storm_water_size_class_for` already
#: refuses to type the ERU numbers here for the same reason (*"a figure typed
#: here would be this fixture teaching a vocabulary the product already owns"*).
#: So the independent statement is kept and the DRIFT is what gets a check:
#: `10-scripts/gates/g73_storm_water_estate.py` derives the total from the
#: ladder and this plan with no database and no Django, and fails the moment
#: this number and the estate disagree — which is `DEF-2368` itself, caught in
#: one second instead of by a suite nobody ran.
#:
#: **54 → 59 on 2026-09-02**: the `CR-062` addendum appended units 48 and 49
#: (1 ERU + 4 ERU). At the seeded `$4.5000` per ERU that is **`$265.50`** of
#: monthly assessment, and **`$270.00`** collected once `BR-RAT-101`'s
#: outside-city 1.5x lands on two houses.
STORM_WATER_ESTATE_ERU = Decimal("59")


def storm_water_size_class_for(entry: dict[str, Any]) -> str | None:
    """Which of `BR-TEN-171`'s five ratified property sizes this premises is, or
    `None` when it has no unit to record an assessment on.

    ⚠ **IT READS THE SHAPE OF THE PREMISES, NOT `premises_type` ALONE**, and
    that is not fussiness: `premises_plan()` types BOTH the 36 houses AND the 2
    duplexes as `single_family` (the duplexes are distinguished by carrying an
    `owner_manager` and two units), so a map keyed on the type would assess a
    two-unit home as 1 ERU and quietly lose `$9.00` a month across the estate.
    The unit COUNT is the fact the ladder's own names are about — *"Single-family
    home"*, *"Two-unit home"*, *"Apartment building"*.

    `SW-COM-L` (10 ERU, large commercial) is ratified and deliberately unused:
    the estate's commercial premises are a laundromat, a diner and the mill
    building, all small commercial by any reading, and inventing a mall to
    exercise a code would put a figure in the demo that nothing in the corpus
    supports.

    ⚠ **THE SENTENCE ABOVE SAID *"two commercial premises"* UNTIL 2026-09-02
    (`DEF-2368`).** `CR-062`'s addendum appended `603 Silver Creek Rd` as a
    third `commercial_building`, so this function assesses it `SW-COM-S` and it
    bills **`$18.00`** a month — measured on a seeded tenant, not reasoned.

    ⚠ **AND THE MUNICIPAL DEPOT AT `601 Quarry Hill Ct` IS ASSESSED `SW-SF`,
    WHICH IS A JUDGMENT NOBODY HAS MADE — `DEF-3400`, filed rather than
    changed.** `government_building` is neither of the two types named above, so
    it falls through to the dwelling branch and is assessed as a single-family
    home at 1 ERU / `$4.50`, while `premises_plan` types that same building's
    unit `commercial` because *"the depot is a non-dwelling building"*. Two
    statements about one building, disagreeing. Nothing bills wrongly — 1 ERU is
    a ratified size and the line is real money on a real bill — so it is
    recorded rather than corrected inside a fix for a different stale figure.
    """
    units = len(entry.get("units") or ())
    if not units:
        return None
    if entry.get("premises_type") == "commercial_building":
        return STORM_WATER_SIZE_COMMERCIAL
    if entry.get("premises_type") == "apartment_complex":
        return STORM_WATER_SIZE_APARTMENT
    return STORM_WATER_SIZE_TWO_UNIT if units == 2 else STORM_WATER_SIZE_SINGLE_FAMILY


def storm_water_assessment_plan() -> tuple[dict[str, Any], ...]:
    """`CR-062` D6 — one row per PREMISES that has a unit: the ratified size
    class it is assessed at and the units that assessment is spread across.

    **The division is the SEEDER's**, because the number being divided lives in
    the tenant's ratified ladder and not here. This publishes the two facts the
    fixture owns — WHICH property size, and WHICH units share it — so the seeder
    writes, a remover deletes and the tests assert over one set.

    `address_line` travels with each row so the seeder can find the premises the
    same way every other block in this fixture does, by address rather than by
    ordinal.
    """
    rows: list[dict[str, Any]] = []
    for entry in premises_plan():
        code = storm_water_size_class_for(entry)
        if code is None:
            continue
        rows.append(
            {
                "address_line": entry["address_line"],
                "size_class": code,
                "unit_indexes": tuple(unit["unit_index"] for unit in entry["units"]),
            }
        )
    return tuple(rows)


def storm_water_assessed_unit_indexes() -> tuple[int, ...]:
    """Every unit index the plan above assesses — all `UNIT_COUNT` of them, and a
    test asserts it is all of them rather than trusting this sentence.

    ⚠ **THIS SENTENCE SAID *"all 48"* TWICE UNTIL 2026-09-02 (`DEF-2368`).** It
    was true until `CR-062`'s addendum appended units 48 and 49; the count is
    named rather than typed now, because the number of units this estate has is
    `UNIT_COUNT`'s to state and repeating it here is a second statement that can
    only go stale.
    """
    return tuple(
        index for row in storm_water_assessment_plan() for index in row["unit_indexes"]
    )


#: **HOW MANY PREMISES THE PLAN ABOVE ASSESSES — DERIVED, NEVER TYPED
#: (`DEF-2368`, 2026-09-02).**
#:
#: It was the literal `41` (*"41 of the 44 — the three newly-platted premises
#: have no unit"*), which was true on the morning it was written and false by
#: the afternoon: the `CR-062` addendum appended two premises with units and
#: this number did not move, so a derived plan and a written figure disagreed
#: for a day with a green suite behind them.
#:
#: **A count of the plan's own rows needs nothing but the plan**, so there is no
#: reason for it to be a second statement at all — unlike `STORM_WATER_ESTATE_
#: ERU` above, which needs the ratified ladder this module may not import and is
#: therefore kept literal and gated instead. The `PREMISES_COUNT - 3` identity
#: is asserted by a test rather than written here, because *"three of them have
#: no unit"* is a fact about the premises mix and not a definition of this
#: number.
STORM_WATER_ASSESSED_PREMISES = len(storm_water_assessment_plan())


# ══════════════════════════════════════════════════════════════════════════
# CR-080 · THERMAL/HEAT ON THE ESTATE — CONNECTED TONNAGE ON THE UNIT
# ══════════════════════════════════════════════════════════════════════════
#
# **PO RULING 2026-09-07, verbatim:** *"connected tonnage - it is capacity not
# metering; i will ahve 100 tonne or 200 tonne etc"*.
#
# ⚠ **THIS BLOCK REPLACES 48 METERS, AN OPENING READ AND THREE MONTHS OF
# READINGS.** Until that day a thermal tenant was in `METERED_ESTATE_SERVICES`
# and received a `TH-5000…TH-5047` register per unit, scaled by
# `CONSUMPTION_SCALE["thermal_heat"] = 500` into about 4,500 ton-hours a month
# and priced at `$0.045` a ton-hour. All of that is withdrawn. What a thermal
# tenant gets now is a service point per unit and its connected tonnage
# recorded ON the unit — storm water's shape, for storm water's own reason:
# **nobody installs a ton.**
#
# ⚠ **IT IS STORM WATER'S SHAPE AND SOLAR'S ARITHMETIC, WHICH IS A COMBINATION
# NEITHER OF THEM HAS.** The tonnage is a UNIT fact (`connections.unit_capacity
# _key("thermal_heat")` → `"connected_capacity"`, so no device carries it) and
# it SUMS (`capacity_uom_for_service("thermal_heat")` → `"ton"`, so two
# connections on one unit add up). Trash and fire COUNT; storm water sums off
# the unit but has only ever had one assessment per unit.

#: The characteristic's unit of measure, stated here so a seeder never assumes
#: one (hard rule 3). It is `BR-TEN-171`'s own unit for every thermal size
#: class since `CR-080` and the unit the seeded `$12.5000` price is quoted per.
#:
#: ⚠ **`ton` IS THE REFRIGERATION TON (12,000 BTU/hr), NOT THE METRIC TONNE.**
#: The PO wrote *"tonne"*; the reading is recorded across `CR-080` so they can
#: correct it in one word, and if they do, this constant, the ladder in
#: `tenancy/service_size_classes.py` and the price above all move together.
THERMAL_UOM = "ton"

#: **THE CONNECTED TONNAGE EACH CUSTOMER CLASS IS SIZED AT, AS ONE OF
#: `BR-TEN-171`'s RATIFIED CODES — never a number.** What each code is WORTH in
#: tons is the tenant's own ladder and is read from it at seed time, exactly as
#: `storm_water_size_class_for`'s codes are: a figure typed here would be this
#: fixture teaching a vocabulary the product already owns, and it would drift
#: the day the ladder moves.
#:
#: ⚠ **THE PO'S OWN TWO NUMBERS ARE ON THE ESTATE BY NAME.** They said *"i will
#: ahve 100 tonne or 200 tonne etc"*; the estate's TWO commercial units are
#: connected at **100 tons** each and its government depot at **200 tons**, so
#: the demo bill a person opens shows the figures they used.
#:
#: **The whole estate is 1,025 connected tons** — 45 houses at 5, two
#: commercial at 100, the depot at 200 and the mill at 400 — which is
#: `1,025 × $12.5000` = **`$12,812.50`** a month before `BR-RAT-101`'s
#: outside-city 1.5x reaches the two houses beyond the city limits.
THERMAL_SIZE_RESIDENTIAL = "TH-T5"  # 5 ton
THERMAL_SIZE_COMMERCIAL = "TH-T100"  # 100 ton — the PO's own figure
THERMAL_SIZE_GOVERNMENT = "TH-T200"  # 200 ton — the PO's own figure
THERMAL_SIZE_INDUSTRIAL = "TH-T400"  # 400 ton

#: **THE RULED ZERO (`BR-MET-108`, PO 2026-08-25 *"Bill it as zero"*): the
#: utility looked and this unit has no chilled-water connection recorded.**
#:
#: It is the same statement `CART_UNIT_WITH_NONE` and `FIRE_UNIT_WITH_NONE`
#: make, and it exists for the same reason: a `$0.00` line standing beside real
#: numbers on a real document is what proves the zero REACHES a bill rather
#: than falling into a silence. `DEF-2388` is what it costs when nobody checks
#: — every storm-water line printed `$0.00` on a document that footed
#: perfectly, and no gate in this repo could see it.
THERMAL_UNIT_WITH_NONE = 6


def thermal_size_class_for(unit_index: int) -> str | None:
    """Which of `BR-TEN-171`'s ratified thermal capacities this unit is
    connected at, or `None` for the one unit that deliberately has none.

    **The estate's own class map decides it** — `meter_class_of` is the one
    place *"which customer class is this seat"* is written down, and asking it
    here means a unit cannot be a government building for its meter and a
    household for its chiller. That mapping already knows the government
    depot (`CASE_GOVERNMENT_ACCOUNT`), the mill (`CASE_INDUSTRIAL_ACCOUNT`) and
    the three commercial units.

    ⚠ **THE NAME SAYS `meter_class_of` AND THERMAL PLANTS NO METER.** That is
    a stale name on a function that is really *"which customer class is this
    seat"*, and renaming it would touch every metered service on a fixture two
    other lanes are editing. Recorded here rather than done.
    """
    if unit_index == THERMAL_UNIT_WITH_NONE:
        return None
    return {
        "residential": THERMAL_SIZE_RESIDENTIAL,
        "commercial": THERMAL_SIZE_COMMERCIAL,
        "government": THERMAL_SIZE_GOVERNMENT,
        "industrial": THERMAL_SIZE_INDUSTRIAL,
    }[meter_class_of(unit_index)]


def thermal_tonnage_plan() -> tuple[dict[str, Any], ...]:
    """`CR-080` — one row per unit that has a connected tonnage: the ratified
    size class it is connected at.

    One flat view so the seeder writes, a remover deletes and the tests assert
    over the SAME set — `capacity_equipment_plan`'s own reason.

    ⚠ **UNLIKE STORM WATER, NOTHING IS DIVIDED.** An ERU is assessed on a
    PREMISES and spread across its units, because hard surface belongs to the
    property. A chilled-water connection is made to a UNIT and is that unit's
    whole capacity; the apartment block's six flats each have their own
    connection rather than a sixth of one.
    """
    return tuple(
        {"unit_index": row["unit_index"], "size_class": code}
        for row in units_flat()
        for code in (thermal_size_class_for(row["unit_index"]),)
        if code is not None
    )


def thermal_connected_unit_indexes() -> tuple[int, ...]:
    """Every unit index the plan above connects — `UNIT_COUNT - 1` of them, the
    one exception being `THERMAL_UNIT_WITH_NONE`. A test asserts the arithmetic
    rather than trusting this sentence."""
    return tuple(row["unit_index"] for row in thermal_tonnage_plan())



#: The apartment block's master (r10 M-MASTER-… shape): meter_type `master`
#: (BR-AST-043's fifth entry), landing on the block's EXISTING water service
#: point — so, like the sub-meters above, it is deliberately never read and
#: adds no phantom missing-read to the July run the PO presses.
MASTER_METER: dict[str, Any] = {
    "asset_no": "M-MASTER-01",
    "type": "meter",
    "unit_index": 40,  # Apt 101 — the block's first unit (same convention as
    #   BTM_DEVICE_PLAN's hardcoded 46; the plan test cross-checks it is an
    #   apartment unit so a mix change cannot silently point it at a house)
    "service": "water",
    "uom": WATER_UOM,
    "meter_type": "master",
    "read_method": "ami",
    "allocation_rule": "equal",  # US-MET-003 §5 master reconciliation config
    "valuation": {
        "purchase_cost": "412.0000",  # r10 ballpark ceiling — a compound master
        "purchase_date": "2025-12-15",
        "supplier": "Neptune",
        "expected_life_years": 20,
        "warranty_end": "2031-01-05",
    },
}


def master_meter(service: str = "water", uom: str = WATER_UOM) -> dict[str, Any]:
    """`MASTER_METER` expressed in the tenant's own backbone service (CR-039 A3).

    Same asset number, same unit, same `master` meter type, same `equal`
    allocation rule and the same valuation — only the register changes. Called
    with no arguments it IS `MASTER_METER`, which is why that constant stays
    published for the tests and callers that already read it.
    """
    return {**MASTER_METER, "service": service, "uom": uom}


def master_sub_meter_plan(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[dict[str, Any], ...]:
    """Three NEW sub-meters parented on the MASTER (BR-AST-003), on the last
    three apartment units — r10's `Sub → M-MASTER-01` role tag needs subs whose
    parent is a master, and CR-010's six subs (parented on each unit's own
    meter) are pinned by test and stay exactly as they are.

    ⚠ **CR-039 A3 · WHAT IS COHERENT HERE AND WHAT IS STILL NOT.** Coherent
    now: the master and every sub speak the tenant's own backbone service, so a
    submetering ELECTRIC utility gets an electric master with electric subs
    behind it instead of the nothing it got before (the asset seeder skips any
    row naming a service the tenant has not enabled — that skip was correct and
    the row was wrong).

    **Still not coherent, named rather than silently reshaped:** the apartment
    block carries a per-unit meter AND a master AND two generations of subs —
    six parented on their own unit's meter (CR-010) and three on the master
    (CR-028) — so three of the six apartment units hold two sub-meters and the
    master has three children for a six-unit block. A real submetering estate
    is one master for the building with one sub per unit behind it. Re-parenting
    the CR-010 six would change what every already-seeded tenant holds and is a
    data question, not a fixture edit; it is reported to CR-039 wave A's lane
    report rather than done here.
    """
    last_three = apartment_unit_indexes()[-3:]
    return tuple(
        {
            "asset_no": f"SM-{7200 + offset + 1:04d}",
            "type": "sub_meter",
            "unit_index": index,
            "parent_asset_no": MASTER_METER["asset_no"],
            "service": service,
            "uom": uom,
            "meter_type": "sub_meter",
            "read_method": "manual",
            "valuation": {
                "purchase_cost": "156.0000",
                "purchase_date": "2026-01-05",
                "supplier": "Neptune",
                "expected_life_years": 15,
            },
        }
        for offset, index in enumerate(last_three)
    )


#: The net meter (BR-AST-010: type `net_meter` locks net_metering ON). Seeded
#: IN INVENTORY, deliberately: assigning it would mint an electric service
#: point with no read behind it, and a phantom missing-read in the July
#: ready-to-run batch deletes the PO's acceptance test (the same argument the
#: 48-not-96 amendment makes above). The detail's net line renders from the
#: FLAG; its export READS are metering's W2 half, and the lane that seeds them
#: is the lane that assigns this meter beside the PV inverter on unit 4.
NET_METER: dict[str, Any] = {
    "asset_no": "M-NET-01",
    "type": "net_meter",
    "service": "electric",
    "uom": "kWh",
    "meter_type": "ami",
    "read_method": "ami",
    "valuation": {
        "purchase_cost": "289.0000",
        "purchase_date": "2026-06-20",
        "supplier": "Itron Inc",
        "expected_life_years": 20,
        "warranty_end": "2031-06-20",
    },
}

#: The two r10 device kinds CR-010's three left out (B16 §4.3 draws five).
#: A SEPARATE constant from BTM_DEVICE_PLAN on purpose — that tuple's three
#: kinds are pinned by test_us_ten_019_sample_records and stay untouched.
#: The battery sits beside unit 4's PV inverter (a solar+storage household);
#: the comms endpoint reads an ordinary house. Non-measuring: no service, no
#: UoM (BR-AST-009).
CR028_DEVICE_PLAN: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "COM-0001",
        "type": "comms",
        "unit_index": 10,
        "note": "communication endpoint (device_types: the tenancy lookup's comms row)",
        "valuation": {
            "purchase_cost": "132.0000",
            "purchase_date": "2026-02-10",
            "supplier": "Itron Inc",
            "expected_life_years": 10,
        },
    },
    {
        "asset_no": "BAT-0001",
        "type": "battery",
        "unit_index": 4,  # beside PV-0001 — the solar household stores what it makes
        "note": "customer battery storage, paired with PV-0001's household",
        "valuation": {
            "purchase_cost": "398.0000",
            "purchase_date": "2026-03-02",
            "supplier": "Itron Inc",
            "expected_life_years": 12,
        },
    },
)

#: Unassigned stock for the Inventory tab (§10-D5: counts & costs only).
#: Created with NO unit, so BR-AST-011's leave-in-inventory path lands them
#: status `inventory` / behavior `available`. W-5100 is the AGED one — bought
#: 2025-03-10, more than 12 months before the fixture's mid-August clock — and
#: carries r10's own $164.00 purchase cost. Measuring spares still declare
#: service + UoM (BR-AST-009 holds in the yard too).
INVENTORY_PLAN: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "W-5100",
        "type": "meter",
        "service": "water",
        "uom": WATER_UOM,
        "meter_type": "walk_by",
        "read_method": "walk_by",
        "valuation": {
            "purchase_cost": "164.0000",  # r10 AST-02's own worked purchase cost
            "purchase_date": "2025-03-10",  # AGED: > 12 months before 2026-08-14
            "supplier": "Badger Meter",
            "expected_life_years": 15,
            "warranty_end": "2030-03-10",
        },
    },
    {
        "asset_no": "W-5101",
        "type": "meter",
        "service": "water",
        "uom": WATER_UOM,
        "meter_type": "walk_by",
        "read_method": "walk_by",
        "valuation": {
            "purchase_cost": "171.0000",
            "purchase_date": "2026-07-15",
            "supplier": "Neptune",
            "expected_life_years": 15,
        },
    },
    {
        "asset_no": "BF-0002",
        "type": "backflow",
        "valuation": {
            "purchase_cost": "247.0000",
            "purchase_date": "2026-06-02",
            "supplier": "Watts Water",
            "expected_life_years": 12,
        },
    },
    {
        "asset_no": "CART-0099",
        "type": TRASH_CART_TYPE,
        "valuation": {
            "purchase_cost": "118.0000",
            "purchase_date": "2026-05-20",
            "supplier": "Watts Water",
            "expected_life_years": 10,
        },
    },
)


def inventory_plan(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[dict[str, Any], ...]:
    """`INVENTORY_PLAN` with its two MEASURING spares expressed in the tenant's
    backbone service (CR-039 A1).

    The backflow preventer and the spare cart are non-measuring and carry no
    service at all (BR-AST-009), so they are unchanged for every tenant. The two
    spare meters take the backbone's prefix and the backbone's UoM — a yard full
    of water meters is not stock a gas utility can fit, and the asset seeder
    skips any measuring row whose service the tenant has not enabled, so before
    this the Inventory tab was empty on every non-water tenant.
    """
    prefix = SERVICE_METER_PREFIX.get(service, service[:2].upper())
    out: list[dict[str, Any]] = []
    for entry in INVENTORY_PLAN:
        if not entry.get("service"):
            out.append(entry)
            continue
        number = entry["asset_no"].split("-", 1)[1]
        out.append({**entry, "asset_no": f"{prefix}-{number}", "service": service, "uom": uom})
    return tuple(out)


# ── THE METERS THE NIGHTLY RULE FIRES ON (CR-070 wave M · M5) ───────────────
#: `M5`'s fixture line, verbatim: *"AST-04412 and two more meters past
#: certification life; the drawing's seven rules, six On"*. These are the three
#: SUBJECTS — the rules themselves are `apps/work/sample_data.py`'s.
#:
#: ⚠ **THE NUMBERS ARE LITERAL AND ARE NOT PREFIXED BY SERVICE.** Every other
#: plan here renames its meters through `SERVICE_METER_PREFIX` so a gas utility
#: gets `G-5100` rather than `W-5100`. These three do not, because `AST-04412`
#: is the number `Work-028`'s drawing prints in its kicker, the number the
#: execution plan's `M5`/`M7` name, and the number
#: `10-scripts/render-checks/cr070-m-rules-and-doors.mjs` types into the asset
#: search box. A prefixed number would be tidier and would break the one script
#: this fixture exists to let somebody run.
#:
#: ⚠ **THEY ARE SEEDED INTO INVENTORY — NO `unit_index`, SO NO SERVICE POINT.**
#: `BR-AST-011`'s leave-in-inventory path. The drawing puts `AST-04412` at
#: *221 Oak Ave · Unit 3*, and putting it there would mean a SECOND live meter
#: on a service point that already carries one: `connection_size_for` answers
#: `None` the moment two assets on one point record different sizes (decision
#: log 2026-08-27), the July and August reads would gain a meter nobody walks,
#: and the demo tenant's billing would change to make a work-order fixture
#: prettier. The rule does not care where the meter sits — `assets_past_
#: certification` reads dates and status, never a service point — and neither
#: does the Assets door. **The divergence from the drawing is the LOCATION and
#: it is deliberate; the certification arithmetic is exactly as drawn.**
#:
#: ⚠ **PAST-DUE IS ARITHMETIC, NOT A STORED DATE.** No seeded asset carries an
#: explicit `certification_due`, so `assets_seam.assets_past_certification`
#: derives it as `purchase_date + expected_life_years` — which is why each row
#: below carries a valuation and why the dates are old. `AST-04412` is bought
#: **15 Mar 2021** with a **5**-year life, so its certification ran out on
#: **15 Mar 2026** — the drawing's own *"installed Mar 2021 · Certification
#: life ends Mar 2026"*, to the month.
#:
#: ⚠ **A REPLAY MUST NOT AGE THEM FURTHER AND CANNOT**: the dates are constants,
#: not offsets from `today()`, so the third sweep of a tenant seeded in 2027
#: still finds exactly these three and not a set that grew while nobody looked.
AGED_METER_PLAN: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "AST-04412",
        "type": "meter",
        "meter_type": "ami",
        "read_method": "ami",
        "valuation": {
            "purchase_cost": "182.0000",
            "purchase_date": "2021-03-15",
            "supplier": "Badger Meter",
            "expected_life_years": 5,
        },
    },
    {
        "asset_no": "AST-04413",
        "type": "meter",
        "meter_type": "amr",
        "read_method": "amr",
        "valuation": {
            "purchase_cost": "176.0000",
            "purchase_date": "2020-11-02",
            "supplier": "Neptune",
            "expected_life_years": 5,
        },
    },
    {
        "asset_no": "AST-04414",
        "type": "meter",
        "meter_type": "walk_by",
        "read_method": "walk_by",
        "valuation": {
            "purchase_cost": "164.0000",
            "purchase_date": "2019-06-20",
            "supplier": "Badger Meter",
            "expected_life_years": 6,
        },
    },
)


def aged_meter_plan(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[dict[str, Any], ...]:
    """`AGED_METER_PLAN` expressed in the tenant's backbone service.

    The SERVICE and the UoM are parameterised and the asset NUMBERS are not —
    see the constant's own note. A measuring asset must declare both
    (`BR-AST-009` / CLAUDE.md rule 3), and the asset seeder skips any measuring
    row whose service the tenant has not enabled (`DEF-2397`), so naming water
    here would leave a gas utility's Rules screen with a rule and no subject.
    """
    return tuple({**entry, "service": service, "uom": uom} for entry in AGED_METER_PLAN)


def aged_meter_numbers() -> tuple[str, ...]:
    """The three numbers, for the seeder's idempotence check and the remover."""
    return tuple(entry["asset_no"] for entry in AGED_METER_PLAN)


def cr028_asset_plan(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[dict[str, Any], ...]:
    """Every CR-028 asset in seeding order, each carrying its valuation —
    one flat view so the seeder tags, the tests assert and the remover deletes
    the SAME set without three places re-deriving it.

    ⚠ **`NET_METER` KEEPS ITS OWN SERVICE AND IS NOT PARAMETERISED.** It is an
    ELECTRIC net meter by definition (BR-AST-010 — the type locks net metering
    on, and net metering is an electricity arrangement), and it is seeded IN
    INVENTORY precisely so it needs no service point. On a tenant that does not
    sell electricity the asset seeder skips it BY NAME, which is the correct
    answer and not a gap: a gas utility has no net meter.
    """
    return (
        *trash_cart_plan(),
        master_meter(service, uom),
        *master_sub_meter_plan(service, uom),
        NET_METER,
        *CR028_DEVICE_PLAN,
        *inventory_plan(service, uom),
    )


def cr028_asset_numbers(
    service: str = "water", uom: str = WATER_UOM
) -> tuple[str, ...]:
    return tuple(entry["asset_no"] for entry in cr028_asset_plan(service, uom))


# ── The live payment plan (spec §4 case 6 — CR-010 Part-10.4 amendment 3) ────
# PO verbatim 2026-08-17: *"you did not cover outstanding repcrds, payment
# plans"*. CASE_PAYMENT_PLAN stops being a narrative and becomes ROWS: the
# account's June bill is left wholly unpaid (payments' `_share_for`), the S24
# wizard path spreads it, and two instalments are already paid so the plan is
# genuinely MID-SCHEDULE with the next one due against the mid-August "today".
#
# EVERY DOLLAR DERIVES FROM THE JUNE BILL THE ENGINE ISSUED — nothing here is
# an amount. The schedule arithmetic is BR-CUS-043's, computed by
# `apps/customers/payment_plan.build_schedule` (GT-47 ❄️ owns it), never
# duplicated in a seeder. The SHAPE below (4 biweekly instalments, 20% down,
# 2 paid) is fixture authorship, not signed law — flagged in
# 12-governance/09-human-review-ledger.md for the PO to ratify or amend.
PAYMENT_PLAN: dict[str, Any] = {
    "unit_index": CASE_PAYMENT_PLAN,
    "proposed_on": date(2026, 7, 10),  # after the June bill of 2 July
    "signed_on": date(2026, 7, 12),  # activation = the customer's e-signature
    "first_due": date(2026, 7, 20),
    "cadence": "biweekly",  # dues: Jul 20 · Aug 3 · Aug 17 · Aug 31
    "installments": 4,
    "paid_installments": 2,  # Jul 20 + Aug 3, both posted ON their due date
    "down_payment_share": Decimal("0.20"),  # of the spread balance, 2dp
}


# ── The refund and the overcharge correction (spec §4 cases 14 + 15) ────────
# CR-040 wave D, PO 2026-08-27: *"you need credit and refunds cases, overcharge
# cases, creit cases"*.
#
# ⚠ **NOT ONE FIGURE HERE IS AN AMOUNT OF MONEY, AND THAT IS THE POINT.**
# The refund is whatever credit the ALLOCATOR left on the account after the
# overpayment (`selectors.account_credit_position`), and the correction's delta
# is whatever the PRICING ENGINE makes of the corrected read. A fixture that
# typed "$41.20" here would be a number nobody computed riding into a demo bill
# looking as though somebody had chosen it — the failure OQ-004's closure names
# ("no silent conversion") one field along. What IS authored below is the
# SHAPE: which account, which dates, how much the meter was over-read by.
#
# ⚠ **THE DATES SIT BETWEEN THE TWO BILL RUNS ON PURPOSE (task D14).** June's
# bill issues 2 July and July's issues 2 August, so both events are dated in
# between and both are WRITTEN in between — a refund written after both runs is
# a row, a refund written between them is a history, and an overcharge
# correction cannot exist before run 1 at all because it corrects a bill that
# has issued.
def first_billed_period() -> dict[str, Any]:
    """The period bill run 1 covers — the one the refund and the overcharge are
    both written against."""
    return min(
        (period for period in PERIODS if period["billed"]), key=lambda p: p["end"]
    )


def between_the_bill_runs(days_after_run_1: int) -> date:
    """A day inside the window between bill run 1 and bill run 2.

    ⚠ **THE DATES BELOW WERE LITERAL `date(2026, 7, …)` UNTIL 2026-09-25
    (`DEF-LED-6640`), AND THE COMMENT ABOVE THEM STATED THE INVARIANT THEY
    BROKE THE MOMENT THE CALENDAR TRAVELLED**: *"THE DATES SIT BETWEEN THE TWO
    BILL RUNS ON PURPOSE (task D14) … an overcharge correction cannot exist
    before run 1 at all because it corrects a bill that has issued."*

    **It was measured, not reasoned about.** On the first tenant seeded with a
    travelling calendar (offset +1, 2026-09-25) run 1 issued **2026-08-02** and
    the rebill was still stamped **2026-07-17** — a correction dated **16 days
    before the bill it corrects**, on a money path. Nothing went red: the
    corrections engine does not compare the two, every count was right, the
    trial balance footed, and the only reason it was seen at all is that a
    readback printed `first_issued` per period and one row did not fit.

    ⚠ **THAT IS THE GENERAL HAZARD OF A TRAVELLING CALENDAR AND IT IS WORTH
    MORE THAN THIS FUNCTION:** shifting the periods moves every date that is
    DERIVED from them and leaves every date that is TYPED exactly where it was,
    so a fixture with a mix of both does not break — it goes QUIETLY
    INCONSISTENT. Every literal date in this file was read for this reason; the
    ones left are the ones that genuinely do not belong to the accounting
    calendar (`GT16_CUTOVER_ON` is a ❄️ frozen GT-16 figure and a historical
    import's book date, and the asset purchase dates are deliberately old).

    The window is the ~31 days from run 1 to run 2 and is that wide in every
    month, because run 1 is the 2nd of M-1 and run 2 the 2nd of M.
    """
    first_billed = min(
        (period for period in PERIODS if period["billed"]), key=lambda p: p["end"]
    )
    return first_billed["bill_on"] + timedelta(days=days_after_run_1)


REFUND: dict[str, Any] = {
    "unit_index": CASE_REFUND,
    "overpay_share": Decimal("1.40"),  # of the June bill — the surplus is the credit
    "requested_on": between_the_bill_runs(18),
    "approved_on": between_the_bill_runs(19),
    "issued_on": between_the_bill_runs(21),
    "cleared_on": between_the_bill_runs(27),
    "method": "check",  # US-PAY-011 §5: a cheque refund needs its cheque number
    "reference": "10241",  # PE-9's own cheque number, so the demo matches the worked example
    "reason": "Customer overpaid the June bill and asked for the surplus back",
}

#: How far the June meter was over-read on the overcharge account. It is a
#: QUANTITY, in the meter's own unit, not money (hard rule 3) — the engine
#: prices it, and what the bill moves by is the engine's answer.
#:
#: ⚠ **THE SECOND CYCLE THEN BILLS MORE, AND THAT IS CORRECT ARITHMETIC RATHER
#: THAN A SIDE EFFECT.** A register read too high in June is corrected DOWN,
#: which credits June — and July's consumption is measured FROM that corrected
#: figure, so July's delta grows by exactly the same quantity. The customer is
#: made whole across the two bills, which is what a real re-read does and what a
#: demo of a correction ought to show.
#: `CR-059` CS-12 · task 74 — **ONE CHEQUE THAT PAYS THREE PROPERTIES.**
#:
#: The change request's own scenario is *"Cheque #8842 for $520.00, 8 August:
#: `ACC-1042` 12 Oak St Unit 1 owes 184.20 · `ACC-1043` Unit 2 owes 156.90 ·
#: `ACC-1044` 40 Cedar Ave owes 178.90"*, and what goes wrong today is that it
#: *"fans into three independent recordings and re-joins only at the bank"* —
#: three receipts printed for one cheque, with nothing checking the split.
#:
#: ⚠ **THE THREE AMOUNTS AND THE CHEQUE TOTAL ARE DELIBERATELY NOT HERE.** They
#: are whatever this estate's own June bills came to, read back from the product
#: at seed time — the same discipline `REFUND` keeps one entry down (*"THE AMOUNT
#: IS THE ALLOCATOR'S, NOT THIS FILE'S"*). A typed 520.00 would drift the day a
#: tariff moved and would then fail deep inside the tender's own sum check,
#: which is the one rule the seeded cheque exists to demonstrate.
#:
#: ⚠ **THE LANDLORD'S THREE JUNE BILLS ARE LEFT UNPAID BY THE ORDINARY
#: COLLECTION** (`apps/payments/sample_data._share_for`) so that this cheque has
#: something to settle. Without that they are paid at 100% like every other
#: ordinary unit and the demo's one multi-property tender would be a cheque for
#: nothing.
MULTI_PROPERTY_TENDER: dict[str, Any] = {
    "unit_indexes": CASE_LANDLORD,
    "paid_on": BUSY_DAY,  # spec §5's "one busy day (8 August) with mixed methods"
    "method": "check",
    "reference": "8842",  # CS-12's own cheque number, so the demo matches the spec
}

OVERCHARGE: dict[str, Any] = {
    "unit_index": CASE_OVERCHARGE,
    "over_read_by": Decimal("4"),  # the June register was this much too high
    "reason_code": "wrong_read",  # apps/billing/correction_reasons — class R, restatement
    "opened_on": between_the_bill_runs(13),
    "approved_on": between_the_bill_runs(14),
    "executed_on": between_the_bill_runs(15),
    # ⚠ **COMPOSED, NOT TYPED (`DEF-LED-6640`).** It read *"The June reading …
    # re-read on 14 July"*, and this string is STORED — it is the correction
    # case's `note` and the read correction's `reason`, so on a tenant seeded in
    # November a clerk would open a correction against an October bill and read
    # the word *June*. A month name in stored prose is a date like any other.
    "note": (
        f"The {first_billed_period()['start']:%B} reading was transcribed from the "
        f"wrong dial and the meter was re-read on "
        f"{between_the_bill_runs(12):%-d %B}"
    ),
}


# ── Bank statement (spec §5) ────────────────────────────────────────────────
#: Three lines with three different fates. The whole reason this exists is the
#: MIDDLE one: a clerk must have a day that does NOT tie, and must have to
#: explain the difference against the bank-fee account. A statement where
#: everything matches teaches nothing.
BANK_STATEMENT_NOTES: tuple[dict[str, str], ...] = (
    {
        "kind": "cheque_batch",
        "expectation": "ties exactly to the 8 August cheque deposit batch",
    },
    {
        "kind": "card_settlement",
        "expectation": (
            "does NOT tie — the processor kept a fee, so the bank credit is short of "
            "the card takings and the clerk explains the difference against the "
            "bank-fee account"
        ),
    },
    {
        "kind": "interest",
        "expectation": "belongs to no customer — bank interest, matched to nothing",
    },
)


# ══════════════════════════════════════════════════════════════════════════
# CR-030 · THE DEMO ESTATE — W2 task 2.10 · W3 task 3.12 · W4 task 4.14
# ══════════════════════════════════════════════════════════════════════════
#
# PO AUTHORISATION, 2026-08-24, verbatim: ***"so add them"*** — given after the
# lane measured the gap and priced it: B18 §5.1.5 asks for EIGHT account shapes
# and seven of them need a UNIT SEAT the fixture does not have (48 units, 48
# occupying accounts, BR-CUS-017 allows one each, ever), the design's own
# addresses appear in NO fixture plan, and the `+3` service-chip overflow needs
# EIGHT services on ONE unit.
#
# ⚠ **EVERYTHING HERE IS ADDITIVE, EXACTLY AS THE CR-028 SECTION ABOVE IS.**
# `premises_plan()` / `units_flat()` / `account_plan()` are UNTOUCHED and still
# describe 44 premises, 48 units and 48 accounts — the figures
# `tests/test_us_ten_019_sample_records.py` pins and the figures every count in
# this file's docstring states. The CR-030 estate is a SECOND plan, seeded after
# the first, and no existing row is renumbered, re-addressed or re-priced.
#
# ⚠ **AND IT JOINS NO ROUTE, WHICH IS THE OTHER HALF OF "ADDITIVE".** The
# seeder plants these premises AFTER `_ensure_cycle_and_route`, so the estate
# carries service points (the chips are real) and appears in NO bill run — the
# PO's READY-TO-RUN July batch keeps exactly the 48 rows it had, and no phantom
# missing-read is added to the month they are going to press. That is the
# cutover seat's own argument (`apps/metering/sample_data.CUTOVER_UNIT_NO`)
# applied to twelve more units.
#
# WHERE EVERY NAME, NUMBER AND FIGURE COMES FROM
# ------------------------------------------------
# [D] B18 §5.1.5 (the eight shapes) · §5.2.4 (A-10432's nine tabs) · §5.3.10
#     (the eight requests) · §6.6 (the estate table and its THREE cross-tab
#     consistency contracts) · B19 §12.1/§12.3 (the same eight requests, drawn
#     again, with their ages and what each is waiting on).
# Where the design draws a name or an amount, it is copied. Where it draws a
# SHAPE and no identity — the `Vacation hold` row is the only one — the fixture
# names it and says so at the row.
#
# ⚠ **THE ONE FIXTURE SLIP B18 ITSELF RECORDS, DECIDED HERE.** B18 §10 item 4:
# *"`A-11780` is `Delgado, Pilar` on Move-outs and `Whitfield, Dana` on
# Disconnects — the same account number, two customers. A fixture slip; the seed
# must pick one."* **This seed picks `Delgado, Pilar`**, because `Dana Whitfield`
# is the demo tenant's own OWNER USER (`seed_demo.BRAZOS_BEND.owner`) and a
# customer sharing the operator's name teaches a reader that the two are
# connected. Nothing else follows from the choice; the account number, the
# $318.60 and the tier-1 reminder are unchanged.
#
# ⚠ **THE REQUEST NUMBERS ARE ALLOCATED, NOT CHOSEN, AND THEY WILL NOT BE THE
# DRAWN ONES.** B18 §5.3.10 draws `SR-26-0039 … SR-26-0048`; BR-CUS-093 numbers
# a request AT CREATION from the tenant's own `service_request` series, which on
# a fresh tenant starts at 0001. Seeding the drawn numbers would mean either
# writing `request_no` behind the allocator's back or burning 38 numbers on
# phantom drafts, and consequence (a) of that ruling — *"gaps are normal and
# must not be treated as loss"* — is about ABANDONED drafts, not manufactured
# ones. So the eight are created OLDEST FIRST, which reproduces the drawn ORDER
# and the drawn AGE column, and the numbers come out `SR-26-0001…0008`.
# **REPORTED, not worked around**: the cross-tab wiring below travels by
# `CR030_SR_KEY`, never by the printed number.

#: The estate's own unit-number band. `SCW-U-001…048` are the fixture units and
#: `SCW-U-101` is the ❄️ GT-16 cutover seat, so the estate starts at 201 and no
#: seeder has to know that to stay out of the way.
CR030_UNIT_PREFIX = "SCW-U-2"

#: ⚠ **THE `+3` OVERFLOW NEEDS EIGHT SERVICES ON ONE UNIT** — B18 TC-ACC-4, as
#: CORRECTED on 2026-08-24: *"this row said an account with 6 services, and
#: 6 − 5 = 1, not 3 — the `[shot]`'s `+3` needs EIGHT. The overflow chip renders
#: the REMAINDER, so the fixture is what was wrong, not the chip."*
#:
#: These are CLAUDE.md's ten in seed order, first eight. A tenant that has not
#: ENABLED a service cannot have a service point for it (BR-MET-003, BR-RAT-024)
#: and the seeder may not enable one — that is tenancy's own service and a
#: cross-module write from a metering seeder is forbidden (B2 §2). So the
#: seeder takes the INTERSECTION with what the tenant has enabled and NAMES the
#: rest, in the BR-TEN-060 posture every other block here uses: an unloaded
#: thing is a named line, never a silent skip.
#:
#: **On a tenant with fewer than eight enabled, the chip row is correct and the
#: `+3` does not appear** — which is the truth about that tenant, not a fixture
#: failure. Enabling them is one visit to Settings → Services, or one edit to
#: `seed_demo.BRAZOS_BEND["services"]`.
CR030_OVERFLOW_SERVICES: tuple[str, ...] = (
    "electric",
    "water",
    "gas",
    "sewer",
    "trash",
    "storm_water",
    "solar",
    "broadband",
)

#: A-10432's own two, and the ONLY two its `[shot]` header draws:
#: `▪ ELECTRIC · M-4021` `▪ WATER · M-4022` (B18 §5.2.1).
CR030_A10432_SERVICES: tuple[str, ...] = ("electric", "water")


def cr030_premises_plan() -> tuple[dict[str, Any], ...]:
    """The estate's premises and the units on them — the SEATS B18 §5.1.5 needs.

    Same shape as `premises_plan()` so `apps/metering/sample_data.py` can walk
    one loop over both, with ONE addition: a unit declares the SERVICES it
    takes, because this estate is deliberately not uniform (A-10432 is an
    electric+water house; the Ridge Property common unit takes everything the
    tenant sells; `3450 Oak Ridge Dr` is served and EMPTY).
    """
    return CR030_PREMISES


CR030_PREMISES: tuple[dict[str, Any], ...] = (
    {
        # [D] B18 §5.2.1 — *"1408 Elm Street · Unit A · Austin, TX 78704 ·
        # Since Feb 2024"*. THE account every screenshot uses.
        "address_line": "1408 Elm Street",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit A",
                "unit_no": "SCW-U-201",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # [D] B18 §5.7.2 — `A-11780 · Delgado, Pilar · 220 Sable Court`.
        "address_line": "220 Sable Court",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "SCW-U-202",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # [D] B18 §5.7.2 / §6.6(c) — `A-11455 · Park, Jenna · 901 Hillside Ave`,
        # whose $542.10 is the Accounts `60+ past` balance AND the transfer's
        # *arrear follows* figure. ONE figure, two tabs.
        "address_line": "901 Hillside Ave",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "SCW-U-203",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # [D] B18 §5.8.2 / §6.6(b) — `A-11340 · Northwind Mfg. · 77 Industrial
        # Way · $8,240.00 · TIER 3`, the `Marked disconnect` row, and the one
        # figure that has to agree across Accounts, Move-outs and Disconnects.
        "address_line": "77 Industrial Way",
        "premises_type": "commercial_building",
        "owner_manager": "Northwind Mfg.",
        "status": "active",
        "units": (
            {
                "label": "Suite 1",
                "unit_no": "SCW-U-204",
                "unit_type": "commercial",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # [D] B18 §5.5.2 — `88 Pine Vista`, and it carries TWO of the eight
        # requests at once: `SR-26-0045 · Kwan, Michael · Move-in · Approved`
        # and `SR-26-0046 · Thompson, R. · Move-out · Submitted`. Two units, so
        # both are lawful at one address (BR-CUS-017 is per UNIT): Thompson
        # holds unit 1 and is moving out; Kwan's approved move-in has produced
        # `A-12048`, PENDING ACTIVATION, on unit 2.
        "address_line": "88 Pine Vista",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "SCW-U-205",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
            {
                "label": "Unit 2",
                "unit_no": "SCW-U-206",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # [D] B19 §12.2 — `SR-26-0039 · Osei, Grace · 3450 Oak Ridge Dr`, whose
        # header sentence IS this premises' state: *"3450 Oak Ridge Dr —
        # served, and the unit is vacant"*.
        #
        # ⚠ **IT MUST HAVE SERVICE POINTS AND NO ACCOUNT.** That pair is what
        # `service_request_service._evidence_for` reads to produce
        # `served_vacant`, and `served_vacant` is what badges `Move-in` as
        # *Fits the evidence* on the decision panel. A premises with no service
        # point would resolve `no_premise` and the whole drawn decision would
        # read differently.
        "address_line": "3450 Oak Ridge Dr",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "SCW-U-207",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
                "leave_vacant": True,
            },
        ),
    },
    {
        # [D] B18 §5.1.2 (`Ridge Coffee Co.` at `500 Main · 200`, carrying the
        # `4 accounts` sub-link) · §5.3.10 (`SR-26-0043 · Ridge Property LLC ·
        # 500 Main St · 25 units`) · §5.3.10 again (`SR-26-0048 · DISCONNECT ·
        # Ridge Coffee Co. · 500 Main · 200`).
        #
        # ⚠ **25 UNITS ARE NOT SEEDED AND MUST NOT BE.** The 25 are the
        # `SR-26-0043` NEW CONNECTION's future — `CON-26-0117` builds them (W6,
        # not built) and B18 §6.6 puts the connection's own fixture in the
        # Connections tab. Seeding them here would show a request `In
        # fulfilment` for units that already exist, which is the one thing that
        # request is not. Five units: the common-area unit the `+3` overflow
        # needs, and the four Ridge Coffee Co. holds.
        "address_line": "500 Main St",
        "premises_type": "commercial_building",
        "owner_manager": "Ridge Property LLC",
        "status": "active",
        "units": (
            {
                "label": "Unit 100",
                "unit_no": "SCW-U-208",
                "unit_type": "commercial",
                # THE `+3` OVERFLOW SEAT — see CR030_OVERFLOW_SERVICES.
                "services": CR030_OVERFLOW_SERVICES,
            },
            {
                "label": "Unit 200",
                "unit_no": "SCW-U-209",
                "unit_type": "commercial",
                "services": CR030_A10432_SERVICES,
            },
            {
                "label": "Unit 205",
                "unit_no": "SCW-U-210",
                "unit_type": "commercial",
                "services": CR030_A10432_SERVICES,
            },
            {
                "label": "Unit 210",
                "unit_no": "SCW-U-211",
                "unit_type": "commercial",
                "services": CR030_A10432_SERVICES,
            },
            {
                "label": "Unit 215",
                "unit_no": "SCW-U-212",
                "unit_type": "commercial",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
    {
        # ⚠ **THE ONE ROW B18 DRAWS AS A SHAPE AND NEVER NAMES.** §5.1.5 asks
        # for a `Vacation hold` account and no `[shot]` anywhere gives it a
        # number, a customer or an address. The fixture names it — and says so
        # here rather than letting a later reader assume it was copied from a
        # screenshot like its seven neighbours.
        "address_line": "61 Larkspur Way",
        "premises_type": "single_family",
        "owner_manager": None,
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "SCW-U-213",
                "unit_type": "residential",
                "services": CR030_A10432_SERVICES,
            },
        ),
    },
)


def cr030_units_flat() -> tuple[dict[str, Any], ...]:
    """Every estate unit in seeding order, each carrying its premises address."""
    out: list[dict[str, Any]] = []
    for premises in CR030_PREMISES:
        for unit in premises["units"]:
            out.append({**unit, "address_line": premises["address_line"]})
    return tuple(out)


# ── DEF-709 · THE ESTATE'S ONE COMMON AREA, AND THE MASTER ACCOUNT IT ANCHORS ─
#
# **BR-MET-116 (PO 2026-08-25, closing OQ-373), verbatim:** *"it will be master
# acocunt ; unit will be all vacant right now, if there is common area you can
# add that in premises"* — and the same rule states the manifest it produces:
# *"the drawn manifest's `Units 26` = 25 apartments + 1 common area"*. The 25
# apartments are `W6_SEATS`' own (`SCW-U-325…349`); **this is the 26th**, and
# until DEF-709 no seeder anywhere wrote it, so `is_common_area` was FALSE on
# every one of the demo's units and `BR-CUS-068`'s only door —
# `create_master_account`, which anchors on a common area — could not be
# opened. The feature was built, wired and invisible.
#
# WHY THIS UNIT AND NOT `1408 Elm`'s TWO. BR-CUS-068 and BR-MET-101 work their
# figures at *1408 Elm — 3 units + 2 common areas, $41.20 + $28.40 = $69.60*.
# The estate's `1408 Elm Street` is a **single-family house with one unit**
# (`SCW-U-201`), the seat of `A-10432` — the account every B18 `[shot]` draws.
# Seeding that worked case would mean re-shaping the demo's most-photographed
# premises into a three-flat block and inventing two occupants; the $69.60
# already comes out of the product end to end in
# `tests/test_br_cus_068_master_bill.py`, so it buys no proof either.
# **BR-CUS-083's worked case is already HERE**: `SR-26-0043` → `CON-26-0117`,
# `500 Main St`, 25 units, **$14,390.00**, whose payer that rule makes *"the
# developer, via a master account"* — and `Ridge Property LLC` is already this
# premises' `owner_manager`, which is the payer `create_master_account` picks up
# on its own. One unit is the whole of what was missing.
#
# ⚠ **IT IS DELIBERATELY NOT IN `W6_SEATS['units']`.** `_w6_units_for` reads
# that tuple, and B18 §5.4.8's tile draws `UNITS 25`; a 26th entry there is how
# the drawn 25 silently becomes 26.
#
# ⚠ **AND ITS NUMBER IS `SCW-U-324`, NOT THE `SCW-U-350` A READER WILL EXPECT.**
# The build's twenty-five run `SCW-U-325…349`, so the 26th "should" be 350 —
# **350 is already `18 Marten Row`, the first of `W7_SEATS`' twelve disconnect
# seats** (and `A-10650 · Iversen, Britt` stands on it). 324 is the free slot
# immediately BELOW the build's block, which keeps the common area next to the
# twenty-five it belongs to without renumbering a seat another lane already
# drew an account on.
CR030_COMMON_AREA_ADDRESS = "500 Main St"
CR030_COMMON_AREA_UNIT_NO = "SCW-U-324"
CR030_COMMON_AREA_LABEL = "Common area"

#: The common area's own services. BR-MET-101 names exactly two shared supplies
#: — *hallway lighting* (electric) and *shared irrigation* (water) — and those
#: are `CR030_A10432_SERVICES`, so this borrows the estate's existing pair
#: rather than minting a second list that means the same thing. Intersected with
#: what the tenant has ENABLED by the seeder (BR-MET-003), like every other
#: estate unit.
CR030_COMMON_AREA_SERVICES: tuple[str, ...] = CR030_A10432_SERVICES

#: ⛔ **THE ESTATE OWNER'S TAX ID — `BR-CUS-1024`, PO 2026-09-01.** Verbatim:
#: *"Without identifier we cannot create Customer ID or master account ot
#: regular account"*. The estate's master account is the DEVELOPER's account at
#: `500 Main St` and its payer is the premises' free-text `owner_manager`,
#: *Ridge Property LLC* — **a NAME and not an identity**, which is precisely the
#: case that ruling closed. Without one identifier the seed's master account is
#: refused, `DEF-709`'s eleven cases lose their fixture, and every demo tenant
#: silently loses the `Master` pill on its Accounts list.
#:
#: **A company is identified by its Tax ID and by nothing else** (`BR-CUS-1022`),
#: so that is what the estate's owner carries. It is a FIXTURE value in an
#: obviously-reserved range — `00-` is not issued — because a demo utility must
#: model a LAWFUL account and must not model a real business's tax number.
CR030_COMMON_AREA_OWNER_TAX_ID = "00-1000324"


# ══════════════════════════════════════════════════════════════════════════
# `DEF-MET-6302` — THE OTHER OWNERS' ACCOUNTS (PO 2026-09-23)
# ══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim: ***"attach master accounts to the sample data"***, after
# creating a master account by hand, linking it to a premises, and finding the
# Premises list's owner column **empty on every row**. It was empty honestly:
# measured on a seeded `brazosbend` clone, **79 premises and 0 of them naming a
# master account** — `premises.master_account_id` had never been written by any
# seeder in the product's history.
#
# ⛔ **NOT EVERY ADDRESS GETS ONE, AND THAT IS THE INSTRUCTION RATHER THAN A
# SHORTCUT.** PO, same instruction: *"a demo where all 80 properties have an
# identical master account teaches a clerk nothing and hides the cases that
# matter"*. So the estate demonstrates the feature where it is REAL — a
# landlord, a developer, a property company — and leaves the owner-occupied
# street alone, which is what a real utility's premises list looks like.

#: ⛔ **THE THREE REMAINING OWNERS' TAX IDS — `BR-CUS-1024`, the same ruling and
#: the same reserved range as `CR030_COMMON_AREA_OWNER_TAX_ID` one screen up.**
#: PO 2026-09-01: *"Without identifier we cannot create Customer ID or master
#: account ot regular account"*. A company is identified by its Tax ID and by
#: nothing else (`BR-CUS-1022`), so each owner that receives an account carries
#: one, and every value is in the **`00-` prefix, which is not issued** — a demo
#: utility models a lawful account and never a real business's tax number.
#:
#: ⚠ **`Silver Creek Duplex Holdings` OWNS TWO ADDRESSES AND HAS ONE TAX ID,
#: DELIBERATELY — AND IT RECEIVES ONE ACCOUNT, NOT TWO.** Measured on a seeded
#: clone, 2026-09-23: both `181 Willow Bend Dr` and `183 Cedar Ridge Way` declare
#: `AC-2026-00054`. The two share one typed owner record, so the door takes its
#: typed-owner branch and `ensure_owner_master_account` is *ensure* for the
#: OWNER. `BR-CUS-1011` reads *at most one owner account per address*, never
#: *exactly one per address*, and `premises.master_account`'s own `PROTECT`
#: comment states the intended shape — *"an account twelve addresses are billed
#: through"*. It is the case a clerk meets first (one landlord, several
#: buildings) and the estate now demonstrates it rather than only describing it.
#:
#: ⚠ **`Ridge Property LLC` IS ABSENT FROM THIS TABLE ON PURPOSE.** Its account
#: is `DEF-709`'s and already exists, carrying `CR030_COMMON_AREA_OWNER_TAX_ID`;
#: a second value here would be the drifting copy this fixture keeps refusing to
#: make. What that address was missing is the DECLARATION, not the account.
OWNER_ACCOUNT_TAX_IDS: dict[str, str] = {
    "Mill Pond Apartments LP": "00-1000325",
    "Silver Creek Duplex Holdings": "00-1000326",
    "Kestrel Park Developments": "00-1000327",
}

#: The fewest units an address must hold before its named owner is given an
#: account of their own.
#:
#: ⛔ **IT IS A FACT ABOUT THE ADDRESS, NEVER A READING OF THE OWNER'S NAME.**
#: `BR-MET-151` clause 3 forbids deriving a party's category from a string —
#: *Whitfield Rentals LLC* is not evidence of a landlord — and
#: `test_cr039_c14__no_seeded_owner_has_an_INVENTED_category` already caught one
#: seeder trying. **TWO units is not a heuristic about a name: it is the
#: arithmetic that says the owner cannot be the address's only occupier.** On
#: this estate it excludes exactly the three single-suite commercial premises
#: whose `owner_manager` IS their occupying customer — `Northwind Mfg.` at 77
#: Industrial Way, `Quarry Hill Diner`, `Creekside Laundromat` — and an
#: owner-occupier has no use for a second account naming itself.
OWNER_ACCOUNT_MIN_UNITS = 2

#: The one category refused outright, whatever the unit count says.
#: `OWNER_CATEGORY_BY_NAME` already STATES which of this fixture's owners live
#: in what they own, so the exclusion is read from a declared fact rather than
#: inferred a second time — and it keeps the rule right if a later estate ever
#: gives an owner-occupier a second unit.
OWNER_CATEGORY_OWNER_OCCUPIER = "owner_occupier"

#: The consumer category every one of these accounts opens under.
#:
#: ⚠ **ONE VALUE FOR ALL OF THEM, STATED ONCE, BECAUSE THE REASON IS THE SAME
#: FOR ALL OF THEM:** every owner in `OWNER_ACCOUNT_TAX_IDS` is a COMPANY — an
#: LP, a Holdings, a Developments — and `_seed_developer_master_account` already
#: made and stated this choice for `Ridge Property LLC`. The category describes
#: the PARTY and not the units, so a landlord's own account at a block of
#: residential flats is still a commercial customer.
#:
#: ⚠ **AND IT MOVES NO MONEY TODAY.** None of these four addresses has a
#: common-area unit (measured 2026-09-23: the tenant holds exactly one, at
#: `500 Main St`, and `DEF-709`'s account already covers it), so each of these
#: accounts covers nothing, bills nothing and produces no document — *no lines,
#: no document*, the 2026-08-31 ruling's own general rule.
#:
#: ⛔ **AND THAT SENTENCE HAS A CLOCK IN IT, SO IT SAYS *TODAY* RATHER THAN
#: *EVER*.** `BR-CUS-1094` was ruled the same day this fixture was written
#: (`OQ-CUS-12609`, CLOSED 2026-09-23): **a VACANT unit is billed to its
#: premises' master account and an occupied one to its tenant, decided when the
#: run starts.** Billing has no concept of a master account today — every
#: `master` in `apps/billing/` is `master_data_ref`, unrelated — so nothing
#: flows now; the moment that ruling is built, `Kestrel Park ph. 2` (12 units,
#: all vacant, with an owner account) becomes exactly the case it describes, and
#: the single-family street becomes its open clause: *a vacant unit whose
#: premises has no master account*. **That is the fixture the billing lane will
#: need, and it is here by construction rather than by luck — but nothing in
#: this file decides anything about a bill.**
OWNER_ACCOUNT_TYPE = "commercial"


# ── W2 · TASK 2.10 — THE EIGHT `[shot]` ACCOUNT SHAPES (B18 §5.1.5) ──────────
#
# *"`1,247` accounts is a DEMO FIGURE, NOT A SEED TARGET. The seed needs the
# SHAPES, one row each: Active/Current · Active/30d past · Active/60+ past
# (accent balance) · Marked disconnect · Pending activation (balance reads
# awaiting, LAST BILL = —) · Vacation hold · a multi-service account with `+3`
# overflow · a customer with 4 linked accounts. **Eight rows** `[shot]`."*
#
# HOW EACH AGEING SHAPE IS MADE, AND WHY IT IS NOT A DATE IN THIS FILE
# ---------------------------------------------------------------------
# The `AGEING` column is DERIVED (BR-CUS-016) from the account's own opening
# position, aged FORWARD from the batch cutover (BR-CUS-048). So a shape is
# made by giving the account an opening BUCKET, never by typing a segment:
# `ob_current` reads `Current`, `ob_31_60` reads `31-60`, `ob_90_plus` reads
# `90+`. The CUTOVER DATE is `apps/customers/sample_data.demo_cutover_on()` —
# DEF-629's ruling (PO 2026-08-24: *"whenever you do the migration cant you
# devcide the date at that time"*), decided at seed time and persisted, so the
# demo still draws the screenshot's ageing in six months' time.
#
# ❄️ **GT-16'S FIXTURE IS UNTOUCHED.** `A-12103` keeps its finance-signed
# 2026-08-31 cutover and its 84.20 / 62.10 / 0.00 / 121.00 buckets; nothing in
# this section reads, re-dates or re-sums them, and `_seed_gt16_cutover_account`
# still refuses a seat offering any other date.
#
# MONEY: 4 decimals stored, `CHAR(3)` currency from the TENANT (never typed
# here), display 2 (CLAUDE.md rule 2). Every figure below is a string.

CR030_CURRENT = "ob_current"
CR030_31_60 = "ob_31_60"
CR030_61_90 = "ob_61_90"
CR030_90_PLUS = "ob_90_plus"

#: The eight shapes, in the order B18 §5.1.5 lists them. `shape` is the SENTENCE
#: the design uses for the row, carried so a test can name what it is asserting
#: and so the seeder's report says which shape landed rather than a count.
CR030_ACCOUNT_SHAPES: tuple[dict[str, Any], ...] = (
    {
        "shape": "Active / Current",
        "account_no": "A-10432",
        "unit_no": "SCW-U-201",
        "customer_name": "Miller, Sarah",
        "customer_ref": "CUS-00432",
        "account_type": "residential",
        "status": "active",
        # [D] §5.2.1 — `BALANCE $247.30 / Due Aug 25`. The DUE DATE needs
        # billing and is not seeded (§5.2.1 marks it ❌); the figure is.
        "buckets": {CR030_CURRENT: "247.30"},
        # [D] §5.2.1 state pills — `▪ Active` · `▪ Autopay on`.
        "autopay": True,
        # [D] §5.2.1 sub-line — *"… · Since Feb 2024"*.
        "opened_at": date(2024, 2, 5),
        # [D] §5.2.2 Overview right rail — `Deposit & credit · On file $150.00`.
        "deposit_on_file": "150.00",
        "deposit_received_on": date(2024, 2, 5),
        "email": "sarah.miller@example.invalid",
        "phone": "+1 (512) 555-0142",
    },
    {
        "shape": "Active / 30d past",
        "account_no": "A-11780",
        "unit_no": "SCW-U-202",
        # See the fixture-slip note at the top of this section.
        "customer_name": "Delgado, Pilar",
        "customer_ref": "CUS-01780",
        "account_type": "residential",
        "status": "active",
        # [D] §5.8.2 — `A-11780 · $318.60 · TIER 1 · REMINDER`.
        "buckets": {CR030_31_60: "318.60"},
        "autopay": False,
        "opened_at": date(2023, 9, 12),
        "email": "pilar.delgado@example.invalid",
        "phone": "+1 (512) 555-0177",
    },
    {
        "shape": "Active / 60+ past (accent balance)",
        "account_no": "A-11455",
        "unit_no": "SCW-U-203",
        "customer_name": "Park, Jenna",
        "customer_ref": "CUS-01455",
        "account_type": "residential",
        "status": "active",
        # [D] §6.6(c) — ONE figure, two tabs: the Accounts `60+ past` balance
        # and the transfer's *arrear follows $542.10*.
        "buckets": {CR030_61_90: "542.10"},
        "autopay": False,
        "opened_at": date(2022, 6, 1),
        "email": "jenna.park@example.invalid",
        "phone": "+1 (512) 555-0155",
    },
    {
        "shape": "Marked disconnect",
        "account_no": "A-11340",
        "unit_no": "SCW-U-204",
        "customer_name": "Northwind Mfg.",
        "customer_ref": "CUS-01340",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "marked_disconnect",
        # [D] §5.8.2 / §6.6(b) — `$8,240.00`, on Accounts, Move-outs AND
        # Disconnects.
        "buckets": {CR030_90_PLUS: "8240.00"},
        "autopay": False,
        "opened_at": date(2021, 3, 15),
        "email": "ap@northwind.example.invalid",
        "phone": "+1 (512) 555-0340",
    },
    {
        "shape": "Pending activation (balance awaiting · LAST BILL —)",
        "account_no": "A-12048",
        "unit_no": "SCW-U-206",
        "customer_name": "Kwan, Michael",
        "customer_ref": "CUS-02048",
        "account_type": "residential",
        # ⚠ **NO BUCKETS AND NO BILL, DELIBERATELY.** §5.1.5: *"balance reads
        # awaiting, LAST BILL = —"*. An opening bucket here would give the row a
        # balance and an ageing segment, and the whole point of this shape is
        # the two cells that have nothing to say yet.
        "buckets": None,
        "status": "pending_activation",
        "autopay": False,
        # [D] §5.5.2 — the move-in `A-12048 · Kwan, Michael · 88 Pine Vista ·
        # Sep 01 · 3 of 5 · collected $150.00`. Opened, not yet activated.
        "opened_at": date(2026, 9, 1),
        "deposit_on_file": "150.00",
        "deposit_received_on": date(2026, 8, 22),
        "email": "michael.kwan@example.invalid",
        "phone": "+1 (512) 555-2048",
    },
    {
        "shape": "Vacation hold",
        "account_no": "A-11512",
        "unit_no": "SCW-U-213",
        # NAMED BY THE FIXTURE — no `[shot]` names this row. See CR030_PREMISES.
        "customer_name": "Hollis, Marcus",
        "customer_ref": "CUS-01512",
        "account_type": "residential",
        "status": "vacation_hold",
        # `vacation_hold` is BR-CUS-055's `billable_base_only` class, so the
        # account is live and owes what it owes: a small current position, which
        # is what a snowbird's base charge leaves behind.
        "buckets": {CR030_CURRENT: "30.50"},
        "autopay": True,
        "opened_at": date(2020, 11, 2),
        "email": "marcus.hollis@example.invalid",
        "phone": "+1 (512) 555-0512",
    },
    {
        "shape": "Multi-service — the `+3` chip overflow",
        "account_no": "A-11720",
        "unit_no": "SCW-U-208",
        "customer_name": "Ridge Property LLC",
        "customer_ref": "CUS-01720",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        # ⚠ **NOTHING OUTSTANDING, AND THAT IS LOAD-BEARING RATHER THAN TIDY.**
        # `SR-…0043 · Ridge Property LLC` is drawn `In fulfilment`, so it was
        # APPROVED — and approval reads the arrears condition over every account
        # the matched customer holds (B19 §12.3's `CLEAR — Nothing owed on
        # A-11024`). An opening balance here would block the approval and the
        # Requests tab would draw a state the estate contradicts.
        "buckets": None,
        "autopay": False,
        "opened_at": date(2019, 4, 1),
        "email": "accounts@ridgeproperty.example.invalid",
        "phone": "+1 (512) 555-1720",
    },
    # ── the EIGHTH shape is a CUSTOMER, not an account: `Ridge Coffee Co.`
    # with FOUR linked accounts (§5.1.2's `4 accounts` sub-link, and the
    # `4-account customer` row of §6.6's estate table).
    #
    # ⚠ The SUB-LINK ITSELF WAS CUT — W2 task 2.5, PO 2026-08-24: *"okay dont
    # link it"*. The SHAPE was not: §5.1.5 still asks for the customer, §6.6
    # still counts it, and `customer_accounts` is the N:M table BR-CUS-054
    # exists for. What is not built is the anchor on the NAME cell.
    #
    # ONE `customer_ref` = ONE `customers` row (`link_customer` matches on it),
    # so four accounts carrying `CUS-00311` land under one customer without any
    # seeder choosing which row to reuse.
    #
    # ⚠ NOT `CUS-00218`, which B19 §12.3 draws as `Osei, Grace`'s matched
    # customer (*"1 closed account · deposit available $153.50"*). Reusing it
    # here would teach a reader that the coffee shop and the move-in applicant
    # are the same person.
    {
        "shape": "Customer with 4 linked accounts (1 of 4)",
        "account_no": "A-11801",
        "unit_no": "SCW-U-209",
        "customer_name": "Ridge Coffee Co.",
        "customer_ref": "CUS-00311",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        "buckets": {CR030_CURRENT: "412.75"},
        "autopay": True,
        "opened_at": date(2023, 1, 9),
        "email": "hello@ridgecoffee.example.invalid",
        "phone": "+1 (512) 555-1801",
    },
    {
        "shape": "Customer with 4 linked accounts (2 of 4)",
        "account_no": "A-11802",
        "unit_no": "SCW-U-210",
        "customer_name": "Ridge Coffee Co.",
        "customer_ref": "CUS-00311",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        "buckets": {CR030_CURRENT: "96.20"},
        "autopay": True,
        "opened_at": date(2023, 5, 4),
        "email": "hello@ridgecoffee.example.invalid",
        "phone": "+1 (512) 555-1801",
    },
    {
        "shape": "Customer with 4 linked accounts (3 of 4)",
        "account_no": "A-11803",
        "unit_no": "SCW-U-211",
        "customer_name": "Ridge Coffee Co.",
        "customer_ref": "CUS-00311",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        "buckets": {CR030_31_60: "148.90"},
        "autopay": True,
        "opened_at": date(2024, 2, 19),
        "email": "hello@ridgecoffee.example.invalid",
        "phone": "+1 (512) 555-1801",
    },
    {
        "shape": "Customer with 4 linked accounts (4 of 4)",
        "account_no": "A-11804",
        "unit_no": "SCW-U-212",
        "customer_name": "Ridge Coffee Co.",
        "customer_ref": "CUS-00311",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        "buckets": None,
        "autopay": True,
        "opened_at": date(2026, 7, 1),
        "email": "hello@ridgecoffee.example.invalid",
        "phone": "+1 (512) 555-1801",
    },
    # ── NOT ONE OF THE EIGHT, AND REQUIRED BY THEM. `SR-26-0046 · Thompson, R.
    # · Move-out · 88 Pine Vista` is a move-out request, and a move-out needs a
    # LIVE ACCOUNT to close. Without this row the request resolves
    # `served_vacant` and the decision panel would badge `Move-out` *Not
    # possible — the applicant holds no live account at this address*, which is
    # the opposite of what §5.3.10 draws.
    {
        "shape": "Support row — the move-out request's live account",
        "account_no": "A-11996",
        "unit_no": "SCW-U-205",
        "customer_name": "Thompson, R.",
        "customer_ref": "CUS-01996",
        "account_type": "residential",
        "status": "active",
        "buckets": {CR030_CURRENT: "64.80"},
        "autopay": False,
        "opened_at": date(2021, 8, 30),
        "email": "r.thompson@example.invalid",
        "phone": "+1 (512) 555-1996",
    },
)

#: The account number every §5.2 `[shot]` is taken from — named so no seeder,
#: test or report has to spell it twice.
CR030_DEMO_ACCOUNT_NO = "A-10432"

#: The ledger BATCH KEY the estate's opening entries are keyed to — *"idempotent
#: per (batch, account)"* (B5 GT-16, and `ledger.opening_balances.cutover_event`
#: is the one place that string is composed).
#:
#: ⚠ **DELIBERATELY NOT `RUN-2814`, which is ❄️ GT-16's.** The buckets still
#: CITE the migration run they came across on — one migration, one story — but
#: the ledger key is separate so that a replay, a repair or a rollback of the
#: demo estate can never reach the finance-signed batch, and so `RUN-2814` keeps
#: the property B5 states about it: one batch, one set of opening entries.
CR030_OPENING_BATCH_KEY = "cr030-demo-estate"


# ── W3 · TASK 3.12 — `A-10432` WITH ALL NINE TABS POPULATED (B18 §5.2.4) ─────
#
# *"One account (`A-10432 · Miller, Sarah`) carrying: 6 bills incl. one `Draft
# (in run)` · 6 payments incl. a `DEPO-4218` deposit at `Held` · 2 meters
# (`M-4021` AMI electric, `M-4022` AMR water) with 4 reads each, one flagged
# *Partial cycle* · 3 adjustments with 3 distinct reasons and 2 approvers ·
# 5 documents across all five types · 3 notes · 7 audit rows spanning `System`,
# a staff user and a portal actor. **That single account is the demo.**"*
#
# ⚠ **WHAT THIS FIXTURE DECLARES IS WHAT THE PRODUCT CAN HOLD TODAY, AND THE
# REST IS NAMED HERE RATHER THAN LEFT AS A GAP A READER FINDS LATER:**
#
#   · **6 bills / 6 payments** — NOT declared. The demo's bills are issued by
#     the REAL engine over the sample billing cycle (`apps/billing/sample_data`)
#     and this estate deliberately joins no route (see the top of this section),
#     so A-10432 has no bill. Declaring six invoice rows would mean writing
#     `invoices` from a fixture — append-only rows (hard rule 4) that no bill
#     run produced. **Owed: task 3.12's billing half, once the estate can be
#     billed without moving the PO's ready-to-run July batch.**
#   · **5 documents** — NOT declarable. There is NO account-document table in
#     this product: `service_request_documents` is the request's, and B18
#     §5.2.2 marks the Documents tab ❌ *"whole tab"*. A seeder cannot seed a
#     table that does not exist (task 3.7 owns it).
#   · **3 adjustments** — billing owns `adjustments`; declared below, seeded by
#     billing's own sample module if it publishes a service for them.
#   · **7 audit rows** — NOT declared, and that is correct rather than missing:
#     every service call this seed makes writes its own `audit_log` row (rule
#     7), so the Audit tab fills from the seeding itself. The `portal actor`
#     row §5.2.2 draws is NOT seeded — the identity model has no portal actor
#     (§5.2.2 says so in the same cell) and inventing one would be a fabricated
#     actor on an audit trail.

#: [D] §5.2.2 Meters tab — `METER # · SERVICE · TYPE (AMI · Itron OpenWay
#: CENTRON) · INSTALL DATE · MULTIPLIER · LAST READ · LAST READ DATE · STATUS`.
#: Valuation on every new seed is BR-AST-047, as the CR-028 section above.
CR030_A10432_METERS: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "M-4021",
        "unit_no": "SCW-U-201",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "valuation": {
            "purchase_cost": "289.0000",
            "purchase_date": "2024-02-01",
            "supplier": "Itron Inc",
            "expected_life_years": 20,
        },
    },
    {
        "asset_no": "M-4022",
        "unit_no": "SCW-U-201",
        "service": "water",
        "uom": WATER_UOM,
        "meter_type": "amr",
        # ⚠ **CORRECTED 2026-08-27 — THIS COMMENT ASSERTED A RULE THAT WAS
        # NEVER RULED, AND IT IS WHY `OQ-392` WAS AMBIGUOUS AT ALL.** It read:
        # *"`mobile` is the seeded read-method code for a drive-by round"*,
        # which states `drive_by ≈ Mobile` **by comment**. Nobody ever decided
        # that. OQ-392 quoted this very line as the repo contradicting itself,
        # and BR-MET-142 (PO ruling 2026-08-27) settled it the other way:
        # `drive_by` is its own read method, because `mobile` is about WHAT
        # DEVICE was used and a drive-by round is about HOW the round was run.
        # A comment claiming a rule is not the rule (hard-won law 1).
        #
        # So this AMR water meter now carries `drive_by`, which is what its own
        # batch's `source_detail` has said since the fixture was written.
        "read_method": "drive_by",
        "multiplier": "1",
        "valuation": {
            "purchase_cost": "171.0000",
            "purchase_date": "2024-02-01",
            "supplier": "Badger Meter",
            "expected_life_years": 15,
        },
    },
)

#: FOUR reads per meter, one flagged *Partial cycle* (§5.2.4), as REGISTER
#: values — the seeder posts them through the S28 stage→validate→commit
#: pipeline a clerk drives, so consumption is DERIVED from consecutive
#: registers and never typed (CLAUDE.md rule 3: the unit travels with it).
#:
#: The electric figures are the ones B18 §5.2.2's Usage strip states —
#: `AVG/MONTH 628 kWh · PEAK 842 kWh (Jul 2026) · LOW 412 kWh (Feb 2026)` — so
#: the months that are seeded produce those consumptions rather than a shape
#: that merely looks plausible: 412 (May→Jun), 842 (Jun→Jul), 628 (Jul→Aug).
#: ⚠ The strip's own 24-month window needs 24 months of reads; four reads make
#: THREE months, which is what a fixture can honestly state (BR-MET-106: an
#: unread month renders ABSENT, never `0`).
CR030_A10432_READS: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "M-4021",
        "service": "electric",
        "uom": "kWh",
        # `read_batches.source_detail` is a CLOSED vocabulary (walk_by ·
        # drive_by · self_read · field_visit · ami_itron · ami_sensus), so the
        # batch says HOW the reading arrived in the product's own words. An AMI
        # meter's reads arrive from the head-end; the AMR water meter's are
        # collected on a drive-by round.
        "source_detail": "ami_itron",
        # ⚠ **AND `read_method` IS THE ONE THAT NOW COUNTS (CR-038 W3,
        # 2026-08-26).** BR-MET-123 makes the read SOURCE a TAG chosen at
        # upload from the TENANT's `read_methods` list, and the line above is
        # the legacy vocabulary it replaces. Both are seeded so the demo shows
        # a read whose method is RECORDED rather than derived — the thing the
        # change exists to make possible.
        # These two values are NOT a new judgment: each is the code the METER
        # already carries in `CR030_A10432_METERS` above — `ami` for M-4021,
        # `drive_by` for M-4022.
        # ⚠ **THIS BLOCK SAID "five-word" AND CITED M-4022's `mobile` "on the
        # strength of the seeded read-method code for a drive-by round".** Both
        # halves moved on 2026-08-27: BR-MET-142 made the list EIGHT and made
        # `drive_by` a method of its own, and the comment that stood in for a
        # ruling is corrected at its source in `CR030_A10432_METERS`. Batch,
        # meter and legacy `source_detail` now all say the same word.
        "read_method": "ami",
        "reads": (
            {"read_on": date(2026, 5, 31), "register": "14200", "note": None},
            {"read_on": date(2026, 6, 30), "register": "14612", "note": None},
            {"read_on": date(2026, 7, 31), "register": "15454", "note": None},
            {"read_on": date(2026, 8, 14), "register": "16082", "note": "Partial cycle"},
        ),
    },
    {
        "asset_no": "M-4022",
        "service": "water",
        "uom": WATER_UOM,
        "source_detail": "drive_by",
        # ⚠ `mobile` UNTIL 2026-08-27, on the strength of the stale comment
        # above. BR-MET-142 made `drive_by` a read method of its own, so the
        # batch tag, the meter's own code and the legacy `source_detail` now all
        # say the SAME word — which is what the fixture always meant and could
        # not previously express.
        "read_method": "drive_by",  # matches M-4022's own meter-side code
        "reads": (
            {"read_on": date(2026, 5, 31), "register": "820", "note": None},
            {"read_on": date(2026, 6, 30), "register": "828", "note": None},
            {"read_on": date(2026, 7, 31), "register": "837", "note": None},
            {"read_on": date(2026, 8, 14), "register": "841", "note": "Partial cycle"},
        ),
    },
)

#: [D] §5.2.2 Notes tab — *"cards, not rows: title (bold) · date · author
#: right-aligned · body"*. THREE.
CR030_A10432_NOTES: tuple[dict[str, str], ...] = (
    {
        "title": "Meter box obstructed",
        "body": (
            "Reader could not lift the lid on the July visit — a planter is standing on "
            "it. Customer called and has agreed to move it before the next cycle."
        ),
    },
    {
        "title": "Autopay enrolled",
        "body": (
            "Customer enrolled in autopay at the counter on the Chase account ending "
            "4021. Bank verification came back clear the same day."
        ),
    },
    {
        "title": "Paperless preference confirmed",
        "body": (
            "Confirmed by phone that bills go by email only. SMS reminders stay on for "
            "the due-date notice."
        ),
    },
)

#: [D] §5.2.2 Adjustments tab — *"DATE · ADJUSTMENT # · REASON · APPLIED TO ·
#: AMOUNT (−$42.50) · APPROVED BY"*, three distinct reasons and two approvers.
#: Money as 4-decimal strings; the sign is the ADJUSTMENT's own (a credit is
#: negative on the screen and TC-ACD-7 pins that the formatter does not re-sign
#: it).
CR030_A10432_ADJUSTMENTS: tuple[dict[str, str], ...] = (
    {"reason": "leak_adjustment", "amount": "-42.50", "note": "Verified leak, 3 kgal credited"},
    {"reason": "goodwill", "amount": "-15.00", "note": "Missed appointment, goodwill credit"},
    {
        "reason": "billing_error",
        "amount": "22.40",
        "note": "Re-billed after an estimate correction",
    },
)


# ── W4 · TASK 4.14 — THE EIGHT `[shot]` REQUESTS (B18 §5.3.10 · B19 §12.1) ───
#
# *"Eight requests, exactly the `[shot]` set — because it is the only fixture
# that demonstrates all five types and six states at once."*
#
# **THE FIXTURE IS CROSS-WIRED ON PURPOSE AND EVERY LANE MUST PRESERVE IT:**
# SR-…0043 → `CON-26-0117` (§5.4) · SR-…0044 → the `Alvarez, Rosa` draft
# move-in (§5.5) · SR-…0046 → the `Thompson, R.` move-out (§5.6) · SR-…0047 →
# the `Park, Jenna` transfer (§5.7) · SR-…0048 → the `Ridge Coffee Co.`
# shortfall (§5.6). *"That is what "we need to keep them conencted" looks like
# in seed data."*
#
# ⚠ **THE CHILD TABLES DO NOT EXIST YET (W5/W6/W7).** BR-CUS-080's link is
# `outcome_kind` + `outcome_ref` on the request, TEXT and not an FK precisely
# because the child is not built (`link_child`'s own docstring). So the
# cross-wiring is seeded as the REFERENCE the child will carry, and the lane
# that builds each child tab wires its half to the same string. `AGE` is
# relative: the seeder back-dates `received_at` to *today − age_days*, so the
# oldest thing waiting is still 15 days old whenever the demo is planted.
#
# ✅ **BR-CUS-095 (PO 2026-08-24, closing OQ-351) IS WHAT UNBLOCKED THIS**, and
# its sharpest clause governs what the seed may do: *"THE DEFAULT IS THE
# RULING'S SHARPEST CLAUSE AND MUST NOT BE SOFTENED: nothing is ticked, so a
# utility that never opens the screen never has a request blocked."*
# **The SHIPPED default is untouched** — no migration, no code default, no
# platform row. `CR030_DOCUMENT_REQUIREMENTS` below is the DEMO TENANT
# deliberately configuring its own checklist, exactly as a real utility would on
# the Settings screen, through `set_document_requirement` (the same call the
# screen makes). A tenant that never loads sample data still ticks nothing.

#: The demo tenant's own checklist — two ticks, on MOVE-IN only, which is
#: BR-CUS-095's own worked example verbatim: *"a utility ticks proof of identity
#: and signed service agreement for MOVE-IN only → a move-in request submits and
#: sits happily in `Under review` with neither attached, and `approve` refuses
#: by name until both are attached AND verified; the same tenant's TRANSFER
#: requests tick nothing and approve with no documents at all."*
#:
#: This is what lets `SR-…0039` sit in `More info needed` and SAY WHAT IT IS
#: WAITING FOR, which is the sentence the ruling ends on.
CR030_DOCUMENT_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {"request_type": "move_in", "doc_type": "proof_of_identity", "required": True},
    {"request_type": "move_in", "doc_type": "signed_service_agreement", "required": True},
)

#: The `SR-` keys the cross-wiring travels by — never the printed number, which
#: the series allocates (see the note at the top of this section).
CR030_SR_KEY = "key"

# ── WHAT EACH REQUEST ASKS FOR, AND WHEN IT WANTS IT (`BR-CUS-1070`) ────────
#
# ⚠ **THE `services` KEY IS NEW ON 2026-09-16 AND IT CLOSES `DEF-CUS-5423`.**
# Measured on the demo tenant that morning: **8 seeded requests and ZERO rows
# in `service_request_services`**. `_drive_cr030_request` drove every other
# step of a request through the product's own service calls and never called
# `set_services`, so capture step 2 and the request's own services panel had
# never had anything to show on demo data — and an absence is invisible to
# every check this repo has.
#
# **THE SHAPE, AND WHY IT IS A DAY OFFSET RATHER THAN A DATE.** Each entry is
# `{"code": …}` — *this service, no date given* — or `{"code": …,
# "start_days": n}`, meaning **n days after the day this request came in**.
# `age_days` is already relative for exactly this reason (the note above:
# *"the oldest thing waiting is still 15 days old whenever the demo is
# planted"*), and a connection date that had quietly slipped into the past
# would demonstrate the opposite of what it is here to show.
#
# **`start_days` IS ABSENT, NOT NULL, WHEN NO DATE WAS GIVEN.** `BR-CUS-1070`:
# an unset `requested_start` means *the clerk gave none* and never *read the
# job's* — in either direction — so a fixture that spelled *no date* as a
# number would be encoding the fallback the rule removed.
#
# **THE SET IS FILTERED TO WHAT THE TENANT SWITCHED ON.** The seeder drops any
# code this utility does not sell (`sample_data._cr030_services_for`), so this
# list is what the request ASKS FOR and the tenant's own `tenant_services` row
# decides what is seeded. Brazos Bend sells electric and water; a sewer-and-
# trash utility loading the same fixture gets its own two. Nothing here
# switches a service on to make the data look richer.
#
# **THE FIVE CASES, one per shape the read has to tell apart** (the table in
# `CR-094-BRC01-capture-lane-F-per-service-starts.md` §4):
#   · `osei-move-in` — every service on the SAME day, over a blank job date.
#     That is `p080`'s drawn pair: `Requested start → …, all of them` beside
#     `Connection date → — not given`, which no fallback can produce.
#   · `ridge-property-new-connection` — **TWO SERVICES, TWO DIFFERENT DAYS.**
#     `p076`'s own argument: *"A block that needs electric on the 12th and
#     sewer a fortnight later is one request and not two, so the date sits per
#     service rather than once on the form."* A 25-unit build energises first
#     and takes water a fortnight later, and this is the only entry that proves
#     the column is a clerk's answer rather than a copy.
#   · `park-transfer` — every service, NO date on any of them. `count` > 0,
#     `agreed` null, `unset` = all: three services all saying *not given* must
#     never read as three services agreeing on a date.
#   · `okonkwo-new-connection` — one dated, one not. The mixed list.
#   · `thompson-move-out` — **NO `services` KEY AT ALL, deliberately.** A
#     request that never reached step 2, so `count` is 0 — a real answer the
#     screens have to render and nothing may divide by.

CR030_SERVICE_REQUESTS: tuple[dict[str, Any], ...] = (
    {
        # `SR-26-0039 | Move-in | Osei, Grace | 3450 Oak Ridge Dr | Aug 08 |
        #  15d | documents | More info needed`
        "key": "osei-move-in",
        "drawn_no": "SR-26-0039",
        "age_days": 15,
        "state": "more_info",
        "outcome": None,
        "applicant_name": "Osei, Grace",
        "applicant_kind": "person",
        "applicant_email": "grace.osei@example.invalid",
        "applicant_phone": "+1 (512) 555-0039",
        "channel": "walk_in",
        "address_as_given": "3450 Oak Ridge Dr",
        "address_unit_as_given": "3450 Oak Ridge Dr · Unit 1",
        # [D] B19 §12.3 — *"What they said → I'm moving into somewhere"*.
        "what_they_said": "I'm moving into somewhere",
        "account_type": "residential",
        "property_type": "rental_tenant_applying",
        "requested_start": None,
        "waiting_on": "documents",
        "park_note": "Photo ID and the signed agreement still to come — chased 21 Aug.",
        "remind_on_days": 2,
        # BR-CUS-095: the tenant ticked TWO for move-in. One is attached and
        # verified, one is not attached at all — which is exactly what *"More
        # info needed · waiting on documents"* means, and it is now sayable.
        "match": {"searched": True, "basis": "no prior customer on file"},
        # `p080`'s DRAWN PAIR: every service on one day, over a job with no
        # `Connection date` at all (`requested_start` is None above). The two
        # are separate facts and this row is what proves it on demo data.
        "services": (
            {"code": "electric", "start_days": 21},
            {"code": "water", "start_days": 21},
        ),
        "documents": (
            {
                "doc_type": "proof_of_address_or_occupancy",
                "name": "tenancy-agreement.pdf",
                "what_it_proves": "Shows they are entitled to occupy the unit",
                "verify": True,
            },
            {
                "doc_type": "proof_of_identity",
                "name": "drivers-licence.jpg",
                "what_it_proves": "Confirms who the applicant is",
                "verify": False,
            },
        ),
        "fees": (),
    },
    {
        # `SR-26-0043 | New connection | Ridge Property LLC | 500 Main St ·
        #  25 units | Aug 12 | 11d | — | In fulfilment`
        "key": "ridge-property-new-connection",
        "drawn_no": "SR-26-0043",
        "age_days": 11,
        "state": "in_fulfilment",
        "outcome": "new_connection",
        # [D] §5.4 — `CON-26-0117`, the 25-unit build, 7 orders.
        "outcome_kind": "connection",
        "outcome_ref": "CON-26-0117",
        "applicant_name": "Ridge Property LLC",
        "applicant_kind": "business",
        "applicant_email": "projects@ridgeproperty.example.invalid",
        "applicant_phone": "+1 (512) 555-1720",
        "channel": "email",
        "address_as_given": "500 Main St",
        "address_unit_as_given": "500 Main St · Unit 100",
        "what_they_said": "We are building 25 units and need service to all of them",
        "account_type": "builder_developer",
        "property_type": "multi_unit_building",
        "requested_start": None,
        "waiting_on": None,
        "match": {
            "customer_ref": "CUS-01720",
            "tier": "strong",
            "basis": "company name and account number",
        },
        # ⚠ **THE ONE ENTRY THAT PROVES THE COLUMN IS REAL — TWO SERVICES, TWO
        # DIFFERENT DAYS.** `p076`: *"A block that needs electric on the 12th
        # and sewer a fortnight later is one request and not two."* A 25-unit
        # build is energised first and takes water a fortnight after, and
        # before `BR-CUS-1070` no clerk could say so: `set_services` copied the
        # job's date onto every row.
        "services": (
            {"code": "electric", "start_days": 30},
            {"code": "water", "start_days": 44},
        ),
        "documents": (
            {
                "doc_type": "site_plan_or_unit_schedule",
                "name": "500-main-unit-schedule.pdf",
                "what_it_proves": "Shows how many units are being served",
                "verify": True,
            },
        ),
        "fees": (),
    },
    {
        # `SR-26-0047 | Transfer | Park, Jenna | 901 Hillside → 2201 Cedar |
        #  Aug 18 | 5d | — | Under review`
        "key": "park-transfer",
        "drawn_no": "SR-26-0047",
        "age_days": 5,
        "state": "under_review",
        "outcome": None,
        "applicant_name": "Park, Jenna",
        "applicant_kind": "person",
        "applicant_email": "jenna.park@example.invalid",
        "applicant_phone": "+1 (512) 555-0155",
        "channel": "phone",
        # BR-CUS-070: kept VERBATIM as the applicant gave it, arrow and all.
        "address_as_given": "901 Hillside Ave → 2201 Cedar Ave",
        "address_unit_as_given": "901 Hillside Ave · Unit 1",
        "what_they_said": "I'm moving across town and want to take my service with me",
        "account_type": "residential",
        "property_type": "standalone_owner_occupied",
        "requested_start": None,
        "waiting_on": None,
        "match": {"customer_ref": "CUS-01455", "tier": "strong", "basis": "account number"},
        # EVERY service, NO date on any of them — `unset` = the whole list and
        # `agreed` null. Services all saying *not given* must never read as
        # services agreeing on a date, and a single null could not tell the two
        # apart; this row is what a screen is tested against.
        "services": ({"code": "electric"}, {"code": "water"}),
        "documents": (),
        "fees": (),
    },
    {
        # `SR-26-0042 | New connection | Okonkwo, David | 14 Willow Bend (new
        #  plot) | Aug 19 | 4d | payment | Under review`
        "key": "okonkwo-new-connection",
        "drawn_no": "SR-26-0042",
        "age_days": 4,
        "state": "under_review",
        "outcome": None,
        "applicant_name": "Okonkwo, David",
        "applicant_kind": "person",
        "applicant_email": "david.okonkwo@example.invalid",
        "applicant_phone": "+1 (512) 555-0042",
        "channel": "walk_in",
        # ⚠ NOT a seeded address — deliberately. B19 §12.3's Location tab:
        # `Resolved to → No premise record` · `Consequence → This becomes a new
        # connection`, with `Plot reference → PL-2026-0884`.
        "address_as_given": "14 Willow Bend, Springfield",
        "address_unit_as_given": None,
        "plot_or_parcel": "PL-2026-0884",
        "what_is_being_built": "Single dwelling on a newly platted lot",
        "what_they_said": "There is nothing here yet — I need service to a new build",
        "account_type": "residential",
        "property_type": "under_construction",
        "requested_start": None,
        "waiting_on": "payment",
        "park_note": "Application fee not taken yet — $130.00 due.",
        "remind_on_days": 3,
        "match": {"searched": True, "basis": "no prior customer on file"},
        # THE MIXED LIST — one service dated, one not. `agreed` null and
        # `unset` 1, which is neither of the two rows above.
        "services": ({"code": "electric", "start_days": 45}, {"code": "water"}),
        "documents": (
            {
                "doc_type": "tenancy_agreement_or_deed",
                "name": "deed-pl-2026-0884.pdf",
                # [D] B19 §12.3 — the fourth document type, drawn with its own
                # sentence: *"Deed or site plan — Shows they may build on the
                # plot"*, `Not yet checked`.
                "what_it_proves": "Shows they may build on the plot",
                "verify": False,
            },
        ),
        # ⚠ **BR-CUS-090's WORKED QUOTE, $130.00 — AND NOTHING TAKEN YET.**
        # Until 2026-09-24 this row seeded `$25.00` cash taken short on receipt
        # `RCP-26-4471`, the PO's 2026-08-24 *"we acept it … finance will
        # reconcile"*. `OQ-CUS-12624` (PO 2026-09-24, *"all or waived"*,
        # `DEF-CUS-6455`) refuses a short payment at the desk, so the seed would
        # have been refused and its park note would have described a state the
        # product can no longer reach. The request now waits on the WHOLE fee,
        # which is what `waiting_on: payment` always said.
        "fees": (
            {
                "charge_code": "CC-REQFEE",
                "description": "Application processing fee",
                "basis": "per request",
                "unit_amount": "25.00",
                "quantity": "1",
            },
            {
                "charge_code": "CC-EXPEDITE",
                "description": "Expedited handling",
                "basis": "per request",
                "unit_amount": "45.00",
                "quantity": "1",
            },
            {
                "charge_code": "CC-METERTEST",
                "description": "Meter test on request",
                "basis": "per meter",
                "unit_amount": "60.00",
                "quantity": "1",
            },
        ),
    },
    {
        # `SR-26-0048 | Disconnect | Ridge Coffee Co. | 500 Main · 200 |
        #  Aug 20 | 3d | third party | Under review`
        #
        # ✅ **BR-CUS-091 (PO 2026-08-24, *"Yes customer can request it"*),
        # closing DEF-638 12.a.** The list was right; REQ-02's decision-panel
        # reason is WITHDRAWN. Raised by COLLECTIONS, so `channel` is
        # `staff_collections` and the applicant-identity fields are not
        # required — the rule's own consequence clause, and the reason this row
        # can exist without a clerk inventing an applicant.
        "key": "ridge-coffee-disconnect",
        "drawn_no": "SR-26-0048",
        "age_days": 3,
        "state": "under_review",
        "outcome": None,
        "applicant_name": "Ridge Coffee Co.",
        "applicant_kind": "business",
        "applicant_email": None,
        "applicant_phone": None,
        "channel": "staff_collections",
        "address_as_given": "500 Main St",
        "address_unit_as_given": "500 Main St · Unit 200",
        "what_they_said": None,
        "account_type": "commercial",
        "property_type": None,
        "requested_start": None,
        "waiting_on": "third party",
        "park_note": "Landlord's agent has to be present before the meter can be pulled.",
        "remind_on_days": 4,
        "match": {"customer_ref": "CUS-00311", "tier": "strong", "basis": "account number"},
        # ONE service and a date — a shop having its electric pulled. `count`
        # of 1 is the list a screen renders without a comma in it.
        "services": ({"code": "electric", "start_days": 7},),
        "documents": (),
        "fees": (),
    },
    {
        # `SR-26-0045 | Move-in | Kwan, Michael | 88 Pine Vista | Aug 21 | 2d |
        #  — | Approved`  → the account it produced is A-12048, PENDING
        # ACTIVATION (the fifth account shape above). BR-CUS-080's link, both
        # ends, on one estate.
        "key": "kwan-move-in",
        "drawn_no": "SR-26-0045",
        "age_days": 2,
        "state": "approved",
        "outcome": "move_in",
        "outcome_kind": "account",
        "outcome_ref": "A-12048",
        "applicant_name": "Kwan, Michael",
        "applicant_kind": "person",
        "applicant_email": "michael.kwan@example.invalid",
        "applicant_phone": "+1 (512) 555-2048",
        "channel": "portal",
        "address_as_given": "88 Pine Vista",
        "address_unit_as_given": "88 Pine Vista · Unit 2",
        "what_they_said": "I'm moving in on the first",
        "account_type": "residential",
        "property_type": "rental_tenant_applying",
        "requested_start": date(2026, 9, 1),
        "waiting_on": None,
        # The tenant ticks TWO for move-in (BR-CUS-095) and `approve` refuses by
        # name until both are attached AND verified — so an APPROVED move-in
        # must carry both, verified. That is the ruling working, seeded.
        "match": {
            "customer_ref": "CUS-02048",
            "tier": "strong",
            "basis": "account number and name",
        },
        # ⚠ **THE MIRROR OF `p080`'s PAIR, AND IT IS THE HALF A FALLBACK WOULD
        # HAVE HIDDEN.** This request HAS a job-level `Connection date`
        # (`requested_start` above) and its services carry none. Under the old
        # copy both services would have read `2026-09-01`; under `BR-CUS-1070`
        # they read *not given*, because the job's date is not theirs.
        "services": ({"code": "electric"}, {"code": "water"}),
        "documents": (
            {
                "doc_type": "proof_of_identity",
                "name": "kwan-passport.jpg",
                "what_it_proves": "Confirms who the applicant is",
                "verify": True,
            },
            {
                "doc_type": "signed_service_agreement",
                "name": "service-agreement-signed.pdf",
                "what_it_proves": "The terms they have agreed to",
                "verify": True,
            },
        ),
        "fees": (),
    },
    {
        # `SR-26-0044 | Move-in | Alvarez, Rosa | 1408 Elm St · Unit A |
        #  Aug 22 | 1d | — | Submitted` → §5.5's DRAFT move-in, and J26's own
        # journey ("A phone call becomes SR-26-0044").
        #
        # ⚠ 1408 Elm Street · Unit A is A-10432's unit and A-10432 is LIVE, so
        # this resolves `served_occupied` — which is the truth about a request
        # to move into somewhere somebody still lives, and is what the drawn
        # move-in job has to settle before it can complete.
        "key": "alvarez-move-in",
        "drawn_no": "SR-26-0044",
        "age_days": 1,
        "state": "submitted",
        "outcome": None,
        "outcome_kind": "move_in",
        "outcome_ref": None,
        "applicant_name": "Alvarez, Rosa",
        "applicant_kind": "person",
        "applicant_email": "rosa.alvarez@example.invalid",
        "applicant_phone": "+1 (512) 555-0044",
        "channel": "phone",
        "address_as_given": "1408 Elm Street",
        "address_unit_as_given": "1408 Elm Street · Unit A",
        "what_they_said": "I'm taking over the lease at the start of next month",
        "account_type": "residential",
        "property_type": "rental_tenant_applying",
        "requested_start": date(2026, 9, 1),
        "waiting_on": None,
        "match": {"searched": True, "basis": "no prior customer on file"},
        # A single-service move-in, dated. One code and one date.
        "services": ({"code": "water", "start_days": 14},),
        "documents": (),
        "fees": (),
    },
    {
        # `SR-26-0046 | Move-out | Thompson, R. | 88 Pine Vista | Aug 23 | 0d |
        #  scheduled date | Submitted`
        #
        # ⚠ **`Submitted` AND `waiting on a scheduled date` AT ONCE** — the pair
        # the model's own docstring cites to prove `waiting_on` is ORTHOGONAL to
        # `state`. Park writes it and moves nothing.
        "key": "thompson-move-out",
        "drawn_no": "SR-26-0046",
        "age_days": 0,
        "state": "submitted",
        "outcome": None,
        "outcome_kind": "move_out",
        "outcome_ref": None,
        "applicant_name": "Thompson, R.",
        "applicant_kind": "person",
        "applicant_email": "r.thompson@example.invalid",
        "applicant_phone": "+1 (512) 555-1996",
        "channel": "phone",
        "address_as_given": "88 Pine Vista",
        "address_unit_as_given": "88 Pine Vista · Unit 1",
        "what_they_said": "I'm leaving at the end of the month",
        "account_type": "residential",
        "property_type": "rental_tenant_applying",
        "requested_start": None,
        "waiting_on": "scheduled date",
        "park_note": "Customer has not named a move-out day yet.",
        "remind_on_days": 5,
        "match": {"customer_ref": "CUS-01996", "tier": "strong", "basis": "account number"},
        # ⚠ **NO `services` KEY, AND IT IS DELIBERATE.** This request never
        # reached step 2, so `requested_start_agreement` answers `count: 0` —
        # a real state every screen has to render and nothing may divide by.
        # One of the eight stays empty on purpose; the seeder does not treat a
        # missing key as a gap.
        "documents": (),
        "fees": (),
    },
)


def cr030_request_count() -> int:
    """Eight — B18 §6.6's own figure for the Requests tab fixture."""
    return len(CR030_SERVICE_REQUESTS)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16, amended the same day for percent-of-water sewer) · CR-028/B16 §9 AST-W0-T1 (PO 2026-08-22)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane) · AMENDED 2026-08-22 by story-coder (CR-028 AST-W0 lane — the r10 registry-shape section: carts/master+subs/net meter/five BTM kinds/inventory/valuation, all ADDITIVE; fixture version → .3) · AMENDED 2026-08-26 by the CR-039 wave A lane (DEF-795 — the estate is a SHAPE and the service is a PARAMETER: METERED_ESTATE_SERVICES / COMPANION_ESTATE_SERVICES / SERVICE_METER_PREFIX / CONSUMPTION_SCALE, EstatePlan + estate_plan(enabled, default_uoms), meter_no / replacement_meter_no / consumption(service=...), and meter_plan / sub_meter_plan / master_meter / master_sub_meter_plan / inventory_plan / cr028_asset_plan taking (service, uom). Every default is the water estate byte for byte)
# checklist: A✔ B✔ C=n/a(no API half — this file is a declaration, not a service) D=n/a E=n/a(no frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: THREE DEPARTURES FROM THE SPEC AS WRITTEN, each argued in the module docstring rather than made silently — percent-of-water sewer (the model landed 2026-08-16 and the PO ratified $15.80 on $39.50), 48 water meters rather than 96 (a percent-of-water sewer line reads no register, and 48 unread sewer meters would bury the three deliberately unreadable ones), and three premises with no unit (44 premises AND 48 units are otherwise arithmetically impossible with the stated mix) · the SENIOR plan is NOT declared here: no signed figure states its discount and spec rule 7 forbids choosing one — OQ-240
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
