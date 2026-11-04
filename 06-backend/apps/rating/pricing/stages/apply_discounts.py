# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-502 (discounts were priced by NOTHING on the bill path — the
#           pipeline had no discount stage at all; the PO found it by reading
#           the stage list aloud)
# Rules:    BR-RAT-071 (R6 before R7 — discounts apply BEFORE taxes and each
#           tax picks its own base) · BR-RAT-068 (an OVERLAY: the bill shows
#           the full tariff amount and the reduction as its own line) ·
#           BR-RAT-069/110 (enrolment grants; the caller has already applied
#           the plan-binding gate) · BR-RAT-106 (treatment per tax — this stage
#           returns the PAIR, it never picks) · BR-RAT-003 (the reduction is a
#           bill line, rounded like one — by `discount_pricing`, once) ·
#           BR-BIL-037 as amended 2026-08-22 (run stage 5: apply-discounts) ·
#           BR-BIL-039 (pure — no writes, no clock; everything time-dependent
#           was resolved at gather)
# Tests:    06-backend/tests/test_def_502_discount_stage.py ·
#           tests/test_cr013_discounts.py (the arithmetic's own 47 cases)
# Impacts:  apps/rating/engine.py 🔒 (the only caller) ·
#           apps/rating/discount_pricing.py (the LAW this stage wires) ·
#           apps/billing/stages/assemble_document.py (stores the line)
# ───────────────────────────────────────────────────────
"""Stage: apply-discounts — R6 wired onto the live bill. HUMAN-OWNED 🔒.

HUMAN-REVIEW-PENDING — AI-authored 2026-08-22 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Rating math is a
CLAUDE.md sensitive path; row in 12-governance/09-human-review-ledger.md.

THIS STAGE COMPUTES NOTHING. `apps/rating/discount_pricing.price_discounts` is
the R6 arithmetic — six rules, 47 tests, written 2026-08-19 and called by
nothing on the bill path until this stage existed (DEF-502: *"both ends are
built and tested, so every test passes"*). This module BUILDS ITS INPUTS from
the stage contract and PLACES ITS OUTPUT as bill lines; every figure is the law
module's.

WHERE IT RUNS, AND WHY THERE (the placement is a recorded decision — decision
log 2026-08-22; B4 ❄ was grepped for "discount" and is SILENT, so the signed
sources are BR-RAT-071 and the §A2 chain):

    apply_charges → finalize → **apply_discounts** → compute_tax

  * AFTER finalize, because BR-RAT-068 makes a scoped percentage *"a
    percentage of what is printed"* — the reduction is computed over the
    FINALIZED (2dp) tariff line amounts, exactly as `discount_pricing`'s rule
    4 states, so a customer who applies −10% to the printed lines reaches the
    printed reduction.
  * BEFORE compute_tax, because BR-RAT-071 puts R6 before R7 — and because
    BR-RAT-106 then lets EACH TAX choose its base, this stage hands compute-tax
    the PAIR (`taxable_subtotal` untouched as `subtotal_before`, plus
    `discount_reduction_taxable`) rather than a single reduced number. A stage
    that netted the subtotal would have chosen one statute for every authority
    in the product, which is the exact failure BR-RAT-106 exists to forbid.

WHAT THE DISCOUNT IS COMPUTED OVER — the TARIFF lines only. usage + base +
minimum-adjustment kinds (the B4.2 tax-base kinds): BR-RAT-068's overlay
*"references the plan's normal schedules and reduces the subtotal"*. FEES and
DEPOSITS are excluded — a late fee is a fact about the account, not a tariff
line, and a deposit is the customer's own money; discounting either has no
signed rule. A `named_codes` scope selects the tariff lines carrying a named
charge code — today the BASE line, stamped with its code (`DEF-RAT-9327`,
2026-10-03; until then this stage REFUSED the whole bill, because the code did
not travel). A named code that can never be on a tariff line (a fee) is
refused at APPROVAL, where a clerk is looking, so a scope cannot silently
select nothing — the failure BR-RAT-068's *"subsidy granted is reportable"*
exists to prevent.

WHAT IS DROPPED, STATED RATHER THAN HIDDEN: `DiscountOutcome.denied` (the
per-discount denial reasons) and `.exhausted` (the codes whose budget crossed
zero) do not survive this stage today. The denials are a support-screen
feature with no story; the exhaustion status-flip is a WRITE a pure stage may
not perform (BR-BIL-039) and is filed as its own defect row (2026-08-22)
rather than wired here as a side effect.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating import discount_pricing
from apps.rating import discounts as discount_models
from apps.rating.pricing import errors
from apps.rating.pricing.contracts import (
    KIND_BASE,
    KIND_DISCOUNT,
    KIND_MINIMUM_ADJUSTMENT,
    KIND_USAGE,
    FinalizedLines,
    PricedLine,
)

ZERO = Decimal("0")

#: The kinds a discount reduces — the tariff lines (BR-RAT-068's overlay), and
#: deliberately the same set as the B4.2 tax base, because `discount_pricing`'s
#: `subtotal_after` must be derivable from `taxable_subtotal` by subtraction
#: (see `_reduction_taxable` below).
DISCOUNTABLE_KINDS = frozenset({KIND_USAGE, KIND_BASE, KIND_MINIMUM_ADJUSTMENT})

#: How a PricedLine kind maps onto `discount_pricing.BillLine.kind`
#: (`base | usage | other` — what the four scopes select on).
_BILL_LINE_KIND = {KIND_USAGE: "usage", KIND_BASE: "base", KIND_MINIMUM_ADJUSTMENT: "other"}


def apply_discounts(source: FinalizedLines) -> FinalizedLines:
    """R6 over one bill's finalized lines. PURE — and identity when there is
    nothing to do, so every undiscounted bill (every B5 fixture included) is
    byte-identical to the pre-DEF-502 output."""
    rules = tuple(getattr(source.normalized, "discounts", ()) or ())
    if not rules:
        return source

    # 🔒 DEF-RAT-9327 (2026-10-03) — a `named_codes` scope used to REFUSE here,
    # for every enrolled account, because the priced lines carried no charge
    # code to select on. That refusal stopped the WHOLE bill (a `BillRunBreak`)
    # for a discount approval had accepted: the walk's Mia Okafor, enrolled in a
    # Lead line waiver on `BASE-W`, got no October bill at all. The code now
    # travels — `billing.gather` always sent it as `TariffConfig.base_charge_code`
    # and `price_usage` stamps it on the BASE line — so the law module's own
    # `named_codes` branch (`discount_pricing._scoped_base`) selects it, and
    # BR-RAT-068 decides the figure: a scoped discount is taken over the TARIFF
    # lines in its scope. Worked: $60.00 bill, waiver on `BASE-W` → −$8.00 →
    # $52.00, the $8.00 base still printed. A code that can never be on a
    # tariff line (a FEE — fees are never discounted, decision log 2026-08-22)
    # is refused when the discount is APPROVED
    # (`discount_services._refuse_unpriceable`), never here at a bill run.

    tariff_lines = tuple(line for line in source.lines if line.kind in DISCOUNTABLE_KINDS)
    if any(not line.taxable for line in tariff_lines):
        # Unreachable today — every usage/base/minimum line the engine emits is
        # taxable=True — and guarded rather than assumed: `_reduction_taxable`
        # below equates "what the discount reduced" with "what left the tax
        # base", which is only true while the two line sets coincide. A future
        # non-taxable tariff line under a discount would need an attribution
        # rule nobody has signed, so it refuses by name instead of drifting.
        raise errors.DiscountRefused(
            "this bill carries a tariff line that is outside the tax base "
            "(taxable=False), and a discount is present. The discount stage derives each "
            "tax's reduced base by subtracting the reduction from the taxable subtotal "
            "(BR-RAT-106), which is only sound while every discounted line is in that "
            "base. No signed rule states how to attribute a reduction across "
            "taxable and non-taxable tariff lines, so the bill refuses rather than "
            "computing a tax base by a rule nobody signed."
        )

    bill_lines = tuple(
        discount_pricing.BillLine(
            service=line.service or "",
            kind=_BILL_LINE_KIND[line.kind],
            amount=line.amount,
            # DEF-RAT-9327 — the base line's charge code (`BASE-W`); None on usage.
            charge_code=getattr(line, "charge_code", None),
        )
        for line in tariff_lines
    )

    try:
        outcome = discount_pricing.price_discounts(
            lines=bill_lines,
            rules=tuple(_law_rule(rule) for rule in rules),
            currency=source.normalized.subscription.currency,
        )
    except discount_pricing.DiscountPricingError as refusal:
        # Every R6 refusal — the unpriceable types, the foreign-currency
        # credit, AND `DiscountBudgetExhausted` — becomes ONE account's named
        # break. CR-013 part 3 says the run "raises an exception when budget is
        # exhausted mid-run", and it does: every enrolled account's bill
        # refuses with this sentence and nobody is quietly charged full price.
        # What it does NOT do is kill the other 499 accounts' bills, because
        # BR-BIL-055 (a break never blocks the run; DEF-047's lesson) is
        # billing law. Recorded judgment — decision log 2026-08-22.
        # ⚖️ SINCE 2026-10-04 A SPENT BUDGET NO LONGER REACHES THIS LINE:
        # `BR-RAT-075` "suspend" is SUPERSEDED (PO: *"We cannot hold the bill;
        # we need to make discount value to 0 and move on - we cannot stop the
        # billing"*) and `discount_pricing` denies it as a $0.00 discount. The
        # remaining refusals here (unpriceable type, foreign currency) are
        # configuration errors, not money running out.
        raise errors.DiscountRefused(str(refusal)) from refusal

    if not outcome.applied:
        return source

    names = {
        getattr(rule, "code", ""): (getattr(rule, "name", "") or getattr(rule, "code", ""))
        for rule in rules
    }
    discount_lines = tuple(
        PricedLine(
            kind=KIND_DISCOUNT,
            # DIS-02 step 1: `Discount.name` IS "the bill line label"; the code
            # is the fallback for a rule that crossed the seam without one.
            description=names.get(applied.code) or applied.code,
            # `applied.amount` is the POSITIVE magnitude, already finalized
            # half-up 2dp by `discount_pricing` rule 6 — the reduction IS a
            # bill line and was rounded like one, exactly once. Negated here
            # because on the document it reduces (BR-RAT-068: its own line,
            # beside the full tariff amount).
            amount=-applied.amount,
            taxable=False,  # the treatment question is per TAX (BR-RAT-106)
            service=None,  # an ACCOUNT overlay; no service's revenue line
            # 🔒 DEF-2430 / DEF-BIL-5341 — WHICH PROGRAMME this reduction was
            # granted under, so issue can record it against the enrolment and a
            # yearly cap or budget counts down. The code, never the label.
            discount_code=applied.code or None,
        )
        for applied in outcome.applied
    )

    return FinalizedLines(
        source=source.source,
        lines=source.lines + discount_lines,
        # UNCHANGED — this is `subtotal_before`, the full tariff amount the
        # bill prints (BR-RAT-068). KIND_DISCOUNT is not a TAX_BASE_KIND, so
        # re-summing would give the same figure; stating it keeps the contract
        # explicit.
        taxable_subtotal=source.taxable_subtotal,
        discount_reduction_taxable=outcome.total_reduction(),
    )


def _law_rule(rule) -> discount_pricing.DiscountRule:
    """One seam-shaped rule onto R6's own input contract, field for field.

    Structural `getattr` reads with the law module's own defaults, for the
    reason every seam crossing in this repo gives: the seam's shape is another
    module's contract, and a field it has not grown yet must degrade to the
    documented default rather than to an AttributeError mid-run. NO field is
    invented and NO figure is touched — the value, caps, budget and floor cross
    verbatim; everything time-dependent (in force? verified? budget left?) was
    resolved by `rating.selectors.billable_discount_rules` at gather, so this
    stage keeps no clock (BR-BIL-039).
    """
    return discount_pricing.DiscountRule(
        code=getattr(rule, "code", ""),
        discount_type=getattr(rule, "discount_type", ""),
        value=Decimal(getattr(rule, "value", ZERO)),
        currency=getattr(rule, "currency", ""),
        applies_to=getattr(rule, "applies_to", discount_models.SCOPE_WHOLE_BILL),
        verified=bool(getattr(rule, "verified", True)),
        proof_before_first_reduction=bool(getattr(rule, "proof_before_first_reduction", True)),
        applies_to_service=getattr(rule, "applies_to_service", None),
        applies_to_charge_codes=tuple(getattr(rule, "applies_to_charge_codes", ()) or ()),
        cap_per_bill=_decimal_or_none(getattr(rule, "cap_per_bill", None)),
        cap_year_remaining=_decimal_or_none(getattr(rule, "cap_year_remaining", None)),
        cap_lifetime_remaining=_decimal_or_none(getattr(rule, "cap_lifetime_remaining", None)),
        budget_remaining=_decimal_or_none(getattr(rule, "budget_remaining", None)),
        exhaustion_behaviour=getattr(
            rule, "exhaustion_behaviour", discount_models.EXHAUSTION_SUSPEND
        ),
        bill_floor_amount=Decimal(getattr(rule, "bill_floor_amount", ZERO) or ZERO),
        stacking_precedence=int(getattr(rule, "stacking_precedence", 100)),
        stacks_with_others=bool(getattr(rule, "stacks_with_others", True)),
        exclusivity_group=getattr(rule, "exclusivity_group", None),
    )


def _decimal_or_none(value) -> Decimal | None:
    return None if value is None else Decimal(value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-502 (the full register row, read first) + BR-RAT-068/069/071/106/110
#         verbatim from 06-rating/02-business-rules.md + B4 ❄ grepped for
#         "discount" (SILENT — recorded) + discount_pricing.py's own INTEGRATION
#         note + decision log rows 2026-08-22 (placement · scoped-tax refusal ·
#         exhaustion-as-break)
# generated: 2026-08-22 by the W9a DEF-502 lane (discounts reach the bill)
# checklist: A✔ B✔ C✔ D=n/a(pure stage) E=n/a(no screen half in this wave) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 rating math, HUMAN-REVIEW-PENDING,
#         ledger row appended)
# gates: ruff✔ black✔ · tests/test_def_502_discount_stage.py (proved RED first —
#         the seam had no DiscountRule to even construct) · golden-verify 33/33
#         before AND after (a discount is a new line; no frozen figure moves,
#         and every B5 fixture passes no discounts so this stage is identity)
# exceptions: (1) `named_codes` REFUSED here until DEF-RAT-9327 (2026-10-03);
#         it now selects the base line by its charge code. (2) `DiscountOutcome.denied` and
#         `.exhausted` are dropped — denials have no screen yet; the exhaustion
#         status flip is a write a pure stage may not do (filed 2026-08-22).
#         (3) [SUPERSEDED 2026-10-04 — a spent budget is a $0.00 discount and
#         the bill goes out, BR-RAT-075] budget exhaustion under `suspend` is ONE account's break, not a
#         run abort — BR-BIL-055 over CR-013 part 3's letter, recorded in the
#         decision log with the reasoning.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
