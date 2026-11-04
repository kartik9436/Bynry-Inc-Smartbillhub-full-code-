# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8744 — a part-month per-kW line printed the FULL rate beside
#           the cut-down amount ("6 kW · $14.00 · $53.20" on 19 of 30 days).
# Rules:    B4.3 / BR-RAT-004 (proration by calendar days, unchanged) ·
#           DEF-BIL-8743 (the money this line now carries) · `billing/0039`
#           (`invoice_lines.pricing_trace` stores `service_days` / `cycle_days`)
# Tests:    06-backend/tests/test_def_bil_8744_day_share_printed.py
# ───────────────────────────────────────────────────────
"""The day fraction a printed line was cut down by — DISPLAY ONLY.

`DEF-BIL-8743` (2.428.1) prorated a summed capacity charge by calendar days,
as B4.3 says: 6 kW × $14.00 on 19 of 30 days is **$53.20**. The kW is never
scaled and the rate is the schedule's rate, so the line printed
`6 kW · $14.00 · $53.20` and a customer multiplying it out got $84.00. This
answers the one missing fact, so the line reads
`6 kW · $14.00 · 19/30 days · $53.20` and foots.

⚠ **IT MOVES NO MONEY AND RECOMPUTES NO DAYS.** The days are the ones the bill
was priced on — the stored line's `pricing_trace` (`billing/0039`), or the
gathered `AccountBillingData` on a preview that has not been saved. The amount
is the engine's, already rounded.

⚠ **IT ANSWERS ONLY WHEN THE FRACTION EXPLAINS THE AMOUNT.** A line is shown a
day fraction exactly when `quantity × rate` does NOT round to its amount and
`quantity × rate × days ÷ cycle days` DOES (`core.money.finalize`, B4.4's one
rounding law). So a whole-month line, a metered line (only its tier bound
scales, never its money — BR-RAT-002), a base line and a counted service's
joined line (whose printed rate is already its own share) all answer None, and
a line that fails to foot for any OTHER reason is never labelled as prorated —
the label is a statement of fact, so it is only made where it is true.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from core.money import finalize

#: The line kinds whose money a day share can cut (B4.3: a capacity or counted
#: service's per-thing charge). A base line prints its own prorated figure as
#: its rate (`DEF-BIL-8315`), so it foots without one.
SHARED_KINDS = ("usage",)


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "" or value == "tiered":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def day_share(
    *,
    kind: Any,
    quantity: Any,
    rate: Any,
    amount: Any,
    service_days: Any,
    cycle_days: Any,
) -> dict[str, int] | None:
    """`{"days": 19, "of": 30}` when the line's amount is `quantity × rate`
    cut down by those days, else None. Worked: 6 kW, $14.00, $53.20, 19 of 30
    → `6 × 14.00 = 84.00 ≠ 53.20` and `84.00 × 19/30 = 53.20` → the share."""
    if str(kind or "") not in SHARED_KINDS:
        return None
    q, r, a = _decimal(quantity), _decimal(rate), _decimal(amount)
    if q is None or r is None or a is None:
        return None
    try:
        days, of = int(service_days), int(cycle_days)
    except (TypeError, ValueError):
        return None
    if not 0 < days < of:
        return None
    whole = q * r
    if finalize(whole) == finalize(a):
        return None
    if finalize(whole * Decimal(days) / Decimal(of)) != finalize(a):
        return None
    return {"days": days, "of": of}


def of_stored_line(line: Any) -> dict[str, int] | None:
    """The share of a saved `invoice_lines` row, its days read off the line's
    own `pricing_trace` — the days it was priced on, never today's."""
    trace = getattr(line, "pricing_trace", None) or {}
    return day_share(
        kind=getattr(line, "kind", None),
        quantity=getattr(line, "quantity", None),
        rate=getattr(line, "unit_price", None),
        amount=getattr(line, "amount", None),
        service_days=trace.get("service_days"),
        cycle_days=trace.get("cycle_days"),
    )


def words(share: dict[str, int] | None) -> str | None:
    """`19/30 days` — the printed document's wording (B14 rule 33: a fact)."""
    if not share:
        return None
    return f"{share['days']}/{share['of']} days"


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-10-01 by the "two small fixes" lane (DEF-BIL-8744)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
