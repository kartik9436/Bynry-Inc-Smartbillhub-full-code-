# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8283 (critical, PO report 2026-09-30) — issued bills printed
#          no customer name, no service address, no mailing address, and "Who
#          sent it" read "This bill did not record it". Evidence: one-time fee
#          bill BL-2609-000081 (AC-2026-00058, Ottumwa Water Works).
# Rules:   BR-BIL-030 (the locked instance carries who the bill is for and who
#          sent it — frozen, never joined) · CLAUDE.md hard rule 8 (an address
#          lives on the PREMISES and is walked to; `customers.addresses`
#          kind='mailing' and `service_centres.address` are named exceptions) ·
#          hard rule 4 (an issued bill is never rewritten)
# Code:    apps/billing/stages/assemble_document.py (`_stamp_addressee`) ·
#          apps/billing/customers_seam.py (`bill_addressee`) ·
#          apps/customers/selectors.py (`bill_addressee_for_account`) ·
#          apps/tenancy/selectors.py (`bill_masthead` fallback chain) ·
#          apps/billing/documents.py (Mailing address row · Customer on the stub)
# ───────────────────────────────────────────────────────
"""A bill that does not say who it is for, or who sent it, is not a bill.

Stage 6 is the ONE path every bill kind shares — a cycle bill and all the
one-time kinds — so that is where the answer is frozen. These cases drive both
kinds through their real doors and read the answer back off the RENDERED
document, not only the payload (hard-won law 6).

RED FIRST (hard-won law 7), against the tip `28f99c55f`: tc1 failed on the fee
bill's payload holding no `customer_name`; tc2 on a cycle bill with no
`mailing_address`; tc3 on the mailing fallback; tc4 on the masthead address.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a renderer reading
the live account instead of the payload would print the right name today. tc5
renames the contact and moves the mailing row AFTER issue and asserts the bill
still prints the stamped values (BR-BIL-030).
"""

from datetime import date

import pytest

from apps.billing import documents, fee_bill, issue, models, runs

from tests.test_cr108_w1_one_time_fee_lines_and_books import (
    a_charge_code,
    TEST_CODE,
    a_one_time_account,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    an_account,
    an_authorised_run,
)
from tests.test_us_bil_022_documents import a_contact, pdf_text
from tests.test_us_bil_029_assemble import SERVICE_DATE, billing_data
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FEE_ON = date(2026, 9, 12)
DASH = documents.ABSENT_MARK


def a_mailing_row(tenant, account, **overrides):
    from apps.customers import models as customer_models

    values = dict(
        tenant=tenant,
        account=account,
        kind="mailing",
        line1="PO Box 88",
        city="Ottumwa",
        state="IA",
        postal_code="52501",
    )
    values.update(overrides)
    return customer_models.Address.objects.create(**values)


def a_utility_address(tenant):
    tenant.dba_name = "Ottumwa Water Works"
    tenant.mailing_address = "230 Market St, Ottumwa, IA 52501"
    tenant.support_phone = "(641) 555-0100"
    tenant.save(update_fields=["dba_name", "mailing_address", "support_phone"])


def meta(document, label):
    return next(f for f in document.meta if f.label == label)


def masthead(document, label):
    return next(f for f in document.masthead if f.label == label)


def a_fee_bill(tenant, dana, account):
    a_charge_code(tenant)
    return fee_bill.raise_and_issue_charge_fee(
        dana,
        account_id=str(account.id),
        charge_code=TEST_CODE,
        on_date=FEE_ON,
        due_days=21,
    )


def a_cycle_bill(tenant, dana, account, *, snapshot):
    run = an_authorised_run(tenant, dana)
    draft = runs.calculate_account(
        billing_data(account, snapshot=snapshot, taxes=()), bill_run=run, service_date=SERVICE_DATE
    )
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana,
    )


def test_def_bil_8283_tc1__a_one_time_fee_bill_names_its_customer_and_both_addresses(brazos, dana):
    """THE PO'S BILL: a fee bill, a premises address, a separate mailing row."""
    with tenant_ctx(brazos):
        a_utility_address(brazos)
        account = a_one_time_account(
            brazos, dana, account_no="A-82831", asset_no="M-8283", label="Unit 4"
        )
        a_contact(brazos, account, "Priya Raman")
        a_mailing_row(brazos, account)

        bill = a_fee_bill(brazos, dana, account)

        payload = models.Invoice.objects.get(pk=bill.pk).bill_payload
        assert payload["customer_name"] == "Priya Raman"
        assert payload["service_address"] == "M-8283 Bluestem Ln, Katy, TX 77494"
        assert payload["unit_label"] == "Unit 4"
        assert payload["mailing_address"] == "PO Box 88, Ottumwa, IA 52501"
        assert payload["mailing_address_source"] == "mailing_address"
        assert payload["utility_address"] == "230 Market St, Ottumwa, IA 52501"

        document = documents.render_invoice(bill)
        assert meta(document, "Customer").value == "Priya Raman"
        assert meta(document, "Service address").value == "M-8283 Bluestem Ln, Katy, TX 77494"
        assert meta(document, "Unit").value == "Unit 4"
        assert meta(document, "Mailing address").value == "PO Box 88, Ottumwa, IA 52501"
        assert masthead(document, "Utility").value == "Ottumwa Water Works"
        assert masthead(document, "Address").value == "230 Market St, Ottumwa, IA 52501"
        stub = {f.label: f.value for f in document.stub}
        assert stub["Customer"] == "Priya Raman"
        assert stub["Account"] == "A-82831"
        named = {a.field for a in document.absent}
        assert not (
            {"customer_name", "service_address", "mailing_address", "utility_address"} & named
        ), named
        # And on the page the customer holds (law 6).
        page = pdf_text(document.pdf)
        for text in ("Priya Raman", "M-8283 Bluestem Ln", "PO Box 88", "230 Market St"):
            assert text in page, text


