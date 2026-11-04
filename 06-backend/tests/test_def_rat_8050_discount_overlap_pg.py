# ── Trace ──────────────────────────────────────────────
# Defect: DEF-RAT-8050 — nothing in the database stops two versions of one
#         discount being in force on one date; no writer ever closed a
#         predecessor's window; and the two readers of `discount_versions`
#         resolved a tie by `.first()` on a money path.
# Rules:  B2 — ⚠ **DECLARES NOTHING FOR DISCOUNTS**, so this constraint
#         arrives with a B2 amendment and a review-ledger row · BR-RAT-1016
#         verb 2 (a CORRECTION restates the SAME window) · BR-RAT-031 (a
#         dateless draft) · CLAUDE.md hard-won law 14 (the suite runs SQLite,
#         which has neither gist nor an aborted-transaction state) · law 7
#         (prove a guard RED before trusting it green, in the harness that
#         runs it)
# ───────────────────────────────────────────────────────
"""`ex_discount_versions_no_overlap`, asserted on the only engine that has it.

⚠ **SKIPPED ON SQLITE BY NAME, AND THE SKIP IS THE POINT.**
`config/settings/test.py` hardcodes in-memory SQLite, which has no range type,
no exclusion constraint and no `btree_gist`. A version of `rating/0049` that
created nothing at all would pass every other test in this repo, green, on
every machine.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_def_rat_8050_discount_overlap_pg.py

⚠ **MEASURED 2026-09-29: 12 PASSED IN 400s, PLUS ONE TEARDOWN ERROR ON A BOX
WITH NO BROKER — AND IT IS NOT A FAILING ASSERTION.** Under `JOBS_EAGER=false`
something on the refusal path of
`test_…__active_version_refuses_rather_than_picking` queues a job, and `kombu`
then reports `Error 111 connecting to localhost:6379` at teardown. The test
BODY passed — pytest counts a teardown error separately — so all twelve
assertions held. Named here rather than left for the next reader to
re-diagnose: run with a broker up, or with `JOBS_EAGER=true`, if a clean
summary line matters. **Which job it is has NOT been chased and is not claimed
to be harmless**; it is outside this file's subject and it is written down
rather than swallowed.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked rather than assumed:
  * **THE DEFERRED CHECK NEVER HAPPENING.** Under `django_db` every test runs
    inside one transaction that is rolled back, so an `INITIALLY DEFERRED`
    constraint is never checked at all and BOTH kinds of case pass vacuously.
    Every case calls `_check_now()` (`SET CONSTRAINTS ALL IMMEDIATE`) at the
    point where the answer is due. `rating/0047`'s sibling file records that
    its first draft fell into exactly this, so it is not hypothetical.
  * **The constraint being absent.** `pytest.raises(IntegrityError)` goes
    green if the INSERT failed for ANY other reason, so the first test reads
    `pg_constraint` and asserts the DEFINITION — predicate and deferral
    included — rather than the name.
  * **The constraint being too strict.** Four cases exist to prove what it
    must ALLOW: a clean handover, a dateless draft beside a live version, a
    CORRECTION written in the order the service writes it, and — the one that
    is specific to this object — **a `scheduled` successor overlapping the
    incumbent's still-open window**, which is the ordinary shape of every
    approval on a live discount and which a `status IN ('active','scheduled')`
    predicate would have refused.
  * **The application-side refusals never firing.** They are asserted here
    too, against real rows, because they are the ONLY layer that exists on
    SQLite and a constraint cannot be relied on to be the thing that speaks.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db(transaction=False)

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "SQLite has no range type, no exclusion constraint and no btree_gist, so "
        "this guarantee cannot exist there — skipping is honest; passing would be "
        "a lie (CLAUDE.md hard-won law 14)"
    ),
)

CONSTRAINT = "ex_discount_versions_no_overlap"


def env_tenant(tenant_id):
    """The `Tenant` ROW for a tenant id — `tenant_ctx` takes the object."""
    from apps.tenancy.models import Tenant

    return Tenant.objects.get(pk=tenant_id)

INSERT = """
INSERT INTO discount_versions (
  id, tenant_id, discount_id, version_no, status, discount_type, value, currency,
  applies_to, bill_floor_amount, stacking_precedence, stacks_with_others,
  enrolment_mode, verification_method, proof_required, proof_before_first_reduction,
  recertification_notice_days, recertification_grace_days, lapse_behaviour,
  budget_period, exhaustion_behaviour, second_approval_required, self_approved,
  is_sample, created_at, updated_at, effective_from, effective_to
) VALUES (
  %s, %s, %s, %s, %s, 'percentage', 15, 'USD',
  'whole_bill', 0, 0, true,
  'automatic', 'automatic', false, false,
  60, 30, 'never_expires',
  'annual', 'suspend', false, false,
  false, now(), now(), %s, %s
)
"""


def _definition() -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
            [CONSTRAINT],
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _check_now() -> None:
    """Force the DEFERRED constraint to be checked HERE.

    ⚠ **WITHOUT THIS EVERY CASE IN THIS FILE IS A CHECK THAT CANNOT FAIL**
    (hard-won law 7). `pytest.mark.django_db` wraps each test in one outer
    transaction that is ROLLED BACK, and a nested `atomic()` is a SAVEPOINT. A
    constraint declared `INITIALLY DEFERRED` is checked at COMMIT — a commit
    that never happens.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.fixture
