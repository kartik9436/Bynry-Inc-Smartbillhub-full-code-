# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-004 (EP-WRK-01) — `GET /work-orders`, the Orders tab's read.
#           Screens: Work-007 (head and table), Work-006 (the shell)
# Rules:    BR-WRK-001 (Work owns the list) · BR-SHL-011 (q/page/per house
#           parser) · A4 (the connections family: Executive VIEW, so any
#           tenant role may read) · CLAUDE.md hard rule 1 (the read runs under
#           the request's tenant context — BE-01)
# Tests:    06-backend/tests/test_us_wrk_004_orders_list.py (the list, the
#           dash, isolation) · 06-backend/openapi/schema.json (one new path)
# Impacts:  config/urls.py (one include line) · 07-frontend/src/features/work/
#           workEndpoints.ts
# ───────────────────────────────────────────────────────
"""work API — the READ half of the Work shell (wave A).

THIN by law (B8 / LAW 0): resolve the tenant, parse the list params, ask the
selector, answer in the ONE list envelope every list in this product answers
(`count` / `next` / `previous` / `results` — `metering/api.py`'s
`_connections_envelope` records why a second shape is not allowed).

ONE ROUTE IN WAVE A, AND WHERE THE OTHERS ARE
---------------------------------------------
    GET  /work-orders                     every open order, any anchor; q·page·per
    POST /work-orders                     the ONE raise every door uses (wave B)
    GET  /work-orders/awaiting-approval   finished, nobody accepted (wave B)

The six filters and the `400` on a seventh are wave G's (07-endpoints.md row
61). `POST /work-orders/{id}/field-result` and `/accept` stay mounted by
metering, unchanged, until §16 settles the move — which is why *Accept* is
pressed from the drawer this queue opens and not from a route of Work's own.

`core.errors` was imported unused in wave A for `G9`'s sake; wave B's `_payload`
raises from it, so the `noqa` is gone rather than left to rot as a comment that
stopped being true (hard-won law 1).
"""

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from apps.work import checklist, evidence, mobile, sync
from apps.work import money as work_money
from apps.work import asset_door, dispatch, edit, from_flows, rules as rules_svc, selectors
from apps.work import duplicate as duplicate_svc
from apps.work import raise_svc, services
from apps.work import technician_figures, template_help, template_history, templates_svc, workforce
from apps.work.seams import customers_seam, metering_seam
from core import errors
from core.pagination import parse_list_params, prepaged
from core.permissions import (
    AdminOrClerk,
    AnyTenantRole,
    FieldAppRole,
    SettingsReadAnyWriteSystemAdmin,
    WorkTemplateListRead,
    WorkOrdersReadAnyWriteAdminOrClerk,
)
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user, in the B12 §6a service shape: the id from the session
    user and the role the identity layer attached — NEVER client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    """The request body as a dict, or a refusal. A list or a string reaching a
    service that does `payload.get(...)` is an `AttributeError` in a 500, so it
    is refused at the door in the B12 §3 envelope instead."""
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    return data


