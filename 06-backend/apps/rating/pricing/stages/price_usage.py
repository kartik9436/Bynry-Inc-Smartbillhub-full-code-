# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (BR-BIL-037 stage 3)
#           Screens: — (the priced lines render in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-044 (this stage carries NO per-model branching — it asks the
#           registry) · BR-RAT-012/027 (base charge is per service; the plan's
#           base is derived from the service bases) · BR-RAT-004 (the base is
#           prorated by calendar days — B4.3) · BR-RAT-003 (nothing rounds here)
#           · BR-BIL-037 (stage 3: PricedLines out) · BR-BIL-039 (pure)
# Golden:   GT-1 (82.08 + 18.50) · GT-2 (13.74 + 12.00) · GT-3 (base 15.25) ·
#           GT-5 (343.60, no base) — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_012_engine.py ·
#           06-backend/tests/test_us_rat_015_plugins.py (no-branching check)
# Impacts:  apps/rating/pricing/stages/apply_charges.py (its sole consumer)
# ───────────────────────────────────────────────────────
"""Stage 3 — price-usage: usage lines from the model plugin, plus the base line.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

THE THING TO NOTICE IS WHAT IS ABSENT
-------------------------------------
This module names no pricing model. There is no `if model == "tiered"` here and
there is nowhere for one to be added — the model is a key into the registry, and
the plugin is whatever that key resolves to (BR-RAT-044). US-RAT-015 TC-4 greps
this file for exactly that property, so adding a branch here fails a test rather
than merely offending a convention.

The base charge is part of stage 3's output, not stage 4's: US-BIL-029 section 7
totals stage 3 as "usage + base + capacity". It is per service (BR-RAT-012) and
prorated by calendar days when the period is partial (BR-RAT-004 / B4.3, GT-3).

`base_charge=None` means the tariff states NO base charge and NO base line is
emitted — absence, not a base of zero. B5 GT-5 names none, and a 0.00 line the
customer never agreed to is an invented input (GT-5's fixture asserts the
absence directly).

⚠ **AND NOTHING ON THE LIVE PATH CAN PRODUCE THAT `None` — `OQ-1221` /
`DEF-2864`, 2026-08-31.** `billing.gather._base_charge_for` returns a `Decimal`
or raises, so this branch is reached only from B5's own fixtures. A real
configuration that has no standing charge for a service has to state `0`,
because a blank means *this size is not served* (CR-013 part 1) and stops the
bill — and the `0` then prints exactly the line the paragraph above calls an
invented input. It did, on the PO's BL-2608-000048: `sewer base charge  —  —
0.00 USD`. The repair is one line HERE and it reverses a PO ruling of
2026-08-19 (*"print $0.00"*), so it is asked rather than taken.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from apps.rating import proration
from apps.rating.pricing import registry
from apps.rating.pricing.contracts import (
    KIND_BASE,
    LineCandidate,
    NormalizedInput,
    PricedLines,
)


def _base_lines(source: NormalizedInput) -> tuple[LineCandidate, ...]:
    base_charge = source.config.base_charge
    if base_charge is None:
        return ()
    amount = proration.prorated_amount(base_charge, source.period.factor)
    # R5 — the PREMISES jurisdiction factor reaches the BASE CHARGE as well as
    # the usage, which is the second half of the PO's correction of 2026-08-19:
    # *"you will have to add rate changes in base charges and rates"*. §A4's S2
    # is the worked case — an outside-city electric base of $18.50 bills $27.75
    # while the sewer base beside it stays $8.00, because the tenant listed
    # sewer as flat everywhere and the factor arrives per service.
    amount = amount * source.config.jurisdiction_factor
    # 🔒 HUMAN-REVIEW-PENDING — `DEF-CUS-9050` (PO 2026-10-02, option A): an
    # EMPTY unit's base on the owner's bill, for the days nobody occupied it.
    # `occupancy_factor` is vacant days / period days, UNROUNDED, so a move-in on
    # the 16th of a 30-day month bills the owner 15/30 × $8.00 = $4.00 and the
    # one rounding is still finalize's (hard rule 2). `None` everywhere else.
    occupancy = getattr(source.config, "occupancy_factor", None)
    if occupancy is not None:
        amount = amount * occupancy
    partial = source.period.is_partial or occupancy is not None
    label = " (prorated)" if partial else ""
    unit = getattr(source.config, "unit_label", None)
    named = f"{unit} · " if unit else ""
    return (
        LineCandidate(
            kind=KIND_BASE,
            description=f"{named}{source.subscription.service} base charge{label}",
            amount=amount,
            taxable=True,  # B4.2: the base charge is in the tax base
            service=source.subscription.service,
            # DEF-276 — the base charge is priced from this version too, so it
            # carries the same provenance as the usage lines beside it. A bill
            # whose usage re-prices and whose base does not is not reproducible.
            tariff_version_id=source.config.tariff_version_id,
            # 2026-09-30 — the meter, when this config is one of a split
            # service's meters. Identity, never arithmetic.
            asset_id=getattr(source.config, "asset_id", None),
            # 🔒 DEF-RAT-9327 — the charge code this base came from (`BASE-W`),
            # so a discount scoped to NAMED charge codes selects this line
            # (BR-RAT-068). A label: the amount above is the only figure.
            charge_code=getattr(source.config, "base_charge_code", None),
        ),
    )


def price_usage(source: NormalizedInput) -> PricedLines:
    """Resolve the model's plugin and price with it. UNROUNDED throughout.

    THE SERVICE IS STAMPED HERE, NOT IN THE PLUGIN (BR-BIL-069, PO ruling
    2026-08-11). Every line this stage emits belongs to `source.subscription.
    service` by construction — the stage is invoked once per service and holds
    exactly one — so the identity is written on the way out rather than being
    asked of each plugin. A plugin that forgot it would produce a line billing
    cannot stamp a GL account onto, and BR-BIL-010 would refuse the whole bill;
    making it structural means a new pricing model cannot introduce that defect.
    The plugin's own value is overwritten deliberately: a plugin is told which
    service it is pricing, so it has no other one to name.
    """
    plugin = registry.PRICING_MODELS.resolve(source.config.model)
    factor = source.config.jurisdiction_factor
    # 🔒 DEF-BIL-8566 · PO ruling 2026-10-01 (decision log *"SIX PO RULINGS IN
    # ONE MESSAGE"*, (5)), verbatim: *"A · Cart shrinks too: $9.00"*. A COUNTED
    # service's per-asset charge (trash carts, fire lines — `per_size_line`, set
    # only by `billing.gather._per_size_configs`) is a monthly charge per thing,
    # so on a part month it prorates by calendar days EXACTLY as the base line
    # below does (B4.3 / BR-RAT-004): one cart on 18 of 30 days is 18/30 ×
    # $15.00 = **$9.00**, and each half of a month cut at a price change takes
    # its own share (15/31 and 16/31 of $15.00 = $7.26 + $7.74). The COUNT is
    # never scaled — one cart stays one cart on the line — and a METERED tiered
    # service is untouched: its quantity is what the meter measured and only its
    # tier BOUND scales (BR-RAT-002). A flag on the config and not a model name,
    # so this stage still names no pricing model (BR-RAT-044). A whole month is
    # a factor of 1, so every full-month figure — fire's $84.00 (CR-063), the
    # $15.00 cart — is byte-identical.
    #
    # 🔒 DEF-BIL-8743 — the SUMMED installed size of a summing service (CR-062
    # D1: solar 2 + 4 + 8 kW × $14.00, battery kW × $3.00; `installed_sum_line`,
    # set only by billing's measure stage) is the same kind of charge — monthly,
    # per thing installed — and signed law prorates it (B4.3; B5 WE-16/GT-31
    # *"Solar 4 units activated Jul 22 → 10/31 days × $40.00 = $12.90"*; GT-15
    # amended 2026-08-11, *"BOTH lines prorate"*). A schedule quoted *flat per
    # kW* — the shape a signed-up utility's own sample schedules carry — charged
    # it whole: 6 kW × $14.00 on 19 of 30 days was $84.00 where B4.3 says $53.20.
    count_share = (
        source.period.factor
        if getattr(source.config, "per_size_line", False)
        or getattr(source.config, "installed_sum_line", False)
        else 1
    )
    usage_lines = _without_zero_rate_installed_lines(
        source,
        plugin(
            source.subscription,
            source.usage,
            source.config,
            **({"period": source.period} if _accepts_period(plugin) else {}),
        ),
    )
    return PricedLines(
        source=source,
        usage_lines=tuple(
            dataclasses.replace(
                line,
                # R5 — AFTER PRICING AND BEFORE ROUNDING, which is the only
                # place it can go. The plugin has already walked the tier
                # boundaries with the customer's real quantity (that is the
                # METER multiplier's job and it happened upstream), so scaling
                # here changes the money and cannot change which tier a kWh
                # landed in. Doing it before the plugin would move the tier
                # boundaries; doing it after `finalize` would round twice and
                # break BR-RAT-003's single rounding event.
                amount=proration.prorated_amount(line.amount, count_share) * factor,
                # AND THE PRINTED RATE MOVES WITH IT, so the line still foots.
                # A customer who multiplies the quantity by the unit price on
                # their own bill must arrive at the amount beside it — the same
                # reason B4.2's 2026-08-11 re-signing sums the tax base from the
                # ROUNDED line amounts. Scaling the money and leaving "0.110000"
                # printed next to $82.50 would produce a document that argues
                # with itself. None stays None: a line with no stated rate has
                # no rate to scale.
                #
                # 🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` (PO 2026-10-12,
                # *"quantity × rate = amount on every row"*) — and the SAME
                # sentence holds for the per-item day share above: a cart or an
                # ERU on 19 of 30 days is `1 × $4.50 × 19/30 = $2.85`, so the
                # printed rate is `$2.85`, not `$4.50` beside `$2.85`. The COUNT
                # is never scaled and neither is the money (it already was);
                # only the printed rate now says what was charged per item. A
                # whole month is a share of 1 and prints exactly as before.
                unit_price=(
                    None
                    if line.unit_price is None
                    else proration.prorated_rate(line.unit_price, count_share) * factor
                ),
                service=source.subscription.service,
                # THE VERSION IS STAMPED HERE FOR THE SAME REASON THE SERVICE IS
                # (DEF-276). This stage is invoked once per service and holds
                # exactly one tariff version, so the provenance is written on the
                # way out by construction rather than being asked of each plugin.
                # A plugin that forgot it would produce a line that cannot be
                # re-priced, and BR-RAT-007's promise would fail silently — the
                # exact failure mode the defect was filed for. Making it
                # structural means a new pricing model cannot reintroduce it.
                tariff_version_id=source.config.tariff_version_id,
                # 2026-09-30 — stamped here for the reason the version is: one
                # config per call, so the meter is known by construction.
                asset_id=getattr(source.config, "asset_id", None),
            )
            for line in usage_lines
        ),
        base_lines=_base_lines(source),
    )


ZERO = Decimal(0)


def _without_zero_rate_installed_lines(
    source: NormalizedInput, lines: tuple[LineCandidate, ...]
) -> tuple[LineCandidate, ...]:
    """Leave off a CAPACITY line whose RATE is exactly $0. 🔒 HUMAN-REVIEW-PENDING.

    `DEF-RAT-10210` · PO ruling 2026-10-17 (decision log *"A $0.00 CAPACITY
    LINE IS LEFT OFF THE BILL"*), option B, verbatim reply *"please start these
    changes"*: a utility charging solar or battery a flat fee states the fee as
    the base charge (`BASE-SOL $25.00`) and the per-kW rate as `$0`, and the
    bill printed `solar 6 kW × $0.00 = $0.00` beside the real $25.00. **When a
    capacity line prices to $0.00 because its rate is $0, it is not printed on
    the bill or the portal; the base charge and tax are unchanged.**

    WHY HERE, AND NOT AT EACH SCREEN. This is the one place every bill's lines
    are born: the bill-run review, the one-time bill preview, the stored
    `invoice_lines`, the document and the portal all read what this stage
    emits, so dropping the line here makes all of them agree by construction —
    and no `$0.00` row is ever written. Filtering at five presentation surfaces
    instead would leave a stored line that a sixth surface (an export, a
    statement, a report) prints. The line carried no money: a `$0.00` line
    adds nothing to the tax base (B4.2 sums amounts), nothing to a minimum's
    basis (`apply_charges.minimum_basis`), and the base line beside it — the
    one that makes `apply_charges` consider the service priced at all — is
    untouched, so **no total, tax or golden figure can move**. No signed GT
    prices a capacity rate of zero.

    WHAT COUNTS AS A CAPACITY LINE — by CONFIGURATION, never by model name
    (BR-RAT-044 — this stage names no model, so `ModelConfig.
    charges_per_installed_unit` answers it): a config with a capacity spec
    (`models/capacity.py`'s own shape) or one flagged `installed_sum_line` (a
    summed solar / battery / storm-water kW total priced on a flat or tiered
    schedule — how every live schedule bills them, set only by billing's
    measure stage). **A COUNTED service (trash, fire — `per_size_line`) is NOT
    in scope:** its per-item charge is joined with its base into ONE bill line
    (`billing.counted_service_line`), so there is no separate $0.00 row to
    hide. A METERED $0 line is not a capacity line and is emitted as before.

    WHAT DECIDES IT — THE RATE, NEVER THE AMOUNT. `unit_price == 0`. A real
    rate times zero installed kilowatts still prints (`0 kW × $4.00 = $0.00`):
    that tells a clerk the equipment sums to zero, and the ruling hides only
    the line a $0 RATE produces. Equipment with no recorded size never reaches
    here — billing's measure stage holds the account first
    (`installed_capacity_unresolved`), which keeps the ruling's *"installed
    equipment must still be recorded on each unit"*. A line with no stated rate
    (`None`) is never dropped: no rate is not a zero rate.

    ISSUED BILLS ARE NOT TOUCHED (hard rule 4): this runs only when a bill is
    priced, so an already-issued `$0.00` row stays as the customer received it.
    """
    if not source.config.charges_per_installed_unit:
        return lines
    return tuple(
        line
        for line in lines
        if not (line.unit_price is not None and line.unit_price == ZERO and line.amount == ZERO)
    )


def _accepts_period(plugin: object) -> bool:
    """Whether a plugin takes the optional `period` argument.

    Kept deliberately narrow: the interface BR-RAT-044 names is
    `price(subscription_ctx, measured_usage, model_config)`, and the period is
    an OPTIONAL fourth argument for the models whose thresholds scale with it
    (BR-RAT-002). A plugin that does not need it does not have to accept it, and
    this stage still learns nothing about which model it is talking to.
    """
    code = getattr(plugin, "__code__", None)
    return bool(code and "period" in code.co_varnames[: code.co_argcount])


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: the SERVICE is stamped on every usage and base line here, structurally, so no plugin can forget it)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1/2/3/5 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: `_accepts_period` inspects the plugin's signature rather than the model NAME — the stage still holds no per-model knowledge, but a reviewer should know introspection is doing that work. Alternative considered and rejected: making `period` mandatory on the interface, which would depart from BR-RAT-044's stated three-argument contract.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
