# ── Trace ──────────────────────────────────────────────
# Component: BE-01 RLS tenant-context middleware (B13 §3, W0 kernel lane — component packet)
# Contract:  B3 (03-tenancy-and-security.md session propagation / TD-4) · B2 §3 RLS template
#            (core/rls.py) · 11b §3 G4 (tenant resolved server-side, never client input) ·
#            PO ruling 2026-08-10 "TENANCY MOVES TO PATH-BASED" (12-governance/02-decision-log.md):
#            API routes are /api/{tenant}/… ; the public + platform surface carries no tenant
# Rules:     HR-1 (CLAUDE.md rule 1) · BR-TEN-003 (membership+tenant resolved server-side) ·
#            BR-IDN-001 (tenant-first sign-in) · BR-IDN-006 (one tenant per session — the
#            control the one-origin move makes load-bearing) · BR-TEN-011 (slug law)
# Tests:     06-backend/tests/test_be01_tenancy.py (mocked cursor) ·
#            06-backend/tests/test_path_tenancy_session_binding.py (the cross-tenant refusal) ·
#            isolation suite (G5) for the live-Postgres RLS assertions
# Impacts:   EVERY tenant-scoped request and job — RLS FORCE only isolates when this GUC is set
# ───────────────────────────────────────────────────────
"""BE-01 — tenant context propagation. HUMAN-OWNED (CLAUDE.md 🔒 list, RLS-adjacent).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09 ("AI
will do it; we will review it later as human"), AMENDED 2026-08-10 for the PO's
path-tenancy ruling, implementing SIGNED law only (B3 contract below + B2 §3
RLS template + the 2026-08-10 decision-log row). Row updated in
12-governance/09-human-review-ledger.md; must not reach RATIFIED without a
recorded human sign-off.

Contract (B3, as amended by the PO ruling of 2026-08-10):
- Resolve the tenant from the REQUEST PATH's first segment under /api/ —
  `/api/{tenant}/…` — then the authenticated user's membership in it.
  (Until 2026-08-10 the source was the Host header's first DNS label. Only the
  SOURCE changed: the tenant is still resolved FIRST, server-side, and never
  from client-chosen input.)
- SET app.tenant_id = <uuid> on the DB session for the request/transaction.
- NEVER accept tenant_id from client input.
- Background jobs set context explicitly per tenant before touching tenant tables.

How the pieces fit (deny-by-default, HR-1):
- RLS policies (B2 §3 template) compare `tenant_id` to
  `NULLIF(current_setting('app.tenant_id', true), '')::uuid`. When the GUC is
  unset or empty that expression is NULL, and `tenant_id = NULL` is NULL, which
  is not TRUE — so a request that never got tenant context can touch NO tenant
  table. This module only ever ADDS context; absence is already safe.
  ⚠ AMENDED 2026-08-24 (DEF-639). It used to be the bare
  `current_setting('app.tenant_id')::uuid`, where an unset GUC made the CAST
  FAIL rather than the row not match. Same denial, but loud — and that loudness
  made a fresh database un-buildable, because the identical policy is evaluated
  during FOREIGN KEY VALIDATION and three committed migrations clear tenant
  context before their own deferred FKs are validated. Deny-by-default is
  unchanged; absence of context is now silent on reads and still loud on writes.
- The path segment is not client input in the sense BR-TEN-003 forbids: it is
  the ROUTE, matched against the tenants table server-side, exactly as the Host
  label was. What is still never read is a tenant id in a header, body field or
  query param.
- The middleware never blocks a request itself: endpoints that require tenant
  context enforce it via require_tenant() / core.permissions, so the refusal
  renders through the BE-02 envelope, not a middleware short-circuit.

THE control the one-origin move makes load-bearing
--------------------------------------------------
Subdomains used to give tenant isolation for free: the browser kept one cookie
jar per host. `/api/{tenant}/…` is ONE origin, so it does not. Two rules close
the hole, and both live where they can be proved:
  1. a session row is BOUND to its tenant (apps/identity `sessions.tenant_id`);
  2. a session presented on another tenant's path is refused as 404 — never
     403 (existence must not leak, HR-1 / 11b G4), never a silent switch to the
     session's own tenant. That refusal is raised by
     apps/identity/auth.py::IdentitySessionAuthentication and rendered by BE-02
     with a body byte-identical to any other 404.
`require_tenant()` below carries the same law for the unauthenticated half: a
path naming a tenant that does not exist is a 404, not an AUTH-003 — otherwise
the mismatch answer would be distinguishable from the unknown-tenant answer and
the leak would reopen through the status code.

Membership half of the contract: WHO the user is inside the tenant (their
role) is the identity module's story (BR-IDN-001 resolves the tenant first,
then (tenant, email) credentials). This kernel resolves slug → tenant_id
through a registered resolver so core stays free of app model imports
(B8 layering); apps.tenancy registers the real lookup in its AppConfig.ready().
"""

