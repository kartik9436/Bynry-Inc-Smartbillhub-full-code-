# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W1, tasks
#           W1-T1 (🔒 cycle schedule migration) and W1-T2 (every reader moves
#           to ONE schedule generation).   Screens: S8 · SET-05/07 · S27
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2, §6, §7
# Rules:    the pre-CR PO ruling, verbatim — *"routes and cycles are grouping
#           only - so we will not tag late fees , etc - we can capture start
#           day, frequency, monthly, weekly daily, biweekly, once in two
#           months , quaterly etc and days to complete it ; give business names
#           to frequence - 1 word."* · D2 (*"Yes"* — unify the two cycle column
#           generations) · BR-MET-077 (a cycle is a DEFINITION) · BR-MET-078
#           (NO money on these surfaces) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""CR-029 RC-W1 — the three fields about time, and the bug that dies with them.

**THE BUG THIS FILE PINS (B17 §5 gap G2).** A cycle created through the CR-006
wizard writes `read_day_from`/`read_day_to` and never writes the legacy
`window_start`/`window_end` DATE pair — and the bill-run picker and the ops
Cycles tab (S27) both render the window from those dates. So the cycle a staff
member just created shows **no read window anywhere**, and nothing was broken:
two generations of columns, each half-read.

`test_a_wizard_created_cycle_shows_a_read_window...` is that bug, written as a
test before the fix. It fails on the shipped tree with `window_start is None`.

