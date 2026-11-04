# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-10 (bulk run · Check — Payments & balances)
# Rules:    BR-BIL-1053 (payment checks at Check) · BR-BIL-017 (level =
#           trailing average of the eligibility window, whole $; auto re-level
#           at ±20% drift — the SAME threshold, read from the tenant's own
#           `relevel_drift_pct`) · BR-BIL-021 (every budget parameter is tenant
#           config) · BR-TEN-043 (no clock) · CLAUDE.md hard rules 1 and 2
# Decision: 12-governance/02-decision-log.md 2026-09-30 *"THE FOUR PAYMENT
#           CHECKS WITH NO DATA BEHIND THEM ARE BUILT, NOT PUT TO THE PO"* (1)
# Defect:   DEF-BIL-8241
# Tests:    06-backend/tests/test_bbr_payment_checks.py (level pay cases)
# ───────────────────────────────────────────────────────
"""LEVEL PAY OFF TRACK — the one Payments & balances fact that is BILLING's.

The coordinator's judgment of 2026-09-30, under BR-BIL-017 and not re-asked
(law 13): *"Level pay off track = the level-pay account has drifted more than
±20% — the threshold BR-BIL-017 already signs for the automatic re-level … the
Check raises it as a warning so the clerk sees it before billing, and never
re-levels by itself."*

WHAT IT MEASURES, AND WHY IT IS EXACTLY THE RE-LEVEL'S MEASURE
--------------------------------------------------------------
`budget_service.relevel` recomputes the level from the account's trailing
actuals (`budget.compute_level`: Σ ÷ the tenant's eligibility window, rounded
the tenant's way) and re-levels when `budget.drift_fraction(current, recomputed)`
is STRICTLY greater than the tenant's `relevel_drift_pct`. This file asks the
same question with the same two functions and the same three settings, and
drops only the CADENCE gate — the clerk should see the drift in any month, not
only in the month a re-level is due. Worked (the test's figures):

    level $242, twelve bills of $300 → recomputed $300 → |300 − 242| ÷ 242
    = 23.97% > 20% → tagged, *"+23.97%"*
    level $242, twelve bills of $260 → 7.44% → not tagged

The current level is `status.level`, the COMPUTED one, because that is what
the re-level measures and what an override is bounded against (OQ-068); the
figure the customer actually pays (`effective_level`) rides on the tag beside it.

THE ACTUALS ARE THE ONES `selectors.budget_history_for` READS — issued and paid
bills only (a draft is not an actual), newest first, the eligibility window's
worth. **An account with fewer bills than the window has no trailing average and
is NOT tagged**: dividing a six-month sum by twelve would report a false drop,
and a figure made up to fill the gap is the guess BR-BIL-021 refuses. Bills in
two currencies on one account are the same refusal.

IT NEVER RE-LEVELS, NEVER WRITES, AND NEVER STOPS THE CHECK. A WARNING bills
anyway (`check_taxonomy`). If the tenant's budget settings cannot be read, no
account is tagged and the tag is DECLARED unavailable for the pass instead —
never a silent *"no drift anywhere"*.

Two queries per chunk: the enrolled accounts, then their issued bills — and
none at all for a chunk with nobody on level pay.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from apps.billing import budget, models, settings_seam
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from core import tenancy as core_tenancy

FACT_LEVEL_OFF_TRACK = "level_pay_off_track"

#: Declared on the Check's `unavailable` when the tenant's budget settings
#: cannot be read — the same shape `payments.bill_run_checks.UNAVAILABLE` uses.
SETTINGS_UNREADABLE: dict[str, str] = {
    "code": FACT_LEVEL_OFF_TRACK,
    "reason": "budget_settings_unreadable",
    "detail": (
        "the tenant's budget-billing settings (the re-level threshold and the averaging "
        "window) could not be read, so no level-pay account was measured"
    ),
}

_CENT = Decimal("0.01")
_HUNDRED = Decimal("100")


def _display(value: Decimal) -> str:
    """Hard rule 2: stored exactly, DISPLAYED to two places."""
    return str(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def settings() -> dict[str, Any] | None:
    """`{months, rounding, drift_pct}` from the tenant's S69 row, or None when it
    cannot be read (`settings_seam.budget_billing` refuses rather than
    defaulting, and so does this)."""
    try:
        values = settings_seam.budget_billing()
        return {
            "months": int(values["eligibility_months"]),
            "rounding": str(values["level_rounding"]),
            "drift_pct": Decimal(str(values["relevel_drift_pct"])),
        }
    except (BillingConfigError, BillingRuleError, KeyError, ValueError, InvalidOperation):
        return None  # declared unavailable, never guessed


def level_pay_off_track(
    account_ids: Iterable[Any], *, config: dict[str, Any]
) -> list[tuple[str, str, dict[str, Any]]]:
    """`(account_id, code, params)` for every level-pay account in the chunk
    whose trailing average has drifted past the tenant's re-level threshold."""
    ids = [str(one) for one in account_ids if one]
    if not ids:
        return []
    tenant_id = core_tenancy.current_tenant_id()
    statuses = {
        str(row["account_id"]): row
        for row in models.AccountBudgetStatus.objects.filter(
            tenant_id=tenant_id, account_id__in=ids, status=budget.STATUS_ENROLLED
        )
        .order_by("account_id", "-created_at")
        .values("account_id", "level", "level_override", "currency")
    }
    if not statuses:
        return []
    months = config["months"]
    actuals: dict[str, list[tuple[Decimal, str]]] = {}
    for row in (
        models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=list(statuses),
            status__in=(models.INVOICE_ISSUED, models.INVOICE_PAID),
        )
        .order_by("account_id", "-period_end", "-id")
        .values("account_id", "total", "currency")
    ):
        bills = actuals.setdefault(str(row["account_id"]), [])
        if len(bills) < months:
            bills.append((row["total"], row["currency"]))

    out: list[tuple[str, str, dict[str, Any]]] = []
    for account_id, status in statuses.items():
        bills = actuals.get(account_id, [])
        level = status["level"]
        if len(bills) < months or len({c for _, c in bills}) != 1 or not level:
            continue  # no full window, mixed currency, or no level: nothing to measure
        recomputed = budget.compute_level(
            trailing_actuals=[total for total, _ in bills],
            months=months,
            rounding=config["rounding"],
        )
        drift = budget.drift_fraction(current_level=level, recomputed_level=recomputed)
        if not drift > config["drift_pct"] / _HUNDRED:
            continue
        signed = (recomputed - level) / level * _HUNDRED
        effective = status["level_override"] if status["level_override"] is not None else level
        out.append(
            (
                account_id,
                FACT_LEVEL_OFF_TRACK,
                {
                    "level": _display(level),
                    "pays": _display(effective),
                    "trailing_average": _display(recomputed),
                    "drift_pct": _display(signed),
                    "threshold_pct": _display(config["drift_pct"]),
                    "months": months,
                    "currency": bills[0][1],
                },
            )
        )
    return out


__all__ = ["FACT_LEVEL_OFF_TRACK", "SETTINGS_UNREADABLE", "level_pay_off_track", "settings"]
