# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9756 — Search customer ID shows Rosa owing $0.00 when the
#           ledger says she owes $84.20 ($50.00 + $34.20): her accounts were
#           opened at the counter / by a move-in, so their links carry no
#           match tier, and the total counted only `strong`/`probable` links.
# CR:       CR-171-BRC10 P4.01 (Rosa Delgado, AC-2026-00054 + AC-2026-00055)
# ───────────────────────────────────────────────────────
"""Search customer ID's total foots to the rows drawn under it.

The screen draws every linked account with its ledger figure; the total sat
under them at $0.00 for a customer whose accounts were opened by the product
itself. The total is now the sum the ledger owes over EVERY account of that
customer; `unconfident_outstanding` still states how much of it rides on a
weak or untiered link. `customer_statement` (the C16 report) is NOT changed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.test_cr171_p109_search_customer_id import (
    DOB,
    NAME,
    SSN,
    _link,
    _person,
    _search,
)
from tests.ledger_le_fixtures import make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_untiered_links_count_in_the_total_and_are_still_stated(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {}, service="electric")
        post_le1_month(brazos, accounts)
        rosa = _person(brazos)
        _link(brazos, rosa, accounts["ACC-1042"], tier=None)
        _link(brazos, rosa, accounts["ACC-1051"], tier=None)

    search = _search(dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN})
    found = search["customers"][0]["accounts"]
    owed = sum((Decimal(row["outstanding"]) for row in found["rows"]), Decimal("0"))
    assert owed > 0, "the fixture must owe something or this proves nothing"
    assert Decimal(found["outstanding_total"]) == owed
    assert Decimal(found["unconfident_outstanding"]) == owed
