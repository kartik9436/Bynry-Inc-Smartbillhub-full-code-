# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-044 (EP-INT-13) — the inbound door's one route.
#           07-endpoints.md row 25: `POST /integrations/inbound/{key}/{operation}`.
# Rules:    BR-INT-021 (authenticate before the body is trusted) · BR-INT-030
#           (the reply is a declared position) · BR-INT-044 (the allowlist
#           refuses before the body is read, revealing nothing) · BR-INT-045
#           (the status numbers are the manifest's, never typed here) ·
#           BR-INT-058 (the door stops after `dedupe`; the apply is Runbooks') ·
#           BR-TEN-003 (the tenant is the path and nothing else) ·
#           CLAUDE.md hard rule 1 · B14 rule 33 (five or six words) ·
#           B8/LAW 0 (thin views — no logic here)
# Tests:    06-backend/tests/test_us_int_044_inbound_door.py (TC-1..TC-10) ·
#           06-backend/tests/test_be_default_authentication.py (this route is
#           named on the public surface, deliberately)
# Impacts:  config/urls.py (one include line, inside the tenant list) ·
#           apps/integrations/inbound.py (everything this view calls)
# ───────────────────────────────────────────────────────
"""The one door a partner POSTs to — thin, and the same five words when it will not.

    POST /api/{utility}/integrations/inbound/{key}/{operation}

⚠ **AND SINCE 2026-10-07 (`DEF-INT-10020`) THE SAME DOOR HAS A SECOND KIND OF
ADDRESS.** An operation whose manifest declares a `served_path` — US
Payments' three: `/partner/v1/account-lookup`, `/add-payment`, `/add-return` —
is served ONLY at `/api{served_path}`, with no utility in the path: the KEY
opens the utility first (`partner_urls._with_utility_from_key`), then
`partner_door_for` runs exactly this view's body (`_serve`). At the address
below such an operation is refused in the ordinary way and the refusal is
logged with where it moved. An operation with no `served_path` (the generic
kiosk) is served here and only here, exactly as before.

⚠ **THE TENANT IS IN THE PATH, FOR THE REASON WAVE S RECORDED AND FOR ONE
MORE.** `BR-TEN-003` says the tenant is read from the path and from nothing
else, and with no tenant on the session RLS `FORCE` yields zero rows for every
key including a valid one — so a door at a tenant-less address would be
incapable of passing (CLAUDE.md law 7's third shape). The extra reason here is
that this door WRITES: a delivery row landing under no tenant, or under the
wrong one, is somebody else's money in somebody else's book.

⚠ **A PARTNER THAT DICTATES ITS OWN PATHS HAS THEM DECLARED ON ITS
OPERATIONS**, which is why the operation is the last segment rather than a
field in the body. `07-endpoints.md` row 25 says the design's
`POST /integrations/webhooks/{key}` spelling is this same door for a
single-operation provider; the kiosk calls three, so it names which.

⚠ **THIS VIEW OPTS OUT OF THE DEFAULT AUTHENTICATOR, AND IT IS NAMED FOR IT.**
`authentication_classes = []` — a kiosk has no session and never will.
`tests/test_be_default_authentication.py` asserts the public surface EXACTLY,
so this route is added to `PUBLIC_ROUTES` in the same commit; if that test
goes red naming this file, the answer is to name the route there deliberately,
never to widen the assertion.

⚠ **THE REFUSAL IS BUILT IN EXACTLY ONE PLACE.** `serve.REFUSAL_SENTENCE` —
the same five words wave S answers with, from the same constant. An address
off the allowlist, a wrong key, a revoked key, a provider that does not exist
and an operation it does not declare are the same bytes with the same status,
because anything else is an oracle. **It carries no `message_key` and needs
none:** the reader is a machine, not a clerk, so there is no catalogue line
for it in any of the eleven — the same posture `partner_api.py` takes.
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny

from apps.integrations import inbound
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve

logger = logging.getLogger(__name__)

#: The status a refused caller gets. Read off the manifest when we know which
#: one it is, and otherwise this — because a caller presenting a key for a
#: provider that is not connected here must not learn that from a different
#: number (`BR-INT-044`).
#:
#: ⚠ IT IS NOT A NUMBER THIS FILE CHOSE. `_refused_status` below asks the
#: registry first and only falls back when there is no manifest to ask, and
#: the fallback is `serve`'s — one constant, one answer, one grep.
FALLBACK_REFUSED_STATUS = 401


def _refused_status(provider_key: str, operation_name: str) -> int:
    """The declared `refused` number, or the fallback (`BR-INT-045`).

    ⚠ **THE LOOKUP MUST NOT LEAK WHICH PROVIDERS EXIST.** Every manifest that
    declares an inbound operation declares the same `refused` number today, so
    asking the registry cannot separate a real provider from an invented one
    — and when a future manifest declares a different one, the answer is still
    the same for every caller naming THAT provider, which is the property the
    allowlist rule actually requires.
    """
    manifest = REGISTRY.get(provider_key)
    if manifest is not None:
        operation = inbound.operation_named(manifest, operation_name)
        candidates = [operation] if operation is not None else list(manifest.operations)
        for one in candidates:
            declared = (one.envelope_status or {}).get("refused")
            if declared:
                return int(declared)
    return FALLBACK_REFUSED_STATUS


def _refused(provider_key: str, operation_name: str) -> JsonResponse:
    """The ONE body. Five words (B14 rule 33), no code, no trace id.

    ⚠ A `JsonResponse` rather than a DRF `Response` on purpose, exactly as
    `partner_api._refused` explains: DRF's renderer negotiates content and can
    vary the body with an `Accept` header, and a refusal that changes shape
    with a header is a refusal that carries information.
    """
    return JsonResponse(
        {"error": serve.REFUSAL_SENTENCE},
        status=_refused_status(provider_key, operation_name),
    )


def _source_address(request: Any) -> str | None:
    """Imported from identity rather than re-derived.

    ⚠ THE ALLOWLIST IS ONLY AS GOOD AS THIS ANSWER, so it must not be a second
    implementation. `identity.auth.client_ip` honours `X-Forwarded-For` only
    to the depth of `settings.TRUSTED_PROXY_COUNT` (default 0), so a caller
    cannot spoof its own source address by sending the header. A private copy
    here would be one deploy away from disagreeing with that, and the
    disagreement would OPEN the allowlist rather than close it.
    """
    from apps.identity.auth import client_ip

    return client_ip(request)


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def inbound_door(request, key: str, operation: str):
    """`POST /api/{utility}/integrations/inbound/{key}/{operation}` — the
    per-utility address. An operation a manifest PUBLISHES on the partner
    surface (`served_path`) is not answered here; see `_serve`.
    """
    return _serve(request, key, operation, at=None)


def key_scheme_name(header: str) -> str:
    """The OpenAPI security-scheme name for a key presented in `header` —
    `passwordHeader` for US Payments. ONE spelling, imported by
    `core/openapi.py` rather than retyped (`DEF-INT-6529`'s lesson)."""
    return f"{header}Header"


def published_key_schemes() -> dict[str, dict[str, Any]]:
    """`DEF-INT-10020` — a security scheme for every header a PUBLISHED inbound
    operation's key arrives in, read off the registry (`BR-INT-037`).

    Without it the three US Payments addresses would publish `security: [{}]`
    — *this endpoint needs no credentials* — on a door that takes money,
    which is exactly `DEF-INT-6529` one door over.
    """
    schemes: dict[str, dict[str, Any]] = {}
    for manifest in REGISTRY.all():
        if not any(one.served_path and one.applies for one in manifest.operations):
            continue
        try:
            header = inbound.credential_header(manifest)
        except inbound.DoorMisconfigured:
            continue
        schemes[key_scheme_name(header)] = {
            "type": "apiKey",
            "in": "header",
            "name": header,
            "description": (
                f"A key we issued, presented exactly as issued in the `{header}` header "
                "(no `Bearer`). The key names its utility; there is no utility in any "
                "path. A missing, unknown, revoked or expired key, an address the "
                "connection does not allow and a disabled connector all get the same "
                "refusal, in the same time."  # BR-INT-044 — kept out of the published text (G28)
            ),
        }
    return schemes


def partner_door_for(provider_key: str, operation_name: str, served_path: str):
    """`DEF-INT-10020` — the view for ONE operation a manifest publishes at
    `/api{served_path}` (US Payments: `/api/partner/v1/account-lookup`,
    `/add-payment`, `/add-return`).

    The address carries no utility and no vendor (the 2026-09-16 rule): the
    utility was already opened from the KEY by `partner_urls`'s wrapper before
    this view runs, and the provider and operation are fixed by the ROUTE, read
    off the manifest when the route table is built. **Nothing the caller sends
    selects either.** Everything after that is `_serve`, byte for byte the
    path the per-utility address took: live key, identity headers, allowlist,
    rate limit, verb, tender mapping, `409` on a repeated `paymentId`, and
    `apps/payments/agent_door.py` saving the money.
    """

    from drf_spectacular.utils import extend_schema

    manifest = REGISTRY.require(provider_key)
    operation = inbound.operation_named(manifest, operation_name)
    assert operation is not None, (provider_key, operation_name)

    def partner_inbound_door(request, *args: Any, **kwargs: Any):
        return _serve(request, provider_key, operation_name, at=served_path)

    # ⚠ **ONE VERB, THE OPERATION'S OWN — LIKE `make-payment`.** The lookup is
    # a `GET`, the two messages are `POST`s; another verb is DRF's `405`
    # before anything is read, which says nothing about any key.
    partner_inbound_door.__name__ = f"partner_inbound_door_{operation_name}"
    partner_inbound_door.__doc__ = (
        f"`{operation.http_method} /api{served_path}` — {operation.description} "
        "The key in the declared header names the utility; see `partner_door_for`."
    )
    view = permission_classes([AllowAny])(partner_inbound_door)
    view = authentication_classes([])(view)
    view = api_view([operation.http_method])(view)
    return extend_schema(auth=[{key_scheme_name(inbound.credential_header(manifest)): []}])(view)


def _published_elsewhere(manifest, operation_name: str, at: str | None) -> bool:
    """Is this operation answered at a DIFFERENT address than the one called?

    `DEF-INT-10020`. An operation that declares a `served_path` is reached
    ONLY there, so each partner has exactly one address (PO ruling
    2026-10-07, our judgment stated before the go); one that declares none
    (the generic kiosk) is reached only at the per-utility address, exactly as
    before. Data, not a branch on a provider (`BR-INT-037`, `G77`).
    """
    operation = inbound.operation_named(manifest, operation_name)
    if operation is None:
        return False  # `receive` refuses an undeclared operation itself
    return (operation.served_path or None) != at


def _serve(request, key: str, operation: str, *, at: str | None):
    """The door's body, shared by both addresses.

    Everything this view does is: ask `inbound.verify()` what the caller proved
    knowledge of, read the source address, hand the RAW BYTES to
    `inbound.receive()`, and turn what comes back into a response with the
    manifest's own number. No logic (B8 LAW 0) and no status literal
    (`BR-INT-045`).

    ⚠ **`request.body` IS READ AS BYTES AND NOT PARSED HERE.** DRF would parse
    it into `request.data` on access, and that access is the thing
    `BR-INT-021` forbids before authentication. This view never touches
    `request.data`.

    ⚠ **THE BYTES NOW GO TO `verify()` AS WELL, AND THAT IS STILL NOT A PARSE.**
    A signature-verified webhook (SendGrid) proves itself BY the body: there is
    no credential in any header to read. `verify()` hashes those bytes and
    never interprets them — fixed work on any input, no grammar, nothing to
    exhaust — so the property `BR-INT-021` is about is unchanged, and
    `test_the_body_is_hashed_and_never_parsed_before_authentication` asserts it
    by replacing the parser with a recorder.

    ⚠ **`received_at` IS TAKEN ONCE AND USED TWICE.** The replay window and the
    delivery's recorded arrival time must be the same instant: two `now()`
    calls would let a signature age between the check and the record, which is
    a difference nothing could reproduce and nobody would look for.
    """
    manifest = REGISTRY.get(key)
    if manifest is None:
        return _refused(key, operation)
    if _published_elsewhere(manifest, operation, at):
        # ⚠ **`DEF-INT-10020`. THE ORDINARY REFUSAL, BEFORE THE KEY IS READ**
        # — the same place and the same bytes an undeclared operation gets, so
        # a stale caller learns nothing about its key. The log line is the
        # record: it names the connector, the operation and the address it
        # now lives at, and never the key, the body or the source address.
        operation_row = inbound.operation_named(manifest, operation)
        logger.warning(
            "inbound refusal: connector=%s operation=%s called at %s; it is served at %s",
            manifest.key,
            operation,
            "/api/{utility}/integrations/inbound/…" if at is None else f"/api{at}",
            "/api/{utility}/integrations/inbound/…"
            if operation_row is None or operation_row.served_path is None
            else f"/api{operation_row.served_path}",
        )
        return _refused(key, operation)
    received_at = timezone.now()
    try:
        presented = inbound.verify(manifest, request.META, request.body, received_at=received_at)
    except inbound.DoorMisconfigured:
        # OUR manifest is wrong, not their call. Fail closed with the same
        # words rather than telling a caller our configuration is broken.
        return _refused(key, operation)
    try:
        reply = inbound.receive(
            provider_key=key,
            operation_name=operation,
            presented=presented,
            source_address=_source_address(request),
            raw_body=request.body,
            received_at=received_at,
            # `CR-174-BRC10` — the verb, the partner's identity headers and a
            # lookup's query string, all read AFTER authentication inside
            # `receive`. `request.GET` is Django's own parse of the query, not
            # DRF's of the body, so `BR-INT-021`'s ordering is unchanged.
            method=request.method,
            headers=request.META,
            query=request.GET,
        )
    except inbound.DoorRefused:
        return _refused(key, operation)
    except inbound.DoorRateLimited as limited:
        # `CR-110-BRC04` — the one place this door answers something other than
        # the five words, and it is reachable only AFTER authentication. The
        # kiosk network reads the number: `429` means come back, `401` means
        # stop and page somebody, and telling it the wrong one takes a payment
        # machine out of service until a person intervenes.
        response = JsonResponse({"error": serve.REFUSAL_SENTENCE}, status=429)
        response["Retry-After"] = str(limited.retry_after_s)
        return response
    except inbound.DoorMisconfigured:
        return _refused(key, operation)
    if reply.answer is not None:
        # `CR-174-BRC10` — the partner's own words, with money as a JSON
        # NUMBER (`147.85`) and never a float on the way (hard rule 2).
        return HttpResponse(
            inbound.render_answer(reply.answer),
            status=reply.status,
            content_type="application/json",
        )
    return JsonResponse(reply.envelope(), status=reply.status)


urlpatterns = [
    # Four segments, and the first two are literal — so this can never be
    # swallowed by `api.py`'s two-segment `integrations/<str:key>` nor by its
    # four-segment `integrations/<str:key>/oauth/start`, whose third segment is
    # the literal `oauth`. `tests/test_us_int_044_inbound_door.py` resolves the
    # real path rather than reasoning about it.
    path("integrations/inbound/<str:key>/<str:operation>", inbound_door),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-044@wave-N (EP-INT-13) · 07-endpoints.md row 25
# generated: 2026-09-06 by the CR-069 wave N build lane (the door half)
# checklist: A✔ B✔ C✔ D✔ E=n/a(no screen — a kiosk POSTs here; inbound.py's docstring says why) F✔ G✔ H=n/a(the 🔒 half is inbound.py, whose glob is asked of the PO)
# gates: pytest tests/test_us_int_044_inbound_door.py tests/test_be_default_authentication.py · G9 error envelope · G77 (no provider-key branch)
# exceptions: the refusal carries NO message_key and needs none — its reader is a machine, the same posture partner_api.py takes for the same five words
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
