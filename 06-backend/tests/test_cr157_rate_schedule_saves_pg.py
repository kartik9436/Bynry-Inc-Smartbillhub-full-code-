# ── Trace ──────────────────────────────────────────────
# Change:  CR-157-BRC10 wave A — rate schedules: two clerks saving at once get a
#          named refusal, and billing reads exactly one record for every date.
# Defect:  DEF-RAT-8750 — no save path took a row lock, so the second of two
#          simultaneous saves met `rating/0047`'s DEFERRED constraint at COMMIT
#          as a raw IntegrityError instead of `rating.schedules.window_overlap`.
# Rules:   BR-RAT-037 (windows never overlap; a change is a new version) ·
#          BR-RAT-007 (the version in force on the SERVICE date) · BR-RAT-104 /
#          BR-RAT-1016 verb 2 / BR-RAT-1044 (a correction restates the window and
#          the original is kept) · BR-RAT-031 (a draft has no window) ·
#          CLAUDE.md hard-won law 14 (SQLite has no exclusion constraint, no
#          row locks and no aborted-transaction state — proved here, on
#          PostgreSQL) · law 7 (the control case proves the race is real)
# ───────────────────────────────────────────────────────
"""Concurrent rate-schedule saves, on real PostgreSQL, through the real services.

    DATABASE_URL=postgres://… JOBS_EAGER=false \\
        pytest tests/test_cr157_rate_schedule_saves_pg.py --ds=config.settings.pgtest --reuse-db

⚠ **`--reuse-db` AFTER THIS FILE NEEDS `--create-db` ONCE.** Its race cases are
transactional, so their teardown FLUSHES the database; `serialized_rollback`
puts the platform seed back at the START of each such case, and pytest-django
runs them last — so the session is fine, but the reused database is left
empty for the NEXT session (*"SubscriptionPlan matching query does not
exist"* on every fixture). Measured on 2026-10-01; `test_bbr_f4_two_sends_pg`
has the same property.

⚠ **SKIPPED BY NAME ON SQLITE, AND THE SKIP IS THE POINT** (hard-won law 14):
no row locks, no exclusion constraint, no second connection that can see a
committed row — the race this file is about cannot exist there.

HOW THE RACE IS FORCED, rather than hoped for. Clerk A's save is slowed AFTER
it has written its version and BEFORE it commits (`_write_version` is wrapped
for thread A only); clerk B starts only once A has written. So B's save
overlaps A's uncommitted transaction every single run:

  * with the fix, B waits at `_lock_schedule` until A commits, then reads A's
    version and is refused BY NAME (`rating.schedules.window_overlap`);
  * without it (the CONTROL case, which puts the old reads back), B reads the
    world without A's version, passes `_guard_window`, writes, and meets the
    deferred constraint at COMMIT — a raw `IntegrityError`. **That control is
    what makes the green case mean something**: it is the same race, run
    against the code as it was, and it fails the way `DEF-RAT-8750` says.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked rather than assumed:
  * B finishing BEFORE A writes — then there is no race at all and B is refused
    by the ordinary single-clerk guard. The event below makes B wait for A's
    write, and the control case shows the race is real (it goes red without
    the lock).
  * the threads sharing ONE connection — Django opens one per thread, and each
    thread closes its own at the end (`connections.close_all()`).
  * a deadlock read as a refusal — a deadlock surfaces as `DeadlockDetected`
    (SQLSTATE 40P01); every outcome is recorded as its exception TYPE and
    MESSAGE KEY and asserted exactly.
"""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, connection, connections, transaction

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env)
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "SQLite has no row locks, no exclusion constraint and no second connection "
        "that sees a committed row, so this race cannot exist there — skipping is "
        "honest; passing would be a lie (CLAUDE.md hard-won law 14)"
    ),
)

#: A transactional case tears down by FLUSHING; `serialized_rollback` puts the
#: platform seed back for the next file (the reason `test_bbr_f4_two_sends_pg`
#: gives).
TRANSACTIONAL = pytest.mark.django_db(transaction=True, serialized_rollback=True)

V1_FROM = "2026-01-01"
TIERS_V2 = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.40"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "5.00"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.50"},
]
TIERS_FIX = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.25"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "4.80"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.20"},
]


def _version_payload(effective_from, tiers=TIERS_V2, reason="Board order 2026-14"):
    return {
        "model": "tiered",
        "uom": "kgal",
        "effective_from": effective_from,
        "reason": reason,
        "structure": {"tiers": tiers},
    }


def _outcome(call):
    """Run one save; record WHAT happened, never swallow it."""
    try:
        call()
        return "saved"
    except errors.BizError as exc:
        return f"refused:{exc.message_key}"
    except IntegrityError as exc:
        return f"raw:IntegrityError:{type(exc.__cause__).__name__}"
    except Exception as exc:  # noqa: BLE001 — a deadlock must show up as itself
        return f"raw:{type(exc).__name__}"


