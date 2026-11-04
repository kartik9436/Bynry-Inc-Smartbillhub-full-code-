# ── Trace ──────────────────────────────────────────────
# Component: BE-02 error-catalog module (B13 §3, W0 kernel lane — component packet, not a story)
# Contract:  B12 §3 error catalog + Addendum r1 §3-expanded (full HTTP series) · A11 Addendum r2 /
#            11b §3 G1 (envelope shape), G4 (404-never-403), G13 (RBAC denials), G15 (attempt rows)
# Rules:     BR-AUD-018 (refusal attempt rows) · BR-IDN-009 (server-side RBAC denial)
# Tests:     06-backend/tests/test_be02_errors.py · gate G9 (endpoint files import this module)
# Impacts:   every api.py in 06-backend/apps (raise catalog exceptions only, B8) · FI-01 client
# ───────────────────────────────────────────────────────
"""BE-02 — the ONE exception→envelope mapping for the whole API surface.

Every refusal an endpoint can produce is a catalog exception from this module
(B8: "raise only catalog exceptions — never bare ValueError into an API").
The DRF exception handler here renders the ratified envelope for EVERY error:

    {code, message_key, params, field_errors[], br_ref, trace_id}   (11b §3 G1)

Catalog codes are module constants below — never magic strings at call sites.
Codes come ONLY from B12 §3 (AUTH/VAL/BIZ/SYS); constructing an exception with
any other code raises immediately, so an invented code cannot reach a response.

404-never-403 law (11b §3 G4, HR-1): a cross-tenant resource returns 404 with a
body IDENTICAL to a genuinely-absent resource — existence must not leak. Use
`deny_as_not_found()` for the cross-tenant case; the denial is recorded
server-side only (BR-AUD-018 attempt row), never in the response body.

HTTP statuses with no catalog code (400/404/405/415/429 — defined by the B12 r1
HTTP-series table, not the §3 catalog) render the envelope with `code: null`;
inventing codes for them would violate G1. Flagged to the PO as a catalog gap.
"""

import logging
import uuid
from typing import Any

from django.core import exceptions as django_exceptions
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response

from core import refusal_catalogue

logger = logging.getLogger("smartbillhub.api")

# ── B12 §3 catalog codes (constants, never magic strings) ──────────────────
# AUTH class — 401/403 (law: BR-IDN-001/009, T6)
AUTH_UNAUTHENTICATED = "AUTH-001"
AUTH_PERMISSION_DENIED = "AUTH-002"
AUTH_TENANT_UNRESOLVABLE = "AUTH-003"
# VAL class — 422 (law: IS-7, OQ-004 closure)
VAL_REQUIRED = "VAL-001"
VAL_FORMAT = "VAL-002"
VAL_RANGE = "VAL-003"
VAL_UOM_MISMATCH = "VAL-004"
VAL_UNKNOWN_LOOKUP = "VAL-005"
# BIZ class — 409/422 (law: HR-4 · NFR-16 · BR-TEN-042/038 · BR-BIL-026 · BR-PAY-011 ...)
BIZ_IMMUTABLE = "BIZ-IMMUTABLE"
BIZ_IDEMPOTENT = "BIZ-IDEMPOTENT"
BIZ_LOCKED = "BIZ-LOCKED"
BIZ_WINDOW = "BIZ-WINDOW"
BIZ_APPROVAL = "BIZ-APPROVAL"
BIZ_COMPLETENESS = "BIZ-COMPLETENESS"
BIZ_CAP = "BIZ-CAP"
BIZ_STATE = "BIZ-STATE"
BIZ_SOD = "BIZ-SOD"
# SYS class — 500/503 (law: BR-LED-007, BR-NOT-005)
SYS_DRIFT = "SYS-DRIFT"
SYS_PROVIDER = "SYS-PROVIDER"
SYS_INTERNAL = "SYS-INTERNAL"

