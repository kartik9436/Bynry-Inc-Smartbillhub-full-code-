# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S9, S10,
#           S11 (the plans and schedules this writes are what those screens
#           draw) · S8 (Sample data panel, BR-TEN-069)
# Rules:    BR-TEN-056 (the sample set) · BR-TEN-057 (`is_sample` on the owning
#           row, written by THIS module's own service) · BR-TEN-061 (removal
#           order) · BR-TEN-063 (idempotent, audited) · BR-TEN-068 (sample
#           plans are PROMOTED on first real attachment) · BR-RAT-015 (sewer =
#           % of water usage-charge dollars, excl. base, excl. tax) ·
#           BR-RAT-025 (plan-as-bundle) · BR-RAT-030 (draft → published) ·
#           BR-RAT-031 (one service, one model; activation needs a complete
#           structure)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the two
#           seams below) · apps/customers (attaches accounts to these plans)
# ───────────────────────────────────────────────────────
"""rating's half of the sample set: the plans and rate schedules (DEF-153).

WHAT THIS EXISTS TO END
-----------------------
`apps/tenancy/seams.py` has documented `apps.rating.services.seed_sample_records`
since 2026-08-15 and nothing implemented it, so the Sample data panel loaded
nothing and a brand-new tenant had no plan to put an account on. That is
DEF-153, and it is built-is-not-wired at its purest: an orchestrator, a panel
and eight documented seams, with zero implementers.

EVERY ROW IS WRITTEN THROUGH THIS MODULE'S OWN AUDITED SERVICES
----------------------------------------------------------------
`create_rate_schedule`, `create_plan` and `publish_plan` — the same three calls
S11 and S10 make when a human fills the wizard in. Spec §rule 4 is the reason:
*"A fixture built by direct insert proves the tables exist and proves nothing
about the product."* The ONLY direct write here is stamping `is_sample`, which
BR-TEN-057 says must be done by this module's own service function on the
sample path and by nothing else.

THE ESTATE AND THE TARIFF ARE ONE SHAPE (DEF-2397, 2026-09-01)
---------------------------------------------------------------
⚠ **THIS FILE PRICED `water`, `sewer` and `trash` IN LITERALS FOR THREE DAYS
AFTER CR-039 WAVE A MADE METERING AND ASSETS SERVICE-SHAPED, AND THE GAP COST
EVERY BILL ON THREE OF THE TEN SERVICES.** Measured on PostgreSQL 16 through
`tenancy.services.provision_tenant`, one tenant per service: **electric, gas and
storm water each received a complete metered estate — 70 premises, 118 units,
75 service points, 70 meters, 193 reads — and then 0 schedules, 0 plans, 0
accounts and 0 bills**, with 9 of 17 seeding blocks failed and all 48 seats
refused `customers.account.plan_required_at_activation` (`BR-MET-040`).

`estate()` below now asks `core.sample_fixture.estate_plan` the same question
metering and assets ask it, through rating's own seams (B1), so one tenant gets
one estate from one pure function. **A water tenant is unmoved byte for byte** —
`estate_plan` picks water as the backbone whenever the tenant sells it, ahead of
catalogue order, precisely so that GT-17 ❄️'s frozen figures keep standing on
unit 0's 8 kgal.

WHAT A NON-WATER BACKBONE COSTS — THE BASE IS SIGNED, THE USAGE IS NOT
-----------------------------------------------------------------------
`[W] §1` states a monthly base for electric (`$12.00` residential, `$48.00`
Small Commercial) and for gas (`$6.00`), and those are seeded on the plan and on
`BR-RAT-088`'s charge code, agreeing to the cent by construction.

⚠ **EVERY METERED SERVICE PRICES ITS USAGE FROM 2026-09-07, AND `OQ-1290` IS
CLOSED (`DEF-RAT-4516`).** This section said *"No signed figure prices the USAGE
against the single register this fixture plants"* and described a stored `$0.00`
naming its question. That was true when it was written and it was answered in
three instalments: **electric** took a signed TIERED ladder and **thermal**
`$0.045` a ton-hour under `CR-062` E1/E6 (PO, 2026-09-02); **storm water** is a
CAPACITY service whose impervious-area characteristic nobody records, which
`BR-MET-108` rules bills as **zero** (PO: *"Bill it as zero"*) with the zero
**stamped and surfaced**, never silent; and **gas** — the last one open — takes
the workbook's own `$1.15` per `ccf` from 2026-09-07, applied in the unit it is
signed in against a register that has read that unit since `BR-TEN-1180`
(2026-09-02). Nothing here chose a number: spec rule 7 was satisfied by waiting
for each figure to be signed, not by guessing one.

**Worked, on the gas tenant this closed:** the reference customer's meter
`G-5000` reads **40 ccf** in June, its usage line is `40 × $1.15` = **`$46.00`**
and its bill is `$46.00 + $6.00` base = **`$52.00`** before tax. It was `$6.00`
and twelve cents of tax until the price was seeded — the PO's own words for it
were *"One real gap, and it is money. Gas bills $0.00 usage"*.

THE SEWER LINE IS A PERCENTAGE OF WATER'S VOLUME, PRICED ON ITS OWN RATE
--------------------------------------------------------------------------
The fixture spec was written when `percent_of_service` did not exist and said
*"seed sewer FLAT and say so on the plan"*. It exists now
(`apps/rating/pricing/models/percent_of_service.py`, 2026-08-16).

⚠ **THIS SECTION SAID, UNTIL 2026-09-08:** *"the Product Owner ratified its
figure the same day: sewer is 40% of the water USAGE charge — $15.80 on $39.50 —
deliberately NOT counting the $8.00 base, which would give $19.00. So sewer is
seeded as `percent_of_service` at 40 of `water`, which is BR-RAT-015 and GT-17
❄️."* Every clause of that was true and is now SUPERSEDED by a later signature
from the same authority (`CR-081`, HUMAN-GUIDE §6 re-sign 2026-09-08).

**What is seeded now:** `percent_of_service` at **90** of `water` with a rate of
**$5.0000** per water's unit. The 90 is a RETURN-TO-SEWER FACTOR — the share of
metered water that reaches the sewer — and not the price ratio the 40 was. On
the reference unit's 8 kgal that is **7.2 kgal × $5.0000 = $36.00**, where it
was $15.80.

TRASH IS PRICED PER CART — $15.00 EACH (AMENDED 2026-08-21, DEF-491)
---------------------------------------------------------------------
BR-RAT-025 / publish's D2 gate requires a schedule for every ticked service, so
trash cannot be on the plan without one.

⚠ **THIS SECTION SAID "ITS PRICE IS ZERO, ON PURPOSE" AND THE PURPOSE EXPIRED.**
It argued that trash *"is not measured — no meter, no read"* and therefore had
nothing to price per quantity. **BR-RAT-090 (PO ruling 2026-08-20, option A,
closing OQ-283) made it measured** — not by a register but by a COUNT of the
unit's active carts, *"an unmetered service's quantity is a COUNT OF ITS ASSETS
ON THE UNIT"*, observed and never typed. And **OQ-303 closed on 2026-08-21 at
`$15.00` per cart**, verbatim: *"they are bill 1 trash can $15 - for example if
you have 3 you multiple by 3"*.

**So the schedule prices `$15.00` per `cart`. Worked, ratified: 3 carts ×
`$15.00` = `$45.00`; remove one and the next bill is `$30.00`.**

**Why it sat at zero for a day after being ruled, which is the part worth
keeping (DEF-491):** the placeholder cited no question. A `0.00` under a comment
explaining itself is invisible to every check in this repo, so closing the
question that had held it there moved nothing and nothing noticed. A placeholder
waiting on an answer must NAME that answer's question at the line the
placeholder sits on — which every one below now does.

⛔ **THE `$18.00` MONTHLY BASE IS RETIRED — `OQ-317` CLOSED 2026-08-27 ON OPTION
A (`DEF-2490`, `BR-RAT-832`).** PO verbatim: *"option A is correct; where do you
see the carts - they are not on accounts theya re on Units."* This paragraph read
*"the `$18.00` monthly base is UNCHANGED and is OQ-317"* for a day after the
ruling, because the closure reached the registry, the decision log and
`BR-BIL-300` and never reached this file — `DEF-491`'s own shape, one ruling
later. **The plan's trash base and `BASE-T` both read `fixture.TRASH_BASE`
(`$0.00`) now, so a three-cart household bills `$45.00` and not `$63.00`; across
the demo's 48 trash accounts the retirement is `$864.00` a month.** It is a
stored ZERO and never an omission: a blank base means *this size is not served*
and stops the bill (CR-013 part 1 / `DEF-277`). `TRASH_FLAT` survives in
`core/sample_fixture.py` as the RECORDED superseded `[W] §1` figure — a signed
figure is superseded, never deleted — and is read by nothing. WE-9's *"Broadband
$49 + Trash $18"* is history for the same reason.

⚠ **AND THE CART LINE CANNOT REACH A BILL YET, WHICH IS NOT THIS FILE'S HALF.**
Three joints downstream are open: no carts are seeded on any unit (DEF-496),
`tenant_services.metered` has no reader so the run still treats trash as a
missing read (DEF-495, DEF-161), and the billing seeder therefore records
`bill_without_service`, which DELETES the trash line. The price is seeded where
the rule puts it and the wiring gap stays visible — the same posture the DEF-154
paragraph below takes, and for the same reason.

⚠ AND THAT $18 IS WHERE DEF-154 BITES. The base charge lives on the PLAN and the
bill engine reads it from the rate SCHEDULE, where it is zero. Until DEF-154 is
fixed every seeded bill prints a $0.00 base. This fixture does NOT paper over it
by moving the figure into the schedule — that would hide a live money defect
behind a fixture, and the defect would then reach a real utility instead of the
demo. The figure is seeded where the rule puts it and the defect stays visible.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.rating.constants import PRICE_HISTORY_EPOCH
from apps.rating import (
    base_size_amounts,
    discount_sample_data,
    models,
    seams,
    selectors,
    service_base_amounts,
    services,
)
from core import errors
from core import sample_fixture as fixture
from core import tenancy as core_tenancy
from core.pagination import ListParams

logger = logging.getLogger("smartbillhub.rating")


class CapacityUomNotDeclared(ValueError):
    """A capacity service is about to be PRICED and declares no unit — `CR-062` D8.

    ⚠ **THIS EXISTS BECAUSE THE SILENT DEFAULT IT REPLACES WAS A MONEY BUG.**
    `_capacity_uom` used to end `or fixture.CAPACITY_UOM` — the string
    `"month"` — which was harmless only while every capacity price was `$0.00`.
    With `fixture.CAPACITY_UNIT_PRICES` signed on 2026-09-02, that fallback
    would quote **solar's `$14.00` per MONTH against a quantity measured in
    kW**: a well-formed schedule, a passing unit gate, and a wrong bill. That is
    `DEF-497` exactly, one service over, and it is the defect this raise exists
    to make impossible.

    **A `ValueError` and deliberately NOT a `SizeClassNotRuled`.** Nothing here
    is waiting on a PO answer — `SERVICE_DEFAULT_UOMS` declares a unit for all
    five capacity services, so reaching this means a tenant's own Settings are
    incomplete. It is a data state to report by name (`BR-TEN-060`), not an
    unruled boundary to stub.
    """

    def __init__(self, service_code: str) -> None:
        super().__init__(
            f"{service_code!r} is priced as a capacity service and the tenant declares "
            "no billed or primary unit for it, so there is no unit to quote its price "
            "per. Set one on Settings -> Services & UoM. (CR-062 D8 — a seeded price "
            "must never be quoted per an invented unit; that is DEF-497.)"
        )
        self.service_code = service_code


#: Every sample row this module writes carries this prefix in its name, so a
#: human reading S10/S11 can see at a glance which rows are the demo's. The
#: `Sample` pill BR-TEN-069 rules for S14/S15/S17/S25 is the screen half of the
#: same idea; this is the half that survives a screenshot.
SAMPLE_PREFIX = "Sample —"

SCHEDULE_WATER_RES = f"{SAMPLE_PREFIX} Residential water (inclining tiers)"
SCHEDULE_WATER_COM = f"{SAMPLE_PREFIX} Commercial water (flat)"
SCHEDULE_SEWER = f"{SAMPLE_PREFIX} Sewer (% of water)"
#: ⚠ **THE NAME IS STALE AND IS DELIBERATELY NOT CHANGED (DEF-491).** Trash IS
#: measured since BR-RAT-090 — by a count of the unit's carts — and this
#: schedule now prices `$15.00` per cart, so *"(monthly, not measured)"* is no
#: longer true of it.
#:
#: **The name is an IDENTITY, not a description.** `create_rate_schedule` is
#: idempotent on (tenant, name, service) — `uq_tariffs_tenant_name_service` — so
#: renaming it would not rename anything: it would mint a SECOND trash schedule
#: on every tenant that already has this one, and the plan would then bind one
#: of two. Same reasoning as the migration module DEF-490 declined to rename:
#: the name is history and the docstring is truth. Renaming it needs a data
#: migration, and that is not this defect.
SCHEDULE_TRASH = f"{SAMPLE_PREFIX} Trash (monthly, not measured)"
#: DEF-463 — the seed wrote ONLY schedules with a version in force, so the
#: status a card derives had exactly one value and the DRAFT state could not
#: be walked at all. r10 draws one (`Residential Water 2027 filing`) beside
#: its actives, which is what made the gap visible. This is a SEPARATE
#: schedule, not another version of the residential one: DEF-357's history
#: already gives that a dated pending version, and a schedule with something
#: in force reads as ACTIVE with a scheduled change — a different fact from a
#: filing that has never been in force.
SCHEDULE_WATER_FILING = f"{SAMPLE_PREFIX} Residential water 2027 filing"

#: **THE INDUSTRIAL ELECTRIC USAGE SCHEDULE — `CR-062` ADDENDUM J4.**
#:
#: ⚠ **A SEPARATE NAME AND THEREFORE A SEPARATE SCHEDULE, WHICH IS THE WHOLE
#: MECHANISM.** `create_rate_schedule` is idempotent on `(tenant, name,
#: service)` (`uq_tariffs_tenant_name_service`), so an industrial ladder written
#: under `backbone_schedule_name("electric")` would not be a second schedule —
#: it would COLLIDE with the residential one and a plan would then bind whichever
#: of the two a query reached first. The residential tiers and this flat rate are
#: two prices for one service, and `BR-RAT-108` separates those by CLASS.
SCHEDULE_ELECTRIC_IND = f"{SAMPLE_PREFIX} Industrial electric usage"

PLAN_RESIDENTIAL = "SCW-RES"
PLAN_COMMERCIAL = "SCW-COM"
#: `CR-062` addendum J4 — the third seeded plan class. The code follows the two
#: above and `seed_demo`'s own `IND`, so a person reading S10 sees one grammar.
PLAN_INDUSTRIAL = "SCW-IND"


# ══════════════════════════════════════════════════════════════════════════
# DEF-2397 · THE ESTATE AND THE TARIFF ARE SHAPED BY ONE RULE, NOT TWO
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS MODULE PRICED `water`, `sewer` and `trash` IN LITERALS WHILE
# METERING AND ASSETS HAD BEEN SERVICE-SHAPED SINCE CR-039 WAVE A, AND THAT
# GAP COST EVERY BILL ON THREE SERVICES.** Measured on PostgreSQL 16 through
# `tenancy.services.provision_tenant`, one tenant per service: an ELECTRIC
# utility received **70 premises, 118 units, 75 service points, 70 `E-` meters
# and 193 kWh reads** — a complete metered estate — and then **0 schedules, 0
# plans, 0 accounts and 0 bills**, with 9 of 17 seeding blocks failed. Gas and
# storm water were the same shape. The refusal was honest and named:
#
#     no sample account was created: every one of the 48 seats this tenant
#     holds refused … SCW-U-001: BizError: BIZ-COMPLETENESS
#     (customers.account.plan_required_at_activation)
#
# — because `_schedule_payloads` built nothing, `_plan_payloads` returned an
# empty list, no plan existed, `metering._backfill_missing_unit_plans` found no
# plan id, and every unit kept `rate_plan_id` NULL (`BR-MET-040`).
#
# **The fix is to ask the SAME question metering and assets ask**, through
# rating's own seams (B1), so one tenant gets one estate shape from one pure
# function rather than two modules disagreeing about what utility this is.


def estate() -> fixture.EstatePlan:
    """THE ESTATE THIS TENANT CAN BE GIVEN — the same plan metering builds.

    ⚠ **RESOLVED INDEPENDENTLY OF METERING AND ASSETS AND GUARANTEED TO AGREE.**
    All three call `core.sample_fixture.estate_plan`, which is PURE and
    deterministic on its inputs, each through its OWN seam file — no module
    imports another module's seams (B1). That is what makes the agreement
    structural rather than a convention somebody has to remember: assets plants
    an `E-5000` meter, metering stages a read against that serial, and this
    module prices the service they both chose.

    ⚠ **AND A DISAGREEMENT HERE IS SILENT, WHICH IS WHY IT LASTED.** Metering's
    own note warns that a mismatched backbone surfaces as `unknown_meter` on 49
    rows. Rating's mismatch does not surface at all — it produces NO schedule,
    which reads exactly like a tenant that has not been seeded yet, and the
    failure appears four blocks later in `apps/customers` under a completeness
    error that names neither rating nor the service.
    """
    return fixture.estate_plan(
        seams.enabled_service_codes(),
        seams.service_default_uoms(),
        seams.service_billed_uoms(),
        seams.unit_reconciliation,
    )


def backbone_schedule_name(service_code: str) -> str:
    """The ONE usage schedule a non-water backbone gets, by name.

    ⚠ **THE NAME IS AN IDENTITY AND IT DELIBERATELY STATES NO PRICE OR STATUS.**
    `create_rate_schedule` is idempotent on `(tenant, name, service)`
    (`uq_tariffs_tenant_name_service`), so a rename does not rename anything —
    it mints a SECOND schedule on every tenant that already holds this one, and
    the plan then binds one of two. `SCHEDULE_TRASH` above is this repo's
    worked example of the cost: it still reads *"(monthly, not measured)"*
    about a service that has been measured since `BR-RAT-090`, and correcting
    it needs a data migration.
    **So a name that said *"usage not yet priced"* would be a temporary fact
    welded into a permanent key.** The fact that the usage is unpriced lives in
    `NOT_SEEDED` and in the plan's description, both of which can be rewritten
    the day `OQ-1290` closes.

    The service's own catalogue name is used where the platform has one, so the
    row reads in the utility's vocabulary rather than in a code (`B14` rule 31:
    no internal identifier is the visible value of a field).
    """
    return f"{SAMPLE_PREFIX} {_service_label(service_code)} usage"


#: The `is_base` charge-code suffix per backbone service (`BR-RAT-088`).
#:
#: ⚠ **A SHORT EXPLICIT MAP, NOT A DERIVATION, and the reason is that the codes
#: are a VOCABULARY a human reads on S12.** `BASE-W` / `BASE-S` / `BASE-T` have
#: been these letters since the fixture was written and `seed_demo` already
#: ships `BASE-E` and `BASE-E-IND` for the demo tenant, so the electric letter
#: is fixed by precedent rather than chosen here. Deriving them from the code
#: string would give `BASE-STORM_WATER`, which is a database identifier wearing
#: a charge code's clothes.
#:
#: `water` is absent: its two codes are declared in `BASE_CHARGE_CODES` below
#: and no water figure moves for this defect.
#: ⚠ **`storm_water` MOVED TO `CAPACITY_BASE_CODE` ON 2026-09-02 (`CR-062` C9,
#: `DEF-3231`) AND THE CODE STRING `BASE-SW` DID NOT CHANGE.** Storm water is
#: billed on the size of the property rather than on a dial, so it has no
#: register and no metered base; what it has is a capacity base, at the same
#: letters a person already reads on S12. Moving the code rather than minting a
#: second one is deliberate — `create_charge` is idempotent on `code`, so a
#: rename would leave every existing tenant holding both.
BACKBONE_BASE_CODE: dict[str, str] = {
    "electric": "BASE-E",
    "gas": "BASE-G",
    # ⚠ `thermal_heat`'s `BASE-TH` LEFT ON 2026-09-07 (`CR-080`) — it moved to
    # `CAPACITY_BASE_CODE` below **with its letters unchanged**, exactly as
    # `BASE-SW` did on 2026-09-02 and for the paragraph above's reason:
    # `create_charge` is idempotent on `code`, so minting a new one would leave
    # every existing tenant holding both.
}

#: The `is_base` charge-code suffix per CAPACITY service — `DEF-3156`.
#:
#: ⚠ **THESE EXIST BECAUSE `DEF-528` SAYS THEY MUST, AND WITHOUT THEM THE WHOLE
#: SEED DIES.** `BR-RAT-088`'s guard now fires for EVERY tenant, not only for
#: one that has adopted declared base codes: `SBH_BILLING_RESOLUTION_STEPS`
#: ships `R3,R4` and `_guard_base_charge_code` refuses any schedule activation
#: for a service with no `is_base` code the moment *"the chain states the
#: base"* (`DEF-2923`). So `DEF-528`'s own sentence binds — *a base charge code
#: is seeded for EVERY service this seed prices, or for none* — and this map is
#: the "every" half for the three services `capacity_schedule_payloads` prices.
#:
#: **A SHORT EXPLICIT MAP AND NOT A DERIVATION, for `BACKBONE_BASE_CODE`'s own
#: reason one map up: the codes are a VOCABULARY a human reads on S12.**
#: Deriving them from the code string would give `BASE-STORM_WATER`'s shape —
#: `BASE-THERMAL_HEAT`, `BASE-BROADBAND` — a database identifier wearing a
#: charge code's clothes. These four letters follow the abbreviations already in
#: use (`BASE-SW` for storm water), and they are fixed by this line the moment a
#: tenant carries one: `create_charge` is keyed on `code`, so a later rename
#: mints a SECOND code rather than renaming the first.
CAPACITY_BASE_CODE: dict[str, str] = {
    "solar": "BASE-SOL",
    "broadband": "BASE-BB",
    "battery": "BASE-BAT",
    # CR-062 C9 — arrived here from `BACKBONE_BASE_CODE` with its letters
    # unchanged when storm water stopped being a metered service.
    "storm_water": "BASE-SW",
    # ⚠ **CR-063 — AND ITS ABSENCE MEANT A FIRE UTILITY ISSUED ZERO BILLS
    # (`DEF-3087`).** `fire` joined `CAPACITY_ESTATE_SERVICES` on 2026-09-02 and
    # this map did not, so the bare subscript below raised `KeyError: 'fire'`,
    # `seed_sample_records` died, **14 of 17 seeding blocks failed**, no plan
    # existed, every seat refused at activation and the tenant issued NOTHING.
    # Measured on PostgreSQL 16 — and the eleventh service is the one whose
    # customer is real, which is the whole reason `CR-063` was raised.
    "fire": "BASE-FIRE",
    # CR-080 (PO 2026-09-07) — arrived here from `BACKBONE_BASE_CODE` with its
    # letters unchanged when thermal/heat stopped being a metered service.
    # ⚠ **AND `DEF-3087` IS WHY THIS LINE IS NOT OPTIONAL:** the bare subscript
    # in `capacity_schedule_payloads` raises `KeyError` for a member of
    # `CAPACITY_ESTATE_SERVICES` that is missing here, `seed_sample_records`
    # dies, no plan exists and the tenant issues NOTHING. Fire cost exactly
    # that on 2026-09-02.
    "thermal_heat": "BASE-TH",
}

#: Spec §2 asks for THREE plans, the third a discounted "Senior" variant. No
#: signed figure states that discount and spec rule 7 forbids inventing one
#: (*"the seeder stubs and mints a question rather than choosing a number that
#: then looks official"*). It is therefore NOT seeded, it is REPORTED by name on
#: every run, and the question is OQ-240.
NOT_SEEDED: tuple[dict[str, str], ...] = (
    {
        "what": "Senior rate plan (the discounted variant)",
        "oq": "OQ-240",
        "reason": (
            "no signed figure states the senior discount — neither the billing "
            "workbook §1 nor B4/B5 names one, and a demo tariff that looks "
            "official is exactly what spec rule 7 forbids. The two plans that DO "
            "seed are structurally different from each other (inclining tiers vs "
            "a flat rate), which is what a third plan was there to give"
        ),
    },
    # ── `OQ-1290`'s ENTRY IS GONE, AND THE ABSENCE IS THE DELIVERABLE ───────
    # It read "a usage price for an electric, gas or storm-water backbone" and
    # was `BR-TEN-060`'s surface for a gap: a stored `$0.00` that NAMES its
    # question, rather than a silent zero. **`OQ-1290` CLOSED on 2026-09-07
    # (`DEF-RAT-4516`) and all three services now price their usage** — electric
    # on `ELECTRIC_TIERS` and thermal at $0.045 (`CR-062` E1/E6, 2026-09-02),
    # storm water at a RULED zero on the CAPACITY side (`BR-MET-108`, "Bill it
    # as zero"), and gas at the workbook's signed $1.15/ccf. There is no gap
    # left for this entry to surface, and a `NOT_SEEDED` row describing a
    # closed question is exactly the stale body CLAUDE.md warns is what the next
    # lane actually reads. `test_the_signed_gas_usage_figure_is_seeded_as_signed`
    # is what goes red if the price ever leaves again.
)


def _enabled(service_code: str) -> bool:
    return bool(seams.service_is_enabled(service_code))


def _tag(queryset: Any) -> int:
    """BR-TEN-057: stamp `is_sample` on rows THIS module owns. The only direct
    write in this file, and the rule names it as this module's job."""
    return int(queryset.update(is_sample=True))


