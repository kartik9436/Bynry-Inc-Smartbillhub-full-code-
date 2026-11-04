# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures/helpers for the US-TEN W0 feature-lane tests
#            (imported by tests/test_us_ten_*.py via `from ... import *`).
#            sqlite tier ONLY: the app.tenant_id GUC statements are recorded
#            against a fake connection (sqlite has no set_config); the
#            Python-side ContextVar mirror still drives every service/selector
#            tenant filter. ⚠ ON POSTGRES NOTHING IS FAKED — the SHIPPING kernel
#            writes the real GUC (DEF-2761; it was faked on both vendors until
#            2026-08-31, across 447 modules / 6,575 cases). Live-RLS behavior =
#            G5 isolation suite on Postgres.
# ───────────────────────────────────────────────────────
"""Shared plumbing for the tenancy story tests: sqlite-safe tenant context,
captured audit sink (BE-03 contract — capture, don't fake storage), the
identity-seam RECORDER (see `identity_seam` below), actors, and signup
payloads.

⚠ THIS DOCSTRING SAID THE IDENTITY SEAM FUNCTIONS WERE *"a documented seam,
not yet authored"* UNTIL 2026-09-01, AND THEY HAD BEEN AUTHORED FOR WEEKS
(DEF-566). That is hard-won law 1 read backwards: a comment claiming a GAP is
no more the gap than a comment claiming a guarantee is the guarantee, and this
one kept a write-nothing stub in front of a working function until the
sample-data collapse it caused (DEF-2395) cost three lanes an hour each."""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from django.db import connection  # the REAL one — `core_tenancy.connection` is what gets faked

from core import audit as core_audit
from core import tenancy as core_tenancy


class FakeCursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.log.append((sql, params))


class FakeGucConnection:
    """Records the set_config calls BE-01 would issue (sqlite cannot run them)."""

    def __init__(self):
        self.executed = []

    def cursor(self):
        return FakeCursor(self.executed)


class FakeUser:
    def __init__(self, user_id=None):
        self.id = user_id or uuid.uuid4()
        self.pk = self.id
        self.is_authenticated = True


def admin_actor():
    return SimpleNamespace(id=uuid.uuid4(), role="system_admin")


def clerk_actor():
    return SimpleNamespace(id=uuid.uuid4(), role="billing_clerk")


