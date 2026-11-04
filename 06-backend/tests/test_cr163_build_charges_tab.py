# ── Trace ──────────────────────────────────────────────
# Change:   CR-163-BRC10 (lane NC-B) — the New Connection detail's Charges tab:
#           items 18 (Each / Amount), 20 (each payment), 21 (the payer's id),
#           22 (the bill's id) of the PO's Table 2, decision log 2026-10-02
#           (`56eb54ba9`).
# Rules:    CLAUDE.md hard rule 2 (stored 4, displayed 2, ONE rounding — the
#           server's) · hard rule 6 (a payment's one idempotency key) · B14
#           rule 31 (an id travels for an address, the NUMBER is the value)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The build record's money block, as the Charges tab reads it.

Two halves: the record's SHAPE against stubbed neighbours (any vendor), and the
whole path on real PostgreSQL — a build committed with a cheque taken at the
counter, read back through payments' own new read.
"""

from decimal import Decimal

import pytest

from apps.metering import connection_record as record
from apps.work import connection_models as work_tables
from tests.test_cr126_build_record import _build
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

BILL_ID = "0199a1d2-0000-7000-8000-0000000c0163"
ACCOUNT_ID = "0199a1d2-0000-7000-8000-0000000a0163"


def _stub_bill(monkeypatch):
    monkeypatch.setattr(
        record.seams,
        "quote_bill",
        lambda invoice_id: {
            "id": BILL_ID,
            "invoice_no": "BL-2610-000101",
            "account_id": ACCOUNT_ID,
            "account_no": "AC-2026-00061",
            "currency": "USD",
            "total": Decimal("90.0000"),
            "lines": [
                {
                    "charge_code": "CONN",
                    "description": "Connection fee",
                    "quantity": "2.000000",
                    "unit_price": "45.0000",
                    "amount": "90.0000",
                }
            ],
        },
    )
    monkeypatch.setattr(record.seams, "settled_against_bills", lambda ids: {})


def test_each_line_carries_the_servers_each_and_amount(dana, brazos, monkeypatch):
    """Item 18: *"Each/Amount show '— Priced on the bill' while $90 was charged"*.

    The figures are the server's pairs — stored to 4, displayed to 2, rounded
    once by `_pair` — so the screen never multiplies or rounds.

    RED PROVED: before this change the line carried no `each` / `line_total`
    and `KeyError: 'each'` was raised here.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana, no="CON-26-0163")
        work_tables.Connection.objects.filter(pk=connection.id).update(quote_invoice_id=BILL_ID)
        _stub_bill(monkeypatch)
        monkeypatch.setattr(record.seams, "payments_for_bills", lambda ids, **kw: [])
        money = record.build_record(connection.id)["money"]

    line = money["lines"][0]
    assert line["each"] == {"stored": "45.0000", "display": "45.00"}
    assert line["line_total"] == {"stored": "90.0000", "display": "90.00"}
    assert line["invoice_no"] == "BL-2610-000101"
    # Items 21 and 22 — the ids an ADDRESS is built from, never shown.
    assert money["invoice_id"] == BILL_ID
    assert money["billed_to_id"] == ACCOUNT_ID
    assert money["bills"] == [
        {
            "invoice_no": "BL-2610-000101",
            "invoice_id": BILL_ID,
            "total": {"stored": "90.0000", "display": "90.00"},
            "added": False,
        }
    ]


def test_each_payment_is_a_row_and_the_tender_absence_is_gone(dana, brazos, monkeypatch):
    """Item 20: *"Paid so far: table of each payment — date, method (e.g. Cheque
    #4471), type, amount, receipt no."*

    The record asks payments with the build's OWN idempotency reference, so a
    cheque still `processing` (met no bill) is listed too.

    RED PROVED: before this change `money` had no `payments` key and the
    tender absence was stated on every build.
    """
    asked: dict = {}

    def fake(ids, *, entry_reference):
        asked["ids"] = list(ids)
        asked["ref"] = entry_reference
        return [
            {
                "id": "p1",
                "payment_no": "PY-261002-0084",
                "posted_at": "2026-10-02T00:00:00+00:00",
                "method_code": "check",
                "method_name": "Check",
                "confirmation": "4471",
                "type": "payment",
                "purpose": "bill",
                "status": "processing",
                "amount": "90.000000",
                "applied": False,
                "currency": "USD",
            }
        ]

    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana, no="CON-26-0164")
        work_tables.Connection.objects.filter(pk=connection.id).update(quote_invoice_id=BILL_ID)
        _stub_bill(monkeypatch)
        monkeypatch.setattr(record.seams, "payments_for_bills", fake)
        money = record.build_record(connection.id)["money"]

    assert asked["ids"] == [BILL_ID] or [str(one) for one in asked["ids"]] == [BILL_ID]
    assert asked["ref"] == f"new-connect:{connection.id}"
    row = money["payments"][0]
    assert row["payment_no"] == "PY-261002-0084"
    assert row["confirmation"] == "4471"
    assert row["amount"] == {"stored": "90.0000", "display": "90.00"}
    assert record.ABSENCE_TENDER_NOT_PUBLISHED not in {e["code"] for e in money["unavailable"]}


def test_payments_unpublished_is_null_and_says_so(dana, brazos, monkeypatch):
    """`None` from the seam is *could not ask*, never *nothing paid*."""
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana, no="CON-26-0165")
        work_tables.Connection.objects.filter(pk=connection.id).update(quote_invoice_id=BILL_ID)
        _stub_bill(monkeypatch)
        monkeypatch.setattr(record.seams, "payments_for_bills", lambda ids, **kw: None)
        money = record.build_record(connection.id)["money"]

    assert money["payments"] is None
    assert record.ABSENCE_TENDER_NOT_PUBLISHED in {e["code"] for e in money["unavailable"]}


# ════════════════════════════════════════════════════════════════════════════
# THE WHOLE PATH, ON REAL POSTGRESQL
# ════════════════════════════════════════════════════════════════════════════
from tests.isolation_helpers import requires_postgres  # noqa: E402


@requires_postgres
def test_a_committed_build_lists_its_payment_from_payments_own_rows(dana, brazos):
    """A build committed with $500.00 taken by ACH and NOT cleared: payments
    keeps it `processing` and allocates nothing (`BR-PAY-021`), and the record
    still lists it — by the build's own idempotency key — with its reference.
    """
    from tests.test_br_met_1187_books_entry_at_creation import POSTING_DATE, _commit
    from tests.test_cr163_add_fee import _build_with_an_owner_account

    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        _commit(
            dana,
            connection,
            payment_method="ach",
            payment_amount="500.0000",
            payment_date=POSTING_DATE,
            payment_reference="TRN-0163",
        )
        money = record.build_record(connection.id)["money"]

    assert money["payments"] is not None
    rows = [row for row in money["payments"] if row["confirmation"] == "TRN-0163"]
    assert len(rows) == 1, money["payments"]
    row = rows[0]
    assert row["amount"]["display"] == "500.00"
    assert row["applied"] is False
    assert row["status"] == "processing"
    assert row["payment_no"]
    # The line figures are the bill's own: 6 × $45.00 is the first line.
    first = money["lines"][0]
    assert first["each"]["display"] == "45.00"
    assert first["line_total"]["display"] == "270.00"
