# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9692 (CR-168-BRC10 round 8, lane FIX-8A) — a transfer
#           record read *Committed by: Not recorded* although a clerk committed
#           it in the wizard (TRF-26-0001, lane WALK-B).
# Rules:    BR-CUS-1030 · CLAUDE.md hard rule 4 (the audit log is pruned, so it
#           is never read as the committer's record — `OQ-1340`)
# ───────────────────────────────────────────────────────
"""A sale keeps who committed it on its OWN row — `transfers.committed_by`,
written at the commit — the way a move keeps `move_records.performed_by`. The
record reads the name and the moment; a sale committed before the column
existed still says *not stored*, and never borrows the audit log."""

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


def _fact(transfer_id):
    row = transfers.Transfer.objects.get(id=transfer_id)
    return transfer_reads.record_detail(row.transfer_no or str(row.id))["what_happened"][
        "committed_by"
    ]


def test_9692_a_completed_sale_names_who_committed_it_and_when(brazos, marcus):
    from apps.identity.models import User

    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell(marcus, account)
        fact = _fact(row["id"])
        name = User.objects.get(pk=marcus.id).full_name
    assert fact["unavailable"] is None, fact
    assert fact["value"]["name"] == name
    assert fact["value"]["at"], "the moment of the commit is on the row"


def test_9692_a_sale_committed_before_the_column_still_says_not_stored(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell(marcus, account)
        transfers.Transfer.objects.filter(id=row["id"]).update(committed_by_id=None)
        fact = _fact(row["id"])
    assert fact["value"] is None
    assert fact["unavailable"]["code"] == transfer_reads.COMMITTED_BY_NOT_STORED["code"]
