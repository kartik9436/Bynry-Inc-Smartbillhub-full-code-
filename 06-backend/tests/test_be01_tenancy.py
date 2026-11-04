# ── Trace ──────────────────────────────────────────────
# Component: BE-01 tests (core/tenancy.py) — unit tier, mocked DB cursor (no live Postgres).
# Rules:     HR-1 · BR-TEN-003 · BR-IDN-001 · BR-TEN-011. Live-RLS behavior = isolation
#            suite (G5). AMENDED 2026-08-10: the tenant source is the /api/{tenant}/ path
#            segment, not the Host label (PO ruling, 12-governance/02-decision-log.md).
# ───────────────────────────────────────────────────────
"""BE-01 unit tests. The DB session is a recording fake: these tests prove the
kernel issues exactly the parameterized set_config calls the B2 §3 policies
key on, and that context can never leak past a request/job. What only a real
Postgres can prove (RLS actually denying) is marked for the isolation suite."""

import uuid

import pytest

from apps.tenancy.models import Uom
from core import tenancy

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    current_guc,
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)

TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


class FakeCursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.log.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.executed = []

    def cursor(self):
        return FakeCursor(self.executed)


class FakeRequest:
    """Bare request double: only what the middleware may touch.

    `path_info` is the ONLY tenancy input since the 2026-08-10 path ruling —
    `get_host()` is still here so a regression that starts reading the Host
    again would have to add the call back deliberately (nothing calls it).
    """

    def __init__(self, path, host="smartbillhub.bynry.com", headers=None, get_params=None):
        self.path_info = path
        self.path = path
        self._host = host
        self.headers = headers or {}
        self.GET = get_params or {}

    def get_host(self):
        return self._host


