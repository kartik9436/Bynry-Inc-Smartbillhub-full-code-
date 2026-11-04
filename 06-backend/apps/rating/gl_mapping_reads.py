# ── Trace ──────────────────────────────────────────────
# CR:       CR-197-BRC10 (GL mapping becomes one list)
# Rules:    BR-LED-800 (the list's rows) · BR-LED-802 (Disable = the owner's own
#           stop-new-use act) · BR-BIL-010 (charge codes carry their own GL) ·
#           DEF-BIL-10648 (a discount's own GL account is read at issue) ·
#           BR-TEN-013 / B1 (a module writes only its own rows)
# Tests:    06-backend/tests/test_cr197_gl_mapping_list.py
# ───────────────────────────────────────────────────────
"""RATING's published half of the one GL mapping list.

The ledger's list (`apps/ledger/gl_mapping_list.py`) shows charge codes,
discounts and taxes beside the ledger's own rows. Those three belong to rating,
so the ledger never queries them: it calls THESE functions by name at call time
(`apps/ledger/gl_mapping_seams.py`). Every write below is a thin door onto the
act rating already owns and already audits — nothing here writes a column in a
way the owning screen does not.

  * reads — `charges_for_gl_mapping`, `discounts_for_gl_mapping`,
    `taxes_for_gl_mapping`, and `gl_account_id_for_discount_code`, which
    billing asks at issue (DEF-BIL-10648);
  * writes — the account pointer of a charge code, a discount and a tax, each
    through its existing writer (`update_charge`, `set_discount_gl_account`,
    `set_tax_liability_account`);
  * Disable / Enable — a charge code through `set_charge_active`, a discount
    through `retire_discount` dated the tenant's today. A retired discount has
    no undo in rating, so Enable is refused by name rather than invented here
    (decision log 2026-10-29, judgment 2).
"""
from __future__ import annotations

from typing import Any

from apps.rating import discount_services, seams, selectors, services
from apps.rating import discounts as discount_models
from apps.rating import models
from core import errors
from core import tenancy as core_tenancy
from core.pagination import ListParams

#: `charges.kind` → the Detail word the list shows. NULL is a code minted on
#: Settings and not yet given a kind; it is an OTHER charge until it is.
CHARGE_KIND_DETAIL = {"base": "base", "plan": "plan", "other": "other"}


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def charges_for_gl_mapping() -> list[dict[str, Any]]:
    """Every charge code of this tenant, live and retired, with its account."""
    rows = []
    for charge_id, code, name, kind, is_base, gl_id, deleted_at in models.Charge.objects.filter(
        tenant_id=_tenant_id()
    ).order_by("code", "id").values_list(
        "id", "code", "name", "kind", "is_base", "gl_account_id", "deleted_at"
    ):
        detail = CHARGE_KIND_DETAIL.get(kind or "") or ("base" if is_base else "other")
        rows.append(
            {
                "id": str(charge_id),
                "code": code,
                "name": name,
                "kind": detail,
                "gl_account_id": str(gl_id) if gl_id else None,
                "active": deleted_at is None,
            }
        )
    return rows


def discounts_for_gl_mapping() -> list[dict[str, Any]]:
    """Every discount of this tenant with its account. `active` is False once a
    retirement is written (`retire_on` set), which is what Disable writes."""
    rows = []
    for discount_id, code, name, gl_id, retire_on in discount_models.Discount.objects.filter(
        tenant_id=_tenant_id()
    ).order_by("code", "id").values_list("id", "code", "name", "gl_account_id", "retire_on"):
        rows.append(
            {
                "id": str(discount_id),
                "code": code,
                "name": name,
                "gl_account_id": str(gl_id) if gl_id else None,
                "active": retire_on is None,
            }
        )
    return rows


def taxes_for_gl_mapping() -> list[dict[str, Any]]:
    """The tenant's CURRENT taxes (one row per chain, as the Taxes tab lists
    them) with the authority they are collected for and the liability account."""
    rows = []
    for tax in selectors.tax_list_queryset(ListParams()):
        jurisdiction = tax.jurisdiction
        authority = (
            (getattr(jurisdiction, "authority", None) or getattr(jurisdiction, "name", None))
            if jurisdiction is not None
            else None
        )
        rows.append(
            {
                "id": str(tax.id),
                "name": tax.name,
                "authority": authority or tax.name,
                "gl_account_id": (
                    str(tax.liability_gl_account_id) if tax.liability_gl_account_id else None
                ),
                "active": tax.deleted_at is None,
            }
        )
    return rows


def gl_account_id_for_discount_code(code: Any) -> str | None:
    """The account a discount's OWN line posts to, or None (DEF-BIL-10648).

    `None` means "no account of its own" and billing then uses the
    `discount_contra_revenue` designation, exactly as before this read existed.
    A retired discount still answers: the line was already priced and is only
    asking where its money belongs (the same reasoning `gl_account_id_for_charge`
    gives for a retired code).
    """
    text = str(code or "").strip()
    if not text:
        return None
    value = (
        discount_models.Discount.objects.filter(tenant_id=_tenant_id(), code__iexact=text)
        .values_list("gl_account_id", flat=True)
        .first()
    )
    return str(value) if value else None


# ── writes, each through rating's own act ──────────────────────────────────
def set_charge_gl_account(actor: Any, charge_id: Any, account_id: str | None) -> dict[str, Any]:
    return services.update_charge(actor, charge_id, {"gl_account_id": account_id})


def set_discount_gl_account(actor: Any, discount_id: Any, account_id: str | None) -> dict[str, Any]:
    return services.set_discount_gl_account(actor, discount_id, {"gl_account_id": account_id})


def set_tax_gl_account(actor: Any, tax_id: Any, account_id: str | None) -> dict[str, Any]:
    return services.set_tax_liability_account(
        actor, tax_id, {"liability_gl_account_id": account_id}
    )


def set_charge_enabled(actor: Any, charge_id: Any, enabled: bool) -> dict[str, Any]:
    return services.set_charge_active(actor, charge_id, enabled)


def set_discount_enabled(actor: Any, discount_id: Any, enabled: bool) -> dict[str, Any]:
    """Disable = retire today. Enable = refused: a retirement has no undo."""
    if enabled:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-802",
            message_key="ledger.glMapping.discountCannotReturn",
        )
    return discount_services.retire_discount(
        actor, discount_id, {"effective_to": seams.tenant_today().isoformat()}
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-197-BRC10 (12-governance/change-requests/CR-197-BRC10-gl-mapping-one-list.md) · decision log 2026-10-29 · BR-LED-800/802 · DEF-BIL-10648
# generated: 2026-10-29 by the CR-197-BRC10 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a (no money math; each write is rating's existing audited act)
# gates: tests/test_cr197_gl_mapping_list.py
# exceptions: Enable on a retired discount is refused by name — rating has no un-retire and this file does not invent one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
