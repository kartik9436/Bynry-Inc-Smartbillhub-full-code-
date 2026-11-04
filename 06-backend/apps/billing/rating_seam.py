# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the pure pricing function) ·
#           EP-MET-05 (estimation + true-up quantities) · EP-BIL-01 (bill run
#           pipeline, BR-BIL-037 stages 3·4·5) · EP-PAY-02 (allocation)
#           Screens: — (pure functions; their output renders in S31.2/S31.3)
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's TCs"; this file
#           ships NO story — it is the interface the B5 golden fixtures bind to
#           and every function in it is an honest stub. The stories that will
#           implement it are named in the docstring below, where G10 does not
#           read them as a completion claim.
# Rules:    BR-PAY-001 (default = oldest open bill; staff options specific /
#           carry credit / split — the `targets` argument) ·
#           BR-RAT-001 (multiplier BEFORE tiers) · BR-RAT-002 (tiers reset per
#           bill, thresholds scale with the prorated period) · BR-RAT-003
#           (round per line, half-up, 2dp, at finalization ONLY) · BR-RAT-004
#           (calendar-day proration of base AND usage) · BR-RAT-005 (tax base =
#           usage + base only) · BR-RAT-006 (exemption is account-level) ·
#           BR-RAT-011 (rollover consumption) · BR-RAT-026 (pure tiers) ·
#           BR-MET-026 (estimation math) · BR-MET-029 (true-up by register
#           arithmetic) · BR-BIL-001 (late fee = max($5, 1.5% × overdue
#           portion)) · BR-BIL-008 (grace: default 5 calendar days from Due) ·
#           BR-BIL-004 (issued invoices immutable; corrections = credit note) ·
#           BR-PAY-010 (allocation: oldest invoice first; within an invoice
#           usage+base → taxes → the tenant-defined class → fees LAST — the
#           `composition` / `class_order` contract, added 2026-08-11 by PO
#           ruling; the fourth class added the same day, OQ-109 closed)
# Golden:   GT-1 · GT-2 · GT-3 · GT-4 · GT-5 · GT-6 · GT-7 · GT-8 · GT-9 ·
#           GT-10 · GT-11 — B5 ❄️ FROZEN, finance-signed 2026-08-08.
# Tests:    06-backend/tests/golden/test_gt01..test_gt11 (all @requires_engine
#           xfail until the owning lanes land — that flip is the proof)
# Impacts:  apps/rating/engine.py (🔒 HUMAN-OWNED — must publish price_period /
#           prorate_base_charge) · apps/metering (consumption_from_registers,
#           true_up_quantity) · apps/billing (assess_late_fee,
#           issue_credit_note) · apps/payments (allocate_payment)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

billing → money-math SEAMS: the interface the B5 golden fixtures call.

WHAT THIS FILE IS
-----------------
The named, typed boundary between the FROZEN B5 expectations and the code that
must reproduce them. B5 (❄️ finance-signed 2026-08-08) states the figures; this
module states the SHAPE those figures arrive in; `tests/golden/` binds the two
together. Written test-first, deliberately: the specification exists before the
implementation, so the implementation has something to be wrong against.

