"""Immutability suite (CLAUDE.md rule #4): UPDATE/DELETE on issued invoices,
invoice lines, payments, journal entries MUST raise (B2 triggers).
Corrections are new rows; this suite proves the triggers hold."""

import pytest


@pytest.mark.skip(reason="activates with the billing/payments migrations")
def test_issued_invoice_is_append_only():
    raise NotImplementedError
