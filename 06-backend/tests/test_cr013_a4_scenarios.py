# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-15 (the resolution engine — the four §A4 scenarios as
#           fixtures, design §B2)
#           Screens: — (the figures print on S31.2; nothing here renders)
# Rules:    BR-RAT-001/002/026 (multiplier before tiers; pure tiers) ·
#           BR-RAT-003 (round per line, half-up, 2dp, once) · BR-RAT-005 /
#           B4.2 (tax base = usage + base, summed from the ROUNDED lines) ·
#           BR-RAT-036 (a tax states one form) · BR-RAT-007 (the version in
#           force at the service date)
# Rulings:  PO 2026-08-19 — the meter multiplier and the premises factor are
#           two different factors; a plan cannot override a price; the fire
#           line is a charge code
# Golden:   NOT a B5 GT. These four are CR-013's OWN pinned figures, shown to
#           the PO in the design's §A4 and recomputed here to the cent.
# Tests:    this file IS the §A4 fixture set (design §B4 tier 1, first four)
# ───────────────────────────────────────────────────────
"""§A4's four scenarios, run — the same catalogue narrowing four different ways.

**WHY THESE FOUR AND NOT A HUNDRED.** Design §A4's point is not coverage, it is
that **three different selectors each changed the answer on their own**:

    S1 -> S2   the PREMISES jurisdiction moved it (and moved TWO things at once,
               in opposite directions: every line goes up 50% and the city
               franchise fee disappears)
    S1 -> S3   the CUSTOMER CLASS moved it (CAP-W appears, TX State applies)
    S1 -> S4   the SERVICE COUNT moved it

So the fixture runs ONE catalogue through `rating.resolution` and then through
the engine, and asserts the printed figures. A test that only checked totals
would pass with the two multipliers swapped; these check the lines.

⚠ TWO OF THE FOUR PRINTED TOTALS ARE NOT REACHABLE TODAY, AND THE FIXTURE SAYS
SO RATHER THAN QUIETLY DROPPING A LINE.
Each scenario states TWO figures:

  * `printed_total` — the figure in the design, shown to the PO. Kept verbatim.
  * `reachable_total` — the same bill with the objects this product cannot yet
    express removed, recomputed line by line in the docstring.

and `unmodelled` names every object standing between them, with the epic that
will build it. S3 and S4 have an EMPTY `unmodelled`, so their printed totals are
asserted exactly: **$2,072.71** and **$126.19**. S1 and S2 each lose the
PAPERLESS discount (there is no discounts table in this product — CR-013 part 3
/ EP-RAT-12) and the Water Conservation surcharge (a per-unit tax; BR-RAT-036's
per-unit form is unbuilt and `compute_tax` has named that gap since it was
written). The day either lands, its line comes out of `unmodelled` and this
fixture demands the money actually move.

**Nothing here adjusts a figure to match the code.** The four arithmetics in
§A4 were re-derived independently while writing this file and all four foot
exactly; where the engine and the design disagreed, the code was wrong and was
fixed — the City Franchise Fee is 1.5% of the ELECTRIC lines and was being
computed over the whole bill, which is the `applies_to_services` narrowing added
to `compute_tax` on 2026-08-19.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.billing import rating_seam
from apps.rating import resolution as R

SERVICE_DATE = date(2026, 7, 31)
PERIOD = rating_seam.BillingPeriod(cycle_days=31, service_days=31)

# ── THE CATALOGUE — one, for all four scenarios (§A4: "Same catalogue every
# time. The point is how differently the same 31 objects narrow.")
#
# ⚠ THE COUNT "31 PRICED OBJECTS" IS r10's DRAWING AND IS STALE. Measured on the
# live seeded tenant by the CR-010 lane on 2026-08-19: 5 plans · 6 rate schedules
# · 23 charge codes · 0 discounts · 2 tax rates over 5 jurisdictions = 31, and a
# tenant provisioned at HEAD gets 34 because the five ruled Texas tax rates now
# seed. Charge codes went 13 -> 23, which is the increase the PO was pointing at
# (*"we have increase this number check out seed data"*). The narrowing argument
# is unaffected — a bigger catalogue makes it stronger — so this fixture states
# only the objects the four scenarios touch and does not pretend to be the seed.

RES_STD = R.PlanVersion(
    plan_id="RES-STD",
    version=3,
    services=("electric", "water", "sewer"),
    effective_from=date(2026, 1, 1),
    schedules={"electric": "SCH-E-RES", "water": "SCH-W-RES", "sewer": "SCH-S"},
)
RES_ELEC = R.PlanVersion(
    plan_id="RES-ELEC",
    version=1,
    services=("electric",),
    effective_from=date(2026, 1, 1),
    schedules={"electric": "SCH-E-RES"},
)
COMM_SM = R.PlanVersion(
    plan_id="COMM-SM",
    version=2,
    services=("electric", "water", "water_capacity"),
    effective_from=date(2026, 1, 1),
    schedules={
        "electric": "SCH-E-TOU",
        "water": "SCH-W-COMM",
        "water_capacity": "SCH-W-CAP",
    },
)

SCHEDULES = (
    R.ScheduleVersion(
        version_id="TV-E-RES-2026",
        service="electric",
        tariff_id="SCH-E-RES",
        effective_from=date(2026, 1, 1),
        size_rows={"1φ 100A": Decimal("18.50")},
    ),
    R.ScheduleVersion(
        version_id="TV-W-RES-2026",
        service="water",
        tariff_id="SCH-W-RES",
        effective_from=date(2026, 1, 1),
        size_rows={'5/8"': Decimal("12.00")},
    ),
    R.ScheduleVersion(
        version_id="TV-S-2026",
        service="sewer",
        tariff_id="SCH-S",
        effective_from=date(2026, 1, 1),
        # "flat everywhere" — one size row, and R5 never touches it (below).
        size_rows={"—": Decimal("8.00")},
    ),
    R.ScheduleVersion(
        version_id="TV-E-TOU-2026",
        service="electric",
        tariff_id="SCH-E-TOU",
        effective_from=date(2026, 1, 1),
        size_rows={"3φ": Decimal("34.00")},
    ),
    R.ScheduleVersion(
        version_id="TV-W-COMM-2026",
        service="water",
        tariff_id="SCH-W-COMM",
        effective_from=date(2026, 1, 1),
        size_rows={'2"': Decimal("64.00")},
    ),
    R.ScheduleVersion(
        version_id="TV-W-CAP-2026",
        service="water_capacity",
        tariff_id="SCH-W-CAP",
        effective_from=date(2026, 1, 1),
        # A capacity schedule carries no fixed monthly charge of its own — the
        # capacity RATE is the price. An explicit 0, not a blank: DEF-277 makes
        # blank mean "not served" and this size is served.
        size_rows={'2"': Decimal("0")},
    ),
)

#: R4's charge codes. `CAP-W` is the one that moves with the CUSTOMER CLASS —
#: §A4 S3: *"`CAP-W` appears because the class is Commercial"*.
#:
#: ⚠ `charge_type` / `auto_apply` ADDED 2026-08-28 (`BR-RAT-730`, `DEF-493`) and
#: they change no figure in this file. §A4 S3 prints `CAP-W` as a line on an
#: ORDINARY MONTHLY BILL — *"capacity @ 2" (commercial only) $120.00"* — so the
#: scenario has always said this code recurs and applies by itself; the fixture
#: now states it, because R4 no longer infers recurrence from a code merely
#: having an amount. Leaving it unstated would silently drop the $120.00 line
#: and the total would move to $1,952.71, which is what made this test go red
#: and is exactly the reading `DEF-493` exists to stop being implicit.
CHARGE_CODES = (
    R.ChargeCode(
        code="CAP-W",
        service="water",
        customer_classes=("commercial", "industrial"),
        charge_type="recurring",
        auto_apply=True,
        amounts={'2"': Decimal("120.00"), '5/8"': None},
    ),
)

#: R7's taxes. Every condition here decides APPLICABILITY; `services` on the
#: franchise fee additionally narrows its BASE, which is the difference between
#: $1.82 and $2.83 on S1.
TAXES = (
    R.TaxRule(
        code="TX State Utility",
        tax_id="TAX-TX",
        rate=Decimal("0.0625"),
        customer_classes=("commercial", "industrial"),
    ),
    R.TaxRule(code="Bexar County", tax_id="TAX-BEXAR", rate=Decimal("0.02")),
    R.TaxRule(
        code="PUC Regulatory Fee",
        tax_id="TAX-PUC",
        flat_amount=Decimal("0.85"),
        services=("electric",),
    ),
    R.TaxRule(
        code="City Franchise",
        tax_id="TAX-CITY",
        rate=Decimal("0.015"),
        services=("electric",),
        inside_city_only=True,
    ),
)


def catalogue(plan: R.PlanVersion) -> R.Catalogue:
    """The whole catalogue with ONE plan in it.

    One plan at a time because R1 refuses two plan versions in force on one date
    and an account is on exactly one plan; the SCHEDULES, CHARGE CODES and TAXES
    are shared verbatim across all four, which is §A4's whole claim.
    """
    return R.Catalogue(
        plan_versions=(plan,),
        schedule_versions=SCHEDULES,
        charge_codes=CHARGE_CODES,
        taxes=TAXES,
        outside_city_factor=Decimal("1.5"),
        # §A4 S2: *"BASE-S $8.00 (flat everywhere — the multiplier does NOT
        # touch sewer)"*.
        outside_city_exempt_services=("sewer",),
    )


# ── Pricing configuration, per schedule ─────────────────────────────────────
#
# The RESOLUTION chain says which schedule version and which base charge; these
# say how that schedule turns a quantity into money. They are separate on
# purpose — the narrowing is what CR-013 is about and the arithmetic is B4/B5,
# frozen, and already proved by the golden harness.

TIERS_E_RES = (
    rating_seam.Tier(upper=Decimal("500"), unit_price=Decimal("0.11")),
    rating_seam.Tier(upper=None, unit_price=Decimal("0.14")),
)
TIERS_W_RES = (
    rating_seam.Tier(upper=Decimal("4"), unit_price=Decimal("3.20")),
    rating_seam.Tier(upper=Decimal("10"), unit_price=Decimal("4.80")),
    rating_seam.Tier(upper=None, unit_price=Decimal("7.20")),
)
TIERS_W_COMM_SUMMER = (
    rating_seam.Tier(upper=Decimal("10"), unit_price=Decimal("4.10")),
    rating_seam.Tier(upper=None, unit_price=Decimal("6.40")),
)
WINDOWS_E_TOU = (
    rating_seam.TouWindow(label="On-peak", unit_price=Decimal("0.22"), channel="tou_on"),
    rating_seam.TouWindow(label="Off-peak", unit_price=Decimal("0.09"), channel="tou_off"),
)


def tiered(service, unit, tiers, resolved: R.ServiceResolution) -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service=service,
        model="tiered",
        billed_unit=unit,
        base_charge=resolved.base_charge,
        tiers=tiers,
        version_id=resolved.schedule_version_id,
        jurisdiction_factor=resolved.money_factor,
    )


def tax_rules(resolved: R.Resolution) -> tuple[rating_seam.TaxRule, ...]:
    """R7's attached rules, onto the seam's shape. Nothing is filtered here —
    the narrowing already happened and this is a translation."""
    return tuple(
        rating_seam.TaxRule(
            code=rule.code,
            rate=rule.rate,
            tax_id=rule.tax_id,
            flat_amount=rule.flat_amount,
            applies_to_services=rule.services,
        )
        for rule in resolved.taxes
    )


def amounts(bill) -> dict[str, Decimal]:
    """Every line, by description, so an assertion names the line it means."""
    return {line.description: line.amount for line in bill.lines}


@dataclass(frozen=True)
class Unmodelled:
    """One object the design's scenario uses and this product cannot express.

    Named rather than deleted, because a scenario quietly missing a line is how
    a figure and the code that produces it drift apart without either looking
    wrong (hard-won law 1).
    """

    label: str
    amount: Decimal
    owner: str


PAPERLESS = Unmodelled(
    label="PAPERLESS discount",
    amount=Decimal("-1.00"),
    owner="EP-RAT-12 — there is no discounts table in this product; the table does not "
    "exist and the live tenant carries zero discounts. CR-013 part 3 owns the discount "
    "object, the enrolment table, verification, recertification and budget exhaustion.",
)
CONSERVATION = Unmodelled(
    label="Water Conservation Surcharge",
    amount=Decimal("0.25"),
    owner="BR-RAT-036's PER-UNIT tax form is unbuilt — r10 states it as '$0.25 / kgal · "
    "Tier 3+ usage only' and pricing it needs the tier-3 quantity that stage 5 does not "
    "receive. `compute_tax` has named this gap in its own docstring since it was written.",
)


# ── S1 · Residential Standard · inside city ─────────────────────────────────


def test_cr013_a4_s1__residential_inside_city():
    """§A4 S1 — 3 of 7 schedules · 5 of 13 charge codes · 4 of 6 taxes.

    ```
    BASE-E    electric base @ 1φ 100A                 $18.50
    USAGE-E   500 kWh × 0.11                          $55.00
    USAGE-E   340 kWh × 0.14                          $47.60
    BASE-W    water base @ 5/8"                       $12.00
    USAGE-W   4 kgal × 3.20                           $12.80
    USAGE-W   6 kgal × 4.80                           $28.80
    USAGE-W   1 kgal × 7.20                            $7.20
    BASE-S    sewer base (flat everywhere)             $8.00
              subtotal                                $189.90
    ```

    **PRINTED (§A4, shown to the PO): $195.60**, from a taxable base of $188.90
    after the PAPERLESS discount — Bexar 2.00% $3.78 · PUC $0.85 · City
    Franchise 1.50% of the $121.10 of electric $1.82 · Conservation $0.25.

    **REACHABLE TODAY: $196.37.** Remove the discount and the base is $189.90,
    so Bexar becomes 2.00% × 189.90 = 3.798 -> **$3.80**; the franchise fee does
    not move, because its base is the electric lines and the discount was never
    part of them; the conservation surcharge cannot be priced at all.

        189.90 + 3.80 + 0.85 + 1.82 = 196.37

    TX State does not fire — residential is exempt, and that is the CLASS
    selector doing its work before any arithmetic happens.
    """
    resolved = R.resolve(
        catalogue=catalogue(RES_STD),
        account=R.AccountFacts(account_no="A-1001", unit_id="U-1", customer_class="residential"),
        premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
        meters=(
            R.MeterFacts(service="electric", connection_size="1φ 100A"),
            R.MeterFacts(service="water", connection_size='5/8"'),
            R.MeterFacts(service="sewer", connection_size="—"),
        ),
        quantities={"electric": Decimal("840"), "water": Decimal("11")},
        service_date=SERVICE_DATE,
    )

    assert [rule.code for rule in resolved.taxes] == [
        "Bexar County",
        "PUC Regulatory Fee",
        "City Franchise",
    ]
    assert resolved.charge_codes == ()  # CAP-W is commercial only
    # DEF-361: this asserted `modelled is False` until 2026-08-20, when the six
    # discount tables had already existed for a day. This catalogue configures no
    # discounts, so the honest answer is a MODELLED empty — the account is
    # enrolled in nothing. The distinction still matters and has changed sides.
    #
    # ⚠ S1 is the scenario the ORDER rule is worked against: discounts apply
    # BEFORE taxes, so removing the $1.00 PAPERLESS discount moves Bexar County
    # from $3.78 to $3.80 — which is why "reachable" is $196.37 and not $194.60.
    # That case needs an enrolled account and belongs to EP-RAT-12's suite; this
    # assertion only fixes the shape S1 resolves to.
    assert resolved.discounts.modelled is True
    assert resolved.discounts.applied == ()
    assert resolved.service("electric").money_factor == Decimal("1")

    bill = rating_seam.price_bill(
        services=(
            (
                tiered("electric", "kWh", TIERS_E_RES, resolved.service("electric")),
                rating_seam.Quantity(amount=Decimal("840"), unit="kWh"),
            ),
            (
                tiered("water", "kgal", TIERS_W_RES, resolved.service("water")),
                rating_seam.Quantity(amount=Decimal("11"), unit="kgal"),
            ),
        ),
        base_only_services=(sewer_config(resolved),),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=tax_rules(resolved),
    )

    line = amounts(bill)
    assert line["electric base charge"] == Decimal("18.50")
    assert line["water base charge"] == Decimal("12.00")
    assert line["sewer base charge"] == Decimal("8.00")
    assert sum(ln.amount for ln in bill.lines_of("usage") if ln.service == "electric") == Decimal(
        "102.60"
    )
    assert sum(ln.amount for ln in bill.lines_of("usage") if ln.service == "water") == Decimal(
        "48.80"
    )
    assert bill.taxable_subtotal == Decimal("189.90")
    assert line["Tax Bexar County"] == Decimal("3.80")
    assert line["Tax PUC Regulatory Fee"] == Decimal("0.85")
    # 1.5% of the ELECTRIC lines (121.10), not of the whole 189.90 bill.
    assert line["Tax City Franchise"] == Decimal("1.82")
    assert bill.total == Decimal("196.37")
    assert unmodelled_note(bill.total, Decimal("195.60"), (PAPERLESS, CONSERVATION))


def sewer_config(resolved: R.Resolution) -> rating_seam.TariffConfig:
    """Sewer: a monthly base and no usage at all.

    ⚠ MODELLED AS `flat` AT A ZERO UNIT PRICE, AND THAT IS A GAP RATHER THAN A
    CHOICE. CR-013 part 1 names **Base only** as one of the six structures and
    `TARIFF_MODELS` has six entries of which `base_only` is not one — there is no
    plugin for it (EP-RAT-10). Routing it through `base_only_services` means the
    engine drops the usage line before it can exist (BR-BIL-028's own mechanism),
    so the zero never reaches a line, a total or a document. REPORTED here rather
    than papered over: the day `base_only` lands, this helper goes away.
    """
    return rating_seam.TariffConfig(
        service="sewer",
        model="flat",
        billed_unit="kgal",
        base_charge=resolved.service("sewer").base_charge,
        unit_price=Decimal("0"),
        version_id=resolved.service("sewer").schedule_version_id,
        jurisdiction_factor=resolved.service("sewer").money_factor,
    )


def unmodelled_note(engine_total, printed_total, gaps) -> bool:
    """Always True — it exists so the gap between the two figures is READ.

    A scenario whose printed total is unreachable must say what stands between
    the two, in the file, next to the number. Asserting an inequality here would
    add nothing: the engine total above is already pinned to the cent, and this
    records why it is not the figure in the design.
    """
    assert engine_total != printed_total or not gaps
    assert all(gap.owner for gap in gaps)
    return True


# ── S2 · the SAME account, outside city limits ──────────────────────────────


def test_cr013_a4_s2__the_same_account_outside_city_limits():
    """§A4 S2 — **two things change at once, in opposite directions.**

    ```
    BASE-E  $18.50 × 1.5 = $27.75    USAGE-E ×1.5 = $82.50 + $71.40
    BASE-W  $12.00 × 1.5 = $18.00    USAGE-W ×1.5 = $19.20 + $43.20 + $10.80
    BASE-S  $8.00 (flat everywhere — the multiplier does NOT touch sewer)
            subtotal $280.85
    ```

    The multiplier raises the bill 48% AND the City Franchise Fee **disappears**,
    because the premises is outside the city. An implementation that treats
    "outside city" as one flag with one consequence gets one of the two wrong,
    and this test fails on either.

    **PRINTED (§A4): $286.55** — $279.85 after PAPERLESS, Bexar $5.60, PUC
    $0.85, Conservation $0.25, no franchise.

    **REACHABLE TODAY: $287.32.** Base $280.85, Bexar 2.00% × 280.85 = 5.617 ->
    **$5.62**, PUC $0.85, no franchise, no conservation.

        280.85 + 5.62 + 0.85 = 287.32
    """
    resolved = R.resolve(
        catalogue=catalogue(RES_STD),
        account=R.AccountFacts(account_no="A-1001", unit_id="U-1", customer_class="residential"),
        premises=R.PremisesFacts(inside_city_limits=False, county="Bexar"),
        meters=(
            R.MeterFacts(service="electric", connection_size="1φ 100A"),
            R.MeterFacts(service="water", connection_size='5/8"'),
            R.MeterFacts(service="sewer", connection_size="—"),
        ),
        quantities={"electric": Decimal("840"), "water": Decimal("11")},
        service_date=SERVICE_DATE,
    )

    # THE FRANCHISE FEE IS GONE — a different three of six, not a smaller share.
    assert [rule.code for rule in resolved.taxes] == ["Bexar County", "PUC Regulatory Fee"]
    assert resolved.service("electric").money_factor == Decimal("1.5")
    assert resolved.service("water").money_factor == Decimal("1.5")
    assert resolved.service("sewer").money_factor == Decimal("1")

    bill = rating_seam.price_bill(
        services=(
            (
                tiered("electric", "kWh", TIERS_E_RES, resolved.service("electric")),
                rating_seam.Quantity(amount=Decimal("840"), unit="kWh"),
            ),
            (
                tiered("water", "kgal", TIERS_W_RES, resolved.service("water")),
                rating_seam.Quantity(amount=Decimal("11"), unit="kgal"),
            ),
        ),
        base_only_services=(sewer_config(resolved),),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=tax_rules(resolved),
    )

    line = amounts(bill)
    assert line["electric base charge"] == Decimal("27.75")
    assert line["water base charge"] == Decimal("18.00")
    assert line["sewer base charge"] == Decimal("8.00")  # untouched
    assert sum(ln.amount for ln in bill.lines_of("usage") if ln.service == "electric") == Decimal(
        "153.90"
    )
    assert sum(ln.amount for ln in bill.lines_of("usage") if ln.service == "water") == Decimal(
        "73.20"
    )
    assert bill.taxable_subtotal == Decimal("280.85")
    assert line["Tax Bexar County"] == Decimal("5.62")
    assert "Tax City Franchise" not in line
    assert bill.total == Decimal("287.32")
    assert unmodelled_note(bill.total, Decimal("286.55"), (PAPERLESS, CONSERVATION))


# ── S3 · Small Commercial ───────────────────────────────────────────────────


def test_cr013_a4_s3__small_commercial_tou_and_capacity():
    """§A4 S3 — the CUSTOMER CLASS changed the tax set, not just the rates.

    ```
    BASE-E   @ 3φ                                      $34.00
    USAGE-E  2,400 kWh on-peak × 0.22                 $528.00
    USAGE-E  9,600 kWh off-peak × 0.09                $864.00
    BASE-W   @ 2"                                      $64.00
    CAP-W    capacity @ 2" (commercial only)          $120.00
    USAGE-W  10 kgal × 4.10 (summer season)            $41.00
    USAGE-W  38 kgal × 6.40                           $243.20
             taxable base                           $1,894.20
             TX State Utility 6.25%    APPLIES        $118.39
             Bexar County 2.00%                        $37.88
             PUC fee $0.85 flat                         $0.85
             City Franchise 1.50% (electric)           $21.39
             TOTAL                                  $2,072.71
    ```

    **PRINTED = REACHABLE = $2,072.71.** No discount and no conservation
    surcharge, so this scenario is asserted to the cent with nothing removed.

    Two things are worth reading twice. `CAP-W` appears **because the class is
    Commercial** — R4 resolved it, and R4 also refuses it for a residential
    account at the same size. And the franchise fee is $21.39, which is 1.5% of
    the **$1,426.00 of electric** and not of the $1,894.20 bill; read as a
    whole-bill percent it would be $28.41, and the customer would be paying the
    city's electric franchise fee on their water.
    """
    resolved = R.resolve(
        catalogue=catalogue(COMM_SM),
        account=R.AccountFacts(account_no="A-2002", unit_id="U-2", customer_class="commercial"),
        premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
        meters=(
            R.MeterFacts(service="electric", connection_size="3φ"),
            R.MeterFacts(service="water", connection_size='2"'),
            R.MeterFacts(service="water_capacity", connection_size='2"'),
        ),
        quantities={"electric": Decimal("12000"), "water": Decimal("48")},
        service_date=SERVICE_DATE,
    )

    assert [rule.code for rule in resolved.taxes] == [
        "TX State Utility",
        "Bexar County",
        "PUC Regulatory Fee",
        "City Franchise",
    ]
    # R4 resolved CAP-W at this account's class AND its connection size.
    assert [(code.code, amount) for code, amount in resolved.charge_codes] == [
        ("CAP-W", Decimal("120.00"))
    ]

    electric = rating_seam.TariffConfig(
        service="electric",
        model="time_of_use",
        billed_unit="kWh",
        base_charge=resolved.service("electric").base_charge,
        windows=WINDOWS_E_TOU,
        version_id=resolved.service("electric").schedule_version_id,
        jurisdiction_factor=resolved.service("electric").money_factor,
    )
    capacity = rating_seam.TariffConfig(
        service="water_capacity",
        model="capacity",
        billed_unit="2in meter equivalent",
        base_charge=resolved.service("water_capacity").base_charge,
        # THE AMOUNT R4 RESOLVED, priced as one unit. `CAP-W` is a CHARGE CODE
        # (§A3: the charge code owns the amount) and charge codes do not reach a
        # bill as taxable lines yet — that is EP-RAT-11. Pricing the resolved
        # figure through the capacity model puts it in the tax base, where §A4
        # puts it, without inventing a number: the 120.00 below is R4's answer.
        capacity=rating_seam.CapacityRate(
            unit_label="2in meter equivalent",
            rate_per_unit=resolved.charge_codes[0][1],
        ),
        version_id=resolved.service("water_capacity").schedule_version_id,
        jurisdiction_factor=resolved.service("water_capacity").money_factor,
    )

    bill = rating_seam.price_bill(
        services=(
            (
                electric,
                rating_seam.Quantity(
                    amount=Decimal("12000"),
                    unit="kWh",
                    windows=(
                        rating_seam.WindowQuantity(
                            channel="tou_on",
                            quantity=rating_seam.Quantity(Decimal("2400"), "kWh"),
                        ),
                        rating_seam.WindowQuantity(
                            channel="tou_off",
                            quantity=rating_seam.Quantity(Decimal("9600"), "kWh"),
                        ),
                    ),
                ),
            ),
            (
                tiered("water", "kgal", TIERS_W_COMM_SUMMER, resolved.service("water")),
                rating_seam.Quantity(amount=Decimal("48"), unit="kgal"),
            ),
            (
                capacity,
                rating_seam.Quantity(amount=Decimal("1"), unit="2in meter equivalent"),
            ),
        ),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=tax_rules(resolved),
    )

    line = amounts(bill)
    assert line["electric base charge"] == Decimal("34.00")
    assert line["electric usage — On-peak"] == Decimal("528.00")
    assert line["electric usage — Off-peak"] == Decimal("864.00")
    assert line["water base charge"] == Decimal("64.00")
    assert sum(ln.amount for ln in bill.lines_of("usage") if ln.service == "water") == Decimal(
        "284.20"
    )
    # BR-RAT-029: a capacity charge is a BASE-kind line — taxable structurally,
    # like the base charge, rather than a usage line with an invented quantity.
    assert sum(line.amount for line in bill.lines if line.service == "water_capacity") == Decimal(
        "120.00"
    )
    assert bill.taxable_subtotal == Decimal("1894.20")
    assert line["Tax TX State Utility"] == Decimal("118.39")
    assert line["Tax Bexar County"] == Decimal("37.88")
    assert line["Tax PUC Regulatory Fee"] == Decimal("0.85")
    assert line["Tax City Franchise"] == Decimal("21.39")
    assert bill.total == Decimal("2072.71")


# ── S4 · Residential electric-only ──────────────────────────────────────────


def test_cr013_a4_s4__residential_electric_only():
    """§A4 S4 — the SERVICE COUNT moved it. 1 of 7 schedules · 2 charge codes ·
    3 of 6 taxes.

    ```
    BASE-E $18.50 + USAGE-E $102.60 = $121.10
    Bexar $2.42 · PUC $0.85 · Franchise $1.82 · TOTAL $126.19
    ```

    **PRINTED = REACHABLE = $126.19.** Asserted to the cent.

    The franchise fee is $1.82 here and $1.82 on S1 — identical, because its base
    is the electric lines and those are the same 840 kWh on the same schedule.
    That equality is the cheapest possible check that the base narrowing is real:
    a whole-bill reading would give $1.82 here and $2.83 on S1.
    """
    resolved = R.resolve(
        catalogue=catalogue(RES_ELEC),
        account=R.AccountFacts(account_no="A-4004", unit_id="U-4", customer_class="residential"),
        premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
        meters=(R.MeterFacts(service="electric", connection_size="1φ 100A"),),
        quantities={"electric": Decimal("840")},
        service_date=SERVICE_DATE,
    )

    assert [rule.code for rule in resolved.taxes] == [
        "Bexar County",
        "PUC Regulatory Fee",
        "City Franchise",
    ]

    bill = rating_seam.price_bill(
        services=(
            (
                tiered("electric", "kWh", TIERS_E_RES, resolved.service("electric")),
                rating_seam.Quantity(amount=Decimal("840"), unit="kWh"),
            ),
        ),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=tax_rules(resolved),
    )

    line = amounts(bill)
    assert bill.taxable_subtotal == Decimal("121.10")
    assert line["Tax Bexar County"] == Decimal("2.42")
    assert line["Tax PUC Regulatory Fee"] == Decimal("0.85")
    assert line["Tax City Franchise"] == Decimal("1.82")
    assert bill.total == Decimal("126.19")


# ── The provenance the whole CR turns on ───────────────────────────────────


def test_cr013_a4_every_priced_line_names_the_version_that_priced_it():
    """DEF-276, at the seam rather than at the table.

    §A0's compliance promise is that *"every issued bill must re-price to the
    identical figure, forever, from the versions in force for its service
    period"*. On a multi-service bill that means each line naming ITS OWN
    schedule version — electric's and water's are different rows — which a
    single version id on the invoice could never have expressed.
    """
    resolved = R.resolve(
        catalogue=catalogue(RES_STD),
        account=R.AccountFacts(account_no="A-1001", unit_id="U-1", customer_class="residential"),
        premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
        meters=(
            R.MeterFacts(service="electric", connection_size="1φ 100A"),
            R.MeterFacts(service="water", connection_size='5/8"'),
            R.MeterFacts(service="sewer", connection_size="—"),
        ),
        quantities={"electric": Decimal("840"), "water": Decimal("11")},
        service_date=SERVICE_DATE,
    )
    bill = rating_seam.price_bill(
        services=(
            (
                tiered("electric", "kWh", TIERS_E_RES, resolved.service("electric")),
                rating_seam.Quantity(amount=Decimal("840"), unit="kWh"),
            ),
            (
                tiered("water", "kgal", TIERS_W_RES, resolved.service("water")),
                rating_seam.Quantity(amount=Decimal("11"), unit="kgal"),
            ),
        ),
        base_only_services=(sewer_config(resolved),),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=tax_rules(resolved),
    )

    by_service = {
        line.service: line.tariff_version_id
        for line in bill.lines
        if line.kind in ("usage", "base")
    }
    assert by_service == {
        "electric": "TV-E-RES-2026",
        "water": "TV-W-RES-2026",
        "sewer": "TV-S-2026",
    }
    # A tax line was not priced from a rate schedule and names none.
    assert all(line.tariff_version_id is None for line in bill.lines_of("tax"))