# code → HTTP status, exactly per B12 §3 + Addendum r1 §3-expanded.
# 409 = the r1 "BIZ conflicts (immutable/idempotent/locked/state)" row;
# the remaining BIZ codes are "semantic refusals" → 422 (BIZ-CAP → 422 per 11b G11).
# AUTH-003 → 401: the §3 row allows 401/403; 401 is used because an unresolvable
# tenant means no authenticated tenant context exists at all.
HTTP_STATUS_BY_CODE: dict[str, int] = {
    AUTH_UNAUTHENTICATED: 401,
    AUTH_PERMISSION_DENIED: 403,
    AUTH_TENANT_UNRESOLVABLE: 401,
    VAL_REQUIRED: 422,
    VAL_FORMAT: 422,
    VAL_RANGE: 422,
    VAL_UOM_MISMATCH: 422,
    VAL_UNKNOWN_LOOKUP: 422,
    BIZ_IMMUTABLE: 409,
    BIZ_IDEMPOTENT: 409,
    BIZ_LOCKED: 409,
    BIZ_WINDOW: 422,
    BIZ_APPROVAL: 422,
    BIZ_COMPLETENESS: 422,
    BIZ_CAP: 422,
    BIZ_STATE: 409,
    BIZ_SOD: 422,
    SYS_DRIFT: 500,
    SYS_PROVIDER: 503,
    SYS_INTERNAL: 500,
}
ALL_CODES = frozenset(HTTP_STATUS_BY_CODE)

AUTH_CODES = frozenset({AUTH_UNAUTHENTICATED, AUTH_PERMISSION_DENIED, AUTH_TENANT_UNRESOLVABLE})
VAL_CODES = frozenset({VAL_REQUIRED, VAL_FORMAT, VAL_RANGE, VAL_UOM_MISMATCH, VAL_UNKNOWN_LOOKUP})
BIZ_CODES = frozenset(
    {
        BIZ_IMMUTABLE,
        BIZ_IDEMPOTENT,
        BIZ_LOCKED,
        BIZ_WINDOW,
        BIZ_APPROVAL,
        BIZ_COMPLETENESS,
        BIZ_CAP,
        BIZ_STATE,
        BIZ_SOD,
    }
)
SYS_CODES = frozenset({SYS_DRIFT, SYS_PROVIDER, SYS_INTERNAL})


def default_message_key(code: str) -> str:
    """Mechanical i18n key for a catalog code (TD-16: server sends keys, UI renders).

    Callers pass domain keys ("billing.run.not_draftable") when they have one;
    this fallback is derived from the code so no prose is ever invented here.
    """
    return "errors." + code.lower()


