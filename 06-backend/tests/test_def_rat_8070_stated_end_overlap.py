# ── Trace ──────────────────────────────────────────────
# Defect: DEF-RAT-8070 — a rate-schedule overlap where the EARLIER row's
#         `effective_to` is STATED and runs into the next row's start was
#         reported by the census as `SUCCESSION`, which that file's own header
#         calls *"repairable mechanically"*, while `rating/0046` refuses it by
#         name because only a NULL end is ever filled. The refusal then named
#         two remedies and neither could be carried out — a correction COPIES
#         the window, and nothing in the product moves a stated end — so a
#         deploy stopped with an instruction nobody could follow, for ever.
# Rules:  B2 §2 (the signed no-overlap constraint) · BR-RAT-007 (a period
#         prices on the version in force AT THE SERVICE DATE) · BR-RAT-031 (a
#         NULL `effective_from` IS the draft) · BR-RAT-1044 (a corrected row's
#         window is settled) · CLAUDE.md hard rule 1 (tenant scoping) · hard
#         rule 4 (an issued bill is reproduced from the version in force at its
#         service date) · hard rule 7 (every money action writes `audit_log`) ·
#         hard-won law 7 (prove a guard RED, in the harness that runs it)
# ───────────────────────────────────────────────────────
"""The shape that had no exit, and the door that now has one.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY**, asked rather than assumed:

  * **THE CLASSIFIER CASE PASSING BECAUSE BOTH KINDS ARE THE SAME WORD.** The
    whole defect is that one word covered two shapes, so a test asserting only
    *"it returns something"* would have passed on the broken version.
    `test_a_stated_end_is_not_reported_as_repairable` asserts the kind is NOT
    `SUCCESSION` **and** that a NULL-ended pair still IS — one case each way,
    because a classifier that answered `STATED-END` to everything would satisfy
    half of this and is just as wrong.

  * **THE COMMAND CASES PASSING BECAUSE THE COMMAND REFUSED FOR ANOTHER
    REASON.** `pytest.raises(CommandError)` around a management command goes
    green on a typo in the arguments. Every refusal here matches on the text of
    the rule it is refusing for, so a refusal that fires for the wrong reason
    fails.

  * **THE WRITE CASE PASSING WITHOUT WRITING.** It asserts the row's new
    `effective_to` **and** the `audit_log` row's `before`/`after` (hard rule 7),
    because an UPDATE with no trail is not the behaviour this command claims.

⚠ **THE POSTGRES-ONLY CASES ARE SKIPPED BY NAME ON SQLITE.** The default suite
hardcodes in-memory SQLite (`config/settings/test.py`), which has no
`to_regclass`, no RLS and no exclusion constraint — hard-won law 14. Run them:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_def_rat_8070_stated_end_overlap.py

⚠ **THE CLASSIFIER CASE IS NOT SKIPPED**, on purpose: it is pure Python over
two dicts, it is the regression that actually caused the loop, and a file where
every case skips on the default suite is a file nobody notices going red.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS

pytestmark = pytest.mark.django_db(transaction=False)

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "the command reads `to_regclass`, writes under RLS and records an `audit_log` "
        "row — none of which SQLite has, so passing there would be a lie (law 14)"
    ),
)

#: `10-scripts/` is not a package and is not importable by name. It is also not
#: in the deployed image, which is why the COMMAND lives in `06-backend/` — but
#: the census is still the repo's counting tool and its classifier is the thing
#: that mis-reported this shape, so the test loads it from its path.
_CENSUS_PATH = Path(__file__).resolve().parents[2] / "10-scripts" / "rat_schedule_overlap_census.py"


def _census_module():
    if not _CENSUS_PATH.exists():  # pragma: no cover — the repo always has it
        pytest.skip(f"census tool not present at {_CENSUS_PATH}")
    spec = importlib.util.spec_from_file_location("rat_schedule_overlap_census", _CENSUS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(lo: date, hi: date | None, *, superseded=None) -> dict:
    """One census row, shaped as `census()` shapes it before classifying."""
    census = _census_module()
    return {
        "effective_from": lo,
        "effective_to": hi,
        "superseded_by_version_id": superseded,
        "lo": lo,
        "hi": census._upper(hi),
        "tenant_name": "t",
        "tariff_name": "s",
    }


# ── THE CLASSIFIER: ONE WORD COVERED TWO SHAPES ───────────────────────────────
def test_a_stated_end_is_not_reported_as_repairable():
    """`2026-06-01 → 2026-07-31` beside `2026-07-31 → …` is the reported estate.

    RED before the fix: `_classify` returned `SUCCESSION`, and the census's own
    header calls that *"repairable mechanically"* — so the operator was told to
    migrate again and met the identical refusal, for ever.
    """
    census = _census_module()
    group = [_row(date(2026, 6, 1), date(2026, 7, 31)), _row(date(2026, 7, 31), date(2026, 8, 1))]

    kind = census._classify(group)

    assert kind != "SUCCESSION", (
        "a STATED end that runs into the next start is refused by rating/0046 — "
        "reporting it as the kind this file calls mechanically repairable is the loop"
    )
    assert kind == "STATED-END"
    assert kind in census.KINDS, "a kind that is counted and never printed reads as a zero"


def test_an_open_end_is_still_the_repairable_kind():
    """The mirror, so a classifier answering `STATED-END` to everything fails.

    `0046` pass 1 DOES fill this one: the older row's end is NULL and a later
    row starts, so the window closes at `next.effective_from - 1 day`.
    """
    census = _census_module()
    group = [_row(date(2026, 6, 1), None), _row(date(2026, 8, 1), None)]

    assert census._classify(group) == "SUCCESSION"


def test_the_discount_half_separates_the_same_two_shapes():
    """`rating/0048` carries `0046`'s rule verbatim, so its census half must too."""
    census = _census_module()
    stated = [_row(date(2026, 6, 1), date(2026, 7, 31)), _row(date(2026, 7, 31), None)]
    open_ended = [_row(date(2026, 6, 1), None), _row(date(2026, 8, 1), None)]

    assert census._discount_classify(stated) == "STATED-END"
    assert census._discount_classify(open_ended) == "SUCCESSION"


