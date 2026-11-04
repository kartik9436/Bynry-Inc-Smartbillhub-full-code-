# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `bills` group
#           Screens: shell chrome (the topbar popover, every authenticated screen)
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (≤5; prefix-then-recency; by their
#           B2 identifiers — signed field for bills is `invoices.invoice_no`) ·
#           BR-SHL-006 (app.tenant_id + RLS FORCE) · CLAUDE.md hard rule 2
#           (money never a float, never re-rounded here, DISPLAY 2) ·
#           B14 rule 31
# Tests:    06-backend/tests/test_us_shl_003_search.py ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7)
# Impacts:  core.search registry (apps/billing/apps.py registers this) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The billing module's global-search source — bills by invoice number.

⚠ **THE ACCOUNT NUMBER IS DELIBERATELY NOT A MATCH FIELD HERE, AND THE LIST
SCREEN'S OWN SEARCH IS DIFFERENT ON PURPOSE.** `selectors._apply_search` on S30
matches `invoice_no` OR `account__account_no`, which is right for a list of
bills — you are already in Billing and you want that account's bills. In the
GLOBAL box it would be wrong twice over: typing an account number would fill the
Bills group with five invoices that all say the same thing, and the Accounts
group two rows above already answers that query properly. BR-SHL-005's signed
field for this group is `invoices.invoice_no`, and the amendment of 2026-09-03
repeats *"by their B2 identifiers"* as a thing not to relax. Recorded in
12-governance/02-decision-log.md so a widening is a decision, not a drift.

MONEY: the total rides as its exact stored decimal string beside the CHAR(3)
currency and is formatted by the client (hard rule 2 — never a float on the
wire, rounded for DISPLAY only). Nothing here parses, sums or re-rounds one.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.billing.models import Invoice
from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

_SIX_PLACES = Decimal("0.000001")

_BILL_PREFIX_FIELDS = ("invoice_no",)
_BILL_MATCH_FIELDS = ("invoice_no",)


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def _decimal_str(value: Decimal | None) -> str | None:
    """The stored NUMERIC value as its exact decimal STRING ("148.630000").

    The quantize is the COLUMN's six places (DB-3 storage precision), not money
    rounding — that is B4's, at finalization/display, and this is neither.
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(_SIX_PLACES, rounding=ROUND_HALF_UP))


def search_bills(term: str, limit: int) -> list[dict[str, Any]]:
    """Bills by invoice number.

    The context line is the ACCOUNT the bill belongs to — an invoice number on
    its own tells a clerk nothing about whose bill it is, and the account number
    is the thing they will check it against. `select_related` so five rows cost
    one query.
    """
    qs = (
        Invoice.objects.filter(tenant_id=_tenant_id())
        .select_related("account")
        .filter(core_search.matches_any(term, _BILL_MATCH_FIELDS))
    )
    rows = list(core_search.prefix_then_recency(qs, term, _BILL_PREFIX_FIELDS)[:limit])
    return [
        {
            "id": str(row.id),
            "label": row.invoice_no,
            "context": row.account.account_no if row.account_id else None,
            "amount": _decimal_str(row.total),
            "currency": row.currency,
        }
        for row in rows
    ]


def register() -> None:
    """Register the bills group with the BE-08 kernel.

    Called from `BillingConfig.ready()`. Default `visible_to` — every tenant
    role — because reading a bill is `AnyTenantRole` (A4 gives Executive VIEW on
    Billing). BR-SHL-006's omission clause guards a future role, in the kernel.
    """
    core_search.register_search_source("bills", search_bills)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03 (BR-SHL-005 amended)
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in the same lane) F✔ G✔ H=deferred(PO)
# exceptions: matches `invoice_no` only — the S30 list's own search also matches
#         the account number, and the divergence is deliberate and recorded
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
