# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (GET /accounts — the S17 table + header roll-up) ·
#           US-CUS-002 (search + the AC-8 filter set on the same endpoint) ·
#           US-CUS-003 (POST /accounts · PATCH /accounts/{id} ·
#           POST /accounts/{id}/activate — the S18 New Account write path) ·
#           US-CUS-004 (POST /accounts/{id}/move-in — S19) ·
#           US-CUS-005 (POST /accounts/{id}/move-out — S20)
#           Screens: S17 · S18 · S19 · S20 · S21
# Rules:    BR-CUS-017 (at most ONE active account per unit — refused 409 here,
#           enforced in services) · BR-CUS-068 (POST /accounts/master — the
#           premises' master account over its common areas, PO 2026-08-22) ·
#           BR-CUS-018 (POST creates the pending draft;
#           activation is its own call) · BR-CUS-020 (vacant-unit rule) ·
#           BR-CUS-030 (move-out closes the account) · BR-CUS-031 (the
#           final-bill handoff this endpoint returns and does not persist) ·
#           BR-CUS-056 (the outgoing account owns the move day) ·
#           BR-CUS-053 (S17 capability row: search/filters/default sort) ·
#           BR-SHL-011 (list grammar q/sort/dir/page/per/f.<name> via BE-05) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC; A4 gives Executive
#           VIEW on Premises/Accounts, so writes are Admin-or-Clerk) ·
#           BR-MET-036 (occupancy derives from what this endpoint writes — and
#           a move-out is what frees it again)
# Tests:    06-backend/tests/test_us_cus_003_account_write.py ·
#           06-backend/tests/test_us_cus_003_account_race.py ·
#           06-backend/tests/test_us_cus_004_005_move_in_out.py ·
#           06-backend/tests/test_us_cus_004_move_in_race.py ·
#           06-backend/tests/test_w5_move_out_endpoints.py (S20 steps 3/4 —
#           the four routes over apps/customers/move_out_settlement.py)
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) · FI-01 typed
#           client · 06-backend/openapi/schema.json (the committed contract
#           snapshot moves with any endpoint added here — BE-11 TC05)
# ───────────────────────────────────────────────────────
"""customers API endpoints per A11 as amended by 11b §2.6.

THIN by law (B8/LAW 0): every write goes through services (sole writer), every
read through selectors; no ORM here. Refusals are catalog exceptions rendered
by the BE-02 handler (G9); role gates are the BE-04 permission classes AND the
service-layer @require_role guards (defense in depth, BR-SHL-025).

Role posture, from A4: "Premises / Accounts — System Admin Full · Billing Clerk
Full · Executive View". So reads are open to any tenant role and every write is
`AdminOrClerk` — US-CUS-001 TC-6 is exactly that ("Priya Menon (Executive)
opens the list … server rejects a forged POST").

The 11b §2.6 rows this slice serves, and the ones it deliberately does not:

    GET    /accounts                 US-CUS-001/002   S17 list + roll-up
    POST   /accounts                 US-CUS-003       S18 create (draft by
                                                      default, BR-CUS-018)
    GET    /accounts/{id}            US-CUS-003       read-back / S21 header
    PATCH  /accounts/{id}            US-CUS-003       attribute edits
    POST   /accounts/{id}/activate   US-CUS-003       draft → occupant
    POST   /accounts/{id}/move-in    US-CUS-004       S19 — the NEXT occupant of
                                                      {id}'s unit (a new account)
    POST   /accounts/{id}/move-out   US-CUS-005       S20 — {id} leaves; the unit
                                                      derives Vacant
    POST   /units/{unit_id}/move-in  DEF-CUS-6353     S19 on a unit nobody has
                                                      lived in (same body, same
                                                      guards as the account door)
    POST   /accounts/master          BR-CUS-068       the premises' MASTER
                                                      account (PO 2026-08-22,
                                                      OQ-314 second half)
    GET    /accounts/{id}/close-impact      US-CUS-005 S20 step 3 — B19 §15.9's
                                                      five money landings
    POST   /accounts/{id}/settle-shortfall  US-CUS-005 S20 step 4 — BR-CUS-082 /
                                                      BR-CUS-097 (W5 task 5.8)
    POST   /accounts/{id}/refund            US-CUS-005 BR-CUS-081 (W5 task 5.9)
    POST   /accounts/{id}/hold-excess       US-CUS-005 BR-CUS-096 (W5 task 5.9)
    GET    /accounts/imports/template US-CUS-019      S68 — the PUBLISHED
                                                      template (BR-CUS-046)
    POST   /accounts/imports         US-CUS-019       S68 — stage + validate
    GET    /accounts/imports/{id}    US-CUS-019       S68 — the staged preview
    POST   /accounts/imports/{id}/commit  US-CUS-019  S68 — "N created · N failed"

    NOT here: /accounts/{id}/move-out/preview (11b §S20 — the preview is B4.3
    final-bill math over invoices billing does not have),
    PUT /accounts/imports/{id}/mappings (11b §S68 — the BR-CUS-052 value-mapping
    step is US-CUS-020 and is not built; an unmapped legacy code is a ROW ERROR,
    which is what that rule says happens to one),
    /customers* (the BR-CUS-054 entity HAS a table as of 2026-08-11, but no
    story owns a customer LIST or DETAIL endpoint yet — US-CUS-008's "all
    accounts for this customer" chip is the first that will),
    /accounts/{id}/notes · /documents · /adjustments · /statements · /notices ·
    /plan-changes · /payment-plans (later stories, later waves). None of them is
    stubbed as an endpoint: a route that 501s is a promise, and these have no
    rows to promise anything about yet.

    ⚠ **SUPERSEDED 2026-09-23 (`DEF-CUS-6353`).** This read: *"11b §S19 defines
    ONE move-in row and it is account-scoped, so the STANDALONE S19 entry (S17 →
    Move-in on a unit with no predecessor) has no path of its own. It is served
    by `POST /accounts` with an occupying status … No endpoint is invented for
    it."* The move-in approval flow ruled that day sends an approved request for
    a never-occupied unit straight to the move-in wizard, so that answer became
    a dead end on the ruled flow. `POST /units/{unit_id}/move-in` is the unit's
    door; it runs the SAME `services._move_in` body and guards as the account's.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.customers import (
    account_documents,
    account_import,
    close_out as close_out_service,
    customer_edit,
    deposit as deposit_capability,
    disconnect_reads,
    discounts,
    move_in_list,
    move_in_units,
    move_out_settlement,
    move_reads,
    move_record_reads,
    owner_lookup,
    payment_plan,
    payment_plan_service,
    seams,
    selectors,
    services,
    transfer_reads,
    unit_correction,
)
from core import errors
from core.pagination import ListParams, parse_list_params
from core.permissions import AdminOrClerk, AdminOrExecutive, AnyTenantRole
from core.tenancy import require_tenant, tenant_path


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape: id from the session user,
    role server-attached by the identity layer (BE-04) — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    return data


def _prepaged(
    request: Any,
    rows: list[dict[str, Any]],
    total: int,
    params: ListParams,
    extra: dict[str, Any] | None = None,
    refetch: Any = None,
) -> Response:
    """The SAME DRF envelope, over a page the SELECTOR already took (`NFR-3`).

    ⚠ **WHY THIS EXISTS, AND WHY `_paginated` NO LONGER DOES.**
    `paginator.paginate_queryset(rows, request)` needs the WHOLE result set to
    slice, which is the `NFR-3` breach `BR-CUS-1046` required fixing with the
    default sort: 40,000 accounts built to draw fifty. `selectors.account_page`
    takes the page in SQL, so what arrives here is already one page and the
    count is a `COUNT(*)` — there is nothing left to slice.

    ⚠ **AND THIS IS NOW THE ONLY PAGING HELPER IN THIS FILE (`DEF-CUS-5753`,
    2026-09-18).** `_paginated` — the list-slicing one — went on living beside
    it for six days, and `GET /customers` was still on it: every customer the
    tenant holds built to draw fifty, plus one query per person for that
    person's accounts, measured at 5 statements for 4 customers and 17 for 16.
    A helper that builds every row is a trap the next list endpoint in this
    file falls into exactly as that one did, so it is DELETED rather than left
    with a warning on it — hard-won law 1: a comment claiming a guarantee is
    not the guarantee.

    ⚠ **THE ENVELOPE IS BYTE-FOR-BYTE THE ONE EVERY OTHER LIST SERVES**, and
    that is the whole point: `count` / `next` / `previous` / `results`, with the
    page links built by DRF's own `replace_query_param` so `?page=2` is formed
    the same way on this endpoint as on the other thirty. A second envelope
    shape on the product's busiest screen would be a client-side special case
    for ever.

    ⚠ **`page` IS RE-CLAMPED HERE AND NOT ONLY IN THE PARSER (BR-SHL-011).**
    `parse_list_params` clamps `page` to ≥ 1 but cannot know the last page — it
    has not counted anything yet. `StandardPagination.get_page_number` does that
    clamp for the queryset path; this path has to do it itself, or `?page=999`
    on a three-page list serves an empty `results` with a `previous` link
    pointing at page 998, and the screen shows a blank table rather than the
    last page.
    """
    from rest_framework.utils.urls import remove_query_param, replace_query_param

    per = max(params.per, 1)
    pages = max(1, math.ceil(total / per)) if total else 1
    number = min(max(params.page, 1), pages)
    if number != params.page:
        # The clamp above changed the page, so the rows we were handed are the
        # wrong ones. Ask again for the page that exists rather than serving a
        # blank table (BR-SHL-011: clamp, never error).
        #
        # ⚠ **`refetch` IS A PARAMETER SINCE 2026-09-12 (`CR-094-BRC01` wave I)
        # AND DEFAULTS TO WHAT IT ALWAYS DID.** This helper hard-coded
        # `selectors.account_page`, so the SECOND SQL-paged list in this module
        # — an account's documents — could either copy the whole envelope or
        # re-clamp wrongly. A copied envelope on one screen is a client-side
        # special case for ever, which is the sentence this function's own
        # docstring already makes about the accounts list.
        rows, total = (refetch or selectors.account_page)(replace(params, page=number))
        pages = max(1, math.ceil(total / per)) if total else 1
    url = request.build_absolute_uri()
    following = (
        replace_query_param(url, "page", number + 1) if number < pages and total else None
    )
    if number > 2:
        preceding = replace_query_param(url, "page", number - 1)
    elif number == 2:
        preceding = remove_query_param(url, "page")
    else:
        preceding = None
    body: dict[str, Any] = {
        "count": total,
        "next": following,
        "previous": preceding,
        "results": rows,
    }
    for key, value in (extra or {}).items():
        body[key] = value
    return Response(body)


# ── S17 Accounts list + S18 create (11b §2.6) ───────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # read: all three roles (A4 View for Executive)
def accounts(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            # A4: Executive is VIEW on Accounts. The service-layer @require_role
            # refuses this too — both halves exist on purpose (BR-SHL-025).
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        account = services.create_account(_actor(request), _payload(request))
        response = Response(account, status=201)
        response["Location"] = tenant_path(request, f"/accounts/{account['id']}")
        return response
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.ACCOUNT_SORTS,
        default_sort=selectors.ACCOUNT_DEFAULT_SORT,
        # `BR-CUS-1046` — *"The new newly created entries should always show on
        # the top."* Without this the grammar falls back to `asc` and the screen
        # opens on the OLDEST account, which looks exactly like a working
        # feature and is the inversion of the ruling.
        default_dir=selectors.ACCOUNT_DEFAULT_DIR,
        allowed_filters=selectors.ACCOUNT_FILTERS,
    )
    params = _with_ageing_segment(request, params)
    rows, total = selectors.account_page(params)
    return _prepaged(
        request, rows, total, params, {"rollup": selectors.accounts_rollup()}
    )


def _with_ageing_segment(request: Any, params: ListParams) -> ListParams:
    """CR-030 W2 task 2.4 — `GET /accounts?ageing=<segment>`, both spellings.

    CR-030 §5.1.3 writes the endpoint as **`GET /accounts?ageing=`** and BE-05's
    grammar (BR-SHL-011) writes every list filter as **`f.<name>=`**. Serving
    only one of them would make either the signed design or the platform
    grammar wrong on this screen, so both are accepted and normalised onto the
    ONE filter key — the design's bare form for the URL the CR names, `f.ageing`
    so the segment travels with the rest of the list state and survives a reload
    (TC-ACC-5). `f.ageing` wins if a client somehow sends both.

    An unrecognised segment is IGNORED, not refused: BR-SHL-011 says a list URL
    can never 4xx over its params.
    """
    key = selectors.AGEING_FILTER
    bare = request.query_params.get(key)
    if bare is None or key in params.filters:
        return params
    return replace(params, filters={**params.filters, key: str(bare)})


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ: all three roles (A4 View for Executive)
def account_deposit_standard(request: Any) -> Response:
    """`GET /accounts/deposit-standard?unit_id=&account_type=` — the deposit
    the unit's plan asks of this category (`BR-RAT-020/023`, `DEF-CUS-6369`).

    What the Deposit step on S18 (step 4) and S19 (step 5) SHOWS, read before
    the account exists: `{asks, amount, currency}`. It is the SAME walk the
    commit takes (`deposit.standard_for_unit` → `seams.deposit_rule_for_account`
    → `rating.deposit_rule_for`), so the figure on screen is the figure the
    server takes. `asks: false` means *this plan asks no deposit of this
    category* — the step then offers nothing to type (`OQ-CUS-12620` (a)).
    `account_type` is the category CODE the Customer step holds. Where the
    plan prices the deposit by meter size and no meter is fitted, the answer
    offers the plan's sizes (`pick_size`, `sizes`) and `size_class=` prices
    the one the clerk picked (`DEF-CUS-9521`).

    ⚠ **REGISTERED ABOVE `accounts/<str:account_id>` ON PURPOSE** — below it,
    `deposit-standard` would be read as an account id and answer 404."""
    require_tenant(request)
    return Response(
        deposit_capability.standard_for_unit(
            request.query_params.get("unit_id"),
            request.query_params.get("account_type"),
            # `DEF-CUS-9521` — the size the clerk picked where no meter is fitted.
            request.query_params.get("size_class"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive is VIEW on Accounts
def master_accounts(request: Any) -> Response:
    """`POST /accounts/master` — BR-CUS-068 (PO ruling 2026-08-22, OQ-314's
    second half): create the premises' MASTER account — one ordinary `accounts`
    row, `kind='master'`, payer = the owner/manager, attached to every
    common-area unit (or the `unit_ids` subset) through the same
    service-agreement linkage every account uses.

    Refuses 409 BIZ-STATE naming the unit for anything that is not one of this
    premises' common areas, for a unit already occupied, and for one already
    covered by another master; 422 when a common area has no plan (BR-MET-040)
    or the premises names no owner/manager and the payload no contact.

    There is deliberately NO separate list/detail route: a master account is an
    ordinary row, so `GET /accounts?f.kind=master` and `GET /accounts/{id}`
    serve it — that inheritance is the whole point of the ruled design."""
    require_tenant(request)
    account = services.create_master_account(_actor(request), _payload(request))
    response = Response(account, status=201)
    response["Location"] = tenant_path(request, f"/accounts/{account['id']}")
    return response


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def account_item(request: Any, account_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        return Response(services.update_account(_actor(request), account_id, _payload(request)))
    return Response(selectors.account_detail(account_id))


@api_view(["PATCH"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive may not write
def account_contact(request: Any, account_id: str) -> Response:
    """`PATCH /accounts/{id}/contact` — correct the account's primary contact.

    **`BR-CUS-045`'s PII columns, keyed to the ACCOUNT — a different table from
    `PATCH /customers/{id}`**, which writes the `customers` row reached through
    `customer_accounts`. The Overview's CUSTOMER group renders this one, and
    until 2026-09-13 nothing in the product could write it: the wizards CREATE a
    contact and the portal's self-service door writes the customer. The Product
    Owner found it by driving the screen — *"I cannot edit Customer details"*.

    The guard is on the service as well (`BR-SHL-025`: the server-side guard is
    THE guard), so the write refuses twice.
    """
    require_tenant(request)
    return Response(
        services.update_account_contact(_actor(request), account_id, _payload(request))
    )


@api_view(["PATCH"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive may not write
def account_mailing_address(request: Any, account_id: str) -> Response:
    """`PATCH /accounts/{id}/mailing-address` — where the BILL goes.

    Hard rule 8's first named exception (`customers.addresses kind='mailing'`),
    which had a CREATE path and no correction path at all. `kind` is not read
    from the body: this route writes `mailing` and nothing else, so the retired
    `kind='service'` cannot arrive through it (`BR-MET-1161`). An empty `line1`
    removes the row, which is how the account says *the bill goes to the service
    address* — the sentence the screen already draws.
    """
    require_tenant(request)
    return Response(
        services.update_account_mailing_address(_actor(request), account_id, _payload(request))
    )


@api_view(["PATCH"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive may not write
def account_co_applicant(request: Any, account_id: str) -> Response:
    """`PATCH /accounts/{id}/co-applicant` — the account's SECOND person.

    PO ruling 2026-09-23 (T4, closing `OQ-CUS-12514`), verbatim: *"a) Store a
    second person on the account (name, email, phone), shown on the account
    page"*. The sale writes one; this is the door the account page's pencil
    uses to correct, add or remove it. `{"full_name": ""}` removes it.
    """
    require_tenant(request)
    return Response(
        services.update_account_co_applicant(_actor(request), account_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive may not activate
def account_activate(request: Any, account_id: str) -> Response:
    """BR-CUS-018's other half: the saved draft becomes the unit's occupant.
    Refuses 409 BIZ-STATE when the unit already has one (BR-CUS-017)."""
    require_tenant(request)
    return Response(services.activate_account(_actor(request), account_id, _payload(request)))


@api_view(["GET", "POST"])
# ⚠ **`AdminOrExecutive`, NOT `AdminOrClerk`, AND THAT IS THE RULING RATHER THAN
# A STRICTER GUESS.** `BR-CUS-1047` requires *"a supervisor's approval"*; A4's
# signed grid gives `Approve` to System Admin and Executive and `Request` to a
# Billing Clerk, and `OQ-042`'s closure names the same two verbatim (*"supervisor
# = SysAdmin/Executive"*). This class's own docstring says so: *"+ approvals"*.
# The service under it carries the same guard, so the write refuses twice
# (BR-SHL-025 — server-side enforcement is THE enforcement).
@permission_classes([AdminOrExecutive])
def account_correct_unit(request: Any, account_id: str) -> Response:
    """POST /accounts/{id}/correct-unit — `BR-CUS-1047` (PO ruling 2026-09-12).

    Re-points an account at another unit AS A CORRECTION: a `reason_code` from a
    fixed list of three, approved by the supervisor making the call, effective
    TODAY (an `effective_on` in the body is refused BY NAME), and **every issued
    bill left exactly as it is** (hard rule 4).

    ⚠ **A MOVE IS NOT A CORRECTION.** A customer who has actually moved still
    leaves by `POST /accounts/{id}/move-out` and arrives by
    `POST /accounts/{id}/move-in` — the bills, meters and reads belong to the
    unit and must not follow a person. This door serves a RECORD that named the
    wrong unit, and every reason it accepts says so.

    Refuses 403 AUTH-002 for a Billing Clerk, 409 BIZ-STATE for a master
    account, for an account with no unit, for the unit it is already on and for
    a unit another account occupies (`BR-CUS-017`'s surviving half), and 422 for
    an unknown reason or a missing one.

    GET serves this account's corrections, newest first — the Overview's
    history, and the answer to *"why is this account on Suite 2 when five bills
    say Suite 1?"*"""
    require_tenant(request)
    if request.method == "GET":
        return Response({"items": unit_correction.corrections_for(account_id)})
    return Response(
        unit_correction.correct_account_unit(_actor(request), account_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4: Accounts = Full for Admin/Clerk, View for Executive
def account_move_out(request: Any, account_id: str) -> Response:
    """POST /accounts/{id}/move-out (11b §S20 · US-CUS-005 · BR-CUS-030).

    The occupant leaves and the unit derives Vacant again (BR-MET-036). The
    response carries the BR-CUS-031 `final_bill_handoff` this module can
    assemble and a `warnings` list naming every downstream that does not exist
    — no final bill, no deposit settlement, no dunning stop.

    11b also lists `POST /accounts/{id}/move-out/preview`. It is NOT mounted:
    the preview is B4.3 final-bill math over invoices billing does not have, and
    a route that answers 501 is a promise (see the module docstring)."""
    require_tenant(request)
    return Response(services.move_out(_actor(request), account_id, _payload(request)))


# ── DEF-724 · THE CLOSE-OUT — the terminal path a CUT customer has (BR-CUS-430) ──
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  A SECOND DOOR, AND `account_move_out` ABOVE IS DELIBERATELY UNTOUCHED   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# PO ruling 2026-08-27: *"A disconnected customer can never be closed - Add a
# separate close-out act — Cleaner in the record"*. The temptation this file
# must resist is relaxing the move-out route's occupancy check, which would file
# a disconnection as a move-out in the permanent record — and to a regulator
# those are not the same event (BR-CUS-430). Two routes, two acts, two audit
# actions (`account.closed` vs `account.closed_out`).
#
#   GET  /accounts/{id}/close-out   `close_out.eligibility`  — can it, and why not
#   POST /accounts/{id}/close-out   `close_out.close_out`    — do it
#
# The GET is a PREVIEW and writes nothing: it exists so a clerk is never offered
# a button that will refuse them, and so the date BR-CUS-431 will write into
# `closed_at` is shown BEFORE it is written — it is the one thing on this screen
# that no correction row can un-say.


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — Executive may not close an account
def account_close_out(request: Any, account_id: str) -> Response:
    """GET/POST /accounts/{id}/close-out (DEF-724 · BR-CUS-430 · BR-CUS-431).

    GET answers `eligible` with the blocking rule's own words when it is False,
    the cut date that WILL become `closed_at`, the balance read from AR (never
    the `accounts.balance` cache — BR-CUS-015), what BR-CUS-082 will do with it,
    and the four stated absences a screen may not paper over.

    POST performs the act. No `preview` route is mounted beside it: the GET IS
    the preview, and a second one would be two answers to one question."""
    require_tenant(request)
    if request.method == "GET":
        return Response(close_out_service.eligibility(account_id))
    return Response(close_out_service.close_out(_actor(request), account_id, _payload(request)))


# ── S20 steps 3 and 4 — the settlement, the shortfall, the refund ──────────
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FOUR ROUTES OVER ONE MODULE THAT NOTHING COULD REACH (hard-won law 2)   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# `apps/customers/move_out_settlement.py` shipped built and tested on
# 2026-08-24 with its own lifecycle block saying so: *"D=deferred(no-API-half —
# S20 steps 3/4 have no route yet; another lane owns api.py)"*. This is that
# half. Nothing about the settlement changes here — no figure is computed in
# this layer, no landing is chosen, no gap is defaulted; the module answers and
# the view returns the answer.
#
#   GET  /accounts/{id}/close-impact     `settlement_for`      — B18 §6.2
#   POST /accounts/{id}/settle-shortfall `shortfall_decision`  — B18 §6.2
#   POST /accounts/{id}/refund           `refund_disposition`  — ADDED
#   POST /accounts/{id}/hold-excess      `hold_excess`         — ADDED
#
# **The first two names come from B18 §6.2 and from the screen** — the S20
# wizard already reads `GET /accounts/{id}/close-impact` through
# `moveShared.closeImpactPort()` and already names `POST …/settle-shortfall` in
# step 4's reason — so those paths are the frontend's, not this lane's. The
# last two are ADDITIONS: B18 §6.2 lists the move-out gap as *"❌ two"* and no
# document or screen names a path for BR-CUS-081's refund or BR-CUS-096's hold,
# which are the other two callables the module publishes. REPORTED as additions
# rather than slipped in, exactly as §S24's `…/payment-plans/preview` was.
#
# **200, not 201, on all three POSTs.** Each writes an `audit_log` row and
# NOTHING else: there is no `final_settlements` table, customers writes no
# invoice, payment or journal line, and every response carries
# `persisted: false` with the reason. A 201 with a `Location` would promise a
# resource that does not exist.
#
# ⚠ **`AdminOrClerk` ON THE READ, WHICH A4 WOULD GIVE AN EXECUTIVE.** A4's
# "Premises / Accounts" row is System Admin Full · Billing Clerk Full ·
# Executive **View**, and every other read in this module is `AnyTenantRole`
# for that reason. `move_out_settlement.settlement_for` is guarded
# `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and refuses an Executive itself
# (asserted by `test_w5_wired__an_executive_may_not_settle_or_decide`), so a
# view class that admitted one would hand it straight to a 403 from the layer
# below. The narrower gate is mounted so the two halves agree, and the
# divergence is REPORTED rather than resolved here: widening or narrowing the
# rule is the settlement module's call and that file is not this lane's.
def _stated_as_of(raw: Any) -> Any:
    """The business day a move-out settlement is worked on, or None (CS-20).

    BR-CUS-057's interest accrues from the original receipt date TO a day, and
    that day is the caller's: BR-TEN-043 and gate G6 keep a clock out of a money
    path, so this layer parses what a person typed and never fills one in.

    ⚠ **A BAD DATE IS REFUSED, NEVER READ AS ABSENT.** Absent means *"nobody
    stated a day"* and the settlement then reports its interest gap honestly; a
    typo read as absent would give the same answer for a different reason, so a
    clerk who DID type a date would be told the engine is missing. That is
    `_stated_final_bill` directly below taking the same posture on the same
    screen, and the reason is the same one: a settlement decides where a
    departing customer's money goes.
    """
    from datetime import date as _date

    if raw is None or str(raw).strip() == "":
        return None
    try:
        return _date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.account.date_invalid",
            field_errors=[{"field": "as_of", "code": errors.VAL_FORMAT}],
        ) from bad


def _stated_date(raw: Any, field: str) -> Any:
    """`_stated_as_of`'s parser, reporting the field the CALLER actually named.

    ⚠ **IT EXISTS BECAUSE REUSING `_stated_as_of` NAMES THE WRONG FIELD.** That
    function hardcodes `"field": "as_of"` in its `field_errors`, which is right
    on the settlement routes where the parameter IS `as_of` and wrong on the
    final-bill preview, where the dates are `moved_out_on` and `period_start`.
    A screen highlights the field a `field_errors` entry names, so the reused
    version would have marked a field that is not on the form and left the one
    the clerk mistyped looking fine — a refusal that reaches a clerk as a
    puzzle, which is `DEF-CWP-3925`'s shape one layer down.

    Everything else is `_stated_as_of`'s posture unchanged, including the part
    that matters: **a BAD date is refused and never read as absent.** Absent
    means *nobody stated a day*; a typo read as absent would answer the same
    way for a different reason, and on a money path that is the difference
    between *you have not told us yet* and *we ignored what you told us*.
    """
    from datetime import date as _date

    if raw is None or str(raw).strip() == "":
        return None
    try:
        return _date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.account.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from bad


def _stated_final_bill(raw: Any) -> Any:
    """B19 §15.9.0's left-hand column, restated by the caller as TEXT.

    Billing publishes no per-account final-bill total, so the settlement takes
    the figure the wizard is already showing and says on the payload that it
    was stated (`final_bill_stated_by_caller`). Absent, the read model reports
    `final_bill_not_stated` and states NO LANDING — which is the answer, not a
    failure, and is why nothing here substitutes a zero.

    A JSON number arrives from DRF as a `float` and is passed through
    UNTOUCHED: `move_out_settlement._money` refuses it by name (CLAUDE.md rule
    2 — never float), and a second copy of that refusal in this layer is a
    second place for it to drift. What IS handled here is text that is not a
    number: `Decimal("nine")` inside the service is an unhandled
    `InvalidOperation` and therefore a 500, and a 500 is not a refusal.
    """
    from decimal import Decimal, InvalidOperation

    if not isinstance(raw, str):
        return raw
    if not raw.strip():
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.move_out.money_not_a_decimal",
            field_errors=[{"field": "final_bill", "code": errors.VAL_FORMAT}],
        ) from bad


def _settlement_payload(request: Any) -> dict[str, Any]:
    """The decision body, with the two stated fields normalised on the way in.

    ⚠ **THIS DOCSTRING SAID *"the ONE money field"* UNTIL 2026-09-03.** CR-059
    CS-20 gives the settlement a second thing the caller states — the day
    BR-CUS-057's deposit interest accrues to — and it is normalised here for the
    same reason the money is: a bad date reaching the service is an unhandled
    exception, and a 500 is not a refusal.
    """
    payload = _payload(request)
    return {
        **payload,
        "final_bill": _stated_final_bill(payload.get("final_bill")),
        "as_of": _stated_as_of(payload.get("as_of")),
    }


#: `DEF-CUS-5931` — the step-2 capture a preview may be priced from, in the
#: shape the wizard already posts to the move-out door at step 6. Named here so
#: the read and the write cannot drift into two spellings of one row.
FINAL_BILL_PREVIEW_READS = "final_reads"


def _keyed_reads(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """The reads a clerk has KEYED and nobody has committed, normalised.

    ⚠ **REFUSED RATHER THAN FILTERED WHEN THE SHAPE IS WRONG.** A row that is
    not an object, or that names no meter, is a caller sending something this
    door does not understand — and silently dropping it would price a final
    bill from FEWER meters than the clerk keyed, on a screen that then says it
    priced from what they keyed. That is a wrong figure wearing a true sentence.

    An EMPTY list is lawful and means *nothing keyed yet*: the preview then
    prices from committed reads alone, which is exactly what it did before the
    PO's ruling of 2026-09-20.
    """
    rows = payload.get(FINAL_BILL_PREVIEW_READS)
    if rows is None:
        return ()
    if not isinstance(rows, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.event_reads.rows_required",
            field_errors=[{"field": FINAL_BILL_PREVIEW_READS, "code": errors.VAL_FORMAT}],
        )
    keyed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("meter_no") or "").strip():
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="customers.event_reads.rows_required",
                field_errors=[{"field": FINAL_BILL_PREVIEW_READS, "code": errors.VAL_FORMAT}],
            )
        keyed.append(row)
    return tuple(keyed)


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_move_out_estimate(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/move-out-estimate?meter_no=&moved_out_on=` —
    `DEF-BIL-10052` task 5: the estimate step 2 shows when *Estimate* is ticked,
    computed by billing's own draft-bill path so step 2 and step 3 agree.
    A READ: nothing is written."""
    require_tenant(request)
    meter_no = str(request.query_params.get("meter_no") or "").strip()
    moved_out_on = _stated_date(request.query_params.get("moved_out_on"), "moved_out_on")
    if not meter_no or moved_out_on is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.account.move_out_date_required",
            field_errors=[{"field": "moved_out_on" if meter_no else "meter_no", "code": errors.VAL_REQUIRED}],
        )
    answer = seams.estimate_closing_usage(
        account_id=account_id, meter_no=meter_no, moved_out_on=moved_out_on
    )
    return Response(answer or {"estimated": False, "reason": "billing_not_published"})


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])  # A4 reads_billing_runs: Executive is VIEW
def account_final_bill_preview(request: Any, account_id: str) -> Response:
    """`GET|POST /accounts/{id}/final-bill-preview` — S20 step 3's FIGURE.

    **PO ruling 2026-09-19 on step 3 of the move-out wizard, verbatim:** *"we
    need to do it"*. This is the keystone that ruling names: steps 3, 4 and 5
    were one blocked chain because `close-impact` takes a final-bill figure the
    caller states and **nothing in the product ever stated one**, so `landing`
    was `null` on every account and step 4's four shortfall radios rendered
    enabled over a `POST` that refused with `no_shortfall` every single time.

    **IT PRICES AND POSTS NOTHING.** The Billing blueprint settles it itself on
    p112, in a dashed panel: *"NO BILL IS ISSUED BY THIS SCREEN. Billing raises
    the final bill; this wizard prices what it will contain and posts nothing.
    The figures above are a settlement position, not an invoice, and the
    account closes owing what the invoice will say."* No invoice, no invoice
    line, no journal line, no payment, no ledger entry and **no bill number** —
    stage 6 is where a draft is written and where `core.numbering` spends a
    number (BR-BIL-063), and it is not on this path. That is what makes the
    figure safe inside a wizard a clerk may abandon halfway.

    **`?moved_out_on=` IS REQUIRED AND IS NEVER A CLOCK** (BR-TEN-043, gate
    G6): it is the move-out day the clerk stated at step 2, it is the day the
    bill runs THROUGH (BR-CUS-056 — the outgoing account pays the move day),
    and it is the day BR-CUS-057's deposit interest accrues to. A settlement
    re-opened next month recomputes to the same figure because the date is a
    stored business fact. `?period_start=` is OPTIONAL and re-prices a window a
    clerk corrected; absent, billing derives the first unbilled day itself and
    **refuses** an account it cannot derive one for rather than guessing.

    **WHAT TO DO WITH THE ANSWER:** pass `total` — the CHARGES — straight to
    `GET /accounts/{id}/close-impact?final_bill=`. It is deliberately NOT net
    of BR-MET-107's export credit and NOT net of the deposit: `close-impact`
    applies both and serves `export_credit`, `final_bill_net` and the five
    landings. Subtracting either here would double-count it.

    ⚠ **`POST` PRICES THE READS THE CLERK KEYED AND WRITES NOTHING EITHER** —
    PO ruling 2026-09-20, verbatim *"option b is correct"* (`DEF-CUS-5931`).
    Step 2 asks for the closing register and step 6 writes it with the close, so
    at step 3 the closing read does not exist and every move-out refused on a
    missing meter factor. The body carries `final_reads` in the SAME shape the
    move-out door takes at step 6 — `[{"meter_no": "M-4021", "value": "52410"}]`
    — and it is read, never stored. `GET` is unchanged and prices from committed
    reads alone; both methods answer the identical payload, and the one on the
    wire that says which is `priced_from_uncommitted_reads`.

    ⚠ **A POST THAT WRITES NOTHING IS THIS PRODUCT'S OWN SHAPE FOR A PRICED
    PREVIEW**, not an exception invented here: `POST /billing/one-time/preview`
    is phase 1 of the one-time bill and its comment says *"writes NOTHING"*. The
    method is the body's, not the side effect's — a capture of eleven registers
    does not belong in a query string, and a re-read with a corrected reading
    must not be cached by anything between the clerk and the engine.

    A READ — no `audit_log` row, because nothing moved. `account_close_impact`
    directly below states the same for the same screen.
    """
    require_tenant(request)
    keyed_reads = _keyed_reads(_payload(request)) if request.method == "POST" else ()
    moved_out_on = _stated_date(request.query_params.get("moved_out_on"), "moved_out_on")
    if moved_out_on is None and request.method == "POST":
        moved_out_on = _stated_date(_payload(request).get("moved_out_on"), "moved_out_on")
    if moved_out_on is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            # ⚠ **AN EXISTING KEY, NOT A NEW ONE.** `customers.account.
            # move_out_date_required` — *"Enter the move-out date."* — already
            # says exactly this and is present in all ELEVEN catalogues. B14
            # rule 35 makes a catalogue its own language rather than a
            # translation of English, so minting a twelfth key here would have
            # meant ten machine translations or ten missing entries, and a
            # refusal that reaches a clerk as silence (`DEF-CWP-3925`'s shape,
            # and the 21 live refusals G32 could not see).
            message_key="customers.account.move_out_date_required",
            field_errors=[{"field": "moved_out_on", "code": errors.VAL_REQUIRED}],
        )
    answer = seams.preview_final_bill(
        account_id=account_id,
        moved_out_on=moved_out_on,
        period_start=_stated_date(request.query_params.get("period_start"), "period_start"),
        keyed_reads=keyed_reads,
    )
    if answer is None:
        # The seam is unpublished. A GAP IS SERVED, NEVER PAPERED OVER — the
        # same posture `close-impact` takes for every term it cannot read, and
        # the same SHAPE, so step 3 renders one thing whichever half is missing.
        return Response(
            {
                "account_id": str(account_id),
                "period_end": moved_out_on.isoformat(),
                "issues_nothing": True,
                "writes": [],
                "priced": False,
                "lines": [],
                # ⚠ **THE RULE ID AND THE MODULE PATH GO IN `br_ref`, NEVER IN
                # `detail` — B14 rule 32 (no rule id or internal code in
                # clerk-facing copy) and rule 33 (RATIONALE is ZERO WORDS ON
                # SCREEN; it belongs in the code and the register).** `G28`
                # caught this lane writing both into the prose and went from
                # *"no internal reference on screen"* to one, which is the only
                # reason it is worth a comment: the structured shape is what
                # every `unavailable[]` entry on `close-impact` already uses,
                # and it was reached for out of habit rather than by reading
                # the neighbours. WHY billing owns pricing is recorded here, in
                # the code, where rule 33 says it belongs: customers may not
                # price a bill (BR-CUS-037) and will not invent a figure — an
                # amount shown here with no engine behind it is invented money
                # on the one bill nobody looks at again.
                "priced_from_uncommitted_reads": False,
                "uncommitted_read_services": [],
                "priced_unavailable": {
                    "reason": "final_bill_preview_seam_unpublished",
                    "br_ref": "BR-CUS-037",
                    "detail": "the closing period could not be priced. Billing is "
                    "not answering, and no amount is shown rather than one that "
                    "was guessed.",
                },
            }
        )
    return Response(answer)


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the service's own @require_role, mirrored — see above
def account_close_impact(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/close-impact` — B19 §15.9's step 3, serialized.

    ONE subtraction and five landings: everything outstanding (the prior
    balance from the LEDGER plus the final bill net of BR-MET-107's export
    credit) less what is applied against it (the deposit, its BR-CUS-057
    interest, this account's own credit). `?final_bill=` states the drafted
    total as TEXT.

    **A GAP IS SERVED, NEVER PAPERED OVER.** When a term cannot be read the
    payload carries `landing: null`, the `gaps[]` codes and an `unavailable[]`
    entry naming the rule that leaves each open — `deposit_interest_not_accrued`
    (BR-CUS-057's engine is not built), `open_disputes_not_readable`
    (only when a PUBLISHED dispute store cannot answer — BR-CUS-096 is
    SUSPENDED by PO ruling 2026-10-11, so no store at all reads as no dispute),
    `export_credit_exceeds_final_bill` (BR-MET-107's open half, deliberately
    not floored at zero), `sibling_credit_rule_unsigned` (OQ-362) and
    `held_excess_has_no_release_path`. This view returns those verbatim: a
    settlement decides where a departing customer's money goes, so a gap must
    reach the screen as a gap.

    A READ — no `audit_log` row, because nothing moved. The three decisions
    below each write their own, inside the service (hard rule 7).
    """
    require_tenant(request)
    return Response(
        move_out_settlement.settlement_for(
            _actor(request),
            account_id,
            final_bill=_stated_final_bill(request.query_params.get("final_bill")),
            # CR-059 CS-20 (2026-09-03). The day BR-CUS-057's interest accrues
            # TO, stated by the caller exactly as the final bill is, because
            # gate G6 keeps a clock out of a money path and a settlement
            # re-opened tomorrow must show the same figure unless somebody
            # moved the date. Absent, an account that holds a deposit keeps
            # reporting `deposit_interest_not_accrued` — the same fail-closed
            # answer it gave while the engine did not exist.
            as_of=_stated_as_of(request.query_params.get("as_of")),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-SHL-025 / A4 — a settlement is never a View action
def account_settle_shortfall(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/settle-shortfall` — S20 step 4 (B18 §6.2).

    *"Step 4 decides where the remaining balance goes. It cannot be skipped."*
    Reachable ONLY on the `short` landing; every other landing is refused by
    name (`customers.move_out.no_shortfall`) rather than recording a decision
    about nothing. `path` is one of three — collect · payment_plan · transfer — and an
    unknown one is refused with the closed set. ⚠ `write_off` is refused BY
    NAME (`customers.move_out.write_off_not_at_move_out`, PO 2026-10-12,
    *"MOVE-OUT DOES NOT WRITE OFF"*): the balance stays outstanding and is
    chased (BR-CUS-082); Finance or a System Admin writes it off later in
    Payments (BR-PAY-020).

    **The transfer TARGET is resolved from the data and is never a caller
    argument** (BR-CUS-097: *"a transfer cannot be built against an ambiguous
    target"*), which is what makes US-BIL-011 TC-6's forged transfer
    unrepresentable rather than merely rejected. No account id in this body is
    read as a destination.

    200: the decision is RECORDED — an `audit_log` row written by the service,
    `persisted: false` on the wire. ⚠ On `transfer` the books MOVE since
    2026-10-14 (`OQ-1250` → a, `CR-185-BRC10`): one AR→AR entry, owner account
    DR / this account CR, reported as `posting.posted: true`; on collect and
    payment plan no money moves.
    """
    require_tenant(request)
    return Response(
        move_out_settlement.shortfall_decision(
            _actor(request), account_id, _settlement_payload(request)
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_refund(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/refund` — BR-CUS-081's settle-and-refund.

    ADDED: no document or screen names this path (B18 §6.2's move-out row is
    the two above), so it is REPORTED as an addition. It exists because
    `refund_disposition` is a published callable of the settlement module and
    hard-won law 2 is what happens to one nothing can reach.

    *"settle the $142.30 from the $153.50 deposit and refund $11.20; the
    account closes at zero and the bill does NOT stand."* BOTH movements come
    back on one response, because a payload carrying only the refund reads as
    "the whole deposit went back" — the reading the PO rejected.

    Reachable ONLY on `refund_due`. `refused_excess` is refused by name and
    belongs to `hold-excess` below (BR-CUS-096). **The amount is the
    settlement's own and is never a caller input**, so a clerk cannot refund a
    figure they typed; `method` is the closed vocabulary ACH · mailed cheque ·
    carry to new account, and the forwarding street is required for the CHEQUE
    alone.

    It does not PAY. Payments owns `refunds`, whose `payment_id` is NOT NULL
    with no account column (OQ-195), so a deposit excess has no row to become —
    the response says so in `execution_unavailable[]` and this layer does not
    soften it.
    """
    require_tenant(request)
    return Response(
        move_out_settlement.refund_disposition(
            _actor(request), account_id, _settlement_payload(request)
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_hold_excess(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/hold-excess` — BR-CUS-096, *"hold until dispute close"*.

    ADDED for the same reason as `/refund` above, and REPORTED the same way.

    The `refused_excess` landing: the deposit is worth more than everything
    owed AND part of what is owed is disputed, so the excess is HELD — because
    the amount owed can still move. Refused by name on every other landing.

    ⚠ The response states, on every call, that **nothing chases the hold**:
    BR-CUS-096 does not say who releases it or on what clock, and there is no
    release path, no timer and no queue in this repository. That sentence
    (`held_excess_has_no_release_path`) is the deliverable; inventing a release
    clock here would be answering a question the PO has not been asked.
    """
    require_tenant(request)
    return Response(
        move_out_settlement.hold_excess(_actor(request), account_id, _settlement_payload(request))
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def move_in_messages(request: Any) -> Response:
    """`GET /move-ins/messages?category=&deposit_taken=&deposit_cleared=` (`DEF-CUS-6365`) —
    what the move-in's save will queue for the customer, for its review step.

    Readable by every role, like the move-in itself: the notification RULES are
    a Settings door a Billing Clerk may not open (`SettingsReadAnyWriteSystemAdmin`),
    and this serves only the answer those rules give for this one flow — which
    channels, which template — never the rules. A READ: nothing is written.
    """
    require_tenant(request)
    from apps.customers import notifications_seam

    category = (request.query_params.get("category") or "").strip() or None
    def flag(name: str) -> bool:
        return (request.query_params.get(name) or "").strip().lower() in ("1", "true", "yes")

    plan = notifications_seam.move_in_message_plan(
        category=category,
        deposit_taken=flag("deposit_taken"),
        deposit_cleared=flag("deposit_cleared"),
    )
    return Response({"results": [] if plan is None else list(plan), "served": plan is not None})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_subcategories(request: Any) -> Response:
    """`GET /accounts/subcategories` (`DEF-CUS-6426`) — the ACTIVE sub-categories
    a clerk picks under a category on New account and Move-in.

    ⚠ **A CUSTOMERS READ, NOT THE SETTINGS LOOKUP.** The same rows are served by
    `GET /lookups/account_subtypes`, a Settings door
    (`SettingsReadAnyWriteSystemAdmin`, A4 `settings_lookups`) that answers a
    Billing Clerk 403 — measured 2026-09-23 as the seeded clerk — so the two
    screens a clerk opens accounts on showed no sub-category at all. That door
    is left exactly as signed; this serves only what a picker needs (active
    rows, code, name, the category they hang under), with the posture of
    `GET /service-requests/categories`, which serves the categories themselves.
    The PO's ruling of 2026-09-23 (`OQ-CUS-12618`) names the source: Settings →
    Reference data → account categories and sub-categories.
    """
    require_tenant(request)
    from apps.customers import models as customer_models
    from core.tenancy import current_tenant_id

    rows = (
        customer_models.AccountSubtype.objects.filter(tenant_id=current_tenant_id(), active=True)
        .select_related("account_type")
        .order_by("name", "code", "id")
    )
    return Response(
        {
            "results": [
                {
                    "id": str(row.id),
                    "code": row.code,
                    "name": row.name,
                    "parent_code": row.account_type.code if row.account_type_id else None,
                }
                for row in rows
            ]
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_move_in(request: Any, account_id: str) -> Response:
    """POST /accounts/{id}/move-in (11b §S19 · US-CUS-004) — {id} is the
    OUTGOING account; the new occupant takes ITS unit.

    201 with a Location header, because this creates a NEW account with its own
    number (T4-06 step 5: reopening does not exist). Refuses 409 BIZ-STATE with
    BR-CUS-017 while the unit is still occupied, and with BR-CUS-056 when the
    start date lands on the outgoing account's move day.

    ⚠ **`services` — `BR-CUS-1101`, PO ruling 2026-09-25. OPTIONAL, and
    ABSENT MEANS ALL OF THEM.** A list of service codes saying which of the
    unit's services this account takes: *the unit has six, the account takes
    three*. A code the unit has no service point for is refused 422
    VAL-UNKNOWN-LOOKUP **naming it**, with the unit's own offer beside it —
    a clerk cannot buy a connection that does not exist. An EMPTY list is
    refused too (`final_reads`' reason): a screen that sent the key sent it
    because a clerk ticked boxes. Nothing is stored beyond the
    `service_agreements` rows themselves, so an absent agreement and a
    deliberate untick are the same fact, which the PO was shown and accepted."""
    require_tenant(request)
    account = services.move_in(_actor(request), account_id, _payload(request))
    response = Response(account, status=201)
    response["Location"] = tenant_path(request, f"/accounts/{account['id']}")
    return response


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def move_in_units_search(request: Any) -> Response:
    """`GET /move-ins/units?q=&page=&per=` (`DEF-CUS-10190`, PO 2026-10-17) —
    EVERY live unit of this utility a move-in may be for, VACANT FIRST, each
    row with its `state`, `occupant`, `selectable`, the `path` a move-in takes
    (`move_in` · `move_out_first` · `close_out_first`) and, when blocked, a
    `reason_key`. A removed unit is not listed. Paged in SQL (`NFR-3`), the
    standard envelope. See `move_in_units.search`."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    term = request.query_params.get("q") or ""
    unit_id = request.query_params.get("unit_id") or None
    rows, total = move_in_units.search(term, page=params.page, per=params.per, unit_id=unit_id)
    return _prepaged(
        request,
        rows,
        total,
        params,
        refetch=lambda p: move_in_units.search(term, page=p.page, per=p.per, unit_id=unit_id),
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def move_in_handover(request: Any) -> Response:
    """`POST /move-ins/handover` `{unit_id, opened_at, move_in_park_id?}`
    (`DEF-CUS-10190`) — the move-in found somebody still on the unit, so it
    raises the old occupant's MOVE-OUT as a draft (prefilled; the day before
    the move-in) and answers where to go. Writes one draft and nothing else;
    the account is settled by the normal move-out. A disconnected unit answers
    `close_out_first` and writes nothing. See `move_in_units.start_handover`."""
    require_tenant(request)
    return Response(move_in_units.start_handover(_actor(request), _payload(request)), status=201)


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def unit_move_in(request: Any, unit_id: Any) -> Response:
    """POST /units/{unit_id}/move-in (`DEF-CUS-6353`) — the move-in that names
    the UNIT, for a unit nobody has lived in. Same body, same guards and same
    201 + Location as `POST /accounts/{id}/move-in`: both run
    `services._move_in`, and the only difference is where the unit comes from.
    That includes `BR-CUS-1101`'s optional `services` list — same field, same
    refusals, validated against THIS unit's points.
    See `services.move_in_to_unit`."""
    require_tenant(request)
    account = services.move_in_to_unit(_actor(request), str(unit_id), _payload(request))
    response = Response(account, status=201)
    response["Location"] = tenant_path(request, f"/accounts/{account['id']}")
    return response


# ── S68 account onboarding import (11b §S68 · US-CUS-019) ──────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_import_template(request: Any) -> Response:
    """`accounts_template.csv` — the PUBLISHED template (BR-CUS-046).

    A real downloadable artifact, not a README sentence: the file an operator
    opens in a spreadsheet, fills in and uploads, carrying the column set the
    PO's AC-1 enumerates and a comment block stating the import ORDER
    (BR-CUS-047) so the rule arrives with the file rather than after the first
    failed run.

    One template, no per-tenant variant — the same standard S28 reads follows
    (BR-MET-032: mapping is re-detected on every upload, never remembered).

    ⛔ **CLOSED 2026-09-01 — `BR-CUS-1043` / `DEF-2592`.** This file publishes
    the column set of a door that no longer accepts uploads, and a template
    whose columns no live loader reads is the same *"promised and honoured by
    nothing"* fault as the `Customer #` cell one file along (`DEF-2593`). The
    live import hands out its own template, derived from the columns it actually
    reads. Kept and unreachable, like the two write doors."""
    require_tenant(request)
    services.refuse_retired_account_import()
    from django.http import HttpResponse

    response = HttpResponse(account_import.template_csv(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="accounts_template.csv"'
    return response


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # re-gated in services (BR-SHL-025)
def account_imports(request: Any) -> Response:
    """`POST /accounts/imports` — stage. BR-CUS-051: nothing is written to
    `accounts` or `customers` until the commit below.

    Answers 201 synchronously rather than 11b's 202 + job, for the reason the
    assets import packet already recorded: `core.jobs` has no registered store
    on this deployment, and a 202 pointing at a job that will never be polled
    is a worse promise than a synchronous answer. REPORTED, not invented."""
    require_tenant(request)
    result = services.stage_account_import(_actor(request), _payload(request))
    response = Response(result, status=201)
    response["Location"] = tenant_path(request, f"/accounts/imports/{result['id']}")
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_import_detail(request: Any, batch_id: str) -> Response:
    require_tenant(request)
    return Response(selectors.account_import_batch(batch_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_import_commit(request: Any, batch_id: str) -> Response:
    """`POST /accounts/imports/{id}/commit`.

    Refuses 409 BIZ-IDEMPOTENT when this batch — or the same FILE under the
    same batch tags — has already been committed (CLAUDE.md rule 6 / DB-12).
    Otherwise always answers the BR-CUS-051 summary: "N created · N failed",
    with the per-row error report beside it."""
    require_tenant(request)
    return Response(services.commit_account_import(_actor(request), batch_id, _payload(request)))


# ── S21 Notes tab + S22 Add note (11b §2.6 · US-CUS-011 / US-CUS-015) ──────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # A4: Executive VIEWS an account's notes
def account_notes(request: Any, account_id: str) -> Response:
    """`GET|POST /accounts/{id}/notes` — the Notes tab and the S22 modal.

    NOT paginated, deliberately, and it is the one list in this module that is
    not: 11b G5's rule is about LIST SCREENS, and the capability matrix types
    this as a CARD LIST scoped to one account, ordered pinned-first. A page
    boundary through a pinned-first order would hide exactly the note somebody
    pinned so it would not be missed."""
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        note = services.create_account_note(_actor(request), account_id, _payload(request))
        response = Response(note, status=201)
        response["Location"] = tenant_path(request, f"/accounts/{account_id}/notes/{note['id']}")
        return response
    return Response({"results": selectors.account_notes(account_id)})


# ── S21 Documents tab · ACC-S8 (11b §S21 · BR-CUS-036 · CR-094-BRC01 wave I) ──
@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([AnyTenantRole])  # A4: Executive VIEWS an account's documents
def account_documents_list(request: Any, account_id: str) -> Response:
    """`GET|POST /accounts/{id}/documents` — the Documents tab and its upload.

    ⚠ **PAGED IN SQL, NOT IN PYTHON (`NFR-3`).** `CLAUDE.md` counts four live
    breaches that all named the old 3,000-connection ceiling as their excuse
    (`DEF-PAY-4221`); this is a new list and it is not the fifth. A landlord's
    four hundred filings are counted with `COUNT(*)` and drawn ten at a time.

    ⚠ **`POST` IS `AdminOrClerk`, NOT `AnyTenantRole`** — `BR-SHL-031`, verbatim:
    *"v1 uploads staff-mediated, consumer portal v2"*. An Executive may read the
    tab and may not file into it, which is the same split `account_notes` makes
    one tab across.

    Multipart because the bytes come through the application: `file` is the
    part, everything else is a form field.

    ⚠ **413 AND 415 ARE CAUGHT HERE AND NOT RAISED AS CATALOG REFUSALS.**
    `HTTP_STATUS_BY_CODE` maps a B12 §3 code to a status and neither transport
    row has one, so a `ValidationError` would answer 422 to a file over the cap
    (B12 r1's HTTP-series rows; 11b G11). The body is the SHARED envelope
    `core.errors.http_series_refusal_body`, which is the kernel follow-up
    `apps/tenancy/api.py` reported in 2026-08-09 and which this wave built
    rather than copying.
    """
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        payload = {k: v for k, v in (request.data or {}).items() if k != "file"}
        try:
            filed = account_documents.file_document(
                _actor(request), account_id, payload, request.FILES.get("file")
            )
        except account_documents.UploadRefused as refusal:
            return Response(
                errors.http_series_refusal_body(
                    refusal.message_key, br_ref=refusal.br_ref, **refusal.params
                ),
                status=refusal.status,
            )
        response = Response(filed, status=201)
        response["Location"] = tenant_path(
            request, f"/accounts/{account_id}/documents/{filed['id']}"
        )
        return response

    params = parse_list_params(
        request.query_params,
        allowed_sorts=account_documents.DOCUMENT_SORTS,
        default_sort=account_documents.DOCUMENT_DEFAULT_SORT,
        # `BR-CUS-1046` — *"The new newly created entries should always show on
        # the top."* Without this the grammar falls back to `asc` and a filing
        # cabinet opens on the oldest scan.
        default_dir=account_documents.DOCUMENT_DEFAULT_DIR,
        allowed_filters=account_documents.DOCUMENT_FILTERS,
    )
    rows, total = account_documents.documents_page(account_id, params)
    return _prepaged(
        request,
        rows,
        total,
        params,
        refetch=lambda p: account_documents.documents_page(account_id, p),
    )


@api_view(["GET", "DELETE"])
@permission_classes([AnyTenantRole])
def account_document_item(request: Any, account_id: str, document_id: str) -> Response:
    """`GET|DELETE /accounts/{id}/documents/{docId}` — a link that dies, and the
    filing that can be taken back.

    Four hours, and it is a bearer token: `document_store.download_url` mints it
    at `document_storage.url_ttl_seconds()`, capped by the PO ruling of
    2026-08-30. The row is resolved under THIS tenant first and the URL is
    minted second, so a link is never issued for a document the caller could not
    have found — another utility gets a 404, the same answer as for one that
    never existed (`BR-TEN-003`, HR-1).

    ⚠ **THERE IS A `DELETE` NOW, AND WHAT IT DELETES IS THE FILING.** This
    docstring read *"There is no DELETE … so no removal route is invented"*
    until 2026-09-13, when the PO ruled on wave I's own report that *"a clerk who
    files the wrong scan cannot take it back"* — verbatim, *"We should have this
    functionality"* (`BR-CUS-1052`). **The two rules that sentence cited are not
    reversed:** `BR-CUS-036` still audit-locks system and contract documents, so
    a `DELETE` of either answers **409 `BIZ-LOCKED`** with its reason rather
    than removing anything; and `NFR-35` still makes the bytes write-once for
    seven years, so **no byte is erased** — the stored object stays and only
    the account's filing of it goes away. (⚠ It is no longer under an object
    LOCK: `CR-160-BRC10`, 2026-10-02, suspended the lock for every file; nothing
    in the product deletes the object either way.)

    ⚠ **`DELETE` IS `AdminOrClerk`, NOT `AnyTenantRole`** — the same split
    `POST` makes one route up, and for the same reason (`BR-SHL-031`, *"v1
    uploads staff-mediated"*). An Executive reads the tab and may not take a
    document off it. The permission class on the view is the READ's, so the
    narrower gate is checked in the branch, exactly as `account_notes` and
    `account_documents_list` already do.

    **204 and no body.** Nothing survives the call that a caller could want: the
    filing is gone from every read, and the audit row it wrote is not this
    endpoint's to serve.
    """
    require_tenant(request)
    if request.method == "DELETE":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        account_documents.withdraw_document(_actor(request), account_id, document_id)
        return Response(status=204)
    return Response(account_documents.document_link(account_id, document_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_document_content(request: Any, account_id: str, document_id: str) -> Any:
    """`GET /accounts/{id}/documents/{docId}/content?as=view|download` — the
    file itself, for a clerk to open or save (`DEF-CUS-9147`).

    The service request's content route (`CR-158-BRC10`) for an account, with
    its headers taken from that view rather than restated: `inline` only for a
    PDF, PNG or JPEG asked for with `as=view`, `nosniff`, a policy under which
    no script runs inside a served file, and `private, no-store`.

    `AnyTenantRole` — a READ, like the link one route up. Resolved under this
    tenant first; another utility gets 404. Audited, one row per open or save.
    """
    from django.http import HttpResponse

    from apps.customers.service_request_api import DOCUMENT_CSP, _content_disposition

    require_tenant(request)
    mode = str(request.query_params.get("as") or "view")
    served = account_documents.document_content(_actor(request), account_id, document_id, mode)
    response = HttpResponse(served["payload"], content_type=served["content_type"])
    response["Content-Disposition"] = _content_disposition(served["inline"], served["name"])
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = DOCUMENT_CSP
    response["Cache-Control"] = "private, no-store"
    response["Content-Length"] = str(len(served["payload"]))
    return response


@api_view(["PATCH"])
@permission_classes([AdminOrClerk])
def account_note_item(request: Any, account_id: str, note_id: str) -> Response:
    """`PATCH /accounts/{id}/notes/{noteId}` — pin, unpin, correct.

    There is no DELETE. IS-1's pattern for an audited annotation is supersede or
    edit, never remove, and no rule rules on deleting a note — so no route is
    minted for one (a route that answers 501 is a promise)."""
    require_tenant(request)
    return Response(
        services.update_account_note(_actor(request), account_id, note_id, _payload(request))
    )


# ── S23 Change Plan wizard (11b §2.6 · US-CUS-016 / US-CUS-017) ────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_plan_change_options(request: Any, account_id: str) -> Response:
    """Step 1's picker: the PUBLISHED, service-compatible plans (BR-RAT-030),
    the current plan for contrast, and each row's service-drop note.

    A read, so any tenant role may see it — an Executive reviewing what a clerk
    is about to do is A4's whole View posture."""
    require_tenant(request)
    return Response(services.plan_change_options(account_id))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def account_plan_change_preview(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/plan-changes/preview` — step 2's figures.

    POST for a read, exactly as 11b §2.6 contracts it: the preview takes a
    BODY (target plan, effective option or date) and a GET with that body in
    the query string would be a cacheable URL carrying a customer's pending
    plan change. It writes nothing — asserted in US-CUS-016 TC-1 — and the
    response's `writes: []` says so on the wire.

    Every figure in it comes from the rating engine or from the tenant's own
    stored base charges; this layer computes no money at all (B8/LAW 0)."""
    require_tenant(request)
    return Response(services.preview_plan_change(account_id, _payload(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4: Executive is VIEW on Accounts
def account_plan_changes(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/plan-changes` — step 3's confirm.

    201 because a NEW effective-dated assignment row is created. The response
    carries `problems[]`: the deposit-differential instruction US-CUS-017 §1 (c)
    asks for is NOT registered (OQ-168 — BR-CUS-042 and BR-CUS-062 disagree),
    and a caller must read that rather than infer it from silence."""
    require_tenant(request)
    return Response(
        services.change_plan(_actor(request), account_id, _payload(request)), status=201
    )


# ── S24 Payment Plan wizard (11b §S24 · US-CUS-018 / US-PAY-017) ───────────
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  THE FOUR ROUTES 11b §S24 NAMES, AND WHAT SHIPPED INSTEAD OF TWO OF THEM ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# 11b §S24 lists `POST /accounts/{id}/payment-plans` · `GET …` ·
# `PATCH /payment-plans/{id}` (proposed state only) · `POST /payment-plans/{id}/void`.
#
#   POST   /accounts/{id}/payment-plans/preview   ADDED, and not in 11b. The
#          schedule is server-side money math (BR-CUS-043 / B4.4, ❄️ GT-47) and
#          step 2 must SHOW it before anything is written, so the wizard needs a
#          computing read that commits nothing. The precedent is §S23's own
#          `POST /accounts/{id}/plan-changes/preview`, which takes a body for the
#          same reason: a GET carrying the proposal in its query string is a
#          cacheable URL holding a customer's pending arrangement. REPORTED as
#          an addition rather than slipped in.
#   POST   /accounts/{id}/payment-plans          step 3, "Send agreement ✓".
#   GET    /accounts/{id}/payment-plans          the wizard's context + history.
#   POST   /payment-plans/{id}/activate          ADDED — the customer signed.
#          BR-CUS-044 activates on the CUSTOMER's e-signature ALONE and the
#          e-sign envelope is the DocuSign seam (B7), which does not exist in
#          this release: `apps/integrations` holds three docstrings and no
#          models. S24's PRINT channel is a ratified election (US-CUS-018 §5,
#          "print for counter signature"), and a signature that arrives on paper
#          has to be recorded by the person holding it or the plan can never
#          leave `agreement_sent`. The signature DATE is a required input
#          (BR-TEN-043 — never a clock), and the screen states that no e-sign
#          provider is connected rather than implying one signed anything.
#
#   NOT MOUNTED, each for its own reason and neither stubbed (a route that
#   answers 501 is a promise):
#   · PATCH /payment-plans/{id} "proposed state only" — NO PLAN IS EVER IN
#     `proposed` ONCE PERSISTED. `plans.propose_payment_plan` writes the rows and
#     moves the plan to `agreement_sent` in the SAME transaction, deliberately
#     (its own docstring says why), so the state this route is contracted for
#     cannot be reached by any caller. Step 2's edits happen BEFORE anything is
#     written, through the preview above.
#   · POST /payment-plans/{id}/void — THERE IS NO VOID. PO 2026-08-11: *"nodrop
#     we chase for payments until write off"*, so `PLAN_STATUSES` has four
#     values and none of them is `void`. Whether STAFF may cancel a plan (the
#     customer rings to say they cannot keep it; the plan was written against
#     the wrong account) is question (1) of OQ-171 and the PO's closure answered
#     only the write-off half — so it is **OQ-239**, minted rather than
#     answered, and no control anywhere offers it.
def _decimal_field(payload: dict[str, Any], name: str, *, required: bool = True) -> Any:
    """A money field as `Decimal`, from TEXT. Never a float (CLAUDE.md rule 2).

    `float("36.22")` is not 36.22 and a schedule built from one re-sums to
    something a customer's agreement does not say. JSON numbers are parsed by
    DRF as float, so a numeric literal is refused here rather than coerced.
    """
    from decimal import Decimal, InvalidOperation

    raw = payload.get(name)
    if raw is None and not required:
        return None
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.plan.moneyMustBeText",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.plan.required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return Decimal(str(raw))
    except InvalidOperation as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.plan.moneyMustBeText",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _plan_date(payload: dict[str, Any], name: str) -> Any:
    """A business date the CALLER states (BR-TEN-043, gate G6)."""
    from datetime import date as date_cls

    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.plan.required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date_cls.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.plan.dateFormat",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _plan_refusal(refusal: Exception) -> errors.BizError:
    """A payment-plan rule refusal as the ONE catalog exception G9 allows.

    Same translation billing's `_as_catalog_refusal` makes and for the same
    reason: `PaymentPlanRuleError` is raised by a service that also runs outside
    a request, so it carries no HTTP status, and this layer is the only one that
    knows what HTTP is. The refusal's own sentence travels in `params.detail` —
    BR-CUS-043's *"the schedule must equal the total to spread"* is written for a
    clerk and reaches the audit trail.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-CUS-043",
        message_key="customers.plan.refused",
        params={"detail": str(refusal)},
    )


def _int_field(payload: dict[str, Any], name: str) -> int:
    """A whole number of instalments. `4.5` instalments is not a schedule."""
    raw = payload.get(name)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.plan.wholeNumber",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    return raw


def _flag(payload: dict[str, Any], name: str, fallback: bool) -> bool:
    """One of S24 step 1's three toggles. Absent ⇒ the prototype's own default;
    present ⇒ it must be a boolean, never a truthy string."""
    raw = payload.get(name)
    if raw is None:
        return fallback
    if not isinstance(raw, bool):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.plan.trueOrFalse",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    return raw


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # read: A4 gives Executive VIEW on Accounts
def account_payment_plans_entry(request: Any, account_id: str) -> Response:
    """`GET|POST /accounts/{id}/payment-plans` — one path, two verbs.

    The same shape `accounts` above takes: DRF routes a path to one view, and
    splitting the read onto a second URL would give the S24 history and the S24
    send two different resources for one thing.
    """
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            # A4: Executive is VIEW on Accounts. The service-layer role guard
            # refuses this too — both halves on purpose (BR-SHL-025).
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        return _payment_plan_create(request, account_id)
    return _payment_plan_context(request, account_id)


def _payment_plan_context(request: Any, account_id: str) -> Response:
    """The wizard's context and the history.

    NOT paginated, and it is the second list in this module that is not: an
    account has at most one LIVE plan (BR-CUS-043) and a handful of closed ones,
    and a page boundary through a set that small would hide the live one.

    Three of its fields are absences carrying reasons — the balance the ledger
    could not be asked for, the plans payments could not be read, and the reason
    a plan cannot be proposed. None of them is ever a zero: DEF-127 is what
    happens when a product spells "we could not tell" the same way as "nothing".
    """
    account = selectors.account_detail(account_id)
    return Response(
        payment_plan_service.wizard_context(account=account, as_of=seams.tenant_today())
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4: Executive is VIEW on Accounts
def account_payment_plan_preview(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/payment-plans/preview` — step 1 → step 2.

    **WRITES NOTHING**, and the response says so on the wire (`writes: []`), the
    same contract §S23's preview carries. ❄️ GT-47 is what it computes: 267.30
    less a 50.00 down payment over six instalments is 5 × 36.22 and a FINAL
    36.20 — the remainder lands on the last row and nowhere else (BR-CUS-043),
    which is what makes Σ equal the total to the cent.

    Step 2's per-row edits come back through this same route with `edits`, so
    the arithmetic that re-sums them is the server's (B4.4) and a clerk cannot
    send an agreement whose own numbers disagree.
    """
    require_tenant(request)
    payload = _payload(request)
    _, plan = _proposed_plan(request, account_id, payload)
    return Response({**plan.as_dict(), "writes": []})


def _proposed_plan(request: Any, account_id: str, payload: dict[str, Any]) -> Any:
    """Step 1's inputs → the validated schedule step 2 renders. ONE derivation.

    The preview and the send BOTH go through here, deliberately: a send that
    re-derived the schedule from the same body by a second code path is two
    implementations of BR-CUS-043 in one file, and the day they disagree the
    customer signs one and the table holds the other.
    """
    account = selectors.account_detail(account_id)
    context = payment_plan_service.wizard_context(account=account, as_of=seams.tenant_today())
    if not context["can_propose"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-043",
            message_key="customers.plan.refused",
            params={"detail": context["cannot_propose_reason"]},
        )
    try:
        plan = payment_plan_service.preview(
            balance_to_spread=_decimal_field(payload, "balance_to_spread"),
            # The ledger's figure, never client input: a clerk cannot widen the
            # ceiling their own proposal is checked against (US-CUS-018 TC-6).
            account_balance=_decimal_field({"b": context["balance"]}, "b"),
            down_payment=_decimal_field(payload, "down_payment", required=False)
            or _decimal_field({"z": "0"}, "z"),
            installments=_int_field(payload, "installments"),
            cadence=str(payload.get("cadence") or ""),
            first_due_date=_plan_date(payload, "first_due_date"),
            as_of=seams.tenant_today(),
            # The TENANT's currency (BR-TEN-021), never the caller's.
            currency=str(context["currency"] or ""),
            live_plan_exists=context["live_plan"] is not None,
            autopay_enabled=_flag(payload, "autopay_enabled", True),
            suspend_late_fees=_flag(payload, "suspend_late_fees", False),
            suspend_disconnect=_flag(payload, "suspend_disconnect", True),
        )
        edits = payload.get("edits")
        if edits:
            plan = payment_plan_service.apply_preview_edits(plan=plan, edits=edits)
    except payment_plan.PaymentPlanRuleError as refusal:
        raise _plan_refusal(refusal) from refusal
    return context, plan


def _payment_plan_create(request: Any, account_id: str) -> Response:
    """Step 3, **Send agreement ✓**.

    201 with a Location header: the plan ROW is created, by PAYMENTS, through
    the seam (BR-CUS-037 — this module writes no financial table). The plan
    leaves in `agreement_sent`; it is NOT active, because activation is the
    customer's signature and nothing else (BR-CUS-044).

    The response repeats `current_bill_still_due` so the confirmation a clerk
    reads carries the same sentence the summary did (PO 2026-08-11).
    """
    payload = _payload(request)
    channels = payload.get("channels")
    if not isinstance(channels, list) or any(not isinstance(one, str) for one in channels):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.plan.required",
            field_errors=[{"field": "channels", "code": errors.VAL_REQUIRED}],
        )
    _, plan = _proposed_plan(request, account_id, payload)
    try:
        created = payment_plan_service.send_agreement(
            actor=_actor(request),
            account_id=account_id,
            plan=plan,
            channels=tuple(channels),
            on_date=_plan_date(payload, "on_date"),
        )
    except payment_plan.PaymentPlanRuleError as refusal:
        raise _plan_refusal(refusal) from refusal
    response = Response({**created, "current_bill_still_due": True}, status=201)
    response["Location"] = tenant_path(request, f"/accounts/{account_id}/payment-plans")
    return response


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def payment_plan_activate(request: Any, plan_id: str) -> Response:
    """`POST /payment-plans/{id}/activate` — the customer signed (BR-CUS-044).

    `signed_on` is REQUIRED and is the day the CUSTOMER signed, not the day a
    clerk keys it: BR-TEN-043 makes the event date an input, and a plan whose
    signature date is the keying date misstates when dunning stopped.

    No countersignature is taken and none exists — BR-CUS-044 supersedes A19
    §3's countersign block in those words.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        return Response(
            payment_plan_service.activate(
                actor=_actor(request),
                plan_id=plan_id,
                current_status=str(payload.get("current_status") or ""),
                signed_on=_plan_date(payload, "signed_on"),
            )
        )
    except payment_plan.PaymentPlanRuleError as refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-044",
            message_key="customers.plan.refused",
            params={"detail": str(refusal)},
        ) from refusal


# ══════════════════════════════════════════════════════════════════════════
# MOVE-IN STEP 4 — ELIGIBILITY AND THE DEPOSIT CARRY-FORWARD (W5 · 5.4 / 5.5)
# ══════════════════════════════════════════════════════════════════════════
# `apps/customers/discounts.py` was built with no route to it. That is
# hard-won law 2 — a built endpoint nothing calls is not a feature — and it is
# the same gap these four routes' move-out siblings above were mounted to
# close. Every one is a thin pass-through: the service owns the rules, the
# refusals and (for the one write) its own `audit_log` row.


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # mirrors the service's own @require_role
def discount_programmes(request: Any) -> Response:
    """`GET /discount-programmes` — B18 §5.5.5, and it is a SECOND NAME.

    ⚠ `GET /discounts` already serves these rows (`apps/rating/api.discounts`
    over `rating.selectors.discount_list`); CR-013 part 3 built the whole
    catalogue on 2026-08-19. This route exists because B18 names it and the
    move-in panel asks for it, and it reads THROUGH THE SEAM to that same
    table rather than growing a parallel catalogue — which would be
    BR-RAT-069's *"available is not granted"* failure under a different name.
    Programmes are tenant-authored, not a shipped list. REPORTED against B18.
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return Response(discounts.discount_programmes(_actor(request), params))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_eligibility(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/eligibility` — move-in step 4's panel (task 5.4).

    **Eligibility NEVER blocks service; it only changes what is charged**
    (B18 §5.3.4, BR-RAT-043, BR-RAT-112). `blocks_service` is a CONSTANT on the
    payload, not a computed field, so no input can make it true.

    Whether an unproven claim reduces the bill straight away is **per
    programme**, not a global answer: BR-RAT-076's stored
    `proof_before_first_reduction`. A READ — no audit row.
    """
    require_tenant(request)
    return Response(discounts.eligibility_panel(_actor(request), account_id))



@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_units(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/units` — **every unit at a master account's address,
    its live occupancy, and who its bill goes to** (`BR-CUS-1094`).

    PO 2026-09-23, verbatim: *"show all units with its status what wil be billed
    to master account - can we do that?"*

    ⚠ **IT WRITES NOTHING AND IT STORES NOTHING**, which is not tidiness here
    but the rule itself: `BR-CUS-1094` is a prohibition as well as a ruling —
    *"No column may cache which units a master account pays for, because a
    cached answer is wrong the first time a tenant moves in and nothing would
    go red."* Every answer on this payload is derived at read time from the two
    seam reads `apps/billing/gather` uses, so what this screen shows is what a
    bill run starting NOW would decide.

    **404 for an account that is not a master**, through the 404-never-403
    refusal every other read in this module uses: an ordinary account has no
    building to answer for, and saying *"this account is not a master"* to
    somebody who may not be allowed to know the account exists is the leak that
    refusal shape exists to prevent.

    A READ — no audit row (`CLAUDE.md` hard rule 7 is about money ACTIONS).
    """
    require_tenant(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.MASTER_UNIT_SORTS,
        default_sort=selectors.MASTER_UNIT_DEFAULT_SORT,
        default_dir=selectors.MASTER_UNIT_DEFAULT_DIR,
        allowed_filters=selectors.MASTER_UNIT_FILTERS,
    )
    answer = selectors.master_unit_billing_page(account_id, params)
    if answer is None:
        raise errors.deny_as_not_found("BR-CUS-068")
    rows, total, counts = answer
    return _prepaged(request, rows, total, params, {"counts": counts})

@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_claim_assistance(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/discounts` — record an assistance claim (task 5.4).

    Writes an enrolment through rating's own service, so there is ONE grant
    table and the bill run reads the table it already reads. The status is
    rating's to decide (`pending` vs `not_required`, per BR-RAT-076) and a
    caller-supplied one is refused.

    ⚠ **A CLERK WAS REFUSED HERE BY ANOTHER MODULE'S RBAC UNTIL 2026-10-05.**
    Rating's `enrol_account` was `@require_role(SYSTEM_ADMIN)` (reported by the
    R2 lane, 2026-08-25). The PO ruled (b) on 2026-10-05 — *"Let billing clerks
    record it themselves"* — and rating now admits a Billing Clerk, so this door
    enrols for the clerk. Any refusal rating still raises passes through
    UNCHANGED.

    ⚠ **`DEF-RAT-9297` — THIS PASSED THE WHOLE BODY AS THE PROGRAMME ID AND
    ANSWERED 500 EVERY TIME** (`CR-166-BRC10` r2 t3). `claim_assistance(actor,
    account_id, programme_id)` takes an id; the view handed it
    `{"programme_id": …}`, so `_discount_or_404` raised Django's own *"… is not
    a valid UUID"*. Tests called the service directly and no test posted to the
    URL, so the view's argument was never exercised. The body is read FIELD BY
    FIELD now — `programme_id` required, `household_size` passed through so the
    service can refuse it by name as before.
    """
    require_tenant(request)
    payload = _payload(request)
    programme_id = str(payload.get("programme_id") or "").strip()
    if not programme_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.eligibility.programmeRequired",
            field_errors=[
                {
                    "field": "programme_id",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "customers.eligibility.programmeRequired",
                    "params": {},
                }
            ],
        )
    return Response(
        discounts.claim_assistance(
            _actor(request),
            account_id,
            programme_id,
            household_size=payload.get("household_size"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def customers_match(request: Any) -> Response:
    """`POST /customers/match` — New Connection step 1's owner lookup
    (`CR-164-BRC10` item 11, PO ruling Q5 of 2026-10-02).

    A READ carried on POST because its body is a Social Security number, a
    licence or a Tax ID, and a query string is logged by every proxy between
    the browser and here. Nothing is written, so no audit row. The verdict and
    its reasoning are `owner_lookup`'s; this view only scopes the tenant.
    """
    require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    return Response(owner_lookup.lookup(body))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive is VIEW on Accounts/people
def customers(request: Any) -> Response:
    """`GET /customers` — CR-056 W5 task 25. THE LIST THAT DID NOT EXIST.

    This file's own header recorded the absence, verbatim: *"no story owns a
    customer LIST or DETAIL endpoint yet"*. Until today a person could be
    reached only BACKWARDS, through an account, so a landlord whose account
    numbers nobody remembers was unreachable.

    One search box, four legs: the customer number, the legacy reference, the
    name, and the phone through its blind index. A READ — no audit row.

    ⚠ **PAGED IN SQL, NOT IN PYTHON, SINCE 2026-09-18 (`NFR-3`,
    `DEF-CUS-5753`).** This route was built on `_paginated`, which slices a
    BUILT list — so a landlord-heavy utility built every customer it holds in
    order to draw fifty, and each row then asked for that person's accounts on
    its own. `selectors.customer_page` takes the page and its `COUNT(*)` in the
    database and batches the page's links into one query; `_prepaged` serves
    the same envelope `GET /accounts` does, re-clamping `page` per
    `BR-SHL-011`.
    """
    require_tenant(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.CUSTOMER_SORTS,
        default_sort=selectors.CUSTOMER_DEFAULT_SORT,
        allowed_filters=selectors.CUSTOMER_FILTERS,
    )
    rows, total = selectors.customer_page(params)
    # `refetch` is what the out-of-range clamp re-asks, and it MUST be named:
    # its default is `selectors.account_page`, which would serve an accounts
    # page from the customers route on `?page=999`.
    return _prepaged(request, rows, total, params, refetch=selectors.customer_page)


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def customer_item(request: Any, customer_id: str) -> Response:
    """`GET /customers/{id}` — one person and the accounts linked to them.
    **`PATCH /customers/{id}` — BR-CUS-1054, and it did not exist until
    2026-09-13.** PO, verbatim: *"Start the customer edit one also - we will
    need this"*. A misspelt name, a wrong telephone number and a wrong email
    could not be corrected anywhere in the product: this route is read-only no
    longer, and the account edit surfaces never reached these fields because
    they are not `accounts` columns.

    404-never-403 for an id another tenant holds (HR-1/G4): from outside the
    tenant, an id that exists elsewhere and an id that does not exist are the
    same fact, and telling them apart is a membership oracle.

    ⚠ **THE WRITE IS GUARDED IN THE SERVICE, NOT HERE.** `AnyTenantRole` reads;
    `customer_edit.update_customer` carries `@require_role(SYSTEM_ADMIN,
    BILLING_CLERK)` and refuses whichever door forgets — `BR-SHL-025`: the
    server-side guard is THE guard. Mounting a narrower permission class on the
    whole view would take the READ away from an Executive who has it today.
    """
    require_tenant(request)
    if request.method == "PATCH":
        return Response(
            customer_edit.update_customer(request.user, customer_id, request.data)
        )
    row = selectors.customer_detail(customer_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return Response(row)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def customer_statement(request: Any) -> Response:
    """`GET /reports/customer-statement?customer={id}` — **CR-060 C16 / T17.**

    One customer, their accounts, each balance, **and a total across them**.
    **NO MIGRATION AND NO NEW TABLE:** the link table has carried the pair, the
    confidence tier and the confirmer since `BR-CUS-054` shipped, and every
    money figure is the ledger's own per-account Σ reached through the customers
    seam. This view adds a door, not a derivation.

    **WHY IT LIVES IN CUSTOMERS AND NOT IN REPORTS.** The read walks
    `customer_accounts` — a customers table — and B1 forbids another module
    touching this one's ORM. The `reports/` PREFIX is the URL grammar for a
    report and is not a claim about ownership; `apps/audit/api.py` already
    serves `reports/user-activity-audit` on exactly that reading.

    **THE CUSTOMER IS A QUERY PARAMETER, NOT A PATH SEGMENT**, because the URL
    is a REPORT's and a report is parameterised. A missing or malformed
    `customer` is a 422 rather than a 404: *"you did not say who"* and *"there
    is no such person"* are different answers, and collapsing them would send a
    clerk looking for a deleted customer who never existed.

    404-never-403 for an id another tenant holds (HR-1/G4): from outside the
    tenant an id that exists elsewhere and one that does not are the same fact,
    and telling them apart is a membership oracle.

    A READ — no audit row (CLAUDE.md rule 7 is about money ACTIONS).
    """
    require_tenant(request)
    customer_id_param = (request.query_params.get("customer") or "").strip()
    if customer_id_param == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.statement.customerRequired",
            field_errors=[{"field": "customer", "code": errors.VAL_REQUIRED}],
        )
    row = selectors.customer_statement(customer_id_param)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return Response(row)


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def customer_deposit_position(request: Any, customer_id: str) -> Response:
    """`GET /customers/{id}/deposit-position` — B18 §5.5.5 (task 5.5).

    ⚠ **TWO GAPS ARE SERVED HERE AND THEY POINT IN OPPOSITE DIRECTIONS.**
    `deposit_interest_not_readable` — BR-CUS-057's accrual is unbuilt, so
    interest and the refundable total are `null` rather than 0.00; a zero would
    carry $150.00 where $153.50 is owed. And
    `deposit_not_net_of_settlement` — BR-CUS-025 settles the deposit at close
    and **nothing writes that back** (`move_out_settlement` returns
    `persisted: false`), so a closed account's column is the deposit AS
    RECEIVED. Carrying it silently would pay a customer twice.

    Both travel to the client verbatim. A READ — no audit row.
    """
    require_tenant(request)
    return Response(discounts.deposit_position(_actor(request), customer_id))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def customer_carry_forward(request: Any, customer_id: str) -> Response:
    """`GET /customers/{id}/deposit-carry-forward` — TC-MVI-2/3 (task 5.5).

    **AN OFFER, AND ONLY AN OFFER.** BR-CUS-024's mechanics are PROPOSED and
    `deposit_on_file` is a refused field on every non-import door, so there is
    no accept path and the payload names the missing rule
    (`carry_forward_has_no_accept_path`).

    **BR-CUS-089: money moves only on a `strong` match.** The service READS a
    stored tier and can neither compute nor accept one — `tier` is not a
    parameter of the callable, which a test pins against the signature. Every
    other tier is refused carrying `identity_match_strength_has_no_rule`, and
    **the refusal shows no figure at all**: a number on a refused offer is an
    invitation to type it in by hand. What earns `strong` is **OQ-364**, open.
    """
    require_tenant(request)
    return Response(discounts.carry_forward_offer(_actor(request), customer_id))



@api_view(["GET"])
@permission_classes([AdminOrClerk])  # narrower than A4's Executive VIEW — see below
def transfers_list(request: Any) -> Response:
    """`GET /transfers` — S89's Transfers tab (CR-030 W7 task 7.4, B18 §5.7.2).

    B18 §6.2 lists this row as `❌`. The list is `transfer_reads.list_transfers`
    and this view adds nothing to it: no figure is computed, no absence is
    defaulted and no money is moved anywhere in this layer.

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`, AND THE REASON IS THE PAYLOAD.**
    A4 gives Executive VIEW on Accounts and every other read on this file is
    `AnyTenantRole`. But the MONEY cell this list serves is the same statement
    `transfers.money_statement` gates with `@require_role(SYSTEM_ADMIN,
    BILLING_CLERK)`, so `AnyTenantRole` here would hand an Executive figures the
    layer below refuses them. The narrower gate is mounted to match rather than
    promising a view the service denies — the precedent is
    `account_close_impact`, mounted the same way for the same reason.
    """
    require_tenant(request)
    # CR-045 wave D task D.12 (DEF-1702) — `allowed_filters` is what makes
    # `f.state` reach the read model at all: `parse_list_params` DROPS every
    # `f.<name>` outside the tuple (BR-SHL-011), so a view that declares none
    # can never be filtered however the client asks.
    params = parse_list_params(
        request.query_params,
        # `BR-CUS-1046` / `DEF-CUS-5060` — this list declared NO sorts and
        # fixed one `.order_by(...)`. `parse_list_params` DROPS a `sort` outside
        # `allowed_sorts` exactly as it drops an undeclared filter, so declaring
        # the vocabulary here is what lets a clerk's chosen column reach the read
        # model at all — and `default_dir` is what makes the untouched screen open
        # on the NEWEST row rather than the oldest.
        allowed_sorts=tuple(transfer_reads.SORTS),
        default_sort=transfer_reads.DEFAULT_SORT,
        default_dir=transfer_reads.DEFAULT_DIR,
        allowed_filters=transfer_reads.TRANSFER_FILTERS,
    )
    return Response(
        transfer_reads.list_transfers(
            q=params.q or None,
            page=params.page,
            per=params.per,
            filters=params.filters,
            sort=params.sort,
            dir=params.dir,
        )
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # narrower than A4's Executive VIEW — see above
def disconnects_list(request: Any) -> Response:
    """`GET /disconnects` — S90's Disconnects tab (CR-030 W7 task 7.11, B18 §5.8.2).

    ⛔ **ONLY `?segment=all` IS SERVED, AND THE REFUSAL IS A SENTENCE, NOT A
    500.** B18 §5.8.2's six segments are not mutually exclusive — `On hold` is
    computed from the account's protections while `At notice`, `Due to cut`,
    `Cut` and `Reconnecting` are the stored `disconnect_cases.state`, and no
    rule ranks them (see `disconnect_reads` §3; AN OPEN QUESTION IS OWED). The
    selector raises `NotImplementedError` because that is the prime directive's
    shape for an unruled path; a clerk must not meet it as a stack trace, so it
    is translated here into the catalogue refusal with its message key.

    TC-DSC-9: tenant B's `GET /disconnects` returns none of tenant A's — the
    selector filters on `app.tenant_id` and `require_tenant` is what sets it.
    """
    require_tenant(request)
    # CR-045 wave D task D.8 (DEF-1702) — `f.state` on the STORED case state.
    # Not `?segment=`, which is still refused for everything but `all`; see
    # `disconnect_reads.DISCONNECT_FILTERS` for why one is answerable and the
    # other is an open question.
    params = parse_list_params(
        request.query_params,
        # `BR-CUS-1046` / `DEF-CUS-5060` — this list declared NO sorts and
        # fixed one `.order_by(...)`. `parse_list_params` DROPS a `sort` outside
        # `allowed_sorts` exactly as it drops an undeclared filter, so declaring
        # the vocabulary here is what lets a clerk's chosen column reach the read
        # model at all — and `default_dir` is what makes the untouched screen open
        # on the NEWEST row rather than the oldest.
        allowed_sorts=tuple(disconnect_reads.SORTS),
        default_sort=disconnect_reads.DEFAULT_SORT,
        default_dir=disconnect_reads.DEFAULT_DIR,
        allowed_filters=disconnect_reads.DISCONNECT_FILTERS,
    )
    segment = str(request.query_params.get("segment") or disconnect_reads.SEGMENT_ALL)
    try:
        payload = disconnect_reads.list_disconnects(
            segment=segment,
            q=params.q or None,
            page=params.page,
            per=params.per,
            filters=params.filters,
            sort=params.sort,
            dir=params.dir,
        )
    except NotImplementedError as unruled:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.disconnects.segment.unavailable",
            params={"segment": segment, "supported": disconnect_reads.SEGMENT_ALL},
        ) from unruled
    return Response(payload)


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the DEPOSIT box — see `move_ins_list` below
def move_record_detail(request: Any, ref: str) -> Response:
    """`GET /moves/{ref}` — the MOVE RECORD screen (blueprint p074).

    The assembly is `move_record_reads.record_detail` and this view adds
    nothing to it: no figure is computed here, no absence is defaulted, and
    **nothing is written — this endpoint has no sibling that writes.** That is
    the blueprint's own ruling rather than an omission (see that module's §1).

    ⚠ **`ref` IS THE MOVE NUMBER, NEVER A UUID** (B14 rule 31). `MVI-26-0114`
    is what the list links to and what a clerk quotes on the phone, and it
    keeps resolving across the commit because a draft and the finished record
    carry the same string (`CR-122-BRC06`).

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`,** for the reason `move_ins_list`
    gives one screen over: this page carries a deposit box, and the deposit
    statement the layer below builds is gated to the same two roles. Handing an
    Executive a figure the service refuses them is the defect that rule exists
    to prevent.
    """
    require_tenant(request)
    return Response(move_record_reads.record_detail(ref))


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # narrower than A4's Executive VIEW — see below
def move_ins_list(request: Any) -> Response:
    """`GET /move-ins` — the Accounts page's Move-ins tab (CR-030 W5, B18 §5.5.2).

    The list is `move_reads.move_ins_list` and this view adds nothing to it: no
    figure is computed here, no absence is defaulted, and nothing is written.

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`, FOR THE REASON `transfers_list`
    GIVES.** Each row carries a DEPOSIT cell, and the deposit statement the
    layer below builds is gated `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`.
    `AnyTenantRole` here would hand an Executive figures the service refuses
    them. Matching the narrower gate is the precedent set by `transfers_list`
    and `account_close_impact`.

    **A move-in is not a table — it is the life of a BR-CUS-018 draft account**,
    from `services.create_account` writing a `pending_activation` row to
    `services.activate_account` making it occupy. The window is the terminal
    CLASS, never the label (BR-CUS-055).

    §5.7.3's counting contract is applied inside the read model, not here: a
    committed transfer's incoming half goes through `create_account` and would
    otherwise appear on this list, so `transfers.exclude_transfer_halves` is
    load-bearing rather than tidy.
    """
    require_tenant(request)
    # CR-045 wave D task D.9 (DEF-1702) — `f.state`, applied in the queryset.
    params = parse_list_params(
        request.query_params,
        # `BR-CUS-1046` / `DEF-CUS-5060` — this list declared NO sorts and
        # fixed one `.order_by(...)`. `parse_list_params` DROPS a `sort` outside
        # `allowed_sorts` exactly as it drops an undeclared filter, so declaring
        # the vocabulary here is what lets a clerk's chosen column reach the read
        # model at all — and `default_dir` is what makes the untouched screen open
        # on the NEWEST row rather than the oldest.
        # `CR-171-BRC10` P1.04 — the redesign's list: every status, `f.status`
        # and `f.service` (images 01–02). `move_in_list` is the one assembly.
        allowed_sorts=tuple(move_in_list.SORTS),
        default_sort=move_in_list.DEFAULT_SORT,
        default_dir=move_reads.MOVE_DEFAULT_DIR,
        allowed_filters=move_in_list.FILTERS,
    )
    return Response(
        move_in_list.move_ins_list(
            q=params.q or None,
            page=params.page,
            per=params.per,
            filters=params.filters,
            sort=params.sort,
            dir=params.dir,
        )
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # narrower than A4's Executive VIEW — see above
def move_outs_list(request: Any) -> Response:
    """`GET /move-outs` — the Accounts page's Move-outs tab (CR-030 W5, B18 §5.6.2).

    Same envelope as `GET /move-ins`, so one screen component reads both.

    ⚠⚠ **THIS DOCSTRING SAID *"ONLY A MOVE-OUT THAT HAS ALREADY HAPPENED IS
    SERVABLE"* UNTIL 2026-09-19, AND IT IS NOT TRUE ANY MORE.** PO ruling of
    that day, verbatim **`yes`**, asked whether the Move-outs list should show
    move-outs that have not finished yet. The envelope now carries TWO kinds of
    row — closed accounts, and the `wizard_parks` drafts a clerk started and put
    down — each naming itself in `row_kind`. It was never a missing column: the
    draft store has carried `flow`, `step` and `waiting_on` for all five flows
    since `CR-035`, and what was missing was this list's WINDOW.

    ⚠ **WHAT IS STILL TRUE:** a move-out nobody has STARTED leaves no trace at
    all — `accounts` carries no `scheduled_move_out_on` — so B18 §5.6.7's
    `Scheduled` row is the one state this product still cannot hold, and
    `MOVE_OUT_STATES` marks it unsupported with its reason.

    The read model states an absence on every cell a draft cannot answer rather
    than inventing a value, and the tiles it cannot compute come back `null`
    with their reason attached. **Do not "fix" those nulls by defaulting them to
    0 here: an unknown and a zero are different answers, and only one of them is
    true.**
    """
    require_tenant(request)
    # CR-045 wave D task D.10 (DEF-1702) — `f.closed`, a window on `closed_at`.
    # The one stored, filterable fact this list holds; see `MOVE_OUT_FILTERS`.
    params = parse_list_params(
        request.query_params,
        # `BR-CUS-1046` / `DEF-CUS-5060` — this list declared NO sorts and
        # fixed one `.order_by(...)`. `parse_list_params` DROPS a `sort` outside
        # `allowed_sorts` exactly as it drops an undeclared filter, so declaring
        # the vocabulary here is what lets a clerk's chosen column reach the read
        # model at all — and `default_dir` is what makes the untouched screen open
        # on the NEWEST row rather than the oldest.
        allowed_sorts=tuple(move_reads.MOVE_OUT_SORTS),
        default_sort=move_reads.MOVE_OUT_DEFAULT_SORT,
        default_dir=move_reads.MOVE_DEFAULT_DIR,
        allowed_filters=move_reads.MOVE_OUT_FILTERS,
    )
    return Response(
        move_reads.move_outs_list(
            q=params.q or None,
            page=params.page,
            per=params.per,
            filters=params.filters,
            sort=params.sort,
            dir=params.dir,
        )
    )


urlpatterns = [
    # ── CR-030 W7 · the two worklists behind S89 and S90 (tasks 7.4 / 7.11) ──
    # Not under `accounts/`, so ordering against the `<str:account_id>` matcher
    # below does not apply to them.
    path("transfers", transfers_list),
    path("disconnects", disconnects_list),
    # ── CR-030 W5 · the two move worklists. Same placement, same reason. ──
    path("move-ins", move_ins_list),
    # `DEF-CUS-6365` — a literal second segment; `moves/<str:ref>` is a
    # different first segment, so nothing below can take it.
    path("move-ins/messages", move_in_messages),
    # `DEF-CUS-10190` — the all-units search and the move-out handover. Two
    # more literal second segments, beside `messages`.
    path("move-ins/units", move_in_units_search),
    path("move-ins/handover", move_in_handover),
    path("move-outs", move_outs_list),
    # ── The MOVE RECORD (blueprint p074) — a NEW TOP-LEVEL address, not
    # under `accounts/`, because a move is a record of an ACT and the
    # account is what it produced. `<str:ref>` takes the move NUMBER and
    # never a uuid (B14 rule 31); it cannot collide with the two literal
    # segments above because neither is a move number.
    path("moves/<str:ref>", move_record_detail),
    path("accounts", accounts),
    # BR-CUS-068 — registered BEFORE the <str:account_id> matcher below, which
    # would otherwise swallow the literal segment "master".
    path("accounts/master", master_accounts),
    path("accounts/deposit-standard", account_deposit_standard),
    # `DEF-CUS-6426` — BEFORE `accounts/<str:account_id>`, which would take
    # `subcategories` as an account id.
    path("accounts/subcategories", account_subcategories),
    path("accounts/imports", account_imports),
    path("accounts/imports/template", account_import_template),
    path("accounts/imports/<uuid:batch_id>", account_import_detail),
    path("accounts/imports/<uuid:batch_id>/commit", account_import_commit),
    path("accounts/<str:account_id>", account_item),
    path("accounts/<str:account_id>/contact", account_contact),
    path("accounts/<str:account_id>/mailing-address", account_mailing_address),
    path("accounts/<str:account_id>/co-applicant", account_co_applicant),
    path("accounts/<str:account_id>/activate", account_activate),
    # `BR-CUS-1047` — the unit correction. A FOURTH literal last segment under
    # `accounts/<id>/`, beside `activate`, `move-out` and `documents`, so no
    # catch-all can shadow it and it can shadow nothing.
    path("accounts/<str:account_id>/correct-unit", account_correct_unit),
    path("accounts/<str:account_id>/move-in", account_move_in),
    # `DEF-CUS-6353` — the first-occupant move-in. Metering owns `units/…` for
    # the unit itself and has no `move-in` segment; this is the ACCOUNT write
    # that takes the unit, so it lives with `account_move_in` above.
    path("units/<uuid:unit_id>/move-in", unit_move_in),
    path("accounts/<str:account_id>/move-out", account_move_out),
    path("accounts/<str:account_id>/close-out", account_close_out),
    # S20 steps 3 and 4 — the settlement read and its three decisions. Each is
    # its own literal segment under the account, so nothing here can be
    # swallowed by the `<str:account_id>` matcher above.
    path("accounts/<str:account_id>/final-bill-preview", account_final_bill_preview),
    path("accounts/<str:account_id>/move-out-estimate", account_move_out_estimate),
    path("accounts/<str:account_id>/close-impact", account_close_impact),
    path("accounts/<str:account_id>/settle-shortfall", account_settle_shortfall),
    path("accounts/<str:account_id>/refund", account_refund),
    path("accounts/<str:account_id>/hold-excess", account_hold_excess),
    path("accounts/<str:account_id>/eligibility", account_eligibility),
    # `BR-CUS-1094` (PO 2026-09-23) — the master account's Units tab. A READ,
    # declared here rather than under `premises/` because the SUBJECT is the
    # account: the same building read from the owner's side answers a
    # different question (who pays) from the property's own Units tab.
    path("accounts/<str:account_id>/units", account_units),
    path("accounts/<str:account_id>/discounts", account_claim_assistance),
    # CR-056 W5 task 25 — declared BEFORE the two `<str:customer_id>/…` paths
    # for the same reason `accounts/master` sits above `accounts/<id>`: a
    # wildcard segment swallows any literal declared after it.
    path("customers", customers),
    # `CR-164-BRC10` — a literal segment, so it sits above the wildcard.
    path("customers/match", customers_match),
    path("customers/<str:customer_id>", customer_item),
    # CR-060 C16 / T17 — the customer statement. Under `reports/` because
    # that is the URL grammar for a report, and OWNED here because the read
    # walks `customer_accounts` and B1 forbids another module touching this
    # module's ORM (`apps/audit/api.py` serves `reports/user-activity-audit`
    # on the same reading). The customer rides as a query parameter, so this
    # path has no wildcard segment and nothing below can be swallowed by it.
    path("reports/customer-statement", customer_statement),
    path("customers/<str:customer_id>/deposit-position", customer_deposit_position),
    path("customers/<str:customer_id>/deposit-carry-forward", customer_carry_forward),
    path("discount-programmes", discount_programmes),
    path("accounts/<str:account_id>/documents", account_documents_list),
    path("accounts/<str:account_id>/documents/<str:document_id>", account_document_item),
    path(
        "accounts/<str:account_id>/documents/<str:document_id>/content",
        account_document_content,
    ),
    path("accounts/<str:account_id>/notes", account_notes),
    path("accounts/<str:account_id>/notes/<str:note_id>", account_note_item),
    path("accounts/<str:account_id>/plan-changes", account_plan_changes),
    path("accounts/<str:account_id>/plan-changes/options", account_plan_change_options),
    path("accounts/<str:account_id>/plan-changes/preview", account_plan_change_preview),
    # S24 — the payment-plan wizard. `…/preview` is declared BEFORE the bare
    # path so the literal segment cannot be swallowed by a wildcard.
    path("accounts/<str:account_id>/payment-plans/preview", account_payment_plan_preview),
    path("accounts/<str:account_id>/payment-plans", account_payment_plans_entry),
    path("payment-plans/<str:plan_id>/activate", payment_plan_activate),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@bbed56d (slice 3 — EP-CUS-02 move-out lead story; co-packets US-CUS-004@bbed56d · US-CUS-003@bbed56d · EP-CUS-01@a2e1d59 · customers 02-business-rules@f125a9c)
# generated: 2026-08-11 by story-coder (W2 customers slice 3 — move-out + move-in and their two endpoints)
# AMENDED: 2026-08-24 by the CR-030 W2 ageing lane (task 2.4 — `GET /accounts?ageing=<segment>`; `_with_ageing_segment` accepts BOTH the CR's bare `?ageing=` spelling and BE-05's `f.ageing=`, normalised onto one filter key)
# AMENDED: 2026-08-25 by the CR-030 W5 move-out SERVING lane (tasks 5.8/5.9's API half — `apps/customers/move_out_settlement.py` shipped 2026-08-24 with `D=deferred(no-API-half)` and NOTHING COULD REACH IT, which is hard-won law 2 exactly. Four routes mounted over its four published callables: `GET …/close-impact` → `settlement_for`, `POST …/settle-shortfall` → `shortfall_decision`, `POST …/refund` → `refund_disposition`, `POST …/hold-excess` → `hold_excess`. No figure is computed, no landing chosen and no gap defaulted in this layer; `_stated_final_bill` parses TEXT money and passes a float through so the service's own never-float refusal fires. Tests: tests/test_w5_move_out_endpoints.py)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions (2026-08-24, ageing lane): `openapi/schema.json` is NOT regenerated — the schema is UNCHANGED by this lane and BE-11 TC05 is green, because drf-spectacular publishes no query parameters for these function views (`/api/{tenant}/accounts` GET declares only the `tenant` PATH param; `f.status`, `f.category`, `f.autopay`, `balance_gt` and `f.kind` are equally unpublished). `?ageing=` is therefore as documented as every other filter on this endpoint, which is not very — REPORTED, and a fix belongs to whoever documents the whole list grammar, not to one filter · the view is left WITHOUT a docstring for the same reason: spectacular puts a view docstring into the schema description, which would move the committed snapshot (hard-won law 5 — one generated file, committed once).
# exceptions: `urlpatterns` IS included in config/urls.py (one line, from slice 2) and openapi/schema.json is REGENERATED by this lane — the snapshot lives outside apps/customers and BE-11 TC05 diffs it, so an endpoint added without it goes red; named in the lane report · no move-out/preview, notes, documents, adjustments, statements, plan-change, payment-plan or import route is stubbed: a route that answers 501 is a promise, and those stories own tables that do not exist · the STANDALONE S19 move-in has NO path in 11b §S19 (the one row there is account-scoped) and none is invented — `POST /accounts` with an occupying status is it, and it takes the identical BR-CUS-017 + BR-CUS-056 guard · REPORTED · the S17 A18 status SEGMENTS and the BR-CUS-053 `plan` filter are still NOT served — both need billing invoices or the BR-CUS-029 snapshot (see selectors.py)
# exceptions (2026-08-25, W5 move-out serving lane): (1) `POST /accounts/{id}/refund` and `POST /accounts/{id}/hold-excess` ARE ADDITIONS — B18 §6.2's move-out row lists `GET …/close-impact` and `POST …/settle-shortfall` as "❌ two" and NO document or screen names a path for BR-CUS-081's refund or BR-CUS-096's hold. Both callables exist and are tested; leaving them unreachable is the defect this lane closes. REPORTED, not slipped in — the precedent is §S24's `…/payment-plans/preview` · (2) THE READ IS `AdminOrClerk`, WHICH A4 WOULD GIVE AN EXECUTIVE. A4's Premises/Accounts row is Executive **View** and every other read here is `AnyTenantRole`; `move_out_settlement.settlement_for` carries `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and refuses an Executive itself, so the narrower gate is mounted to match rather than promising a view the layer below denies. Widening it is the settlement module's call and that file is not this lane's — REPORTED · (3) THE FRONTEND'S `CloseImpact` INTERFACE IS A DIFFERENT SHAPE. `07-frontend/src/features/customers/moveShared.tsx` types the close-impact answer as `{landing, units_occupied_after, owner_on_record, owner_is_free_text, common_area_account_no, vacant_base_charge, open_sub_accounts, payment_plan}` — task 5.7's IMPACT screen. `settlement_for` serves `landing` and the whole of §15.9's money, and NONE of the other seven fields: they are premises occupancy, the BR-MET-105a owner (whose column does not exist), the master account, the vacant base charge and the payment-plan progress, each owned by another module. The path is the frontend's own; the payload is a SUPERSET on the money side and a SUBSET on the impact side, and no field is invented here to close the difference. REPORTED · (4) `openapi/schema.json` IS NOT REGENERATED BY THIS LANE. Four routes are added, so BE-11 TC05 will diff — the snapshot lives outside apps/customers and is not this lane's file (hard-won law 5: one generated file, committed once). The command is `python manage.py export_openapi` from 06-backend (MEASURED: `tests/test_be11_openapi.py::test_be11_tc05_…` is RED on this tree and names that command in its own message); REPORTED for whoever owns that commit · (5) NO NEW `message_key` IS MINTED. The only refusal raised in this layer reuses `customers.move_out.money_not_a_decimal`, which already resolves in all eleven catalogues (G32 PASS, baseline 0)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
