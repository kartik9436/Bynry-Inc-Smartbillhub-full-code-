# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data) · US-CUS-021 (opening
#           balances as AGED BUCKETS)   Screens: S17 (the `AGEING` column
#           CR-030 §5.1.2 splits off `STATUS`)
# Defect:   DEF-629 — the seeded demo's ageing shapes drift with the calendar
# Rules:    BR-CUS-048 (buckets age FORWARD by CALENDAR DAYS from the cutover
#           as-of date) · BR-CUS-049 (opening JEs dated at cutover, immutable)
#           · BR-CUS-016 (ageing DERIVED, never stored) · BR-TEN-043 (event
#           time — a date that governs money is the EVENT's date, never a clock
#           a reader happens to read) · BR-TEN-063 (a replay writes nothing) ·
#           BR-TEN-081 (the tenant's own day) · CLAUDE.md hard rule 4
# Golden:   GT-16 ❄️ FROZEN (finance-signed 2026-08-08) — EXCLUDED from the
#           seed-time date by the PO's own ruling, and that exclusion is what
#           `test_def629_tc4`/`tc5` pin
# Tests:    this file
# ───────────────────────────────────────────────────────
"""DEF-629 — the demo seed decides its cutover date WHEN IT RUNS.

THE DEFECT, AND WHY NO EXISTING TEST COULD SEE IT
--------------------------------------------------
Opening buckets age FORWARD from the batch cutover date (BR-CUS-048, verbatim:
*"Buckets age forward by CALENDAR DAYS from the cutover as-of date (an amount
imported 45 days past due is 75 days past due 30 days later)"*) and BR-CUS-049
pins that date to the batch's ONE cutover. So a demo ageing shape planted at a
HARDCODED cutover stops being the shape it was planted as the moment the
calendar moves: a row seeded `Current` at 2026-08-31 reads `31–60` on
2026-10-01 and `90+` by December.

Every existing seed test asserts the STORED figures — the four bucket amounts,
the balance, the journal pair — and those stay correct forever. The thing that
drifts is the DERIVED cell, which no test read. DEF-629's own escape_reason says
so: *"the seed tests assert the stored figures, which stay correct forever,
while the DERIVED column silently changes underneath them"*. This file reads the
derived cell, through `selectors.ageing_segments_for` and nothing else.

THE RULING — PO 2026-08-24, verbatim
-------------------------------------
    *"whenever you do the migration cant you devcide the date at that time"*

❄️ **GT-16 IS EXCLUDED, and the exclusion is part of the same ruling** (decision
log 2026-08-24, item 5): *"GT-16's fixture is EXCLUDED: it is finance-signed at
cutover 2026-08-31 and that date is part of the frozen case. The seed-time date
applies to the DEMO SHAPES only."*

HOW THIS FILE AVOIDS BEING THE THING IT TESTS
----------------------------------------------
A test that read the real clock would drift exactly like the fixture does. So
**no test here ever reads a clock.** Each one names the day the seed is imagined
to run, pins the tenant's day to it (`seams.tenant_today`, the ONE seam both
`demo_cutover_on()` and `ageing_segments_for` read), and asserts the derived
segment on that same day. The days are chosen far apart on purpose — including
2026-10-01, the date DEF-629 predicts the first drift on — so a hardcoded
cutover cannot pass all four.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import import_writer
from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.customers import seams as customers_seams
from apps.customers import selectors as customers_selectors
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana/marcus are fixtures
    brazos,
    dana,
    marcus,
)
from tests.test_cr030_w0_customer_no import _account_for  # noqa: F401

pytestmark = pytest.mark.django_db

BUCKETS = customers_models.AccountOpeningBucket

#: B18 §5.1.5's three ageing rows, and the segment DEF-629 names for each:
#: *"derive `current` / `d31_60` / `d61_90`"*. One positive bucket each, so the
#: OLDEST-positive-band rule `ageing_segments_for` applies has one answer and
#: the assertion is about the DATE and nothing else.
DEMO_AGEING_SHAPES: tuple[tuple[str, dict[str, str], str], ...] = (
    ("Active / Current", {"ob_current": "118.40"}, BUCKETS.BUCKET_CURRENT),
    ("Active / 30d past", {"ob_31_60": "204.75"}, BUCKETS.BUCKET_31_60),
    ("Active / 60+ past", {"ob_61_90": "542.10"}, BUCKETS.BUCKET_61_90),
)

#: Four days a demo tenant might be seeded on, chosen so no single hardcoded
#: cutover can satisfy them all. `2026-10-01` is DEF-629's own predicted first
#: drift; `2026-08-31` is the frozen GT-16 date itself, present so the fix is
#: not merely "a different literal".
SEED_DAYS: tuple[date, ...] = (
    date(2026, 8, 31),
    date(2026, 10, 1),
    date(2027, 3, 15),
    date(2028, 12, 31),
)


def _pin_tenant_day(monkeypatch, day: date) -> None:
    """Pin the ONE seam both the policy and the derivation read.

    `sample_data.demo_cutover_on()` calls `seams.tenant_today()` and
    `selectors.ageing_segments_for()` falls back to the same function, so one
    patch fixes "the day the seed runs" AND "the day the screen is read" — which
    is the pairing the drift lives in.
    """
    monkeypatch.setattr(customers_seams, "tenant_today", lambda: day)


def _plant_shape(actor, tenant, *, label: str, mapped: dict[str, str], as_of: date):
    """One demo ageing shape, on its own seat, dated `as_of`.

    Written through `import_writer.write_opening_buckets` — the ONE writer of
    `account_opening_buckets` (BR-CUS-061's own posture) — never by setting a
    field, so what is asserted below is a real derivation over real rows.
    """
    account = _account_for(actor, tenant, label=label)
    import_writer.write_opening_buckets(
        account_id=account["id"],
        account_ref=account.get("account_no"),
        mapped=mapped,
        as_of=as_of,
        currency="USD",
        # BR-TEN-057 — the writer's own tag, not a second UPDATE beside it.
        # `demo_cutover_on()` looks only at sample rows, so a test that skipped
        # this would be exercising a different query from the one that ships.
        is_sample=True,
    )
    return account


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — THE DEFECT ITSELF: the shape derives its intended segment whenever the
#        seed runs
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("seed_day", SEED_DAYS, ids=lambda d: d.isoformat())
def test_def629_tc1__a_demo_shape_derives_its_intended_segment_whenever_the_seed_runs(
    monkeypatch, brazos, marcus, seed_day
):
    """The whole of DEF-629, on real rows.

    Seed the three shapes on `seed_day` at the cutover the SEED CHOOSES, then
    read the AGEING cell on that same day. `Active / Current` must read
    `current` on every one of these days — which a hardcoded 2026-08-31 cannot
    do, and does not: run against that literal this test fails on three of the
    four days, `current` deriving `d31_60` (31 days) on 2026-10-01 — DEF-629's
    own predicted first drift — `d90_plus` (196 days) on 2027-03-15 and
    `d90_plus` (853 days) on 2028-12-31.
    """
    _pin_tenant_day(monkeypatch, seed_day)
    with tenant_ctx(brazos):
        cutover = customers_sample.demo_cutover_on()
        assert cutover == seed_day, (
            "the demo cutover must be the day the seed RUNS (PO 2026-08-24), "
            f"and it answered {cutover} on {seed_day}"
        )
        planted = {
            expected: _plant_shape(
                marcus, brazos, label=f"D629 {expected}", mapped=mapped, as_of=cutover
            )
            for _name, mapped, expected in DEMO_AGEING_SHAPES
        }
        segments = customers_selectors.ageing_segments_for(
            [row["id"] for row in planted.values()], as_of=seed_day
        )
        for expected, account in planted.items():
            segment, days = segments[str(account["id"])]
            assert segment == expected, (
                f"a shape seeded to read `{expected}` on a demo plant of {seed_day} "
                f"derives `{segment}` ({days} days past due) instead — DEF-629"
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE SECOND RUN: a replay re-dates nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_def629_tc2__the_second_run_reuses_the_stored_cutover_and_never_re_dates(
    monkeypatch, brazos, marcus
):
    """*Decide the date at seed time* must not mean *a new date every time*.

    BR-CUS-049 makes the opening journal entries *"dated at cutover,
    immutable"*, so a replay that re-dated the buckets would leave the books at
    one cutover and the ageing at another. BR-TEN-063 (*a replay writes
    nothing*) and hard rule 4 point the same way: the first run decides, every
    run after reads that decision back.
    """
    first_day, much_later = date(2026, 9, 10), date(2027, 6, 1)
    _pin_tenant_day(monkeypatch, first_day)
    with tenant_ctx(brazos):
        cutover = customers_sample.demo_cutover_on()
        assert cutover == first_day
        _plant_shape(
            marcus, brazos, label="D629 replay", mapped={"ob_current": "77.00"}, as_of=cutover
        )

        # The clock has moved a long way. The seed runs again.
        _pin_tenant_day(monkeypatch, much_later)
        assert customers_sample.demo_cutover_on() == first_day, (
            "a replay must return the cutover already stored on this tenant's demo "
            "buckets — re-dating them would strand the immutable opening entries "
            "behind them at the old date (BR-CUS-049, hard rule 4)"
        )
        assert (
            customers_models.AccountOpeningBucket.objects.filter(
                tenant_id=brazos.id, is_sample=True
            )
            .exclude(as_of=first_day)
            .count()
            == 0
        ), "the stored rows moved on a replay"


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — a REAL migration's cutover is not the demo's
# ═══════════════════════════════════════════════════════════════════════════
def test_def629_tc3__a_real_migrations_cutover_never_becomes_the_demo_date(
    monkeypatch, brazos, marcus
):
    """The lookback is scoped to `is_sample` rows for a reason.

    A tenant that has migrated its OWN receivables holds opening buckets at its
    own cutover. If the demo policy read those, seeding sample data would date
    the demo shapes at a real utility's go-live — a date that has nothing to do
    with either the demo or today.
    """
    seed_day = date(2027, 2, 2)
    _pin_tenant_day(monkeypatch, seed_day)
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="D629 real")
        import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped={"ob_90_plus": "900.00"},
            as_of=date(2024, 1, 31),  # the utility's own go-live, years ago
            currency="USD",
        )
        assert customers_sample.demo_cutover_on() == seed_day


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 / TC-5 — ❄️ GT-16 IS EXCLUDED, on the tenant the seed actually plants
# ═══════════════════════════════════════════════════════════════════════════
#: THE DAY THIS FILE IMAGINES THE SEED RUNNING — chosen here, never inherited
#: from the clock (DEF-2796). It is deliberately NOT ❄️ GT-16's finance-signed
#: `2026-08-31`, which is the whole point of the two assertions below.
DEMO_SEED_DAY = date(2026, 11, 12)


@pytest.fixture()
def seeded(monkeypatch, brazos, dana):
    """The sample plant in the orchestrator's own order, through each module's
    REAL seam (the `test_cr030_w1_import_seed` fixture, unchanged).

    ⚠ **THE CLOCK IS PINNED, AND THAT IS DEF-2796 (2026-08-31).** This fixture
    used to seed on whatever day the suite ran, and `demo_cutover_on()` takes
    the tenant's own today on a first run (BR-TEN-081) — so on **2026-08-31**,
    and on that one day of the year only, the demo shapes were dated at exactly
    ❄️ GT-16's frozen `GT16_CUTOVER_ON` and `tc4`/`tc8` read

        assert datetime.date(2026, 8, 31) != datetime.date(2026, 8, 31)

    verbatim. The rule those cases state was never wrong; they were unable to
    express it on one day, and a lane editing this module that day inherited two
    failures it did not cause. **AND THE OTHER DIRECTION IS WORSE:** on the same
    day a genuine DEF-629 regression — a demo shape WRONGLY inheriting the
    frozen date — would compare equal to the correct seed-time date and fail for
    the innocent reason instead of the guilty one. A guard that cannot tell its
    pass from its fail is worse than no guard.

    Pinning the seam the seeder actually reads makes the case CHOOSE its date,
    so the two dates differ on every day of every year and the inequality means
    what it says.
    """
    monkeypatch.setattr(customers_seams, "tenant_today", lambda: DEMO_SEED_DAY)
    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        customers_sample.seed_sample_records(dana)
    return brazos, dana


def test_def629_tc4__gt16_keeps_its_frozen_cutover_and_the_demo_shapes_take_seed_time(
    seeded,
):
    """❄️ The exclusion, and the MEASUREMENT behind this lane's scope.

    Two claims, both about the tenant a trial user actually receives:

      1. `A-12103`'s four buckets are dated **2026-08-31** — B5 GT-16 line 55,
         finance-signed, and not a date any seeder chose;
      2. it is the ONLY account carrying opening buckets. DEF-629's three demo
         shapes are three of B18 §5.1.5's eight `[shot]` rows and W2 task 2.10
         is BLOCKED on fixture estate, so they are not seeded yet.

    ⚠ **THE TRIPWIRE FIRED ON 2026-08-24 AND THIS IS THE EXTENSION IT ASKED
    FOR.** The PO authorised B18 §5.1.5's eight `[shot]` account shapes the same
    day (*"so add them"*) and CR-030 W2 task 2.10 seated them, so claim 2 as
    written — *"GT-16 is the only shape"* — is no longer the truth about the
    tenant a trial user receives, and asserting it would pin a scope decision
    the PO has since reversed. **What the tripwire was protecting is kept
    exactly:** every OTHER shape must carry `demo_cutover_on()`'s date, and
    ❄️ GT-16 must still carry the finance-signed 2026-08-31. A literal cutover
    in a seeder is still the defect; this is how the file now catches one.
    """
    brazos, _dana = seeded
    with tenant_ctx(brazos):
        rows = list(
            customers_models.AccountOpeningBucket.objects.values(
                "account__account_no", "as_of"
            ).order_by("account__account_no")
        )
        assert rows, "the demo tenant carries no opening buckets at all"
        frozen = [r for r in rows if r["account__account_no"] == customers_sample.GT16_ACCOUNT_NO]
        assert len(frozen) == 4, f"❄️ GT-16 must carry four aged bands, found {len(frozen)}"
        assert {r["as_of"] for r in frozen} == {customers_sample.GT16_CUTOVER_ON}, (
            "❄️ GT-16 is finance-signed at cutover 2026-08-31 (B5 line 55) and the seed-time "
            "date is for the DEMO SHAPES only (PO 2026-08-24)"
        )
        others = sorted(
            {
                r["account__account_no"]
                for r in rows
                if r["account__account_no"] != customers_sample.GT16_ACCOUNT_NO
            }
        )
        assert others, (
            "no demo ageing shape is seeded at all — B18 §5.1.5's eight `[shot]` shapes "
            "were authorised by the PO on 2026-08-24 (*so add them*) and CR-030 W2 task "
            "2.10 seats them through `apps.customers.sample_data._seed_cr030_account_shapes`"
        )
        seed_time = customers_sample.demo_cutover_on()
        # DEF-2796 — say what the rule IS, not only what it is not. The demo
        # shapes take the day the seed RAN (pinned by `seeded`), and ❄️ GT-16
        # does not move off its finance-signed date. Both hold every day of the
        # year; the bare inequality below held 364 of them.
        assert seed_time == DEMO_SEED_DAY, (
            "the demo shapes must take the day the seed RAN (PO 2026-08-24), and this "
            f"tenant was seeded on {DEMO_SEED_DAY} yet reports {seed_time}"
        )
        assert customers_sample.GT16_CUTOVER_ON == date(2026, 8, 31), (
            "❄️ GT-16's cutover is finance-signed at 2026-08-31 (B5 line 55) and moving "
            "it is a re-sign through HUMAN-GUIDE §6, never a code edit"
        )
        assert seed_time != customers_sample.GT16_CUTOVER_ON, (
            "the demo shapes must not inherit ❄️ GT-16's finance-signed date — that is "
            "DEF-629 itself, wearing the lookback's clothes"
        )
        demo_dates = {
            r["as_of"] for r in rows if r["account__account_no"] != customers_sample.GT16_ACCOUNT_NO
        }
        assert demo_dates == {seed_time}, (
            f"every demo ageing shape is dated at SEED TIME ({seed_time}) — DEF-629, PO "
            '2026-08-24: "whenever you do the migration cant you devcide the date at that '
            'time". A literal cutover in the seeder is the defect, not the fix; found '
            f"{sorted(str(d) for d in demo_dates)} on {', '.join(others)}"
        )


@pytest.mark.parametrize("years_on", [0, 1, 5])
def test_def629_tc5__the_frozen_shape_does_not_drift_which_is_why_excluding_it_is_safe(
    seeded, years_on
):
    """The exclusion costs nothing, and this is the evidence.

    ❄️ GT-16 holds **121.00** in `90+`, so the OLDEST band holding a positive
    amount is `90+` on cutover day and stays `90+` for ever — forward ageing can
    only make a band older and there is no band above `90+`. Its
    `days_past_due` grows (91 → 456 → 1,916), which is BR-CUS-048 working
    correctly on a frozen fixture, and the AGEING column reads the same cell.
    """
    brazos, _dana = seeded
    as_of = customers_sample.GT16_CUTOVER_ON + timedelta(days=365 * years_on)
    with tenant_ctx(brazos):
        account_id = (
            customers_models.Account.objects.filter(
                tenant_id=brazos.id, account_no=customers_sample.GT16_ACCOUNT_NO
            )
            .values_list("id", flat=True)
            .first()
        )
        assert account_id is not None, "❄️ GT-16's account is not planted"
        segment, days = customers_selectors.ageing_segments_for([account_id], as_of=as_of)[
            str(account_id)
        ]
        assert segment == BUCKETS.BUCKET_90_PLUS
        assert days == customers_selectors.AGEING_BAND_FLOORS[BUCKETS.BUCKET_90_PLUS] + (
            as_of - customers_sample.GT16_CUTOVER_ON
        ).days


def test_def629_tc6__the_frozen_sum_is_untouched_by_this_lane(seeded):
    """❄️ B5 GT-16 line 56 — `accounts.balance` = 267.30, Σ buckets exact.

    Nothing in DEF-629's fix goes near a frozen figure; this asserts it from the
    rows rather than trusting the diff.
    """
    brazos, _dana = seeded
    with tenant_ctx(brazos):
        total = sum(
            customers_models.AccountOpeningBucket.objects.filter(
                tenant_id=brazos.id, account__account_no=customers_sample.GT16_ACCOUNT_NO
            ).values_list("amount", flat=True),
            Decimal("0"),
        )
        assert total == customers_sample.GT16_BALANCE == Decimal("267.30")


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the exclusion GUARD, shown to bite (hard-won law 7)
# ═══════════════════════════════════════════════════════════════════════════
def test_def629_tc7__a_seat_offering_any_other_cutover_is_refused(monkeypatch, brazos, dana):
    """A guard is not trusted green until it has been seen RED.

    The seat is metering's to publish, so the only way customers can hold ❄️
    GT-16's finance-signed date is to REFUSE a seat that offers a different
    one. Without this, the day a lane routes the migration through
    `demo_cutover_on()` — the natural next step, and the one the PO's ruling
    invites — `A-12103` would silently be re-dated and the ONLY signal would be
    golden-verify noticing much later.
    """
    from core import sample_fixture

    moved = date(2026, 9, 30)
    monkeypatch.setattr(
        customers_sample,
        "_cutover_seat",
        lambda: {
            "run_id": None,
            "run_no": "RUN-2814",
            "unit_no": "SCW-U-101",
            "cutover_on": moved,
        },
    )
    with tenant_ctx(brazos):
        with pytest.raises(sample_fixture.BlockCannotRun) as refusal:
            customers_sample._seed_gt16_cutover_account(dana)
    assert customers_sample.GT16_CUTOVER_ON.isoformat() in str(refusal.value)
    assert str(moved) in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — ❄️ GT-16's date is excluded from the LOOKBACK too
# ═══════════════════════════════════════════════════════════════════════════
def test_def629_tc8__the_frozen_cutover_is_not_inherited_by_the_demo_shapes(monkeypatch, seeded):
    """The exclusion has two halves and this is the one that is easy to miss.

    ❄️ GT-16's four buckets carry `is_sample = True` (BR-TEN-057) like every
    other sample row, so a lookback that only asked *"has this tenant any demo
    buckets?"* would find 2026-08-31 and hand the FROZEN date to every demo
    shape seeded afterwards — re-creating DEF-629 through the very function
    written to close it. `demo_cutover_on()` excludes `A-12103` by number.
    """
    brazos, _dana = seeded
    seed_day = date(2027, 5, 20)
    _pin_tenant_day(monkeypatch, seed_day)
    with tenant_ctx(brazos):
        # ⚠ **AMENDED 2026-08-24 (CR-030 W2 task 2.10).** This asserted
        # `== seed_day`, which held only while the tenant carried NO demo
        # buckets: with none stored, `demo_cutover_on()` falls to the tenant's
        # today. The eight `[shot]` shapes are now seeded (PO: *"so add them"*),
        # so the function correctly takes its PERSISTED branch — *"a replay
        # re-dates nothing"* (BR-CUS-049 makes the opening entries immutable) —
        # and returns the date those shapes were actually migrated at, whatever
        # the clock says today. **The claim this test exists for is unchanged
        # and is the second line:** ❄️ GT-16's frozen date is excluded from the
        # lookback, so it can never become a demo shape's.
        stored = customers_sample.demo_cutover_on()
        # DEF-2796 — the POSITIVE statement first: the lookback returns the day
        # the shapes were actually migrated at, which `seeded` chose. That is
        # true every day; `stored != GT16_CUTOVER_ON` was not.
        assert stored == DEMO_SEED_DAY, (
            f"the lookback must return the day the demo shapes were migrated at "
            f"({DEMO_SEED_DAY}); it returned {stored}"
        )
        assert stored != customers_sample.GT16_CUTOVER_ON
        assert stored != seed_day, (
            "with demo shapes on file the lookback wins over the clock — if this ever "
            "equals the pinned day, the persistence branch has stopped working and a "
            "replay would re-date buckets whose journal entries cannot move"
        )
        parked = customers_models.AccountOpeningBucket.objects.exclude(
            account__account_no=customers_sample.GT16_ACCOUNT_NO
        ).values_list("as_of", flat=True)
        assert set(parked) == {stored}
