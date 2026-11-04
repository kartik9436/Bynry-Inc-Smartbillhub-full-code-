# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-001 (EP-INT-01) — `GET /integrations`, the grid data source
#           (A11 addendum). US-INT-002 — the four ratified endpoints
#           (`connect · test · PATCH · DELETE`) plus `credential` and `run`
#           (A11 addendum / 07-endpoints.md rows 2–6, 8, 12). US-INT-017 —
#           every write route refuses a coming-soon key with zero secret
#           persistence. US-INT-004 — every lifecycle event audited, masked.
#           US-INT-016 — `test` and `run` answer 202 + poll url.
#           Screens: S8 · S141
# Rules:    BR-INT-002 (the endpoint set) · BR-INT-001 (coming-soon = refused
#           at the API, not only the button) · BR-INT-003 (no credential in
#           any payload — masked refs only) · BR-INT-014 (audit) · BR-INT-037
#           (an unknown key → 404 identical to any absent resource; no
#           provider is named here) · B14 rule 33 (a refusal is ≤ 6 words) ·
#           A4 `settings_lookups` (System Admin Full · Executive View ·
#           Billing Clerk no cell) · CLAUDE.md hard rule 1 (BE-01 tenant
#           context) · B8 / LAW 0 (thin: resolve, ask the service, answer)
# Tests:    06-backend/tests/test_us_int_001_grid.py ·
#           tests/test_us_int_017_gating.py · tests/test_us_int_002_connect.py ·
#           tests/test_us_int_016_queue.py · tests/test_us_int_004_audit.py
# Impacts:  config/urls.py (one include line, unchanged) ·
#           06-backend/openapi/schema.json (re-exported: six new paths)
# ───────────────────────────────────────────────────────
"""integrations API — the read, and the six writes the modal presses (wave B).

THIN by law (B8 / LAW 0): resolve the tenant, ask the service, answer. No
ORM here, no registry walk, no state word chosen — `selectors.grid()` and
`services.*` own all of it, so the same read-model serves this route today
and the notifications provider-status panel later (US-INT-004).

THE ROUTES, AND THE ONE ORDER EVERY WRITE OBEYS
-----------------------------------------------
    GET    /integrations                    the grid: every manifest, this tenant's state
    POST   /integrations/{key}/connect      201 · the card — validate, then write, or nothing
    POST   /integrations/{key}/test         202 · {job_id, status_url} — the row before the message
    PATCH  /integrations/{key}              200 · the card — non-secret settings, audited
    DELETE /integrations/{key}              200 · the card — credentials destroyed, runs kept
    POST   /integrations/{key}/credential   202 (a test queued) or 200 · v(n+1), n deactivated
    POST   /integrations/{key}/run          202 · a manual attempt, never inline
    POST   /integrations/{key}/oauth/start  409 · the redirect's boundary, stated (wave G/H)

Every write does step 1 in `services._live_manifest`: an unknown key is
404 with a body identical to any absent resource (no `code`, G4), and a
coming-soon key is refused with `BIZ-STATE` + `integrations.refusal.
not_available` — six words — and an audit row carrying the key and the wave
and no field. **The database is byte-for-byte unchanged on every refusal**,
which `tests/test_us_int_017_gating.py` reads back as row counts.

⚠ THE STORY NAMED `INT_COMING_SOON` AND `INT_UNKNOWN_KEY` AS "NEW CATALOGUE
CODES", AND THEY ARE MESSAGE KEYS, NOT ENVELOPE CODES (lane judgment,
decision log 2026-09-03). `core/errors.py`'s G1 forbids an endpoint inventing
an envelope code, and a 404 carries no code by law so cross-tenant and absent
read identically; so the coming-soon refusal rides the existing `BIZ-STATE`
with its own message key, and the unknown key is the plain 404.

THE ROLE GATE is A4's `settings_lookups` cell through the one class that
encodes it (`SettingsReadAnyWriteSystemAdmin`, DEF-196): System Admin and
Executive may READ; every write needs System Admin — refused here at 403 AND
again in the service's own `@require_role`. `OQ-INT-1479` (may a clerk press
*Test it now*) is OPEN; Admin-only ships and the modal says so.
"""

from datetime import date
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.integrations import (
    custom_apis,
    gis,
    gis_parcels,
    meter_reading,
    page_policy,
    selectors,
    sending_domain as sending_domain_service,
    services,
)
from core import errors
from core import jobs as core_jobs
from core.permissions import AnyTenantRole, SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant

#: Wave J. A period a clerk did not give us, refused in words rather than
#: as a stack trace. In all eleven catalogues (G15 · G32).
REFUSAL_DATE_REQUIRED = "integrations.refusal.date_required"


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape: id from the session
    user, role server-attached by the identity layer (BE-04) — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _as_api_error(refusal: Any) -> Any:
    """A `gis.GisRefusal` as the error class its own code belongs to.

    `BizError` accepts only `BIZ-*` and `ValidationError` only `VAL-*`; handing
    either the other's code raises inside the handler, and the clerk gets a 500
    where a sentence was written for them.
    """
    if refusal.code in errors.VAL_CODES:
        return errors.ValidationError(refusal.code, message_key=refusal.message_key)
    return errors.BizError(
        refusal.code, br_ref=refusal.br_ref, message_key=refusal.message_key,
        params=refusal.params,
    )