@pytest.fixture()
def db(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(tenancy, "connection", fake)
    return fake


@pytest.fixture(autouse=True)
def clean_context():
    # ⚠ **SAVE AND RESTORE THE RESOLVER, NEVER LEAVE IT `None` (`DEF-TEN-6789`,
    # fixed 2026-10-02).** The real resolver is registered ONCE, at
    # `AppConfig.ready`, for the whole process. This fixture used to set it to
    # None on teardown, so every later test in the same run that went through
    # `TenantContextMiddleware` found no resolver, opened no utility, and got
    # `404 errors.not-found` on its sign-in — which is how
    # `test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack`
    # went red in every full isolation run and green on its own, for four
    # weeks, reading as an order-dependent mystery on hard rule 1's own kernel
    # test. `test_us_idn_helpers.idn` already does save-and-restore for exactly
    # this reason.
    previous_resolver = tenancy._tenant_resolver
    tenancy._current_tenant.set(None)
    tenancy.set_tenant_resolver(None)
    yield
    tenancy._current_tenant.set(None)
    tenancy.set_tenant_resolver(previous_resolver)


# ── slug resolution (PATH only — BR-TEN-003, PO ruling 2026-08-10) ──────────
def test_be01_tc01_tenant_slug_of_takes_the_first_segment_under_api():
    assert tenancy.tenant_slug_of("/api/brazosbend/settings/company") == "brazosbend"
    assert tenancy.tenant_slug_of("/api/brazosbend/auth/session") == "brazosbend"
    assert tenancy.tenant_slug_of("/api/brazosbend") == "brazosbend"  # no trailing path


def test_be01_tc02_tenant_slug_of_folds_case():
    # BR-TEN-011 slugs are lowercase, so an upper-case segment can only ever be
    # a case variant of ONE tenant — never a second, separate one.
    assert tenancy.tenant_slug_of("/api/BrazosBend/settings/company") == "brazosbend"


def test_be01_tc03_the_no_tenant_surface_resolves_to_none():
    # The public + platform routes config/urls.py mounts beside the tenant one.
    assert tenancy.tenant_slug_of("/api/public/pricing-plans") is None
    assert tenancy.tenant_slug_of("/api/tenants") is None
    assert tenancy.tenant_slug_of("/api/jobs/0f9d1c1e-0000-7000-8000-000000000000") is None
    assert tenancy.tenant_slug_of("/api/exports") is None
    assert tenancy.tenant_slug_of("/api/exports/0f9d1c1e-0000-7000-8000-000000000000/file") is None
    assert tenancy.tenant_slug_of("/api/health") is None
    # Anything outside /api/ is an SPA route — Django serves no HTML at all.
    assert tenancy.tenant_slug_of("/") is None
    assert tenancy.tenant_slug_of("/pricing") is None
    assert tenancy.tenant_slug_of("/brazosbend/settings") is None
    assert tenancy.tenant_slug_of("/api") is None
    assert tenancy.tenant_slug_of("/api/") is None
    assert tenancy.tenant_slug_of("") is None


# ── GUC set/clear is parameterized, mirrored, and validated ─────────────────
def test_be01_tc04_set_current_tenant_is_parameterized_set_config(db):
    tenancy.set_current_tenant(TENANT_A)
    assert db.executed == [(tenancy._SET_TENANT_SQL, [str(TENANT_A)])]
    # HR-1: the value travels as a bind parameter, never interpolated into SQL.
    assert str(TENANT_A) not in db.executed[0][0]
    assert tenancy.current_tenant_id() == TENANT_A


def test_be01_tc05_clear_current_tenant_resets_guc_and_mirror(db):
    tenancy.set_current_tenant(TENANT_A)
    tenancy.clear_current_tenant()
    assert db.executed[-1] == (tenancy._CLEAR_TENANT_SQL, None)
    assert tenancy.current_tenant_id() is None


def test_be01_tc06_malformed_tenant_id_never_reaches_the_db(db):
    with pytest.raises(ValueError):
        tenancy.set_current_tenant("1; DROP POLICY; --")
    assert db.executed == []  # refused before any SQL


def test_be01_tc07_string_uuid_accepted(db):
    tenancy.set_current_tenant(str(TENANT_B))
    assert tenancy.current_tenant_id() == TENANT_B


# ── job context manager (B3: jobs set context explicitly) ───────────────────
def test_be01_tc08_tenant_context_sets_then_always_clears(db):
    with tenancy.tenant_context(TENANT_A) as tid:
        assert tid == TENANT_A
        assert tenancy.current_tenant_id() == TENANT_A
    assert tenancy.current_tenant_id() is None
    assert db.executed[-1][0] == tenancy._CLEAR_TENANT_SQL


def test_be01_tc09_tenant_context_clears_on_error(db):
    with pytest.raises(RuntimeError), tenancy.tenant_context(TENANT_A):
        raise RuntimeError("job blew up")
    # A crashed job may not leave its tenant behind for the next loop iteration.
    assert tenancy.current_tenant_id() is None
    assert db.executed[-1][0] == tenancy._CLEAR_TENANT_SQL


# ── middleware ──────────────────────────────────────────────────────────────
def _run_middleware(request, seen=None):
    def view(req):
        if seen is not None:
            seen.append(tenancy.current_tenant_id())
        return "response"

    return tenancy.TenantContextMiddleware(view)(request)


def test_be01_tc10_known_slug_sets_context_for_the_view_then_clears(db):
    tenancy.set_tenant_resolver(lambda slug: TENANT_A if slug == "brazosbend" else None)
    request = FakeRequest("/api/brazosbend/settings/company")
    seen = []
    assert _run_middleware(request, seen) == "response"
    assert request.tenant_id == TENANT_A
    assert request.tenant_slug == "brazosbend"
    assert seen == [TENANT_A]  # context held DURING the view
    assert tenancy.current_tenant_id() is None  # and cleared after (HR-1)
    assert db.executed[-1][0] == tenancy._CLEAR_TENANT_SQL


def test_be01_tc11_unknown_slug_sets_no_context(db):
    tenancy.set_tenant_resolver(lambda slug: None)
    request = FakeRequest("/api/nobody/settings/company")
    _run_middleware(request)
    assert request.tenant_id is None
    assert request.tenant_slug == "nobody"  # the path NAMED one; it just is not real
    assert db.executed == []  # no GUC ever set — RLS stays deny-everything


def test_be01_tc12_no_resolver_registered_sets_no_context(db):
    request = FakeRequest("/api/brazosbend/settings/company")
    _run_middleware(request)
    assert request.tenant_id is None
    assert db.executed == []


def test_be01_tc13_client_supplied_tenant_ids_are_never_read(db):
    # BR-TEN-003 negative: a forged header/param must not influence resolution.
    tenancy.set_tenant_resolver(lambda slug: TENANT_A if slug == "brazosbend" else None)
    request = FakeRequest(
        "/api/public/pricing-plans",  # a no-tenant route
        headers={"X-Tenant-ID": str(TENANT_B)},
        get_params={"tenant_id": str(TENANT_B)},
    )
    _run_middleware(request)
    assert request.tenant_id is None
    assert db.executed == []
    # …and the Host is no longer an input either: a tenant-shaped hostname on a
    # no-tenant path resolves nothing (the whole point of the 2026-08-10 move).
    hosted = FakeRequest("/api/public/pricing-plans", host="brazosbend.smartbillhub.com")
    _run_middleware(hosted)
    assert hosted.tenant_id is None
    assert db.executed == []


def test_be01_tc14_context_cleared_even_when_view_raises(db):
    tenancy.set_tenant_resolver(lambda slug: TENANT_A)

    def exploding_view(req):
        raise RuntimeError("view blew up")

    with pytest.raises(RuntimeError):
        tenancy.TenantContextMiddleware(exploding_view)(FakeRequest("/api/brazosbend/x"))
    assert tenancy.current_tenant_id() is None
    assert db.executed[-1][0] == tenancy._CLEAR_TENANT_SQL


def test_be01_tc14b_context_adopted_inside_the_request_is_still_cleared(db):
    """The platform paths (/api/jobs, /api/exports) get their context AFTER the
    middleware has already decided there is no slug — from the session row. It
    must still not outlive the request on a pooled connection (HR-1)."""
    request = FakeRequest("/api/jobs/0f9d1c1e-0000-7000-8000-000000000000")

    def view(req):
        tenancy.adopt_session_tenant(req, TENANT_B)
        assert tenancy.current_tenant_id() == TENANT_B
        return "response"

    assert tenancy.TenantContextMiddleware(view)(request) == "response"
    assert request.tenant_id == TENANT_B
    assert tenancy.current_tenant_id() is None
    assert db.executed[-1][0] == tenancy._CLEAR_TENANT_SQL


def test_be01_tc14c_adopting_a_session_tenant_on_a_tenant_path_is_refused(db):
    """A session may never OVERRIDE the tenant the path names — on those paths
    the law is match-or-404, and this guard makes the wrong call impossible."""
    request = FakeRequest("/api/brazosbend/settings/company")
    request.tenant_slug = "brazosbend"
    with pytest.raises(RuntimeError):
        tenancy.adopt_session_tenant(request, TENANT_B)


# ── require_tenant → 404 for a named-but-unknown tenant, AUTH-003 otherwise ──
def test_be01_tc15_require_tenant_returns_id_or_refuses():
    from core import errors

    request = FakeRequest("/api/brazosbend/settings/company")
    request.tenant_slug = "brazosbend"
    request.tenant_id = TENANT_A
    assert tenancy.require_tenant(request) == TENANT_A

    # The path NAMED a tenant that does not exist → 404, so the answer is the
    # same one a foreign-session request gets and neither leaks existence.
    unknown = FakeRequest("/api/nobody/settings/company")
    unknown.tenant_slug = "nobody"
    unknown.tenant_id = None
    with pytest.raises(errors.NotFoundError):
        tenancy.require_tenant(unknown)

    # No tenant in the path at all → AUTH-003: a wiring fault, said loudly.
    bare = FakeRequest("/api/exports")
    bare.tenant_slug = None
    bare.tenant_id = None
    with pytest.raises(errors.AuthError) as exc_info:
        tenancy.require_tenant(bare)
    assert exc_info.value.code == errors.AUTH_TENANT_UNRESOLVABLE


def test_be01_tc16_every_platform_segment_is_a_reserved_tenant_name():
    """core and apps.tenancy must not drift: a tenant that could be named
    `jobs` would be unreachable at its own API forever, because the kernel
    resolves that segment to "no tenant" before the resolver ever runs."""
    from apps.tenancy.selectors import RESERVED_SUBDOMAINS

    assert tenancy.NON_TENANT_SEGMENTS <= RESERVED_SUBDOMAINS
    # …and the names the PO's ruling enumerated are all in there too.
    assert {
        "api",
        "signup",
        "signin",
        "pricing",
        "static",
        "assets",
        "public",
        "jobs",
        "exports",
        "health",
    } <= RESERVED_SUBDOMAINS


def test_be01_tc17_tenant_path_builds_urls_a_client_can_follow():
    request = FakeRequest("/api/brazosbend/plans")
    request.tenant_slug = "brazosbend"
    assert tenancy.tenant_path(request, "/plans/abc") == "/api/brazosbend/plans/abc"
    # No slug (direct view call / platform path): the bare path, never a guess.
    bare = FakeRequest("/api/exports")
    bare.tenant_slug = None
    assert tenancy.tenant_path(bare, "/plans/abc") == "/plans/abc"


# ── live-Postgres assertions (isolation suite, G5 — not runnable on mocks) ──
@pytest.mark.isolation
@requires_postgres
@pytest.mark.django_db
def test_be01_isolation_guc_unset_denies_all_tenant_tables(rls, iso_tenants):
    """The kernel's whole reason to exist, against a real Postgres.

    Everything above this line runs on a recording cursor: it proves BE-01
    ISSUES the right `set_config` statements. This proves those statements
    MATTER — that with the GUC unset the B2 §3 policies deny every tenant
    table, and that under A's GUC not one of B's rows is reachable. Asserted
    under a non-superuser role (tests/isolation_helpers.py explains why).
    """
    tenant_a, tenant_b = iso_tenants
    probe_tables = ("uoms", "number_series", "users", "rate_plans", "audit_log")

    with live_tenant_context(tenant_a.id):
        a_uom = Uom.objects.create(tenant=tenant_a, code="kWh", name="Kilowatt hour")
    with live_tenant_context(tenant_b.id):
        b_uom = Uom.objects.create(tenant=tenant_b, code="kgal", name="Thousand gallons")

    # 1 · no context → the ::uuid cast of '' fails → NO row on ANY tenant table.
    assert_denied_without_context(rls, *probe_tables)

    # 2 · A's context → A's row, and only A's row.
    with live_tenant_context(tenant_a.id) as tid:
        assert tid == tenant_a.id
        assert current_guc() == str(tenant_a.id)  # the kernel really SET it
        assert rls.ids("uoms") == {str(a_uom.id)}

    # 3 · B's context → B's row; A's is not merely filtered, it is unreachable.
    with live_tenant_context(tenant_b.id):
        assert rls.ids("uoms") == {str(b_uom.id)}
        assert rls.count("uoms", "id = %s", [str(a_uom.id)]) == 0

    # 4 · leaving the context clears it: the connection cannot carry A's
    #     identity into whoever it serves next (the try/finally in BE-01).
    assert current_guc() == ""
    assert_denied_without_context(rls, *probe_tables)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-01@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 15/15✔ (this file; mocked cursor, no live DB) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py) · [path-tenancy lane 2026-08-10] TC-1/2/3 rewritten from Host labels to path segments; the three subdomain_of TCs were DELETED with the function; TC-14b/14c, TC-16 (platform segments ⊆ reserved names) and TC-17 (tenant_path) are new
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
