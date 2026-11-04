# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10767 (W3) — a statement imported from the screen carried
#           no opening or closing balance, so the reconciliation always read
#           "BANK SHOWS Not on this statement"
# Ruling:   decision log 2026-10-30 "Final-walk questions W1–W4 answered (PO)"
#           — *"W3-A"*; worked: 26–31 Oct statement, closing $616.10 →
#           "Bank shows $616.10 · books $616.10"
# Rules:    CS-14 (the bank's OWN figure, counted as reported; unknown is never
#           0.00) · CLAUDE.md rule 2 (money as a decimal string)
# ───────────────────────────────────────────────────────
"""W3 through the ONE door a clerk has — `POST /bank-statements` — not the service.

`test_lbx05_09_statement_lines_post` proves the tie-out by handing
`closing_balance=616.10` straight to `import_bank_statement`; the defect was
that the screen's door never carried it. Here the tester's statement arrives as
the browser sends it (base64, balances as strings), the day is worked exactly
as in LBX-05, and the reconciliation reads **bank 616.10 · books 616.10 ·
difference 0.00**. A statement sent without them still reads UNKNOWN, never 0.00.
"""

import base64
import uuid

import pytest

from apps.payments import api as payments_api
from apps.payments import reconciliation

from tests.test_def_pay_10765_executive_statement_return import _person
from tests.test_lbx05_09_statement_lines_post import (
    IMPORTED_AT,
    STATEMENT_ROWS,
    WORKED_AT,
    line,
    the_lockbox_day,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import a_bank_account, a_statement
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _import(brazos, admin, **balances):
    with tenant_ctx(brazos):
        account = a_bank_account(brazos, name=f"Bank of America {uuid.uuid4().hex[:6]}")
    body = {
        "bank_account_id": str(account.pk),
        "period_start": "2026-10-26",
        "period_end": "2026-10-31",
        "file_name": "stmt.csv",
        "file_base64": base64.b64encode(a_statement(STATEMENT_ROWS)).decode(),
        "imported_at": IMPORTED_AT.isoformat(),
        **balances,
    }
    response = api_call(
        payments_api.bank_statements, "post", user=admin, role="system_admin", tenant=brazos, data=body
    )
    assert response.status_code == 201, response.data
    return response.data["statement_import_id"]


def _reconciliation(brazos, admin, statement_id):
    response = api_call(
        payments_api.bank_statement_reconciliation,
        "get",
        user=admin,
        role="system_admin",
        tenant=brazos,
        statement_import_id=statement_id,
    )
    assert response.status_code == 200, response.data
    return response.data


def test_w3__the_testers_statement_through_the_door_reads_bank_616_10_books_616_10(brazos, dana):
    admin = _person(brazos, "system_admin", "dana@brazosbendutilities.test")
    with tenant_ctx(brazos):
        payments, batch = the_lockbox_day(dana, brazos)
    statement_id = _import(brazos, admin, opening_balance="0.00", closing_balance="616.10")

    with tenant_ctx(brazos):
        reconciliation.reconcile_batch(actor=dana, batch_id=batch.pk, posted_at=WORKED_AT)
        for reference, cheque in (("RET1029-01", "4102"), ("RET1029-02", "4103")):
            reconciliation.match_returned_line(
                actor=dana,
                bank_line_id=line(statement_id, reference).pk,
                payment_id=payments[cheque].pk,
                occurred_at=WORKED_AT,
            )
        reconciliation.explain_bank_fee_line(
            actor=dana, bank_line_id=line(statement_id, "FEE1031").pk, occurred_at=WORKED_AT
        )

    body = _reconciliation(brazos, admin, statement_id)
    assert body["statement"]["opening_balance"] == "0.000000"
    assert body["statement"]["closing_balance"] == "616.100000"
    assert body["bank_closing_balance"] == "616.100000"
    assert body["book_cash_balance"] == "616.100000"
    assert body["difference_bank_less_books"] == "0.000000"
    assert body["bank_equals_books"] is True
    assert "no_closing_balance_captured" not in {gap["code"] for gap in body["unavailable"]}


def test_w3__a_statement_sent_without_balances_still_reads_unknown_never_zero(brazos, dana):
    admin = _person(brazos, "system_admin", "dana@brazosbendutilities.test")
    with tenant_ctx(brazos):
        the_lockbox_day(dana, brazos)
    statement_id = _import(brazos, admin)
    body = _reconciliation(brazos, admin, statement_id)
    assert body["bank_closing_balance"] is None
    assert body["difference_bank_less_books"] is None
    assert body["bank_equals_books"] is None
    assert "no_closing_balance_captured" in {gap["code"] for gap in body["unavailable"]}
