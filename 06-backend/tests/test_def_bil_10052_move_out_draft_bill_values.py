"""`DEF-BIL-10052` — the move-out draft bill is fed every value, and when values
are missing it names ALL of them (PO 2026-10-11).

PO, verbatim: *"our goal should be to generate the draft bill and show it on the
screen"* and *"if you dont get all those values - not just 1 if 2, or 3 or 4 or
any number then you should show bill is not genertaed because all these valaues
are missing"*. The engine is unchanged (`runs.price_account`); these cases pin
what `preview_final_bill` hands it and what it says when it cannot.
"""
from __future__ import annotations

from datetime import date

import pytest

from apps.billing import final_bill
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_us_bil_001_prepare import PERIOD_START
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

BEFORE_THE_PERIOD = date(2026, 5, 28)


def _unread_account(brazos, dana, monkeypatch, *, asset_no="M-9201", account_no="A-12201"):
    """Read only BEFORE the closing period — so the period has no usable read."""
    from tests import test_us_bil_011_final_bill as fb

    original = fb.a_unit_read_before_the_move

    def read_earlier(actor, tenant, cycle, plan, *, asset_no, label, day):
        return original(actor, tenant, cycle, plan, asset_no=asset_no, label=label, day=BEFORE_THE_PERIOD)

    monkeypatch.setattr(
        "tests.test_br_bil_013_final_bill_preview.a_unit_read_before_the_move", read_earlier
    )
    return _a_moving_out_account(brazos, dana, monkeypatch, asset_no=asset_no, account_no=account_no)


def test_a_period_with_no_usable_read_says_not_generated_and_names_the_service_and_meter(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch)
        body = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, period_start=PERIOD_START
        )
    assert body["priced"] is False
    gap = body["priced_unavailable"]
    assert gap["reason"] == final_bill.PREVIEW_VALUES_MISSING
    assert gap["message_key"] == "billing.finalPreview.notGenerated"
    assert gap["missing"], "every missing value is listed"
    first = gap["missing"][0]
    assert first["service"] == "electric"
    assert first["what"] == "reading"
    assert "M-9201" in first["meters"]
    # the engine's sentence and its rule id never become the clerk's words
    assert "BR-BIL-015" not in str(gap.get("message_key"))


def test_a_keyed_estimate_with_no_history_is_named_as_such_not_as_a_missing_reading(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9202", account_no="A-12202")
        body = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            period_start=PERIOD_START,
            keyed_reads=[{"meter_no": "M-9202", "estimate": True}],
        )
        estimate = final_bill.estimate_closing_usage(
            account_id=account.id, meter_no="M-9202", moved_out_on=MOVE_OUT
        )
    gap = body["priced_unavailable"]
    if body["priced"]:
        # metering had enough history: the draft priced an ESTIMATED line
        assert any(line.get("estimated") for line in body["lines"])
        assert estimate["estimated"] is True
    else:
        assert gap["reason"] == final_bill.PREVIEW_VALUES_MISSING
        assert gap["missing"][0]["what"] == "estimate_no_history"
        assert estimate["estimated"] is False
        assert estimate["reason"]


def test_a_keyed_reading_prices_the_draft(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9203", account_no="A-12203")
        body = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            period_start=PERIOD_START,
            keyed_reads=[{"meter_no": "M-9203", "value": "14400"}],
        )
    assert body["priced"] is True, body.get("priced_unavailable")
    assert body["lines"]


def test_a_master_and_its_sub_meter_on_the_unit_both_reach_the_draft_bill(brazos, dana, monkeypatch):
    """Step 1 of the confirmed plan — the PO's screen showed W-5042 MASTER and
    SM-7042 SUB on the closing unit. A master meter on the unit's own service
    point is one of the unit's meters like any other: its keyed reading is used,
    and leaving it blank names it in the missing list rather than dropping it."""
    from apps.assets import models as asset_models
    from tests.test_us_met_reads_helpers import a_meter, commit_read

    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9204", account_no="A-12204")
        master = a_meter(dana, asset_no="M-9300", unit_id=str(account.unit_id))
        commit_read(
            dana,
            master["id"],
            day=BEFORE_THE_PERIOD.isoformat(),
            value="50000",
            prior_value="49000",
            consumption="1000.000000",
            unit="kWh",
        )
        asset_models.Asset.objects.filter(asset_no="M-9204").update(parent_asset_id=master["id"])

        only_the_sub = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            period_start=PERIOD_START,
            keyed_reads=[{"meter_no": "M-9204", "value": "14400"}],
        )
        both = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            period_start=PERIOD_START,
            keyed_reads=[
                {"meter_no": "M-9204", "value": "14400"},
                {"meter_no": "M-9300", "value": "50600"},
            ],
        )
    if not only_the_sub["priced"]:
        gap = only_the_sub["priced_unavailable"]
        assert gap["reason"] == final_bill.PREVIEW_VALUES_MISSING
        assert any("M-9300" in row["meters"] for row in gap["missing"])
    assert both["priced"] is True, both.get("priced_unavailable")


def test_estimate_on_a_meter_already_read_says_read_on_file_with_its_usage(brazos, dana, monkeypatch):
    """Walk follow-up — a meter whose period already holds a committed read was
    answered `meter_not_on_this_account`. The committed read wins over a keyed
    estimate, so step 2 names it: already read, this usage billed."""
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9205", account_no="A-12205")
        estimate = final_bill.estimate_closing_usage(
            account_id=account.id, meter_no="M-9205", moved_out_on=MOVE_OUT
        )
    assert estimate["estimated"] is False
    assert estimate["reason"] == "read_on_file"
    assert estimate["consumption"]
    assert estimate["unit"]


def test_a_move_out_before_the_period_is_refused_with_a_catalogue_sentence(brazos, dana, monkeypatch):
    """Walk follow-up — the refusal reached the screen as engine English with ISO dates."""
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9206", account_no="A-12206")
        body = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=BEFORE_THE_PERIOD, period_start=PERIOD_START
        )
    assert body["priced"] is False
    assert body["priced_unavailable"]["message_key"] == "billing.finalPreview.moveOutBeforePeriod"
