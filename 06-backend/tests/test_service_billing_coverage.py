# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S8, S62
# Change:   PO request 2026-09-01, verbatim: *"Sicne we are testing trash
#           service and its billing, similar way, can you test all non meter
#           services - SOlar, Battery, Strom water - we never tested them - we
#           tested electric, wter, sewar. […] hence ensure you create test
#           scenarios, data and test billing logic work for all cases"*
# Defect:   DEF-2414 (high, deployed) — "ticking Trash at signup produces ZERO
#           bills". Its own prevention line asks for exactly this file: *"a
#           provisioning run must assert that every service a tenant can select
#           at signup actually produces bills, because that is the assertion
#           nothing in the repo makes today."*  Also DEF-2409 (every service is
#           declared metered at signup) · DEF-2396 (four of the ten got no
#           sample estate at all) · DEF-3156 (a capacity service got the whole
#           estate and still had no tariff, so it billed nothing).
# Rules:    BR-RAT-024 (the catalogue is TEN services) · BR-MET-003 (a unit
#           takes only services the tenant SELLS) · BR-MET-040 (an account
#           derives its plan from the unit) · BR-TEN-056/060/063 (the sample
#           set · a gap is NAMED, never a silent zero · idempotent per tenant)
#           · BR-BIL-058 (the release gate records WHO authorised the run) ·
#           BR-RAT-015 ❄️ (sewer = % of the WATER usage charge) · BR-RAT-090
#           (trash is priced by a COUNT of the unit's carts) · CLAUDE.md rule 1
#           (tenant scoping) · rule 3 (a quantity carries its unit)
# Tests:    this file
# Impacts:  core/sample_fixture.py · apps/rating/sample_data.py ·
#           apps/metering/sample_data.py · apps/tenancy/services.py
# ───────────────────────────────────────────────────────
"""**DOES EVERY SERVICE A UTILITY CAN TICK AT SIGNUP ACTUALLY PRODUCE A BILL?**

Measured 2026-09-02 on PostgreSQL 16, one tenant per row through the real
signup entry point: **NINE of the ten do — electric, water, gas, trash, storm
water, thermal/heat, solar, broadband and battery.** The tenth is sewer, it
produces nothing, and it is NAMED below with the sentence it refuses with.

⚠ **IT WAS SIX EARLIER THE SAME DAY.** `DEF-3156` moved solar, broadband and
battery from zero to **96 issued bills each**: they had the whole estate
(`DEF-2396`, hours earlier) and no tariff, because `apps/rating/sample_data`
priced the metered backbone and the two water companions and had no payload for
a CAPACITY companion, so all 48 seats refused
`customers.account.plan_required_at_activation`.

⚠ **AND IT WAS ONE IN TEN NINE COMMITS EARLIER.** At `0ab55cba`, the same
thirteen tenants measured the same way, only water billed — and so the
municipal `water + sewer + trash` shape this whole sample fixture was written
for **billed nothing at all**, 8 of 17 seeding blocks failed. `DEF-2414`'s fix
landed in between and took trash from 0 to 96 and the municipal shape back to
95. That is what this file is for: the number moved, and without a test holding
it nobody could have said in which direction.

WHY THIS FILE EXISTS AND WHY IT IS NOT A UNIT TEST
--------------------------------------------------
`DEF-2414` was found the same day: a utility that ticked **Trash** at signup
received **zero bills** — 47 of 48 accounts refused, 8 of 17 seeding blocks
collapsed. The rating engine was correct at every step. The failure was in the
CHAIN in front of it: service point → asset → connection size → resolution. **No
unit test could see it**, because a unit test builds the rows it needs and this
defect is about the rows the PRODUCT builds for itself.

It was found by provisioning real tenants through the real signup entry point
and COUNTING THE BILLS. This file is that measurement, kept, and widened from
one service to all ten.

WHAT IT ASSERTS
---------------
One tenant per catalogue service, plus three realistic combinations, each
provisioned through `apps.tenancy.services.provision_tenant` — the same function
S114 commits — with the sample plant run inline. For each, whether any invoice
reached `issued` is compared against `RECORD` below; and where none did, the
seeding block that refused must have said WHY in the sentence `RECORD` names.

**`RECORD` IS A RECORD OF WHAT THE PRODUCT DOES TODAY, NOT AN APPROVAL OF IT.**
One of the ten is recorded as producing no bill — sewer, by design — with the
exact sentence the product refuses with and the reason it is correct. That is
deliberate and it is the whole design: the failure mode this file exists to stop
is a service quietly producing NOTHING, so a service that produces nothing must
be NAMED here, with its reason, and the test goes red the moment either half
moves.

⚠ **AND THAT COLUMN WAS EIGHT ROWS DEEP ON THE MORNING OF 2026-09-02.** Three
defects closed in one day emptied it — `DEF-2397` (electric, gas, storm water),
`DEF-2396` (thermal/heat, and the estate for the other three) and `DEF-3156`
(solar, broadband, battery). Every one of those was found by this file's own
`because` column and fixed by moving a row to `BILLS`; none of them was found by
a bill count.

⚠ **AND THE *REASON* MOVING IS ITSELF A RESULT — `DEF-2396`'S FIX MOVED FOUR
ROWS WITHOUT MOVING A SINGLE BILL COUNT.** Solar, broadband, battery and
thermal/heat used to fail with no estate at all and now fail at the same single
joint electric, gas and storm water fail at. A test that only counted bills
would have gone green through that change and reported nothing; the `because`
column is what makes it visible, and it is why that column exists.

**SO WHEN A LANE FIXES ONE, THIS TEST GOES RED — AND THAT IS IT WORKING.** Move
the row to `BILLS` and the assertion becomes "solar bills", which is what the
fix just made true. A test that kept passing silently through the fix could
never have caught the defect either. The failure message prints the WHOLE table
rather than the first divergence, so a lane that moves three services at once
sees three lines and not one.

⚠ **THAT ALREADY HAPPENED ONCE, BETWEEN THIS FILE'S FIRST RUN AND ITS LAST, AND
IT IS THE BEST DESCRIPTION OF HOW TO USE IT.** `DEF-2414` was fixed while this
was being written. Its fix moved exactly three rows — `svc-trash`,
`svc-municipal` and `svc-allten` — and no others, and the whole edit was three
`Expected(False, …)` becoming `BILLS`. Do the same for the next one.

⚠ **IT ASSERTS BILLS, NEVER A COLUMN.** The PO ruling of 2026-09-01 replaces
`TenantService.metered` with a three-way declaration — metered · share of
another service · capacity. Nothing here reads that column, on purpose: the
question the PO asked is *"does billing work"*, and a test pinned to today's
storage would have to be rewritten by the lane that lands the declaration —
exactly the moment it most needs to be trustworthy.

⚠ **THE PURE CASES BELOW WERE INVERTED ON 2026-09-01 AND THAT IS HOW THIS FILE
IS MEANT TO BE USED (`DEF-2396`).** `test_the_estate_plan_names_the_four_
services_it_cannot_shape` asserted, correctly, that four of the ten got no
premises. The lane that gave them premises met that assertion as a RED — its own
sentence, *"solar is being seeded into an estate that has no shape for it"* —
read the paragraph beside it, and replaced the case with the question asked of
all ten. Do the same for the next one.

⚠ **THE `identity_seam` FIXTURE IS DELIBERATELY NOT USED — `DEF-566`.** It stubs
`provision_owner`, so the tenant has no real user, and the billing block then
refuses on ATTRIBUTION (BR-BIL-058: *"this sample load has no attributable
user"*) BEFORE it can reach the real cause. Measured both ways on PostgreSQL 16:
with the stub the WATER tenant reported 0 bills, for a reason that has nothing
to do with water, and all ten services looked equally broken. Every figure in
`RECORD` was taken with the REAL seam. If a future lane adds `identity_seam` to
these signatures to "make it consistent with the other tenancy tests", this file
stops measuring anything.

PROVED ON POSTGRESQL 16, NOT ONLY ON THE DEFAULT SUITE (CLAUDE.md law 14)
-------------------------------------------------------------------------
The seeding blocks catch database errors and continue, which is the exact shape
law 14 says the in-memory-SQLite suite cannot judge. Every figure below was
measured with::

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    SBH_TEST_DB_NAME=test_sbh_svccov \\
    .venv/bin/python -m pytest tests/test_service_billing_coverage.py --reuse-db

and the file also runs in the default suite, so the next lane inherits it
without having to know that.

⚠ **IT COSTS FIFTEEN PROVISIONINGS — and the price WENT UP on 2026-09-02, so
budget for it.** This said *"thirteen provisionings — about eleven minutes"*.
Measured after `CR-062` group C: **35 minutes 56 seconds** on PostgreSQL 16, on
a box also running sibling suites. Two things moved it and both are the change
working: two rows were added for the PO's own signup shapes (`DEF-3223`), and
**every metered service a tenant sells now gets its own 48 meters and its own
four months of readings** — so `svc-allten` plants four registers per unit where
it planted one, and `svc-elec-water-sewer` plants two. The pure cases above it
still need no database and finish in milliseconds, so a lane that breaks the
estate plan learns it at once and never waits for the live run:
`-k "estate_plan or catalogue or backbone or realistic or everything"`.

⚠ **AND IT IS MEASURED AS SHIPPED.** `SBH_BILLING_RESOLUTION_STEPS` defaults to
`R3,R4` (`config/settings/base.py`) — the ruled pricing path — and nothing here
turns it off. A figure taken with the documented one-line rollback is a
different figure and is not the product.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from apps.tenancy.services import SERVICE_DEFAULT_UOMS
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _platform_catalogue() -> tuple[str, ...]:
    """The service codes, READ from the platform seed and never retyped.

    G47's own reasoning, one file along: *"a gate that carries its own copy of
    the list it is policing is the fifteenth copy, and would go green on the day
    the seed changed underneath it."* A service added to the catalogue arrives
    here as a MISSING ROW in `RECORD` — a red test — rather than as nine
    services quietly still passing.

    ⚠ **IT READ ONE FILE UNTIL 2026-09-02 AND THAT WAS THE WHOLE GUARANTEE
    FAILING QUIETLY (`CR-063`).** `0001_initial.py` has run on every database
    that exists and cannot gain a row, so an ELEVENTH service has to arrive in
    its own migration — and a reader pointed at `0001` alone would have reported
    a complete catalogue while `fire` had no row in `RECORD` at all. **The
    sentence above would still have been true and the promise it makes would
    have been false**, which is `DEF-524` exactly: a check whose hardcoded path
    outlives what it names reports PASS through real defects.
    **Every tenancy migration is scanned now**, in migration-number order, so a
    TWELFTH service needs no edit here either.
    """
    migrations = Path(__file__).resolve().parents[1] / "apps/tenancy/migrations"
    codes: list[str] = []
    for path in sorted(migrations.glob("[0-9][0-9][0-9][0-9]_*.py")):
        spec = importlib.util.spec_from_file_location(f"_tenancy_{path.stem}_for_coverage", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for attr in ("SERVICE_SEED", "FIRE_SEED"):
            for code, _name in getattr(module, attr, ()):
                codes.append(code)
    assert codes, f"no service seed found under {migrations} — the authority moved"
    return tuple(codes)


CATALOGUE: tuple[str, ...] = _platform_catalogue()


@dataclass(frozen=True)
class Expected:
    """What a tenant that ticked this set is expected to end up with.

    `bills` — did ANY invoice reach `issued`. That is the whole question the PO
    asked, and the only figure `DEF-2414` was ever measured in.

    `because` — a fragment that MUST appear in the detail of a FAILED seeding
    block when `bills` is False. It is what stops a zero being accepted for the
    wrong reason: a tenant that stops billing tomorrow for a brand-new cause
    goes red here even though its bill count did not move.

    `tracked_by` — the defect that owns the gap, so a reader of a red run knows
    where the work already is instead of filing it a second time.

    `bills_for` — **the service codes that must actually APPEAR on an issued
    bill.** `()` means not measured yet, and nothing is asserted.

    `sold_but_absent` — **the service codes this tenant SELLS that appear on no
    bill line at all.** Asserted, so the day the fixture stops dropping one this
    goes RED and the row moves, exactly as `Expected(False, …)` → `BILLS` does.

    ⚠ **THE LAST TWO WERE ADDED ON 2026-09-02 AND THEY EXIST BECAUSE `bills`
    ALONE IS BLIND TO THE THING THAT COST A SUPPORT ROUND TRIP (`DEF-3224`).**
    `bills` is one boolean per TENANT, so **a tenant that bills water perfectly
    and drops electric entirely scores as a PASS.** That is not hypothetical: a
    utility that ticks electric + water + sewer gets a WATER estate,
    `estate_plan` refuses electric as a second register, and electric therefore
    has no service point, no meter, no read and **no line on any invoice — not
    even its `$12.00` monthly base.** 48 units × `$12.00` is **`$576.00` a month
    that is simply not on the bills**, on a tenant where 95 invoices issue and 0
    of 17 seeding blocks fail. Every count in this file was green on it.

    **A COUNT OF INVOICES CANNOT SEE A MISSING SERVICE ON THOSE INVOICES.** That
    sentence is the whole reason these two fields exist.
    """

    bills: bool
    because: str = ""
    tracked_by: str = ""
    bills_for: tuple[str, ...] = ()
    sold_but_absent: tuple[str, ...] = ()


BILLS = Expected(bills=True)

# ── the refusal sentences, quoted from the product ──────────────────────────
#: `core/sample_fixture._NOT_IN_THE_SHAPE` — what solar, broadband and battery
#: refused with until `DEF-2396` was fixed on 2026-09-02.
#:
#: ⚠ **KEPT, AND NO ROW USES IT — DELIBERATELY, AND IT IS NOW UNREACHABLE FOR
#: EVERY ONE OF THE TEN.** `METERED ∪ COMPANION ∪ CAPACITY` covers the whole
#: catalogue, so this sentence now stands for the ELEVENTH service: a code added
#: to the platform catalogue and to no list in `core/sample_fixture` must be
#: refused BY NAME rather than silently produce an estate that does not speak
#: it. This is the string to check that refusal against.
NO_ESTATE_SHAPE = "this fixture has no estate shape for it"
#: `core/sample_fixture._NO_DEFAULT_UOM` — what thermal/heat refused with until
#: `DEF-2396`. `SERVICE_DEFAULT_UOMS` named six of the ten services and thermal
#: was not one of them, so the fixture refused rather than create a meter with a
#: blank unit (CLAUDE.md rule 3). **The refusal is unchanged and still fires for
#: any metered service whose tenant declares no unit**; what changed is that
#: thermal is no longer such a service.
NO_DECLARED_UOM = "declares no primary unit of measure for it"
#: `customers.services._require_unit_plan` (BR-MET-040) — what electric, gas and
#: storm water refused with until `DEF-2397` was fixed on 2026-09-01, and what
#: solar, broadband and battery refused with until `DEF-3156` was fixed on
#: 2026-09-02: the estate was built and then every one of the 48 seats refused,
#: because `apps/rating/sample_data` had no schedule payload for a CAPACITY
#: COMPANION and the unit therefore carried no rate plan.
#:
#: ⚠ **KEPT, AND NO ROW USES IT — DELIBERATELY, AND IT IS THE ONE OF THE THREE
#: MOST LIKELY TO COME BACK.** It is the sentence a service refuses with when it
#: HAS an estate and nothing prices it, which is the exact shape both of the
#: last two defects took and which nothing else in the repo counts: `rating
#: .sample_data.enabled_services_no_published_plan_prices` reports an
#: enabled-but-unpriced service as a LOG LINE on the sample run, never as a
#: failure. This is the string to check the next one against.
NO_PLAN_ON_THE_UNIT = "customers.account.plan_required_at_activation"
#: `core/sample_fixture._SEWER_NEEDS_WATER` — and CORRECT. Sewer is 90% of the
#: WATER VOLUME (`CR-081`, re-signed 2026-09-08; it was BR-RAT-015 ❄️'s 40% of
#: the water usage charge before) and this tenant sells no water, so there is no
#: basis for the percentage to be taken of. ⚠ **THIS READ `"BR-RAT-015"` UNTIL
#: 2026-10-01 (`DEF-BIL-8725`)** — the fixture's sentence moved to `CR-081` with
#: the re-sign on 2026-09-08 (`ace95d812`) and this fragment did not, so the pure
#: case below was red on wording for three weeks and hid the live case's red.
SEWER_HAS_NO_BASIS = "CR-081"


#: ── THE RECORD ──────────────────────────────────────────────────────────
#: Measured 2026-09-02 on PostgreSQL 16.13, in a clean `git worktree` with no
#: lane's uncommitted work in it, on a test database created from scratch
#: (`--create-db`, `DEF-2404`), `SBH_BILLING_RESOLUTION_STEPS=R3,R4` as shipped.
#: **NINE of the ten bill: electric, water, gas, trash, storm water,
#: thermal/heat, solar, broadband and battery.** The tenth is sewer, it produces
#: ZERO, and it is NAMED below with the sentence it refuses with.
#:
#: ⚠ **FOUR OF THE TEN RECEIVED NO ESTATE AT ALL UNTIL 2026-09-02 — that was
#: `DEF-2396`, and it is CLOSED.** Solar, broadband and battery had no shape in
#: `core/sample_fixture.estate_plan` (*"this fixture has no estate shape for
#: it"*) and thermal/heat was refused one step earlier for having no declared
#: primary UoM. Each produced **0 premises, 0 units, 0 service points, 0
#: accounts, 0 bills and 14 of 17 failed blocks**; each now produces **70
#: premises and 118 units**. Neither refusal was weakened — solar, broadband and
#: battery were given the shape the PO's `DEF-2409` ruling already describes
#: (CAPACITY: they ride on the unit with no register, exactly as trash does),
#: and thermal/heat was given the unit the platform catalogue already scopes to
#: it. **Thermal/heat then billed on `DEF-2397`'s own generalisation** — it is a
#: METERED service, so once it had a unit it became a backbone and
#: `_backbone_schedule_payload` priced it with no further change. The two fixes
#: met in the middle, which is what a service-shaped fixture is for.
#:
#: ⚠ **THE THREE CAPACITY SERVICES THEN STOPPED ONE STEP FURTHER ON, AND THAT
#: WAS `DEF-3156` — CLOSED THE SAME DAY.** They got the whole estate and were
#: refused `customers.account.plan_required_at_activation` on all 48 seats,
#: because `apps/rating/sample_data` priced the BACKBONE and the two water
#: companions and had no payload for a capacity companion — so no plan existed
#: for the unit to carry. It was filed apart from `DEF-2396`'s estate gap so
#: that a reader of either sees one fact and not two.
#:
#: **Measured on PostgreSQL 16.13 through `provision_tenant`, before and after:
#: each of the three went from 70 premises / 118 units / 48–49 service points /
#: 0 accounts / 0 rate schedules / 0 plans / 0 issued bills / 13 of 17 blocks
#: failed, to 70 accounts, 1 rate schedule, 2 plans and 96 ISSUED BILLS, 8 of
#: 17 blocks failed.** A capacity companion now gets a flat schedule, a plan
#: service row and a `BR-RAT-088` base charge code, the same three things trash
#: has had since `DEF-2414`.
#:
#: ⚠ **AND WHAT THEY BILL IS `$0.00` ON EVERY LINE, WHICH IS RULED AND NOT A
#: GAP — `BR-MET-108`, PO verbatim *"Bill it as zero"*.** No signed figure
#: prices solar, broadband or battery, `OQ-370` (which characteristic each has,
#: in what unit) is OPEN, and no capacity equipment is seeded — so
#: `BR-RAT-090`'s OBSERVED count is `0` and the price is a stored `0`. The line
#: reads `0 × $0.0000 = $0.00` and it is ON the document rather than in a
#: silence (`BR-TEN-060`). **This file asserts BILLS, so a `$0.00` total does
#: not move a row here**; what it does move is the 8 remaining failed blocks —
#: the refund and the payment plan need money to spread, exactly as they do on
#: the storm-water tenant, and the meters and reads are refused correctly
#: because a capacity service has no register by design.
#:
#: ⚠ **THREE OF THOSE FIVE MOVED ON 2026-09-01 AND THIS IS WHAT THAT LOOKED
#: LIKE — `DEF-2397`.** Electric, gas and storm water each received a COMPLETE
#: metered estate (70 premises, 118 units, 75 service points, 70 meters, 193
#: reads) and then **not one account**, because `apps/rating/sample_data` still
#: seeded schedules and plans for water, sewer and trash in LITERALS after
#: CR-039 wave A had made metering and assets service-shaped. 9 of 17 blocks
#: failed and all 48 seats refused
#: `customers.account.plan_required_at_activation`. Rating asks
#: `core.sample_fixture.estate_plan` the same question its two siblings ask now,
#: so the estate and the tariff are one shape.
#:
#: ⚠ **THIS SAID THOSE THREE BILL A BASE CHARGE AND A `$0.00` USAGE LINE, AND
#: `OQ-1290` IS NOW CLOSED (amended 2026-09-07, `DEF-RAT-4516`).** It read: the
#: workbook signs the monthly BASE for two of them — electric `$12.00`
#: residential and `$48.00` Small Commercial, gas `$6.00` — *"and signs no usage
#: price this fixture's single register can be charged on"*. **All three are
#: answered now.** Electric took a signed TIERED ladder and thermal `$0.045`
#: under `CR-062` E1/E6 (2026-09-02). Gas takes the workbook's own `$1.15` per
#: `ccf` (2026-09-07) — the old sentence's reason was *"against a register
#: reading therm"*, and that register has read `ccf` since `BR-TEN-1180` swapped
#: it on 2026-09-02 for exactly this purpose. **Storm water alone still totals
#: `$0.00`, and there it is RULED rather than missing** (`BR-MET-108`, PO: *"Bill
#: it as zero"*), so the fixture's own overpayment and payment-plan cases still
#: refuse on a storm-water estate — they need money to spread. **This file
#: asserts BILLS, so that refusal does not move a row here.**
#:
#: **sewer alone is refused BY DESIGN and correctly** (BR-RAT-015 ❄️). It is in
#: the table so the refusal stays a NAMED one rather than becoming a silent
#: zero the day somebody edits the estate plan.
#:
#: ⚠ **THE COMBINATION ROWS ARE WHY ONE BROKEN SERVICE IS NOT A SMALL PROBLEM.**
#: Nine commits before this figure was taken, `water + sewer + trash` — the
#: municipal utility this entire fixture was written for — billed NOTHING, and
#: so did all-ten, because trash rode in with the water. Water alone was fine
#: throughout. A per-service test would have called that a trash problem; the
#: product had stopped billing.
RECORD: dict[str, Expected] = {}

#: `(subdomain, services at signup)`, filled by `_case` beside its expectation
#: so a row can never be added to one and forgotten in the other. Subdomains are
#: lowercase and hyphenated — `_validate_signup` refuses an underscore with
#: `signup.subdomain_invalid`, which is why `thermal_heat` is `svc-thermalheat`.
CASES: list[tuple[str, tuple[str, ...]]] = []


def _case(subdomain: str, services: tuple[str, ...], expected: Expected) -> None:
    RECORD[subdomain] = expected
    CASES.append((subdomain, services))


# ── one tenant per catalogue service, in seed order ─────────────────────────
_case("svc-electric", ("electric",), BILLS)
_case("svc-water", ("water",), BILLS)
_case("svc-gas", ("gas",), BILLS)
_case("svc-sewer", ("sewer",), Expected(False, SEWER_HAS_NO_BASIS, "by design — BR-RAT-015"))
_case("svc-trash", ("trash",), BILLS)
_case("svc-stormwater", ("storm_water",), BILLS)
# ⚠ These four were `DEF-2396` — NO ESTATE AT ALL — until 2026-09-02, and each
# produced 0 premises, 0 units, 0 accounts, 0 bills and 14 of 17 failed blocks.
# Their estate now lands in full (70 premises, 118 units each). **Thermal/heat
# then BILLED, 95 issued** — it is METERED, so once it had a declared unit it
# became a backbone and `DEF-2397`'s own generalisation priced it.
#
# ⚠ **AND THE OTHER THREE STOPPED ONE STEP FURTHER ON — AT A TARIFF THAT DID
# NOT EXIST — UNTIL `DEF-3156` WAS FIXED THE SAME DAY.** They had the whole
# estate and no plan, so all 48 seats refused
# `customers.account.plan_required_at_activation`; the fix gives a CAPACITY
# COMPANION a schedule, a plan row and a base charge code the same way trash
# has had them since `DEF-2414`. **Each now produces 96 issued bills** — the
# same 96 a trash-only tenant produces, and every capacity line on them is
# `$0.00`, which is `BR-MET-108`'s ruled zero rather than a gap (see the record
# note above). These three moving is what took this file from six of ten to
# nine of ten.
_case("svc-solar", ("solar",), BILLS)
_case("svc-broadband", ("broadband",), BILLS)
_case("svc-thermalheat", ("thermal_heat",), BILLS)
_case("svc-battery", ("battery",), BILLS)
# ── CR-063 · THE ELEVENTH SERVICE, AND THE ONE A REAL CUSTOMER IS WAITING ON ──
# PO 2026-09-02: *"we have to do it ; curenlty we need it for one of the
# customer we want to go live"*. Fire is a CAPACITY companion that COUNTS its
# equipment — trash's arithmetic, not solar's — so it needs no metered backbone
# and no register, and `CAPACITY_ESTATE_SERVICES` is the one line that gives it
# an estate.
#
# ⚠ **`bills_for=("fire",)` AND NOT MERELY `BILLS`, AND THAT IS `DEF-3224`'S
# WHOLE LESSON APPLIED ON THE DAY THE SERVICE ARRIVED RATHER THAN MONTHS
# LATER.** `bills` is one boolean per TENANT, so a fire tenant that issued 96
# invoices with **no fire line on any of them** would score as a PASS here —
# which is exactly the state that put `$576.00 a month` of electric off the
# bills of a tenant where every count in this file was green. A count of
# invoices cannot see a missing service ON those invoices, and Fire is the one
# service in this table whose customer is real.
_case("svc-fire", ("fire",), Expected(bills=True, bills_for=("fire",)))


def _record_the_combinations() -> None:
    """Five real signup shapes, added after the singles so the table reads in
    catalogue order first.

    * **water + sewer + trash** is the municipal utility this whole fixture was
      written for and the shape `DEF-2414` was reported on.
    * **electric + gas** is the shape `DEF-795` was reported on — the tenant
      that signed up successfully and received nothing.
    * **all ten** is the PO's own question. It is the row that shows the
      backbone rule at work: the estate is metered in ONE service, so a utility
      that sells everything still gets a water estate and seven named refusals
      — and then bills nothing, because trash rode in with the water.

    ⚠ **THE LAST TWO WERE ADDED ON 2026-09-02 AFTER THE PO REPORTED THE SHAPE
    THIS FILE HAD NEVER MEASURED, AND THE CHOICE OF *WHICH* TWO IS THE POINT
    (`DEF-3223`).** The report was *"We tried to create tenant with Electric,
    Water and Sewer - no bill generated"*. Thirteen shapes were measured here
    and **the most ordinary combination a small utility would tick was not one
    of them.**

    A live row costs a whole provisioning — about **50 seconds** each, and
    thirteen of them is the eleven minutes this file's own note quotes — so the
    question is not *"which shapes exist"* (there are 1,013 non-empty subsets of
    ten services) but **"which shapes could produce a DIFFERENT BILL COUNT"**.
    `estate_plan` decides that on exactly three things, and every shape below is
    here because it is the first to vary one of them:

      1. **which backbone wins** — `METERED_ESTATE_SERVICES` is ordered
         `water, electric, gas, storm_water, thermal_heat` and the FIRST enabled
         one takes the estate, so a tenant that ticks electric first still gets
         a WATER estate;
      2. **whether a companion has its basis** — sewer needs the backbone to BE
         water (`BR-RAT-015` ❄️), trash does not;
      3. **whether a capacity service rides along** — solar, broadband and
         battery need no backbone and no register at all.

    * **electric + water + sewer** — `svc-elec-water-sewer`, **the PO's own
      shape**. It is the first row in this file where the backbone is a service
      the tenant did NOT tick first: water wins, sewer keeps its basis, and
      **electric is REFUSED and silently dropped**. `svc-elecgas` looks similar
      and is not: there the winner is the service the clerk ticked first, so a
      reader could never tell the two mechanisms apart.
    * **electric + trash + solar** — `svc-elec-trash-solar`, a companion AND a
      capacity rider on a **NON-WATER backbone**. Every trash and every capacity
      bill this file has ever recorded rode a WATER backbone (`svc-municipal`,
      `svc-allten`) or no backbone at all (`svc-trash`, `svc-solar`). Whether
      `apps/rating/sample_data` prices a rider when the backbone is electric had
      never been measured — and `DEF-2397` was precisely *"rating's sample
      fixture is still water, sewer and trash in literals"*, so a literal that
      survived is the live risk here. Both riders travel through that one
      untested joint, so they share a row rather than costing two.

    **AND HERE IS WHAT WAS DELIBERATELY *NOT* ADDED, because saying why is the
    half of this judgment that stops the next lane paying for it again.**
    `electric + sewer` (a tenant that bills while a service it SOLD is refused),
    `sewer + trash` (no metered backbone at all) and `gas + trash` are all real
    shapes with genuinely distinct ESTATES — and none of them can move a BILL
    COUNT that is not already recorded above: their bills come from a service
    this file already measures alone, and their refusals are decided by a PURE
    function. So they are asserted in **PART 1**, where they cost nothing, by
    `test_the_backbone_and_the_riders_are_decided_the_same_way_for_every_
    realistic_shape`. **A shape whose only new fact is a refusal belongs in the
    pure layer; a shape that could bill a different number belongs here.**
    """
    _case("svc-municipal", ("water", "sewer", "trash"), BILLS)
    _case("svc-elecgas", ("electric", "gas"), BILLS)
    _case("svc-allten", CATALOGUE, BILLS)
    # ⚠ **MEASURED 2026-09-02 ON POSTGRESQL 16, and the two rows say opposite
    # things — which is exactly why both were worth a provisioning.**
    #
    # `svc-elec-water-sewer` — 70 premises, 118 units, 151 service points, 70
    # accounts, **95 issued**, 0 of 17 blocks failed. **And electric is on NONE
    # of those 95 bills** (`DEF-3224`): water wins the estate, electric is
    # refused as a second register, and 48 units × `$12.00` of monthly base is
    # simply not there. Every count in this file was green on that tenant, which
    # is what `sold_but_absent` now exists to stop.
    #
    # `svc-elec-trash-solar` — 70 premises, 118 units, 173 service points, 70
    # accounts, **96 issued**, 0 of 17 blocks failed, and **all three services
    # reach a bill line.** That is the answer to the question this row was added
    # for: `apps/rating/sample_data` DOES price a companion and a capacity rider
    # when the backbone is ELECTRIC rather than water. `DEF-2397` was *"rating's
    # sample fixture is still water, sewer and trash in literals"*, so a literal
    # that survived would have shown up here as a zero. None did — and now the
    # fact is pinned instead of assumed.
    # ⚠ **THIS ROW MOVED ON 2026-09-02 AND THE MOVE IS THE WHOLE OF `CR-062`
    # GROUP C.** It read `bills_for=("sewer", "water")` with
    # `sold_but_absent=("electric",)` — a tenant issuing 95 bills, 0 of 17
    # blocks failed, every count in this file green, and **electric on none of
    # those bills**, not even its `$12.00` monthly base. That is `DEF-3224`, it
    # is `$576.00` a month across 48 homes, and the PO ruled it out: *"this is
    # not correct - you cannot drop electricty or gas"*. Electric moved from
    # `sold_but_absent` into `bills_for`, which is exactly what that field
    # exists to make visible — its own failure message says *"if that is a fix,
    # move it into bills_for"*.
    _case(
        "svc-elec-water-sewer",
        ("electric", "water", "sewer"),
        Expected(
            bills=True,
            bills_for=("electric", "sewer", "water"),
            tracked_by="CR-062 group C",
        ),
    )
    _case(
        "svc-elec-trash-solar",
        ("electric", "trash", "solar"),
        Expected(bills=True, bills_for=("electric", "solar", "trash")),
    )


_record_the_combinations()


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE PURE LAYER — no database, milliseconds, fails first
# ══════════════════════════════════════════════════════════════════════════
#
# Two of the three causes above are decided by a pure function before any row is
# written, so they are asserted here as well: a live run takes minutes and this
# takes none, and a lane that breaks the estate plan should learn it at once.


def test_every_catalogue_service_has_a_row_in_the_record():
    """A service a utility can TICK must be a service this file has measured.

    RED PROVED FIRST — with `svc-battery` deleted from the cases above:

        AssertionError: the platform catalogue has services this file does not
        measure: ['battery']. A service a utility can tick at signup with no row
        here is exactly the state DEF-2414 shipped in — add a case, run it, and
        record what it actually does.
        assert set() == {'battery'}
    """
    measured = {code for _sub, services in CASES if len(services) == 1 for code in services}
    missing = set(CATALOGUE) - measured
    assert missing == set(), (
        f"the platform catalogue has services this file does not measure: {sorted(missing)}. "
        "A service a utility can tick at signup with no row here is exactly the state "
        "DEF-2414 shipped in — add a case, run it, and record what it actually does"
    )


def test_the_estate_plan_now_shapes_an_estate_for_every_one_of_the_ten():
    """**`DEF-2396`'s pure half, INVERTED — this case used to assert the
    opposite and the inversion is the fix.**

    Until 2026-09-01 it read `test_the_estate_plan_names_the_four_services_it_
    cannot_shape` and asserted that solar, broadband, battery and thermal/heat
    each produced NO estate and a named refusal. That was true, honest and the
    whole product for four of the ten utilities a person can sign up as: 0
    premises, 0 units, 0 accounts, 0 bills, 14 of 17 seeding blocks failed,
    measured one tenant per service on PostgreSQL 16.13.

    **RED PROVED FIRST — this case's own predecessor is the proof.** With
    `CAPACITY_ESTATE_SERVICES` in place and the old assertions still standing:

        AssertionError: solar is being seeded into an estate that has no shape
        for it — a premises claiming to receive a service the fixture cannot
        price is worse than no premises (BR-MET-003)
        assert 'solar' not in ('solar',)

    …which is word for word the sentence the old case wrote for a lane that
    added a shape, and it fired for the lane that added one on purpose.

    **WHAT REPLACES IT IS THE SAME QUESTION ASKED OF ALL TEN**, because *"which
    services can this fixture furnish"* is the thing `DEF-2396` was about and a
    per-service list would go stale the same way the old one did.
    """
    for code in CATALOGUE:
        uom = SERVICE_DEFAULT_UOMS.get(code, (None,))[0]
        plan = fixture.estate_plan([code], {code: uom})
        if code == "sewer":
            # BY DESIGN and correct — CR-081 prices sewer as 90% of the WATER
            # VOLUME (BR-RAT-015 ❄️ before 2026-09-08) and this tenant sells no water. It is the
            # one service of the ten that a single-service tenant cannot have,
            # and the refusal must stay NAMED rather than become a silent zero.
            assert plan.services == (), "sewer alone must still be refused (CR-081)"
            assert SEWER_HAS_NO_BASIS in dict(plan.refused)["sewer"]
            continue
        assert plan.services == (code,), (
            f"a utility that sells only {code} gets an estate that speaks "
            f"{plan.services!r}. Every service in the catalogue except sewer must be "
            "shapeable on its own — that is DEF-2396, and it was four of the ten"
        )
        assert not plan.refused, f"{code} was shaped AND refused: {plan.refused!r}"


def test_a_capacity_service_needs_no_backbone_and_no_unit_of_measure():
    """The capacity services ride with NO register, so `estate_plan`
    resolves no backbone and asks for no UoM — which is what lets a solar-only
    utility have an estate at all.

    ⚠ **THE UoM HALF IS NOT COSMETIC: it is the second of `DEF-2396`'s two
    mechanisms, seen from the other side.** A capacity service bills on a
    characteristic rather than on consumption, and asking it for a register's
    unit would be inventing a register. CLAUDE.md rule 3 is satisfied by there
    being no quantity to carry a unit, not by assuming one.

    ⚠ **THERMAL/HEAT USED TO BE THIS PARAGRAPH'S COUNTER-EXAMPLE AND IS NOW ONE
    OF THE MEMBERS (`CR-080`, 2026-09-07).** It was *"declared METERED by the
    PO's `DEF-2409` ruling, so it DOES need a unit and was refused for want of
    one"*; the PO ruled it capacity-based on connected tonnage, so it is
    iterated here with the rest and declares `ton` — a capacity, not a
    register's unit.
    """
    for code in fixture.CAPACITY_ESTATE_SERVICES:
        plan = fixture.estate_plan([code], {})  # no declared UoM at all
        assert plan.services == (code,)
        assert plan.metered == () and plan.primary is None
        assert code in fixture.UNMETERED_ESTATE_SERVICES, (
            f"{code} is shaped into the estate but not declared unmetered — it would be "
            "seeded with a service point and then refused on every account for want of a "
            "read and a connection size, which is DEF-2414's shape one service over"
        )


def test_thermal_heat_is_capacity_and_rides_with_no_register_at_all():
    """**THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-07 AND THE INVERSION IS
    THE FIX (`CR-080`).** It was called `test_thermal_heat_is_metered_and_
    therefore_carries_a_declared_unit` and it required thermal to resolve a
    BACKBONE — `("ton-hr", "klb")`, `plan.primary` a `thermal_heat` register,
    and `thermal_heat NOT IN UNMETERED_ESTATE_SERVICES`.

    **PO verbatim, 2026-09-07:** *"connected tonnage - it is capacity not
    metering; i will ahve 100 tonne or 200 tonne etc"*, confirmed the same day
    — *"Thermal — basis disputed - this si correct"*. It is a debt being called
    in rather than a new ruling: the PO had already said on 2026-08-27 that
    *"multiplier replaces bands for capacity services (solar, battery,
    thermal)"* and thermal was the one of the three never executed.

    **What `DEF-2396`'s second mechanism established still stands and is not
    weakened:** a service with no declared unit is REPORTED, never guessed. What
    moved is which unit thermal declares and what it is FOR — `ton` is a
    capacity a building is connected at, not a register's unit — so the estate
    resolves no backbone and asks for no read.

    RED PROVED FIRST — against the pre-CR-080 code:

        AssertionError: assert ('ton-hr', 'klb') == ('ton', 'klb')
        AssertionError: thermal/heat is CAPACITY-billed (CR-080) and its estate
        still planted a register
    """
    assert (
        SERVICE_DEFAULT_UOMS["thermal_heat"].primary,
        SERVICE_DEFAULT_UOMS["thermal_heat"].alt,
    ) == ("ton", "klb"), (
        "the basis and the unit move together — a capacity service cannot be "
        "priced per ton-hour, which is an ENERGY (CR-080, and DEF-497's shape)"
    )
    assert SERVICE_DEFAULT_UOMS["thermal_heat"].basis == "capacity"
    # `klb` STAYS: it is thermal STEAM's unit and `OQ-560` is still open.
    # Dropping it would leave this map silent about steam, which reads like
    # steam was settled.
    plan = fixture.estate_plan(["thermal_heat"], {})  # no declared UoM at all
    assert plan.services == ("thermal_heat",)
    assert plan.metered == () and plan.primary is None, (
        "thermal/heat is CAPACITY-billed (CR-080) and its estate still planted "
        f"a register: {plan.metered!r}"
    )
    assert "thermal_heat" in fixture.UNMETERED_ESTATE_SERVICES


def test_a_utility_that_sells_everything_now_gets_a_register_for_every_one():
    """All ELEVEN enabled resolves to FOUR metered services, the two water
    companions, the FIVE capacity services, and NOTHING refused.

    ⚠ **FIRE JOINED THE CAPACITY RIDERS ON 2026-09-02 (`CR-063`) AND IT IS LAST
    IN `plan.services` FOR A REASON WORTH READING.** The order is not the
    catalogue's — it is metered first, then the water companions, then the
    capacity riders in `CAPACITY_ESTATE_SERVICES` order — so fire sits after
    storm water because it was APPENDED to that tuple, exactly as it was
    appended to the catalogue. Nothing above it moved.

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-02 AND THE INVERSION IS
    THE FIX (`CR-062` group C).** It was called
    `test_a_utility_that_sells_everything_still_gets_ONE_metered_backbone` and
    it required electric, gas, storm water and thermal to be REFUSED — *"the
    fixture declares ONE register per unit, so they are refused for being second
    in line — and that is a fixture limit, not a billing one"*. The limit was
    honest and the PO overruled it after being shown that a utility selling
    electric got no electric line on any bill: *"this is not correct - you
    cannot drop electricty or gas"*.

    **Two things move here and they move in opposite directions.** Electric, gas
    and thermal join the metered list — three services that were enabled and
    invisible. Storm water LEAVES it and rides as a capacity service instead
    (`CR-062` C9, closing `DEF-3231`): the PO ruled the same day that it is
    billed on the size of the property rather than on a dial, and the fixture
    was still planting an `SD-` meter for it.

    RED PROVED FIRST — with the old assertions standing against the new plan:

        AssertionError: assert 'water' == <MeteredService 'water'>
    """
    uoms = {code: SERVICE_DEFAULT_UOMS.get(code, (None,))[0] for code in CATALOGUE}
    plan = fixture.estate_plan(list(CATALOGUE), uoms)
    assert plan.primary is not None
    assert (plan.primary.code, plan.primary.uom) == ("water", "kgal"), (
        "water must still LEAD — every ❄️ frozen figure this fixture reproduces is a "
        "water figure and `primary` is what the awkward cases hang on"
    )
    # ⚠ **THERMAL LEFT THE METERED LIST ON 2026-09-07 (`CR-080`)** and joined
    # the capacity riders at the END of `CAPACITY_ESTATE_SERVICES`, after fire —
    # appended, exactly as fire was, and nothing above it moved. THREE metered
    # services now, not four.
    assert plan.metered_codes == ("water", "electric", "gas")
    assert plan.services == (
        "water",
        "electric",
        "gas",
        "sewer",
        "trash",
        "solar",
        "broadband",
        "battery",
        "storm_water",
        "fire",  # CR-063 — the eleventh service, a capacity rider needing no register
        "thermal_heat",  # CR-080 — arrived from the METERED list on 2026-09-07
    )
    assert plan.refused == (), (
        "a utility that sells everything must now see everything: "
        f"{[code for code, _why in plan.refused]!r} is still refused"
    )


def test_the_backbone_and_the_riders_are_decided_the_same_way_for_every_realistic_shape():
    """**THE SHAPES A SMALL UTILITY ACTUALLY TICKS, ASSERTED FOR FREE
    (`DEF-3223`, 2026-09-02).**

    `DEF-3223` is that the PO reported `electric + water + sewer` producing no
    bill and **this file had never measured that combination** — thirteen live
    rows and not the most ordinary one. The live fix is two new rows above; this
    is the other half, and it is the half that scales.

    A live row costs a provisioning (~50s). **This costs nothing**, because
    `estate_plan` is pure — so the shapes whose only new fact is WHICH SERVICES
    THE ESTATE SPEAKS are settled here instead of being bought one minute at a
    time. What it pins, per shape: the backbone that won, the services the
    estate speaks, and the services REFUSED BY NAME.

    ⚠ **A REFUSAL IS THE THING THIS CATCHES AND A BILL COUNT CANNOT.** A tenant
    that ticks `electric + sewer` BILLS — 95 invoices, from electric — while the
    sewer it sold is dropped. Every bill-counting assertion in this repo is
    green on that tenant. Only the refusal list says a service went missing,
    which is `BR-TEN-060`'s *"named, never a silent zero"* asserted rather than
    hoped for.

    RED PROVED FIRST — this table's own first row is the proof, because
    `CR-062` group C moved it. Against the pre-change code it recorded
    `speaks=("water", "sewer")` and `refused=("electric",)`; against the new
    plan those very entries said:

        AssertionError: these signup shapes no longer resolve as recorded:
          electric+water+sewer: the estate leads with 'water', speaks
          ('water', 'electric', 'sewer') and refuses [] — recorded as 'water',
          ('water', 'sewer') and ['electric']. If that is a fix, move the row;
          if it is not, a service the tenant SELLS has changed hands

    …which is the message this case exists to print, firing on the fix rather
    than on a regression. The rows below are the post-change measurement.

    ⚠ **THE FIRST ENTRY IS THE PO'S OWN SHAPE AND IT IS WHY `CR-062` EXISTS.**
    `water` is FIRST in `METERED_ESTATE_SERVICES` and the catalogue seeds
    `electric` first, so a utility that ticks Electric, Water and Sewer LEADS
    with water — which is correct and deliberate, because the ❄️ `GT-17` figures
    are water figures. What is no longer true is that leading meant winning:
    electric used to be refused as a second register and dropped from every
    bill, and it is now seeded beside water.
    """
    uom = {code: SERVICE_DEFAULT_UOMS.get(code, (None,))[0] for code in CATALOGUE}

    #: `(enabled, backbone, speaks, refused)` — measured from `estate_plan`
    #: itself on 2026-09-02, not predicted.
    shapes: tuple[tuple[tuple[str, ...], "str | None", tuple[str, ...], tuple[str, ...]], ...] = (
        # THE PO'S SHAPE — water LEADS, and electric is seeded beside it.
        (
            ("electric", "water", "sewer"),
            "water",
            ("water", "electric", "sewer"),
            (),
        ),
        # A tenant that BILLS and still loses a service it sold — and it is
        # SEWER, which is refused by a signed RULE (BR-RAT-015 ❄️: 40% of the
        # water usage charge, and there is no water) rather than by a fixture
        # limit. That distinction is the one `CR-062` turns on. No live row: the
        # bills are electric's, already measured by `svc-electric`.
        (("electric", "sewer"), "electric", ("electric",), ("sewer",)),
        # A companion on a NON-water metered service — this one DOES get a live
        # row (`svc-elec-trash-solar`), because a rider's tariff could be missing.
        (("electric", "trash", "solar"), "electric", ("electric", "trash", "solar"), ()),
        # No metered service at all, and one companion that cannot stand up.
        (("sewer", "trash"), None, ("trash",), ("sewer",)),
        # Gas leads when no water is sold — the metered order past its first
        # entry, which nothing else asserts.
        (("gas", "trash"), "gas", ("gas", "trash"), ()),
        # Two metered, neither of them water: the FIRST in metered order LEADS,
        # not the first ticked — and since `CR-062` the second is seeded too
        # rather than refused. `svc-elecgas` bills this shape.
        (("gas", "electric"), "electric", ("electric", "gas"), ()),
    )

    problems: list[str] = []
    for enabled, primary, speaks, refused in shapes:
        plan = fixture.estate_plan(list(enabled), uom)
        found_refused = tuple(sorted(code for code, _why in plan.refused))
        found_primary = plan.primary.code if plan.primary else None
        if (
            found_primary != primary
            or plan.services != speaks
            or found_refused != tuple(sorted(refused))
        ):
            problems.append(
                f"{'+'.join(enabled)}: the estate leads with {found_primary!r}, speaks "
                f"{plan.services} and refuses {list(found_refused)} — recorded as "
                f"{primary!r}, {speaks} and {sorted(refused)}. If that is a fix, move the "
                "row; if it is not, a service the tenant SELLS has changed hands"
            )
        # BR-TEN-060 — a refusal must be a SENTENCE a person can read, never a
        # bare code. This is the half `DEF-3223` turned on: the product knew
        # electric had been dropped and said so only to a log file.
        for code, why in plan.refused:
            if not why or len(why) < 40:
                problems.append(f"{'+'.join(enabled)}: {code} was refused with no reason: {why!r}")

    assert not problems, "\n  ".join(
        ["these signup shapes no longer resolve as recorded:", *problems]
    )


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · THE LIVE RUN — the assertion the repo did not make
# ══════════════════════════════════════════════════════════════════════════


def _measure(tenant) -> dict[str, object]:
    """What a person opening this tenant would actually find.

    Read inside the tenant's own context (CLAUDE.md rule 1); nothing here
    queries across tenants and every count is filtered on `tenant_id` as well,
    so a missing context is a zero rather than a leak.
    """
    with tenant_ctx(tenant):
        blocks: list[dict] = []
        for row in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant.id):
            for block in row.blocks or []:
                blocks.append(dict(block, module=block.get("module") or row.module))
        return {
            "premises": metering_models.Premises.objects.filter(tenant_id=tenant.id).count(),
            "units": metering_models.Unit.objects.filter(tenant_id=tenant.id).count(),
            "service_points": metering_models.ServicePoint.objects.filter(
                tenant_id=tenant.id
            ).count(),
            "accounts": customers_models.Account.objects.filter(tenant_id=tenant.id).count(),
            "issued": billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, status="issued"
            ).count(),
            # `DEF-3224` — WHICH services reached a bill, not merely how many
            # bills there are. A line whose `service` is NULL is not a service
            # this tenant sells appearing; it is a line that names none, so it
            # is dropped rather than counted as a match.
            "on_bills": tuple(
                sorted(
                    str(code)
                    for code in billing_models.InvoiceLine.objects.filter(
                        tenant_id=tenant.id, invoice__status="issued"
                    )
                    .values_list("service__code", flat=True)
                    .distinct()
                    if code
                )
            ),
            "blocks": blocks,
            "failed": [b for b in blocks if b.get("outcome") != "seeded"],
        }


def test_every_service_a_utility_can_tick_at_signup_produces_the_bills_recorded(
    growth_plan, audit_rows, settings
):
    """**THE ASSERTION `DEF-2414` ASKS FOR.** Thirteen tenants, provisioned
    through the real signup service, each counted.

    Every row is measured before ANY assertion fires, and the whole table is
    printed in the failure. A loop that asserted per iteration would report the
    first divergence and hide the other twelve — which on a fixture change is
    the difference between "solar now bills" and "solar now bills and water
    stopped".

    RED PROVED FIRST — and the first proof was NOT a mutation, it was the
    measurement itself. The very first run of this file, at commit `0ab55cba`
    with `svc-trash`, `svc-municipal` and `svc-allten` recorded as BILLING (this
    lane's own expectation before it had measured them), said:

        AssertionError: 3 of 13 signup shapes no longer does what this file
        recorded:
          svc-trash              trash: recorded as BILLING and produced 0 issued
            bills. 12 of 17 seeding blocks failed; the first said:
            assets/seed_sample_records: no meters were seeded: this tenant sells
            no service the sample estate can put a register on…
          svc-municipal          water+sewer+trash: recorded as BILLING and
            produced 0 issued bills. 8 of 17 seeding blocks failed; the first
            said: billing/seed_sample_records: june: BillingRuleError: run … has
            no bills to release, so there is no amount and no currency to record…
          svc-allten             electric+water+gas+sewer+trash+storm_water+
            solar+broadband+thermal_heat+battery: … 0 issued bills. 8 of 17 …

    (Those three are `BILLS` again in the record above because `DEF-2414`'s fix
    landed nine commits later. The quote is kept because it is the only proof
    that this file can SEE a service losing its bills, and because it is what
    the fix lane's own before-and-after looks like from here.)

    Two more clauses were then proved by MUTATION, on the same PostgreSQL 16
    database, each in a throwaway copy of this file trimmed to two rows
    (`svc-water` + `svc-electric`) so the proof cost two tenants rather than
    thirteen — which is why the counts below read *"1 of 2"*:

    **(A) `svc-water` moved to `Expected(False, NO_PLAN_ON_THE_UNIT, …)`** — the
    clause that catches a service quietly LOSING its bills:

        AssertionError: 1 of 2 signup shapes no longer does what this file
        recorded:
          svc-water              water: recorded NO BILLS (RED-PROOF-A),
          produced 95 issued. If that is a fix, move this row to BILLS — the
          record is what the next lane reads

    **(B) `svc-electric`'s `because` changed to a sentence the product never
    says** — the clause that stops a zero being accepted for the WRONG reason,
    which is the half a bare bill count can never check:

        AssertionError: 1 of 2 signup shapes no longer does what this file
        recorded:
          svc-electric           electric: 0 bills, and NO failed block explains
          it with 'the moon was in the wrong phase'. What the blocks actually
          said: billing/seed_sample_records: june: BillingRuleError: run … has no
          bills to release, so there is no amount and no currency to record…
    """
    settings.JOBS_EAGER = True  # the plant runs inline, as it does on a real signup

    rows: list[tuple[str, tuple[str, ...], dict[str, object]]] = []
    for subdomain, services in CASES:
        tenant, result = provisioned_tenant(
            brazosbend_payload(
                subdomain=subdomain,
                name=f"Service coverage {subdomain}",
                services=list(services),
                owner={
                    "full_name": "Dana Whitfield",
                    "email": f"dana@{subdomain}.example.invalid",
                    "password": "S3cure!passw0rd",
                    "phone": None,
                },
            )
        )
        assert result["created"] is True, (
            f"{subdomain}: the tenant must OPEN whatever the sample plant does — C-15 "
            "rules an incomplete plant SOFT and BR-TEN-063 says its failure never fails "
            "provisioning"
        )
        rows.append((subdomain, services, _measure(tenant)))

    problems: list[str] = []
    for subdomain, services, found in rows:
        expected = RECORD[subdomain]
        issued = int(found["issued"])
        label = f"{subdomain:22} {'+'.join(services)}"
        if expected.bills and issued == 0:
            problems.append(
                f"{label}: recorded as BILLING and produced 0 issued bills. "
                f"{len(found['failed'])} of {len(found['blocks'])} seeding blocks failed; "
                f"the first said: {_first_detail(found)}"
            )
        elif not expected.bills and issued > 0:
            problems.append(
                f"{label}: recorded NO BILLS ({expected.tracked_by}), produced {issued} "
                "issued. If that is a fix, move this row to BILLS — the record is what "
                "the next lane reads"
            )
        elif not expected.bills:
            explained = any(expected.because in (b.get("detail") or "") for b in found["failed"])
            if not explained:
                problems.append(
                    f"{label}: 0 bills, and NO failed block explains it with "
                    f"{expected.because!r}. What the blocks actually said: "
                    f"{_first_detail(found)}"
                )

        # ── DEF-3224 · WHICH services reached a bill ────────────────────────
        # Asked of every row that has recorded an answer, and of no other: an
        # unmeasured row asserts nothing rather than asserting a guess.
        on_bills = tuple(found["on_bills"])  # type: ignore[arg-type]
        if expected.bills_for:
            missing = tuple(c for c in expected.bills_for if c not in on_bills)
            if missing:
                problems.append(
                    f"{label}: recorded as billing for {list(expected.bills_for)} and "
                    f"{list(missing)} is on NO invoice line. The bills exist and the "
                    f"service does not appear on them — which is DEF-3224's shape, and a "
                    f"bill COUNT cannot see it. Lines were found for: {list(on_bills)}"
                )
        for code in expected.sold_but_absent:
            if code in on_bills:
                problems.append(
                    f"{label}: recorded as SOLD BUT ABSENT ({expected.tracked_by or 'DEF-3224'}) "
                    f"and {code!r} now appears on a bill line. **If that is a fix, move it "
                    f"into bills_for** — a service that stopped being dropped is exactly "
                    f"what this field exists to notice. Lines found for: {list(on_bills)}"
                )

    report = (
        f"{len(problems)} of {len(rows)} signup shapes no longer does what this file "
        "recorded:\n  " + "\n  ".join(problems) + "\n\n" + _table(rows)
    )
    assert not problems, report


#: Every catalogue service a utility can sell ON ITS OWN. Sewer is the one that
#: cannot: it is a percentage of water's volume (`CR-081`) and is refused by
#: name when there is no water, which `svc-sewer` above asserts.
SOLD_ALONE = tuple(code for code in CATALOGUE if code != "sewer")


@pytest.mark.parametrize("service", SOLD_ALONE)
def test_def_bil_8725_a_utility_that_signs_up_for_one_service_gets_sample_bills(
    service, growth_plan, audit_rows, settings
):
    """**`DEF-BIL-8725` — a new utility's first look at the product is its
    sample data, and for seven of the eleven services it was EMPTY.**

    Signed up for trash, storm water, solar, broadband, thermal/heat, battery
    or fire alone, the sample utility seeded 75 accounts and issued **0
    bills**. The PO's ruling of 2026-09-30 — *no asset = not in service* — made
    installed equipment the thing that puts a service on a bill, and two things
    then left every capacity-only tenant with none:

      * the assets block raised *"no meters were seeded"* BEFORE planting the
        carts, fire lines, panels, batteries and broadband lines, so a utility
        with no metered service got no equipment at all;
      * storm water and thermal/heat have NO equipment by ruling — their
        capacity is recorded on the unit — so they were *not in service* on
        every tenant, the all-services one included.

    One tenant per service, through the real signup service, asserting the
    bills issue AND that this service is on them: a bill count alone cannot see
    a missing service (`DEF-3224`).
    """
    settings.JOBS_EAGER = True
    subdomain = f"alone-{service.replace('_', '')}"
    tenant, result = provisioned_tenant(
        brazosbend_payload(
            subdomain=subdomain,
            name=f"Alone {service}",
            services=[service],
            owner={
                "full_name": "Dana Whitfield",
                "email": f"dana@{subdomain}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    assert result["created"] is True
    found = _measure(tenant)
    assert int(found["issued"]) > 0, (
        f"{service} alone issued 0 bills. {len(found['failed'])} of "
        f"{len(found['blocks'])} seeding blocks failed; the first said: {_first_detail(found)}"
    )
    assert service in tuple(found["on_bills"]), (  # type: ignore[arg-type]
        f"{service} alone issued {found['issued']} bills and {service} is on none of "
        f"them. Lines were found for: {list(found['on_bills'])}"  # type: ignore[call-overload]
    )


def _first_detail(found: dict[str, object]) -> str:
    for block in found["failed"]:  # type: ignore[index]
        detail = (block.get("detail") or "").strip()
        if detail:
            return f"{block.get('module')}/{block.get('block')}: {detail[:300]}"
    return "(no failed block reported a reason at all — that is DEF-795's own shape)"


def _table(rows: list[tuple[str, tuple[str, ...], dict[str, object]]]) -> str:
    """The whole measurement, so a red run is a report and not a riddle."""
    lines = [
        f"{'signup shape':24}{'prem':>6}{'units':>7}{'points':>8}"
        f"{'accts':>7}{'issued':>8}  blocks failed  services billed / SOLD BUT ABSENT"
    ]
    for subdomain, services, found in rows:
        # DEF-3224 — printed for EVERY row, including the ones that assert
        # nothing about it yet, because the fastest way to fill `bills_for` in
        # for the other thirteen is to read them off a run that already happened.
        on_bills = tuple(found["on_bills"])  # type: ignore[arg-type]
        absent = sorted(set(services) - set(on_bills))
        lines.append(
            f"{subdomain:24}{found['premises']:>6}{found['units']:>7}"
            f"{found['service_points']:>8}{found['accounts']:>7}{found['issued']:>8}"
            f"  {len(found['failed'])}/{len(found['blocks'])}"
            f"  {','.join(on_bills) or '-'}"
            + (f"  /  ABSENT: {','.join(absent)}" if absent else "")
        )
    return "\n".join(lines)
