# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-10165 (Move-in step 1 read date) · DEF-CUS-10166 (Mark as
#           cut closing reading) · DEF-CUS-10167 (Enter opening read date)
# Ruling:   PO 2026-10-17, decision log *"WHERE A USER ENTERS A METER
#           READING"* — *"Move-in, step 1 (opening) - read date is required"*,
#           gaps 3 and 6 (closing reading + read date at the cut; read date on
#           Enter opening read).
# Rules:    BR-CUS-021 · BR-MET-128 · BR-TEN-043 (the tenant's day, never a
#           clock) · CLAUDE.md hard rules 1 · 3 · 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A read date a clerk chose: accepted, defaulted, refused — on all three
doors, read back from `meter_reads`.**

RED PROVED (law 7), through pytest — the harness that runs them: with the
guard switched off by a one-fixture plugin (`_refuse_bad_read_dates` →
no-op) the five refusal cases fail `DID NOT RAISE` (13 run: 5 failed, 8
passed); with it on, 13 of 13 pass on SQLite and on PostgreSQL 16. The cut's
ordering case asserts what `b30401c66` did not do: there, `commit_cut` raised
the cut bill BEFORE posting `final_reads`, so the spy would have seen no head.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A date check that reads a server clock.** `tenant_today` is pinned to
    2026-08-25 here, so a check reading `date.today()` (2026-10-17 on the day
    this was written) would pass 2026-09-01 and the future case goes red.
  * **A before-last check that reads another tenant's reads.** The isolation
    case gives `lonestar` the SAME meter number with a later reading; a check
    that ignored the tenant would refuse brazos's lawful date.
  * **A refusal that leaves debris.** Each refusal asserts no reading landed.
"""

from datetime import date

import pytest

from core import errors

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import disconnect_record
from apps.customers import moves
from apps.customers import seams as customers_seams
from apps.customers import move_in_flow
from apps.customers import services as customers_services
from apps.metering import models as metering_models

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import a_meter, commit_read, make_premises, make_unit, seed_config, tenant_ctx
from tests.test_w9_event_reads import (
    _account_on,
    _asset_id,
    _head,
    _metered_unit,
    _scheduled_cut,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)


@pytest.fixture(autouse=True)
def _pinned_today(monkeypatch):
    monkeypatch.setattr(customers_seams, "tenant_today", lambda: TODAY)


def _move_in(dana, unit_id, reads, opened_at="2026-08-20"):
    """A first-occupant move-in on a vacant unit, through `move_in_to_unit` —
    the one `_move_in` body the wizard's door shares — so no move-out (and the
    final bill it now drafts) is needed to make the unit vacant."""
    return customers_services.move_in_to_unit(
        dana,
        unit_id,
        {
            "account_type": "residential",
            "opened_at": opened_at,
            "contact": {"full_name": "Alvarez, Rosa"},
            "customer": identity_fixtures.customer_block("Alvarez, Rosa", account_type="residential"),
            "initial_reads": reads,
        },
    )


def _vacant(dana, brazos, label="Unit D"):
    return _metered_unit(dana, brazos, label=label)


def _reads_on(asset_id):
    return metering_models.MeterRead.objects.filter(asset_id=asset_id).count()


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10165 · MOVE-IN STEP 1
# ═══════════════════════════════════════════════════════════════════════════
def test_move_in__a_read_date_before_the_move_in_is_stored_as_typed(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        moved = _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-18"}])
        head = _head(_asset_id(unit, "M-9101"))
    assert moved["event_reads"]["posted_reads"] == 1
    assert head.event_context == "move_in"
    assert head.read_at.date() == date(2026, 8, 18), "the clerk's date, not the move-in day"


def test_move_in__a_row_without_a_date_still_takes_the_move_in_day(brazos, dana):
    """Backward compatibility: a parked draft from before the column sends none."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566"}])
        head = _head(_asset_id(unit, "M-9101"))
    assert head.read_at.date() == date(2026, 8, 20)


def test_move_in__a_read_date_after_today_is_refused_and_nothing_lands(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-09-01"}])
        landed = _reads_on(_asset_id(unit, "M-9101"))
    fe = caught.value.field_errors[0]
    assert fe["field"] == "initial_reads[1].read_at"
    assert fe["message_key"] == "customers.event_reads.read_at_future"
    assert fe["params"]["today"] == "2026-08-25"
    assert landed == 0


def test_move_in__a_read_date_before_the_meters_last_reading_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        commit_read(dana, asset_id, day="2026-08-12", value="43000")
        before = _reads_on(asset_id)
        with pytest.raises(errors.ValidationError) as caught:
            _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-10"}])
        after = _reads_on(asset_id)
    fe = caught.value.field_errors[0]
    assert fe["message_key"] == "customers.event_reads.read_at_before_last"
    assert fe["params"]["last_read_at"] == "2026-08-12"
    assert after == before


def test_move_in__the_same_day_as_the_last_reading_is_lawful(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        commit_read(dana, asset_id, day="2026-08-12", value="43000")
        moved = _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-12"}])
    assert moved["event_reads"]["posted_reads"] == 1


def test_move_in__a_garbled_date_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "1", "read_at": "18/08/2026"}])
    assert caught.value.field_errors[0]["message_key"] == "customers.event_reads.read_at_invalid"


