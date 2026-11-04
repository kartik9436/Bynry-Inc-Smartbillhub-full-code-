# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9820 — the PO's request: "PO on bills" could not be changed
#          after move-in.
# Ruling:  PO 2026-10-06, D4 (a), verbatim: *"Yes: add an editable "PO on
#          bills" field to the account's Billing preferences. Bills drafted
#          after the change print the new PO; bills already issued keep the
#          old one"*.
# Rules:   hard rule 4 (an issued bill is never rewritten) · hard rule 7 (the
#          change writes `audit_log`) · BR-BIL-030 (a bill prints what was
#          STAMPED) · BR-SHL-025 (`update_account`'s roles) · CR-171 P1.01
#          (`accounts.po_number`, 60 characters at move-in).
# ───────────────────────────────────────────────────────
"""The school's PO moves from PO-2026-118 to PO-2027-044 through Billing
preferences: the next bill prints PO-2027-044 and the bill already issued keeps
PO-2026-118.

RED FIRST (law 7), PostgreSQL 16, on tip `4a75e8831` before the fix: every case
that writes `po_number` failed on the refusal `customers.account.unknown_field`
(`po_number` was not in `PATCH_FIELDS`); tc5 (the technician) passed on the
base, because the role refusal comes first either way.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a bill renderer that
read the LIVE account would print PO-2027-044 on the new bill and pass tc4's
first half — so tc4 also renders the bill issued BEFORE the change and asserts
it still reads PO-2026-118, and that PO-2027-044 is nowhere on it.
"""

from datetime import date

import pytest

from apps.billing import documents, fee_bill, models
from apps.customers import services as customers_services
from core import errors

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_cr108_w1_one_time_fee_lines_and_books import TEST_CODE
from tests.test_def_bil_8283_bill_addressee import a_fee_bill, meta
from tests.test_us_bil_022_documents import a_contact, pdf_text
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

OLD_PO = "PO-2026-118"
NEW_PO = "PO-2027-044"


def _school(brazos, dana, *, account_no, asset_no):
    account = a_one_time_account(
        brazos, dana, account_no=account_no, asset_no=asset_no, label="Main campus"
    )
    a_contact(brazos, account, "Cedar Ford Independent School District")
    return account


def test_def_cus_9820_tc1__a_clerk_changes_the_po_and_it_is_audited(
    brazos, dana, marcus, audit_rows
):
    with tenant_ctx(brazos):
        account = _school(brazos, dana, account_no="A-98201", asset_no="M-98201")
        customers_services.update_account(marcus, account.pk, {"po_number": OLD_PO})
        audit_rows.clear()
        out = customers_services.update_account(marcus, account.pk, {"po_number": f"  {NEW_PO} "})

    assert out["po_number"] == NEW_PO, "trimmed, and read back from the row"
    assert "account.updated" in audit_actions(audit_rows)
    row = next(r for r in audit_rows if r.get("action") == "account.updated")
    assert row["before"]["po_number"] == OLD_PO
    assert row["after"]["po_number"] == NEW_PO


def test_def_cus_9820_tc2__blank_clears_it(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account = _school(brazos, dana, account_no="A-98202", asset_no="M-98202")
        customers_services.update_account(marcus, account.pk, {"po_number": OLD_PO})
        out = customers_services.update_account(marcus, account.pk, {"po_number": "   "})
        account.refresh_from_db()
    assert out["po_number"] is None
    assert account.po_number is None, "blank is stored as no PO, never an empty string"


def test_def_cus_9820_tc3__longer_than_the_move_in_allows_is_refused_by_name(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        account = _school(brazos, dana, account_no="A-98203", asset_no="M-98203")
        with pytest.raises(errors.ValidationError) as refused:
            customers_services.update_account(marcus, account.pk, {"po_number": "P" * 61})
        account.refresh_from_db()
    error = refused.value.field_errors[0]
    assert error["field"] == "po_number"
    assert error["message_key"] == "customers.lookups.too_long"
    assert error["params"] == {"max": 60}
    assert account.po_number is None, "nothing written"
    with tenant_ctx(brazos):
        out = customers_services.update_account(marcus, account.pk, {"po_number": "P" * 60})
    assert out["po_number"] == "P" * 60


def test_def_cus_9820_tc4__the_next_bill_prints_the_new_po_and_the_issued_one_keeps_the_old(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        account = _school(brazos, dana, account_no="A-98204", asset_no="M-98204")
        customers_services.update_account(marcus, account.pk, {"po_number": OLD_PO})
        issued = a_fee_bill(brazos, dana, account)

        customers_services.update_account(marcus, account.pk, {"po_number": NEW_PO})
        # The NEXT bill, on a later day (one one-time run per day per cycle,
        # BR-BIL-005), drafted after the change.
        drafted_after = fee_bill.raise_and_issue_charge_fee(
            dana,
            account_id=str(account.id),
            charge_code=TEST_CODE,
            on_date=date(2026, 9, 19),
            due_days=21,
        )

        new_payload = models.Invoice.objects.get(pk=drafted_after.pk).bill_payload
        assert new_payload["po_number"] == NEW_PO
        new_doc = documents.render_invoice(models.Invoice.objects.get(pk=drafted_after.pk))
        assert meta(new_doc, "PO number").value == NEW_PO

        old_doc = documents.render_invoice(models.Invoice.objects.get(pk=issued.pk))
        assert meta(old_doc, "PO number").value == OLD_PO
        assert models.Invoice.objects.get(pk=issued.pk).bill_payload["po_number"] == OLD_PO
        assert NEW_PO not in pdf_text(old_doc.pdf), "hard rule 4: the issued bill is untouched"


def test_def_cus_9820_tc5__the_edit_keeps_update_accounts_roles(brazos, dana):
    """BR-SHL-025: the same roles as every other Billing preferences field."""
    with tenant_ctx(brazos):
        account = _school(brazos, dana, account_no="A-98205", asset_no="M-98205")
        technician = staff_actor(brazos, "field_technician", "dee@brazosbendutilities.test")
        with pytest.raises(errors.AuthError) as refused:
            customers_services.update_account(technician, account.pk, {"po_number": NEW_PO})
        account.refresh_from_db()
    assert refused.value.code == errors.AUTH_PERMISSION_DENIED
    assert account.po_number is None