def _actor_name(request: Any) -> str | None:
    """The signed-in person's name, for a run that records who started it.

    ⚠ **IT READS `request.user` AND NOT `_actor(request)`, AND THE SECOND ONE
    WAS THE FIRST DRAFT.** `_actor` builds a namespace of exactly two fields —
    `id` and `role` — so a name read off it is `None` on EVERY request, for
    every user, for ever. `gis.reconcile` refuses an unnamed person, so the
    first draft refused every run a person started: a control that could never
    once succeed (hard-won law 7, *incapable of passing*). It was caught by
    calling the route rather than by any test asserting the namespace.

    ⚠ **NEVER THE BODY'S.** `CR-115-BRC05` R31 asks a run to record *schedule |
    person + their name*; a name a client could send is a name a client could
    invent, and the whole value of the column is that the answer to *who ran
    this* is not the caller's to choose.

    `full_name` first, because it is what a colleague would say; the email is
    the fallback because `identity.User.full_name` defaults to `""` and reads
    as a dash for an invited user who has not finished signing up. `None` only
    when the request carries no user at all.
    """
    user = getattr(request, "user", None)
    for attribute in ("full_name", "email"):
        found = str(getattr(user, attribute, "") or "").strip()
        if found:
            return found
    return None


def _payload(request: Any) -> dict[str, Any]:
    """The JSON body as a mapping. A body that is not an object is a
    contract violation, refused with the catalogue's shape code (G9)."""
    data = getattr(request, "data", None)
    if data is None or data == "":
        return {}
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="integrations.refusal.fields")
    return dict(data)


def _file_bytes(request: Any) -> bytes:
    """The bytes AS THEY ARRIVED — a multipart `file` part, or the raw body.

    ⚠ NEVER `request.data` FOR THE CONTENT AND NEVER A DECODE. A parser that
    turns the upload into text has already chosen an encoding, and the hash
    this product refuses duplicates on has to be of the bytes the bank sent
    (`BR-INT-020` C). `.read()` on the uploaded file and `request.body` are
    both `bytes`; nothing between here and `hashlib` looks inside them.
    """
    files = getattr(request, "FILES", None)
    if files:
        part = files.get("file") or next(iter(files.values()), None)
        if part is not None:
            return part.read()
    # ⚠ **NO VIRUS SCAN, ON EITHER SHAPE — PO 2026-09-22 and 2026-09-23.** This
    # raw-body branch scanned by hand from 2026-09-13 (`BR-SHL-253`), because
    # a raw body never reached the middleware that scanned multipart parts. The
    # PO removed the scan, so both branches hand back the bytes as they arrived
    # (`DEF-SHL-6347`).
    return getattr(request, "body", b"") or b""


def _date_field(body: dict[str, Any], name: str) -> date:
    """One ISO date off the body, or a refusal a clerk can read.

    ⚠ **PARSED HERE AND NOWHERE DEEPER (`CR-069` wave J).**
    `departures.export_key` refuses a string ON PURPOSE — two spellings of one
    July are two keys, and a `date` is the only shape with one spelling. That
    refusal is a `TypeError`, which is right for a programming mistake and
    wrong for a clerk who typed a bad date, so the HTTP boundary is where the
    string becomes a date and where a bad one becomes a 400.
    """
    raw = body.get(name)
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=REFUSAL_DATE_REQUIRED,
            params={"field": name},
        ) from None


