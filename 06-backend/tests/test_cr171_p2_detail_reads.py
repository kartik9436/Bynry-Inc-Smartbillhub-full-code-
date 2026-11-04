"""CR-171-BRC10 P2.10 / P2.11 (lane MVI-DETAIL) — the two reads the details
view's Account and Billing tabs draw, added to `GET /moves/{ref}`:

* `fee_lines` — the lines Complete wrote on the move record (image 26's *Fees*
  table), in their own order, each amount the stored 4-place figure (the screen
  displays 2, hard rule 2). The worked figures are J4's: DEPOSIT $150.00 +
  CONN $25.00 + RUSH $40.00 = $215.00.
* `co_owners` — the account's co-owners (image 25), with NO identifier: no SSN,
  no licence, not even their last four (BR-CUS-092 keeps those off a list).

Both are reads only: nothing here writes.
"""

import pytest

from apps.customers import move_record_reads
from apps.customers.moves import MoveRecord
from apps.customers import services as customers_services
from tests.test_cr094_wh_deposit import _payload
from tests.test_cr171_p1_12_move_in_fees import _deferred, _move_in, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CO_OWNER = {
    "full_name": "G, Riya",
    "relationship": "Spouse",
    "phone": "732-555-0144",
    "email": "riya@example.test",
    "contact_by": "text",
    "ssn": "123-45-6789",
    "responsible_for_bills": True,
}


def _committed(actor, tenant, **extra):
    _unit, _plan, outgoing = _world(actor, tenant)
    result = _move_in(actor, outgoing, **extra)
    record = MoveRecord.objects.get(account_id=result["id"], kind="move_in")
    return record


def test_p2_11__the_record_serves_its_fee_lines_in_order_with_their_figures(brazos, dana):
    with tenant_ctx(brazos):
        record = _committed(dana, brazos)
        served = move_record_reads.record_detail(record.move_no)

    assert [(r["seq"], r["kind"], r["source"], r["code"], r["amount"]) for r in served["fee_lines"]] == [
        (1, "deposit", "plan", "DEPOSIT", "150.0000"),
        (2, "fee", "plan", "CONN", "25.0000"),
        (3, "fee", "charge_code", "RUSH", "40.0000"),
    ]
    assert served["tiles"]["fees"]["total"] == "215.0000"
    assert {r["currency"] for r in served["fee_lines"]} == {"USD"}


def test_p2_10__the_record_serves_its_co_owners_and_never_an_identifier(brazos, dana):
    with tenant_ctx(brazos):
        record = _committed(dana, brazos, co_owners=[CO_OWNER])
        served = move_record_reads.record_detail(record.move_no)

    # `DEF-CUS-9770` — the row carries `id`, the handle the Account tab's *Photo
    # ID* upload addresses (lane MVI-WIZ-CUST, P2.24); it is never shown and it
    # is not an identifier of the PERSON, which is what this test refuses.
    rows = served["co_owners"]
    assert len(rows) == 1 and isinstance(rows[0].pop("id"), str)
    assert rows == [
        {
            "kind": "co_owner",
            "full_name": "G, Riya",
            "relationship": "Spouse",
            "title": None,
            "phone": "732-555-0144",
            "email": "riya@example.test",
            "contact_by": "text",
            "responsible_for_bills": True,
            "photo_id": False,
        }
    ]
    flat = repr(served["co_owners"])
    assert "6789" not in flat and "ssn" not in flat


def test_p2_10__a_move_in_with_neither_serves_two_empty_lists(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _plan, outgoing = _world(dana, brazos)
        result = customers_services.move_in(dana, outgoing["id"], _payload(deposit=_deferred()))
        record = MoveRecord.objects.get(account_id=result["id"], kind="move_in")
        served = move_record_reads.record_detail(record.move_no)

    assert served["fee_lines"] == [] and served["co_owners"] == []