def seed(env):
    """One tenant + one discount, and RAW SQL for everything after.

    Raw on purpose: this file is about what the DATABASE refuses, and going
    through `discount_services` would give the app-side guards the chance to
    refuse first — law 7's *looking at the wrong thing*. The service-level
    half is asserted separately at the end of this file.

    ⚠ `app.tenant_id` is set for the raw cursor, because `discount_versions`
    carries RLS FORCE and an unset setting returns zero rows — which would
    make every refusal test pass for the wrong reason (hard rule 1).
    """
    tenant_id = env.tenant.id
    discount_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        cursor.execute(
            "INSERT INTO discounts (id, tenant_id, code, name, status, "
            "report_in_assistance_filing, is_sample, created_at, updated_at) "
            "VALUES (%s, %s, 'SENIOR-8050', 'Senior', 'active', false, false, now(), now())",
            [discount_id, tenant_id],
        )
    return tenant_id, discount_id


def _insert(tenant_id, discount_id, version_no, status, lo, hi):
    new_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute(INSERT, [new_id, tenant_id, discount_id, version_no, status, lo, hi])
    return new_id


# ── PART 1 · THE CONSTRAINT IS THERE, AND IS THE ONE THAT WAS ARGUED FOR ────


@POSTGRES_ONLY
def test_def_rat_8050__btree_gist_is_installed():
    """`rating/0045` is a dependency of this chain and not a coincidence:
    without it `rating/0049`'s DDL cannot even parse."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'btree_gist'")
        assert cursor.fetchone() is not None, "btree_gist is absent — `rating/0045` did not run"


@POSTGRES_ONLY
def test_def_rat_8050__the_constraint_exists_with_the_predicate_it_needs():
    """Reading the NAME is not enough — the four deviations from
    `rating/0047` are each load-bearing and each is asserted here rather than
    only argued in a docstring (hard-won law 1)."""
    definition = _definition()
    assert definition is not None, f"{CONSTRAINT} is absent — `rating/0049` did not run"
    assert "EXCLUDE USING gist" in definition
    assert "tenant_id WITH =" in definition and "discount_id WITH =" in definition
    # 1 · supersession on this object is a STATUS, not a foreign key.
    assert "status = 'active'" in definition
    assert "superseded_by" not in definition, (
        "the predicate names `superseded_by` — that is a SECOND representation of "
        "a fact the status already carries, which is what let the two readers of "
        "this table come apart in the first place"
    )
    # ⚠ and `scheduled` must NOT be inside it: see the allow case below.
    assert "scheduled" not in definition
    # 2 · a dateless draft has an unbounded-below daterange.
    assert "effective_from IS NOT NULL" in definition
    # 3 · `correct_discount_version` holds two ACTIVE rows on one window
    #     between two statements of one transaction.
    assert "DEFERRABLE" in definition and "INITIALLY DEFERRED" in definition
    # 4 · `effective_to` is INCLUSIVE and `daterange` is half-open.
    assert "effective_to + 1" in definition


# ── PART 2 · WHAT IT REFUSES ────────────────────────────────────────────────


@POSTGRES_ONLY
def test_def_rat_8050__two_open_active_windows_are_refused(seed):
    """The defect, in one transaction. Ottumwa's shape, one object over."""
    tenant_id, discount_id = seed
    with pytest.raises(IntegrityError) as refused:
        with transaction.atomic():
            _insert(tenant_id, discount_id, 1, "active", date(2090, 1, 1), None)
            _insert(tenant_id, discount_id, 2, "active", date(2090, 6, 1), None)
            _check_now()
    assert CONSTRAINT in str(refused.value)