import logging
import uuid
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from django.db import connection

logger = logging.getLogger("smartbillhub.tenancy")

# set_config(..., is_local := false) is the parameterized form of SET: Postgres
# cannot bind parameters into a bare `SET`/`SET LOCAL` utility statement, and
# string-formatting a GUC value into SQL is exactly the injection surface this
# kernel exists to close. Session-scoped (not SET LOCAL) because one Django
# request may span several transactions; try/finally below guarantees the GUC
# is cleared before the connection can serve anyone else (HR-1).
_SET_TENANT_SQL = "SELECT set_config('app.tenant_id', %s, false)"
_CLEAR_TENANT_SQL = "SELECT set_config('app.tenant_id', '', false)"
# '' (empty) — the policy's NULLIF(…, '') turns that into NULL, `tenant_id =
# NULL` is not TRUE, and RLS denies everything: cleared context == no access,
# never wrong access. (Before DEF-639 the empty string made the ::uuid cast
# FAIL instead. Same denial; the difference is that clearing context can no
# longer blow up an unrelated foreign-key validation scan.)

# ── the path contract (PO ruling 2026-08-10, Eng-Lead-fixed so FE and BE
# cannot diverge) ───────────────────────────────────────────────────────────
#: Every API route lives under this prefix. Tenant-scoped ones continue
#: `/api/{tenant}/…`; the public + platform ones do not (below).
API_PREFIX = "/api/"

#: First segments under /api/ that are NOT tenant slugs — the whole no-tenant
#: surface config/urls.py mounts beside the tenant include:
#:   public/…              pricing catalog + slug availability (11b §2.1)
#:   tenants               POST /api/tenants, provisioning (S114)
#:   jobs/{id}             BE-07 poll resource (B12 r1 202 contract)
#:   exports, exports/…    US-SHL-008 table export + IS-11 download
#:   health                the load-balancer probe. ⚠ **IT IS ANSWERED NOW,
#:                         AND NOT BY A ROUTE** — this line read "no Django
#:                         route yet" until 2026-09-28 (`CR-144-BRC07`).
#:                         `core.health.HealthCheckMiddleware` answers it
#:                         FIRST in the chain, ahead of host validation,
#:                         because the load balancer dials the task by its
#:                         private IP and Django would answer 400 before
#:                         any view ran. So nothing under `config/urls.py`
#:                         will ever mention it, and its reservation here
#:                         is what keeps a customer from being named
#:                         `health` and shadowing the probe.
#:   partner/v1/…          THE PARTNER SURFACE — one base URL for every partner
#:                         and every utility, added 2026-09-16 (`CR-110-BRC04`
#:                         phase 2, `DEF-INT-5546`). PO, verbatim: *"we agreed
#:                         not to use utility names in partner apis that was our
#:                         rule … we will resolve utility name using keys"*. The
#:                         utility is opened from the KEY, through
#:                         `adopt_partner_tenant` below — the same shape as
#:                         `jobs` and `exports`, which open it from the session.
#: apps/tenancy/selectors.RESERVED_SUBDOMAINS must be a SUPERSET of this set —
#: a tenant that could be named `jobs` would be unreachable at its own API.
#: test_be01_tc16 asserts exactly that, so the two lists cannot drift.
# `auth` added 2026-10-24 (DEF-FLD-10580): `POST /api/auth/activation/lookup`.
NON_TENANT_SEGMENTS = frozenset(
    # `hooks` — CR-198-BRC10: Twilio's incoming-text webhook, `/api/hooks/…`.
    {"public", "tenants", "jobs", "exports", "health", "partner", "auth", "hooks"}
)

