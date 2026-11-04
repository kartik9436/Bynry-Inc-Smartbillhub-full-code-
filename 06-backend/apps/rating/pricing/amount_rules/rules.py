# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — charge amount rules as plugins) ·
#           EP-BIL-01 (the late fee is the percent-with-minimum rule)
#           Screens: — (amounts render on the invoice / S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-045 (flat · percent · percent-with-minimum are three
#           implementations of ONE amount(charge_ctx) interface; no
#           implementation rounds its own return value) · BR-RAT-041 (those
#           three ARE v1; "Formula" is visible but disabled) · BR-RAT-003
#           (rounding is finalization's job, once) · BR-BIL-001 (the late fee is
#           max($5, 1.5% x overdue portion) — the same percent-with-minimum rule)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08: max(5, 0.015 x 542.10) = 8.13
# Tests:    06-backend/tests/test_us_rat_015_plugins.py ·
#           06-backend/tests/test_gt08_late_fee_grace.py
# Impacts:  apps/rating/engine.py 🔒 (publishes amount_for) · apps/billing
#           (late fee) · EP-RAT-07 plugs a fourth rule into this same interface
# ───────────────────────────────────────────────────────
"""The three v1 charge amount rules, each behind one `amount(charge)` call.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-015 TC-3/TC-6. BR-RAT-041 (CONFIRMED, PO OQ-053) fixes v1 at
flat / percent / percent-with-minimum; this module is those three and no fourth.
A tenant-authored formula (EP-RAT-07, BR-RAT-046) would be a fourth module and a
registry row — which is the point of the interface, and is also why nothing here
is reachable from tenant data.

NOTHING HERE ROUNDS. Every rule returns a full-precision Decimal; the caller
finalizes half-up to 2dp exactly once (BR-RAT-003 / B4.4). US-RAT-015 TC-6 makes
that a contract test rather than a convention: a second rounding law is precisely
the defect B4.4 exists to prevent.

GT-8's arithmetic lives in `percent_with_minimum` and nowhere else. Billing's
late-fee assessment owns the GRACE CLOCK (BR-BIL-001/008 — when the fee applies)
and calls this rule for the AMOUNT, so there is one implementation of
max($5, 1.5% x overdue portion) in the codebase, not two that can drift.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing import errors
from apps.rating.pricing.contracts import ChargeContext

FLAT = "flat"
PERCENT = "percent"
PERCENT_MIN = "percent_min"


def _require(value: Decimal | None, field: str, rule: str) -> Decimal:
    if value is None:
        raise errors.RatingInputError(
            f"charge amount rule {rule!r} needs {field!r} and it was not supplied. "
            "A missing input is a refusal, never a zero charge (hard-won law 3)."
        )
    return value


def flat(charge: ChargeContext) -> Decimal:
    """`amount` as configured (BR-RAT-041). Example: CONN $85.00."""
    return _require(charge.amount, "amount", FLAT)


def percent(charge: ChargeContext) -> Decimal:
    """`percent x basis` (BR-RAT-041).

    The BASIS is supplied by the caller and passed through unchanged. Which
    subtotal a percent charge is a percent OF is under-specified in
    BR-RAT-041/US-RAT-008 section 7 — EP-RAT-07 US-RAT-016 section 8 raises it as
    candidate OQ-096(c). This rule does not decide it; it applies the percent to
    whatever basis it is handed, exactly as US-RAT-015 says ("passes the basis
    through unchanged").
    """
    return _require(charge.percent, "percent", PERCENT) * _require(charge.basis, "basis", PERCENT)


def percent_with_minimum(charge: ChargeContext) -> Decimal:
    """`max(minimum, percent x basis)` (BR-RAT-041; BR-BIL-001's late fee).

    B5 GT-8: max(5, 0.015 x 542.10) = max(5, 8.1315) = 8.1315 -> finalized 8.13.
    The comparison happens on the UNROUNDED product, then the caller finalizes
    once (B4.4). B5 presents 8.13 already finalized and both orders agree there;
    doing it this way keeps a single rounding point rather than two that could
    disagree on some other figure.
    """
    minimum = _require(charge.minimum, "minimum", PERCENT_MIN)
    computed = _require(charge.percent, "percent", PERCENT_MIN) * _require(
        charge.basis, "basis", PERCENT_MIN
    )
    return minimum if minimum > computed else computed


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-8 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: the `percent` rule's BASIS is under-specified upstream (BR-RAT-041 / US-RAT-008 §7 never say which subtotal); per US-RAT-015 it is passed through unchanged and the gap is left where EP-RAT-07 US-RAT-016 §8 already raises it (candidate OQ-096(c)). No basis is chosen here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
