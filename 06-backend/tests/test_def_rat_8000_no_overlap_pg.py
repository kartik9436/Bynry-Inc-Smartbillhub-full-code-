# ── Trace ──────────────────────────────────────────────
# Defect: DEF-RAT-8000 — B2 §2 signs an `EXCLUDE USING gist` no-overlap
#         constraint on `tariff_versions`; `rating/0001` never materialised it
#         (`btree_gist` was not installed), `rating/0004` reported that and
#         left it "for the human review of this row", and the review never
#         happened. A live tenant then ran four versions of one sewer schedule
#         in force on one date.
# Rules:  B2 §2 · BR-RAT-031 (a NULL `effective_from` IS the draft) ·
#         BR-RAT-104 / BR-RAT-1016 verb 2 (a CORRECTION restates the SAME
#         window) · CLAUDE.md hard-won law 14 (the suite runs SQLite, which
#         has neither gist nor an aborted-transaction state) · law 7 (prove a
#         guard RED before trusting it green, in the harness that runs it)
# ───────────────────────────────────────────────────────
"""`ex_tariff_versions_no_overlap`, asserted on the only engine that has it.

⚠ **SKIPPED ON SQLITE BY NAME, AND THE SKIP IS THE POINT.**
`config/settings/test.py` hardcodes in-memory SQLite, which has no range type,
no exclusion constraint and no `btree_gist`. The whole suite therefore runs
WITHOUT this guarantee, and a version of `rating/0047` that created nothing at
all would pass every other test in this repo, green, on every machine. That is
hard-won law 14's shape for DDL, and this file is the answer to it.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_def_rat_8000_no_overlap_pg.py

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked rather than assumed — and the
first draft of this file fell into the first of these, so it is not a
hypothetical list:
  * **THE DEFERRED CHECK NEVER HAPPENING.** Under `django_db` every test runs
    inside one transaction that is rolled back, so an `INITIALLY DEFERRED`
    constraint is never checked at all and BOTH kinds of case here pass
    vacuously — the refusals because nothing raises, the allowances because
    nothing could have. Every case calls `_check_now()`
    (`SET CONSTRAINTS ALL IMMEDIATE`) at the point where the answer is due.
  * **The constraint being absent.** A `pytest.raises(IntegrityError)` around
    an overlapping INSERT would go green if the INSERT failed for ANY other
    reason. So the first test reads `pg_constraint` and asserts the DEFINITION
    string — the predicate and `DEFERRABLE INITIALLY DEFERRED` included —
    rather than only the name.
  * **The constraint being too strict.** Three of these cases exist to prove
    what it must ALLOW: a clean handover, a saved draft beside a live version,
    and a correction. A no-overlap constraint that refuses corrections would
    make every one of `BR-RAT-1016`'s five priced objects unfixable, and it
    would pass a test that only checked refusals.
  * **The deferral being cosmetic.** `test_…_a_correction_commits` writes the
    two statements in the order `services.correct_rate_schedule_version`
    writes them — the new row first, the `superseded_by` stamp second. On an
    IMMEDIATE constraint the first statement fails. That test is the only
    thing in the repo that would notice the deferral being dropped.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS

pytestmark = pytest.mark.django_db(transaction=False)

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "SQLite has no range type, no exclusion constraint and no btree_gist, so "
        "this guarantee cannot exist there — skipping is honest; passing would be "
        "a lie (CLAUDE.md hard-won law 14)"
    ),
)

CONSTRAINT = "ex_tariff_versions_no_overlap"


def _definition() -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
            [CONSTRAINT],
        )
        row = cursor.fetchone()
    return row[0] if row else None


@pytest.fixture
def seed(env):
    """One tenant + one live schedule, then RAW SQL for everything after.

    The schedule is built through the ordinary service so the row is shaped
    like a real one. Every INSERT the tests then make is raw, and that is
    deliberate: this file is about what the DATABASE refuses, and going
    through a service would give the app-side guards (`_guard_window`,
    `_close_open_windows_before`) the chance to refuse first — law 7's
    *looking at the wrong thing*. The service-level half is
    `tests/test_def_rat_8001_windows_close.py`.

    ⚠ `app.tenant_id` is set for the raw cursor, because `tariff_versions`
    carries RLS FORCE and an unset setting returns zero rows — which would
    make every refusal test pass for the wrong reason (hard rule 1).
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(env.tenant.id)])
        # ⚠ **CLOSE THE FIXTURE'S OWN WINDOW, AND THE FIRST DRAFT OF THIS FILE
        # DID NOT.** `tiered_schedule` activates a version `2026-08-01 → open`,
        # and an OPEN window overlaps every date after it — so all five planted
        # cases below, including the three that must be ALLOWED, conflicted
        # with the fixture rather than with each other and the whole file
        # errored at teardown. The constraint was right and the fixture was
        # wrong, which is the only reason it was worth running.
        cursor.execute(
            "UPDATE tariff_versions SET effective_to = DATE '2026-12-31' "
            "WHERE tariff_id = %s AND effective_to IS NULL AND effective_from IS NOT NULL",
            [water["id"]],
        )
        cursor.execute(
            "SELECT v.tenant_id, v.tariff_id, v.model, v.currency, v.percent_basis "
            "FROM tariff_versions v WHERE v.tariff_id = %s LIMIT 1",
            [water["id"]],
        )
        row = cursor.fetchone()
    assert row is not None, "the fixture schedule is invisible — app.tenant_id or RLS"
    return row


