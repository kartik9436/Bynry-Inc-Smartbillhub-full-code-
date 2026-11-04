# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — totals) · EP-BIL-01 (BR-BIL-037
#           stage 5)
#           Screens: — (tax lines render in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-005 (tax base = usage + base only; fees/late never taxed) ·
#           BR-RAT-006 (exemption is ACCOUNT-level: tax = 0 regardless of
#           service) · BR-RAT-036 (percent CONFIRMED; flat & per-unit PROPOSED
#           — all three BUILT; no tax-on-tax) · BR-RAT-042 (a per-unit
#           threshold is MARGINAL — only units above it are taxed; CONFIRMED,
#           PO closing OQ-054 option (a)) · BR-RAT-003 (each line finalized once)
#           · BR-BIL-037 (stage 5: TaxedLines out) · BR-BIL-039 (pure)
# Golden:   GT-1 (8.25% x 100.58 -> 8.30) · GT-10 (same, fee excluded) ·
#           GT-11 (exempt -> 0) — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_013_totals.py ·
#           06-backend/tests/test_def_rat_9307_tax_bill_label.py (the line's
#           words: Bill label, else "Tax " + name — DEF-RAT-9307, 2.481.2)
# Impacts:  apps/rating/pricing/stages/assemble.py (its sole consumer)
# ───────────────────────────────────────────────────────
"""Stage 5 — compute-tax: percent taxes on the B4.2 base, or nothing at all.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Two frozen rules, and nothing else in this file:

* **The base is usage + base** (B4.2 / BR-RAT-005). This stage does not decide
  that — `finalize` already computed the base by KIND, so a fee cannot reach
  this module's arithmetic even if it wanted to. Tax is computed on a number
  that structurally cannot contain a fee.
* **Exemption is account-level** (B4.2 / BR-RAT-006, GT-11). An exempt account
  gets NO tax lines, regardless of service. The rules are still evaluated as
  present — GT-11 passes live tax rules with an exempt account precisely so the
  exemption has to ZERO a tax that would otherwise apply.

No tax-on-tax: tax lines are emitted after the base is fixed and never join it
(BR-RAT-036). Each tax line is finalized on its own, half-up 2dp, which is where
GT-1's "8.2979 -> 8.30" comes from.

FLAT-PER-BILL IS IMPLEMENTED (2026-08-18); PER-UNIT IS NOT. BR-RAT-036 defines
three forms. The PO's ruled Texas table (decision log 2026-08-18, DEF-254/273)
includes a **PUC Regulatory Fee of $0.85 FLAT PER BILL on electric**, so the
seam's `TaxRule` now carries `flat_amount` and a flat rule bills that amount as
itself — `$0.85` on a $40 bill and `$0.85` on a $4,000 one, which is the whole
meaning of "flat". It is emitted ONCE per bill by construction: `price_bill`
withholds taxes from every per-service pass and runs this stage exactly once on
the combined lines, so a three-service bill carries one $0.85 line and not three.

PER-UNIT IS IMPLEMENTED AS OF 2026-08-31 (CR-052 W5 task 16). ⚠ **THE
PARAGRAPH THAT STOOD HERE IS REPLACED RATHER THAN DELETED (hard-won law 1).** It
read: *"PER-UNIT is still not implemented. r10's Water Conservation Surcharge is
'$0.25 / kgal · Tier 3+ usage only' and pricing it needs the tier-3 usage this
stage does not receive; the tax row is seeded carrying its whole condition and
prices nothing until a signed rule says how a per-unit tax reads a tiered
schedule."*

**BOTH HALVES OF THAT SENTENCE WERE WRONG BY THE TIME ANYONE READ IT.**

*The signed rule exists.* `OQ-054` asked precisely this question and the PO
closed it on 2026-08-09 as **`BR-RAT-042`, CONFIRMED, option (a): the threshold
is MARGINAL — only units ABOVE it are taxed.** So a per-unit tax never reads a
tier table at all: it reads a QUANTITY the tax itself states
(`taxes.applies_above_units`), which is what makes it work across plans whose
tier tables differ — the other half of what OQ-054 asked.

*The quantity was here all along.* This stage receives `FinalizedLines`, and
every usage line on it carries its own `quantity` and `unit` (the tiered plugin
stamps one per block, the flat plugin one per service). Summing the usage lines
in the tax's scope IS the billed quantity, in the unit it was measured in. No
new field crosses the seam for it and no plugin had to change.

    amount = per_unit_amount x max(0, quantity_in_scope - applies_above_units)

**Worked, and it is `EP-RAT-05` TC-6's own figure:** water billed at
`5 + 10 + 3.72 = 18.72 kgal` with the surcharge stated at `$0.25 / kgal` above
`15` is taxed on `3.72 kgal` and the line is **`$0.93`**. Read as a whole-bill
levy it would be `$4.68`, which is the customer paying the surcharge on the
first fifteen thousand gallons the rule exempts.

⚠ **THE UNIT IS CHECKED, NEVER CONVERTED** (CLAUDE.md hard rule 3, and
BR-RAT-038's *"no silent conversion"* applied one module over). A per-unit rule
states `per_unit_uom`; a usage line in its scope measured in anything else makes
the sum meaningless — kWh cannot be added to kgal — so the rule REFUSES and names
the two units. In practice that means an unscoped per-unit tax on a
multi-service bill refuses and asks to be scoped, which is the correct request:
`$0.25 / kgal` is a statement about water.

⚠ **THE THRESHOLD IS NOT PRORATED, AND THAT IS STATED RATHER THAN CHOSEN.**
BR-RAT-002 scales TIER thresholds by the period factor; it is a rule about a
rate schedule and says nothing about a tax. Nothing signed states whether a
`$0.25/kgal above 15` surcharge becomes *above 7.5* on a fifteen-day period. The
unscaled reading taxes FEWER units on a short period, so it under-charges rather
than over-charges, which is this repo's stated fail-safe direction. Filed as
`DEF-2702` rather than decided here.

PER-METER IS IMPLEMENTED AS OF 2026-10-03 (`DEF-RAT-9278`, CR-165-BRC10
round 2) — BR-RAT-036's FOURTH form as amended by DEF-386 (PO 2026-08-21,
option C, verbatim: *"Per-meter now (it's a small change), stacking later"*).
The column existed for six weeks and nothing priced it, so a `$1.25` per-meter
fee billed `$0.00`. A per-meter rule prices a COUNT OF METERS, never a measure:

    amount = per_meter_amount x meters_in_scope

**The count comes from the lines this stage already receives**, the same way
per-unit's quantity does — no new field crosses the seam for it. A meter is a
USAGE line's meter: within each service in the tax's scope, the distinct
`asset_id`s stamped on its usage lines (set when a service carries two or more
meters, PO 2026-09-30), or ONE where the service has usage lines and no
`asset_id` (every single-meter service). **Worked:** `$1.25` on a one-meter
water bill is **`$1.25`**; on a duplex with two water meters it is **`$2.50`**
(DEF-386's own figure). A service with no usage line — a base-only trash cart,
an unmetered storm-water charge — contributes NO meter: a cart is not a meter.
That zero is a real answer (the line prints `0 meter x 1.25 = 0.00`, the same
posture BR-RAT-042 gives a per-unit tax below its threshold), and the decision
log records it. No ❄️ B5 fixture states a per-meter rule, so no frozen figure
can move.

THE CONDITIONS ARE NOT EVALUATED HERE, AND THAT IS DELIBERATE (DEF-273). A tax
that does not apply to this customer's class, services or premises must produce
**no line at all**, not a zero one — and a stage whose job is to compute lines
cannot decline to have one. So `rating.selectors.plan_tax_rules` decides WHICH
rules reach a bill and this stage prices the ones that do, the same division the
account-level exemption above already uses.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.rating.pricing.contracts import (
    KIND_TAX,
    KIND_USAGE,
    FinalizedLines,
    LineCandidate,
    TaxedLines,
)
from apps.rating.pricing.errors import TaxRuleUnpriceable
from apps.rating.pricing.stages import finalize as finalize_stage


def compute_tax(source: FinalizedLines) -> TaxedLines:
    normalized = source.normalized
    if normalized.subscription.tax_exempt:
        # B4.2 / BR-RAT-006 — account-level, regardless of service. No lines at
        # all rather than zero-valued ones: the bill should not show a tax the
        # account does not owe.
        return TaxedLines(source=source, tax_lines=(), tax_total=Decimal("0.00"))

    lines = tuple(
        finalize_stage.finalize_line(
            LineCandidate(
                kind=KIND_TAX,
                description=_printed_description(rule),
                amount=_tax_amount(rule, _base_for(rule, source), source),
                taxable=False,  # BR-RAT-036: no tax-on-tax
                # -- BR-RAT-036 PER-UNIT -- the line has to FOOT -------------
                # A per-unit line prints `3.72 kgal x 0.250000 = 0.93`, so the
                # quantity and its unit travel on the line exactly as they do on
                # a usage line. A percent or flat rule states neither: there is
                # no quantity to print beside `$0.85`, and a `0` there would be
                # a figure the customer could not reconcile.
                quantity=_taxed_quantity(rule, source),
                unit=_printed_unit(rule),
                # A percent rule's unit price IS its rate — that is what the
                # bill prints beside the line. A FLAT rule has no rate to print
                # and states None rather than 0, because a printed "0.000000 %"
                # beside $0.85 reads as a bug to the customer looking at it.
                unit_price=_printed_rate(rule),
                # BR-BIL-069 (PO ruling 2026-08-11, OQ-116): the line names the
                # TAX that produced it, and through it the authority whose money
                # this is. One rule, one line, one authority — so a $8.30 charge
                # that is really Texas $6.29 + Harris County $1.01 + Katy $1.00
                # arrives at `invoice_lines` as three lines, each able to say
                # whose debt it is. Carried, never derived: the description is
                # display text and matching on it (option D) misposts money the
                # first time a tax is renamed or a catalogue is translated.
                tax_id=rule.tax_id,
            )
        )
        for rule in normalized.taxes
    )
    return TaxedLines(
        source=source,
        tax_lines=lines,
        tax_total=sum((line.amount for line in lines), Decimal("0.00")),
    )


def _printed_description(rule: Any) -> str:
    """WHAT THE CUSTOMER READS on a tax line (DEF-RAT-9307, PO 2026-10-03).

    The clerk's Bill label when one is stored — the walk's *County utility
    tax* with label *County tax* prints **"County tax  $1.20"** — and the
    wording every bill has always had, ``"Tax " + code``, where none is. A
    label of only spaces is no label: a line never prints a blank name beside
    its amount.

    Display text and nothing else. The amount is computed from the rule's
    rate/amount fields before and independently of this, and the line's
    authority travels as ``tax_id`` (BR-BIL-069), never matched off the words.
    An already-issued line is never reworded (hard rule 4): this decides what
    a NEW line says.
    """
    label = (getattr(rule, "bill_label", None) or "").strip()
    return label or f"Tax {rule.code}"


def _base_for(rule: Any, source: FinalizedLines) -> Decimal:
    """WHICH MONEY THIS TAX IS A PERCENT OF (R7, added 2026-08-19).

    A tax stating no services is a percent of the whole bill, which is every
    frozen B5 figure — GT-1, GT-10 and GT-17 each state one rate over one
    combined base and none of them moves by a cent.

    A tax stating services is a percent of THOSE SERVICES' taxable lines. r10's
    City Franchise Fee is *"1.5% · Electric only"* and the CR-013 design works
    it that way: on §A4's S1 the electric lines come to **$121.10**, so the fee
    is **$1.82**. Read as a whole-bill percent it would be 1.5% of $188.90 =
    **$2.83** — the city taxing the customer's water and sewer at its electric
    franchise rate, on a document where nothing looks wrong.

    The narrowing goes through `finalize.taxable_base`, the same function the
    whole-bill base uses, so there is ONE definition of "the tax base" and not
    two that can drift — and a fee still cannot reach it, because that function
    filters by KIND (B4.2 / BR-RAT-005).

    ⚠ THIS DECIDES THE BASE, NEVER WHETHER THE TAX APPLIES. Applicability is
    resolved before a rule is ever built (`rating.selectors.plan_tax_rules`,
    `rating.resolution.resolve_taxes`), because a tax that does not apply must
    produce NO LINE and not a zero-valued one (DEF-273). A rule that reaches
    here and finds none of its services on the bill yields a $0.00 base, which
    is a resolution bug upstream rather than something to paper over here.

    ── THE DISCOUNT PAIR (DEF-502, 2026-08-22 — BR-RAT-106) ──────────────────
    The apply-discounts stage hands on BOTH subtotals: `taxable_subtotal` is
    the full tariff amount (`subtotal_before`) and `discount_reduction_taxable`
    is what R6 took off it. WHICH one this authority levies on is statutory and
    stated per tax (`taxes.discount_treatment`), and the pick goes through the
    ONE signed reader, `rating.selectors.taxable_subtotal_for` — imported
    lazily because `selectors` imports the engine and a module-level import
    would be a cycle. Worked (BR-RAT-106's own pair): a $1.00 PAPERLESS credit
    leaves a 2% county line at $3.78 under `before` and $3.80 under `after`.

    A SERVICE-SCOPED rule prices on its services' own taxable lines whether or
    not the bill carries a discount (`BR-RAT-116`, PO 2026-08-22 — OQ-331's
    refusal retired the day the rule was signed). On an undiscounted bill
    (reduction 0) every path below is byte-identical to the pre-DEF-502 code.
    """
    if (
        getattr(rule, "flat_amount", None) is not None
        or getattr(rule, "per_unit_amount", None) is not None
        # DEF-RAT-9278 — a per-meter tax's base is a COUNT, never money.
        or getattr(rule, "per_meter_amount", None) is not None
    ):
        # A flat-per-bill tax is not a percent of anything (BR-RAT-036): it has
        # no base, so neither the scope narrowing nor the discount pair can
        # concern it. Returned as zero UNUSED — `_tax_amount` reads the flat
        # figure first — and short-circuited here so a scoped flat fee on a
        # discounted bill does not trip the OQ-331 refusal over a base it
        # would never have read.
        #
        # A PER-UNIT tax is short-circuited for the same reason and it is a
        # stronger one: its base is a QUANTITY, not money. `applies_to_services`
        # narrows which USAGE LINES it counts (`_usage_lines_in_scope`), never
        # which dollars, and a discount reduces money and cannot remove a
        # kilolitre from a meter — so BR-RAT-106's before/after pair has nothing
        # to decide here.
        return Decimal("0")
    reduction = getattr(source, "discount_reduction_taxable", None) or Decimal("0")
    services = getattr(rule, "applies_to_services", ()) or ()
    if not services:
        before = source.taxable_subtotal
        if not reduction:
            return before
        from apps.rating.selectors import taxable_subtotal_for  # lazy — see docstring

        return taxable_subtotal_for(
            getattr(rule, "discount_treatment", None), before, before - reduction
        )
    # BR-RAT-116 (PO 2026-08-22, closing OQ-331 — verbatim: "tax is always on
    # Utility service charge + base fees"): a SCOPED tax's base is the scoped
    # services' own taxable lines, and a whole-bill discount does not shrink
    # it, whatever the treatment says. The OQ-331 refusal that stood here
    # retired the day the rule was signed; on the OQ's own worked bill the
    # electric-only 1.5% fee reads $0.89 (1.5% x $59.00), never $0.74 or $0.80.
    scoped = tuple(line for line in source.lines if line.service in services)
    return finalize_stage.taxable_base(scoped)


def _printed_rate(rule: Any) -> Decimal | None:
    """WHAT THE BILL PRINTS BESIDE THE LINE — the rate, the per-unit price, or
    nothing.

    A percent rule's unit price IS its rate. A PER-UNIT rule's is its
    `per_unit_amount`, so the customer can multiply the printed quantity by the
    printed price and arrive at the printed amount — `3.72 x 0.25 = 0.93`. A
    FLAT rule has no rate to print and states None rather than 0, because a
    printed "0.000000 %" beside $0.85 reads as a bug to the customer looking at
    it.
    """
    if getattr(rule, "flat_amount", None) is not None:
        return None
    per_unit = getattr(rule, "per_unit_amount", None)
    if per_unit is not None:
        return Decimal(per_unit)
    per_meter = getattr(rule, "per_meter_amount", None)
    if per_meter is not None:
        return Decimal(per_meter)  # `1 meter x 1.25 = 1.25` foots on the bill
    return rule.rate


#: The word a per-meter line prints beside its count. A meter is not a measure,
#: so this is a COUNT NOUN and never a unit of consumption (hard rule 3 is about
#: consumption; nothing here is one).
METER_COUNT_UNIT = "meter"


def _printed_unit(rule: Any) -> str | None:
    """The unit beside the printed quantity: per-unit's own UoM, `meter` for a
    per-meter rule, nothing for percent and flat (they print no quantity)."""
    if getattr(rule, "per_unit_amount", None) is not None:
        return getattr(rule, "per_unit_uom", None)
    if getattr(rule, "per_meter_amount", None) is not None:
        return METER_COUNT_UNIT
    return None


def _meters_in_scope(rule: Any, source: FinalizedLines) -> Decimal:
    """🔒 `DEF-RAT-9278` — HOW MANY METERS a per-meter tax is charged on.

    Per service in the tax's scope (`applies_to_services`, empty = the whole
    bill — the same meaning every other form gives it): the distinct
    `asset_id`s on that service's USAGE lines, or ONE where it has usage lines
    and none carries an id. A service with no usage line contributes nothing.
    See the module docstring for the worked figures.
    """
    meters: dict[str, set[str]] = {}
    for line in _usage_lines_in_scope(rule, source):
        ids = meters.setdefault(str(line.service), set())
        asset_id = getattr(line, "asset_id", None)
        if asset_id:
            ids.add(str(asset_id))
    return Decimal(sum(len(ids) or 1 for ids in meters.values()))


def _usage_lines_in_scope(rule: Any, source: FinalizedLines) -> tuple[Any, ...]:
    """The USAGE lines a per-unit tax is levied on — its services', or the bill's.

    The same field the percent form narrows its base by (`applies_to_services`,
    R7) and the same meaning: empty = the whole bill. Filtered on KIND, so a base
    charge, a fee, a deposit or a discount can never contribute a quantity —
    exactly as `finalize.taxable_base` filters money.
    """
    services = tuple(getattr(rule, "applies_to_services", ()) or ())
    return tuple(
        line
        for line in source.lines
        if line.kind == KIND_USAGE and (not services or line.service in services)
    )


def _taxed_quantity(rule: Any, source: FinalizedLines) -> Decimal | None:
    """BR-RAT-036 per-unit + BR-RAT-042 marginal — HOW MANY UNITS ARE TAXED.

    `None` for every rule that is not per-unit: a percent or flat line has no
    quantity, and printing `0` beside one would be a figure that does not exist.

    THREE REFUSALS, and each is a fact somebody must fix rather than a number
    this stage may invent:

      * **no unit stated** — CLAUDE.md hard rule 3. `$0.25` per WHAT.
      * **a usage line in its scope measured in another unit** — kWh cannot be
        added to kgal (BR-RAT-038's *"no silent conversion"*). This is what an
        UNSCOPED per-unit tax meets on a multi-service bill, and the refusal
        names both units and asks for the scope.
      * **a usage line in its scope with no measured quantity** — a
        percent-of-service line is priced from another service's DOLLARS
        (BR-RAT-015) and measures nothing, so it cannot contribute units. Its
        presence in the scope means the scope is wrong.

    **Worked:** `5 + 10 + 3.72 = 18.72 kgal` above a threshold of `15` is
    `3.72`. With no threshold stated it is the whole `18.72`. Below the
    threshold it is `0`, and `0 x 0.25 = 0.00` is a REAL answer — the authority
    levies nothing on a customer who stayed under — which is why this returns
    zero rather than refusing, and why the line still prints: BR-RAT-042 makes
    the surcharge apply to the account, at zero units.
    """
    if getattr(rule, "per_meter_amount", None) is not None:
        return _meters_in_scope(rule, source)
    if getattr(rule, "per_unit_amount", None) is None:
        return None
    unit = getattr(rule, "per_unit_uom", None)
    if not unit:
        raise TaxRuleUnpriceable(
            # CLAUDE.md hard rule 3 — the id stays here, out of the sentence.
            f"per-unit tax rule {rule.code!r} charges {rule.per_unit_amount} per unit "
            "and no unit of measure is recorded with it, so there is nothing to charge "
            "it per. Set the unit on the tax."
        )
    total = Decimal("0")
    for line in _usage_lines_in_scope(rule, source):
        if line.quantity is None or line.unit is None:
            raise TaxRuleUnpriceable(
                # BR-RAT-015 — a percent-of-service line is priced from another
                # service's dollars and measures nothing.
                f"per-unit tax rule {rule.code!r} is charged per {unit!r} and the line "
                f"{line.description!r} has no measured quantity, so it cannot contribute "
                "any. That line is priced as a percentage of another service rather than "
                "from a meter. Restrict this tax to the services it is charged on."
            )
        if line.unit != unit:
            raise TaxRuleUnpriceable(
                # BR-RAT-038 — no silent conversion; the engine holds no factor.
                f"per-unit tax rule {rule.code!r} is charged per {unit!r} and the line "
                f"{line.description!r} is measured in {line.unit!r}. The two cannot be "
                "added and nothing here converts between them. Restrict this tax to the "
                "services it is charged on — '$0.25 per kgal' is a statement about "
                "water, not about a bill that also carries electricity."
            )
        total += line.quantity
    threshold = getattr(rule, "applies_above_units", None)
    if threshold is None:
        return total
    # BR-RAT-042 (CONFIRMED, PO closing OQ-054 option (a)): MARGINAL. Only the
    # units ABOVE the threshold are taxed — never the whole quantity once the
    # threshold is passed, which on the worked bill is the difference between
    # $0.93 and $4.68. The threshold is NOT scaled by the period factor; see the
    # module docstring and DEF-2702.
    above = total - Decimal(threshold)
    return above if above > 0 else Decimal("0")


def _tax_amount(rule: Any, taxable_subtotal: Decimal, source: FinalizedLines) -> Decimal:
    """The one place a tax rule becomes a number (BR-RAT-036's THREE built forms).

    FLAT FIRST, and the order is the rule rather than a preference: a flat
    amount is an absolute figure the authority set, and multiplying it by
    anything — or falling back to a percent when both are somehow present —
    would produce a number nobody chose. PER-UNIT next, for the same reason: it
    is a rate on a QUANTITY and bears no relation to the money subtotal, so a
    rule that states one must never fall through to a percent. A rule carrying
    none of the three REFUSES (hard-won law 3: the unsafe option must be the one
    you type); it is never priced at 0.00, because a $0.00 tax line is a claim
    that the authority charges nothing.
    """
    flat = getattr(rule, "flat_amount", None)
    if flat is not None:
        return Decimal(flat)
    per_unit = getattr(rule, "per_unit_amount", None)
    if per_unit is not None:
        # BR-RAT-036 per-unit x BR-RAT-042 marginal. UNROUNDED — `finalize_line`
        # is the one rounding event (BR-RAT-003), exactly as for the percent
        # form beside it.
        return Decimal(per_unit) * (_taxed_quantity(rule, source) or Decimal("0"))
    per_meter = getattr(rule, "per_meter_amount", None)
    if per_meter is not None:
        # BR-RAT-036's fourth form (DEF-386 / DEF-RAT-9278). UNROUNDED, like
        # every form here — `finalize_line` is the one rounding event.
        return Decimal(per_meter) * _meters_in_scope(rule, source)
    if rule.rate is None:
        raise TaxRuleUnpriceable(
            # BR-RAT-036 gives a tax exactly one computation form.
            f"tax rule {rule.code!r} carries no percent rate, no flat amount and no "
            "per-unit amount, so there is no arithmetic to perform. A tax has exactly "
            "one form of calculation and this one states none."
        )
    return taxable_subtotal * rule.rate


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: each tax line names the TAX that produced it, so it can resolve its authority's own 2200 account) · AMENDED 2026-10-03 by the CR-165-BRC10 round 2 back-end lane (DEF-RAT-9278: the per-meter form — `_meters_in_scope`, `_printed_unit`)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1/10/11 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: (1) ⚠ THIS LINE READ "flat-per-bill and per-unit tax forms (BR-RAT-036, PROPOSED) are NOT implemented — the seam's TaxRule carries only a percent rate" AND BOTH ARE NOW BUILT (flat 2026-08-18; per-unit 2026-08-31, CR-052 W5 task 16). The FOURTH form, per-METER, is BUILT 2026-10-03 (DEF-RAT-9278, CR-165-BRC10 round 2 — amount x meters in scope; HUMAN-REVIEW-PENDING, ledger row 2026-10-03). What is still unbuilt of BR-RAT-036 as amended is the compounding half (DEF-381, deliberately deferred: a tax that taxes itself in a circle needs a cycle guard). (2) B5 GT-1/GT-10 name ONE combined 8.25% rate and never decompose it into jurisdictions, so one rule produces one tax line; the per-jurisdiction split of US-RAT-013 §4 is not frozen and is not invented here. (3) The exemption EXPIRY branch (US-RAT-013 TC-8, BR-CUS-063) needs an expiry date the seam's AccountContext does not carry — REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