# ── Exception hierarchy (one class per B12 §3 catalog class) ────────────────
class ApiError(Exception):
    """Base catalog exception. Carries everything the envelope needs.

    Subclasses restrict `code` to their catalog class — an endpoint physically
    cannot raise a BIZ code through AuthError, or a made-up code through any.
    """

    allowed_codes: frozenset[str] = ALL_CODES

    def __init__(
        self,
        code: str,
        *,
        message_key: str | None = None,
        params: dict[str, Any] | None = None,
        field_errors: list[dict[str, Any]] | None = None,
        br_ref: str | None = None,
    ) -> None:
        if code not in self.allowed_codes:
            # G1: "no endpoint invents a code; catalog additions = PR to B12 §3".
            raise ValueError(f"{code!r} is not a {type(self).__name__} catalog code (B12 §3)")
        self.code = code
        self.message_key = message_key or default_message_key(code)
        self.params = params or {}
        self.field_errors = field_errors or []
        self.br_ref = br_ref
        self.http_status = HTTP_STATUS_BY_CODE[code]

        # ⚠ A REFUSAL WITH NO SENTENCE REACHES A CLERK AS SILENCE, NOT AS AN
        # UGLY KEY — the PO's 2026-08-19 ruling suppressed `params.detail`, so
        # an unresolved `message_key` means the click does nothing and nothing
        # appears. This is the single choke point every catalog refusal passes
        # through, which makes it the earliest place the fault can be caught:
        # the lane's OWN test run, rather than a gate after the branch has it.
        # Off outside a test run; see core/refusal_catalogue for why that is not
        # law 3 pointing the other way.
        #
        # ⚠ ONLY A KEY THE CALLER SUPPLIED, AND THE SCOPE IS A FINDING RATHER
        # THAN AN EXEMPTION. `default_message_key(code)` below derives a key
        # from the code when a caller gives none; that is a CLOSED SET OF 20
        # owned by this module, not something a lane writes, and EIGHT of the
        # twenty resolve to nothing today (measured 2026-09-05: biz-immutable,
        # biz-locked, biz-window, biz-approval, biz-completeness, biz-cap,
        # biz-sod, sys-drift). Folding those into the per-raise check would
        # report ONE of them, whichever code a test happened to exercise, and
        # only where coverage reaches. They get a check of their own instead —
        # tests/test_refusal_keys_resolve_at_raise.py names the whole closed set
        # and all eight at once, which does not depend on coverage and is the
        # stronger question to ask about a fixed list. DEF-SHL-4092 owns them.
        if message_key is not None:
            refusal_catalogue.assert_resolves(message_key, raised_by=type(self).__name__)
        # Inline field errors render UNDER THE INPUT through `envelopeErrors`,
        # from their own keys. An unresolved one is the same silence one level
        # down — the field goes red with no reason written beside it — and G32
        # reads this dict-literal form for exactly that reason.
        for item in self.field_errors:
            key = item.get("message_key") if isinstance(item, dict) else None
            if isinstance(key, str):
                refusal_catalogue.assert_resolves(key, raised_by=f"{type(self).__name__} field_errors")

        super().__init__(f"{code} ({self.message_key})")


class AuthError(ApiError):
    allowed_codes = AUTH_CODES


class ValidationError(ApiError):
    allowed_codes = VAL_CODES


class BizError(ApiError):
    """B8: every BIZ refusal carries its BR-ID — br_ref is mandatory here."""

    allowed_codes = BIZ_CODES

    def __init__(self, code: str, *, br_ref: str, **kwargs: Any) -> None:
        super().__init__(code, br_ref=br_ref, **kwargs)


class SysError(ApiError):
    allowed_codes = SYS_CODES


class NotFoundError(Exception):
    """404 — genuinely absent OR cross-tenant (indistinguishable by law, G4/HR-1).

    Not an ApiError: 404 has no B12 §3 catalog code, so the envelope renders
    `code: null`. `audit_br_ref` is SERVER-SIDE ONLY — set by deny_as_not_found
    so the handler writes a BR-AUD-018 attempt row; it never serializes,
    keeping cross-tenant and plain-absent bodies byte-identical (no leak).
    """

    def __init__(self, audit_br_ref: str | None = None) -> None:
        self.audit_br_ref = audit_br_ref
        super().__init__("not found")


def deny_as_not_found(br_ref: str = "BR-TEN-003") -> NotFoundError:
    """Cross-tenant access → 404, never 403 (HR-1: existence must not leak).

    Usage: `raise deny_as_not_found()` wherever an object lookup crosses the
    tenant boundary. The response equals a plain 404; the denial is recorded
    server-side as a BR-AUD-018 attempt row by the exception handler.
    """
    return NotFoundError(audit_br_ref=br_ref)


