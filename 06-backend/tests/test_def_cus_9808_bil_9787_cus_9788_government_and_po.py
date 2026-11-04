# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-9808 (the Account types card could not clear `legacy`,
#          so Government and its four sub-types were unreachable — the root of
#          DEF-CUS-9786, the PO's M7 "Government · Schools") · DEF-BIL-9787
#          (the PO number recorded at move-in reached no bill) · DEF-CUS-9788
#          (the PO number was on no screen after Complete)
# Rulings: OQ-CUS-12407 option (a), PO 2026-09-18 *"go with option a"* — any
#          tenant admin may set or clear `legacy` on any row, seeded rows
#          included · OQ-CUS-12618, PO 2026-09-23 — sub-categories come from
#          Settings → Reference data, no seed row is moved · CR-171 P1.01 /
#          P1.11 — `accounts.po_number`, *"printed on every bill of THIS account"*
# Rules:   BR-CUS-094 (legacy closes the PICKER, never re-labels a record) ·
#          BR-BIL-030 (a bill prints what was STAMPED, never a live join) ·
#          hard rule 4 (an issued bill is never rewritten)
# ───────────────────────────────────────────────────────
"""Government · Schools can be moved in once a utility offers Government, and
the PO number an account records is printed on its bills and shown on its page.

RED FIRST (hard-won law 7), on the tip `0b2df5b1b` before the fix, PostgreSQL 16
(5 failed, 1 passed): tc1 failed on `assert True is False` — the handler ignored
the key and Government stayed legacy; tc2 on a non-boolean `legacy` raising
nothing; tc3 on
`KeyError: 'po_number'` in the bill payload; tc4 on no *PO number* row in the
rendered document; tc3b passed on the base
(it pins that a PO-less bill is unchanged); tc5 on `KeyError: 'po_number'` in
the account detail.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a renderer reading
the LIVE account would print today's PO and pass tc3/tc4. tc4 changes the PO
AFTER issue and asserts the issued bill still prints the stamped one, so a
live join goes red (BR-BIL-030, hard rule 4).
"""

import pytest

from apps.billing import customers_seam, delivery_seam, documents, models
from apps.customers import lookups as customer_lookups
from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from core import errors

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_def_bil_8283_bill_addressee import a_fee_bill, meta
from tests.test_po_20260917_account_types_are_the_tenants import _categories
from tests.test_us_bil_022_documents import a_contact, pdf_text
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import provisioned_tenant

pytestmark = pytest.mark.django_db

HANDLER = customer_lookups.AccountTypeLookupHandler()
PO = "PO-2026-118"


def _selectable(tenant):
    return [row["code"] for row in _categories(tenant)["selectable"]]


def test_def_cus_9808_tc1__an_admin_offers_government_again_and_its_sub_types_follow(
    growth_plan, identity_seam
):
    """The PO's M7: a utility that bills a school district clears Government's
    legacy flag on Settings → Reference data → Account types (OQ-CUS-12407 a);
    the move-in's Customer type then offers Government, and its Sub-type list
    holds the seeded Schools under it."""
    tenant, _ = provisioned_tenant()
    # `_categories` drives the real DRF stack, which sets and clears its own tenant
    # context — so each handler call sits in its own `tenant_ctx`, never around one.
    with tenant_ctx(tenant):
        government = customer_models.AccountType.objects.get(tenant=tenant, code="government")
        assert government.legacy is True
    assert "government" not in _selectable(tenant)

    with tenant_ctx(tenant):
        saved = HANDLER.update(government, {"legacy": False})
        assert HANDLER.serialize(saved)["legacy"] is False
        under = set(
            customer_models.AccountSubtype.objects.filter(
                tenant=tenant, account_type=government, active=True
            ).values_list("code", flat=True)
        )
        assert {"schools", "municipal_buildings", "parks_facilities", "government"} <= under
    assert "government" in _selectable(tenant)

    # And back: any row, seeded rows included — Residential stops being offered
    # and keeps every record it already has (BR-CUS-094's third axis).
    with tenant_ctx(tenant):
        residential = customer_models.AccountType.objects.get(tenant=tenant, code="residential")
        HANDLER.update(residential, {"legacy": True})
        assert customer_models.AccountType.objects.get(pk=residential.pk).active is True
    assert "residential" not in _selectable(tenant)


