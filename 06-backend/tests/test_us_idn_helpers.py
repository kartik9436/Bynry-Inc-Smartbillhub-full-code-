# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures/helpers for the US-IDN-001..010 per-TC test files
#            (no TCs live here). Wiring notes below are the honest record of
#            what the sqlite unit tier CAN and CANNOT prove.
# ───────────────────────────────────────────────────────
"""Shared wiring for the identity story tests (imported by name into each
tests/test_us_idn_*.py file).

What this fixture wires, and why it is honest:
- Tenant context: on sqlite, core.tenancy's DB cursor is replaced with a no-op
  recorder (sqlite has no set_config; the parameterized-SQL behavior is BE-01's
  own suite). On PostgreSQL the REAL connection is left in place, so the
  @pytest.mark.isolation cases in this tier drive the shipping GUC end to end.
  A real slug→tenant_id resolver is registered either way, so the BE-01
  middleware resolves tenants exactly as in production.
- Paths: every request goes through `/api/{tenant}/…` (PO ruling 2026-08-10,
  path tenancy). `api_path()` below is the ONE place that knows the shape, and
  it also knows the no-tenant surface — the public reads, POST /api/tenants and
  the platform resources /api/jobs, /api/exports — so a test can hand it either
  kind of path and get the right URL.
- Audit: a recording sink (core.audit contract). The real single-INSERT sink
  registration belongs to apps.audit's US-AUD-003 lane, not this one.
- Time: services._now is a controllable clock (lockout/expiry TCs).
- Hashing: MD5PasswordHasher for test speed (check_password contract only).
"""

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.hashers import make_password
from django.db import connection as db_connection
from django.test import Client
from django.utils import timezone

from apps.identity import services
from apps.identity.models import Role, Session, TenantMembership, User
from apps.tenancy.models import Tenant
from core import audit as core_audit
from core import tenancy as core_tenancy
from tests.isolation_helpers import writing_as_tenant

# One origin, two tenants — the whole point of the 2026-08-10 ruling and the
# reason the session-binding control exists. These are PATH segments now, not
# hostnames; every request in this tier goes to the same host.
SC = "silvercreek"
BM = "bluemesa"
JSON = "application/json"

#: First segments under /api/ that carry NO tenant (config/urls.py mounts them
#: beside the tenant include). Mirrors core.tenancy.NON_TENANT_SEGMENTS; the
#: kernel's own test asserts that list against the reserved-name list, and this
#: one exists so a test can pass "/exports" or "/audit-log" without caring.
#  `tenants` is deliberately absent: POST /api/tenants is handled by the exact
#  match below, while /tenants/checklist is a TENANT-scoped A11 path.
_NO_TENANT_FIRST_SEGMENTS = ("public", "jobs", "exports", "health")


def api_path(path: str, tenant: str = SC) -> str:
    """The URL a client would actually call for `path` (PO ruling 2026-08-10).

    "/users"          → "/api/silvercreek/users"
    "/exports"        → "/api/exports"            (platform, no tenant)
    "/api/jobs/{id}"  → unchanged                 (already a server-issued URL,
                                                   e.g. a 202's status_url)
    """
    if path.startswith("/api/") or path == "/api":
        return path
    if path == "/tenants":  # provisioning: the tenant does not exist yet
        return "/api/tenants"
    first = path.lstrip("/").split("/", 1)[0].split("?", 1)[0]
    if first in _NO_TENANT_FIRST_SEGMENTS:
        return "/api" + path
    return f"/api/{tenant}{path}"


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        return None


class _FakeConnection:
    def cursor(self):
        return _FakeCursor()


class Clock:
    """Frozen-time stand-in for services._now (BR-IDN-025 lockout timing)."""

    def __init__(self):
        self.current = timezone.now()

    def __call__(self):
        return self.current

    def advance(self, **kwargs):
        self.current += timedelta(**kwargs)


