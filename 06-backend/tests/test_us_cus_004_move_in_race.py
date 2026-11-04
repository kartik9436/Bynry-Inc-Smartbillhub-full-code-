# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (EP-CUS-02 S19 Move-In — the second door onto a unit) ·
#           US-CUS-005 (the move-out that frees it first)
#           Screens: S19 · S20
# Rules:    BR-CUS-017 (at most ONE active account per unit — the rule with NO
#           database half, OQ-092 CLOSED option (a)) · BR-CUS-030 (move-out
#           frees the unit) · BR-CUS-056 (the outgoing account owns the move
#           day) · BR-MET-036 (occupancy derives from the active account)
# Journeys: T5-15 step 4 — "two clerks submit move-ins for vacant 4C
#           simultaneously → one wins; the loser hits the same conflict.
#           Post-race: exactly one active account on 4C" — the journey says
#           MOVE-INS, and until this lane there was no move-in path to say it
#           about. T5-15 step 5 is the flow the race runs on.
# Tests:    this file IS the test half for the move-in path; the refusal +
#           ordering halves are 06-backend/tests/test_us_cus_004_005_move_in_out.py,
#           and the same proof for the CREATE path is
#           06-backend/tests/test_us_cus_003_account_race.py
# Note:     Every case here carries @pytest.mark.isolation + @requires_postgres.
#           Advisory locks do not exist on sqlite, so a green sqlite run proves
#           NOTHING about this race — the cases skip there with a vendor reason
#           and run on the live cluster (tests/isolation_helpers.py).
# ───────────────────────────────────────────────────────
"""BR-CUS-017's concurrency half for MOVE-IN — proved on a live PostgreSQL cluster.

WHY A SECOND RACE FILE
----------------------
tests/test_us_cus_003_account_race.py proves the scope lock for `create_account`.
That proof does not transfer: `move_in` is a DIFFERENT entry point onto the same
unit, and the failure it would hide is not "the guard is broken" but "the new
door does not use it". A move-in that carried its own copy of the occupancy
check would pass every refusal test in the suite — sequential calls always see
the committed winner — and still let two clerks moving the same tenant in at the
same moment both succeed, because on a VACANT unit there are no rows for
`SELECT … FOR UPDATE` to lock:

    clerk A: move-in on freed unit U → occupancy check → none
    clerk B: move-in on freed unit U → occupancy check → none   (A uncommitted)
    clerk A: INSERT active account   → ok
    clerk B: INSERT active account   → ok
    result:  one meter, two accounts, two bills

What closes it is the lock on the (tenant, unit) SCOPE, taken inside the write
transaction and BEFORE the check. The claim proved here is that the move-in path
takes THAT lock — the same namespace, the same key — and not one of its own.

The proof is by composition, exactly as the create-path file argues it:

  1. `move_in` really holds the scope, asserted from a SECOND, INDEPENDENT
     PostgreSQL session — the only vantage point from which "another request"
     means anything.
  2. A second session attempting the same scope BLOCKS (statement_timeout, the
     way a queued web worker waits for real).
  3. It is per (tenant, unit): another unit's key stays free.
  4. It is LOAD-BEARING: with `lock_unit_scope` neutralised the same probe
     returns True — the RED half, kept permanently rather than performed once.
  5. Once the winner commits, the loser's check sees its row and REFUSES, so
     blocking converts into a 409 rather than into a second account.

Ordering (lock BEFORE check) is asserted vendor-agnostically for the move-in
path in tests/test_us_cus_004_005_move_in_out.py. Lock + ordering + refusal is
the whole argument, and no part of it is a comment.

A two-thread end-to-end variant is NOT written here, for the reason the create
race file records: it needs `django_db(transaction=True)`, whose flush teardown
deletes the migration-seeded platform rows every later test in the session
depends on.
"""

from types import SimpleNamespace

import pytest
from django.db import connection, transaction

from apps.customers import models as customers_models
from apps.identity import models as identity_models
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import tenancy as core_tenancy

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    live_tenant_context,
    requires_postgres,
    rls_probe_role,
)
from tests.test_us_cus_003_account_race import SecondSession
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    provisioned_tenant,
    seeding_ctx,
)

pytestmark = pytest.mark.django_db


def admin_actor():
    """A system admin backed by a REAL `users` row.

    ⚠ **THE SHARED `admin_actor()` IS A `SimpleNamespace` CARRYING A RANDOM
    UUID, AND `move_records.performed_by` IS A GENUINE FOREIGN KEY TO `users`**
    (`customers/0030_cr039_wd_move_records`). Every move this file makes writes
    a move record naming its actor, so the shared helper plants a key that
    matches no user; PostgreSQL reports it at Django's
    `SET CONSTRAINTS ALL IMMEDIATE` in teardown, which surfaces as an ERROR on a
    test that otherwise PASSED.

    It had never been reached: until 2026-09-05 every case in this file died in
    its own fixture, before any move record existed (`BR-MET-119` — the premises
    was not carrying a service list). The foreign key is right — a move record
    says who performed the move — so the fixture grows a real clerk rather than
    the column losing its constraint.

    One row per tenant, reused, so every move in a test names the same person.
    Written through `seeding_ctx` because `users` carries FORCE row-level
    security and a create with no `app.tenant_id` is refused (DEF-GOV-4036).
    """
    tenant_id = core_tenancy.current_tenant_id()
    assert tenant_id is not None, (
        "admin_actor() must be called inside the tenant's own context — the "
        "user row it needs is tenant-scoped and RLS refuses a contextless write"
    )
    with seeding_ctx(tenant_id):
        user, _ = identity_models.User.objects.get_or_create(
            tenant_id=tenant_id,
            email="race-clerk@brazosbend.example",
            defaults={"full_name": "Race Clerk"},
        )
    return SimpleNamespace(id=user.id, role="system_admin")

