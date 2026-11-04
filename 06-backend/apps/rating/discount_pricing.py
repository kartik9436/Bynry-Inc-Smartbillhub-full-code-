# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS) · EP-RAT-15 (the R6 step of
#           the resolution chain). No US-ID is cited: the CR-013 epics are not
#           authored yet and G2 refuses an ID that does not resolve.
# Rules:    BR-RAT-068 (overlay, never a rate) · BR-RAT-071 (R6 before R7; the
#           tax picks its own base) · BR-RAT-073 (precedence is data;
#           exclusivity — the larger applies) · BR-RAT-074 (the bill floor) ·
#           BR-RAT-075 (caps, budget, exhaustion) · BR-RAT-076 (proof before
#           the first reduction) · BR-RAT-003 (round at line level) ·
#           BR-RAT-062 (tax is a BILL-level concept)
# Tests:    06-backend/tests/test_cr013_discounts.py
# Impacts:  apps/rating/discount_services.py (the DB-backed caller) ·
#           apps/rating/resolution.resolve_discounts (R6 — the integration
#           point; NOT edited by this lane, see `INTEGRATION` below)
# ───────────────────────────────────────────────────────
"""R6 — the discount overlay, as ARITHMETIC. HUMAN-OWNED 🔒.

HUMAN-REVIEW-PENDING — AI-authored 2026-08-19 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Rating math
and money rounding are CLAUDE.md sensitive paths. Row in
12-governance/09-human-review-ledger.md; this file does not reach lifecycle
RATIFIED without a recorded human sign-off.

WHAT THIS MODULE IS, AND WHAT IT IS NOT
----------------------------------------
It holds NO database access and NO clock, for the same reason
`apps/rating/resolution.py` holds none: the arithmetic can then be tested
exhaustively without a stack, and every figure in CR-013 design §A4 can be
pinned to the cent. The reads — which account is enrolled in what, how much
budget is left, whether the proof is on file — belong to
`apps/rating/discount_services.py`, which builds the `DiscountRule` tuples this
module consumes.

**It also computes no tax.** R6 runs before R7 and hands on a subtotal; CR-013
part 4 makes the DISCOUNT TREATMENT statutory and PER TAX — some authorities
levy on the pre-discount amount — so this module returns BOTH figures (the
subtotal before and after) and lets each tax choose. A module that returned one
number would have chosen for every authority in the product.

THE SIX RULES THIS ARITHMETIC IMPLEMENTS, IN THE ORDER THEY BITE
-----------------------------------------------------------------
1. **PROOF FIRST, IF THE PROGRAMME SAYS SO.** `proof_before_first_reduction`
   with an unverified enrolment yields NO reduction, and the reason is returned
   rather than the line silently vanishing.
2. **EXCLUSIVITY: THE LARGER APPLIES.** r10's SENIOR detail, verbatim: *"Not
   with CAP credit · One assistance program per account — the larger applies."*
   Two discounts sharing an `exclusivity_group` are resolved by computing both
   and keeping the larger reduction; the loser is returned as a DENIAL with its
   reason, because a subsidy an account did not get is a question the customer
   asks.
3. **PRECEDENCE IS DATA, NOT CODE ORDER.** Part 3 gives the reason:
   *"percentage-of-usage after a usage allowance gives a different number than
   the reverse."* Rules run in `stacking_precedence` order, ties broken by code
   so a run is deterministic.
4. **SCOPE DECIDES THE BASE, AND `whole_bill` IS THE ONLY RUNNING ONE.** A
   `whole_bill` percentage takes the RUNNING subtotal — that is what makes
   precedence change the answer. A scoped rule (`usage_only`, `base_only`,
   `one_service`, `named_codes`) takes the sum of the TARIFF lines in its scope,
   undiscounted, because part 3 requires the bill to show *"the full tariff
   amount and the reduction as its own line"* and a percentage of a
   partly-reduced scope is not a percentage of anything printed.
5. **CAPS AND BUDGET TRIM; THE FLOOR STOPS.** Per-bill, per-year and lifetime
   caps and the remaining budget each trim the reduction to what is left; the
   bill floor stops the running subtotal from going below the figure the
   programme states (default 0 — a discount may take a bill to zero, never
   below it, because a negative bill is a CREDIT and no discount may mint one).
6. **ROUND AT LINE LEVEL, HALF-UP, 2dp** (`core.money.finalize`, B4 ❄, and
   CR-013's own *"rates stored to 6 decimals, rounded at line level"*). The
   discount IS a bill line, so it is rounded like one, and the running subtotal
   carries the ROUNDED figure — otherwise the printed lines would not sum to
   the printed total.

⚠ WHAT IS NOT PRICED HERE, NAMED RATHER THAN FAKED
---------------------------------------------------
`rate_override` and `usage_allowance` (two of part 3's five types) are storable
but not priceable — see `discounts.DISCOUNT_TYPES_PRICEABLE`. A rate override
swaps a schedule inside R2 and a usage allowance deducts QUANTITY before R3b's
tier walk, so neither is a subtraction at R6 at all. `price_discounts` REFUSES
such a rule by name rather than treating it as a zero, because a discount that
silently reduces nothing is the failure part 3's whole *"subsidy granted is
reportable"* clause exists to prevent.

⚠ **THE SENTENCE "BOTH ARE ENGINE WORK IN EP-RAT-15" STOOD HERE UNTIL
2026-08-31 AND IS NOW HALF TRUE, SO IT IS REPLACED RATHER THAN LEFT STANDING
(hard-won law 1, CR-052 W5 task 17).** The ARITHMETIC for both is built, where
the CR said it belongs — in the chain's own terms, in
`apps/rating/resolution.py`:

    resolve_schedule_with_override(...)      R2 · the schedule swap
    allowance_deducted_quantity(...)         R3b · the quantity deduction

**Worked, and the second figure is why the placement is the rule.** A `2 kgal`
allowance on water priced `0–5 @ 3.20 / 5–15 @ 4.80 / 15+ @ 7.20` with a meter
reading `18.72 kgal` takes the quantity to `16.72` and the usage from `90.78`
to `76.38` — the allowance is worth **`$14.40`**, because the two kilogallons
come off the TOP block. Handed to THIS module as a money credit at the bill's
average price it would be **`$9.70`**, and the customer would be `$4.70` worse
off for a discount the utility believes it granted.

⚠ **THE PARAGRAPH THAT STOOD HERE UNTIL 2026-08-31 SAID BOTH TYPES WERE BLOCKED
ON `OQ-291` AND `OQ-292`, AND IT IS NOW FALSE — `BR-RAT-962`.** **Both questions
are CLOSED** (PO rulings of that date) and **neither type became priceable**, so
a reader who checked the questions, found them answered, and concluded this
module was merely stale would make a MONEY change believing it was a tidy-up.
Hard-won law 1 is *a comment claiming a guarantee is not the guarantee*; this is
the same failure aimed at a REASON, which decays exactly as quietly.

**WHAT ACTUALLY BLOCKS EACH ONE NOW:**

* **`usage_allowance` — THE STEP, and it is arithmetic.**
  `DISCOUNT_TYPES_PRICEABLE` gates `_raw_reduction` below, which is **R6: a
  subtraction of MONEY from a subtotal.** An allowance deducts **UNITS** before
  R3b's tier walk. Admit it here and the `2 kgal` allowance worked above is
  priced as **`$2.00` off** where the ruled arithmetic makes it **`$14.40`** —
  `$12.40` on one bill, against the customer. `BR-RAT-960` settled WHAT UNIT it
  is measured in (the service's own); it settled nothing about WHICH STEP
  subtracts it, and this module is the wrong step.
* **`rate_override` — NOTHING LEFT TO PRICE.** `BR-RAT-961` ruled that a subsidy
  is the standard schedule plus an ordinary discount line, which removes the
  type's one stated use; `BR-RAT-068` had forbidden the shape since 2026-08-19
  anyway (*an overlay, never a rate*).
* **And `DEF-438` still, for both:** the R1–R7 chain has no production caller, so
  switching a step is the ruled cutover's step 5, gated on its step 4.

**`DISCOUNT_TYPES_PRICEABLE` IS THEREFORE UNCHANGED and activation still refuses
both types** — a `usage_allowance` that activated today would reach the LIVE
path, land in this module, and break every bill for that account on
`DiscountTypeNotPriceable`. **Widening it is a money change, not a clean-up.**

INTEGRATION — HOW R6 GETS WIRED, AND WHY THIS LANE DID NOT WIRE IT
-------------------------------------------------------------------
`apps/rating/resolution.resolve_discounts` currently returns
`DiscountResolution(modelled=False, …)` with a reason naming CR-013 part 3.
That file belongs to the EP-RAT-15 lane, working in this same tree on this same
CR, and it was told to leave R6 explicitly unmodelled — so this lane does not
edit it out from under them. **The integration is two lines when that lane
takes it:**

    from apps.rating import discount_services
    applied = discount_services.r6_enrolled_discounts(account_no, period_end)
    return DiscountResolution(modelled=True, applied=applied)

`r6_enrolled_discounts` returns exactly the `tuple[tuple[str, Decimal], ...]`
that `DiscountResolution.applied` is typed as — code and signed amount, in
applied order — so nothing on the contract has to change. Until that call
exists, no bill carries a discount line, and `resolution.py` says so rather
than reporting an empty list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from apps.rating import discounts as discount_models
from core.money import finalize

ZERO = Decimal("0")
HUNDRED = Decimal("100")


class DiscountPricingError(Exception):
    """Base for every refusal this module makes. Each carries a sentence a
    utility can act on — *"the product cannot express that"* is a defect, not
    an answer (design §A0 promise 2)."""

    step = "R6"


class DiscountTypeNotPriceable(DiscountPricingError):
    """A stored type no engine can price yet (`rate_override`,
    `usage_allowance`). Refused rather than treated as zero."""


class DiscountBudgetExhausted(DiscountPricingError):
    """Part 3, verbatim: *"Run bills applies in precedence order and raises an
    exception when budget is exhausted mid-run."* ⚖️ RAISED BY NOTHING SINCE
    2026-10-04 — `BR-RAT-075` "suspend" is SUPERSEDED (PO: *"We cannot hold
    the bill; we need to make discount value to 0 and move on - we cannot stop
    the billing"*). Kept so an importer of the name does not break; a spent
    budget is a denial ($0.00), never an exception."""


class DiscountCurrencyMismatch(DiscountPricingError):
    """A fixed-amount discount in a currency the bill is not in. Hard rule 2 is
    about the pairing, and a $25 credit on a euro bill is not 25 of anything."""


# ── the facts this module narrows over ──────────────────────────────────────


@dataclass(frozen=True)
class BillLine:
    """One priced tariff line, BEFORE any discount and BEFORE any tax.

    `kind` is `base` | `usage` | `other`, which is what the four scopes select
    on. `charge_code` is the catalogue code (`BASE-W`, `USAGE-E`) so a
    `named_codes` discount can name it; None for a line no charge code produced.
    """

    service: str
    kind: str
    amount: Decimal
    charge_code: str | None = None


@dataclass(frozen=True)
class DiscountRule:
    """One in-force discount version, as R6 needs to see it.

    Built by `discount_services` from `Discount` + `DiscountVersion` +
    `DiscountEnrolment` + the grant history. Everything time-dependent
    (*is it in force? is the proof current? how much budget is left?*) is
    RESOLVED BEFORE it gets here, so this module has no clock and cannot
    disagree with the caller about what day it is.
    """

    code: str
    discount_type: str
    value: Decimal
    currency: str
    applies_to: str
    #: `verified` is the ENROLMENT's state, not the discount's. With
    #: `proof_before_first_reduction` true, an unverified enrolment reduces
    #: nothing — part 3's *"whether proof precedes the first reduction"*.
    verified: bool = True
    proof_before_first_reduction: bool = True
    applies_to_service: str | None = None
    #: `CR-091-BRC01` — the services named by a `specific_services` scope. A
    #: TUPLE of service codes, empty on every other scope. The singular above
    #: is untouched: a stored `one_service` row keeps exactly the meaning it
    #: had, which is the ruling's own requirement.
    applies_to_services: tuple[str, ...] = ()
    applies_to_charge_codes: tuple[str, ...] = ()
    cap_per_bill: Decimal | None = None
    #: What the year's and the lifetime's caps have LEFT, already netted of
    #: what this enrolment has been granted. None = uncapped.
    cap_year_remaining: Decimal | None = None
    cap_lifetime_remaining: Decimal | None = None
    #: What the PROGRAMME has left, netted of every account's grants. None =
    #: no budget cap was typed, which part 3 allows and the PO's second-approval
    #: ruling of 2026-08-19 treats as the largest commitment there is.
    budget_remaining: Decimal | None = None
    exhaustion_behaviour: str = discount_models.EXHAUSTION_SUSPEND
    bill_floor_amount: Decimal = ZERO
    stacking_precedence: int = 100
    stacks_with_others: bool = True
    exclusivity_group: str | None = None


@dataclass(frozen=True)
class AppliedDiscount:
    """One reduction, as it will print on the bill and post to the ledger."""

    code: str
    amount: Decimal  # POSITIVE magnitude of the reduction, rounded to 2dp
    base: Decimal  # what it was computed on, so the line is explicable
    #: Set when the reduction is SMALLER than the rule alone would give, naming
    #: what trimmed it — `cap_per_bill` | `cap_per_year` | `cap_lifetime` |
    #: `budget` | `bill_floor`. Part 3's Budget-&-usage tab asks for exactly
    #: this (*"denials by cap or funding"*).
    trimmed_by: str | None = None


@dataclass(frozen=True)
class DeniedDiscount:
    """A discount the account is enrolled in that reduced NOTHING, and why.

    Returned rather than dropped because *"why did I not get my senior
    discount?"* is a support call, and an answer that requires reading the
    code is not an answer.
    """

    code: str
    reason: str


@dataclass(frozen=True)
class DiscountOutcome:
    """R6's answer for one bill.

    Both subtotals are returned because R7 has not chosen its base yet: CR-013
    part 4 makes discount treatment statutory and PER TAX, so a tax that levies
    on the pre-discount amount reads `subtotal_before` and one that levies on
    the reduced amount reads `subtotal_after`. Returning one figure would have
    decided that for every authority in the product.
    """

    subtotal_before: Decimal
    subtotal_after: Decimal
    applied: tuple[AppliedDiscount, ...] = ()
    denied: tuple[DeniedDiscount, ...] = ()
    #: Codes whose budget ran out to exactly zero under `suspend`, so the
    #: caller can flip the discount to `suspended_funding_exhausted` — the one
    #: status in the product a BILL RUN sets (CR-013 part 3).
    exhausted: tuple[str, ...] = field(default_factory=tuple)

    def total_reduction(self) -> Decimal:
        return sum((line.amount for line in self.applied), ZERO)

    def as_resolution_pairs(self) -> tuple[tuple[str, Decimal], ...]:
        """The shape `resolution.DiscountResolution.applied` is typed as —
        `(code, signed amount)`, NEGATIVE because it reduces. See INTEGRATION
        in the module docstring."""
        return tuple((line.code, -line.amount) for line in self.applied)


# ── the arithmetic ──────────────────────────────────────────────────────────


def _scoped_base(rule: DiscountRule, lines: tuple[BillLine, ...]) -> Decimal:
    """The sum of the TARIFF lines this rule's scope selects, undiscounted.

    Undiscounted deliberately: part 3 requires the bill to show *"the full
    tariff amount and the reduction as its own line"*, so a scoped percentage
    is a percentage of what is printed. Only `whole_bill` runs against the
    reducing subtotal, which is what makes precedence change the answer.
    """
    scope = rule.applies_to
    if scope == discount_models.SCOPE_USAGE_ONLY:
        selected = [line for line in lines if line.kind == "usage"]
    elif scope == discount_models.SCOPE_BASE_ONLY:
        selected = [line for line in lines if line.kind == "base"]
    elif scope in (discount_models.SCOPE_ONE_SERVICE, discount_models.SCOPE_SPECIFIC_SERVICES):
        # ⚠ **`CR-091-BRC01` — ONE EQUALITY BECAME ONE MEMBERSHIP TEST, AND THE
        # SINGULAR STILL MEANS EXACTLY WHAT IT MEANT.** This branch read
        # `line.service == rule.applies_to_service`. A one-element membership
        # test is that equality, so every `one_service` row stored before today
        # prices to the same figure — which is the PO's own requirement (*"The
        # existing `one_service` scope is NOT widened"*), not a happy accident.
        #
        # ⚠ **THE TWO SCOPES DO NOT SHARE A FIELD, ON PURPOSE.**
        # `_wanted_services` reads the singular for `one_service` and the list
        # for `specific_services` and never mixes them, so a row that somehow
        # carried both could not quietly widen the older scope.
        wanted_services = _wanted_services(rule)
        selected = [line for line in lines if line.service in wanted_services]
    elif scope == discount_models.SCOPE_NAMED_CODES:
        wanted = set(rule.applies_to_charge_codes)
        selected = [line for line in lines if line.charge_code in wanted]
    else:
        # `SCOPE_ALL_SERVICES` and `SCOPE_WHOLE_BILL` land here, and they are
        # NOT the same thing: `whole_bill` never reaches this function at all —
        # the caller runs it against the REDUCING subtotal — while
        # `all_services` takes the undiscounted sum of every line, like every
        # other scope in this function. On a bill with one discount the two
        # agree; on a bill with two stacked discounts they do not, which is the
        # choice precedence exists to make visible.
        selected = list(lines)
    return sum((line.amount for line in selected), ZERO)


def _wanted_services(rule: DiscountRule) -> frozenset[str]:
    """Which service codes this rule's scope selects.

    `one_service` reads the SINGULAR column and yields at most one code;
    `specific_services` reads the LIST. Kept apart so neither can widen the
    other by accident — `CR-091-BRC01`, PO ruling 2026-09-10.
    """
    if rule.applies_to == discount_models.SCOPE_SPECIFIC_SERVICES:
        return frozenset(rule.applies_to_services)
    return frozenset() if rule.applies_to_service is None else frozenset({rule.applies_to_service})


def _raw_reduction(rule: DiscountRule, base: Decimal, currency: str) -> Decimal:
    """What the rule is worth before any cap, budget or floor touches it.

    Six decimals throughout — `core.money.finalize` is called ONCE, by the
    caller, on the figure that becomes the bill line (B4 §Rounding: round at
    finalization, never mid-calculation).
    """
    kind = rule.discount_type
    if kind not in discount_models.DISCOUNT_TYPES_PRICEABLE:
        raise DiscountTypeNotPriceable(
            f"discount {rule.code} is a {kind!r}, which this product stores but cannot yet "
            "price: a rate override swaps a schedule inside R2 and a usage allowance deducts "
            "QUANTITY before the tier walk at R3b, so neither is a subtraction at R6. Both are "
            "EP-RAT-15 engine work. The bill REFUSES rather than applying zero, because a "
            "discount that silently reduces nothing is exactly what CR-013 part 3's "
            "'subsidy granted is reportable' exists to prevent."
        )
    if kind == discount_models.DISCOUNT_PERCENTAGE:
        return base * rule.value / HUNDRED
    if kind == discount_models.DISCOUNT_CHARGE_WAIVER:
        # A waiver removes the whole of what its scope selected — r10 draws it
        # as `CONN · ~~$85.00~~ $0.00`, the line still on the bill, struck
        # through. The line is NOT deleted; the reduction equals it.
        return base
    # DISCOUNT_FIXED_AMOUNT
    if rule.currency != currency:
        raise DiscountCurrencyMismatch(
            f"discount {rule.code} is a fixed credit in {rule.currency} and this bill is in "
            f"{currency}. Hard rule 2 pairs every amount with its currency, and a "
            f"{rule.value} credit is not {rule.value} of another currency — the bill refuses "
            "rather than converting at a rate nobody signed."
        )
    return rule.value


def _trim(amount: Decimal, rule: DiscountRule) -> tuple[Decimal, str | None]:
    """Apply the three caps and the remaining budget, naming which one bit.

    Order is fixed and deliberate: the tightest limit wins, and the NAME
    returned is the limit that actually produced the final figure, because part
    3's Budget-&-usage tab reports *"denials by cap or funding"* and "capped"
    without a reason is not a report.
    """
    trimmed_by: str | None = None
    for limit, label in (
        (rule.cap_per_bill, "cap_per_bill"),
        (rule.cap_year_remaining, "cap_per_year"),
        (rule.cap_lifetime_remaining, "cap_lifetime"),
        (rule.budget_remaining, "budget"),
    ):
        if limit is None:
            continue
        capped = max(limit, ZERO)
        if capped < amount:
            amount = capped
            trimmed_by = label
    return amount, trimmed_by


def _resolve_exclusivity(
    rules: tuple[DiscountRule, ...],
    candidate: dict[str, Decimal],
) -> tuple[tuple[DiscountRule, ...], tuple[DeniedDiscount, ...]]:
    """*"One assistance program per account — the larger applies"* (r10).

    Within one `exclusivity_group` the rule with the LARGEST candidate
    reduction survives; ties break on `stacking_precedence` then on code, so
    two equal-value programmes still resolve deterministically rather than by
    dictionary order.
    """
    groups: dict[str, list[DiscountRule]] = {}
    free: list[DiscountRule] = []
    for rule in rules:
        if rule.exclusivity_group:
            groups.setdefault(rule.exclusivity_group, []).append(rule)
        else:
            free.append(rule)

    kept = list(free)
    denied: list[DeniedDiscount] = []
    for group, members in groups.items():
        winner = max(
            members,
            key=lambda r: (candidate.get(r.code, ZERO), -r.stacking_precedence, r.code),
        )
        kept.append(winner)
        for loser in members:
            if loser.code == winner.code:
                continue
            denied.append(
                DeniedDiscount(
                    code=loser.code,
                    reason=(
                        f"excluded by {winner.code}: both are in the {group!r} programme group "
                        "and only one applies per account — the larger reduction wins "
                        f"({winner.code} {candidate.get(winner.code, ZERO)} vs "
                        f"{loser.code} {candidate.get(loser.code, ZERO)})"
                    ),
                )
            )
    return tuple(kept), tuple(denied)


def price_discounts(
    lines: tuple[BillLine, ...],
    rules: tuple[DiscountRule, ...],
    currency: str = "USD",
) -> DiscountOutcome:
    """R6 — apply every in-force discount to one bill, in precedence order.

    `lines` are the PRICED tariff lines before tax; `rules` are the account's
    in-force enrolments, already resolved for date, proof and budget by
    `discount_services`. The bill's subtotal is Σ `lines`, and nothing here
    reads a database or a clock.
    """
    subtotal_before = sum((line.amount for line in lines), ZERO)

    # ── 1 · proof, before anything is computed ──────────────────────────────
    denied: list[DeniedDiscount] = []
    eligible: list[DiscountRule] = []
    for rule in rules:
        if rule.proof_before_first_reduction and not rule.verified:
            denied.append(
                DeniedDiscount(
                    code=rule.code,
                    reason=(
                        "the programme requires proof before the first reduction and this "
                        "enrolment is not verified, so the bill is charged in full. The "
                        "enrolment stands; the reduction starts when the proof is recorded."
                    ),
                )
            )
            continue
        eligible.append(rule)

    # ── 2 · exclusivity, decided on candidate figures ───────────────────────
    # Computed against the UNDISCOUNTED subtotal so the comparison is between
    # the programmes and not between their positions in the order.
    candidate: dict[str, Decimal] = {}
    for rule in eligible:
        base = (
            subtotal_before
            if rule.applies_to == discount_models.SCOPE_WHOLE_BILL
            else _scoped_base(rule, lines)
        )
        candidate[rule.code] = finalize(_raw_reduction(rule, base, currency))
    kept, excluded = _resolve_exclusivity(tuple(eligible), candidate)
    denied.extend(excluded)

    # ── 3 · precedence order, then the running arithmetic ───────────────────
    ordered = sorted(kept, key=lambda r: (r.stacking_precedence, r.code))
    running = subtotal_before
    applied: list[AppliedDiscount] = []
    exhausted: list[str] = []

    for index, rule in enumerate(ordered):
        if index > 0 and not rule.stacks_with_others:
            denied.append(
                DeniedDiscount(
                    code=rule.code,
                    reason=(
                        "this discount does not stack and another reduction has already been "
                        "applied to this bill. Its precedence decides which one that is — "
                        "make it the lowest number if it must win."
                    ),
                )
            )
            continue

        if rule.budget_remaining is not None and rule.budget_remaining <= ZERO:
            # ⚖️ `BR-RAT-075` "suspend" SUPERSEDED — PO 2026-10-04, verbatim:
            # *"We cannot hold the bill; we need to make discount value to 0
            # and move on - we cannot stop the billing"*. This RAISED
            # `DiscountBudgetExhausted` under `suspend` until that ruling, and
            # the bill run turned it into a held bill for every enrolled
            # account (worked: a $10.00/bill programme with a $45.00 yearly
            # budget held both its accounts' bills from April). Now a spent
            # budget is a $0.00 discount, named as denied, for EVERY setting,
            # and the bill is priced, issued and sent as normal. The stored
            # value `suspend` stays readable and means "stop the discount".
            denied.append(
                DeniedDiscount(
                    code=rule.code,
                    reason=f"budget exhausted ({rule.exhaustion_behaviour})",
                )
            )
            continue

        base = (
            running
            if rule.applies_to == discount_models.SCOPE_WHOLE_BILL
            else _scoped_base(rule, lines)
        )
        amount, trimmed_by = _trim(_raw_reduction(rule, base, currency), rule)

        # ── the floor: a discount never takes the bill below it ─────────────
        headroom = running - rule.bill_floor_amount
        if headroom <= ZERO:
            denied.append(
                DeniedDiscount(
                    code=rule.code,
                    reason=(
                        f"the bill is already at this programme's floor of "
                        f"{rule.bill_floor_amount}, so there is nothing left to reduce"
                    ),
                )
            )
            continue
        if amount > headroom:
            amount, trimmed_by = headroom, "bill_floor"

        amount = finalize(amount)
        if amount <= ZERO:
            denied.append(
                DeniedDiscount(code=rule.code, reason="the reduction rounds to $0.00 on this bill")
            )
            continue

        applied.append(
            AppliedDiscount(code=rule.code, amount=amount, base=base, trimmed_by=trimmed_by)
        )
        running -= amount
        if (
            rule.budget_remaining is not None
            and rule.exhaustion_behaviour == discount_models.EXHAUSTION_SUSPEND
            and rule.budget_remaining - amount <= ZERO
        ):
            exhausted.append(rule.code)

    return DiscountOutcome(
        subtotal_before=subtotal_before,
        subtotal_after=running,
        applied=tuple(applied),
        denied=tuple(denied),
        exhausted=tuple(exhausted),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 of 5 VERBATIM (12-governance/11-change-requests.md) + part 4's per-tax discount treatment + 08-cr013-design.md §A2 (R6 before R7) and §A4 scenarios S1/S2 + 07-r10-plans-rates-readout.md §4 (the SENIOR detail read-out) + B4 §Rounding ❄ + BR-RAT-003/062
# generated: 2026-08-19 by the CR-013 EP-RAT-12 lane (discounts — the R6 arithmetic)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half — DIS-01/DIS-02 are out of this slice) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 rating math, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: ruff✔ black✔ py_compile✔ · pytest tests/test_cr013_discounts.py 47 passed✔ · ⚠ FOUR GUARDS PROVED RED FIRST (hard-won law 7): the bill floor, the exclusivity resolution, the proof-before-first-reduction gate and the unpriceable-type refusal were each broken in turn and the matching test FAILED before being trusted green · golden-verify 33 PASS/0 FAIL (unchanged — a discount is a new line, not a change to a frozen figure)✔ · G6 forbidden PASS (no wall clock, no float on money)
# exceptions: `rate_override` and `usage_allowance` REFUSE by name rather than pricing as zero — ⚠ AMENDED 2026-08-31 (CR-052 W5 task 17): the ARITHMETIC for both now exists in `apps/rating/resolution.py` (R2's `resolve_schedule_with_override`, R3b's `allowance_deducted_quantity`, worked at $14.40 for a 2 kgal allowance), and this module still refuses them — ⚠ AMENDED AGAIN 2026-08-31 (BR-RAT-962): OQ-291 and OQ-292 are now CLOSED and the reason CHANGED IDENTITY rather than disappearing. `usage_allowance` is excluded because this module is R6 and subtracts MONEY while an allowance deducts UNITS before the tier walk (admitting it prices that 2 kgal allowance at $2.00 instead of $14.40, a $12.40 error against the customer); `rate_override` because BR-RAT-961 left it nothing to price; and DEF-438 still leaves the chain with no production caller · R6 is NOT wired into `resolution.resolve_discounts` by this lane — that file belongs to the EP-RAT-15 lane working in this same tree and was told to leave R6 unmodelled; the two-line integration is written out in the module docstring under INTEGRATION · a scoped discount takes the UNDISCOUNTED scope sum while `whole_bill` takes the running subtotal — stated in `_scoped_base` because it is the choice precedence exists to make visible
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