def test_every_kind_the_classifier_returns_is_declared():
    """The roll-call reads `KINDS`; a kind missing from it is never printed.

    Proved RED by adding `return "NEW-KIND"` to `_classify`: the guard names the
    kind and exits before a row is read.
    """
    census = _census_module()
    # Every kind the classifiers can actually return is declared, so the
    # roll-call prints all of them.
    census._kinds_are_declared()

    # And the guard is not vacuous: hide one kind and it exits rather than
    # letting that kind be counted invisibly.
    original = census.KINDS
    census.KINDS = ("CORRECTION",)
    try:
        with pytest.raises(SystemExit):
            census._kinds_are_declared()
    finally:
        census.KINDS = original


# ── THE DOOR: A DECISION A PERSON MADE, CARRIED OUT ───────────────────────────
@pytest.fixture
def touching(env):
    """One schedule holding the reported shape: a stated end running into a start.

    ⚠ `app.tenant_id` is set for the raw cursor — `tariff_versions` carries RLS
    FORCE and an unset setting returns zero rows, which would make every
    refusal below pass for the wrong reason (hard rule 1).
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    earlier = uuid.uuid4()
    later = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(env.tenant.id)])
        cursor.execute(
            "SELECT tenant_id, tariff_id, model, currency, percent_basis FROM tariff_versions "
            "WHERE tariff_id = %s AND effective_from IS NOT NULL LIMIT 1",
            [water["id"]],
        )
        seed = cursor.fetchone()
        assert seed is not None, "the fixture schedule is invisible — app.tenant_id or RLS"
        # The fixture's own version is activated `2026-08-01 → open`; an OPEN
        # window overlaps every later date, so it is moved out of the way here
        # or it joins every group below and the cases stop being about each
        # other.
        #
        # ⚠ **BOTH DATES IN ONE STATEMENT, AND TWO STATEMENTS IS WHY THIS
        # COMMENT EXISTS.** `ex_tariff_versions_no_overlap` is DEFERRABLE but
        # its `daterange(effective_from, effective_to + 1)` is evaluated per
        # ROW as it is written, so setting the end to 2026-05-31 while the
        # start is still 2026-08-01 builds an inverted range and PostgreSQL
        # refuses with `range lower bound must be less than or equal to range
        # upper bound` — which then aborts the whole transaction (hard-won law
        # 14) and every case in the file errors on a message about the
        # transaction rather than about the range.
        cursor.execute(
            "UPDATE tariff_versions SET effective_from = DATE '2026-01-01', "
            "effective_to = DATE '2026-05-31' WHERE tariff_id = %s",
            [water["id"]],
        )
        for version_id, lo, hi in (
            (earlier, "2026-06-01", "2026-07-31"),
            (later, "2026-07-31", "2026-08-01"),
        ):
            cursor.execute(
                "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
                "percent_basis, notify_customers, publish_public, created_at, updated_at, "
                "effective_from, effective_to) VALUES (%s, %s, %s, %s, %s, %s, false, false, "
                "now(), now(), %s, %s)",
                [str(version_id), *[str(c) for c in seed[:2]], seed[2], seed[3], seed[4], lo, hi],
            )
    yield {"tariff_id": water["id"], "earlier": earlier, "later": later, "tenant": env.tenant.id}

    # ⚠ **THE PLANTED PAIR IS REMOVED BEFORE TEARDOWN, AND IT IS NOT HOUSEKEEPING
    # — WITHOUT IT MOST OF THIS FILE ERRORS ON A MESSAGE ABOUT A CONSTRAINT.**
    # This command's whole subject is an estate where `rating/0047` has not been
    # applied, so the fixture has to hold a pair that `0047` forbids. The test
    # database has every migration applied, and `ex_tariff_versions_no_overlap`
    # is DEFERRABLE INITIALLY DEFERRED — which is fine inside the test, and is
    # NOT fine at the end of it, because Django's fixture teardown calls
    # `connection.check_constraints()`, which sets every constraint IMMEDIATE
    # and validates it. A rollback alone would never have checked it; the
    # harness checks it on purpose.
    #
    # So the four cases whose job is to leave the overlap STANDING — a refusal
    # that wrote nothing is the assertion — all errored in TEARDOWN with
    # `ExclusionViolation`, while the cases that happened to clear the overlap
    # passed. Read quickly that looks like the command failing on exactly the
    # rows it is meant to handle. It was the harness disagreeing with the
    # premise.
    #
    # ⚠ **DROPPING THE CONSTRAINT INSTEAD DOES NOT WORK, so do not swap this
    # back for the one-liner it looks like it wants to be:** by the time this
    # fixture runs, `env` has already written to `tariff_versions`, so
    # `ALTER TABLE … DROP CONSTRAINT` fails with `cannot ALTER TABLE
    # "tariff_versions" because it has pending trigger events` and aborts the
    # transaction (hard-won law 14), turning 8 errors into 16.
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(env.tenant.id)])
        cursor.execute(
            "DELETE FROM tariff_versions WHERE id = ANY(%s)",
            [[str(earlier), str(later)]],
        )


@POSTGRES_ONLY
def test_it_refuses_to_work_out_the_date_itself(touching):
    """The whole design: the end date is an ARGUMENT, never a computation."""
    with pytest.raises(CommandError) as raised:
        call_command("rat_resolve_schedule_overlap", version_id=str(touching["earlier"]))

    assert "--end-on is required" in str(raised.value)
    assert "BR-RAT-007" in str(raised.value), "it must say WHY it will not choose"


@POSTGRES_ONLY
def test_it_refuses_a_date_that_leaves_the_overlap(touching):
    """A repair that does not repair is worse than a refusal — the operator
    would otherwise learn it failed on the next `migrate`."""
    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(touching["earlier"]),
            end_on="2026-07-31",
            apply=True,
        )

    assert "still in force on the same date" in str(raised.value)
    assert _effective_to(touching["earlier"]) == date(2026, 7, 31), "nothing may have been written"


@POSTGRES_ONLY
def test_it_refuses_a_superseded_row(touching):
    """BR-RAT-1044: a corrected row's window is settled and is never moved."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE tariff_versions SET superseded_by_version_id = %s WHERE id = %s",
            [str(touching["later"]), str(touching["earlier"])],
        )
    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(touching["earlier"]),
            end_on="2026-07-30",
            apply=True,
        )

    assert "SUPERSEDED" in str(raised.value)
    assert "BR-RAT-1044" in str(raised.value)