def _race(env, monkeypatch, first, second, *, hold=1.0):
    """Clerk A runs `first`, writes, and holds its transaction open for `hold`
    seconds; clerk B runs `second` only once A has written. Returns
    `(outcome_a, outcome_b, seconds)`."""
    a_wrote = threading.Event()
    real_write = services._write_version

    def slow_write(*args, **kwargs):
        version = real_write(*args, **kwargs)
        if threading.current_thread().name == "clerk-a":
            a_wrote.set()
            time.sleep(hold)
        return version

    monkeypatch.setattr(services, "_write_version", slow_write)
    outcomes: dict[str, str] = {}

    def clerk(name, call):
        try:
            if name == "clerk-b":
                assert a_wrote.wait(timeout=60), "clerk A never wrote — no race was run"
            with tenant_ctx(env.tenant):
                outcomes[name] = _outcome(call)
        finally:
            connections.close_all()

    started = time.monotonic()
    threads = [
        threading.Thread(target=clerk, args=("clerk-a", first), name="clerk-a"),
        threading.Thread(target=clerk, args=("clerk-b", second), name="clerk-b"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not any(thread.is_alive() for thread in threads), "a save never finished"
    return outcomes.get("clerk-a"), outcomes.get("clerk-b"), time.monotonic() - started


def _schedule(env, name="Res Water · Race"):
    return env.tiered_schedule(name, "water", RES_WATER_TIERS, effective_from=V1_FROM)


def _activated(tariff_id):
    return list(
        models.TariffVersion.objects.filter(tariff_id=tariff_id, effective_from__isnull=False)
        .order_by("effective_from", "created_at")
    )


def _live_rows_on(tariff_id, day):
    """Every row the database could price `day` from — must always be ONE."""
    return list(
        models.TariffVersion.objects.filter(
            tariff_id=tariff_id,
            effective_from__isnull=False,
            effective_from__lte=day,
            superseded_by__isnull=True,
        ).exclude(effective_to__lt=day)
    )


@POSTGRES_ONLY
@pytest.mark.django_db
def test_cr157_pg__this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


# ── 1 · two clerks, one new version each, the same start date ──────────────


@POSTGRES_ONLY
@TRANSACTIONAL
def test_cr157_pg__two_clerks_one_date__one_saves_the_other_is_refused_by_name(
    env, monkeypatch
):
    """THE DEFECT, CLOSED. Dana and Marcus both file the June rate change for
    the same schedule at the same moment. One version lands; the other clerk
    reads *"Versions may not overlap"* — never a server error — and nothing of
    the refused save is left behind."""
    water = _schedule(env)
    tid = water["id"]
    a, b, seconds = _race(
        env,
        monkeypatch,
        lambda: services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01")),
        lambda: services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01")),
    )
    print(f"\nPROOF CR-157 two clerks: A={a} B={b} in {seconds:.2f}s")
    assert a == "saved", a
    assert b == "refused:rating.schedules.window_overlap", b
    with tenant_ctx(env.tenant):
        rows = _activated(tid)
        logs = models.RateChangeLog.objects.filter(entity_type="schedule", entity_id=tid).count()
    # v1 + exactly ONE June version — no half-written second one.
    assert [str(r.effective_from) for r in rows] == ["2026-01-01", "2026-06-01"]
    assert rows[0].effective_to == date(2026, 5, 31)
    assert rows[1].effective_to is None
    assert logs == 1, "the refused save wrote a rate_change_log row"


@POSTGRES_ONLY
@TRANSACTIONAL
def test_cr157_pg__control__without_the_lock_the_same_race_is_a_raw_error(env, monkeypatch):
    """⚠ THE CONTROL — the same race against the code AS IT WAS (plain reads,
    no immediate check). It must fail the way `DEF-RAT-8750` says, or the green
    case above proves nothing (hard-won law 7: prove it RED in the harness that
    runs it). Recorded result when written: B = `raw:IntegrityError:
    ExclusionViolation`."""
    monkeypatch.setattr(services, "_lock_schedule", selectors.tariff_or_404)
    monkeypatch.setattr(services, "_check_windows_now", lambda tariff, effective_from: None)
    water = _schedule(env, name="Res Water · Control")
    tid = water["id"]
    a, b, _ = _race(
        env,
        monkeypatch,
        lambda: services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01")),
        lambda: services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01")),
    )
    print(f"\nPROOF CR-157 control (old code): A={a} B={b}")
    assert a == "saved", a
    assert b.startswith("raw:IntegrityError"), b


# ── 2 · different verbs at once: no deadlock, one legal history ───────────


@POSTGRES_ONLY
@TRANSACTIONAL
def test_cr157_pg__a_correction_and_a_rate_change_at_once_never_deadlock(env, monkeypatch):
    """Ana corrects v1's mistyped price while Marcus files the June change.
    Both lock the schedule row FIRST, so one waits for the other — no
    `DeadlockDetected`, both land, and every date still has exactly one
    pricing row."""
    water = _schedule(env, name="Res Water · Two verbs")
    tid = water["id"]
    with tenant_ctx(env.tenant):
        v1 = _activated(tid)[0]
    a, b, seconds = _race(
        env,
        monkeypatch,
        lambda: services.correct_rate_schedule_version(
            env.admin,
            tid,
            str(v1.id),
            {"model": "tiered", "uom": "kgal", "reason": "Tier 1 typed 3.20, filed 3.25",
             "structure": {"tiers": TIERS_FIX}},
        ),
        lambda: services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01")),
    )
    print(f"\nPROOF CR-157 two verbs: A={a} B={b} in {seconds:.2f}s")
    assert a == "saved", a
    assert b == "saved", b
    with tenant_ctx(env.tenant):
        for offset in range(0, 365, 7):
            day = date(2026, 1, 1) + timedelta(days=offset)
            assert len(_live_rows_on(tid, day)) == 1, day


@POSTGRES_ONLY
@TRANSACTIONAL
def test_cr157_pg__two_activations_of_one_saved_draft__one_activates_the_other_is_refused(
    env, monkeypatch
):
    """The second hole `DEF-RAT-8750` names: both clerks press Activate on the
    same saved draft. Without the lock both found *no live version*, and the
    one posting the structure would `_discard_draft` — a DELETE by primary key
    of the row the other had just activated. Now the second reads the first's
    activation and is refused by name; the activated version survives."""
    env._base_codes_for_activation("water")
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin,
            {"name": "Res Water · Draft race", "service": "water", "model": "tiered",
             "uom": "kgal", "structure": {"tiers": RES_WATER_TIERS}},
        )
    tid = draft["id"]
    a, b, _ = _race(
        env,
        monkeypatch,
        lambda: services.activate_rate_schedule(
            env.admin, tid,
            {"model": "tiered", "uom": "kgal", "effective_from": "2026-03-01",
             "structure": {"tiers": RES_WATER_TIERS}},
        ),
        lambda: services.activate_rate_schedule(
            env.admin, tid,
            {"model": "tiered", "uom": "kgal", "effective_from": "2026-03-01",
             "structure": {"tiers": TIERS_V2}},
        ),
    )
    print(f"\nPROOF CR-157 two activations: A={a} B={b}")
    assert a == "saved", a
    assert b == "refused:rating.schedules.already_activated", b
    with tenant_ctx(env.tenant):
        rows = _activated(tid)
        drafts = models.TariffVersion.objects.filter(tariff_id=tid, effective_from__isnull=True)
        assert len(rows) == 1 and rows[0].effective_from == date(2026, 3, 1)
        assert not drafts.exists()


@POSTGRES_ONLY
@TRANSACTIONAL
def test_cr157_pg__two_draft_saves_at_once__last_one_wins_and_one_draft_remains(
    env, monkeypatch
):
    """Two autosaves of one draft. A draft is dateless and is REPLACED whole on
    every save (BR-RAT-031), so the lawful ending is the later save's content
    and exactly one draft row — never `uq_tariff_versions_one_draft` as a raw
    error."""
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin,
            {"name": "Res Water · Autosave", "service": "water", "model": "tiered",
             "uom": "kgal", "structure": {"tiers": RES_WATER_TIERS}},
        )
    tid = draft["id"]
    a, b, _ = _race(
        env,
        monkeypatch,
        lambda: services.update_rate_schedule(
            env.admin, tid, {"model": "tiered", "uom": "kgal", "structure": {"tiers": TIERS_V2}}
        ),
        lambda: services.update_rate_schedule(
            env.admin, tid, {"model": "tiered", "uom": "kgal", "structure": {"tiers": TIERS_FIX}}
        ),
    )
    assert (a, b) == ("saved", "saved"), (a, b)
    with tenant_ctx(env.tenant):
        drafts = list(models.TariffVersion.objects.filter(tariff_id=tid, effective_from__isnull=True))
        assert len(drafts) == 1
        first_tier = models.RateTier.objects.filter(tariff_version=drafts[0]).order_by("seq").first()
        assert str(first_tier.unit_price.normalize()) == "3.25"  # clerk B's, the later save