def test_def_bil_8283_tc2__a_cycle_bill_carries_the_mailing_address_too(brazos, dana):
    """A cycle bill: gather stamped the name and the service address; stage 6
    adds the mailing address and the utility, and keeps gather's values."""
    with tenant_ctx(brazos):
        a_utility_address(brazos)
        account = an_account(dana, brazos)
        a_mailing_row(brazos, account, line1="18 Wapello St", line2="Suite 2")

        bill = a_cycle_bill(
            brazos,
            dana,
            account,
            snapshot={
                "customer_name": "Sarah Chen",
                "unit_label": "Unit A",
                "service_address": "1901 Bluestem Ln, Katy, TX 77494",
            },
        )

        payload = models.Invoice.objects.get(pk=bill.pk).bill_payload
        assert payload["customer_name"] == "Sarah Chen", "gather's stamped name wins"
        assert payload["mailing_address"] == "18 Wapello St, Suite 2, Ottumwa, IA 52501"
        document = documents.render_invoice(bill)
        assert meta(document, "Customer").value == "Sarah Chen"
        assert meta(document, "Service address").value == "1901 Bluestem Ln, Katy, TX 77494"
        assert meta(document, "Mailing address").value == (
            "18 Wapello St, Suite 2, Ottumwa, IA 52501"
        )
        assert masthead(document, "Address").value == "230 Market St, Ottumwa, IA 52501"


def test_def_bil_8283_tc3__no_mailing_row_posts_to_the_service_address_with_its_unit(brazos, dana):
    """B2 §2 — an absent mailing row means *same as service*; a cycle bill whose
    gather stamped nothing is filled from customers too."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_contact(brazos, account, "Sarah Chen")

        bill = a_cycle_bill(brazos, dana, account, snapshot={})

        payload = models.Invoice.objects.get(pk=bill.pk).bill_payload
        assert payload["customer_name"] == "Sarah Chen"
        assert payload["service_address"] == "1901 Bluestem Ln, Katy, TX 77494"
        assert payload["mailing_address"] == "1901 Bluestem Ln, Unit A, Katy, TX 77494"
        assert payload["mailing_address_source"] == "service_address"
        document = documents.render_invoice(bill)
        assert meta(document, "Mailing address").value == (
            "1901 Bluestem Ln, Unit A, Katy, TX 77494"
        )


def test_def_bil_8283_tc4__who_sent_it_falls_back_to_the_utilitys_own_counter(brazos, dana):
    """A utility that left the company mailing box blank but shows a service
    centre prints that centre's address, never a dash (`bill_masthead`)."""
    from apps.tenancy import published_content_models as content

    with tenant_ctx(brazos):
        brazos.mailing_address = None
        brazos.remit_to_address = None
        brazos.support_phone = None
        brazos.support_email = None
        brazos.save(
            update_fields=["mailing_address", "remit_to_address", "support_phone", "support_email"]
        )
        content.ServiceCentre.objects.create(
            tenant=brazos,
            slug="hidden-depot",
            name="Depot",
            address="1 Yard Rd, Ottumwa, IA 52501",
            is_shown_to_customers=False,
            position=0,
        )
        content.ServiceCentre.objects.create(
            tenant=brazos,
            slug="main",
            name="Main office",
            address="230 Market St, Ottumwa, IA 52501",
            phone="(641) 555-0100",
            is_shown_to_customers=True,
            position=1,
        )
        account = a_one_time_account(brazos, dana, account_no="A-82834", asset_no="M-82834")

        document = documents.render_invoice(a_fee_bill(brazos, dana, account))

        assert masthead(document, "Address").value == "230 Market St, Ottumwa, IA 52501"
        assert masthead(document, "Contact").value == "(641) 555-0100"


def test_def_bil_8283_tc5__the_stamp_is_frozen_a_later_change_does_not_reprint(brazos, dana):
    """BR-BIL-030 — rename the customer and move the mailing row AFTER issue."""
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-82835", asset_no="M-82835")
        contact = a_contact(brazos, account, "Priya Raman")
        mailing = a_mailing_row(brazos, account)
        bill = a_fee_bill(brazos, dana, account)

        contact.full_name = "Priya Raman-Okafor"
        contact.save(update_fields=["full_name"])
        mailing.line1 = "PO Box 99"
        mailing.save(update_fields=["line1"])

        document = documents.render_invoice(models.Invoice.objects.get(pk=bill.pk))
        assert meta(document, "Customer").value == "Priya Raman"
        assert meta(document, "Mailing address").value == "PO Box 88, Ottumwa, IA 52501"