def _check_now():
    """Force the DEFERRED constraint to be checked HERE.

    ⚠ **WITHOUT THIS EVERY CASE IN THIS FILE IS A CHECK THAT CANNOT FAIL
    (hard-won law 7), AND THE FIRST DRAFT PROVED IT.** `pytest.mark.django_db`
    wraps each test in one outer transaction that is ROLLED BACK, and nested
    `transaction.atomic()` blocks are SAVEPOINTs. A constraint declared
    `INITIALLY DEFERRED` is checked at COMMIT — a commit that never happens —
    so `pytest.raises(IntegrityError)` around two overlapping INSERTs simply
    never fired, and the three ALLOW cases would have passed just as happily
    against a constraint that refuses everything.

    `SET CONSTRAINTS ALL IMMEDIATE` checks every deferred constraint at this
    point instead. It is what Django's own `TestCase` teardown runs, one step
    earlier and inside the assertion.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _insert(tenant_id, tariff_id, model, currency, basis, lo, hi, superseded=None):
    new_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
            "percent_basis, notify_customers, publish_public, created_at, updated_at, "
            "effective_from, effective_to, superseded_by_version_id) VALUES "
            "(%s, %s, %s, %s, %s, %s, false, false, now(), now(), %s, %s, %s)",
            [new_id, tenant_id, tariff_id, model, currency, basis, lo, hi, superseded],
        )
    return new_id


@POSTGRES_ONLY
def test_def_rat_8000__btree_gist_is_installed():
    """A1. Without it `rating/0047`'s DDL cannot even parse, which is the whole
    reason B2 §2's constraint has never existed."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'btree_gist'")
        assert cursor.fetchone() is not None, (
            "btree_gist is absent — `rating/0045` did not run, or this database "
            "predates it and was never migrated"
        )


@POSTGRES_ONLY
def test_def_rat_8000__the_constraint_exists_with_the_predicate_it_needs():
    """Reading the NAME is not enough — the three deviations from B2 §2's
    literal text are each load-bearing and each is checked here.

    `rating/0047`'s docstring is the authority on why; this asserts they are
    still in the database rather than only in the docstring (hard-won law 1).
    """
    definition = _definition()
    assert definition is not None, f"{CONSTRAINT} is absent — `rating/0047` did not run"
    assert "EXCLUDE USING gist" in definition
    assert "tenant_id WITH =" in definition and "tariff_id WITH =" in definition
    # BR-RAT-031 — a dateless DRAFT has an unbounded-below daterange and would
    # otherwise overlap every dated version of its schedule.
    assert "effective_from IS NOT NULL" in definition
    # BR-RAT-104 / BR-RAT-1016 verb 2 — a correction restates the SAME window.
    assert "superseded_by_version_id IS NULL" in definition
    # `effective_to` is INCLUSIVE and `daterange` is half-open.
    assert "effective_to + 1" in definition
    # `correct_rate_schedule_version` holds two live rows on one window between
    # two statements of one transaction.
    assert "DEFERRABLE" in definition and "INITIALLY DEFERRED" in definition


@POSTGRES_ONLY
def test_def_rat_8000__two_open_windows_are_refused(seed):
    """The defect, in one INSERT. Ottumwa's shape."""
    tenant_id, tariff_id, model, currency, basis = seed
    with pytest.raises(IntegrityError) as refused:
        with transaction.atomic():
            _insert(tenant_id, tariff_id, model, currency, basis, date(2090, 1, 1), None)
            _insert(tenant_id, tariff_id, model, currency, basis, date(2090, 6, 1), None)
            _check_now()
    assert CONSTRAINT in str(refused.value)