LOCK_NAMESPACE = customers_services.UNIT_ACCOUNT_LOCK_NAMESPACE
MOVE_OUT_DAY = "2026-08-14"
MOVE_IN_DAY = "2026-08-15"


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
    """T5-15's "Unit 4C". Built with metering's models rather than its services
    so the fixture cost stays off the clock this test is measuring."""
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


def _freed_unit(tenant, label="Unit 4C"):
    """A unit whose previous tenancy has been MOVED OUT — the state a chained
    move-in starts from, and the state that did not exist before this lane
    (T5-15 step 5's recovery door). Returns the outgoing account."""
    unit = _unit_with_plan(tenant, label=label)
    outgoing = customers_services.create_account(
        admin_actor(),
        {
            "unit_id": str(unit.id),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
        },
    )
    customers_services.move_out(admin_actor(), outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})
    return unit, outgoing


def _unit_with_an_unlocked_predecessor(tenant, label="Unit 4C"):
    """A vacant unit plus a predecessor account to chain the move-in off —
    where the predecessor is a DRAFT, deliberately.

    Found by running the first draft of this file against the live cluster: a
    fixture that MOVED an occupant OUT leaves the scope lock held for the whole
    test, because `pg_advisory_xact_lock` releases at the OUTERMOST transaction
    end and pytest-django never commits the per-test transaction. The fixture's
    own `create_account` would then be holding the very key this file is trying
    to watch `move_in` take, and every assertion below would be about the
    fixture rather than about the move-in.

    A `pending_activation` draft takes no lock at all — BR-CUS-018: it "never
    derives occupancy", so `_make_occupying` is never called for it — which
    leaves the scope observably FREE at the start of the test. The draft is a
    legitimate predecessor: `move_in` reads only its `unit_id`, and the vacancy
    of the unit is decided by the BR-CUS-017 check, not by the predecessor's
    status.

    The move-out → move-in shape is exercised end to end in
    tests/test_us_cus_004_005_move_in_out.py, which does not need to observe
    locks and therefore does not have this problem.
    """
    unit = _unit_with_plan(tenant, label=label)
    predecessor = customers_services.create_account(
        admin_actor(),
        {"unit_id": str(unit.id), "account_type": "residential", "opened_at": "2026-07-01"},
    )
    assert predecessor["status_behavior_class"] == "non_billable"  # took no lock
    return unit, predecessor


def _move_in_payload(**overrides):
    payload = {"account_type": "residential", "opened_at": MOVE_IN_DAY}
    payload.update(overrides)
    return payload


def _this_backend_pid() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


# ══════════════════════════════════════════════════════════════════════════
# The proof
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_cus_004_tc6__a_move_in_holds_the_unit_scope_against_another_session(
    growth_plan, identity_seam, other_session
):
    """T5-15 step 4 for the MOVE-IN path: while clerk A's move-in is in flight,
    clerk B cannot even reach its own occupancy check.

    Proved RED two ways below — the same probe on a DIFFERENT unit is free, and
    with the guard neutralised the contended key is free too.
    """
    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit, predecessor = _unit_with_an_unlocked_predecessor(tenant)
        other_unit, _ = _unit_with_an_unlocked_predecessor(tenant, label="Unit 4D")
        key = customers_services.unit_lock_key(tenant.id, unit.id)
        other_key = customers_services.unit_lock_key(tenant.id, other_unit.id)

        assert other_session.backend_pid() != _this_backend_pid()
        # Baseline: the vacant unit's scope is unheld before anyone moves in.
        assert other_session.try_lock(key) is True
        other_session.release()

        with transaction.atomic():
            moved_in = customers_services.move_in(
                admin_actor(), predecessor["id"], _move_in_payload()
            )

            # 1 · clerk B cannot take the contended scope …
            assert other_session.try_lock(key) is False, (
                "the move-in path does not hold the (tenant, unit) scope — BR-CUS-017 has no "
                "database half (OQ-092 closed to service-layer enforcement), so a second door "
                "onto the unit that skips the lock lets two concurrent move-ins both pass their "
                "check and one meter gets two active accounts"
            )
            # 2 · … and really WAITS for it, rather than failing fast.
            assert other_session.blocks_on(key) is True
            # 3 · a different unit is untouched — the guard serializes the
            #     contended scope only, not every move-in in the tenant.
            assert other_session.try_lock(other_key) is True
            other_session.release()

        assert moved_in["status"] == "active"


