# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (the stage contracts the
#           bill run's stages 3·4·5 pass between each other)
#           Screens: — (pure data contracts; priced lines render in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see errors.py.
# Rules:    BR-RAT-003 (round per line, half-up, 2dp, at finalization ONLY —
#           which is exactly why LineCandidate and PricedLine are two types) ·
#           BR-RAT-044 (pricing models are plugins behind ONE price(...)
#           interface) · BR-RAT-045 (charge amount rules behind ONE amount(...)
#           interface) · BR-RAT-005 (tax base = usage + base) · BR-RAT-004
#           (calendar-day proration factor travels on the period contract) ·
#           BR-BIL-037 (one input contract and one output contract per stage) ·
#           BR-BIL-039 (stages 1–5 are pure)
# Golden:   GT-1 · GT-2 · GT-3 · GT-5 · GT-10 · GT-11 — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_012_engine.py ·
#           06-backend/tests/test_us_rat_013_totals.py ·
#           06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/** ·
#           apps/billing/rating_seam.py (adapts PricedBill to its RatedBill)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

The rating engine's value types — every stage boundary, stated as data.

Serves US-RAT-012 (usage pricing), US-RAT-013 (totals) and US-RAT-015 (rule-type
plugins). Nothing here computes: these are frozen dataclasses that name what one
stage hands the next, so a stage can be executed from a fixture with no database
and no other stage present (BR-BIL-039 / US-BIL-029 TC-2).

THE ONE DISTINCTION THAT MATTERS
--------------------------------
`LineCandidate` carries an UNROUNDED amount at full Decimal precision;
`PricedLine` carries a FINALIZED amount, half-up to 2dp. They are two types on
purpose. BR-RAT-003 (B4.4, finance-signed) says rounding happens per line, once,
at finalization — so a plugin that returns a `LineCandidate` structurally cannot
be the thing that rounded it (US-RAT-015 TC-6), and the finalize stage is the
only place in the engine where a 2dp value comes into existence.

NUMERIC(18,6) is a STORAGE precision (B2/DB-3), not a rounding law: intermediates
stay at full Decimal precision in memory and are quantized only when they are
written or finalized. apps/rating/services.py records the same distinction.

THE SECOND DISTINCTION, ADDED 2026-08-11: A LINE'S AMOUNT IS NOT ITS IDENTITY
----------------------------------------------------------------------------
`LineCandidate` / `PricedLine` carry `service` and `tax_id` alongside the money.
Neither is arithmetic and neither is read by any stage in this package: they are
carried so that the line arriving at `invoice_lines` can say WHAT PRODUCED IT,
which is what BR-BIL-010's GL stamp is keyed on (BR-BIL-069, PO ruling
2026-08-11 closing OQ-116). Until they existed, a $6.29 State-of-Texas tax line
and a $1.01 Harris-County one were indistinguishable by the time they reached
billing, and the stamp correctly refused every bill that carried tax.

WHY EACH INPUT IS SHAPED THIS WAY (the seam's docstring states this for the
public boundary; this is the internal half)
-----------------------------------------------------------------------------
* `MeasuredUsage` carries the raw quantity AND the multiplier AND the
  post-multiplier quantity, because B4.4's whole content is the ORDER of those
  two (multiplier BEFORE tiers, GT-5). A contract that carried only the product
  could not be tested for the order.
* `PeriodShape` carries the calendar-day counts AND the factor derived from
  them, because BR-RAT-004 proration and BR-RAT-002 tier-threshold scaling are
  the same ratio and must never be able to disagree.
