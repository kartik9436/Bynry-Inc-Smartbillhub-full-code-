# ── Trace ──────────────────────────────────────────────
# Rule:   BR-RAT-1044 — when `correct_rate_schedule_version` supersedes a
#         version, the corrected row's OPEN end date is stamped with
#         `max(the correction date, its own effective_from)`, so the register
#         shows WHEN THE WRONG VERSION STOPPED BEING USED. PO ruling
#         2026-09-29, option (a) of three, verbatim: *"i will take this and
#         use superseded_by in filter - so that it is always unique and even
#         if we see in audit it is clear"*.
# Rules:  BR-RAT-104 / BR-RAT-1016 verb 2 (a CORRECTION restates the SAME
#         window; the corrected row carries `superseded_by`) · BR-RAT-007 (a
#         period prices on the version in force AT THE SERVICE DATE) ·
#         BR-RAT-031 (a NULL `effective_from` IS the draft) · BR-TEN-081 /
#         BR-TEN-043 (the correction date is the UTILITY's day, event-time) ·
#         CLAUDE.md hard rule 4 (no issued bill's basis may move) · hard-won
#         law 7 (prove it RED first, in the harness that runs it) · law 14
#         (this suite is SQLite; the constraint half is the `_pg` sibling)
# Tests:  the database half is
#         06-backend/tests/test_br_rat_1044_correction_window_pg.py
# ───────────────────────────────────────────────────────
"""**WHEN DID THE WRONG VERSION STOP BEING USED?** — the register's answer.

⚠ **PROVED RED FIRST (hard-won law 7).** Against `caab7e774`, the tip this
was written on, three of the eight cases here failed and five passed — the
five describe behaviour that was already right and are here so a later
"simplification" cannot take it away. The two that matter, verbatim:

    test_br_rat_1044__corrected_after_it_started_ends_on_the_correction_date
    AssertionError: the corrected row must record the day it stopped being
    used, not run on for ever
    assert None == datetime.date(2026, 3, 1)

    test_br_rat_1044__corrected_before_it_started_ends_on_its_own_start_date
    AssertionError: the `max` — a future-dated version corrected before it
    started reads as replaced the day it would have started
    assert None == datetime.date(2026, 2, 1)

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked rather than assumed:

  * **THE `max` NEVER BEING EXERCISED.** The edge case only exists for a
    version ACTIVATED WITH A FUTURE DATE and corrected before that date
    arrives, so the second case PATCHES the tenant's clock back behind the
    version's start. Without that patch the case is the first case again and
    the `max` is dead code that no assertion touches. `test_…_without_the_max`
    is the proof that the naive version FAILS: it asserts the refusal
    (`window_inverted`) the bare correction date would produce, by writing it
    directly, so the reason for the `max` is in the file rather than in a
    comment.
  * **A DATE ASSERTION STANDING IN FOR THE MONEY QUESTION.** The end date is
    written on a row BOTH readers already drop, so three cases assert the
    readers rather than the column: `selectors.in_force_version` (the live
    bill run), `resolution_catalogue.schedule_version_facts` (the chain the
    one-time and move-out final bills use) and the two together over every
    date in and around the corrected window.
  * **THE CONSTRAINT.** SQLite has no exclusion constraint, so nothing in
    this file can show that `ex_tariff_versions_no_overlap` still accepts the
    pair. That is the `_pg` sibling's whole job and it skips itself by name
    here rather than passing vacuously (hard-won law 14).
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.rating import models, resolution_catalogue, seams, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

FIXED = [{"from_qty": "0", "to_qty": None, "unit_price": "3.20"}]

REASON = "Tier 1 was typed as 32.00 and the board approved 3.20"


@pytest.fixture
def clock(monkeypatch):
    """The UTILITY's today, which is what `BR-RAT-1044` writes.

    `services` reads `seams.tenant_today()` — never `date.today()` — so this
    patches the seam the money path actually calls. A test that patched
    `apps.tenancy.selectors.tenant_today` instead would also work today and
    would stop working the moment the seam is re-pointed, which is law 7's
    *looking at the wrong thing*.
    """

    def _set(day: date) -> None:
        monkeypatch.setattr(seams, "tenant_today", lambda: day)

    return _set


def _schedule(env, start: str):
    return env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from=start
    )


def _correct(env, tariff_id, version_id):
    with tenant_ctx(env.tenant):
        return services.correct_rate_schedule_version(
            env.admin,
            tariff_id,
            str(version_id),
            {"model": "tiered", "uom": "kgal", "reason": REASON, "structure": {"tiers": FIXED}},
        )


def _original(env, tariff_id):
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=tariff_id)
        return selectors.latest_version(tariff)


def _reload(env, version):
    with tenant_ctx(env.tenant):
        return models.TariffVersion.objects.get(pk=version.pk)


# ── THE TWO WORKED CASES THE PO WAS SHOWN ─────────────────────────────────


def test_br_rat_1044__corrected_after_it_started_ends_on_the_correction_date(env, clock):
    """Worked case 1 — *in use a month, then replaced.*

    A version priced from 2026-02-01; somebody notices the figure on
    2026-03-01. The corrected row must say it ran to 2026-03-01.
    """
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    assert original.effective_from == date(2026, 2, 1)
    assert original.effective_to is None, "the fixture must start with an OPEN window"

    _correct(env, water["id"], original.id)

    original = _reload(env, original)
    assert original.superseded_by_id is not None
    assert original.effective_to == date(2026, 3, 1), (
        "the corrected row must record the day it stopped being used, not run "
        "on for ever"
    )


def test_br_rat_1044__corrected_before_it_started_ends_on_its_own_start_date(env, clock):
    """Worked case 2 — *replaced the day it would have started.*

    ⚠ **THIS IS NOT "CORRECTED BEFORE ACTIVATION".** A draft has no dates and
    is edited in place — `correct_rate_schedule_version` refuses one by name
    (`rating.schedules.correct_draft`) because no version exists and there is
    nothing to supersede. This is a version ACTIVATED WITH A FUTURE DATE and
    corrected before that date arrives, which is the only way the correction
    date can land behind `effective_from`.
    """
    clock(date(2026, 1, 15))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])

    _correct(env, water["id"], original.id)

    original = _reload(env, original)
    assert original.effective_to == date(2026, 2, 1), (
        "the `max` — a future-dated version corrected before it started reads "
        "as replaced the day it would have started"
    )
    assert original.effective_to >= original.effective_from


def test_br_rat_1044__without_the_max_the_correction_would_be_refused_by_name(env, clock):
    """⚠ WHY THE `max` IS THERE, ASSERTED RATHER THAN DESCRIBED.

    The bare correction date on worked case 2 is 2026-01-15 against an
    `effective_from` of 2026-02-01 — an end 17 days BEFORE the start. This
    repo already refuses that shape by name, so the naive rule does not
    produce a slightly odd row: the whole correction fails and the clerk
    cannot fix their typo at all.
    """
    clock(date(2026, 1, 15))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    naive = seams.tenant_today()

    assert naive < original.effective_from
    assert max(naive, original.effective_from) == original.effective_from

    # And the refusal the naive value would meet is a real, named one — the
    # same message key every other schedule write raises for an inverted
    # window. Written out rather than described, so this case fails if the
    # refusal is ever renamed or dropped.
    with tenant_ctx(env.tenant):
        with pytest.raises(Exception) as caught:
            services.create_rate_schedule_version(
                env.admin,
                water["id"],
                {
                    "model": "tiered",
                    "uom": "kgal",
                    "reason": "an inverted window, written on purpose",
                    "effective_from": "2026-03-01",
                    "effective_to": "2026-02-01",
                    "structure": {"tiers": FIXED},
                },
            )
    assert "window_inverted" in str(getattr(caught.value, "field_errors", caught.value))


# ── WHAT MUST NOT CHANGE ──────────────────────────────────────────────────


def test_br_rat_1044__the_new_version_keeps_the_original_start_and_stays_open(env, clock):
    """A correction restates the SAME window — that single property is what
    makes it a correction rather than a rate update. Moving the new row's
    start would re-price a different span."""
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])

    _correct(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        correction = models.TariffVersion.objects.get(corrects=original)
    assert correction.effective_from == date(2026, 2, 1)
    assert correction.effective_to is None, (
        "the correction inherits the open end the original had — it is the row "
        "that prices now"
    )


def test_br_rat_1044__a_stated_end_is_never_moved(env, clock):
    """OURS RATHER THAN THE PO'S, and recorded as such (decision log
    2026-09-29).

    The ruling was put and answered for the CURRENT version, whose window is
    open. A version already closed by a later rate change stopped being used
    the day its successor started, not the day somebody noticed the figure was
    wrong — so writing the correction date over it would make the register say
    it ran a month longer than it did. `rating/0046` states the same rule for
    the same column: *"AN END DATE THAT ALREADY EXISTS IS NEVER MOVED."*
    """
    clock(date(2026, 6, 1))
    water = _schedule(env, "2026-02-01")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            water["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Board-approved rate change effective 2026-04-01",
                "effective_from": "2026-04-01",
                "structure": {"tiers": [{"from_qty": "0", "to_qty": None, "unit_price": "4.10"}]},
            },
        )
        tariff = models.Tariff.objects.get(pk=water["id"])
        first = (
            selectors.activated_versions(tariff).order_by("effective_from").first()
        )
    assert first.effective_to == date(2026, 3, 31), "the successor closed it"

    _correct(env, water["id"], first.id)

    first = _reload(env, first)
    assert first.superseded_by_id is not None
    assert first.effective_to == date(2026, 3, 31), (
        "a stated end is the day a bill was reproduced against; the correction "
        "date must not overwrite it"
    )


# ── THE THREE THINGS THAT MAKE THIS SAFE, PROVED RATHER THAN ASSUMED ──────


def test_br_rat_1044__reader_one_the_live_bill_run_does_not_price_the_closed_row(env, clock):
    """`selectors.in_force_version` — the read the nightly run uses. It has
    filtered `superseded_by__isnull=True` since `DEF-RAT-5715`, so the end
    date written here changes nothing it answers."""
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    _correct(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        correction = models.TariffVersion.objects.get(corrects=original)
        # inside the corrected row's OWN window, and after its new end
        for day in (date(2026, 2, 15), date(2026, 3, 1), date(2026, 9, 30)):
            chosen = selectors.in_force_version(tariff, day)
            assert chosen is not None, day
            assert chosen.id == correction.id, day
            assert chosen.id != original.id, day


def test_br_rat_1044__reader_two_the_resolution_chain_agrees(env, clock):
    """`resolution_catalogue.schedule_version_facts` — the read the one-time
    and move-out final bills use. It gained the same filter today
    (`DEF-RAT-8002`); before that, two rows on one window made R2 raise
    `AmbiguousSchedule` on a schedule the nightly run priced fine."""
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    _correct(env, water["id"], original.id)

    with tenant_ctx(env.tenant):
        correction = models.TariffVersion.objects.get(corrects=original)
        facts = resolution_catalogue.schedule_version_facts(water["id"])
    assert [f.version_id for f in facts] == [str(correction.id)], facts
    for day in (date(2026, 2, 15), date(2026, 3, 1), date(2026, 9, 30)):
        in_force = [f for f in facts if f.in_force_on(day)]
        assert [f.version_id for f in in_force] == [str(correction.id)], day


def test_br_rat_1044__hard_rule_4_the_end_date_moves_no_resolver_answer(env, clock):
    """CLAUDE.md hard rule 4, asked the only way that settles it: **the same
    question, with and without this change.**

    A correction re-prices history by design — the old figure was never right
    — but THIS CHANGE must not move WHICH VERSION answers a date, because
    that is what a past bill is reproduced from (BR-RAT-007/017). So the
    comparison is not *before the correction* against *after the correction*
    (the answering row moving from the original to the correction is the
    correction working). It is **the new behaviour against the old one**: the
    correction is taken, both readers are asked for every day across the
    window and past the new end, the corrected row's `effective_to` is then
    put BACK to NULL — exactly what the code wrote yesterday — and the two
    sets of answers are compared as a pair.

    They are identical because both readers drop a superseded row before they
    look at a window at all. That is the claim this change rests on, and it
    is asserted here rather than reasoned about.
    """
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    days = [
        date(2026, 2, 1),
        date(2026, 2, 28),
        date(2026, 3, 1),
        date(2026, 3, 2),
        date(2027, 1, 1),
    ]

    def answers():
        with tenant_ctx(env.tenant):
            tariff = models.Tariff.objects.get(pk=water["id"])
            facts = resolution_catalogue.schedule_version_facts(water["id"])
            out = {}
            for day in days:
                live = selectors.in_force_version(tariff, day)
                chain = tuple(sorted(f.version_id for f in facts if f.in_force_on(day)))
                out[day] = (str(live.id) if live else None, chain)
            return out

    _correct(env, water["id"], original.id)
    with_the_change = answers()

    with tenant_ctx(env.tenant):
        models.TariffVersion.objects.filter(pk=original.pk).update(effective_to=None)
    without_the_change = answers()

    assert with_the_change == without_the_change, (
        "stamping the corrected row's end date moved a resolver answer — it "
        "must not, because both readers drop a superseded row first"
    )
    # …and not vacuously equal because nothing answers at all.
    with tenant_ctx(env.tenant):
        correction_id = str(models.TariffVersion.objects.get(corrects=original).id)
    assert all(
        value == (correction_id, (correction_id,)) for value in with_the_change.values()
    ), with_the_change


# ── `latest_version` — THE FOURTH READER, PINNED ──────────────────────────
#
# Asked because this change moves a corrected row's `effective_to` and
# `latest_version` sorts on dates. It has NO `superseded_by` filter where its
# two siblings do, and twelve call sites take its answer — `previous` for a
# rate change, the base charge code carried forward, the window that gets
# closed. The selector's own docstring carries the reasoning; these cases are
# the part that goes red.


def _latest(env, tariff_id):
    with tenant_ctx(env.tenant):
        return selectors.latest_version(models.Tariff.objects.get(pk=tariff_id))


def test_br_rat_1044__latest_version_never_returns_the_corrected_row(env, clock):
    """Three shapes, and none of them may hand a caller a row that no longer
    prices: correcting the newest version · correcting a correction · and the
    same question asked again after a later rate change."""
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])

    # 1 · the ordinary case — correct the newest version
    _correct(env, water["id"], original.id)
    with tenant_ctx(env.tenant):
        first_correction = models.TariffVersion.objects.get(corrects=original)
    assert _latest(env, water["id"]).id == first_correction.id
    assert _latest(env, water["id"]).superseded_by_id is None

    # 2 · a CHAIN — correct the correction. `already_corrected` refuses a
    #     second correction of the SAME row, so this is the only way a chain
    #     forms, and both earlier rows are now superseded on one date.
    _correct(env, water["id"], first_correction.id)
    with tenant_ctx(env.tenant):
        second_correction = models.TariffVersion.objects.get(corrects=first_correction)
        superseded = set(
            models.TariffVersion.objects.filter(
                tariff_id=water["id"], superseded_by__isnull=False
            ).values_list("id", flat=True)
        )
    assert superseded == {original.id, first_correction.id}
    assert _latest(env, water["id"]).id == second_correction.id, (
        "two rows on one effective_from are superseded and the third is live — "
        "`latest_version` must return the live one"
    )

    # 3 · correcting a version that is NOT the newest leaves the newest alone
    clock(date(2026, 6, 1))
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
        newest = selectors.latest_version(models.Tariff.objects.get(pk=water["id"]))
    assert newest.effective_from == date(2026, 7, 1)
    _correct(env, water["id"], second_correction.id)
    assert _latest(env, water["id"]).id == newest.id
    assert _latest(env, water["id"]).superseded_by_id is None


def test_br_rat_1044__latest_version_answers_the_same_with_and_without_the_stamp(env, clock):
    """This change writes `effective_to` on the corrected row. `latest_version`
    orders by `effective_from` then `created_at` and reads `effective_to`
    NOWHERE, so the answer cannot move — asserted rather than reasoned."""
    clock(date(2026, 3, 1))
    water = _schedule(env, "2026-02-01")
    original = _original(env, water["id"])
    _correct(env, water["id"], original.id)

    with_the_stamp = _latest(env, water["id"]).id
    with tenant_ctx(env.tenant):
        models.TariffVersion.objects.filter(pk=original.pk).update(effective_to=None)
    without_the_stamp = _latest(env, water["id"]).id
    assert with_the_stamp == without_the_stamp


def test_br_rat_1044__latest_version_still_orders_by_created_at(env):
    """⚠ THE MECHANISM, PINNED — the guarantee above rests on `-created_at`
    and on nothing else.

    A correction TIES with the row it corrects on `effective_from`, by
    definition (BR-RAT-104). `-created_at` is the only thing that then puts
    the live row first. A lane tidying this ordering away would hand
    `previous`, `_carry_forward_base_charge_code` and the window close a row
    that no longer prices, and every other test in this repo would stay green.

    ⚠ **THE SQL IS CAPTURED FROM THE REAL CALL**, not rebuilt here from the
    same two strings the selector uses — a test that re-states the ordering
    and then asserts its own statement is law 7's *looking at the wrong
    thing*, and would pass over a `latest_version` that had been rewritten to
    order by something else entirely.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    water = env.tiered_schedule("Res Water · Ordering", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        with CaptureQueriesContext(connection) as captured:
            selectors.latest_version(tariff)
    sql = [q["sql"] for q in captured.captured_queries if "ORDER BY" in q["sql"].upper()]
    assert sql, [q["sql"] for q in captured.captured_queries]
    order_by = sql[-1].upper().rsplit("ORDER BY", 1)[1]
    assert "CREATED_AT" in order_by, (
        "`latest_version` must keep `-created_at` in its ordering: it is the "
        "only thing separating a corrected row from its replacement, which "
        f"share an `effective_from` by definition. ORDER BY was: {order_by}"
    )
    assert "EFFECTIVE_TO" not in order_by, (
        "`latest_version` must not sort on `effective_to` — BR-RAT-1044 now "
        "writes that column on a corrected row, and sorting on it would make "
        "this selector's answer move with a correction"
    )
