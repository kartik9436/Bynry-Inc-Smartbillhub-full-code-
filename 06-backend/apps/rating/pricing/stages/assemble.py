# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the totals the engine reports)
#           Screens: — (the totals render in S31.2 and on the invoice)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-005 (the taxable subtotal is the B4.2 base) · BR-RAT-003
#           (totals are sums of ALREADY-finalized line amounts — nothing is
#           rounded a second time) · BR-BIL-039 (pure)
# Golden:   GT-1 (total 108.88) · GT-10 (total 117.01, re-signed 2026-08-10) ·
#           GT-11 (total 108.71) — B5 ❄️ FROZEN
# Tests:    06-backend/tests/test_us_rat_013_totals.py
# Impacts:  apps/rating/engine.py 🔒 (returns what this stage builds)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

The engine's result: finalized lines and the totals that are their sums.

Every total here is a SUM OF FINALIZED LINE AMOUNTS. Nothing is recomputed from
unrounded intermediates and nothing is rounded twice — which is what makes the
totals reconcile with the lines a customer can read on the bill, and is why
GT-10's re-signed total falls out of the arithmetic rather than being asserted
separately:

    usage 82.08 + base 18.50 + fee 8.13 + tax 8.30 = 117.01

The fee is inside `total` and outside `taxable_subtotal`, which is exactly
GT-10's "(fee added after tax)" claim: `total - fee_total` leaves the taxed part.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing.contracts import KIND_FEE, PricedBill, PricedLine, TaxedLines


def _sum(lines: tuple[PricedLine, ...]) -> Decimal:
    return sum((line.amount for line in lines), Decimal("0.00"))


def assemble(source: TaxedLines) -> PricedBill:
    charged = source.source.lines
    lines = charged + source.tax_lines
    return PricedBill(
        lines=lines,
        taxable_subtotal=source.source.taxable_subtotal,
        tax_total=source.tax_total,
        fee_total=_sum(tuple(line for line in charged if line.kind == KIND_FEE)),
        total=_sum(lines),
        currency=source.normalized.subscription.currency,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1/10/11 totals PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: `total` is the sum of every finalized line, so it includes fees. That matches GT-1 (108.88, no fee), GT-10 (117.01 with the 8.13 fee, re-signed 2026-08-10 under HUMAN-GUIDE §6) and GT-11 (108.71). PRIOR BALANCE is NOT in it — that is billing's stage-6 payload figure (US-BIL-029 §7: current charges vs total due), not the engine's.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
