"""**The account detail serves the mailing address's "Apt, suite or unit" line**
(`DEF-CUS-6460`).

The account door has stored `line2` since `3b0a8ee12`, and the bill's own read
(`mailing_address_for_account`) carries it, but `address_dict` — the read the
account page draws from — served line1, city, state and ZIP only. So the page
printed `1408 Elm St, Ottumwa, IA, 52501` for an address whose envelope reads
`1408 Elm St, Apt 3B, …`.

What would make this pass wrongly: asserting only that the key exists — a
`None` would pass. So the stored value is asserted, and a row with no second
line is asserted to serve `None`, not a blank string.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=["water"],
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    return tenant


def _account(tenant, tag):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"1408 Elm St {tag}", city="Ottumwa", state="IA"
    )
    unit = metering_models.Unit.objects.create(tenant=tenant, premises=premises, label=f"Unit {tag}")
    status = customers_models.AccountStatus.objects.filter(
        tenant=tenant, behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES
    ).first()
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        account_no=f"A-86{tag}",
        status=status,
        account_type=customers_models.AccountType.objects.first(),
    )


def _mailing(detail):
    (row,) = [a for a in detail["addresses"] if a["kind"] == "mailing"]
    return row


def test_the_account_detail_serves_the_unit_line(ottumwa):
    with tenant_ctx(ottumwa):
        account = _account(ottumwa, "a")
        customers_models.Address.objects.create(
            tenant=ottumwa, account=account, kind="mailing", line1="1408 Elm St",
            line2="Apt 3B", city="Ottumwa", state="IA", postal_code="52501",
        )
        row = _mailing(customers_selectors.account_detail_dict(account))
    assert row["line1"] == "1408 Elm St"
    assert row["line2"] == "Apt 3B"


def test_an_address_with_no_unit_line_serves_none(ottumwa):
    with tenant_ctx(ottumwa):
        account = _account(ottumwa, "b")
        customers_models.Address.objects.create(
            tenant=ottumwa, account=account, kind="mailing", line1="9 Oak Ave",
            city="Ottumwa", state="IA", postal_code="52501",
        )
        row = _mailing(customers_selectors.account_detail_dict(account))
    assert row["line2"] is None