# Python-side mirror of the GUC so services (audit writer, jobs) can read the
# current tenant without a DB round-trip. ContextVar: safe across async tasks.
_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("smartbillhub_tenant", default=None)

# Narrow resolver interface (slug → tenant_id or None). apps.tenancy owns the
# tenants table (B1 boundary) and registers its lookup at startup:
#     core.tenancy.set_tenant_resolver(selectors.tenant_id_for_subdomain)
# The seam did not change with the path ruling — only what is handed to it: the
# path's first segment instead of the Host's first label. The stored column is
# still `tenants.subdomain` (B2), which the decision-log row keeps as the slug.
TenantResolver = Callable[[str], uuid.UUID | None]
_tenant_resolver: TenantResolver | None = None


def set_tenant_resolver(resolver: TenantResolver | None) -> None:
    """Register (or clear, with None) the slug→tenant_id lookup."""
    global _tenant_resolver
    _tenant_resolver = resolver


def tenant_id_for_slug(slug: str) -> uuid.UUID | None:
    """READ the registered slug→tenant_id lookup — the seam's public half.

    ⚠ ADDED 2026-09-04 (CR-069 wave C), AND IT IS A READER FOR A SEAM THAT
    ALREADY EXISTED. The middleware has resolved a slug through
    `_tenant_resolver` since BE-01; nothing else could, so a management command
    that lets an operator type `--tenant brazosbend` had only one way to find
    the tenant — `from apps.tenancy.models import Tenant` — which is the
    cross-module import B2 §2 forbids and G6 refuses. This is the same one
    lookup, exposed rather than duplicated.

    Returns None when no resolver is registered (nothing has started
    `apps.tenancy`) and when the slug names no tenant. A caller that cannot
    tell those apart does not need to: both mean *I cannot act on this name*.
    """
    if _tenant_resolver is None:
        return None
    return _tenant_resolver(slug)


def _as_uuid(tenant_id: uuid.UUID | str) -> uuid.UUID:
    """Defense in depth: only a real UUID ever reaches the GUC."""
    if isinstance(tenant_id, uuid.UUID):
        return tenant_id
    return uuid.UUID(tenant_id)  # raises ValueError on anything malformed


def set_current_tenant(tenant_id: uuid.UUID | str) -> uuid.UUID:
    """SET app.tenant_id on the DB session + the Python mirror. Returns the UUID."""
    tid = _as_uuid(tenant_id)
    with connection.cursor() as cursor:
        cursor.execute(_SET_TENANT_SQL, [str(tid)])  # parameterized, never interpolated
    _current_tenant.set(tid)
    return tid


def clear_current_tenant() -> None:
    """Clear the GUC and the mirror — RLS returns to deny-everything."""
    with connection.cursor() as cursor:
        cursor.execute(_CLEAR_TENANT_SQL)
    _current_tenant.set(None)


def current_tenant_id() -> uuid.UUID | None:
    """The tenant this request/job is executing as, or None outside any context."""
    return _current_tenant.get()


def tenant_slug_of(path: str) -> str | None:
    """The tenant slug a request path names, or None when it names none.

    '/api/brazosbend/settings/company' → 'brazosbend'
    '/api/public/pricing-plans'        → None   (public surface)
    '/api/tenants'                     → None   (provisioning)
    '/api/jobs/<id>' · '/api/exports'  → None   (platform resources)
    '/' · '/pricing' · '/brazosbend'   → None   (SPA routes; Django serves no HTML)

    Case is folded because the slug grammar is lowercase-only (BR-TEN-011), so
    an upper-case segment can only ever be a case variant of one tenant — never
    a second one. Segments that are not tenants simply resolve to None at the
    resolver; this function allow-lists nothing beyond NON_TENANT_SEGMENTS,
    which exist because those segments are ROUTES of their own.
    """
    if not path.startswith(API_PREFIX):
        return None
    segment = path[len(API_PREFIX) :].split("/", 1)[0].strip().lower()
    if not segment or segment in NON_TENANT_SEGMENTS:
        return None
    return segment