# ── B12 r1 HTTP-series rows that have NO B12 §3 catalog code ────────────────
def http_series_refusal_body(
    message_key: str, *, br_ref: str, **params: Any
) -> dict[str, Any]:
    """The G1 envelope for a refusal whose status has no catalog code — **413**
    (upload over the cap) and **415** (type outside the allowlist).

    ⚠ **THIS IS THE KERNEL FOLLOW-UP `apps/tenancy/api.py` REPORTED ON
    2026-08-09 AND NOBODY BUILT, arriving the moment a SECOND uploader needed
    it** (`CR-094-BRC01` wave I — account documents). That module's own
    docstring said so in its own words: *"Built here because core.errors'
    handler has no 413 branch and core/ is outside this lane's territory:
    REPORTED as a kernel follow-up."* Two uploaders each composing this dict by
    hand is two places a refusal envelope can drift from the one every other
    status renders, and an envelope that drifts reaches a clerk as silence
    (`DEF-SHL-4092`'s family).

    ⚠ **`code` IS `None` AND IS NEVER AN INVENTED STRING.** `HTTP_STATUS_BY_CODE`
    maps catalog codes to statuses, and 413/415 are not in it — B12 r1 defines
    them as transport rows. Minting a `VAL-…` code to fill the field would make
    a client's `code` switch answer wrongly for two statuses.

    It returns the BODY, not a `Response`, so `core/` stays free of a DRF
    import and each caller sets its own status beside the body it is sending.
    """
    return {
        "code": None,
        "message_key": message_key,
        "params": params,
        "field_errors": [],
        "br_ref": br_ref,
        "trace_id": uuid.uuid4().hex,
    }


# ── DRF validation-detail mapping (framework codes → catalog codes) ─────────
_DRF_CODE_TO_VAL = {
    "required": VAL_REQUIRED,
    "null": VAL_REQUIRED,
    "blank": VAL_REQUIRED,
    "invalid": VAL_FORMAT,
    "incorrect_type": VAL_FORMAT,
    "min_length": VAL_RANGE,
    "max_length": VAL_RANGE,
    "min_value": VAL_RANGE,
    "max_value": VAL_RANGE,
    "max_digits": VAL_RANGE,
    "max_decimal_places": VAL_RANGE,
    "max_whole_digits": VAL_RANGE,
    "invalid_choice": VAL_UNKNOWN_LOOKUP,
    "does_not_exist": VAL_UNKNOWN_LOOKUP,
}


def _field_errors_from_drf(detail: Any) -> list[dict[str, Any]]:
    """Flatten DRF's ValidationError.detail into envelope field_errors[].

    Item shape: {field, code, message_key, params}. Rich params (limits, units)
    come from stories raising core ValidationError directly; this fallback maps
    serializer-level failures so no framework error escapes the envelope.
    """
    items: list[dict[str, Any]] = []
    if isinstance(detail, dict):
        for field, errors in detail.items():
            errors = errors if isinstance(errors, list) else [errors]
            for err in errors:
                code = _DRF_CODE_TO_VAL.get(getattr(err, "code", ""), VAL_FORMAT)
                items.append(
                    {
                        "field": str(field),
                        "code": code,
                        "message_key": default_message_key(code),
                        "params": {},
                    }
                )
    else:  # non-field (list/str) details attach to the whole payload
        errors = detail if isinstance(detail, list) else [detail]
        for err in errors:
            code = _DRF_CODE_TO_VAL.get(getattr(err, "code", ""), VAL_FORMAT)
            items.append(
                {
                    "field": None,
                    "code": code,
                    "message_key": default_message_key(code),
                    "params": {},
                }
            )
    return items


# ── Envelope rendering ──────────────────────────────────────────────────────
def _envelope(
    *,
    code: str | None,
    message_key: str,
    trace_id: str,
    params: dict[str, Any] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
    br_ref: str | None = None,
) -> dict[str, Any]:
    # The one ratified shape (11b §3 G1) — all six keys always present.
    return {
        "code": code,
        "message_key": message_key,
        "params": params or {},
        "field_errors": field_errors or [],
        "br_ref": br_ref,
        "trace_id": trace_id,
    }