# ── DEF-2799 · THE SIZE AXIS AND THE VERSION BASE, SEEDED TOGETHER ──────────
#
# ⚠ **THE SIZE AXIS WAS ONE OF TWO MISSING FACTS AND THE OTHER ONE TURNED OUT
# TO BE A DEFECT IN THE CHAIN.** Measured over a whole prepared bill run on this
# very fixture (47 accounts, real PostgreSQL, `rolsuper=false`,
# `rolbypassrls=false`): the ruled `R1–R7` chain refused **47 of 47** at `R3`
# with *"connection size 'W-58' has no row on the rate schedule version …"*,
# because `rate_size_rows` held **0 rows** on a tenant whose meters are all
# `W-58`. That half is a fixture gap and it is fixed here.
#
# ⚠ **THE SECOND HALF IS FIXED IN THE CHAIN, NOT HERE (`DEF-2823`, CLOSED
# 2026-08-31) — AND THE WORKAROUND THAT USED TO LIVE ON THIS LINE IS GONE.**
# Writing a size row for every size left R3 STILL refusing all 47, now with the
# OTHER sentence — *"…with a BLANK base charge … a blank base means THIS SIZE IS
# NOT SERVED (DEF-277)"* — because `tariff_versions.base_charge` was NULL on all
# nine versions. **That column is RETIRED.** `BR-RAT-088` moved the base onto the
# CHARGE CODE and `RateScheduleWizard.tsx` removed its control in the same
# ruling — *"CARRIED, NEVER EDITED … no control, no editing, no loss"* — and
# `decimalOut("")` omits the key entirely, so **every schedule version a real
# utility creates through this product today stores NULL there, unavoidably.**
#
# For one afternoon this seeder wrote that column anyway, to make R3 resolve. It
# worked and it was exactly the wrong shape: **it configured the demo utility in
# a way no customer could copy.** The fix is in the chain — R3 now asks only
# *does this schedule serve this size* and R4 states the amount from the
# `is_base` charge code — so this file writes the SIZE AXIS and no base at all,
# and `BASE_CHARGE_CODES` below is where every base figure lives.
#
# ⚠ **NEITHER FACT MOVES A BILL, AND THAT IS MEASURED RATHER THAN CLAIMED.**
# `10-scripts/def2799_live_base_charges.py` prints the base the live path
# resolves for every ready account BY NAME; run across this change it diffs
# **empty** — water base **$8.00** on the reference account, **$390.00** across
# the run, account by account. `tests/test_def2799_seeded_size_axis.py` and
# `tests/test_def2823_base_from_charge_code.py` pin both figures.
#
# ⚠ **AND THE SIZE ROWS THEMSELVES CANNOT MOVE A BILL AT ALL**: no live pricing
# read touches `rate_size_rows`. `pricing_inputs_for_version` publishes the
# version's SCALAR `minimum_bill` and derives `size_groups` from
# `RateTier.size_class` (every seeded tier is NULL there), so `gather`'s
# `connection_size_unresolved_for_sized_schedule` refusal is not armed by this.


def sample_size_rows(service_code: str) -> list[dict[str, Any]]:
    """`BR-RAT-120`'s size axis for ONE service, as the SCHEDULE's own statement.

    Every row carries `size_class` and NO `minimum_bill`, which
    `_validate_size_rows` stores as a real row with a NULL amount — *"this size
    IS served and has no floor"*, r10's em-dash — and never as `$0.00`.

    **The ladder is the PLATFORM's ratified list for the service, not the sizes
    this tenant's meters happen to be**, and that is a judgment with a reason.
    `DEF-2799`'s own note asks for *"a row for every (service, size class) its
    own meters are"*, and the schedules are seeded BEFORE any asset exists, so
    that set is not knowable here. The ratified list is knowable, it is the
    same list every seeded `meter_size_classes` row comes from — so it covers
    every size a meter on this tenant can ever be, by construction — and a
    fixture that served only the one size installed today would start refusing
    bills the first time a 3/4" meter was fitted.

    ⚠ **THIS IS NOT `DEF-1810` COMING BACK.** That defect was the CALLER telling
    the catalogue which sizes to serve, so R3 looked up a size it had just been
    told about and a 3" connection resolved the 5/8" rate. Here the SCHEDULE
    states its axis, in stored rows, and R3 reads it back — the caller still
    cannot widen anything (`build_catalogue` has no `served_sizes` keyword).

    ⚠ **SEWER CORRECTLY GETS NONE.** `service_size_classes` rules sewer to have
    no size classes (it is a share of the water usage charge and reads no
    register), so this returns `[]` and `configured_sizes_for` answers with the
    single blank-size ladder rather than refusing.

    An UNRULED service — battery, thermal steam — raises `SizeClassNotRuled`
    carrying its OQ-ID, and it is deliberately not caught: the prime directive
    forbids answering an unruled boundary by choosing a value, and a seed that
    stopped with a named question is the correct failure.
    """
    # Local: `apps.tenancy.service_size_classes` holds no model and issues no
    # query — it is ratified law expressed as data. `resolution_catalogue
    # .configured_sizes_for` imports it the same way and for the same reason.
    from apps.tenancy import service_size_classes

    return [
        {"size_class": code}
        for code, _name in service_size_classes.size_classes_for_service(service_code)
    ]


def _backbone_schedule_payload(metered: "fixture.MeteredService") -> dict[str, Any]:
    """The usage schedule for a NON-water METERED service — `DEF-2397`.

    ⚠ **IT TOOK THE WHOLE `EstatePlan` UNTIL `CR-062` C1 (2026-09-02) BECAUSE
    THERE WAS ONLY EVER ONE.** The estate now holds a register per metered
    service, so this is called once per service and is handed that service's own
    row — its code, its unit and its factor — rather than reaching into a plan
    for a scalar that no longer exists. A tenant selling electric + water gets
    the water tiers AND an electric usage schedule; before, electric had no
    schedule because it had no estate.

    ⚠ **ONE SCHEDULE, BOUND BY BOTH PLANS, AND THAT IS A STATEMENT RATHER THAN
    A SHORTCUT.** Water gets two because its two are structurally different —
    inclining tiers for residential, a flat rate for commercial — and that
    difference is what gives the demo something to compare. Electric, gas and
    storm water have ONE usage answer each (this said *"today (`OQ-1290`:
    none)"* until 2026-09-07; the answers are now signed — gas is a single flat
    $1.15/ccf — and there is still only ONE of them per service), so seeding two
    identical rows would put two schedules on S11 that a clerk would rightly
    ask about and that differ in nothing. `uq_plan_rate_schedules_plan_service`
    is on `(rate_plan, service)`, so two plans may point at one tariff.

    ⚠ **`unit_price` IS A STORED ZERO AND NOT AN OMISSION.** A blank means
    *this size is not served* and stops the bill (`CR-013` part 1 / `DEF-277`);
    a stored zero is a price and prints `$0.00` (PO 2026-08-19, *"print
    $0.00"*). `OQ-670` closed on exactly this reading for a service a plan
    prices nowhere — PO verbatim, *"(b) Bill $0.00"* — over the lane's own
    recommendation to refuse, because *"the zero line buys VISIBILITY, putting
    the gap on the document instead of in a silence"*.

    **Worked, on the seeded GAS tenant (2026-09-07, `DEF-RAT-4516`):** the
    reference customer's meter `G-5000` reads `40 ccf` in June, its usage line
    is `40 × $1.15` = `$46.00`, and its bill is `$46.00` plus the signed `$6.00`
    base = `$52.00` before tax. **This example used to be the ELECTRIC tenant
    and used to end in `$0.00`** — *"unit 0 draws 8 × 100 = 800 kWh in June, its
    usage line is `$0.00`"* — with the missing figure named in `NOT_SEEDED`.
    Electric was priced on 2026-09-02 and gas on 2026-09-07, so there is no
    missing figure left to name and `NOT_SEEDED` no longer carries one.

    The UoM is the TENANT's own declared primary unit, carried through
    `MeteredService.uom` — the same unit that service's meter reads (CLAUDE.md
    rule 3). It is never defaulted here: `estate_plan` refuses a metered service
    with no declared unit, BY NAME and on its own, before this is reached.
    """
    service = str(metered.code)
    return _flat_schedule_payload(
        service,
        name=backbone_schedule_name(service),
        uom=str(metered.uom),
        # ── CR-062 E6 · A PRICE PER SERVICE, FALLING BACK TO THE STORED ZERO ─
        # This read `fixture.BACKBONE_USAGE_UNPRICED` for every metered service
        # alike. `thermal_heat` is signed at $0.045 per ton-hour and `gas` at
        # $1.15 per ccf (DEF-RAT-4516, 2026-09-07); both take their figure from
        # the map. Electric never reaches here at all: it is TIERED and is built
        # in `_schedule_payloads` one function down.
        #
        # ⚠ **NO SEEDED SERVICE LANDS ON THE FALLBACK ANY MORE**, and the
        # comment here said `gas` did until 2026-09-07. The four services in
        # `METERED_ESTATE_SERVICES` are all priced, so the `.get()` default is
        # now a safety net for a FIFTH metered service arriving unpriced — a
        # stored zero that prints $0.00 and names its gap, rather than a blank
        # that stops the bill (`CR-013` part 1 / `DEF-277`).
        unit_price=fixture.METERED_USAGE_PRICES.get(
            service, fixture.BACKBONE_USAGE_UNPRICED
        ),
    )


def _flat_schedule_payload(service: str, *, name: str, uom: str, unit_price: str) -> dict[str, Any]:
    """ONE flat schedule row — the backbone's and a capacity companion's alike.

    ⚠ **EXTRACTED FOR `DEF-3156` SO THERE IS EXACTLY ONE OF IT, AND NOT A LINE
    OF IT MOVED.** Every key below was inside `_backbone_schedule_payload`; what
    is new is that a SECOND caller needs the same seven keys. A copy would drift
    on the first key a rate shape gains — silently, because both copies would go
    on producing a well-formed schedule — which is the argument
    `gather.version_fields_from` already records one module along.

    The three things that DO differ between the two callers are the three
    arguments, and each is a decision its caller owns: the schedule's NAME (an
    identity `create_rate_schedule` is idempotent on, so a rename mints a second
    row rather than renaming one), the UNIT the price is quoted per (hard rule
    3), and the PRICE.

    `size_rows` is `BR-RAT-120`'s size axis and is the PLATFORM's ratified
    ladder for the service (`service_size_classes`) rather than the sizes this
    tenant's own equipment happens to be — see `sample_size_rows`. An UNRULED
    service raises `SizeClassNotRuled` carrying its OQ-ID and is deliberately
    not caught; a service ruled to have NONE (sewer, battery) answers `[]`,
    which `configured_sizes_for` reads as the single blank-size ladder.
    """
    return {
        "name": name,
        "service": service,
        "model": "flat",
        "uom": uom,
        "effective_from": fixture.PERIODS[0]["start"].isoformat(),
        "size_rows": sample_size_rows(service),
        "structure": {"unit_price": unit_price},
    }


def capacity_schedule_name(service_code: str) -> str:
    """The ONE schedule a CAPACITY companion gets, by name — `DEF-3156`.

    ⚠ **IT DOES NOT SAY *"usage"*, AND THAT IS THE ONE THING THIS FUNCTION
    DECIDES.** `backbone_schedule_name` one function up ends every name in
    *usage*, which is true of a register's reading and false of a capacity
    service: `BR-RAT-090` prices these by a COUNT of what is installed on the
    unit, and nothing is used. **The name is an IDENTITY** —
    `create_rate_schedule` is idempotent on `(tenant, name, service)`
    (`uq_tariffs_tenant_name_service`), so a later correction would not rename
    this row, it would mint a SECOND schedule on every tenant that already holds
    it and the plan would then bind one of two. `SCHEDULE_TRASH` is this repo's
    worked example of that cost: it still reads *"(monthly, not measured)"*
    about a service measured since `BR-RAT-090`, and correcting it needs a data
    migration. So the word is chosen once, here, before any tenant carries it.

    *Capacity* is the PO's own word for these three (the 2026-09-01 three-value
    declaration — metered · share of another service · capacity), and the
    service's own catalogue name is used where the platform has one so the row
    reads in the utility's vocabulary rather than in a code (`B14` rule 31).
    """
    return f"{SAMPLE_PREFIX} {_service_label(service_code)} capacity"