def test_isolation__another_tenants_later_reading_on_the_same_meter_number_is_not_read(
    brazos, lonestar, dana, erin
):
    with tenant_ctx(lonestar):
        seed_config()
        # Lonestar is water-only: the SAME meter number, a LATER reading.
        premises = make_premises(erin, services_available=["water"])
        other = make_unit(erin, premises["id"], label="Other", services=["water"])
        a_meter(erin, "M-9101", unit_id=other["id"], service="water", uom="kgal")
        commit_read(erin, _asset_id(other, "M-9101"), day="2026-08-24", value="99999", unit="kgal")
    with tenant_ctx(brazos):
        seed_config()
        unit = _vacant(dana, brazos)
        moved = _move_in(dana, unit["id"], [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-18"}])
        head = _head(_asset_id(unit, "M-9101"))
    assert moved["event_reads"]["posted_reads"] == 1
    assert head.read_at.date() == date(2026, 8, 18)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10166 · DISCONNECT → MARK AS CUT
# ═══════════════════════════════════════════════════════════════════════════
def test_cut__a_closing_reading_with_its_date_posts_with_event_disconnect(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        account = _account_on(dana, unit["id"], name="Achebe, Ngozi")
        _scheduled_cut(dana, account["id"], monkeypatch)
        cut = disconnects.commit_cut(
            dana,
            account["id"],
            cut_on=date(2026, 8, 24),
            as_of=date(2026, 8, 24),
            final_reads=[{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-23"}],
        )
        read = _head(_asset_id(unit, "M-9101"))
    assert cut["event_reads"]["posted_reads"] == 1
    assert read.event_context == "disconnect"
    assert read.read_at.date() == date(2026, 8, 23)
    assert read.imported_by_id == dana.id


def test_cut__the_closing_reading_exists_before_the_cut_bill_is_raised(brazos, dana, monkeypatch):
    """The bill at the cut must be able to price the reading the clerk typed."""
    seen: list[bool] = []
    real = disconnects._raise_final_bill_at_the_cut
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        account = _account_on(dana, unit["id"], name="Achebe, Ngozi")
        _scheduled_cut(dana, account["id"], monkeypatch)

        def spy(*args, **kwargs):
            seen.append(_head(asset_id) is not None)
            return real(*args, **kwargs)

        monkeypatch.setattr(disconnects, "_raise_final_bill_at_the_cut", spy)
        disconnects.commit_cut(
            dana,
            account["id"],
            cut_on=date(2026, 8, 24),
            as_of=date(2026, 8, 24),
            final_reads=[{"meter_no": "M-9101", "value": "43566"}],
        )
    assert seen == [True]


def test_cut__a_future_closing_date_refuses_the_whole_cut(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        account = _account_on(dana, unit["id"], name="Achebe, Ngozi")
        case = _scheduled_cut(dana, account["id"], monkeypatch)
        with pytest.raises(errors.ValidationError) as caught:
            disconnects.commit_cut(
                dana,
                account["id"],
                cut_on=date(2026, 8, 24),
                as_of=date(2026, 8, 24),
                final_reads=[{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-30"}],
            )
        case.refresh_from_db()
        landed = _reads_on(_asset_id(unit, "M-9101"))
    assert caught.value.field_errors[0]["field"] == "final_reads[1].read_at"
    assert caught.value.field_errors[0]["message_key"] == "customers.event_reads.read_at_future"
    assert case.state == disconnects.STATE_SCHEDULED and case.cut_on is None
    assert landed == 0


def test_cut__the_record_serves_the_meters_to_read_with_unit_and_last_reading(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-12", value="43000")
        account = _account_on(dana, unit["id"], name="Achebe, Ngozi")
        case = _scheduled_cut(dana, account["id"], monkeypatch)
        meters = disconnect_record.closing_read_meters(case, customers_models.Account.objects.get(id=account["id"]))
    assert [m["asset_no"] for m in meters] == ["M-9101"]
    assert meters[0]["unit"] == "kWh"
    assert meters[0]["last_read"]["read_at"][:10] == "2026-08-12"


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10167 · MOVE RECORD → ENTER OPENING READ
# ═══════════════════════════════════════════════════════════════════════════
def _committed_move_in(dana, brazos):
    unit = _metered_unit(dana, brazos, label="Unit R")
    moved = customers_services.move_in_to_unit(
        dana,
        unit["id"],
        {
            "account_type": "residential",
            "opened_at": "2026-08-20",
            "contact": {"full_name": "Verma, Asha"},
            "customer": identity_fixtures.customer_block("Verma, Asha", account_type="residential"),
        },
    )
    return unit, moves.MoveRecord.objects.get(pk=moved["move_record_id"])


def test_opening_read__a_chosen_date_is_stored(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit, record = _committed_move_in(dana, brazos)
        answer = move_in_flow.enter_opening_reads(
            dana, record.move_no, [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-22"}]
        )
        head = _head(_asset_id(unit, "M-9101"))
    assert answer["posted_reads"] == 1
    assert head.event_context == "move_in"
    assert head.read_at.date() == date(2026, 8, 22)


def test_opening_read__a_future_date_is_refused_on_the_reads_field(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit, record = _committed_move_in(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            move_in_flow.enter_opening_reads(
                dana, record.move_no, [{"meter_no": "M-9101", "value": "43566", "read_at": "2026-08-26"}]
            )
        landed = _reads_on(_asset_id(unit, "M-9101"))
    assert caught.value.field_errors[0]["field"] == "reads[1].read_at"
    assert landed == 0