@POSTGRES_ONLY
def test_it_refuses_an_inverted_window(touching):
    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(touching["earlier"]),
            end_on="2026-05-01",
            apply=True,
        )

    assert "window_inverted" in str(raised.value)


@POSTGRES_ONLY
def test_it_refuses_a_row_that_overlaps_nothing(touching):
    """It is the overlap door, not a general window editor: changing an
    in-force window for any other reason is a new version (BR-RAT-037)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE tariff_versions SET effective_from = DATE '2026-09-01', "
            "effective_to = DATE '2026-09-30' WHERE id = %s",
            [str(touching["later"])],
        )
    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(touching["later"]),
            end_on="2026-09-15",
            apply=True,
        )

    assert "does not overlap any live version" in str(raised.value)
    assert "BR-RAT-037" in str(raised.value)


@POSTGRES_ONLY
def test_a_dry_run_writes_nothing(touching):
    call_command(
        "rat_resolve_schedule_overlap", version_id=str(touching["earlier"]), end_on="2026-07-30"
    )

    assert _effective_to(touching["earlier"]) == date(2026, 7, 31)


@POSTGRES_ONLY
def test_it_writes_the_decision_and_the_trail(touching, audit_rows):
    """Hard rule 7: the row and the trail, in one transaction, or neither.

    ⚠ **THE TRAIL IS ASSERTED AT THE SINK AND NOT IN `audit_log`, AND THE FIRST
    VERSION OF THIS CASE READ THE TABLE AND FOUND IT EMPTY.** `test_us_ten_
    helpers` registers an **autouse** capture sink (`audit_rows`) that replaces
    `core.audit._sink` with `rows.append` for the whole suite, so under pytest
    the row never reaches the table — it reaches the list. Reading the table
    therefore reported *"a money action with no audit row"* about a command that
    had written one correctly, which is law 7's *looking at the wrong thing*
    inside the test rather than inside the code.
    **The table half is proved where it can be:** on a real PostgreSQL 16
    database, outside pytest, this command wrote
    `tariff.version_window_resolved` on `tariff_version` with
    `actor_kind='job'`, `actor_label='Rate schedule overlap resolution'` and
    `before`/`after` carrying `2026-07-31` → `2026-07-30`. That run is quoted in
    the review-ledger row, because it is the half a suite with a capture sink
    structurally cannot make.
    """
    call_command(
        "rat_resolve_schedule_overlap",
        version_id=str(touching["earlier"]),
        end_on="2026-07-30",
        apply=True,
    )

    assert _effective_to(touching["earlier"]) == date(2026, 7, 30)
    mine = [r for r in audit_rows if r["entity_id"] == touching["earlier"]]
    assert len(mine) == 1, "a money action with no audit row is not this command's behaviour"
    row = mine[0]
    assert row["action"] == "tariff.version_window_resolved"
    assert row["entity_type"] == "tariff_version"
    assert row["tenant_id"] == touching["tenant"], "hard rule 1 — the trail is tenant-scoped"
    # BR-AUD-019: a non-person actor NAMES itself and never borrows a login.
    assert row["actor_kind"] == "job"
    assert row["actor_user_id"] is None
    assert row["before"]["effective_to"] == "2026-07-31"
    assert row["after"]["effective_to"] == "2026-07-30"


@POSTGRES_ONLY
def test_the_migration_then_applies(touching):
    """The exit the loop did not have: resolve, then `rating/0046` walks clean.

    It asserts `0046`'s OWN predicate rather than re-implementing one — the
    question that matters is whether the migration would still refuse.
    """
    call_command(
        "rat_resolve_schedule_overlap",
        version_id=str(touching["earlier"]),
        end_on="2026-07-30",
        apply=True,
    )

    assert _overlapping_rows(touching["tariff_id"]) == 0


def _effective_to(version_id) -> date | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT effective_to FROM tariff_versions WHERE id = %s", [str(version_id)])
        return cursor.fetchone()[0]


def _overlapping_rows(tariff_id) -> int:
    """`rating/0047`'s constraint expression, asked of the rows as they stand."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM tariff_versions v WHERE v.tariff_id = %s "
            "AND v.effective_from IS NOT NULL AND v.superseded_by_version_id IS NULL "
            "AND EXISTS (SELECT 1 FROM tariff_versions w WHERE w.tariff_id = v.tariff_id "
            "AND w.id <> v.id AND w.effective_from IS NOT NULL "
            "AND w.superseded_by_version_id IS NULL AND daterange(w.effective_from, "
            "COALESCE(w.effective_to + 1, 'infinity'::date)) && daterange(v.effective_from, "
            "COALESCE(v.effective_to + 1, 'infinity'::date)))",
            [str(tariff_id)],
        )
        return cursor.fetchone()[0]


