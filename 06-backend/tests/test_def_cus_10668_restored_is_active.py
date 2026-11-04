# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10668 — after *Confirm restored* an account the ladder had
#           marked before the cut went back to `Marked disconnect`, while S148
#           step 2 promised *"The mark on the account clears"* (walk: A-11340,
#           marked → cut → reconnected owing $8,315.00).
# Ruling:   PO 2026-10-29, verbatim *"2A"* — decision log *"Five open questions
#           answered in one message (PO)"* item 2: a restored account returns to
#           Active; if they still don't pay, the ladder starts again. Supersedes
#           CR-052 W0's *"the status held before the cut"*.
# Rules:    BR-CUS-107 (amended 2026-10-29) · BR-CUS-055 (Active is the seeded
#           `active` row, chosen by CODE — `Marked disconnect` shares its
#           behaviour class) · BR-CUS-1097 · hard rule 1.
# ───────────────────────────────────────────────────────
"""The engine's answer, against the screen's own consequence row.

RED FIRST (law 7): before the fix `restore_service` put back
`status_before_cut`, so this account read `marked_disconnect` after the very
screen that listed `the_mark_clears` had been confirmed.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): a fixture whose
account was `active` before the cut — then "the status before the cut" and
"Active" are the same answer and the old code passes. So the case records
`marked_disconnect` as the status before the cut, which is A-11340's shape, and
the account is read back from its ROW, not from the payload.
"""

from decimal import Decimal as D

import pytest

from apps.customers import disconnects, reconnect_read
from apps.customers import models as customers_models
from apps.customers import services as customer_services

from tests.test_def_cus_10657_reconnect_request import (  # noqa: F401 — fixture
    REQUESTED_ON,
    RESTORED_ON,
    _case_no,
    _post,
    raised,
)
from tests.test_def_not_10649_cut_restore_notices import (  # noqa: F401 — autouse fixture
    _cut,
    _fee_and_reads_at_the_boundary,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

#: A-11340's figure at restoration — still owing, and restored anyway (BR-CUS-1097).
STILL_OWED = D("8315.00")


def test_confirm_restored_clears_the_mark_and_the_account_reads_active(
    brazos, marcus, monkeypatch, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        # A-11340's shape: the ladder had MARKED the account before the cut.
        disconnects.DisconnectCase.objects.filter(account_id=account["id"]).update(
            status_before_cut="marked_disconnect"
        )
        _owes(monkeypatch, STILL_OWED)
        ref = _case_no(account["id"])
        requested = _post(
            reconnect_read.reconnect_request, brazos, marcus, ref, {"on_date": REQUESTED_ON}
        )
        assert requested.status_code == 200, requested.data

        # What S148 step 2 PROMISES, read from the screen's own payload.
        # (`api_call` leaves the tenant context it opened, so re-enter it.)
        with tenant_ctx(brazos):
            detail = reconnect_read.reconnect_detail(ref)
        promised = {row["code"] for row in detail["consequences"]}
        assert "the_mark_clears" in promised

        done = _post(
            reconnect_read.reconnect_complete, brazos, marcus, ref, {"on_date": RESTORED_ON}
        )
        assert done.status_code == 200, done.data
        with tenant_ctx(brazos):
            row = customers_models.Account.objects.select_related("status").get(
                id=account["id"]
            )

    # The engine keeps the promise: the mark clears, the account is Active.
    assert row.status.code == "active"
    assert row.status.code != "marked_disconnect"
    assert row.status.behavior_class == customer_services.CLASS_BILLABLE
    assert done.data["account_status_restored_to"] == "active"
    assert "account_status_restore" not in done.data
    # Restored OWING — the money is recorded, never a gate.
    assert done.data["owed_at_restoration"]["stored"] == "8315.0000"