@POSTGRES_ONLY
def test_def_rat_8050__the_same_date_tie_is_refused(seed):
    """Two ACTIVE versions starting on one day — the coin toss
    `active_version` used to settle with `.order_by(...).first()`."""
    tenant_id, discount_id = seed
    with pytest.raises(IntegrityError) as refused:
        with transaction.atomic():
            _insert(tenant_id, discount_id, 1, "active", date(2094, 1, 1), date(2094, 12, 31))
            _insert(tenant_id, discount_id, 2, "active", date(2094, 1, 1), date(2094, 12, 31))
            _check_now()
    assert CONSTRAINT in str(refused.value)


@POSTGRES_ONLY
def test_def_rat_8050__an_end_that_touches_the_next_start_is_refused(seed):
    """⚠ THE OFF-BY-ONE A HALF-OPEN `daterange` WOULD HAVE ALLOWED.

    `effective_to` is INCLUSIVE — `active_version` asks `effective_to >= when`
    — so a version ending 2091-06-30 and one starting 2091-06-30 are BOTH in
    force on 2091-06-30. One day of coin toss on a money path.
    """
    tenant_id, discount_id = seed
    with pytest.raises(IntegrityError) as refused:
        with transaction.atomic():
            _insert(tenant_id, discount_id, 1, "active", date(2091, 1, 1), date(2091, 6, 30))
            _insert(tenant_id, discount_id, 2, "active", date(2091, 6, 30), None)
            _check_now()
    assert CONSTRAINT in str(refused.value)


# ── PART 3 · WHAT IT MUST ALLOW, WHICH IS THE HALF THAT BREAKS A PRODUCT ────


@POSTGRES_ONLY
def test_def_rat_8050__a_clean_handover_the_day_after_is_allowed(seed):
    """What `_close_open_windows_before` produces: `next_from - 1 day`."""
    tenant_id, discount_id = seed
    with transaction.atomic():
        _insert(tenant_id, discount_id, 1, "active", date(2092, 1, 1), date(2092, 6, 30))
        _insert(tenant_id, discount_id, 2, "active", date(2092, 7, 1), None)
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8050__a_dateless_draft_beside_a_live_version_is_allowed(seed):
    """BR-RAT-031's shape. Without `WHERE effective_from IS NOT NULL` this
    INSERT would be refused and no tenant holding a draft could migrate."""
    tenant_id, discount_id = seed
    with transaction.atomic():
        _insert(tenant_id, discount_id, 1, "active", date(2093, 1, 1), None)
        _insert(tenant_id, discount_id, 2, "draft", None, None)
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8050__a_scheduled_successor_over_an_open_window_is_allowed(seed):
    """⚠ **THE CASE THAT DECIDES THE PREDICATE, AND IT IS SPECIFIC TO THIS
    OBJECT.**

    `scheduled` reads like *approved, holds a real future window, therefore
    belongs inside the constraint*. It does not. `activate_discount_version`
    supersedes by STATUS, so a live discount's `effective_to` stays NULL — an
    OPEN window — until its successor is activated. Put `scheduled` in the
    predicate and **approving any successor to any live discount is refused**,
    because that open window contains every future date.

    A `pending_approval` version collides the same way and for the same
    reason: a proposal is not a price.
    """
    tenant_id, discount_id = seed
    with transaction.atomic():
        _insert(tenant_id, discount_id, 1, "active", date(2095, 1, 1), None)
        _insert(tenant_id, discount_id, 2, "scheduled", date(2095, 6, 1), None)
        _insert(tenant_id, discount_id, 3, "pending_approval", date(2095, 6, 1), None)
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8050__a_correction_commits_in_the_order_the_service_writes_it(seed):
    """⚠ THE DEFERRAL, AND THE ONLY TEST THAT WOULD NOTICE IT BEING DROPPED.

    `correct_discount_version` creates the correction row **`active`, carrying
    the corrected row's window VERBATIM** — that identical window is the whole
    definition of a correction (BR-RAT-1016 verb 2) — and only THEN flips the
    original to `superseded`. On an IMMEDIATE constraint the INSERT fails and
    **every correction this product can take is refused.**
    """
    tenant_id, discount_id = seed
    with transaction.atomic():
        original = _insert(
            tenant_id, discount_id, 1, "active", date(2096, 1, 1), date(2096, 12, 31)
        )
        correction = _insert(
            tenant_id, discount_id, 2, "active", date(2096, 1, 1), date(2096, 12, 31)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE discount_versions SET status = 'superseded', "
                "superseded_by_version_id = %s WHERE id = %s",
                [correction, original],
            )
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8050__another_discount_of_the_same_tenant_is_untouched(seed):
    """The constraint keys on `discount_id`: two discounts may of course both
    be in force on one day, which is what a programme portfolio IS."""
    tenant_id, discount_id = seed
    other = uuid.uuid4()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO discounts (id, tenant_id, code, name, status, "
                "report_in_assistance_filing, is_sample, created_at, updated_at) "
                "VALUES (%s, %s, 'CAP-8050', 'Cap', 'active', false, false, now(), now())",
                [other, tenant_id],
            )
        _insert(tenant_id, discount_id, 1, "active", date(2097, 1, 1), None)
        _insert(tenant_id, other, 1, "active", date(2097, 1, 1), None)
        _check_now()