def require_tenant(request: object) -> uuid.UUID:
    """For endpoints that only exist inside a tenant: the resolved tenant_id.

    Two different refusals, deliberately:
    - the path NAMED a tenant and it did not resolve → 404, byte-identical to
      any other 404 (HR-1 / 11b G4). Under one origin this is the same answer a
      foreign-session request gets, so neither the status nor the body can be
      used to ask "does tenant X exist?".
    - the path named NO tenant and none was adopted → AUTH-003 through the
      BE-02 envelope. That is a wiring fault (a tenant-scoped view mounted
      outside the /api/{tenant}/ include, or called with no session on a
      platform path), not a probe, and it should say so loudly.
    """
    tenant_id = getattr(request, "tenant_id", None)
    if tenant_id is not None:
        return tenant_id
    from core import errors  # local import: errors ↔ tenancy stay decoupled at import time

    if getattr(request, "tenant_slug", None) is not None:
        raise errors.NotFoundError()
    raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")


def adopt_session_tenant(request: object, tenant_id: uuid.UUID | str) -> uuid.UUID:
    """Bind context from an authenticated session on a NO-TENANT path.

    The platform resources (`/api/jobs/{id}`, `/api/exports`,
    `/api/exports/{id}/file`) serve tenant-scoped records but carry no tenant
    segment — that is the Eng-Lead-fixed shape of the 2026-08-10 contract. The
    only server-side fact that can scope them is the SESSION ROW, which is
    bound to exactly one tenant (BR-IDN-006). Adopting it is not client input:
    the cookie selects a row, the row states the tenant.

    Refuses outright when the path DOES name a tenant — on those paths the
    session must MATCH the path (the 404 rule), never override it. That branch
    is unreachable from the shipping caller; it exists so a future caller
    cannot quietly turn this into a tenant switch.
    """
    if getattr(request, "tenant_slug", None) is not None:
        raise RuntimeError(
            "adopt_session_tenant() called on a tenant-scoped path — the session "
            "must match the path there (PO ruling 2026-08-10), never replace it"
        )
    tid = set_current_tenant(tenant_id)
    request.tenant_id = tid  # type: ignore[attr-defined]
    return tid


def adopt_partner_tenant(request: object, tenant_id: uuid.UUID | str) -> uuid.UUID:
    """Bind context from an ISSUED KEY on a NO-TENANT path — the partner surface.

    `/api/partner/v1/bills` carries no utility segment, by PO ruling of
    2026-09-16 (`CR-110-BRC04` phase 2, `DEF-INT-5546`): *"we agreed not to use
    utility names in partner apis that was our rule … we will resolve utility
    name using keys"*. One base URL, the same for every partner and every
    utility.

    ⚠ **THIS IS NOT THE THING `BR-TEN-003` FORBIDS, AND THE DISTINCTION IS THE
    WHOLE RULE.** That rule forbids reading a tenant a caller ASSERTS — a
    `tenant_id` in a header, a parameter or a body — because an assertion is
    free to make and somebody must then compare it against the truth on every
    single handler. A bearer key asserts nothing: it is a secret WE minted, and
    `apps.integrations.key_directory` looks up the utility we recorded against
    it. The blueprint puts it in four words — *a path segment is a claim; a key
    is proof.*

    It is the same move `adopt_session_tenant` above makes, one door along: the
    cookie selects a row and the row states the tenant; here the key selects a
    row and the row states the tenant. Both read a table B2 §3 declares
    RLS-exempt precisely so it can be read before a utility is open.

    ⚠ **AND IT RESOLVES NOTHING ITSELF.** It is handed a tenant id that a
    caller never sent and cannot influence, and it sets the GUC. Everything that
    decides whether this key may do anything at all happens AFTERWARDS, under
    the context this opens, in `runners/serve.resolve_caller`.

    Refuses outright when the path DOES name a tenant, for the reason the
    session version does: on those paths the path has already decided, and a key
    that could override it would be a tenant switch reachable by presenting a
    key. Unreachable from the shipping caller — `key_directory.adopt_tenant_for`
    returns early when a context exists — and kept so a future caller cannot
    quietly turn this into one.
    """
    if getattr(request, "tenant_slug", None) is not None:
        raise RuntimeError(
            "adopt_partner_tenant() called on a tenant-scoped path — the path "
            "decides there (BR-TEN-003), and a key may never override it"
        )
    tid = set_current_tenant(tenant_id)
    request.tenant_id = tid  # type: ignore[attr-defined]
    return tid


