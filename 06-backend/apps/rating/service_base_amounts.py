# ── Trace ──────────────────────────────────────────────
# Delegation: PO 2026-09-07, verbatim — *"you can research in amrket at
#          Municiapl utility in north amrica and put it there"*, said when the
#          PO was asked for one monthly base figure for each of the services
#          that charge nothing today. So the FIGURES below are LANE JUDGMENTS
#          made under that delegation. **THE PRODUCT OWNER HAS NOT SEEN ONE OF
#          THEM.** Every row carries the utility and the year it came from so
#          the PO can correct any single row in one word.
#          ⚠ **SEWER `$9.00` IS CONFIRMED 2026-10-01 (PO: "Yes").** Shown:
#          *"Every demo sewer account pays $9.00 on top of its percentage"*; PO
#          verbatim *"Is $9.00 a month right for the demo sewer base? Yes"*
#          (decision log 2026-10-01, "TWO PO RULINGS ON THE BASE CHARGE", (2)).
#          It is no longer a lane judgment the PO has not seen. The OTHER rows
#          are unchanged: still lane judgments, still unseen.
# Rules:   BR-RAT-080 (a base is paid because a CONNECTION EXISTS) · BR-RAT-088
#          (the CHARGE CODE owns the base amount, and the code and
#          `plan_services.base_charge` must agree to the cent or the bill is
#          REFUSED by name) · BR-RAT-092 / BR-RAT-089 (money to 4 decimals,
#          displayed to 2 — CLAUDE.md hard rule 2) · CR-013 part 1 / DEF-277
#          (a BLANK base means THIS SIZE IS NOT SERVED and stops the bill; a
#          stored `"0"` is a PRICE and prints `$0.00`)
# Golden:  none — and that is EVIDENCE rather than assurance, see the
#          `NOTHING FROZEN MOVES` section of the module docstring.
# Impacts: apps/rating/sample_data.py (`BASE_CHARGE_CODES`, `_plan_payloads`,
#          `backbone_plan_inputs`, `backbone_base_charge_codes`,
#          `capacity_base_charge_codes`) · the base charge line on every
#          seeded sewer / storm-water / broadband / battery / thermal / fire
#          bill
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

**WHAT A CONNECTION COSTS PER MONTH ON THE EIGHT SERVICES THAT USED TO CHARGE
NOTHING FOR SIMPLY EXISTING.**

`core/sample_fixture` has said since it was written that *"a base nobody signed
is a base this fixture does not invent"*, and it was right: the billing workbook
`[W] §1` names a monthly base for **electric, water and gas** and for nothing
else, so the other eight services all stated `$0.00`. On 2026-09-07 the Product
Owner was asked for one figure each and delegated the research instead —
*"you can research in amrket at Municiapl utility in north amrica and put it
there"*. This file is that research.

⚠ **CONFIRMED 2026-10-01 FOR SEWER ONLY — `BASE-S` `$9.00` IS THE DEMO DEFAULT
BY PO RULING** (*"Is $9.00 a month right for the demo sewer base? Yes"*, decision
log 2026-10-01). Every OTHER figure below is still exactly what the next
paragraph says.

⚠ **EVERY FIGURE HERE IS A LANE JUDGMENT AND NOT A PO RULING, AND THE
DIFFERENCE IS THE WHOLE REASON THIS FILE EXISTS SEPARATELY FROM THE FIXTURE.**
`WATER_BASE`, `ELECTRIC_BASE` and `GAS_BASE` are signed figures from a signed
workbook. These seven are a lane reading published North American **municipal**
rate schedules under a delegation. They are kept in their own file, each with
its utility and year, so that:

  * a reader can tell signed law from researched default at a glance;
  * the PO can correct ONE row without touching a signed one; and
  * `12-governance/02-decision-log.md`'s row for 2026-09-07 can say, truthfully,
    which figures a human has seen (three: `$8.00`, `$12.00`, `$6.00`) and which
    a human has not (all seven below).

── HOW EACH FIGURE WAS CHOSEN, AND AGAINST WHAT ────────────────────────────
The sanity check throughout is the SAME UTILITY's signed figures: water `$8.00`
residential / `$15.00` commercial, electric `$12.00` / `$48.00` / `$180.00`,
gas `$6.00`. A base that did not sit in a plausible relationship to an `$8.00`
water base would be wrong even if some real city printed it.

