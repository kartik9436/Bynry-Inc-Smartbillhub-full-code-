# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (BR-BIL-037 stage 4)
#           Screens: — (charge/fee lines render in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-005 (fees are never taxed — they arrive here and stay out of
#           the base by KIND) · BR-RAT-028 (minimum bill: per-service first,
#           then the plan floor — the slot this stage owns) · BR-RAT-045
#           (charge amounts come from the amount-rule plugins) · BR-BIL-037
#           (stage 4: ChargedLines out) · BR-BIL-039 (pure)
# Golden:   GT-10 · GT-11 (a late fee present on the bill, outside the tax base)
#           — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_013_totals.py
# Impacts:  apps/rating/pricing/stages/finalize.py (its sole consumer)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

Stage 4 — apply-charges: the priced lines, plus everything charged after them.

WHY A FEE IS AN INPUT AND NOT AN OUTPUT
---------------------------------------
B4.2's claim is structural: a fee sitting on the bill must not reach the tax
base. The only way to test a structural claim is to hand the engine a fee and
watch it stay out (GT-10 / GT-11; US-RAT-013 TC-1 words the fixture the same
way). So billing computes its charge and fee lines and passes them in; this
stage places them AFTER the priced lines and before tax, which is the order
BR-RAT-049 states for the whole family and the order GT-10 asserts by asking
that the total minus the fee equals the taxed part.

THE MINIMUM-BILL ADJUSTMENT — BR-RAT-028, BOTH MODES (CR-052 W1, 2026-08-30)
----------------------------------------------------------------------------
⚠ **THE PARAGRAPH THAT USED TO SIT HERE IS NOW FALSE AND IS QUOTED RATHER THAN
DELETED (hard-won law 1).** It read: *"The minimum-bill adjustment
(BR-RAT-016/028, GT-13) belongs here — per-service minimums first, then the plan
floor tops up. It is NOT implemented: neither the per-service minimum
(`plan_services.minimum_amount`) nor the plan floor (`plans.minimum_bill_amount`)
can travel on the seam's `TariffConfig` today, so there is no input to apply.
Emitting the line would require inventing the threshold."* It was REPORTED
rather than approximated, for three weeks, and on 2026-08-30 the seam was
extended (CR-052 task 4) and both thresholds arrived. The rule is now applied.

