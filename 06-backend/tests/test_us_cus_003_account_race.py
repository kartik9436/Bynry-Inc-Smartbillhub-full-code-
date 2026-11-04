# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-003 (EP-CUS-02 S18 New Account — the write path) ·
#           US-CUS-001 (EP-CUS-01 TC-5, one active account per unit)
#           Screens: S17 · S18
# Rules:    BR-CUS-017 (at most ONE active account per unit — the rule with NO
#           database half, OQ-092) · BR-CUS-020 (vacant-unit picker) ·
#           BR-MET-036 (occupancy derives from the active account)
# Journeys: T5-15 step 4 — "two clerks submit move-ins for vacant 4C
#           simultaneously → one wins; the loser hits the same conflict.
#           Post-race: exactly one active account on 4C"
# Tests:    this file IS the test half; the refusal half is
#           06-backend/tests/test_us_cus_003_account_write.py
# Note:     Every case here carries @pytest.mark.isolation + @requires_postgres.
#           Advisory locks do not exist on sqlite, so a green sqlite run proves
#           NOTHING about this race — the cases skip there with a vendor reason
#           and run on the live cluster (tests/isolation_helpers.py).
# ───────────────────────────────────────────────────────
"""BR-CUS-017's concurrency half — proved on a live PostgreSQL cluster.

WHY THIS FILE EXISTS
--------------------
OQ-092 (CLOSED — PO 2026-08-10, option (a)) rules that "at most ONE active
account per unit" is enforced in the SERVICE LAYER ONLY: "the check runs inside
the create/update transaction with row locking so two concurrent requests
cannot both win, and a test proves the race is closed." This file is that test.

There is deliberately no unique constraint to catch the loser of a race — the
PROPOSED partial index is not constructible now that `status` is a PROTECTed FK
to `account_statuses`, and the ruling refuses a denormalised column that could
drift. Application code is the ENTIRE guard, and a check-then-insert in
application code is the textbook race:

    clerk A: SELECT occupying accounts for unit U  → none
    clerk B: SELECT occupying accounts for unit U  → none   (A has not committed)
    clerk A: INSERT active account                 → ok
    clerk B: INSERT active account                 → ok
    result:  one meter, two accounts, two bills

`SELECT … FOR UPDATE` cannot fix it: on a VACANT unit there are no rows to
lock. What closes it is a lock on the (tenant, unit) SCOPE — an advisory lock
taken inside the write transaction, before the check.

WHAT IS PROVED HERE, AND IN WHAT FORM
-------------------------------------
The proof is by composition, and each part is deterministic:

  1. `create_account`/`activate_account` really do take the scope lock, inside
     their own transaction — asserted from a SECOND, INDEPENDENT PostgreSQL
     session, which is the only vantage point from which "another request"
     means anything.
  2. A second session attempting the same scope BLOCKS — asserted by giving it
     a `statement_timeout` and watching the statement be cancelled, which is
     what a queued web worker does for real.
  3. The lock is per (tenant, unit): a different unit's key is free, so the
     guard serializes the contended scope and nothing else.
  4. It releases at transaction end (roles reversed: the second session holds,
     this one waits, the second rolls back, this one acquires).
  5. It is LOAD-BEARING: with `lock_unit_scope` neutralised the key stays free,
     which is the RED half — the guard, not the surroundings, is what holds it.

Ordering (lock BEFORE check) is asserted vendor-agnostically in
tests/test_us_cus_003_account_write.py, and the refusal the winner's commit
produces for the loser is asserted there too. Lock + ordering + refusal is the
whole argument, and no part of it is a comment.

A two-thread end-to-end variant is NOT written here on purpose: it needs
committed fixture data, i.e. `django_db(transaction=True)`, whose teardown
flushes the database — including the platform rows seeded by data migrations
(`account_types`, `services`, `subscription_plans`) that every later test in
the session depends on. Buying a nicer-looking test by breaking the suite it
runs in is not a trade this lane will make; it is recorded in the lane report
as the one shape of proof this harness cannot host.
"""

import pytest
from django.db import connection, transaction

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    admin_actor,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

LOCK_NAMESPACE = customers_services.UNIT_ACCOUNT_LOCK_NAMESPACE