def _operation_name(request: Any) -> str:
    """Which file operation the upload arrived for.

    A multipart form carries it beside the file; a raw-body POST carries it in
    the query string. Both are read, the form first, because that is the one a
    screen sends.
    """
    data = getattr(request, "data", None)
    if hasattr(data, "get"):
        named = data.get("operation")
        if isinstance(named, str) and named.strip():
            return named.strip()
    return str((getattr(request, "GET", {}) or {}).get("operation") or "").strip()


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups: Admin Full · Exec View
def integrations_grid(request: Any) -> Response:
    """`GET /integrations` — seventeen cards from the registry, this tenant's state.

    Under the request's tenant context (BE-01) RLS FORCE already hides every
    other tenant's rows; the selector's own `tenant_id` filter is the second
    guard. The payload carries `credential.hint` (`••••3F9A`) and never a
    payload — the credential table's encrypted column is not even read.
    """
    tenant_id = require_tenant(request)
    return Response(selectors.grid(tenant_id))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def connect(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/connect` → 201 and the card.

    Body: `{environment, cadence, label?, fields: {name: value}}` — the
    modal's one mapping. The service splits it by the manifest's field kinds,
    validates BOTH halves before any write, and stores nothing on a refusal.
    """
    tenant_id = require_tenant(request)
    body = _payload(request)
    services.connect_with_fields(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        environment=str(body.get("environment") or ""),
        cadence=str(body.get("cadence") or "manual"),
        label=(body.get("label") or None),
        fields=dict(body.get("fields") or {}),
    )
    return Response(selectors.provider_card(tenant_id, key), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def test(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/test` → 202 + `{job_id, status_url}`.

    Body: `{recipient?}` — the typed address a mail test sends to. The `jobs`
    row exists before the broker message and before this reply.
    """
    tenant_id = require_tenant(request)
    record = services.request_test(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        recipient=_payload(request).get("recipient"),
    )
    return Response(core_jobs.accepted(record), status=status.HTTP_202_ACCEPTED)


@api_view(["PATCH", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def connection(request: Any, key: str) -> Response:
    """`PATCH /integrations/{key}` (non-secret settings) · `DELETE` (disconnect)."""
    tenant_id = require_tenant(request)
    if request.method == "DELETE":
        services.disconnect(actor=_actor(request), tenant_id=tenant_id, provider_key=key)
    else:
        services.update_connection(
            actor=_actor(request),
            tenant_id=tenant_id,
            provider_key=key,
            changes=_payload(request),
        )
    return Response(selectors.provider_card(tenant_id, key))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def credential(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/credential` — rotate. 202 when a test was
    queued behind it, 200 with the card otherwise."""
    tenant_id = require_tenant(request)
    _row, record = services.rotate_credential(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        fields=dict(_payload(request).get("fields") or {}),
    )
    if record is not None:
        return Response(core_jobs.accepted(record), status=status.HTTP_202_ACCEPTED)
    return Response(selectors.provider_card(tenant_id, key))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def credential_rollback(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/credential/rollback` — the previous version
    active again in one row, and nobody re-authorises (US-INT-024).

    Answers the CARD, not the credential: the screen wants the connection's
    new word (*Not tested yet*) and the refreshed history, and a credential
    row is not a thing this API ever serves.
    """
    tenant_id = require_tenant(request)
    services.rollback_credential(actor=_actor(request), tenant_id=tenant_id, provider_key=key)
    return Response(selectors.provider_card(tenant_id, key))


@api_view(["POST", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def partner_key(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/key` — issue or replace · `DELETE` — revoke.

    ⚠ **THE `POST` BODY IS THE ONLY TIME THE KEY IS EVER RENDERED, ANYWHERE.**
    It is not in `GET /integrations`, not on the card, not in the audit row,
    not in a run row and not in any error message; `selectors` serves the
    four-character hint and nothing else, and no route re-reads it, because
    there is nothing stored to re-read (`machine_auth`'s module docstring).
    If the person who pressed the button loses this response, the answer is to
    issue another key — which is what pressing the button again does.

    `DELETE` answers the CARD rather than the credential, the shape
    `credential/rollback` already established: what the screen wants back is
    the connection's new state and the refreshed key list.
    """
    tenant_id = require_tenant(request)
    if request.method == "DELETE":
        services.revoke_partner_key(
            actor=_actor(request), tenant_id=tenant_id, provider_key=key
        )
        return Response(selectors.provider_card(tenant_id, key))
    # `CR-110-BRC04` — WHICH OF OUR APIS THIS KEY MAY CALL, from the body.
    #
    # ⚠ **AN ABSENT `scope` IS NOT "EVERYTHING", IT IS A REFUSAL.** The
    # blueprint draws *"Leave blank for everything the key allows"* under its
    # Scope box and the CR refuses it under hard-won law 3 — the unsafe option
    # must be the one you type. `machine_auth._validated_scope` raises on an
    # empty list, so this route does NOT need to default it and deliberately
    # does not: a default here would be a second opinion about the same
    # question, and the two would drift.
    row, minted = services.issue_partner_key(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        scope=request.data.get("scope"),
    )
    return Response(
        {
            "key": minted,  # once, and never again
            "hint": row.masked_hint,
            "version": row.version,
            "issued_at": row.created_at,
            "scope": list(row.scope or []),
            "card": selectors.provider_card(tenant_id, key),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def run(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/run` → 202.

    Body: `{operation, work?: [...], parameters?: {...}, window?: {from, to},
    request_key?}`. The last three are wave K's (`CR-069`): what the request
    states, the span a walk covers, and the key a partner-state write may only
    be made once under. All three are OPTIONAL and an operation that needs none
    is unchanged — which is what let the water meter cloud arrive without a
    single edit to this view's contract for the six providers before it.
    """
    tenant_id = require_tenant(request)
    body = _payload(request)
    record = services.request_run(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        operation=str(body.get("operation") or ""),
        work=list(body.get("work") or []),
        parameters=dict(body.get("parameters") or {}),
        window=dict(body.get("window") or {}),
        request_key=(str(body["request_key"]) if body.get("request_key") else None),
    )
    return Response(core_jobs.accepted(record), status=status.HTTP_202_ACCEPTED)


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def departure(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/export` — a period was asked for on this connection.

    Body: `{operation, period_start, period_end, target}`. Answers **201** when
    the window has not gone out on this connection before and **409** when it
    has, with the sentence naming the first handover by date. An unregistered
    format is refused **422** by name with the list of what this connection
    offers, before a run row exists at all.

    ⚠ THE MIRROR OF `arrival` BELOW, AND THE 409 IS THE SAME ARGUMENT. A second
    handover of July is a REFUSAL a clerk has to see and act on — *did I export
    July twice?* — and answering 200 with a quiet flag is how an ERP books a
    month's revenue twice with nothing going red. The run row is written either
    way, so the second request is never invisible.

    ⚠ AND 422 RATHER THAN 409 FOR THE FORMAT, WHICH IS NOT A DETAIL. A
    duplicate is a state of the world; an unregistered format is a bad request,
    and it leaves no row because nothing was ever a handover (`BR-INT-031` —
    inbound degrades, outbound refuses). ⚠ **422 and not 400**: `core/errors.py`
    maps the whole VAL class to 422 (IS-7, `OQ-004`'s closure), so every
    validation refusal in this product answers 422 and this endpoint is not an
    exception. This docstring said 400 until it was read against the running
    server.

    ⚠ THE RESPONSE CARRIES NO FIGURE AND NO FILE. It carries the run's trace
    id, the export key, and the refusal sentence — because what is IN the file
    is Runbooks' (`BR-INT-054`, `CR-069` §20.4) and this door does not know it.
    """
    tenant_id = require_tenant(request)
    body = _payload(request)
    result = services.request_export(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        operation=_operation_name(request),
        period_start=_date_field(body, "period_start"),
        period_end=_date_field(body, "period_end"),
        target=str(body.get("target") or ""),
    )
    payload = {
        "accepted": result.accepted,
        "export_key": result.export_key,
        "trace_id": result.run.trace_id,
        "outcome": result.run.outcome,
        "summary": result.run.summary,
    }
    return Response(
        payload,
        status=status.HTTP_201_CREATED if result.accepted else status.HTTP_409_CONFLICT,
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def arrival(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/arrival` — a file landed on this connection.

    Multipart with a `file` part, or a raw body; `operation` names which of the
    provider's file operations it arrived for. Answers **201** when the file is
    new and **409** when these exact bytes have arrived on this connection
    before, with the sentence that names the first arrival by day and time.

    ⚠ 409 AND NOT 200. A duplicate is a REFUSAL a clerk has to see and act on —
    *did Wednesday's upload go in twice?* — and answering 200 with a quiet flag
    is how a second application of a bank file becomes invisible. The run row
    is written either way, so the arrival itself is never lost.

    ⚠ THE RESPONSE CARRIES NO FILE CONTENT AND NO CREDENTIAL. It carries the
    run's trace id, the content hash, and the refusal sentence — which is what
    S142 draws and what a clerk reads down the phone.
    """
    tenant_id = require_tenant(request)
    body = _file_bytes(request)
    operation = _operation_name(request)
    result = services.receive_file(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        operation=operation,
        body=body,
    )
    payload = {
        "accepted": result.accepted,
        "content_hash": result.input_hash,
        "trace_id": result.run.trace_id,
        "outcome": result.run.outcome,
        "summary": result.run.summary,
    }
    return Response(
        payload,
        status=status.HTTP_201_CREATED if result.accepted else status.HTTP_409_CONFLICT,
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def oauth_start(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/oauth/start` → `{authorize_url, state}`.

    ⚠ THIS ROUTE REFUSED EVERY CALL UNTIL 2026-09-06 and its docstring said so.
    Wave H built the round trip, so the refusal went in the same commit — a
    control still refusing over a screen that has landed is the mirror of
    hard-won law 2 and costs more than dead UI, because every check passes over
    it (DEF-CWP-3925).

    The body carries `redirect_uri`: the address the provider brings the person
    back to. It is the CALLER's because the front end knows its own origin and
    the server does not — a hardcoded one here would work on the demo host and
    silently send every production sign-in to the wrong place.
    """
    tenant_id = require_tenant(request)
    body = _payload(request)
    return Response(
        services.start_oauth(
            actor=_actor(request),
            tenant_id=tenant_id,
            provider_key=key,
            redirect_uri=str(body.get("redirect_uri") or ""),
        )
    )


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def oauth_return(request: Any, key: str) -> Response:
    """`GET /integrations/{key}/oauth/return?code=…&state=…` — the trip back.

    Answers the CARD, exactly as `credential_rollback` does and for the same
    reason: the screen wants the connection's new word and its refreshed
    history, and a credential row is not a thing this API ever serves.

    ⚠ **GET, because a provider redirects a BROWSER here** — it is not our
    form post. The `state` nonce minted at `start` is what makes that safe, and
    `oauth.complete` refuses before exchanging the code when it does not match.
    """
    tenant_id = require_tenant(request)
    services.complete_oauth(
        actor=_actor(request),
        tenant_id=tenant_id,
        provider_key=key,
        code=str(request.query_params.get("code") or ""),
        state=str(request.query_params.get("state") or ""),
    )
    return Response(selectors.provider_card(tenant_id, key))


# ═══════════════════════════════════════════════════════════════════════════
# CR-069 wave M — the address search, the write, and the page policy
# ═══════════════════════════════════════════════════════════════════════════


def _gis_or_404(key: str) -> None:
    """Every other provider key is an absent resource, byte-identically.

    `BR-INT-037` — no provider is named in a branch anywhere else, and this is
    a route bound to ONE operation shape rather than to a provider: the key in
    the path is checked against the module that serves it and anything else is
    the plain 404 any absent resource gets (G4: no `code` on a 404).
    """
    if key != gis.PROVIDER_KEY:
        raise errors.NotFoundError()


@api_view(["GET"])
# ⚠ **`AnyTenantRole`, AND THE SETTINGS CLASS BESIDE IT WAS A REAL BUG
# (`DEF-INT-4267`).** These two routes sit among the connect/test/credential
# routes, every one of which is genuinely a SETTINGS surface — so they were
# given the same class by proximity. `SettingsReadAnyWriteSystemAdmin` allows
# `{system_admin, executive}` to READ, because A4's `settings_lookups` row
# gives a **Billing Clerk no cell at all**. But this is not settings: it is
# the premises create form, and `metering.services.create_premises` carries
# `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` (`BR-MET-035`). So the clerk
# this screen exists for was refused the search outright, the panel caught the
# 403, decided the tenant had no City and removed itself — the feature simply
# did not exist for her, in silence.
# `POST /premises` in `apps/metering/api.py` is `AnyTenantRole` for exactly
# this reason and lets the service re-gate; these follow it, so the write
# still refuses twice.
@permission_classes([AnyTenantRole])
def address_search(request: Any, key: str) -> Response:
    """`GET /integrations/gis_esri/address-search?q=&session=` → 200, INLINE.

    ⚠ **200 AND NOT 202.** Every other provider call in this API answers `202`
    with a job id and a poll url; this one answers the candidates themselves,
    because `C15` says an inline operation is *a latency budget, not a job*.
    There is no `core.jobs` row to poll and no progress for a screen to draw.

    **Nothing is written** (`C16`, disposition `offer`). The reply carries
    `reachable: false` and a `message_key` when the City is not answering, so
    the screen draws frame 66.2's amber box rather than a red error — the City
    being slow is not the clerk doing something wrong.
    """
    _gis_or_404(key)
    tenant_id = require_tenant(request)
    try:
        return Response(
            gis.search(
                tenant_id,
                query=str(request.query_params.get("q") or ""),
                session_id=(request.query_params.get("session") or None),
            )
        )
    except gis.GisRefusal as refusal:
        raise errors.BizError(
            refusal.code, br_ref=refusal.br_ref, message_key=refusal.message_key,
            params=refusal.params,
        ) from refusal


@api_view(["GET"])
# `AnyTenantRole` — the premises and unit screens a Billing Clerk works on ask
# it (gap 9), and it discloses a state word and nothing else (`gis.city_state`).
@permission_classes([AnyTenantRole])
def gis_state(request: Any, key: str) -> Response:
    """`GET /integrations/gis_esri/state` → `{state, message_key}` (PO GIS review
    gaps 9 and 12, 2026-10-07).

    `none` hides the City's fields; `broken` keeps them and says why in one
    sentence; `working` says nothing. Reads the connection row, dials nothing.
    """
    _gis_or_404(key)
    return Response(gis.city_state(require_tenant(request)))


@api_view(["POST"])
# `AnyTenantRole` — the premises form a Billing Clerk works on asks it, for the
# reason `address_search` gives (`DEF-INT-4267`). It writes nothing.
@permission_classes([AnyTenantRole])
def gis_check_address(request: Any, key: str) -> Response:
    """`POST /integrations/gis_esri/check-address` → 200 `{result, match,
    session, message_key}` — `CR-177-BRC10` task 2, ONE request per press of
    *Check address*. Body `{address_line, city, state, postal_code}`. See
    `gis.check_address` for the four results. Nothing is written."""
    _gis_or_404(key)
    tenant_id = require_tenant(request)
    body = _payload(request)
    return Response(
        gis.check_address(
            tenant_id,
            address_line=body.get("address_line"),
            city=body.get("city"),
            state=body.get("state"),
            postal_code=body.get("postal_code"),
        )
    )


@api_view(["POST"])
# `AnyTenantRole` — the move-in / move-out reading box a Billing Clerk fills
# asks it, for `gis_check_address`'s reason. It writes nothing.
@permission_classes([AnyTenantRole])
def meter_reading_fetch(request: Any) -> Response:
    """`POST /integrations/meter-reading/fetch` → 200 `{result, reading,
    message_key}` — DEF-CUS-10050, ONE request per press of *Fetch reading*.
    Body `{meter_no, as_of?}` (`as_of` = `YYYY-MM-DD`: the reading on or last
    before that day; absent = the latest). See `meter_reading.fetch` for the
    four results. Nothing is written."""
    tenant_id = require_tenant(request)
    body = _payload(request)
    return Response(
        meter_reading.fetch(
            tenant_id,
            meter_no=body.get("meter_no"),
            as_of=meter_reading.parse_as_of(body.get("as_of")),
        )
    )


@api_view(["POST"])
# `AnyTenantRole` — `DEF-INT-4267`, and see the note on `address_search`. The
# write is re-gated by `metering.services.create_premises`'s own
# `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`, so removing either guard still
# leaves it refused for every other role.
@permission_classes([AnyTenantRole])
def gis_premises(request: Any, key: str) -> Response:
    """`POST /integrations/gis_esri/premises` → 201 and the premises.

    Body: `{parcel?, session?, premises: {...}}`. With a `parcel` the City is
    asked again at this moment (`C16`); without one the address is taken as
    typed and the row is marked unchecked (`OQ-INT-1471`, ruled option (b)).

    ⚠ **THE WRITE IS INTEGRATIONS' AND THAT IS A DATED RULING**, not an
    oversight: `OQ-INT-1728` was ruled option (a) on 2026-09-06 — a record
    update a person makes synchronously on a screen stays with the module that
    owns the screen.
    """
    _gis_or_404(key)
    tenant_id = require_tenant(request)
    body = _payload(request)
    try:
        premises = gis.create_premises(
            _actor(request),
            tenant_id,
            parcel=(str(body.get("parcel")).strip() if body.get("parcel") else None),
            typed=dict(body.get("premises") or {}),
            session_id=(body.get("session") or None),
            # `DEF-MET-10013` — which ROW was picked, when a building and its
            # units share the parcel. Absent from an older screen.
            point=(str(body.get("point")).strip() if body.get("point") else None),
        )
    except gis.GisRefusal as refusal:
        raise errors.BizError(
            refusal.code, br_ref=refusal.br_ref, message_key=refusal.message_key,
            params=refusal.params,
        ) from refusal
    return Response(premises, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups
def gis_reconcile(request: Any, key: str) -> Response:
    """`POST /integrations/gis_esri/reconcile` → 200 and the report itself.

    Body: `{mode: "preview" | "apply"}`. **`preview` is what a missing mode
    means** — hard-won law 3, the unsafe option is the one somebody types.

    ⚠ **THE ROUTE DID NOT EXIST AND THE RUN HAD NO CALLER (`DEF-INT-5601`).**
    `CR-112` reported the sync as *"callable and tested, not yet exposed"*; this
    is the exposure. PO ruling R31 of 2026-09-17, verbatim: *"i dont have Run
    button here"*.

    ⚠ **200 AND NOT 202, WHICH IS THE OPPOSITE OF `POST /integrations/{key}/run`
    ON THIS SAME FILE, AND THE REASON IS THE REPORT.** That route enqueues and
    hands back a job id and a poll url; a `core.jobs` record carries a
    `result_link` and no payload, so a clerk pressing *Preview* to find out what
    a reconciliation WOULD do would be handed a link to nothing. The thing being
    asked for here is the answer, so the answer is what comes back. The
    scheduled, unattended form of the same run is Runbooks' (`BR-INT-054`) and
    is not this route.

    ⚠ **`started_by` IS TAKEN FROM THE REQUEST AND NEVER FROM THE BODY.** A
    client that could name the person could name somebody else; the name is the
    signed-in user's, and a run with no user on the request is refused rather
    than recorded as anonymous.

    ⚠ **`pages` — `?pages=3` or `{"pages": 3}` (`DEF-INT-9849`, PO GIS review
    gap 3).** A PREVIEW stops after that many of the City's pages and says so;
    with none given a preview reads `gis.MANUAL_PREVIEW_PAGES` (3), because the
    whole register at Ann Arbor's size outlasts this worker's 60 seconds and the
    clerk got nothing at all. An APPLY with `pages` is refused (all or nothing);
    an APPLY without it reads the whole register, exactly as before. The query
    string wins over the body, so a hand-typed test URL means what it says.
    """
    _gis_or_404(key)
    tenant_id = require_tenant(request)
    body = _payload(request)
    actor = _actor(request)
    mode = str(body.get("mode") or gis_parcels.PREVIEW)
    asked = request.query_params.get("pages")
    if asked is None:
        asked = body.get("pages")
    if asked is None and mode == gis_parcels.PREVIEW:
        asked = gis.MANUAL_PREVIEW_PAGES
    try:
        return Response(
            gis.reconcile(
                actor,
                tenant_id,
                mode=mode,
                started_by=gis_parcels.BY_PERSON,
                started_by_name=_actor_name(request),
                max_pages=asked,
            )
        )
    except gis.GisRefusal as refusal:
        # ⚠ **A REFUSAL IS RAISED AS THE CLASS ITS CODE BELONGS TO, AND THE
        # FIRST DRAFT WRAPPED EVERY ONE IN `BizError`** — which allows only the
        # `BIZ-*` codes, so a `VAL-*` refusal raised a `ValueError` INSIDE the
        # handler and reached a clerk as a **500 with no message at all**. The
        # two routes above can wrap unconditionally because every refusal they
        # raise is `BIZ_STATE`; this one carries both classes, so it asks.
        raise _as_api_error(refusal) from refusal


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def page_policy_view(request: Any) -> Response:
    """`GET /integrations/page-policy` — the generated Content-Security-Policy.

    ⚠ **`AllowAny`, AND `page_policy.py`'s DOCSTRING CARRIES THE REASONING.**
    In one sentence: a document is served before anybody signs in, an SPA does
    not reload after sign-in, so a policy computed from a session would be
    computed once on the login page with no hosts in it and the map would be
    blocked for the rest of the session by a policy that was correct when it
    was made. What this discloses is the set of hosts the browser is about to
    be told to fetch from — a fact any viewer reads out of their own developer
    tools a second later — and no credential, count, name or row.

    Read by `07-frontend/server.mjs`, which puts the value on the DOCUMENT
    response. A header on this JSON governs nothing a browser enforces; the
    document's does.
    """
    tenant_id = require_tenant(request)
    return Response(page_policy.described(tenant_id))



@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups
def sending_domain(request: Any, key: str) -> Response:
    """`GET|POST /integrations/{key}/sending-domain` — the DNS records, and who is waiting.

    **`GET` never dials and always answers.** It serves what we last stored,
    plus the one record we can always give (DMARC, which no ESP issues), so a
    panel opens on a connector nobody has checked yet — which is the state every
    utility is in on the day the clock starts.

    **`POST` is the press that asks the provider**, through the guard like every
    other dial in this module, and answers the same shape.

    ⚠ **200 AND NOT 202, LIKE `reconcile` AND UNLIKE `run`.** A person is
    looking at a panel and the thing they asked for IS the answer; a `core.jobs`
    record carries a `result_link` and no payload, so a clerk pressing *Check*
    would be handed a link to nothing. The operation declares a latency budget
    for exactly this (`C15`).

    ⚠ **THE LONG POLE IS THEIRS, NOT OURS** — PO 2026-09-17: the utility's IT
    team takes *"one to three weeks"* and Production waits on them. Which is why
    `GET` gives away everything it can before anybody presses anything.
    """
    tenant_id = require_tenant(request)
    if request.method == "POST":
        return Response(
            sending_domain_service.check_now(
                actor=_actor(request), tenant_id=tenant_id, provider_key=key
            )
        )
    return Response(sending_domain_service.described(tenant_id, key))


# ═══════════════════════════════════════════════════════════════════════════
# CR-115-BRC05 §7 — the per-API table and form
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE ARE THE ROUTES `CR-115-BRC05` §3 RISK 1 WARNS ABOUT, AND THEY GO
# DELIBERATELY *ROUND* `PATCH /integrations/{key}`.** That route's save path
# prunes `config` to what the manifest still declares — which is `DEF-INT-5582`,
# the defect that broke the PO's allowed addresses — so per-API rows kept in
# `config` would be **silently deleted by the next Edit save**. Their own table
# cannot be pruned by a field validator. The risk the CR names is real; the
# answer to it is a different door rather than a more careful use of that one.
#
# ⚠ **AND THE PROOF IS A BROWSER, NOT A PASSING TEST.** §7.6: *"Prove a save
# works in a BROWSER, not with a passing test."* See
# `10-scripts/cr115_custom_apis_walkthrough.mjs`.


def _connection_or_refuse(tenant_id: Any, key: str) -> Any:
    """The connection these rows hang off, or the refusal a clerk reads.

    ⚠ **THE ROWS ARE PER UTILITY BECAUSE THE CONNECTION IS** (§7.6 — *"Two
    utilities on the same connector configure it independently"*). Every read
    and write below starts here, so the tenant scoping is one line rather than
    four, and under the request's tenant context RLS FORCE is the second guard
    (CLAUDE.md hard rule 1).
    """
    row = services.connection_for(tenant_id, key)
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-002",
            message_key=services.REFUSAL_NOT_CONNECTED,
        )
    return row


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def custom_api_list(request: Any, key: str) -> Response:
    """`POST /integrations/{key}/apis` — add one custom API (§7.3's form).

    Answers the CARD, which is what the screen re-renders: the new row is in
    `operations[]` and the Kind has left `custom_api_kinds`, both from the one
    read the page already knows how to draw. Answering the ROW would make the
    screen splice it in by hand and then disagree with the next fetch about
    whether the dropdown still offers that Kind.
    """
    tenant_id = require_tenant(request)
    body = _payload(request)
    custom_apis.add(
        actor=_actor(request),
        connection=_connection_or_refuse(tenant_id, key),
        kind=str(body.get("kind") or ""),
        name=body.get("name"),
        url=body.get("url"),
    )
    return Response(selectors.provider_card(tenant_id, key))


@api_view(["PATCH", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def custom_api_detail(request: Any, key: str, api_id: str) -> Response:
    """`PATCH /integrations/{key}/apis/{id}` — rename, re-point, or switch ·
    `DELETE` — remove a custom API.

    ⚠ **ONE PATCH FOR BOTH THE EDIT AND THE SWITCH, AND THE SERVICE KEEPS THEM
    APART.** `enabled` is legal on a STANDARD row and `name`/`url` are not
    (R36 — *"standard APis those will be availabel for enable diable but those
    will not be editable"*), so `custom_apis.edit` refuses a standard row by
    name while `custom_apis.switch` accepts one. Splitting the route instead
    would put that rule in the URL, where nothing enforces it.
    """
    tenant_id = require_tenant(request)
    connection = _connection_or_refuse(tenant_id, key)
    if request.method == "DELETE":
        custom_apis.remove(actor=_actor(request), connection=connection, row_id=api_id)
        return Response(selectors.provider_card(tenant_id, key))
    body = _payload(request)
    if "enabled" in body:
        custom_apis.switch(
            actor=_actor(request),
            connection=connection,
            row_id=api_id,
            enabled=bool(body["enabled"]),
        )
    if "name" in body or "url" in body:
        custom_apis.edit(
            actor=_actor(request),
            connection=connection,
            row_id=api_id,
            name=body.get("name"),
            url=body.get("url"),
        )
    return Response(selectors.provider_card(tenant_id, key))


@api_view(["PATCH"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def standard_api_switch(request: Any, key: str, operation_name: str) -> Response:
    """`PATCH /integrations/{key}/apis/standard/{operation}` — the switch on an
    API that ships with the connector.

    ⚠ **A SEPARATE ROUTE BECAUSE A STANDARD API HAS NO ROW UNTIL NOW.** Absence
    means ON (`custom_apis.is_enabled`), so there is no id to address until
    somebody first disagrees with that default — and inventing one so the two
    switches could share a URL would mean writing a row per operation per
    connection at migration time, for the sake of a tidier route.

    ⚠ **THE OPERATION NAME IS NOT A DATABASE ID AND IS NEVER RENDERED** (B14
    rule 31). It is the manifest's own name — the same string `…/runs` and the
    catalogue stem already use in a URL.
    """
    tenant_id = require_tenant(request)
    custom_apis.switch(
        actor=_actor(request),
        connection=_connection_or_refuse(tenant_id, key),
        operation_name=operation_name,
        enabled=bool(_payload(request).get("enabled")),
    )
    return Response(selectors.provider_card(tenant_id, key))


urlpatterns = [
    path("integrations", integrations_grid),
    # ── CR-069 wave M (US-INT-042) ────────────────────────────────────────
    # ⚠ **`integrations/page-policy` IS ABOVE `integrations/<str:key>` AND HAS
    # TO BE.** Django matches this list IN ORDER and both are two segments, so
    # the catch-all would read `page-policy` as a provider key and answer 405
    # — which is exactly the collision `config/urls.py`'s own comment records
    # for `integrations/subprocessors`, found by a browser and not by
    # reasoning. `tests/test_us_int_042_gis.py` resolves this path through the
    # real URLconf so a future insertion above it cannot pass silently.
    path("integrations/page-policy", page_policy_view),
    # DEF-CUS-10050 — above `integrations/<str:key>/…` for the reason above.
    path("integrations/meter-reading/fetch", meter_reading_fetch),
    path("integrations/<str:key>/address-search", address_search),
    path("integrations/<str:key>/state", gis_state),
    path("integrations/<str:key>/check-address", gis_check_address),  # CR-177-BRC10
    path("integrations/<str:key>/premises", gis_premises),
    # `CR-115-BRC05` R31 — Run now. ⚠ **ABOVE `integrations/<str:key>`**,
    # like every other two-segment route on this list: Django takes the
    # first match, and `<str:key>` would read `reconcile` as a provider key.
    path("integrations/<str:key>/reconcile", gis_reconcile),
    # ── `CR-115-BRC05` §7 · the per-API table and form ─────────────────────
    # ⚠ **ALL THREE ABOVE `integrations/<str:key>`**, for the reason stated
    # twice already on this list: Django takes the FIRST match, so `<str:key>`
    # would read `apis` as a provider key and answer a POST with the connection
    # route's PATCH/DELETE. The most specific path comes first.
    path("integrations/<str:key>/apis/standard/<str:operation_name>", standard_api_switch),
    path("integrations/<str:key>/apis/<str:api_id>", custom_api_detail),
    path("integrations/<str:key>/apis", custom_api_list),
    path("integrations/<str:key>/connect", connect),
    path("integrations/<str:key>/test", test),
    # `CR-115-BRC05` §7 — domain verification, the long pole. ⚠ **ABOVE
    # `integrations/<str:key>`**, like every other multi-segment route on this
    # list: Django takes the first match and `<str:key>` would read
    # `sending-domain` as a provider key and answer it with the connection
    # route's PATCH/DELETE.
    path("integrations/<str:key>/sending-domain", sending_domain),
    path("integrations/<str:key>/credential/rollback", credential_rollback),
    path("integrations/<str:key>/credential", credential),
    # CR-069 wave R (US-INT-040) — 07-endpoints.md rows 19 and 20. Written
    # above `integrations/<str:key>` for the same reason every other two-segment
    # route is: Django matches this list IN ORDER, so `<str:key>` would swallow
    # `gl_partner/key` and answer it with the connection route's PATCH/DELETE.
    path("integrations/<str:key>/key", partner_key),
    path("integrations/<str:key>/run", run),
    path("integrations/<str:key>/arrival", arrival),
    path("integrations/<str:key>/export", departure),
    path("integrations/<str:key>/oauth/start", oauth_start),
    path("integrations/<str:key>/oauth/return", oauth_return),
    path("integrations/<str:key>", connection),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-001@a63a1b7 · US-INT-002@a63a1b7 · US-INT-004@a63a1b7 (EP-INT-01) · US-INT-016@62d3643 · US-INT-017@62d3643 (EP-INT-05)
# generated: 2026-09-03 by the CR-069 wave A build lane · EXTENDED 2026-09-03 by the wave B build lane (the six writes)
# checklist: A✔ B✔ C✔ D✔ E✔(ConnectModal.tsx presses connect/test/PATCH/DELETE/credential; the card's buttons press test and PATCH) F✔ G✔ H=n/a(no 🔒 path — the RLS half is the migration)
# gates: pytest tests/test_us_int_017_gating.py tests/test_us_int_002_connect.py tests/test_us_int_016_queue.py tests/test_us_int_004_audit.py · openapi export re-run · G9 error envelope · G79 (no /send route in any URLconf — BR-INT-008)
# exceptions: none for OAuth — `oauth/start` and `oauth/return` are the REAL round trip since wave H (2026-09-06). ⚠ THIS LINE SAID `oauth/start` "exists only to refuse (wave G/H builds the trip)" AFTER wave H had built it, and a sibling lane filed DEF-INT-4226 against it: the wave that lands a thing has to correct every sentence that was waiting for it, and a trailer is one of them (hard-won law 1 — a comment claiming a guarantee, here claiming an absence). `credential/rollback`, `runs`, `mappings` and `key` are waves E, C, D and R and are stated absent here rather than mounted empty
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
