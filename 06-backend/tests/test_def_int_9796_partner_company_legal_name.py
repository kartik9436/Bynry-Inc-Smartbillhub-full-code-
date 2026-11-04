# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-INT-9796 — the partner Customers API named a COMPANY account by
#          its contact person, split into first/last ("Ruth" / "Okafor"), while
#          every staff screen names it by the company (DEF-CUS-9776, 2.549.8).
# Ruling:  PO 2026-10-06, D3 (a), verbatim: *"From the next release, send the
#          company's legal name for company accounts, and say so in the release
#          notes."* (decision log, same date).
# Rules:   BR-INT-054 (integrations hands over what we hold, it does not
#          interpret) · DEF-CUS-9776's single source,
#          `customers.selectors.current_customers_for`.
# ───────────────────────────────────────────────────────
"""A company account goes to partners under the company's LEGAL NAME; a person
account goes exactly as before.

THE CHURCH, BEFORE AND AFTER (the release note's own example):

    before  customer_name "Ruth Okafor"   first_name "Ruth"   last_name "Okafor"
    after   customer_name "Grace Fellowship of Cedar Ford"
            first_name    "Grace Fellowship of Cedar Ford"    last_name null
            organization_name "Grace Fellowship of Cedar Ford"

`email` and `phone` stay the contact's (Ruth's): they are how the partner
REACHES the account, and the ruling moved the NAME only.

RED FIRST (law 7), in pytest on PostgreSQL 16, on tip `4a75e8831` before the
fix: tc1/tc2/tc4 failed on `'Ruth Okafor' == 'Grace Fellowship of Cedar Ford'`
and on `KeyError: 'organization_name'`; tc3 (the person case) failed only on the
missing `organization_name` key, which is the one thing a person record gains.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a fixture whose
customer `display_name` equals the contact's name — which is how every account
in `address_stories` is built — cannot tell the two sources apart. The company
here has a contact (Ruth Okafor) whose name is NOT the company's, on purpose.
"""

from __future__ import annotations

import json

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.integrations import partner_api, shapes
from apps.integrations.runners import serve

from tests.test_cr110_phase2_partner_customers import (  # noqa: F401
    OKONJO_PREMISES,
    RUIZ_PREMISES,
    _account_at,
    _by_number,
    _records,
)
from tests.test_cr110_phase2_partner_reference import _body, _get, wired  # noqa: F401
from tests.test_cr111_invoice_cloud import DOC_KEY, IC_RECORDS, wired_for_documents  # noqa: F401
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

LEGAL_NAME = "Grace Fellowship of Cedar Ford"

pytestmark = pytest.mark.django_db


@pytest.fixture()
def person(brazos, marcus):
    """An ordinary person account. Built here rather than borrowed from
    `address_stories`, whose orphan row names a premises that does not exist —
    a foreign key PostgreSQL refuses at commit, so that fixture cannot run on
    the database this file is proved on."""
    with tenant_ctx(brazos):
        _, account = _account_at(
            marcus,
            brazos,
            RUIZ_PREMISES,
            label="Unit A",
            contact={
                "full_name": "Charles Schultz",
                "email": "charles.schultz@example.com",
                "phone": "+1 (512) 555-0101",
                "dob": "1988-04-02",
                "gov_id_last4": "1122",
            },
        )
    return account


@pytest.fixture()
def church(brazos, marcus, person):
    """Grace Fellowship of Cedar Ford, a COMPANY customer, whose primary contact
    is Ruth Okafor — the CR-171 M5 account."""
    with tenant_ctx(brazos):
        _, account = _account_at(
            marcus,
            brazos,
            {**OKONJO_PREMISES, "address_line": "12 Chapel Road"},
            label="Sanctuary",
            contact={
                "full_name": "Ruth Okafor",
                "email": "ruth.okafor@gracefellowship.example.org",
                "phone": "+1 (281) 555-0177",
                "dob": "1970-03-03",
                "gov_id_last4": "4411",
            },
        )
        link = customers_models.CustomerAccount.objects.get(
            tenant_id=brazos.id, account=account, ended_at__isnull=True
        )
        customers_models.Customer.objects.filter(pk=link.customer_id).update(
            kind="company", display_name=LEGAL_NAME
        )
    return account


def test_def_int_9796_tc1__a_company_goes_to_partners_under_its_legal_name(
    brazos, dana, wired, church
):
    record = _by_number(_records(brazos))[church.account_no]
    assert record["customer_name"] == LEGAL_NAME
    # The whole legal name is the first half and the last half is null —
    # `split_name`'s own rule for a name that is not a person's — so
    # first + last still reassembles `customer_name` exactly.
    assert record["first_name"] == LEGAL_NAME
    assert record["last_name"] is None
    assert record["organization_name"] == LEGAL_NAME
    # The ruling moved the NAME only: the contact is still how they reach it.
    assert record["email"] == "ruth.okafor@gracefellowship.example.org"
    assert record["phone"] == "+1 (281) 555-0177"


def test_def_int_9796_tc2__the_partner_name_is_the_account_screens_name(
    brazos, dana, wired, church
):
    """One source: the account page's own read (`DEF-CUS-9776`)."""
    with tenant_ctx(brazos):
        on_screen = customers_selectors.primary_contact_name(church)
    record = _by_number(_records(brazos))[church.account_no]
    assert record["customer_name"] == on_screen == LEGAL_NAME


def test_def_int_9796_tc3__a_person_account_is_unchanged(brazos, dana, wired, church, person):
    record = _by_number(_records(brazos))[person.account_no]
    assert record["customer_name"] == "Charles Schultz"
    assert (record["first_name"], record["last_name"]) == ("Charles", "Schultz")
    assert record["organization_name"] is None


def test_def_int_9796_tc4__consumer_info_carries_the_same_name_in_invoice_clouds_words(
    brazos, dana, wired_for_documents, church
):
    """`consumer-info` is the same composer, read through Invoice Cloud's
    shape — `customer_name` arrives as `account_name`."""
    serve.reset_partner_limits()
    response = _get(
        brazos,
        partner_api.partner_consumer_info,
        key=DOC_KEY,
        query={"consumer_id": church.account_no},
        path="/partner/v1/consumer-info",
    )
    assert response.status_code == 200, _body(response)
    record = json.loads(_body(response))[IC_RECORDS][0]
    assert record["account_name"] == LEGAL_NAME
    assert record["first_name"] == LEGAL_NAME and record["last_name"] is None
    assert record["organization_name"] == LEGAL_NAME


def test_def_int_9796_tc5__the_invoice_cloud_shape_passes_the_new_field_through():
    """A shape renames and drops; it may not lose a field it never named."""
    company = {
        "customer_name": LEGAL_NAME,
        "first_name": LEGAL_NAME,
        "last_name": None,
        "organization_name": LEGAL_NAME,
        "status": {"code": "active", "label": "Active"},
        "status_display": "Active",
    }
    out = shapes.apply_record(company, shapes.INVOICE_CLOUD, resource="customers")
    assert out["account_name"] == LEGAL_NAME
    assert out["organization_name"] == LEGAL_NAME