def tenant_path(request: object, path: str) -> str:
    """An absolute API path inside THIS request's tenant prefix.

    Used for `Location:` on 201s so a created resource's URL is one a client
    can actually GET (`/api/brazosbend/plans/{id}`, not `/plans/{id}`). With no
    slug on the request — a direct view call in a unit test, or a platform
    path — the bare path is returned unchanged rather than a guessed prefix.
    """
    slug = getattr(request, "tenant_slug", None)
    return f"{API_PREFIX}{slug}{path}" if slug else path


class TenantContextMiddleware:
    """Per-request tenant context: path slug → tenant_id → SET app.tenant_id.

    Registered in config/settings/base.py MIDDLEWARE. Order: after
    CommonMiddleware, before any view runs a query.

    Reads the RAW path (`request.path_info`), not the resolved URL kwarg:
    middleware runs before URL resolution, and the alternative — moving this
    into process_view — would leave every request between middleware entry and
    view dispatch running with no GUC. The raw path and the route agree by
    construction because config/urls.py mounts exactly one tenant prefix
    (`api/<slug:tenant>/`) and NON_TENANT_SEGMENTS lists every sibling.
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request):  # type: ignore[no-untyped-def]
        # BR-TEN-003: the ONLY input consulted is the request path. tenant_id
        # in a header/param/body is never read.
        request.tenant_slug = tenant_slug_of(request.path_info)
        request.tenant_id = None
        if request.tenant_slug is not None and _tenant_resolver is not None:
            tenant_id = _tenant_resolver(request.tenant_slug)
            if tenant_id is not None:
                request.tenant_id = set_current_tenant(tenant_id)
            # An unknown slug sets NO context: RLS denies tenant tables by
            # default (HR-1), and require_tenant() renders the 404.
        try:
            return self.get_response(request)
        finally:
            # The GUC must never outlive the request on a pooled connection.
            # Checked rather than unconditional so a genuinely public request
            # still costs zero SQL — and so context adopted DOWNSTREAM of this
            # middleware (adopt_session_tenant, on the platform paths) is
            # cleared here too.
            if current_tenant_id() is not None:
                clear_current_tenant()


@contextmanager
def tenant_context(tenant_id: uuid.UUID | str) -> Iterator[uuid.UUID]:
    """B3: background jobs set context EXPLICITLY per tenant.

    Usage (Celery tasks, management commands, partition jobs):
        with tenant_context(tenant.id):
            ...touch tenant tables...
    Context is cleared on exit even on error — a job can never carry one
    tenant's context into the next tenant's loop iteration.
    """
    tid = set_current_tenant(tenant_id)
    try:
        yield tid
    finally:
        clear_current_tenant()


def stream_within_tenant_context(tenant_id: uuid.UUID | str, body: Iterable[Any]) -> Iterator[Any]:
    """Wrap a STREAMED response body so its late queries still have a tenant.

    ⛔ **DEF-2734 — THE TRAP THIS EXISTS FOR, AND IT IS SILENT IN EVERY
    DIRECTION.** `StreamingHttpResponse` returns from the view with its body
    UNCONSUMED. `TenantContextMiddleware.__call__` above clears `app.tenant_id`
    in its `finally` the moment `get_response` returns, and WSGI iterates the
    body afterwards — so the generator's first query runs with NO tenant marker,
    the RLS policy's `NULLIF(current_setting('app.tenant_id', true), '')::uuid`
    is NULL, `tenant_id = NULL` is not TRUE, and the queryset yields **zero
    rows**. Nothing raises. The download succeeds. The file is a header and
    nothing under it.

    Measured, before this function was written, on a batch whose own screen said
    *"2 rows will not post"*: `GET /read-batches/{id}/results.csv?kind=failures`
    answered **200** with **1 line and 0 data rows**, and the account importer's
    `GET /imports/{run_id}/results.csv?kind=failures` answered 200 with a header
    of `why_it_failed,how_to_fix_it` and nothing else — the operator's own nine
    columns gone too, because `_source_headers`' pre-`DEF-2513` fallback is a
    QUERY inside the generator and every run on that database needs it. (A run
    that stored its column order keeps its header, because `run.mapping_spec` is
    already in memory; the ROWS are lost either way.) **An empty rejects file
    reads as "nothing was rejected"**, which is the exact `DEF-320` failure
    `metering.read_rejects._refuse_not_decided` cites as its reason for refusing
    rather than serving an empty file.

    ⚠ **AND IT IS INVISIBLE ON MOST DATABASES.** A SUPERUSER or a `BYPASSRLS`
    role skips row-level security completely, FORCE included, while every table
    still reports `relrowsecurity=t` — so the two routes passed their checks
    twice an hour before this was caught, and only stopped when a sibling lane
    revoked that bit (`DEF-2717`). `config/settings/test.py` hardcodes in-memory
    SQLite, which has no row-level security at all, so no default-suite test can
    reach it either. Before believing a green run of anything below, check:
        select rolsuper, rolbypassrls from pg_roles where rolname=current_user;

    WHAT THIS DOES
    --------------
    Re-enters `tenant_id` when the FIRST chunk is pulled and puts the session's
    previous marker back in a `finally`. Between the view returning and that
    first chunk the marker stays cleared, so the window in which a pooled
    connection carries a tenant is exactly the window in which rows are being
    read — never wider. CLAUDE.md hard rule 1 is not softened to make a download
    work; the query is simply moved back inside the context that was already
    granted to it.

    **SAVE-AND-RESTORE, NOT `tenant_context`.** `tenant_context` CLEARS on exit,
    which is right for a background job that owns the connection and wrong here:
    a caller that consumes the body while still inside its own context (every
    existing test does, and that is why none of them could see the defect) would
    have that context stripped out from under it by the join. Restoring is
    correct in both worlds and can never leave the connection holding a marker
    it did not already have.

    **PASS THE REQUEST'S OWN TENANT — `require_tenant(request)` — NOT the
    record's `tenant_id`.** They are equal today because the selector that read
    the record is tenant-scoped, and if they ever stop being equal the honest
    answer is to re-enter the context the REQUEST was granted, never the one a
    row claims. `_as_uuid` runs eagerly, inside the request, so a malformed id
    fails where someone can see it rather than half-way down a file.

    Usage, and **`G58`** refuses a `StreamingHttpResponse` in `06-backend/apps/**`
    built any other way. (`G56` and `G57` are two SIBLING gates from the same day
    and the same root cause, and reading the three together is the point: `G56`
    asks whether the RUNNING APPLICATION is on a role subject to RLS, `G57`
    whether a test fixture stands in front of this kernel, `G58` whether a
    streamed response is still inside the context when it queries.):

        tenant_id = require_tenant(request)
        filename, body = read_rejects.results_csv(batch, kind)
        StreamingHttpResponse(stream_within_tenant_context(tenant_id, body), ...)
    """
    tid = _as_uuid(tenant_id)

    def _chunks() -> Iterator[Any]:
        previous = current_tenant_id()
        set_current_tenant(tid)
        try:
            yield from body
        finally:
            # Restore, never blindly clear — see the docstring. The connection
            # is alive here in every ordering that matters: WSGI consumes the
            # body before calling `response.close()`, and `close()` sends
            # `request_finished` (which closes connections) only AFTER running
            # the body's own `close`, which is what unwinds this generator.
            if previous is None:
                clear_current_tenant()
            else:
                set_current_tenant(previous)

    return _chunks()


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-01@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the SPA half is a concurrent lane) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row updated)
# gates: black✔ (no new offender; the repo's 37-file pre-existing backlog is unchanged) · ruff --select E4,E7,E9,F: 169→186, the +17 all F811 pytest-fixture shadowing in the new test file, the same pattern every existing test file carries (test_us_aud_004_006_viewer.py has 21) — recorded honestly rather than claimed clean · pytest tests/test_be01_tenancy.py 19 passed / 1 postgres-only skipped✔ · tests/test_path_tenancy_session_binding.py 21 passed / 3 postgres-only skipped✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · migrate makemigrations --check --dry-run clean (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: subdomain_of() and its three TCs were DELETED, not kept — nothing reads a Host label for tenancy any more and dead 🔒 code is worse than none · the platform paths (/api/jobs, /api/exports) carry no tenant segment per the fixed contract yet serve tenant-scoped records, so their context comes from the session row via adopt_session_tenant() — REPORTED as the one place the contract needed a mechanism it did not name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
