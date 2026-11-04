# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5. The three doors
#           `P5.7`'s two screens read through, which the drawing's own *To
#           build* row names (`GET /settlements`, p070) and which no §4 task
#           row owned — `DEF-PAY-6286`.
# Story:    no story — 5·1 Settlements and 5·2 Settlement are `S-NEW · PAY-P`.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · BR-SHL-011 (the list URL
#           grammar) · NFR-3 (server pagination) · BR-TEN-043 (the caller names
#           the day; this module reads no clock) · B14 rule 31 (the address
#           segment is the provider's reference, never a uuid)
# Tests:    06-backend/tests/test_cr139_p5_7_settlements_read.py
# Impacts:  apps/payments/api.py's urlpatterns (one `include`, declared ABOVE
#           `detail_api` because that one must stay last) ·
#           apps/payments/settlements_read.py (every query; no ORM here)
# ───────────────────────────────────────────────────────
"""The Settlements surface — **three doors, and none of them writes.**

    GET /settlements                    5·1  the list, one row per payout
    GET /settlements/{code}             5·2  one payout and its four figures
    GET /settlements/{code}/members     5·2  the payments inside it, paged

**THIN BY LAW** (B8 / LAW 0): parse → call a read → serialize. No ORM here, no
money arithmetic and no clock.

⚠ **THERE IS NO `POST`, NO `PATCH` AND NO `DELETE`, AND THAT IS THE DRAWING'S
OWN STEP 3.** p072, verbatim: *"A settlement has no actions, on purpose. It is
a statement of fact from a provider. There is nothing to approve, nothing to
edit and nothing to cancel — if a payout is wrong, the provider issues another
one."* The payout is WRITTEN by `settlements.ingest_payout`, from the
integration feed `P5.9` landed. A second write path here would be a second
answer to one question, on the money path.

⚠ **THE ADDRESS SEGMENT IS THE PROVIDER'S OWN REFERENCE.** p071 draws
`/:tenant/payments/settlements/STL-260921-CARD`, and B14 rule 31 keeps a
database id out of the most visible field a screen has. `settlement_by_code`
refuses an ambiguous one by name rather than answering the first of two.
"""

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import settlements_read
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    ⚠ **THE `message_key` IS A LITERAL AND THIS HELPER IS DEFINED IN THIS
    FILE.** `G32` resolves a key only where the helper is defined in the same
    file — two modules that imported theirs from a sibling reported **0
    unresolved** truthfully over 21 live refusals that reached a clerk as
    silence. `counters_api` records the same reasoning one noun along.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-SHL-020",
        message_key="payments.settlement.refused",
        params={"detail": str(refusal)},
    )


def _refuse_an_unknown_filter(request: Any, allowed: tuple[str, ...]) -> None:
    """An `f.<name>` this list does not serve is REFUSED, never dropped.

    `DEF-PAY-6235`'s root cause, kept on this endpoint the way `counters_api`
    keeps it on its own: `core.pagination.parse_list_params` IGNORES an
    undeclared filter name for every list in the product, so a caller that
    trusted a narrowing reads the whole utility's payouts as though they had
    been narrowed. Refused rather than corrected — a server that guesses what
    a typo meant is how the next one hides too.
    """
    unknown = sorted(
        key[len("f.") :]
        for key in request.query_params
        if key.startswith("f.") and key[len("f.") :] not in allowed
    )
    if not unknown:
        return
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-SHL-011",
        message_key="payments.settlement.refused",
        params={
            "detail": (
                f"this list does not serve the filter(s) {', '.join(unknown)}. It serves "
                f"{', '.join(allowed) or 'none'}. Refused rather than ignored: a filter that "
                "is silently dropped turns a narrowed question into the whole list, and the "
                "caller reads the answer as though it had been narrowed."
            )
        },
    )


