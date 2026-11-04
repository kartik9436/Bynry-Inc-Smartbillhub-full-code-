# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the pure pricing function)
#           Screens: — (pure functions; refusals surface to billing's S31.3)
#           No US-ID is cited in this header ON PURPOSE: G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs", and this file ships no
#           test. The stories it serves are named in the docstring — the
#           precedent apps/billing/rating_seam.py set for the same reason.
# Rules:    BR-RAT-038 (UoM gate: match or a defined factor, never a silent
#           conversion) · BR-RAT-032 (tier contiguity) · BR-RAT-044 (an
#           unregistered pricing model refuses; it never prices as 0) ·
#           BR-RAT-045 (same for charge amount rules) · BR-RAT-004 (calendar-day
#           proration needs a real cycle length)
# Golden:   — (no B5 figure is stated here; these are refusals, not amounts)
# Tests:    06-backend/tests/test_us_rat_012_engine.py ·
#           06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/** · apps/billing
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

Rating-engine refusals. Every one fails CLOSED (hard-won law 3).

Serves US-RAT-012 (usage pricing), US-RAT-013 (totals) and US-RAT-015 (rule-type
plugins). Not one of these exceptions carries a fallback: an unknown unit, an
unregistered model or a missing price is a REFUSAL, never a zero and never a
guess. US-RAT-015 TC-5 states it exactly — "it never prices as 0 and never
silently falls back to flat".

These are plain value errors rather than the BE-02 catalog exceptions because
the engine is a pure function with no request context. The caller (billing's
run) maps a refusal onto its own S31.3 exception row (BR-BIL-040); doing that
mapping here would give the engine knowledge of a screen it must not have.
"""


class RatingError(Exception):
    """Base: the engine refused to price. Never raised directly."""


class RatingInputError(RatingError, ValueError):
    """An input the engine cannot price from — reported, never defaulted."""


class MissingUnit(RatingInputError):
    """A consumption arrived without an explicit unit (CLAUDE.md hard rule 3)."""


class UomMismatch(RatingInputError):
    """Read unit is not the tariff's billed unit and no factor converted it.

    BR-RAT-038 (PO R6, OQ-004 closure): the conversion happens at rating INPUT
    or not at all. The engine holds no factor and performs no conversion — a
    mismatch here is the blocked read the rule describes.
    """


class InvalidPeriod(RatingInputError):
    """The billing period cannot yield a B4.3 calendar-day proration factor."""


class TaxRuleUnpriceable(RatingInputError):
    """A tax rule arrived carrying neither a percent rate nor a flat amount.

    BR-RAT-036 gives a tax exactly one form and `TaxRuleSpec` carries one figure
    per form. A rule with no figure at all cannot be priced, and pricing it as
    0.00 would print a line asserting the authority charges nothing — a claim,
    and one nobody made. Refused by name, like every other engine input gap.
    """


class TariffConfigError(RatingInputError):
    """The tariff version cannot be priced as configured (e.g. a tiered
    structure violating BR-RAT-032 contiguity, or a flat model with no price)."""


class MissingWindowQuantity(RatingInputError):
    """A TOU window is priced by the tariff and nothing measured it.

    BR-RAT-021: *"reads arrive pre-split per window"*. When one does not arrive,
    the engine does not know whether the customer used nothing on-peak or
    whether the on-peak register was never read — and those are different and
    very differently priced facts. So it refuses, naming the window. The same
    posture `apps.billing.contracts.ServiceReading` states for a whole service:
    a zero *"would be a claim that the meter was read and showed no usage"*.
    """


class MissingDemandQuantity(RatingInputError):
    """A demand tariff priced an energy quantity and no peak demand arrived.

    BR-RAT-014's measurement is a max-demand register read. An absent read is
    an unread register, not a month with no peak — on a $2,002.00 demand line
    (B5 GT-21 / WE-5: 182 kW x $11.00) the difference is the whole line.
    """


class BasisUnavailable(RatingInputError):
    """A percent-of-service tariff cannot see the service it is a percent OF.

    BR-RAT-015: sewer = a percent of the WATER usage-charge dollars. When water
    is not on this bill — not on the plan, out of the run's service scope, or
    priced with no usage line — there is no basis, and 0% of an unknown number
    is not zero dollars. The refusal NAMES the basis service so the run's
    exception screen can say which service is missing (BR-BIL-015), which is
    the seam posture CLAUDE.md requires: *report that it cannot answer, never
    answer 0*.
    """


class DiscountRefused(RatingInputError):
    """R6 refused to price a discount on this bill (DEF-502, 2026-08-22).

    Raised by `stages/apply_discounts.py`, wrapping `apps.rating
    .discount_pricing.DiscountPricingError` — the R6 law module's own refusals
    (an unpriceable type, a foreign-currency credit, an exhausted budget under
    `suspend`) — and its own two scope refusals (`named_codes`, a non-taxable
    tariff line under a reduction). A `RatingInputError` so the billing seam
    translates it to `PricingRefused`: ONE account's named break on the run's
    exception screen, never a crashed batch (BR-BIL-055; the wrapping of the
    budget-exhaustion raise is a recorded judgment — decision log 2026-08-22).
    """


class DiscountTaxBaseUnruled(RatingInputError):
    """RETIRED 2026-08-22, kept as a tombstone: OQ-331 closed as `BR-RAT-116`
    (PO verbatim: *"tax is always on Utility service charge + base fees"*), so
    a SERVICE-SCOPED tax on a discounted bill prices on its services' own
    taxable lines — $0.89 on the worked bill — and nothing raises this any
    more. The class stays one release so an old traceback in a log still
    resolves to its explanation; delete after 2026-09."""


class UnknownPricingModel(RatingError, LookupError):
    """`tariff_versions.model` resolves to no registered plugin (BR-RAT-044)."""


class UnknownAmountRule(RatingError, LookupError):
    """`charges.amount_rule` resolves to no registered plugin (BR-RAT-045)."""


class RegistryClosed(RatingError, RuntimeError):
    """Something tried to register a plugin after import time (BR-RAT-044).

    The registry is code, never tenant data: US-RAT-015 TC-7 requires that no
    runtime path can add or replace an implementation.
    """


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: none — this module holds no money math and states no B5 figure.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
