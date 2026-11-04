# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — proration)
#           Screens: — (the prorated base line renders in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see
#           apps/rating/pricing/errors.py for the reason (G10 semantics).
# Rules:    BR-RAT-004 (proration = CALENDAR days; base AND usage both
#           prorated — B4.3 CONFIRMED) · BR-RAT-002 (tier thresholds scale with
#           the prorated period, driven by this same factor) · BR-RAT-003
#           (nothing here rounds; the factor and the product stay unrounded)
# Golden:   GT-3 — B5 ❄️ FROZEN 2026-08-08: 15/30 x 30.50 = 15.25
# Tests:    06-backend/tests/test_us_rat_012_engine.py (GT-3 + the factor)
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/stages/**
# ───────────────────────────────────────────────────────
"""Proration — CONFIRMED (B4.3): calendar days; base AND usage both prorated.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

ONE factor, derived ONCE, used everywhere
-----------------------------------------
`service_days / cycle_days` is the only proration number in the engine. It
prorates the base charge (BR-RAT-004) and it scales tier thresholds
(BR-RAT-002). Those two are the same ratio by rule, so they are the same value
in code — two independently computed factors could disagree, and a bill where
the base is half but the tier bounds are whole is not a bill anyone can explain.

CALENDAR days, never billing days, never 30/360. B4.3 is explicit and it is
frozen. GT-3: move-in day 16 of 30 -> 15 days served -> 15/30 x 30.50 = 15.25.

Nothing here rounds. The factor keeps full Decimal precision (a 10/31 period is
0.32258... and truncating it early would move money), and the product is
finalized once, by the finalize stage or by the public seam that returns a line
amount (BR-RAT-003 / B4.4).

Deposit-differential proration is NOT here and is not missing: the PO CL round
(2026-08-08 -> BR-CUS-062) ruled there is no recompute on plan change in v1.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.rating.pricing import errors


def proration_factor(*, cycle_days: int, service_days: int) -> Decimal:
    """`service_days / cycle_days` as an exact ratio (B4.3, calendar days).

    A full period gives exactly 1, so callers need no "is this prorated?" branch.
    Refuses a non-positive cycle length and a negative service length — both are
    inputs no calendar can produce, and defaulting either would invent a period.
    """
    if cycle_days <= 0:
        raise errors.InvalidPeriod(
            f"cycle_days must be positive to prorate by calendar days (B4.3); got {cycle_days}."
        )
    if service_days < 0:
        raise errors.InvalidPeriod(f"service_days cannot be negative (B4.3); got {service_days}.")
    if service_days == cycle_days:
        return Decimal(1)
    return Decimal(service_days) / Decimal(cycle_days)


def prorated_amount(amount: Decimal, factor: Decimal) -> Decimal:
    """`amount x factor`, UNROUNDED (BR-RAT-003 — finalization happens once)."""
    return amount * factor


#: A unit price is stored and shown to at most 4 places (CLAUDE.md rule 2 as
#: amended 2026-10-02: *"Show unit prices with up to 4 decimals"*).
RATE_PLACES = Decimal("0.0001")


def prorated_rate(rate: Decimal, factor: Any) -> Decimal:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` — the PRINTED per-item rate of
    a part-month per-item line, so quantity × rate = amount on the bill (PO
    2026-10-12). It is a label beside an amount `prorated_amount` already
    computed and never feeds one: the money is unchanged. A whole month
    (factor 1) returns the rate untouched, so every full-month line prints
    exactly as before; a part month prints the day share to 4 places —
    `$4.50 × 19/30 = $2.85`, `$5.00 × 11/30 = $1.8333`."""
    if factor == 1:
        return rate
    return (rate * factor).quantize(RATE_PLACES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-3 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: B5 GT-3 freezes ONLY the prorated base (15.25) and says so in its own words ("example total pending usage figures"). The usage half of B4.3 is implemented as BR-RAT-002 threshold scaling (US-RAT-012 TC-4) and has NO frozen figure to bind to — REPORTED, not invented.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
