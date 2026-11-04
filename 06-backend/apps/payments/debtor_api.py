# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.3 — the door on the debtor read. Blueprint
#           `05-prototype/06 Payments Page Blueprint.pdf` screen **7·2 Debtor**,
#           whose proposed address is `/{tenant}/payments/debtors/{AC}`.
#           Screens: 7·2 (S-NEW · PAY-J) — the SCREEN is `P4.8`, HELD to wave 2
# Rules:    BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1
#           (a cross-tenant id reads as absent, never as somebody else's rows) ·
#           BR-TEN-043 (the business date is the caller's) · NFR-3 · NFR-5 ·
#           CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_cr138_p4_3_debtor_read.py
# Impacts:  config/urls.py inclusion · apps/payments/debtor_read.py
# ───────────────────────────────────────────────────────
"""`GET /debtors/{account_id}` — the drill-down 7·1 has never had.

ITS OWN MODULE rather than more lines in `apps/payments/api.py`, on the
`refunds_api` / `writeoffs_api` / `credit_notes_api` precedent and for hard-won
law 11's reason: a file several lanes edit is where a pathspec commit eats
somebody's work — and `api.py` is `P4.1`'s file in this same wave.

THIN BY LAW: the read is `debtor_read.debtor`. **No ORM, no figure and no
rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
WHY `debtors/{id}` AND NOT `outstandings/{id}` OR `accounts/{id}/debtor`
═══════════════════════════════════════════════════════════════════════════════
The blueprint draws the screen at `/{tenant}/payments/debtors/{AC}` and calls
the tab **Debtors**, so the API noun follows the product's own word rather than
introducing a second one a clerk would never say.

It is deliberately NOT `outstandings/{id}`: `GET /outstandings` is the LIST and
`P4.1` is rewriting its paging and sorting in this same wave. A detail route
hanging off that path would put two lanes in one URL family for no gain.

It is also not `accounts/{id}/debtor`: `accounts/<id>/…` is customers' address
space, already carrying `payments`, `refunds`, `collections`, `open-bills`,
`credit-sources`, `premises-position` and `premises-payments` as literal last
segments. A seventh would work and would say the wrong thing — this is a
payments SCREEN's read, not a fact about an account.

═══════════════════════════════════════════════════════════════════════════════
`AnyTenantRole`, AND WHY IT IS NOT NARROWER
═══════════════════════════════════════════════════════════════════════════════
Every one of the four things it gathers is already readable at that gate:
`GET /outstandings`, `GET /collections/ladder`, `GET /accounts/{id}/collections`
and `GET /accounts/{id}/open-bills` are all `AnyTenantRole`. A4 gives the
Executive VIEW on payments, and a door must not deny a reach its siblings
grant. **This read takes no act** — it moves no money, sends nothing and
advances no ladder.
"""

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from importlib import import_module