@pytest.fixture(autouse=True)
def sqlite_guc(monkeypatch, request):
    """GUC statements go to a recording fake ON SQLITE ONLY; the mirror is real.

    ⚠ **VENDOR-GUARDED SINCE DEF-2761 (2026-08-31). DO NOT REMOVE THE GUARD —
    IT IS THE WHOLE POINT OF THE FIXTURE, NOT A DETAIL OF IT.**

    Until that date this fixture patched `core.tenancy.connection` with
    `FakeGucConnection` UNCONDITIONALLY, and it is `autouse=True`. It is
    re-exported by `from tests.test_us_ten_helpers import *`, and through
    `test_us_met_helpers` → `test_us_met_reads_helpers` / `test_us_rat_helpers`
    that star-import chain reaches **447 collected test modules — 6,575 test
    cases**. In every one of them `set_config('app.tenant_id', …)` was written
    to a Python list and **never reached PostgreSQL**. Measured on live
    PostgreSQL 16.13, same connection, same transaction:

        core.tenancy.connection is  : FakeGucConnection
        ContextVar mirror says      : 11111111-1111-1111-1111-111111111111
        current_setting says        : '00000000-0000-0000-0000-000000000000'

    (the nil sentinel `apps/tenancy/migrations/0004_…` leaves on the session —
    castable, matches no row, i.e. deny-everything).

    **WHY THAT WAS INVISIBLE, and it is the repo's recurring shape — a check
    that cannot fail.** While the app role was `SUPERUSER` the missing marker
    could not be noticed, because RLS is bypassed and no policy is ever
    consulted: the run was green and had proved nothing about hard rule 1. So a
    green PostgreSQL run of those 447 modules was never evidence of tenant
    scoping. `DEF-2717`/`DEF-2760` revoked that bypass — `smartbillhub` is now
    `rolsuper=f rolbypassrls=f` — which is what made this measurable at all.

    On sqlite the recorder is still NECESSARY: sqlite has no `set_config()`, and
    without it every `tenant_ctx` dies on `sqlite3.OperationalError: no such
    function: set_config`. The Python-side ContextVar mirror drives the
    service/selector tenant filters on both vendors, so app-layer scoping is
    exercised either way; what only PostgreSQL can add is the DATABASE refusing
    the row, and that half must run against the SHIPPING kernel.

    This is not a new idea — it is the shape **four sibling fixtures already
    used**, and this autouse one was the only holdout:
    `test_us_idn_helpers.idn`, `test_bil_holiday_seam._tenant_guc`,
    `test_be_default_authentication.sqlite_tenant_guc`,
    `test_cr049_t1_document_store`'s shim, and `isolation_helpers`
    (`live_tenant_context` swaps the real connection BACK, which is why G5 has
    always been honest).

    ⚠ **THE TEARDOWN CLEARS THE REAL GUC ON POSTGRES, DELIBERATELY.** Django
    reuses one connection across the tests in a run. Leaving `app.tenant_id`
    set at the tenant the previous case adopted would let the NEXT case read
    that tenant's rows without ever asking for a tenant — a test that passes
    because of its neighbour is exactly the defect above wearing a different
    hat. Clearing through the shipping kernel puts every case back to
    deny-by-default, which is the posture a fresh production connection has.

    ⚠ **…BUT ONLY FOR A CASE THAT ACTUALLY HAS A DATABASE, AND THAT CONDITION
    IS NOT OPTIONAL.** This fixture is `autouse`, so it also runs for the pure
    unit cases in these modules — the ones with no `django_db` mark. Clearing
    the GUC opens a cursor, and pytest-django BLOCKS that for such a case:

        RuntimeError: Database access not allowed, use the "django_db" mark,
        or the "db" or "transactional_db" fixtures to enable it.

    A first draft of this fix did exactly that and turned every no-database
    case in 447 modules into an error. It was caught by running one such case
    on purpose rather than by any suite, because `-x` stops each module at its
    first failure and the database-backed cases fail earlier. Hence the
    `request.fixturenames` test below: it asks whether pytest-django has given
    this case a database, which is the same question, asked of the only object
    that can answer it.

    ⚠ `monkeypatch` is shared with every other fixture in the test (DEF-922):
    a `monkeypatch.undo()` anywhere lifts THIS patch too. Use a private
    `pytest.MonkeyPatch()` in a test that needs to undo something.
    """
    fake = None
    #: A case that pytest-django has given a database. Anything else must not
    #: touch the connection at all — see the second warning in the docstring.
    wants_db = {"db", "transactional_db"} & set(request.fixturenames)
    live_db = bool(wants_db)
    if live_db:
        # ⚠ NAMING THE FIXTURE IS NOT ENOUGH — IT HAS TO BE SET UP FIRST, AND
        # THIS ONE IS `autouse`, SO BY DEFAULT IT IS NOT. `request.fixturenames`
        # is the whole set pytest computed for the case, including fixtures that
        # have not run yet; an autouse fixture sorts AHEAD of an explicitly
        # requested one, so `db` was still pending and the blocker still armed:
        #
        #     RuntimeError: Database access not allowed, use the "django_db" mark
        #
        # in 3 of the 447 modules — the ones whose database arrives through a
        # chain rather than through the case's own signature. `getfixturevalue`
        # pulls it up to here, which is the only way to express "after that one"
        # from inside an autouse fixture.
        request.getfixturevalue("transactional_db" if "transactional_db" in wants_db else "db")
    if connection.vendor != "postgresql":
        fake = FakeGucConnection()
        monkeypatch.setattr(core_tenancy, "connection", fake)
    elif live_db:
        core_tenancy.clear_current_tenant()
    core_tenancy._current_tenant.set(None)
    try:
        yield fake
    finally:
        if connection.vendor == "postgresql" and live_db:
            core_tenancy.clear_current_tenant()
        core_tenancy._current_tenant.set(None)