@pytest.mark.isolation
@requires_postgres
def test_us_cus_004_tc6__without_the_guard_the_move_in_scope_is_wide_open(
    growth_plan, identity_seam, other_session, monkeypatch
):
    """The RED half, kept permanently rather than performed once at authoring
    time (hard-won law 7): neutralise `lock_unit_scope` and the very same probe
    that returned False now returns True — clerk B walks straight into its own
    check, which under READ COMMITTED cannot see clerk A's uncommitted row, and
    both writers insert.

    This is what makes the green assertion above evidence about the GUARD rather
    than about the surroundings."""
    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit, predecessor = _unit_with_an_unlocked_predecessor(tenant)
        key = customers_services.unit_lock_key(tenant.id, unit.id)
        monkeypatch.setattr(customers_services, "lock_unit_scope", lambda unit_id: False)
        with transaction.atomic():
            customers_services.move_in(admin_actor(), predecessor["id"], _move_in_payload())
            assert other_session.try_lock(key) is True
            other_session.release()


@pytest.mark.isolation
@requires_postgres
def test_us_cus_004_tc6__the_loser_of_two_move_ins_is_refused_once_the_winner_commits(
    growth_plan, identity_seam
):
    """The other end of the wait: after the winner's transaction ends, the
    loser's check sees the winner's row and refuses — so blocking converts into
    a 409 rather than into a second account (T5-15 step 4's "the loser hits the
    same conflict"; step 5's "sequential occupancy, never parallel").

    Both move-ins chain off the SAME outgoing account, which is exactly the
    double-submit a clerk produces by clicking "Complete move-in ✓" twice."""
    from core import errors

    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit, outgoing = _freed_unit(tenant)
        winner = customers_services.move_in(admin_actor(), outgoing["id"], _move_in_payload())

        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_in(admin_actor(), outgoing["id"], _move_in_payload())
        assert excinfo.value.br_ref == "BR-CUS-017"
        assert excinfo.value.params["account_no"] == winner["account_no"]

        occupying = customers_models.Account.objects.filter(
            tenant=tenant,
            unit=unit,
            status__behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES,
        )
        assert occupying.count() == 1  # T5-15: "exactly one active account on 4C"
        # …and the unit's history is sequential: the outgoing tenancy is still
        # closed, the incoming one is the only occupant.
        assert customers_models.Account.objects.filter(tenant=tenant, unit=unit).count() == 2


@pytest.mark.isolation
@requires_postgres
def test_us_cus_005_tc1__the_move_out_and_move_in_pair_serializes_on_one_key(
    growth_plan, identity_seam, other_session
):
    """T5-15 step 5's recovery door, from the locking side: the move-out and the
    move-in that follows it contend for the SAME (tenant, unit) scope — one key,
    one queue — so a clerk racing the turnover cannot slip an account in beside
    the one leaving.

    Asserted by running the real pair and watching the key from an independent
    session. A release-side assertion is NOT made here: `pg_advisory_xact_lock`
    releases at the OUTERMOST transaction end, pytest-django never commits the
    per-test transaction, and the property is already proved for this exact lock
    in tests/test_us_cus_003_account_race.py
    (`test_us_cus_001_tc5__the_scope_lock_is_released_when_the_transaction_ends`)
    — it is a property of the lock, not of these two flows."""
    tenant, _ = provisioned_tenant()
    with live_tenant_context(tenant.id):
        unit, predecessor = _unit_with_an_unlocked_predecessor(tenant)
        key = customers_services.unit_lock_key(tenant.id, unit.id)
        assert other_session.try_lock(key) is True
        other_session.release()

        # Occupy through the draft's activation, then move out, then move in —
        # the whole turnover, all on one key.
        customers_services.activate_account(admin_actor(), predecessor["id"])
        assert other_session.try_lock(key) is False
        customers_services.move_out(
            admin_actor(), predecessor["id"], {"moved_out_on": MOVE_OUT_DAY}
        )
        moved_in = customers_services.move_in(admin_actor(), predecessor["id"], _move_in_payload())
        assert moved_in["status"] == "active"
        assert other_session.try_lock(key) is False, (
            "the turnover pair must contend for ONE key — if move-in used a different "
            "scope than the create/activate path, this probe would be free while an "
            "account is being written"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-004@bbed56d (story+rules snapshot — EP-CUS-02 move-in story; co-packets US-CUS-005@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-11 by story-coder (W2 customers slice 3 — the BR-CUS-017 concurrency proof for the move-in door)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m isolation✔ (sqlite tier skips every case with the vendor reason) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: the proof is by COMPOSITION (scope lock held against a second session + lock-before-check ordering, asserted vendor-agnostically in tests/test_us_cus_004_005_move_in_out.py + refusal after the winner commits) rather than a two-thread end-to-end race — a threaded variant needs `django_db(transaction=True)`, whose flush teardown would delete the migration-seeded platform rows every later test in the session depends on (REPORTED, same disposition as the create-path race file) · `SecondSession` is IMPORTED from tests/test_us_cus_003_account_race.py rather than copied: two definitions of "an independent PostgreSQL session" would drift, and the create-path file is where it was first justified
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