class SecondSession:
    """An independent PostgreSQL session — a different backend PID, its own
    transaction, exactly like a second web worker.

    Everything the isolation suite normally asserts happens on ONE connection
    inside one transaction; a lock is the one thing that cannot be observed
    that way, because a session never blocks on itself.
    """

    def __init__(self) -> None:
        import psycopg

        settings = connection.settings_dict
        self.conn = psycopg.connect(
            dbname=settings["NAME"],
            user=settings["USER"] or None,
            password=settings["PASSWORD"] or None,
            host=settings["HOST"] or None,
            port=settings["PORT"] or None,
            autocommit=False,
        )

    def close(self) -> None:
        self.conn.rollback()
        self.conn.close()

    def backend_pid(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()")
            return cur.fetchone()[0]

    def try_lock(self, key: int) -> bool:
        """Non-blocking probe: False means "I would have had to wait"."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", (LOCK_NAMESPACE, key))
            return bool(cur.fetchone()[0])

    def blocks_on(self, key: int, timeout_ms: int = 750) -> bool:
        """Really WAIT for the lock, with a timeout. True = we were still
        waiting when the clock ran out, i.e. genuinely blocked."""
        import psycopg

        with self.conn.cursor() as cur:
            cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            try:
                cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (LOCK_NAMESPACE, key))
            except psycopg.errors.QueryCanceled:
                self.conn.rollback()
                return True
        return False

    def hold_lock(self, key: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (LOCK_NAMESPACE, key))

    def release(self) -> None:
        self.conn.rollback()


@pytest.fixture()
def other_session():
    session = SecondSession()
    yield session
    session.close()


def _plan(tenant, service_code="electric"):
    """A PUBLISHED rate plan for the unit to hold (PO ruling 2026-08-11).

    Was a `Tariff` — one service's prices — until a unit started holding the
    PLAN across its services. Only published plans are assignable (BR-RAT-030),
    so the status is not a default here.
    """
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name="Residential Standard",
        defaults={"code": "residential-standard", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"Residential Standard — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit_with_plan(tenant, label="Unit 4C"):
    """A vacant unit with a plan and one service point — the T5-15 fixture's
    "Unit 4C vacant". Built with metering's models rather than its services so
    the fixture cost stays off the clock this test is measuring."""
    premises = metering_models.Premises.objects.create(
        tenant=tenant,
        address_line="9 Brazos Bend Apartments",
        city="Katy",
        state="TX",
        # ⚠ THE ADDRESS MUST SAY WHAT IT OFFERS (BR-MET-119, added 2026-08-26 by
        # DEF-756/762). `ensure_service_point` below refuses a service the
        # premises does not offer, and `services_available=NULL` — the state
        # this fixture left it in — means *nobody has been asked*, which refuses
        # with `metering.premises_services_unknown`. That refusal is the product
        # working: an address nobody has been asked about has provisioned
        # nothing. A real premises carries the list, so the fixture does too.
        services_available=["electric"],
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, label=label, rate_plan=_plan(tenant)
    )
    metering_services.ensure_service_point(unit.id, "electric")
    return unit


def _payload(unit_id, **overrides):
    payload = {
        "unit_id": str(unit_id),
        "account_type": "residential",
        "opened_at": "2026-08-15",
        "status": "active",
    }
    payload.update(overrides)
    return payload


# ══════════════════════════════════════════════════════════════════════════
# The proof
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc5__a_create_holds_the_unit_scope_against_another_session(
    growth_plan, identity_seam, other_session
):
    """T5-15 step 4, the half a single connection can never show: while clerk
    A's create is in flight, clerk B cannot even reach its own check.

    Proved RED two ways below — the same probe on a DIFFERENT unit is free, and
    with the guard neutralised the contended key is free too.
    """
    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit = _unit_with_plan(tenant)
        other = _unit_with_plan(tenant, label="Unit 4D")
        key = customers_services.unit_lock_key(tenant.id, unit.id)
        other_key = customers_services.unit_lock_key(tenant.id, other.id)

        # Independent session, different backend — a second worker for real.
        assert other_session.backend_pid() != _this_backend_pid()
        # Baseline: nothing holds the scope before anyone writes.
        assert other_session.try_lock(key) is True
        other_session.release()

        with transaction.atomic():
            created = customers_services.create_account(admin_actor(), _payload(unit.id))

            # 1 · clerk B cannot take the contended scope …
            assert other_session.try_lock(key) is False, (
                "BR-CUS-017 has no database half (OQ-092 closed to service-layer "
                "enforcement): if the write path does not "
                "hold the (tenant, unit) scope, two concurrent creates both pass their "
                "check and one meter gets two active accounts"
            )
            # 2 · … and really WAITS for it, rather than failing fast.
            assert other_session.blocks_on(key) is True
            # 3 · a different unit is untouched — the guard serializes the
            #     contended scope only, not every account create in the tenant.
            assert other_session.try_lock(other_key) is True
            other_session.release()

        assert created["status"] == "active"


@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc5__the_scope_lock_is_released_when_the_transaction_ends(
    growth_plan, identity_seam, other_session
):
    """The loser must eventually get its turn — and then meet the refusal, not
    a deadlock. Roles reversed so the release can be observed from here."""
    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit = _unit_with_plan(tenant)
        key = customers_services.unit_lock_key(tenant.id, unit.id)

        other_session.hold_lock(key)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", [LOCK_NAMESPACE, key])
            assert cursor.fetchone()[0] is False  # held by the other session

        other_session.release()  # its transaction ends → the lock goes with it

        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", [LOCK_NAMESPACE, key])
            assert cursor.fetchone()[0] is True


@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc5__without_the_guard_the_scope_is_wide_open(
    growth_plan, identity_seam, other_session, monkeypatch
):
    """The RED half, kept permanently rather than performed once at authoring
    time (hard-won law 7): neutralise `lock_unit_scope` and the very same probe
    that returned False now returns True — clerk B walks straight into its own
    check, which under READ COMMITTED cannot see clerk A's uncommitted row, and
    both writers insert.

    This is what makes the green assertion above evidence about the GUARD
    rather than about the surroundings.
    """
    tenant, _ = provisioned_tenant()
    monkeypatch.setattr(customers_services, "lock_unit_scope", lambda unit_id: False)
    with live_tenant_context(tenant.id):
        unit = _unit_with_plan(tenant)
        key = customers_services.unit_lock_key(tenant.id, unit.id)
        with transaction.atomic():
            customers_services.create_account(admin_actor(), _payload(unit.id))
            assert other_session.try_lock(key) is True
            other_session.release()


@pytest.mark.isolation
@requires_postgres
def test_us_cus_003_tc8__the_scope_key_is_per_tenant_as_well_as_per_unit(
    growth_plan, identity_seam
):
    """Two tenants cannot collide on one another's units, and the key is stable
    across processes — `hash()` is salted per interpreter, so a key built from
    it would differ between web workers and guard nothing."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    unit_id = "019fed00-0000-7000-8000-000000000001"
    assert customers_services.unit_lock_key(brazos.id, unit_id) != customers_services.unit_lock_key(
        lonestar.id, unit_id
    )
    assert customers_services.unit_lock_key(brazos.id, unit_id) == customers_services.unit_lock_key(
        brazos.id, unit_id
    )
    # int4 range — pg_advisory_xact_lock(int4, int4) would error otherwise.
    for key in (
        customers_services.unit_lock_key(brazos.id, unit_id),
        customers_services.UNIT_ACCOUNT_LOCK_NAMESPACE,
    ):
        assert -(2**31) <= key < 2**31


@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc5__the_loser_of_the_race_is_refused_once_the_winner_commits(
    growth_plan, identity_seam
):
    """The other end of the wait: after the winner's transaction ends, the
    loser's check sees the winner's row and refuses — so blocking converts into
    a 409 rather than into a second account (T5-15 step 4's "the loser hits the
    same conflict")."""
    from core import errors

    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit = _unit_with_plan(tenant)
        winner = customers_services.create_account(admin_actor(), _payload(unit.id))
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.create_account(admin_actor(), _payload(unit.id))
        assert excinfo.value.br_ref == "BR-CUS-017"
        assert excinfo.value.params["account_no"] == winner["account_no"]
        occupying = customers_models.Account.objects.filter(
            tenant=tenant,
            unit=unit,
            status__behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES,
        )
        assert occupying.count() == 1  # T5-15: "exactly one active account on 4C"


def _this_backend_pid() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-003@bbed56d (story+rules snapshot — EP-CUS-02 lead story for the write path; co-packets EP-CUS-01@a2e1d59 · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers slice 2 — the BR-CUS-017 concurrency proof)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m isolation✔ (sqlite tier skips every case with the vendor reason) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: the proof is by COMPOSITION (scope lock held against a second session + lock-before-check ordering, asserted in test_us_cus_003_account_write.py + refusal after the winner commits) rather than a two-thread end-to-end race: a threaded variant needs `django_db(transaction=True)`, whose flush teardown would delete the migration-seeded platform rows every later test in the session depends on — REPORTED, not silently traded away · the RED half is kept as a permanent test (`without_the_guard_the_scope_is_wide_open`) instead of a one-off authoring-time demonstration
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
