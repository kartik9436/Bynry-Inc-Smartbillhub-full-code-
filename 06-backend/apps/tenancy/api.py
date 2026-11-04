# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001/002/004 (POST /tenants — S114 commit, atomic + idempotent) ·
#           US-TEN-003 (GET/POST /tenants/checklist* — S62) · US-TEN-005 (S8
#           /settings/company) · US-TEN-006 (/settings/regional) · US-TEN-007/008
#           (/settings/services*) · US-TEN-009/010/011 (/lookups/*) · US-TEN-012
#           (/settings/number-series*)   Screens: S1, S8, S62, S110–S114
#           AMENDED 2026-08-09 (settings rule-page + logo gap lane): US-TEN-005
#           (POST /settings/company/logo) · US-TEN-009 (the five S63–S71 rule
#           pages, EP-TEN-07 scope addendum) · US-MET-011 (S64 field set)
#           Screens += S64, S66, S69, S70, S71
#           AMENDED 2026-08-10 (job-runner lane): GET /jobs/{id} — the shared
#           BE-07 poll resource (11b §2.17, no story of its own; the `jobs`
#           table is hosted by this module), consumed by every 202 screen
#           AMENDED 2026-08-10 (list-export lane): US-SHL-008 — POST /exports,
#           the table-level export of 11b §2.11, serving the nine registered
#           lists (S14 · S15 · S26 · S27 · S49 · S9 plans/charges/taxes/history)
#           Screens += S14, S15, S26, S27, S49, S9
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014/015/016/017 (GET|POST /settings/custom-fields · PATCH /…/{id} ·
#           PUT /…/{id}/placement · GET /custom-fields). NO DELETE ROUTE EXISTS (BR-TEN-050). A11 carries no row for these paths yet — the addendum is REPORTED as owed
# Rules:    BR-TEN-003 (tenant from subdomain, never client input) · BR-TEN-010/011
#           (idempotent commit, live check advisory) · BR-TEN-016 (audit via
#           services) · BR-TEN-024 (atomic per-tab save) · BR-TEN-039 (holidays) ·
#           BR-TEN-019 (logo allowlist/cap/sanitizer) · BR-TEN-043 (config
#           changes are event-time forward) · BR-MET-020 (thresholds are config) ·
#           A4 (Settings = System Admin Full / Executive View; server-enforced
#           per BR-IDN-009/G13 + the service-layer guard, BR-SHL-025) ·
#           BR-SHL-016 + BR-SHL-029 (POST /exports: server-side under the
#           caller's tenant context, >50,000 rows → 422 BIZ-CAP, money-table
#           exports write audit_log) · BR-SHL-011 (the export body mirrors the
#           list's own q/sort/dir/f.‹name› state)
# Tests:    06-backend/tests/test_us_ten_*.py (API halves per story file) ·
#           06-backend/tests/test_be_list_export.py (POST /exports, per-TC)
# Impacts:  A11 Addendum r2 + 11b §2.1/§2.3/§2.11 inventory (typed client FI-01) ·
#           config/urls.py inclusion (wiring lane — urlpatterns exported here) ·
#           the nine registered lists' Download buttons (07-frontend)
# ───────────────────────────────────────────────────────
"""tenancy API endpoints per A11 (as amended by 11b §2.1/§2.3, PO-ratified).

THIN by law (B8/LAW 0): every write goes through services (sole writer), every
read through selectors; no ORM here. Refusals are catalog exceptions rendered
by the BE-02 handler; role gates are the BE-04 permission classes AND the
service-layer @require_role guards (defense in depth, BR-SHL-025).

`urlpatterns` is exported for inclusion by config/urls.py — the include itself
is the platform wiring lane's one-liner (config/ is outside this packet's
territory; recorded in the build report).
"""

import uuid
from types import SimpleNamespace
from typing import Any

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.identity.auth import (
    SESSION_COOKIE,
    IdentitySessionAuthentication,
    client_ip,
    session_cookie_max_age,
)
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import exports
from apps.tenancy import logo as logo_law
from apps.tenancy import sample_data
from apps.tenancy import selectors, services
from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import (
    AdminOrExecutive,
    AnyTenantRole,
    NewConnectionLookupRead,  # DEF-CUS-9048 — PO 2026-10-02, clerk reads two lists
    SettingsReadAnyWriteSystemAdmin,  # DEF-196 — read open, write admin-only
    ShellDisplayRead,  # DEF-SHL-4272 — the shell's boot read, every role
    SystemAdminOnly,
)
from core.tenancy import require_tenant


class PublicOnboardingThrottle(AnonRateThrottle):
    """11b G12: tighter throttles on the public surface (429 + Retry-After
    via BE-02). Rate is deliberately generous for the W0 cut."""

    rate = "60/min"


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
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    return data


def _http_series_refusal(status: int, message_key: str, **params: Any) -> Response:
    """The G1 envelope for a B12 r1 HTTP-series row that has NO B12 §3 catalog
    code — 413 upload cap and 415 unsupported type, rendered exactly the way
    core.errors renders 404/405/415/429 (`code: null`, never an invented code).

    ⚠ **THE BODY IS `core.errors.http_series_refusal_body` SINCE 2026-09-12, AND
    THIS FUNCTION IS NOW THE STATUS AND THE `br_ref`.** It used to compose the
    dict here and said why: *"Built here because core.errors' handler has no 413
    branch and core/ is outside this lane's territory: REPORTED as a kernel
    follow-up."* `CR-094-BRC01` wave I is the second uploader — account
    documents — and a second hand-composed copy of a refusal envelope is two
    places it can drift from the one every other status renders.
    """
    return Response(
        errors.http_series_refusal_body(message_key, br_ref="BR-TEN-019", **params),
        status=status,
    )


def _maybe_304(request: Any, payload: Any) -> Response | None:
    """ETag/304 for cacheable public/lookup GETs (11b G6, B12 r1 3xx row)."""
    tag = selectors.etag_for(payload)
    if request.headers.get("If-None-Match") == tag:
        response = Response(status=304)
    else:
        response = None
    if response is not None:
        response["ETag"] = tag
    return response


# ── public & onboarding (11b §2.1 — S1, S110, S114) ─────────────────────────
# `authentication_classes([])` on all three, and on POST /tenants below, is
# LOAD-BEARING since 2026-08-10: IdentitySessionAuthentication became the DRF
# default (config/settings/base.py, 09-infra/02 §10.14), so a view that stays
# silent now reads the cookie. These four must not. They are the surface a
# visitor reaches with NO tenant and, on the signup path, often with a STALE
# cookie from some other utility — and the platform paths carry no `/{tenant}/`
# segment, so the authenticator would take the session's own tenant as the
# scope (core.tenancy.adopt_session_tenant). On POST /tenants that would enter
# the wrong tenant's context for a transaction that is creating a new one, and
# a revoked or expired cookie would 401 a signup that needs no session at all.
# Empty list = "this route is public", stated, not inherited.
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle])
def subdomain_check(request: Any) -> Response:
    """S110 live availability — ADVISORY; commit re-checks (BR-TEN-011)."""
    return Response(selectors.subdomain_availability(request.query_params.get("subdomain")))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle])
