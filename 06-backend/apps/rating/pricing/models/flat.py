# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing)
#           Screens: — (the priced line renders in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-044 (a pricing model is a module behind ONE price(...)
#           interface) · BR-RAT-003 (a plugin NEVER rounds — it returns
#           NUMERIC(18,6); finalization is the caller's, once) · BR-RAT-001
#           (the quantity it prices is already post-multiplier)
# Golden:   GT-1 — B5 ❄️ FROZEN 2026-08-08: 684 x 0.12 = 82.08
# Tests:    06-backend/tests/test_us_rat_012_engine.py (GT-1) ·
#           06-backend/tests/test_us_rat_015_plugins.py (interface + no-rounding)
# Impacts:  apps/rating/pricing/stages/price_usage.py (resolves this by name)
# ───────────────────────────────────────────────────────
"""`flat` pricing model: one usage line, quantity x unit price.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-012 TC-1. B5 GT-1: 684 kWh x $0.12/kWh = $82.08.

The whole module is four lines of arithmetic, and that is the point of
BR-RAT-044 — the price-usage stage does not know this file exists by name, it
asks the registry. A flat tariff with no unit price is a REFUSAL (a tariff that
cannot be priced is an exception, never a zero-dollar bill).

Proration note: a flat rate needs none. B4.3 prorates the BASE charge and scales
TIER THRESHOLDS (BR-RAT-002/004) — a per-unit price times a metered quantity is
already proportional to the days that produced the quantity, so multiplying it
by the period factor would charge a short period twice as short. B5 freezes no
prorated-flat figure and none is invented here.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing import errors
from apps.rating.pricing.contracts import (
    KIND_USAGE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    SubscriptionContext,
)

MODEL = "flat"


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
) -> tuple[LineCandidate, ...]:
    """One usage line at `config.unit_price`. UNROUNDED (BR-RAT-003)."""
    if config.unit_price is None:
        raise errors.TariffConfigError(
            f"flat tariff for service {subscription.service!r} has no unit_price; "
            "a tariff that cannot be priced is a refusal, never a zero line "
            "(BR-RAT-044, hard-won law 3)."
        )
    amount: Decimal = usage.billed_quantity * config.unit_price
    return (
        LineCandidate(
            kind=KIND_USAGE,
            # CR-063 — a per-size line SAYS which size it is, so two lines of
            # one service on one document are tellable apart. `size_label` is
            # None on every other tariff, so this is byte-identical everywhere
            # else and no frozen figure's wording moves.
            description=(
                f"{subscription.service} usage"
                if not config.size_label
                else f"{subscription.service} - {config.size_label}"
            ),
            amount=amount,
            taxable=True,  # B4.2: usage is in the tax base
            quantity=usage.billed_quantity,
            unit=usage.unit,
            unit_price=config.unit_price,
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: none — GT-1 is fully frozen in B5 and this module reproduces it to the digit.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