# ── RLS: AN UNSCOPED READ RETURNS NOTHING, NOT EVERYTHING (DEF-RAT-8073) ──────
def test_every_read_names_its_tenant():
    """Each SQL constant scopes by tenant in the TEXT, not only by context.

    Two mechanisms, because they fail in opposite directions. RLS hides rows
    from a normal role when `app.tenant_id` is unset; a `rolbypassrls` role is
    not scoped by RLS at all and would fold every tenant's rows into one
    report. The context alone covers the first and the predicate covers the
    second.

    RED on the shipped version: `OVERLAP_SQL`, `ROW_SQL` and `ISSUED_SQL`
    carried no tenant predicate.
    """
    from apps.rating.management.commands import rat_resolve_schedule_overlap as cmd

    for name in ("OVERLAP_SQL", "ROW_SQL", "SIBLINGS_SQL", "ISSUED_SQL"):
        assert "tenant_id = %s" in getattr(cmd, name), (
            f"{name} does not name a tenant. Under RLS FORCE an unscoped read returns "
            "NOTHING, and this command then reports a clean estate over a live overlap"
        )


@POSTGRES_ONLY
def test_the_report_enters_each_tenant(touching, monkeypatch):
    """`app.tenant_id` is SET for the tenant holding the overlap before it is read.

    ⚠ **THE ASSERTION IS ON THE CONTEXT BEING ENTERED, NOT ON THE ROWS COMING
    BACK, AND THAT IS DELIBERATE.** The suite's role can see every row whether
    or not the setting is right, so *"the report found the overlap"* passes on
    the broken version too — it is the vacuous assertion that let this ship.
    What cannot pass vacuously is whether the command set the tenant at all.
    RED on the shipped version: `_enter_tenant` did not exist and the report
    made one unscoped read.

    The measured behaviour it stands in for, from PostgreSQL 16.13 as a
    `NOSUPERUSER NOBYPASSRLS` role: `select count(*) from tariff_versions`
    returns 0 with the setting unset and 4 with it set.
    """
    from apps.rating.management.commands import rat_resolve_schedule_overlap as cmd

    entered = []
    real = cmd._enter_tenant

    def recording(tenant_id):
        entered.append(tenant_id)
        return real(tenant_id)

    monkeypatch.setattr(cmd, "_enter_tenant", recording)
    call_command("rat_resolve_schedule_overlap")

    assert touching["tenant"] in entered, (
        "the report never set `app.tenant_id` to the tenant holding the overlap, so "
        "under RLS FORCE it would have read zero rows and called the estate clean"
    )