def _capacity_uom(service_code: str) -> str:
    """The unit a capacity schedule's price is quoted per — `DEF-3156`.

    **THE TENANT'S OWN EFFECTIVE BILLED UNIT WHERE IT HAS ONE, AND THE SAME
    EXPRESSION THE `BR-RAT-038` GATE USES.** `rating.selectors.uom_gate_for`
    resolves *the unit the thing that prices it is written in* as `billed_uom`
    or, where that is NULL, `primary_uom` — NULL means *the register's own unit
    is what is billed* and reading it as "unconfigured" is what made that gate
    blind on every tenant alive (2026-09-02). Asking the same question here is
    what makes the seeded schedule satisfy the gate BY CONSTRUCTION rather than
    by luck: broadband declares `month`
    (`tenancy.services.SERVICE_DEFAULT_UOMS`) and gets `month`.

    ⚠ **AND IT READS THE KEYS THE SEAM ACTUALLY RETURNS, WHICH `_trash_uom` DID
    NOT (`DEF-497`).** That function asked for `uom` and `code`; `seams
    .billed_uom` returns `billed_uom` / `primary_uom` / `conversion_factor` and
    nothing else, so every lookup missed and the fallback was the only reachable
    branch — a guarantee stated in prose and delivered by no code (hard-won law
    1). The two keys below are that seam's own.

    ⚠ **THE `month` FALLBACK IS GONE, AND ITS REMOVAL IS `CR-062` TASK D8
    (2026-09-02).** This function used to end `or fixture.CAPACITY_UOM`, which
    was the string `"month"`. That was safe for exactly as long as every
    capacity price was `$0.00`, and its own docstring said so: *"the price and
    the unit are ONE decision and must move in ONE commit … a lane that changes
    the price and leaves `month` here has rebuilt `DEF-497` on a live money
    path"*. The prices are now signed (`fixture.CAPACITY_UNIT_PRICES`), so the
    fallback would price **solar at `$14.00` per MONTH against a quantity in
    kW** — hard rule 3 satisfied in FORM and wrong in SUBSTANCE, which is
    `DEF-497` verbatim.

    ⚠ **SO A SERVICE THAT DECLARES NO UNIT IS REFUSED BY NAME, AND THE REFUSAL
    IS THE FEATURE.** All five capacity services declare one in
    `tenancy.services.SERVICE_DEFAULT_UOMS` — solar `kW`, battery `kW`, storm
    water `ERU`, broadband `Mbps`, fire `connection` — so this raises on no
    tenant that was provisioned from the platform's own seed map. If it ever
    does raise, the honest answer is that the tenant's Settings are incomplete
    and a seeded money figure would be a guess; `BR-TEN-060` is the rule that a
    gap is NAMED rather than filled with a silent default.
    """
    declared = seams.billed_uom(service_code) or {}
    uom = declared.get("billed_uom") or declared.get("primary_uom")
    if not uom:
        raise CapacityUomNotDeclared(service_code)
    return str(uom)


def fire_schedule_payload() -> dict[str, Any]:
    """**FIRE'S SCHEDULE, PRICED PER SIZE - `CR-063` task C3.**
    🔒 rating math. HUMAN-REVIEW-PENDING.

    ⚠ **THIS EXISTS BECAUSE A SHIPPED FIRE BILL READ `$0.00` (hard-won law
    2 - *built is not wired*).** `CR-063` landed fire end to end: the service,
    the screens, the eleven locale strings, revenue account `4155`, an estate, a
    service point, a line on the document. The seven real prices landed too, in
    `tenancy.service_size_classes.FIRE_DEFAULT_PRICES`, with
    `fire_charge({"FL-2": 1}) == $12.00` asserted by a test - **and nothing in
    the product called any of it.** Fire took the same flat
    `fixture.CAPACITY_UNIT_PRICES["fire"]` the four SUMMING services take, which
    is the string `"0"`, so every diameter priced at nothing on a bill that
    footed and printed.

    ⚠ **WHY THE PRICE IS NOT IN `CAPACITY_UNIT_PRICES` AND WILL NOT BE
    MOVED THERE.** That map holds ONE amount per service, multiplied by a
    quantity in that service's own unit - `$14.0000` per kW, `$0.1000` per Mbps.
    It is the right shape for a service that SUMS and it cannot express fire at
    all: the quantity is a COUNT of connections and the price is picked by the
    SIZE, so seven amounts are needed and a single scalar would price a 6" line
    exactly like a 2" one. Fire's `"0"` therefore STAYS in that map,
    deliberately - it is a stored zero and not an omission (`CR-013` part 1: a
    blank means *this size is not served* and stops the bill), and it is what a
    fire schedule falls back to for a size the ladder below does not name. The
    prices live with the SIZES, in `service_size_classes`, because they are one
    unratified statement: the seven rows mean nothing to a utility without an
    amount beside them, and splitting them across two files would let one move
    without the other.

    ⚠ **AND THE PRICES ARE READ, NEVER RETYPED.** `FIRE_DEFAULT_PRICES` is
    the one place they exist. A copy here would be a second statement of a money
    figure, and the two would disagree the first time `OQ-1360` closes with the
    going-live customer's own list.

    **THE SHAPE, AND WHY IT IS `tiered` RATHER THAN `flat`.** A per-size price
    can only be stored on `RateTier.size_class` - `DEF-433` opened that axis, and
    `_validate_size_rows` records that a size ROW carries a minimum bill and no
    price. So each of fire's six bands gets ONE unbounded tier at its own
    monthly amount, `rating.selectors.pricing_inputs` serves the tier group for
    the size billing resolved, and `BR-RAT-032`'s contiguity is satisfied per
    group by construction (one tier, from 0, open-ended).

    **Worked, and both figures are the ones already put to the Product Owner:**

        one 2" line               ->  1 x $12.0000              = $12.00
        one 6" line               ->  1 x $60.0000              = $60.00
        one 6" line + 2 2" lines  ->  1 x $60.00 + 2 x $12.00   = $84.00

    ⚠ **THE MIDDLE FIGURE MOVED BY PO RULING ON 2026-09-03** — *"remove private
    hydrants from list"*. It read *"one 6" line + 2 hydrants -> 1 x $60.00 + 2 x
    $25.00 = $110.00"*, and the same warehouse now bills `$60.00`: `-$50.00` a
    month on that customer. The six diameters and their prices did not move.

    ⚠ **THE THIRD FIGURE NEEDS THE COUNT SPLIT AS WELL AS THIS PRICE
    LIST**, and the two land together: `billing.gather` bills a COUNTING
    capacity service one line per size (decision log 2026-09-02). Seeding these
    prices without that would have replaced a quiet `$0.00` with a REFUSED
    account, because a version that names sizes makes `gather` demand one.

    **NOT SIGNED, NOT FROZEN.** No finance signature covers a figure here;
    `OQ-1360` is the customer's real list and is OPEN. `GT-17`'s water `$39.50`
    and sewer `$15.80` are untouched - fire is new money on new lines.
    """
    from apps.tenancy import service_size_classes

    return {
        "name": capacity_schedule_name("fire"),
        "service": "fire",
        "model": "tiered",
        # CLAUDE.md rule 3 - `connection`, fire's own declared unit
        # (`SERVICE_DEFAULT_UOMS`), resolved through the same expression the
        # BR-RAT-038 gate uses rather than typed here.
        "uom": _capacity_uom("fire"),
        "effective_from": fixture.PERIODS[0]["start"].isoformat(),
        "size_rows": sample_size_rows("fire"),
        "structure": {
            "tiers": [
                # ── THE EVERY-SIZE LADDER, AND IT IS REQUIRED (`BR-RAT-032`) ──
                # `_validate_tiers` refuses a payload of per-size overrides with
                # no base group by name — *"the exception without the rule"* —
                # so a version that prices seven bands must also say what an
                # EIGHTH size costs. Fire's answer is `fixture
                # .CAPACITY_UNIT_PRICES["fire"]`, the stored `"0"`, and this is
                # the whole reason that key stays in that map: a stored zero is
                # a PRICE and prints `$0.00` (PO 2026-08-19), where an omission
                # would mean *this size is not served* and stop the bill
                # (`CR-013` part 1 / `DEF-277`).
                #
                # ⚠ **IT IS REACHED BY A UNIT WITH NO FIRE EQUIPMENT AT ALL**,
                # which is `BR-MET-108`'s ruled zero — nothing installed, a
                # count of 0, and `0 × $0.0000` is the `$0.00` line the document
                # carries instead of a silence. An item whose size nobody
                # RECORDED does not reach it: `gather` refuses that account by
                # name, because a 6-inch line priced on the every-size ladder
                # would be `$0.00` for equipment somebody installed.
                {
                    "from_qty": "0",
                    "to_qty": None,
                    "unit_price": fixture.CAPACITY_UNIT_PRICES["fire"],
                },
                *[
                    {
                        "from_qty": "0",
                        "to_qty": None,
                        # ⚠ `unit_price`, NOT `rate` (`DEF-487`) -
                        # `_validate_tiers` `_reject_unknown`s any other key and
                        # `create_rate_schedule` would raise VAL-002, failing the
                        # WHOLE rating seed block and every block behind it.
                        "unit_price": str(service_size_classes.FIRE_DEFAULT_PRICES[code]),
                        "size_class": code,
                    }
                    for code, _name in service_size_classes.size_classes_for_service("fire")
                ],
            ]
        },
    }


def capacity_schedule_payloads(plan: fixture.EstatePlan) -> list[dict[str, Any]]:
    """One flat schedule per CAPACITY service this tenant's estate speaks.

    ⚠ **WITHOUT THESE A SOLAR, BROADBAND OR BATTERY UTILITY BILLS NOTHING AT
    ALL, AND IT IS MEASURED (`DEF-3156`).** `DEF-2396` gave the three an estate
    — 70 premises, 118 units, 48–49 service points on PostgreSQL 16.13 — and
    this module had no payload for a capacity companion, so `_plan_payloads`
    returned an empty list, no plan existed, `metering._backfill_missing_unit_
    plans` found no plan id, every unit kept `rate_plan_id` NULL (`BR-MET-040`)
    and all 48 seats refused `customers.account.plan_required_at_activation`.
    **A service this module has no payload for is simply ABSENT, which is
    indistinguishable from a service the tenant does not sell** — that is why
    the gap survived two fixes that each looked complete from their own side.

    **THE SHAPE IS TRASH'S AND NOTHING NEW IS DESCRIBED.** A capacity service
    rides on the unit with no register (`fixture.CAPACITY_ESTATE_SERVICES`), is
    declared unmetered so `BR-MET-710` answers `service_not_metered` rather than
    demanding a read, and `BR-RAT-090`'s OBSERVED asset count is the billable
    quantity. Membership of `plan.services` is the test rather than `_enabled`,
    for `_schedule_payloads`' own reason: the estate is what decides, and a
    service the tenant sells but the fixture cannot furnish is refused BY NAME
    one level up instead of being priced into a plan whose units cannot carry
    it.
    """
    speaks = set(plan.services)
    return [
        # ── CR-063 C3 · FIRE IS PRICED PER SIZE AND THE OTHER FOUR ARE NOT ──
        # A flat schedule states ONE `unit_price`, and fire has SEVEN: a 2" line
        # is $12.00 a month and a 6" line is $60.00. Handing fire the flat
        # payload is what made a shipped fire bill read `$0.00`.
        (
            fire_schedule_payload()
            if code == "fire"
            else _flat_schedule_payload(
                code,
                name=capacity_schedule_name(code),
                uom=_capacity_uom(code),
                # ── CR-062 E2-E5 · THE PO'S OWN FIGURES, PER SERVICE ────────────
                # This was ONE constant, `fixture.CAPACITY_UNPRICED = "0"`, for
                # every capacity service alike. It is now a price per service —
                # solar $14.00/kW (the PO's own words), battery $3.00/kW, storm
                # water $4.50/ERU, broadband $0.10/Mbps — and `fire` alone keeps
                # the stored zero, because CR-063's service arrived after these
                # six were signed and no price for it has been put to the PO
                # (`OQ-1360`).
                #
                # ⚠ The UNIT above moved in the SAME commit and that is not a
                # coincidence: `CAPACITY_UOM`'s docstring required it, because a
                # price quoted per an invented unit is `DEF-497`. `_capacity_uom`
                # now REFUSES rather than defaulting to `month`.
                unit_price=fixture.CAPACITY_UNIT_PRICES[code],
            )
        )
        for code in fixture.CAPACITY_ESTATE_SERVICES
        if code in speaks
    ]


def _schedule_payloads() -> list[dict[str, Any]]:
    """One payload per schedule, for the estate THIS TENANT can be given.

    ⚠ **THE GATE WAS `_enabled("water")` / `_enabled("sewer")` /
    `_enabled("trash")` UNTIL `DEF-2397`, AND THOSE THREE LITERALS WERE THE
    DEFECT.** BR-RAT-024 refuses a disabled service and a fixture that ignored
    that would seed a tariff nobody could bill on — that reasoning is unchanged
    and is now enforced one level up, by `estate()`, which resolves the
    tenant's enabled set and its declared units into the SAME backbone metering
    and assets resolved. Asking the estate is strictly narrower than asking
    `_enabled`: a service the tenant sells but the fixture cannot build a
    register for is refused BY NAME instead of being priced into a plan whose
    units carry no meter.

    ⚠ **A WATER TENANT IS UNMOVED, BYTE FOR BYTE.** `estate_plan` picks water
    as the backbone whenever the tenant sells it — deliberately, and ahead of
    catalogue order, because every signed money figure this fixture reproduces
    is a water figure (GT-17 ❄️'s `$39.50` and `$15.80` stand on unit 0 drawing
    exactly 8 kgal). So on water the three payloads below are the three that
    were always built, in the same order, and `sewer`/`trash` ride alongside
    exactly as before.
    """
    plan = estate()
    speaks = set(plan.services)
    rows: list[dict[str, Any]] = []
    # ── CR-062 C1 · A USAGE SCHEDULE PER METERED SERVICE ────────────────────
    # This read `if plan.backbone is not None and plan.backbone != "water"` and
    # seeded ONE. A tenant selling electric + water got the water tiers and no
    # electric schedule at all, so even once electric had meters and readings
    # there would have been nothing to price them with and every electric line
    # would have been the `$0.00` of a service the plan prices nowhere.
    # Water keeps its own two schedules below (inclining tiers for residential,
    # a flat rate for commercial), unmoved, because those two are what carry
    # the ❄️ GT-17 figures.
    for metered in plan.metered:
        if metered.code == "water":
            continue
        # ── CR-062 E1 · ELECTRIC IS TIERED, NOT FLAT ────────────────────────
        # PO statement (7), verbatim: *"Electric $12.00 base kWh read - along
        # with base you will need rate schedule - Either Tiered or TOU"*. TOU
        # was considered and NOT chosen (CR-062 judgment 2): it needs three
        # registers per meter and the seeded estate plants one, so a TOU ladder
        # would seed a schedule no seeded meter could answer.
        #
        # ⚠ **THE NAME IS `backbone_schedule_name("electric")` AND IS UNCHANGED
        # ON PURPOSE.** `create_rate_schedule` is idempotent on
        # `(tenant, name, service)`, so renaming this row would not rename
        # anything — it would mint a SECOND electric schedule on every tenant
        # that already holds one, and the plan would then bind one of two. Only
        # the MODEL and the STRUCTURE change; a tenant provisioned before today
        # keeps its one row and gains the tiers.
        #
        # Worked: 800 kWh = 500 x $0.1100 + 300 x $0.1350 = $95.50, plus the
        # signed $12.00 base = $107.50.
        if metered.code == "electric":
            rows.append(
                {
                    "name": backbone_schedule_name("electric"),
                    "service": "electric",
                    "model": "tiered",
                    "uom": str(metered.uom),
                    "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                    "size_rows": sample_size_rows("electric"),
                    # `unit_price`, NEVER `rate` — `_validate_tiers`
                    # `_reject_unknown`s any other key and `create_rate_schedule`
                    # would raise VAL-002, failing the WHOLE rating seed block
                    # and every block behind it (`DEF-487`, which cost exactly
                    # that on the water draft row).
                    "structure": {
                        "tiers": [
                            {"from_qty": lo, "to_qty": hi, "unit_price": price}
                            for lo, hi, price in fixture.ELECTRIC_TIERS
                        ]
                    },
                }
            )
            # DEF-RAT-9842 — the same tiers under the commercial plan's own
            # schedule, which names `BASE-E-COM` ($48.00) where the residential
            # one names `BASE-E` ($12.00): a schedule names ONE base code.
            (res_name, _res), (com_name, _com) = backbone_plan_inputs(metered)
            if com_name != res_name:
                rows.append({**rows[-1], "name": com_name})
            # ── CR-062 ADDENDUM J4 · THE INDUSTRIAL ELECTRIC USAGE LINE ─────
            # PO ruling 2026-09-02, verbatim: *"for usage line use
            # $0.085/kWh"*. FLAT, not tiered: `[W] §1` states one energy rate
            # for the industrial tariff, and a ladder would be inventing tier
            # boundaries the workbook does not state.
            #
            # ⚠ **THE PO WAS SHOWN WHAT THIS LEAVES OUT AND CHOSE IT ANYWAY**,
            # which is why it is seeded rather than refused: `$0.085/kWh` is
            # the ENERGY half of an energy-plus-demand pair and the seeded
            # estate takes no demand read, so the demo does not charge the
            # `+ $11.00/kW`. At the seeded plant's 100 kW peak that is
            # **$1,100.00** a month the demo does not bill, on a bill of
            # **$4,770.00**. `fixture.INDUSTRIAL_DEMAND_PER_KW` records the
            # figure and is read by nothing, the posture `GAS_FLAT_PER_CCF`
            # has held since `OQ-303`.
            #
            # **Worked:** 54,000 kWh x $0.0850 = $4,590.00 of usage, plus the
            # signed $180.00 industrial base = $4,770.00 before taxes.
            rows.append(
                {
                    "name": SCHEDULE_ELECTRIC_IND,
                    "service": "electric",
                    "model": "flat",
                    "uom": str(metered.uom),
                    "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                    "size_rows": sample_size_rows("electric"),
                    "structure": {"unit_price": fixture.INDUSTRIAL_ELECTRIC_PER_KWH},
                }
            )
            continue
        rows.append(_backbone_schedule_payload(metered))
        # DEF-RAT-9842 — the same usage prices under the commercial plan's own
        # name, where that plan's base code differs (see
        # `backbone_commercial_schedule_name`). Today no non-electric backbone
        # does; this keeps the rule general rather than electric's alone.
        (res_name, _res), (com_name, _com) = backbone_plan_inputs(metered)
        if com_name != res_name:
            rows.append({**_backbone_schedule_payload(metered), "name": com_name})
    if "water" in speaks:
        rows.append(
            {
                "name": SCHEDULE_WATER_RES,
                "service": "water",
                "model": "tiered",
                "uom": fixture.WATER_UOM,
                "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                "size_rows": sample_size_rows("water"),
                "structure": {
                    "tiers": [
                        {"from_qty": lo, "to_qty": hi, "unit_price": price}
                        for lo, hi, price in fixture.WATER_TIERS
                    ]
                },
            }
        )
        rows.append(
            {
                "name": SCHEDULE_WATER_COM,
                "service": "water",
                "model": "flat",
                "uom": fixture.WATER_UOM,
                "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                "size_rows": sample_size_rows("water"),
                "structure": {"unit_price": fixture.COMMERCIAL_WATER_FLAT},
            }
        )
        # DEF-463 · the DRAFT row. `effective_from` is omitted DELIBERATELY —
        # `create_rate_schedule` reads its absence as "Save draft & exit" and
        # lands a version with a NULL effective date, which `schedule_state`
        # then derives as `draft` because nothing is in force. Giving it a date
        # would make it a fourth ACTIVE schedule and seed nothing new.
        #
        # Its structure is the water tiers uplifted for a 2027 filing, so the
        # row is a plausible thing to open rather than an empty shell — a draft
        # nobody could resume would not exercise BR-RAT-031's resume view.
        rows.append(
            {
                "name": SCHEDULE_WATER_FILING,
                "service": "water",
                "model": "tiered",
                "uom": fixture.WATER_UOM,
                "size_rows": sample_size_rows("water"),
                # ⚠ DEF-487 — THIS SAID `"rate": price` AND THE WHOLE RATING
                # SEED FAILED ON IT. `_validate_tiers` `_reject_unknown`s any key
                # outside (from_qty, to_qty, unit_price, season, size_class), so
                # `create_rate_schedule` raised VAL-002 and `apps/tenancy/
                # sample_data` recorded the rating block as `failed` — no sample
                # schedules, no sample plans, no sample taxes on a fresh tenant.
                # The two payloads above send `unit_price`; this one is now the
                # same. `rate` is what a PERSON calls that column, which is why
                # it read correctly to everyone who looked at it.
                "structure": {
                    "tiers": [
                        # ⚠ `unit_price`, NOT `rate` (DEF-487). This said `rate`
                        # for one commit and `_validate_tiers` accepts
                        # `unit_price`, so the WHOLE rating sample-data block
                        # failed and identity, metering, customers and billing
                        # then failed behind it with `BlockCannotRun` — "Load
                        # sample data" loaded nothing at all.
                        {"from_qty": lo, "to_qty": hi, "unit_price": price}
                        for lo, hi, price in fixture.WATER_2027_FILING_TIERS
                    ]
                },
            }
        )
    # `estate_plan` already refuses sewer unless the backbone IS water
    # (`_SEWER_NEEDS_WATER` — `CR-081` takes 90% of the WATER VOLUME and there
    # is no basis without one), so membership of `speaks` is the same
    # test the old `_enabled("sewer") and _enabled("water")` was making, decided
    # by the rule rather than restated here.
    if "sewer" in speaks:
        rows.append(
            {
                "name": SCHEDULE_SEWER,
                "service": "sewer",
                "model": "percent_of_service",
                "uom": fixture.WATER_UOM,
                "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                # DEF-2823 — NO `size_rows` and NO base: `service_size_classes`
                # rules sewer to have NONE — it is a share of the water usage
                # charge and reads no register — so `sample_size_rows("sewer")`
                # would return `[]` anyway and `configured_sizes_for` answers
                # with the single blank-size ladder, which is correct and not an
                # error. The base itself is `BASE-S` on the charge code.
                # BR-RAT-015 ❄️ SUPERSEDED / GT-17 ❄️ RE-SIGNED 2026-09-08
                # (`CR-081`) — **90 percent POINTS of the WATER VOLUME**, priced
                # at sewer's own `$5.0000` per water's unit.
                # `tariff_versions.percent` stores what the tenant typed; the
                # rate is stored as `flat` stores one, a single 0→∞ rate tier
                # (BR-RAT-032), which is what `_validate_structure` builds from
                # `unit_price` here.
                #
                # ⚠ It read `{"percent": …, "basis_service": "water"}` and NO
                # rate until that date, because 40% of the water MONEY needed
                # none. Sewer has never had a rate on any tenant; this is the
                # first one.
                #
                # ⚠ `CR-130-BRC07` (PO 2026-09-22) makes the BASIS a stated
                # choice — `'usage'` (a share of the water VOLUME) or
                # `'charge'` (a share of the water MONEY). The seed states
                # `'usage'` OUT LOUD rather than relying on the column default,
                # for the same reason `rating/0043` backfills every existing
                # row by name: ❄️ GT-17's $36.00 is the usage basis, and a
                # fixture that lets the default answer for it would go on
                # passing on the day somebody changed the default.
                "structure": {
                    "percent": fixture.SEWER_PERCENT_OF_WATER,
                    "basis_service": "water",
                    "percent_basis": fixture.SEWER_PERCENT_BASIS,
                    "unit_price": fixture.SEWER_RATE_PER_UNIT,
                },
            }
        )
    if "trash" in speaks:
        rows.append(
            {
                "name": SCHEDULE_TRASH,
                "service": "trash",
                "model": "flat",
                "uom": _trash_uom(),
                "effective_from": fixture.PERIODS[0]["start"].isoformat(),
                # DEF-2799/DEF-2823 — the size axis is trash's SEVEN asset
                # classes (three carts, four dumpsters): trash is UNMETERED and
                # R3 still runs on it where the assets carry a size class
                # (BR-RAT-090 — a 96-gallon cart may be priced differently from
                # a 35-gallon one). The base itself is `BASE-T` on the charge
                # code, never this retired column.
                "size_rows": sample_size_rows("trash"),
                # ── $15.00 PER CART (DEF-491 · OQ-303 CLOSED 2026-08-21) ─────
                # This priced `0.00` until 2026-08-21 under a comment saying
                # trash "is not measured". BR-RAT-090 had already made it
                # measured — by a COUNT of the unit's active carts rather than
                # by a register — and the PO had already stated the price:
                # *"they are bill 1 trash can $15 - for example if you have 3
                # you multiple by 3"*.
                #
                # **Worked, ratified: 3 carts × $15.00 = $45.00**; remove one
                # and the next bill is $30.00.
                #
                # ⚠ THE ZERO WAS A PLACEHOLDER THAT NAMED NO QUESTION, which is
                # why closing OQ-303 moved nothing for a day (DEF-491). Every
                # placeholder below now cites the OQ it waits on, at the line it
                # sits on.
                #
                # ⚠ THE $18.00 MONTHLY BASE IS UNCHANGED AND IS **OQ-317**. It
                # is a signed [W] §1 figure; whether it survives beside the
                # per-cart price was not ruled, so it is neither withdrawn nor
                # defended here. Seeded as it stands, a three-cart bill is
                # $18.00 + $45.00 = $63.00; if the PO retires the base it is
                # $45.00. The CART LINE is $45.00 either way.
                "structure": {"unit_price": fixture.TRASH_PER_CART},
            }
        )
    # ── DEF-3156 · THE CAPACITY COMPANIONS ──────────────────────────────────
    # LAST, and the order is the one thing this line decides: `_plan_payloads`
    # reads `schedule_ids` by NAME and not by position, and `create_rate_
    # schedule` is idempotent per `(tenant, name, service)`, so nothing here
    # depends on where these sit. They are appended rather than interleaved so
    # a water tenant's three payloads stay the three it always had, in the
    # order it always had them — the same guarantee `DEF-2397` gave.
    rows.extend(capacity_schedule_payloads(plan))
    return rows