@pytest.fixture(autouse=True)
def audit_rows():
    """BE-03 capture sink: every BR-TEN-016 row lands here for assertion.

    Save-and-restore, never clear: apps.audit registers the REAL sink at
    AppConfig.ready, and a fixture that hands back None instead of what it
    found silently disarms every later test that asserts the wiring
    (US-AUD-001 TC-4 is exactly that test). Same posture as the `idn` fixture.
    """
    previous = core_audit._sink
    rows = []
    core_audit.set_audit_sink(rows.append)
    yield rows
    core_audit.set_audit_sink(previous)


@pytest.fixture()
def identity_seam(monkeypatch):
    """RECORDER over the REAL identity seam (apps/tenancy/seams.py contract).

    ⚠ **IT USED TO BE A STUB THAT WROTE NOTHING, AND THAT WAS DEF-566 — THE
    HEAD OF THE CASCADE DEF-2395 IS ABOUT.** Until 2026-09-01 `provision_owner`
    here returned a bare `uuid.uuid4()` and created **no `users` row and no
    `tenant_memberships` row**. It called itself skip-until-wired; the real
    function has lived at `apps/identity/services.py:811` since long before,
    so the stub SHADOWED a working implementation and every tenant this
    harness provisioned — `brazos`, `lonestar`, and the several hundred tests
    behind them — had **no owner at all**.

    WHAT THAT COST, MEASURED ON REAL POSTGRESQL 16.13 (2026-09-01, this
    worktree): the sample plant on a harness tenant came to **16 of 17 blocks
    seeded, 1 failed** — `identity:seed_sample_records`, refusing with
    *"no sample staff user was created: this tenant has no ACTIVE System
    Admin"*, because `apps/identity/sample_data._owner_as_actor` looks for the
    ACTIVE System Admin membership `provision_owner` is contracted to write
    (`seams.py`: *"REQUIRED — an owner-less tenant would be half-seeded
    (BR-TEN-001), so provisioning refuses without it"*). With the seam real,
    the same run seeds **17 of 17**.

    ⚠ **AND THE FAILURE NAMED THE WRONG MODULE FOR THREE LANES.** Before
    DEF-2722/DEF-2795 put savepoints in the seeders, billing and payments
    collapsed BEHIND identity, so what a lane saw was a billing or a payments
    failure. Those savepoints hold now — the cascade is gone and only the head
    of it remained, which is this fixture.

    WHY IT IS STILL A FIXTURE AND NOT SIMPLY DELETED: it RECORDS. Nine
    assertions across `test_us_ten_001_004_provisioning.py` and
    `test_us_ten_019_sample_data.py` read `calls.provisioned`, `calls.sessions`
    and `calls.provision_owner` (the last so a test can re-install the seam
    after installing a fault stub over it). Every one of those still works: the
    recording is unchanged, and only the VALUES became real — a uuid7 owner id
    that a `users` row actually carries, and a session id that a `sessions` row
    actually carries.
    """
    import apps.identity.services as identity_services

    real_provision_owner = identity_services.provision_owner
    real_start_owner_session = identity_services.start_owner_session
    real_owner_email_for = identity_services.owner_email_for

    calls = SimpleNamespace(provisioned=[], owners={}, member_counts={}, sessions=[])

    def provision_owner(*, tenant_id, email, full_name, password, phone):
        owner_id = real_provision_owner(
            tenant_id=tenant_id,
            email=email,
            full_name=full_name,
            password=password,
            phone=phone,
        )
        calls.provisioned.append(
            {
                "tenant_id": tenant_id,
                "email": email,
                "full_name": full_name,
                "phone": phone,
                "owner_id": owner_id,
            }
        )
        calls.owners[str(tenant_id)] = email
        return owner_id

    def owner_email_for(tenant_id):
        return real_owner_email_for(tenant_id)

    def start_owner_session(*, tenant_id, user_id, ip=None, user_agent=None):
        """Seam half added by the 2026-08-10 path-tenancy lane: provisioning
        signs the owner in at commit (supersedes BR-TEN-045). It delegates for
        the same reason `provision_owner` now does — the owner id is a REAL
        `users` row, so the real function can hang a real session off it, which
        is what the `sessions[0]["session_id"] == cookie.value` assertions in
        `test_us_ten_001_004_provisioning.py` are checking."""
        session_id = real_start_owner_session(
            tenant_id=tenant_id, user_id=user_id, ip=ip, user_agent=user_agent
        )
        calls.sessions.append(
            {"tenant_id": tenant_id, "user_id": user_id, "ip": ip, "session_id": session_id}
        )
        return session_id

    calls.provision_owner = provision_owner  # so tests can re-install after a fault stub
    monkeypatch.setattr(identity_services, "provision_owner", provision_owner, raising=False)
    monkeypatch.setattr(identity_services, "owner_email_for", owner_email_for, raising=False)
    monkeypatch.setattr(
        identity_services, "start_owner_session", start_owner_session, raising=False
    )
    return calls