# ── A WINDOW THAT ENDS BEFORE IT STARTS (DEF-RAT-8074) ────────────────────────
@pytest.fixture
def backwards(env):
    """One schedule holding a version whose `effective_to` precedes its start.

    It is the ONLY dated version of its schedule, which is how it reached a real
    deploy unnoticed: `rating/0046` had no well-formedness check at all, and the
    resolver's overlap query only builds a range when there is a sibling to
    compare against — with none, nothing raised and nothing was reported.
    `0047`'s `ADD CONSTRAINT` builds a range for EVERY row, so it failed there.
    """
    water = env.tiered_schedule("Res Water · Backwards", "water", RES_WATER_TIERS)
    version_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(env.tenant.id)])
        # ⚠ **THE CONSTRAINT HAS TO GO BEFORE THIS ROW CAN EXIST, AND THAT IS THE
        # PREMISE RATHER THAN A CONVENIENCE.** `ex_tariff_versions_no_overlap` is
        # backed by a partial GiST index whose expression is
        # `daterange(effective_from, COALESCE(effective_to + 1, 'infinity'))`. That
        # expression is evaluated when the ROW IS WRITTEN, not at the deferred
        # check — so on a database that already carries the constraint, a
        # backwards window cannot be stored at all: the UPDATE itself raises
        # `DataException` and aborts the transaction (hard-won law 14). The estate
        # this models is one where `0047` has NOT been applied, which is exactly
        # where the defect lives.
        #
        # ⚠ `SET CONSTRAINTS ALL IMMEDIATE` FIRST, and without it the DROP fails.
        # `env` has already written to `tariff_versions` in this transaction, so
        # the deferred constraint has pending trigger events and PostgreSQL
        # refuses `ALTER TABLE … because it has pending trigger events`. Flushing
        # the checks (the fixture's own rows are lawful, so it passes) clears them.
        # The DROP is inside `django_db`'s transaction and is rolled back with
        # everything else, so no other test sees a database without it.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute(
            "ALTER TABLE tariff_versions DROP CONSTRAINT IF EXISTS "
            "ex_tariff_versions_no_overlap"
        )
        cursor.execute(
            "SELECT tenant_id, tariff_id, model, currency, percent_basis FROM tariff_versions "
            "WHERE tariff_id = %s AND effective_from IS NOT NULL LIMIT 1",
            [water["id"]],
        )
        seed = cursor.fetchone()
        assert seed is not None, "the fixture schedule is invisible — app.tenant_id or RLS"
        # The fixture's own version becomes the backwards one, so the schedule
        # holds exactly one dated row and has no sibling to compare against.
        cursor.execute(
            "UPDATE tariff_versions SET effective_from = DATE '2026-09-01', "
            "effective_to = DATE '2026-08-01' WHERE tariff_id = %s AND effective_from IS NOT NULL",
            [water["id"]],
        )
        cursor.execute(
            "SELECT id FROM tariff_versions WHERE tariff_id = %s AND effective_from IS NOT NULL",
            [water["id"]],
        )
        version_id = cursor.fetchone()[0]
    yield {"tariff_id": water["id"], "version": version_id, "tenant": env.tenant.id}

    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(env.tenant.id)])
        # Leave a lawful window behind: Django's fixture teardown validates the
        # DEFERRED constraint, and it cannot even build a range from this row.
        cursor.execute(
            "UPDATE tariff_versions SET effective_from = DATE '2026-09-01', "
            "effective_to = DATE '2026-09-30' WHERE id = %s",
            [str(version_id)],
        )