⚠ **AND FIVE OF THESE SERVICES ALREADY CHARGE FOR CAPACITY, WHICH IS WHY SEVERAL
FIGURES LOOK SMALL.** `core/sample_fixture.CAPACITY_UNIT_PRICES` already prices
solar at `$14.00`/kW, battery at `$3.00`/kW, storm water at `$4.50`/ERU and
broadband at `$0.10`/Mbps, and `service_size_classes.FIRE_DEFAULT_PRICES` prices
a fire line by DIAMETER (`$12.00` at 2" up to `$230.00` at 12"). The market's
whole monthly charge for those services is therefore ALREADY partly on the bill.
**What a base adds is the part that does NOT vary with size** — the account, the
billing, the meter reading — so each figure below is chosen so that the TOTAL a
customer pays lands inside the published municipal range, not so that the base
alone matches a published headline number. The worked total is stated on every
row for exactly that reason.

⚠ **NOTHING FROZEN MOVES, AND HERE IS THE EVIDENCE RATHER THAN THE CLAIM
(hard-won law 1).** The ❄️ FROZEN B4/B5 golden figures are built by
`06-backend/tests/golden/conftest.py`, which hands the engine a literal
`rating_seam.TariffConfig(... base_charge=Decimal("18.50") ...)` and reads no
tenant, no plan and no charge code at all. Not one of the eleven services this
file names appears in a B5 worked example: B4/B5 price water, electric, gas,
sewer-as-a-percentage and trash-per-cart. The golden suite was run either side
of this change and reported in the decision-log row.

⚠ **AND ONE CONSTRAINT STOPS EVERY BILL IF IT IS GOT WRONG (CR-013 part 2).**
A charge code may state a FLAT AMOUNT **or** a PER-SIZE TABLE and never both —
`rating.charges.amount_and_size_table` refuses the payload and
`resolve_charge_codes` refuses the BILL on billing day. None of the seven
services below is in `base_size_amounts.LADDERED_SERVICES`, so
`base_size_amounts.size_amounts()` returns `[]` for every one of them and the
seeder writes a FLAT amount, exactly as it does today. **Raising a base here
does not arm that trap; adding one of these services to `LADDERED_SERVICES`
without also giving it a `CAPACITY_RATIOS` entry would.**

⚠ **WHY NONE OF THEM GETS A SIZE LADDER, STATED SO IT IS NOT REDISCOVERED AS AN
OMISSION.** `base_size_amounts`' ladder answers *"what does a bigger connection
pay for its base"*, and for five of these seven that question is ALREADY
answered by the capacity price above — a fire line's diameter, a battery's kW, a
property's ERUs. A second size axis on the base would charge the same capacity
twice. Sewer cannot have one at all: `service_size_classes` rules sewer to have
**no size classes**. Thermal could have one (chilled water is banded ≤25 /
25–100 / 100+ tons) and does not, because a ladder needs a RATED CAPACITY RATIO
and nobody has stated one for tons — that is the follow-up, not this file.

── WHAT COULD NOT BE SOURCED ───────────────────────────────────────────────
**`thermal_heat` is the weakest row in this file and is flagged rather than
smoothed.** A municipal district-energy utility (Jamestown, New York Board of
Public Utilities) confirms the SHAPE — a flat monthly *meter charge* "billed
whether or not there is any heat consumption", separate from the delivery charge
and the fuel-cost adjustment — but no published district-heat customer charge in
dollars was readable from this environment. `$20.00` is therefore set from the
house relationship (thermal is a commercial/institutional connection, so it
should sit above commercial water's `$15.00` and below commercial electric's
`$48.00`) and NOT from a rate sheet. **It is the first row to ask the PO about.**

