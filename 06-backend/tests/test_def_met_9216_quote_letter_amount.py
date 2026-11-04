"""DEF-MET-9216 — the "Quote and what is owed" letter reads the figure the books hold.

Found by the New Connection end-to-end web walk (2026-10-02): `CON-26-0129` issued
its quote bill `BL-2610-000103` for **$135.00** at Create (`BR-MET-1187`, the posting
path that landed on 2026-09-28), and the request's Messages tab still read *Sent on
approval* for this letter after the build was Activated — `_amount_owed` went on
answering *"not in the books"* for every build, so the letter was never queued.

The figure is the build record's own Outstanding (`connection_record._money`), so the
letter and the Charges tab say the same thing. A build with no bill keeps the refusal:
`quote_total` is a recorded figure and is never used as the amount.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from apps.metering import connection_messages as step7
from apps.metering import connection_record


def test_an_issued_quote_is_the_amount_the_letter_asks_for(monkeypatch):
    """$135.00 quoted, $0.00 allocated → the letter asks for $135.00."""
    monkeypatch.setattr(
        connection_record,
        "_money",
        lambda connection: {"outstanding": {"stored": "135.0000", "display": "135.00"}},
    )
    amount, gap = step7._amount_owed(SimpleNamespace(quote_total=Decimal("135.0000")))
    assert gap is None
    assert amount == Decimal("135.0000")


def test_a_part_paid_quote_asks_for_what_is_left(monkeypatch):
    """$135.00 quoted, $40.00 allocated → $95.00, exactly what the Charges tab shows."""
    monkeypatch.setattr(
        connection_record,
        "_money",
        lambda connection: {"outstanding": {"stored": "95.0000", "display": "95.00"}},
    )
    amount, gap = step7._amount_owed(SimpleNamespace(quote_total=Decimal("135.0000")))
    assert (amount, gap) == (Decimal("95.0000"), None)


def test_a_build_with_no_bill_still_refuses_and_never_uses_the_recorded_total(monkeypatch):
    """No bill → no figure. The recorded `quote_total` is not smuggled through."""
    monkeypatch.setattr(
        connection_record,
        "_money",
        lambda connection: {"outstanding": {"stored": None, "display": None}},
    )
    amount, gap = step7._amount_owed(SimpleNamespace(quote_total=Decimal("3030.0000")))
    assert amount is None
    assert gap["code"] == step7.REASON_AMOUNT_NOT_IN_THE_BOOKS
