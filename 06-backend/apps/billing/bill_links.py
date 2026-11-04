# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill-ready email said "it is attached to this
#           email" and nothing was attached
# Ruling:   PO 2026-10-22, decision log *"Bill email sends a link instead of the
#           PDF"* (*"can't we sent link instead"*) and *"The bill email's link
#           opens the bill PDF directly, with no sign-in"* (*"b direct PDF
#           link"*); lane BILL-LINK's judgments entry after them
# Rules:    BR-NOT-027 (the KEPT PDF, never a re-render — `frozen_bill`) ·
#           CLAUDE.md hard rule 1 (the tenant from the path, RLS on the table) ·
#           hard rule 4 (nothing on the invoice is written) · hard rule 7 (every
#           open is audited) · law 3 (no public origin → no link, never a
#           relative one) · law 14 (the mint is a savepoint) · decision log
#           2026-10-22 *"One-time link secrets travel in the URL FRAGMENT"*
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py ·
#           06-backend/tests/test_def_bil_10531_bill_link_pg.py
# Impacts:  apps/billing/delivery_seam.bill_render_context (mints one per bill)
#           · apps/billing/bill_link_public_api.py (the public door) ·
#           07-frontend/src/portal/bill-link/BillLinkPage.tsx
# ───────────────────────────────────────────────────────
"""THE BILL EMAIL'S DIRECT PDF LINK — made at issue, opened without a sign-in.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides what a stranger holding
a link may download: the token, its digest, its expiry and the one refusal are
the whole security of that page. AI-authored 2026-10-22 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`.

THE FLOW
─────────────────────────────────────────────────────────────────────────────
`mint(invoice)` — called by `delivery_seam.bill_render_context` while the bill
  is issued: a 256-bit token (`core.link_tokens`, the agreement link's scheme),
  only its digest stored, expiring after the utility's `bill_link_valid_days`
  (Settings → Customer portal, seeded 30). Returns the two email tokens
  `{bill_link}` (`/{utility}/portal/bill#token=…`) and `{link_expires_on}`.
`public_view(token)` / `public_document(token)` — the page's two POSTs. The
  secret arrives in the request BODY, never the address. Each open is audited.

THE PUBLIC REFUSAL IS ONE REFUSAL
─────────────────────────────────────────────────────────────────────────────
Unknown, expired, another utility's, and a bill with no kept PDF all answer
`LinkUnavailable`, and the page shows one sentence and the utility's phone. The
lookup is by digest UNDER THE TENANT OF THE PATH, then compared in constant
time, so nothing about any bill is read before the token has matched.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any

from django.db import DatabaseError, transaction

from apps.billing import bill_link_seam, frozen_bill
from apps.billing.bill_link_models import BillLink
from core import audit as core_audit
from core import link_tokens, public_origin
from core.tenancy import current_tenant_id

#: The page's route, relative to the product's public origin. The screen's
#: route is `BILL_LINK_ROUTE` in `07-frontend/src/portal/bill-link/`.
BILL_LINK_PATH = "/{tenant}/portal/bill"
#: The fragment key the page reads (`useLinkSecret`).
TOKEN_PARAM = "token"

AUDIT_ENTITY = "bill_link"
AUDIT_OPENED = "billing.bill_link.opened"
AUDIT_DOWNLOADED = "billing.bill_link.downloaded"

#: The problem codes `mint` can report (they ride on the bill's delivery problems).
NO_PUBLIC_ORIGIN = "bill_link_public_origin_not_configured"
NOT_MADE = "bill_link_not_made"


class LinkUnavailable(Exception):
    """THE public refusal — unknown, expired, foreign or unkept, one answer."""


# ═══════════════════════════════════════════════════════════════════════════
# MINT — at issue
# ═══════════════════════════════════════════════════════════════════════════


def _expires_on(expires_at: datetime) -> Any:
    try:
        return expires_at.astimezone(bill_link_seam.tenant_timezone()).date()
    except Exception:  # noqa: BLE001 — a zone that cannot be read: UTC's date
        return expires_at.date()


def _ref(invoice: Any) -> str:
    return str(getattr(invoice, "pk", None) or getattr(invoice, "id", None) or "")


def mint(
    invoice: Any, *, now: datetime | None = None
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """One new link to this bill. Returns `(tokens, problems)`.

    `tokens` is `{"bill_link": <url or None>, "link_expires_on": <date or None>}`.
    Both are None — and a problem says why — when the host has no public
    address (law 3: never a relative link) or the row could not be written; the
    email then leaves the link paragraph out (`catalogs`: both are optional)
    and the bill still issues.
    """
    empty: dict[str, Any] = {"bill_link": None, "link_expires_on": None}
    tenant_id = getattr(invoice, "tenant_id", None) or current_tenant_id()
    subdomain = bill_link_seam.tenant_subdomain(tenant_id) if tenant_id else None
    if public_origin.public_app_origin() is None or not subdomain:
        return empty, ({"code": NO_PUBLIC_ORIGIN, "invoice_id": _ref(invoice)},)
    # G6 bans a server clock in billing, so the instant comes from tenancy's one
    # sanctioned read. NOT the bill's `issued_at`, deliberately: that is the
    # bill's EVENT time and may be a clerk's earlier stated moment, which would
    # mint a link already past its 30 days. A link's life is a security clock
    # that starts when the email is queued, and that instant is now.
    # In UTC before the arithmetic: in the zone, "+30 days" across a clock change
    # is 30 days and an hour (measured: 1 Nov 2026 in America/Chicago).
    now = (now or bill_link_seam.tenant_now()).astimezone(dt_timezone.utc)
    token = link_tokens.mint()
    try:
        expires_at = now + timedelta(days=bill_link_seam.link_valid_days(tenant_id))
        # Law 14: a failed insert must not poison the issue's transaction.
        with transaction.atomic():
            BillLink.objects.create(
                tenant_id=tenant_id,
                invoice_id=invoice.pk,
                token_hash=link_tokens.digest(token),
                issued_at=now,
                expires_at=expires_at,
            )
    except (DatabaseError, KeyError, TypeError, ValueError) as problem:
        return empty, (
            {"code": NOT_MADE, "invoice_id": _ref(invoice), "detail": type(problem).__name__},
        )
    link = public_origin.public_app_link(
        BILL_LINK_PATH.format(tenant=subdomain), fragment={TOKEN_PARAM: token}
    )
    return {"bill_link": link, "link_expires_on": _expires_on(expires_at)}, ()


# ═══════════════════════════════════════════════════════════════════════════
# THE PUBLIC PAGE
# ═══════════════════════════════════════════════════════════════════════════


def _by_token(token: Any) -> BillLink:
    """The live link this token opens — or `LinkUnavailable`, for every reason."""
    if not link_tokens.plausible(token):
        raise LinkUnavailable()
    text = str(token)
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise LinkUnavailable()
    row = (
        BillLink.objects.filter(tenant_id=tenant_id, token_hash=link_tokens.digest(text))
        .select_related("invoice")
        .first()
    )
    if row is None or not link_tokens.matches(row.token_hash, text):
        raise LinkUnavailable()
    if row.expires_at <= bill_link_seam.tenant_now():
        raise LinkUnavailable()
    return row


def _audit(action: str, row: BillLink, **extra: Any) -> None:
    core_audit.write_row(
        action=action,
        entity_type=AUDIT_ENTITY,
        entity_id=row.pk,
        # Judgment 3: the bill and the time (the row's own created_at), and
        # nothing about who opened it.
        after={"invoice_id": str(row.invoice_id), **extra},
    )


def _payload(invoice: Any) -> dict[str, Any]:
    return invoice.bill_payload if isinstance(invoice.bill_payload, dict) else {}


def public_view(token: Any) -> dict[str, Any]:
    """`POST …/open` — what the page shows once the token has matched."""
    row = _by_token(token)
    invoice = row.invoice
    profile = bill_link_seam.company_profile()
    _audit(AUDIT_OPENED, row)
    return {
        "utility_name": profile.get("dba_name") or profile.get("legal_name"),
        "bill_no": invoice.invoice_no,
        "bill_date": _payload(invoice).get("bill_date"),
        "due_date": invoice.due_date,
        "expires_on": _expires_on(row.expires_at),
    }


def public_document(token: Any) -> tuple[bytes, str]:
    """`POST …/document` — the bill's KEPT PDF, byte for byte, hash-verified.

    A bill with no kept PDF is refused, never re-drawn (judgment 6, BR-NOT-027).
    """
    row = _by_token(token)
    invoice = row.invoice
    reproduction = frozen_bill.reproduce(invoice)
    if not reproduction.is_original or reproduction.pdf is None:
        raise LinkUnavailable()
    try:
        payload = bill_link_seam.fetch_document(reproduction.pdf.id)
    except bill_link_seam.document_read_errors() as problem:
        raise LinkUnavailable() from problem
    _audit(AUDIT_DOWNLOADED, row, byte_length=len(payload))
    name = (invoice.invoice_no or str(invoice.pk)).replace("/", "-")
    return payload, f"{name}.pdf"


def public_unavailable() -> dict[str, Any]:
    """The dead end's facts: the utility's own number, from Settings → Company."""
    return {
        "state": "unavailable",
        "support_phone": bill_link_seam.company_profile().get("support_phone") or None,
    }


__all__ = [
    "BILL_LINK_PATH",
    "LinkUnavailable",
    "mint",
    "public_document",
    "public_unavailable",
    "public_view",
]
