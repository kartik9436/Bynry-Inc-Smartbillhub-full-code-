# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (the engine's front door
#           onto the BR-BIL-037 pipeline)
#           Screens: — (a refusal here surfaces in S31.2's Reads tab)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-001 (meter multiplier applies BEFORE tier evaluation — B4.4,
#           and this stage is where it is applied) · BR-RAT-038 (UoM gate: the
#           read unit must BE the billed unit; no silent conversion) ·
#           BR-RAT-004 (the calendar-day proration factor is derived here, once)
#           · BR-BIL-037 (one output contract) · BR-BIL-039 (pure)
# Golden:   GT-5 (raw 274 x10 -> 2,740 before tiers) · GT-2 · GT-1 — B5 ❄️ FROZEN
# Tests:    06-backend/tests/test_us_rat_012_engine.py (unit gate, UoM gate,
#           multiplier order)
# Impacts:  apps/rating/pricing/stages/price_usage.py (its sole consumer)
# ───────────────────────────────────────────────────────
"""Stage 0 — gather the inputs into one contract, and gate them.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

This is the engine's front door. It does three things and no arithmetic at all:

1. **Unit discipline** (CLAUDE.md hard rule 3). A consumption with no unit is
   rejected, never assumed. US-RAT-012 TC-9.
2. **The UoM gate** (BR-RAT-038, PO R6 / OQ-004 closure). The read unit must
   equal the tariff's billed unit. Conversion by a per-service factor happens at
   rating INPUT, upstream; the engine holds no factor and performs none, so a
   mismatch is the blocked read the rule describes — never a silent conversion.
   US-RAT-012 TC-7.
3. **The multiplier trip-wire** (PO ruling 2026-08-11, decision 4). This stage
   USED to multiply. It no longer does: metering owns the meter multiplier,
   because the multiplier belongs to the METER and not to the tariff — two
   meters on one tariff have different multipliers, so a tariff-carried
   multiplier could only ever be right by coincidence. B4.4 is untouched: the
   multiplier still precedes tier evaluation, one module upstream. A tariff
   that still carries one is REFUSED, loudly, because the caller who set it
   believes something about this engine that is no longer true.

It also derives the B4.3 calendar-day proration factor once, so that base
proration and tier-threshold scaling can never be driven by two numbers that
disagree.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.rating import proration
from core.units import same_unit
from apps.rating.pricing import errors
from apps.rating.pricing.contracts import (
    KIND_FEE,
    CapacitySpec,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    NormalizedInput,
    PeakDemand,
    PeriodShape,
    SeasonLadder,
    SeasonMeasured,
    SeasonShare,
    SubscriptionContext,
    TaxRuleSpec,
    TierSpec,
    TouWindowSpec,
    WindowUsage,
)


def _quantity_of(consumption: Any) -> tuple[Decimal, str]:
    """The amount and its unit, refusing anything that lacks one."""
    amount = getattr(consumption, "amount", None)
    unit = getattr(consumption, "unit", None)
    if amount is None:
        raise errors.RatingInputError("consumption has no amount; nothing to price.")
    if not unit:
        raise errors.MissingUnit(
            "consumption arrived without an explicit unit. CLAUDE.md hard rule 3: "
            "a quantity always carries its unit and the engine never assumes one."
        )
    return amount, unit


def _gate_uom(read_unit: str, billed_unit: str, service: str) -> None:
    # DEF-RAT-10220 — "the same unit" is `core.units.same_unit` (case and
    # white space only, never a conversion), the SAME rule billing's
    # `bills_installed_capacity` uses, so a clerk's `KW` and a capacity's `kW`
    # are one unit at both points and `kWh` vs `MWh` still refuses here.
    if not same_unit(read_unit, billed_unit):
        raise errors.UomMismatch(
            f"service {service!r}: read unit {read_unit!r} is not the billed unit "
            f"{billed_unit!r} and the engine holds no conversion factor. BR-RAT-038 "
            "(PO R6): convert at rating input with a defined per-service factor, or "
            "block the read — never convert silently."
        )


def _window_usage(consumption: Any, billed_unit: str, service: str) -> tuple[WindowUsage, ...]:
    """The seam's pre-split TOU quantities, gated one window at a time.

    BR-RAT-021: reads arrive PRE-SPLIT per window. Each window's quantity is
    gated for its own unit — hard rule 3 applies per measurement, and three
    windows of one meter are three measurements.
    """
    windows = getattr(consumption, "windows", ()) or ()
    out: list[WindowUsage] = []
    for window in windows:
        quantity = getattr(window, "quantity", None)
        amount, unit = _quantity_of(quantity)
        _gate_uom(unit, billed_unit, service)
        out.append(WindowUsage(channel=window.channel, quantity=amount, unit=unit))
    return tuple(out)


def _peak_demand(consumption: Any) -> PeakDemand | None:
    """The seam's peak-demand measurement, or None when nothing measured one.

    NOT gated against the tariff's billed unit, deliberately: the demand read is
    in kW and the energy beside it is in kWh, so gating it against the ENERGY's
    unit would refuse every demand bill there is. It still must carry a unit
    (hard rule 3) — the gate that applies to it is "has one", not "matches".
    """
    demand = getattr(consumption, "demand", None)
    if demand is None:
        return None
    amount, unit = _quantity_of(demand)
    return PeakDemand(quantity=amount, unit=unit)


def _threshold(value: Any) -> Decimal | None:
    """A BR-RAT-028 minimum as a Decimal, keeping ABSENT and ZERO apart.

    `None` in, `None` out: a tariff that states no minimum has none, and a
    stage that receives `Decimal("0")` for it would apply a floor of zero on
    every bill — arithmetically harmless today and indistinguishable from a
    stated one the moment anybody reads it back. That is DEF-154's shape, and
    it is why this is a function rather than `value or None`, which would
    also swallow a genuine stated `0`.
    """
    if value is None:
        return None
    return Decimal(str(value))


def normalize(
    *,
    tariff: Any,
    consumption: Any,
    period: Any,
    account: Any,
    taxes: tuple[Any, ...] = (),
    fees: tuple[Any, ...] = (),
    basis_quantity: Any = None,
    basis_unit: str | None = None,
    basis_amount: Any = None,
) -> NormalizedInput:
    """Seam inputs -> the one contract every priced stage runs on.

    Inputs are read STRUCTURALLY (by attribute), not by importing billing's
    dataclasses: rating is called BY billing and must not depend on it. The
    field names are the seam's published contract
    (apps/billing/rating_seam.py), and the adapter there is what binds them.
    """
    billed_unit = tariff.billed_unit
    service = tariff.service
    raw_amount, read_unit = _quantity_of(consumption)
    _gate_uom(read_unit, billed_unit, service)

    # PO ruling 2026-08-11 (decision 4): METERING applies the meter multiplier;
    # the engine never does. B4.4's rule is unchanged — the multiplier still
    # lands before any tier sees the quantity — but it lands one module
    # upstream, in `apps.metering.quantities`, where the multiplier is a
    # property of the METER (`assets.Asset.multiplier`) rather than of the
    # tariff. The consumption reaching this stage is already a real quantity in
    # a real unit.
    #
    # THIS IS A TRIP-WIRE, NOT A VALIDATION. A caller that sets `multiplier`
    # believes the engine will apply it. It will not. If that caller ALSO went
    # through metering, the quantity is already multiplied and pricing it again
    # is the one failure mode this ruling exists to make impossible: a dial
    # delta of 1,247 at x40 is 49,880 kWh and about $4,853; multiplied twice it
    # is 1,995,200 kWh and about $194,113, on a bill that looks structurally
    # perfect. So a multiplier here is refused LOUDLY rather than ignored
    # quietly — ignoring it would price the right number for the wrong reason
    # and leave the caller's belief intact for the next change to act on.
    supplied_multiplier = getattr(tariff, "multiplier", None)
    if supplied_multiplier is not None and Decimal(supplied_multiplier) != Decimal(1):
        raise errors.TariffConfigError(
            f"tariff.multiplier={supplied_multiplier} was supplied to the pricing engine, "
            "which does NOT apply meter multipliers (PO ruling 2026-08-11). Consumption "
            "must arrive post-multiplier from apps.metering.quantities, whose multiplier "
            "is the METER's (assets.Asset.multiplier) — a tariff cannot carry one, since "
            "two meters on the same tariff have different multipliers. Applying it here "
            "as well would double-multiply the bill. B4.4 is unchanged: the multiplier "
            "still precedes tier evaluation, one module upstream."
        )
    usage = MeasuredUsage(
        # Already post-multiplier (see above). `raw_quantity` and `multiplier`
        # stay on the contract so a caller can still SHOW the derivation on a
        # bill; they are carried, never re-applied.
        billed_quantity=raw_amount,
        unit=read_unit,
        raw_quantity=raw_amount,
        multiplier=Decimal(1),
        # The other two things ONE service point can measure in one period
        # (2026-08-16): a TOU register per window (BR-RAT-021) and a max-demand
        # register (BR-RAT-014). Absent on every model that bills one total, and
        # ABSENT MEANS UNKNOWN — the plugins refuse rather than price zero.
        windows=_window_usage(consumption, billed_unit, service),
        demand=_peak_demand(consumption),
        # 🔒 DEF-RAT-8849 (PO 2026-10-01, *"yes build the season-change day
        # reading"*) — per register, what each season of the period MEASURED,
        # cut by the CALLER at a read dated on the season-change day. Empty on
        # every other bill, which then splits by calendar days (BR-RAT-034).
        season_measured=tuple(
            SeasonMeasured(
                channel=getattr(part, "channel", None),
                quantities=tuple(Decimal(str(q)) for q in part.quantities),
            )
            for part in getattr(consumption, "season_parts", ()) or ()
        ),
    )

    shape = PeriodShape(
        cycle_days=period.cycle_days,
        service_days=period.service_days,
        factor=proration.proration_factor(
            cycle_days=period.cycle_days, service_days=period.service_days
        ),
    )

    # Every field below is read with `getattr(..., default)` for the reason the
    # module docstring gives for reading structurally at all: rating is called
    # BY billing and must not import its dataclasses. A caller whose seam
    # predates a field gets the field's absence — which each plugin turns into a
    # named refusal — rather than an AttributeError in the middle of a run.
    capacity_spec = None
    capacity_source = getattr(tariff, "capacity", None)
    if capacity_source is not None:
        capacity_spec = CapacitySpec(
            unit_label=capacity_source.unit_label,
            rate_per_unit=capacity_source.rate_per_unit,
        )
    config = ModelConfig(
        model=tariff.model,
        billed_unit=billed_unit,
        unit_price=tariff.unit_price,
        tiers=tuple(TierSpec(upper=t.upper, unit_price=t.unit_price) for t in tariff.tiers),
        base_charge=tariff.base_charge,
        windows=tuple(
            TouWindowSpec(
                label=window.label,
                unit_price=window.unit_price,
                channel=getattr(window, "channel", None),
                season=getattr(window, "season", None),
                day_type=getattr(window, "day_type", "weekday"),
            )
            for window in getattr(tariff, "windows", ()) or ()
        ),
        # The season IN FORCE on the service date, resolved by the caller for
        # the same reason the tariff VERSION is (BR-RAT-007): it is a lookup
        # against stored date ranges, and a pure engine holds no calendar.
        season=getattr(tariff, "season", None),
        # BR-RAT-034 · THE SEASON-CROSSING SPLIT (OQ-234 CLOSED 2026-09-07,
        # built 2026-10-01). The calendar days of this period in each season,
        # COUNTED BY THE CALLER — `rating.selectors._season_days_between`, the
        # sibling of the one-season lookup above — because this engine holds no
        # calendar. Empty on every caller that predates the field and on every
        # period inside one season, which then prices exactly as before.
        season_days=tuple(
            SeasonShare(season=getattr(share, "season", None), days=int(share.days))
            for share in getattr(tariff, "season_days", ()) or ()
        ),
        # `seasonal` — each season's own ladder (BR-RAT-034).
        season_tiers=tuple(
            SeasonLadder(
                season=ladder.season,
                tiers=tuple(TierSpec(upper=t.upper, unit_price=t.unit_price) for t in ladder.tiers),
            )
            for ladder in getattr(tariff, "season_tiers", ()) or ()
        ),
        capacity=capacity_spec,
        energy_rate=getattr(tariff, "energy_rate_per_kwh", None),
        demand_rate=getattr(tariff, "demand_rate_per_kw", None),
        ratchet_enabled=bool(getattr(tariff, "ratchet_enabled", False)),
        pf_penalty_enabled=bool(getattr(tariff, "pf_penalty_enabled", False)),
        percent=getattr(tariff, "percent", None),
        basis_service=getattr(tariff, "basis_service", None),
        # CR-063 — the NAME of the connection size this line is for, when the
        # service bills one line per size. It names the line and prices nothing;
        # `getattr` for the same late-binding reason as every field around it.
        size_label=getattr(tariff, "size_label", None),
        per_size_line=bool(getattr(tariff, "per_size_line", False)),
        # DEF-BIL-8743 — a summed capacity line prorates on a part period.
        installed_sum_line=bool(getattr(tariff, "installed_sum_line", False)),
        # 2026-09-30 — the METER this config prices, when a metered service
        # carries two (each its own connection). Identity only; see
        # `ModelConfig.asset_id`.
        asset_id=getattr(tariff, "asset_id", None),
        # 🔒 DEF-RAT-9327 — the base's charge CODE, a label (`BASE-W`) that
        # `billing.gather` has always sent and this stage dropped. Identity
        # only: what a named-codes discount selects the base line by.
        base_charge_code=getattr(tariff, "base_charge_code", None),
        # 🔒 `DEF-CUS-9050` — an empty unit's base on its owner's bill: the
        # unit's name and the share of the period it stood empty.
        unit_label=getattr(tariff, "covers_unit_label", None),
        occupancy_factor=getattr(tariff, "occupancy_factor", None),
        # NOT tariff configuration — the other service's billed QUANTITY and
        # its UNIT, which exist only once that service has been priced.
        # `price_bill` supplies both on a second pass; everywhere else they are
        # None and the plugin refuses by name rather than pricing a sewer line
        # at zero (BR-RAT-015 as superseded by CR-081).
        #
        # ⚠ THIS WAS ONE ARGUMENT, `basis_amount`, IN DOLLARS, UNTIL 2026-09-08,
        # AND THE RENAME WAS DELIBERATE (`CR-081`): a caller left unconverted
        # failed HERE with a TypeError instead of handing the plugin money
        # where a volume belongs.
        #
        # ⚠ **THAT TRIP-WIRE IS GONE AS OF 2026-09-22, AND SAYING SO IS THE
        # POINT (hard-won law 1 — a comment claiming a guarantee is not the
        # guarantee).** `CR-130-BRC07` puts `basis_amount` back as a THIRD
        # keyword, so a caller passing it no longer raises. What replaces the
        # TypeError is `percent_basis`, which every caller must now carry: a
        # tariff that says `'charge'` and supplies no amount refuses BY NAME,
        # and so does one that says `'usage'` and supplies no quantity. The
        # guarantee moved from the signature into the plugin, and
        # `tests/test_cr130_percent_basis.py` is what holds it there.
        basis_quantity=basis_quantity,
        basis_unit=basis_unit,
        # CR-130-BRC07 — the OTHER half of the same seam: on the `'charge'`
        # basis the number that crosses is the basis service's usage-charge
        # DOLLARS. Exactly one of the two is ever filled, and which one is
        # decided by `percent_basis` below rather than by whichever happens to
        # be non-None — a plugin that fell back from one to the other would
        # price 90% of money at a factor meant for 90% of gallons.
        basis_amount=_threshold(basis_amount),
        # A PERCENTAGE OF WHAT — read STRUCTURALLY off the seam like every
        # other tariff fact here, so a caller whose seam predates the column
        # states None and the plugin REFUSES BY NAME. It deliberately does not
        # degrade to `'usage'`: every stored row says one of the two out loud
        # (`rating/0043`), so a None means a hop dropped it, and a bill priced
        # on a guessed basis is a wrong bill that looks right.
        percent_basis=getattr(tariff, "percent_basis", None),
        # DEF-276 — read structurally with `getattr`, like every other seam
        # field here: a caller whose seam predates the column states no version
        # and its lines simply name none, exactly as every bill issued before
        # 2026-08-19 did. Nothing is derived and nothing is looked up; rating's
        # `pricing_inputs` has served this id since it was written and this is
        # the step that puts it where a line can pick it up.
        tariff_version_id=getattr(tariff, "version_id", None),
        # R5 — the premises factor on the money (PO ruling 2026-08-19). Read
        # structurally like everything else here; a caller that states none
        # prices exactly as before, which is what keeps every frozen figure
        # still frozen.
        jurisdiction_factor=Decimal(str(getattr(tariff, "jurisdiction_factor", 1) or 1)),
        # BR-RAT-028 — the two minimum-bill thresholds (CR-052 task 4). Read
        # structurally like every other seam field here, so a caller whose seam
        # predates them states neither and prices exactly as before — which is
        # every B5 fixture and every bill this product has issued.
        #
        # `_threshold` and not `Decimal(str(...) or ...)`: a stated `0` must
        # survive as `Decimal("0")` (a tenant saying "no floor" by typing one)
        # and an ABSENT threshold must stay None. `x or default` collapses the
        # two, which is DEF-154's shape.
        minimum_amount=_threshold(getattr(tariff, "minimum_amount", None)),
        plan_minimum_bill_amount=_threshold(getattr(tariff, "plan_minimum_bill_amount", None)),
    )

    return NormalizedInput(
        subscription=SubscriptionContext(
            service=service,
            currency=account.currency,
            # B4.2 / BR-RAT-006: exemption is an ACCOUNT fact. There is no
            # per-service exemption input anywhere in these contracts.
            tax_exempt=bool(account.tax_exempt),
        ),
        usage=usage,
        config=config,
        period=shape,
        taxes=tax_specs(taxes),
        fees=fee_candidates(fees),
    )


def tax_specs(taxes: tuple[Any, ...]) -> tuple[TaxRuleSpec, ...]:
    """Seam `TaxRule`s -> the engine's own spec. Named because it is used TWICE.

    `price_period` adapts a single service's taxes here; `price_bill` adapts
    the BILL's taxes at its combined pass, where the tax actually belongs
    (B4.2 / GT-17). One adaptation function, so the two paths cannot drift into
    reading a rate differently.

    `tax_id` is carried through with `getattr`, like every other seam field:
    it is the AUTHORITY's identity (BR-BIL-069, PO ruling 2026-08-11) and the
    engine performs no arithmetic with it. A caller whose rule states no tax id
    produces a tax line that names no authority — which BR-BIL-010 refuses at
    issue, rather than posting the money to whichever 2200 account came first.
    """
    return tuple(
        TaxRuleSpec(
            code=rule.code,
            # DEF-RAT-9307 — display text for the tax line; never arithmetic.
            bill_label=getattr(rule, "bill_label", None),
            rate=getattr(rule, "rate", None),
            tax_id=getattr(rule, "tax_id", None),
            # BR-RAT-036's flat-per-bill form (the PO's ruled $0.85 PUC fee,
            # 2026-08-18). `getattr` like every other seam field: a caller that
            # predates the column states no flat amount and keeps its percent
            # behaviour exactly.
            flat_amount=getattr(rule, "flat_amount", None),
            # R7 — the services this tax is a percent OF. Empty keeps today's
            # whole-bill base, which is what every B5 fixture states.
            applies_to_services=tuple(getattr(rule, "applies_to_services", ()) or ()),
            # BR-RAT-106 (DEF-502) — this authority's statutory before/after
            # answer, from `taxes.discount_treatment` via the seam. `getattr`
            # like every field here; None degrades to `before` downstream,
            # which is the column's own default and inert without a discount.
            discount_treatment=getattr(rule, "discount_treatment", None),
            # BR-RAT-036's PER-UNIT form and BR-RAT-042's marginal threshold
            # (CR-052 W5 task 16). `getattr` like every field above it: a caller
            # that predates these columns states none of the three and prices
            # exactly as it did — every B5 fixture included.
            per_unit_amount=getattr(rule, "per_unit_amount", None),
            per_unit_uom=getattr(rule, "per_unit_uom", None),
            applies_above_units=getattr(rule, "applies_above_units", None),
            # BR-RAT-036's per-METER form (`DEF-RAT-9278`). `getattr` like
            # every field here: an older caller states none and prices as it did.
            per_meter_amount=getattr(rule, "per_meter_amount", None),
        )
        for rule in taxes
    )


def fee_candidates(fees: tuple[Any, ...]) -> tuple[LineCandidate, ...]:
    """Seam fee lines -> line candidates, read structurally (rating never
    imports billing's types).

    Also used twice, and for the same reason: on a multi-service bill the fees
    are added ONCE at bill level rather than once per service.
    """
    return tuple(
        LineCandidate(
            kind=getattr(fee, "kind", KIND_FEE),
            description=fee.description,
            amount=fee.amount,
            # A fee's own flag is carried faithfully — and B4.2 is enforced
            # structurally downstream by KIND, so a fee that arrives wrongly
            # flagged taxable still never reaches a percent base
            # (US-RAT-013 TC-7).
            taxable=bool(getattr(fee, "taxable", False)),
            quantity=getattr(fee, "quantity", None),
            unit=getattr(fee, "unit", None),
            unit_price=getattr(fee, "unit_price", None),
            # Carried faithfully, exactly like every other field above, and
            # usually None: a fee is a fact about the ACCOUNT (a late fee is
            # not "the water's"), so billing's fee lines name no service today.
            # DEF-554 (2026-08-22): `tariff_version_id` rides the same channel,
            # because this channel does not only carry fees — a multi-pass bill
            # (a back-bill's unequal segments, BR-RAT-114's mid-period split)
            # hands already-priced usage/base lines through it, and dropping
            # the field here erased DEF-276's provenance on exactly the bills
            # that span two versions. A real fee states none and stays None.
            # Nothing is invented for one — a fee's GL account comes from its
            # CHARGE CODE (BR-BIL-010, `rating.charges.gl_account_id`), which
            # rides its OWN field (`charge_id`, below) since DEF-714 and is
            # never substituted for by a service.
            service=getattr(fee, "service", None),
            tariff_version_id=getattr(fee, "tariff_version_id", None),
            # WHICH CHARGE CODE THIS FEE IS (DEF-714, 2026-08-25) — carried
            # faithfully, `getattr` like every field above. The paragraph
            # directly above used to end *"the charge id does not travel on
            # this seam at all; that gap is reported by
            # `apps/billing/issue._gl_account_for`"*. It travels now, because
            # the report was a refusal of the whole bill: BR-BIL-010 keys a
            # fee's GL account on `rating.charges.gl_account_id` and the line
            # could not say which code it came from. Still nothing is
            # INVENTED — a fee that states no code arrives None and is refused
            # by name at issue, exactly as before.
            charge_id=getattr(fee, "charge_id", None),
        )
        for fee in fees
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-16 by the pricing-engines lane (projects the TOU windows, the resolved season, the capacity unit+rate, the demand rates and the percent+basis onto ModelConfig, and gates each pre-split window quantity for its OWN unit) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `tax_specs` carries the tax id across the seam; `fee_candidates` carries a fee's service faithfully)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1/2/5/10/11 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: the multiplier is applied HERE although US-RAT-012 §1 says metering normally supplies post-multiplier consumption ("the engine asserts it"). B5 GT-5's fixture hands the engine the RAW delta plus the multiplier and freezes the post-multiplier quantity (2,740), so the seam's contract requires the engine to apply it. Recorded rather than reconciled silently.
# amended: 2026-10-01 by the season-change-reading lane (DEF-RAT-8849) — a reading on the season-change day replaces the day split (PO "yes build the season-change day reading"); HUMAN-REVIEW-PENDING, review-ledger row "DEF-RAT-8849"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
