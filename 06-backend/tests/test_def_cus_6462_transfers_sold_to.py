# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-6462` (2026-09-24) — the Transfers list's `Sold to` column
#           named the SELLER on every completed sale.
# Rules:    BR-CUS-1030 · migration 0060 (`transfers.customer_id` is the SELLER
#           for good; the buyer is `buyer_customer_id`)
# Screen:   07-frontend/src/features/customers/TransfersTab.tsx (`Sold to`)
# ───────────────────────────────────────────────────────
"""**The list serves who BOUGHT each sale, not only who sold it.**

`list_row` served `customer` — `transfers.customer`, the seller since
2026-09-20 — and nothing else, so the `Sold to` column drew the seller. It now
serves `buyer` / `buyer_no` from `buyer_customer_id`, batched once per page.
Worked, as walked on the sample utility: A-11512 sold by *Hollis, Marcus* to
*Aiden, Tim*, then by *Aiden, Tim* to *Reyes, Carla* — the list printed
*Hollis, Marcus* and *Aiden, Tim* under `Sold to`.
"""

from datetime import date

import pytest

from apps.customers import transfer_reads, transfers

from tests.test_cr058_w4_transfer_reassigns import BUYER, SELLER_NAME, _sell, _sold_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SECOND_BUYER = {
    "display_name": "Reyes, Carla",
    "kind": "person",
    "identity": {"phone": "+1-555-0199"},
}
TODAY = date(2026, 9, 24)


def _rows_by_id():
    return {row["id"]: row for row in transfer_reads.list_transfers(as_of=TODAY)["rows"]}


def test_each_sale_on_the_list_names_its_own_buyer_and_seller(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        first = _sell(marcus, account, buyer=BUYER, sold_on="2026-09-01")
        second = _sell(marcus, account, buyer=SECOND_BUYER, sold_on="2026-09-20")
        rows = _rows_by_id()

        one, two = rows[first["id"]], rows[second["id"]]
        assert (one["customer"], one["buyer"]) == (SELLER_NAME, BUYER["display_name"])
        assert (two["customer"], two["buyer"]) == (BUYER["display_name"], "Reyes, Carla")
        assert one["buyer_no"] and one["buyer_no"].startswith("C-")
        assert two["buyer_no"] != one["buyer_no"]
        assert one["buyer_no"] == two["customer_no"], "the first buyer is the second seller"


def test_an_open_sale_has_no_buyer_on_the_list(brazos, marcus):
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        row = _rows_by_id()[started["id"]]
        assert row["buyer"] is None and row["buyer_no"] is None
        assert row["customer"] == SELLER_NAME


def test_a_sale_committed_before_0060_reads_its_buyer_from_customer(brazos, marcus):
    """Before migration 0060 the commit OVERWROTE `customer_id` with the buyer
    and wrote no `buyer_customer_id`, so on those rows `customer` IS the buyer."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        sold = _sell(marcus, account, buyer=BUYER)
        row = transfers.Transfer.objects.get(id=sold["id"])
        transfers.Transfer.objects.filter(id=row.id).update(
            customer_id=row.buyer_customer_id, buyer_customer_id=None
        )
        listed = _rows_by_id()[sold["id"]]
        assert listed["buyer"] == BUYER["display_name"]