def _write_attempt_row(exc: Exception, context: dict[str, Any], trace_id: str) -> None:
    """BR-AUD-018: permission denials and business-rule refusals write an
    attempt row (who/what/when/rule); the refused action itself wrote NOTHING.

    Centralized HERE so no endpoint can forget it (11b §3 G15). Never allowed
    to mask the refusal response — failures log loudly instead of raising.
    """
    from core import audit as core_audit  # local import: breaks the import cycle

    request = context.get("request")
    refused_code: str | None = None
    br_ref: str | None = None
    if isinstance(exc, ApiError) and (exc.code == AUTH_PERMISSION_DENIED or exc.code in BIZ_CODES):
        refused_code, br_ref = exc.code, exc.br_ref
    elif isinstance(exc, (drf_exceptions.PermissionDenied, django_exceptions.PermissionDenied)):
        refused_code = AUTH_PERMISSION_DENIED
    elif isinstance(exc, NotFoundError) and exc.audit_br_ref:
        refused_code, br_ref = AUTH_PERMISSION_DENIED, exc.audit_br_ref  # cross-tenant denial
    if refused_code is None:
        return
    try:
        core_audit.refusal_attempt(
            actor_user_id=_actor_user_id(request),
            code=refused_code,
            br_ref=br_ref,
            method=getattr(request, "method", None),
            path=getattr(request, "path", None),
            trace_id=trace_id,
        )
    except Exception:  # pragma: no cover - defensive: refusal must still be answered
        logger.exception("BR-AUD-018 attempt row failed to write (trace_id=%s)", trace_id)


def _log_refusal(exc: Exception, context: dict[str, Any], trace_id: str) -> None:
    """Every refusal leaves its trace id, its key and its `detail` in the server log.

    ⚠ THIS IS THE OTHER HALF OF THE 2026-08-19 RULING, and without it the ruling
    would have COST support something. `params.detail` is the free text a service
    attaches to a refusal — *"account … has 9 months of billing history and the
    tenant requires 12"* — and until that day it was rendered to the customer.
    It no longer is (BR-SHL-020 r2, DEF-322). The ruling's clause 2 is explicit
    that *"support does not lose the diagnostic — it moves"*, so this is where it
    moved to: one WARNING line per refusal, carrying the trace id support is now
    given on screen.

    ⚠ AND IT IS THE FALLBACK FOR OQ-271. `_write_attempt_row` above returns early
    for anything that is not a permission denial or a `BIZ-*` code, so ten of the
    twelve refusals that print a support reference write NO audit row — meaning
    S61 answers the reference with nothing. That gap was found by the browser
    test, it is a RULE question (an attempt row is defined as a security event;
    a programming error is not one), and it is the PO's to rule. Until they do,
    `grep 5f2b9c1d` over this log answers every printed reference, which is the
    thing the ruling actually requires: *"a shortened id that support cannot look
    up is worse than none."*

    Never raises: a logging failure must not mask the refusal a caller is owed.
    """
    if not isinstance(exc, ApiError):
        return  # non-catalog exceptions are logged where they are handled below
    request = context.get("request")
    try:
        logger.warning(
            "refusal trace_id=%s code=%s key=%s br_ref=%s %s %s detail=%s",
            trace_id,
            exc.code,
            exc.message_key,
            exc.br_ref,
            getattr(request, "method", None),
            getattr(request, "path", None),
            (exc.params or {}).get("detail"),
        )
    except Exception:  # pragma: no cover - defensive
        pass


def _actor_user_id(request: Any) -> Any:
    try:
        # DRF resolves `request.user` LAZILY, by running authentication. When
        # authentication is what refused — the cross-tenant session denial of
        # the 2026-08-10 path ruling is exactly that case — touching it here
        # re-raises the very refusal being recorded. There is no actor to name
        # then, and the attempt row must still be written (BR-AUD-018).
        user = getattr(request, "user", None)
    except Exception:
        return None
    if user is not None and getattr(user, "is_authenticated", False):
        return getattr(user, "id", None) or getattr(user, "pk", None)
    return None