def _trash_uom() -> str:
    """The unit the trash schedule's price is quoted PER — `cart` (BR-RAT-090).

    ⚠ **THIS FUNCTION READ TWO KEYS ITS OWN SEAM NEVER RETURNS (DEF-497).** It
    asked `declared.get("uom")` and `declared.get("code")`; `seams.billed_uom`
    returns `billed_uom` / `primary_uom` / `conversion_factor` and nothing else,
    so both lookups missed on every input and the fallback was the ONLY
    reachable branch. The docstring said it *"carries the service's own declared
    UoM rather than one this file picked"* and it had never once done so — a
    guarantee stated in prose and delivered by no code (hard-won law 1).

    **It was harmless while trash priced `$0.00` per unit and it stopped being
    harmless the moment DEF-491 seeded `$15.00` per cart**, because the schedule
    then read *$15.00 per MONTH* against a quantity of 3 CARTS. CLAUDE.md rule 3
    was satisfied in form — a unit was present — and wrong in substance, which
    is the worse of the two failures because it reads as correct.

    So: the declared key is read correctly now, and **the fallback is `cart`**,
    not `month`. `cart` is the platform's own code (`lookup_defaults.json.uoms`
    seeds it scoped to trash), so nothing here invents a unit; and a tenant that
    HAS declared one still wins, which is what this function was always for.
    """
    declared = seams.billed_uom("trash") or {}
    return str(declared.get("billed_uom") or fixture.TRASH_UOM)


def _account_type_id(code: str) -> str:
    """The platform `account_types` id for a code, or REFUSE. DEF-452.

    ⚠ **REFUSES RATHER THAN SEEDING A NULL, and that is the whole point of the
    fix.** A plan with no customer class is not a cosmetic gap: `BR-RAT-108`
    derives the base from service → ACCOUNT TYPE → meter size and expects
    exactly one survivor, so a NULL class is a dimension the derivation cannot
    narrow on. Seeding one quietly is how DEF-452 lasted — it looks like data
    and behaves like an absence.

    The four rows are platform-seeded by migration 0003 before any tenant
    exists, so a missing one means the migration did not run, which is a broken
    install rather than a seeding choice.
    """
    account_type_id = seams.account_type_id_by_code(code)
    if account_type_id is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RAT-108",
            message_key="rating.sample.account_type_missing",
            params={"code": code},
        )
    return str(account_type_id)


# ── BR-RAT-890 · A SEEDED PLAN STATES WHEN IT STARTS (DEF-494) ──────────
# PO ruling 2026-08-28: a plan cannot be published without a start date. So
# a fixture that omitted one could no longer publish, and — the point of
# the rule — a fresh tenant must never reproduce the state the ruling
# removed.
#
# ⚠ **`PERIODS[0]["start"]`, THE SAME DATE THE SAMPLE RATE SCHEDULES
# ALREADY CARRY, AND THE SAMENESS IS THE WHOLE ARGUMENT.** The fixture's
# first BILLED period is June 2026 and every sample schedule version is
# effective from its first day; a plan dated any later would be a plan that
# does not cover the bills this fixture goes on to issue on it, and the
# ruled pricing path would refuse to explain 90 invoices the sample tenant
# ships already paid. It is also exactly what `rating/0024` computes for a
# tenant that predates this line, so a seeded tenant and a migrated one
# land on the same date by two different routes.
PLAN_EFFECTIVE_FROM = fixture.PERIODS[0]["start"].isoformat()


def _backbone_base_pair(service: str) -> tuple[str, str]:
    """`(residential, commercial)` monthly base for ONE metered service.

    ⚠ **ONE FUNCTION BECAUSE TWO CALLERS MUST NEVER DISAGREE.**
    `backbone_plan_inputs` writes `plan_services.base_charge` and
    `backbone_base_charge_codes` writes `BR-RAT-088`'s `is_base` charge code,
    and until 2026-09-28 `gather._base_charge_for` REFUSED the bill by name
    when those two stated different figures. They read ONE expression here so
    they cannot drift — `DEF-2823` is what it costs when they do ($180.00 on
    the plan against $12.00 on the code, a $168.00 gap nothing could see).

    ⚠ **THE REFUSAL IS GONE AND THE ONE EXPRESSION STAYS — `DEF-BIL-7170`.**
    PO 2026-09-28: *"we will never take default value from plan $8.0 - that is
    retired"*. Nothing a plan states can stop a bill any more, so the two
    cannot DISAGREE dangerously; what they can still do is make the plan SHOW a
    figure the bill does not charge, and the plan's column is still written and
    still shown (that half is explicitly not ruled). One expression is what
    keeps the display honest.

    `fixture.BACKBONE_BASE` stays the SOURCE for every signed figure — electric
    `$12.00`/`$48.00` and gas `$6.00`, both `[W] §1` — and
    `service_base_amounts` overrides ONLY where the workbook prices nothing.
    Today that is `thermal_heat` alone, which the fixture states as `("0", "0")`
    under the note *"Nothing signed"*. The researched figure is `$20.00`, it is
    a LANE JUDGMENT the Product Owner has not seen, and its evidence travels
    with it on the row.

    ⚠ **THE SAME FIGURE FOR BOTH CLASSES, which is what the fixture already
    said.** `BR-RAT-108` separates one service's two amounts by CLASS only where
    a source distinguishes them, and no municipal district-energy schedule
    readable from here states a residential figure at all — so inventing a
    second one would claim the research found a distinction it did not.
    """
    residential, commercial = fixture.BACKBONE_BASE.get(service, ("0", "0"))
    return (
        service_base_amounts.base_for(service, residential),
        service_base_amounts.base_for(service, commercial),
    )


def backbone_plan_inputs(
    metered: "fixture.MeteredService",
) -> tuple[tuple[str, str], tuple[str, str]]:
    """`((res schedule name, res base), (com schedule name, com base))` for ONE
    metered service — DEF-2397.

    The one place that says which schedule each of the two sample plans binds
    for a METERED service and what base charge it states, so the plan and
    `BR-RAT-088`'s charge code below cannot state different figures — `DEF-455`
    requires the two to *"agree to the cent by construction"* and `DEF-2823`
    is what it costs when they do not (`$180.00` on the plan against `$12.00`
    on the code, a `$168.00` gap nothing could see).

    Water keeps its own two schedules and its own two figures, unmoved.
    Every other metered service binds ONE schedule from both plans and takes its
    pair from `fixture.BACKBONE_BASE`, where each figure carries its `[W] §1`
    citation.

    ⚠ **IT TOOK THE `EstatePlan` AND ANSWERED ONCE PER TENANT UNTIL `CR-062` C1
    (2026-09-02).** It is now asked once per metered service, so an electric +
    water plan carries BOTH pairs — water's `$8.00` residential base beside
    electric's `$12.00` — which is what puts an electric base charge on the
    bill at all. That `$12.00` × 48 units is the `$576.00` a month `DEF-3224`
    was about — **the figure as MEASURED then, kept as the record of that
    defect. The estate is 50 units since `CR-062` addendum J3/J4, so the same
    arithmetic on today's fixture is `$600.00`.**
    """
    if metered.code == "water":
        return (
            (SCHEDULE_WATER_RES, fixture.WATER_BASE),
            (SCHEDULE_WATER_COM, fixture.COMMERCIAL_WATER_BASE),
        )
    service = str(metered.code)
    name = backbone_schedule_name(service)
    # `("0", "0")` for a metered service the workbook prices nowhere — the SEWER
    # precedent two branches below, and a stored zero rather than an omission
    # because an omission means "this size is not served" and stops the bill.
    residential, commercial = _backbone_base_pair(service)
    # DEF-RAT-9842 — a service whose two classes pay DIFFERENT bases gets a
    # second, commercial schedule, because a schedule names ONE base code.
    com_name = backbone_commercial_schedule_name(service) if residential != commercial else name
    return ((name, residential), (com_name, commercial))


def backbone_commercial_schedule_name(service_code: str) -> str:
    """`DEF-RAT-9842` — the COMMERCIAL plan's usage schedule for a backbone
    whose residential and commercial bases differ (today: electric, `$12.00`
    against `$48.00`).

    PO ruling 2026-10-06: the base is plan → rate schedule → the base code the
    schedule NAMES, and a schedule that names none bills `$0.00`. A schedule
    names exactly one code, so the one usage schedule both plans used to share
    could carry `BASE-E` or `BASE-E-COM` and never both — one class would lose
    its base. The usage prices are identical on both; only the named base
    differs. The residential schedule keeps `backbone_schedule_name`, unchanged,
    so no tenant that already holds it gains a duplicate.
    """
    return f"{SAMPLE_PREFIX} Commercial {_service_label(service_code).lower()} usage"


def schedule_base_codes() -> dict[str, str]:
    """`DEF-RAT-9842` — the base charge code each seeded schedule NAMES, by
    schedule name.

    PO ruling 2026-10-06, verbatim: *"You will take the code from plan -> rate
    schedule -> base charges - in that case if it is provided then you will take
    it if it is not provided then you will take it zeo"*. So a sample schedule
    that names nothing would bill every sample account a `$0.00` base. Each
    schedule here is bound by plans of ONE class-group, so it names the code
    this file already creates for that group (`BASE_CHARGE_CODES`,
    `backbone_base_charge_codes`, `capacity_base_charge_codes`) — the same code
    the retired class-narrowed pool used to pick, so every sample bill keeps
    its figure: residential water `$8.00`, commercial water `$15.00`,
    residential electric `$12.00`, commercial `$48.00`, industrial `$180.00`.

    This is OUR sample's configuration, never a choice made for a utility:
    nothing here touches a schedule that already exists.
    """
    names: dict[str, str] = {
        SCHEDULE_WATER_RES: "BASE-W",
        SCHEDULE_WATER_FILING: "BASE-W",
        SCHEDULE_WATER_COM: "BASE-W-COM",
        SCHEDULE_SEWER: "BASE-S",
        SCHEDULE_TRASH: "BASE-T",
    }
    for service, code in BACKBONE_BASE_CODE.items():
        names[backbone_schedule_name(service)] = code
        residential, commercial = _backbone_base_pair(service)
        if residential != commercial:
            names[backbone_commercial_schedule_name(service)] = f"{code}-COM"
    names[SCHEDULE_ELECTRIC_IND] = f"{BACKBONE_BASE_CODE['electric']}-IND"
    for service, code in CAPACITY_BASE_CODE.items():
        names[capacity_schedule_name(service)] = code
    return names


def _split_commercial_schedule_names() -> set[str]:
    """The commercial schedules `DEF-RAT-9842` adds beside a shared one."""
    return {
        backbone_commercial_schedule_name(service)
        for service in BACKBONE_BASE_CODE
        if len(set(_backbone_base_pair(service))) == 2
    }


def _services_already_priced_by_sample_plans() -> dict[str, set[str]]:
    """`{plan code: {service code}}` for the sample plans that already exist —
    so a replay never seeds a schedule nobody will bind (`DEF-RAT-9842`)."""
    tenant_id = core_tenancy.current_tenant_id()
    out: dict[str, set[str]] = {}
    for row in models.PlanRateSchedule.objects.filter(
        tenant_id=tenant_id,
        rate_plan__code__in=(PLAN_RESIDENTIAL, PLAN_COMMERCIAL, PLAN_INDUSTRIAL),
    ).values("rate_plan__code", "service__code"):
        out.setdefault(str(row["rate_plan__code"]), set()).add(str(row["service__code"]))
    return out


def industrial_plan_inputs(
    metered: "fixture.MeteredService",
) -> tuple[str, str]:
    """`(schedule name, base charge)` the INDUSTRIAL plan binds for ONE metered
    service — `CR-062` addendum J4.

    ⚠ **ELECTRIC IS THE ONLY SERVICE WITH AN INDUSTRIAL FIGURE, AND EVERY OTHER
    ONE FALLS BACK TO THE COMMERCIAL PAIR RATHER THAN TO ZERO.** `[W] §1` states
    an industrial base (`$180`) and an industrial energy rate (`$0.085/kWh`) for
    electricity and states nothing industrial about water, gas or thermal. A
    plant on this demo's water system is a commercial water customer, and
    saying `("0", "0")` instead would mean *this size is not served* and stop
    its bill (`CR-013` part 1 / `DEF-277`) — a refusal dressed as a price.

    **Worked:** the seeded plant's electric line is 54,000 kWh × `$0.0850` =
    `$4,590.00`, plus the `$180.00` base = `$4,770.00` before taxes; the
    `$12.00` residential base it would otherwise have carried is `$168.00` less,
    which is `DEF-2823`'s own gap said out loud.
    """
    if str(metered.code) == "electric":
        return (SCHEDULE_ELECTRIC_IND, fixture.INDUSTRIAL_ELECTRIC_BASE)
    return backbone_plan_inputs(metered)[1]


