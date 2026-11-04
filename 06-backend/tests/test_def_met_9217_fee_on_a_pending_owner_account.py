# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9217 — New Connection "Add fee" was refused on every build
#           before approval ("cannot be priced"): the owner's account is held
#           `pending_activation` after Create (CR-162-BRC10 Q1) and billing's
#           one-time door refuses a non-billable account (BR-CUS-055), while
#           CR-163-BRC10 item 2 adds fees "after submission, until approval".
# Rules:    BR-CUS-055 (billability is a class — kept for every other caller) ·
#           BR-MET-113 · CLAUDE.md hard rules 2, 4, 5, 7 · hard-won law 14 (the
#           money cases run on PostgreSQL).
# ───────────────────────────────────────────────────────
"""**A $30.00 inspection fee added the day after Create lands on the build's
own Pending owner account — master or regular — and NOTHING else moves.**

Worked figures: the apartment build's quote at Create is 2 × CONN $45.00 +
1 × INSPECT $30.00 = $120.00 on the master account; the fee added on
2026-10-03 is one more INSPECT = **$30.00**, a SECOND issued bill on the same
account (an issued bill is never edited, hard rule 4).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * a fee that went to SOME account — the invoice's `account_id` is compared
    with the build's own `owner_account_id`, and that account is asserted
    `pending_activation` first, so the case cannot pass on an Active account;
  * a flag that opened every non-billable account — a Disconnected account
    (also `non_billable`) is still refused WITH the flag;
  * a door that stopped refusing for everybody — the same Pending account is
    still refused WITHOUT the flag, which is every caller but the fee door.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import gather
from apps.billing import models as billing_models
from apps.billing import single
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import connection_fees as fees

from tests.isolation_helpers import requires_postgres
from tests.test_def_cus_9228_single_family_owner_pays import (
    _maria_builds,
    _owner_account,
)
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    _ctx,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam

pytestmark = pytest.mark.django_db

INSPECT_FEE = {
    "charge_code": "INSPECT",
    "quantity": "1",
    "basis": "per premise",
    "posting_date": "2026-10-03",
    "due_days": 30,
}


def _apartment_builds(clerk, tenant):
    """Two homes at a NEW apartment-complex address — the owner's MASTER
    account opens, held Pending (CR-162-BRC10 Q1)."""
    return _maria_builds(
        clerk,
        tenant,
        address="200 Cedar Row",
        labels=("Unit 1", "Unit 2"),
        premises={
            "id": None,
            "address": "200 Cedar Row",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "premise_type": "apartment_complex",
            "parcel_ref": None,
            "read_route": None,
            "services_available": ["battery", "solar"],
        },
    )


@requires_postgres
def test_a_fee_added_before_approval_goes_to_the_pending_master_account(cedar, clerk):
    built = _apartment_builds(clerk, cedar)
    account = _owner_account(cedar, built["id"])
    assert account.kind == "master"
    assert account.status.code == customers_services.PENDING_STATUS_CODE
    with _ctx(cedar):
        added = fees.add_connection_fee(clerk, built["id"], dict(INSPECT_FEE))
        invoice = billing_models.Invoice.objects.get(pk=added["invoice_id"])
        assert str(invoice.account_id) == str(account.pk)
        assert invoice.total == Decimal("30.0000")
        assert invoice.status == "issued"
    # The hold is untouched: billing the account did not activate it.
    assert _owner_account(cedar, built["id"]).status.code == customers_services.PENDING_STATUS_CODE


@requires_postgres
def test_without_the_flag_a_pending_account_is_still_refused(cedar, clerk):
    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    account = _owner_account(cedar, built["id"])
    assert account.status.code == customers_services.PENDING_STATUS_CODE
    with _ctx(cedar):
        with pytest.raises(gather.GatherProblem):
            single.billable_account(account.pk)
        scope = single.billable_account(account.pk, pending_new_connection_owner=True)
        assert scope.account_id == str(account.pk)


@requires_postgres
def test_the_flag_does_not_open_a_disconnected_account(cedar, clerk):
    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    account = _owner_account(cedar, built["id"])
    with _ctx(cedar):
        disconnected = customers_models.AccountStatus.objects.get(code="disconnected")
        assert disconnected.behavior_class == customers_services.CLASS_NON_BILLABLE
        customers_models.Account.objects.filter(pk=account.pk).update(status=disconnected)
        with pytest.raises(gather.GatherProblem):
            single.billable_account(account.pk, pending_new_connection_owner=True)
