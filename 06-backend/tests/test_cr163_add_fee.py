# ── Trace ──────────────────────────────────────────────
# Change:   CR-163-BRC10 item 2 (lane NC-B) — a fee added to a New Connection
#           after submission, as a NEW issued bill.
# Rules:    hard rule 4 (never edit an issued line) · hard rule 2 (billing
#           multiplies, nothing else) · hard rule 7 (audited) · BR-BIL-005
#           (one fee bill per account per day — OQ-BIL-12377, open) ·
#           BR-BIL-020 (no typed figure on a priced code) · BR-TEN-043 (the
#           clerk's posting date, never a clock)
# ───────────────────────────────────────────────────────
"""Add a fee after submission — the refusals (any vendor) and the bill (PG).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A door that answered an invoice
number and wrote no bill would pass any case reading the RESPONSE, so the PG
case reads the bill back through the BUILD RECORD — two bills, the added line
on the second, the totals summed by the server — and through
`connection_fee_bills`. And a door that edited the quote would pass a total
check, so the quote's own total is asserted UNCHANGED.
"""

from decimal import Decimal

import pytest

from apps.metering import connection_fees as fees
from apps.metering import connection_record as record
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _build_with_an_owner_account(actor):
    """`test_br_met_1187`'s builder with a SECOND unit — a master account now
    needs two (`customers.account.master_needs_two_units`), and a build with
    one unit could not open its payer."""
    from tests import test_br_met_1187_books_entry_at_creation as base

    premises = base.make_premises(actor)
    unit = base.make_unit(actor, premises["id"])
    base.make_unit(actor, premises["id"], label="Unit 2")
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    account = base.customers_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "contact": {"full_name": base.OWNER_NAME},
            "customer": base.identity_fixtures.customer_block(base.OWNER_NAME, account_type="commercial"),
        },
    )
    w6.tag_charges_to_account(actor, connection.id, account["id"])
    connection.refresh_from_db()
    return connection, unit, account


def _submitted_build(actor):
    """A committed build, without the billing half — enough for the refusals,
    which all fire before billing is asked anything."""
    connection, _unit, _account = _build_with_an_owner_account(actor)
    work_tables.Connection.objects.filter(pk=connection.id).update(state=work_tables.REQUESTED)
    connection.refresh_from_db()
    return connection


GOOD = {"charge_code": "INSPECT", "quantity": "1", "basis": "per premise",
        "posting_date": "2026-09-22", "due_days": 30}


@pytest.mark.parametrize(
    "change, key",
    [
        ({"charge_code": ""}, "metering.connection.feeCodeRequired"),
        # A recurring code and a penalty are not one-time fees (item 2).
        ({"charge_code": "PAPER"}, "metering.connection.feeCodeRequired"),
        ({"charge_code": "NSF"}, "metering.connection.feeCodeRequired"),
        ({"due_days": 45}, "metering.connection.feeTermsRequired"),
        ({"posting_date": ""}, "metering.connection.feeDateRequired"),
        ({"quantity": "0"}, "metering.connection.feeQuantityRequired"),
        ({"basis": "per flat"}, "metering.connection.feeBasisRequired"),
        ({"amount": "99.00"}, "metering.connection.feeAmountNotTyped"),
    ],
)
def test_a_fee_is_refused_by_name_before_billing_is_asked(dana, brazos, change, key):
    with tenant_ctx(brazos):
        connection = _submitted_build(dana)
        with pytest.raises(errors.ValidationError) as refused:
            fees.add_connection_fee(dana, connection.id, {**GOOD, **change})
        assert refused.value.message_key == key
        assert not fees.ConnectionFeeBill.objects.filter(connection_id=connection.id).exists()


def test_a_fee_waits_for_submission_and_stops_at_approval(dana, brazos):
    """*"Add fees after submission, until approval"* — a draft and an
    activated build both refuse, by name."""
    with tenant_ctx(brazos):
        connection = _submitted_build(dana)
        for state in (work_tables.DRAFT, work_tables.ACTIVATED, work_tables.PARTLY_ACTIVATED, work_tables.CANCELLED):
            work_tables.Connection.objects.filter(pk=connection.id).update(state=state)
            with pytest.raises(errors.BizError) as refused:
                fees.add_connection_fee(dana, connection.id, GOOD)
            assert refused.value.message_key == "metering.connection.feeNotNow"


@requires_postgres
def test_an_added_fee_is_a_new_issued_bill_and_the_quote_is_untouched(dana, brazos, audit_rows):
    """The whole money path on real PostgreSQL: the build commits with its
    $800.00 quote on 2026-09-21; a $30.00 inspection is added on 2026-09-22.

    RED PROVED: before `CR-163-BRC10` there was no door — `AttributeError:
    module 'apps.metering' has no attribute 'connection_fees'`.
    """
    from tests.test_br_met_1187_books_entry_at_creation import _commit

    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        _commit(dana, connection)
        connection.refresh_from_db()
        quote_before = record.build_record(connection.id)["money"]
        assert quote_before["quoted"]["display"] == "800.00"

        added = fees.add_connection_fee(dana, connection.id, GOOD)
        money = record.build_record(connection.id)["money"]

        # A SECOND bill, with its own number; the first is untouched.
        assert added["invoice_no"] and added["invoice_no"] != quote_before["invoice_no"]
        assert [bill["added"] for bill in money["bills"]] == [False, True]
        assert money["bills"][0]["total"] == quote_before["bills"][0]["total"]
        assert money["bills"][1]["total"]["display"] == "30.00"
        # Charged is the SERVER's sum over both bills.
        assert money["quoted"]["display"] == "830.00"
        added_lines = [line for line in money["lines"] if line["invoice_no"] == added["invoice_no"]]
        assert [line["each"]["display"] for line in added_lines] == ["30.00"]
        assert fees.ConnectionFeeBill.objects.filter(connection_id=connection.id).count() == 1

        # Audited as a money action, by the person who pressed.
        assert [row["action"] for row in audit_rows if row["action"] == "connection.fee_added"]

        # ⚠ OQ-BIL-12377 — a SECOND fee on the same day for the same payer is
        # refused by billing's own idempotency key, by name, and writes nothing.
        with pytest.raises(errors.BizError) as refused:
            fees.add_connection_fee(dana, connection.id, GOOD)
        assert refused.value.message_key == "metering.connection.feeSameDay"
        assert fees.ConnectionFeeBill.objects.filter(connection_id=connection.id).count() == 1
        # The transaction is still usable after the refusal (law 14).
        assert record.build_record(connection.id)["money"]["quoted"]["display"] == "830.00"
    assert Decimal(added["total"]) == Decimal("30")
