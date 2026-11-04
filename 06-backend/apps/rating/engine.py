# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing: consumption → priced lines) ·
#           US-RAT-013 (totals: tax base + account exemption) ·
#           US-RAT-015 (rule-type plugins: one interface per pricing model,
#           one per charge amount rule)
#           Screens: — (pure service; priced lines render in S31.2/S31.3)
# Rules:    BR-RAT-001 (multiplier BEFORE tiers) · BR-RAT-002 (tier thresholds
#           reset per bill, scale with the prorated period) · BR-RAT-003 (round
#           per line, half-up, 2dp, at finalization ONLY) · BR-RAT-004
#           (calendar-day proration of base AND usage) · BR-RAT-005 (tax base =
#           usage + base) · BR-RAT-006 (exemption is ACCOUNT-level) ·
#           BR-RAT-026 (pure tiers) · BR-RAT-032 (tier contiguity) ·
#           BR-RAT-038 (UoM gate) · BR-RAT-041 (amount rules v1) ·
#           BR-RAT-044/045 (plugins behind one interface each) ·
#           BR-BIL-037/039 (the stage contracts; stages 3·4·5 are rating's)
# Golden:   GT-1 · GT-2 · GT-3 · GT-5 · GT-8 (amount rule) · GT-10 · GT-11 —
#           B5 ❄️ FROZEN, finance-signed 2026-08-08 (GT-10's total re-signed
#           2026-08-10 under HUMAN-GUIDE §6, DEF-028)
# Tests:    06-backend/tests/golden/test_gt01..test_gt11 (the frozen contract) ·
#           06-backend/tests/test_us_rat_012_engine.py ·
#           06-backend/tests/test_us_rat_013_totals.py ·
#           06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/billing/rating_seam.py (the published contract this satisfies)
#           · apps/billing (late fee reuses the percent-with-minimum rule)
# ───────────────────────────────────────────────────────
"""THE rating engine. HUMAN-OWNED (CLAUDE.md: 'rating math (B4)').
HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will
do it; we will review it later as human"); row recorded in
12-governance/09-human-review-ledger.md. This file implements finance-signed
law; it never invents it. Changing a signed rule or figure needs a finance
re-sign via HUMAN-GUIDE §6, never an edit here.

PURE function contract (B1): (reads, tariff version, period) -> priced invoice
line candidates. No I/O, no ORM, no clock, no writes — which is what keeps the
B5 golden tests meaningful and is asserted directly (US-RAT-012 TC-8).

WHAT THIS MODULE IS
-------------------
The public entry point, and the ONLY module that knows the stage order. Every
line of arithmetic lives in `apps/rating/pricing/`:

    normalize -> price_usage -> apply_charges -> finalize -> compute_tax -> assemble

- `price_period` runs all six and returns the priced bill.
- `prorate_base_charge` is the one-figure seam GT-3 binds to (B5 freezes the
  prorated base and explicitly withholds the usage half).
- `amount_for` dispatches a charge amount rule (BR-RAT-045); billing's late fee
  calls it so `max($5, 1.5% x overdue portion)` exists once in the codebase.

CONFIRMED rules implemented here, each with the golden case that proves it:
  multiplier BEFORE tiers (B4.4, GT-5) · pure tiers reset per bill with
  thresholds scaling on the prorated period (BR-RAT-002/026, GT-2) · round per
  line half-up 2dp at finalization only (B4.4, GT-1's 8.2979 -> 8.30) ·
  calendar-day proration of the base (B4.3, GT-3) · tax base = usage + base
  (B4.2, GT-10) · account-level exemption (B4.2, GT-11).

⚠ THE PARAGRAPH THAT USED TO SIT HERE WAS TRUE AND STOPPED BEING TRUE, and it
is corrected rather than deleted (hard-won law 1). It read: *"NOT implemented …
TOU · demand · seasonal · capacity · percent-of-service pricing models: the
configuration cannot travel on the seam's TariffConfig and B5 freezes no figure
for any of them."* On **2026-08-16** the seam gained the fields and four of the
five landed as plugins — `time_of_use`, `percent_of_service`, `capacity` and
`demand` — each reproducing a figure the frozen harness already recomputes
(GT-17's 88.60 · 15.80 · 40.00; GT-31's 12.90; GT-20/21's 134.90 and
4,097.00 + 2,002.00). `price_bill` below gained a SECOND PASS for the one model
whose price depends on another service's price.

⚠ `seasonal` WAS LISTED BELOW AS NOT IMPLEMENTED UNTIL 2026-10-01 (*"neither
the day weights nor a machine-verified figure exist on this contract; it
refuses at the registry"*). The PO closed OQ-234 on 2026-09-07 (*"please split
swithch it on"*) and it is now registered: the caller counts the calendar days
per season (`rating.selectors._season_days_between`), the TOU and seasonal
plugins split by them (`pricing/season_split.py`, BR-RAT-034), and WE-18 is
engine-verified as GT-34 (DEF-RAT-8832). No line of this module changed for it.

STILL not implemented, and each is a boundary rather than an omission:
  Minimum bill (BR-RAT-016/028, GT-13 PROPOSED): no threshold input on the seam
  (see stages/apply_charges.py).
  Flat / per-unit tax forms (BR-RAT-036 PROPOSED) and the jurisdiction split
  behind GT-10's single 8.25%: not frozen (see stages/compute_tax.py).
Each is a registry row or a contract field away, and none of them is guessed.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any

from apps.rating import proration
from apps.rating.pricing import registry  # noqa: F401 — imports seal the registries
from apps.rating.pricing import errors
from apps.rating.pricing.contracts import (
    KIND_FEE,
    KIND_USAGE,
    ChargeContext,
    ChargedLines,
    FinalizedLines,
    NormalizedInput,
    PricedBill,
    PricedLines,
    SubscriptionContext,
)
from apps.rating.pricing.stages import (
    apply_charges as apply_charges_stage,
)
from apps.rating.pricing.stages import (
    apply_discounts as apply_discounts_stage,
)
from apps.rating.pricing.stages import (
    assemble as assemble_stage,
)
from apps.rating.pricing.stages import (
    compute_tax as compute_tax_stage,
)
from apps.rating.pricing.stages import (
    finalize as finalize_stage,
)
from apps.rating.pricing.stages import (
    normalize as normalize_stage,
)
from apps.rating.pricing.stages import (
    price_usage as price_usage_stage,
)
from core import money


def price_period(
    *,
    tariff: Any,
    consumption: Any,
    period: Any,
    account: Any,
    taxes: tuple[Any, ...] = (),
    fees: tuple[Any, ...] = (),
) -> PricedBill:
    """Price one service point for one period. PURE: no I/O, no clock, no writes.

    This is the callable `apps.billing.rating_seam.price_period` resolves. The
    argument names and shapes are that seam's published contract; the seam
    adapts the returned `PricedBill` onto its own `RatedBill`.

    The six stages run in the order named in `pricing/stages/__init__.py` and
    nowhere else. A stage never calls another stage; this function is the only
    place the sequence exists.
    """
    normalized = normalize_stage.normalize(
        tariff=tariff,
        consumption=consumption,
        period=period,
        account=account,
        taxes=taxes,
        fees=fees,
    )
    priced = price_usage_stage.price_usage(normalized)
    charged = apply_charges_stage.apply_charges(priced)
    finalized = _with_plan_floor(
        finalize_stage.finalize(charged),
        apply_charges_stage.plan_floor((normalized.config,)),
    )
    # DEF-502 — the discount stage (R6, BR-RAT-071: before taxes). This door
    # prices ONE service point and takes no `discounts` argument, because a
    # discount is an ACCOUNT overlay (BR-RAT-068) that belongs to the whole
    # bill — `price_bill` is where they arrive. `normalize` therefore leaves
    # `NormalizedInput.discounts` empty here and the stage is the identity, so
    # every B5 fixture prices byte-identically; the stage still runs so the
    # sequence is one sequence and not two.
    discounted = apply_discounts_stage.apply_discounts(finalized)
    taxed = compute_tax_stage.compute_tax(discounted)
    return assemble_stage.assemble(taxed)


def _with_plan_floor(finalized: Any, floor: Any) -> Any:
    """BR-RAT-028 mode B — top the bill up to the PLAN's floor, once.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 rating math). CR-052 W1 task 5.

    The floor is the SECOND half of BR-RAT-028's combination rule — *"per-service
    minimums apply first, then the plan floor tops up the total"* — so it is
    applied here, over lines that already carry every per-service adjustment,
    and never inside the per-service pass, which cannot see a total.

    The ARITHMETIC is not here: `apply_charges.plan_floor_line` decides whether
    a top-up is owed and how much, because that is the stage BR-RAT-028 belongs
    to. This function does the three things only the orchestrator can do —
    rounds the resulting line by the ONE rounding law (`finalize_line`, exactly
    as the bill's fee lines are), places it in bill order, and restates the
    taxable subtotal from the same `taxable_base` every other total uses, so
    the tax that follows is charged on the floor (GT-13's *"tax on $25.00"*)
    and not on the subtotal it replaced.

    Identity when no plan floor is stated, which is every plan in the database
    before CR-052 and therefore every ❄️ B5 figure.
    """
    candidate = apply_charges_stage.plan_floor_line(finalized.lines, floor)
    if candidate is None:
        return finalized
    lines = apply_charges_stage.place_before_fees(
        finalized.lines, finalize_stage.finalize_line(candidate)
    )
    return dataclasses.replace(
        finalized, lines=lines, taxable_subtotal=finalize_stage.taxable_base(lines)
    )


class _NoUsage:
    """A zero in the tariff's own billed unit, for a service that bills no usage.

    Structural, like every other input the engine reads: `normalize` asks for
    `.amount` and `.unit` and this answers. It exists so a base-only service can
    satisfy rule 3 without billing importing a rating type or rating importing
    billing's `Quantity` — and it is deliberately a private class with a
    self-describing name, so a zero appearing anywhere it should not is
    traceable to the one place that makes one.
    """

    __slots__ = ("amount", "unit")

    def __init__(self, unit: str) -> None:
        self.amount = Decimal("0")
        self.unit = unit


def _no_usage(tariff: Any) -> _NoUsage:
    return _NoUsage(tariff.billed_unit)


#: The one model whose price depends on another service's price (BR-RAT-015).
#: Named here rather than tested inline so the two places `price_bill` asks the
#: question cannot drift, and so a reader can grep for the whole of the
#: engine's per-model knowledge in one string.
PERCENT_OF_SERVICE = "percent_of_service"


def _is_percent_of_service(tariff: Any) -> bool:
    return getattr(tariff, "model", None) == PERCENT_OF_SERVICE


def _basis_volume(normalized: Any) -> tuple[Decimal, str]:
    """One service's BILLED QUANTITY and its unit — CR-081's basis, exactly.

    ⚠ **THIS FUNCTION WAS `_usage_dollars` UNTIL 2026-09-08 AND IT SUMMED
    MONEY.** Its docstring opened *"Σ of one service's FINALIZED USAGE lines —
    BR-RAT-015's basis, exactly"* and spelled out THREE EXCLUSIONS: the water
    BASE charge was out (*"including it would make the sewer line 40% x 47.50 =
    $19.00 rather than the frozen $15.80"*), TAX was out, and a FEE was out
    structurally, by filtering on line KIND. That is quoted rather than deleted
    (hard-won law 1), because a reader who finds this function and wonders why
    it no longer filters anything deserves the answer: **there is nothing to
    exclude from a metered volume.** A base charge is not in it, a tax is not in
    it, and a fee is not in it — not by a filter, but because none of them is a
    quantity of water.

    The PO re-signed the volume basis on 2026-09-08 under HUMAN-GUIDE §6 (*"C —
    factor 90%, rate $5.00 → $36.00, which is what a real sewer customer
    actually pays"*), superseding BR-RAT-015 ❄️ and reopening BR-RAT-010 the
    other way.

    It reads the NORMALIZED input rather than the finalized lines because a
    quantity is an INPUT to pricing and money is an output: `billed_quantity` is
    already post-multiplier (`apps.metering.quantities` applies the meter's
    multiplier one module upstream) and is the same number that produced the
    water line the customer is reading. The unit travels with it — hard rule 3,
    and here it is the only thing that says whether 7.2 means kgal or ccf.
    """
    usage = normalized.usage
    return usage.billed_quantity, usage.unit


def _usage_dollars(finalized: Any) -> Decimal:
    """Σ of one service's FINALIZED USAGE lines — `CR-130-BRC07`'s charge basis.

    ⚠ **THIS FUNCTION EXISTED UNTIL 2026-09-08 UNDER THIS EXACT NAME AND IS
    RESTORED RATHER THAN REINVENTED.** `_basis_volume` above quotes what it
    used to say, because `CR-081` replaced it; the PO's ruling of 2026-09-22
    asks for both arithmetics as a CHOICE — *"we also need to create 2 option
    5age of charges or % of usage"* — so the two now stand side by side and
    `percent_basis` decides which one a schedule bought. **Nothing about the
    volume basis moves**: ❄️ GT-17 ($36.00), GT-20 ($54.00), GT-25 ($27.00) and
    GT-26 ($27.00) never reach this function at all.

    THE THREE EXCLUSIONS, WHICH ARE THE WHOLE ARITHMETIC
    -----------------------------------------------------
    The filter is on line KIND and that is the entire mechanism:

      * the BASE charge is OUT. `BR-RAT-015`'s own words were *"% of water
        usage-charge dollars (excl. base, excl. tax)"*, and the original
        function recorded what including it would have cost: *"40% x 47.50 =
        $19.00 rather than the frozen $15.80"*.
      * TAX is OUT, for the same clause — and structurally too, because tax is
        computed once over the whole bill and does not exist per service at
        this point.
      * a FEE is OUT, by kind.

    WHICH DOLLARS: THE PRINTED ONES (`OQ-232`, OPEN — non-blocking)
    ----------------------------------------------------------------
    `finalized.lines` are past `stages/finalize.py`, so each amount is the
    half-up 2dp figure the customer reads. The register's own row already
    records that disposition and its reasoning, borrowed rather than invented:
    `10-scripts/03-golden-verify.py` computes GT-17's basis as the sum of the
    ROUNDED tier lines, and B4.2 as re-signed 2026-08-11 settled the identical
    question for the tax base — *"a customer who adds up the four printed lines
    and applies the rate"* must reach the printed figure.

    ⚠ **THE PO'S WORKED FIGURE DOES NOT DISTINGUISH THE TWO READINGS**: water
    $100.00 at 80% is $80.00 whichever dollars you take, and so is every figure
    in the signed corpus. `OQ-232` stays OPEN and the readings part company one
    cent at a time; this docstring is where the choice is stated so no later
    lane has to re-derive it.

    ⚠ **THE LIFECYCLE BLOCK OF `models/percent_of_service.py` SAID `OQ-232` WAS
    *CLOSED BY SUPERSESSION* FROM 2026-09-08 — AND THE REGISTER NEVER AGREED.**
    Its status column read OPEN throughout (`DEF-RAT-6142`). CLAUDE.md's rule
    is that the status column decides, so the question was live even while the
    code called it closed; restoring the charge basis makes it live again in
    substance as well as on paper.
    """
    return sum(
        (line.amount for line in finalized.lines if line.kind == KIND_USAGE),
        Decimal("0.00"),
    )


def price_bill(
    *,
    services: tuple[Any, ...] = (),
    base_only_services: tuple[Any, ...] = (),
    period: Any,
    account: Any,
    taxes: tuple[Any, ...] = (),
    fees: tuple[Any, ...] = (),
    discounts: tuple[Any, ...] = (),
) -> PricedBill:
    """Price a WHOLE BILL — every service on the account's plan, one tax pass.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 rating math). Implements signed law.

    WHY THIS EXISTS. `price_period` prices ONE service point. A plan is a
    BUNDLE (PO ruling 2026-08-11) — a house on electric + water + trash is one
    plan, one bill, three sets of prices — and billing's own stage-1 contract
    has carried `tariffs: tuple[TariffConfig, ...]` since it was written. There
    was no function joining the two, so no multi-service bill could be priced
    at all, while `apps/billing/stages/__init__.py` said stages 3–5 "run as one
    priced pass". That claim was true only of a single-service account
    (DEF-032, hard-won law 1).

    TAX IS COMPUTED ONCE, OVER THE COMBINED BASE. Not per service and summed.
    Three signed sources say so and they agree:

      * **B5 GT-17** (= WE-1, the reference bill, machine-verified by
        10-scripts/03-golden-verify.py): five services' lines are rounded per
        line, summed into ONE taxable base of 221.90, and one tax pass emits
        FOUR lines — one per authority, not one per authority per service.
      * **EP-BIL-01 §7**, tracing the same bill: "stage 3 Σ usage + base +
        capacity = … 221.90 (all taxable) → … stage 5 tax … split by authority".
        Stage 3 runs once across services; stage 5 runs once over their sum.
      * **B4.2 as re-signed 2026-08-11**: the tax base is summed from the
        ROUNDED line amounts, and the stated reason is that a customer adding
        up the printed lines and applying the rate must get the printed tax.
        Per-service tax breaks exactly that: Σ(rate × base_i) rounded per
        service need not equal rate × Σ(base_i), so the document would not foot
        against itself — the failure B4.2's ruling exists to forbid.

    So each service runs stages 3–4 and finalizes (that is where BR-RAT-003's
    per-line rounding happens, once per line, unchanged), and then ONE tax pass
    runs over the union. FEES ride at bill level and are added once, after the
    services: a late fee is a fact about the account, not about its water, and
    charging it per service would multiply it by the number of services.

    `services` is a tuple of `(tariff, consumption)` pairs. A service with no
    consumption is NOT passed there — a missing read is a decision the run has
    already resolved (BR-BIL-015), and that parameter must never see an absence
    it might turn into a zero.

    `base_only_services` is the OTHER absence, and the two are kept apart on
    purpose. BR-BIL-028 (CONFIRMED): on a vacation hold "usage lines bill
    through the day before the hold … base charges and flat services continue
    the full month". So a base-only service carries its base charge and NO usage
    line — not a $0.00 usage line, which would state on the customer's document
    that their meter was read and showed nothing. A missing read is *unknown*;
    a base-only service is *known to have no billable usage*. One parameter for
    both would make the caller's intent unreadable at exactly the point where
    the difference reaches a customer.

    `discounts` (DEF-502, 2026-08-22) are the account's GRANTED discounts —
    enrolment ∩ plan binding, resolved by billing's gather at the service date
    (BR-RAT-069/110) — applied ONCE at the bill level by the apply-discounts
    stage, after the union is finalized and before the tax pass (BR-RAT-071).
    Empty means an undiscounted bill and the stage is the identity; the
    arithmetic itself is `apps/rating/discount_pricing.py`'s, untouched.
    """
    if not services and not base_only_services:
        # A bill with no priced service is not a $0.00 bill; it is an account
        # that should not have reached the engine. Refusing here means the
        # caller's exception list gets it, rather than a customer getting a
        # document with a tax line and nothing else.
        raise errors.RatingInputError(
            "price_bill received no services. A plan that resolves to nothing "
            "priceable is an exception for a human (BR-BIL-015), never a bill."
        )

    priced_services = [(tariff, consumption, False) for tariff, consumption in services]
    priced_services += [(tariff, None, True) for tariff in base_only_services]

    # ── TWO PASSES, because one service can be priced OFF ANOTHER ────────────
    # BR-RAT-015 as SUPERSEDED by CR-081 (PO re-sign 2026-09-08): sewer bills as
    # a percentage of the WATER VOLUME, priced on sewer's own schedule. It read
    # *"a percentage of the WATER usage-charge dollars"* until that date; the
    # two-pass shape is unchanged and the reason for it moved by one word — the
    # BASIS still does not exist until water has been normalized, so a single
    # pass would reach the sewer tariff with nothing to take a percentage of.
    #
    # Pass A prices every OTHER model and records each service's billed quantity
    # and unit. Pass B prices the percent-of-service tariffs against that record.
    # A percent tariff whose basis service is not on this bill REFUSES BY NAME
    # (errors.BasisUnavailable) rather than pricing zero — CLAUDE.md's seam rule.
    #
    # A percent tariff may not itself be a basis: `basis_volumes` and
    # `basis_dollars` are written in pass A only, so sewer-of-sewer resolves to
    # "not on this bill" and refuses. That is deliberate — chained percentages
    # have no signed rule and no frozen figure, and nothing here invents an
    # evaluation order for them. `CR-130-BRC07` widens WHAT a percentage may be
    # taken of and does not touch that: a percentage OF a percentage is still
    # refused, on both bases.
    #
    # THE PRICING ORDER IS NOT THE BILL'S ORDER. Lines come out in the order the
    # CALLER listed the services, so a document does not silently reorder itself
    # the day a plan gains a sewer line. `finalized_by_index` is what keeps the
    # two apart.
    order = list(enumerate(priced_services))
    pass_a = [entry for entry in order if not _is_percent_of_service(entry[1][0])]
    pass_b = [entry for entry in order if _is_percent_of_service(entry[1][0])]
    basis_volumes: dict[str, tuple[Decimal, str]] = {}
    # CR-130-BRC07 — THE SECOND RECORD, and it is a SECOND one rather than a
    # widening of the first on purpose. A schedule reads ONE of the two, named
    # by `percent_basis`, and the plugin refuses when the one it named is
    # absent. Two dicts make "this service supplied a volume but no money" a
    # state the code can be in; one dict of pairs would have tempted a caller
    # into reaching for whichever half happened to be there.
    basis_dollars: dict[str, Decimal] = {}
    finalized_by_index: dict[int, Any] = {}

    for index, (tariff, consumption, base_only) in pass_a + pass_b:
        # CR-081 — the BASIS service's volume and unit, or (None, None) when
        # that service is not on this bill. Resolved before `normalize` so the
        # two fields cross the seam together and neither can arrive alone: a
        # quantity with no unit is refused by hard rule 3, and a unit with no
        # quantity would name a measurement nobody made.
        basis_code = getattr(tariff, "basis_service", None) or ""
        basis = basis_volumes.get(basis_code, (None, None))
        # CR-130-BRC07 — the charge basis's number, resolved in the same breath
        # and from the same record, so neither can be filled from a different
        # service than the other.
        basis_money = basis_dollars.get(basis_code)
        normalized = normalize_stage.normalize(
            tariff=tariff,
            # A base-only service still has to satisfy `normalize`'s contract,
            # which refuses a quantity without a unit (rule 3). It is given a
            # zero in the tariff's OWN billed unit and its usage lines are then
            # dropped below — the zero never reaches a line, a total or a
            # document. Building the NormalizedInput by hand instead would put
            # a second constructor for it in the codebase, which is how the two
            # would eventually disagree about the period or the exemption.
            consumption=(_no_usage(tariff) if base_only else consumption),
            period=period,
            account=account,
            # Taxes and fees are deliberately WITHHELD from the per-service
            # pass. Passing them would run a tax pass per service (the rule
            # above forbids it) and would repeat every fee once per service.
            taxes=(),
            fees=(),
            # CR-081's basis, and it is None on every model but one. On a
            # percent-of-service tariff this is the BASIS service's billed
            # QUANTITY and the unit it was metered in — 8 kgal of water, of
            # which 90% (7.2 kgal) is billed as sewer at sewer's own rate.
            # It was the Σ of that service's FINALIZED usage DOLLARS until
            # 2026-09-08, and OQ-232 (which of the two roundings those dollars
            # were) is closed by supersession: there are no basis dollars.
            basis_quantity=basis[0],
            basis_unit=basis[1],
            # CR-130-BRC07's charge basis: the SAME service's usage-charge
            # dollars. `percent_basis` on the tariff decides which of the two
            # the plugin reads; passing both costs nothing and lets the plugin
            # refuse BY NAME for the basis the schedule actually bought,
            # instead of refusing for the one it did not.
            basis_amount=basis_money,
        )
        priced = price_usage_stage.price_usage(normalized)
        if base_only and not _is_percent_of_service(tariff):
            # BR-BIL-028: the base charge continues, the usage line does not.
            #
            # ⚠ `not _is_percent_of_service` added 2026-08-16 for DEF-161, and
            # it changes NO frozen figure — GT-17/20/25/26 price sewer from a
            # MEASURED water service and never reach this branch.
            #
            # BR-BIL-028's clause is about a METER: *"usage lines bill through
            # the day before the hold"*, i.e. a register stopped being read. A
            # percent-of-service line is not read off a meter at all; it is
            # `percent x the basis service's printed usage dollars`
            # (BR-RAT-015), and dropping it here billed the customer nothing for
            # sewer while the water it is a percentage of billed in full.
            #
            # THE VACATION HOLD IS STILL SAFE, and by the engine's own
            # construction rather than by this line: a base-only WATER service
            # records NEITHER number, so the sewer tariff reaches pass B with
            # `basis_quantity=None` AND `basis_amount=None` and REFUSES BY NAME
            # (BasisUnavailable, BR-RAT-066) instead of pricing a percentage of
            # nothing as $0.00. `CR-130-BRC07` leaves that untouched and makes
            # it symmetric: the hold silences both bases, not one of them.
            priced = dataclasses.replace(priced, usage_lines=())
        # OQ-1166 (b), PO ruling 2026-08-30 — *"when units are vacant - at that
        # time, we are only charging base rates"*. The flag exists HERE and
        # nowhere below, so it is handed down rather than re-derived: a
        # base-only service and a metered service that consumed nothing both
        # reach `apply_charges` with no usage line and must not be topped up
        # the same way. Mode B (the plan floor, applied once over the finished
        # union in `_with_plan_floor`) is deliberately NOT given this flag —
        # DEF-2822.
        charged = apply_charges_stage.apply_charges(priced, base_only=base_only)
        finalized = finalize_stage.finalize(charged)
        finalized_by_index[index] = finalized
        if not _is_percent_of_service(tariff) and not base_only:
            # `not base_only` is the difference between "$0.00 of water" and
            # "water's usage was not billed at all", and BR-RAT-015 needs them
            # apart. A metered zero IS a basis — a customer who used no water
            # owes no sewer, and 40% x 0.00 = 0.00 is the right answer. A
            # BASE-ONLY service (BR-BIL-028's vacation hold: "usage lines bill
            # through the day before the hold … base charges continue") has no
            # usage figure at all, so recording 0.00 for it would let a sewer
            # line quietly become free while the water base kept billing.
            # Under CR-081 the recorded figure is a VOLUME rather than money and
            # the distinction is identical: 0 kgal metered is a real basis and
            # bills 0 kgal of sewer; a service that was never metered is not.
            # ── 2026-09-30 · TWO METERS ON THE BASIS SERVICE ARE ONE BASIS ────
            # PO ruling 2026-09-30: two water meters bill as two lines, each on
            # its own ladder — so ONE service can now reach this loop twice.
            # Assigning here kept only the LAST meter, and sewer (a percentage
            # of water) would have been priced off half the water. The basis
            # is the service's, so it is SUMMED across its configs. Two meters
            # stating different units cannot be summed and refuse by name
            # (hard rule 3) rather than adding kgal to ccf. One config per
            # service — every bill before the ruling — is byte-identical.
            service_code = normalized.subscription.service
            volume, volume_unit = _basis_volume(normalized)
            if service_code in basis_volumes:
                prior_volume, prior_unit = basis_volumes[service_code]
                if prior_unit != volume_unit:
                    raise errors.RatingInputError(
                        f"{service_code}: two meters state different units "
                        f"({prior_unit!r}, {volume_unit!r}), so they cannot be "
                        "added into one basis. Nothing is converted (rule 3)."
                    )
                volume = prior_volume + volume
            basis_volumes[service_code] = (volume, volume_unit)
            # CR-130-BRC07 — the same service, the same gate, the other number.
            # It is recorded from `finalized` and not from `priced` because the
            # charge basis is the PRINTED dollars (`OQ-232`, OPEN, with that
            # disposition already recorded): `finalize` has rounded each line
            # half-up to 2dp by this point, which is the figure the customer
            # adds up. The gate above is unchanged and carries the same
            # meaning for money as it does for volume: a metered ZERO is a real
            # basis and bills $0.00 of sewer, while a base-only service was
            # never metered at all and supplies nothing.
            basis_dollars[service_code] = basis_dollars.get(
                service_code, Decimal("0")
            ) + _usage_dollars(finalized)

    finalized_per_service = [finalized_by_index[index] for index, _ in order]

    # The bill-level pass. It reuses the FIRST service's normalized input for
    # the account facts every stage downstream reads — currency and the
    # account-level exemption (B4.2/BR-RAT-006: exemption applies regardless of
    # service, so any service's copy carries the same answer) — and replaces
    # the taxes with the BILL's, which is where they live.
    first = finalized_per_service[0]
    bill_normalized = dataclasses.replace(
        first.normalized,
        taxes=normalize_stage.tax_specs(taxes),
        fees=(),
        # DEF-502 — the account's granted discounts join the BILL-level input,
        # exactly where the bill's taxes do and for the same reason: a discount
        # is an ACCOUNT overlay (BR-RAT-068), never a per-service fact, so the
        # per-service passes above were given none and the stage runs ONCE over
        # the union. The tuple arrives from billing's gather (enrolment ∩ plan
        # binding, resolved at the service date — BR-RAT-069/110) and crosses
        # here untouched; `stages/apply_discounts.py` is what reads it.
        discounts=tuple(discounts),
    )
    service_lines = tuple(line for f in finalized_per_service for line in f.lines)
    fee_lines = tuple(
        finalize_stage.finalize_line(candidate)
        for candidate in normalize_stage.fee_candidates(fees)
    )
    lines = service_lines + fee_lines
    # BR-RAT-028 mode B (CR-052 W1) — the plan's floor over the WHOLE bill,
    # resolved from the tariffs' own normalized configs so the engine reads one
    # figure rather than being handed a second channel for it. `plan_floor`
    # REFUSES a bill whose tariffs state two different floors; it answers None
    # for every plan in the database before CR-052, and the two lines below are
    # then byte-identical to what they replaced.
    floor = apply_charges_stage.plan_floor(
        finalized.normalized.config for finalized in finalized_per_service
    )
    combined = _with_plan_floor(
        FinalizedLines(
            # `source` is threaded from the first service so `.normalized`
            # resolves to the bill-level input above. Nothing downstream reads
            # its lines — `combined.lines` is what the later stages use — and
            # rebuilding the whole chain would fabricate a ChargedLines that
            # never ran.
            source=dataclasses.replace(
                first.source,
                source=dataclasses.replace(first.source.source, source=bill_normalized),
            ),
            lines=lines,
            # Σ of the FINALIZED taxable amounts across every service (B4.2).
            # The per-service subtotals are deliberately not summed: this is the
            # same function stage 4's own finalize uses, applied to the union,
            # so there is one definition of "the tax base" and not two.
            taxable_subtotal=finalize_stage.taxable_base(lines),
        ),
        floor,
    )
    # DEF-502 — R6, between apply-charges and compute-tax (BR-RAT-071; B4 ❄ is
    # SILENT on discounts — grepped, recorded in the decision log 2026-08-22).
    # Identity when `discounts` is empty, which is every bill this product had
    # ever priced and every frozen fixture.
    discounted = apply_discounts_stage.apply_discounts(combined)
    taxed = compute_tax_stage.compute_tax(discounted)
    return assemble_stage.assemble(taxed)


def price_fee_bill(
    *,
    account: Any,
    taxes: tuple[Any, ...] = (),
    fees: tuple[Any, ...],
) -> PricedBill:
    """Price a FEE BILL — charge-code lines only, and ONE tax pass over them.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 rating math). Implements the ❄️ B4.2
    finance RE-SIGN of 2026-09-30 and invents nothing beyond it.

    ── THE RULING ────────────────────────────────────────────────────────────
    B4.2 (❄️ 2026-08-08) says *"tax base = usage + base charge only (fees and
    late charges are NOT taxed)"*, and `finalize.taxable_base` enforces it by
    KIND, so a fee can never reach a percent base on an ordinary bill. That is
    unchanged here. What changed is a NEW SHAPE of bill the frozen rule was not
    written about: a fee bill (`bill_type='fee'`, DEF-708) has no services, so
    it never entered this engine at all and a code the tenant marked
    *taxable* was charged with no tax (`OQ-812`).

    PO 2026-09-30, asked *"Re-sign the frozen tax rule so a Fee bill is taxed
    when its charge code is marked taxable?"*, verbatim: *"Yes, re-sign."*
    Worked figure shown: **RECON $75.00 marked taxable at 8.25% → $81.19**
    (`75.00 × 8.25% = 6.1875 → 6.19`). The re-sign is recorded as a dated ❄️
    ADDENDUM to `04-docs/02-decisions/04-money-math-rules.md`, never as an
    inline edit of the signed line.

    ── WHAT THIS FUNCTION DOES, AND WHY IT IS NOT A SECOND TAX CALCULATION ────
    The SAME stages every other bill uses: each fee line is finalized once
    (`finalize_line`, BR-RAT-003 — half-up 2dp, the one rounding event), then
    `compute_tax` runs ONCE (BR-RAT-062 / GT-17 ❄️: one tax pass per bill, one
    line per authority), then `assemble`. The only new fact is the BASE: on a
    fee bill it is **Σ of the finalized fee lines the caller flagged
    taxable** — and the caller flags a line taxable only from the tenant's own
    `charges.taxable_default` (billing's `fee_bill.charge_code_line`). It is
    summed from ROUNDED line amounts, as B4.2's 2026-08-11 re-sign requires, so
    a customer adding up the printed line and applying the rate gets the
    printed tax.

    ── WHAT IT DELIBERATELY DOES NOT DO ──────────────────────────────────────
    * **Only PERCENT rules are priced.** A FLAT-per-bill rule (the $0.85 PUC
      fee) and a PER-UNIT rule are dropped here. The re-sign covered a percent
      of the fee and nothing else: a flat amount is a charge per UTILITY bill
      and is not "the fee being taxed", and a per-unit rule is a rate on a
      metered quantity a fee bill does not have. Dropping them under-charges
      rather than over-charges, which is this repo's stated fail-safe
      direction; the choice is recorded in the decision log of 2026-09-30.
    * **Exemption is account-level and wins** (B4.2 / BR-RAT-006): an exempt
      account gets no tax lines, exactly as `compute_tax` does for every bill.
    * **WHICH taxes reach the bill is not decided here** (DEF-273). The caller
      resolves the account's plan taxes with NO service list, so a tax scoped
      to a service fails closed and never arrives.
    * **An ordinary bill is untouched.** `price_bill` and `price_period` do not
      call this, and a fee riding an ordinary bill is still kept out of the
      base by KIND.

    PURE: no I/O, no clock, no writes — like every function in this file.
    """
    subscription = SubscriptionContext(
        service="",
        currency=account.currency,
        tax_exempt=bool(getattr(account, "tax_exempt", False)),
    )
    percent_only = tuple(
        rule
        for rule in taxes
        if getattr(rule, "flat_amount", None) is None
        and getattr(rule, "per_unit_amount", None) is None
    )
    normalized = NormalizedInput(
        subscription=subscription,
        # A fee bill has no usage, no pricing model and no period shape — the
        # stages below read none of the three (compute_tax reads the
        # subscription, the taxes and the lines; assemble reads the currency).
        # None rather than a fabricated object, so any stage that DID start
        # reading one would fail loudly instead of pricing from invented data.
        usage=None,
        config=None,
        period=None,
        taxes=normalize_stage.tax_specs(percent_only),
        fees=(),
    )
    candidates = normalize_stage.fee_candidates(fees)
    charged = ChargedLines(
        source=PricedLines(source=normalized, usage_lines=(), base_lines=()),
        lines=candidates,
    )
    lines = tuple(finalize_stage.finalize_line(candidate) for candidate in candidates)
    finalized = FinalizedLines(
        source=charged,
        lines=lines,
        # THE RE-SIGNED BASE (B4.2 ADDENDUM 2026-09-30): the finalized fee lines
        # flagged taxable. Not `finalize.taxable_base`, which filters by KIND
        # and would — correctly, for every other bill — return 0.00 here.
        taxable_subtotal=sum(
            (line.amount for line in lines if line.taxable and line.kind == KIND_FEE),
            Decimal("0.00"),
        ),
    )
    taxed = compute_tax_stage.compute_tax(finalized)
    return assemble_stage.assemble(taxed)


def prorate_base_charge(*, base_charge: Decimal, period: Any) -> Decimal:
    """The base charge for a partial period — B4.3 CONFIRMED: CALENDAR days.

    B5 GT-3 freezes exactly one figure here (15/30 x 30.50 = 15.25) and states
    in its own words that the rest is "pending usage figures". This seam returns
    that one figure: the prorated base as it would appear on the invoice line,
    finalized half-up to 2dp exactly once (BR-RAT-003).

    `price_period` does NOT call this function — both compute from
    `proration.prorated_amount` and each finalizes once, so no amount is ever
    rounded twice.
    """
    factor = proration.proration_factor(
        cycle_days=period.cycle_days, service_days=period.service_days
    )
    return money.finalize(proration.prorated_amount(base_charge, factor))


def amount_for(
    *,
    rule: str,
    amount: Decimal | None = None,
    percent: Decimal | None = None,
    basis: Decimal | None = None,
    minimum: Decimal | None = None,
) -> Decimal:
    """One charge amount rule, resolved through the registry (BR-RAT-045).

    Returns NUMERIC(18,6) UNROUNDED — the caller finalizes once (BR-RAT-003).
    An unregistered rule REFUSES; it never returns zero (US-RAT-015 TC-5).

    GT-8's `max(5, 0.015 x 542.10)` is `rule="percent_min"`. Billing's late-fee
    assessment owns the grace clock (BR-BIL-001/008) and calls this for the
    amount, so that arithmetic exists in exactly one place.
    """
    plugin = registry.AMOUNT_RULES.resolve(rule)
    return plugin(ChargeContext(amount=amount, percent=percent, basis=basis, minimum=minimum))


def rate(reads: Any, tariff_version: Any, period: Any) -> PricedBill:  # pragma: no cover
    """The pre-B5 name for this entry point. NOT implemented, deliberately.

    `rate(reads, tariff_version, period)` was this module's stub signature
    before the golden fixtures existed. It takes ORM-shaped arguments — a
    queryset of reads and a `tariff_versions` row — that the pure contract
    above deliberately does not: resolving a tariff version from the database is
    the bill run's stage 1, not the engine's (BR-BIL-037). It stays here, named
    and refusing, so a caller written against the old signature fails loudly
    instead of finding nothing.
    """
    raise NotImplementedError(
        "apps.rating.engine.rate() is superseded by price_period(...) — the pure "
        "contract the B5 golden fixtures bind to (apps/billing/rating_seam.py). "
        "Resolve the tariff version and the reads in the bill run's stage 1/2 and "
        "call price_period with the resulting values."
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10;
#         co-packets US-RAT-013@70a0044 · US-RAT-015@70a0044, same four sources)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-16 by the pricing-engines lane: `price_bill` gained a SECOND PASS so a service priced OFF another service (BR-RAT-015 sewer-of-water) can see its basis, and `_usage_dollars` states the three exclusions that basis is · AMENDED 2026-09-08 by the CR-081 lane: `_usage_dollars` became `_basis_volume` and the basis crossing the seam is the water VOLUME and its UNIT rather than the water money — BR-RAT-015 ❄️ SUPERSEDED and BR-RAT-010 reopened, under the PO's HUMAN-GUIDE §6 re-sign of six frozen figures · AMENDED 2026-08-22 by the W9a DEF-502 lane: the APPLY-DISCOUNTS stage (R6, BR-RAT-071) runs between finalize and compute-tax in both doors — `price_bill` gained `discounts=()` (the account's granted discounts, gathered by billing) and `price_period` runs the stage as the identity; no frozen figure moves because every B5 fixture passes no discounts
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure service) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → 7 PASS / 4 xfail (GT-4·GT-9 metering-owned, GT-6 billing corrections, GT-7 payments — none of them this lane's to publish)✔ · pytest tests -m "not golden and not isolation" → 1052 baseline + this lane's new tests, 0 failures✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: PARTIAL story delivery, stated rather than implied — AND THE 2026-08-16 LANE CLOSED THREE OF THE GAPS THIS LINE NAMED. US-RAT-012: TC-1/2/3/4/7/8/9 shipped 2026-08-10 and TC-5 (TOU) + TC-6 (sewer %-of-water) shipped 2026-08-16; TC-10 (cross-tenant isolation) is not shipped because the engine takes no tenant argument and touches no queryset (isolation is the caller's RLS boundary). US-RAT-013: TC-1/2/7 ship; TC-3/TC-4 (minimum bill) have no threshold input on the seam and GT-13 is PROPOSED; TC-5 (plan tax overrides), TC-6 (flat/per-unit taxes), TC-8 (exemption expiry) need fields the seam does not carry; TC-9 isolation as above. US-RAT-015: TC-1/3/5/6/7/8 shipped 2026-08-10 and TC-2 (capacity) shipped 2026-08-16; TC-9 (isolation) does not. TC-4's "stage names no model" is shipped as a test over stages/price_usage.py. Every gap is a missing INPUT or an unfrozen figure — not a rule this lane declined to implement.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