from apps.payments import debtor_read
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.pagination import clamp_page_size
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _as_of(request: Any) -> date:
    """The caller's business day — `BR-TEN-043`, gate `G6`, never a clock.

    `apps/payments/api._as_of` takes the same parameter in the same spelling for
    the same reason, and this repeats the parse rather than importing it only
    because that file is `P4.1`'s in this wave; the DEFAULT below is the one
    place the two must not drift, and neither invents a date.
    """
    raw = request.query_params.get("as_of")
    if raw in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.as_of_required",
            field_errors=[{"field": "as_of", "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "as_of", "code": errors.VAL_FORMAT}],
        ) from bad


#: How the SCREEN addresses a debtor — the reference a clerk reads out on the
#: telephone, never the primary key. The blueprint draws the address bar as
#: `/{tenant}/payments/debtors/AC-2026-00001`.
CUSTOMERS_MODULE = "customers"
ACCOUNT_READ = "account_queryset"


def _resolve_account_id(reference: str) -> Any:
    """`AC-2026-00001` → the account's pk, or the reference unchanged.

    ⚠ **B14 RULE 31 IS WHY THIS EXISTS, AND AN ADDRESS BAR IS A VISIBLE FIELD.**
    The rule names *"a primary or foreign key … a module path, a file name …
    an HTTP route"*, and a uuid in the browser's address bar is all of that at
    once. `CR-136-BRC07`'s `P2.6` settled the identical question for the
    Counter screens hours ago — *"a counter resolves by its CODE, because the
    drawing puts `CTR-260921-DW` in the address bar and B14 rule 31 keeps a
    database id out of it"* — and this is that precedent applied.

    ⚠ **IT IS A WIDENING AND NOT A REPLACEMENT.** A pk still resolves, because
    `POST /collections/run`, the debtor list and every seam in this module
    speak in ids, and a route that stopped accepting one would break callers
    that are right to use it. A reference that matches no account falls through
    unchanged and `open_bills.open_bill_position` refuses it by the sentence it
    already refuses an unknown id by — so a bad number and a bad id read the
    same to a stranger (`BR-TEN-003`, HR-1: a 403 would confirm the row exists).

    Read through customers' OWN published `account_queryset()`, resolved BY
    NAME — the seam `outstandings.py`, `reporting.py`, `autopay.py` and
    `writeoffs.py` already use (B1). Payments does not touch customers' ORM.
    """
    if not reference:
        return reference
    try:
        target = import_module(f"apps.{CUSTOMERS_MODULE}.selectors")
    except ImportError:  # pragma: no cover - defensive
        return reference
    read = getattr(target, ACCOUNT_READ, None)
    if not callable(read):  # pragma: no cover - customers publishes it
        return reference
    try:
        account = read().filter(account_no=reference).first()
    except (ValueError, TypeError):  # pragma: no cover - a text column
        return reference
    return reference if account is None else account.pk


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same reach its four sources already grant
def debtor(request: Any, account_id: str) -> Response:
    """`GET /debtors/{id}` — bills, ladder state and history, in ONE call.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  "Why does this account owe $1,284.60, and what have we already      ║
    ║   tried?" — 7·2's own question, which nothing answers today.         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The blueprint's TODAY line for this screen is four words: *"No such
    screen."* The debtor list is a report a clerk cannot drill into, so the
    person with the customer on the telephone opens four screens and assembles
    the answer themselves.

    ⚠ **THE SCREEN IS `P4.8` AND IS HELD TO WAVE 2.** This read is built ahead
    of it so the screen lane has one call instead of four — and that is said
    here, in `debtor_read`'s docstring and on the CR board's `P4.8` row,
    because **a read nothing calls is hard-won law 2's dead UI facing
    backwards**: it serves nothing, every test passes, and the feature does not
    exist. Its consumer is named so the absence is visible rather than assumed.

    QUERY PARAMETERS::

        as_of            the clerk's business day — REQUIRED, never a clock
        history_page     which page of the notice trail (default 1)
        history_per      how many rows (clamped to the platform's page sizes)

    **ONLY THE HISTORY PAGES, AND `NFR-3` IS WHY.** The position is one row, the
    ladder state is one row and the open bills are bounded by the account; the
    notice trail grows for ever, because every send AND every skip appends
    (J4 step 2) and the ladder runs nightly. It is paged with `LIMIT`/`OFFSET`
    **in the database**, and `history_count` is a real `COUNT(*)` — so there is
    no number here any row can be beyond (`NFR-5`).

    **A cross-tenant or unknown account id reads as ABSENT, never as
    forbidden** (`BR-TEN-003`, HR-1): a 403 would confirm the row exists.

    A READ. No clock, no money arithmetic, no write, no audit row.
    """
    require_tenant(request)
    per = clamp_page_size(request.query_params.get("history_per"))
    try:
        page_number = max(int(str(request.query_params.get("history_page"))), 1)
    except (TypeError, ValueError):
        # BR-SHL-011 "never error": a garbage page clamps to the first rather
        # than 404-ing, which is what `StandardPagination` does for every other
        # list in this product.
        page_number = 1
    try:
        body = debtor_read.debtor(
            # B14 rule 31 — the address bar carries `AC-2026-00001`.
            account_id=_resolve_account_id(account_id),
            as_of=_as_of(request),
            history_offset=(page_number - 1) * per,
            history_limit=per,
        )
    except PaymentRuleError as refusal:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-032",
            message_key="payments.record.refused",
            params={"detail": str(refusal)},
        ) from refusal
    body["history_page"] = page_number
    return Response(body)


urlpatterns = [
    # ⚠ ORDER AND OWNERSHIP, checked rather than assumed. `debtors` is a literal
    # claimed by nothing else in `config/urls.py`: payments declares
    # `outstandings`, `collections/run`, `collections/ladder`, `write-offs`,
    # `refunds`, `deposits`, `bank-*` and `payments`; customers owns
    # `accounts/<id>/…`. Two segments, and no `<str:…>` catch-all exists above
    # it that could read "debtors" as somebody's id — the `deposits/import`
    # shape this module's siblings record.
    path("debtors/<str:account_id>", debtor),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.3 · 05-prototype/06 Payments Page Blueprint.pdf
#         screen 7·2 (pp.83–84) · apps/payments/debtor_read.py · api.py
#         (`outstandings`, the list this drills into) · BR-SHL-025 · BR-TEN-043
# generated: 2026-09-23 by the CR-138 lane P4-READS
# checklist: A✔ B=deferred(`P4.8` owns screen 7·2, HELD to wave 2 — NAMED, see
#            the view docstring) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the address answered `Resolver404` before this file
#        was included; quoted verbatim in the test file's header.
# exceptions:
#   (1) ⚠ **ITS CONSUMER IS `P4.8`, WHICH IS HELD.** Said out loud in three
#       places rather than left to be noticed (law 2, reversed).
#   (2) `as_of` IS REQUIRED AND IS NOT DEFAULTED TO TODAY. BR-TEN-043 — this
#       layer reads no clock, and a position dated by the server is dated in
#       the server's timezone.
#   (3) NO `days_late` MEMBER. It is `as_of` − `oldest_due_on` (BR-PAY-032) and
#       both travel on the body; computing it here as well as on the board is
#       how a screen and a letter come to disagree by a day.
#   (4) ONLY THE HISTORY PAGES. The other three are bounded by the ACCOUNT, and
#       paging a one-row position would be furniture.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