Every case quotes the ruling it defends, because four of these reverse an
obvious reading and the quote is what stops a later lane "fixing" it back.
"""

from datetime import date

import pytest

from apps.metering import models, schedule, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# W1-T1 · THE VOCABULARY — *"give business names to frequence - 1 word"*
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t1__the_frequency_vocabulary_is_the_eight_business_words():
    """B17 §2's table, in its order. *"give business names to frequence -
    1 word."* — eight one-word names, and **Fortnightly** rather than the PO's
    *"biweekly"* because biweekly also means twice-a-week in common use
    (B17 §2 records exactly that reasoning)."""
    assert services.CYCLE_FREQUENCIES == (
        "Daily",
        "Weekly",
        "Fortnightly",
        "Monthly",
        "Bimonthly",
        "Quarterly",
        "Semiannual",
        "Annual",
    )


@pytest.mark.parametrize(
    "legacy,business",
    [
        ("monthly", "Monthly"),
        ("bi_monthly", "Bimonthly"),
        ("quarterly", "Quarterly"),
        ("biweekly", "Fortnightly"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ],
)
def test_w1_t1__a_legacy_frequency_value_maps_onto_its_business_word(legacy, business):
    """The three shipped values (`monthly` · `bi_monthly` · `quarterly`) and the
    PO's own spellings are ACCEPTED and STORED as the business word. A caller
    still sending the old vocabulary must not be refused — the migration maps
    the rows, and this maps the writes that arrive after it."""
    assert schedule.business_frequency(legacy) == business


def test_w1_t1__an_unknown_frequency_is_still_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_cycle(dana, {"code": "CY-F1", "frequency": "whenever"})
    assert caught.value.field_errors[0]["message_key"] == "metering.cycle.frequency_unknown"


def test_w1_t1__a_cycle_stores_the_business_word_the_old_vocabulary_asked_for(brazos, dana):
    with tenant_ctx(brazos):
        row = services.create_cycle(dana, {"code": "CY-F2", "frequency": "monthly"})
    assert row["frequency"] == "Monthly"


def test_w1_t1__a_cycle_carries_start_day_and_days_to_complete(brazos, dana):
    """B17 §2 — the cycle captures exactly three things about time: start day ·
    frequency · days to complete."""
    with tenant_ctx(brazos):
        row = services.create_cycle(
            dana,
            {"code": "CY-S1", "frequency": "Monthly", "start_day": 1, "days_to_complete": 5},
        )
    assert (row["start_day"], row["days_to_complete"]) == (1, 5)
    stored = models.Cycle.objects.get(code="CY-S1")
    assert (stored.start_day, stored.days_to_complete) == (1, 5)


def test_w1_t1__days_to_complete_must_be_at_least_one(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_cycle(dana, {"code": "CY-S2", "start_day": 1, "days_to_complete": 0})
    assert caught.value.field_errors[0]["field"] == "days_to_complete"


def test_w1_t1__the_backfill_reads_the_legacy_day_pair_first():
    """W1-T1's backfill, as the pure function the migration calls. A cycle that
    reads the 1st–3rd is a 3-day window opening on the 1st."""
    assert schedule.backfill_schedule(read_day_from=1, read_day_to=3) == (1, 3)
    assert schedule.backfill_schedule(read_day_from=12, read_day_to=16) == (12, 5)


def test_w1_t1__the_backfill_falls_back_to_the_legacy_calendar_dates():
    """`window_start`/`window_end` are the 2026-08-08 modal's DATES. A cycle
    that has them and no day pair still yields a start day and a length.

    ⚠ **THE COLUMNS ARE DROPPED (W5-T2) AND THIS PARAMETER PAIR IS NOT** —
    `backfill_schedule` keeps it because **migration 0019 calls this function
    against its own historical model**, where the columns still exist, and 0019
    must keep replaying correctly on a fresh database forever. So this case is
    not stale: it is the only remaining test of the path 0019 takes.
    """
    assert schedule.backfill_schedule(
        window_start=date(2026, 8, 12), window_end=date(2026, 8, 16)
    ) == (12, 5)


def test_w1_t1__the_backfill_invents_nothing_when_nothing_is_there():
    assert schedule.backfill_schedule() == (None, None)


def test_w1_t1__the_migration_deprecates_the_legacy_columns_and_drops_none_of_them():
    """B17 §6: *legacy calendar columns deprecated → dropped at W5*.

    ⚠ **UPDATED BY RC-W5-T2, DELIBERATELY, AND THE NO-`RemoveField` CLAUSE
    STAYS.** This test was W1 protecting W5's work from a lane that felt like
    tidying up, and W5 has now done the drop — in its OWN migration (0021),
    which is the thing the clause below still asserts. 0019 marks; 0021 removes;
    neither does the other's job, and a lane that adds a `RemoveField` to 0019
    would rewrite a migration that has already run on deployed databases.

    The tuple is unchanged and still names SIX, because six were deprecated.
    Five were dropped and `bill_date` was not — billing's due-terms fallback
    reads it and no ruling says what replaces it. `test_cr029_rcw5_legacy_
    columns.py` holds that split.
    """
    from importlib import import_module

    migration = import_module("apps.metering.migrations.0019_cr029_cycle_schedule")
    assert set(migration.LEGACY_DEPRECATED_COLUMNS) == {
        "window_start",
        "window_end",
        "bill_date",
        "read_day_from",
        "read_day_to",
        "due_day",
    }
    source = migration.__doc__ or ""
    assert "RC-W5" in source
    for operation in migration.Migration.operations:
        assert (
            type(operation).__name__ != "RemoveField"
        ), "0019 marks the legacy columns; metering 0021 drops them"


# ═══════════════════════════════════════════════════════════════════════════
# W1-T2 · ONE GENERATION — the derived read window
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t2__the_window_is_start_day_plus_days_to_complete():
    """B17 §2: *"start day + N days IS the read window"*. Worked: start day 1,
    5 days to complete, August 2026 → 1 Aug … 5 Aug."""
    assert schedule.derive_read_window(1, 5, date(2026, 8, 23)) == (
        date(2026, 8, 1),
        date(2026, 8, 5),
    )


def test_w1_t2__a_window_may_run_past_the_month_end():
    """Start day 29, 5 days to complete, August 2026 → 29 Aug … 2 Sep. The
    window is a length, not a range inside one month."""
    assert schedule.derive_read_window(29, 5, date(2026, 8, 23)) == (
        date(2026, 8, 29),
        date(2026, 9, 2),
    )


def test_w1_t2__a_start_day_past_the_month_end_clamps_to_the_last_day():
    """Start day 31 in February 2027 (28 days) → 28 Feb … 2 Mar. The same clamp
    `apps/reports/dashboard_regions.py` already applies to `read_day_to`:
    *"Clamped, because read_day_to may be 31 and February is not."*"""
    assert schedule.derive_read_window(31, 3, date(2027, 2, 10)) == (
        date(2027, 2, 28),
        date(2027, 3, 2),
    )


def test_w1_t2__no_start_day_or_no_length_derives_nothing():
    assert schedule.derive_read_window(None, 5, date(2026, 8, 23)) is None
    assert schedule.derive_read_window(1, None, date(2026, 8, 23)) is None


def test_w1_t2__a_wizard_created_cycle_shows_a_read_window_in_the_picker_and_on_s27(brazos, dana):
    """⚠ **THE BUG (B17 §5 gap G2).** A cycle created through the wizard writes
    the day fields and no calendar dates, and both the bill-run picker
    (`BillRunWizard.tsx` reads `cycle.window_start`/`window_end`) and the S27
    ops tab (`RoutesCyclesPage.tsx`, same two keys) render an em-dash for it.

    On the shipped tree this assertion reads `window_start is None`."""
    with tenant_ctx(brazos):
        created = services.create_cycle(
            dana,
            {
                "code": "CY-W1",
                "name": "Monthly — north",
                "frequency": "Monthly",
                "start_day": 1,
                "days_to_complete": 5,
            },
        )
    assert created["window_start"] is not None, "the run picker renders nothing without this"
    assert created["window_end"] is not None
    start = date.fromisoformat(created["window_start"])
    end = date.fromisoformat(created["window_end"])
    assert start.day == 1
    assert (end - start).days == 4  # 5 days INCLUSIVE
    assert created["read_window_source"] == "derived"


def test_w1_t2__a_stored_calendar_window_is_ACCEPTED_AND_IGNORED_NOW(brazos, dana):
    """⚠ **INVERTED BY RC-W5-T2, DELIBERATELY.** This asserted that legacy dates
    WIN over the derived window — *"they are the window a shipped run already
    used, and restating history is worse than showing none"* — which was right
    while the columns existed. metering 0021 dropped them, so there is no stored
    window to prefer and `read_window_source` can only answer `"derived"`.

    The payload keys are STILL SENT here on purpose: a client that has not moved
    may post them, and this pins the posture W5-T2 chose — **accepted, ignored,
    never refused.** Refusing would break a caller over a field it is entitled
    to think exists, for no gain; storing it is impossible; and silently mapping
    it onto `start_day` would let one particular period's dates redefine the
    cycle's repeating schedule.
    """
    with tenant_ctx(brazos):
        created = services.create_cycle(
            dana,
            {
                "code": "CY-W2",
                "frequency": "Monthly",
                "start_day": 1,
                "days_to_complete": 5,
                "window_start": "2026-08-01",
                "window_end": "2026-08-05",
            },
        )
    assert created["read_window_source"] == "derived"
    # The derived window is the cycle's own — the 1st for 5 days — in whatever
    # month the tenant is in, NOT the August the payload named.
    assert created["window_start"] is not None
    assert date.fromisoformat(created["window_start"]).day == 1
    assert (
        date.fromisoformat(created["window_end"]) - date.fromisoformat(created["window_start"])
    ).days == 4


def test_w1_t2__an_old_client_writing_the_day_pair_gets_the_new_fields(brazos, dana):
    """The other direction, and it is what makes the generation SINGLE rather
    than merely doubled: a caller that still posts the CR-006 day pair ends up
    with a start day and a length, so every reader sees the same window."""
    with tenant_ctx(brazos):
        created = services.create_cycle(
            dana, {"code": "CY-W4", "read_day_from": 1, "read_day_to": 3}
        )
    assert (created["start_day"], created["days_to_complete"]) == (1, 3)


def test_w1_t2__updating_the_start_day_moves_the_window_with_it(brazos, dana):
    """W5-T2: there is one generation to move now. This asserted that a PATCH
    dragged the legacy day pair along behind the ruled fields; the pair is gone,
    and what matters is that the DERIVED window follows — which it does by
    construction rather than by a copy somebody has to remember to keep."""
    with tenant_ctx(brazos):
        created = services.create_cycle(
            dana, {"code": "CY-W5", "start_day": 1, "days_to_complete": 3}
        )
        updated = services.update_cycle(dana, created["id"], {"start_day": 10})
    assert (updated["start_day"], updated["days_to_complete"]) == (10, 3)
    assert date.fromisoformat(updated["window_start"]).day == 10
    assert (
        date.fromisoformat(updated["window_end"]) - date.fromisoformat(updated["window_start"])
    ).days == 2


def test_w1_t2__the_cycles_export_carries_the_derived_window(brazos, dana):
    """B17 §7 W1-T2 names FOUR readers: the run picker, billing's due-date math,
    the ops Cycles tab and the exports. The export serialises `cycles_list`
    rows, so it inherits the derived window through the same one function —
    which is the point of moving the derivation there and not into each screen."""
    with tenant_ctx(brazos):
        services.create_cycle(
            dana, {"code": "CY-W6", "frequency": "Monthly", "start_day": 2, "days_to_complete": 4}
        )
        rows = {row["code"]: row for row in selectors.cycles_list()}
    assert rows["CY-W6"]["window_start"] is not None
    assert rows["CY-W6"]["window_end"] is not None


def test_w1_t2__no_money_field_reaches_the_new_schedule_fields(brazos, dana):
    """BR-MET-078, hardened by this CR — *"routes and cycles are grouping only
    - so we will not tag late fees , etc"*."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_cycle(
                dana, {"code": "CY-W7", "start_day": 1, "days_to_complete": 5, "late_day": 10}
            )
    assert caught.value.field_errors[0]["field"] == "late_day"
