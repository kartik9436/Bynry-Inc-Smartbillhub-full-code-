# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10129 — move-out step 2 (ACC-06): master meter M-MASTER-01,
#           never read, showed "Not enough history to estimate." AND "Already
#           read: 22 kgal billed." in one row (PO screenshot 2026-10-14;
#           decision log "G1–G4 APPROVED" item 4).
# Rules:    B14 rule 33 (one fact, said once) · BR-MET-026 (an estimate comes
#           from the register's own history)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""`final_bill.estimate_closing_usage` says *"already read"* only of a reading
taken on THE METER ASKED ABOUT.

A billing reading is one row per SERVICE POINT. Matched by service, the point's
committed read was claimed for every meter on that point — a master and a
sub-meter that had never been read among them.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a fix that simply
stopped answering `read_on_file` would pass the master and sub cases, so the
read meter on the SAME point must still answer `read_on_file` with its usage.
"""

from __future__ import annotations

import pytest

from apps.assets import models as asset_models
from apps.billing import final_bill
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter

pytestmark = pytest.mark.django_db


def test_a_never_read_master_and_sub_on_a_read_point_are_not_called_already_read(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9291", account_no="A-12291"
        )
        master = a_meter(dana, asset_no="M-9292", unit_id=str(account.unit_id))
        sub = a_meter(dana, asset_no="M-9293", unit_id=str(account.unit_id))
        asset_models.Asset.objects.filter(pk=sub["id"]).update(parent_asset_id=master["id"])

        read = final_bill.estimate_closing_usage(
            account_id=account.id, meter_no="M-9291", moved_out_on=MOVE_OUT
        )
        never_read_master = final_bill.estimate_closing_usage(
            account_id=account.id, meter_no="M-9292", moved_out_on=MOVE_OUT
        )
        never_read_sub = final_bill.estimate_closing_usage(
            account_id=account.id, meter_no="M-9293", moved_out_on=MOVE_OUT
        )

    # The meter that WAS read keeps its answer, with its usage.
    assert read["reason"] == "read_on_file"
    assert read["consumption"] and read["unit"]
    # Neither neighbour on the same point borrows it.
    assert never_read_master == {"estimated": False, "reason": "no_history"}
    assert never_read_sub == {"estimated": False, "reason": "no_history"}