# ── 3 · one record for every date, through the services ──────────────────


def _check_now():
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


@POSTGRES_ONLY
@pytest.mark.django_db
def test_cr157_pg__v1_v2_v3_and_a_correction__exactly_one_row_prices_every_day(
    env, monkeypatch
):
    """Area 1 + 3. v1 from 01/01, v2 from 04/01, v3 from 07/01, then v2's price
    corrected (same window, original kept). For EVERY day of 2026 the database
    holds exactly one row that could price it, `in_force_version` returns that
    row, the constraint is satisfied when forced, and a catch-up bill for
    February still reads v1."""
    from apps.rating import seams

    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 5, 15))
    water = _schedule(env, name="Res Water · Three versions")
    tid = water["id"]
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-04-01"))
        services.create_rate_schedule_version(
            env.admin, tid, _version_payload("2026-07-01", tiers=TIERS_FIX, reason="Board 2026-22")
        )
        v1, v2, v3 = _activated(tid)
        services.correct_rate_schedule_version(
            env.admin, tid, str(v2.id),
            {"model": "tiered", "uom": "kgal", "reason": "Tier 2 typed 5.00, filed 4.95",
             "structure": {"tiers": TIERS_V2[:1] + [
                 {"from_qty": "4", "to_qty": "10", "unit_price": "4.95"}
             ] + TIERS_V2[2:]}},
        )
        _check_now()
        v2.refresh_from_db()
        fix = models.TariffVersion.objects.get(corrects=v2)
        tariff = models.Tariff.objects.get(pk=tid)
        # The original is KEPT, stamped, and stops pricing (BR-RAT-104/1044).
        assert v2.superseded_by_id == fix.id
        assert v2.effective_to == date(2026, 6, 30)  # a stated end is never moved
        assert (fix.effective_from, fix.effective_to) == (date(2026, 4, 1), date(2026, 6, 30))
        expected = {v1.id: (date(2026, 1, 1), date(2026, 3, 31)),
                    fix.id: (date(2026, 4, 1), date(2026, 6, 30)),
                    v3.id: (date(2026, 7, 1), date(2026, 12, 31))}
        day = date(2026, 1, 1)
        while day <= date(2026, 12, 31):
            live = _live_rows_on(tid, day)
            assert len(live) == 1, (day, [str(r.id) for r in live])
            chosen = selectors.in_force_version(tariff, day)
            assert chosen.id == live[0].id
            lo, hi = expected[chosen.id]
            assert lo <= day <= hi, (day, chosen.effective_from)
            day += timedelta(days=1)
        # A catch-up bill for February, run in May, prices on v1 (BR-RAT-007).
        assert selectors.pricing_inputs(tariff, date(2026, 2, 15))["version_id"] == str(v1.id)
        assert selectors.pricing_inputs(tariff, date(2026, 5, 15))["version_id"] == str(fix.id)