@POSTGRES_ONLY
def test_the_report_does_not_crash_on_a_backwards_window(backwards):
    """RED before the fix: `DataException: range lower bound must be less than
    or equal to range upper bound`, raised by the report's OWN query.

    The overlap query built `daterange(effective_from, effective_to + 1)` over
    every candidate row, so it died on the one row the report exists to name —
    while `--apply` on that same row worked. A report that cannot survive the
    fault it reports is worse than no report.

    ⚠ **A SIBLING IS ADDED HERE AND WITHOUT IT THIS CASE PASSES ON THE BROKEN
    CODE.** The range in `OVERLAP_SQL` lives inside an `EXISTS` over the other
    versions of the same schedule, so PostgreSQL only evaluates it when there is
    a row to compare against. On a schedule holding ONE dated version the
    expression is never reached and nothing raises — which is precisely why the
    live deploy's own report came back clean and `0047` failed anyway. Proved:
    without this sibling the case passed on the pre-fix code, so it was testing
    nothing.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(backwards["tenant"])])
        cursor.execute(
            "SELECT tenant_id, tariff_id, model, currency, percent_basis FROM tariff_versions "
            "WHERE id = %s",
            [str(backwards["version"])],
        )
        seed = cursor.fetchone()
        cursor.execute(
            "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
            "percent_basis, notify_customers, publish_public, created_at, updated_at, "
            "effective_from, effective_to) VALUES (%s, %s, %s, %s, %s, %s, false, false, "
            "now(), now(), DATE '2026-11-01', DATE '2026-11-30')",
            [str(uuid.uuid4()), *[str(c) for c in seed[:2]], seed[2], seed[3], seed[4]],
        )

    call_command("rat_resolve_schedule_overlap")


@POSTGRES_ONLY
def test_the_report_names_the_backwards_window(backwards, capsys):
    """It is listed FIRST and as its own fault, not as a worse overlap:
    `0047` cannot be created at all while one exists."""
    call_command("rat_resolve_schedule_overlap")

    out = capsys.readouterr().out
    assert "ENDS BEFORE IT STARTS" in out
    assert str(backwards["version"]) in out


@POSTGRES_ONLY
def test_a_backwards_window_can_be_repaired(backwards):
    """RED before the fix: refused with *"does not overlap any live version"*.

    A backwards interval compares False against everything, so the overlap guard
    turned the command away from the one row it was being run for.
    """
    call_command(
        "rat_resolve_schedule_overlap",
        version_id=str(backwards["version"]),
        end_on="2026-09-30",
        apply=True,
    )

    assert _effective_to(backwards["version"]) == date(2026, 9, 30)


@POSTGRES_ONLY
def test_0046_refuses_a_backwards_window_rather_than_leaving_it_to_0047(backwards):
    """The migration must stop with an answerable question, which is its own rule.

    RED before the fix: `0046` reported `0 overlap(s) need a person`, was marked
    applied, and `0047` then died on PostgreSQL's message naming no row.

    ⚠ The migration's function is called DIRECTLY rather than through the
    executor: `0046` is already applied in the test database, and re-running the
    executor would need a reverse that this migration deliberately does not have.
    """
    import importlib.util

    from django.apps import apps as live_apps

    path = (
        Path(__file__).resolve().parents[1]
        / "apps/rating/migrations/0046_def_rat_8000_close_open_windows.py"
    )
    spec = importlib.util.spec_from_file_location("m0046", path)
    m0046 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0046)

    with pytest.raises(m0046.OverlappingScheduleVersions) as raised:
        m0046.close_open_windows(live_apps, SimpleNamespace(connection=connection))

    message = str(raised.value)
    assert "ENDS BEFORE IT STARTS" in message
    assert str(backwards["version"]) in message, "the refusal must NAME the row"


# ── `--clear-end`: THE NEWEST VERSION'S HONEST END IS NO END (DEF-RAT-8074) ────
@POSTGRES_ONLY
def test_clear_end_reopens_the_window(backwards):
    """A backwards window is usually the NEWEST version, whose end is NULL.

    Without this the operator had to invent a far-future date on the column that
    decides which version prices a service date — the exact figure-inventing this
    chain refuses to do, moved into their hand.
    """
    call_command(
        "rat_resolve_schedule_overlap",
        version_id=str(backwards["version"]),
        clear_end=True,
        apply=True,
    )

    assert _effective_to(backwards["version"]) is None


@POSTGRES_ONLY
def test_clear_end_is_refused_when_it_would_run_into_a_later_version(backwards):
    """An open window overlaps every later date, so it is NOT always safe.

    `_upper(None)` is `date.max`, so a cleared end is compared as the open window
    it is and a row that would swallow a later version is refused HERE rather
    than at the next `migrate`.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(backwards["tenant"])])
        cursor.execute(
            "SELECT tenant_id, tariff_id, model, currency, percent_basis FROM tariff_versions "
            "WHERE id = %s",
            [str(backwards["version"])],
        )
        seed = cursor.fetchone()
        cursor.execute(
            "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
            "percent_basis, notify_customers, publish_public, created_at, updated_at, "
            "effective_from, effective_to) VALUES (%s, %s, %s, %s, %s, %s, false, false, "
            "now(), now(), DATE '2026-12-01', DATE '2026-12-31')",
            [str(uuid.uuid4()), *[str(c) for c in seed[:2]], seed[2], seed[3], seed[4]],
        )

    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(backwards["version"]),
            clear_end=True,
            apply=True,
        )

    assert "--clear-end would leave" in str(raised.value), "the message must name the flag used"
    assert _effective_to(backwards["version"]) == date(2026, 8, 1), "nothing may have been written"


