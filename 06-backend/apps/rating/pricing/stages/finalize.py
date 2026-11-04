# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the ONE rounding point)
#           Screens: — (finalized amounts render in S31.2 and on the invoice)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-003 (round per line, half-up, 2dp, AT FINALIZATION ONLY —
#           B4.4, finance-signed) · BR-RAT-005 (tax base = usage + base, by
#           KIND, structurally) · BR-BIL-039 (pure)
# Golden:   GT-1 (tax 8.2979 -> 8.30 comes from this boundary) · GT-2 · GT-10 ·
#           GT-11 — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_013_totals.py (rounding + the
#           structural tax base)
# Impacts:  apps/rating/pricing/stages/compute_tax.py · core/money.py (the
#           frozen half-up rule lives there and is not re-implemented here)
# ───────────────────────────────────────────────────────
"""The rounding boundary — the only place in the engine where 2dp happens.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

BR-RAT-003 / B4.4 (CONFIRMED, finance 2026-08-07): round PER LINE, HALF-UP, 2dp,
at finalization only. Every intermediate upstream of this module is a
full-precision Decimal; every amount downstream is 2dp. There is exactly one
call to `core.money.finalize` in the pricing path and it is here, so "we round
once" is a property of the code's shape rather than a claim in a docstring
(hard-won law 1).

`core.money.finalize` is not re-implemented here. One rounding law, one
implementation — a second one is precisely the defect B4.4 exists to prevent.

THE TAX BASE IS DECIDED BY KIND, NOT BY A FLAG ALONE
----------------------------------------------------
`taxable_subtotal` sums the FINALIZED amounts of lines whose KIND is in
TAX_BASE_KINDS (usage, base, minimum adjustment) and whose `taxable` flag is
true. US-RAT-013 section 5 defines the base as "Sigma invoice_lines.amount where
taxable" — finalized line amounts, which is why the sum happens after rounding
and not before. Requiring the KIND as well is US-RAT-013 TC-7: a fee line that
arrives wrongly flagged taxable from a mis-seeded charge code still cannot enter
a percent base, because B4.2 is structural and not data-driven.

Fee lines are finalized here too, along with everything else. A caller that
hands in an already-2dp fee (GT-10's 8.13) gets it back unchanged; a caller that
hands in more precision gets it finalized by the same law as every other line,
rather than by a second one.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing.contracts import (
    TAX_BASE_KINDS,
    ChargedLines,
    FinalizedLines,
    LineCandidate,
    PricedLine,
)
from core import money


def finalize_line(candidate: LineCandidate) -> PricedLine:
    """One candidate -> one invoice-line-ready amount (half-up, 2dp, once).

    Rounding touches the AMOUNT. `service`, `tax_id` and `charge_id` — the
    line's identity, which BR-BIL-010's GL stamp is keyed on (BR-BIL-069 for a
    tax, DEF-714 for a fee) — cross unchanged: a line that knew which service,
    which tax authority or which charge code produced it before finalization
    still knows it afterwards.
    """
    return PricedLine(
        kind=candidate.kind,
        description=candidate.description,
        amount=money.finalize(candidate.amount),
        taxable=candidate.taxable,
        quantity=candidate.quantity,
        unit=candidate.unit,
        unit_price=candidate.unit_price,
        service=candidate.service,
        tax_id=candidate.tax_id,
        # DEF-276 — provenance survives rounding. A line that knew which tariff
        # version priced it before finalization still knows it afterwards, for
        # the same reason `service` and `tax_id` do.
        tariff_version_id=candidate.tariff_version_id,
        # DEF-714 — and so does a fee's CHARGE CODE, which is the key
        # BR-BIL-010 resolves its GL account by. Rounding touches the amount
        # and nothing else; a line that lost its identity here would be
        # refused at issue with no way to tell why.
        charge_id=candidate.charge_id,
        # 2026-09-30 — the meter a line was priced for survives rounding too.
        asset_id=getattr(candidate, "asset_id", None),
        # DEF-RAT-9327 — the base line's charge CODE survives rounding, so a
        # discount scoped to named codes can still find it at apply-discounts.
        charge_code=getattr(candidate, "charge_code", None),
    )


def taxable_base(lines: tuple[PricedLine, ...]) -> Decimal:
    """Sigma of the finalized taxable line amounts, by KIND (B4.2/BR-RAT-005)."""
    return sum(
        (line.amount for line in lines if line.taxable and line.kind in TAX_BASE_KINDS),
        Decimal("0.00"),
    )


def finalize(source: ChargedLines) -> FinalizedLines:
    lines = tuple(finalize_line(candidate) for candidate in source.lines)
    return FinalizedLines(source=source, lines=lines, taxable_subtotal=taxable_base(lines))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `finalize_line` carries `service`/`tax_id` unchanged — rounding touches the amount and nothing else)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-1/2/10/11 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: the tax base is summed from FINALIZED line amounts, per US-RAT-013 §5 ("Σ invoice_lines.amount where taxable") — an invoice line's amount is its finalized amount. B5 GT-1/GT-10 are exact at both precisions (82.08 + 18.50 = 100.58 either way), so no frozen figure distinguishes the two readings; the documented one is implemented and the ambiguity is REPORTED rather than left implicit.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