@POSTGRES_ONLY
@pytest.mark.django_db
def test_cr157_pg__an_earlier_start_is_refused_by_name(env):
    """A new version may not start on or before the newest one (BR-RAT-037)."""
    water = _schedule(env, name="Res Water · Earlier start")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(env.admin, water["id"], _version_payload("2026-06-01"))
        with pytest.raises(errors.BizError) as refused:
            services.create_rate_schedule_version(
                env.admin, water["id"], _version_payload("2026-05-01")
            )
    assert refused.value.message_key == "rating.schedules.window_overlap"


@POSTGRES_ONLY
@pytest.mark.django_db
def test_cr157_pg__the_backstop_names_an_overlap_a_foreign_writer_left_behind(env):
    """`_check_windows_now` — the database's own rule asked at the end of the
    save. A second live v1 is planted the way an un-locked writer would leave
    it (two open windows from 01/01); the next rate change closes both at
    05/31, they still overlap EACH OTHER, and the clerk reads the named refusal
    — not an `IntegrityError` at COMMIT. Nothing of the save survives."""
    water = _schedule(env, name="Res Water · Foreign writer")
    tid = water["id"]
    with tenant_ctx(env.tenant):
        v1 = _activated(tid)[0]
        twin = models.TariffVersion.objects.get(pk=v1.pk)
        twin.pk = None
        twin.id = None
        twin._state.adding = True
        twin.save(force_insert=True)
        with pytest.raises(errors.BizError) as refused:
            with transaction.atomic():
                services.create_rate_schedule_version(env.admin, tid, _version_payload("2026-06-01"))
        assert refused.value.message_key == "rating.schedules.window_overlap"
        # The refused save wrote nothing: both twins are still open, no June row.
        rows = _activated(tid)
        assert [r.effective_to for r in rows] == [None, None]
        assert not any(r.effective_from == date(2026, 6, 1) for r in rows)
        models.TariffVersion.objects.filter(pk=twin.pk).delete()