def pricing_plans(request: Any) -> Response:
    plans = selectors.pricing_plans()
    not_modified = _maybe_304(request, plans)
    if not_modified is not None:
        return not_modified
    response = Response(plans)
    response["ETag"] = selectors.etag_for(plans)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle])
def tenants(request: Any) -> Response:
    """S114 "Create utility & go live": one transactional commit, idempotent on
    the subdomain natural key (BR-TEN-010) — replay returns 200 + the existing
    tenant; first commit returns 201 + Location.

    **The owner is signed in at commit** (PO ruling 2026-08-10, supersedes
    BR-TEN-045). Signup and the new tenant now share one origin, so the session
    opened inside the provisioning transaction rides back as the ordinary
    httpOnly `sbh_session` cookie and the SPA can go straight to
    `/{subdomain}` → S62. `signed_in` says whether it did; the session id
    itself is never in the body (it is the credential — cookie only).

    A REPLAY is answered 200 with `signed_in: false`: BR-TEN-010 matches on
    subdomain + owner email and checks no password, so that path may not mint a
    login (see services.provision_tenant).
    """
    result = services.provision_tenant(
        request.data,
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    session_id = result.pop("owner_session_id", None)
    body = {**result, "signed_in": session_id is not None}
    response = Response(body, status=201 if result["created"] else 200)
    if result["created"]:
        response["Location"] = f"/api/tenants/{result['id']}"
    if session_id is not None:
        # Same cookie POST /api/{tenant}/auth/session sets — one session
        # mechanism, one place to change it (apps/identity/auth.py).
        # CR-144-BRC07 (X3) — `Secure`, so the session cookie never travels
        # over plain HTTP. ⚠ **ONE SETTING, NOT A LITERAL**: `AUTH_COOKIE_SECURE`
        # defaults True (hard-won law 3) and is turned OFF by
        # `SBH_AUTH_COOKIE_SECURE=false` for local HTTP development.
        # ⚠ **THE NAME `sbh_session` DOES NOT MOVE** — renaming a live session
        # cookie signs every signed-in user out at once.
        # ⚠ **`CR-145-BRC08` — `max_age`, the same one function all three
        # cookie sites use (`apps/identity/auth.session_cookie_max_age`).**
        # Until 2026-09-28 none of the three passed an expiry at all, so
        # *"Keep me signed in"* died when the browser closed.
        #
        # **This one is always `None` and that is CORRECT, not an oversight.**
        # The signup form has no *"Keep me signed in"* tick box — the session
        # `start_owner_session` opens carries `persistent=False` and says so in
        # its own docstring — so the owner's first cookie is a browser-session
        # cookie exactly as it has always been. It goes through the shared
        # helper anyway, because the day that form grows a tick box the answer
        # should already be right here rather than be a fourth thing to
        # remember.
        #
        # ⚠ **THE POLICY IS NOT READ HERE, AND THE EMPTY DICT IS THE REASON
        # STATED RATHER THAN HIDDEN.** `persistent=False` answers the question
        # before any setting is consulted — the helper returns `None` on its
        # first line — so reading `security_policies` would be a query whose
        # result cannot change the answer, on the one path in this product
        # where the tenant was created microseconds ago and its RLS context is
        # the provisioning transaction's. If this form ever grows a tick box,
        # the empty dict becomes a `KeyError` on the very first request rather
        # than a quietly wrong expiry, which is the failure worth having.
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=session_cookie_max_age({}, persistent=False),
            httponly=True,
            samesite="Lax",
            secure=settings.AUTH_COOKIE_SECURE,
        )
    return response


# ── S62 checklist (11b §2.2) ────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def checklist(request: Any) -> Response:
    require_tenant(request)
    return Response(selectors.checklist())


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def checklist_item_dismiss(request: Any, item: str) -> Response:
    require_tenant(request)
    return Response(services.mark_checklist_item(_actor(request), item))


