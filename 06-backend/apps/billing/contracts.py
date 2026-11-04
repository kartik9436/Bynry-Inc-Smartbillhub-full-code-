# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (the run's internal shape — seven stages, one input and
#           one output contract each)   Screens: — (S31.2 renders stage 1–5
#           output; S31.3 acts on it)
# Rules:    BR-BIL-037 (seven named stages, one fixed order; a stage receives
#           its predecessor's output and nothing else) · BR-BIL-039 (stages 1–5
#           are PURE — no writes, no external calls, no clock; only stage 6
#           writes) · BR-TEN-043 (event-time law) · CLAUDE.md rule 2 (money
#           NUMERIC(18,6) + currency) · rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_bil_029_stages.py
# Impacts:  apps/billing/stages/** · apps/billing/rating_seam.py (stages 3–5)
# ───────────────────────────────────────────────────────
"""The contracts the bill run's stages pass between them.

BR-BIL-039 says stages 1–5 are pure: **no writes, no external calls, no clock.**
Read that literally and it settles the whole shape of the run, because a stage
that cannot call anything cannot go and fetch what it needs. Everything it
needs must already be in its input.

So the run has a GATHER step in front of the pipeline — one impure pass that
reads the database and builds `AccountBillingData` per account — and then the
pipeline is arithmetic over data that is already in memory. That is not a
convenience; it is what makes three separate things possible:

  * **The preview.** BR-BIL-039: "the S31.2 preview is stages 1–5 with stage 6
    not run." A preview and a real run are then THE SAME CODE with the last
    stage withheld, rather than two implementations that agree until they
    don't.
  * **The PO's screen.** *"we build the data first for billing show all that
    data on screen for user … in case any data should be changed, he is able
    to do it."* `AccountBillingData` is that data. It is what is shown, what is
    edited, and what the pipeline then runs on — so what the clerk saw and
    what got billed cannot diverge.
  * **Re-rate.** BR-BIL-039: "re-rate replays stages 2–6 with no compensating
    cleanup." Replaying is trivial when the stages hold no state and touch
    nothing outside their arguments.

WHY THESE ARE FROZEN DATACLASSES AND NOT DICTS. A dict passed down seven
stages accumulates keys nobody declared and loses keys nobody noticed. The
type IS the contract BR-BIL-037 asks for, and a stage that returns the wrong
shape fails at its own boundary instead of three stages later.

MONEY AND QUANTITIES. Money is `Decimal` with an explicit currency
(CLAUDE.md rule 2). A consumption is a `Quantity` carrying its unit, never a
bare number (rule 3) — the same discipline `apps/metering/quantities.py`
applies upstream, so the unit survives from the meter to the bill line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from apps.billing import rating_seam


@dataclass(frozen=True)
class ServiceReading:
    """What one service point measured over the period — or why it did not.

    `consumption` is None when there is NO usable read. That is not an error
    here and must not be turned into a zero: a missing read and a genuine zero
    are different facts about a customer, and BR-BIL-015 makes the missing one
    a decision a human takes (estimate / hold / bill without this service).
    Stage 2 carries the absence forward; the run surfaces it.
    """

    service_code: str
    service_id: str | None = None
    consumption: rating_seam.Quantity | None = None
    #: Present when the quantity came from an estimate rather than a real read
    #: (BR-MET-029). It changes what the bill says, so it travels with it.
    estimated: bool = False
    #: Why there is no consumption, when there is none: no_read | no_meter |
    #: read_flagged | meter_replaced. Free text is not enough — the run groups
    #: exceptions by this.
    absent_reason: str | None = None
    prior_read: Decimal | None = None
    current_read: Decimal | None = None
    #: THE READ'S OWN IDENTITY, carried from `apps.metering.selectors
    #: .billing_reads_for_unit` (which has always published it) all the way to
    #: issue, where `mark_read_billed` applies BR-MET-053's BILLED lock.
    #:
    #: ⚠ **THIS FIELD DID NOT EXIST AND ITS ABSENCE WAS DEF-098.** The identity
    #: crossed metering's seam on every row and was DROPPED here, at billing's
    #: own contract boundary — the string `read_id` appeared nowhere in
    #: `apps/billing/` — so nothing could tell metering which reads a bill had
    #: priced. A read that HAD been billed still read as `committed`, a clerk
    #: correcting it took the plain supersede path, and **no correction linkage
    #: was recorded**: precisely the failure US-MET-016 exists to prevent.
    #:
    #: None when there is no read to name (no meter, no read, base-only). It is
    #: never invented and never defaulted to a service point id — a lock on the
    #: wrong row is worse than no lock, because it is silent.
    read_id: str | None = None
    #: **`DEF-CUS-5931` · THIS QUANTITY CAME FROM A READING NOBODY HAS
    #: COMMITTED**, keyed by a clerk on the move-out wizard's step 2 and due to
    #: be written at step 6 with the close (Billing blueprint p111, PO ruling
    #: 2026-09-20 *"option b is correct"*).
    #:
    #: ⚠ **IT IS A DIFFERENT CLAIM ABOUT A CUSTOMER AND IT TRAVELS WITH THE
    #: FIGURE.** A bill priced from a committed read is priced from a fact; one
    #: priced from a keyed read is priced from what somebody typed and may still
    #: change. `preview_final_bill` carries it to S20's step 3, which says so on
    #: its face, and it is `False` on every reading in every bill run, every
    #: back-bill and every one-time bill — so no ❄️ B4/B5 figure moves.
    provisional: bool = False
    #: **BR-MET-500's FACTOR, ON THE ROW THAT USED IT.** Metering has published
    #: it on the reading row since `DEF-1812` and billing's contract dropped it,
    #: exactly as it dropped `read_id` before `DEF-098`.
    #:
    #: ⚠ **READ ONLY WHERE THERE IS NO COMMITTED HEAD TO ASK (`provisional`).**
    #: `resolution_shadow._multiplier_for` resolves the factor through
    #: `metering.billing_multiplier_for`, which answers from the latest billable
    #: head — and a keyed read has none, so the chain would refuse a reading
    #: whose factor is perfectly well known. Preferring this field on EVERY row
    #: would be the better rule and is `DEF-CUS-5935`; it is not taken here
    #: because it would move the factor on live bills, which is a money change
    #: and belongs in its own commit.
    #:
    #: `None` wherever metering published none — never `Decimal("1")`, because
    #: an absent factor is not 1 (`resolution.MeterMultiplierUnstated`).
    multiplier: Decimal | None = None
    #: **`DEF-BIL-5270` — WHAT METERING'S OWN READ COUNTED UP FROM**, kept only
    #: where the anchor moved this period off it. PO ruling 2026-09-14: a period
    #: OPENS at the closing read of the last ISSUED bill, not at the previous
    #: read on the meter, because the difference is consumption a customer
    #: physically used that no bill would ever carry — *"we cannot create wrong
    #: conusmption that is loss"*.
    #:
    #: `prior_read` is then the ANCHOR (13,500) rather than this (13,800),
    #: because `BR-BIL-030` freezes *each meter with its prior and current read*
    #: into the bill, and a document printing 13,800 → 14,212 while charging 712
    #: does not foot on the customer's own copy.
    #:
    #: So this is the TRACE and never an input to any arithmetic: it answers
    #: *why is this bill 300 kWh larger than metering's stored consumption*. A
    #: money figure that moves silently is what this repository is bitten by
    #: most often. `None` on every reading in every pre-ruling fixture, so no
    #: ❄️ B4/B5 figure moves.
    unanchored_prior_read: Decimal | None = None
    #: **BR-RAT-090 (DEF-1813) — the OBSERVED count that PRODUCED `consumption`,
    #: on an UNMETERED service.** Three carts on a unit is a billable quantity
    #: of `3`, which a `$15.00` per-cart schedule prices at `$45.00`; remove one
    #: and the next bill is `$30.00`. `None` on every metered service and on
    #: every service whose quantity came from a register.
    #:
    #: ⚠ **IT IS NOT A SECOND COPY OF THE QUANTITY — IT IS WHAT MAKES A COUNTED
    #: LINE DISTINGUISHABLE FROM A READ ONE.** `consumption` says *3 cart* and
    #: `read_id` is None either way for a service with no read, so without this
    #: field nothing downstream could tell a counted quantity from a quantity a
    #: clerk estimated. The R1–R7 shadow reads it rather than issuing a query of
    #: its own, which is the mapping-not-a-data-job property that whole exercise
    #: rests on.
    #:
    #: ⚠ **`0` AND `None` ARE DIFFERENT FACTS.** `0` is the utility having
    #: looked and found no carts; `None` here means this service's quantity did
    #: not come from a count at all. *"Nobody looked"* never reaches this field:
    #: it is refused one layer earlier, by name, and the account stops.
    asset_count: int | None = None
    #: **CR-062 D1/H2 — the SUM of the installed capacity on this unit, and the
    #: unit that sum is in.** The Product Owner's own example, 2026-09-02: three
    #: panels of 2 kW, 4 kW and 8 kW are **14 kW**, and at their `$14.00` per kW
    #: that is **$196.00** — where the COUNT above would have said `3` and
    #: billed `$42.00`, a 78% undercharge on the same array.
    #:
    #: ⚠ **BOTH FIELDS TRAVEL TOGETHER OR NEITHER DOES (hard rule 3).** A total
    #: without its unit is not a quantity, and `14` alone could be kilowatts,
    #: ERU or megabits. Metering stamps them as a pair and
    #: `measure_consumption` refuses to price one without the other.
    #:
    #: ⚠ **THIS DOES NOT REPLACE `asset_count`, AND THE ROW CARRIES BOTH.** They
    #: answer different questions about the same equipment — *how many* and *how
    #: much* — and which one a bill uses is decided where the TARIFF is in hand,
    #: because a schedule quoting *$14.00 per kW* bills the kW and one quoting
    #: *$10.00 per panel* bills the panels. Keeping both means a counted line
    #: stays explicable next to a summed one on the same document.
    #:
    #: `capacity_uom` is `None` for every BANDED service — trash, fire, water —
    #: and that `None` is the statement *"these do not sum in any unit"* rather
    #: than a gap. `installed_capacity` is `None` where the total could not be
    #: STATED (an asset records no size class, or one this service does not
    #: have) and **is never a zero**: an empty unit sums to `0`, which is a real
    #: billable answer under BR-MET-108's ruled zero.
    installed_capacity: Decimal | None = None
    capacity_uom: str | None = None
    #: `DEF-RAT-10220` — where `installed_capacity` could not be stated, the
    #: NUMBERS of the assets whose size has no capacity (or no size at all),
    #: so the refusal can name them. Empty everywhere else; never a quantity.
    capacity_unresolved_assets: tuple[str, ...] = ()
    #: **`CR-063` C3/C5 — HOW MANY OF EACH SIZE, for a service billed by a
    #: COUNT PER SIZE.** Decision log 2026-09-02: *"the bill carries ONE LINE
    #: PER SIZE, and the quantity on each line is the count of items of that
    #: size."* A mixed fire property is `{"FL-6": 1, "FL-2": 2}` — one 6" fire
    #: line at `$60.00` and two 2" lines at `$12.00` each, `$84.00` in total on
    #: TWO lines. (`CR-063`'s warehouse held this example at `$110.00` until the
    #: PO removed the private hydrant from fire's size list on 2026-09-03; it
    #: now bills `$60.00` on ONE line.)
    #:
    #: ⚠ **IT IS THE SPLIT OF `asset_count`, NOT A SECOND COUNT.** The two are
    #: published from ONE population at ONE date and must agree —
    #: `sum(asset_size_counts.values()) == asset_count` — because a bill that
    #: counted one set of assets and grouped another would foot perfectly and be
    #: wrong, and nothing downstream could see it.
    #:
    #: ⚠ **A `None` KEY IS AN ITEM WHOSE SIZE NOBODY RECORDED, AND IT IS A
    #: REFUSAL RATHER THAN A ZERO** (same ruling). Dropping it would price a 6"
    #: fire line at nothing on a document that foots and prints.
    #:
    #: `None` for every service not billed that way — every metered service, and
    #: the four capacity services that SUM their capacity into one quantity.
    asset_size_counts: "dict[str | None, int] | None" = None
    #: **THE METER THIS READING IS FROM — PO ruling 2026-09-30.** Metering sets
    #: it only when a METERED service point carries two or more in-service
    #: meters and so publishes one row per meter (*"both meter should be build
    #: in metered case also - as a speearte line"*). `None` on every other row,
    #: which is every row before the ruling: one meter, or one exchange, is
    #: still one row per service point.
    asset_id: str | None = None
    #: **`DEF-BIL-8324` — THE DAY THIS READ MEASURES FROM** (the prior read's
    #: date, metering's `measured_from`). A catch-up uses it to see that a read
    #: taken after a stretch nobody read measured that stretch too, and shares
    #: it by days rather than estimating the stretch a second time. `None`
    #: where there is no read or the read stored no start.
    measured_from: date | None = None
    #: 🔒 **`DEF-MET-10163` — A LATER ACTUAL ALREADY COVERS THIS PERIOD** (PO
    #: 2026-10-15, *"go with 1 and 3"*). Set by metering only on a reading with
    #: no read in the period whose meter holds a later actual measuring from on
    #: or before the period's end. Billing then estimates nothing: the usage
    #: waits for the next bill, which that reading measures. `None` everywhere
    #: else, so no existing figure moves.
    covered_by_read_id: str | None = None
    #: 🔒 **`DEF-RAT-8849` · EVERY REGISTER READING INSIDE THE PERIOD**, as
    #: metering's `billing_reads_for_unit` published them (`period_registers`,
    #: the heads it had already loaded — no extra query). Read by exactly one
    #: thing: `gather`, which looks for a reading dated on a SEASON-CHANGE DAY
    #: and, where one exists, prices the usage before it and after it at each
    #: season's rates instead of splitting by days (PO 2026-10-01, *"yes build
    #: the season-change day reading"*). Never priced from directly.
    period_registers: tuple[dict, ...] = ()
    #: 🔒 **`DEF-BIL-9075` — EVERY READING THIS QUANTITY WAS SUMMED FROM**,
    #: the closing one first. Since `DEF-BIL-9016` a period with a reading
    #: partway through charges for each reading in its chain, so issue locks
    #: them ALL (BR-MET-053), not only `read_id`. Empty where metering published
    #: none (a keyed move-out read), and `read_id` alone is then locked.
    chain_read_ids: tuple[str, ...] = ()
    #: 🔒 **`DEF-BIL-8244` — THE TWO PARTS OF A METER SWAPPED INSIDE THE
    #: PERIOD**, once a clerk accepted *bill both parts* (changes rows 44–46).
    #: One entry per meter — `meter`, `asset_id`, `read_id`, `from`, `to`,
    #: `quantity`, `unit` — old meter first. `consumption` is their SUM and
    #: `prior_read`/`current_read` are None, because one pair cannot foot two
    #: registers. Empty on every other reading, so no existing figure moves.
    meter_parts: tuple[dict, ...] = ()


#: The one shape a gathered WARNING takes — `{"key": str, "params": dict}`.
#: A catalogue key and its parameters, never a sentence: the screen renders it
#: in the clerk's language (B14 rule 35) and the run groups on the key.
WARN_NO_AGREEMENTS = "billing.oneTime.warn.noAgreements"


@dataclass(frozen=True)
class AccountBillingData:
    """Everything the pipeline needs about ONE account, gathered before it runs.

    This is the object the PO's prepare screen shows, the object a clerk edits,
    and the object the stages consume. One object for all three on purpose: if
    the screen rendered one shape and the pipeline consumed another, "what I
    approved" and "what was billed" would be two different things that merely
    look alike.

    `billable` is the BR-CUS-055 behaviour class already resolved — billable,
    billable_base_only, non_billable or terminal — because the class lives on
    the account's STATUS row and a pure stage cannot go and read it.
    """

    account_id: str
    account_no: str
    behavior_class: str  # BR-CUS-055 — billable | billable_base_only | ...
    currency: str  # CLAUDE.md rule 2 — the tenant's, never client input
    tax_exempt: bool  # B4.2 — account-level, regardless of service
    period_start: date
    period_end: date
    cycle_days: int
    service_days: int  # < cycle_days for a mid-period move-in (B4.3)
    #: Plan resolved through the unit (PO ruling 2026-08-11 — the account
    #: DERIVES its plan; there is no account-side plan record).
    rate_plan_id: str | None = None
    rate_plan_name: str | None = None
    rate_plan_version: int | None = None
    #: One tariff configuration per service the plan covers.
    tariffs: tuple[rating_seam.TariffConfig, ...] = ()
    readings: tuple[ServiceReading, ...] = ()
    taxes: tuple[rating_seam.TaxRule, ...] = ()
    #: Fees already sitting on the account that this bill carries — a late fee
    #: a clerk applied, for instance. INPUTS to the totals pass, never computed
    #: by it (the shape GT-10 is written in).
    fees: tuple[rating_seam.RatedLine, ...] = ()
    #: DEF-502 (2026-08-22) — the account's GRANTED discounts: open enrolment ∩
    #: the plan's binding, resolved at the service date by rating's
    #: `billable_discount_rules` (BR-RAT-069/110 — the plan makes a discount
    #: AVAILABLE, the enrolment GRANTS it, and the run reads both gates).
    #: Gathered here, like the taxes above, because stages 1–6 are pure and
    #: cannot go and read an enrolment; applied ONCE at the bill level by the
    #: engine's apply-discounts stage (BR-RAT-071: before taxes). Empty = an
    #: undiscounted bill, which prices byte-identically to pre-DEF-502.
    discounts: tuple[rating_seam.DiscountRule, ...] = ()
    #: BR-RAT-114 (2026-08-22) — the mid-period split, when the period contains
    #: a rate-version or plan boundary. Each entry is a `midperiod.SplitSegment`
    #: (typed loosely because contracts may not import the orchestrator's
    #: module): one sub-period, gathered at ITS OWN service date, carrying its
    #: own plan, tariff versions and apportioned consumption. EMPTY on every
    #: unsplit account — which is every account before this field existed —
    #: and the pipeline then prices exactly as it always has; the split branch
    #: in `runs.calculate_account` never runs. Attached by `prepare_run` /
    #: `prepare_single_bill` so the clerk's prepare screen and the priced bill
    #: read the same object.
    split_segments: tuple[Any, ...] = ()
    #: `BR-BIL-300/301` — the plan's services THIS PROPERTY IS NOT IN SERVICE
    #: FOR: no service point, or (PO 2026-09-30) a point with no asset on it,
    #: or a `%`-of-service whose basis is one of those. **Since 2026-09-30
    #: they print NO line** (*"sane no line - and use 0"*; until then each
    #: carried a `$0.00 (not connected)` line in `fees`). This tuple is what is
    #: left of the ruling and it is the half that matters: read by
    #: `runs._decisions_for` so the accounts billing zero for a service they
    #: are sold land on the Check screen a clerk works through. **Carried
    #: rather than re-derived**, because `gather` has already asked
    #: `service_points_for` and a second read here could answer differently —
    #: a bill that marked one set of services and listed another would be two
    #: facts where the ruling names one. `()` on every account whose unit takes
    #: everything its plan prices, which is every bill this product has issued.
    unconnected_services: tuple[str, ...] = ()
    #: What the document will print, captured at gather time so the bill's
    #: locked-at-issue snapshot is built from what the clerk saw.
    snapshot: dict = field(default_factory=dict)
    #: BR-BIL-870 (2026-08-28) — WHICH RULES OF THE R1–R7 CHAIN PRICED THIS
    #: ACCOUNT. Empty on every deployment that has not switched one on, which
    #: is all of them, and empty is therefore what every bill this product has
    #: ever issued would carry.
    #:
    #: It exists because the choice is carried by a DEPLOYMENT SETTING and
    #: hard-won law 4 says a host's environment and the repo can disagree: with
    #: nothing stamped, nobody could say which narrowing produced a given
    #: bill. Stamping it here puts the answer on the object the clerk approves
    #: and the pipeline consumes, rather than only in a host's environment.
    resolution_steps: tuple[str, ...] = ()
    #: PO ruling 2026-09-30 — NAMED WARNINGS the bill carries while it is being
    #: made: the bill COMPLETES and the process says so (*"if you want to show
    #: the warning you can display it dueing the process"*). Each entry is
    #: `{"key": str, "params": dict}` — a catalogue key and its codes/names,
    #: never a composed sentence (`apps/billing/bill_warnings.py` owns the
    #: shape). `()` on every account nothing warns about, which is every bill
    #: this product issued before the ruling, so no payload moves for them.
    #: Written by more than one step (the `$0.00` base, the no-agreements
    #: bill): APPEND to it, never assign over it.
    warnings: tuple[dict, ...] = ()
    #: PO ruling 2026-09-30 (fixed-charge case 1, *"Bill without it"*): the
    #: service codes whose BASE bills on this bill while their USAGE waits for
    #: the next reading. Written only by `decisions._apply_to_account`; `()`
    #: on every other account, so no existing payload moves.
    usage_next_bill: tuple[str, ...] = ()
    #: PO ruling 2026-10-01 — *"i want tracbility -> billing -> account -> unit
    #: -> plan -> rate schedule -> base charge -> size and amount"*. Per service
    #: code, what its base and price were found from: base code, rate schedule
    #: version, customer type, and per size the count, base each, base total
    #: and price each — VALUES, written onto every line of that service by
    #: stage 6 (`invoice_lines.pricing_trace`). Empty on a fixture-built
    #: object, which then writes no trace.
    pricing_trace: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriptionContext:
    """Stage 1's output — WHAT is being billed, before any measuring.

    Separating "what does this account subscribe to" from "how much did it use"
    is what lets a base-only account bill at all: it has a subscription and no
    usage, and the two stages disagree about it in a way the pipeline handles
    rather than a single function papering over.
    """

    account_id: str
    account_no: str
    currency: str
    tax_exempt: bool
    period: rating_seam.BillingPeriod
    rate_plan_id: str | None
    rate_plan_name: str | None
    rate_plan_version: int | None
    #: The services this run will price for this account, already narrowed by
    #: the run's service scope and by the account's behaviour class.
    tariffs: tuple[rating_seam.TariffConfig, ...]
    taxes: tuple[rating_seam.TaxRule, ...]
    fees: tuple[rating_seam.RatedLine, ...]
    #: True when the behaviour class permits base charges but NOT usage
    #: (BR-CUS-055 Vacation-hold / Suspended). Stage 2 reads this and returns
    #: no usage rather than being asked to invent a zero.
    base_only: bool
    snapshot: dict
    #: DEF-502 — carried from `AccountBillingData.discounts` unchanged, the way
    #: taxes are: stage 1 states WHAT the account subscribes to and what rides
    #: its bill; the engine's apply-discounts stage is what prices them.
    #: Defaulted so pre-DEF-502 fixture constructors keep working.
    discounts: tuple[rating_seam.DiscountRule, ...] = ()
    #: 2026-10-01 — carried from `AccountBillingData.pricing_trace` unchanged
    #: so stage 6 can write it. Defaulted so other constructors keep working.
    pricing_trace: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MeasuredService:
    """One service's measured position after stage 2."""

    service_code: str
    tariff: rating_seam.TariffConfig
    consumption: rating_seam.Quantity | None
    estimated: bool = False
    absent_reason: str | None = None
    #: The read this service was priced from (DEF-098). Carried through stage 2
    #: so stage 6 can freeze it into the bill's own snapshot, which is what
    #: makes it still findable at issue — by then the readings are gone
    #: entirely and `issue_invoice` receives only the Invoice.
    #:
    #: Set ONLY on a service that actually measured. A service with no
    #: consumption names no read, because there is no read to lock.
    read_id: str | None = None
    #: BR-RAT-090 (DEF-1813) — the OBSERVED count this service's quantity IS,
    #: on an unmetered service. Carried through stage 2 so the document can say
    #: *three carts* rather than *3 cart of usage*, and so a counted line stays
    #: distinguishable from a read one after `read_id` has told it nothing.
    asset_count: int | None = None
    #: **`CR-063` — WHICH SIZE this row is the line for**, when the service
    #: bills one line per size. `None` for every other service, and for a
    #: counting service on a unit whose equipment carries no size at all.
    #: The exception screen and the snapshot read it so two fire rows on one
    #: account stay tellable apart after the tariff has gone.
    size_class: str | None = None
    #: 2026-09-30 — the METER this row is, when its service carries two (see
    #: `ServiceReading.asset_id`). The snapshot's `services` list is one entry
    #: per `MeasuredService`, so two meters are two entries, each naming its
    #: meter. `None` everywhere else.
    asset_id: str | None = None
    #: 🔒 `DEF-BIL-8244` — the swap's two parts, carried from the reading to
    #: the snapshot (`ServiceReading.meter_parts`). Empty everywhere else.
    #: 🔒 **`DEF-BIL-9075` — EVERY READING THIS QUANTITY WAS SUMMED FROM**,
    #: the closing one first. Since `DEF-BIL-9016` a period with a reading
    #: partway through charges for each reading in its chain, so issue locks
    #: them ALL (BR-MET-053), not only `read_id`. Empty where metering published
    #: none (a keyed move-out read), and `read_id` alone is then locked.
    chain_read_ids: tuple[str, ...] = ()
    meter_parts: tuple[dict, ...] = ()


