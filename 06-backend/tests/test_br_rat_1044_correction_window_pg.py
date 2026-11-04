# ── Trace ──────────────────────────────────────────────
# Rule:  BR-RAT-1044 — a corrected row's OPEN end date is stamped with
#        `max(the correction date, its own effective_from)` (PO ruling
#        2026-09-29). This is the DATABASE half: the pair must still be legal
#        under `ex_tariff_versions_no_overlap` (`rating/0047`) afterwards.
# Rules: B2 §2 · BR-RAT-104 / BR-RAT-1016 verb 2 · CLAUDE.md hard-won law 14
#        (the suite is SQLite and this guarantee cannot exist there) · law 7
#        (prove it RED in the harness that runs it, and name the false pass)
# Sibling: 06-backend/tests/test_br_rat_1044_correction_closes_the_window.py
#          — the service-level half, which runs on the default suite.
# ───────────────────────────────────────────────────────
"""`BR-RAT-1044`'s stamp, against the constraint that could refuse it.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_br_rat_1044_correction_window_pg.py

⚠ **SKIPPED BY NAME ON SQLITE, AND THE SKIP IS THE POINT** (hard-won law 14).
`config/settings/test.py` hardcodes in-memory SQLite, which has no range type
and no exclusion constraint, so a version of this change that produced a pair
`ex_tariff_versions_no_overlap` refuses would pass the entire default suite,
green, on every machine.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked rather than assumed — and the
first draft of the sibling `test_def_rat_8000_no_overlap_pg.py` fell into the
first of these, so it is not a hypothetical list:

  * **THE DEFERRED CHECK NEVER HAPPENING.** Under `django_db` the whole test
    runs inside one transaction that is rolled back, and the constraint is
    `DEFERRABLE INITIALLY DEFERRED` — so it is never checked at all and every
    case here passes vacuously. `_check_now()` issues
    `SET CONSTRAINTS ALL IMMEDIATE` at the point where the answer is due.
  * **THE CONSTRAINT BEING ABSENT.** A test that merely fails to raise says
    nothing if `rating/0047` never ran. The first case asserts the constraint
    exists by reading `pg_constraint` before anything else is claimed.
  * **THE STAMP NEVER BEING WRITTEN.** A correction whose end date came out
    NULL would also commit cleanly, so each case asserts the DATE as well as
    the absence of a refusal.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from apps.rating import models, seams, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

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
FIXED = [{"from_qty": "0", "to_qty": None, "unit_price": "3.20"}]
REASON = "Tier 1 was typed as 32.00 and the board approved 3.20"


def _check_now():
    """Force the DEFERRED constraint to be checked HERE rather than at a
    COMMIT that `django_db` never performs. Without this every case in this
    file is a check that cannot fail (hard-won law 7)."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _definition() -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
            [CONSTRAINT],
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _correct_and_check(env, water_id, version_id):
    with tenant_ctx(env.tenant):
        services.correct_rate_schedule_version(
            env.admin,
            water_id,
            str(version_id),
            {"model": "tiered", "uom": "kgal", "reason": REASON, "structure": {"tiers": FIXED}},
        )
        # The service's own `atomic()` is a SAVEPOINT here, so the deferred
        # check has still not run. This is where the answer is due.
        _check_now()


@POSTGRES_ONLY
def test_br_rat_1044_pg__the_constraint_is_actually_there(env):
    """Everything below is worthless if `rating/0047` never ran."""
    definition = _definition()
    assert definition is not None, (
        f"{CONSTRAINT} does not exist on this database — every 'it commits' "
        "assertion in this file would pass for the wrong reason"
    )
    assert "superseded_by_version_id IS NULL" in definition, definition
    assert "DEFERRABLE INITIALLY DEFERRED" in definition, definition


