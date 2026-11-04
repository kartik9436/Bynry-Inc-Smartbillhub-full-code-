# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-6429` (2026-09-24) — a completed sale's record page read
#           *"Committed by: Not committed yet"*.
# Rules:    BR-CUS-1030 · CLAUDE.md hard rule 4 (the audit log is pruned, so it
#           is never read as the committer's record — `OQ-1340`)
# Screen:   07-frontend/src/features/customers/TransferRecordPage.tsx
# ───────────────────────────────────────────────────────
"""**The record says WHICH absence it is: not committed, or committed and not kept.**

`transfers` has no column for who committed a sale, so `committed_by` is always
an absence. It used to be the SAME absence on every record, and the screen drew
one label for it — so a done sale read like a draft. The read now serves
`transfer_not_committed` until the sale commits and `committed_by_not_stored`
after, and the screen's label follows the record's state.
"""

import pytest

from apps.customers import transfer_reads, transfers

from tests.test_cr058_w4_transfer_reassigns import _sell, _sold_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _committed_by(transfer_id):
    row = transfers.Transfer.objects.get(id=transfer_id)
    detail = transfer_reads.record_detail(row.transfer_no or str(row.id))
    return detail["state"], detail["what_happened"]["committed_by"]


def test_an_unfinished_sale_says_it_is_not_committed(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        state, fact = _committed_by(started["id"])
        assert state == "in_flight"
        assert fact["value"] is None
        assert fact["unavailable"]["code"] == transfer_reads.NOT_COMMITTED_YET["code"]


def test_a_completed_sale_says_the_committer_is_not_kept_never_not_committed(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell(marcus, account)
        # `DEF-CUS-9692` (2.520.2): the committer is on the row now, so the
        # absence case is a sale committed BEFORE the column — simulated here.
        transfers.Transfer.objects.filter(id=row["id"]).update(committed_by_id=None)
        state, fact = _committed_by(row["id"])
        assert state == "completed"
        assert fact["value"] is None, "no column holds the committer, and the log is not one"
        assert fact["unavailable"]["code"] == transfer_reads.COMMITTED_BY_NOT_STORED["code"], (
            "a DONE sale was committed — its absence is 'not stored', never 'not committed'"
        )