@pytest.fixture()
def growth_plan(db):
    """The S112 pre-selected SKU — READ from the catalog, not minted here.

    AMENDED 2026-08-10 (deploy-blocker lane, 09-infra/02 §10.3): until then this
    fixture created the row itself, which is precisely why the suite was green
    while a fresh production database had an EMPTY `subscription_plans` and every
    signup failed with `signup.plan_unknown`. The catalog is now platform
    reference data seeded by `apps/tenancy/migrations/0005_seed_subscription_plans.py`,
    so the fixture fetches it: if that migration ever stops seeding, every signup
    test fails at collection instead of quietly passing on a self-made row."""
    from apps.tenancy.models import SubscriptionPlan

    return SubscriptionPlan.objects.get(code="growth")


def brazosbend_payload(**overrides):
    """US-TEN-001 §4 signed test data."""
    payload = {
        "name": "Brazos Bend Utilities",
        "subdomain": "brazosbend",
        "state": "Texas",
        "services": ["electric", "water"],
        "currency": "USD",
        "plan": "growth",
        "load_defaults": True,
        "owner": {
            "full_name": "Dana Whitfield",
            "email": "dana@brazosbendutilities.com",
            "password": "S3cure!passw0rd",
            "phone": "+1 (281) 555-0164",
        },
    }
    payload.update(overrides)
    return payload


def lonestarridge_payload(**overrides):
    payload = brazosbend_payload(
        name="Lone Star Ridge Water Co-op",
        subdomain="lonestarridge",
        services=["water"],
        owner={
            "full_name": "J. Okafor",
            "email": "j.okafor@lsrwater.coop",
            "password": "An0ther!passw0rd",
            "phone": None,
        },
    )
    payload.update(overrides)
    return payload


def provisioned_tenant(payload=None):
    """Provision through the real service and return the Tenant row."""
    from apps.tenancy import models, services

    result = services.provision_tenant(payload or brazosbend_payload())
    return models.Tenant.objects.get(pk=uuid.UUID(result["id"])), result


def tenant_ctx(tenant):
    return core_tenancy.tenant_context(tenant.id)


@contextmanager
def seeding_ctx(tenant):
    """Enter a tenant's context for a direct-ORM fixture write, RESTORING
    whatever context was in force before rather than clearing it.

    ⚠ ADDED FOR DEF-2761 (2026-08-31), AND THE DIFFERENCE FROM `tenant_ctx`
    MATTERS. `core.tenancy.tenant_context` CLEARS on exit, which is exactly
    right for a request or a job — they own the connection for their whole
    life. A fixture helper does not: it is frequently called from inside a
    test's own `with tenant_ctx(...)`, and a helper that cleared on exit would
    silently drop the caller's context and leave the rest of that test denied
    by RLS. So this saves and puts back.

    WHY IT IS NEEDED AT ALL. Setting `tenant=tenant` as a COLUMN is not the
    same as being IN that tenant's context, and until DEF-2761 nothing in this
    suite could tell the difference: the autouse `sqlite_guc` fixture sent
    every `set_config('app.tenant_id', …)` to a Python list, and the app role
    was a superuser that bypassed row-level security anyway. Now the marker
    reaches PostgreSQL and the policies are enforced, a seed written outside
    any context is refused — and its READ is refused first, silently, which is
    why the symptom is `DoesNotExist` rather than a permission error.
    """
    previous = core_tenancy.current_tenant_id()
    tid = core_tenancy.set_current_tenant(getattr(tenant, "id", tenant))
    try:
        yield tid
    finally:
        if previous is None:
            core_tenancy.clear_current_tenant()
        else:
            core_tenancy.set_current_tenant(previous)