@POSTGRES_ONLY
def test_br_rat_1044_pg__control_the_check_in_this_file_can_actually_refuse(env, monkeypatch):
    """⚠ **THE CONTROL, AND WITHOUT IT EVERY "IT COMMITS" CASE BELOW IS A
    CHECK THAT CANNOT FAIL** (hard-won law 7's *incapable of failing*).

    Three of the four cases here assert that something does NOT raise. An
    assertion of that shape is worthless unless the same machinery, at the
    same point, is shown refusing something it should. So this plants a
    second LIVE row on the same window — no `superseded_by`, which is the
    only thing that makes the real pair legal — and asserts `_check_now()`
    raises at exactly the place the other cases call it and see nothing.

    Written with a SAVEPOINT because a refusal aborts the whole PostgreSQL
    transaction and the fixture teardown still has work to do (hard-won law
    14).

    ⚠ **THE ROW IS COPIED THROUGH THE ORM AND NOT BY A HAND-WRITTEN INSERT,
    AND THE FIRST DRAFT LEARNED THAT THE HARD WAY.** An INSERT naming ten
    columns was refused by PostgreSQL with *"null value in column
    `notify_customers` … violates not-null constraint"* — a real refusal, so
    a `pytest.raises(IntegrityError)` with no assertion on the MESSAGE would
    have gone GREEN on the wrong error entirely, and this control would have
    been a control over nothing. That is why the assertion names the
    constraint rather than the exception type. Copying the whole instance
    carries every column the table grows from now on, so the case cannot rot
    the same way again.
    """
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 3, 1))
    water = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2026-02-01"
    )
    with tenant_ctx(env.tenant):
        original = selectors.latest_version(models.Tariff.objects.get(pk=water["id"]))
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():
                twin = models.TariffVersion.objects.get(pk=original.pk)
                twin.pk = None
                twin.id = None
                twin._state.adding = True
                twin.save(force_insert=True)
                _check_now()
    assert CONSTRAINT in str(caught.value), (
        "the refusal must be the no-overlap constraint and not some other "
        f"IntegrityError — a control that fires on the wrong error is no "
        f"control at all. Got: {caught.value}"
    )


@POSTGRES_ONLY
def test_br_rat_1044_pg__the_stamped_pair_commits_worked_case_one(env, monkeypatch):
    """Worked case 1 through the REAL service, against the real constraint.

    Version from 2026-02-01, corrected on 2026-03-01. Afterwards the two rows
    hold `2026-02-01 → 2026-03-01` (superseded) and `2026-02-01 → open`
    (live), which OVERLAP. The constraint's `superseded_by_version_id IS NULL`
    predicate is what makes that legal, and this asserts it rather than
    trusting the predicate's text.
    """
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 3, 1))
    water = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2026-02-01"
    )
    with tenant_ctx(env.tenant):
        original = selectors.latest_version(models.Tariff.objects.get(pk=water["id"]))

    _correct_and_check(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        original.refresh_from_db()
        correction = models.TariffVersion.objects.get(corrects=original)
    assert original.effective_to == date(2026, 3, 1), "the stamp must be written"
    assert correction.effective_to is None
    assert correction.effective_from == original.effective_from
    # The overlap is real and the constraint allows it because one side is
    # superseded — the same sentence the live bill run reads.
    assert original.effective_from <= correction.effective_from <= original.effective_to


@POSTGRES_ONLY
def test_br_rat_1044_pg__the_stamped_pair_commits_worked_case_two(env, monkeypatch):
    """Worked case 2 — the `max`. A version activated for 2026-02-01 and
    corrected on 2026-01-15 gets `effective_to = 2026-02-01`, so
    `daterange(effective_from, effective_to + 1)` is a single valid day
    rather than the EMPTY or inverted range a bare correction date would
    build. An inverted `daterange` raises `range lower bound must be less
    than or equal to range upper bound` in PostgreSQL itself — a refusal the
    SQLite suite cannot show at all."""
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 1, 15))
    water = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2026-02-01"
    )
    with tenant_ctx(env.tenant):
        original = selectors.latest_version(models.Tariff.objects.get(pk=water["id"]))

    _correct_and_check(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        original.refresh_from_db()
    assert original.effective_to == date(2026, 2, 1)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT daterange(effective_from, effective_to + 1) FROM tariff_versions "
            "WHERE id = %s",
            [original.id],
        )
        assert cursor.fetchone()[0] is not None


@POSTGRES_ONLY
def test_br_rat_1044_pg__a_later_rate_change_over_the_stamped_pair_still_commits(env, monkeypatch):
    """The sequence a real schedule goes through: correct it, then file a rate
    change over it. `_close_open_windows_before` must still find exactly one
    open window to close — the correction — and leave the stamped row alone.
    """
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 3, 1))
    water = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2026-02-01"
    )
    with tenant_ctx(env.tenant):
        original = selectors.latest_version(models.Tariff.objects.get(pk=water["id"]))
    _correct_and_check(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            water["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Board-approved rate change effective 2026-07-01",
                "effective_from": "2026-07-01",
                "structure": {"tiers": [{"from_qty": "0", "to_qty": None, "unit_price": "4.10"}]},
            },
        )
        _check_now()
        original.refresh_from_db()
        correction = models.TariffVersion.objects.get(corrects=original)
        correction.refresh_from_db()
    assert original.effective_to == date(2026, 3, 1), (
        "the stamped row is superseded, so `_close_open_windows_before` must "
        "not touch it"
    )
    assert correction.effective_to == date(2026, 6, 30), "the live row closed normally"