* `SubscriptionContext` carries the account-level exemption flag, because B4.2
  makes exemption an ACCOUNT fact — there is no per-service exemption field
  anywhere in these contracts to get that wrong with (GT-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# Line kinds. The tax base is decided by KIND plus the taxable flag, never by
# the flag alone — B4.2 is structural (US-RAT-013 TC-7: a fee that arrives
# wrongly flagged taxable still never enters a percent base).
KIND_USAGE = "usage"
KIND_BASE = "base"
KIND_TAX = "tax"
KIND_FEE = "fee"
KIND_MINIMUM_ADJUSTMENT = "minimum_adjustment"
#: BR-BIL-012's first-bill security deposit. Its OWN kind rather than a fee,
#: added 2026-08-16 by the US-LED-001 lane, and the reason is a GL account
#: rather than a tax: US-LED-001's contract table sends a deposit line to the
#: **deposit-liability** designation (*"never revenue"*), while BR-BIL-010
#: sends a FEE to its charge code's GL. Sharing one kind made the two
#: indistinguishable at `apps/billing/issue._gl_account_for`, which refused
#: every first bill carrying a deposit with a message about a missing charge
#: code (DEF-181). B4.2 is unaffected and is still structural — the kind is
#: absent from TAX_BASE_KINDS below, so a deposit can never reach a percent
#: base even if somebody flags it taxable.
KIND_DEPOSIT = "deposit"
#: DEF-502 (2026-08-22) — R6's reduction, as its OWN line. BR-RAT-068: *"the
#: bill shows the full tariff amount and the reduction as its own line, so
#: subsidy granted is reportable"* — so a discount is never a smaller number on
#: the tariff line, it is a NEGATIVE line beside it, carrying the discount's
#: customer-facing name. Deliberately absent from TAX_BASE_KINDS below: which
#: subtotal a tax levies on is statutory and PER TAX (BR-RAT-106,
#: `taxes.discount_treatment`), so the tax base question is answered at
#: compute-tax from the treatment, never by this line's kind or flag.
KIND_DISCOUNT = "discount"

#: The kinds B4.2 admits to the percent-tax base: usage + base (+ the minimum
#: bill adjustment, which BR-RAT-028/OQ-007 makes "taxable like base").
#: Deliberately NOT `KIND_DEPOSIT`: a deposit is the customer's own money held
#: by the utility, and taxing it would tax them on their own deposit.
TAX_BASE_KINDS = frozenset({KIND_USAGE, KIND_BASE, KIND_MINIMUM_ADJUSTMENT})


@dataclass(frozen=True)
class WindowUsage:
    """One TOU window's PRE-SPLIT quantity, with its own unit (hard rule 3).

    BR-RAT-021 (CONFIRMED, PO Q&A R3): *"reads arrive pre-split per window"*.
    The engine never divides a total across windows and never infers one window
    from the others — metering measures a register per window (its `channel`
    vocabulary is `tou_on | tou_mid | tou_off`, B2 r8/BR-MET-059) and this is
    that measurement crossing the boundary.

    `channel` is METERING's vocabulary — `tou_on | tou_mid | tou_off` (B2 r8 /
    BR-MET-059) — never the tenant's window label. A label is display text a
    tenant may rename or translate; a channel is the register that was read.
    The same distinction `LineCandidate` draws between `description` and
    `tax_id`, for the same reason.

    THE UNIT TRAVELS PER WINDOW, not once for the service. Three windows of one
    electric meter are all kWh today, and writing that assumption into the
    contract is exactly how hard rule 3 gets broken by the first tenant who
    meters something else.
    """

    channel: str
    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class PeakDemand:
    """The period's MAXIMUM DEMAND — a different unit from the energy beside it.

    BR-RAT-014 (CONFIRMED for scope, PO Q&A R1 Q7): demand billing is v1 and the
    measurement is a max-demand register read. So this is a MEASUREMENT the
    engine is handed, never something it derives: nothing here reads an interval
    series, computes a rolling 15-minute maximum, or applies a ratchet.

    It is its own type rather than a second `Decimal` on `MeasuredUsage` because
    **kW is not kWh**. On one industrial bill the energy line is 48,200 kWh and
    the demand line is 182 kW; a contract that carried both as bare numbers
    would let them be added, compared or swapped, and the resulting bill would
    be arithmetically perfect and off by thousands of dollars.
    """

    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class SeasonMeasured:
    """ONE register's quantity per season, MEASURED by a read on the boundary day.

    HUMAN-REVIEW-PENDING — 🔒 rating math. Added 2026-10-01 to build
    `DEF-RAT-8849` (PO verbatim *"yes build the season-change day reading"*,
    decision log *"A METER READ TAKEN ON THE SEASON-CHANGE DAY REPLACES THE DAY
    SPLIT"*): WE-18's *"an ACTUAL read dated Oct 1 would replace the split"*.

    ⚠ **THE CALLER MEASURES, THE ENGINE NEVER DOES — THE SAME CONSTRAINT AS
    `SeasonShare`.** Billing finds the read dated on the season-change day and
    subtracts registers; this carries only the answer. `quantities` is in the
    order of `ModelConfig.season_days` (chronological) and sums EXACTLY to the
    register's measured quantity — the caller makes the first season the
    remainder. `channel` is metering's register (`tou_on`, …) for a time-of-use
    window, and `None` for the service's ONE billed quantity (the `seasonal`
    model). WE-18 with a read on 1 Oct showing 80 then 40:
    `SeasonMeasured(channel="tou_on", quantities=(80, 40))`.
    """

    channel: str | None
    quantities: tuple[Decimal, ...]


@dataclass(frozen=True)
class MeasuredUsage:
    """What the engine prices: a quantity WITH its unit (CLAUDE.md hard rule 3).

    `billed_quantity` is post-multiplier (BR-RAT-001 / B4.4). `raw_quantity` and
    `multiplier` are kept so the order can be asserted rather than assumed.

    `windows` and `demand` are the OTHER things one service point can measure in
    one period, added 2026-08-16 with the TOU and demand plugins. Both default
    to absent, and absent means UNKNOWN rather than zero: a TOU tariff handed no
    window quantities refuses (see `models/tou.py`), it does not price nothing.
    """

    billed_quantity: Decimal
    unit: str
    raw_quantity: Decimal
    multiplier: Decimal
    #: Pre-split TOU quantities (BR-RAT-021). Empty on a service that bills on
    #: one total — which is every non-TOU model.
    windows: tuple[WindowUsage, ...] = ()
    #: The period's peak demand (BR-RAT-014). None when nothing measured one.
    demand: PeakDemand | None = None
    #: **`DEF-RAT-8849` · A READ ON THE SEASON-CHANGE DAY REPLACES THE DAY
    #: SPLIT** (PO 2026-10-01). Per register, the quantity each season of a
    #: season-crossing period MEASURED, as the caller cut it at that read.
    #: Empty on every bill without such a read — which then splits by calendar
    #: days exactly as before (BR-RAT-034).
    season_measured: tuple[SeasonMeasured, ...] = ()


@dataclass(frozen=True)
class PeriodShape:
    """The service window as B4.3 sees it: CALENDAR days, and their ratio.

    `factor` is `service_days / cycle_days` — the single number that prorates
    the base charge (BR-RAT-004) and scales tier thresholds (BR-RAT-002).
    """

    cycle_days: int
    service_days: int
    factor: Decimal

    @property
    def is_partial(self) -> bool:
        return self.factor != Decimal(1)


@dataclass(frozen=True)
class TierSpec:
    """One inclining block. `upper` None = the open-ended top block (BR-RAT-032:
    only the last tier may be open-ended). Bounds are in the billed unit."""

    upper: Decimal | None
    unit_price: Decimal


@dataclass(frozen=True)
class TouWindowSpec:
    """One configured TOU window's PRICE (BR-RAT-021/033).

    Times are deliberately absent. The window BOUNDARIES decide which register a
    kWh landed in, and that decision is metering's — by the time a quantity
    reaches this engine it has already been split (BR-RAT-021). Carrying the
    hours here would invite a second, disagreeing implementation of the split.

    `season` is the label of the `rate_seasons` row this price belongs to, or
    None on a schedule that defines no seasons at all. `day_type` is
    weekday | weekend | holiday (B2 r5 #17); holidays resolve to the season's
    off-peak window through the tenant calendar, which is again a metering-side
    decision about WHICH register a kWh entered.
    """

    label: str
    unit_price: Decimal
    #: The metering CHANNEL this window's quantity is measured on — `tou_on |
    #: tou_mid | tou_off` (B2 r8 / BR-MET-059). **STATED BY THE UTILITY on the
    #: S11 Time-of-use card and stored on the window row** (BR-RAT-067; PO
    #: ruling 2026-08-16 closing OQ-236, verbatim: *"make the rate wizard say
    #: which register is which"*). Rating READS it; nothing derives it. Until
    #: that ruling it was resolved BY PRICE RANK, and the difference is a bill:
    #: 88.60 paired as stated against 122.40 paired backwards.
    #: None means the utility never stated one — a schedule configured before
    #: the column existed — and the plugin then refuses by name rather than
    #: ranking or pricing the window at 0.00.
    channel: str | None = None
    season: str | None = None
    day_type: str = "weekday"


@dataclass(frozen=True)
class SeasonShare:
    """How many CALENDAR days of this bill period fell in one season (BR-RAT-034).

    HUMAN-REVIEW-PENDING — 🔒 rating math. Added 2026-10-01 to BUILD the ruling of
    2026-09-07 (decision log *"TWO RULINGS IN ONE BREATH: THE SEASON-CROSSING BILL
    PERIOD IS SPLIT, WHICH CLOSES OQ-234"*; PO verbatim *"please split swithch it
    on"*): a period that crosses a season boundary splits pro-rata by calendar days.

    ⚠ **THE CALLER COUNTS, THE ENGINE NEVER DOES.** The engine is pure and holds
    no calendar — the design note in `OQ-234`'s own register row. Rating's
    selector counts the days against the stored `rate_seasons` month/day ranges,
    in the same place it already resolved ONE season on the service date
    (`selectors._season_label_on`, the sibling of BR-RAT-007's version lookup),
    and hands the counts across here. A plugin only multiplies by `days / Σ days`.

    `season` is the season's LABEL, the same string `TouWindowSpec.season` and
    `SeasonLadder.season` carry; `None` is a day no season covers — BR-RAT-033's
    coverage gap — which the plugin REFUSES by name rather than pricing free.
    The shares arrive in CHRONOLOGICAL order (first day of the period first), so
    the bill prints summer before winter on a 15 Sep – 14 Oct period.

    WE-18 / GT-34: 15 Sep – 14 Oct with the season flipping 1 Oct is
    `(SeasonShare("Summer", 16), SeasonShare("Winter", 14))`.
    """

    season: str | None
    days: int


@dataclass(frozen=True)
class SeasonLadder:
    """One season's price set on a `seasonal` schedule (BR-RAT-034).

    `rate_seasons` + season-scoped `rate_tiers` (B2 r5 #2, r6.7): each season
    carries its own ladder — one 0→∞ block for a flat seasonal price, several for
    an inclining one. Added 2026-10-01 with the `seasonal` plugin; read by that
    plugin and by nothing else.
    """

    season: str
    tiers: tuple["TierSpec", ...]


@dataclass(frozen=True)
class CapacitySpec:
    """A capacity charge's tenant-defined unit and rate (BR-RAT-018/019/022).

    `unit_label` is free tenant text — "panel", "kW block", "meter equivalent".
    It is the BILLED UNIT of a capacity service, which is why the UoM gate
    (BR-RAT-038) works on a capacity tariff exactly as it does on a metered one:
    a quantity of 4 arriving in "panel" against a tariff written in "kW block"
    is refused rather than multiplied by the wrong rate.
    """

    unit_label: str
    rate_per_unit: Decimal


@dataclass(frozen=True)
class ModelConfig:
    """The in-force tariff version as a PLUGIN receives it (BR-RAT-044).

    This is a faithful projection of the fields `apps.billing.rating_seam`
    publishes — nothing here invents configuration the seam cannot carry. A new
    rate shape needs its own configuration to arrive on the seam's
    `TariffConfig` first; see the "adding a rate shape" note in
    apps/rating/pricing/models/__init__.py.

    `base_charge=None` means the tariff states NO base charge — absence, not a
    base of zero (B5 GT-5 names none, and inventing 0.00 invents an input).

    ── The 2026-08-16 additions, and what each is for ──────────────────────────
    Until this date the only fields here were a flat price, a tier table and a
    base charge, so `flat` and `tiered` were the only models that could be
    priced at all — a utility on time-of-use rates could not produce an electric
    bill. Each field below is the configuration ONE plugin needs, and none of
    them is read by any other:

      windows        `time_of_use`        (BR-RAT-021)
      season         `time_of_use`        — the season IN FORCE on the service
                                            date, resolved by the caller exactly
                                            as the tariff VERSION is (BR-RAT-007)
      capacity       `capacity`           (BR-RAT-018/022)
      energy_rate /
      demand_rate    `demand`             (BR-RAT-014)
      ratchet_enabled /
      pf_penalty_enabled
                     `demand`             — captured so the plugin can REFUSE a
                                            tariff whose measurement rules are
                                            still PROPOSED, rather than bill a
                                            number the tenant did not configure
      percent /
      basis_service /
      percent_basis /
      basis_quantity /
      basis_unit /
      basis_amount   `percent_of_service` (BR-RAT-015 as SUPERSEDED by CR-081,
                                           WIDENED by CR-130-BRC07/BR-RAT-1030)

    ⚠ **`basis_quantity` AND `basis_unit` READ `basis_amount` — ONE FIELD, IN
    DOLLARS — UNTIL 2026-09-08, AND THE RENAME WAS DELIBERATE (`CR-081`).** The
    field's docstring said, verbatim: *"it is the OTHER service's usage-charge
    dollars, which exist only once that service has been priced"*. The PO's
    re-sign of that date makes sewer a percentage of the water **VOLUME**,
    priced on sewer's own schedule, so the number crossing this boundary is a
    QUANTITY in a UNIT and no longer money. **The field was renamed rather than
    re-documented** because a reader who did not notice would have multiplied
    kgal by a price-per-kgal and produced a well-formed bill for the wrong
    number; a rename makes every unconverted caller fail loudly at the call
    instead. Hard rule 3 is why the UNIT travels beside it: a quantity without
    an explicit unit is never assumed.

    ⚠ **`basis_amount` IS BACK AS OF 2026-09-22 (`CR-130-BRC07`), AND IT IS A
    THIRD FIELD RATHER THAN A REVERSAL.** The PO asked for both arithmetics as
    a CHOICE — *"we also need to create 2 option 5age of charges or % of
    usage"* — so the two bases now travel side by side and `percent_basis` says
    which one this schedule bought. The paragraph above stays word for word:
    the rename did its job, every caller was converted, and nothing here goes
    back to reading money where a volume belongs.

    **Exactly one of the two is supplied per tariff, never both**, and the
    plugin refuses the one it needs when it is missing rather than falling back
    to the other. A fallback is how 90% of a volume would quietly become 90% of
    money at the same 90%, producing a well-formed bill for a number nobody
    configured.

    None of `basis_quantity` / `basis_unit` / `basis_amount` is tariff
    configuration: all three exist only once the BASIS service has been priced.
    They are filled by `engine.price_bill`'s second pass and are None
    everywhere else — a percent-of-service tariff with no basis REFUSES BY NAME
    (see `models/percent_of_service.py`), because a sewer line priced at zero is
    a bill that silently forgives a charge.

    `percent_basis`, by contrast, IS tariff configuration: it is a stored column
    on `tariff_versions`, written by name on every row that already existed
    (`rating/0043_cr130_percent_basis.py`).
    """

    model: str
    billed_unit: str
    unit_price: Decimal | None = None
    tiers: tuple[TierSpec, ...] = ()
    base_charge: Decimal | None = None
    windows: tuple[TouWindowSpec, ...] = ()
    season: str | None = None
    #: **BR-RAT-034 · THE SEASON-CROSSING SPLIT** (built 2026-10-01, ruled
    #: 2026-09-07, `OQ-234` CLOSED). The calendar days of this period in each
    #: season, chronological, counted by the CALLER. Empty — or one share — is a
    #: period inside one season, and every plugin then prices EXACTLY as before
    #: this field existed, on `season` above. Two or more shares split each
    #: measured quantity pro-rata by days (`time_of_use`, `seasonal`).
    season_days: tuple[SeasonShare, ...] = ()
    #: `seasonal` — each season's own ladder (BR-RAT-034, B2 r5 #2).
    season_tiers: tuple[SeasonLadder, ...] = ()
    capacity: CapacitySpec | None = None
    energy_rate: Decimal | None = None
    demand_rate: Decimal | None = None
    ratchet_enabled: bool = False
    pf_penalty_enabled: bool = False
    #: PERCENT POINTS as the tenant typed them on S11 (40 means 40%), because
    #: `tariff_versions.percent` stores points — `services._validate_structure`
    #: refuses <= 0 and asks for confirmation above 100 (US-RAT-007 TC-6). The
    #: division by 100 happens in the plugin, once, and is stated there.
    percent: Decimal | None = None
    basis_service: str | None = None
    #: **A PERCENTAGE OF WHAT** — `CR-130-BRC07` / `BR-RAT-1030`, PO 2026-09-22.
    #: `apps.rating.pricing.percent_basis.PERCENT_BASES`: `'usage'` reads
    #: `basis_quantity`/`basis_unit` and prices the result on THIS schedule's
    #: own rate; `'charge'` reads `basis_amount` and states no rate at all.
    #:
    #: ⚠ **`None` IS NOT `'usage'` AND THE PLUGIN REFUSES IT BY NAME.** Every
    #: stored row says one of the two out loud, so a `None` here means a CALLER
    #: — a seam, a fixture, a script — did not carry the column across. Reading
    #: it as `'usage'` would be a default on a money path that cannot be told
    #: apart from a choice, which is exactly what `rating/0043`'s three-step
    #: backfill exists to prevent in the database.
    percent_basis: str | None = None
    #: `CR-081` — the BASIS service's billed QUANTITY and its UNIT, read on the
    #: `'usage'` basis. `unit_price`/`tiers` above carry sewer's OWN rate per
    #: that unit, which is why this model reads fields it did not used to.
    basis_quantity: Decimal | None = None
    basis_unit: str | None = None
    #: `CR-130-BRC07` — the BASIS service's usage-charge DOLLARS, read on the
    #: `'charge'` basis and on that basis alone. **Σ of that service's FINALIZED
    #: usage lines**, which is the PRINTED figures: `OQ-232` is OPEN in the
    #: register with that disposition already recorded and reasoned (*"a
    #: customer who adds up the four printed lines and applies the rate"* must
    #: reach the printed sewer line — B4.2's re-sign of 2026-08-11, borrowed
    #: rather than re-decided). The base charge, tax and fees are not in it —
    #: not by a filter this field applies, but because `engine._usage_dollars`
    #: sums by line KIND.
    #:
    #: The PO's worked figure — water $100.00, 80% → sewer **$80.00** — is exact
    #: at both readings, so it does not distinguish them; `OQ-232` is why the
    #: reading is stated here rather than left to be inferred.
    basis_amount: Decimal | None = None
    #: R5's PREMISES jurisdiction factor on the MONEY — base charges AND rates
    #: (PO ruling 2026-08-19). NOT the meter multiplier, which scales the
    #: QUANTITY before the tiers are walked and never reaches this engine.
    #: 1 = no factor, which is every B5 fixture.
    jurisdiction_factor: Decimal = Decimal("1")
    #: WHICH VERSION THIS CONFIGURATION IS — `rating.tariff_versions.id`, the
    #: row BR-RAT-007 resolved against the service date. The engine performs no
    #: arithmetic with it and never reads it back; it exists so every line
    #: priced from this config can say what priced it (DEF-276), which is what
    #: BR-RAT-007/017's seven-year reproducibility promise is checked against.
    tariff_version_id: str | None = None
    #: BR-RAT-028 mode A — this service's own minimum (`plan_services
    #: .minimum_amount`). `None` is NO minimum, never a floor of zero. Read by
    #: `stages/apply_charges.py` and by nothing else; no plugin sees it,
    #: because a minimum is not a way of pricing usage — it is a floor applied
    #: to what the pricing produced.
    minimum_amount: Decimal | None = None
    #: BR-RAT-028 mode B — the PLAN's floor over the whole bill
    #: (`plans.minimum_bill_amount`). Carried on every one of the plan's
    #: tariffs (see the seam's own note) and read ONCE, at bill level, by
    #: `engine.price_bill` through `apply_charges.plan_floor_line`.
    plan_minimum_bill_amount: Decimal | None = None
    #: **WHAT THIS LINE'S CONNECTION SIZE IS CALLED** — `CR-063`, decision log
    #: 2026-09-02. A capacity service billed by a COUNT carries ONE LINE PER
    #: SIZE, so one bill can hold two lines for one service: a 6" fire line at
    #: `$60.00` beside two 2" fire lines at `$24.00`. Without a name both
    #: read *"fire usage"* and the customer cannot tell them apart, which is
    #: precisely what that ruling asks the document to show. (The second half of
    #: that example was two private hydrants at `$50.00` until the PO withdrew
    #: the hydrant from fire's size list on 2026-09-03; the per-size split it
    #: illustrates is untouched.)
    #:
    #: ⚠ **IT NAMES A LINE AND PRICES NOTHING.** No plugin does arithmetic with
    #: it; it reaches `LineCandidate.description` and nowhere else. `None` on
    #: every config every other caller builds — every ❄️ B5 fixture included —
    #: so every existing line's wording is byte-identical.
    size_label: str | None = None
    #: **THIS IS ONE OF A SERVICE'S PER-SIZE COUNTED LINES** — `CR-063`. Read by
    #: the tiered plugin and by nothing else, for ONE reason: such a ladder is a
    #: single unbounded tier per size, and a quantity of ZERO on it must still
    #: put a `$0.00` LINE on the document.
    #:
    #: ⚠ **`BR-MET-108`'s RULED ZERO IS A VISIBLE ANSWER, NOT AN ABSENCE.** The
    #: utility looked and this connection has no fire equipment: *"the zero line
    #: buys VISIBILITY, putting the gap on the document instead of in a
    #: silence"* (`OQ-670`, PO 2026-08-27, *"(b) Bill $0.00"*). Trash gets that
    #: for free — its schedule is FLAT, and the flat plugin always emits its one
    #: line — and a tiered ladder walks blocks, so at zero it walks none and
    #: emits nothing at all.
    #:
    #: `False` everywhere else, so a METERED tiered service that consumed
    #: nothing keeps emitting no usage line, exactly as it does today, and no
    #: ❄️ B5 figure and no golden line count moves.
    per_size_line: bool = False
    #: `DEF-BIL-8743` — this config prices the SUMMED installed capacity of a
    #: capacity service (CR-062 D1: solar 2 + 4 + 8 kW × $14.00), set only by
    #: `billing.stages.measure_consumption`'s summed branch. Like a counted
    #: service's per-asset charge it is a monthly charge per thing installed, so
    #: on a part period its MONEY prorates by calendar days (B4.3, WE-16/GT-31,
    #: GT-15 as amended 2026-08-11 *"BOTH lines prorate"*); the kW never scales.
    #: `False` everywhere else; a whole month is a factor of 1.
    installed_sum_line: bool = False
    #: **WHICH METER THIS CONFIGURATION PRICES** — PO ruling 2026-09-30: two
    #: meters on one METERED service are two connections, each on its own tier
    #: ladder with its own base, on its own lines. `assets.Asset.id` as text.
    #: IDENTITY, like `tariff_version_id`: no plugin does arithmetic with it;
    #: `stages/price_usage.py` stamps it on the lines this config produces so
    #: billing can write `invoice_lines.asset_id`. `None` on every config that
    #: is not one of a split service's meters — every ❄️ B5 fixture included.
    asset_id: str | None = None
    #: 🔒 **`DEF-RAT-9327` — THE CHARGE CODE THE BASE CAME FROM** (`BASE-W`),
    #: carried from `TariffConfig.base_charge_code` (billing has always sent
    #: it; this engine dropped it). IDENTITY, never arithmetic: the base is
    #: priced from `base_charge` alone. `stages/price_usage.py` stamps it on the
    #: base line so a discount scoped to NAMED charge codes (BR-RAT-068) can
    #: select that line. `None` where no code answered — every ❄️ B5 fixture.
    base_charge_code: str | None = None
    #: 🔒 `DEF-CUS-9050` (PO 2026-10-02) — an owner's bill carrying an EMPTY
    #: unit's base: the unit's NAME for the line (identity only), and the share
    #: of the period it stood empty (`vacant_days / period_days`), which the base
    #: charge is multiplied by UNROUNDED before the one rounding at finalize
    #: (B4.3's proration, applied per unit). Both `None` on every other config —
    #: every ❄️ B5 fixture included — so nothing else moves.
    unit_label: str | None = None
    occupancy_factor: Decimal | None = None

    @property
    def charges_per_installed_unit(self) -> bool:
        """🔒 `DEF-RAT-10210` — does this config price what is INSTALLED (a
        capacity line: solar / battery / storm-water kW) rather than what a
        meter measured or a count of carts? True for the `capacity` model's own
        shape (a capacity spec) and for a summed installed total priced on a
        flat or tiered schedule (`installed_sum_line`). A COUNTED service
        (`per_size_line`) is not: its per-item charge is joined with its base
        into one bill line. Read by `stages/price_usage.py`, which may name no
        model (BR-RAT-044), to leave a $0-RATE capacity line off the bill (PO
        2026-10-17). Identity only — it prices nothing."""
        return self.capacity is not None or self.installed_sum_line


@dataclass(frozen=True)
class SubscriptionContext:
    """The account/service facts the pricing and totals passes need.

    Named for BR-BIL-037's stage-1 output because that is what fills it in the
    real run; the golden fixtures fill it from `AccountContext` + the tariff's
    service. `tax_exempt` is account-level and applies regardless of service
    (B4.2 / BR-RAT-006).
    """

    service: str
    currency: str
    tax_exempt: bool = False


@dataclass(frozen=True)
class TaxRuleSpec:
    """A percent tax applied to the B4.2 base. `rate` is a fraction (0.0825).

    `tax_id` is WHICH `rating.taxes` row states this rate — the AUTHORITY's
    identity, carried so the line the rule produces can name it (BR-BIL-069, PO
    ruling 2026-08-11 closing OQ-116: *"For each atheority have separate account
    and tagging"*). It is an opaque id to every stage below: nothing here reads
    the tax row, and the ARITHMETIC is `rate` and `rate` alone.

    Optional because a rule may state a rate with no `taxes` row behind it (a
    plan-level `rate_override` on a jurisdiction that has none). Such a line
    carries no authority and is refused at issue by BR-BIL-010 rather than
    posted to a bucket chosen by accident.

    `flat_amount` is the FLAT-PER-BILL form (BR-RAT-036), added 2026-08-18 for
    the PO's ruled **PUC Regulatory Fee — $0.85 flat per bill, electric only**.
    A rule states EITHER a `rate` or a `flat_amount`, never both: the two are
    different arithmetic, and a flat charge is not a percentage of anything, so
    `$0.85` is `$0.85` on a $40 bill and on a $4,000 one. Which one a rule
    carries is decided by the tax row in `rating.taxes`; the engine reads
    whichever is present and refuses a rule carrying neither
    (`TaxRuleUnpriceable`) rather than pricing it as 0.00.

    ⚠ **THE PARAGRAPH THAT STOOD HERE IS ANSWERED AND IS REPLACED RATHER THAN
    DELETED (hard-won law 1, CR-052 W5 task 16).** It read: *"Per-unit
    (BR-RAT-036's third form) is still NOT represented: it needs the usage and a
    threshold, and no signed rule states how a per-unit tax reads a tiered
    schedule. Named rather than approximated."*

    **A SIGNED RULE DOES STATE IT, AND IT HAS SINCE 2026-08-09.** `OQ-054` asked
    this exact question — *"S13 per-unit tax 'Applies above' threshold (e.g.
    Water Conservation Surcharge $0.25/kgal above Tier 3): usage quantity or tier
    reference"* — and the PO closed it as **`BR-RAT-042` (CONFIRMED), option (a):
    MARGINAL, only units above the threshold are taxed.** So the threshold is a
    QUANTITY the tax states (`taxes.applies_above_units`), never a pointer into
    somebody's tier table, and the arithmetic is:

        amount = per_unit_amount x max(0, billed_quantity - applies_above_units)

    **Worked, EP-RAT-05 TC-6's own figure:** `0.25 x 3.72 kgal = 0.93`. On a
    bill of `18.72 kgal` with the surcharge stated above `15`, the taxed
    quantity is `3.72` and the line is **`$0.93`** — not `$4.68`, which is what
    reading the threshold as *"applies to the whole bill once you pass 15"*
    would charge.

    `per_unit_uom` is MANDATORY on a per-unit rule and is CLAUDE.md hard rule 3
    in the contract: a quantity without its unit is not a quantity. `compute_tax`
    refuses a rule whose unit is not the unit the usage was measured in rather
    than converting — BR-RAT-038's *"no silent conversion"*, one module over.
    """

    code: str
    #: DEF-RAT-9307 (PO 2026-10-03) — the clerk's Bill label, what the
    #: customer reads on the line. WORDING ONLY: no stage prices off it. None
    #: or blank = the line reads "Tax " + `code`, as every bill always has.
    bill_label: str | None = None
    rate: Decimal | None = None
    tax_id: str | None = None
    flat_amount: Decimal | None = None
    #: BR-RAT-036's PER-UNIT form (CR-052 W5 task 16). The rate charged per
    #: billed unit of usage — r10's Water Conservation Surcharge, *"$0.25 /
    #: kgal"*. A rule states exactly one of `rate`, `flat_amount` and
    #: `per_unit_amount`; the engine refuses one that states none rather than
    #: pricing it at 0.00.
    per_unit_amount: Decimal | None = None
    #: The unit that amount is quoted PER — `kgal`, `kWh`. Hard rule 3: a
    #: consumption figure always carries its unit and nothing here assumes one.
    #: A per-unit rule stating no unit REFUSES; it is never matched by position.
    per_unit_uom: str | None = None
    #: BR-RAT-042 (CONFIRMED, PO closing OQ-054 option (a)) — *"per-unit tax
    #: 'applies above N units' is MARGINAL: only units above the threshold are
    #: taxed"*. `None` = no threshold, so every billed unit is taxed. Read ONLY
    #: by the per-unit form; a percent or flat rule ignores it, because neither
    #: is a function of a quantity.
    applies_above_units: Decimal | None = None
    #: BR-RAT-036's FOURTH form, PER-METER (DEF-386 / `DEF-RAT-9278`,
    #: CR-165-BRC10 round 2). The amount charged once per meter in the tax's
    #: scope — the engine counts the meters off the usage lines it already has
    #: (`compute_tax._meters_in_scope`). `None` on every rule this product
    #: priced before 2026-10-03, so every existing bill and every ❄️ B5 fixture
    #: is byte-identical.
    per_meter_amount: Decimal | None = None
    #: The services whose taxable lines are this tax's BASE (R7). Empty = the
    #: whole bill, which is every frozen B5 figure. See the seam's own note on
    #: `TaxRule.applies_to_services` for the $1.82-versus-$2.83 worked case.
    applies_to_services: tuple[str, ...] = ()
    #: BR-RAT-106 (DEF-502, 2026-08-22) — WHICH subtotal this authority levies
    #: on when the bill carries a discount: `before` = the discount lands
    #: before the tax (the authority sees the REDUCED subtotal), `after` = the
    #: authority levies on the full tariff amount. Statutory and stated PER TAX
    #: on `taxes.discount_treatment`; None answers `before`, the single
    #: behaviour every issued bill has had, so a row nobody restated moves
    #: nothing. Read only by `stages/compute_tax.py`, through the one signed
    #: reader `rating.selectors.taxable_subtotal_for`. Inert on an
    #: undiscounted bill — both subtotals are then the same number.
    discount_treatment: str | None = None


@dataclass(frozen=True)
class LineCandidate:
    """A priced line BEFORE finalization: amount is UNROUNDED (BR-RAT-003).

    `service` and `tax_id` are the line's IDENTITY, not its arithmetic: which
    service produced a usage/base line, and which tax produced a tax line. They
    exist because BR-BIL-010 stamps a GL account per line at issue and both maps
    are keyed on them — the service→revenue map on the service code, the tax
    liability account on `rating.taxes.liability_gl_account_id`. Before
    2026-08-11 neither travelled, so the identity was lost HERE, at the stage
    boundary, and no bill could be stamped at all (BR-BIL-069 / OQ-116).

    Both are `None` on the lines they do not describe: a tax line names no
    service, a usage line names no tax. Nothing downstream infers one from the
    other, and nothing infers either from `description` — water and sewer both
    meter in kgal, and a tax renamed or translated would silently re-point money
    at a different authority (option D, declined by the PO's ruling).
    """

    kind: str
    description: str
    amount: Decimal
    taxable: bool
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    service: str | None = None
    tax_id: str | None = None
    #: The tariff version that priced this line (DEF-276). Stamped by
    #: `stages/price_usage.py` on the lines a rate schedule produced — usage and
    #: base — and left None on fees and taxes, whose provenance is a charge code
    #: and a tax authority respectively. Never inferred from anything.
    tariff_version_id: str | None = None
    #: **THE CHARGE CODE THAT PRODUCED A FEE LINE** (DEF-714, 2026-08-25) —
    #: `rating.charges.id`, the third member of the identity set beside
    #: `service` and `tax_id`, and it exists for exactly the same reason they
    #: do: BR-BIL-010 stamps a GL account per line at issue and a FEE's account
    #: is keyed on its charge code (`rating.charges.gl_account_id`). The
    #: sentence two fields up — *"whose provenance is a charge code"* — named a
    #: fact that had nowhere to travel, so it was lost HERE, at the stage
    #: boundary, and every fee line reached issue anonymous and was refused.
    #: A tenant with any recurring or auto-apply code (BR-RAT-117) could issue
    #: no bill at all.
    #:
    #: Set on fee lines whose caller knows the code, None on every other kind
    #: and on a fee nobody can attribute (a late fee computed from B4's rule
    #: names no code — it is refused at issue, by name, rather than guessed).
    #: NEVER inferred from `description`: matching money to a mapping by a
    #: line's wording was option D of OQ-116 and the PO declined it.
    charge_id: str | None = None
    #: 2026-09-30 (two meters, two lines) — the meter a usage/base line was
    #: priced for, stamped from `ModelConfig.asset_id`. `None` everywhere else.
    asset_id: str | None = None
    #: 🔒 `DEF-RAT-9327` — the catalogue CODE (`BASE-W`) of the charge code a
    #: BASE line was priced from, stamped from `ModelConfig.base_charge_code`;
    #: what a `named_codes` discount selects on (BR-RAT-068). A label, never a
    #: figure, and NOT `charge_id` (the row id a FEE's GL account is keyed
    #: on). `None` on every other line.
    charge_code: str | None = None


@dataclass(frozen=True)
class PricedLine:
    """A finalized invoice-line candidate: amount is half-up 2dp, exactly once.

    Carries the same `service` / `tax_id` identity as `LineCandidate`, unchanged
    by finalization — rounding touches the amount and nothing else.
    """

    kind: str
    description: str
    amount: Decimal
    taxable: bool
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    service: str | None = None
    tax_id: str | None = None
    #: The tariff version that priced this line (DEF-276). Stamped by
    #: `stages/price_usage.py` on the lines a rate schedule produced — usage and
    #: base — and left None on fees and taxes, whose provenance is a charge code
    #: and a tax authority respectively. Never inferred from anything.
    tariff_version_id: str | None = None
    #: **THE CHARGE CODE THAT PRODUCED A FEE LINE** (DEF-714, 2026-08-25) —
    #: `rating.charges.id`, the third member of the identity set beside
    #: `service` and `tax_id`, and it exists for exactly the same reason they
    #: do: BR-BIL-010 stamps a GL account per line at issue and a FEE's account
    #: is keyed on its charge code (`rating.charges.gl_account_id`). The
    #: sentence two fields up — *"whose provenance is a charge code"* — named a
    #: fact that had nowhere to travel, so it was lost HERE, at the stage
    #: boundary, and every fee line reached issue anonymous and was refused.
    #: A tenant with any recurring or auto-apply code (BR-RAT-117) could issue
    #: no bill at all.
    #:
    #: Set on fee lines whose caller knows the code, None on every other kind
    #: and on a fee nobody can attribute (a late fee computed from B4's rule
    #: names no code — it is refused at issue, by name, rather than guessed).
    #: NEVER inferred from `description`: matching money to a mapping by a
    #: line's wording was option D of OQ-116 and the PO declined it.
    charge_id: str | None = None
    #: 2026-09-30 (two meters, two lines) — the meter a usage/base line was
    #: priced for, stamped from `ModelConfig.asset_id`. `None` everywhere else.
    asset_id: str | None = None
    #: 🔒 `DEF-RAT-9327` — the catalogue CODE (`BASE-W`) of the charge code a
    #: BASE line was priced from, stamped from `ModelConfig.base_charge_code`;
    #: what a `named_codes` discount selects on (BR-RAT-068). A label, never a
    #: figure, and NOT `charge_id` (the row id a FEE's GL account is keyed
    #: on). `None` on every other line.
    charge_code: str | None = None
    #: 🔒 `DEF-2430` / `DEF-BIL-5341` — the PROGRAMME CODE (`CAP`) a DISCOUNT
    #: line was granted under, stamped by `stages/apply_discounts.py` from the
    #: rule that produced it. It is the one fact an issued bill needs to say
    #: WHICH enrolment it spent, so a yearly cap, a lifetime cap and a budget
    #: count down (`discount_services.record_grants_for_invoice`). A label,
    #: never a figure; never inferred from `description` (option D of OQ-116,
    #: declined). `None` on every line that is not a discount.
    discount_code: str | None = None


@dataclass(frozen=True)
class ChargeContext:
    """What a charge amount rule is given (BR-RAT-045).

    Every field is optional because the three v1 rules need different subsets
    (flat needs `amount`; percent needs `percent` + `basis`; percent-with-minimum
    needs all three). A rule that is handed an incomplete context REFUSES — it
    never substitutes zero (US-RAT-015 TC-5's fail-closed posture).
    """

    amount: Decimal | None = None
    percent: Decimal | None = None
    basis: Decimal | None = None
    minimum: Decimal | None = None


# ── Stage contracts (BR-BIL-037: one input, one output, per stage) ───────────


@dataclass(frozen=True)
class NormalizedInput:
    """Stage 0 out — everything the priced stages need, gathered once.

    Taxes and fees ride here so that every downstream stage receives its
    PREDECESSOR'S OUTPUT AND NOTHING ELSE (BR-BIL-037). That is not decoration:
    it is what lets a stage be called from a fixture with no orchestrator.
    """

    subscription: SubscriptionContext
    usage: MeasuredUsage
    config: ModelConfig
    period: PeriodShape
    taxes: tuple[TaxRuleSpec, ...] = ()
    fees: tuple[LineCandidate, ...] = ()
    #: DEF-502 — the account's granted discounts, riding here for the same
    #: reason taxes do: every stage receives its predecessor's output and
    #: nothing else, so `apply_discounts` reads them off its input rather than
    #: being handed a side channel. SEAM-SHAPED objects (billing's
    #: `rating_seam.DiscountRule`), read structurally by `stages/
    #: apply_discounts.py`, which converts them onto `discount_pricing
    #: .DiscountRule` — the R6 arithmetic's own input contract. Empty on every
    #: per-service pass and on every B5 fixture (B5 freezes no discounted
    #: figure); `engine.price_bill` fills it ONCE, at the bill-level pass,
    #: because a discount is an ACCOUNT overlay (BR-RAT-068) and not a
    #: per-service fact.
    discounts: tuple[Any, ...] = ()


@dataclass(frozen=True)
class PricedLines:
    """Stage 3 out (price-usage): usage lines + the base line, unrounded."""

    source: NormalizedInput
    usage_lines: tuple[LineCandidate, ...]
    base_lines: tuple[LineCandidate, ...]

    @property
    def lines(self) -> tuple[LineCandidate, ...]:
        return self.usage_lines + self.base_lines

    @property
    def normalized(self) -> NormalizedInput:
        return self.source


@dataclass(frozen=True)
class ChargedLines:
    """Stage 4 out (apply-charges): the priced lines plus charge/fee lines."""

    source: PricedLines
    lines: tuple[LineCandidate, ...]

    @property
    def normalized(self) -> NormalizedInput:
        return self.source.normalized


@dataclass(frozen=True)
class FinalizedLines:
    """The rounding boundary: every line half-up 2dp, once (BR-RAT-003).

    `taxable_subtotal` is Sigma of the FINALIZED taxable line amounts — the sum
    US-RAT-013 section 5 defines as the tax base ("Sigma invoice_lines.amount
    where taxable"), restricted to the B4.2 kinds.
    """

    source: ChargedLines
    lines: tuple[PricedLine, ...]
    taxable_subtotal: Decimal
    #: DEF-502 — how much the discount stage took OFF THE TAXABLE BASE, as a
    #: POSITIVE magnitude, filled by `stages/apply_discounts.py` and zero
    #: everywhere else. Carried BESIDE `taxable_subtotal` rather than netted
    #: into it, because BR-RAT-106 makes the choice PER TAX: `taxable_subtotal`
    #: stays the full-tariff figure (`subtotal_before`) and compute-tax derives
    #: each authority's own base from the pair — `before` reads
    #: `taxable_subtotal - discount_reduction_taxable`, `after` reads
    #: `taxable_subtotal` — through `rating.selectors.taxable_subtotal_for`.
    #: The discount LINES themselves ride in `lines` with `KIND_DISCOUNT`,
    #: which is not a TAX_BASE_KIND, so their presence never moves this sum.
    discount_reduction_taxable: Decimal = Decimal("0")

    @property
    def normalized(self) -> NormalizedInput:
        return self.source.normalized


@dataclass(frozen=True)
class TaxedLines:
    """Stage 5 out (compute-tax): the tax lines, finalized, plus their total."""

    source: FinalizedLines
    tax_lines: tuple[PricedLine, ...]
    tax_total: Decimal

    @property
    def normalized(self) -> NormalizedInput:
        return self.source.normalized


@dataclass(frozen=True)
class PricedBill:
    """The engine's result. Totals are sums of finalized line amounts."""

    lines: tuple[PricedLine, ...]
    taxable_subtotal: Decimal
    tax_total: Decimal
    fee_total: Decimal
    total: Decimal
    currency: str

    def lines_of(self, kind: str) -> tuple[PricedLine, ...]:
        return tuple(line for line in self.lines if line.kind == kind)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-16 by the pricing-engines lane (WindowUsage · PeakDemand · TouWindowSpec · CapacitySpec, and the ModelConfig fields four new plugins read — the fields whose ABSENCE the old exceptions line below reported) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: LineCandidate/PricedLine carry `service` + `tax_id`, TaxRuleSpec carries `tax_id` — identity, never arithmetic) · AMENDED 2026-08-16 by the register lane (TouWindowSpec.channel is the UTILITY's stated register, read not derived — BR-RAT-067)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: ⚠ THE LINE THAT USED TO SIT HERE IS NOW FALSE AND IS QUOTED RATHER THAN DELETED (hard-won law 1). It read: *"ModelConfig carries ONLY what rating_seam.TariffConfig publishes today … TOU windows, demand rates, seasons, capacity units and the percent-of-service basis are NOT represented — the seam cannot carry them yet."* It was REPORTED rather than silently added, and on 2026-08-16 the seam was extended and the fields landed with the four plugins that read them. What is still absent: the flat/per-unit tax forms (BR-RAT-036 PROPOSED). ⚠ This also read "SEASONS as a first-class model input (the `seasonal` plugin is unregistered — OQ-234)" until 2026-10-01: OQ-234 was CLOSED 2026-09-07 and `SeasonShare`/`SeasonLadder` + `ModelConfig.season_days`/`season_tiers` now carry the caller-counted split (BR-RAT-034), HUMAN-REVIEW-PENDING.
# amended: 2026-10-01 by the season-change-reading lane (DEF-RAT-8849) — a reading on the season-change day replaces the day split (PO "yes build the season-change day reading"); HUMAN-REVIEW-PENDING, review-ledger row "DEF-RAT-8849"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