def _plan_description(plan: fixture.EstatePlan, base_charge: str, *, commercial: bool = False) -> str:
    """What the sample plan says it does, in a clerk's words — `B14` rule 32.

    ⚠ **THE WATER SENTENCES ARE RETURNED BYTE FOR BYTE.** They are the two this
    plan has carried since the fixture was written and this defect is not a
    copy change; a water tenant's `plans.description` must not move.

    For any other backbone the sentence names the service, the base a customer
    will actually be charged, and the fact that usage is not priced — in plain
    English, with the figure, and with **no rule id and no internal code**,
    which is `B14` rule 32 (*"no rule id or internal code in clerk-facing
    copy"*). The rule ids and the question live in `NOT_SEEDED` and in this
    module's docstrings, where an engineer reads them.

    ⚠ **AND A PLAN WITH NO METERED BACKBONE HAS ITS OWN SENTENCE SINCE
    `DEF-3156`, BECAUSE IT USED TO HAVE A HOLE IN IT.** With `plan.backbone`
    None the branch below resolved the catalogue row for `""`, so the
    description read *"Sample plan.  at a $0.00 monthly base; usage is not
    priced on this plan yet."* — two spaces where the service name goes, and a
    second clause about USAGE on a plan that prices none. It has been true of
    every trash-only tenant since `DEF-2414` and would have been true of every
    solar, broadband and battery tenant the moment they started billing, which
    is why this lane owns it. `B14` rule 32 asks for one sentence a clerk can
    read; a sentence with a gap in it is not one.
    """
    primary = plan.primary
    if primary is not None and primary.code == "water":
        shape = "Water at a flat rate per kgal" if commercial else "Water on inclining tiers"
        # ⚠ **BYTE FOR BYTE, AND THE EXTRA METERED SERVICES ARE NAMED AFTER IT
        # RATHER THAN INSIDE IT (`CR-062` C1).** A water tenant's two plan
        # descriptions are what every existing tenant carries and `B14` rule 32
        # gives a screen a description budget of one sentence per section, so
        # the sentence is unchanged and a second short one is added only when
        # there is something more to say.
        extra = [row.code for row in plan.metered if row.code != "water"]
        tail = (
            " " + ", ".join(_service_label(code) for code in extra) + " is metered too."
            if len(extra) == 1
            else (
                " "
                + ", ".join(_service_label(code) for code in extra[:-1])
                + f" and {_service_label(extra[-1])} are metered too."
                if extra
                else ""
            )
        )
        return (
            f"Sample plan. {shape}, sewer at 40% of the water usage charge, "
            "trash at $15.00 per cart with no monthly base." + tail
        )
    if primary is None:
        # Named in the utility's own vocabulary and never in a service code
        # (`B14` rule 31), and it says what these services are priced ON —
        # equipment recorded at the unit — because that is the honest
        # difference between them and a metered service, and it is the fact a
        # clerk needs when the line reads $0.00.
        priced = ", ".join(_service_label(code) for code in plan.services)
        return (
            f"Sample plan. {priced} — billed on the equipment recorded at each "
            "unit, with no monthly base."
        )
    return (
        f"Sample plan. {_service_label(str(primary.code))} at a "
        f"${Decimal(base_charge):.2f} monthly base; usage is not priced on this plan yet."
    )


def _service_label(service_code: str) -> str:
    """The service's name in the UTILITY's vocabulary, never its code.

    `B14` rule 31 — no internal identifier is the visible value of a field — and
    the fallback un-snake-cases the code so `storm_water` reads *storm water*
    rather than as a database identifier on a customer's plan. Extracted for
    `DEF-3156`: three call sites now need the same lookup and a copy of it would
    drift the first time one of them gained a fallback the others did not.
    """
    row = seams.service_catalog_row(service_code) or {}
    return str(row.get("name") or service_code.replace("_", " ")).strip()


def _plan_payloads(schedule_ids: dict[str, str]) -> list[dict[str, Any]]:
    """Plan-as-bundle (BR-RAT-025): one row per ticked service with its own base
    charge and its schedule. The base charges are the workbook's §1 figures.

    ⚠ **THE BACKBONE IS A PARAMETER SINCE `DEF-2397`, NOT THE LITERAL
    `"water"`.** `_services` below took a water schedule and a water base and
    wrote `"service": "water"`, so a tenant that sells electric got a plan with
    no services at all, `publish_plan` was never reached, and every account
    refused at activation.
    """
    estate_plan_ = estate()
    jurisdictions = [row["id"] for row in selectors.jurisdiction_list()]
    tax_rules = [{"jurisdiction": jid} for jid in jurisdictions]

    def _services(plan_class: str) -> list[dict[str, Any]]:
        # ⚠ **A CLASS AND NOT A BOOLEAN SINCE `CR-062` ADDENDUM J4.** It took
        # `commercial: bool`, and the moment a third class arrived a boolean
        # started ANSWERING WRONG rather than refusing — *"not commercial"* is
        # a perfectly well-formed reply that puts an industrial plant on the
        # residential ladder and bills it the `$12.00` household base.
        commercial = plan_class == "commercial"
        industrial = plan_class == "industrial"
        rows: list[dict[str, Any]] = []
        # ── CR-062 C1 / H1 · ONE PLAN SERVICE ROW PER METERED SERVICE ───────
        # This bound ONE — the estate's single backbone — so a plan on a tenant
        # selling electric + water priced water and said nothing about
        # electric. `gather._tariffs_for_plan` builds a tariff per row of
        # `plan_rate_schedules`, so a service missing HERE is a service missing
        # from every bill line, base charge included. That is the engine half of
        # `DEF-3224` and it needed no engine change: the engine has always
        # priced whatever the plan lists.
        for metered in estate_plan_.metered:
            (res_name, res_base), (com_name, com_base) = backbone_plan_inputs(metered)
            if industrial:
                name, base = industrial_plan_inputs(metered)
            elif commercial:
                name, base = com_name, com_base
            else:
                name, base = res_name, res_base
            if name in schedule_ids:
                rows.append(
                    {
                        "service": metered.code,
                        "base_charge": base,
                        "tariff": schedule_ids[name],
                    }
                )
        if SCHEDULE_SEWER in schedule_ids:
            # Sewer's own base is ZERO: the workbook's §1 base column names one
            # for electric and water and none for sewer, and a base nobody
            # signed is a base this fixture does not invent.
            rows.append(
                {
                    "service": "sewer",
                    # ⚠ **THE SAME CALL AS `BASE-S`, AND THAT IS THE POINT.**
                    # `gather._base_charge_for` REFUSES the bill by name when
                    # the plan and the charge code state different bases
                    # (`BR-RAT-088`'s "migration artefact" clause), and
                    # `DEF-2823` is what it costs when they drift. Both read
                    # `service_base_amounts`, so they agree to the cent by
                    # construction (`DEF-455`).
                    "base_charge": service_base_amounts.base_for("sewer", "0"),
                    "tariff": schedule_ids[SCHEDULE_SEWER],
                    # CR-039 wave C task 11 · BR-RAT-102's per-service escape.
                    # §A4 S2, verbatim: *"BASE-S $8.00 (flat everywhere — the
                    # multiplier does NOT touch sewer)"*. Written on BOTH plans
                    # even though only one states a factor, because the exemption
                    # is a fact about the SERVICE on this plan and not a
                    # consequence of the factor — a plan that gains a factor
                    # tomorrow must not silently start surcharging sewer.
                    "outside_city_exempt": "sewer" in fixture.OUTSIDE_CITY_EXEMPT_SERVICES,
                }
            )
        if SCHEDULE_TRASH in schedule_ids:
            rows.append(
                {
                    "service": "trash",
                    # ── OQ-317 CLOSED 2026-08-27, OPTION A — $0.00 (DEF-2490)
                    # This seeded `fixture.TRASH_FLAT` ($18.00) while OQ-317 was
                    # open, and OQ-317 closed on 2026-08-27: PO verbatim,
                    # *"option A is correct; where do you see the carts - they
                    # are not on accounts theya re on Units."* Option A retires
                    # the workbook's $18.00 monthly trash base outright, so a
                    # three-cart household is **$45.00** (3 x $15.00), not
                    # $63.00. The closure reached the registry, the decision log
                    # and BR-BIL-300 and did not reach this line for a day —
                    # DEF-491's own shape, one ruling later, which is why
                    # `TRASH_BASE` cites the question it answers AT the line the
                    # figure sits on.
                    #
                    # ⚠ **`"0"`, NOT AN OMISSION, AND THE DIFFERENCE IS A
                    # REFUSAL.** CR-013 part 1 (PO 2026-08-19) makes a BLANK
                    # base mean *this size is not served* and
                    # `gather._base_charge_for` stops the bill on it (DEF-277);
                    # a stored zero is a PRICE and prints `$0.00` (PO
                    # 2026-08-19). Retiring the base is *trash has no base*, not
                    # *trash is not served* — so it is stated as zero, exactly
                    # as sewer's own base already is two branches up.
                    "base_charge": fixture.TRASH_BASE,
                    "tariff": schedule_ids[SCHEDULE_TRASH],
                }
            )
        # ── DEF-3156 · A CAPACITY COMPANION IS A PRICED SERVICE ON THE PLAN ──
        # ⚠ **THIS IS THE LINE THE WHOLE DEFECT WAS.** The three schedules
        # above it existed for solar, broadband and battery the moment
        # `capacity_schedule_payloads` did; a schedule NO PLAN BINDS prices
        # nothing, `_plan_payloads` returned `[]` for a capacity-only tenant,
        # and every account refused at activation for want of a plan on its
        # unit (`BR-MET-040`). Bound here, a solar-only utility's 48 seats open.
        #
        # ⚠ **`"0"` FOR THE BASE, NOT AN OMISSION — the sewer and trash
        # precedent two branches up, and the difference is a REFUSAL.** A BLANK
        # base means *this size is not served* and `gather._base_charge_for`
        # stops the bill on it (`CR-013` part 1, `DEF-277`); a stored zero is a
        # price and prints `$0.00` (PO 2026-08-19). *No signed base* is what is
        # being said here, and `fixture.CAPACITY_BASE` says it — the same
        # constant `capacity_base_charge_codes` states on the `is_base` code, so
        # the two agree to the cent by construction (`DEF-455`).
        for code in fixture.CAPACITY_ESTATE_SERVICES:
            name = capacity_schedule_name(code)
            if name in schedule_ids:
                rows.append(
                    {
                        "service": code,
                        # ⚠ THE SAME CALL `capacity_base_charge_codes` MAKES —
                        # the plan and the `is_base` code are two statements of
                        # ONE figure and the bill is REFUSED when they differ.
                        "base_charge": service_base_amounts.base_for(
                            code, fixture.CAPACITY_BASE
                        ),
                        "tariff": schedule_ids[name],
                    }
                )
        return rows

    # The description quotes the FIRST metered service's base, which is what it
    # has always quoted — water's `$8.00` on a water tenant (`CR-062` judgment 4:
    # the plan is NAMED for the first service; every service is PRICED).
    primary_ = estate_plan_.primary
    res_base, com_base = (
        (backbone_plan_inputs(primary_)[0][1], backbone_plan_inputs(primary_)[1][1])
        if primary_ is not None
        else ("0", "0")
    )

    payloads: list[dict[str, Any]] = []
    residential = _services("residential")
    if residential:
        payloads.append(
            {
                "name": f"{SAMPLE_PREFIX} Residential",
                "code": PLAN_RESIDENTIAL,
                "effective_from": PLAN_EFFECTIVE_FROM,  # BR-RAT-890 / DEF-494
                "description": _plan_description(estate_plan_, res_base),
                "services": residential,
                "tax_rules": tax_rules,
                # ── CR-039 wave C task 11 · BR-RAT-102's FIRST GATE ──────────
                # `1.5`, r10's own figure on this very schedule: *"Premises
                # outside city limits multiply base and variable by 1.5 — set
                # on the premise record."* Until this line every seeded plan
                # read NULL (`DEF-515`), the premises was never consulted, and
                # the surcharge the engine has multiplied by since it was
                # written could not be reached from any tenant's data.
                #
                # ⚠ **ON THE RESIDENTIAL PLAN AND NOT THE COMMERCIAL ONE, ON
                # PURPOSE.** BR-RAT-102's first gate is what protects a utility
                # that does not price by jurisdiction — *"a plan stating NO
                # factor never consults the premises at all"* — and a fixture
                # where every plan surcharges cannot demonstrate it. The two
                # commercial suites therefore bill byte-identically to before,
                # and their premises flag is never read.
                "outside_city_factor": fixture.OUTSIDE_CITY_FACTOR,
                # ── DEF-452 · THE CLASS THE PLAN PRICES FOR ──────────────────
                # The codes have said `RES` and `COM` since the fixture was
                # written and the COLUMN was left NULL, so PLN-03 step 8 read
                # "CUSTOMER CLASS — Not set" on the plan the product ships and
                # BR-RAT-108's three-dimension base derivation — service →
                # ACCOUNT TYPE → meter size — had nothing to narrow on. The
                # worked example the PO ruled could not be produced from our own
                # data. Resolved through a seam because the id is a uuid minted
                # at migration time and cannot be mirrored the way the four
                # CODES are (see `seams.account_type_id_by_code`).
                "account_type_ids": [_account_type_id("residential")],
            }
        )
    commercial = _services("commercial")
    if commercial:
        payloads.append(
            {
                "name": f"{SAMPLE_PREFIX} Commercial",
                "code": PLAN_COMMERCIAL,
                "effective_from": PLAN_EFFECTIVE_FROM,  # BR-RAT-890 / DEF-494
                "description": _plan_description(estate_plan_, com_base, commercial=True),
                "services": commercial,
                "tax_rules": tax_rules,
                "account_type_ids": [_account_type_id("commercial")],  # DEF-452
            }
        )
    # ── CR-062 ADDENDUM J4 · THE INDUSTRIAL PLAN ────────────────────────────
    # **WHY A THIRD PLAN AND NOT A THIRD BASE ON THE COMMERCIAL ONE.**
    # `BR-RAT-108` separates one service's several amounts by ACCOUNT TYPE, and
    # `plan_services` carries ONE base per service per plan — so the `$180.00`
    # industrial electric base and the `$48.00` commercial one cannot live on
    # one plan row at all. `seed_demo` has had exactly this shape (`RES-STD` /
    # `COM-SM` / `IND`) since it was written; the SAMPLE seed simply never did.
    #
    # ⚠ **SEEDED ONLY WHERE IT PRICES SOMETHING DIFFERENT, WHICH IS ELECTRIC.**
    # On a water-only or capacity-only tenant this plan would be a byte-for-byte
    # copy of the commercial one under a third code — a plan a clerk has to read
    # and cannot tell apart, which is `B14` rule 32's own complaint. The
    # industrial SEAT still bills: `metering._plan_id_for` falls back to the
    # class the tenant actually holds.
    industrial = (
        _services("industrial")
        if any(row.code == "electric" for row in estate_plan_.metered)
        else []
    )
    if industrial:
        payloads.append(
            {
                "name": f"{SAMPLE_PREFIX} Industrial",
                "code": PLAN_INDUSTRIAL,
                "effective_from": PLAN_EFFECTIVE_FROM,  # BR-RAT-890 / DEF-494
                "description": (
                    "Sample plan. Electricity at a $180.00 monthly base and "
                    "$0.085 per kilowatt-hour of use."
                ),
                "services": industrial,
                "tax_rules": tax_rules,
                "account_type_ids": [_account_type_id("industrial")],  # DEF-452
            }
        )
    return payloads


#: The reason written onto the `rate_change_log` row every reconciliation
#: appends. BR-RAT-037 REQUIRES a reason on any content change to a published
#: plan and refuses without one, which is exactly right: a plan that gained a
#: priced service between two bill runs must say in its own filing record why.
RECONCILE_REASON = (
    "Sample data reloaded after this service was switched on at "
    "Settings -> Services & UoM (BR-TEN-063, DEF-1250)"
)


def _current_plan_services(plan_id: Any) -> list[dict[str, Any]]:
    """This plan's service rows RESTATED IN THE WRITE PAYLOAD'S OWN SHAPE.

    Read for `_reconcile_plan_services` below, so a reconciliation can go
    through `update_plan`'s replace-the-set and inherit every rule that guards
    plan content — BR-RAT-037's reason and version bump, the BR-RAT-111 filing
    record, the compliance log and the audit row — instead of growing a second,
    weaker write path. `_plan_tax_rules_payload` in `services.py` reads the tax
    set for the same reason and in the same shape; this is that pattern applied
    to the service set.

    ⚠ **EVERY FIELD IS CARRIED, NOT THE ONES THIS FIXTURE HAPPENS TO SET.** The
    payload is what gets written BACK, so a key omitted here is a value silently
    reset to its default on a plan somebody has since edited: a per-service
    revenue override (CR-008), a minimum, a `outside_city_exempt` exemption
    (BR-RAT-102) or a base the operator retyped. `_validate_plan_services`
    accepts exactly these keys, and each one below exists because dropping it
    would be a silent write.
    """
    tenant_id = core_tenancy.current_tenant_id()
    tariff_by_service = {
        str(row["service_id"]): str(row["tariff_id"])
        for row in models.PlanRateSchedule.objects.filter(
            tenant_id=tenant_id, rate_plan_id=plan_id
        ).values("service_id", "tariff_id")
    }
    rows: list[dict[str, Any]] = []
    for item in (
        models.PlanService.objects.filter(tenant_id=tenant_id, rate_plan_id=plan_id)
        .select_related("service")
        .order_by("service__sort", "service__code")
    ):
        row: dict[str, Any] = {
            "service": item.service.code,
            "currency": item.currency,
            "outside_city_exempt": item.outside_city_exempt,
        }
        # ⚠ A BLANK BASE IS NOT A ZERO (DEF-277 / CR-013 part 1) — it means
        # *this size is not served* and `gather._base_charge_for` refuses on it.
        # Sending `"0"` for a NULL here would convert a refusal into a $0.00
        # line on somebody else's plan, which is a money change this fixture has
        # no business making. Absent stays absent.
        if item.base_charge is not None:
            row["base_charge"] = str(item.base_charge)
        if item.gl_account_id is not None:
            row["gl_account_id"] = str(item.gl_account_id)
        tariff_id = tariff_by_service.get(str(item.service_id))
        if tariff_id:
            row["tariff"] = tariff_id
        rows.append(row)
    return rows


def _reconcile_plan_services(
    actor: Any, plan_id: Any, plan_code: str, wanted: list[dict[str, Any]]
) -> int:
    """Give an ALREADY-SEEDED sample plan the services it is missing — `DEF-1250`.

    ⚠ **THIS IS THE HALF OF BR-TEN-063 THAT WAS NEVER BUILT, AND THE DEFECT WAS
    A GRAIN MISMATCH RATHER THAN A MISSING RULE.**
    `seed_sample_records` is idempotent at TWO different grains and nobody
    noticed they were different: taxes, base charge codes, rate schedules,
    schedule versions and discounts are all keyed on their OWN natural key, so a
    replay adds an object that is genuinely new. **Plans are keyed on the plan's
    `code`** — so a plan that exists is skipped ENTIRELY, contents included, and
    a service it does not yet price can never arrive.

    **MEASURED on a booted tenant before this function existed**, provisioning
    water + sewer, loading the sample data, switching trash on at Settings and
    loading again: the replay DID add the trash rate schedule and the `BASE-T`
    charge code — those are keyed per object — and `SCW-RES` and `SCW-COM` still
    priced `water, sewer` and nothing else. So the tenant ended up holding a
    trash schedule no plan pointed at, which is the mirror image of the shape
    the Product Owner met on their own tenant: units badged for a service their
    plan states no schedule, no base charge and no billed unit for.

    **THIS DOES NOT WEAKEN BR-TEN-063 AND IT IS NOT A CHANGE TO IT.** The rule
    says a replay must not double anything. *"If the parent exists, add
    nothing"* is one implementation of that and it is strictly stronger than the
    rule — strong enough to also refuse what is genuinely absent. Reconciling
    the SET is the rule at the grain the rule is about: nothing doubles, because
    a service already on the plan is never written twice; and what is missing
    arrives. A second call writes nothing and returns 0, which is BR-TEN-063's
    own test.

    THREE GUARDS, and each one is a way this could have become a defect of its
    own
    ------------------------------------------------------------------------
    1. **SAMPLE PLANS ONLY.** BR-TEN-068 promotes a sample plan to the
       operator's own the moment a real account is on it (`is_sample` goes
       false). A promoted plan is somebody's live tariff and a fixture may not
       reprice it, so the caller filters on the tag and this refuses without it.
    2. **ADDITIVE, NEVER A REWRITE.** `update_plan` REPLACES the service set, so
       the payload is *the plan's current rows restated verbatim* plus the
       missing ones. Sending `_plan_payloads`' own list instead would be one
       line shorter and would silently revert every operator edit to the sample
       plan — a retyped water base, a different schedule pick, a BR-RAT-102
       exemption. That is BR-TEN-012's principle (a tenant that already priced
       something is not overwritten by a fixture) and it is the reason
       `_current_plan_services` carries every field rather than the ones this
       file happens to set.
    3. **THROUGH `update_plan`, NOT THE ORM.** Adding a priced service to a
       PUBLISHED plan is a rate change: BR-RAT-037 bumps `plans.version` and
       demands a reason, BR-RAT-111 writes the filing record, and CLAUDE.md rule
       7 wants the audit row. A direct `PlanService.objects.create` would give a
       utility a plan whose version and filing history do not mention the day it
       started charging for trash.

    Returns the number of service rows added.
    """
    # GUARD 1 — BR-TEN-068. Read from the ROW rather than from a projection:
    # `plan_row` does not serve `is_sample`, and a promoted plan is the
    # operator's own tariff that this fixture must not touch.
    if not models.RatePlan.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=plan_id, is_sample=True
    ).exists():
        return 0
    current = _current_plan_services(plan_id)
    present = {row["service"] for row in current}
    missing = [row for row in wanted if row["service"] not in present]
    if not missing:
        return 0
    services.update_plan(
        actor,
        plan_id,
        {
            "services": [*current, *missing],
            # BR-RAT-037 refuses a published plan's content change without one.
            # A draft ignores it, so it is sent unconditionally rather than
            # branched on a status that can change between two reads.
            "reason": RECONCILE_REASON,
        },
    )
    logger.info(
        "sample data: plan %s gained %s — the service(s) were switched on after this "
        "plan was published, so the idempotent replay had nothing to add them (DEF-1250)",
        plan_code,
        ", ".join(sorted(row["service"] for row in missing)),
    )
    return len(missing)