@POSTGRES_ONLY
def test_def_rat_8000__an_end_that_touches_the_next_start_is_refused(seed):
    """⚠ THE CASE B2 §2's SIGNED EXPRESSION WOULD HAVE ALLOWED.

    `effective_to` is INCLUSIVE — `selectors.in_force_version` asks
    `effective_to >= service_date` — so a version ending 2091-06-30 and a
    version starting 2091-06-30 are BOTH in force on 2091-06-30, and
    `daterange(effective_from, COALESCE(effective_to,'infinity'))` says they do
    not overlap. One day of coin toss on a money path.
    """
    tenant_id, tariff_id, model, currency, basis = seed
    with pytest.raises(IntegrityError) as refused:
        with transaction.atomic():
            _insert(
                tenant_id, tariff_id, model, currency, basis,
                date(2091, 1, 1), date(2091, 6, 30),
            )
            _insert(tenant_id, tariff_id, model, currency, basis, date(2091, 6, 30), None)
            _check_now()
    assert CONSTRAINT in str(refused.value)


@POSTGRES_ONLY
def test_def_rat_8000__a_clean_handover_the_day_after_is_allowed(seed):
    """What every writer in `services` produces: `next_from - 1 day`."""
    tenant_id, tariff_id, model, currency, basis = seed
    with transaction.atomic():
        _insert(
            tenant_id, tariff_id, model, currency, basis, date(2092, 1, 1), date(2092, 6, 30)
        )
        _insert(tenant_id, tariff_id, model, currency, basis, date(2092, 7, 1), None)
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8000__a_draft_beside_a_live_version_is_allowed(seed):
    """BR-RAT-031 — `DEF-RAT-5680`'s parked draft on a live schedule. Without
    `WHERE effective_from IS NOT NULL` this INSERT would be refused and no
    tenant holding a draft could be migrated at all."""
    tenant_id, tariff_id, model, currency, basis = seed
    with transaction.atomic():
        _insert(tenant_id, tariff_id, model, currency, basis, date(2093, 1, 1), None)
        _insert(tenant_id, tariff_id, model, currency, basis, None, None)
        _check_now()


@POSTGRES_ONLY
def test_def_rat_8000__a_correction_commits_in_the_order_the_service_writes_it(seed):
    """⚠ THE DEFERRAL, AND THE ONLY TEST THAT WOULD NOTICE IT BEING DROPPED.

    `services.correct_rate_schedule_version` writes the correction row FIRST
    and stamps `superseded_by` on the original SECOND, in one
    `transaction.atomic()`. Between those two statements there are two LIVE
    rows on one window. An IMMEDIATE constraint refuses the first statement; a
    deferred one is checked at COMMIT, by which time the stamp is on.

    Refusing this would make every one of `BR-RAT-1016`'s five priced objects
    uncorrectable — the PO's own *"it is just an error handling"*.
    """
    tenant_id, tariff_id, model, currency, basis = seed
    with transaction.atomic():
        original = _insert(
            tenant_id, tariff_id, model, currency, basis, date(2094, 1, 1), date(2094, 12, 31)
        )
        correction = _insert(
            tenant_id, tariff_id, model, currency, basis, date(2094, 1, 1), date(2094, 12, 31)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tariff_versions SET superseded_by_version_id = %s WHERE id = %s",
                [correction, original],
            )
        # The whole point: the check lands HERE, after the stamp, not at the
        # INSERT above. An IMMEDIATE constraint would have refused that INSERT.
        _check_now()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM tariff_versions WHERE tariff_id = %s "
            "AND effective_from = %s AND superseded_by_version_id IS NULL",
            [tariff_id, date(2094, 1, 1)],
        )
        assert cursor.fetchone()[0] == 1


@POSTGRES_ONLY
def test_def_rat_8000__another_tenants_window_is_not_an_overlap():
    """`tenant_id WITH =` — hard rule 1's shape inside a constraint. Two
    utilities may price the same schedule id... they cannot, but the equality
    column is what makes the guarantee per-tenant rather than global, and a
    constraint missing it would refuse one tenant's window because another
    tenant had one."""
    definition = _definition()
    assert definition is not None
    assert definition.index("tenant_id WITH =") < definition.index("tariff_id WITH =")
