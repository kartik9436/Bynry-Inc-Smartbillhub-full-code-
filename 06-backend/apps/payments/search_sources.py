# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `payments` group
#           Screens: shell chrome (the topbar popover, every authenticated screen)
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (≤5; prefix-then-recency; by their
#           B2 identifiers) · BR-SHL-006 (app.tenant_id + RLS FORCE) ·
#           CLAUDE.md hard rule 2 (money never a float, DISPLAY 2) · B14 rule 31
# Tests:    06-backend/tests/test_us_shl_003_search.py ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7)
# Impacts:  core.search registry (apps/payments/apps.py registers this) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The payments module's global-search source — payments by the two numbers a
person can actually quote.

⚠ **BOTH `payment_no` AND `confirmation` ARE SEARCHED, AND THE SIGNED RULE NAMES
ONLY THE SECOND.** BR-SHL-005's field list reads *"Payments —
payments.confirmation"*, and US-SHL-003's own test data then uses **"PMT-88213"**
as that confirmation — which is the shape of the tenant's `PMT-` SERIES, i.e.
`payment_no`. So the signed field list and the signed test data disagree about
which column the example lives in.

`payment_no` is searched as well, and that is a WIDENING toward the amendment's
own words rather than away from them: *"by their B2 identifiers"*. `payment_no`
is this product's own identifier for a payment — it is the number the receipt
prints — and a global search that could not find a payment by the number the
product itself issued would be broken in the most obvious way available.
`confirmation` is the bank's or the cheque's number and stays searched exactly as
signed. Recorded in 12-governance/02-decision-log.md.

⚠ **`confirmation` IS NOW A CORRECTABLE COLUMN (hard rule 4 as narrowed, PO
2026-09-02).** A cheque number typed wrong is fixed in place through
`POST /payments/{id}/correct-reference`, so a search on the OLD value stops
finding the payment the moment it is corrected. That is the intended behaviour —
the corrected number is the true one — and it is written here because a lane
reading a support ticket ("I searched the cheque number and it vanished") should
find the answer in the code rather than rediscover it.

MONEY: the amount rides as its exact stored decimal string beside the CHAR(3)
currency and is formatted by the client (hard rule 2). Nothing here re-rounds.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.payments import models
from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

_SIX_PLACES = Decimal("0.000001")

# Both quotable numbers rank first — a person reading a cheque and a person
# reading a receipt are equally likely, and neither should come second.
_PAYMENT_PREFIX_FIELDS = ("payment_no", "confirmation")
_PAYMENT_MATCH_FIELDS = ("payment_no", "confirmation")


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def _decimal_str(value: Decimal | None) -> str | None:
    """The stored NUMERIC value as its exact decimal STRING ("247.300000")."""
    if value is None:
        return None
    return str(Decimal(value).quantize(_SIX_PLACES, rounding=ROUND_HALF_UP))


def search_payments(term: str, limit: int) -> list[dict[str, Any]]:
    """Payments by payment number or confirmation number.

    The label prefers `payment_no` — our own number, always issued — and falls
    back to the confirmation when a payment arrived without one. **It never
    falls back to the uuid** (B14 rule 31): where neither number exists the row
    is labelled by its confirmation or, failing that, omitted from the label
    rather than shown as a machine value.
    """
    qs = (
        models.Payment.objects.filter(tenant_id=_tenant_id())
        .select_related("account")
        .filter(core_search.matches_any(term, _PAYMENT_MATCH_FIELDS))
    )
    rows = list(core_search.prefix_then_recency(qs, term, _PAYMENT_PREFIX_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        label = row.payment_no or row.confirmation
        parts = []
        if row.account_id and row.account is not None:
            parts.append(row.account.account_no)
        if row.confirmation and row.confirmation != label:
            parts.append(row.confirmation)
        result.append(
            {
                "id": str(row.id),
                "label": label,
                "context": " · ".join(parts) or None,
                "amount": _decimal_str(row.amount),
                "currency": row.currency,
            }
        )
    return result


def register() -> None:
    """Register the payments group with the BE-08 kernel.

    Called from `PaymentsConfig.ready()`. Default `visible_to` — every tenant
    role — because reading a payment is `AnyTenantRole` today. BR-SHL-006's
    omission clause is what guards a future role that may NOT see this group,
    and it lives in the kernel: an omitted group renders as nothing at all, not
    as a heading over zero rows.
    """
    core_search.register_search_source("payments", search_payments)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03 (BR-SHL-005 amended)
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in the same lane) F✔ G✔ H=deferred(PO)
# exceptions: `payment_no` is searched as well as the signed `confirmation` —
#         a widening toward "by their B2 identifiers", recorded in the decision log
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