def enabled_services_no_published_plan_prices() -> tuple[str, ...]:
    """The tenant's ENABLED services that NO published plan prices, BY NAME.

    `DEF-1250`'s prevention (a): *"the S8 Services screen (or the seed summary)
    should say, per enabled service, whether any published plan prices it — the
    same comparison BR-BIL-300 now makes per account, made once per tenant so a
    utility sees it before a bill run does."*

    ⚠ **THE RECONCILIATION ABOVE DOES NOT MAKE THIS REDUNDANT, AND THE
    DIFFERENCE IS THE WHOLE POINT.** `_reconcile_plan_services` repairs the
    SAMPLE plans, on a replay, for the services the sample estate is shaped for.
    It cannot help a utility that switches gas on and never reloads the sample
    data, or one whose plans are entirely their own, or one that enables a
    service the fixture has no shape for at all. Those tenants sell something no
    plan prices and nothing tells them until a bill run does — which is
    `DEF-1060` arriving one layer earlier.

    A READ, never a write. It is reported by name (BR-TEN-060) and reported
    only: what an ENABLE should do to an already-published plan — add the
    service to every plan, or offer it — is a product decision and not a lane's,
    so this says what is true and changes nothing.
    """
    priced: set[str] = set()
    for row in selectors.plan_list(ListParams(per=1000)):
        if row.get("status") != "published":
            continue
        priced.update(item["service"] for item in _current_plan_services(row["id"]))
    # The tenant's OWN enabled set, in the platform catalogue's order — never a
    # literal list of the ten (BR-RAT-024 went from six to ten on 2026-08-16 and
    # the enumerations that named them one by one are still being found).
    return tuple(code for code in seams.enabled_service_codes() if code not in priced)


def seed_sample_taxes(actor: Any) -> int:
    """The two tax authorities spec §2 asks for, so the remittance report has
    more than one row.

    Created only when the tenant has NO tax rules of its own — a tenant that
    already priced its taxes is not overwritten by a fixture (BR-TEN-012). The
    rates are [F] `lookup_defaults.json`'s, the only signed pair in the repo.

    ⚠ AMENDED 2026-08-16 (DEF-166), AND BOTH HALVES WERE COSTING REAL MONEY ON
    THE DEMO TENANT
    --------------------------------------------------------------------------
    **1 · The docstring above said "only when the tenant has NO tax rules of its
    own" and the code did not do that.** It skipped per NAME, so a tenant
    provisioned with its own `Texas State` (6.25%) and `Local` (2%) gained the
    fixture's `State water tax` (6.25%) and `City utility tax` (2%) beside them.
    Measured on a booted stack: every seeded bill carried FOUR tax lines —
    2.97 + 2.97 + 0.95 + 0.95 on a 39.50 water bill — **16.5% of tax where the
    tenant's own rates say 8.25%**. Hard-won law 1 in its plainest form: the
    comment claimed the guarantee and nothing implemented it. The check is now
    on the SET: any tax rule at all means this fixture adds none.

    **2 · A tax the fixture did not create never got a liability account, and
    that is why NOT ONE BILL ISSUED (DEF-166).** `_map_liability_account` ran
    only inside the create loop. The two authorities provisioning had already
    made stayed unmapped, so at issue every one of the 95 bills broke with
    *"Local has no liability account, so this bill's tax line cannot be
    stamped"* (BR-BIL-010 / BR-BIL-069) and the whole run stayed in `draft`.
    Mapping is now a pass of its own over EVERY authority that has no account —
    the tenant's own included — because the ruling that mints one (PO
    2026-08-12, OQ-145/147: the ledger mints it and generates its code) is about
    an authority that NEEDS an account, not about who created the authority.
    It fills a NULL and changes no rate, so BR-TEN-012 is untouched.
    """
    existing = {row["name"] for row in selectors.tax_list(ListParams(per=1000))}
    known = {row["name"]: row["id"] for row in selectors.jurisdiction_list()}
    created = 0
    if not existing:
        for entry in fixture.TAX_AUTHORITIES:
            jurisdiction_id = known.get(entry["jurisdiction"])
            if not jurisdiction_id:
                # ⚠ 3 · A RUN NEVER WRITES INTO A REFERENCE CATALOGUE. This
                # branch used to pass `{"name": …, "level": …}` and `create_tax`
                # MINTED the jurisdiction, so a sample load added rows to
                # `tax_jurisdictions` — measured 2 → 4 on a provisioned tenant.
                # BR-TEN-058 forbids it outright (*"reference vocabulary is NOT
                # sample data"*) and `test_us_ten_019_tc4` asserts it. The
                # authority is SKIPPED and NAMED (BR-TEN-060) instead: a
                # jurisdiction is a thing the tenant's own reference data
                # declares, and a fixture that invents one is inventing where
                # money is remitted.
                logger.info(
                    "sample data: no tax jurisdiction named %r on this tenant, so the "
                    "%r authority is not seeded (BR-TEN-058 — a run never writes a "
                    "reference catalogue)",
                    entry["jurisdiction"], entry["name"],
                )
                continue
            services.create_tax(
                actor,
                {
                    "name": entry["name"],
                    "kind": "percent",
                    "rate": entry["rate"],
                    "jurisdiction": jurisdiction_id,
                },
            )
            created += 1
    _map_every_unmapped_authority(actor)
    return created


def _map_every_unmapped_authority(actor: Any) -> None:
    """Every tax authority on this tenant that has no liability account gets one.

    Idempotent by predicate (BR-TEN-063): a tax that already names an account is
    not touched, so a second load mints nothing. Unmappable authorities are
    REPORTED here and refused by name at issue — never silently left, because
    "the bills did not go out" with no reason attached is the failure DEF-166
    was.
    """
    for row in selectors.tax_list(ListParams(per=1000)):
        if row.get("liability_gl_account_id"):
            continue
        _map_liability_account(actor, row["id"], str(row.get("name") or "tax authority"))


def unmapped_tax_authorities() -> tuple[str, ...]:
    """The authorities that still have no liability account, BY NAME.

    Published so the sample-data run can say *why* no bill issued instead of
    reporting a count of drafts as a success (DEF-166). A read, never a write.
    """
    return tuple(
        str(row.get("name") or row["id"])
        for row in selectors.tax_list(ListParams(per=1000))
        if not row.get("liability_gl_account_id")
    )


def _map_liability_account(actor: Any, tax_id: Any, authority_name: str) -> None:
    """Give this authority its OWN 2200-series payable account, and map it.

    ⚠ WITHOUT THIS, NOT ONE BILL ISSUES — measured on a booted stack before it
    existed: all 48 June bills broke with *"City has no liability account, so
    this bill's tax line cannot be stamped"* (BR-BIL-010 / BR-BIL-069). The
    product is right to refuse: a guessed account remits money to the wrong
    government.

    It is done the way the PO ruled a human does it (2026-08-12, OQ-145/147):
    the LEDGER mints the account and GENERATES its code, and rating stores the
    mapping through Settings › Accounting's `set_tax_liability_account`, which validates that the account is
    this tenant's and live. Nothing is force-seeded into
    `apps/ledger/chart.py`, which deliberately carries no 2200 row because
    seeding one would invent an authority no tenant created (BR-TEN-037).
    """
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            account = seams.ledger_mint_tax_authority_account(
                name=f"Tax payable — {authority_name}", actor=actor
            )
    except Exception as exc:  # noqa: BLE001 — reported, never a guessed account
        logger.info("sample data: no liability account for %s (%s)", authority_name,
                    type(exc).__name__)
        return
    if account is None:
        logger.info(
            "sample data: the ledger publishes no create_tax_authority_account, so %s "
            "has no liability account and its bills will refuse at issue by name",
            authority_name,
        )
        return
    # DEF-RAT-9298 — through Settings › Accounting's door, not `update_tax`:
    # since 2.472.0 (PO 2026-10-03 on CR-008, "Pick it when you create the tax;
    # change it later only in Settings") `update_tax` refuses this field on a
    # live tax, and the refusal stopped a fresh utility's whole rating seed.
    services.set_tax_liability_account(actor, tax_id, {"liability_gl_account_id": str(account.id)})


def seed_sample_schedule_versions(actor: Any) -> int:
    """DEF-357 — give ONE schedule a real version history.

    **The seed wrote exactly one version per priced object**, so every Versions
    tab in the product rendered a single row, `SUPERSEDED` was always an
    em-dash, and the `DATED` banner made a claim about behaviour nothing in the
    fixture could exhibit. It also silently weakened every version test we own:
    *an assertion that billing picks the version in force on the usage date
    cannot fail when there is only one version to pick.*

    Three versions on the water schedule produce r10's three states at once —
    v1 (2026-06-01) **superseded**, v2 (2026-08-01) **current**, v3 (2027-01-01)
    **dated and not yet in force**.

    ⚠ **JUNE'S BILLS DO NOT MOVE, AND THAT IS THE POINT.** v2 starts on
    2026-08-01, so the June period (billed, `PERIODS[0]`) still prices on v1 —
    BR-RAT-007, and r10's own sentence for it: *"a January bill for December
    usage uses v3 even after v4 activates."* A fixture that changed a billed
    period would be re-pricing history, which is the thing dated versions exist
    to prevent.

    Idempotent (BR-TEN-063): versions are matched by `effective_from` before
    anything is written, so a second run writes nothing and returns 0.
    """
    written = 0
    index = {
        card["name"]: card["id"] for card in selectors.schedule_list(ListParams(per=1000))
    }
    tariff_id = index.get(SCHEDULE_WATER_RES)
    if tariff_id is None:
        # The water service is not enabled for this tenant, so there is no
        # schedule to version. Not a fault — `_schedule_payloads` skips it too.
        return 0

    tariff = models.Tariff.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=tariff_id
    ).first()
    if tariff is None:
        return 0
    existing = {
        version.effective_from.isoformat()
        for version in selectors.tariff_versions(tariff)
        if version.effective_from is not None
    }
    for effective_from, reason, tiers in fixture.WATER_VERSION_HISTORY:
        if effective_from in existing:
            continue
        # The fixture states the UPLIFT and derives the prices from WATER_TIERS,
        # so a change to the base tiers carries through instead of leaving three
        # literals here that are individually well-formed and quietly wrong.
        lo_mid, mid_hi, top = tiers
        # DEF-RAT-9842 — no `base_charge_code` key, so each version CARRIES
        # FORWARD the code v1 names (`BASE-W` on a utility set up from today).
        # The context stays for a utility seeded before today, whose v1 names
        # none: its schedule is not ours to name, and a replay must not stop.
        with services.seeding_schedules_without_a_named_base():  # DEF-RAT-9797
            services.create_rate_schedule_version(
                actor,
                tariff_id,
                {
                    "model": "tiered",
                    "uom": fixture.WATER_UOM,
                    "effective_from": effective_from,
                    # ⚠ DEF-2799 — EVERY VERSION, NOT JUST THE FIRST. The size axis
                    # live on the VERSION, so a history that carried it on v1
                    # alone would price June and refuse August and January — three
                    # versions, two of them dead at R3, and the Versions tab would
                    # look perfectly healthy.
                    #
                    # ⚠ **THE BASE IS NOT WRITTEN HERE ANY MORE (`DEF-2823`).**
                    # `BR-RAT-088` retired `tariff_versions.base_charge` and the
                    # S11 wizard has had no control for it since, so writing it
                    # configured this fixture in a way no real utility could copy.
                    # A version uplift changes the TIERS; the base belongs to
                    # `BASE-W` and moves there or nowhere.
                    "size_rows": sample_size_rows("water"),
                    # BR-RAT-037: a version is never written without a reason, and
                    # the reason is the sentence the Versions tab's CHANGE column
                    # shows. r10 authors it; so does this (DEF-280).
                    "reason": reason,
                    "structure": {
                        "tiers": [
                            {"from_qty": "0", "to_qty": "5", "unit_price": lo_mid},
                            {"from_qty": "5", "to_qty": "15", "unit_price": mid_hi},
                            {"from_qty": "15", "to_qty": None, "unit_price": top},
                        ]
                    },
                },
            )
        written += 1
    return written


#: ── BR-RAT-088'S BASE CHARGE CODES, ONE PER SEEDED SERVICE (DEF-455) ────────
#:
#: `BR-RAT-088` (CONFIRMED 2026-08-20) moved the base amount off the plan and
#: onto the CHARGE CODE — *"a plan displays the base rather than defining it"* —
#: and the FIXTURE was never moved with it. `grep` for `is_base` and `BASE-`
#: across this file returned ZERO, so PLN-03 step 4 read *"No base charge code
#: for this service"* for water, sewer AND trash on the tenant the product
#: ships. The gate was behaving correctly; it had no input.
#:
#: ⚠ **EVERY SEEDED SERVICE GETS ONE, AND THAT IS `DEF-528` AND NOT TIDINESS.**
#: `services._guard_base_charge_code` SELF-ACTIVATES per tenant: it returns
#: early while a tenant has NO `is_base` code and refuses the moment it has
#: SOME. So declaring one code arms a tenant-wide gate for every service — the
#: seed once declared `BASE-W` and not `BASE-E`, and `seed_demo` could not
#: create a single electric schedule on a fresh database. `_schedule_payloads`
#: seeds water, sewer and trash; all three are declared here, together, or none
#: is.
#:
#: ⚠ **THE AMOUNTS MIRROR THE PLAN'S OWN FIGURES AND INVENT NOTHING.** Water is
#: `$8.00` residential and `$15.00` commercial — `BR-RAT-108`'s own worked
#: example, named on this very tenant — which is exactly why that rule gave
#: `charges` a customer-class column: one service, two amounts, and a charge
#: code is per TENANT where the plan column it replaces was per PLAN. Sewer is
#: `$0.00` because the workbook's §1 base column names one for electric and
#: water and NONE for sewer, and a base nobody signed is not invented here.
#: Trash is `[W] §1`'s `$18.00` monthly base (still `OQ-317` beside the per-cart
#: price; seeded as it stands rather than withdrawn on a lane's reading).
#:
#: ⚠ **NO PER-SIZE ROWS, AND IT IS NOT A CHOICE — `charge_code_amounts` HAS NO
#: WRITER AT ANY LAYER.** `DEF-455` asks for the per-size amounts `BR-RAT-088`
#: works its example on, and `CHARGE_FIELDS` carries no `size_amounts` key:
#: `ChargeCodeAmount` has a model, a migration, a reader in
#: `resolution_catalogue`, a reader in `selectors` and NOTHING that writes it
#: outside a test. Filed as its own defect rather than reached past the
#: validated write path (🔒 sensitive path) — so these codes state one amount
#: for every size, which is what the plan column they mirror always did.
BASE_CHARGE_CODES: tuple[dict[str, Any], ...] = (
    {
        "code": "BASE-W",
        "name": "Water base charge — residential",
        "service": "water",
        "amount": fixture.WATER_BASE,
        # BR-RAT-108: one service, two amounts, separated by CLASS and never by
        # name — `BR-RAT-088`'s own docstring warns that name-matching two base
        # codes fails silently.
        #
        # ⚠ **THE LIST IS DERIVED SINCE `CR-062` ADDENDUM J3/J4 (`DEF-3282`),
        # and it used to read `["residential"]`.** A consumer category no
        # `is_base` code covers bills NOTHING — `resolution.resolve_charge_codes`
        # narrows on this very list — so the seeded municipal building issued
        # **0 invoices** while unit 0 issued 2, with nothing failing anywhere.
        # The classes each seeded plan bills for are declared once in
        # `fixture.PLAN_CLASS_ACCOUNT_TYPES`, beside the plan classes
        # themselves, so the code and the plan cannot drift apart.
        "applies_to_customer_classes": fixture.base_code_classes("residential"),
    },
    {
        "code": "BASE-W-COM",
        "name": "Water base charge — commercial",
        "service": "water",
        "amount": fixture.COMMERCIAL_WATER_BASE,
        # `[W] §1` states an industrial figure for ELECTRICITY and for nothing
        # else, so a plant on this demo's water system is a commercial water
        # customer and there is no industrial WATER code to collide with.
        "applies_to_customer_classes": fixture.base_code_classes("commercial"),
    },
    {
        "code": "BASE-S",
        "name": "Sewer base charge",
        "service": "sewer",
        # ⚠ `0` IS A PRICE, NOT AN ABSENCE (PO ruling 2026-08-19, *"print
        # $0.00"*). It mirrors what `_plan_payloads` already states for sewer.
        #
        # ⚠ **$9.00 SINCE 2026-09-07, AND IT IS A LANE JUDGMENT RATHER THAN A
        # SIGNED FIGURE.** The PO was asked for a sewer base and delegated the
        # research instead — *"you can research in amrket at Municiapl utility
        # in north amrica and put it there"*. `service_base_amounts` holds the
        # figure WITH ITS SOURCE (Town of Lexington, South Carolina, July 2025:
        # sewer monthly customer service charge $9.92 inside town) and states
        # in as many words that the PO has not seen it. The `"0"` stays as the
        # DEFAULT, so this line still says what it always said if the row goes.
        # ⚠ **CONFIRMED 2026-10-01 (PO: "Yes")** — *"Is $9.00 a month right for
        # the demo sewer base? Yes"* (decision log 2026-10-01). No longer a lane
        # judgment the PO has not seen.
        "amount": service_base_amounts.base_for("sewer", "0"),
        "applies_to_customer_classes": [],
    },
    {
        "code": "BASE-T",
        "name": "Trash base charge",
        "service": "trash",
        # ⚠ `0` FOR THE SAME REASON AS THE PLAN'S OWN TRASH BASE, AND IT MUST
        # MOVE WITH IT (DEF-2490). This block's docstring says the code and the
        # plan *"agree to the cent by construction"* — they are two statements
        # of one figure, and OQ-317 retired that figure on 2026-08-27. Leaving
        # `$18.00` here while the plan states `$0.00` would put the two sources
        # DEF-455 exists to keep identical $18.00 apart, on the one service
        # whose base was the thing in question.
        "amount": fixture.TRASH_BASE,
        "applies_to_customer_classes": [],
    },
)