# ── S8 Settings → Company (11b §2.3) ────────────────────────────────────────
@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def company_settings(request: Any) -> Response:
    require_tenant(request)
    if request.method == "PUT":
        return Response(services.save_company_profile(_actor(request), _payload(request)))
    return Response(selectors.company_profile())


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
@parser_classes([MultiPartParser, FormParser])
def company_logo(request: Any) -> Response:
    """S8 Company → Brand logo upload (BR-TEN-019 as SUPERSEDED 2026-10-27,
    `DEF-TEN-10618`): PNG or JPG only → an SVG is 415
    `settings.company.logo_svg_not_accepted`, anything else outside the
    allowlist 415, ≤2 MB → 413 over the cap (B12 r1 upload rows), and the bytes
    must BE what the type says (magic bytes, 422 on a mismatch). Returns the
    stored REFERENCE; the bytes never come back out of this endpoint.

    The two guards here are transport-level (they render B12 r1 rows that have
    no catalog code); the identical law runs again inside the service, so a
    job or shell caller cannot bypass it — see services.save_company_logo.

    No DELETE: neither US-TEN-005 nor the prototype drop-zone anchors logo
    removal, so no removal endpoint is invented (reported).
    """
    require_tenant(request)
    upload = request.FILES.get("file") or request.FILES.get("logo")
    if upload is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="settings.company.logo_missing"
        )
    if logo_law.is_svg(getattr(upload, "content_type", None), getattr(upload, "name", None)):
        # DEF-TEN-10618 (PO 2026-10-27, "Allow PNG, JPG"): an SVG gets its OWN
        # sentence, so the person knows what to do instead.
        return _http_series_refusal(
            415,
            logo_law.SVG_NOT_ACCEPTED_KEY,
            allowed=sorted(logo_law.LOGO_CONTENT_TYPES),
            declared=getattr(upload, "content_type", None),
        )
    resolved = logo_law.normalized_content_type(
        getattr(upload, "content_type", None), getattr(upload, "name", None)
    )
    if resolved is None:  # B12 r1: 415 upload type not allowlisted
        return _http_series_refusal(
            415,
            "settings.company.logo_type_not_allowed",
            allowed=sorted(logo_law.LOGO_CONTENT_TYPES),
            declared=getattr(upload, "content_type", None),
        )
    if getattr(upload, "size", 0) > logo_law.LOGO_MAX_BYTES:  # B12 r1: 413 size cap
        return _http_series_refusal(
            413,
            "settings.company.logo_too_large",
            max_bytes=logo_law.LOGO_MAX_BYTES,
            size=upload.size,
        )
    return Response(
        services.save_company_logo(
            _actor(request),
            upload.read(),
            content_type=resolved,
            filename=getattr(upload, "name", None),
        ),
        status=201,
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def company_logo_file(request: Any) -> Any:
    """`GET /settings/company/logo/file` — THE one address every drawing of the
    logo uses: the app header, Settings › Company › Brand, the Bill layout,
    Customer portal settings and the customer portal itself.

    ⚠ **THE BYTES COME FROM THE COMMON DOCUMENT STORE SINCE 2026-10-05
    (`CR-172-BRC10`)** — `selectors.logo_bytes()` → `document_store.fetch()`,
    which re-hashes what S3 returns. Until then they were read from
    `tenants.logo_bytes`, a column a lane chose because no store existed.

    ⚠ **READABLE WITHOUT SIGNING IN (`CR-172-BRC10`, judgment (2) in the
    decision log of 2026-10-05).** The logo is printed on every bill and drawn
    on the PUBLIC portal, so a sign-in on this read protected nothing and left
    the portal unable to draw it. `authentication_classes([])` beside
    `AllowAny` for the reason `subdomain_check` gives: a public read must not
    be refused because the browser also carries some other session.
    The UPLOAD (`company_logo` above) is unchanged: System Admin only, and the
    sanitiser is still its only way in.

    **TENANT SCOPING (CLAUDE.md hard rule 1).** `require_tenant` first — the
    tenant is the one the ADDRESS names, set by the middleware — then
    `selectors.logo_bytes()`, which accepts no id and no tenant from the caller.
    There is no parameter that reaches another utility's logo; `?v=` is the
    browser's cache key and is never read.

    **CACHING.** The ETag is the logo's REFERENCE (the stored document's id), so
    a replacement is a new ETag; the front end also puts the reference in the
    address (`?v=`), so a replaced logo is a different URL and is fetched at
    once. A matching `If-None-Match` is answered 304 from the row alone, with no
    trip to the store. `Cache-Control: private` — never a shared cache entry.

    A store that cannot return the logo answers 503
    (`settings.company.logo_storage_unavailable`); the front end draws the
    generated mark in its place rather than a broken image.
    """
    require_tenant(request)
    current = selectors.logo_current_reference()
    if current is None:
        raise errors.NotFoundError()
    etag = f'"{current}"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
    else:
        from apps.tenancy import document_storage, document_store

        try:
            stored = selectors.logo_bytes()
        except (document_store.DocumentStoreError, document_storage.DocumentStorageError) as exc:
            raise errors.SysError(
                errors.SYS_PROVIDER,
                message_key="settings.company.logo_storage_unavailable",
                params={"reason": type(exc).__name__},
            ) from exc
        if stored is None:
            # Absent, not empty. A 200 with zero bytes would render as a broken
            # image and read as "your upload is corrupt".
            raise errors.NotFoundError()
        content, content_type, reference = stored
        etag = f'"{reference}"'
        response = HttpResponse(content, content_type=content_type)
        response["Content-Length"] = str(len(content))
        # `inline` so the header can draw it; a filename so a deliberate save
        # does not produce a bare uuid.
        response["Content-Disposition"] = 'inline; filename="logo"'
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def regional_settings(request: Any) -> Response:
    require_tenant(request)
    if request.method == "PUT":
        return Response(services.save_regional_settings(_actor(request), _payload(request)))
    return Response(selectors.regional_settings())


# ── The shell's boot read (DEF-SHL-4272 · BR-SHL-252) ───────────────────────
@api_view(["GET"])
@permission_classes([ShellDisplayRead])
def shell_display(request: Any) -> Response:
    """`GET /shell/display` — the branding and the formats every screen draws.

    ⚠ **A BILLING CLERK COULD NOT USE THIS PRODUCT AT ALL BETWEEN 2026-08-21 AND
    2026-09-06 AND THIS ROUTE IS THE FIX (`DEF-SHL-4272`).** The app shell boots
    by reading the tenant's branding and its date/number formats; it took both
    from `GET /settings/company` and `GET /settings/regional`, which are
    `SettingsReadAnyWriteSystemAdmin` — `{system_admin, executive}`, because
    A4's `settings_lookups` row gives a Billing Clerk **no cell**. A clerk
    signed in successfully, reached `/dashboard`, and every screen in the
    product rendered the shell's failure state with a Retry that could not
    succeed.

    **WHY A NEW ROUTE RATHER THAN WIDENING THE GATE ON THE TWO EXISTING ONES.**
    Two reasons, and the second is the one that decided it.

    *One:* widening `SettingsReadAnyWriteSystemAdmin` re-opens `DEF-196`, whose
    docstring records the first cut of that fix doing exactly this, passing
    every test written for it, and being caught by `US-TEN-009 TC-5`. A4 is
    signed; no cell means no access.

    *Two, and this stands on its own even if A4 said otherwise:*
    `GET /settings/regional` also serves `accounting_method`, `close_cadence`,
    `close_day` and `lock_closed_periods`. Those are a utility's finance policy.
    Nobody should receive a close-period lock in order to render `03/04/2026`.

    **AND IT CARRIES THE CURRENT ACCOUNTING PERIOD (`DEF-SHL-4283`,
    2026-09-06).** `{fy_label, period, start, end, status}` — the label a screen
    puts on a figure and the window it runs a report over, computed by
    `selectors.current_period()` and never stored (`BR-TEN-022`). It was left
    off the first cut of this route, and two screens A4 gives a Billing Clerk
    broke on the omission: `Reports → By premises` never ran its report, and
    `Payments → Refunds` headed itself *"Set the fiscal year start to see the
    current period."* at a tenant whose fiscal year start is set. The card's
    sixth field, `close_by`, stays on `GET /settings/regional` — it is
    `close_day` in another shape, a finance-close deadline rather than a
    drawing fact.

    **ONE ROUTE AND NOT TWO** (branding and formats could have been separate).
    The shell cannot draw a screen with half of this, so splitting it would give
    one indivisible fact two loading states, two failure states and two Retry
    buttons — and a boot read failing with a dead Retry is the defect being
    fixed. Halving the number of things that can fail at boot is part of the
    fix, not a convenience.

    **READ ONLY, FOR EVERY ROLE INCLUDING THE SYSTEM ADMIN.** `ShellDisplayRead`
    refuses every mutating verb, so this cannot become a second write path
    around `PUT /settings/regional`'s validation and audit trail. Settings is
    still the one door in.

    Tenant-scoped like every other read here: `require_tenant` first, and
    `selectors.shell_display()` takes no tenant argument — it resolves the row
    from `app.tenant_id`, so there is no id a caller could supply to reach
    another utility's branding.
    """
    require_tenant(request)
    return Response(selectors.shell_display())


# ── S8 Settings → Services & UoM ────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # US-TEN-007 TC-4: clerks read-only; writes below
def services_settings(request: Any) -> Response:
    require_tenant(request)
    return Response(selectors.services_overview())


@api_view(["PUT"])
@permission_classes([SystemAdminOnly])
def service_update(request: Any, service: str) -> Response:
    require_tenant(request)
    return Response(services.update_tenant_service(_actor(request), service, _payload(request)))



# ── S107 Settings → Billing plan (11b §2.16 · DEF-1092) ─────────────────────
@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups
def subscription(request: Any) -> Response:
    """What this tenant buys from Bynry — the read S107 renders.

    **THE PATH IS 11b §2.16's OWN**, `GET /subscription`, ratified 2026-08-09
    and unserved until today. It is not `settings/subscription`: the audit row
    names this resource without the Settings prefix, and a screen living on a
    Settings tab does not make its resource a setting.

    **GET ONLY, and that is a decision rather than a stage.** Nothing on this
    surface writes. A utility cannot change what it pays Bynry from inside its
    own product — a plan change is `S107`'s *Change plan* action, which has no
    endpoint, no rule and no ruling — and the implementation order is a record
    of what Bynry SOLD, whose editability is the open half of `OQ-610`. A PUT
    here would be a door onto a decision nobody has made.

    **The role gate is A4's `settings_lookups` cell**, the same class every
    other Settings read on this module uses: System Admin *Full*, Executive
    *View*, Billing Clerk no cell at all. A clerk at a 1–2 staff utility has no
    business reading the subscription price, and `DEF-196`'s class already
    encodes exactly that split (it refuses a clerk on the READ, which is the
    half that was wrong for a day).
    """
    require_tenant(request)
    return Response(selectors.subscription_overview())


# ── S8 Settings → Numbering ─────────────────────────────────────────────────
@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def number_series(request: Any) -> Response:
    """The SET-08 tab: read every series, or save every changed one at once.

    ONE route, two verbs, because a whole-tab Save is the same resource as the
    whole-tab read — and because `path()` maps one URL to one view, so a second
    function on this path would silently shadow the first.
    """
    require_tenant(request)
    if request.method == "PUT":
        return Response(number_series_bulk_update(request))
    return Response(selectors.number_series_overview())


@api_view(["PUT"])
@permission_classes([SystemAdminOnly])
def number_series_update(request: Any, series: str) -> Response:
    require_tenant(request)
    payload = _payload(request)
    return Response(
        services.save_number_series(
            _actor(request),
            series,
            format_string=payload.get("format"),
            next_number=payload.get("next_number"),
            restart_period=payload.get("restart_period"),
        )
    )


def number_series_bulk_update(request: Any) -> list[dict[str, Any]]:
    """CR-005 Save: every changed row in ONE transaction, ONE audit entry.

    Same path as the tab read, one verb further — `PUT /settings/number-series`
    against `GET /settings/number-series`. The per-series route stays exactly as
    it was: the reset-counter dialog changes one row and has no business posting
    the other twenty-four.

    Not an `@api_view` of its own — `path()` maps one URL to one view, so this
    is the PUT half of `number_series` above and is called by it.
    """
    payload = _payload(request)
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    return services.save_number_series_bulk(_actor(request), rows)


# ── S8 Settings → Reference data → Custom fields (EP-TEN-09) ────────────────
#
# NOTE THE VERBS. GET · POST · PATCH · PUT and **no DELETE anywhere**
# (BR-TEN-050, CONFIRMED PO 2026-08-10 — *"Deactivate only"*). US-TEN-017 TC-3
# asks that a DELETE against a definition answer 405, and it does so because
# `@api_view` refuses a method it was not given — there is no delete route, no
# delete service and no ORM delete behind any of this.
#
# A11 CARRIES NO ROW FOR THESE PATHS YET. The contract file names no
# custom-field endpoint at all, so the paths below are minted from EP-TEN-09's
# own §5 field maps and the addendum is REPORTED as owed rather than written
# here — 04-docs/03-contracts is not this lane's territory.
@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def custom_fields_collection(request: Any) -> Response:
    """S8 → Custom fields: the management table (GET) and Add (POST).

    A4 makes Settings System-Admin-only, which US-TEN-014 TC-5 asserts as the
    permission state a Billing Clerk sees. The *registry* read below is a
    different endpoint with a different gate, because every staff role has to
    render the fields on the screens they already use.
    """
    require_tenant(request)
    if request.method == "POST":
        return Response(
            services.create_custom_field(_actor(request), _payload(request)), status=201
        )
    return Response(
        selectors.custom_field_rows(
            q=request.query_params.get("q"),
            entity=request.query_params.get("f.entity") or request.query_params.get("entity"),
            status=request.query_params.get("f.status") or request.query_params.get("status"),
        )
    )


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def custom_field_slots(request: Any) -> Response:
    """`CR-161-BRC10` W1 — THE ONE SLOT LIST, served (hard-won law 5).

    Every record type a field may apply to, whether Settings offers it for a
    new field, whether its import carries custom columns, and every declared
    screen with whether a screen renders it yet. Settings holds no copy of any
    of this; `custom_fields.SLOTS` is the only literal.
    """
    require_tenant(request)
    return Response({"entities": cf_law.slot_catalogue()})


@api_view(["GET", "PATCH"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def custom_field_item(request: Any, field_id: str) -> Response:
    """Edit one definition. `{"active": bool}` is the deactivate/reactivate row
    action (US-TEN-017), matching the shape the lookup framework already uses so
    the S8 table's row menu needs no second idiom (BR-TEN-047)."""
    require_tenant(request)
    if request.method == "GET":
        return Response(selectors.custom_field_row(field_id))
    payload = _payload(request)
    if set(payload) == {"active"}:
        return Response(
            services.set_custom_field_active(_actor(request), field_id, bool(payload["active"]))
        )
    return Response(services.update_custom_field(_actor(request), field_id, payload))


@api_view(["PUT"])
@permission_classes([SystemAdminOnly])
def custom_field_placement(request: Any, field_id: str) -> Response:
    """US-TEN-016 — the whole placement map, replaced in one write.

    PUT rather than PATCH deliberately: a placement is a MAP and a partial merge
    could never express "remove this screen" — the editor's own `not_shown`
    option would have no way to travel. The body is `{"placement": {...}}` or
    the map itself.
    """
    require_tenant(request)
    payload = _payload(request)
    placement = payload.get("placement", payload)
    return Response(services.save_custom_field_placement(_actor(request), field_id, placement))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def custom_field_registry(request: Any) -> Response:
    """THE registry every placed screen reads (US-TEN-017, BR-TEN-053).

    `?entity=assets&screen=S51&mode=input` — one cached read per screen, not a
    query per field. Any tenant role, because a meter tech filling in S51 is not
    a System Admin; the definitions are tenant configuration, not tenant
    secrets, and RLS FORCE plus the explicit tenant filter keep another
    utility's field set invisible either way (US-TEN-014 TC-6).
    """
    require_tenant(request)
    entity = (request.query_params.get("entity") or "").strip()
    if entity not in cf_law.ENTITIES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="settings.customFields.entity_not_covered",
            params={"entity": entity},
        )
    return Response(
        {
            "entity": entity,
            "fields": selectors.custom_field_registry(
                entity,
                screen=request.query_params.get("screen"),
                mode=request.query_params.get("mode"),
            ),
        }
    )


# ── S8 Settings → Reference data (/lookups/{list} — 11b §2.3) ───────────────
@api_view(["GET", "POST"])
# DEF-196, and `DEF-CUS-9048` (PO 2026-10-02): a Billing Clerk may also READ
# `asset_types` and `service_size_classes` — New Connect step 3's two lists —
# and nothing else here; POST is still a System Admin's alone.
@permission_classes([NewConnectionLookupRead])
def lookups(request: Any, list_code: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(
            services.create_lookup_entry(_actor(request), list_code, _payload(request)),
            status=201,
        )
    # CR-065 · BR-SHL-011's `f.<name>` grammar. A rate schedule for ONE service
    # asks for that service's size classes rather than fetching sixty and
    # choosing — and a list with no scope ignores it (see `lookup_page`).
    rows = selectors.lookup_page(
        list_code,
        request.query_params.get("q"),
        request.query_params.get("f.service_code"),
    )
    not_modified = _maybe_304(request, rows)
    if not_modified is not None:
        return not_modified
    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows, request)
    response = paginator.get_paginated_response(page)
    response["ETag"] = selectors.etag_for(rows)
    return response


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def lookup_fixture_gap(request: Any, list_code: str) -> Response:
    """`GET /lookups/{list}/fixture-gap` — BR-TEN-161 / DEF-902.

    Which entries the platform fixture ships for this list that this tenant
    does not hold. A READ: it delivers nothing and changes nothing (BR-TEN-160
    keeps delivery in the sweep, and OQ-550 asks the PO whether the sweep
    should re-offer a list a tenant already holds).

    ⚠ **ITS ROUTE SITS ABOVE `lookups/<list>/<entry_id>`**, which would
    otherwise match `fixture-gap` as an entry id and answer 404 for a list
    that has one — the DEF-520 route-ordering shape, and the same reason
    `assets/stock` sits above `assets/<uuid>`.

    Same A4 gate as the list it describes: a role that cannot read the list
    cannot read what is missing from it.
    """
    require_tenant(request)
    return Response(services.reference_list_fixture_gap(list_code))


@api_view(["GET"])
# DEF-196: the reference-data CARD GRID is the Settings landing for these
# lists. It writes nothing, and a role A4 grants "View" that cannot see the
# grid cannot reach any list behind it.
#
# ⚠ IT TAKES THE SAME A4-SCOPED CLASS, NOT `AnyTenantRole`. The first cut used
# `AnyTenantRole` here on the reasoning that a pure read needs no write gate —
# true, and irrelevant: the question is WHICH ROLES READ, and A4 gives the
# Billing Clerk no `settings_lookups` cell at all. US-TEN-009 TC-5 caught it.
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def lookup_cards(request: Any) -> Response:
    require_tenant(request)
    return Response(selectors.lookup_cards())


@api_view(["PATCH", "DELETE"])
@permission_classes([SystemAdminOnly])
def lookup_entry(request: Any, list_code: str, entry_id: str) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        services.delete_lookup_entry(_actor(request), list_code, entry_id)
        return Response(status=204)
    payload = _payload(request)
    if set(payload) == {"active"}:  # US-TEN-011 reactivate/deactivate row action
        return Response(
            services.set_lookup_entry_active(
                _actor(request), list_code, entry_id, bool(payload["active"])
            )
        )
    return Response(services.update_lookup_entry(_actor(request), list_code, entry_id, payload))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def lookup_entry_deactivate(request: Any, list_code: str, entry_id: str) -> Response:
    require_tenant(request)
    return Response(services.set_lookup_entry_active(_actor(request), list_code, entry_id, False))


# ── S63 Settings → Holiday calendar ─────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # DEF-196
def holidays(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_holiday(_actor(request), _payload(request)), status=201)
    return Response(selectors.holidays())


@api_view(["PATCH", "DELETE"])
@permission_classes([SystemAdminOnly])
def holiday_item(request: Any, holiday_id: str) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        services.delete_holiday(_actor(request), holiday_id)
        return Response(status=204)
    return Response(services.update_holiday(_actor(request), holiday_id, _payload(request)))


# ── US-SHL-008 — the generic table-level export, POST /exports (11b §2.11) ──
@api_view(["POST"])
@authentication_classes([IdentitySessionAuthentication])
@permission_classes([AnyTenantRole])
def list_export(request: Any) -> Response:
    """POST /exports — 202 + job_id for ANY list that registered itself.

    Route registered in config/urls.py, not in this module's urlpatterns: like
    `/jobs/{id}`, `/exports` is a PLATFORM resource served by the module that
    hosts the jobs table, not a tenancy feature path. Nesting it under
    tenancy's settings routes would misname it.

    The body mirrors the list's OWN request state (BR-SHL-011's grammar):

        {"resource": "premises", "filters": {...}, "sort": "...",
         "dir": "asc|desc", "q": "..."}

    Filters may also arrive as `f.<name>` query params — the same URL state the
    screen already carries — so a client can post the very query string it is
    displaying; the body wins where both name the same filter. Anything outside
    the resource's declared vocabulary is IGNORED, never a 4xx (BR-SHL-011).

    `resource` is required and must be registered: an unknown one is a plain
    404 (HR-1 / 11b G4), never a guessed queryset. Over 50,000 rows the service
    refuses 422 BIZ-CAP with the real count, and no job and no file exist.
    """
    require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    resource_name = body.get("resource") or request.query_params.get("resource")
    resource = exports.export_resource(resource_name)
    if resource is None:
        raise errors.NotFoundError()

    # The declared vocabulary is the LIST endpoint's own, so an export request
    # is parsed exactly the way the list request was (fall back, never error).
    params = parse_list_params(
        request.query_params,
        allowed_sorts=resource.sorts,
        default_sort=resource.default_sort,
        allowed_filters=resource.filters,
    )
    filters = dict(params.filters)
    body_filters = body.get("filters")
    if isinstance(body_filters, dict):
        filters.update({str(k): str(v) for k, v in body_filters.items() if k in resource.filters})
    body_sort = body.get("sort")
    sort = body_sort if body_sort in resource.sorts else params.sort
    body_dir = str(body.get("dir") or "").lower()
    direction = body_dir if body_dir in ("asc", "desc") else params.dir
    if "dir" not in request.query_params and not body_dir:
        direction = resource.default_dir  # the capability row's own default
    q = str(body.get("q") or params.q or "")

    accepted = services.request_list_export(
        actor=request.user,
        resource_name=resource.name,
        q=q,
        sort=sort,
        direction=direction,
        filters=filters,
        # P4.13 — IS-9's second half, RULED by the PO on 2026-09-24: *"all
        # selected columns will go in downloaded file"*. Passed through RAW:
        # `exports.columns_for` owns the vocabulary AND owns BR-SHL-011's
        # fall-back, so validating it here too would be a second place for the
        # two to disagree.
        columns=body.get("columns"),
    )
    return Response(accepted, status=202)


# ── IS-11 download — GET /exports/{job_id}/file ─────────────────────────────
@api_view(["GET"])
@authentication_classes([IdentitySessionAuthentication])
@permission_classes([AnyTenantRole])
# ⚠ `DEF-MET-4954` — this route answered one plain 404 for every export on
# any deployment with `JOBS_EAGER=false`, because the artifact was written on
# the worker's own disk. A shared Docker volume papered over it; since
# 2026-10-02 (PO: exports move to S3) the file is in the environment's bucket
# and this route resolves it through its `job_artifacts` row.
def export_file(request: Any, job_id: uuid.UUID) -> Any:
    """Hand over the file a finished export job produced (BR-REP-018 / IS-11).

    A PLATFORM path beside `/jobs/{id}` and `/exports`, for the same reason
    those two are: the exportable lists live in many modules, so the download
    belongs to none of them — it belongs to whoever hosts the `jobs` table.

    **One 404 for every different no** (HR-1 / 11b G4). An unknown id, another
    tenant's id, a job that is not an export, a job that has not SUCCEEDED, a
    job with no stored file and a file past the utility's retention all produce
    the byte-identical refusal (`exports.resolve_artifact`). Distinguishing them
    would leak which job ids exist, and a 403 would leak it loudest.

    **A 302 to a signed S3 link, never the bytes** (PO 2026-10-02: *"the system
    checks the record and hands over a link to the file that lasts 4 hours"*).
    The link names the file (`Content-Disposition` is signed into it) and lives
    the 2026-08-30 ruling's four hours. The bytes do not pass through this
    process: a sync web worker is killed at 60 s, and a print set is 100 MB+.
    The frontend's plain `<a href download>` follows the redirect unchanged.

    Roles: any signed-in member of the tenant, the same gate the export's own
    accept applies (services.request_list_export records why A4 has no
    per-list export cell). The narrowing to "the user who started the job" is
    the same owed refinement job_status records — the BE-07 record has no
    actor column, and inventing one here would be inventing schema.
    """
    from apps.tenancy import export_store

    require_tenant(request)
    job = selectors.job_artifact(job_id)
    row = exports.resolve_artifact(job)
    if row is None:
        # ⚠ DEF-TEN-9190 — A JOB THAT SAYS IT SUCCEEDED AND HAS NO FILE IS A
        # DEPLOYMENT FAULT, NOT AN EXPIRED LINK, and it was answered with the
        # same silent 404. The answer to the caller stays byte-identical (HR-1);
        # the LOG says which: the usual cause is a worker on a build older than
        # 2.455.0, which writes the file to its own disk and never to S3.
        exports.log_missing_artifact(job)
        raise errors.NotFoundError()
    if not export_store.object_exists(row):
        # DEF-TEN-9190 — the row says stored and the bucket does not hold the
        # file (deleted by hand, a lifecycle rule, a different bucket). The
        # redirect would land the browser on S3's own error document; it gets
        # the same plain 404 instead, and the log names the key.
        raise errors.NotFoundError()
    response = HttpResponseRedirect(export_store.download_url(row))
    # The redirect target is a credential for four hours; nothing caches it.
    response["Cache-Control"] = "no-store, private"
    return response


# ── BE-07 shared job poll — GET /jobs/{id} (11b §2.17) ──────────────────────
@api_view(["GET"])
@authentication_classes([IdentitySessionAuthentication])
@permission_classes([AnyTenantRole])
def job_status(request: Any, job_id: uuid.UUID) -> Response:
    """The ONE resource every 202 in this API promises (B12 r1 / 11b §2.17).

    Route registered in config/urls.py, not in this module's urlpatterns: the
    path is `/jobs/{id}`, a PLATFORM resource that happens to be served by the
    module hosting the `jobs` table — nesting it under tenancy's settings
    routes would misname it.

    Roles: any signed-in member of the tenant (AnyTenantRole). The ratified
    contract says a caller may poll a job THEY started, but the BE-07 record
    (core/jobs.py, `jobs` table) has NO actor column — inventing one here
    would be inventing schema, so the scope enforced is the TENANT's, and the
    narrowing to the starting user is REPORTED as an owed refinement (it needs
    a `started_by` column + a B2 addendum). Nothing sensitive rides in the
    payload this serves: id, kind, status, progress, checkpoint, result_link,
    error — and, for the sample-data plant only, `steps`.

    ⚠ `checkpoint` WAS MISSING FROM THAT LIST AND FROM THE PAYLOAD UNTIL
    DEF-3280 (2026-09-02). The plant job has recorded the label of the block it
    just finished since 2026-08-19 and no client could read it, so this
    endpoint could answer *"11 of 17"* and never *"Meter reads"*.

    ⚠ `steps` IS THE SAMPLE-DATA PLANT'S AND NO OTHER KIND'S — CR-064 (PO
    2026-09-02, *"list down all 17 steps and show 1 by 1 when they finish"*).
    All twenty-eight, always, in creation order, each carrying what the run
    recorded for it or `not_started` when it has not been reached. The key is
    ABSENT for every other kind rather than empty, because a job with no blocks
    has no steps and an empty list would read as an answer.

    Absent, malformed, or another tenant's job id → the same plain 404 (HR-1 /
    11b G4: existence must not leak, and a 403 would confirm it).
    """
    require_tenant(request)
    payload = selectors.job_poll(job_id)
    if payload is None:
        raise errors.NotFoundError()
    return Response(payload)


# ── S64/S66/S69/S70/S71 rule pages (11b §2.3) ───────────────────────────────
# One shape for all five: GET reads the page, PUT saves it whole and atomically
# with ONE audit row (BR-TEN-024/016); every change is event-time forward
# (BR-TEN-043). A4 grants Settings "Full" to System Admin and "View" to
# Executive, so the view class admits both and the SERVICE's @require_role
# refuses the Executive's write with 403 AUTH-002 (BR-SHL-025 defense in depth).
def _rule_page(request: Any, slug: str) -> Response:
    require_tenant(request)
    if request.method == "PUT":
        return Response(services.save_settings_family(_actor(request), slug, _payload(request)))
    return Response(selectors.settings_family(slug))


# ⚠ S64 (`/settings/read-validation`) MOVED to apps/metering/api.py — CR-038
# A1 (PO 2026-08-26). The family document this surface used to save was a
# SECOND home for figures the ENGINE reads from metering's own tables, and a
# tenant's S64 edit never reached validation — the exact divergence the
# settings_families docstring reserved re-homing for. The route is removed
# HERE in the same commit the metering routes land, so the URL never serves
# two owners; the four remaining rule pages are untouched.


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def billing_defaults_settings(request: Any) -> Response:
    """S66 — BR-BIL-021's seeded config family: late %/min (BR-BIL-001) +
    grace days/mode (BR-BIL-002/008) + minimum-bill fallback + overcharge
    guardrail % (BR-BIL-029) + allocation order (BR-PAY-010) + deposit
    interest (B2 r9 #5, tagged S66)."""
    return _rule_page(request, "billing-defaults")


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def budget_billing_settings(request: Any) -> Response:
    """S69 — BR-BIL-017: every budget-billing parameter is a tenant setting."""
    return _rule_page(request, "budget-billing")


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def collections_settings(request: Any) -> Response:
    """S70 — BR-PAY-016/017 cadences + BR-PAY-013 NSF privilege threshold +
    BR-PAY-018 paper suppression. Ladders already walking finish under their
    in-force intervals (BR-TEN-043)."""
    return _rule_page(request, "collections")


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def finance_controls_settings(request: Any) -> Response:
    """S71 — bank auto-match tolerance (BR-PAY-019), small-balance write-off
    bound (BR-BIL-013), DSO target (BR-REP-022), correction-approval mode
    (BR-BIL-014) and the back-bill cap + theft exemption (BR-BIL-018)."""
    return _rule_page(request, "finance-controls")


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def reports_settings(request: Any) -> Response:
    """S8 · Configure → Reference data → REPORTS — `CR-142-BRC07` `P4.6`.

    Two facts about the PLATFORM EXPORT KERNEL that a utility may change:
    how long a generated file is kept (`BR-REP-018`, whose *"3 days by default,
    **tenant-configurable**"* has been signed since 2026-08-08 with only the
    first half built) and what a download IS unless the clerk asks otherwise.

    ⚠ **IT IS SERVED HERE AND NOT BY `apps/reports`, AND THAT IS THE MODULE
    BOUNDARY RATHER THAN A CONVENIENCE.** The number governs
    `exports.ARTIFACT_RETENTION_DAYS`, which is the kernel every list export in
    this product runs through — audit's and the platform's as well as reports'
    — so tenancy declares it, validates it, writes it and audits it. Reports
    READS it through its own seam. The drawing files the cards under a REPORTS
    heading; the heading is presentation, exactly as `reason_codes` is billing's
    and files under Plans & Rates.
    """
    return _rule_page(request, "reports")


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def service_requests_settings(request: Any) -> Response:
    """S8 · Configure → Reference data → ACCOUNTS → Service requests.

    `DEF-CUS-10445` (PO 2026-10-22, *"Default 15 days"*). The number of days
    after the request date that an acknowledgement aims at when the applicant
    gave no preferred date. Tenancy declares, validates, writes and audits it;
    `apps/customers` reads it through its seam.
    """
    return _rule_page(request, "service-requests")


# ── US-TEN-019 — sample data (EP-TEN-03; BR-TEN-069 puts both actions on S8
# Company profile) ──────────────────────────────────────────────────────────
#
# WHY THESE THREE ROUTES EXIST AND WHAT THEY DELIBERATELY DO NOT PROMISE.
# `apps/tenancy/sample_data.py` shipped 2026-08-15 complete, tested and
# `E=deferred(no-frontend-half)` — an orchestrator with an honest report and no
# way for a human to ask it anything. That is the DEF-112 shape G23 counts, and
# these are its API half.
#
# The honesty they carry is the POINT of the feature, not a caveat on it. Every
# module in the sample set resolves to `skipped / seam_not_wired` today, so a
# seed run creates ZERO rows and names all four modules and the reason. The
# endpoints return that verbatim. They do NOT return 204, they do NOT return an
# empty success, and the seed route does NOT answer 202 — there is no job runner
# in this deployment (TD-17) and a 202 with no job behind it is a promise, the
# same posture `POST /rate-changes` and the audit export already take.
#
# GET is `AnyTenantRole` because it is a REPORT — an Executive reading why the
# demo data is not there is A4's whole View posture. Both writes are
# `SystemAdminOnly`: BR-TEN-064 says a human asks and the job runs in
# production, so the human who may ask is the one who owns the tenant.
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def sample_data_runs(request: Any) -> Response:
    """`GET /settings/sample-data` — the BR-TEN-060 honesty report.

    Serves the stored ledger, the removal plan, and `seeded_total`. A tenant
    that has never run the job gets `modules: []` and `succeeded: false`, which
    is why `has_run` is sent as its own boolean: "never asked" and "asked and
    nothing loaded" are different facts and the screen must not merge them into
    one zero (the DEF-127 posture — a count nothing wrote is not a count).
    """
    require_tenant(request)
    summary = sample_data.run_summary()
    return Response(
        {
            **summary,
            "has_run": bool(summary["modules"]),
            # CR-039 wave B: `blocks` is empty for BOTH "never asked" and "asked
            # before block-level reporting existed", and those are different
            # facts — the DEF-127 shape again, one level down. `has_run` keeps
            # the first apart; this keeps the second apart, so the panel can say
            # "re-run to see the breakdown" instead of showing a blank list that
            # reads as an answer.
            "blocks_recorded": bool(summary["blocks"]),
            "removal": sample_data.removal_plan(),
        }
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def sample_data_seed(request: Any) -> Response:
    """`POST /settings/sample-data/seed` — BR-TEN-064: a human asks, always.

    Synchronous on purpose (see the block comment above). Idempotent per tenant
    by BR-TEN-063, so a second press updates the ledger rather than doubling it.
    """
    require_tenant(request)
    return Response(sample_data.seed_sample_data(_actor(request)))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def sample_data_retry(request: Any) -> Response:
    """`POST /settings/sample-data/retry` — CR-039 wave B: re-run ONE block.

    Body: `{"module": "billing", "block": "seed_sample_records"}` — the pair
    `sample_data_runs.blocks[]` reports, because a module owns up to three
    blocks and "retry billing" would be ambiguous the moment it owned two.

    `SystemAdminOnly` like the other two writes: BR-TEN-064's *"a human asks"*
    does not become *"anyone asks"* because the unit got smaller.

    Answers the WHOLE report, not just this block. Fixing the ROOT of a cascade
    does not by itself clear the consequences below it — those blocks are still
    unseeded until they too are run — and an operator who pressed retry needs
    to see which lines are still red, not a green line in isolation.
    """
    require_tenant(request)
    payload = request.data if isinstance(request.data, dict) else {}
    module = str(payload.get("module") or "").strip()
    block = str(payload.get("block") or "").strip()
    if not module or not block:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[
                {"field": name, "code": errors.VAL_REQUIRED}
                for name in ("module", "block")
                if not str(payload.get(name) or "").strip()
            ],
        )
    try:
        result = sample_data.retry_block(_actor(request), module=module, block=block)
    except sample_data.UnknownSampleBlock as exc:
        # A 404 rather than a 422: the addressed thing does not exist. Named
        # rather than silently no-op'd — a retry that reported success over a
        # block the catalogue does not hold is DEF-016's shape.
        raise errors.NotFoundError() from exc
    # The same two booleans GET carries, for the same reason: a caller reading
    # this body must be able to tell "never asked" and "asked, no breakdown"
    # apart from an empty list. `removal` is deliberately NOT recomputed — it
    # walks every module's seams and a retry changed nothing it reports.
    return Response(
        {
            **result,
            "has_run": bool(result["modules"]),
            "blocks_recorded": bool(result["blocks"]),
        }
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def sample_data_remove(request: Any) -> Response:
    """`POST /settings/sample-data/remove` — BR-TEN-066, partial-and-named.

    Returns the plan, which today is "nothing is removable, and here is the
    named reason per module". It is a POST rather than a DELETE because the
    contracted action is a REMOVAL RUN over a tagged row set, not the deletion
    of the resource this path names — and because DELETE on a route that
    removes nothing reads as a destructive button that worked.
    """
    require_tenant(request)
    return Response(sample_data.remove_sample_data(_actor(request)))


# PO ruling 2026-08-10 (path tenancy): the routes below are mounted by
# config/urls.py under `/api/{tenant}/`. The no-tenant half of this module's
# surface is exported separately as `public_urlpatterns` — the public
# onboarding reads and the provisioning POST exist BEFORE any tenant does, so
# they cannot live behind a tenant prefix.
public_urlpatterns = [
    path("public/subdomain-check", subdomain_check),
    path("public/pricing-plans", pricing_plans),
    path("tenants", tenants),
]

urlpatterns = [
    path("tenants/checklist", checklist),
    path("tenants/checklist/<str:item>/dismiss", checklist_item_dismiss),
    path("settings/company", company_settings),
    path("settings/company/logo", company_logo),
    # CR-048 wave D — the READ half. A separate segment rather than a GET on
    # the line above, because the two have different permissions (any role
    # may look, only a System Admin may replace) and different response
    # shapes (raw image bytes vs the JSON reference).
    path("settings/company/logo/file", company_logo_file),
    path("settings/regional", regional_settings),
    # DEF-SHL-4272 — the shell's boot read. Deliberately OUTSIDE the
    # `settings/…` family: the whole rule (BR-SHL-252) is that these values are
    # not settings administration, and a path that filed them under `settings`
    # would invite the next lane to gate them like settings again. ORDER IS
    # SAFE and was checked rather than assumed: `grep -rn '"shell' apps/*/api.py
    # apps/*/*_api.py config/urls.py` finds this line and nothing else, so
    # `shell` is claimed by no other module and is not a prefix of anything —
    # Django matches WHOLE segments, and a duplicate path SHADOWS rather than
    # merges.
    path("shell/display", shell_display),
    # `settings/read-validation` is METERING's since CR-038 A1 — see the note
    # where the view used to be defined.
    path("settings/billing-defaults", billing_defaults_settings),
    path("settings/budget-billing", budget_billing_settings),
    path("settings/collections", collections_settings),
    path("settings/finance-controls", finance_controls_settings),
    # `P4.6` — the REPORTS section of the Reference-data grid. ORDER IS SAFE:
    # `settings/reports` shares no whole segment with any route above and
    # Django matches whole segments, so it shadows nothing.
    path("settings/reports", reports_settings),
    # `DEF-CUS-10445` — ORDER IS SAFE: no other route here or in another
    # module's api claims `settings/service-requests` (grep-checked), and
    # Django matches whole segments.
    path("settings/service-requests", service_requests_settings),
    path("settings/services", services_settings),
    path("settings/services/<str:service>", service_update),
    path("settings/number-series", number_series),
    # S107 (11b §2.16) — GET /subscription. ORDER IS SAFE and was checked
    # rather than assumed: `grep -rn '"subscription' apps/*/api.py config/urls.py`
    # finds this line and nothing else, Django matches WHOLE segments so it is
    # not a prefix of anything, and it shares no first segment with this
    # module's `settings/…` or `lookups/…` families. A duplicate path SHADOWS
    # rather than merges, which is the failure this note exists to rule out.
    path("subscription", subscription),
    path("settings/number-series/<str:series>", number_series_update),
    path("settings/holidays", holidays),
    path("settings/holidays/<str:holiday_id>", holiday_item),
    # US-TEN-019 (EP-TEN-03). The two static verbs are declared BEFORE the
    # collection so neither can ever be read as a path parameter.
    path("settings/sample-data/seed", sample_data_seed),
    path("settings/sample-data/retry", sample_data_retry),
    path("settings/sample-data/remove", sample_data_remove),
    path("settings/sample-data", sample_data_runs),
    # EP-TEN-09. No DELETE route exists at any depth (BR-TEN-050).
    path("settings/custom-fields", custom_fields_collection),
    # Before the `<field_id>` route, which would otherwise read `slots` as an id.
    path("settings/custom-fields/slots", custom_field_slots),
    path("settings/custom-fields/<str:field_id>", custom_field_item),
    path("settings/custom-fields/<str:field_id>/placement", custom_field_placement),
    path("custom-fields", custom_field_registry),
    path("lookups", lookup_cards),
    path("lookups/<str:list_code>", lookups),
    # DEF-902 / BR-TEN-161 — literal segment ABOVE the <entry_id> route.
    path("lookups/<str:list_code>/fixture-gap", lookup_fixture_gap),
    path("lookups/<str:list_code>/<str:entry_id>", lookup_entry),
    path("lookups/<str:list_code>/<str:entry_id>/deactivate", lookup_entry_deactivate),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03 lead story; co-packets EP-TEN-05@0733260 · EP-TEN-06@53479d6 · EP-TEN-07@178c282 · EP-TEN-08@80cdedf · EP-MET-04@34f14b6)
# generated: 2026-08-09 by story-coder v1 (W0 tenancy provisioning + settings lane) · AMENDED 2026-08-09 by story-coder (settings rule-page + logo gap lane) · AMENDED 2026-08-10 by story-coder (job-runner lane: GET /jobs/{id}) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder (deploy-blocker lane — 09-infra/02 §10.14) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F select, same bar the baseline passes) black✔ pytest tests/test_us_ten_*: 86 passed / 2 skipped (logo lane · identity-seam skip-until-wired) / 2 isolation→G5✔ · suite 335 passed, 7 skipped, 20 deselected✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · [job-runner lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [deploy-blocker lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 868 passed / 9 skipped (818 baseline) · `-m isolation` 32 passed / 12 skipped (32 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0005 (plan catalog) added by this lane, ledger row present
# exceptions: owner session token in the POST /tenants response is the identity lane's half (seam) — reported · [gap lane 2026-08-09] urlpatterns ARE now included by config/urls.py (the wiring lane landed the include) · 413/415 are rendered by a local envelope helper because core.errors' handler has no 413 branch and core/ is outside this lane's territory — REPORTED as a one-elif kernel follow-up · the five rule pages admit Executive on GET per A4 ("Settings & lookup tables: Full / — / View") while the older /settings/company and /settings/regional endpoints are System-Admin-only on both verbs — divergence REPORTED, existing endpoints not flipped by this lane · no GET/DELETE for the logo: no signed-URL/document-delivery contract exists in core and no story anchors removal — neither invented · [job-runner lane 2026-08-10] GET /jobs/{id} scopes by TENANT, not by the user who started the job: the BE-07 record has no actor column and inventing one would be inventing schema (11b §2.17 says "a job they started") — REPORTED, needs a `started_by` column + B2 addendum · this file's other endpoints declare NO authentication_classes, so a real cookie-session client cannot reach them (DRF's defaults do not attach request.tenant_role); job_status declares IdentitySessionAuthentication explicitly — the gap on the older endpoints is REPORTED, not silently patched from this lane · [path-tenancy lane 2026-08-10] the owner-session gap recorded above is CLOSED: POST /api/tenants now returns the session as the httpOnly cookie and `signed_in` in the body (PO ruling supersedes BR-TEN-045); a BR-TEN-010 REPLAY deliberately gets NEITHER, because that path verifies no password · public_urlpatterns split out of urlpatterns: the public reads + provisioning cannot sit behind a tenant prefix · the no-authentication_classes gap on this file's older endpoints is UNCHANGED and re-REPORTED — a cookie client still gets 401 there for every tenant alike, so it leaks nothing, and those endpoints inherit the cross-tenant 404 the day their lane wires IdentitySessionAuthentication (pinned by test_path_tenancy_the_unauthenticated_endpoints_leak_nothing_either) · [deploy-blocker lane 2026-08-10] THE no-authentication_classes GAP RECORDED ABOVE IS CLOSED, and not by editing this file's endpoints: IdentitySessionAuthentication is now the DRF DEFAULT (config/settings/base.py), so every endpoint here reads the session and inherits the BR-IDN-006 cross-tenant 404 — the prediction the previous trailer made, kept without a single per-view declaration. What this file DID gain is four deliberate opt-OUTS: subdomain_check, pricing_plans and tenants now declare `authentication_classes([])` beside their AllowAny, because a default that reads the cookie would 401 a signup carrying a stale session and, on the tenant-less /api/tenants path, would enter the OLD tenant's context (adopt_session_tenant) for a transaction creating a new one · the pricing_plans endpoint finally has rows to serve: the catalog is seeded by tenancy migration 0005 (was empty on every fresh database — 09-infra/02 §10.3)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