WHAT THIS FILE IS NOT
---------------------
It is not the rating engine, and it holds no money math whatsoever. Every
function below is a stub that raises NotImplementedError. The arithmetic is
owned elsewhere and stays there:

  price_period / prorate_base_charge  -> apps.rating.engine   (🔒 HUMAN-OWNED,
        B4 money math; stories US-RAT-012 usage pricing + US-RAT-013 totals)
  consumption_from_registers          -> apps.metering        (BR-RAT-011 wrap
        arithmetic on the asset's register span; GT-4 / GT-14)
  true_up_quantity                    -> apps.metering        (BR-MET-029;
        stories US-MET-014 / US-MET-015)
  assess_late_fee / issue_credit_note -> apps.billing         (BR-BIL-001/008,
        BR-BIL-004)
  allocate_payment                    -> apps.payments        (BR-PAY-010)

LATE BINDING (the repo's seams.py pattern — apps/metering/seams.py precedent)
----------------------------------------------------------------------------
Each seam resolves its owner's callable AT CALL TIME. While the owner has not
published it, the seam raises NotImplementedError naming exactly what is
missing — so a golden test xfails at the seam with a readable reason instead of
erroring on an import, and so the day the owner lands the function the fixtures
start exercising it with no edit here ("built is not wired" — hard-won law 2).

✅ CONTRACT NOTICE — CLOSED 2026-08-10 (engine lane). The gap this notice used to
report ("`apps/rating/engine.py` exposes `rate(reads, tariff_version, period)`
and NOT `price_period`/`prorate_base_charge`") was closed the way it was meant to
be: the engine lane PUBLISHED both callables, plus `amount_for` for the
BR-RAT-045 amount rules. `rate()` remains in the engine as a named refusal so a
caller written against the old ORM-shaped signature fails loudly rather than
finding nothing. The seam was amended in the same change in exactly one place —
`_as_rated_bill` below — and no golden expectation moved.

TYPES
-----
Money is Decimal end to end (`NUMERIC(18,6)`, hard rule 2) — never float, never
cents. Rounding to 2dp happens exactly once, at invoice-line finalization,
inside the owner (BR-RAT-003 / B4.4); nothing here rounds. Consumption is always
a `Quantity` carrying its explicit unit (hard rule 3) — there is no code path in
this module that accepts a bare number as a consumption.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.billing.exceptions import BillingRuleError

# ── Value types (inputs) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Quantity:
    """A measured quantity WITH its unit. Hard rule 3: never assume a unit.

    ── `windows` and `demand`, added 2026-08-16 with the TOU and demand engines ─
    One service point can measure more than one thing in one period, and a
    contract that could only carry a single total is why a utility on
    time-of-use rates could not produce an electric bill. A TOU meter holds a
    REGISTER PER WINDOW (metering's `channel` vocabulary: `tou_on | tou_mid |
    tou_off`, B2 r8 / BR-MET-059) and a demand meter holds a max-demand register
    beside its energy one.

    Both default to EMPTY/None, and both absences mean UNKNOWN rather than zero.
    A TOU tariff handed no window quantities REFUSES, naming the window
    (`apps.rating.pricing.errors.MissingWindowQuantity`), for the reason
    `apps.billing.contracts.ServiceReading` already states about a whole
    service: a zero *"would be a claim that the meter was read and showed no
    usage, which is a different and sometimes very expensive statement"*.

    `demand` is a `Quantity` in its OWN unit — kW where `amount` is kWh. That is
    not tidiness: on B5 GT-21 (= WE-5) the two numbers are 48,200 and 182, and a
    shape that let them be confused would produce a bill that adds up perfectly
    and is wrong by thousands of dollars.
    """

    amount: Decimal
    unit: str
    #: Pre-split TOU quantities (BR-RAT-021). Empty on every non-TOU service.
    windows: tuple["WindowQuantity", ...] = ()
    #: The period's peak demand (BR-RAT-014). None when nothing measured one.
    demand: "Quantity | None" = None
    #: 🔒 **`DEF-RAT-8849` — A READ ON THE SEASON-CHANGE DAY REPLACES THE DAY
    #: SPLIT** (PO 2026-10-01, verbatim *"yes build the season-change day
    #: reading"*). Per register, what each season of a season-crossing period
    #: MEASURED, cut by `gather` at that read. Empty everywhere else, and the
    #: engine then splits by calendar days (BR-RAT-034).
    season_parts: tuple["SeasonParts", ...] = ()


@dataclass(frozen=True)
class SeasonParts:
    """One register's quantity per season, cut at a read on the boundary day.

    `DEF-RAT-8849` (PO 2026-10-01). `channel` is metering's register for a TOU
    window (`tou_on`, …) and `None` for the service's one billed quantity.
    `quantities` follow `TariffConfig.season_days`' chronological order and sum
    exactly to the register's quantity. WE-18 with a read on 1 Oct showing 80
    then 40: `SeasonParts(channel="tou_on", quantities=(80, 40))` — 80 at
    summer's $0.22, 40 at winter's $0.18.
    """

    channel: str | None
    quantities: tuple[Decimal, ...]


@dataclass(frozen=True)
class WindowQuantity:
    """One TOU window's pre-split consumption (BR-RAT-021), with its own unit.

    `channel` is METERING's vocabulary — `tou_on | tou_mid | tou_off` (B2 r8 /
    BR-MET-059) — and it is deliberately not the tenant's window label. A label
    is display text a tenant may rename or translate at any moment; a channel is
    the register that was read. This is the same distinction `TaxRule` draws
    between `code` and `tax_id`, and for the same reason: placing money by
    display text misposts silently the first time somebody renames something.
    """

    channel: str
    quantity: Quantity


@dataclass(frozen=True)
class BillingPeriod:
    """The service window and the cycle it sits in (B4.3: proration by CALENDAR
    days). `service_days` < `cycle_days` is a mid-cycle move-in / plan change;
    the proration factor the owner applies is service_days / cycle_days.

    `start`/`end` are OPTIONAL and default to None. What B4.3 rules on is the
    day COUNTS, and B5 states its proration case as "day 16 of 30" — a ratio,
    with no calendar dates anywhere in GT-1..GT-11. The dates exist here because
    tariff-version resolution needs a service date (BR-RAT-007), which no golden
    case in this range exercises; a fixture leaves them None rather than
    inventing a calendar.
    """

    cycle_days: int
    service_days: int
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class Tier:
    """One inclining-block tier. `upper` is the block's upper bound in the
    tariff's billed unit; None = the open-ended top block (B5 GT-2 "5+")."""

    upper: Decimal | None
    unit_price: Decimal


@dataclass(frozen=True)
class TouWindow:
    """One configured TOU window's PRICE for one season and day-type.

    Window TIMES are deliberately absent: the hours decide which register a kWh
    landed in, and that split has already happened by the time anything reaches
    this seam (BR-RAT-021 — *"reads arrive pre-split per window"*). Carrying the
    boundaries across would invite a second implementation of a split that has
    one owner.

    `channel` IS THE JOIN, and since 2026-08-16 a signed rule states it. A
    configured window is a row in `time_of_use_windows` with a tenant's own
    label; a measurement is a row in `meter_reads` with metering's channel
    (`tou_on | tou_mid | tou_off`, B2 r8 / BR-MET-059). **The utility says which
    is which**, on the S11 Time-of-use card, and the answer is stored on the
    window row — PO ruling 2026-08-16, verbatim: *"make the rate wizard say
    which register is which"* (OQ-236 CLOSED → BR-RAT-067). Rating READS the
    column (`apps.rating.selectors.pricing_inputs`); the price-rank resolution
    this docstring used to describe (BR-RAT-064) is superseded and its code is
    deleted. `None` means the utility never stated one — a schedule configured
    before the column existed — and the engine then REFUSES by name rather than
    pricing kWh at a window price picked by position or at 0.00.
    """

    label: str
    unit_price: Decimal
    channel: str | None = None
    season: str | None = None
    day_type: str = "weekday"


@dataclass(frozen=True)
class SeasonDays:
    """The calendar days of this bill period that fell in ONE season (BR-RAT-034).

    Added 2026-10-01 to build `OQ-234`'s ruling (CLOSED 2026-09-07, PO verbatim
    *"please split  swithch it on"*): a period crossing a season boundary splits
    pro-rata by calendar days. COUNTED BY RATING (`selectors._season_days_between`)
    against the stored season ranges and carried here unchanged; the engine is
    pure and holds no calendar. `season=None` is a day no season covers, which the
    engine refuses by name (BR-RAT-033). WE-18: `("Summer", 16), ("Winter", 14)`.
    """

    season: str | None
    days: int


@dataclass(frozen=True)
class SeasonTiers:
    """One season's own ladder on a `seasonal` schedule (BR-RAT-034, B2 r5 #2)."""

    season: str
    tiers: tuple[Tier, ...]


@dataclass(frozen=True)
class CapacityRate:
    """A capacity charge's TENANT-DEFINED unit label and rate (BR-RAT-022).

    "panel" @ $10.00 · "kW block" @ $12.00 · "meter equivalent" @ $6.00 — the
    label is free tenant text and it is the capacity service's BILLED UNIT, so
    the BR-RAT-038 UoM gate applies to it exactly as it does to kWh.
    """

    unit_label: str
    rate_per_unit: Decimal


@dataclass(frozen=True)
class TariffConfig:
    """The in-force tariff version as the engine receives it.

    `base_charge=None` means the fixture states NO base charge — absence, not a
    base of zero. B5 GT-4/GT-5 name no base, and inventing 0.00 would be
    inventing an input.

    ── AMENDED 2026-08-16: four more rate shapes can now cross this boundary ───
    Until this date this contract could express a flat price, a tier table and a
    base charge, and NOTHING ELSE — so `flat` and `tiered` were the only models
    the engine could price. `apps/rating/pricing/models/__init__.py` recorded the
    consequence honestly ("their configuration cannot travel on the seam's
    TariffConfig today") and the consequence was that a utility on time-of-use
    rates could not produce an electric bill, a sewer service billed as a
    percentage of water could not be priced, and a demand charge did not exist.

    Each field below is the configuration ONE model needs. None is read by any
    other model, and every one arrives from `apps.rating.selectors.pricing_inputs`
    — rating's own answer to "what does the engine need", kept correct by rating,
    because storage is not an interface.
    """

    service: str
    #: flat | tiered | time_of_use | percent_of_service | capacity | demand |
    #: seasonal (B2 r5 #16 + r6.1). ⚠ This read *"`seasonal` is in the enum and
    #: has no plugin — it refuses at the registry"* until 2026-10-01; `OQ-234`
    #: was CLOSED 2026-09-07 and the plugin is registered (`DEF-RAT-8832`).
    model: str
    billed_unit: str
    base_charge: Decimal | None = None
    unit_price: Decimal | None = None
    tiers: tuple[Tier, ...] = ()
    multiplier: Decimal = Decimal("1")
    #: `time_of_use` — the per-window prices (BR-RAT-021/033).
    windows: tuple[TouWindow, ...] = ()
    #: `time_of_use` — the season IN FORCE on the service date, resolved by the
    #: caller for the same reason the tariff VERSION is (BR-RAT-007): it is a
    #: lookup against stored date ranges, and a pure engine holds no calendar.
    season: str | None = None
    #: `time_of_use` + `seasonal` — **BR-RAT-034's split** (built 2026-10-01):
    #: the calendar days of the period in each season, chronological, counted
    #: by rating. Empty or one entry = a period inside one season, priced on
    #: `season` exactly as before. Two or more split each measured quantity
    #: pro-rata by days (WE-18 / GT-34).
    season_days: tuple[SeasonDays, ...] = ()
    #: `seasonal` — every season's own ladder (BR-RAT-034).
    season_tiers: tuple[SeasonTiers, ...] = ()
    #: **WHICH DAYS `season_days` WAS COUNTED OVER** — `(first, last)`, the
    #: account's served span of the bill period, set by `gather`. IDENTITY, like
    #: `version_id`: no arithmetic reads it. It exists so a caller that swaps the
    #: VERSION (the R2 fork, `resolution_switch._schedule_from_chain`) can ask
    #: rating to count the SAME days against the new version's seasons, rather
    #: than pricing one version's prices on another version's season calendar.
    season_span: tuple[date, date] | None = None
    #: `capacity` — the tenant's unit label and rate (BR-RAT-018/022).
    capacity: CapacityRate | None = None
    #: `demand` — energy per billed unit, and the peak charge per kW
    #: (BR-RAT-014). Both are required together; half a demand tariff refuses.
    energy_rate_per_kwh: Decimal | None = None
    demand_rate_per_kw: Decimal | None = None
    #: `demand` — captured so the engine can REFUSE a tariff whose measurement
    #: rules are still PROPOSED, rather than quietly bill the raw peak. The
    #: tenant switched these on believing something the engine cannot do.
    ratchet_enabled: bool = False
    pf_penalty_enabled: bool = False
    #: `percent_of_service` — PERCENT POINTS as typed on S11 (90 means 90%),
    #: and the service the percentage is taken OF (BR-RAT-015 as superseded by
    #: CR-081 and widened by CR-130-BRC07).
    percent: Decimal | None = None
    basis_service: str | None = None
    #: **A PERCENTAGE OF WHAT** — `'usage'` (of that service's metered
    #: quantity, priced on this schedule's own rate) or `'charge'` (of its
    #: usage-charge dollars). `BR-RAT-1030`, PO ruling 2026-09-22.
    #:
    #: ⚠ **IT IS CARRIED RATHER THAN DEFAULTED, AND THAT IS THE WHOLE POINT OF
    #: THE FIELD.** `rating.selectors.pricing_inputs` publishes the stored
    #: column on every version, `gather._tariff_config_for` copies it here, and
    #: `rating.pricing.stages.normalize` reads it off this object. A hop that
    #: dropped it would reach the plugin as None — and the plugin REFUSES a
    #: None instead of pricing on a guess, because 90% of a volume and 90% of
    #: money are different bills at the same 90%. Without this field the whole
    #: charge basis would be configurable on screen and dead in the bill run,
    #: which is CLAUDE.md hard-won law 2 exactly.
    percent_basis: str | None = None
    #: **WHICH VERSION THIS CONFIGURATION IS** — `rating.tariff_versions.id`,
    #: resolved by BR-RAT-007 against the SERVICE date and served by
    #: `rating.selectors.pricing_inputs`, which has carried it since it was
    #: written (*"travels onto the bill line — provable prices"*).
    #:
    #: ⚠ IT TRAVELS WITH THE PRICES AND NOT BESIDE THEM (DEF-276, 2026-08-19).
    #: Every line the engine prices from this config is stamped with this id and
    #: the stamp reaches `invoice_lines.tariff_version_id`. The alternative —
    #: looking the version up again at assembly from the tariff and the service
    #: date — agrees with the engine almost always and disagrees exactly when it
    #: matters, and a provenance column that can disagree with the price it
    #: describes is not provenance. BR-RAT-007/017 promise that an issued bill
    #: re-prices to the identical figure for seven years; this field is the only
    #: thing that makes the promise checkable.
    #:
    #: Optional because the golden fixtures state raw prices and no database:
    #: B5 GT-1..GT-11 name no version row and none is invented for them. A None
    #: reaching a real bill leaves the column NULL, which is what DEF-276 was.
    version_id: str | None = None
    #: ── WHICH CONNECTION SIZE PRICED THIS LINE (R3, `DEF-2823`) ────────────
    #: `meter_size_classes.code` for this service's connection, resolved by
    #: `gather._connection_size_for` and already used to select the tier ladder
    #: and the base charge code's per-size amount. It is CARRIED so that R3 can
    #: be compared SEPARATELY from R4 in the pricing shadow: while the base was
    #: one fused figure, neither step could ever satisfy the cutover's rule that
    #: a step switches only when its own class is at zero, and 47 of 47 accounts
    #: read *cannot evaluate* at both.
    #:
    #: ⚠ **NOTHING PRICES FROM IT.** The engine never reads this field — the
    #: ladder is already selected in `pricing_inputs` and the base is already
    #: resolved — so no ❄️ B5 figure can move: every golden fixture states no
    #: size and gets `None`, which is what they had before the field existed.
    size_class: str | None = None
    #: ── WHAT THAT SIZE IS CALLED, FOR THE LINE A CUSTOMER READS (`CR-063`) ─
    #: `BR-TEN-171`'s ratified NAME for `size_class` — *Fire line 6"*, *Fire
    #: line 2"* — resolved by `gather` and used by the pricing models to name a
    #: PER-SIZE line. (It read *Private hydrant* as the second example until the
    #: PO withdrew that size on 2026-09-03.)
    #:
    #: ⚠ **IT EXISTS BECAUSE TWO LINES OF ONE SERVICE ARE OTHERWISE
    #: INDISTINGUISHABLE.** A counting capacity service bills one line per size
    #: (decision log 2026-09-02), so a mixed fire property's document carries two
    #: fire lines; without a name both read *"fire usage"* and the customer cannot
    #: tell the `$60.00` line from the `$24.00` one — the very thing the ruling
    #: asks the bill to show: *"they are different equipment at different prices
    #: and a single blended quantity would hide that."*
    #:
    #: ⚠ **NOTHING PRICES FROM IT AND NO ❄️ B5 FIGURE CAN MOVE.** It changes a
    #: DESCRIPTION and never an amount, and it is `None` on every tariff every
    #: other caller builds — every golden fixture included — so every existing
    #: line's wording is byte-identical.
    size_label: str | None = None
    #: **THIS TARIFF IS ONE OF A SERVICE'S PER-SIZE LINES** — `CR-063`,
    #: decision log 2026-09-02. Set by `gather._per_size_configs` and by nothing
    #: else, so it is a STATEMENT rather than something a reader has to infer
    #: from two configs happening to share a service code.
    #:
    #: ⚠ **IT IS READ BY `resolution_switch` AND THE INFERENCE IT REPLACES WAS
    #: UNSAFE.** The R1–R7 chain resolves ONE answer per service and refuses a
    #: bill carrying two tariffs for one service, because a master account
    #: covers several units and it cannot say which connection an answer belongs
    #: to (`BR-CUS-068`). A per-size split produces the same shape for a
    #: completely different reason — ONE connection, several kinds of equipment
    #: on it — and telling the two apart by comparing size classes would
    #: misread a master account whose two water units happen to be different
    #: diameters. This flag cannot be misread.
    #:
    #: `False` on every tariff every other caller builds, so every bill this
    #: product has issued prices byte for byte.
    per_size_line: bool = False
    #: `DEF-BIL-8743` — set by `measure_consumption` where the quantity is the
    #: SUMMED installed capacity (CR-062 D1), so the engine prorates its money on
    #: a part period (B4.3, WE-16). See `rating.pricing.contracts`.
    installed_sum_line: bool = False
    #: ── R5, THE PREMISES JURISDICTION FACTOR (PO ruling 2026-08-19) ─────────
    #: r10: *"Premises outside city limits multiply base and variable by 1.5"*,
    #: and the PO's correction of the CR-013 design makes both halves explicit —
    #: *"you will have to add rate changes in base charges and rates"*.
    #:
    #: ⚠ IT IS NOT THE METER MULTIPLIER AND THE TWO ARE NOT INTERCHANGEABLE.
    #: The meter multiplier is a METERING fact that scales the QUANTITY before
    #: any tier boundary is walked (a x10 register reading 62 is 620 kWh, which
    #: lands in tier 2 where 62 never leaves tier 1) and it does not travel on
    #: this contract at all — consumption arrives post-multiplier, by the PO's
    #: ruling of 2026-08-11. THIS is a PRICING fact carried by the PREMISES: it
    #: scales the MONEY, after the tiers have been walked, on the base charge
    #: and the usage alike. Applying either one in the other's place produces a
    #: different number that looks entirely plausible on a document.
    #:
    #: PER SERVICE, because §A4's S2 needs it to be: electric and water move 50%
    #: while the sewer base is *"flat everywhere"* and does not.
    #:
    #: Defaults to 1 — no B5 figure states a jurisdiction factor and none is
    #: invented for one, so every frozen expectation prices exactly as before.
    jurisdiction_factor: Decimal = Decimal("1")
    #: ── THIS TARIFF CHARGES ITS BASE AND NO USAGE (DEF-990 · DEF-1060) ──────
    #: 🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.
    #:
    #: ⚠ **BASE-ONLY WAS AN ACCOUNT FACT AND IS NOW ALSO A TARIFF FACT, AND
    #: UNTIL IT WAS BOTH TWO RULED BILLS COULD NOT BE PRODUCED.**
    #: `SubscriptionContext.base_only` is BR-CUS-055's *behaviour class* — it is
    #: true of the WHOLE account (a vacation hold bills every service's base and
    #: no usage) and it cannot say *this one service bills base only while the
    #: one beside it prices usage*. Two PO rulings of 2026-08-27 need exactly
    #: that sentence:
    #:
    #:   * **BR-CUS-170 / DEF-990** — a master's bill carries the BASE CHARGES
    #:     of every unit on its premises nobody occupies, beside the common
    #:     areas it prices in full. On BR-MET-101's building with Unit C empty
    #:     and taking electric the owner owes `$69.60 + $12.00` = **`$81.60`**,
    #:     and that bill holds TWO electric tariffs — one pricing the hallway's
    #:     usage, one base-only for Unit C.
    #:   * **OQ-601 edge 1 / DEF-1060** — a service the UNIT takes that the plan
    #:     states no schedule for. PO verbatim: *"1 Unit has a service, plan has
    #:     no schedule for it - this will never happen, in such case bill base
    #:     only"*.
    #:
    #: **IT IS ALSO WHAT KEEPS A SECOND TARIFF OFF THE FIRST ONE'S METER.**
    #: `stages/measure_consumption._reading_for` matches a reading by SERVICE
    #: CODE alone, so a second electric tariff on one bill would silently pick
    #: up the first connection's read and bill that usage twice. A tariff
    #: flagged here never asks for a reading at all (that stage's own
    #: `ABSENT_TARIFF_BASE_ONLY` branch), which is the routing DEF-990 named as
    #: missing and is why the flag lives on the TARIFF rather than beside it.
    #:
    #: **False on every tariff `gather` has ever built**, so every bill this
    #: product has issued and every ❄️ B5 figure prices byte for byte: the
    #: engine reads no new field — `price_bill(base_only_services=…)` already
    #: prices a base with no usage line and is untouched — and billing's own
    #: routing is what this flag steers.
    base_only: bool = False
    #: ── BR-RAT-028 MODE A — THIS SERVICE'S OWN MINIMUM (CR-052 task 4) ──────
    #: 🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.
    #:
    #: `plan_services.minimum_amount`, the figure a clerk types beside the base
    #: charge on S9. When this service's own usage + base falls below it, the
    #: apply-charges stage tops the difference up as its own TAXABLE line
    #: (BR-RAT-028 mode A; B4's OQ-007 addendum: *"minimum bill adjustment line
    #: taxable like base"*).
    #:
    #: ⚠ **UNTIL 2026-08-30 NEITHER THRESHOLD COULD CROSS THIS BOUNDARY AT
    #: ALL**, and `apps/rating/pricing/stages/apply_charges.py` — the stage that
    #: OWNS the rule — said so in its own docstring: *"neither the per-service
    #: minimum (`plan_services.minimum_amount`) nor the plan floor
    #: (`plans.minimum_bill_amount`) can travel on the seam's `TariffConfig`
    #: today, so there is no input to apply."* A CONFIRMED rule with a signed
    #: worked example (WE-3: water-only, 0.4 kgal, `9.60` against a `15.00`
    #: floor → **`+5.40`**, total **`$16.42`**) was therefore charged on no
    #: bill this product has ever issued. These two fields are the input.
    #:
    #: `None` means NO MINIMUM — absence, exactly as `base_charge=None` means
    #: no base charge. A default of `Decimal("0")` would be a floor of zero
    #: that bites on nothing and reads identically to a stated one, which is
    #: the shape DEF-154 taught: a column that defaults to a plausible number
    #: is a number nobody typed.
    minimum_amount: Decimal | None = None
    #: ── BR-RAT-028 MODE B — THE PLAN'S FLOOR OVER THE WHOLE BILL ────────────
    #: `plans.minimum_bill_amount`. It is a fact about the PLAN and not about
    #: this service, and it rides here anyway because a plan is a BUNDLE (PO
    #: 2026-08-11) whose services all reach the engine as tariffs: carrying it
    #: on the bill-level call instead would mean a second way to reach
    #: `price_bill`, and `price_period` — the single-service seam every B5
    #: fixture is written against — could not state one at all.
    #:
    #: Every tariff of one plan therefore carries the SAME figure. The engine
    #: REFUSES a bill whose tariffs state two different floors rather than
    #: picking one (a master's bill can carry another plan's tariffs —
    #: BR-CUS-014/170), because nothing signed says which plan's floor governs
    #: a combined total.
    plan_minimum_bill_amount: Decimal | None = None
    #: **THE METER THIS TARIFF PRICES — PO ruling 2026-09-30** (*"both meter
    #: should be build in metered case also - as a speearte line"*). Set by
    #: `gather` ONLY when a metered service carries two or more in-service
    #: meters, one config per meter, each on its own tier ladder with its own
    #: base. `measure_consumption` pairs a config with ITS meter's reading by
    #: this id (never the first reading of the service), and the engine stamps
    #: it on the lines so `invoice_lines.asset_id` names the meter. `None` on
    #: every other config, which is every bill before the ruling.
    asset_id: str | None = None
    #: **THE EMPTY UNIT THIS BASE-ONLY TARIFF BELONGS TO — `DEF-BIL-8724`,
    #: 2026-10-01.** Set by `gather._unbilled_unit_tariffs` ONLY, on the base
    #: charge BR-CUS-170 puts on an owner's bill for a unit nobody occupies,
    #: which is priced from that UNIT's own plan (DEF-990). The ruled path
    #: (`resolution_switch._substituted`) resolves the OWNER's plan, one answer
    #: per service, so it cannot state a base that belongs to another unit on
    #: another plan; it leaves a tariff carrying this exactly as `gather` priced
    #: it, by name, instead of refusing the whole owner's bill. Moves no figure:
    #: no arithmetic reads it. `None` on every other tariff.
    covers_unit_id: str | None = None
    #: 🔒 **`DEF-CUS-9050` (PO 2026-10-02) — THE EMPTY UNIT'S NAME, AND THE SHARE
    #: OF THE PERIOD IT STOOD EMPTY.** Set by `gather._unbilled_unit_tariffs`
    #: ONLY, beside `covers_unit_id`. `covers_unit_label` names the line
    #: (*"Unit 4 · water base charge"*) and prices nothing. `occupancy_factor` is
    #: `vacant_days / period_days` for a unit let for PART of the period — the
    #: owner pays the base for the days nobody lived there (15/30 × $8.00 =
    #: $4.00) — and `None` for a unit empty all period, which multiplies by
    #: nothing. Both `None` on every other tariff, so no other line moves.
    covers_unit_label: str | None = None
    occupancy_factor: Decimal | None = None
    #: **THE CHARGE CODE THE BASE CAME FROM — A LABEL, NEVER A FIGURE**
    #: (`DEF-BIL-8316`, 2026-09-30). `gather._base_charge_code_for` has always
    #: answered `(amount, code)` and the code was dropped; the one-time bill's
    #: Rates table draws *"$8.00 · BASE-W"*. No arithmetic reads it: the engine
    #: prices from `base_charge` alone. `None` where no code answered.
    base_charge_code: str | None = None


@dataclass(frozen=True)
class TaxRule:
    """A percent tax applied to Σ(taxable lines) — usage + base only (B4.2).

    `code` is what the customer reads on the line ("State of Texas"); `tax_id`
    is WHOSE DEBT IT IS — the `rating.taxes` row, and through it the authority
    and that authority's own 2200-series liability account (BR-BIL-069, PO
    ruling 2026-08-11 closing OQ-116: *"For each atheority have separate account
    and tagging"*).

    The two are deliberately separate. `code` is display text a tenant may
    rename or translate at any moment; `tax_id` is an identity that does not
    move. Placing money by the display text was option D and the PO declined it
    — it costs nothing and misposts silently the first time a tax is renamed.

    Optional because a plan rule may state a `rate_override` for a jurisdiction
    that has no `taxes` row to point at. The tax is still charged (the rate is
    real); the LINE then names no authority and BR-BIL-010 refuses the bill at
    issue rather than guessing which authority is owed the money.

    `flat_amount` is BR-RAT-036's FLAT-PER-BILL form, added 2026-08-18 for the
    PO's ruled **PUC Regulatory Fee — $0.85 flat per bill, electric only**
    (decision log 2026-08-18; DEF-254/273). A rule states EITHER `rate` or
    `flat_amount`: percent and flat are different arithmetic and the engine
    refuses a rule stating neither rather than pricing it at 0.00.

    ⚠ **WHAT THIS DATACLASS DOES NOT CARRY, ON PURPOSE.** r10's ruled rates come
    with CONDITIONS — *"Commercial + Industrial only"*, *"Inside city limits"*,
    *"Electric only"* — and none of them appears here. They are evaluated in
    `rating.selectors.plan_tax_rules` BEFORE a rule is built, because the
    required outcome is **no tax line at all** and not a zero-valued one. A
    `TaxRule` reaching this module has already been ruled applicable; billing's
    job is to hand the engine the facts (`apps/billing/gather.py`) and print
    what comes back.
    """

    code: str
    #: DEF-RAT-9307 (PO 2026-10-03) — the clerk's Bill label, what the
    #: customer reads on the line. WORDING ONLY: no stage prices off it. None
    #: or blank = the line reads "Tax " + `code`, as every bill always has.
    bill_label: str | None = None
    rate: Decimal | None = None
    tax_id: str | None = None
    flat_amount: Decimal | None = None
    #: ── WHICH SUBTOTAL THIS AUTHORITY LEVIES ON (BR-RAT-106 / DEF-502) ──────
    #: `before` = the discount lands BEFORE this tax, so it levies on the
    #: REDUCED subtotal; `after` = it levies on the full tariff amount and the
    #: discount never reaches its base. STATUTORY AND STATED PER TAX
    #: (`taxes.discount_treatment` — CR-013 part 4: *"Any global before/after
    #: setting is wrong"*), which is why this rides the rule and not the bill.
    #: None answers `before` — the column's own default and the single
    #: behaviour every issued bill has had — and the field is inert on an
    #: undiscounted bill, which is every bill priced before DEF-502 closed.
    #: Filled by `gather._taxes_for` from rating's
    #: `discount_treatments_for_taxes`; read only by the engine's compute-tax
    #: through the one signed reader (`rating.selectors.taxable_subtotal_for`).
    discount_treatment: str | None = None
    #: ── WHICH SERVICES' MONEY THIS TAX IS A PERCENT OF (R7, 2026-08-19) ─────
    #: r10's City Franchise Fee is *"1.5% · Electric only"*, and the CR-013
    #: design's §A4 works it as 1.5% of the ELECTRIC lines — $1.82 on S1's
    #: $121.10 of electric, not $2.83 on the whole $188.90 bill. Until this
    #: field existed "electric only" could only be expressed as an
    #: APPLICABILITY condition, so a franchise fee on a three-service bill taxed
    #: the water and the sewer at the city's electric rate.
    #:
    #: EMPTY MEANS THE WHOLE BILL, which is every B5 fixture and every frozen
    #: figure — GT-1, GT-10 and GT-17 all state one rate over one combined base
    #: and none of them moves. Stated, it narrows the base to the taxable lines
    #: of those services, using `finalize.taxable_base` so there is exactly one
    #: definition of "the tax base" and not two.
    #:
    #: It does NOT decide whether the tax applies — that is still resolved
    #: before a rule is built (`rating.selectors.plan_tax_rules` /
    #: `rating.resolution.resolve_taxes`), because the required outcome of a
    #: failed condition is no line at all and not a zero-valued one (DEF-273).
    #:
    #: ⚠ **ON A PER-UNIT RULE IT NARROWS A QUANTITY, NOT A SUM OF MONEY** — the
    #: USAGE LINES whose units are counted. Same field, same meaning ("which
    #: services is this levied on"), two different things being narrowed,
    #: because the two forms are levied on two different kinds of thing.
    applies_to_services: tuple[str, ...] = ()
    #: ── BR-RAT-036's PER-UNIT FORM (CR-052 W5 task 16) ─────────────────────
    #: r10's Water Conservation Surcharge — *"$0.25 / kgal · Tier 3+ usage
    #: only"*. A rule states EXACTLY ONE of `rate`, `flat_amount` and
    #: `per_unit_amount`: they are three different arithmetics on three
    #: different bases (a money subtotal, nothing at all, and a measured
    #: quantity), and the engine refuses a rule stating none rather than
    #: pricing it at 0.00.
    #:
    #: `per_unit_uom` is the unit the amount is quoted PER and is MANDATORY on a
    #: per-unit rule — CLAUDE.md hard rule 3. The engine checks it against the
    #: unit the usage was measured in and REFUSES a mismatch; it holds no
    #: conversion factor and performs none (BR-RAT-038, *"no silent
    #: conversion"*).
    #:
    #: `applies_above_units` is BR-RAT-042 (CONFIRMED, PO closing OQ-054 option
    #: (a)): *"per-unit tax 'applies above N units' is MARGINAL: only units
    #: above the threshold are taxed"*. **Worked:** `18.72 kgal` against a
    #: threshold of `15` is taxed on `3.72`, so `$0.25/kgal` bills **`$0.93`**
    #: and not `$4.68`. `None` = no threshold, so every billed unit is taxed.
    #:
    #: All three are `None` on every rule this product has ever priced, so every
    #: existing bill and every ❄️ B5 fixture is byte-identical.
    per_unit_amount: Decimal | None = None
    per_unit_uom: str | None = None
    applies_above_units: Decimal | None = None
    #: BR-RAT-036's FOURTH form, PER-METER (DEF-386 / `DEF-RAT-9278`,
    #: CR-165-BRC10 round 2). The amount charged once per meter in the tax's
    #: scope — the engine counts the meters off the usage lines it already has
    #: (`compute_tax._meters_in_scope`). `None` on every rule this product
    #: priced before 2026-10-03, so every existing bill and every ❄️ B5 fixture
    #: is byte-identical.
    per_meter_amount: Decimal | None = None


@dataclass(frozen=True)
class DiscountRule:
    """One GRANTED discount, as the bill run hands it to the engine (DEF-502).

    THE ARITHMETIC IS NOT HERE. `apps/rating/discount_pricing.py` is R6's law —
    six rules, finance-shaped, HUMAN-REVIEW-PENDING — and this dataclass
    mirrors its `DiscountRule` input field for field so the engine's
    apply-discounts stage can convert structurally. Billing contributes no
    figure and no rule: everything below is rating's own stored configuration,
    resolved by `rating.selectors.billable_discount_rules` at the SERVICE DATE
    (the same pivot every tariff resolves on, BR-RAT-007), with the two gates
    already applied — the account's open ENROLMENT (BR-RAT-069: the grant) and
    the plan's BINDING (BR-RAT-110: availability; an enrolment in a discount
    the plan does not bind reaches no bill, exactly as
    `rating.resolution.resolve_discounts` drops it on the R-chain).

    `name` is the one field the law module does not carry: `Discount.name` is
    *"the bill line label"* (DIS-02 step 1) — part 3 requires the reduction to
    print as its own line and something has to print on it. The `code` is the
    programme's identity; the name is what the customer reads.

    Everything time-dependent — is it in force, is the proof verified, how much
    budget and cap headroom is LEFT — was resolved at gather, so the engine
    keeps no clock (BR-BIL-039) and cannot disagree with the run about what
    day it is.
    """

    code: str
    name: str
    discount_type: str  # percentage | fixed_amount | charge_waiver (priceable set)
    value: Decimal
    currency: str  # hard rule 2 — a fixed credit pairs with its currency
    applies_to: str  # whole_bill | usage_only | base_only | one_service | named_codes
    verified: bool = True
    proof_before_first_reduction: bool = True
    applies_to_service: str | None = None
    applies_to_charge_codes: tuple[str, ...] = ()
    cap_per_bill: Decimal | None = None
    cap_year_remaining: Decimal | None = None
    cap_lifetime_remaining: Decimal | None = None
    budget_remaining: Decimal | None = None
    exhaustion_behaviour: str = "suspend"
    bill_floor_amount: Decimal = Decimal("0")
    stacking_precedence: int = 100
    stacks_with_others: bool = True
    exclusivity_group: str | None = None


@dataclass(frozen=True)
class AccountContext:
    """Account-level facts the totals pass needs. Exemption is account-level and
    applies regardless of service (B4.2 / BR-RAT-006)."""

    currency: str
    tax_exempt: bool = False


# ── The allocation instruction (BR-PAY-010 · BR-PAY-001) ────────────────────
#
# The FOUR line classes BR-PAY-010 orders inside an invoice, and the order it
# puts them in. Mirrored in `apps.payments.allocation` (payments may not import
# billing, and billing calls payments), and asserted equal by
# tests/test_us_pay_006_allocation.py so the two copies cannot drift.
#
# It was three until 2026-08-11, when the PO closed OQ-109 with option C as
# amended — verbatim: *"C Its own class between tax and fees - it can be service
# fees or it can be special fees anything; allow tenant user to define it in
# ledge[r]"*. The MEMBERSHIP of the fourth class is tenant configuration in the
# ledger and is deliberately NOT mirrored here: this block carries the ORDER,
# and `apps.payments.allocation.TENANT_CLASS_READ` names the ledger read that
# carries the contents.

CLASS_USAGE_BASE = "usage_base"
CLASS_TAXES = "taxes"
CLASS_TENANT_DEFINED = "tenant_defined"
CLASS_FEES = "fees"

#: Every class BR-PAY-010's order can place — four of them since 2026-08-11.
ALLOCATION_CLASSES: tuple[str, ...] = (
    CLASS_USAGE_BASE,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_FEES,
)

#: BR-PAY-010 as extended by the PO on 2026-08-11: "within invoice usage+base →
#: taxes → the tenant-defined class → fees last". A DEFAULT, not a constant —
#: the rule says tenant-configurable and US-PAY-006 TC-5 exercises a tenant that
#: puts fees before taxes.
DEFAULT_CLASS_ORDER: tuple[str, ...] = (
    CLASS_USAGE_BASE,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_FEES,
)


@dataclass(frozen=True)
class ClassBalance:
    """One line class's share of an invoice's OPEN balance (BR-PAY-010).

    `balance` is what that class still OWES, not what it was originally billed:
    a bill part-paid last cycle opens this one with a smaller usage+base balance
    and its tax balance untouched. The caller states it because only the caller
    can see `invoice_lines` and the allocations already written against them —
    payments neither classifies lines nor re-derives a balance from them.
    """

    line_class: str
    balance: Decimal


@dataclass(frozen=True)
class ClassApplication:
    """What one payment put against ONE class of ONE invoice (BR-PAY-010).

    The output twin of `ClassBalance`; `applied` rather than `balance` because
    an allocation is a movement and a balance is a position.
    """

    line_class: str
    applied: Decimal


@dataclass(frozen=True)
class AllocationTarget:
    """One invoice the staff member NAMED, and the amount against it (BR-PAY-001).

    `amount is None` means "this bill, up to whatever it owes" — the `specific`
    instruction, where the customer named a bill and not a figure. A `split`
    states an amount per target and every amount is the staff member's, never
    computed here: Σ(amounts) must equal the payment exactly (US-PAY-006 TC-4,
    "Σ rows = payment amount"), so no distribution arithmetic — and therefore no
    new rounding event — exists inside this contract.
    """

    invoice_number: str
    amount: Decimal | None = None


@dataclass(frozen=True)
class OpenInvoice:
    """One open bill in an allocation run. B5 GT-7 names BL-A as "oldest" and
    gives no dates, so `issued_on` stays None there and the caller's sequence
    carries the ordering B5 states — no date is invented to stand in for it.

    `composition` is the WITHIN-invoice breakdown BR-PAY-010 walks (usage+base →
    taxes → the tenant-defined class → fees LAST). It is OPTIONAL because B5
    GT-7 states no line detail
    whatsoever and must stay expressible: a bill that states none is allocated
    by amount exactly as before and reports no breakdown, rather than a
    breakdown invented from its total. When stated, the class balances must foot
    to `balance`.
    """

    number: str
    balance: Decimal
    issued_on: date | None = None
    composition: tuple[ClassBalance, ...] = ()


# ── Value types (outputs) ───────────────────────────────────────────────────


@dataclass(frozen=True)
class RatedLine:
    """One priced line candidate. `taxable` is what drives the tax base (B4.2
    schema note): true on usage/base/minimum-adjustment, false on fees.

    ── WHAT PRODUCED THIS LINE (added 2026-08-11, BR-BIL-069) ────────────────
    `service` and `tax_id` are the line's IDENTITY, and they are on this
    contract because **the identity was being lost HERE**, at the seam, not
    only at the table. Until they existed a priced line carried its kind, its
    wording and its money and nothing else, so by the time it reached
    `invoice_lines` a usage line could not say which service it charged for and
    a tax line could not say whose tax it was. BR-BIL-010 stamps a GL account
    per line at issue, both maps are keyed on exactly these two facts, and the
    stamp therefore refused every real bill — which is what the PO's ruling of
    2026-08-11 closed (OQ-116).

    Worked, from the ruling itself: a $117.01 bill with a $100.58 taxable base
    carries $8.30 of tax that is NOT one tax — State of Texas 6.25% = $6.29,
    Harris County 1.00% = $1.01, City of Katy 1.00% = $1.00. Three authorities,
    three debts, three returns. Each line names its own `tax_id`, so each
    resolves its own authority's 2200-series account.

    Each is `None` on the lines it does not describe (a tax line names no
    service; a usage line names no tax), and NEITHER IS EVER INFERRED — not
    from `description`, not from `unit`. Water and sewer both meter in kgal.
    """

    kind: str  # "usage" | "base" | "tax" | "fee" | "minimum_adjustment"
    description: str
    amount: Decimal
    taxable: bool
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    #: The service CODE this line charged for — `tenancy.services.code`, the key
    #: the ledger's service→revenue map is keyed on. Set on usage/base lines.
    service: str | None = None
    #: The `rating.taxes` row that produced this line. Set on tax lines.
    tax_id: str | None = None
    #: **THE TARIFF VERSION THAT PRICED THIS LINE** (DEF-276, 2026-08-19) —
    #: `rating.tariff_versions.id`, carried from `TariffConfig.version_id` by
    #: the engine's own `price_usage` stage and written onto
    #: `invoice_lines.tariff_version_id` at assembly.
    #:
    #: Set on the lines a RATE SCHEDULE priced — usage and base — and None on
    #: the ones it did not. A tax line names its authority through `tax_id`
    #: instead (BR-BIL-069) and a fee line's provenance is its charge code; a
    #: version id on either would be a claim nothing supports, which is the
    #: same class of error as leaving the usage line blank.
    tariff_version_id: str | None = None
    #: **WHICH CHARGE CODE A FEE LINE CAME FROM** — `rating.charges.id`
    #: (DEF-714, 2026-08-25). The sentence directly above already said a fee's
    #: provenance IS its charge code; until this field existed there was
    #: nowhere for that fact to ride, so it was lost at the seam exactly as
    #: `service` and `tax_id` once were, and BR-BIL-010's stamp refused every
    #: fee line at issue for want of it. A tenant with any recurring or
    #: auto-apply charge code (BR-RAT-117, PO 2026-08-22) could issue NO bill.
    #:
    #: Set on fee lines whose producer knows the code — `gather
    #: ._charge_fees_for` (BR-RAT-117), `first_bill`'s connection charge
    #: (BR-BIL-012) and, since **BR-BIL-075** (PO ruling 2026-08-26, closing
    #: DEF-719), `decisions`' APPLIED LATE FEE.
    #:
    #: ⚠ **THE LATE FEE IS THE ONE CASE WHERE THE CODE SUPPLIES THE ACCOUNT AND
    #: NOT THE AMOUNT.** The other two producers read the amount off the code
    #: because those fees are flat; a late fee's amount is BR-BIL-001's ❄️
    #: FROZEN B4 figure (GT-10's **8.13**) and a code's `amount` never overrides
    #: it — that would need a finance re-sign under HUMAN-GUIDE §6. This field
    #: carries WHERE, never WHAT.
    #:
    #: None everywhere else, and a fee line that still names no code is refused
    #: at issue BY NAME rather than stamped on a guess.
    charge_id: str | None = None
    #: 2026-09-30 — the meter a usage/base line was priced for, when its
    #: service carries two (`TariffConfig.asset_id`). `None` everywhere else.
    asset_id: str | None = None
    #: 🔒 `DEF-2430` / `DEF-BIL-5341` (2026-10-03) — **WHICH PROGRAMME A
    #: DISCOUNT LINE WAS GRANTED UNDER** (`CAP`), carried from the engine's own
    #: priced line and written onto `invoice_lines.discount_code` at assembly,
    #: exactly as `tariff_version_id` and `charge_id` are. Issue hands it back
    #: to rating (`record_discount_grants` below) so the enrolment it spent is
    #: recorded and a yearly cap, a lifetime cap and a budget count down. Until
    #: it existed the line carried only the customer-facing NAME, and an issued
    #: bill could not say which enrolment to deplete. `None` on every other
    #: line; never inferred from `description`.
    discount_code: str | None = None


@dataclass(frozen=True)
class RatedBill:
    """The priced result. Totals are reported by the owner, never recomputed
    here — this seam does no arithmetic on money at all."""

    lines: tuple[RatedLine, ...]
    taxable_subtotal: Decimal
    tax_total: Decimal
    fee_total: Decimal
    total: Decimal
    currency: str

    def lines_of(self, kind: str) -> tuple[RatedLine, ...]:
        """Every line of one kind, in the order the owner emitted them."""
        return tuple(line for line in self.lines if line.kind == kind)

    def sole_line(self, kind: str) -> RatedLine:
        """The ONE line of a kind. Raises when there are none or several — a
        golden fixture that expects one usage line must fail loudly, not pick."""
        found = self.lines_of(kind)
        if len(found) != 1:
            raise AssertionError(f"expected exactly one {kind!r} line, got {len(found)}")
        return found[0]


@dataclass(frozen=True)
class Allocation:
    """One invoice's share of a payment (BR-PAY-010).

    `by_class` is what that share met INSIDE the bill, in the order it met it —
    empty when the invoice stated no composition. Only classes that received
    money appear: an allocation is a row in financial history and a row is
    written for money that moved, never for money that did not.
    """

    invoice_number: str
    applied: Decimal
    by_class: tuple[ClassApplication, ...] = ()

    def applied_to_class(self, line_class: str) -> Decimal:
        for entry in self.by_class:
            if entry.line_class == line_class:
                return entry.applied
        raise AssertionError(f"no {line_class!r} application recorded on {self.invoice_number!r}")


@dataclass(frozen=True)
class AllocationOutcome:
    """What one payment did to the open bills it met.

    `remaining_by_class` is the account-level outstanding composition — the
    figure US-PAY-006 TC-1 states as "47.87 = 21.90 + 20.97 + 5.00" and the one
    tax remittance reads (PO ruling 2026-08-11). Unlike `Allocation.by_class` it
    reports every class the open bills stated INCLUDING zeros, because a tax
    outstanding of 0.00 is a fact a remittance report must be able to read; it
    is empty only when no open bill stated a composition at all.
    """

    allocations: tuple[Allocation, ...]
    remaining_balance: Decimal
    credit_carried: Decimal
    remaining_by_class: tuple[ClassBalance, ...] = ()

    def applied_to(self, invoice_number: str) -> Decimal:
        for allocation in self.allocations:
            if allocation.invoice_number == invoice_number:
                return allocation.applied
        raise AssertionError(f"no allocation recorded for {invoice_number!r}")

    def remaining_of(self, line_class: str) -> Decimal:
        for entry in self.remaining_by_class:
            if entry.line_class == line_class:
                return entry.balance
        raise AssertionError(
            f"no outstanding balance reported for {line_class!r} — the open bills stated "
            "no composition, so no breakdown exists to report (B5 GT-7's shape)"
        )


@dataclass(frozen=True)
class CreditNoteOutcome:
    """A credit note raised against an ISSUED invoice (BR-BIL-004, hard rule 4).

    `invoice_total` is echoed back so a fixture can assert the original document
    was untouched; `journal_debits`/`journal_credits` prove the reversing entry
    is a balanced pair (hard rule 5) without this seam claiming to know which
    accounts it hits — B5 GT-6 says "balanced reversing journal entry" and
    stops there, so this reports balance and nothing more.
    """

    invoice_total: Decimal
    credit_total: Decimal
    balance: Decimal
    references_invoice: str
    journal_debits: Decimal
    journal_credits: Decimal


# ── Owner resolution ────────────────────────────────────────────────────────


def _resolve(module: str, attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    """The owning module's callable, or None while its lane has not landed."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _require(module: str, attribute: str, kind: str, golden: str) -> Callable[..., Any]:
    found = _resolve(module, attribute, kind)
    if found is None:
        raise NotImplementedError(
            f"{golden}: apps.{module}.{kind}.{attribute}(...) is not published yet — "
            "the golden fixture is frozen (B5, finance-signed 2026-08-08); the "
            "implementation is not written. Nothing here guesses a figure."
        )
    return found


#: `CR-101-BRC03` §06 — which programme and which VERSION a bill's discount
#: line names. Published by rating (`selectors.discount_versions_for_labels`)
#: and named here so the contract is greppable from both sides, exactly as
#: `billable_discount_rules` is for the pricing half.
DISCOUNT_VERSIONS_READ = "discount_versions_for_labels"  # (labels, on_day) -> {label: row}


def discount_versions_for_labels(labels: Any, on_day: date) -> dict[str, dict[str, Any]] | None:
    """The programme and the version behind each discount LABEL — or **None**.

    A discount reaches a bill as a line whose label is the programme's bill
    line label (`Discount.name`, DIS-02 step 1) and nothing else crosses with
    it — no code, no version, and no `discount_grants` row (see
    `corrections.discount_panel` for why). So the correction preview asks
    rating, BY LABEL, at the bill's own service date (BR-RAT-007's pivot),
    and rating answers with the programme's code and the version in force that
    day, or a NAMED reason it could not (`reason` on the row).

    **`None` means rating has not published the read; `{}` means nothing was
    asked.** The caller carries the difference onto the preview as a problem
    rather than drawing a version column that is blank for no stated reason.
    No arithmetic here — this is identity, never money.
    """
    read = _resolve("rating", DISCOUNT_VERSIONS_READ, "selectors")
    if read is None:
        return None
    answer = read(tuple(labels), on_day)
    return dict(answer) if isinstance(answer, dict) else None


# ── DEF-2430 / DEF-BIL-5341 · what an issued bill GRANTED, recorded by rating ─
#
# PO ruling 2026-10-03, verbatim: *"A · Yearly caps don't count down - a"*.
# Billing contributes the figures and the document; rating owns which
# enrolment and which version they spent (it already answers that while
# pricing), so these calls are the whole of the contract — named here so it
# is greppable from both sides, like `billable_discount_rules`.
DISCOUNT_GRANTS_WRITE = "record_grants_for_invoice"  # rating.discount_services
DISCOUNT_GRANTS_REVERSE = "reverse_grants_for_invoice"  # rating.discount_services
LINE_KIND_DISCOUNT = "discount"


@dataclass(frozen=True)
class GrantOutcome:
    """What issue recorded. TRANSIENT, like `.posting` — never a column.

    `unattributed` counts discount lines that name NO programme: only a draft
    assembled before `invoice_lines.discount_code` existed (`billing/0040`)
    can carry one. They issue as drafted and their reduction is NOT counted
    against any cap — reported here rather than refused, because refusing
    would hold drafts already in flight at the deploy, and recalculating such
    a draft stamps the code.
    """

    recorded: int = 0
    already_recorded: int = 0
    unattributed: int = 0
    reversed: int = 0
    #: DEF-RAT-9522 — programmes the bill gave a discount under that could not
    #: be counted against anything (the account never held them, or rating's
    #: writer is not published). Reported, audited — never a refusal.
    unrecorded: int = 0
    problem: str | None = None


def _granted_by_code(lines: Any) -> tuple[dict[str, Decimal], int]:
    granted: dict[str, Decimal] = {}
    unattributed = 0
    for line in lines:
        if getattr(line, "kind", None) != LINE_KIND_DISCOUNT:
            continue
        code = getattr(line, "discount_code", None)
        if not code:
            unattributed += 1
            continue
        # A discount line is stored NEGATIVE (it reduces the bill); a grant is
        # the POSITIVE subsidy given. The sign flips, nothing is rounded.
        granted[code] = granted.get(code, Decimal("0")) - Decimal(line.amount)
    return granted, unattributed


def record_discount_grants(invoice: Any, *, lines: Any, actor: Any = None) -> GrantOutcome:
    """Hand an ISSUING bill's discount lines to rating, which records one
    `discount_grants` row per programme so yearly caps, lifetime caps and
    budgets count down. Called by `issue.issue_invoice` INSIDE its
    transaction: a bill and the subsidy it spent are one fact.

    ⚖️ **IT NEVER REFUSES THE ISSUE** (`DEF-RAT-9522`; PO 2026-10-04: *"We
    cannot hold the bill; we need to make discount value to 0 and move on - we
    cannot stop the billing"*). 2.491.0 kept the bill a draft when the account
    no longer held the programme on its service date, and when rating's writer
    was absent. Rating now records against the enrolment that priced the bill
    (or audits that nothing could be counted), and an absent writer is
    reported on the outcome; the bill issues either way.
    """
    granted, unattributed = _granted_by_code(lines)
    if not granted:
        return GrantOutcome(unattributed=unattributed)
    write = _resolve("rating", DISCOUNT_GRANTS_WRITE, "discount_services")
    if write is None:
        return GrantOutcome(
            unattributed=unattributed,
            unrecorded=len(granted),
            problem="discount_grant_writer_not_published",
        )
    result = write(
        actor,
        account_id=invoice.account_id,
        invoice_id=invoice.pk,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        service_date=invoice.service_date,
        granted=granted,
    )
    return GrantOutcome(
        recorded=len(result.get("written") or ()),
        already_recorded=len(result.get("already_recorded") or ()),
        unattributed=unattributed,
        unrecorded=len(result.get("unrecorded") or ()),
    )


def grants_excluded(*invoice_ids: Any) -> Any:
    """Price AS IF these bills had granted nothing — rating's own read-only
    context (`discount_services.grants_excluded`), for a correction PREVIEW,
    so its figure matches the one the executed correction issues after it has
    given the original's grants back. A no-op context while rating has not
    published it."""
    excluded = _resolve("rating", "grants_excluded", "discount_services")
    if excluded is None:
        from contextlib import nullcontext

        return nullcontext()
    return excluded(*invoice_ids)


def reverse_discount_grants(
    invoice: Any, *, reason: str, document_id: Any = None, actor: Any = None
) -> GrantOutcome:
    """Give back what a CORRECTED bill granted — rating writes a reversing row
    per grant (hard rule 4). Called by `corrections.execute_restatement`
    BEFORE the rebill is priced, so the rebill sees the cap headroom the
    original spent. A bill that granted nothing reverses nothing."""
    reverse = _resolve("rating", DISCOUNT_GRANTS_REVERSE, "discount_services")
    if reverse is None:
        # DEF-RAT-9522 — a discount never stops a correction either; reported.
        return GrantOutcome(problem="discount_grant_reverser_not_published")
    result = reverse(actor, invoice_id=invoice.pk, reason=reason, document_id=document_id)
    return GrantOutcome(reversed=len(result.get("reversed") or ()))


class PricingRefused(BillingRuleError):
    """The rating engine refused to price this account, in BILLING's vocabulary.

    A seam adapts BOTH directions. `_as_rated_bill` below adapts the owner's
    RESULT onto billing's contract so rating never imports billing; this adapts
    the owner's REFUSAL for the same reason, in the same place.

    Why it exists at all (DEF-047): the run loop catches `GatherProblem` and
    `BillingRuleError` per account, so one bad account never stops the other
    499. Rating raises neither — `apps.rating.pricing.errors.RatingError` is its
    own hierarchy, deliberately (its own docstring: "the caller maps a refusal
    onto its own S31.3 exception row"). Nothing did that mapping, so a UoM
    mismatch, an unregistered pricing model or an account left with nothing
    priceable escaped the loop and killed the whole run — the exact failure
    BR-BIL-052 forbids and the loop's own docstring promises against.

    A subclass of `BillingRuleError` so that a caller which only knows billing's
    base class still catches it. `runs.calculate_run` catches this one FIRST, to
    name `price-usage` as the stage rather than the base class's default.
    """


def _refusal_types() -> tuple[type[BaseException], ...]:
    """Rating's own refusal base class, resolved by name like its callables.

    The same late binding as `_resolve`: billing must not import rating at
    module scope, and an empty tuple is a legal `except` that catches nothing —
    so while rating's error module is absent, its exceptions propagate unwrapped
    rather than being silently swallowed by a bare `except Exception`. Only
    `RatingError` is caught; an `AttributeError` inside the engine is a bug in
    the engine and must NOT be reported to a clerk as "this account cannot be
    priced".
    """
    try:
        module = import_module("apps.rating.pricing.errors")
    except ImportError:  # pragma: no cover - defensive
        return ()
    base = getattr(module, "RatingError", None)
    if isinstance(base, type) and issubclass(base, BaseException):
        return (base,)
    return ()  # pragma: no cover - defensive


def _priced(owner: Callable[..., Any], what: str, **kwargs: Any) -> RatedBill:
    """Call the owner and adapt whatever comes back — a bill or a refusal."""
    try:
        return _as_rated_bill(owner(**kwargs))
    except _refusal_types() as refusal:
        raise PricingRefused(f"rating refused to price {what}: {refusal}") from refusal


# ── Rating engine (🔒 apps.rating.engine — B4 money math) ───────────────────


def price_period(
    *,
    tariff: TariffConfig,
    consumption: Quantity,
    period: BillingPeriod,
    account: AccountContext,
    taxes: tuple[TaxRule, ...] = (),
    fees: tuple[RatedLine, ...] = (),
) -> RatedBill:
    """Price one service point for one period. PURE: no I/O, no clock, no writes.

    This is THE seam of EP-RAT-05 — the shape chosen so that every B5 case is
    expressible as data rather than as a call sequence:

    * `tariff` carries the model AND its configuration (flat price or tiers,
      base charge, meter multiplier). One argument, because a tier table without
      the multiplier that feeds it is not a testable unit — B4.4's whole content
      is the ORDER of those two (GT-5).
    * `consumption` is a `Quantity`, never a bare number (hard rule 3, GT-2's
      kgal vs GT-5's kWh).
    * `period` carries cycle days AND service days, because B4.3 proration and
      BR-RAT-002 tier-threshold scaling are both functions of that ratio and
      must be driven by one input, not two that can disagree (GT-3).
    * `account` carries the exemption flag, because B4.2 makes exemption an
      ACCOUNT fact — passing it per service would encode the rule finance
      explicitly rejected (GT-11).
    * `taxes` are percent rules applied to Σ(taxable lines); `fees` are
      already-computed non-taxable charge lines the caller (billing) supplies.
      Fees are an INPUT rather than an output because B4.2's claim is structural
      — a fee present on the bill must not reach the tax base — and the only way
      to test that claim is to hand the engine a fee and watch it stay out
      (GT-10 / GT-11, and EP-RAT-05 US-RAT-013 TC-1 states the fixture the same
      way: "late fee 8.13 present").

    Returns priced lines plus the totals the owner computed. Line amounts are
    finalized half-up to 2dp by the OWNER (BR-RAT-003); intermediates stay at
    NUMERIC(18,6) and never surface here.
    """
    owner = _require("rating", "price_period", "engine", "GT-1/2/5/10/11")
    return _priced(
        owner,
        f"service {tariff.service!r}",
        tariff=tariff,
        consumption=consumption,
        period=period,
        account=account,
        taxes=taxes,
        fees=fees,
    )


def price_bill(
    *,
    services: tuple[tuple[TariffConfig, Quantity], ...] = (),
    base_only_services: tuple[TariffConfig, ...] = (),
    period: BillingPeriod,
    account: AccountContext,
    taxes: tuple[TaxRule, ...] = (),
    fees: tuple[RatedLine, ...] = (),
    discounts: tuple[DiscountRule, ...] = (),
) -> RatedBill:
    """Price a WHOLE BILL — every service on the plan, ONE tax pass. PURE.

    `price_period` above prices one service point, which is the shape every B5
    single-service fixture is written in. A real account is usually not that: a
    plan is a BUNDLE (PO ruling 2026-08-11), and billing's stage-1 contract has
    carried `tariffs: tuple[TariffConfig, ...]` from the day it was written.
    This is the function that joins them, and until it existed no multi-service
    bill could be priced at all (DEF-032).

    `services` is a tuple of `(tariff, consumption)` pairs — only the services
    that HAVE a measured consumption. A missing read never arrives there: it is
    a decision the run resolved first (BR-BIL-015), because a parameter that
    accepted an absence would eventually turn one into a zero.

    `base_only_services` carries the OTHER absence, and the split is the point.
    BR-BIL-028 (CONFIRMED): on a vacation hold "base charges and flat services
    continue the full month" while usage lines stop — so these services bill
    their base charge and produce NO usage line, rather than a $0.00 one that
    would tell the customer their meter was read and showed nothing. Unknown
    and known-to-be-none are different facts, and this is where the difference
    reaches a document.

    TAX IS NOT PER SERVICE. It is computed once over Σ(rounded taxable lines)
    across every service, emitting one line per authority — B5 GT-17 (the WE-1
    reference bill: five services, one base of 221.90, four tax lines) and
    B4.2's 2026-08-11 re-signing, whose stated reason is that a customer adding
    up the printed lines and applying the rate must arrive at the printed tax.
    FEES are bill-level and are added once, after the services: a late fee is a
    fact about the account, and charging it per service would multiply it.
    """
    owner = _require("rating", "price_bill", "engine", "GT-17")
    named = tuple(tariff.service for tariff, _ in services) + tuple(
        tariff.service for tariff in base_only_services
    )
    kwargs: dict[str, Any] = dict(
        services=services,
        base_only_services=base_only_services,
        period=period,
        account=account,
        taxes=taxes,
        fees=fees,
    )
    if discounts:
        # DEF-502 — passed ONLY when there is one, so the empty case is
        # byte-identical to every call this seam has ever made, and an engine
        # deployment that predates the discount stage prices an undiscounted
        # bill exactly as before. When a discount IS present and the engine
        # cannot take it, the TypeError propagates LOUDLY rather than the
        # argument being dropped: silently pricing an enrolled customer's bill
        # at full price is DEF-502 itself, reintroduced by a compatibility
        # shim (the same reasoning as gather's `_call_pricing_inputs`).
        kwargs["discounts"] = discounts
    return _priced(
        owner,
        f"this bill ({', '.join(named) or 'no services at all'})",
        **kwargs,
    )


def price_fee_bill(
    *,
    account: AccountContext,
    taxes: tuple[TaxRule, ...] = (),
    fees: tuple[RatedLine, ...],
) -> RatedBill:
    """Price a FEE BILL — charge-code lines and ONE tax pass over them. PURE.

    The ❄️ B4.2 finance re-sign of 2026-09-30 (`OQ-812` option (b)): a fee bill
    is taxed when its charge code is marked taxable. PO verbatim: *"Yes,
    re-sign."* — worked figure RECON $75.00 at 8.25% → **$81.19**.

    A SEPARATE DOOR from `price_bill`, on purpose: `price_bill` refuses a bill
    with no services by name, and that refusal protects the metered path (see
    `fee_bill`'s module docstring). The engine's `price_fee_bill` runs the same
    finalize → compute-tax → assemble stages over the fee lines alone, so the
    arithmetic is the engine's and not a second implementation here.
    """
    owner = _require("rating", "price_fee_bill", "engine", "B4.2 fee-bill re-sign 2026-09-30")
    return _priced(owner, "this fee bill", account=account, taxes=taxes, fees=fees)


def _as_rated_bill(priced: Any) -> RatedBill:
    """Adapt the owner's result onto THIS module's published contract.

    Why an adapter rather than having the engine build a `RatedBill` directly:
    billing calls rating, so rating must not import billing. The engine returns
    its own frozen result type with these exact field names; this function maps
    them across, field for field, and performs NO arithmetic — every amount and
    every total is the owner's, copied. A result that is already a `RatedBill`
    passes straight through, so a future owner may return one either way.
    """
    if isinstance(priced, RatedBill):
        return priced
    return RatedBill(
        lines=tuple(
            RatedLine(
                kind=line.kind,
                description=line.description,
                amount=line.amount,
                taxable=line.taxable,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                # BR-BIL-069 — the identity crosses with the money. `getattr`
                # rather than attribute access for the same reason every other
                # cross-module read here is late-bound: an owner that has not
                # yet added these fields must degrade to "this line names
                # nothing" (which BR-BIL-010 refuses, loudly, at issue) rather
                # than to an AttributeError in the middle of a bill run.
                service=getattr(line, "service", None),
                tax_id=getattr(line, "tax_id", None),
                # DEF-276 — the PROVENANCE crosses with the money, by the same
                # late-bound read and for the same reason: an owner that has not
                # yet stamped it must degrade to a line that names no version
                # (which is what every bill issued before 2026-08-19 did) rather
                # than to an AttributeError in the middle of a bill run.
                tariff_version_id=getattr(line, "tariff_version_id", None),
                # DEF-714 — and so does a FEE's charge code, by the same
                # late-bound read. This adapter is the last place the identity
                # can be lost, and losing it here costs the whole bill: issue
                # resolves a fee's GL account from this id and refuses the bill
                # without it, so an owner that has not yet stamped it degrades
                # to the named refusal every fee line got before 2026-08-25 —
                # never to an AttributeError mid-run.
                charge_id=getattr(line, "charge_id", None),
                # 2026-09-30 — the meter, read late-bound like its neighbours.
                asset_id=getattr(line, "asset_id", None),
                # DEF-2430 — the programme a discount line was granted under,
                # by the same late-bound read: an owner that has not stamped it
                # degrades to a line issue cannot record (reported, see
                # `record_discount_grants`), never to an AttributeError.
                discount_code=getattr(line, "discount_code", None),
            )
            for line in priced.lines
        ),
        taxable_subtotal=priced.taxable_subtotal,
        tax_total=priced.tax_total,
        fee_total=priced.fee_total,
        total=priced.total,
        currency=priced.currency,
    )


def charge_amount(
    *,
    rule: str,
    amount: Decimal | None = None,
    percent: Decimal | None = None,
    basis: Decimal | None = None,
    minimum: Decimal | None = None,
) -> Decimal:
    """One charge amount rule, computed by rating's registry (BR-RAT-045).

    Billing owns WHEN a charge applies; rating owns WHAT it comes to. This seam
    is that split made concrete: `assess_late_fee` below decides the grace clock
    (BR-BIL-001/008) and calls this for `max($5, 1.5% x overdue portion)`, so
    GT-8's arithmetic exists in exactly one implementation rather than two that
    can drift.

    Returns NUMERIC(18,6) UNROUNDED — the caller finalizes once (BR-RAT-003).
    """
    owner = _require("rating", "amount_for", "engine", "GT-8")
    return owner(rule=rule, amount=amount, percent=percent, basis=basis, minimum=minimum)


#: What `plan_late_fee_terms` answers when a plan charges NO late fee. The
#: string is the REASON, carried so a refusal-shaped zero can be SAID rather
#: than merely returned (CLAUDE.md — an absence is invisible to every check
#: this repo has).
LATE_FEE_NO_TERMS_REASON = "plan_names_no_late_fee_charge_code"


def plan_late_fee_terms(
    rate_plan_id: Any, customer_class: str | None = None, on_date: Any = None
) -> dict[str, Any] | None:
    """The `percent` and `minimum` a PLAN charges late fees on — or None = ZERO.

    **BR-RAT-1011 / `CR-078`, PO ruling 2026-09-07, finance re-signed the same
    day.** Verbatim: *"you ahve to take late fees form charge code mentione din
    the plan - if plan doent provide you that charge code then you have to put
    zero on late payment. - Logic aplplied ot Minimum late fee $5"*.

    ⚠ **None IS THE RULED ZERO, NOT A MISSING SEAM.** This read returns None
    both when the plan names no code and when rating has not published the
    reader at all, and those two must not be conflated — so the second case
    RAISES instead. A seam that answered "no fee" because it could not look
    would turn a deployment problem into free late fees for every customer,
    silently, which is the failure mode `CR-078`'s ordering exists to prevent.

    The engine's arithmetic is untouched: `charge_amount(rule="percent_min")`
    still computes `max(minimum, percent × basis)` and `assess_late_fee` still
    finalizes it once. What moved is where the two TERMS come from — the charge
    code the plan names, rather than the tenant's Billing-defaults screen. The
    seeded `LATE` code carries the same `1.5` / `5`, so `GT-8`/`GT-10`'s ❄️
    FROZEN **8.13** is 8.13 either way.
    """
    owner = _resolve("rating", "plan_late_fee_terms", "selectors")
    if owner is None:
        raise NotImplementedError(
            "apps.rating.selectors.plan_late_fee_terms is not published, so the late-fee "
            "terms a plan charges on cannot be read (BR-RAT-1011 / CR-078). This RAISES "
            "rather than answering 'no fee', because a missing seam and a plan that "
            "charges nothing are different facts and only one of them is a rule."
        )
    # DEF-RAT-8753 — the account's customer class and the assessment day pick
    # the code's per-class terms where it states any; a code with none answers
    # exactly as it did (GT-8 / GT-10 unchanged).
    if customer_class is None and on_date is None:
        return owner(rate_plan_id)
    return owner(rate_plan_id, customer_class=customer_class, on_date=on_date)


def prorate_base_charge(*, base_charge: Decimal, period: BillingPeriod) -> Decimal:
    """The base charge for a partial period — B4.3 CONFIRMED: CALENDAR days.

    Split out from `price_period` because B5 GT-3 freezes exactly one figure
    (the prorated base) and explicitly leaves the usage half and the bill total
    open. A fixture must be able to bind to the one frozen number without
    inventing the consumption B5 does not give it.
    """
    owner = _require("rating", "prorate_base_charge", "engine", "GT-3")
    return owner(base_charge=base_charge, period=period)


# ── Metering (consumption arithmetic — quantities, never money) ─────────────


def consumption_from_registers(
    *,
    prior_read: Decimal,
    current_read: Decimal,
    multiplier: Decimal,
    register_digits: int,
    unit: str,
) -> Quantity:
    """Consumption from two register readings, wrap-aware (BR-RAT-011 / GT-14).

    `register_digits` is the asset's register span exponent (BR-AST-015): the
    span is 10**digits, and the >50%-of-span drop is what distinguishes a
    rollover from a negative-read exception. It is an explicit input because the
    span is an ASSET fact, and a wrap computed against an assumed span is the
    silent-fix this rule exists to prevent.
    """
    owner = _require("metering", "consumption_from_registers", "services", "GT-4")
    return owner(
        prior_read=prior_read,
        current_read=current_read,
        multiplier=multiplier,
        register_digits=register_digits,
        unit=unit,
    )


def true_up_quantity(*, actual: Quantity, previously_billed: Quantity) -> Quantity:
    """The correction carried onto the next bill after an estimate (BR-MET-029).

    Quantities only. B5 GT-9 freezes the QUANTITY arithmetic (estimate 618 kWh,
    actual 700 kWh, true-up +82 kWh) and states no rate and no dollar figure, so
    this seam returns no money and the fixture asserts none.
    """
    owner = _require("metering", "true_up_quantity", "services", "GT-9")
    return owner(actual=actual, previously_billed=previously_billed)


# ── Billing (late fee, credit note) ─────────────────────────────────────────


def assess_late_fee(
    *,
    overdue_amount: Decimal,
    percent: Decimal,
    minimum: Decimal,
    due_date: date,
    as_of: date,
    grace_days: int,
    grace_mode: str,
) -> Decimal:
    """`max(minimum, percent × overdue_amount)` once grace has run out.

    Every term is an explicit input, none is a constant: B4.1 makes the base the
    OVERDUE PORTION (not the full balance), the grace clock start the DUE DATE
    (not the issue date), and BR-BIL-008 makes the grace length and mode tenant
    settings (default 5, calendar). `as_of` is passed in rather than read from a
    clock — the event-time law, BR-TEN-043, and G6 greps for the violation.
    """
    owner = _require("billing", "assess_late_fee", "services", "GT-8")
    return owner(
        overdue_amount=overdue_amount,
        percent=percent,
        minimum=minimum,
        due_date=due_date,
        as_of=as_of,
        grace_days=grace_days,
        grace_mode=grace_mode,
    )


def issue_credit_note(
    *,
    invoice_number: str,
    invoice_total: Decimal,
    credit_amount: Decimal,
    reason_code: str,
) -> CreditNoteOutcome:
    """Raise a credit note against an ISSUED invoice — a NEW row, always.

    The issued document is immutable (hard rule 4 / BR-BIL-004): the outcome
    echoes `invoice_total` unchanged, names the invoice the note references, and
    reports a balanced reversing journal pair (hard rule 5).
    """
    owner = _require("billing", "issue_credit_note", "services", "GT-6")
    return owner(
        invoice_number=invoice_number,
        invoice_total=invoice_total,
        credit_amount=credit_amount,
        reason_code=reason_code,
    )


# ── Payments (allocation) ───────────────────────────────────────────────────


def allocate_payment(
    *,
    payment_amount: Decimal,
    open_invoices: tuple[OpenInvoice, ...],
    order: str = "oldest_first",
    targets: tuple[AllocationTarget, ...] = (),
    class_order: tuple[str, ...] = DEFAULT_CLASS_ORDER,
) -> AllocationOutcome:
    """Spread one payment across open bills (BR-PAY-010).

    `order` is an explicit argument, defaulted to the shipped default, because
    the closure makes the order a TENANT SETTING — hardcoding "oldest first"
    would encode a default as a law. `class_order` is the same argument one
    level down: BR-PAY-010's within-invoice walk is tenant-configurable too
    (US-PAY-006 TC-5) and defaults to usage+base → taxes → the tenant-defined
    class → fees LAST (OQ-109, PO 2026-08-11).

    `targets` carries the staff instruction BR-PAY-001 confirms and this seam
    could not express until 2026-08-11: the invoice a `specific` payment names,
    and the amount against each invoice of a `split`. Added by PO ruling
    2026-08-11 ("build both now") — before it, both orders refused for want of
    anywhere to put the target. Empty on the ordered walks, which take no
    target at all.

    WHY A SEPARATE ARGUMENT rather than an encoding inside `order`
    ("specific:BL-2607") or a single instruction object: `order` is a stored
    TENANT SETTING (BR-BIL-021's "allocation order" config family) while a
    target is a per-payment STAFF INSTRUCTION typed on the S22 form — one is
    configuration and one is input, they have different lifetimes and different
    owners, and packing them into one string would make the tenant default
    unreadable without parsing. The pre-existing three-argument call keeps
    working unchanged, which is why B5 GT-7's fixture did not move.
    """
    owner = _require("payments", "allocate_payment", "services", "GT-7")
    return owner(
        payment_amount=payment_amount,
        open_invoices=open_invoices,
        order=order,
        targets=targets,
        class_order=class_order,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources this seam was
#         written from, concatenated in order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `RatedLine` gains `service`/`tax_id` and `TaxRule` gains `tax_id` — the identity was being lost AT THIS SEAM) · AMENDED 2026-08-16 by the register lane (the TouWindow.channel contract note: a signed rule now states the join — BR-RAT-067)
# amended:   2026-08-11 by story-coder (payments composition + targets lane) — the
#            ALLOCATION half only. `OpenInvoice` gained `composition`, `Allocation`
#            gained `by_class`, `AllocationOutcome` gained `remaining_by_class`, and
#            `allocate_payment` gained `targets` + `class_order`, implementing PO rulings
#            #5 and #6 of 2026-08-11. Every addition is DEFAULTED, so the pre-existing
#            three-argument call is unchanged and no B5 fixture moved. `price_period`,
#            `price_bill` and `_as_rated_bill` were not touched, and this file still holds
#            no arithmetic — the new types declare a shape and compute nothing.
# amended:   2026-08-16 by the pricing-engines lane — the CONFIGURATION half of four
#            rate shapes. `TariffConfig` gained windows + season + capacity + the two
#            demand rates + the ratchet/PF flags + percent/basis_service; `Quantity`
#            gained `windows` (BR-RAT-021's pre-split registers) and `demand` (a
#            quantity in its OWN unit, kW beside kWh); `TouWindow`, `CapacityRate` and
#            `WindowQuantity` are new. Every addition is DEFAULTED, so no pre-existing
#            call moved and no B5 figure moved. This file still holds NO arithmetic.
# amended:   2026-08-11 by Eng-Lead (W3 bill-run lane) — DEF-047, the REFUSAL
#            direction. `_as_rated_bill` adapted the owner's result and nothing
#            adapted the owner's error, so `apps.rating.pricing.errors.RatingError`
#            travelled untranslated into billing's run loop, which catches only
#            billing's own types — one unpriceable account killed a whole run.
#            Added `PricingRefused` (a `BillingRuleError`), `_refusal_types()`
#            (rating's base class resolved BY NAME, the same late binding as its
#            callables, so neither module imports the other) and `_priced()`, now
#            the single call path for both `price_period` and `price_bill`. NO
#            arithmetic was added and no B5 figure moved; the adapter still copies
#            fields and computes nothing. Only `RatingError` is caught — an
#            `AttributeError` inside the engine stays an engine bug.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → 7 passed / 4 xfailed✔ (AMENDED 2026-08-10 by the rating-engine lane: the four seams whose OWNERS have not landed still xfail — GT-4/GT-9 metering, GT-6 billing corrections, GT-7 payments) · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: (1) NO US-ID in the Trace header, deliberately — G10 reads a header US-ID as "this file ships that story's TCs" and this file ships none; the implementing stories are named in the docstring instead. (2) The engine contract gap is CLOSED (2026-08-10): apps/rating/engine.py now publishes `price_period`, `prorate_base_charge` and `amount_for`; `rate(reads, tariff_version, period)` remains there as a named refusal. This seam was amended in the same change in two places — `_as_rated_bill` (a field-for-field adapter, no arithmetic, so rating never has to import billing) and the new `charge_amount` seam (billing owns the late-fee grace clock, rating owns the amount). (3) This seam is 🔒-adjacent (it names rating math) but is NOT on the G7 guard list: 10-scripts/gates/human_owned.txt is out of this lane's ownership, and the file still holds zero arithmetic — the adapter copies fields and computes nothing. Flagged for the PO batch. (4) GT-3/GT-4/GT-5/GT-9 are only PARTIALLY frozen in B5; the seam exposes exactly the sub-function each frozen figure needs so no fixture has to invent the missing inputs.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