def backbone_base_charge_codes(
    metered: "fixture.MeteredService",
) -> tuple[dict[str, Any], ...]:
    """`BR-RAT-088`'s `is_base` codes for ONE non-water metered service —
    `DEF-2397`.

    ⚠ **WITHOUT THESE NOTHING SEEDS AT ALL, AND THAT IS MEASURED RATHER THAN
    FEARED (`DEF-528`, critical).** `BR-RAT-088`'s guard is SELF-ACTIVATING per
    tenant: it returns early while the tenant holds no `is_base` charge, and the
    moment ONE exists it refuses every schedule whose service has no base code.
    So on a tenant that seeds a base code for one service and prices a second,
    the second's schedule is refused and the whole seed dies before premises,
    accounts or bills. **The rule that follows is `DEF-528`'s own sentence: a
    base charge code is seeded for EVERY service this seed prices, or for
    none.** This function is the "every" half for the four backbones
    `BASE_CHARGE_CODES` does not name.

    ⚠ **GATED ON THE ESTATE'S OWN METERED LIST, NOT ON `_enabled`.** A service
    the tenant has switched on but the estate cannot shape — no declared unit,
    or a register/billed pair no factor reconciles — is PRICED NOWHERE, and
    declaring `BASE-E` for it would be a base code for a service with no
    schedule: harmless to the guard, misleading on S12, and a figure nobody
    could trace to a plan. ⚠ **THE ALL-TEN TENANT MOVED HERE ON 2026-09-02
    (`CR-062` C1) AND THE MOVE IS THE FIX.** It used to get ONE metered service
    and four refusals, so electric, gas and thermal were enabled and unpriced;
    it now gets all four metered services, all four schedules and all four base
    codes — which is the whole point of the change.

    Two codes for electric and one for gas, and that asymmetry is `[W] §1`'s
    rather than a choice: the workbook states an electric base for Residential
    Standard (`$12`) and for Small Commercial (`$48`) — `BR-RAT-108` separates
    one service's two amounts by CLASS and never by name — and states a single
    Gas add-on base (`$6`) naming no class.
    """
    # ⚠ **CR-062 C1 — `backbone_base_charge_codes` NOW ANSWERS FOR ONE METERED
    # SERVICE AND `_all_metered_base_charge_codes` BELOW WALKS THEM ALL.** It
    # used to read `plan.backbone` and answer for the estate's single service.
    service = str(metered.code)
    if service == "water":
        return ()
    code = BACKBONE_BASE_CODE.get(service)
    if code is None:  # pragma: no cover — every METERED_ESTATE_SERVICE is mapped
        return ()
    label = _service_label(service)
    residential, commercial = _backbone_base_pair(service)
    if residential == commercial:
        # ONE figure, no class named by the workbook, so ONE unscoped code —
        # exactly the shape `BASE-S` and `BASE-T` already have. Scoping it to
        # both classes would say the workbook distinguishes them; it does not.
        return (
            {
                "code": code,
                "name": f"{label} base charge",
                "service": service,
                "amount": residential,
                "applies_to_customer_classes": [],
            },
        )
    rows = (
        {
            "code": code,
            "name": f"{label} base charge — residential",
            "service": service,
            "amount": residential,
            # BR-RAT-108: one service, two amounts, separated by CLASS and never
            # by name — `BR-RAT-088`'s own docstring warns that name-matching two
            # base codes fails silently.
            #
            # ⚠ **DERIVED SINCE `CR-062` ADDENDUM J3/J4 (`DEF-3282`)** — see
            # `BASE_CHARGE_CODES` above: a class no base code covers bills
            # nothing at all, silently, and it was measured.
            "applies_to_customer_classes": fixture.base_code_classes("residential"),
        },
        {
            "code": f"{code}-COM",
            "name": f"{label} base charge — commercial",
            "service": service,
            "amount": commercial,
            # `industrial` rides this code on every service EXCEPT electric,
            # which has its own industrial base below. Two codes claiming one
            # account is `DEF-468`'s refusal by name, not a preference.
            "applies_to_customer_classes": fixture.base_code_classes(
                "commercial", industrial_code_exists=(service == "electric")
            ),
        },
    )
    if service != "electric":
        return rows
    # ── CR-062 ADDENDUM J4 · A THIRD ELECTRIC BASE, FOR A THIRD CLASS ───────
    # ⚠ **THIS IS THE CODE HALF OF `DEF-2823` AND IT MUST AGREE WITH THE PLAN
    # TO THE CENT** — `DEF-455`'s own requirement, and `DEF-2823` is what it
    # costs when it does not: `IND` stated `$180.00` on `plan_services
    # .base_charge` while the only `is_base` electric code stated `$12.00`, a
    # `$168.00` gap nothing could see because the live path read the plan and
    # the ruled chain read the code. Both figures come from
    # `fixture.INDUSTRIAL_ELECTRIC_BASE` here, so they cannot disagree.
    #
    # The code STRING is `seed_demo`'s (`BASE-E-IND`), not a new one: that
    # letter set has named this charge on the demo tenant since `DEF-2823` was
    # fixed, and `create_charge` is idempotent on `code`, so a second spelling
    # would leave a tenant holding both.
    return (
        *rows,
        {
            "code": f"{code}-IND",
            "name": f"{label} base charge — industrial",
            "service": service,
            "amount": fixture.INDUSTRIAL_ELECTRIC_BASE,
            "applies_to_customer_classes": fixture.base_code_classes("industrial"),
        },
    )


def capacity_base_charge_codes(plan: fixture.EstatePlan) -> tuple[dict[str, Any], ...]:
    """`BR-RAT-088`'s `is_base` codes for the CAPACITY companions — `DEF-3156`.

    ⚠ **WITHOUT THESE THE CAPACITY SCHEDULES CANNOT ACTIVATE AND NOTHING SEEDS
    AT ALL — the `DEF-528` failure, one service group over.** `_guard_base_
    charge_code` refuses to activate a schedule for a service holding no
    `is_base` charge whenever the tenant has adopted declared base codes **or**
    the ruled chain states the base, and `SBH_BILLING_RESOLUTION_STEPS` ships
    `R3,R4`, so the second half is true on every deployment as shipped
    (`DEF-2923`). On a water tenant the first half is true as well, because
    `BASE-W` exists. Either way a solar schedule with no `BASE-SOL` refuses,
    the rating block records `failed`, and identity, metering, customers and
    billing fall over behind it with `BlockCannotRun` — *"Load sample data"*
    loading nothing at all.

    ⚠ **GATED ON THE ESTATE'S OWN SERVICE LIST, NOT ON `_enabled`, AND THE
    DIFFERENCE MATTERS ON THE ALL-TEN TENANT** — the same reasoning
    `backbone_base_charge_codes` states one function up. A capacity service is
    never refused by the one-register rule, so on the all-ten tenant all three
    ARE in `plan.services` and all three ARE priced; the gate is written this
    way so a service the estate refuses can never receive a base code for a
    schedule that does not exist.

    **ONE UNSCOPED CODE PER SERVICE, at `fixture.CAPACITY_BASE`** — the shape
    `BASE-S` and `BASE-T` already have. The workbook names no base for any of
    the three and names no customer class either, so scoping one to residential
    and commercial would say the workbook distinguishes them; it does not.
    """
    rows: list[dict[str, Any]] = []
    speaks = set(plan.services)
    for service in fixture.CAPACITY_ESTATE_SERVICES:
        if service not in speaks:
            continue
        # ⚠ **A NAMED REFUSAL AND NOT A BARE SUBSCRIPT — `DEF-3087`.** These two
        # lists grow independently: a service joins `CAPACITY_ESTATE_SERVICES`
        # in `core/sample_fixture` and its base code is typed HERE, and on
        # 2026-09-02 `fire` joined one and not the other. The bare
        # `CAPACITY_BASE_CODE[service]` then raised `KeyError: 'fire'` out of
        # the middle of `seed_sample_records`, which took down FOURTEEN of the
        # seventeen seeding blocks and left the tenant with no bills at all —
        # and a `KeyError` naming a service code says WHAT was missing and
        # nothing about why it mattered or where to put it.
        #
        # The twelfth service will meet this same gap, so the message is what
        # makes it a five-second fix instead of an afternoon.
        if service not in CAPACITY_BASE_CODE:
            raise KeyError(
                f"{service!r} is a capacity service in core/sample_fixture."
                "CAPACITY_ESTATE_SERVICES and has no base charge code in "
                "apps/rating/sample_data.CAPACITY_BASE_CODE. BR-RAT-088 puts the base "
                "amount on the CHARGE CODE, so without one the seeded plan cannot be "
                "activated: every account refuses "
                "customers.account.plan_required_at_activation and the tenant issues NO "
                f"bills. Add {service!r} to that map with a short code a person reads on "
                "S12 (the others are BASE-SOL, BASE-BB, BASE-BAT, BASE-SW, BASE-FIRE)."
            )
        rows.append(
            {
                "code": CAPACITY_BASE_CODE[service],
                "name": f"{_service_label(service)} base charge",
                "service": service,
                # ⚠ THE SAME CALL THE PLAN'S OWN ROW MAKES. `DEF-455`
                # requires the code and the plan to *"agree to the cent by
                # construction"*, and `DEF-2823` is what it costs when they do
                # not — $180.00 on the plan against $12.00 on the code, a
                # $168.00 gap nothing could see.
                #
                # ⚠ **`fixture.CAPACITY_BASE` IS THE DEFAULT NOW AND NOT THE
                # ANSWER (2026-09-07).** Storm water, broadband and battery each
                # carry a RESEARCHED municipal base in `service_base_amounts`;
                # **solar and fire are stated there at $0.00 deliberately** —
                # most municipal utilities levy nothing monthly for a
                # customer-owned array, and a fire line's monthly charge is the
                # DIAMETER charge this product already bills, so a base would
                # charge that connection twice AND move the going-live
                # customer's signed $60.00 warehouse. A capacity service this
                # file gains later that the other file does not name keeps
                # `CAPACITY_BASE`'s zero, unchanged.
                "amount": service_base_amounts.base_for(service, fixture.CAPACITY_BASE),
                "applies_to_customer_classes": [],
            }
        )
    return tuple(rows)


def seed_sample_base_charge_codes(actor: Any) -> int:
    """BR-RAT-088's declared base codes for the seeded services — `DEF-455`.

    ⚠ **THIS MOVES NO MONEY ON ANY TENANT, AND THE REASON IS WORTH STATING
    BECAUSE THE DEFECT'S OWN PREVENTION ASKS FOR SOMETHING THAT WOULD.**
    `DEF-455` says to seed these codes *"and STOP seeding
    `plan_services.base_charge` in the same commit so the two sources cannot
    both exist"*. **The second half cannot be done today and doing it would bill
    every seeded account `$0.00` for base.** The live bill path takes its base
    from `apps/billing/gather.py::_base_charge_for(service, plan_base,
    schedule_base)` — the PLAN's column — and `BR-RAT-088`'s R4 resolution runs
    only in `apps/billing/resolution_shadow.py`. `BR-RAT-120` (CONFIRMED
    2026-08-28, four days after `DEF-455` was filed) states it in as many words:
    *"the chain still has no production caller"*. Removing the plan's figure
    while the only reader of the code's figure is a shadow is `DEF-154` exactly
    — the schedule-versus-plan base that billed `$0.00` on every bill for weeks.
    So the codes are DECLARED and the plan's figure STAYS, the two agree to the
    cent by construction, and the retirement of `plan_services.base_charge`
    belongs to whoever gives R4 a production caller. Recorded in the decision
    log with this reasoning rather than decided silently.

    Idempotent by natural key (`code`), like every other block in this module.
    """
    written = 0
    existing = {row["code"] for row in selectors.charge_list(ListParams(per=1000))}
    # ⚠ ONE `estate()` FOR BOTH, so the backbone half and the capacity half can
    # never disagree about what utility this is (`DEF-2397`'s whole argument).
    plan = estate()
    for payload in (
        *BASE_CHARGE_CODES,
        # CR-062 C1 — every metered service, not just the first. A service with
        # a schedule and no `is_base` code cannot ACTIVATE that schedule
        # (`DEF-528`), so a second metered service without this line would take
        # the whole sample load down rather than merely go unpriced.
        *[
            row
            for metered in plan.metered
            for row in backbone_base_charge_codes(metered)
        ],
        # DEF-3156 — `DEF-528`: a base charge code is seeded for EVERY service
        # this seed prices, or for none. `capacity_schedule_payloads` prices
        # these three, so these three need one or their schedules cannot
        # activate and the whole load dies behind them.
        *capacity_base_charge_codes(plan),
    ):
        if payload["code"] in existing:
            continue
        if not _enabled(payload["service"]):
            # BR-RAT-024 — a service the tenant has not switched on gets no
            # schedule from `_schedule_payloads`, so it needs no base code and
            # declaring one would arm the guard for a service with no plan.
            continue
        # ── DEF-6440 · THE BASE RISES WITH THE CONNECTION SIZE ──────────────
        # `BR-RAT-088` works its own example on a base that VARIES by size — a
        # 5/8" water base at $8.00 and a 2" at $34.00 — and `BR-RAT-690` built
        # the writer for it on 2026-08-28. Neither reached this seed, so
        # `charge_code_amounts` held **0 rows on every tenant this product has
        # ever created** (counted on PostgreSQL 16 on 2026-09-07, across four
        # seeded utilities and a freshly provisioned eleven-service one), and a
        # utility opening CHG-02 step 2 met an empty table.
        #
        # ⚠ **THE LADDER IS ANCHORED ON THIS CODE'S OWN FIGURE, WHICH IS WHAT
        # MAKES IT SAFE TO SHIP.** The smallest size reproduces
        # `payload["amount"]` exactly, so every seeded bill is unchanged — and
        # it HAS to be — ⚠ **THOUGH THE CONSEQUENCE CHANGED ON 2026-09-28
        # (`DEF-BIL-7170`).** This said *"`gather._base_charge_for` REFUSES an
        # account by name when the charge code and `plan_services.base_charge`
        # disagree … one that broke the anchor would stop the bill."* The PO
        # retired the plan's figure — *"we will never take default value from
        # plan $8.0 - that is retired"* — so a broken anchor no longer stops a
        # bill. It puts a figure on the plan's screen that no bill charges,
        # which is quieter and is why the anchor is still built this way.
        #
        # ⚠ **EVERY RATIFIED SIZE IS PRICED, NOT ONLY THE ONES THE FIXTURE
        # HAPPENS TO PLANT (`DEF-MET-4496`).** An unpriced size is REFUSED and
        # never substituted (PO ruling 2026-08-28), so a partial ladder does not
        # fall back to a nearby size — it stops every connection it missed. The
        # seeded estate now spans all six electric bands and all four gas ones;
        # the ladder is built from the RATIFIED vocabulary rather than from the
        # estate for exactly that reason, so widening the fixture again cannot
        # outrun it.
        #
        # An empty list means *this service has no ladder* — `base_size_amounts`
        # states the two different reasons a service can be in that position —
        # and the flat amount is kept unchanged.
        ladder = base_size_amounts.size_amounts(payload["service"], payload["amount"])
        services.create_charge(
            actor,
            {
                "code": payload["code"],
                "name": payload["name"],
                "service": payload["service"],
                # A base is charged because a CONNECTION EXISTS (BR-RAT-080),
                # every cycle — which is what `recurring` means here.
                "charge_type": "recurring",
                "amount_rule": "flat",
                "effective_from": PRICE_HISTORY_EPOCH.isoformat(),  # CR-156-BRC10 — a seeded price has always applied
                # ⚠ CR-013 part 2 — A CODE HAS **ONE** BASIS, and both halves of
                # the product enforce it: `_validate_charge` refuses a payload
                # carrying a scalar AND a table (`rating.charges.
                # amount_and_size_table`), and `resolve_charge_codes` refuses the
                # BILL on billing day. So where the ladder prices this service
                # the TABLE is the amount, stated once per size, and the scalar
                # is omitted rather than set beside it.
                **({"amount": payload["amount"]} if not ladder else {}),
                **({"size_amounts": ladder} if ladder else {}),
                # ⚠ **THE FLAG THIS WHOLE BLOCK EXISTS FOR.** DECLARED, never
                # inferred from the code string (`Charge.is_base`'s own rule).
                "is_base": True,
                # ⚠ **NOT AUTO-APPLIED.** BR-RAT-117 makes a `recurring` +
                # `auto_apply` code land on every bill as an ADDITIONAL line and
                # says in terms that it *"does not move the base"*. A base that
                # was also auto-applied would be the $24.00-for-one-$12.00-base
                # double that BR-RAT-088 was written to forbid.
                "auto_apply": False,
                "taxable_default": True,
                "applies_to_customer_classes": payload["applies_to_customer_classes"],
            },
        )
        written += 1
    return written


#: ── THE APPLICATION PROCESSING FEE (`DEF-RAT-5424`) ────────────────────────
#:
#: ⚠ **`CC-REQFEE` EXISTED IN A FIXTURE AND IN NO TENANT'S CATALOGUE, AND
#: SINCE 2026-09-15 THAT IS A MONEY HOLE RATHER THAN AN UNTIDINESS.** Counted
#: on the demo tenant on 2026-09-16: **28 charge codes, and this is not one of
#: them**, while `core.sample_fixture.CR030_SERVICE_REQUESTS` quotes it by name
#: on the request a clerk takes `$25.00` cash against.
#:
#: Under the PO ruling of 2026-09-15 that counter fee posts **DR `1010`
#: Undeposited funds · CR `2400` Customer credit balances** the moment it is
#: taken, and is released to *the charge code's OWN revenue account* when the
#: request is approved or refused. `payments.counter_receipts._revenue_account_id`
#: resolves that account from **this table** and is right to refuse rather than
#: guess one — so with no row here the `$25.00` could be taken and held and
#: could never be earned: the liability stays in `2400` and `release_error`
#: names the setting to fix. A clerk is never blocked by it, which is exactly
#: why nothing surfaced it.
#:
#: **THE FIGURE IS NOT NEW.** `$25.00` is `BR-CUS-090`'s own worked case, the
#: one the PO ruled on: quoted `$130.00`, `$25.00` cash taken on receipt
#: `RCP-26-4471`, `$105.00` outstanding. It is copied here, not chosen.
#:
#: ⚠ **THE ACCOUNT IS NOT PICKED HERE EITHER.** `apply_default_gl_accounts`
#: below fills it from `ledger.chart.CHARGE_CODE_ACCOUNTS`, where every other
#: charge code's default lives — one home for the mapping, which is the whole
#: argument of `counter_receipts`' own docstring. `CC-REQFEE` starts at **4600
#: Connection & new-service fees**, beside `CONN`, `TAP`, `TEMP-SVC` and
#: `TRANSFER`: an application to take service is a new-service fee, and the
#: chart already has the category, so no numbering scheme was invented.
#:
#: ⚠ **NO `is_sample` TAG, AND IT IS STATED RATHER THAN WORKED AROUND.**
#: `BR-TEN-057` puts the tag on the OWNING row and `rating.Charge` has no such
#: column — the `BASE-*` family this file already creates is in the identical
#: position — so `remove_sample_records` will not sweep this code either.
#: Adding the column is a migration on rating's own table and belongs to the
#: lane that takes `BR-TEN-057` the rest of the way.
REQUEST_FEE_CHARGE_CODE: dict[str, Any] = {
    "code": "CC-REQFEE",
    "name": "Application processing fee",
    "charge_type": "one_time",
    "amount_rule": "flat",
    # BR-CUS-090's worked case, unmoved.
    "amount": "25",
    # A fee is never in the tax base — B4.2 / WE-1 / WE-6 / WE-11, the same
    # posture every other seeded fee code takes.
    "taxable_default": False,
    # ⚠ **NOT AUTO-APPLIED.** `BR-RAT-117` puts a `recurring` + `auto_apply`
    # code on every ordinary bill; this one is quoted on a service REQUEST by a
    # clerk and must never land on a customer's monthly bill.
    "auto_apply": False,
}


