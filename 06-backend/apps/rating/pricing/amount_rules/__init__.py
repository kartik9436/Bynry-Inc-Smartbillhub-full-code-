# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — charge amount rules as plugins)
#           Screens: — (pure code)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-045 (one amount(charge_ctx) interface, one registry) ·
#           BR-RAT-041 (v1 = flat / percent / percent-with-minimum; "Formula"
#           visible but DISABLED — there is deliberately no fourth row below)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/engine.py 🔒 · apps/billing (late fee)
# ───────────────────────────────────────────────────────
"""Charge-amount rules — flat, percent, percent-with-minimum.
HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING —
AI-authored under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md.
"""

from apps.rating.pricing import registry
from apps.rating.pricing.amount_rules import rules


def _register() -> None:
    """Import-time registration. Called once, by the package __init__."""
    registry.AMOUNT_RULES.register(rules.FLAT, rules.flat)
    registry.AMOUNT_RULES.register(rules.PERCENT, rules.percent)
    registry.AMOUNT_RULES.register(rules.PERCENT_MIN, rules.percent_with_minimum)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: no `formula` rule is registered — BR-RAT-046 is a PROPOSED amendment pending PO ratification (candidate OQ-095) and BR-RAT-041 stands as written.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