def drf_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """The one DRF exception handler (settings REST_FRAMEWORK.EXCEPTION_HANDLER).

    Every response leaving this function is a row of the B12 r1 HTTP-series
    table carrying the G1 envelope — "a response outside this table = a bug
    by definition."
    """
    trace_id = uuid.uuid4().hex
    headers: dict[str, str] = {}

    _write_attempt_row(exc, context, trace_id)
    _log_refusal(exc, context, trace_id)

    if isinstance(exc, ApiError):
        status, body = exc.http_status, _envelope(
            code=exc.code,
            message_key=exc.message_key,
            params=exc.params,
            field_errors=exc.field_errors,
            br_ref=exc.br_ref,
            trace_id=trace_id,
        )
    elif isinstance(exc, (NotFoundError, Http404, drf_exceptions.NotFound)):
        # One body for absent AND cross-tenant (G4) — no catalog code exists
        # for 404, so code stays null rather than inventing one (G1).
        status, body = 404, _envelope(code=None, message_key="errors.not-found", trace_id=trace_id)
    elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
        status, body = 401, _envelope(
            code=AUTH_UNAUTHENTICATED,
            message_key=default_message_key(AUTH_UNAUTHENTICATED),
            trace_id=trace_id,
        )
    elif isinstance(exc, (drf_exceptions.PermissionDenied, django_exceptions.PermissionDenied)):
        # In-tenant role denial only. Cross-tenant NEVER reaches here — that is
        # deny_as_not_found() by law (G4).
        status, body = 403, _envelope(
            code=AUTH_PERMISSION_DENIED,
            message_key=default_message_key(AUTH_PERMISSION_DENIED),
            br_ref="BR-IDN-009",
            trace_id=trace_id,
        )
    elif isinstance(exc, drf_exceptions.ValidationError):
        field_errors = _field_errors_from_drf(exc.detail)
        top_code = field_errors[0]["code"] if field_errors else VAL_FORMAT
        status, body = 422, _envelope(
            code=top_code,
            message_key=default_message_key(top_code),
            field_errors=field_errors,
            trace_id=trace_id,
        )
    elif isinstance(exc, drf_exceptions.Throttled):
        # 429 + Retry-After per the r1 4xx row.
        if exc.wait is not None:
            headers["Retry-After"] = str(int(exc.wait))
        status, body = 429, _envelope(
            code=None,
            # DEF-SHL-10621: the app limits A1–A4 (`core.throttling.AppThrottled`)
            # say "Too many requests. Wait a moment."; the public doors keep theirs.
            message_key=getattr(exc, "message_key", "errors.rate-limited"),
            params={"retry_after_seconds": int(exc.wait) if exc.wait is not None else None},
            trace_id=trace_id,
        )
    elif isinstance(exc, drf_exceptions.MethodNotAllowed):
        status, body = 405, _envelope(
            code=None, message_key="errors.method-not-allowed", trace_id=trace_id
        )
    elif isinstance(exc, drf_exceptions.UnsupportedMediaType):
        status, body = 415, _envelope(
            code=None, message_key="errors.unsupported-media-type", trace_id=trace_id
        )
    elif isinstance(exc, (drf_exceptions.ParseError, drf_exceptions.NotAcceptable)):
        # 400 malformed request (the r1 table has no 406 row; a negotiation
        # failure is answered as a malformed request rather than off-table).
        status, body = 400, _envelope(
            code=None, message_key="errors.bad-request", trace_id=trace_id
        )
    else:
        # 500 SYS-INTERNAL: trace_id only, no internals leaked (r1 5xx row).
        logger.exception("unhandled exception (trace_id=%s)", trace_id)
        status, body = 500, _envelope(
            code=SYS_INTERNAL,
            message_key=default_message_key(SYS_INTERNAL),
            trace_id=trace_id,
        )

    if status in (401, 403, 404, 409, 422, 429):
        logger.info("refused %s (code=%s trace_id=%s)", status, body["code"], trace_id)
    response = Response(body, status=status)
    for name, value in headers.items():
        response[name] = value
    return response


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-02@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be02_errors.py 29/29✔ · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py) · [path-tenancy lane 2026-08-10] `_actor_user_id` now swallows the exception DRF raises when it resolves `request.user` lazily: since the cross-tenant refusal happens INSIDE authentication, reading the actor re-raises it and the BR-AUD-018 attempt row would never be written. There is no actor to name in that case, and the row must still land
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
