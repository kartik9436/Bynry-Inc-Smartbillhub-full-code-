# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check)
# Plan:     15-bulk-bill-run-build-plan.md B12 (payment checks at Check through
#           the payments seam)
# Rules:    BR-BIL-1052 · B1 (billing reaches another module through a seam)
# Defect:   G65 red on 2026-09-30 — `check_engine.py` imported
#           `apps.payments.bill_run_checks` directly (the seam bypassed)
# Tests:    06-backend/tests/test_bbr_check_engine.py (the payments category)
# ───────────────────────────────────────────────────────
"""billing → payments SEAM for the Check's payment facts. Two reads, no writes.

The Check asks payments ONCE per chunk of accounts for the facts its payment
tags are built from, and once per run for the facts payments has declared it
cannot answer (`UNAVAILABLE`). Both used to be `from apps.payments import
bill_run_checks` inside `check_engine.py`, which is the ring bypassed (G65).
They are resolved BY NAME here, at call time, the idiom every billing seam uses.

**An unpublished read is not an empty answer.** `payment_facts_for_accounts`
raises when payments does not publish it, and the engine turns that into a
utility-wide stop (B21) — *"no payment problems anywhere"* is the silent zero
DEF-046 taught. `unavailable_facts` answers an empty tuple when nothing is
published, because a declared absence that cannot be read is simply not shown.
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any

PAYMENTS_CHECKS = "apps.payments.bill_run_checks"


class PaymentsCheckUnpublished(RuntimeError):
    """Payments does not publish the Check's facts read on this deployment."""


def _module() -> Any:
    try:
        return import_module(PAYMENTS_CHECKS)
    except ImportError:  # pragma: no cover - defensive
        return None


def unavailable_facts() -> tuple[dict[str, str], ...]:
    """The payment facts payments has declared it cannot answer, each a dict."""
    module = _module()
    rows = getattr(module, "UNAVAILABLE", None) if module is not None else None
    return tuple(dict(row) for row in (rows or ()))


def payment_facts_for_accounts(
    account_ids: list[Any], *, period_end: date, bill_date: Any, due_date: Any
) -> dict[Any, Any]:
    """Payments' facts for these accounts (B12) — raised when unpublished."""
    module = _module()
    read = getattr(module, "payment_facts_for_accounts", None) if module is not None else None
    if not callable(read):
        raise PaymentsCheckUnpublished(f"{PAYMENTS_CHECKS}.payment_facts_for_accounts")
    return read(account_ids, period_end=period_end, bill_date=bill_date, due_date=due_date)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-037@4cb6ab0 (sha1[:7] of 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md + 04-docs/05-modules/07-billing/02-business-rules.md, concatenated in that order)
# generated: 2026-09-30 by the final bulk-run lane (G65 repair)
# checklist: A✔ B✔ C✔ D✔(reached through POST …/billing/runs/{id}/check — check_api.run_check) E✔(the bulk run's Check step shows the payments tags these facts make) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ · pytest tests/test_bbr_payment_checks.py tests/test_us_bil_037_clerk_checks.py✔ · G65 module-ring✔ (it is the G65 repair)
# exceptions: none — it forwards payments' own read by name and adds no fact of its own
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