⚠ **AND ONE ROW IS A QUESTION FOR THE PO RATHER THAN A GAP IN THE RESEARCH:
`fire` IS `$0.00`, AND A NON-ZERO FIGURE THERE COLLIDES WITH A SIGNED ONE.** The
market's fire charge is the DIAMETER charge and this product already bills it,
so the research says zero on its own — but a lane that disagreed and set, say,
`$5.00` would move the going-live customer's warehouse from the `$60.00` the
Product Owner signed on 2026-09-03 to `$65.00`. **A collision with a signed
figure goes to the PO with its supersession stated (CLAUDE.md hard-won law 13);
it is not a lane's to absorb.** `tests/test_cr063_c3_fire_priced.py` asserts
`$60.00`, `$12.00` and `$84.00` and goes RED on any non-zero fire base, which is
the check doing its job rather than an obstacle to route around.
"""

from __future__ import annotations

from decimal import Decimal

#: `service code → (monthly base as a 4-decimal string, the source sentence)`.
#:
#: ⚠ **THE SOURCE IS PART OF THE DATUM, NOT A COMMENT BESIDE IT.** A figure with
#: no utility and no year is a figure somebody invented, and CLAUDE.md's standing
#: rule is that AI implements signed law and never invents it. The sentence is
#: carried in the structure so `--report` and the review-ledger row can print the
#: figure and its evidence together, and so deleting one cannot leave the other.
#:
#: Money is stored to FOUR decimals (CLAUDE.md hard rule 2), so every value is
#: written at four decimals here and never re-quantized downstream.
RESEARCHED_BASES: dict[str, tuple[str, str]] = {
    # ── SEWER ────────────────────────────────────────────────────────────────
    # Municipal sewer virtually always carries a fixed monthly charge, and it
    # sits AT OR ABOVE the water fixed charge in the same town, because sewer
    # has no meter of its own and its costs are almost entirely fixed.
    #
    # Town of Lexington, South Carolina — rates effective July 2025 — prints a
    # sewer *monthly customer service charge* of **$9.92** inside town ($16.86
    # outside). Bellaire, Texas FY2025 (effective 1 October 2024) charges a
    # sewer base of $11.73; DeSoto, Texas (Ordinance 2457-25, adopted
    # 16 September 2025) $15.29; Augusta, Kansas (effective 1 January 2025)
    # $27.85. The Texas and Kansas figures include a usage allowance and ours
    # does not, so the LOW end of the range is the honest comparator.
    #
    # **$9.00 against this product's $8.00 water base is that relationship at
    # this product's scale**, and it is a figure a utility would print.
    # ⚠ CONFIRMED 2026-10-01 — PO verbatim: *"Is $9.00 a month right for the
    # demo sewer base? Yes"*.
    # Worked: a seeded residential sewer line goes from $0.00 to $9.00 a month
    # before any volumetric charge.
    "sewer": (
        "9.0000",
        "Town of Lexington, South Carolina, rates effective July 2025: sewer "
        "monthly customer service charge $9.92 inside town. Bellaire, Texas "
        "FY2025 $11.73; DeSoto, Texas Ordinance 2457-25 (2025) $15.29; "
        "Augusta, Kansas (2025) $27.85 — the last three include a usage "
        "allowance this product's base does not, so $9.00 is the low end of "
        "the municipal range and sits just above this utility's own $8.00 "
        "water base, which is the relationship those towns print.",
    ),
    # ── STORM WATER ──────────────────────────────────────────────────────────
    # The Western Kentucky University Stormwater Utility Survey — the annual
    # census of US stormwater utilities, run since 2007 — puts the 2026 average
    # monthly single-family residential fee at **$6.33** across 2,202
    # utilities (2016: average $5.14, median $4.00). Urbandale, Iowa charges
    # $9.00 per ERU from 1 July 2025; Iowa cities generally run $3–$15.
    #
    # ⚠ This product ALREADY charges `$4.50` per ERU
    # (`fixture.CAPACITY_UNIT_PRICES["storm_water"]`), so the base is the
    # fixed component only. **$2.00 + $4.50 = $6.50 for a single-family home**
    # — the national average, and a printable figure.
    "storm_water": (
        "2.0000",
        "Western Kentucky University Stormwater Utility Survey 2026: national "
        "average monthly single-family fee $6.33 across 2,202 US stormwater "
        "utilities (2016 survey: average $5.14, median $4.00). Urbandale, Iowa "
        "$9.00 per ERU from 1 July 2025; Iowa range $3–$15. This product "
        "already charges $4.50 per ERU, so $2.00 is the fixed component and a "
        "single-family home pays $6.50 a month in total — the national average.",
    ),
    # ── BROADBAND ────────────────────────────────────────────────────────────
    # Municipal fibre prints ONE flat price per speed tier. Longmont, Colorado
    # (NextLight, city-owned, 2025): 100 Mbps **$39.95**, 1 Gbps $69.95
    # ($59.95 loyalty). Wilson, North Carolina (Greenlight, city-owned):
    # 50 Mbps $39.95, 2 Gbps $99.95.
    #
    # ⚠ This product already charges `$0.10` per Mbps, so 100 Mbps costs
    # `$10.00` today. **$30.00 + $10.00 = $40.00 for a 100 Mbps connection** —
    # NextLight's price for the same speed, to five cents.
    #
    # ⚠ **AND THE GIG TIER OVERSHOOTS, WHICH IS A FINDING ABOUT THE PER-Mbps
    # RATE AND NOT ABOUT THIS BASE.** At 1,000 Mbps the same arithmetic gives
    # $30.00 + $100.00 = $130.00 against NextLight's $69.95. No base can fix
    # that: $0.10/Mbps is linear where the market is nearly flat. Reported to
    # the PO rather than corrected here, because the unit price is a PO figure
    # and this delegation covers bases only.
    "broadband": (
        "30.0000",
        "Longmont, Colorado (NextLight, city-owned, 2025): 100 Mbps $39.95, "
        "1 Gbps $69.95. Wilson, North Carolina (Greenlight, city-owned): "
        "50 Mbps $39.95. This product already charges $0.10 per Mbps, so "
        "$30.00 puts a 100 Mbps connection at $40.00 — NextLight's price for "
        "the same speed. At 1 Gbps the total overshoots the market ($130.00 "
        "against $69.95) because the per-Mbps rate is linear and the market is "
        "nearly flat; that is the unit price's problem, not the base's.",
    ),
    # ── BATTERY ──────────────────────────────────────────────────────────────
    # There is no established municipal monthly charge for a customer-owned
    # home battery. What the market has is PROGRAMME fees: Evergy's residential
    # battery-storage pilot (2025) charges **$10.00 a month** and the utility
    # owns the battery and installs it free; Green Mountain Power's
    # Bring-Your-Own-Device programme charges NOTHING monthly for a
    # customer-owned one and pays an upfront incentive instead.
    #
    # ⚠ This product already charges `$3.00` per kW, so a 10 kW battery costs
    # `$30.00` today. **$5.00 is the enrolment/account component**, between the
    # $10.00 charged where the utility owns the hardware and the $0.00 charged
    # where the customer does. A 10 kW battery totals $35.00 a month.
    "battery": (
        "5.0000",
        "Evergy residential battery-storage pilot (2025): $10.00 a month "
        "programme fee, utility-owned battery, free installation. Green "
        "Mountain Power Bring-Your-Own-Device: no monthly fee for a "
        "customer-owned battery. $5.00 is the enrolment and account component "
        "between the two; with this product's existing $3.00 per kW a 10 kW "
        "battery totals $35.00 a month.",
    ),
    # ── FIRE ─────────────────────────────────────────────────────────────────
    # ⚠ **$0.00, AND IT IS A FINDING WITH TWO INDEPENDENT REASONS RATHER THAN
    # A ROW NOBODY GOT TO.**
    #
    # **(1) THE MARKET'S FIRE CHARGE *IS* THE DIAMETER CHARGE, AND THIS PRODUCT
    # ALREADY LEVIES IT.** Every municipal private-fire-service schedule found
    # prices ONE monthly charge by pipe diameter and prints no separate customer
    # charge beside it: Athens-Clarke County, Georgia FY2025 charges $1.50 at
    # 2", $5.00 at 4" and $10.00 at 6"; East Bay Municipal Utility District
    # charges $37.66, $107.36 and $209.87 for the same three; Santa Rosa,
    # California and Minneapolis both codify the charge by connection size.
    # `service_size_classes.FIRE_DEFAULT_PRICES` is exactly that schedule
    # ($12.00 at 2" to $230.00 at 12", PO ruling 2026-09-02 amended 2026-09-03)
    # and it sits inside that bracket. **A flat base on top would be a second
    # charge for the same connection.** The only fixed fire-service fee found
    # anywhere is an ANNUAL INSPECTION fee — Brookville, Ohio's municipal code
    # charges $15.00 a year — which is a periodic inspection, not a monthly
    # service charge, and belongs on a work order rather than in a base.
    #
    # **(2) AND A NON-ZERO FIGURE HERE WOULD MOVE A SIGNED NUMBER ON A REAL
    # CUSTOMER WITHOUT A RULING.** `CR-063` exists because a utility is being
    # onboarded on fire — PO, *"we need it for one of the customer we want to go
    # live"* — and the PO signed that customer's warehouse at **$60.00** a month
    # on 2026-09-03, in the same breath as taking the private hydrant out
    # (*"remove private hydrants from list"*, −$50.00 a month on that customer).
    # A $5.00 base would make it $65.00. **That is a collision with a signed
    # figure, and CLAUDE.md hard-won law 13 says a collision goes to the PO with
    # its supersession stated — it is not a lane's to absorb.** It is put to
    # them in the report and in the decision-log row instead, with the
    # arithmetic, so they can rule in one word.
    #
    # ⚠ **`"0"` IS A PRICE AND AN OMISSION IS A REFUSAL** (CR-013 part 1 /
    # DEF-277), so fire is STATED at zero here rather than left out of the map.
    "fire": (
        "0.0000",
        "NO SEPARATE CHARGE FOUND, and this product already bills the one the "
        "market does levy. Every municipal private-fire-service schedule found "
        "prices a single monthly charge BY PIPE DIAMETER with no customer "
        'charge beside it: Athens-Clarke County, Georgia FY2025 $1.50 at 2", '
        '$5.00 at 4", $10.00 at 6"; East Bay Municipal Utility District '
        "$37.66 / $107.36 / $209.87 for the same three. This product's own "
        'FIRE_DEFAULT_PRICES ($12.00 at 2" to $230.00 at 12") is that '
        "schedule and sits inside that bracket, so a flat base would charge "
        "the same connection twice. The only fixed fire fee found is "
        "Brookville, Ohio's $15.00 a YEAR inspection charge, which is an "
        "inspection and not a monthly service charge. ⚠ AND a non-zero figure "
        "would move the going-live customer's warehouse from the $60.00 the PO "
        "signed on 2026-09-03 — a collision with a signed figure, which goes "
        "to the PO rather than being absorbed by a lane.",
    ),
    # ── THERMAL / HEAT ───────────────────────────────────────────────────────
    # ⚠ **THE WEAKEST ROW IN THIS FILE — A STRUCTURE SOURCE AND NO PRICE
    # SOURCE.** Jamestown, New York Board of Public Utilities (municipal
    # district heat) bills a flat monthly METER CHARGE per meter, "billed
    # whether or not there is any heat consumption", separate from the delivery
    # charge and the fuel-cost adjustment — which is exactly the shape a base
    # charge is. Its dollar figure is not in any page that could be read from
    # here, and no other municipal district-energy rate sheet was reachable.
    #
    # So `$20.00` is set from the HOUSE relationship instead: thermal's ratified
    # size classes are chilled water at ≤25 / 25–100 / 100+ TONS, i.e. a
    # commercial or institutional building, so its base should sit above
    # commercial water's $15.00 and well below commercial electric's $48.00.
    # **This is the first row to put to the PO.**
    "thermal_heat": (
        "20.0000",
        "Jamestown, New York Board of Public Utilities (municipal district "
        "heat) bills a flat monthly meter charge per meter, billed whether or "
        "not there is any heat consumption, separate from the delivery charge "
        "and fuel-cost adjustment — the shape of a base charge. ⚠ NO PUBLISHED "
        "DISTRICT-HEAT DOLLAR FIGURE WAS READABLE, so $20.00 comes from the "
        "house relationship instead: thermal's size classes are chilled water "
        "in TONS, i.e. a commercial building, so the base sits above this "
        "utility's $15.00 commercial water base and well below its $48.00 "
        "commercial electric base. WEAKEST FIGURE IN THE SET.",
    ),
    # ── SOLAR ────────────────────────────────────────────────────────────────
    # ⚠ **$0.00 IS THE FINDING, NOT A GAP.** Most North American municipal
    # utilities levy NO monthly charge for a customer-owned rooftop array: the
    # customer already pays the ordinary electric customer charge, which is
    # $12.00 on this utility. Where a charge does exist it is PER kW and not
    # fixed — Palmetto Electric Cooperative charges $5.00 per kW per month of
    # installed PV; New York's 2022 published Customer Benefit Contribution
    # rates run $0.30–$1.33 per kW per month. **This product already expresses
    # that as solar's $14.00 per kW capacity price**, so a fixed base would be
    # a second charge the market does not levy.
    #
    # Bowling Green, Ohio's municipal utility does levy a fixed rooftop-solar
    # charge (about $56 a month for one customer) and is being sued over it,
    # which is itself evidence that a fixed solar charge is not settled
    # practice.
    #
    # ⚠ **`"0"` IS A PRICE AND AN OMISSION IS A REFUSAL** (CR-013 part 1 /
    # DEF-277): a BLANK base means *this size is not served* and stops the
    # bill, a stored zero prints `$0.00`. So solar is stated here at zero
    # rather than left out of the map, and the seeded figure is UNCHANGED.
    "solar": (
        "0.0000",
        "NO CHARGE FOUND, and that is the finding. Most North American "
        "municipal utilities levy nothing monthly for a customer-owned rooftop "
        "array — the customer already pays the ordinary electric customer "
        "charge ($12.00 here). Where a charge exists it is PER kW, not fixed: "
        "Palmetto Electric Cooperative $5.00 per kW per month; New York 2022 "
        "Customer Benefit Contribution rates $0.30–$1.33 per kW per month. "
        "This product already prices solar at $14.00 per kW. Bowling Green, "
        "Ohio's municipal fixed rooftop-solar charge (about $56 a month) is "
        "under litigation, which is itself evidence the practice is unsettled.",
    ),
}

#: The three SIGNED bases, named here so a reader can see at a glance what this
#: file does NOT touch. They come from the billing workbook `[W] §1` through
#: `core/sample_fixture`, they are the PO's own figures, and a value for any of
#: them in `RESEARCHED_BASES` would be this file quietly overwriting signed law.
#: `_validate()` refuses that below.
SIGNED_ELSEWHERE: frozenset[str] = frozenset({"water", "electric", "gas"})

#: `trash` is a PO RULING at zero and NOT a gap — `OQ-317` option A retired the
#: trash base because trash bills per CART ($15.00 each, `BR-RAT-090`). Giving
#: it a standing charge would reverse a decision the Product Owner made, so it
#: is named here and deliberately absent from `RESEARCHED_BASES`.
RULED_ZERO: frozenset[str] = frozenset({"trash"})


def _validate() -> None:
    """Refuse at import if this file has grown a row it must not own.

    ⚠ **AT IMPORT AND NOT IN A TEST, because the failure it prevents is
    silent.** A `"water"` key here would override a ❄️-adjacent signed figure
    on every seeded tenant with `tsc`, the suite and every gate green — the
    exact shape of `DEF-CUS-3653`, where a retired value took a screen line
    with it and nothing could see the absence.
    """
    for service in RESEARCHED_BASES:
        if service in SIGNED_ELSEWHERE:
            raise ValueError(
                f"{service!r} has a SIGNED base in the billing workbook [W] §1 "
                "(water $8.00/$15.00, electric $12.00/$48.00/$180.00, gas "
                "$6.00) and reaches the seeder through core/sample_fixture. "
                "apps/rating/service_base_amounts holds RESEARCHED defaults "
                "for the services the workbook prices nowhere; a row here "
                "would silently overwrite signed law. Change the workbook "
                "figure through a finance re-sign (HUMAN-GUIDE §6) instead."
            )
        if service in RULED_ZERO:
            raise ValueError(
                f"{service!r} is ruled to $0.00 by the Product Owner (OQ-317 "
                "option A — trash bills per CART at $15.00, BR-RAT-090), not "
                "merely unpriced. A researched default here would reverse a "
                "decision the PO made."
            )
        amount, source = RESEARCHED_BASES[service]
        Decimal(amount)  # refuses a malformed figure at import
        if not source.strip():
            raise ValueError(
                f"{service!r} states a base of {amount} with no source. A "
                "figure with no utility and no year is a figure somebody "
                "invented; CLAUDE.md's standing rule is that AI implements "
                "signed law and never invents it."
            )


_validate()


def base_for(service_code: str, default: str) -> str:
    """This service's monthly base, or `default` where none was researched.

    `default` is what the caller states today — `fixture.CAPACITY_BASE`,
    `fixture.BACKBONE_BASE`'s pair, or a literal — so a service this file does
    not name keeps exactly the figure it has, and no call site changes meaning
    when it is added or removed here.
    """
    row = RESEARCHED_BASES.get(service_code)
    return row[0] if row is not None else default


def source_for(service_code: str) -> str | None:
    """The utility and year behind this service's figure, or `None`.

    Read by the reporting helper and by the human-review ledger row. Kept
    beside `base_for` so the figure and its evidence cannot be quoted apart.
    """
    row = RESEARCHED_BASES.get(service_code)
    return row[1] if row is not None else None


def report() -> list[tuple[str, Decimal, str]]:
    """`(service, base, source)` for every researched figure — the table a
    person reads, in this file's own declaration order."""
    return [
        (service, Decimal(amount), source) for service, (amount, source) in RESEARCHED_BASES.items()
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO delegation 2026-09-07 · BR-RAT-080 / BR-RAT-088 / CR-013 part 2
# generated: 2026-09-07 by the service-base-research lane (claude)
# gates: ruff · black · pytest tests/test_service_base_amounts.py
# status: VERIFIED-UNRATIFIED — 🔒 money path, HUMAN-REVIEW-PENDING; the PO
#         has seen NONE of these seven figures
# ──────────────────────────────────────────────────────────
