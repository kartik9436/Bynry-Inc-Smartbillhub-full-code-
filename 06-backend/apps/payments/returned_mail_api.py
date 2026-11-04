# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6342 — marking post returned reached nobody: no banner, no
#           needs-attention list, no way to clear the flag.
# Story:    US-PAY-016   Screens: S21 (the account's banner and its clear step)
# Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
#           returned (single/bulk) → account bad-address flag → needs-attention
#           queue + banner → paper suppressed until address verified (config);
#           balances unaffected; audited.") · BR-TEN-043 (the business date is
#           typed, never read from a clock) · BR-SHL-011 / NFR-3 (every list is
#           paged in the database) · B14 rule 31 (no database id is a visible
#           value) · CLAUDE.md rule 7 (audit)
# Tests:    06-backend/tests/test_def_pay_6342_bad_address.py
# Impacts:  apps/payments/returned_mail.py (the sole writer) · config/urls.py
# ───────────────────────────────────────────────────────
"""The needs-attention list and the clear step — the two doors BR-PAY-018 named
and nothing reached.

    GET  /returned-mail          every open return, OLDEST FIRST, paged in SQL;
                                 `f.account_id` narrows it to one account (the
                                 S21 clear step reads it that way)
    POST /returned-mail/clear    `{account_id, resolution, resolved_on}` — every
                                 open return on the account closed, then its
                                 bad-address flag lowered, in one transaction

Its own module rather than more lines in `apps/payments/api.py`, on the
`writeoffs_api` / `reversal_api` precedent: several lanes edit that file and a
pathspec commit there is where somebody's work is eaten (hard-won law 11).

THIN by law — `returned_mail.py` is the only writer and this file holds no ORM.

⚠ **THE CLEAR STEP DOES NOT EDIT AN ADDRESS, AND THAT IS THE DESIGN.** The PO's
ruling (2026-09-23, *"ensure you update correct address - mailing or service"*)
is met by sending the clerk to the door of the module that OWNS the address the
letter went to — customers' `PATCH /accounts/{id}/mailing-address` for a mailing
letter or for adding one, metering's premises page for a service address — and
THEN recording what they found here. Each list row carries `went_to` so the
screen knows which door to offer.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import returned_mail
from apps.payments.api import _actor, _business_date, _payload
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def returned_mail_list(request: Any) -> Response:
    """`GET /returned-mail` — the needs-attention list (J18 step 5).

    Oldest first, always: *"2 open needs-attention rows that will age visibly —
    the queue never silently drops them."* There is no sort control because the
    order IS the rule. The page is a `LIMIT`/`OFFSET` over payments' own table
    and the three enrichment reads are taken once for the page.
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_filters=("account_id",))
    paginator = StandardPagination()
    queryset = returned_mail.needs_attention(account_id=params.filters.get("account_id"))
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(returned_mail.needs_attention_rows(page or []))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the clerk works the stack; an Executive reads it
def returned_mail_clear(request: Any) -> Response:
    """`POST /returned-mail/clear` — the address was dealt with; bring the flag down.

    `resolution` is `address_corrected` (the clerk used the owning module's
    address door first) or `verified_current` (the address was right and the
    carrier was wrong). `resolved_on` is the business date the clerk types.
    """
    require_tenant(request)
    payload = _payload(request)
    account_id = str(payload.get("account_id") or "").strip()
    if not account_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.returnedMail.clear.accountRequired",
            params={"field": "account_id"},
        )
    resolved_on = _business_date(payload, "resolved_on")
    try:
        result = returned_mail.clear_account(
            account_id=account_id,
            resolution=str(payload.get("resolution") or ""),
            resolved_on=resolved_on,
            actor=_actor(request),
        )
    except PaymentRuleError as refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-018",
            message_key="payments.returnedMail.clear.refused",
            params={"detail": str(refusal)},
        ) from refusal
    return Response(result)


urlpatterns = [
    path("returned-mail", returned_mail_list, name="returned-mail-list"),
    path("returned-mail/clear", returned_mail_clear, name="returned-mail-clear"),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6342 (the defect row, BR-PAY-018 verbatim, J18 steps 3–5)
# generated: 2026-09-23 by the BAD-ADDRESS lane (maintenance)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_def_pay_6342_bad_address.py — through these routes
# exceptions: (1) NO TENANT-WIDE SCREEN MOUNTS THE LIST YET. Every host a
#         tenant-wide list would sit in — the Payments summary's returned-post
#         chip (`PaymentsPage.tsx`) and the returned-post modal
#         (`returnedMail.tsx`) — was held by another live lane on 2026-09-23.
#         S21 reads it narrowed to one account. REPORTED to the coordinator.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