⚠ **AND ONE COLUMN NAMED IN THAT QUOTE NO LONGER EXISTS — 2026-09-10.** PO
ruling, *"set it in rates and use it in plans - thats it - this is rule"*:
`plan_services.minimum_amount` is gone (`rating/0030` moves every stated figure
onto the attached rate schedule's versions, `0031` removes the column) and mode
(A) is now `tariff_versions.minimum_bill`. **The quote is left verbatim because
that is what a quote is for**; this note exists so a lane grepping the old column
name does not conclude it is still there. `BR-RAT-028` is AMENDED, not re-signed:
the arithmetic below is untouched and `GT-13`/`GT-19` still describe it.

⚠ **AND MODE (A)'S SOURCE MOVED AGAIN ON 2026-10-01 — PER METER SIZE.** PO,
option A: *"A · Minimum per size - this is correct"* (`DEF-RAT-8737`). The
figure that reaches `config.minimum_amount` is now the rate schedule's minimum
for the connection's SIZE (`rate_size_rows`, via `selectors._size_minimum`),
and `tariff_versions.minimum_bill` is no longer billed. Water — Residential at
1 kgal: 5/8" `$12.41` → **$15.00** under a 5/8" minimum of `$15.00`; 2"
`$32.41` → **$40.00** under `$40.00`; a size with *No minimum* stays `$12.41`.
Nothing in this file's arithmetic changed for it: this stage reads the config,
never a column.

**THE RULE, VERBATIM (BR-RAT-028, CONFIRMED — PO Q&A R5+R6):** *"Minimum bill:
both modes built — (A) per-service minimum and (B) plan-level minimum floor;
plan config chooses either or both. Combination rule when both set: per-service
minimums apply first, then the plan floor tops up the total."*

**MODE A IS THIS FUNCTION.** `apply_charges` runs ONCE PER SERVICE (see
`engine.price_bill`'s per-service loop), so "per service" is not a filter this
code applies — it is the shape of the call. The basis is Σ of the service's own
TAX_BASE_KINDS lines (usage + base, and capacity, which BR-RAT-029 makes a base
line structurally), which is BR-RAT-047's `service_subtotal.<service>`, *"usage
+ base + minimum adjustment — BR-RAT-028 mode-A basis"*, named in the closed
formula vocabulary.

**MODE B IS `plan_floor_line`**, which this stage owns and `engine.price_bill`
calls once over the finalized union — because a floor over "the total" is not a
fact any single service's pass can see.

**THE ADJUSTMENT IS TAXABLE, AND STRUCTURALLY SO.** B4's OQ-007 addendum makes
the *"minimum bill adjustment"* line *"taxable like base"*, and both signed
examples put the tax on the MINIMUM rather than on the subtotal — GT-13's *"tax
on $25.00"* and WE-3's *"tax on 15.00 = 1.42"*. The line carries
`KIND_MINIMUM_ADJUSTMENT`, which is one of the three kinds in `TAX_BASE_KINDS`,
so it enters a percent base for the same structural reason a base charge does
and a fee still cannot (BR-RAT-005).

**A FEE NEVER HELPS A BILL REACH ITS FLOOR**, and that falls out of the same
kind rule rather than being coded: fees are `KIND_FEE`, which is not a
TAX_BASE_KIND, so a $20 late fee on a $9.60 water bill leaves the shortfall at
$5.40. Charging a customer a minimum they only "reached" because they were
penalised would be a second charge wearing the first one's name.

**COMPARED UNROUNDED, AND THAT IS THE DOCUMENTED ORDER RATHER THAN A CHOICE.**
B4.4 rounds at finalization only, and this stage is upstream of it, so the
comparison and the shortfall are full-precision Decimals and the ADJUSTMENT is
rounded once, with every other line, by `finalize`. No signed figure
distinguishes the two readings — WE-3's `1.60 + 8.00` and GT-13's `6.10 +
12.00` are exact at both precisions — so the ambiguity is REPORTED here rather
than left implicit.

**A BASE-ONLY SERVICE IS EXEMPT FROM MODE A — RULED, NOT INVENTED (OQ-1166
CLOSED, PO 2026-08-30).** ⚠ The paragraph this replaces said the opposite and
is quoted here rather than deleted (hard-won law 1), because a reader who greps
for the old sentence must find out what happened to it: *"A BASE-ONLY service …
reaches this stage with its base line and no usage line, and BR-RAT-028 states
no exception for it. So the rule is applied AS WRITTEN and the consequence is
filed rather than quietly avoided: on BR-MET-101's building, six empty units
taking water at an `$8.00` base under a `$15.00` per-service minimum add `$7.00`
each — **`$42.00`** the owner is charged for units nobody occupies. Inventing an
exemption would be as much a guess as inventing the threshold was."*

**It was right to file it and the PO has now answered it**, verbatim: *"when
units are vacant - at that time, we are only charging base rates. minimum rates
are applied when consumer is suppose to use minimum usage, but they end up using
less than what they are suppose ot use"*. The decision log of 2026-08-30 states
the general test the ruling turns on — **a minimum applies when a consumer was
SUPPOSED to use a minimum and used less; a vacant unit was not supposed to use
anything, so there is nothing to fall short of** — and names this row's own
`$42.00` as money that *"should never have been charged"*. That is `OQ-1166`
option (b), and it is one condition, below.

**WHAT THIS DOES NOT TOUCH, STATED SO THE NEXT LANE DOES NOT "FINISH" IT.**

* **Mode B, the PLAN FLOOR, is unchanged.** `OQ-1166` costed the PER-SERVICE
  minimum and the ruling's worked figure is the per-service one; a bill whose
  every line is base-only is a different case with a different figure and no
  ruling behind it. It is filed as `DEF-2822` with its own arithmetic rather
  than swept in here — which is the same discipline that filed this row.
* **No ❄️ B4/B5 figure moves, and that is measured rather than asserted.**
  `WE-3`/`GT-19` is a METERED water household at `0.4 kgal` — it prices a usage
  line, so it is not base-only and never reaches this branch. `10-scripts/
  03-golden-verify.py` reads **33 PASS / 0 FAIL** on both sides of this change.
* **The MINIMUM-USAGE half of the same ruling is not built here.** A minimum
  QUANTITY is a new column and the ruling's other four owed items (a `GT-19`
  re-sign, a time-of-use ruling, a schema decision and a seed move) are
  untouched. This change is only the vacant half, which needs none of them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from apps.rating.pricing.contracts import (
    KIND_FEE,
    KIND_MINIMUM_ADJUSTMENT,
    TAX_BASE_KINDS,
    ChargedLines,
    LineCandidate,
    PricedLines,
)
from apps.rating.pricing.errors import RatingInputError

#: What the customer reads on the line. WE-3 states it verbatim — *"Minimum
#: bill adjustment"* — and it is used for BOTH modes: the per-service line
#: carries `service`, the plan floor's carries None, so which one a reader is
#: looking at is on the line as DATA and not inside a sentence this file made
#: up. Copy is the tenant's and the document's; nothing here invents a second
#: wording for the same charge.
MINIMUM_ADJUSTMENT_DESCRIPTION = "Minimum bill adjustment"


def minimum_basis(lines: Sequence[Any]) -> Decimal:
    """Σ of the amounts BR-RAT-028 measures a minimum against, UNROUNDED.

    The same KIND rule `finalize.taxable_base` uses, so "what the minimum is
    measured against" and "what tax is charged on" are one definition and not
    two — which is what makes GT-13's *"tax on $25.00"* fall out of the
    arithmetic instead of being asserted separately.

    Accepts `LineCandidate`s (mode A, unrounded) and `PricedLine`s (mode B,
    finalized) alike: both carry `kind`, `taxable` and `amount`, and the sum is
    the same shape at either precision.
    """
    return sum(
        (line.amount for line in lines if line.taxable and line.kind in TAX_BASE_KINDS),
        Decimal("0"),
    )


def _adjustment(
    shortfall: Decimal, *, service: str | None, asset_id: str | None = None
) -> LineCandidate:
    return LineCandidate(
        kind=KIND_MINIMUM_ADJUSTMENT,
        description=MINIMUM_ADJUSTMENT_DESCRIPTION,
        amount=shortfall,
        # B4 OQ-007 addendum: taxable like base. Set explicitly AND carried by
        # KIND, because `finalize.taxable_base` requires both — a line that
        # said True here and carried the wrong kind would still stay out of the
        # base (US-RAT-013 TC-7's structural claim, from the other side).
        taxable=True,
        # No quantity, no unit and no unit price: a minimum adjustment is not
        # a measurement of anything (hard rule 3 — a quantity carries its unit,
        # and this line has no quantity to carry one).
        service=service,
        # ── DEF-BIL-8150 · THE TOP-UP NAMES THE METER IT TOPS UP ─────────────
        # PO 2026-09-30 ("ONE-TIME BILL: SIX ANSWERS" (4)), verbatim: *"consider
        # them 2 lines anc charge"* — with two meters on one service the
        # minimum applies to EACH meter. The arithmetic already did (one config
        # per meter, so one shortfall per meter); what was lost was WHICH meter:
        # the line carried no `asset_id`, so the bill printed meter B at $6.00
        # beside an unattributed $4.00. Worked: minimum $10.00, meter A $14.00,
        # meter B $6.00 → meter A $14.00, meter B $6.00 + $4.00 = $10.00, bill
        # $24.00. Identity, never arithmetic — `None` on every one-meter service
        # and on the plan floor, exactly as before.
        asset_id=asset_id,
    )


def minimum_adjustment_line(
    lines: Sequence[Any],
    minimum: Decimal | None,
    *,
    service: str | None,
    base_only: bool = False,
    asset_id: str | None = None,
) -> LineCandidate | None:
    """BR-RAT-028's top-up for one basis, or None when none is owed.

    None when: no minimum is stated (`None`, which is every tariff in the
    database before CR-052), the basis already meets it, there is no line of a
    measured kind at all, or the service is **BASE-ONLY** (OQ-1166, PO
    2026-08-30 — see this module's docstring). **Never a `$0.00` line** — a bill
    that carries an empty adjustment row states that a minimum bit when it did
    not.

    `base_only` defaults False so that every caller which does not know about
    vacancy keeps the behaviour it had; the one caller that DOES know is
    `engine.price_bill`, which is the only place the flag exists at all.
    """
    if base_only:
        # OQ-1166 (b), PO 2026-08-30. A vacant unit and a vacation hold are the
        # two services that reach this stage with a base line and no usage line
        # ON PURPOSE — the customer has been told they are paying the base and
        # no more. There is no shortfall because there was no expected usage to
        # fall short of, so the top-up is not merely waived: it never had a
        # basis. Measured: six empty units at an $8.00 water base under a
        # $15.00 per-service minimum stop being charged $7.00 each — $42.00 a
        # month off one owner's bill.
        return None
    if minimum is None:
        return None
    if not any(line.kind in TAX_BASE_KINDS for line in lines):
        # Nothing was priced for this basis. A minimum tops UP charges; with no
        # charge to top up, emitting the whole minimum would be charging a
        # customer the floor for a service that priced nothing at all, which no
        # signed rule asks for.
        return None
    shortfall = Decimal(str(minimum)) - minimum_basis(lines)
    if shortfall <= 0:
        return None
    return _adjustment(shortfall, service=service, asset_id=asset_id)


def plan_floor(configs: Iterable[Any]) -> Decimal | None:
    """BR-RAT-028 mode B — the ONE plan floor governing this bill, or None.

    Every tariff of one plan carries the same figure (see the seam's own note
    on `TariffConfig.plan_minimum_bill_amount`), so the ordinary answer is the
    single distinct value.

    **TWO DIFFERENT FLOORS REFUSE.** A master's bill can carry tariffs from
    more than one plan (BR-CUS-014: the unit's plan is the unit's), and nothing
    signed says which plan's floor governs a combined total — taking the first
    one reached is exactly how DEF-154 charged `$0.00` for base on every bill.
    It refuses here, by name, rather than producing a plausible number.
    """
    stated = {
        Decimal(str(value))
        for value in (getattr(config, "plan_minimum_bill_amount", None) for config in configs)
        if value is not None
    }
    if not stated:
        return None
    if len(stated) > 1:
        raise RatingInputError(
            "BR-RAT-028 mode B: this bill's tariffs state "
            f"{len(stated)} different plan minimum-bill floors "
            f"({', '.join(format(value, 'f') for value in sorted(stated))}) and the rule "
            "says the plan floor tops up THE TOTAL — one total, one floor. A bill "
            "carrying tariffs from two plans (BR-CUS-014/170) has no signed answer to "
            "which plan's floor governs it, so this refuses rather than charging the "
            "first floor it reached."
        )
    return stated.pop()


def plan_floor_line(lines: Sequence[Any], floor: Decimal | None) -> LineCandidate | None:
    """Mode B's top-up over the WHOLE bill's finalized lines, or None.

    Called ONCE, by `engine.price_bill`, after every service has been priced
    and finalized — which is why it is a separate entry point rather than part
    of `apply_charges` above: a per-service pass cannot see the total, and the
    combination rule is explicit that the floor comes SECOND, over a subtotal
    that already contains every per-service adjustment.
    """
    return minimum_adjustment_line(lines, floor, service=None)


def place_before_fees(lines: Sequence[Any], line: Any) -> tuple[Any, ...]:
    """Insert `line` after the tariff charges and before the first fee.

    Bill order is usage → base → minimum adjustment → fee → tax (BR-RAT-049
    states the evaluation order the same way: *"after … the minimum-bill
    adjustment, and before tax"*). Appending instead would print the top-up
    below a late fee, where it reads as another penalty.
    """
    ordered = list(lines)
    for position, existing in enumerate(ordered):
        if existing.kind == KIND_FEE:
            ordered.insert(position, line)
            return tuple(ordered)
    ordered.append(line)
    return tuple(ordered)


def apply_charges(source: PricedLines, *, base_only: bool = False) -> ChargedLines:
    """Priced lines, the BR-RAT-028 mode-A top-up, then charge/fee lines.

    UNROUNDED throughout. Fees ride on the normalized input (BR-BIL-037: a
    stage receives its predecessor's output and nothing else), so this stage
    can be executed from a fixture with no orchestrator and no database.

    A tariff stating no per-service minimum adds no line, which is every tariff
    in the database before CR-052 and therefore every ❄️ B5 figure: the tuple
    below is byte-identical to `source.lines + source.normalized.fees`.

    `base_only` is the ONE fact this stage cannot derive from its predecessor's
    output and must therefore be told (OQ-1166, PO 2026-08-30). It is not
    inferable from `source`: a base-only service and a metered service that
    happened to consume nothing can both arrive with no usage line, and they
    bill DIFFERENTLY — the metered zero is a customer who fell short of a
    minimum, the base-only one is a customer who was never expected to use
    anything. Passing it explicitly is BR-BIL-037's exception stated in the
    open rather than a heuristic that guesses wrong on the day it matters.
    """
    adjustment = minimum_adjustment_line(
        source.lines,
        source.normalized.config.minimum_amount,
        service=source.normalized.subscription.service,
        base_only=base_only,
        # DEF-BIL-8150 — the meter this config was priced for, when the service
        # carries two (stamped the way `price_usage` stamps the usage line).
        asset_id=getattr(source.normalized.config, "asset_id", None),
    )
    charges = () if adjustment is None else (adjustment,)
    return ChargedLines(source=source, lines=source.lines + charges + source.normalized.fees)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-30 by the CR-052 W1 lane (BR-RAT-028 both modes: `minimum_adjustment_line` mode A per service, `plan_floor` + `plan_floor_line` mode B over the bill, `place_before_fees` for bill order — the hole this file named for three weeks is closed and the paragraph that named it is quoted above, not deleted) · AMENDED 2026-08-31 by the CR-052 W0 task 2 lane (OQ-1166 closed as (b): `minimum_adjustment_line` and `apply_charges` take `base_only`, handed down by `engine.price_bill`, the one caller that knows it — passed and never inferred, because a base-only service and a metered service that consumed nothing both arrive with no usage line and bill DIFFERENTLY)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-10/GT-11 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# AMENDED 2026-09-30 by the one-time-bill defect lane (DEF-BIL-8150, PO "SIX ANSWERS" (4)): the mode-A top-up carries the priced config's `asset_id`, so a per-meter minimum names its meter on the stored line — identity only, no figure moves; HUMAN-REVIEW-PENDING, ledger row 2026-09-30.
# exceptions: (1) BR-RAT-016/028 is now IMPLEMENTED, both modes — the exceptions line here used to say it was not, and that sentence is quoted in the docstring above rather than deleted (hard-won law 1). GT-13 remains a PROPOSED golden test and is asserted in tests/test_br_rat_028_minimum_bill.py alongside WE-3/GT-19 ($16.42), not in 10-scripts/03-golden-verify.py, which reads the DOCUMENT's arithmetic and is unchanged at 33 PASS/0 FAIL. (2) the comparison is UNROUNDED because this stage is upstream of the single rounding boundary (B4.4); no signed figure distinguishes the two readings (WE-3 and GT-13 are exact at both precisions) so the ambiguity is REPORTED, not resolved. (3) ⚠ AMENDED 2026-08-31 — a BASE-ONLY service is now EXEMPT from mode A, because OQ-1166 is CLOSED as option (b) (PO 2026-08-30: "when units are vacant - at that time, we are only charging base rates"). This line read "a BASE-ONLY service is topped up like any other because BR-RAT-028 states no exception — the consequence is filed as OQ-1166 with its worked figure ($42.00 on BR-MET-101's six empty units) rather than an exemption being invented", and it was correct on the day it was written; the exemption is now RULED and not invented. The $42.00 comes off that owner's bill and no ❄️ figure moves (WE-3/GT-19 is a METERED household, so it never reaches the branch). Mode B, the plan floor, is UNCHANGED and still bites on a wholly base-only bill — DEF-2822, filed rather than swept in, because OQ-1166 costed the per-service minimum and that is the figure the PO worked. (4) ⚠ SETTLED 2026-10-01 (DEF-RAT-8737, PO option A, "A · Minimum per size - this is correct"). This read "the schedule-level `tariff_versions.minimum_bill` that `rating.selectors.pricing_inputs` has published since it was written is STILL not read by this stage — DEF-2446 — because BR-RAT-028's field map names the two PLAN columns and nothing signed says what a schedule that also carries one means", and it was stale twice over: the PO ruling of 2026-09-10 made the version's figure mode A (DEF-2446 closed by it, and `gather` read it from then), and the ruling of 2026-10-01 moved mode A again, onto the rate schedule's PER-SIZE minimum (`rate_size_rows`, published as `minimum_bill` by `selectors._size_minimum`); the version's figure is no longer billed and `rating/0053` moved every stated one onto its version's size rows. This stage never read either column — it reads `config.minimum_amount` — so the arithmetic is untouched and WE-3/GT-19 ($16.42) and GT-13 still describe it. Charge-code lines (BR-RAT-041 flat/percent/percent_min) likewise arrive as caller-supplied fee lines until billing's charge-rule reader lands.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
