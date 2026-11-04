# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (stage 2 of seven)   Screens: S31.2 · S31.3
#           Same as stage 1: the story that renders this is in the docstring.
# Rules:    BR-BIL-037 (one input contract, one output contract) · BR-BIL-039
#           (PURE — no writes, no external calls, no clock) · BR-BIL-015
#           (a missing read is a per-case human CHOICE, never a silent skip) ·
#           BR-CUS-055 (billable-base-only bills base charges, not usage) ·
#           BR-BIL-028 (mid-cycle Vacation-hold: usage to the hold date, base
#           charges full month) · CLAUDE.md rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_bil_029_stages.py
# Impacts:  apps/billing/rating_seam.price_period (stages 3–5 consume this)
# ───────────────────────────────────────────────────────
"""Stage 2 — what did each service actually use, or why nobody knows.

Its output is what the S31.2 preview's Reads tab renders and what the S31.3
exception step acts on (US-BIL-002/003) — named here and not in the Trace
block, for the reason stage 1 records.

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

🔒 **HUMAN-OWNED · HUMAN-REVIEW-PENDING** (CLAUDE.md 🔒, PO ruling 2026-08-09).
Row in `12-governance/09-human-review-ledger.md`. ⚠ **RAISED TO THE MODULE
DOCSTRING 2026-09-15 BY `DEF-BIL-5326`**: it was on ONE function
(`bills_installed_capacity`) and this file now also owns
`EXEMPT_FROM_MISSING_READ` — the single list deciding which services BR-BIL-015
stops a bill for, read by every bill path in the product. ⚠ **NO GLOB IN
`10-scripts/gates/human_owned.txt` MATCHES THIS PATH**, so `G7` does not check
it; adding one is the PO's call and is reported in the ledger row.

PURE (BR-BIL-039). The readings were gathered before the pipeline started; this
stage decides what they MEAN for billing and hands the result to rating.

THE ONE THING THIS STAGE EXISTS TO GET RIGHT: a missing read is not a zero.

That distinction is the whole file. A meter nobody could reach and a meter
reading exactly what it read last month produce the same number if you are
careless — and one of them is a customer billed nothing for water they used.
BR-BIL-015 makes the missing case a per-case human choice (estimate / hold the
account / bill without this service), so this stage carries the ABSENCE forward
with its reason and refuses to invent a quantity. `MeasuredUsage.unmeasured` is
the list the exception screen works from.

A GENUINE ZERO IS BILLABLE and is not an exception here. An empty apartment
whose meter really did not move used 0 kWh, and 0 kWh at any tariff is $0 of
usage plus whatever base charges the plan carries. The run may still flag it
for a human under the `no_usage` case — that is a decision about whether it
looks suspicious, taken on screen, not an arithmetic question this stage
answers.

BASE-ONLY ACCOUNTS (BR-CUS-055 Vacation-hold / Suspended). Stage 1 has already
resolved the behaviour class; if it says base-only, this stage returns NO usage
for every service — not zero usage. The difference matters downstream: a zero
would produce a $0.00 usage line on the bill, and the customer is not being
billed zero usage, they are not being billed usage at all. The bill should not
show a line for something that was not charged.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from apps.billing import rating_seam
from apps.billing.contracts import (
    AccountBillingData,
    MeasuredService,
    MeasuredUsage,
    ServiceReading,
    SubscriptionContext,
)
from apps.billing.exceptions import BillingRuleError
from core.units import same_unit

#: Why a service has no measured consumption. Grouped on by the exception
#: screen, so they are values rather than free text.
ABSENT_BASE_ONLY = "base_only_account"
ABSENT_NO_READING = "no_reading_supplied"
#: DEF-161 — the service was never MEASURED, and not because a read is missing.
ABSENT_NOT_USAGE_MEASURED = "tariff_prices_no_consumption"
#: DEF-990 / DEF-1060 — THIS TARIFF charges its base and no usage, whatever the
#: account's behaviour class says. `ABSENT_BASE_ONLY` above is BR-CUS-055's
#: ACCOUNT fact (a vacation hold, every service at once); this one is a fact
#: about ONE tariff on an ordinary billable account, and the two must stay
#: apart because the exception screen groups on this value and a clerk reading
#: *"base-only account"* beside four usage lines would be reading a lie.
ABSENT_TARIFF_BASE_ONLY = "tariff_bills_base_only"
#: PO ruling 2026-09-30 (fixed-charge case 1): a clerk chose *"Bill without
#: it"* for a service with no reading. Its BASE bills this month and its USAGE
#: waits: no reading was billed, so the next bill's reading is measured from
#: the last one billed and nothing is lost. A different fact from the two
#: above, and the customer is told so on the bill.
ABSENT_USAGE_NEXT_BILL = "usage_billed_next_bill"

#: ⚠ **DEF-161 (PO ruling 2026-08-27) — THE SERVICE IS NOT MEASURED BY DESIGN.**
#: **THE VALUE IS METERING'S, NOT THIS MODULE'S**, and it is spelled here rather
#: than imported for the reason every other reason on this seam is: billing
#: resolves metering BY NAME (`gather._resolve`) and never imports it, so the
#: two modules agree on a STRING. `tests/test_def_161_designed_absence_bills.py`
#: asserts this constant equals `apps.metering.selectors
#: .READ_ABSENT_SERVICE_NOT_METERED`, so a rename on either side goes RED
#: instead of silently reopening the defect.
#:
#: **HOW IT DIFFERS FROM THE THREE ABOVE, because four look-alike reasons is
#: exactly how DEF-161 happened:**
#:
#:   * `ABSENT_BASE_ONLY` — an ACCOUNT fact (BR-CUS-055's vacation hold): EVERY
#:     service on this account bills base and no usage.
#:   * `ABSENT_TARIFF_BASE_ONLY` — a TARIFF fact (DEF-990/1060): THIS tariff
#:     charges base and no usage on an account billing usage normally.
#:   * `ABSENT_NOT_USAGE_MEASURED` — a PRICING-MODEL fact (BR-RAT-015): sewer
#:     prices a percentage of WATER, so it has no consumption of its own.
#:   * **this one** — a SERVICE fact (BR-RAT-081): the utility declared that it
#:     does not measure this service at all, so no read was ever owed.
#:
#: All four are exempt from BR-BIL-015's missing-read refusal and all four are
#: separate values, because the S31.3 exception screen GROUPS on this string and
#: a clerk reading *"base-only account"* against a trash service on a fully
#: billing account would be reading a lie.
ABSENT_SERVICE_NOT_METERED = "service_not_metered"

#: ⚠ **BR-RAT-090 (DEF-1813) — THE SERVICE IS UNMETERED AND NOBODY LOOKED.**
#: **THE VALUE IS METERING'S, NOT THIS MODULE'S**, spelled here for the same
#: reason `ABSENT_SERVICE_NOT_METERED` above is: billing resolves metering BY
#: NAME and never imports it, so the two modules agree on a STRING.
#: `tests/test_def_1813_unmetered_count.py` asserts this constant equals
#: `apps.metering.selectors.READ_ABSENT_ASSET_COUNT_UNAVAILABLE`.
#:
#: **HOW IT DIFFERS FROM `ABSENT_SERVICE_NOT_METERED`, which is the whole
#: point:** that one says *no read was ever owed*, and BR-RAT-090 then makes the
#: COUNT of the unit's assets the billable quantity. This one says the count
#: itself could not be determined. A count of `0` is a real answer and bills; no
#: count at all is not, and **it is the one reason on this seam that is NOT
#: exempt from the refusal below**. Reading it as a zero bills a three-cart
#: household `$0.00` for trash on a document that foots and prints.
ABSENT_ASSET_COUNT_UNAVAILABLE = "asset_count_unavailable"

#: ⚠ **CR-062 D1/H2 — THE SERVICE SUMS ITS INSTALLED CAPACITY AND THE TOTAL
#: COULD NOT BE STATED.**
#:
#: ⚠ **THIS ONE IS BILLING'S OWN VALUE AND HAS NO METERING TWIN, WHICH IS THE
#: OPPOSITE POSTURE FROM THE TWO ABOVE — SO IT IS WORTH SAYING WHY.** Metering
#: publishes the FACTS (`installed_capacity`, `capacity_uom`, `asset_count`) and
#: cannot decide this: whether a unit's panels are billed as **14 kW** or as
#: **3 panels** depends on the unit the TARIFF quotes its price per, and the
#: tariff is in hand here and nowhere upstream. A metering-side refusal would
#: have stopped every account whose schedule prices per panel — B5 `GT-15`'s
#: `$40.00` among them — for a total it was never going to use.
#:
#: **WHAT IT MEANS, AND WHY IT IS NOT ANY OF THE FIVE ABOVE.** This service's
#: schedule is priced per kW (or per ERU, or per Mbps) and the equipment on the
#: unit does not say how much capacity it is: an asset records no size class, or
#: records one this service does not have. So there IS a quantity — the utility
#: sells it and the customer has it — and nobody can state it.
#:
#: ⚠ **IT IS A SEPARATE VALUE FROM `ABSENT_ASSET_COUNT_UNAVAILABLE` BECAUSE THE
#: SENTENCE A CLERK READS DECIDES WHAT THEY GO AND DO.** *"Nobody counted the
#: equipment"* sends them to the unit to count things that are already counted;
#: the work here is to open each panel and record which type it is. Collapsing
#: the two would put the wrong job on the S31.3 exception screen.
#:
#: **NOT exempt from the refusal below, for the same reason the two count
#: reasons are not:** reading it as a zero bills a 14 kW array `$0.00`, and
#: totalling only the panels we DO recognise bills a 12 kW array at 2 kW. Both
#: are documents that foot and print.
ABSENT_INSTALLED_CAPACITY_UNRESOLVED = "installed_capacity_unresolved"

#: ⚠ **CLAUDE.md rule 3 (DEF-1813) — THE COUNT IS KNOWN AND ITS UNIT IS NOT.**
#: Also metering's value, mirrored for the same reason. A count of carts is a
#: quantity and a quantity always carries its unit; `3` priced against a
#: schedule quoting *$15.00 per MONTH* is rule 3 satisfied in form and wrong in
#: substance. Refused rather than billed against the tariff's assumed unit —
#: the posture `runs._readings_for` already takes for a read arriving without
#: one. Not exempt below, for the same reason as the constant above.
ABSENT_ASSET_COUNT_UNIT_UNSTATED = "asset_count_unit_unstated"

#: ⚠ **THE FOUR REASONS THAT ARE NOT A MISSING READ — ONE LIST, READ BY EVERY
#: BILL PATH (`DEF-BIL-5326`, 2026-09-15).**
#:
#: BR-BIL-015 makes an unresolved missing read a HUMAN's decision, and each of
#: the four reasons below is a service that was never owed a read at all. Every
#: path that raises BR-BIL-015's refusal must exempt exactly these four, and
#: until this tuple existed each path carried its own copy of the list:
#: `runs.calculate_account` and `midperiod._measured_segment` had all four and
#: `backbill._measured` — the pass that prices a BACK-BILL and a PENALTY bill —
#: had only the first.
#:
#: **WHAT THAT COST, measured on one account and one window before the fix:**
#: account `E11-0001` over 2026-08-16 → 2026-09-15 priced 24 lines totalling
#: `$573.33` as an INTERIM bill, two of them *"sewer usage — 60.00% of water
#: volume"* `$28.35` and *"sewer base charge"* `$22.50`. The same account, the
#: same window, as a BACK-BILL or a PENALTY bill refused with
#: `missing_read_undecided_at_calculate` naming sewer — a service that prices a
#: percentage of water (BR-RAT-015) and therefore has no reading of its own to
#: be missing. Sewer as a percentage of water is the ordinary North American
#: arrangement, so two of the six one-time bill kinds were unusable by an
#: ordinary tenant.
#:
#: ⚠ **THIS TUPLE IS THE EXEMPT SET AND NOT "THE ABSENT REASONS".** The three
#: reasons deliberately OFF it each refuse BY THEIR OWN NAME one layer up —
#: `ABSENT_ASSET_COUNT_UNAVAILABLE` and `ABSENT_ASSET_COUNT_UNIT_UNSTATED`
#: (BR-RAT-090) and `ABSENT_INSTALLED_CAPACITY_UNRESOLVED` (CR-062) — and
#: `ABSENT_NO_READING` is the missing read itself, which is the whole subject
#: of the refusal. **A METERED service with no read still refuses**, in every
#: path, and that half is the deliverable rather than the leftover: adding a
#: reason here bills somebody base-only on a document that foots and prints.
#:
#: **Its reason for being ONE name rather than three matching literals is the
#: defect it was extracted from:** a fifth exempt reason added to the interim
#: path and not to the sub-period path is invisible — every suite stays green,
#: because the suites that exercise the sub-period path use metered services
#: only, and the bill simply refuses for a tenant nobody tested.
EXEMPT_FROM_MISSING_READ: tuple[str, ...] = (
    # An ACCOUNT fact (BR-CUS-055's vacation hold): every service on this
    # account bills base and no usage.
    ABSENT_BASE_ONLY,
    # A PRICING-MODEL fact (BR-RAT-015): sewer prices a percentage of WATER, so
    # it has no consumption of its own. `DEF-BIL-5326` is this one missing from
    # the sub-period path.
    ABSENT_NOT_USAGE_MEASURED,
    # A TARIFF fact (DEF-990 / DEF-1060): this tariff was BUILT base-only by the
    # gather — a master's empty-unit base charge (BR-CUS-170), a unit service
    # the plan states no schedule for (OQ-601 edge 1). No read was ever wanted.
    ABSENT_TARIFF_BASE_ONLY,
    # A SERVICE fact (BR-RAT-081, DEF-161): the utility declared it does not
    # measure this service at all, so no read was ever owed. ⚠ A METERED
    # service point with no meter is NOT this reason (`no_meter`) and still
    # stops the bill.
    ABSENT_SERVICE_NOT_METERED,
    # A CLERK's fact (PO 2026-09-30, case 1): the usage bills next bill.
    ABSENT_USAGE_NEXT_BILL,
)

#: Tariff models that price NO consumption of their own, so no reading of their
#: own can exist for them to be missing.
#:
#: **Exactly one model is on this list and it is here because signed law puts it
#: here, not because this file decided.** BR-RAT-015 (CONFIRMED, PO Q&A R1 Q8):
#: sewer bills as a *"% of water usage-charge dollars"*. Its plugin says the same
#: thing in its own words — *"`usage` is ignored ON PURPOSE … a percent-of-service
#: tariff prices no consumption of its own. Sewer is billed off the WATER meter,
#: and a sewer service point often has no meter at all"* — and BR-RAT-066
#: enumerates when such a tariff refuses: when its BASIS service is not on the
#: bill. Never for want of a reading of its own.
#:
#: ⚠ **A FLAT TARIFF IS STILL NOT ON THIS LIST, AND AS OF 2026-08-27 THAT IS A
#: RULING RATHER THAN AN OPEN QUESTION.** This note used to read *"no signed
#: rule says what a service point with no meter means for a tariff that DOES
#: price consumption, so OQ-246 asks"*. **OQ-246 IS CLOSED** — BR-MET-134 (PO
#: 2026-08-26): *"The service's pricing model decides: unmetered-by-design
#: services expect no read; a consumption-priced service with no meter is a
#: human's exception"* — and DEF-161's ruling the following day settles which
#: side of that boundary a `flat` tariff falls on:
#:
#:   *"A meter that exists and was not read keeps refusing exactly as it does
#:   now — that distinction is the deliverable, and a fix that blurs it has
#:   traded one silent wrong bill for another."*
#:
#: `flat` is a CONSUMPTION-PRICED model — `unit_price × quantity` — and it is
#: the model a small utility's WATER tariff most often uses. Putting it on this
#: list would make every water meter nobody could reach bill as base-only, on a
#: document that foots, with no work on any exception screen. So the trash case
#: BR-MET-134 has in mind is answered by the SERVICE's own declaration
#: (BR-RAT-081's `tenant_services.metered`) and never by its tariff's model —
#: see `ABSENT_SERVICE_NOT_METERED` above. Adding a model here still requires a
#: rule saying that model prices no consumption; `percent_of_service` has one
#: (BR-RAT-015) and nothing else does.
PRICES_NO_CONSUMPTION: tuple[str, ...] = ("percent_of_service",)


def prices_no_consumption(tariff: object) -> bool:
    """Does this tariff price a measurement of its own? See PRICES_NO_CONSUMPTION."""
    return getattr(tariff, "model", None) in PRICES_NO_CONSUMPTION


def bills_base_only(tariff: object) -> bool:
    """Does this ONE tariff charge its base charge and no usage? (DEF-990/1060)

    Read through `getattr` with a default, like every other optional field on
    the seam's contracts: a `TariffConfig` built by a fixture written before the
    flag existed answers False and prices exactly as it always did.
    """
    return bool(getattr(tariff, "base_only", False))


def _reading_for(
    readings: tuple[ServiceReading, ...],
    service_code: str,
    asset_id: str | None = None,
) -> ServiceReading | None:
    """The reading for this service — MATCHED BY SERVICE CODE, which is why the
    caller must never ask on behalf of a base-only tariff.

    ⚠ **AND BY METER WHEN THE TARIFF NAMES ONE (PO ruling 2026-09-30, two
    meters = two lines).** A config built for meter `m-2` must price `m-2`'s
    reading: matched by code alone it would take the first water reading and
    bill `m-1`'s usage twice, on a document that foots. A tariff naming no
    meter matches by code exactly as before — every bill before the ruling.

    ⚠ **THE MATCH IS BY CODE ALONE AND THAT IS DEF-990's SECOND NAMED OBSTACLE.**
    One bill can now hold two tariffs for one service — a master's bill prices
    the hallway's electric usage AND carries the base charge of an empty unit
    that also takes electric (BR-CUS-170). Asked for both, this function returns
    the SAME reading twice and the hallway's kWh is billed a second time, on a
    document that foots. The tariff that must not consume a reading says so
    itself (`base_only`), and `measure_consumption` below branches on it BEFORE
    reaching here — so the guard is at the caller, where the fact is known, and
    this function keeps one job.
    """
    for reading in readings:
        if reading.service_code != service_code:
            continue
        if asset_id is not None and getattr(reading, "asset_id", None) != asset_id:
            continue
        return reading
    return None


def bills_installed_capacity(reading: object, tariff: object) -> bool:
    """**Does THIS tariff bill the SUM of installed capacity rather than a COUNT
    of the things it is installed in?** CR-062 D1/H2. 🔒 rating math.

    HUMAN-REVIEW-PENDING (CLAUDE.md 🔒). Row in
    `12-governance/09-human-review-ledger.md`.

    **THE WHOLE SUM-versus-COUNT DECISION IS THIS FUNCTION, AND IT NAMES NO
    SERVICE.** Since CR-062 the phrase *capacity based* covers two arithmetics:

        trash  COUNTS what is installed   3 carts × $15.00       = $45.00
        solar  SUMS   what is installed   2 + 4 + 8 kW × $14.00  = $196.00

    Two questions, both answered by configuration this product already holds, and
    a service must answer YES to both:

      1. **Do this service's size classes sum at all?** `capacity_uom` on the
         reading is `BR-TEN-171`'s answer, published by metering from
         `service_size_classes.capacity_uom_for_service`. It is `None` for every
         BANDED service: trash's carts are gallons and its dumpsters are cubic
         yards, so their total exists in no unit; fire is *"exactly like trash"*
         (`CR-063`); water's pipe diameters pick a rate and add up to nothing.
         **A `None` here is a finished answer — *do not sum these* — and never
         *sum them in some default unit*.**
      2. **Is that the unit this TARIFF's price is quoted per?** A schedule
         reading *$14.00 per kW* bills the kilowatts installed. A schedule
         reading *$10.00 per panel* bills the panels — and pricing a kW total at
         a per-panel rate would satisfy CLAUDE.md hard rule 3 in FORM and be
         wrong in SUBSTANCE, which is `DEF-497` with an order of magnitude on it.
         B5 `GT-15` is exactly that utility and its `$40.00` is unmoved.

    ⚠ **BECAUSE IT NAMES NO SERVICE, AN ELEVENTH AND A TWELFTH NEED NO EDIT
    HERE.** Fire arrived on 2026-09-02 and landed on the counting side with
    nothing in this module changing, because *"exactly like trash"* is a fact
    about its ratified rows. The mechanical test is
    `capacity_uom_for_service("fire") is None`, not a comment and not a list.

    ⚠ **THE COMPARISON IS `core.units.same_unit`, AND SO IS THE GATE'S.**
    `rating.pricing.stages.normalize._gate_uom` refuses a quantity whose unit
    is not the tariff's (BR-RAT-038 — *"convert at rating input with a defined
    per-service factor, or block the read — never convert silently"*), and
    since `DEF-RAT-10220` (PO 2026-10-17) both points ask the SAME function:
    case and white space are spelling, never a different unit. Until then this
    read `!=` on both sides, so a solar rate saved as *"$14 per KW"* failed
    here against the capacity's `kW` and fell to the COUNT — two panels of
    47.84 and 10 kW billed **2 × $14.00 = $28.00** instead of **57.84 kW ×
    $14.00 = $809.76**. Matching loosely here while the gate stayed exact would
    refuse the bill one stage later; one function means one answer.
    """
    capacity_uom = getattr(reading, "capacity_uom", None)
    if not capacity_uom:
        return False
    billed_unit = getattr(tariff, "billed_unit", None)
    if not billed_unit:
        return False
    return same_unit(billed_unit, capacity_uom)


def _summed_quantity(reading: object) -> "rating_seam.Quantity | None":
    """CR-062's quantity for a service billed on its INSTALLED CAPACITY, or
    `None` when the total could not be stated. Pure.

    The Product Owner's own array, 2026-09-02 — panels of 2 kW, 4 kW and 8 kW on
    one unit — is `Quantity(Decimal("14"), "kW")`, and at their `$14.00` per kW
    that bills **$196.00**.

    ⚠ **THE UNIT COMES FROM THE CAPACITY AND NOT FROM THE TARIFF, WHICH IS THE
    OPPOSITE OF `_counted_quantity` BELOW — AND BOTH ARE RIGHT.** A count is a
    number of THINGS and carries no unit of its own, so it takes the unit the
    price is quoted per. A capacity total IS a measurement and already has one:
    it is 14 kilowatts whatever anybody charges for it. Taking the tariff's
    spelling instead would let a schedule relabel a measurement, which is the
    one thing hard rule 3 exists to stop. `bills_installed_capacity` has already
    established the two agree, so this is the same string either way — stated
    here so a later reader does not "simplify" it into the tariff's copy.

    ⚠ **`None` IS NEVER A ZERO.** An empty unit sums to `Decimal("0.0000")` and
    that is a REAL answer — BR-MET-108's ruled zero, which prices `$0.00` and
    puts the line on the document rather than the gap in a silence. `None` means
    the total could not be STATED, and the caller refuses on it by name.
    """
    total = getattr(reading, "installed_capacity", None)
    if total is None:
        return None
    unit = getattr(reading, "capacity_uom", None)
    if not unit:  # pragma: no cover — the pair travels together or not at all
        return None
    return rating_seam.Quantity(amount=Decimal(str(total)), unit=str(unit))


def _counted_quantity(
    reading: ServiceReading | None, tariff: object, account_no: str
) -> "rating_seam.Quantity | None":
    """BR-RAT-090's quantity for an UNMETERED service, or None when this is not
    one. Pure.

    **THE COUNT ARRIVES WITHOUT A UNIT AND LEAVES WITH ONE, AND THIS IS THE ONLY
    PLACE THAT CAN DO THAT HONESTLY.** Three carts is three things — BR-RAT-036's
    rule row draws the distinction in terms (*"a meter is not a measure of
    anything… the same distinction BR-RAT-090 draws for an unmetered service's
    cart count"*) — so metering publishes the bare integer. The unit is the one
    the PRICE is quoted per, which is the tariff's `billed_unit`, and the tariff
    is in hand exactly here and nowhere upstream. Taking it from anywhere else
    is DEF-497 with money on it: a quantity of `3` against a schedule reading
    *$15.00 per MONTH* satisfies CLAUDE.md rule 3 in form and is wrong in
    substance, which is the worse of the two failures because it reads as
    correct.

    ⚠ **A TARIFF WITH NO BILLED UNIT REFUSES.** Rule 3 again, and the same
    refusal `runs._readings_for` already raises for a read that arrives without
    one: billing never assumes a unit, and a counted line is not the exception.

    Returns None — leaving every existing branch below untouched — for any
    service that is not a declared-unmetered one carrying a count. `0` is a
    real count and returns `Quantity(0)`: the utility looked and this unit has
    no carts, so the cart line prices `$0.00` and the base still applies.
    *"Nobody looked"* never reaches here; metering names it and the run stops.
    """
    if reading is None or reading.asset_count is None:
        return None
    if reading.absent_reason != ABSENT_SERVICE_NOT_METERED:
        # Defensive: metering only ever stamps a count on a designed-absence
        # row. Stated rather than assumed, because a count silently priced onto
        # a service with a real missing read would be a bill built on the wrong
        # fact, and nothing downstream could tell.
        return None
    count = _count_for(reading, tariff)
    if count is None:
        return None
    billed_unit = getattr(tariff, "billed_unit", None)
    if not billed_unit:
        raise BillingRuleError(
            f"account {account_no}, service {getattr(tariff, 'service', '?')}: this "
            "service is billed by a COUNT of its assets (BR-RAT-090) and its tariff "
            "states no billed unit. CLAUDE.md rule 3 — a quantity always carries its "
            "unit and billing never assumes one."
        )
    return rating_seam.Quantity(amount=Decimal(count), unit=str(billed_unit))


def _count_for(reading: ServiceReading, tariff: object) -> int | None:
    """**HOW MANY THIS TARIFF IS FOR — the whole connection, or one SIZE of it.**
    `CR-063` C3/C5, decision log 2026-09-02.

    ⚠ **A COUNTING CAPACITY SERVICE BILLS ONE LINE PER SIZE, so a bill can carry
    TWO tariffs for one service and each must take its OWN count.** A fire
    property holding one 6" line and two 2" lines: `gather` builds two configs,
    `FL-6` and `FL-2`, and this is what stops both of them billing the
    connection's total of `3`. Reading `asset_count` for each would produce
    `3 × $60.00 + 3 × $12.00 = $216.00` where the ruled answer is
    `1 × $60.00 + 2 × $12.00 = $84.00` — a 157% overcharge on a document that
    foots and prints.

    ⚠ This example was `CR-063`'s warehouse — a 6" line and two private hydrants
    at `$110.00` — until the PO removed the hydrant from fire's size list on
    2026-09-03. **The bug it describes is unchanged**; only the sizes that can
    stand on one connection are.

    ⚠ **THE UN-SIZED PATH IS UNCHANGED, BYTE FOR BYTE.** A tariff naming no size
    takes the connection's whole count, which is every trash bill this product
    has issued (`3 carts × $15.00 = $45.00`) and every other service alike. The
    per-size branch is entered ONLY when the tariff names a size AND the reading
    carries the split, and `gather` only ever sets both together.

    ⚠ **A SIZE THE MAP DOES NOT HOLD ANSWERS `None`, WHICH IS NOT A ZERO.** It
    means the tariff and the reading disagree about what stands on this
    connection — the two were resolved at the same date from the same
    population, so they cannot legitimately differ — and the caller carries it
    as an absence for a human rather than billing `$0.00` for equipment somebody
    installed.
    """
    size_class = getattr(tariff, "size_class", None)
    groups = getattr(reading, "asset_size_counts", None)
    if not size_class or groups is None:
        return int(reading.asset_count)
    if size_class not in groups:
        return None
    return int(groups[size_class])


def measure_consumption(
    subscription: SubscriptionContext, data: AccountBillingData
) -> MeasuredUsage:
    """`SubscriptionContext` (+ the gathered readings) -> `MeasuredUsage`.

    Takes `data` as well as its predecessor's output because the readings were
    gathered with the rest of the account's data and a pure stage cannot go and
    fetch them. BR-BIL-037 says a stage receives its predecessor's output "and
    nothing else"; the gathered data is not a second source but the SAME one
    stage 1 read, and the alternative — copying every reading through
    `SubscriptionContext`, which has no use for them — would make stage 1's
    contract carry a payload for stage 2's benefit. REPORTED here rather than
    resolved silently, because it is a real (if narrow) deviation from the
    letter of BR-BIL-037.
    """
    if subscription.account_id != data.account_id:
        # The two arguments must describe the SAME account. Getting this wrong
        # would bill one customer for another's usage, and no downstream stage
        # could detect it — every figure would be internally consistent.
        raise BillingRuleError(
            f"stage 2 received a subscription for {subscription.account_no} and "
            f"readings for {data.account_no}. These must be the same account."
        )

    services: list[MeasuredService] = []
    for tariff in subscription.tariffs:
        if subscription.base_only:
            # BR-CUS-055 — base charges only. NO usage, which is not the same
            # as zero usage: a $0.00 usage line claims the meter was read.
            services.append(
                MeasuredService(
                    service_code=tariff.service,
                    tariff=tariff,
                    consumption=None,
                    absent_reason=ABSENT_BASE_ONLY,
                )
            )
            continue

        if bills_base_only(tariff):
            # DEF-990 / DEF-1060 — a TARIFF that charges its base and no usage,
            # on an account that is otherwise billing usage normally. Two ruled
            # bills need this and neither could be produced without it:
            #
            #   * BR-CUS-170 (PO 2026-08-27) — the base charges of every unit on
            #     a master's premises that nobody occupies ride the owner's
            #     bill. On BR-MET-101's building with Unit C empty and taking
            #     electric the owner owes $69.60 + $12.00 = **$81.60**.
            #   * OQ-601 edge 1 (PO 2026-08-27) — *"1 Unit has a service, plan
            #     has no schedule for it … in such case bill base only"*.
            #
            # ⚠ IT MUST COME BEFORE `_reading_for`, NOT AFTER. That function
            # matches on the service CODE, so a second electric tariff would
            # pick up the first connection's read and bill its usage twice.
            # Skipping the lookup entirely is the only form of this branch that
            # cannot do that, which is why it is not written as a filter on the
            # result.
            services.append(
                MeasuredService(
                    service_code=tariff.service,
                    tariff=tariff,
                    consumption=None,
                    absent_reason=(
                        ABSENT_USAGE_NEXT_BILL
                        if tariff.service in (getattr(data, "usage_next_bill", ()) or ())
                        else ABSENT_TARIFF_BASE_ONLY
                    ),
                )
            )
            continue

        reading = _reading_for(data.readings, tariff.service, getattr(tariff, "asset_id", None))
        if reading is None or reading.consumption is None:
            if (
                reading is not None
                and reading.absent_reason == ABSENT_SERVICE_NOT_METERED
                and bills_installed_capacity(reading, tariff)
            ):
                # ── CR-062 D1/H2 · THE SUM IS THE QUANTITY ───────────────────
                # PO ruling 2026-09-02, verbatim: *"on given Unit we have
                # installed 3 panels with 2Kw, 4Kw and 8 Kw , it means the totla
                # capacity will be 14 Kw ; rate will be for 1 Kw = 14 $ per KW"*
                # — **14 kW × $14.00 = $196.00**. The branch below would have
                # said `3` and billed **$42.00** for the same array, which is a
                # 78% undercharge on every solar customer.
                #
                # It sits ABOVE the count for the same reason the count sits
                # above the two absent branches: this service HAS a quantity. It
                # simply did not come from a register, and for THIS tariff it is
                # not the count either.
                summed = _summed_quantity(reading)
                if summed is None:
                    # The equipment does not say how much capacity it is. NOT a
                    # zero and NOT the count: three panels of unrecorded type
                    # would bill $0.00 read as a zero, or 3 kW read as a count,
                    # and both foot and print. BR-RAT-090's own distinction one
                    # level up — *"'no carts recorded' and 'zero carts' are
                    # different facts and only one of them is billable"*.
                    services.append(
                        MeasuredService(
                            service_code=tariff.service,
                            tariff=tariff,
                            consumption=None,
                            absent_reason=ABSENT_INSTALLED_CAPACITY_UNRESOLVED,
                        )
                    )
                    continue
                # DEF-BIL-8743 — a summed capacity charge prorates its MONEY on
                # a part period (B4.3, WE-16/GT-31; GT-15 amended 2026-08-11,
                # *"BOTH lines prorate"*), as a counted one does (DEF-BIL-8566).
                # NOT on the `capacity` model, which prorates its own line —
                # flagging it too would cut a 10/31 month to (10/31)².
                if getattr(tariff, "model", None) != "capacity":
                    tariff = dataclasses.replace(tariff, installed_sum_line=True)
                services.append(
                    MeasuredService(
                        service_code=tariff.service,
                        tariff=tariff,
                        consumption=summed,
                        # NOT `estimated`, for `_counted_quantity`'s own reason:
                        # an estimate is a number nobody observed, and every kW
                        # in this total is a panel somebody recorded.
                        estimated=False,
                        # What it was summed FROM stays on the row beside the
                        # total, so a 14 kW line remains explicable as three
                        # panels rather than as a number with no provenance.
                        asset_count=reading.asset_count,
                    )
                )
                continue
            counted = _counted_quantity(reading, tariff, data.account_no)
            if counted is not None:
                # ── BR-RAT-090 (DEF-1813) · THE COUNT IS THE QUANTITY ────────
                # PO ruling 2026-08-20, option A: *"an unmetered service's
                # quantity is a COUNT OF ITS ASSETS ON THE UNIT"*, and the count
                # is **OBSERVED, never typed** — three carts on a unit bill
                # three carts, and adding one in the field changes the next bill
                # by itself. **Worked, ratified: 3 × `$15.00` = `$45.00`; remove
                # one and the next bill is `$30.00`.**
                #
                # It sits ABOVE the two absent branches below because it is not
                # an absence: this service HAS a quantity, it just did not come
                # from a register. Metering published the count (`asset_count`)
                # and refused by its own name where none could be determined, so
                # by the time a count reaches here it is a fact.
                services.append(
                    MeasuredService(
                        service_code=tariff.service,
                        tariff=tariff,
                        consumption=counted,
                        # NOT `estimated`. An estimate is a number nobody
                        # observed (BR-MET-029); a count is a number somebody
                        # did, and flagging it would print *"estimated"* on a
                        # bill for three carts a driver can see from the street.
                        estimated=False,
                        # CR-063 — on a per-size line this is the count of THAT
                        # size, not of the whole connection, so the row and the
                        # quantity beside it describe the same equipment.
                        asset_count=int(counted.amount),
                        size_class=getattr(tariff, "size_class", None),
                    )
                )
                continue
            if prices_no_consumption(tariff):
                # ⚠ DEF-161. A SERVICE THAT IS NOT MEASURED BY DESIGN IS NOT A
                # MISSING READ, and until this branch existed the two were
                # indistinguishable: a plan carrying a sewer service billed as a
                # percentage of water refused EVERY account it was on, because
                # metering answered `no_meter` for a service point that has no
                # meter and never will. 48 of 48 accounts broke on a booted
                # stack, and the only decision that let one through —
                # `bill_without_service` — DELETED the sewer line from the bill.
                #
                # BR-RAT-015 is CONFIRMED and says what sewer is priced off:
                # the WATER usage-charge dollars. There is no sewer register to
                # read, so there is nothing absent. It is carried with its own
                # reason so the exception screen never lists it as work, and it
                # still reaches the engine's second pass with the water basis —
                # that is what `calculate_account` does with this reason.
                services.append(
                    MeasuredService(
                        service_code=tariff.service,
                        tariff=tariff,
                        consumption=None,
                        absent_reason=ABSENT_NOT_USAGE_MEASURED,
                    )
                )
                continue
            # ⚠ **DEF-161 — THE DESIGNED ABSENCE TRAVELS THROUGH THE BRANCH
            # BELOW, AND THERE IS DELIBERATELY NO BRANCH OF ITS OWN.**
            #
            # This lane WROTE one — an explicit `if reading.absent_reason ==
            # ABSENT_SERVICE_NOT_METERED` arm returning the same object the line
            # below already returns — and then proved it RED as r11 step 2d
            # requires. **It went GREEN with the branch disabled**, which is the
            # only way to discover that a branch changes nothing: the fallback
            # below already carries metering's reason forward verbatim
            # (`reading.absent_reason`), so `service_not_metered` reaches
            # `MeasuredService` either way. The extra arm was dead code that
            # LOOKED like the fix — hard-won law 2's shape inside a single
            # function — so it is gone, and this note is what replaces it.
            #
            # **WHERE THE FIX ACTUALLY LIVES:** `runs.calculate_account` (and
            # `midperiod`) exempt this reason from BR-BIL-015's unresolved-read
            # refusal, which is what lets the service reach `base_only_services`
            # and bill its base charge. That is the line to break to prove this
            # behaviour, and `tests/test_def_161_designed_absence_bills.py` says
            # so in its own docstring.
            #
            # ⚠ **AND THE PASS-THROUGH IS NARROW ON PURPOSE.** It forwards the
            # reason METERING decided from the SERVICE's own declaration
            # (BR-RAT-081) and never generalises to "no consumption and no
            # meter". That generalisation is the fix DEF-161's ruling forbids in
            # as many words: it would bill a water meter nobody could reach as
            # base-only, on a document that foots, with no clerk ever seeing the
            # work. `no_meter` and `no_read` fall through here too and are NOT
            # exempt downstream, so both still stop the account.
            #
            # BR-BIL-015 — carried forward as an exception for a human, never
            # coerced to zero and never dropped.
            services.append(
                MeasuredService(
                    service_code=tariff.service,
                    tariff=tariff,
                    consumption=None,
                    absent_reason=(
                        reading.absent_reason
                        if reading is not None and reading.absent_reason
                        else ABSENT_NO_READING
                    ),
                )
            )
            continue

        if not reading.consumption.unit:
            # CLAUDE.md rule 3. Metering never emits a unitless quantity, so
            # this means the gather step built one by hand — a fault, not an
            # exception a clerk can resolve.
            raise BillingRuleError(
                f"account {data.account_no}, service {tariff.service}: a "
                "consumption arrived without its unit. CLAUDE.md rule 3 — a "
                "quantity always carries its unit and billing never assumes one."
            )

        services.append(
            MeasuredService(
                service_code=tariff.service,
                tariff=tariff,
                consumption=reading.consumption,
                estimated=reading.estimated,
                # DEF-098 — the read's identity travels with the quantity it
                # produced. Only on the MEASURED branch: the two branches above
                # have no read, and naming one there would lock a row that
                # priced nothing.
                read_id=reading.read_id,
                # 2026-09-30 — the meter, so the snapshot's `services` list
                # carries one entry per meter, each naming it.
                asset_id=getattr(tariff, "asset_id", None),
                # 🔒 DEF-BIL-8244 — a swap's two parts, for the snapshot.
                meter_parts=tuple(getattr(reading, "meter_parts", ()) or ()),
                # 🔒 DEF-BIL-9075 — every reading the quantity was summed from.
                chain_read_ids=tuple(getattr(reading, "chain_read_ids", ()) or ()),
            )
        )

    return MeasuredUsage(subscription=subscription, services=tuple(services))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a pure stage) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_029_stages.py 12 passed in 0.10s —
#         the runtime is itself evidence of purity (no database fixture).
#         PROVED RED: replacing the missing-read branch with the careless line
#         (coerce absence to Quantity(0, billed_unit)) fails exactly ONE test,
#         tc4, on `assert 2 == 1` — the missing water read had become a
#         measured 0 kgal and would have priced to $0.00 of usage on a real
#         customer's bill. One test, the right one.
# exceptions: (1) takes `AccountBillingData` ALONGSIDE its predecessor's output,
#         a narrow deviation from BR-BIL-037's "its predecessor's output and
#         nothing else" — the readings were gathered with the account and
#         threading them through SubscriptionContext, which has no use for
#         them, would make stage 1's contract carry stage 2's payload.
#         REPORTED for the reviewer. (2) A base-only account yields
#         consumption=None, NOT zero: a $0.00 usage line asserts the meter was
#         read, and it was not. (3) A unitless quantity RAISES rather than
#         becoming an exception case — metering never emits one, so it means
#         the gather step hand-built it, which is a fault no clerk can resolve
# exceptions: [DEF-1813 2026-08-28, BR-BIL-710] `_counted_quantity` turns
#         metering's OBSERVED asset count into the billable quantity for a
#         DECLARED-UNMETERED service (BR-RAT-090 — 3 carts x $15.00 = $45.00).
#         It sits ABOVE the two absent branches because it is not an absence:
#         the service HAS a quantity, it just did not come from a register. The
#         count arrives WITHOUT a unit (a count is not a measure — BR-RAT-036)
#         and leaves carrying the TARIFF's own `billed_unit`, which is the unit
#         the price is quoted per; a tariff stating none REFUSES (rule 3). NOT
#         flagged `estimated`: an estimate is a number nobody observed and a
#         count is a number somebody did. 🔒 This is a money decision in a file
#         no `human_owned.txt` glob matches — `DEF-2313`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