def test_end_on_and_clear_end_are_mutually_exclusive():
    with pytest.raises(CommandError) as raised:
        call_command(
            "rat_resolve_schedule_overlap",
            version_id=str(uuid.uuid4()),
            end_on="2026-09-30",
            clear_end=True,
        )

    assert "say two different things" in str(raised.value)


@POSTGRES_ONLY
def test_0047_refuses_a_backwards_window_because_0046_may_already_be_applied(backwards):
    """The same guard in `0047`, which is the copy that fires on a live estate.

    ⚠ **`0046`'s COPY CANNOT HELP A DATABASE THAT HAS ALREADY APPLIED IT, AND
    THAT IS EVERY DATABASE THAT EVER GOT THIS FAR (`DEF-RAT-8074`).** Django never
    re-runs an applied migration. On the estate this was found on, `0046` had run
    before the check existed — silently, reporting `0 overlap(s) need a person` —
    so putting the guard only there left `ADD CONSTRAINT` still failing with
    PostgreSQL's own message. Reproduced with `0046` marked applied and `0047`
    pending, which is exactly that state.

    RED before the fix: `DataError: range lower bound must be less than or equal
    to range upper bound`, out of `ADD CONSTRAINT`, naming nothing.
    """
    import importlib.util

    from django.apps import apps as live_apps

    path = (
        Path(__file__).resolve().parents[1]
        / "apps/rating/migrations/0047_def_rat_8000_no_overlap_constraint.py"
    )
    spec = importlib.util.spec_from_file_location("m0047", path)
    m0047 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0047)

    with pytest.raises(m0047.MalformedWindow) as raised:
        m0047._refuse_malformed_windows(live_apps, SimpleNamespace(connection=connection))

    message = str(raised.value)
    assert "ENDS BEFORE IT STARTS" in message
    assert str(backwards["version"]) in message, "the refusal must NAME the row"
    assert "--clear-end" in message, "it must point at the flag that usually fixes it"