def seed_sample_request_fee_charge_code(actor: Any) -> int:
    """`CC-REQFEE`, the code the service-request fee path quotes by name.

    Idempotent by natural key (`code`), like every other block in this module:
    a tenant that already has the code — because they created it themselves —
    is left entirely alone, which is `BR-TEN-012`.

    ⚠ **A SAMPLE-DATA BLOCK AND NOT A PLATFORM DEFAULT, DELIBERATELY.** The 25
    codes in `apps/tenancy/fixtures/lookup_defaults.json` are the ones CR-066's
    table put to the Product Owner, and widening that list would change what
    every utility in the world is provisioned with. This code arrives with the
    SAMPLE service requests that quote it, on the same button, which is the
    same reasoning that puts the `BASE-*` family here rather than in the
    fixture.
    """
    if any(
        row["code"] == REQUEST_FEE_CHARGE_CODE["code"]
        for row in selectors.charge_list(ListParams(per=1000))
    ):
        return 0
    services.create_charge(
        actor,
        {**REQUEST_FEE_CHARGE_CODE, "effective_from": PRICE_HISTORY_EPOCH.isoformat()},
    )
    return 1


#: ── THE TWO OTHER CODES THE SAMPLE REQUEST QUOTES · `DEF-CUS-6416` ─────────
#: ⚠ **ADDED 2026-09-23, BECAUSE THE SERVER NOW PRICES A FEE LINE.** Until that
#: day `customers.service_request_service.add_fee_line` stored whatever
#: `unit_amount` it was handed, so the sample Okonkwo request quoted
#: `CC-EXPEDITE` at `$45.00` and `CC-METERTEST` at `$60.00` with no `charges`
#: row behind either — `payments/counter_receipts.py` recorded as much. The line
#: is now priced from the tenant's catalogue at the moment of the Add and a code
#: with no price is refused, so without these two rows the sample request would
#: quietly keep only its `$25.00` line and BR-CUS-090's worked case — **`$25.00`
#: taken against a `$130.00` quote, `$105.00` outstanding** — would vanish from
#: the demo with every test that seeds it green.
#:
#: **SAMPLE data, beside `CC-REQFEE` and for the same reason** — the PO's *"can
#: you add this in seeder data"* — never `lookup_defaults.json`. And **NOT in
#: `ledger.chart.CHARGE_CODE_ACCOUNTS`**: they start with no account, which is
#: exactly the unmapped branch `counter_receipts` documents and demonstrates.
REQUEST_QUOTE_SAMPLE_CHARGE_CODES: tuple[dict[str, Any], ...] = (
    {
        "code": "CC-EXPEDITE",
        "name": "Expedited handling",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "45",
        "taxable_default": False,
        "auto_apply": False,
    },
    {
        "code": "CC-METERTEST",
        "name": "Meter test on request",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "60",
        "taxable_default": False,
        "auto_apply": False,
    },
)


def seed_sample_request_quote_charge_codes(actor: Any) -> int:
    """`CC-EXPEDITE` and `CC-METERTEST`, idempotent by `code` like `CC-REQFEE`
    above — a tenant that already holds either is left alone (`BR-TEN-012`)."""
    held = {row["code"] for row in selectors.charge_list(ListParams(per=1000))}
    written = 0
    for row in REQUEST_QUOTE_SAMPLE_CHARGE_CODES:
        if row["code"] in held:
            continue
        services.create_charge(
            actor, {**row, "effective_from": PRICE_HISTORY_EPOCH.isoformat()}
        )
        written += 1
    return written


def seed_sample_records(actor: Any) -> int:
    """THE SEAM `apps/tenancy/seams.py` has documented since 2026-08-15.

    `actor` is the human who pressed the button on Settings (BR-TEN-064) — the
    sample path is never anonymous, because every service below writes an
    `audit_log` row naming who did it (CLAUDE.md rule 7).

    Returns the number of rows written. Idempotent (BR-TEN-063): every object is
    looked up by its natural key through this module's own selector before its
    create service is called, so a second run writes nothing and returns 0.
    """
    written = 0
    written += seed_sample_taxes(actor)
    # ⚠ **BEFORE THE SCHEDULES, AND THE ORDER IS `DEF-528`.**
    # `_guard_base_charge_code` refuses a schedule whose service has no
    # `is_base` code the moment the tenant has ANY, so the code for EVERY
    # service this seed prices must exist before the first
    # `create_rate_schedule` call — not after it, and never some of them.
    # ⚠ AMENDED FOR `DEF-2397`: this said *"all three seeded services"*, which
    # was true while the seed priced only water, sewer and trash. It prices the
    # tenant's own backbone now, so the set is whatever `estate()` resolved and
    # `backbone_base_charge_codes` is the half that covers a non-water one.
    written += seed_sample_base_charge_codes(actor)

    index = {
        card["name"]: card["id"] for card in selectors.schedule_list(ListParams(per=1000))
    }
    # ── DEF-RAT-9842 · EVERY SEEDED SCHEDULE NAMES ITS BASE CODE ────────────
    # PO ruling 2026-10-06: a schedule that names no base code bills a `$0.00`
    # base. This read *"they activate unnamed and are listed for a System
    # Admin"* (`DEF-RAT-9797`) while the class-narrowed pool still priced an
    # unnamed schedule; the ruling removed the pool, and a freshly seeded demo
    # utility measured 8 of 8 schedules naming none and 50 of 71 accounts
    # losing their base. So each schedule names the code its plan's class pays
    # (`schedule_base_codes`), and the electric pair that used to share one
    # schedule is two. No `seeding_schedules_without_a_named_base` here any
    # more: a schedule this file cannot name is refused, loudly, by the guard.
    code_ids = {
        row["code"]: row["id"] for row in selectors.charge_list(ListParams(per=1000))
    }
    named = schedule_base_codes()
    already_priced = _services_already_priced_by_sample_plans()
    for payload in _schedule_payloads():
        if payload["name"] in index:
            continue
        if payload["name"] in _split_commercial_schedule_names() and (
            payload["service"] in already_priced.get(PLAN_COMMERCIAL, set())
        ):
            # A replay over a tenant whose commercial plan already prices this
            # service on the schedule it was published with: that plan is not
            # re-pointed (BR-TEN-012), so a second schedule would be an orphan.
            continue
        body = dict(payload)
        code = named.get(payload["name"])
        if code is not None and code in code_ids:
            body["base_charge_code"] = str(code_ids[code])
        result = services.create_rate_schedule(actor, body)
        index[payload["name"]] = result["id"]
        written += 1
    # DEF-357: the schedules exist now, so they can be given a history.
    written += seed_sample_schedule_versions(actor)
    tagged_schedules = [
        sid for name, sid in index.items() if name.startswith(SAMPLE_PREFIX)
    ]
    _tag(models.Tariff.objects.filter(tenant_id=core_tenancy.current_tenant_id(),
                                      pk__in=tagged_schedules, is_sample=False))

    existing_plans = {
        row["code"]: row for row in selectors.plan_list(ListParams(per=1000))
    }
    for payload in _plan_payloads(index):
        row = existing_plans.get(payload["code"])
        if row is None:
            row = services.create_plan(actor, dict(payload))
            written += 1
        else:
            # ── DEF-1250 · THE PLAN ALREADY EXISTS, SO ITS SERVICE SET IS
            # RECONCILED RATHER THAN SKIPPED ────────────────────────────────
            # Every other block in this file is idempotent PER OBJECT and this
            # one was idempotent per PLAN, so a service switched on after the
            # plan was published could never reach it — the schedule and the
            # base charge code arrived on the replay and the plan went on
            # pricing what it priced the day it was published. Additive only,
            # sample plans only, through `update_plan`; see the function.
            written += _reconcile_plan_services(
                actor, row["id"], str(payload["code"]), list(payload["services"])
            )
        if row["status"] == "draft":
            # ── BR-RAT-890 (DEF-494) · A REPLAY OVER AN OLDER DRAFT ─────────
            # A plan created by THIS file now carries its date from creation,
            # so this branch is for a sample plan a tenant already had as an
            # undated draft — created before the ruling, or left half-set up.
            # `publish_plan` refuses it, and BR-TEN-063 makes the replay a
            # no-op, so without these three lines the seed would abort on that
            # tenant and never recover. Stated through `update_plan` so the
            # write keeps its audit row; a DRAFT needs no BR-RAT-037 reason.
            if not row.get("effective_from"):
                services.update_plan(
                    actor, row["id"], {"effective_from": PLAN_EFFECTIVE_FROM}
                )
            # BR-RAT-030: a plan lands as a DRAFT and is published explicitly.
            # An unpublished plan cannot be assigned, so an account seeder that
            # ran next would find nothing to put anybody on.
            services.publish_plan(actor, row["id"])
        _tag(
            models.RatePlan.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(), pk=row["id"], is_sample=False
            )
        )

    # ── CR-013 part 3 (2026-08-19): r10's five discounts ────────────────────
    # SENIOR, CAP, PAPERLESS, AUTOPAY and MILITARY-as-a-draft. LAST, and after
    # the plans, because `_attach_sample_plan_discounts` makes PAPERLESS and
    # AUTOPAY AVAILABLE on the residential plan — which is what r10 draws on
    # PLN-02's Discounts tab — and it can only do that once that plan exists.
    # ⚠ Availability is NOT a grant: no account is enrolled by this loader, and
    # nobody's bill moves by a cent (BR-RAT-069).
    written += discount_sample_data.seed_sample_discounts(actor)

    # ⚠ **BEFORE `apply_default_gl_accounts` BELOW, WHICH IS THE WHOLE POINT.**
    # A charge code created after the sweep lands with a NULL account and the
    # money it is taken for has nowhere to be earned — which is `DEF-RAT-5424`
    # exactly, one line later.
    written += seed_sample_request_fee_charge_code(actor)
    written += seed_sample_request_quote_charge_codes(actor)

    # ── CR-066 · AFTER EVERYTHING THIS LOADER CREATES ───────────────────────
    # `DEF-2386`: a FEE line resolves `charges.gl_account_id` and refuses the
    # whole bill when it is null, while a USAGE or BASE line resolves from the
    # SERVICE's designation and never looks at a charge code. Provisioning maps
    # the 23 platform codes, but the `BASE-*` family and the five sample
    # discounts are created HERE, minutes to weeks later, when a human presses
    # *Load sample data* — so without this line they land unmapped on a tenant
    # whose other codes are fine, which is the harder version of the same bug to
    # see.
    #
    # ⚠ **A BASE CODE'S ACCOUNT IS ITS SERVICE'S REVENUE ACCOUNT, DERIVED AND
    # NEVER LISTED.** `BASE-W`, `BASE-W-COM`, `BASE-S`, `BASE-T` and `BASE-FIRE`
    # are what a water/sewer/trash/fire tenant happens to hold; `BASE-E`,
    # `BASE-G`, `BASE-TH`, `BASE-SOL`, `BASE-BAT`, `BASE-BB` and `BASE-SW` are
    # what other utilities get, and the rule covers all twelve because
    # `ledger.selectors.default_gl_account_id_for_charge_code` reads the charge
    # row's own `service` and asks `revenue_account_id_for_service`.
    #
    # Idempotent and `BR-TEN-012`-safe: it fills a NULL and never replaces a
    # pointer a tenant has set, so a replay writes nothing.
    services.apply_default_gl_accounts(actor)

    # ── DEF-1250 prevention (a) · SAY WHAT THIS TENANT SELLS AND NO PLAN
    # PRICES ─────────────────────────────────────────────────────────────────
    # BR-TEN-060's report-by-name, pointed at a gap rather than at an unwired
    # seam. The reconciliation above repairs the SAMPLE plans for the services
    # the sample estate is shaped for; a utility that switches gas on, or whose
    # plans are entirely their own, still sells something no plan prices — and
    # under BR-BIL-300 that service now reaches every bill as a `$0.00` line
    # (OQ-670, PO 2026-08-27) rather than as a silence. A line of `$0.00` on
    # 48 bills is better than nothing at all and it is still not an ANSWER, so
    # the run says it once, here, where a person is already reading an outcome.
    unpriced = enabled_services_no_published_plan_prices()
    if unpriced:
        logger.info(
            "sample data: %s enabled on this tenant and priced by NO published plan — "
            "every account whose unit takes one of these bills it at $0.00 until a plan "
            "prices it (BR-BIL-300 / OQ-670, DEF-1250)",
            ", ".join(unpriced),
        )
    return written


def sample_plan_id(code: str) -> str | None:
    """The id of a seeded plan, for the modules that attach accounts to it.

    Published as a READ so customers never has to guess a plan by name or take
    the alphabetically first one — the wrong-cohort failure the brief names: a
    lane once seeded every unit onto a water-only Small Commercial plan by
    taking the first row it found, and every gate passed.
    """
    row = (
        models.RatePlan.objects.filter(tenant_id=core_tenancy.current_tenant_id(), code=code)
        .values("id")
        .first()
    )
    return str(row["id"]) if row else None


def residential_plan_id() -> str | None:
    return sample_plan_id(PLAN_RESIDENTIAL)


def commercial_plan_id() -> str | None:
    return sample_plan_id(PLAN_COMMERCIAL)


def industrial_plan_id() -> str | None:
    """`CR-062` addendum J4 — `None` on a tenant that sells no electricity.

    **`None` IS THE INTERESTING RETURN AND IT IS NOT A GAP.** The industrial
    plan is seeded only where it prices something the commercial plan does not,
    which is electricity; on a water-only utility a third plan would be a
    byte-for-byte copy under a third code, and a clerk cannot be asked to tell
    two identical plans apart (`B14` rule 32). The industrial SEAT still bills
    on such a tenant — `metering._plan_id_for` falls back to the class the
    tenant actually holds.
    """
    return sample_plan_id(PLAN_INDUSTRIAL)


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — a HARD delete of this module's `is_sample = true` rows,
    returning what it RETAINED and why.

    BR-TEN-066 (PO 2026-08-10) is partial-and-named: *"remove what is free,
    report the rest BY NAME"*. A plan a REAL account is on is retained, named,
    and its tag is dropped — which is BR-TEN-068's promotion arriving at the
    only moment it matters. Refusing the whole removal would let one attachment
    strand the entire set; detaching would silently edit the operator's own
    data.
    """
    tenant_id = core_tenancy.current_tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []

    for plan in models.RatePlan.objects.filter(tenant_id=tenant_id, is_sample=True):
        holders = selectors.plan_account_count(plan)
        if holders:
            # BR-TEN-068: a real account is on it, so it stops being sample data
            # and becomes the operator's own plan.
            plan.is_sample = False
            plan.save(update_fields=["is_sample", "updated_at"])
            retained.append(
                {
                    "label": plan.name,
                    "reason": (
                        f"{holders} account(s) are on this plan, so it is now yours rather "
                        "than sample data (BR-TEN-068)"
                    ),
                }
            )
            continue
        models.PlanChargeRule.objects.filter(tenant_id=tenant_id, rate_plan=plan).delete()
        models.PlanRateSchedule.objects.filter(tenant_id=tenant_id, rate_plan=plan).delete()
        models.PlanDepositRule.objects.filter(tenant_id=tenant_id, rate_plan=plan).delete()
        models.PlanService.objects.filter(tenant_id=tenant_id, rate_plan=plan).delete()
        plan.delete()
        removed += 1

    for tariff in models.Tariff.objects.filter(tenant_id=tenant_id, is_sample=True):
        if models.PlanRateSchedule.objects.filter(tenant_id=tenant_id, tariff=tariff).exists():
            retained.append(
                {
                    "label": tariff.name,
                    "reason": "a plan you kept still prices on this schedule",
                }
            )
            continue
        versions = list(
            models.TariffVersion.objects.filter(tenant_id=tenant_id, tariff=tariff)
        )
        for version in versions:
            models.RateTier.objects.filter(tenant_id=tenant_id, tariff_version=version).delete()
            models.TimeOfUseWindow.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).delete()
            models.RateSeason.objects.filter(tenant_id=tenant_id, tariff_version=version).delete()
            models.CapacityRate.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).delete()
            models.DemandRateConfig.objects.filter(
                tenant_id=tenant_id, tariff_version=version
            ).delete()
            version.delete()
        tariff.delete()
        removed += 1

    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    """How many sample rows this module is holding right now — the number the
    Sample data panel renders, read live rather than remembered from the run."""
    tenant_id = core_tenancy.current_tenant_id()
    return int(
        models.RatePlan.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + models.Tariff.objects.filter(tenant_id=tenant_id, is_sample=True).count()
    )


ZERO = Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane) · AMENDED 2026-08-28 by the DEF-1250 seed-reconciliation lane (a replay reconciles an already-seeded plan's SERVICE SET additively — BR-RAT-830; the enabled-but-unpriced report — BR-RAT-831; the trash base retired to $0.00 on OQ-317's closure — BR-RAT-832 / DEF-2490)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel already serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: [DEF-1250] the plan block is no longer idempotent PER PLAN but per SERVICE ROW — a replay ADDS the services an already-seeded SAMPLE plan is missing, additively, through `update_plan` so BR-RAT-037's version bump and reason, BR-RAT-111's filing record and the audit row all happen; it refuses on a plan BR-TEN-068 has promoted, and it restates every existing row verbatim so no operator edit is reset (BR-TEN-012) · [DEF-1250] `enabled_services_no_published_plan_prices` is a READ ONLY: what an ENABLE should do to an already-published plan is a product decision and is DEF-2492, open · [DEF-2490] the trash plan base and BASE-T read `fixture.TRASH_BASE` ($0.00, OQ-317 option A) and NOT `TRASH_FLAT` ($18.00), which stays as the RECORDED superseded [W] §1 figure read by nothing; it is a stored ZERO and not an omission, because a blank base means 'this size is not served' and stops the bill (CR-013 part 1 / DEF-277) · the SENIOR plan is NOT seeded — no signed figure states its discount and spec rule 7 forbids choosing one (OQ-240); it is reported by name on every run · trash's schedule prices $15.00 per CART (BR-RAT-090 · OQ-303 closed 2026-08-21; 3 carts = $45.00), AMENDED 2026-08-21 by DEF-491 from a 0.00 whose stated reason — "trash is not measured" — BR-RAT-090 had already retired; its $18 monthly base is UNCHANGED and whether it survives beside the per-cart price is OQ-317, OPEN · ⚠ THE CART LINE REACHES A BILL NOW AND THIS CLAUSE SAID IT COULD NOT — corrected 2026-08-28. It read 'the cart line cannot reach a bill yet: no carts are seeded (DEF-496), tenant_services.metered has no reader (DEF-495) and the billing seeder still deletes the trash line (DEF-161)'. ALL THREE ARE CLOSED: DEF-496 seeds four container_cart assets, DEF-495 gave the column a reader (tenancy.selectors.unmetered_service_codes) and DEF-161's designed-absence branch bills it, and DEF-1813 carried the observed count across the billing seam — 3 carts x $15.00 = $45.00 on the CR-019 walkthrough unit. What is still owed is DEF-2310: nothing WRITES tenant_services.metered from any screen, so the declaration is made by editing a row by hand · `is_sample` is stamped by a direct update, which is what BR-TEN-057 requires of the OWNING module and forbids of everyone else
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
