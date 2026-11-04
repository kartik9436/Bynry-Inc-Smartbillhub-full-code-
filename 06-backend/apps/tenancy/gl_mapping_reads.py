# ── Trace ──────────────────────────────────────────────
# CR:       CR-197-BRC10 (GL mapping becomes one list)
# Rules:    BR-LED-800 · BR-LED-802 · BR-TEN-013 / B1 (a module writes only its
#           own rows) · BR-TEN-029 (deactivate always allowed; reactivate any time)
# Tests:    06-backend/tests/test_cr197_gl_mapping_list.py
# ───────────────────────────────────────────────────────
"""TENANCY's published half of the one GL mapping list.

Adjustment reasons (`reason_codes.default_gl_account_id`) and ways of paying
(`payment_methods.clearing_gl_account_id`) are tenancy-hosted lists, and a
service's every-class revenue pointer is `tenant_services` — all tenancy's
rows. The ledger's list reads and writes them only through these callables,
which go through the lookup handlers and services tenancy already owns and
already audits (`update_lookup_entry`, `set_lookup_entry_active`,
`set_service_gl_accounts`).
"""
from __future__ import annotations

from typing import Any

from apps.tenancy import models, selectors, services
from core import tenancy as core_tenancy

REASON_LIST = "reason_codes"
TENDER_LIST = "payment_methods"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def reasons_for_gl_mapping() -> list[dict[str, Any]]:
    """Every adjustment reason with its account, active and inactive."""
    return [
        {
            "id": str(row_id),
            "code": code,
            "name": name,
            "gl_account_id": str(gl_id) if gl_id else None,
            "active": bool(active),
        }
        for row_id, code, name, gl_id, active in models.ReasonCode.objects.filter(
            tenant_id=_tenant_id()
        )
        .order_by("code", "id")
        .values_list("id", "code", "name", "default_gl_account_id", "active")
    ]


def tenders_for_gl_mapping() -> list[dict[str, Any]]:
    """Every ACTIVE way of paying with the account it waits in."""
    return [
        {
            "id": str(row_id),
            "code": code,
            "name": name,
            "gl_account_id": str(gl_id) if gl_id else None,
            "active": True,
        }
        for row_id, code, name, gl_id in models.PaymentMethod.objects.filter(
            tenant_id=_tenant_id(), active=True
        )
        .order_by("code", "id")
        .values_list("id", "code", "name", "clearing_gl_account_id")
    ]


def service_names() -> dict[str, str]:
    """`{code: the utility's own name for it}` for the list's Mapped-for column."""
    return dict(selectors.service_names_by_code())


def set_reason_gl_account(actor: Any, reason_id: Any, account_id: str | None) -> dict[str, Any]:
    return services.update_lookup_entry(
        actor, REASON_LIST, reason_id, {"default_gl_account_id": account_id}
    )


def set_tender_gl_account(actor: Any, tender_id: Any, account_id: str | None) -> dict[str, Any]:
    return services.update_lookup_entry(
        actor, TENDER_LIST, tender_id, {"clearing_gl_account_id": account_id}
    )


def set_reason_enabled(actor: Any, reason_id: Any, enabled: bool) -> dict[str, Any]:
    return services.set_lookup_entry_active(actor, REASON_LIST, reason_id, enabled)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-197-BRC10 · decision log 2026-10-29 · BR-LED-800/802
# generated: 2026-10-29 by the CR-197-BRC10 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: tests/test_cr197_gl_mapping_list.py
# exceptions: a way of paying has no Disable here (PO Q1: only charge, adjustment and discount rows)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