def audit_actions(rows):
    return [row["action"] for row in rows]


def api_call(
    view,
    method,
    path="/api",
    *,
    user=None,
    role=None,
    tenant=None,
    data=None,
    query=None,
    headers=None,
    body_format="json",
    **view_kwargs,
):
    """Call a DRF view function the way the wired stack would: authenticated
    user, server-attached tenant_role, BE-01 tenant context entered around the
    view (the middleware's job in production).

    `body_format="multipart"` is the file-upload path (BR-TEN-019 logo): the
    JSON renderer cannot carry bytes, so an upload test must post multipart
    exactly as the browser does."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    factory = APIRequestFactory()
    factory_method = getattr(factory, method)
    kwargs = {"format": body_format} if method in ("post", "put", "patch") else {}
    request = factory_method(path, data if data is not None else query, **kwargs)
    if headers:
        for name, value in headers.items():
            request.META["HTTP_" + name.upper().replace("-", "_")] = value
    if user is not None:
        force_authenticate(request, user=user)
    if role is not None:
        request.tenant_role = role
    if tenant is not None:
        request.tenant_id = tenant.id
        with core_tenancy.tenant_context(tenant.id):
            return view(request, **view_kwargs)
    return view(request, **view_kwargs)


# ══════════════════════════════════════════════════════════════════════════
# DEF-2964 — FAKE A MODULE'S SAMPLE BLOCKS BY ASKING WHICH ONES IT HAS
# ══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THE DEFECT THIS CLOSES, AND IT HAPPENED TWICE IN ONE DAY.** Six tests
# faked a module's sample seams by NAMING them — `monkeypatch.setattr(
# metering_services, "seed_sample_records", …)` and `…"seed_sample_reads"…` —
# and then asserted a total that added up only the blocks that existed when they
# were written (`7 + 3 = 10`). `apps.tenancy.sample_data.SAMPLE_MODULES` is the
# one place that answers *"which blocks does this module own"* and not one of
# them read it. Metering went from two blocks to three and then to four on
# 2026-09-01, and all six went red each time — every one of them for a reason
# its own docstring says nothing about.
#
# ⚠ **AND ONE OF THEM WENT RED IN A MISLEADING DIRECTION**, which is the part
# worth remembering: the block nobody had faked ran FOR REAL against a tenant
# with no estate and refused, so the module reported `failed` where the test had
# arranged `skipped` — a different fact, and worse-first hid the one under test.
# That is why `unwired` is a deliberate, named subset here rather than "whatever
# you forgot to patch".
def fake_module_seams(monkeypatch, module, *, count=1, unwired=()):
    """Fake EVERY block `module` owns, read off `SAMPLE_MODULES`.

    `count` is what each faked seam returns, so the expected total is
    `count * (len(seams) - len(unwired))` — DERIVED by the caller from the
    return value, never typed. `unwired` names blocks to REMOVE instead, which
    is how a test arranges "this module has an unwired block".

    Returns the block names it acted on, in planting order.
    """
    from importlib import import_module

    from apps.tenancy import sample_data as _orchestrator

    services = import_module(f"apps.{module}.services")
    seams = [spec.seam for spec in _orchestrator.SAMPLE_MODULES if spec.module == module]
    unknown = set(unwired) - set(seams)
    assert not unknown, f"{module} owns no block(s) named {sorted(unknown)} — {seams}"
    for seam in seams:
        if seam in unwired:
            monkeypatch.delattr(services, seam, raising=False)
        else:
            monkeypatch.setattr(services, seam, lambda actor, _n=count: _n, raising=False)
    return seams