@dataclass(frozen=True)
class MeasuredUsage:
    """Stage 2's output — WHAT was used, per service, or why it is unknown.

    `unmeasured` is the list the exception step works from. It is a first-class
    part of the output rather than an error, because BR-BIL-015 makes a missing
    read a decision and not a failure: the run continues, the account waits for
    a human, and nothing is invented in the meantime.
    """

    subscription: SubscriptionContext
    services: tuple[MeasuredService, ...]

    @property
    def unmeasured(self) -> tuple[MeasuredService, ...]:
        """Services with no consumption — every one needs a human decision."""
        return tuple(s for s in self.services if s.consumption is None)

    @property
    def measured(self) -> tuple[MeasuredService, ...]:
        return tuple(s for s in self.services if s.consumption is not None)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (sha1[:7] of the four billing sources: B2 §2 +
#         Addendum r10 · EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md
#         · 07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — contracts) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_029_stages.py
# exceptions: `AccountBillingData.snapshot` is an untyped dict because what a
#         bill PRINTS is template-shaped and tenant-specific — the same
#         reasoning as `invoices.issued_snapshot`. The trade is that nothing
#         constrains its contents, and it is stated rather than hidden
#         · a missing read is carried as `consumption=None` with a reason, NEVER
#         coerced to zero: a missing read and a genuine zero are different facts
#         about a customer and BR-BIL-015 makes the first one a human decision
# exceptions: [DEF-1813 2026-08-28] `ServiceReading.asset_count` and
#         `MeasuredService.asset_count` carry BR-RAT-090's OBSERVED count, so a
#         quantity that was COUNTED stays distinguishable from one that was read
#         or estimated all the way to the document. `None` means the quantity did
#         not come from a count; *nobody looked* never reaches these fields — it
#         is refused a layer earlier, by name.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
