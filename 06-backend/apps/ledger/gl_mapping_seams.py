"""ledger → rating / tenancy / customers SEAMS for the one GL mapping list.

`CR-197-BRC10`. The list shows rows three other modules own — charge codes,
discounts and taxes (rating), adjustment reasons and ways of paying (tenancy),
customer classes (customers). B1 / BR-TEN-013: the ledger never imports their
ORM. Each callable below is resolved BY NAME AT CALL TIME from the owner's
published file, the idiom `tenancy_seam.py` already uses, and every write it
reaches is the owner's own audited act.

An unpublished callable REFUSES rather than answering empty, for
`tenancy_seam`'s reason: "this tenant has no charge codes" and "the ledger
cannot see rating" have the same shape, and the second would draw a list that
looks complete.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from core import errors

RATING_FILE = ("rating", "gl_mapping_reads")
TENANCY_FILE = ("tenancy", "gl_mapping_reads")
CUSTOMERS_FILE = ("customers", "selectors")


def _call(where: tuple[str, str], attribute: str, *args: Any) -> Any:
    module, file = where
    try:
        target = import_module(f"apps.{module}.{file}")
    except ImportError:
        target = None
    fn = getattr(target, attribute, None) if target is not None else None
    if not callable(fn):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-013",
            message_key="ledger.glMapping.ownerUnreachable",
            params={"owner": module},
        )
    return fn(*args)


# ── rating ──────────────────────────────────────────────────────────────────
def charges() -> list[dict[str, Any]]:
    return _call(RATING_FILE, "charges_for_gl_mapping")


def discounts() -> list[dict[str, Any]]:
    return _call(RATING_FILE, "discounts_for_gl_mapping")


def taxes() -> list[dict[str, Any]]:
    return _call(RATING_FILE, "taxes_for_gl_mapping")


def set_charge_gl_account(actor: Any, item_id: str, account_id: str | None) -> Any:
    return _call(RATING_FILE, "set_charge_gl_account", actor, item_id, account_id)


def set_discount_gl_account(actor: Any, item_id: str, account_id: str | None) -> Any:
    return _call(RATING_FILE, "set_discount_gl_account", actor, item_id, account_id)


def set_tax_gl_account(actor: Any, item_id: str, account_id: str | None) -> Any:
    return _call(RATING_FILE, "set_tax_gl_account", actor, item_id, account_id)


def set_charge_enabled(actor: Any, item_id: str, enabled: bool) -> Any:
    return _call(RATING_FILE, "set_charge_enabled", actor, item_id, enabled)


def set_discount_enabled(actor: Any, item_id: str, enabled: bool) -> Any:
    return _call(RATING_FILE, "set_discount_enabled", actor, item_id, enabled)


# ── tenancy ─────────────────────────────────────────────────────────────────
def reasons() -> list[dict[str, Any]]:
    return _call(TENANCY_FILE, "reasons_for_gl_mapping")


def tenders() -> list[dict[str, Any]]:
    return _call(TENANCY_FILE, "tenders_for_gl_mapping")


def service_names() -> dict[str, str]:
    return _call(TENANCY_FILE, "service_names")


def set_reason_gl_account(actor: Any, item_id: str, account_id: str | None) -> Any:
    return _call(TENANCY_FILE, "set_reason_gl_account", actor, item_id, account_id)


def set_tender_gl_account(actor: Any, item_id: str, account_id: str | None) -> Any:
    return _call(TENANCY_FILE, "set_tender_gl_account", actor, item_id, account_id)


def set_reason_enabled(actor: Any, item_id: str, enabled: bool) -> Any:
    return _call(TENANCY_FILE, "set_reason_enabled", actor, item_id, enabled)


# ── customers ───────────────────────────────────────────────────────────────
def customer_classes() -> list[dict[str, Any]]:
    """`[{value: code, label: name}]` — the tenant's ACTIVE customer classes."""
    return _call(CUSTOMERS_FILE, "account_type_options")