@POSTGRES_ONLY
def test_0047_refuses_an_overlap_too_because_0046_cannot_re_run(touching):
    """`0046`'s OVERLAP walk cannot re-run either, so `0047` carries that check too.

    ⚠ **THE FIRST VERSION OF `0047`'s PRE-FLIGHT CHECKED ONLY MALFORMED WINDOWS,
    WHICH FIXED THE INSTANCE AND LEFT THE HOLE (`DEF-RAT-8074`).** An estate that
    applied `0046` before gaining an overlap reaches `ADD CONSTRAINT` with no walk
    having seen it, and PostgreSQL answers `ExclusionViolation`, naming one
    conflicting key and no decision. Both of `0046`'s checks belong here.
    """
    import importlib.util

    from django.apps import apps as live_apps

    path = (
        Path(__file__).resolve().parents[1]
        / "apps/rating/migrations/0047_def_rat_8000_no_overlap_constraint.py"
    )
    spec = importlib.util.spec_from_file_location("m0047b", path)
    m0047 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0047)

    with pytest.raises(m0047.MalformedWindow) as raised:
        m0047._refuse_malformed_windows(live_apps, SimpleNamespace(connection=connection))

    message = str(raised.value)
    assert "TWO VERSIONS IN FORCE ON ONE DATE" in message
    assert "ALREADY BEEN APPLIED" in message, "it must say why 0046 did not catch this"
    assert str(touching["earlier"]) in message and str(touching["later"]) in message