def test_def_cus_9808_tc2__legacy_is_a_boolean_and_create_never_sets_it(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        government = customer_models.AccountType.objects.get(tenant=tenant, code="government")
        with pytest.raises(errors.ValidationError) as refused:
            HANDLER.update(government, {"legacy": "no"})
        assert refused.value.field_errors[0]["field"] == "legacy"
        assert customer_models.AccountType.objects.get(pk=government.pk).legacy is True

        created = HANDLER.create({"code": "marina", "name": "Marina berth", "legacy": True})
        assert created.legacy is False, "a row created today is new business"


def test_def_bil_9787_tc3__a_bill_stamps_the_accounts_po_and_one_without_a_po_carries_none(
    brazos, dana
):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-97871", asset_no="M-9787", label="Main campus")
        a_contact(brazos, account, "Cedar Ford Independent School District")
        customer_models.Account.objects.filter(pk=account.pk).update(po_number=f"  {PO} ")

        bill = a_fee_bill(brazos, dana, account)
        payload = models.Invoice.objects.get(pk=bill.pk).bill_payload
        assert payload["po_number"] == PO
        context, _problems = delivery_seam.bill_render_context(bill)
        assert context["po_number"] == PO
        assert customers_seam.po_number_for(str(account.pk)) == PO


def test_def_bil_9787_tc3b__an_account_with_no_po_gets_no_po_key_and_no_po_row(brazos, dana):
    with tenant_ctx(brazos):
        plain = a_one_time_account(brazos, dana, account_no="A-97872", asset_no="M-9788", label="Unit 2")
        other = a_fee_bill(brazos, dana, plain)
        other_payload = models.Invoice.objects.get(pk=other.pk).bill_payload
        assert "po_number" not in other_payload, "no PO, no key: other bills stay byte-identical"
        assert not [f for f in documents.render_invoice(other).meta if f.label == "PO number"]


def test_def_bil_9787_tc4__the_issued_bill_prints_the_stamped_po_on_the_page(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-97873", asset_no="M-9789", label="Main campus")
        customer_models.Account.objects.filter(pk=account.pk).update(po_number=PO)
        bill = a_fee_bill(brazos, dana, account)

        # Changed AFTER issue: the issued bill keeps the stamped PO (BR-BIL-030).
        customer_models.Account.objects.filter(pk=account.pk).update(po_number="PO-2027-001")

        document = documents.render_invoice(models.Invoice.objects.get(pk=bill.pk))
        assert meta(document, "PO number").value == PO
        assert "po_number" not in {a.field for a in document.absent}
        assert PO in pdf_text(document.pdf)
        assert "PO-2027-001" not in pdf_text(document.pdf)


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S5, shown as:
    *"A bill prints the account's PO number under the mailing address — 'PO
    number PO-2026-118'. Display only: no amount moves; bills already issued
    are not touched."*

    One account, the same fee billed twice: the first bill was issued BEFORE
    the PO was recorded (it stays exactly as it was — no PO key, no PO row);
    `PO-2026-118` is then recorded and the next bill prints *PO number ·
    PO-2026-118*, the row straight after the mailing address. Both bills carry
    the same amount and the same lines.
    """
    from datetime import date

    from apps.billing import fee_bill
    from tests.test_def_bil_8283_bill_addressee import TEST_CODE

    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-97875", asset_no="M-9791", label="Main campus")
        before = a_fee_bill(brazos, dana, account)
        payload_before = dict(models.Invoice.objects.get(pk=before.pk).bill_payload)

        customer_models.Account.objects.filter(pk=account.pk).update(po_number=PO)
        after = fee_bill.raise_and_issue_charge_fee(
            dana, account_id=str(account.id), charge_code=TEST_CODE, on_date=date(2026, 10, 12), due_days=21
        )

        issued = models.Invoice.objects.get(pk=before.pk)
        drafted = models.Invoice.objects.get(pk=after.pk)
        # Bills already issued are not touched.
        assert issued.bill_payload == payload_before
        assert "po_number" not in issued.bill_payload
        assert not [f for f in documents.render_invoice(issued).meta if f.label == "PO number"]
        # The new bill prints it, under the mailing address.
        document = documents.render_invoice(drafted)
        labels = [f.label for f in document.meta]
        assert meta(document, "PO number").value == PO
        assert labels.index("PO number") == labels.index("Mailing address") + 1, labels
        assert "PO number" in pdf_text(document.pdf) and PO in pdf_text(document.pdf)
        # Display only: no amount moves.
        assert drafted.total == issued.total
        assert [(l.description, l.amount) for l in drafted.lines.order_by("id")] == [
            (l.description, l.amount) for l in issued.lines.order_by("id")
        ]


def test_def_cus_9788_tc5__the_account_detail_serves_its_po(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-97874", asset_no="M-9790", label="Main campus")
        assert customer_selectors.account_detail(account.pk)["po_number"] is None
        customer_models.Account.objects.filter(pk=account.pk).update(po_number=PO)
        assert customer_selectors.account_detail(account.pk)["po_number"] == PO