class IdentityEnv:
    def __init__(self, rows, clock):
        self.rows = rows  # recorded audit rows (dicts)
        self.clock = clock
        self.silvercreek = Tenant.objects.create(name="Silver Creek Water", subdomain="silvercreek")
        self.bluemesa = Tenant.objects.create(name="Blue Mesa Utilities", subdomain="bluemesa")

    # ── fixtures-on-demand (US-IDN-001/004 §4 test data) ────────────────────
    def make_user(
        self,
        tenant,
        email,
        name,
        *,
        password=None,
        role="billing_clerk",
        status=TenantMembership.STATUS_ACTIVE,
        last_active=None,
        must_change=False,
        temp_expires=None,
    ):
        # ⚠ INSIDE THE TENANT'S OWN CONTEXT, THROUGH THE SHIPPING KERNEL
        # (DEF-GOV-4024/4036, 2026-09-05). `users` and `tenant_memberships`
        # both carry FORCE ROW LEVEL SECURITY, so the policy's WITH CHECK
        # applies to the table owner too and refuses an INSERT made with no
        # `app.tenant_id`. These two creates ran contextless for months and
        # were accepted only because the test connection was a SUPERUSER,
        # which bypasses RLS entirely — the refusal is hard rule 1 working.
        # `writing_as_tenant` restores whatever context the caller had, so a
        # test that seeds from inside its own `tenant_context` keeps it.
        with writing_as_tenant(tenant):
            user = User.objects.create(
                tenant=tenant,
                email=email,
                full_name=name,
                password_hash=make_password(password) if password else None,
                must_change_password=must_change,
                temp_password_expires_at=temp_expires,
            )
            membership = TenantMembership.objects.create(
                tenant=tenant,
                user=user,
                role=Role.objects.get(code=role),
                status=status,
                last_active_at=last_active,
            )
        return user, membership

    def seed_silvercreek(self):
        now = self.clock()
        users = SimpleNamespace()
        users.alex, users.alex_m = self.make_user(
            self.silvercreek,
            "alex@silvercreek.example",
            "Alex Reed",
            password="Canyon2026rapids",
            role="system_admin",
            last_active=now,
        )
        users.priya, users.priya_m = self.make_user(
            self.silvercreek,
            "priya@silvercreek.example",
            "Priya Menon",
            password="Meadow2026sage",
            role="billing_clerk",
            last_active=now - timedelta(hours=2),
        )
        users.diana, users.diana_m = self.make_user(
            self.silvercreek,
            "diana@silvercreek.example",
            "Diana Chen",
            password="Vista2026peak",
            role="executive",
            last_active=now - timedelta(days=3),
        )
        users.marcus, users.marcus_m = self.make_user(
            self.silvercreek,
            "marcus@silvercreek.example",
            "",
            password="Temp-Mrcs-2026",
            role="billing_clerk",
            status=TenantMembership.STATUS_INVITED,
            must_change=True,
            temp_expires=now + timedelta(days=7),
        )
        users.carla, users.carla_m = self.make_user(
            self.silvercreek,
            "carla@silvercreek.example",
            "Carla Ortiz",
            password="River2026stone",
            role="billing_clerk",
            status=TenantMembership.STATUS_DEACTIVATED,
            last_active=now - timedelta(days=30),
        )
        return users

    def seed_bluemesa_admin(self):
        jordan, jordan_m = self.make_user(
            self.bluemesa,
            "jordan@bluemesa.example",
            "Jordan Ellis",
            password="Mesa2026bluff",
            role="system_admin",
        )
        return jordan, jordan_m

    # ── audit-row helpers ───────────────────────────────────────────────────
    def actions(self):
        return [row["action"] for row in self.rows]

    def rows_for(self, action):
        return [row for row in self.rows if row["action"] == action]


@pytest.fixture()
def idn(db, settings, monkeypatch):
    settings.ALLOWED_HOSTS = ["*"]
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    if db_connection.vendor != "postgresql":
        # sqlite has no set_config — record the statements instead. On Postgres
        # the SHIPPING kernel writes the real GUC, which is what the
        # @pytest.mark.isolation cases in this tier exist to exercise.
        monkeypatch.setattr(core_tenancy, "connection", _FakeConnection())
    # Save-and-restore (not clear): other lanes may have registered the real
    # resolver/sink at AppConfig.ready — leave the process as we found it.
    previous_resolver = core_tenancy._tenant_resolver
    previous_sink = core_audit._sink
    core_tenancy.set_tenant_resolver(
        lambda sub: Tenant.objects.filter(subdomain=sub).values_list("id", flat=True).first()
    )
    rows: list[dict] = []
    core_audit.set_audit_sink(rows.append)
    clock = Clock()
    monkeypatch.setattr(services, "_now", clock)
    try:
        yield IdentityEnv(rows, clock)
    finally:
        core_audit.set_audit_sink(previous_sink)
        core_tenancy.set_tenant_resolver(previous_resolver)
        core_tenancy._current_tenant.set(None)


# ── request helpers (every call names its TENANT — path-first law) ──────────
def api_sign_in(client, email, password, *, tenant=SC, keep_signed_in=False, ip=None):
    extra = {"REMOTE_ADDR": ip} if ip else {}
    return client.post(
        api_path("/auth/session", tenant),
        data={"email": email, "password": password, "keep_signed_in": keep_signed_in},
        content_type=JSON,
        **extra,
    )


def signed_in_client(email, password, *, tenant=SC, keep_signed_in=False, ip=None):
    client = Client()
    response = api_sign_in(
        client, email, password, tenant=tenant, keep_signed_in=keep_signed_in, ip=ip
    )
    assert response.status_code == 201, response.content
    return client


def api_get(client, path, *, tenant=SC, ip=None, **extra):
    if ip:
        extra["REMOTE_ADDR"] = ip
    return client.get(api_path(path, tenant), **extra)


def api_post(client, path, payload=None, *, tenant=SC, ip=None, **extra):
    if ip:
        extra["REMOTE_ADDR"] = ip
    return client.post(api_path(path, tenant), data=payload or {}, content_type=JSON, **extra)


def api_patch(client, path, payload, *, tenant=SC, ip=None, **extra):
    if ip:
        extra["REMOTE_ADDR"] = ip
    return client.patch(api_path(path, tenant), data=payload, content_type=JSON, **extra)


def api_put(client, path, payload, *, tenant=SC, ip=None, **extra):
    if ip:
        extra["REMOTE_ADDR"] = ip
    return client.put(api_path(path, tenant), data=payload, content_type=JSON, **extra)


def api_delete(client, path, *, tenant=SC, ip=None, **extra):
    if ip:
        extra["REMOTE_ADDR"] = ip
    return client.delete(api_path(path, tenant), **extra)


def session_id_of(client) -> str:
    return client.cookies["sbh_session"].value


def client_with_session(session_id: str) -> Client:
    client = Client()
    client.cookies["sbh_session"] = session_id
    return client


def body_without_trace(response) -> dict:
    body = json.loads(response.content)
    body.pop("trace_id", None)
    return body


def live_sessions_for(user) -> int:
    return Session.objects.filter(user=user, revoked_at__isnull=True).count()


def random_uuid() -> str:
    return str(uuid.uuid4())