# ── PART 4 · THE APPLICATION LAYER, WHICH IS THE ONLY ONE SQLITE HAS ────────


@POSTGRES_ONLY
def test_def_rat_8050__active_version_refuses_rather_than_picking(seed):
    """`active_version` used to end `.order_by(…).first()` and its docstring
    called that *"deterministic"*. Deterministic is not correct: it picks one
    of two equally valid rows and reduces a bill by that figure.

    ⚠ The two rows are planted with the constraint DEFERRED and never
    committed — the point is what the READER does when it meets them, which
    is the state SQLite can always reach and PostgreSQL can reach inside one
    transaction.
    """
    from apps.rating import discount_services
    from apps.rating import discounts as discount_models

    tenant_id, discount_id = seed
    _insert(tenant_id, discount_id, 1, "active", date(2098, 1, 1), None)
    _insert(tenant_id, discount_id, 2, "active", date(2098, 1, 1), None)
    # ⚠ `_tenant_id()` reads the tenant CONTEXT, not the row — without
    # `tenant_ctx` the service raises `AUTH_TENANT_UNRESOLVABLE` and this test
    # would pass on a `pytest.raises(Exception)` for entirely the wrong
    # reason. That is law 7's *looking at the wrong thing*, which is why the
    # assertion names the message key rather than the exception type.
    with tenant_ctx(env_tenant(tenant_id)):
        discount = discount_models.Discount.objects.get(pk=discount_id)
        with pytest.raises(Exception) as refused:
            discount_services.active_version(discount, date(2098, 6, 1))
    assert "two_versions_in_force" in str(getattr(refused.value, "message_key", "")), (
        f"refused for the wrong reason: {refused.value!r}"
    )


@POSTGRES_ONLY
def test_def_rat_8050__active_version_still_answers_when_there_is_one(seed):
    """The mirror of the case above — a refusal that fires on the ordinary
    shape would be worse than the coin toss it replaced."""
    from apps.rating import discount_services
    from apps.rating import discounts as discount_models

    tenant_id, discount_id = seed
    live = _insert(tenant_id, discount_id, 1, "active", date(2099, 1, 1), None)
    _insert(tenant_id, discount_id, 2, "superseded", date(2098, 1, 1), date(2098, 12, 31))
    with tenant_ctx(env_tenant(tenant_id)):
        discount = discount_models.Discount.objects.get(pk=discount_id)
        answer = discount_services.active_version(discount, date(2099, 6, 1))
    assert answer is not None and str(answer.id) == str(live)