def _as_of_or_none(request: Any) -> date | None:
    """`?as_of=YYYY-MM-DD` — the business day the two day-shaped tiles read FOR.

    ⚠ **THIS MODULE READS NO CLOCK** (`BR-TEN-043`, gate `G6`): a server clock
    decides a business day in the SERVER's timezone, so *paid out today* would
    be a different day for a Texas utility than for the machine. Absent is
    LAWFUL — the two tiles then answer `null` with `as_of_missing` beside them,
    which a screen renders as an absence rather than as a wrong figure.
    """
    raw = request.query_params.get("as_of")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "as_of", "code": errors.VAL_FORMAT}],
        ) from bad


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def settlements_list(request: Any) -> Response:
    """`GET /settlements` — 5·1, *"The bank shows one credit. Which payments is it?"*

        q            the payout's reference, or the provider
        sort         paid_out_at | code | provider | gross | net | payments | status
        dir          asc | desc
        page / per   50 · 100 · 200 · 500 · 1000
        f.state      received | matched
        f.provider   one provider_key
        as_of        the business day PAID OUT TODAY and FEES THIS MONTH mean

    ⚠ **PAGINATED AND SORTED IN SQL** (`NFR-3`, `NFR-5`). The `count` below is
    the database's `COUNT(*)` over the filtered set, not `len()` of a
    materialised list.
    """
    require_tenant(request)
    _refuse_an_unknown_filter(request, settlements_read.SETTLEMENT_FILTERS)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=settlements_read.SETTLEMENT_SORTS,
        default_sort=settlements_read.DEFAULT_SETTLEMENT_SORT,
        default_dir="desc",
        allowed_filters=settlements_read.SETTLEMENT_FILTERS,
    )
    paginator = StandardPagination()
    queryset = settlements_read.settlement_list_queryset(params)
    page = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(settlements_read.settlement_rows(page or []))
    # ⚠ **`rows`, BESIDE DRF's `results` AND NOT INSTEAD OF IT.** The screens
    # are built against `{rows, count, totals}` — the shape `counters_api`
    # settled on the same day — while the shared client reads `results` on
    # every other list. One name added, none taken away.
    response.data["rows"] = response.data["results"]
    # The four tiles, folded over the WHOLE filtered set and never over one
    # page: a figure that described a page would be a different figure wearing
    # the same label.
    response.data["totals"] = settlements_read.settlement_list_totals(
        queryset, as_of=_as_of_or_none(request)
    )
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def settlement_detail(request: Any, code: str) -> Response:
    """`GET /settlements/{code}` — 5·2's head and its four figures."""
    require_tenant(request)
    try:
        return Response(settlements_read.settlement_detail(code))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def settlement_members(request: Any, code: str) -> Response:
    """`GET /settlements/{code}/members` — *"Which 46 payments made up this?"*

    ⚠ **A SEPARATE, PAGED DOOR RATHER THAN A `members[]` ON THE DETAIL.** A
    payout holds any number of payments and `NFR-5` forbids a cap on it, so a
    detail payload that carried them all would be an unbounded response with a
    table's worth of controls that could not reach the server. The drawing puts
    a full toolbar and a pagination footer under this table (p071), which only
    a list endpoint can answer.
    """
    require_tenant(request)
    _refuse_an_unknown_filter(request, settlements_read.MEMBER_FILTERS)
    try:
        payout = settlements_read.settlement_by_code(code)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    params = parse_list_params(
        request.query_params,
        allowed_sorts=settlements_read.MEMBER_SORTS,
        default_sort=settlements_read.DEFAULT_MEMBER_SORT,
        default_dir="desc",
        allowed_filters=settlements_read.MEMBER_FILTERS,
    )
    paginator = StandardPagination()
    queryset = settlements_read.member_list_queryset(payout, params)
    page = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(settlements_read.member_rows(page or []))
    response.data["rows"] = response.data["results"]
    return response


# ⚠ **THE LITERAL `members` SEGMENT IS DECLARED AFTER THE TWO-SEGMENT PATTERN
# AND CANNOT COLLIDE WITH IT** — `settlements/<code>` is two segments and
# `settlements/<code>/members` is three, so Django resolves each unambiguously.
# The trap `api.py` records above its own `detail_api` include is a WIDE
# two-segment pattern eating a LITERAL two-segment one, and there is no literal
# two-segment `settlements/…` route in this module.
urlpatterns = [
    path("settlements", settlements_list),
    path("settlements/<str:code>", settlement_detail),
    path("settlements/<str:code>/members", settlement_members),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 §4 row `P5.7` · blueprint p069–p072 read as IMAGES at 2.0 (B14 rule 42) · DEF-PAY-6286
# generated: 2026-09-23 by LANE P5-SCREENS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr139_p5_7_settlements_read.py
# exceptions: no write verb is served at all — p072 step 3 is titled "What you can do to it — Nothing, and that is the design"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