def _envelope(request: Any, result: dict[str, Any]) -> dict[str, Any]:
    """A selector's page dict → **the four keys this product puts on the wire**.

    ⚠ **THIS IS A BOUNDARY AND IT RENAMES EVERYTHING, WHICH IS WHY THREE SCREENS
    SHIPPED BLANK (`DEF-WRK-4119`, `DEF-WRK-4119`, `DEF-AST-4120`, 2026-09-05).**
    In goes `{rows, page, per, total, …}`; out goes
    `{count, next, previous, results}` and **nothing else**. Three front-end
    wrappers were typed from the dict that goes IN — read out of `selectors.py`,
    which is the right file for the ROW shape and the wrong one for the reply —
    so `data.rows` was `undefined` in the browser and every one of those screens
    rendered its own *no results* state over rows this function had just served.
    Nothing caught it for the length of two waves: a hand-written TypeScript
    response type is checked against no response.

    Two consequences worth stating out loud, because both have now cost a
    screen:

    * **The names change.** `rows` → `results`, `total` → `count`. A client that
      says `rows` is reading the selector, not the API.
    * **Every other key is DISCARDED.** This returns a fresh dict; it does not
      update `result`. A view with an extra figure must spread —
      `{**_envelope(request, result), "counts": …}` — and `asset_work_orders`
      did not, so `maintenance_index` never left the server.

    The client's side of this contract is `07-frontend/src/api/paginated.ts`,
    which is now the ONE declaration of these four names and asserts them at
    runtime. `tests/test_def_ast_4120_envelope_extras.py` pins both halves.
    """
    per, page, total = result["per"], result["page"], result["total"]
    last = max(1, -(-total // per))
    url = request.build_absolute_uri()
    return {
        "count": total,
        "next": replace_query_param(url, "page", page + 1) if page < last else None,
        "previous": replace_query_param(url, "page", page - 1) if page > 1 else None,
        "results": result["rows"],
    }


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])  # read: all three · write: A4
def work_orders(request: Any) -> Response:
    """`GET /work-orders` — Work-007's table: every open order, every anchor.
    **`POST /work-orders` — THE ONE RAISE EVERY DOOR USES** (CR-070 wave B).

    `sort`/`dir` are declared empty because the order is fixed until the
    dispatcher's columns exist (wave G), and an undeclared param is ignored,
    never refused (BR-SHL-011).

    ⚠ **THE POST SHARES THIS VIEW BECAUSE DJANGO REACHES ONLY THE FIRST VIEW ON
    A PATH.** A sibling `path("work-orders", …)` for the write would be dead
    code that read as mounted — the bug `G52` found in the refunds lane. The
    role split lives in the permission class, one rule in one place.

    ⚠ **`07-endpoints.md` §1 row 14 — one raise, every caller.** The connection
    detail's *Raise order* (wave B), the Assets door, the move-out door and the
    rules engine (all wave M) arrive HERE. `apps.work.services.raise_work_order`
    hands straight to metering's `create_work_order` through the seam, which
    allocates the `WO-` number, writes the audit row naming the anchor, and
    refuses an order standing on nothing with a sentence a clerk can read
    (`work.order.anchor_required`) before the database's CHECK ever sees it.

    Wave A shipped this raise with the terminal as its only door, deliberately —
    *"a route with no screen and a screen with no route are the two halves of
    hard-won law 2"*. Wave B lands the screen and the route together.
    """
    require_tenant(request)
    if request.method == "POST":
        # `CR-168-BRC10` P2.5 — the raise may carry `assignee` and a visit
        # window (ruling 25); `raise_svc` writes the order and the assignment
        # in one transaction and pushes after it commits.
        return Response(raise_svc.raise_work_order(_actor(request), _payload(request)))
    # BR-WRK-026 — SIX FILTERS AND A 400 ON A SEVENTH, checked HERE because this
    # is the last place the raw query string exists. `parse_list_params` applies
    # BR-SHL-011's house rule (an undeclared param is IGNORED), which is right
    # for a list you read and wrong for a list you drive in bulk: a dispatcher
    # whose filter was silently dropped is looking at a wider list than they
    # think and ticking rows on it.
    dispatch.check_filters(request.query_params.keys())
    # `CR-168-BRC10` §7.3 — four DECLARED sorts. No sort chosen keeps the
    # dispatcher's fixed order (priority rank, then due), so `default_sort`
    # stays None and an undeclared sort still falls back (`BR-SHL-011`).
    params = parse_list_params(
        request.query_params, allowed_sorts=tuple(dispatch.SORTS), default_sort=None
    )
    result = dispatch.dispatch_page(
        q=params.q or None,
        filters={name: request.query_params.get(name) for name in dispatch.FILTER_PARAMS[1:]},
        page=params.page,
        per=params.per,
        sort=params.sort,
        direction=params.dir,
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # reading the queue is a VIEW right; Accept is not
def work_orders_awaiting_approval(request: Any) -> Response:
    """`GET /work-orders/awaiting-approval` — `Work-009`, `BR-WRK-007`.

    Every order the field has finished and nobody has accepted, across every
    connection and every anchor, oldest first. **The queue is a null, not a
    table:** no migration lands in this wave.

    The envelope carries one figure the standard one does not — `oldest_waiting`
    — because `Work-009`'s footer is *"3 orders · oldest waiting 6 days"* and
    the second half is a fact about the WHOLE queue that the page in hand cannot
    supply. It is `null` on an empty queue rather than `0`, because zero there
    would read as *"something has been waiting no time at all"*.

    ⚠ **A CROSS-TENANT ID IS A 404 IDENTICAL TO AN ABSENT ONE**, which needs no
    code here and is the point: the seam filters by the tenant in context and
    RLS `FORCE` sits under it, so Lone Star Ridge's queue simply has no Brazos
    Bend rows in it (`US-WRK-003` TC-5, hard rule 1).
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = selectors.awaiting_approval(page=params.page, per=params.per)
    return Response(
        {**_envelope(request, result), "oldest_waiting": result["oldest_waiting_days"]}
    )


# ── CR-070 wave O · one destination (§W.11) ─────────────────────────────────
#
# **`/connections/<uuid>` STOPS BEING A PLACE A PERSON NAVIGATES TO.** The PO,
# 2026-09-04: *"you are duplicating this — there is nothing called connections;
# Connection = Account only — you cannot have two different screens — this is an
# integration problem"*, scoped the same day to *"One screen too many … a person
# should reach the build's progress, its units, its work orders and its charges
# from the account, not from a parallel screen."*
#
# Five reads land here, and NOT ONE of them is a new filter. `BR-WRK-026` gives
# the dispatcher exactly six filters and a `400` on a seventh; these are PATHS,
# so that signed rule does not move (execution plan judgment 3).
#
#     GET /premises/{id}/work-orders    every job at an address
#     GET /accounts/{id}/work-orders    every job on an account and at its address
#     GET /premises/{id}/build          the build there, or `null`
#     GET /accounts/{id}/build          the build this account owns, or at its address
#     GET /work/builds/{id}/home        where a bookmarked link should land
#
# ⚠ **`null` IS AN ANSWER AND NOT AN ABSENCE OF ONE.** Most premises in a
# utility's book were connected before this product existed, so *"no build here"*
# is the ordinary case. The two build reads answer `{"build": null}` and the
# screen prints a sentence; a tab drawing an empty panel would be dead UI (law
# 2, `G13`), which is why the Build tab is not rendered at all when the answer
# is null.


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: reading work at an address is a VIEW right
def premises_work_orders(request: Any, premises_id: Any) -> Response:
    """`GET /premises/{id}/work-orders` — every job at this address.

    Every anchor, every state, newest first. The premises is the host that
    ALWAYS exists (execution plan judgment 1), and **that judgment stands on the
    column being OPTIONAL rather than on its writer being missing.**
    `connections.owner_account_id` is nullable; a build may carry no owner
    account because nobody named an owner, or because `BR-MET-116` refuses one on
    a build with no common area by design. An account-only host would render an
    empty screen for any of those builds.

    ⚠ **THIS PARAGRAPH SAID `create_owner_account()` RAISES
    `NotImplementedError("OQ-373")` UNTIL 2026-09-12 (`DEF-MET-5081`).** It does
    not, and has not since `OQ-373` closed on 2026-08-25 → `BR-MET-116`. The
    figure was right and the reason was wrong: measured with `app.tenant_id`
    set, **8 `brazosbend` connections, 0 with an owner account** — because the
    fixture seeds connection rows directly rather than committing them through
    `commit_connection` step 4.

    A cross-tenant id yields an empty page rather than a 404 here, and that is
    the same sentence as *"nothing has happened at this address"*: the seam
    filters by the tenant in context with RLS `FORCE` underneath, so Lone Star
    Ridge cannot learn that one of Brazos Bend's premises exists (hard rule 1).
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = selectors.orders_at_premises(premises_id, page=params.page, per=params.per)
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_work_orders(request: Any, account_id: Any) -> Response:
    """`GET /accounts/{id}/work-orders` — the jobs on this account and at its address.

    ⚠ **THE ADDRESS IS THE PREMISES', REACHED BY WALKING** (`BR-MET-1161`, PO
    2026-09-04). An account declares no address column and must not grow one, so
    the premises is found account → unit → premises and the orders are gathered
    from there. An account naming no unit gets its own orders and nothing else —
    a true, smaller list rather than a guessed larger one.

    Each row carries `stands_on`, so the screen can say whether a job stands on
    this account or on the address it shares (`US-WRK-004`).
    """
    require_tenant(request)
    row = customers_seam.account(account_id)
    if row is None:
        raise errors.NotFoundError()
    premises_id = None if row["unit_id"] is None else metering_seam.premises_id_of_unit(row["unit_id"])
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = selectors.orders_for_account(
        account_id, premises_id, page=params.page, per=params.per
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_build(request: Any, premises_id: Any) -> Response:
    """`GET /premises/{id}/build` — the build at this address, or `null`.

    Every figure is metering's own derivation, called by name through the seam;
    nothing is computed here and nothing is defaulted. `{"build": null}` when
    there is no build, and the screen says so in a sentence rather than drawing
    an empty Build tab (law 2).
    """
    require_tenant(request)
    return Response({"build": metering_seam.build_for_premises(premises_id)})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_build(request: Any, account_id: Any) -> Response:
    """`GET /accounts/{id}/build` — the build this account owns, or `null`.

    Two readings in order: the build whose `owner_account_id` names this account
    — the direct fact, **live since `OQ-373` closed on 2026-08-25 → `BR-MET-116`;
    this line said *"starts being true when `OQ-373` is ruled"* until 2026-09-12
    (`DEF-MET-5081`)** — then the build at the account's own address. The second
    reading is not a stand-in for an unbuilt first one: a build whose owner was
    never named has no `owner_account_id` to match, and its address still does.
    """
    require_tenant(request)
    row = customers_seam.account(account_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(
        {
            "build": metering_seam.build_for_account(account_id, row["unit_id"]),
            # `CR-162-BRC10` (PO 2026-10-02, ruled B) — a move-in before the
            # New Connection is approved: the account opens and billing waits,
            # and the account page says so with a link to the build.
            "awaiting_activation": metering_seam.unit_awaiting_activation(row["unit_id"]),
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def build_home(request: Any, connection_id: Any) -> Response:
    """`GET /work/builds/{id}/home` — where an old `/connections/…` link lands.

    ⚠ **A BOOKMARK IS A WORKING LINK AND STAYS ONE** (execution plan judgment
    5). The New Connect wizard's completion, the *New connects* tab and every
    bookmark point at `/connections/<uuid>` today. Answering 404 would break a
    working link in order to punish a screen, so the front end reads this and
    redirects: to the owner account where there is one, to the premises
    otherwise.

    A cross-tenant or unknown id is a **404 identical to an absent one** — the
    seam filters by the tenant in context and RLS refuses underneath it, so
    *"not yours"* and *"not there"* are the same sentence (hard rule 1).
    """
    require_tenant(request)
    home = metering_seam.build_home(connection_id)
    if home is None:
        raise errors.NotFoundError()
    return Response({"home": home})


# ── Work-025 · the parts register (wave C) ──────────────────────────────────
#
# THE ONLY WORK-OWNED REFERENCE ROUTES IN THIS WAVE, AND WHY THE OTHER FIFTEEN
# DO NOT EXIST. `07-endpoints.md` §2 counts 21 phase-1 reference-data endpoints
# and then asks, in its own margin, whether `BR-SHL-035`'s generic reference-
# data routes can serve the cards instead. They can: five of the six Work lists
# are `code · name · one detail` and are served by `GET|POST /lookups/{list}`
# and friends, with `apps/work/lookups.py` supplying the validation
# (`BR-TEN-031`). **21 → 4.**
#
# `parts` is the one that cannot be: the register carries part number,
# description, category, unit and unit cost, and the generic card renders code,
# name and ONE detail column. So it has its own four routes and its own screen.
@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups · DEF-196
def parts(request: Any) -> Response:
    """`GET /work/parts` — Work-025's Stock register · `POST` — Add part.

    ⚠ **THE ANSWER CARRIES NO `on_hand`, NO `reorder_at` AND NO `location`, AND
    THAT IS ASSERTED BY NAME.** The wireframe draws all three plus a reorder
    banner and *"Issues deduct stock the moment they are recorded"*; the
    commitment card that specifies the same screen says *"No stock levels, no
    reorder points"*, `CR-028` §11-D5 parked the stock table, and where the
    drawing and its card disagree the CARD wins (`DEF-WRK-3550`). Whether such
    a table may exist at all is `OQ-WRK-1490`, OPEN and routed to the Product
    Owner. `US-WRK-010` TC-5 asserts the three key names are absent from this
    body, so a lane cannot add stock quietly, and `POST` REFUSES an unknown
    field rather than ignoring it, so it cannot arrive from the other side.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_part(_actor(request), _payload(request)), status=201)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=(),
        default_sort=None,
        allowed_filters=("category", "unit", "status"),
    )
    result = selectors.parts_page(
        q=params.q or None,
        category=params.filters.get("category") or None,
        unit=params.filters.get("unit") or None,
        status=params.filters.get("status") or None,
        page=params.page,
        per=params.per,
    )
    # CR-168 · `DEF-WRK-9580` — the Unit filter's choices ride beside the page
    # (spread, never inside `_envelope`, which discards every other key).
    return Response({**_envelope(request, result), "units": selectors.part_units()})


@api_view(["GET", "PATCH"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def part(request: Any, part_id: str) -> Response:
    """`GET|PATCH /work/parts/{id}` — one register row.

    A cross-tenant id answers **404, identical to an id that does not exist**
    (CLAUDE.md hard rule 1): the selector filters by the tenant in context and
    RLS refuses underneath it, so *"not yours"* and *"not there"* are the same
    sentence — anything else is an existence oracle across the boundary.
    """
    require_tenant(request)
    if request.method == "PATCH":
        return Response(services.update_part(_actor(request), part_id, _payload(request)))
    row = selectors.part(part_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(row)


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE D · THE TEMPLATE BUNDLE (Work-013, Work-022)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NINE ROUTES, AND SEVEN COLLECTIONS SHARE ONE OF THEM.** A `PUT` per
# collection would be seven places to forget the tenant scope, the audit row
# or the sequence rewrite; `PUT /work/templates/{id}/{collection}` is one, and
# `templates_svc.COLLECTION_NAMES` is what it validates the last segment
# against — so an unknown collection is a refusal with a sentence, never a 404
# that reads as *"no such template"*.
#
# ⚠ **AUTHORING A TEMPLATE IS A SETTINGS-CLASS WRITE, NOT A CLERK'S.** It is
# how the utility decides what its crews do, so the permission class is the
# one the four Work reference cards already use: any tenant role may READ,
# a system admin writes. `US-WRK-013` §1 says *"as a utility admin"*.


@api_view(["GET", "POST"])
# `DEF-CUS-9048` (PO 2026-10-02) — a Billing Clerk READS this list (New Connect
# step 3 adds work from it); POST, and every other template door, is unchanged.
@permission_classes([WorkTemplateListRead])
def templates(request: Any) -> Response:
    """`GET /work/templates` — `Work-013`'s list · `POST` — a new DRAFT.

    The envelope carries two figures the house shape does not: `counts`, the
    footer's *4 published · 1 draft · 1 inactive*, computed over the whole list
    rather than the page (a footer that described the page in hand would change
    as a person paged), and each row's `contents`, which is `Work-013`'s
    *2 tasks · 0 parts · 1 reading* cell.

    ⚠ **`POST` CREATES A DRAFT AND NOTHING ELSE.** No version, no
    `template_no`, nothing an order can be raised from — `BR-WRK-011`, publish
    is the one write.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(templates_svc.create_draft(_actor(request), _payload(request)), status=201)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = selectors.templates_page(
        q=params.q or None,
        service=request.query_params.get("f.service") or None,
        page=params.page,
        per=params.per,
        # `CR-168-BRC10` P2.11 — the raise's step 1 (lane SRV-2).
        job_type=request.query_params.get("f.job_type") or None,
        asset_type=request.query_params.get("f.asset_type") or None,
        scope=request.query_params.get("f.scope") or None,
        raisable=str(request.query_params.get("f.raisable") or "").lower() in ("1", "true"),
    )
    return Response({**_envelope(request, result), "counts": result["counts"]})


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template(request: Any, template_id: Any) -> Response:
    """`GET|PATCH|DELETE /work/templates/{id}` — `Work-022`'s Overview.

    ⚠ **`PATCH` CANNOT TOGGLE `active` AND THAT IS `DEF-WRK-3579`.** Deactivate
    and Reactivate are their own routes with their own audit actions, so the
    one control a supervisor presses cannot arrive as an untraceable field
    edit. The header writer refuses `active` as an unknown field.

    ⚠ **`DELETE` IS REFUSED WHILE ANY VERSION IS REFERENCED**, naming the
    count (`BR-WRK-012`). The screen disables the button with the same reason
    and the server refuses independently — `BR-SHL-025`, both halves.
    """
    require_tenant(request)
    if request.method == "PATCH":
        return Response(
            templates_svc.update_header(_actor(request), template_id, _payload(request))
        )
    if request.method == "DELETE":
        return Response(templates_svc.delete(_actor(request), template_id))
    row = selectors.template(template_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(row)


@api_view(["PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_collection(request: Any, template_id: Any, collection: str) -> Response:
    """`PUT /work/templates/{id}/{collection}` — replace one collection whole.

    Replace-in-full is what makes the drag handle on `Work-015` work: six
    reordered tasks are ONE call carrying the new order, not six PATCHes with
    a moment in between where two rows claim `seq = 3`.

    The body is a list for the six list-shaped collections and an OBJECT for
    `details`, which is one row per template. The request may send either
    `{"rows": [...]}` or a bare list; both are accepted because a bare JSON
    array is what a `PUT` of a collection naturally looks like.
    """
    require_tenant(request)
    body = request.data
    rows = body.get("rows", body) if isinstance(body, dict) else body
    return Response(
        templates_svc.replace_collection(_actor(request), template_id, collection, rows)
    )


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_audit(request: Any, template_id: Any) -> Response:
    """`GET /work/templates/{id}/audit?page=&per=` — P3.28, image 47: the
    template's change history from `audit_log`, newest first, paged in SQL, in
    words (`apps/work/template_history.py`)."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = template_history.template_audit(template_id, page=params.page, per=params.per)
    return Response(
        {
            **_envelope(request, result),
            "template_no": result["template_no"],
            "name": result["name"],
        }
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_help_upload_url(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/help/upload-url {filename, content_type}` —
    P3.14: where to send a help document, its ceiling and accepted types."""
    require_tenant(request)
    return Response(template_help.upload_ticket(template_id, _payload(request)))


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_help_documents(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/help/documents` (multipart `file`) — stores
    one help document and answers its `ref` for the help row (P3.14)."""
    require_tenant(request)
    upload = request.FILES.get("file")
    return Response(
        template_help.store(_actor(request), template_id, upload, dict(request.data or {})),
        status=201,
    )


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_help_content(request: Any, template_id: Any, document_id: Any) -> Any:
    """`GET /work/templates/{id}/help/documents/{doc}/content` — the file's
    bytes, same-origin (`DEF-WRK-9594`'s reason), `private, no-store`."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type, name = template_help.content(template_id, document_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    safe = "".join(ch for ch in name if ch.isprintable() and ch not in '"\\')
    response["Content-Disposition"] = f'inline; filename="{safe}"'
    return response


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_publish(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/publish` — **THE ONE WRITE** (`BR-WRK-011`).

    Pressed twice within a second with nothing changed in between, it answers
    the version that already exists and writes nothing — `created: false` says
    so. That is not an idempotency key: it is the honest question *has anything
    in this bundle changed since the last publish*, and a v2 identical to v1 is
    a number a supervisor would have to explain on `Work-022`.
    """
    require_tenant(request)
    payload = _payload(request) if request.data else {}
    return Response(
        templates_svc.publish(
            _actor(request), template_id, change_note=payload.get("change_note")
        )
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_duplicate(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/duplicate` — a new DRAFT with every child row
    copied, the name suffixed *(copy)*, no number and no version."""
    require_tenant(request)
    return Response(templates_svc.duplicate(_actor(request), template_id), status=201)


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_deactivate(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/deactivate` — `BR-WRK-012`: stop new orders,
    leave every order already raised readable."""
    require_tenant(request)
    return Response(templates_svc.deactivate(_actor(request), template_id))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_reactivate(request: Any, template_id: Any) -> Response:
    """`POST /work/templates/{id}/reactivate` — the mirror route
    `DEF-WRK-3579` asks for, so `PATCH` never has to toggle `active`."""
    require_tenant(request)
    return Response(templates_svc.reactivate(_actor(request), template_id))


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_versions(request: Any, template_id: Any) -> Response:
    """`GET /work/templates/{id}/versions` — `Work-022`'s Versions tab.

    Each row carries the orders it produced, counted from `work_orders` at
    read time. That count IS the demonstration of `BR-WRK-008`: v2 is current
    and the four v1 orders still read v1, because nothing was rewritten.
    """
    require_tenant(request)
    row = selectors.template_versions(template_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(row)


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_usage(request: Any, template_id: Any) -> Response:
    """`GET /work/templates/{id}/usage` — the total and the per-version
    breakdown that sums to it (`US-WRK-018` TC-7)."""
    require_tenant(request)
    row = selectors.template_usage(template_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(row)


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def template_packs(request: Any) -> Response:
    """`GET /work/template-packs` — the three platform packs, as constants.

    ⚠ **THE BUILDER THAT CONSUMES THEM IS WAVE E's** (`US-WRK-016`). This route
    exists because `Work-013`'s *+ New template* needs somewhere to send a
    person, and the packs are what step 1 offers; nothing in wave D renders a
    control onto the builder, which is hard-won law 2 read the right way round.
    """
    require_tenant(request)
    return Response({"packs": selectors.template_packs()})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def proposed_work_orders(request: Any) -> Response:
    """`GET /connections/proposed-work-orders?services=electric,water` —
    `US-WRK-017`, and the sentence that comes off `Work-004`.

    Step 6 of the New Connect wizard has been called *Plans & work orders*
    since the wizard shipped and has proposed no work orders at all: the screen
    says, in its own copy, *"Those templates are not built yet, so no orders
    are proposed here."* Wave D built the templates. This is what the step
    reads instead.

    ⚠ **`AnyTenantRole`, NOT THE SETTINGS CLASS THE REST OF THIS FILE'S
    TEMPLATE ROUTES USE.** Authoring a template is a system admin's act, which
    is why `/work/templates` is `SettingsReadAnyWriteSystemAdmin`; READING which
    jobs a new build needs is what a clerk running the wizard does all day, and
    `OQ-WRK-1492` was closed on 2026-09-04 with exactly that reasoning in the
    PO's own words — *"clark can do it sicne it s a day to day work"*.

    ⚠ **THIS PATH BEGINS WITH METERING'S NOUN AND IS SERVED HERE ON PURPOSE.**
    Wave O set the pattern (`premises/{id}/work-orders`, `accounts/{id}/build`):
    the noun belongs to another module, the CONTENT is Work's, so Work serves
    it. It is also what keeps `apps/customers` honest — the wizard reads this
    over HTTP and never touches `work_order_templates` with an ORM query, which
    is `A7`'s boundary and the mirror of what `G78` enforces from Work's side.

    ⚠ **NOTHING IS WRITTEN, HERE OR ANYWHERE, UNTIL STEP 9** (`BR-MET-112`).
    """
    require_tenant(request)
    from apps.work import from_flows

    # `CR-171-BRC10` P1.19 (lane MVI-WIZ-UNIT) — `?flow=move_in` (or another
    # screen moment with a *Field visit* table) asks for THAT flow's half of
    # the sequence split: the jobs done to a service that already exists. The
    # same reader `raise_orders_for` checks a named template against, so the
    # list a clerk picks from and the list the raise accepts are one list.
    flow = str(request.query_params.get("flow") or "").strip()
    if flow in from_flows.TABLE_MOMENTS:
        offer = selectors.proposed_work_orders(
            request.query_params.get("services"),
            in_sequence=from_flows._IN_CONNECTION_SEQUENCE[flow],
        )
        return Response(offer)
    offer = selectors.proposed_work_orders(request.query_params.get("services"))
    # `CR-168-BRC10` P3.42 — step 6 is the *new connection* screen moment: an
    # enabled Work rule on it marks its template `preselected_by {id, name}`
    # (added when the services' offer lacks it), and step 9's commit applies
    # the rule's priority and holder to that job. Nothing is written here.
    asked = set(offer.get("services") or ())
    proposed = [
        row
        for row in from_flows._preselect("new_connect", offer["proposed"])
        # A rule's template is added only for a service this build carries —
        # a water rule never puts a water job on an electric-only build.
        if not row.get("preselected_by")
        or not (row.get("service") or {}).get("code")
        or (row["service"]["code"] in asked)
    ]
    return Response({**offer, "proposed": proposed, "count": len(proposed)})


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE P · WHAT A FLOW COULD RAISE (US-WRK-039, BR-WRK-055)
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def flow_raise_options(request: Any) -> Response:
    """`GET /work/raise-options` (`DEF-CUS-6363`) — the job types and priorities a
    flow's *+ Add work order* row offers. Readable by every role that can read a
    work order, because every name in it is already printed on those rows; see
    `from_flows.raise_options` for why the Settings lookups cannot serve it."""
    require_tenant(request)
    return Response(from_flows.raise_options())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def flow_proposed_work_orders(request: Any, flow_kind: str, flow_id: str) -> Response:
    """`GET /work/flows/{kind}/{id}/proposed` — what this flow could raise.

    `kind` is one of `service_request` · `move_out` · `move_in` · `transfer` ·
    `reconnect`. The answer is the utility's own PUBLISHED templates for the
    services the flow touches, the flow's own reference, and — when judgment 8
    bites — a `refusal` the panel draws instead of the list.

    ⚠ **THIS IS THE DOOR `apps/customers` USES TO DRAW THE PANEL, AND IT IS
    HTTP ON PURPOSE.** `A7`'s boundary and `G78`'s mirror: the wizard reads what
    Work has to offer over the API and never touches `work_order_templates`
    with an ORM query. The RAISE is a different door — a service call inside the
    flow's own transaction (`apps/customers/seams.py`), because the job has to
    be created in the same commit that finishes the flow or not at all.

    ⚠ **`AnyTenantRole`, for `proposed_work_orders`' reason directly above:**
    `OQ-WRK-1492` was closed on 2026-09-04 in the PO's own words — *"clark can
    do it sicne it s a day to day work"*. Reading which jobs a move-out needs is
    exactly that.

    **NOTHING IS WRITTEN.** `propose` is a read end to end.
    """
    require_tenant(request)
    return Response(from_flows.propose(flow_kind, flow_id))


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_settings_visit_messages(request: Any) -> Response:
    """`GET` · `POST /work/settings/visit-messages` `{visit_prep_default}` —
    the utility's default preparation text for customer visit messages, used
    when a job's template has none (`DEF-WRK-10652`, PO 2026-10-29 ruling 3B)."""
    require_tenant(request)
    if request.method == "POST":
        return Response(
            workforce.set_visit_message_settings(_actor(request), _payload(request))
        )
    return Response(workforce.visit_message_settings())


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def raise_meter_read_field_work(request: Any) -> Response:
    """`POST /work/flows/meter-read/raise` — send somebody out to these meters.

    **THE SIXTH CALLER OF `from_flows.raise_for`** (PO ruling 2026-09-14,
    verbatim ***"please build this"***, reversing that morning's deferral of the
    Reads→Work door). Body:

        {"meters": ["<asset id>", …], "template_ids": ["<template id>", …]}

    ⚠ **WHY THE RAISE IS HTTP HERE WHEN THE OTHER FIVE DO IT AS A SERVICE
    CALL.** Those five raise INSIDE the flow's own transaction, because the job
    has to exist in the same commit that finishes the move-out or not at all. A
    shortfall has no such commit: pressing *Send someone out* IS the whole act.
    So the raise is a ROUTE, on the Work side, for the reason
    `flow_proposed_work_orders` directly above already gives — the noun belongs
    to metering, the CONTENT is Work's, so Work serves it. Metering therefore
    writes nothing to `work_orders` and needs no seam of its own for this.

    ⚠ **THE RAISE IS OFFERED AND NEVER AUTOMATIC** (`from_flows` rule 1). This
    route is reached only by a person pressing a control and ticking templates;
    **no flag, no validation rule and no import commit calls it.** Empty
    `template_ids` raises nothing and is not an error — a clerk who ticked
    nothing has answered the question.

    ⚠ **PARTIAL SUCCESS IS AN ANSWER, NOT AN ERROR — `BR-WRK-055`.** One meter
    whose premises cannot be resolved must not cost the other eleven their
    visits, and must not cost the clerk their reading work either. Each meter is
    raised inside `raise_for`'s own `atomic()`, which is the OUTERMOST block here
    (`ATOMIC_REQUESTS` is set nowhere in `config/settings`), so a refusal rolls
    back that meter alone and the next iteration opens a fresh transaction. ⚠
    **That is hard-won law 14 and it is a claim about PostgreSQL the default
    suite cannot test** — the suite is in-memory SQLite, which has no
    aborted-transaction state and passes the broken version too. It is proved on
    a real database in `06-backend/tests/test_reads_field_work_pg.py`.

    ⚠ **AND NO SECOND SIGNATURE.** PO, the same day: *"we do not need
    confirmation or sign off from another person."* Nothing here waits for an
    approval, and nothing is left pending for one.
    """
    require_tenant(request)
    data = _payload(request)
    meters = [str(value) for value in (data.get("meters") or []) if str(value).strip()]
    template_ids = data.get("template_ids") or []
    if not meters:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.fromFlows.noMeters",
            br_ref="BR-WRK-006",
        )
    actor = _actor(request)
    raised: list[dict[str, Any]] = []
    not_raised: list[dict[str, Any]] = []
    for asset_id in meters:
        try:
            result = from_flows.raise_for(
                from_flows.FLOW_METER_READ, asset_id, template_ids, actor
            )
        except from_flows.FlowRaiseRefused as exc:
            # Judgment 8's refusal — this meter stands at no address. It is DATA
            # here rather than a 400, because the other meters were fine and the
            # clerk has to see both halves of that in one answer.
            not_raised.append(
                {"meter_id": asset_id, "code": exc.code, "message_key": exc.message_key}
            )
        except Exception as exc:  # noqa: BLE001 — BR-WRK-055; see the docstring
            # ⚠ **BROAD ON PURPOSE, AND NOT A SHRUG.** `BR-WRK-055` says the flow
            # completes whether or not the visit could be booked, and the flow
            # here is a clerk's reading work. A template deactivated mid-press, a
            # constraint, an unpublished seam — each is a visit that did not
            # happen and NONE of them is a reason to lose the other meters. Every
            # one is REPORTED per meter and never swallowed into silence, which
            # is `DEF-708`'s shape and what `from_flows`' own docstring warns
            # about: an act recorded that never happened.
            not_raised.append(
                {
                    "meter_id": asset_id,
                    "code": from_flows.NOT_RAISED_CODE,
                    "message_key": from_flows.NOT_RAISED_KEY,
                    "detail": str(exc),
                }
            )
        else:
            raised.extend(result["raised"])
    return Response(
        {
            "raised": raised,
            "count": len(raised),
            "not_raised": not_raised,
            # The platform's ONE sentence for a raise that could not happen. Work
            # owns the words, so a clerk never meets two spellings of one fact
            # depending on which failure they hit.
            "warning": from_flows.not_raised_warning() if not_raised else None,
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE F · THE WORKFORCE (Work-023, Work-024) — 07-endpoints.md §4
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHO MAY READ AND WHO MAY WRITE, AND WHY IT IS NOT THE SETTINGS SHAPE.**
# Deciding that D. Ortiz holds Water II is an OPERATIONAL act a supervisor does
# on a Tuesday, not a Settings change: the SKILL CATALOGUE is Settings (`work/
# lookups`, System Admin writes) and who holds one is dispatch. So these carry
# `WorkOrdersReadAnyWriteAdminOrClerk` — any tenant role reads, a system admin
# or a billing clerk writes — the same class the orders list already uses, and
# for the same A4 reason.
#
# ⚠ **AND A FIELD TECHNICIAN READS NONE OF IT, WITHOUT A LINE HERE SAYING SO.**
# `core.permissions.ROLES` is the three OFFICE roles, so `_role_of` answers
# None for `field_technician` and every one of these routes refuses with 403 —
# which is `US-WRK-023` TC-4 exactly. Adding the fourth role to that frozenset
# would have granted it every read surface in the product in one line.


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def crews(request: Any) -> Response:
    """`GET /work/crews` — `Work-023`'s one table · `POST` — add a crew.

    The envelope carries `counts`, which is `Work-023`'s footer sentence — *6
    rows · 4 people, 1 crew, 1 contractor* — computed over the whole list and
    not over the page, because it is a fact about the utility.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(workforce.create_crew(_actor(request), _payload(request)), status=201)
    # `CR-168-BRC10` P3.4 / ruling 30 — `view` picks one of the three lists,
    # each cut in SQL; `counts {technicians, crews, contractors}` are the
    # three tab badges. No `view` answers the one-table shape for one round.
    params = parse_list_params(
        request.query_params, allowed_sorts=workforce.CREW_SORTS, default_sort="name"
    )
    result = workforce.crews_page(
        q=params.q or None,
        page=params.page,
        per=params.per,
        view=request.query_params.get("view") or None,
        sort=params.sort,
        direction=params.dir,
    )
    body = _envelope(request, result)
    body["counts"] = result["counts"]
    return Response(body)


@api_view(["PATCH"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def crew(request: Any, crew_id: Any) -> Response:
    """`PATCH /work/crews/{id}` — rename, re-shift or deactivate one."""
    require_tenant(request)
    return Response(workforce.update_crew(_actor(request), crew_id, _payload(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def crew_directory(request: Any) -> Response:
    """`GET /work/crew-directory` — who works here, as a NAME and an EMAIL.

    `BR-AST-533`, PO ruling 2026-09-12: ***"a) Let a clerk read the crew list
    (name + email only)"***. It exists so that a Billing Clerk logging a repair
    (`BR-AST-038`) picks the technician from a list instead of typing a uuid
    into a text box, which is B14 rule 31 broken for the one role that screen
    was written for.

    ⚠ **READ-ONLY, AND GET-ONLY.** There is no POST here and there must not be:
    inviting a login is `identity`'s (`BR-IDN-011`) and making one a technician
    is `POST /work/technicians` one function up. This route answers a picker and
    nothing else.

    ⚠ **IT DOES NOT WIDEN `GET /users`, WHICH STAYS `SystemAdminOnly`.**
    Measured with a real Billing Clerk session on `pine-hill`, 2026-09-12:
    `GET /users` → **403 `BR-IDN-009`**, this route → **200 · 7 rows**.

    ⚠ **AND IT IS DELIBERATELY NOT `GET /work/technicians`.** A clerk can
    already read that one, and it carries `role_code`, `status` and
    `has_profile` — the three things the ruling names as not-served. They
    cannot be dropped from it (`Work-023` marks who already has a profile), so
    the narrow contract gets its own address rather than the wide one getting
    quietly narrowed under a screen that needs it.

    The permission class is the workforce set's own: **any of the three office
    roles reads**, a system admin or a billing clerk writes — and there is
    nothing here to write. A `field_technician` still meets 403, because
    `core.permissions.ROLES` is the three office roles and `_role_of` answers
    None for the fourth (`US-WRK-023` TC-4, unchanged by this route).
    """
    require_tenant(request)
    rows = workforce.crew_directory()
    return Response({"count": len(rows), "next": None, "previous": None, "results": rows})


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technicians(request: Any) -> Response:
    """`GET /work/technicians` — the logins that could BE one · `POST` — add.

    ⚠ **THE `GET` ANSWERS THE PICKER, NOT THE TABLE.** `Work-023`'s table is
    `/work/crews` above, which is people AND crews AND contractors in one list
    because that is what the screen draws. This route serves the *add a
    technician* choice: every active or invited login of the tenant, with the
    ones that already have a profile marked, so a supervisor picks a person who
    exists instead of typing an email and being told off (`BR-WRK-028`).
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(
            workforce.create_technician(_actor(request), _payload(request)), status=201
        )
    # PAGED IN SQL since lane SRV-4 (NFR-3; `?q=` searches name and email),
    # each login with the crew it is on (image 26's *on Field crew A*).
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return Response(
        _envelope(request, workforce.staff_page(q=params.q or None, page=params.page, per=params.per))
    )


@api_view(["GET", "PATCH"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician(request: Any, slug: str) -> Response:
    """`GET|PATCH /work/technicians/{slug}` — `Work-024`.

    ⚠ **THE PATH SEGMENT IS A SLUG AND NOT AN ID** — `…/work/crews/r-patel`,
    which is the address `WS-24` itself draws. B14 rule 31 says no database id
    is the visible value of anything, and a URL is the most visible value a
    screen has.

    A slug from another tenant answers **404, identical to one that does not
    exist** (CLAUDE.md hard rule 1): slugs are computed per tenant, so the
    other utility's `r-patel` is simply not found here.
    """
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    if request.method == "PATCH":
        payload = _payload(request)
        # P3.44 — `crew_id` moves the technician (null takes them off a crew);
        # the availability fields keep `set_unavailable`'s meaning. A PATCH
        # naming neither is the availability write it always was.
        if "crew_id" in payload:
            workforce.move_technician(_actor(request), row["id"], payload.get("crew_id"))
        # CR-168-BRC10 §30 — the daily job limit (PO answer (2), 2026-10-05).
        if "daily_job_limit" in payload:
            workforce.set_daily_job_limit(_actor(request), row["id"], payload.get("daily_job_limit"))
        moved = {"crew_id", "daily_job_limit"} & set(payload)
        if not moved or {"status", "reason"} & set(payload):
            return Response(workforce.set_unavailable(_actor(request), row["id"], payload))
        return Response(workforce.technician_by_slug(slug) or row)
    return Response(row)


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_jobs(request: Any, slug: str) -> Response:
    """`GET /work/technicians/{slug}/jobs?f.state=open|done&q=&page=&per=` —
    image 32 (P3.45): every job the person holds or was ever given, paged in
    SQL, newest first; `still_holds` marks the ones that moved away."""
    require_tenant(request)
    params = parse_list_params(
        request.query_params, allowed_filters=("state",), allowed_sorts=(), default_sort=None
    )
    result = technician_figures.jobs_page(
        slug,
        state=params.filters.get("state") or None,
        q=params.q or None,
        page=params.page,
        per=params.per,
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_performance(request: Any, slug: str) -> Response:
    """`GET /work/technicians/{slug}/performance?period=&page=&per=` — image 34
    (P3.46): Performance's arithmetic for one person; `tiles` over the period,
    the by-job-type rows paged in SQL."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = technician_figures.performance(
        slug,
        period=request.query_params.get("period") or None,
        page=params.page,
        per=params.per,
    )
    body = _envelope(request, result)
    body.update(
        {"period": result["period"], "technician": result["technician"], "tiles": result["tiles"]}
    )
    return Response(body)


@api_view(["PUT"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def crew_skills(request: Any, crew_id: Any) -> Response:
    """`PUT /work/crews/{id}/skills` — P3.52, `{skills[] {skill_id,
    proficiency}}`, a replace, audited (the technician's own shape)."""
    require_tenant(request)
    return Response(workforce.set_crew_skills(_actor(request), crew_id, _payload(request)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def crew_members(request: Any, crew_id: Any) -> Response:
    """`POST /work/crews/{id}/members` — ruling 26, *Add crew member*:
    `{technician_id}` moves one onto the crew, `{user_id}` makes a profile for a
    login and puts it there. Answers the crew with its counted `members`."""
    require_tenant(request)
    return Response(
        workforce.add_crew_member(_actor(request), crew_id, _payload(request)), status=201
    )


@api_view(["PUT"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_skills(request: Any, slug: str) -> Response:
    """`PUT /work/technicians/{slug}/skills` — the skills wizard's confirm.

    A REPLACE: step 2 of the wizard shows the whole set and a supervisor who
    unticks Water II means it.
    """
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return Response(workforce.set_skills(_actor(request), row["id"], _payload(request)))


@api_view(["PUT"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_certifications(request: Any, slug: str) -> Response:
    """`PUT /work/technicians/{slug}/certifications`.

    A date in the PAST is accepted (`US-WRK-021` TC-5) — refusing it would lose
    the record of a lapse, which is the one thing the watch exists to show.
    """
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return Response(workforce.set_certifications(_actor(request), row["id"], _payload(request)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_certificate_proof(request: Any, slug: str, type_id: Any) -> Response:
    """`POST /work/technicians/{slug}/certifications/{type_id}/proof`
    (multipart `file`) — image 33's PROOF: the certificate's scan, stored and
    named by the certificate (lane SRV-4, `tenancy/0060`)."""
    from apps.work import certificate_proof

    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return Response(
        certificate_proof.store(_actor(request), row, type_id, request.FILES.get("file")),
        status=201,
    )


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_certificate_proof_content(request: Any, slug: str, type_id: Any) -> Any:
    """`GET …/certifications/{type_id}/proof/content` — the proof's bytes,
    same-origin, `private, no-store` (the page policy refuses a storage host,
    `DEF-WRK-9594`'s reason)."""
    from django.http import HttpResponse

    from apps.work import certificate_proof

    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    payload, content_type, name = certificate_proof.content(row, type_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    safe = "".join(ch for ch in name if ch.isprintable() and ch not in '"\\')
    response["Content-Disposition"] = f'inline; filename="{safe}"'
    return response


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_unavailable(request: Any, slug: str) -> Response:
    """`POST /work/technicians/{slug}/unavailable` — `WS-24`'s *Set
    unavailable*, and the way back (`status: on_shift`)."""
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return Response(workforce.set_unavailable(_actor(request), row["id"], _payload(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def certification_watch(request: Any) -> Response:
    """`GET /work/certification-watch` — expiries within 30 and 60 days.

    ⚠ **IT REFUSES NOTHING AND IT NEVER DID.** What changed on 2026-09-04 is
    that `OQ-WRK-1493` was RULED — option (c), a per-tenant setting defaulting
    to *warn* — so the answer now carries `policy` and `blocks`, and the screen
    renders *blocked from N template types* only where the utility has switched
    blocking on. A screen may not claim a guarantee the setting has switched
    off (hard-won law 1).
    """
    require_tenant(request)
    return Response(workforce.certification_watch())




# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE G · THE DISPATCHER — 07-endpoints.md §5
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NINE ROUTES HERE AND THE TENTH IS `GET /work-orders` ABOVE**, which grew
# the six filters rather than gaining a sibling — Django reaches only the first
# view on a path, so a second `path("work-orders", …)` would be dead code that
# read as mounted (the `G52` shape this file already records for the POST).
#
# ⚠ **`GET /work-orders/map` (row 68) IS BUILT — CR-070 wave I, 2026-09-05.**
# This paragraph said it was NOT, deliberately, so that the absence read as a
# plan rather than a gap. The plan has been executed and the note is corrected
# in the same commit that mounts the route, because a stated absence that
# outlives its own absence is hard-won law 2's mirror (`DEF-CWP-3925`: eight
# doors, two working, every refusal true on the day it was written).
#
# The seam question it named is answered: the coordinates come from
# `premises.lat`/`lng` through the SAME anchor walk the list's address cell uses
# (`dispatch._premises_row_of`), because hard rule 8 says a work order declares
# no coordinate of its own — so a pin and an envelope for one job cannot point
# at different buildings. Not `customers_seam`: premises is metering's.


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: reading the board is a VIEW right
def work_kpis(request: Any) -> Response:
    """`GET /work/kpis` — the five tiles, counted over the whole open window."""
    require_tenant(request)
    return Response(dispatch.kpis())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_areas(request: Any) -> Response:
    """`GET /work/areas` — the Area chip's options, from `tenancy.Area` (US-WRK-011).

    ⚠ **NOT A SEVENTH FILTER.** `BR-WRK-026` counts the filters ON THE LIST; this
    serves the options for one of the six, the way every other chip in the
    product is filled. The rule that does not move is that Work never keeps its
    own copy of an area (`BR-WRK-022`).
    """
    require_tenant(request)
    return Response({"results": dispatch.area_options()})


@api_view(["GET", "PATCH"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_detail(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}` — one order's dispatch row.
    `PATCH /work-orders/{id}` — **everything a dispatcher changes after the
    order exists** (`CR-070` wave I, `US-WRK-031`, `Work-021`).

    Wave H builds `Work-008` on the GET; it was served by `G2` because a screen
    with no route is the other half of hard-won law 2.

    ⚠ **TWO VERBS ON ONE VIEW, BECAUSE DJANGO REACHES ONLY THE FIRST VIEW
    REGISTERED ON A PATH.** A sibling `path("work-orders/<uuid:order_id>", …)`
    for the write would be dead code that never runs — the mistake this file
    already records twice, for `work-orders` itself and in the `G52` shape.

    **So the permission class changes from `AnyTenantRole` to
    `WorkOrdersReadAnyWriteAdminOrClerk`, and READING IS NOT NARROWED BY IT:**
    that class's `SAFE_METHODS` set lets every tenant role GET this row exactly
    as before, and restricts only the PATCH to a System Admin or a Billing
    Clerk — the same pair holding every other write in this file. `BR-SHL-025`:
    the server enforces it independently of whatever the screen has disabled.
    """
    require_tenant(request)
    if request.method == "PATCH":
        return Response(edit.save_order_edit(_actor(request), order_id, _payload(request)))
    return Response(dispatch.order_row(order_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_by_number(request: Any, order_no: str) -> Response:
    """`GET /work-orders/by-number/{order_no}` — the ONE door that takes the
    reference a person can read, and the only new route `DEF-WRK-4518` needed.

    ⚠ **WHY A LOOKUP AND NOT A BY-NUMBER TWIN OF ALL FOURTEEN ROUTES.** The
    order-detail screen makes fourteen calls and every route on this family is
    `<uuid:order_id>`, so an address carrying `WO-0016` 404'd fourteen times and
    drew a dash for each. Two shapes of fix were on the table: give the whole
    family a by-number door, or let the screen RESOLVE the number once and use
    the id for the other thirteen. This is the second, and the reasons are
    recorded in `02-decision-log.md` (2026-09-07): one new endpoint against
    fourteen changed ones, and a by-number vocabulary spread over fourteen
    routes would make every future route on this family choose a door.

    ⚠ **IT RETURNS THE WHOLE ROW, NOT JUST THE ID, AND THAT IS THE POINT OF
    RESOLVING ONCE.** The screen's first call is the detail read either way, so
    answering with the id alone would cost a second round trip to fetch what
    this query already has in hand.

    Read permission is `AnyTenantRole`, the same as `GET /work-orders/{id}` —
    this door answers exactly what that one answers and must not become a way
    to read a row a role could not otherwise reach (`BR-SHL-025`).
    """
    require_tenant(request)
    return Response(dispatch.order_row_by_number(order_no))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_edit_form(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/edit` — the RAW values `Work-021` opens with.

    Separate from the detail row above because the two answer different
    questions: the LIST needs an area's NAME to draw a cell, the FORM needs its
    ID to select an option. Serving the display row into a form makes a select
    that cannot post back what it shows — and it fails SILENTLY, with every
    check green, which is `DEF-CUS-3653`'s shape exactly.
    """
    require_tenant(request)
    return Response(edit.form_values(order_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_orders_map(request: Any) -> Response:
    """`GET /work-orders/map` — the day's work on the ground (`US-WRK-029`).

    ⚠ **THE SAME SIX FILTERS, CHECKED BY THE SAME FUNCTION.** `check_filters`
    runs here exactly as it does on the list, so a seventh parameter is a `400`
    on the map too (`BR-WRK-026`). A map that quietly ignored a filter the list
    refuses would let a dispatcher believe they were looking at North when they
    were looking at everything — the same argument `BR-WRK-026` makes for the
    list, and stronger here, because you cannot count pins.
    """
    require_tenant(request)
    dispatch.check_filters(request.query_params.keys())
    return Response(
        dispatch.map_pins(
            q=request.query_params.get("q"),
            filters={p: request.query_params.get(p) for p in dispatch.FILTER_PARAMS},
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_audit(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/audit` — the assignment history, oldest first.

    This is what proves `BR-WRK-027`: a bulk assign of three orders leaves three
    rows here, one per order.
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = dispatch.order_audit(order_id, page=params.page, per=params.per)
    # ⚠ PAGED (`CR-168-BRC10` P4.11, NFR-3) — the house envelope, plus
    # `order_no`. SRV-1's one-round `rows` twin is retired (lane SRV-3,
    # 2026-10-04): the order page reads `results` when `rows` is absent
    # (`orderPageEndpoints.getOrderHistory`) and the other reader was dead.
    return Response(
        {**_envelope(request, result), "order_no": result["order_no"]}
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_candidates(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/candidates?q=&page=&per=` — every technician,
    crew and contractor with ADVICE beside each, best fit first, **paged and
    uncapped** (`CR-168-BRC10` P4.5/P4.12, NFR-5; `BR-WRK-029` SUPERSEDED by
    ruling 2). The house envelope `{results, count, next, previous}`, plus
    `skill` and `on`. (SRV-2's one-round `policy` and `candidates` twins were
    retired by lane SRV-3 once lane ASSIGN read only `results`, 2.501.1.)"""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = dispatch.assign_candidates(
        order_id, q=params.q or None, page=params.page, per=params.per
    )
    return Response(
        {
            **_envelope(request, result),
            "skill": result["skill"],
            "on": result["on"],
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def raise_candidates(request: Any) -> Response:
    """`GET /work/candidates?template_id=&premises_id=&unit_ids=&on=&q=&page=&per=`
    — the same advice BEFORE the job exists (`CR-168-BRC10` P2.5, ruling 25:
    *"user can either assign or can leave blank"*). The raise's step 2 has no
    order to ask about, so it names what the order WILL be: the template (its
    skill), the premises (its area — ruling 24, never asked) and the day."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = raise_svc.raise_candidates(
        template_id=request.query_params.get("template_id") or None,
        premises_id=request.query_params.get("premises_id") or None,
        unit_ids=_id_list(request.query_params.get("unit_ids")),
        on=request.query_params.get("on") or None,
        q=params.q or None,
        page=params.page,
        per=params.per,
    )
    return Response({**_envelope(request, result), "skill": result["skill"], "on": result["on"]})


def _id_list(raw: Any) -> list[str]:
    """`a,b,c` (or a repeated param read by the caller) → a list of ids."""
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_assignments(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/assignments` — appends a row, never updates."""
    require_tenant(request)
    return Response(dispatch.record_act(_actor(request), order_id, _payload(request)))


# ── CR-070 wave H · the order's own copies — 07-endpoints.md §6 #71–#73 ────


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_checklist(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/checklist` — the six copy collections (#71).

    Everything served here is the ORDER's copy, never the template's live rows
    (`BR-WRK-008`). It also carries `safety_lock`, so the screen and the phone
    both draw the same locked/unlocked state from the same evaluation rather
    than each deciding for itself.
    """
    require_tenant(request)
    return Response(checklist.checklist(order_id))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_safety_tick(request: Any, order_id: Any, safety_id: Any) -> Response:
    """`POST /work-orders/{id}/safety/{sid}/tick` (#72) — lifts the lock.

    Never refused by the lock: this is the act that clears it.
    """
    require_tenant(request)
    return Response(checklist.tick_safety(_actor(request), order_id, safety_id))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_task_tick(request: Any, order_id: Any, task_id: Any) -> Response:
    """`POST /work-orders/{id}/tasks/{tid}/tick` (#73) — **refused while the
    safety lock holds** (`BR-WRK-037`).

    ⚠ **THE REFUSAL IS HERE AND NOT ONLY ON THE SCREEN.** `Work-008` greys the
    task list and `Work-011` locks it, and both of those are courtesies: this
    route refuses on its own, so the rule survives a replayed request, a sync
    batch that arrived out of order, and anything the phone attempts while
    offline. Hard-won law 1 — a disabled control claiming a guarantee is not
    the guarantee.
    """
    require_tenant(request)
    return Response(checklist.tick_task(_actor(request), order_id, task_id))


# ── CR-070 wave N · the part that was used — #75 ───────────────────────────
#
# ⚠ **WAVE `N` LEFT THIS ROUTE UNWRITTEN AND SAID SO**: *"wave `H`'s table
# landed mid-build and the route was not written"*. That stamp names an
# OMISSION, not a deferral and not a question — `07-endpoints.md` row 75 has
# specified it all along, `work_order_materials` exists, and `costing.py` has
# been reading the column it writes since the day it was written.
#
# ⚠ **`AnyTenantRole` FOR WAVE K's REASON, WHICH APPLIES UNCHANGED.** Row 75
# names `Work-012` first — this is a control a TECHNICIAN uses, and a field
# technician holds no staff permission at all (`OQ-WRK-1494`, closed
# 2026-09-04). What scopes the write is not the role: `set_material_used`
# resolves the order through `_order_or_404` and then the material row under
# THIS tenant and THAT order, so another utility's part is a 404 — byte
# identical to one that does not exist (HR-1).


@api_view(["PUT"])
@permission_classes([AnyTenantRole])
def work_order_material_used(request: Any, order_id: Any, material_id: Any) -> Response:
    """`PUT /work-orders/{id}/materials/{mid}/used` — used-of-planned (#75).

    ⚠ **PUT AND NOT PATCH, BECAUSE THE THING BEING REPLACED IS ONE FACT.**
    *How many of this part did this job use* has one current answer; a second
    report supersedes the first rather than adding to it, which is what makes
    the route safe to retry from a handset that lost its signal mid-write.

    The body is `{"used_qty": "1"}`. Everything the rule turns on —
    NULL is not zero, no on-hand count moves, who and when — is in
    `checklist.set_material_used`, which is the ONE writer of the column and
    is what `sync._apply_material` now calls.
    """
    require_tenant(request)
    return Response(
        checklist.set_material_used(
            _actor(request), order_id, material_id, request.data if isinstance(request.data, dict) else {}
        )
    )


# ── CR-070 wave K · what the phone sends back — #74, #76, #77, #78, #79 ────
#
# ⚠ **`AnyTenantRole` ON ALL FIVE, FOR WAVE J's REASON AND NOT A NEW ONE.**
# These are the routes a TECHNICIAN calls, and a field technician holds no staff
# permission at all (`OQ-WRK-1494`, closed 2026-09-04) — the role exists so a
# login may open the phone. A permission class naming a staff role would refuse
# the only person who ever calls them. What scopes them is not the role: every
# one resolves the order through `_order_or_404`, which reads the metering seam
# under this tenant, so another utility's job is a **404** — byte-identical to
# one that does not exist (HR-1).
#
# ⚠ **AND `Work-033` READS THESE TOO.** A supervisor opening the Checklist tab
# needs the same photograph list and the same four-hour link, so there is one
# route per fact rather than a staff copy and a phone copy of each. Two copies
# is how the two surfaces come to disagree about whether a job may close, which
# is the argument `checklist.safety_lock()` already makes for the safety rule.


@api_view(["PUT"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_reading(request: Any, order_id: Any, reading_id: Any) -> Response:
    """`PUT /work-orders/{id}/readings/{rid}` — the value AND its unit (#74).

    ⚠ **NEVER REFUSED FOR RANGE** (`BR-WRK-039`). 1,204 against a 0–999 bound
    is stored, flagged, and the job can still close. The only refusals here are
    a value that is not a number, and — hard rule 3 — a value with no unit or
    with a unit that disagrees with the one the job was raised carrying.
    """
    require_tenant(request)
    mobile.require_own_job(_actor(request), order_id)  # DEF-WRK-9593
    return Response(
        evidence.set_reading(_actor(request), order_id, reading_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_upload_ticket(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/attachments/upload-url` — where to send it (#76).

    ⚠ **NOT A PRE-SIGNED S3 URL** (`BR-WRK-047a`, decision log 2026-09-05). It
    answers with this application's own address plus the ceiling in bytes. The
    blueprint asked for a direct-to-store PUT when a photograph was 250 KB–3 MB;
    the PO's 100 KB ruling made that a bad trade, because the server would never
    see the bytes and so could not hash them, count them, check the tenant,
    audit them or enforce the ceiling.
    """
    require_tenant(request)
    mobile.require_own_job(_actor(request), order_id)  # DEF-WRK-9593
    return Response(evidence.upload_ticket(_actor(request), order_id, _payload(request)))


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_attachments(request: Any, order_id: Any) -> Response:
    """`POST` the row (#77) · `GET` this job's photographs — `Work-033`'s list.

    ⚠ **IDEMPOTENT ON THE KEY THE HANDSET MINTED** (`BR-WRK-047`). A phone that
    syncs nine photographs and loses signal halfway retries the whole batch;
    every file it already delivered comes back with its key and gets the
    existing row rather than a second one. `US-WRK-048` TC-2: re-syncing three
    jobs adds **zero** rows.

    Multipart because the bytes come through the application. `file` is the
    part; everything else is a form field.
    """
    require_tenant(request)
    if request.method == "GET":
        mobile.require_own_record(_actor(request), order_id)  # DEF-WRK-9593, FB-030 (a closed job read)
        return Response(evidence.attachments_for_order(order_id))
    payload = {
        k: v for k, v in (request.data or {}).items() if k not in ("file", "capture_token")
    }
    # BR-WRK-059 — with a capture token the photograph is the CAPTOR's (who must
    # hold and have accepted the job); without one, the session's own job.
    token = (request.data or {}).get("capture_token")
    actor = mobile.capture_actor(_actor(request), order_id, token)
    # DEF-WRK-4126 — which handset took it: what the request names, else the
    # captor's token label, else this request's own User-Agent.
    if not str(payload.get("device") or "").strip():
        payload["device"] = mobile.capture_device_label(
            token, request.META.get("HTTP_USER_AGENT", "")
        )
    return Response(
        evidence.record_attachment(actor, order_id, payload, request.FILES.get("file"))
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_attachment(request: Any, order_id: Any, attachment_id: Any) -> Response:
    """`GET /work-orders/{id}/attachments/{aid}` — a link that dies (#78).

    ⚠ **FOUR HOURS, AND IT IS A BEARER TOKEN** (PO ruling 2026-08-30). Whoever
    holds the URL reads this one photograph with no session and no further
    check until it expires. The row is resolved under this tenant FIRST, so a
    link is never minted for a photograph the caller could not have found.
    """
    require_tenant(request)
    mobile.require_own_record(_actor(request), order_id)  # DEF-WRK-9593, FB-030 (a closed job read)
    return Response(evidence.attachment_link(order_id, attachment_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_attachment_content(request: Any, order_id: Any, attachment_id: Any) -> Any:
    """`GET /work-orders/{id}/attachments/{aid}/content` — the photograph's
    bytes, same-origin (`DEF-WRK-9594`): what the office's photo viewer draws.
    `private, no-store` — a job's photograph is never kept by a shared cache."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type = evidence.attachment_bytes(order_id, attachment_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_signature(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/signature` — signed, or refused (#79).

    `BR-WRK-046`: a signature is a printed name plus an image; a refusal is a
    decline reason plus a photograph of the door hanger. **Never both** — the
    CHECK constraint says so too, and this route refuses earlier only so the
    caller gets a sentence rather than an integrity error.

    `GET` is what `Work-008`'s Customer tab reads; `null` when the crew has not
    asked yet, which is a different thing from a refusal and renders that way.
    """
    require_tenant(request)
    if request.method == "GET":
        mobile.require_own_record(_actor(request), order_id)  # DEF-WRK-9593, FB-030 (a closed job read)
        return Response(evidence.signature_for_order(order_id))
    payload = {
        k: v for k, v in (request.data or {}).items() if k not in ("file", "capture_token")
    }
    actor = mobile.capture_actor(  # BR-WRK-059, as the photograph route
        _actor(request), order_id, (request.data or {}).get("capture_token")
    )
    return Response(
        evidence.capture_signature(actor, order_id, payload, request.FILES.get("file"))
    )


# ── CR-168-BRC10 round 6 · lane SRV-5 · P6.3 — a work order and a day, printed ──


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_print(request: Any, order_id: Any) -> Any:
    """`GET /work-orders/{id}/print` — the job on one sheet, as a PDF (P6.3).

    Any role that reads the order prints it: the paper says nothing the order
    page does not. Served with `core.document_response`'s four headers —
    `inline`, so the browser's own viewer opens it and its print button prints
    it; `private, no-store`, because a customer's name and phone are on it.
    """
    from apps.work import print_docs
    from core.document_response import document_http_response

    require_tenant(request)
    payload, name = print_docs.order_pdf(order_id)
    return document_http_response(
        payload=payload, content_type="application/pdf", name=name, inline=True
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_day_pack_print(request: Any) -> Any:
    """`GET /work/print/day-pack?date=&technician=|crew=` — a technician's or a
    crew's day: a cover list, then each open job on its own sheet (ruling 3).
    `technician` / `crew` are the SLUGS the Crews screens address people by
    (B14 rule 31), never ids."""
    from apps.work import print_docs
    from core.document_response import document_http_response

    require_tenant(request)
    payload, name = print_docs.day_pack_pdf(
        on=request.query_params.get("date"),
        technician=request.query_params.get("technician") or None,
        crew=request.query_params.get("crew") or None,
    )
    return document_http_response(
        payload=payload, content_type="application/pdf", name=name, inline=True
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_order_signature_image(request: Any, order_id: Any) -> Any:
    """`GET /work-orders/{id}/signature/image` — the signature's mark, same-origin
    (`CR-168-BRC10` P1.23; `DEF-WRK-9594`'s reason). `private, no-store`."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type = evidence.signature_image_bytes(order_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def work_order_close_readiness(request: Any, order_id: Any) -> Response:
    """May this job close, and what merely flags — `Work-033`'s footer.

    ⚠ **`BR-WRK-040` SUPERSEDED 2026-10-21 (PO: *"warn"*).** Missing REQUIRED
    photographs are served under `missing_photos` and WARN; they no longer
    stop the close, so `blocking` is empty. `flagged` holds out-of-range
    values, which never stopped it. The server returns the lists apart rather
    than letting each screen decide (`evidence.close_readiness`).
    """
    require_tenant(request)
    mobile.require_own_job(_actor(request), order_id)  # DEF-WRK-9593
    return Response(evidence.close_readiness(order_id))


# ── CR-070 wave J · the phone — 07-endpoints.md §6 #88, #89, #91 ───────────
#
# ⚠ **`FieldAppRole` SINCE 2026-10-04 (`DEF-WRK-9593`) — THIS PARAGRAPH SAID
# `AnyTenantRole` AND THAT IT ADMITTED THE TECHNICIAN; IT NEVER DID**, because
# `core.permissions._role_of` answers None for any role outside `ROLES`, so the
# only person these routes are for met 403 on every one (hard-won law 1).
# The reasoning below about the PROFILE scoping them still holds.
# A field technician holds NO staff permission (`OQ-WRK-1494`, closed 2026-09-04)
# — the role exists so a login may open the phone and nothing else — so a
# permission class naming a staff role would refuse the only person these routes
# are for. What scopes them is not the ROLE, it is the PROFILE: every one asks
# `mobile.technician_of(actor)` and answers from the `technicians` row belonging
# to the caller's own login. There is no `technician_id` parameter on any of
# them, so *"show me somebody else's day"* is not a request that can be made
# (`US-WRK-041` TC-6).


@api_view(["GET"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def mobile_today(request: Any) -> Response:
    """`GET /work/mobile/today` — the caller's own day, in appointment order (#88).

    `?days=7` is the *Week* tab, the same list over a longer window
    (`US-WRK-040` TC-7). The ordering is `BR-WRK-035`'s and is not a parameter:
    priority is a pill and never a sort key.

    A login with no technician profile gets an EMPTY DAY and a reason token, at
    200 — never a 403 and never an error page (`US-WRK-040` TC-3).
    """
    require_tenant(request)
    days = request.query_params.get("days")
    try:
        window = int(days) if days else 1
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.mobile.days_not_a_number",
            br_ref="BR-WRK-035",
            params={"days": str(days)},
        ) from None
    return Response(mobile.today(_actor(request), days=window))


@api_view(["GET"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def mobile_job(request: Any, order_id: Any) -> Response:
    """`GET /work/mobile/jobs/{id}` — one job, whole, in one response (#89).

    The order's six copies, the customer's contact and the help documents as
    pre-signed links. ONE response by design: `BR-WRK-042` says the bundle is
    fetched at sync and never on tap, and a route that answered half a job would
    make that rule unimplementable however careful the client was.

    Another technician's job — or another tenant's — is a **404**, byte-identical
    to one that does not exist (HR-1).
    """
    require_tenant(request)
    return Response(mobile.bundle(_actor(request), order_id))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_job_help_content(request: Any, order_id: Any, help_id: Any) -> Any:
    """`GET /work/mobile/jobs/{id}/help/{help_id}/content` — FB-031: a help
    document's bytes for the phone to keep and open offline, with the
    technician's own credential instead of a four-hour storage link. Own job
    only, the bundle's 404 for everything else; `private, no-store`."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type, name = mobile.help_content(_actor(request), order_id, help_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    safe = "".join(ch for ch in name if ch.isprintable() and ch not in '"\\')
    response["Content-Disposition"] = f'attachment; filename="{safe}"'
    return response


def _credential_device_uid(request: Any) -> str | None:
    """`CR-187-BRC10` — the handset the native app's bearer credential is bound
    to, or None for a cookie session. Read FROM THE CREDENTIAL, never the body
    (`R127`)."""
    return getattr(getattr(request, "auth", None), "device_uid", None) or None


@api_view(["GET", "POST", "DELETE"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def mobile_devices(request: Any) -> Response:
    """`POST /work/mobile/devices` — register this handset's push token (#91).

    Idempotent on the token: re-registering the same one refreshes the row
    rather than adding a second, because a service worker re-subscribes on every
    install and browser update, and two rows for one phone would push the same
    job twice.

    The answer carries the device id and the token's last four characters. **It
    never carries the token** — see `models.TechnicianDevice`.

    ⚠ **`CR-187-BRC10`, ADDITIVE:** with a handset id — the native app's bearer
    credential, or `device_id` in the body — `POST {name, push_token?,
    platform?}` registers the HANDSET by name, push token optional
    (`mobile._register_handset`). `GET` lists the signed-in technician's own
    registrations, paged.
    """
    require_tenant(request)
    if request.method == "GET":
        technician = mobile.technician_of(_actor(request))
        if technician is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
        return prepaged(
            request,
            params,
            lambda p: mobile.devices_page(technician.id, page=p.page, per=p.per),
        )
    if request.method == "DELETE":
        # BR-WRK-059 — signing out of a shared handset: pushes stop following
        # this technician to it.
        return Response(mobile.release_device(_actor(request), request.data or {}))
    return Response(
        mobile.register_device(
            _actor(request),
            request.data or {},
            credential_device_uid=_credential_device_uid(request),
        )
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_capture_token(request: Any) -> Response:
    """`POST /work/mobile/capture-token` — `{device_label?}` → the signed token a
    handset stamps on every item captured while this technician is signed in
    (`BR-WRK-059`). Called right after sign-in.

    `CR-187-BRC10`: from the native app (bearer) the token is BOUND to this
    technician's registration of the handset the credential names, and is
    refused until that handset is registered (`POST work/mobile/devices`)."""
    require_tenant(request)
    return Response(
        mobile.issue_capture_token(
            _actor(request),
            request.data or {},
            credential_device_uid=_credential_device_uid(request),
        )
    )


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_devices(request: Any, slug: str) -> Response:
    """`GET /work/technicians/{slug}/devices` — every handset this technician
    signs in on, paged (`CR-187-BRC10`, Security §4: *"The office sees every
    device a technician uses"*). Never a push token."""
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return prepaged(
        request, params, lambda p: mobile.devices_page(row["id"], page=p.page, per=p.per)
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def technician_device_sign_out(request: Any, slug: str, device_id: Any) -> Response:
    """`POST /work/technicians/{slug}/devices/{device_id}/sign-out` — the office
    signs a handset out (`CR-187-BRC10`, `R115`). Every token of the handset is
    revoked; the phone hears `401 · params.reason = device_signed_out` on its
    next contact, drops its mirror and KEEPS its outbox. Audited."""
    require_tenant(request)
    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return Response(mobile.remote_sign_out(_actor(request), row["id"], device_id))


@api_view(["POST"])
@permission_classes([FieldAppRole])  # DEF-WRK-9593
def mobile_sync(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/sync` — one job's offline queue (#90).

    A batch of captured items **in capture order**, each with the key its
    handset minted at capture, and **per-item results, never a boolean**: a
    duplicate is the queue working correctly and a refusal is something the
    technician has to see and re-do.

    ⚠ **A SAVEPOINT PER ITEM — hard-won law 14.** `apps/work/sync.py`'s module
    docstring carries the reasoning and the reason the SQLite suite cannot prove
    it. Read it before changing anything in that file.

    ⚠ **NOTHING ACTIVATES HERE** (`BR-WRK-041`, `BR-MET-110`). The close inside
    the batch is `submit_field_result`: the order becomes *completed*,
    `accepted_by` stays NULL, and the reading the technician typed becomes a
    meter read at ACCEPTANCE and not before.
    """
    require_tenant(request)
    payload = _payload(request)
    # BR-WRK-059 — a batch whose every item carries a capture token is checked
    # ITEM BY ITEM against the captor (who may not be the courier signed in
    # now: a shared tablet). Anything else is the session's own job, as before.
    if not sync.every_item_has_a_capture_token(payload):
        mobile.require_own_job(_actor(request), order_id)  # DEF-WRK-9593
    return Response(sync.sync_batch(_actor(request), order_id, payload))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_sync_batch(request: Any) -> Response:
    """`POST /work/mobile/sync` — one batch of the day's queue ACROSS jobs
    (`CR-187-BRC10` T-30, R45). `{items: [{work_order_id, key, kind, seq,
    captured_at, payload, capture_token?, location?}, ...]}` — fifty to a
    request on the native field app.

    ADDITIVE: the per-job route below is unchanged and the web field app keeps
    calling it. Each job's items go through that route's own `sync_batch`, in
    the order they arrived, a savepoint per item (hard-won law 14); the answer
    is per item, in the order sent, each carrying its `work_order_id`. A job
    that cannot be reached refuses its own items and costs no other job.
    """
    require_tenant(request)
    return Response(sync.sync_across_jobs(_actor(request), _payload(request)))


@api_view(["PUT", "GET"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([FieldAppRole])
def mobile_photo(request: Any, photo_id: Any) -> Response:
    """`PUT /work/mobile/photos/{photo_id}` — the bytes of a photograph, to the
    LINK its data page created (`CR-168-BRC10` §F). The body is the image
    itself (`Content-Type: image/jpeg`) or a multipart `file`. Idempotent: a
    link that already has its bytes answers `duplicate: true` and adds nothing.
    A hash that does not match the declared `sha256` is refused 409
    `work.photo.hash_mismatch` and nothing is kept — send it again. `GET`
    answers the link's state (`pending` · `staged` · `landed`).

    Any field login of this tenant may carry the bytes — on a shared tablet the
    courier is whoever is signed in — because the declaration already fixed
    whose photograph it is and the hash fixes which bytes."""
    from apps.work import photo_links

    require_tenant(request)
    if request.method == "GET":
        answer = photo_links.link_answer_for(photo_id)
        if answer is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return Response(answer)
    content_type = str(request.content_type or "")
    if content_type.startswith("multipart/"):
        upload = request.FILES.get("file")
        data = upload.read() if upload is not None else b""
        content_type = getattr(upload, "content_type", "") or "image/jpeg"
    else:
        data = request.body
    return Response(photo_links.receive_bytes(_actor(request), photo_id, data, content_type))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_photo_content(request: Any, photo_id: Any) -> Any:
    """`GET /work/mobile/photos/{photo_id}/content` — FB-030: a job
    photograph's bytes for a record whose file has left the phone. Own work
    only (`mobile.photo_content`); `private, no-store` — shown, never kept."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type = mobile.photo_content(_actor(request), photo_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_changes(request: Any) -> Response:
    """`GET /work/mobile/changes?cursor=&page_size=` — this technician's change
    feed: jobs given or changed (`upsert`) and taken away (`removed`, with a
    `reason`: reassigned · unassigned · cancelled), paged by an opaque cursor
    holding a watermark per table (TECHNICIAN SYNC DESIGN (3); `CR-187-BRC10`
    T-31/T-32). `GET /work/mobile/today` hands out a cursor as well, so the
    first refresh after a day read is a delta. A cursor minted before
    `CR-187-BRC10` is still read."""
    require_tenant(request)
    return Response(
        mobile.changes(
            _actor(request),
            cursor=request.query_params.get("cursor"),
            per=request.query_params.get("page_size") or 50,
        )
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_job_readings(request: Any, order_id: Any) -> Response:
    """`GET /work/mobile/jobs/{id}/readings?page=&page_size=` — paged."""
    require_tenant(request)
    return Response(
        mobile.readings_page(
            _actor(request),
            order_id,
            page=request.query_params.get("page") or 1,
            per=request.query_params.get("page_size") or 50,
        )
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_reconciliation(request: Any) -> Response:
    """`GET /work/mobile/reconciliation` — what the server holds of this
    technician's captures, to compare with what the device captured."""
    require_tenant(request)
    return Response(mobile.reconciliation(_actor(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def photo_links_stale(request: Any) -> Response:
    """`GET /work/photo-links/stale` — links still empty after 24 hours, for
    the office; never deleted (TECHNICIAN SYNC DESIGN (4)). Paged."""
    from apps.work import photo_links

    require_tenant(request)
    return Response(
        photo_links.stale_links(
            page=request.query_params.get("page") or 1,
            per=request.query_params.get("page_size") or 50,
        )
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_accept(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/accept` — the technician takes the job they
    were given (`CR-168-BRC10` §F, the technician API). No body. Idempotent.
    Another technician's job is a 404 (HR-1); a declined or finished job is
    refused by name.

    `DEF-FLD-10579` — the phone now sends this on the technician's first
    *Start*, queued through its outbox, so it arrives with the CAPTOR's
    `capture_token` like every own-door act (`mobile.door_actor`, lane
    S-GAPS): the accept is the captor's whoever is signed in when it sends."""
    require_tenant(request)
    payload = _payload(request)
    actor = mobile.door_actor(_actor(request), payload)
    return Response(mobile.accept_job(actor, order_id))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_job_money(request: Any, order_id: Any) -> Response:
    """`GET /work/mobile/jobs/{id}/money` — the job's account money, stamped
    `as_at` (CR-187-BRC10 T-33). READ-ONLY (R16). Balance, the latest payment
    that stands and whether it is `posted` or `cleared`, each charge a step
    names (FF-61's fee), and every money step's freshness bar. A contractor's
    login gets `withheld` and no figure (R26). Another technician's job — or
    another tenant's — is a 404 (HR-1)."""
    require_tenant(request)
    return Response(work_money.money_read(_actor(request), order_id))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_task_money_proceed(request: Any, order_id: Any, task_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/tasks/{task_id}/money-proceed` —
    `{money_as_at?, proceeded_at?}` (CR-187-BRC10 T-35). Records going ahead on
    a money step, fresh or UNVERIFIED (R17). Never refused for staleness."""
    require_tenant(request)
    return Response(
        work_money.record_proceed(_actor(request), order_id, task_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_step_stopped(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/step-stopped` — `{reason, owing?, limit?,
    money_as_at?, ends_on?}` (FB-028, PO 2026-10-31). A raised job's reconnect
    or disconnect step stopped on the phone: one audit row, and the office is
    told once per job and reason (`step_gates.record_stop`). Own job only."""
    require_tenant(request)
    from apps.work import step_gates

    return Response(step_gates.record_stop(_actor(request), order_id, _payload(request)))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_decline(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/decline` — `{reason}` (required), `note?`,
    `capture_token?`. The job stays with the technician until the dispatcher
    moves it. A `capture_token` writes the decline as its captor
    (`mobile.door_actor`) — the phone queues a decline made offline
    (`DEF-FLD-10579`)."""
    require_tenant(request)
    payload = _payload(request)
    actor = mobile.door_actor(_actor(request), payload)
    return Response(mobile.decline_job(actor, order_id, mobile.without_capture_token(payload)))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_act(request: Any, order_id: Any) -> Response:
    """`POST /work/mobile/jobs/{id}/acts` — `{act: "depart" | "arrive", key?,
    capture_token?}`, the same append-only dispatch row the office writes
    (`BR-WRK-025`). A replayed `key` answers `duplicate: true`; a
    `capture_token` writes the act as its captor (`mobile.door_actor`)."""
    require_tenant(request)
    payload = _payload(request)
    actor = mobile.door_actor(_actor(request), payload)
    return Response(mobile.field_act(actor, order_id, mobile.without_capture_token(payload)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_hold(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/hold` — off the run, WITH A REASON, nothing
    deleted (`CR-168-BRC10` P0.3/P4.3). `{reason_code, expected_return_on?,
    note?}`; a hold with no reason is refused `work.hold.reason_required`."""
    require_tenant(request)
    return Response(dispatch.hold(_actor(request), order_id, _payload(request)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_resume(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/resume` — back on the run where the history says
    it was; the held time counted (`CR-168-BRC10` P4.3, P5.2)."""
    require_tenant(request)
    return Response(dispatch.resume(_actor(request), order_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def work_hold_reasons(request: Any) -> Response:
    """`GET /work/hold-reasons` — the tenant's active reasons by rank (P0.4).

    Not paged, deliberately and by the list's nature rather than its size: it
    is a tenant's own short reference list (five seeded) read whole into a
    dialog's select, the shape every lookup select in this product reads. Its
    Settings home is the generic `/lookups/work_hold_reasons`, which pages.
    """
    require_tenant(request)
    return Response({"results": dispatch.hold_reasons()})


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_settings_sla(request: Any) -> Response:
    """`GET` · `POST /work/settings/sla` `{default_target_priority_id}` — which
    priority's hours a job with no due date is measured against (PO answer (1)
    of 2026-10-04, judgment J7). Seeded: Normal, 72 h."""
    require_tenant(request)
    if request.method == "POST":
        return Response(workforce.set_default_target(_actor(request), _payload(request)))
    return Response(workforce.default_target())


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def work_settings_push(request: Any) -> Response:
    """`GET` · `POST /work/settings/push` `{push_by_priority}` — whether an
    assignment rings as its priority's push kind (CR-187-BRC10, PO answer 9 as
    corrected 2026-10-21: an OPTION, seeded OFF). Read by any role; written by
    the System Admin, the same gate as the priorities card it sits on."""
    require_tenant(request)
    if request.method == "POST":
        return Response(workforce.set_push_settings(_actor(request), _payload(request)))
    return Response(workforce.push_settings())


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_cancel(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/cancel` — danger tier; nothing deleted."""
    require_tenant(request)
    return Response(
        dispatch.set_dispatch_state(
            _actor(request), order_id, "cancelled", "work.order.cancelled"
        )
    )


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_priority(request: Any, order_id: Any) -> Response:
    """`Change priority…` on one order — and `due_at` moves with it."""
    require_tenant(request)
    return Response(dispatch.change_priority(_actor(request), order_id, _payload(request)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_orders_bulk(request: Any) -> Response:
    """`POST /work-orders/bulk` — per-order results, never a boolean."""
    require_tenant(request)
    return Response(dispatch.bulk_act(_actor(request), _payload(request)))



# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave N · `07-endpoints.md` §7 #80–#81 and §9 #92–#94
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def labour_rates(request: Any) -> Response:
    """`GET|POST /work/labour-rates` — `Work-030`, `US-WRK-051`.

    A change is a NEW DATED ROW and the old one is superseded, never updated
    (`BR-WRK-020`): `WO-4822`, closed 15 March, must still price at `48.5000`
    after the rate moves to `50.0000` on 1 April.

    ⚠ **A RATE IS PER ROLE AND NEVER PER PERSON**, so this body carries no
    `technician_id` and an unknown field is REFUSED rather than ignored. `WM-45`
    is explicit about why: *"a per-person rate is a salary, it belongs in
    payroll"*.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_labour_rate(_actor(request), _payload(request)), status=201)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return Response(_envelope(request, selectors.labour_rates_page(page=params.page, per=params.per)))


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def part_issues(request: Any) -> Response:
    """`GET|POST /work/parts/issues` — `Work-025`'s Issue log, `US-WRK-050`.

    An issue is a NEGATIVE quantity and a return a POSITIVE one; a return is a
    new row and never a deletion of the issue (TC-7), because deleting it
    would make the log say the parts were never taken.

    ⚠ **NOTHING HERE MOVES A COUNT, BECAUSE NO COUNT LAWFULLY EXISTS**
    (`OQ-WRK-1490`, closed 2026-09-04 to option (a)). The answer carries no
    `on_hand`, no `reorder_at`, no `location` and no running balance, and
    `POST` refuses those field names rather than dropping them — the same door
    `POST /work/parts` closes for the register.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_part_issue(_actor(request), _payload(request)), status=201)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = selectors.part_issues_page(
        q=params.q or None,
        part_id=request.query_params.get("part_id") or None,
        purpose=request.query_params.get("purpose") or None,
        page=params.page,
        per=params.per,
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_performance(request: Any) -> Response:
    """`GET /work/performance?period=` — `Work-027`, `US-WRK-054`.

    Four tiles and the by-job-type table, over completed orders.

    ⚠ **AND NO POSTING, NO LINK AND NO WORD INTO FINANCE.** r10 says the total
    *"feeds the O&M / labour line in Finance → Cost & Margin"*; that arrow is
    **not built** (`BR-WRK-004`, `OQ-WRK-1491` closed to option (a);
    `CR-028` D3 is the same sentence removed for asset maintenance). Payroll
    already posts the hour and posting field labour beside it would count the
    same hour twice. `US-WRK-054` TC-3 greps this payload and the rendered
    page for *Finance*, *Cost & Margin*, *O&M* and `5300`.
    """
    require_tenant(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.PERFORMANCE_SORTS,
        default_sort="volume",
    )
    result = selectors.performance(
        period=request.query_params.get("period") or None,
        page=params.page,
        per=params.per,
        sort=params.sort,
        # The table's own default: volume, most first; a clerk's `dir` wins.
        direction=(request.query_params.get("dir") or None),
    )
    body = _envelope(request, result)
    body.update(
        {
            "period": result["period"],
            "tiles": result["tiles"],
            "total": result["totals"],
            # `by_job_type` — SRV-4's one-round twin of `results` — is GONE
            # (lane PERFORMANCE, `DEF-WRK-9656`): the screen reads `results`
            # and `count` and pages through them; a second copy of the page
            # under another name is a field nothing reads.
        }
    )
    return Response(body)


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_at_risk(request: Any) -> Response:
    """`GET /work/at-risk?page=&per=` — `CR-168-BRC10` P5.3's read (lane SRV-4):
    open jobs whose promise falls within the tenant's warning window, or has
    passed; held time excluded; soonest first; paged in SQL, uncapped."""
    from apps.work import promise

    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = promise.at_risk_page(page=params.page, per=params.per)
    body = _envelope(request, result)
    body["window_hours"] = result["window_hours"]
    return Response(body)


@api_view(["PATCH"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def work_job_type(request: Any, type_id: Any) -> Response:
    """`PATCH /work/job-types/{id} {sla_hours}` — P5.10: a job type's own
    promise, overriding its priority's; blank is the priority's."""
    from apps.work import promise

    require_tenant(request)
    return Response(promise.set_job_type_sla(_actor(request), type_id, _payload(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_reports(request: Any, order_id: Any) -> Response:
    """`GET /work-orders/{id}/reports` — the versions (`BR-WRK-050`).

    A list and never a single row: a correction produces `-v2` BESIDE `-v1`
    and neither is overwritten. `Work-008` renders them.
    """
    require_tenant(request)
    return Response({"rows": selectors.work_order_reports(order_id)})


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_cost(request: Any, order_id: Any) -> Response:
    """The report's COST section — the persisted lines and their total.

    ⚠ **READ, NEVER RECOMPUTED**, so an edited part price or a superseded rate
    cannot change a report after it was signed — and **no tax row**: the total
    is `138.42`, not the wireframe's `149.84` (`BR-WRK-052`).
    """
    require_tenant(request)
    return Response(selectors.work_order_cost_lines(order_id))


# ── CR-070 wave M · the rules screen (`Work-026`, US-WRK-037) — #82–#87 ──────


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rules(request: Any) -> Response:
    """`GET|POST /work/rules` — `Work-026`, `US-WRK-037`, `BR-WRK-033`.

    The POST is the five-step builder's last step, *Review & activate*: a rule
    arrives complete or not at all, because a half-written rule that saved would
    sit on this screen looking exactly like a working one.

    ⚠ **AN UNKNOWN TRIGGER IS REFUSED HERE, NOT IGNORED AT 02:00.** See
    `rules._clean_rule` — the door is the only place a person is present to read
    the message.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(rules_svc.create_rule(_actor(request), _payload(request)), status=201)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    # `q` (P3.60's server half, lane SRV-4): the rule's name, its template's
    # name and its processes' words — the search box drawn on image 56.
    return Response(
        _envelope(
            request,
            rules_svc.rules_page(page=params.page, per=params.per, q=params.q or None),
        )
    )


@api_view(["GET", "PATCH"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule(request: Any, rule_id: Any) -> Response:
    """`GET|PATCH /work/rules/{id}` — one rule, and the builder re-opened.

    Editing a rule never rewrites what it has already done: every order it
    raised keeps its own `source`, `source_ref` and rule stamp.
    """
    require_tenant(request)
    if request.method == "PATCH":
        return Response(rules_svc.update_rule(_actor(request), rule_id, _payload(request)))
    # Image 62: the rule plus *Tonight it would raise N jobs* (read-only).
    return Response(rules_svc.rule_detail(rule_id))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_processes(request: Any) -> Response:
    """`GET /work/rules/processes` — every process a rule can be set on, ONCE
    (`CR-168-BRC10` P3.30, ruling 10): `{key, label, module, source_label,
    moment, params[]}` plus the read-only estimate limit and the Notify step's
    vocabularies. The form and the save validate against the same list."""
    require_tenant(request)
    return Response(rules_svc.processes())


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_preview(request: Any) -> Response:
    """`POST /work/rules/preview {triggers[], template_id}` — the Review's
    *Tonight it raises N jobs. Nothing is written yet.* (image 61, P3.39's
    server half). Validated exactly as a save; writes nothing."""
    require_tenant(request)
    return Response(rules_svc.preview(_payload(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_jobs(request: Any, rule_id: Any) -> Response:
    """`GET /work/rules/{id}/jobs?page=&per=` — image 63, every job the rule
    raised, newest first, paged in SQL (P3.62's server half)."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return Response(
        _envelope(request, rules_svc.rule_jobs_page(rule_id, page=params.page, per=params.per))
    )


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_audit(request: Any, rule_id: Any) -> Response:
    """`GET /work/rules/{id}/audit?page=&per=` — image 64, the rule's own
    history in words, newest first, paged in SQL."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    return Response(
        _envelope(request, rules_svc.rule_audit_page(rule_id, page=params.page, per=params.per))
    )


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_enable(request: Any, rule_id: Any) -> Response:
    """`POST /work/rules/{id}/enable` — the switch, on."""
    require_tenant(request)
    return Response(rules_svc.set_rule_enabled(_actor(request), rule_id, True))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_rule_disable(request: Any, rule_id: Any) -> Response:
    """`POST /work/rules/{id}/disable` — the switch, off.

    `BR-WRK-033`: a rule that is off raises nothing. Its memory of what it has
    already raised is KEPT, so switching it back on in March does not re-raise
    every subject it has ever seen.
    """
    require_tenant(request)
    return Response(rules_svc.set_rule_enabled(_actor(request), rule_id, False))


# ── CR-070 wave M · the Assets door (`Work-028`, US-WRK-038, BR-WRK-056) ─────
#
# ⚠ **THESE ARE ASSET-SHAPED ADDRESSES SERVED BY *WORK*, AND THAT IS THE POINT.**
# `work_orders` is not the assets module's table, so `apps/assets/**` gains no
# line of code for this feature — the same arrangement
# `GET /premises/{id}/work-orders` and `GET /accounts/{id}/work-orders` already
# use. The RAISE itself is `POST /work-orders` (#14) with `asset_id`; it needs
# no route of its own and `07-endpoints.md` §10 says so.


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def asset_work_orders(request: Any, asset_id: Any) -> Response:
    """`GET /assets/{id}/work-orders` — every job raised against this asset.

    Serves the Maintenance history's Work-order column (`BR-WRK-056`: *no column
    is added to `AssetMaintenance`*) and `Work-028`'s own list. A cross-tenant
    id yields an empty page rather than a 404 — the same sentence as *nothing
    has been raised for this asset* (hard rule 1).
    """
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = asset_door.orders_for_asset(asset_id, page=params.page, per=params.per)
    # ⚠ **SPREAD, DO NOT PASS — `_envelope` BUILDS A FRESH FOUR-KEY DICT AND
    # COPIES NOTHING ELSE (`DEF-AST-4120`).** Setting a sixth key on `result`
    # and handing `result` to `_envelope` looks exactly like it works and drops
    # the key on the floor: the index never reached the browser, so every WORK
    # ORDER cell in the asset's Maintenance history was a dash. The two other
    # views in this file that carry an extra figure (`awaiting-approval`'s
    # `oldest_waiting`, `templates`' `counts`) spell the spread out for the
    # same reason. `test_def_ast_4120_envelope_extras.py` pins all three.
    return Response(
        {
            **_envelope(request, result),
            "maintenance_index": asset_door.maintenance_order_index(asset_id),
        }
    )


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def asset_work_order_templates(request: Any, asset_id: Any) -> Response:
    """`GET /assets/{id}/work-order-templates?page=&per=` — what may be raised
    HERE: the asset's TYPE (a template naming no type is unrestricted, not
    inapplicable) and its SERVICE (`CR-168-BRC10` P2.21), paged in SQL. The
    envelope, plus `asset`. (SRV-2's one-round `rows` twin was retired by lane
    SRV-3 once lane RAISE read only `results`, 2.501.0.)"""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = raise_svc.templates_for_asset(asset_id, page=params.page, per=params.per)
    return Response({**_envelope(request, result), "asset": result["asset"]})


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_orders_bulk_raise(request: Any) -> Response:
    """`POST /work-orders/bulk-raise` — one job per ticked unit (ruling 19), or
    per ticked asset when an asset type was chosen (ruling 20); one savepoint
    per job (law 14); an answer per job; a repeated `idempotency_key` returns
    the first answer (`CR-168-BRC10` P2.12)."""
    require_tenant(request)
    return Response(raise_svc.bulk_raise(_actor(request), _payload(request)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def raise_assets(request: Any) -> Response:
    """`GET /work/raise/assets?unit_ids=&asset_type=&service=&q=&page=&per=` —
    the assets on the ticked units, searchable by asset no, serial and where
    (ruling 22), paged (`CR-168-BRC10` P2.16, image 15)."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = raise_svc.raise_assets(
        unit_ids=_id_list(request.query_params.get("unit_ids")),
        asset_type_id=request.query_params.get("asset_type") or None,
        service=request.query_params.get("service") or None,
        q=params.q or None,
        page=params.page,
        per=params.per,
    )
    return Response(_envelope(request, result))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_send_back(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/send-back {reason}` — a finished job back to the
    field, ONLY before acceptance (`CR-168-BRC10` P4.14, judgment J9); refused
    `work.order.already_accepted` once accepted. Metering's own service."""
    require_tenant(request)
    reason = (_payload(request) or {}).get("reason")
    return Response(metering_seam.send_back_field_result(_actor(request), order_id, reason))

@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def work_order_duplicate(request: Any, order_id: Any) -> Response:
    """`POST /work-orders/{id}/duplicate` — the same job raised again, unassigned
    (`DEF-WRK-9690`, beta #28). Work's own write through metering's ONE raise
    door; see `apps/work/duplicate.py` for what is and is not copied."""
    require_tenant(request)
    return Response(duplicate_svc.duplicate(_actor(request), order_id), status=201)


# CR-187-BRC10 T-40/T-41 (lane S-FIND) — the field app's search, Nearby and
# alert routes live in `field_api.py` and are spliced in FIRST by this one line.
from apps.work import field_api  # noqa: E402  (placed with the list it extends)

urlpatterns = [
    *field_api.urlpatterns,
    # ── CR-070 wave F · the workforce — 07-endpoints.md §4 #50–#60 ────────
    # ⚠ ORDER MATTERS AND IS NOT ALPHABETICAL: Django takes the FIRST pattern
    # that matches, so `certification-watch` is registered before the
    # `<str:slug>` technician route would otherwise swallow it, and the three
    # sub-paths precede the bare slug for the same reason.
    # ── CR-070 wave G · the dispatcher (07-endpoints.md §5) ────────────────
    #
    # ⚠ LITERALS BEFORE CONVERTERS, and neither could shadow the other anyway:
    # a `<uuid:…>` cannot match `bulk` or `awaiting-approval`. Ordered this way
    # so a future looser converter cannot swallow them (the DEF-520 shape).
    #
    # ⚠ `work-orders/<uuid>/field-result` and `/accept` stay METERING's and are
    # included BEFORE this module in `config/urls.py`. Neither literal collides
    # with the five below.
    path("work/kpis", work_kpis),
    path("work/areas", work_areas),
    # CR-070 wave J — the phone (#88, #89, #91). Every segment static except the
    # job's uuid, and `work/mobile/...` cannot collide with `work/technicians/
    # <str:slug>` below because that pattern is one segment deep and these are
    # two — but they are listed HERE, above it, so a reader never has to work
    # that out (the same belt-and-braces the reports routes carry).
    path("work/mobile/today", mobile_today),
    path("work/mobile/devices", mobile_devices),
    path("work/mobile/capture-token", mobile_capture_token),
    path("work/mobile/photos/<uuid:photo_id>", mobile_photo),
    # FB-030 — one segment deeper than the link above, so neither shadows the other.
    path("work/mobile/photos/<uuid:photo_id>/content", mobile_photo_content),
    path("work/mobile/changes", mobile_changes),
    # CR-187-BRC10 T-30 — the batch across jobs; a literal, two segments deep
    # like its neighbours, so it cannot meet `jobs/<uuid>/sync`.
    path("work/mobile/sync", mobile_sync_batch),
    path("work/mobile/reconciliation", mobile_reconciliation),
    path("work/mobile/jobs/<uuid:order_id>/readings", mobile_job_readings),
    path("work/photo-links/stale", photo_links_stale),
    path("work/mobile/jobs/<uuid:order_id>", mobile_job),
    # ⚠ **BEFORE the bare job route above would matter, and it does not: the
    # two patterns differ in segment COUNT, so no ordering hazard exists.
    # Listed adjacent so the pair reads as one surface (#89, #90).
    path("work/mobile/jobs/<uuid:order_id>/sync", mobile_sync),
    path(
        "work/mobile/jobs/<uuid:order_id>/help/<uuid:help_id>/content",
        mobile_job_help_content,
    ),
    # CR-168-BRC10 §F — the technician API's three acts that had no route.
    path("work/mobile/jobs/<uuid:order_id>/accept", mobile_accept),
    path("work/mobile/jobs/<uuid:order_id>/decline", mobile_decline),
    path("work/mobile/jobs/<uuid:order_id>/acts", mobile_act),
    # CR-187-BRC10 Phase 13 — the money read (T-33) and the proceed (T-35).
    path("work/mobile/jobs/<uuid:order_id>/money", mobile_job_money),
    # FB-028 — a raised job's gated step stopped; the office is told.
    path("work/mobile/jobs/<uuid:order_id>/step-stopped", mobile_step_stopped),
    path(
        "work/mobile/jobs/<uuid:order_id>/tasks/<uuid:task_id>/money-proceed",
        mobile_task_money_proceed,
    ),
    path("work-orders/bulk", work_orders_bulk),
    # ── CR-070 wave I · the map (07-endpoints.md §6 row 68) ────────────────
    # A LITERAL, placed before `<uuid:order_id>` for the reason the block above
    # states: Django takes the first pattern that matches. `map` cannot parse as
    # a uuid today, so this is defence against a looser converter later — the
    # `DEF-520` shape, exactly as `bulk` is placed.
    path("work-orders/map", work_orders_map),
    path("work-orders/by-number/<str:order_no>", work_order_by_number),
    path("work-orders/<uuid:order_id>/edit", work_order_edit_form),
    path("work-orders/<uuid:order_id>/assignments", work_order_assignments),
    path("work-orders/<uuid:order_id>/candidates", work_order_candidates),
    path("work/candidates", raise_candidates),
    path("work/raise/assets", raise_assets),
    path("work-orders/bulk-raise", work_orders_bulk_raise),
    path("work-orders/<uuid:order_id>/priority", work_order_priority),
    path("work-orders/<uuid:order_id>/audit", work_order_audit),
    # ── CR-070 wave H · #71–#73. Two-segment sub-paths, registered with the
    # rest of the `<uuid:order_id>` family and before the bare id below.
    # ── CR-070 wave K · #74, #76, #77, #78, #79. Registered with the rest of
    # the `<uuid:order_id>` family and BEFORE the bare id below, for the reason
    # the block at the top of this list states: Django takes the first pattern
    # that matches. ⚠ `attachments/upload-url` is listed before `attachments`
    # even though `<uuid:attachment_id>` cannot parse `upload-url` today —
    # defence against a looser converter later, the `DEF-520` shape, exactly as
    # `bulk` and `map` are placed.
    # ── CR-070 wave N · #75, the route wave N left unwritten. FOUR segments,
    # so nothing three-deep can shadow it; listed with the rest of the
    # `<uuid:order_id>` family and before the bare id below.
    path(
        "work-orders/<uuid:order_id>/materials/<uuid:material_id>/used",
        work_order_material_used,
    ),
    path("work-orders/<uuid:order_id>/readings/<uuid:reading_id>", work_order_reading),
    path("work-orders/<uuid:order_id>/attachments/upload-url", work_order_upload_ticket),
    path("work-orders/<uuid:order_id>/attachments/<uuid:attachment_id>", work_order_attachment),
    path(
        "work-orders/<uuid:order_id>/attachments/<uuid:attachment_id>/content",
        work_order_attachment_content,
    ),
    path("work-orders/<uuid:order_id>/attachments", work_order_attachments),
    path("work-orders/<uuid:order_id>/signature/image", work_order_signature_image),
    path("work-orders/<uuid:order_id>/signature", work_order_signature),
    path("work-orders/<uuid:order_id>/close-readiness", work_order_close_readiness),
    path("work-orders/<uuid:order_id>/checklist", work_order_checklist),
    path("work-orders/<uuid:order_id>/safety/<uuid:safety_id>/tick", work_order_safety_tick),
    path("work-orders/<uuid:order_id>/tasks/<uuid:task_id>/tick", work_order_task_tick),
    path("work-orders/<uuid:order_id>/print", work_order_print),
    path("work/print/day-pack", work_day_pack_print),
    path("work-orders/<uuid:order_id>/hold", work_order_hold),
    path("work-orders/<uuid:order_id>/resume", work_order_resume),
    path("work-orders/<uuid:order_id>/send-back", work_order_send_back),
    path("work-orders/<uuid:order_id>/duplicate", work_order_duplicate),
    path("work-orders/<uuid:order_id>/cancel", work_order_cancel),
    path("work-orders/<uuid:order_id>", work_order_detail),
    path("work/hold-reasons", work_hold_reasons),
    path("work/settings/sla", work_settings_sla),
    path("work/settings/push", work_settings_push),
    path("work/settings/visit-messages", work_settings_visit_messages),
    path("work/certification-watch", certification_watch),
    # `BR-AST-533` — a two-segment literal, sibling of `work/crews`. Nothing
    # can swallow it: `work/crews/<uuid:…>` is three segments and needs a uuid.
    path("work/crew-directory", crew_directory),
    path("work/crews/<uuid:crew_id>/skills", crew_skills),
    path("work/crews/<uuid:crew_id>/members", crew_members),
    path("work/crews/<uuid:crew_id>", crew),
    path("work/crews", crews),
    path("work/technicians/<str:slug>/skills", technician_skills),
    path("work/technicians/<str:slug>/certifications", technician_certifications),
    path(
        "work/technicians/<str:slug>/certifications/<uuid:type_id>/proof",
        technician_certificate_proof,
    ),
    path(
        "work/technicians/<str:slug>/certifications/<uuid:type_id>/proof/content",
        technician_certificate_proof_content,
    ),
    path("work/technicians/<str:slug>/unavailable", technician_unavailable),
    # `CR-187-BRC10` — the office's view of a technician's handsets.
    path("work/technicians/<str:slug>/devices", technician_devices),
    path(
        "work/technicians/<str:slug>/devices/<uuid:device_id>/sign-out",
        technician_device_sign_out,
    ),
    path("work/technicians/<str:slug>/jobs", technician_jobs),
    path("work/technicians/<str:slug>/performance", technician_performance),
    path("work/technicians/<str:slug>", technician),
    path("work/technicians", technicians),
    # ⚠ THE LITERAL BEFORE THE BARE NAME, and here it MATTERS rather than being
    # a habit: `work-orders/awaiting-approval` is two segments and so is
    # `work-orders` — different paths, so no shadowing — but metering also owns
    # `work-orders/<uuid>/field-result` and `/accept` (three segments). No
    # pattern in config/urls.py is a prefix of either of these, and a `<uuid:…>`
    # converter cannot match the literal `awaiting-approval`, so nothing can
    # swallow it. Registered first anyway, so the ordering stays true the day
    # somebody adds a looser converter.
    path("work-orders/awaiting-approval", work_orders_awaiting_approval),
    path("work-orders", work_orders),
    # `work/parts` — a two-segment prefix nothing else in config/urls.py
    # claims. The literal list before the `<str:part_id>` detail, so a future
    # looser converter cannot swallow it (the DEF-520 route-ordering shape).
    # ── CR-070 wave D · the template bundle ───────────────────────────────
    #
    # ⚠ **EVERY LITERAL BEFORE EVERY CONVERTER**, and here it is load-bearing
    # rather than habitual: `work/template-packs` is two segments and so is
    # `work/templates`; `work/templates/<uuid>/publish` is four and so is
    # `work/templates/<uuid>/<collection>`, which WOULD swallow it — a
    # `<str:collection>` converter matches the literal `publish` happily. The
    # five named four-segment routes are therefore declared FIRST and the
    # collection route last. This is the `DEF-520` shape and it is the only
    # ordering in this file that a reorder would actually break.
    path("work/template-packs", template_packs),
    path("work/templates", templates),
    path("work/templates/<uuid:template_id>/publish", template_publish),
    path("work/templates/<uuid:template_id>/duplicate", template_duplicate),
    path("work/templates/<uuid:template_id>/deactivate", template_deactivate),
    path("work/templates/<uuid:template_id>/reactivate", template_reactivate),
    path("work/templates/<uuid:template_id>/versions", template_versions),
    path("work/templates/<uuid:template_id>/usage", template_usage),
    path("work/templates/<uuid:template_id>/audit", template_audit),
    path("work/templates/<uuid:template_id>/help/upload-url", template_help_upload_url),
    path("work/templates/<uuid:template_id>/help/documents", template_help_documents),
    path(
        "work/templates/<uuid:template_id>/help/documents/<uuid:document_id>/content",
        template_help_content,
    ),
    path("work/templates/<uuid:template_id>/<str:collection>", template_collection),
    path("work/templates/<uuid:template_id>", template),
    path("work/parts", parts),
    # ⚠ BEFORE `work/parts/<str:part_id>`, or Django matches the converter
    # first and "issues" arrives as a part id — a 404 that looks like a
    # missing row rather than a routing mistake.
    path("work/parts/issues", part_issues),
    path("work/parts/<str:part_id>", part),
    # `work/rules` — the literal before the uuid route, so `enable`/`disable`
    # (three segments) cannot be swallowed by `<uuid:rule_id>` (two). The same
    # ordering `work/templates` above uses, for the same reason.
    # `assets/{id}/…` — asset-shaped addresses served by WORK, beside the
    # premises and account pairs above. The literal `work-order-templates`
    # before `work-orders` is not needed (different final segments), but both
    # sit above nothing looser, so ordering is stable.
    path("assets/<uuid:asset_id>/work-orders", asset_work_orders),
    path("assets/<uuid:asset_id>/work-order-templates", asset_work_order_templates),
    path("work/rules", work_rules),
    path("work/rules/processes", work_rule_processes),
    path("work/rules/preview", work_rule_preview),
    path("work/rules/<uuid:rule_id>/jobs", work_rule_jobs),
    path("work/rules/<uuid:rule_id>/audit", work_rule_audit),
    path("work/rules/<uuid:rule_id>/enable", work_rule_enable),
    path("work/rules/<uuid:rule_id>/disable", work_rule_disable),
    path("work/rules/<uuid:rule_id>", work_rule),
    path("work/labour-rates", labour_rates),
    path("work/performance", work_performance),
    path("work/at-risk", work_at_risk),
    path("work/job-types/<uuid:type_id>", work_job_type),
    path("work-orders/<uuid:order_id>/reports", work_order_reports),
    path("work-orders/<uuid:order_id>/cost", work_order_cost),
    # ── CR-070 wave E · what New Connect step 6 proposes ──────────────────
    #
    # ⚠ **METERING'S NOUN, WORK'S CONTENT — AND NOTHING SHADOWS IT, CHECKED
    # RATHER THAN ASSUMED.** `apps.metering.api` is included BEFORE this module
    # in `config/urls.py` and claims `connections` (one segment, exact) and
    # `connections/<uuid:connection_id>/…` — a `<uuid:…>` converter cannot
    # match the literal `proposed-work-orders`, so this two-segment path is
    # reachable. It is registered here rather than in metering because the rows
    # it answers with are `work_order_templates` read through Work's own seam,
    # which is the wave O shape (`premises/<id>/work-orders`).
    path("connections/proposed-work-orders", proposed_work_orders),
    # ── CR-070 wave P · what one of the five flows could raise ────────────
    #
    # ⚠ **FOUR SEGMENTS, AND `<str:flow_id>` RATHER THAN `<uuid:…>` ON PURPOSE.**
    # Four of the five ids are uuids and the fifth — a move, asked about from a
    # wizard whose move record does not exist yet — is an ACCOUNT id, also a
    # uuid. The converter is `str` because a malformed id must reach
    # `from_flows._resolve` and come back as a 404-shaped refusal (HR-1:
    # existence must not leak), not as a route miss that renders a different
    # page. Nothing in `config/urls.py` claims `work/flows`.
    path("work/raise-options", flow_raise_options),  # DEF-CUS-6363
    path("work/flows/<str:flow_kind>/<str:flow_id>/proposed", flow_proposed_work_orders),
    # ── the Reads→Work door, 2026-09-14 · the SIXTH flow's raise ──────────
    #
    # ⚠ **A FIXED SEGMENT, NOT `<str:flow_kind>`, AND THE NARROWNESS IS THE
    # POINT.** `/proposed` above is generic because a READ of what a flow could
    # raise is harmless for any of the six. A generic RAISE would not be: the
    # other five raise inside their own flow's commit, and a second HTTP door
    # onto the same service would let a move-out's jobs be raised twice — once
    # by the wizard and once by anybody who can spell the URL. So this route
    # names `meter-read` in the path and there is no way to point it elsewhere.
    #
    # It takes the meters in the BODY rather than one in the path because the
    # act is *send someone out to these five*: five paths would be five audit
    # rows for one decision and five chances for a clerk's tick list to be
    # half-applied.
    path("work/flows/meter-read/raise", raise_meter_read_field_work),
    # ── CR-070 wave O · the two hosts, and the door a bookmark comes through ──
    #
    # ⚠ **THESE FIVE HANG OFF ANOTHER MODULE'S NOUN, AND THAT IS THE POINT.**
    # `premises` is metering's and `accounts` is customers'; the WORK at one of
    # them is Work's, so Work serves it, exactly as the PO's ruling asks —
    # *"they are part of product and interact with existing functionalities and
    # pull push data amongst existing modules endpoints, databases"*. Not one of
    # them writes: `apps/work` reads the six neighbours through one seam file
    # each and `G78` fails a foreign write from its first commit.
    #
    # ⚠ **NO PATTERN HERE IS SHADOWED, CHECKED RATHER THAN ASSUMED.** metering
    # is included BEFORE work in `config/urls.py` and claims `premises`,
    # `premises/<uuid>`, `premises/<uuid>/submeter-reconciliation` and
    # `premises/<uuid>/deactivate` — no `work-orders` and no `build`. customers
    # is included AFTER work and claims `accounts/<uuid>/…` for plan-changes,
    # payment-plans and the rest — again neither of these two words. The
    # three-segment literal is declared here in full so a future looser
    # converter cannot swallow it (the DEF-520 route-ordering shape).
    path("premises/<uuid:premises_id>/work-orders", premises_work_orders),
    path("premises/<uuid:premises_id>/build", premises_build),
    path("accounts/<uuid:account_id>/work-orders", account_work_orders),
    path("accounts/<uuid:account_id>/build", account_build),
    # `work/builds/<id>/home` sits under Work's own two-segment prefix rather
    # than under `connections/<id>/…`, which is metering's path space. The
    # redirect is a Work behaviour — it exists because Work re-hosted the
    # screen — and putting it in metering's namespace would make the retired
    # destination look like it still had one.
    path("work/builds/<uuid:connection_id>/home", build_home),
]

# CR-187-BRC10 lane S-ORDER — the field app's order acts and their office
# queues live in `field_orders_api.py` (one line here, so a merge touches one line).
from apps.work import field_orders_api as _field_api  # noqa: E402

urlpatterns += _field_api.urlpatterns

# CR-187-BRC10 lane FINDINGS — route findings (`BR-WRK-067`), the same one line.
from apps.work import route_findings_api as _findings_api  # noqa: E402

urlpatterns += _findings_api.urlpatterns

# CR-193-BRC10 (MQ-040 step 1) — working days, the phone's week, End shift and
# Submit the day live in `shifts_api.py`, the same one line.
from apps.work import shifts_api as _shifts_api  # noqa: E402

urlpatterns += _shifts_api.urlpatterns

# CR-194-BRC10 (PO 2026-10-26, "store on both") — the office's refused field
# work lives in `refused_items_api.py`, the same one line.
from apps.work import refused_items_api as _refused_api  # noqa: E402

urlpatterns += _refused_api.urlpatterns

# `CR-187-BRC10` — the native field app's bearer access token is accepted on
# EVERY `work/mobile/*` route, in front of the cookie, by this ONE line: a
# route another lane adds under that prefix tomorrow is covered without anyone
# remembering to decorate it, and `tests/test_cr187_native_auth.py` asserts the
# exact set. The cookie is unchanged everywhere (`apps/identity/native_auth.py`).
from apps.identity.native_auth import accept_native_bearer  # noqa: E402

accept_native_bearer(urlpatterns, "work/mobile/")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-004@87b94265 (EP-WRK-01) · 07-endpoints.md §1 · A11 list envelope
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D✔ E✔(OrdersPage.tsx consumes this) F✔ G✔ H=n/a(read route; no 🔒 path)
# gates: pytest tests/test_us_wrk_004_orders_list.py · pytest tests/test_us_wrk_002_one_destination.py (wave O) · G9 error envelope (refusals come from the shared handler)
# ⚠ AMENDED 2026-09-04 (DEF-GOV-3760): this line read "openapi export re-run (one new path)" and the export had NOT been run — the committed snapshot did not carry /work-orders, and test_be11_tc05 was red over it for four waves. Hard-won law 1: a comment claiming a guarantee is not the guarantee. Wave O re-ran it (467 → 513 paths) and this line now claims only what was done.
# exceptions: the raise and the approval-queue routes are wave B's (07-endpoints.md §1 rows 14–15) — stated here so their absence is a plan and not a gap
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
