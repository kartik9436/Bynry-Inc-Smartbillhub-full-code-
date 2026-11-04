# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2847 (2026-08-31) — THE ACCOUNT'S MAILING ADDRESS HAS NO LINE 2
#          AND NO COUNTRY COLUMN, so two of the print manifest's nine address
#          fields can only ever be empty. Every layer above the table was
#          already written to carry them; only the columns were missing.
# Rules:   BR-NOT-029 clause (a) — DISCRETE columns, never assembled from or
#          split out of one field · clause (b) — city, state and postal code are
#          the mandatory three, and neither new column is among them ·
#          CLAUDE.md hard-won law 7 (prove it RED first)
# Impacts: apps/customers/models.Address · selectors.mailing_address_for_account
#          · apps/billing/customers_seam.MailingAddress
# ───────────────────────────────────────────────────────
"""A FULL POSTAL ADDRESS CAN BE RECORDED, AND NOTHING IS INVENTED FOR AN OLD ROW.

Three things have to hold together and only the first is obvious:

1. a second line and a country, once written, come back out of the read;
2. **an address written before migration 0038 answers `None` for both** — no
   backfill split line 1 and none took the tenant's own country;
3. **neither column can hold a bill.** `BR-NOT-029` clause (b) names city, state
   and postal code; adding two fields to the manifest must not add two ways for
   a bill to be held out of the print file, and `missing` is what decides that.

The third is the one a careless fix breaks: adding the columns to
`REQUIRED_ADDRESS_PARTS` would look tidy and would hold every bill in the
product on the day it shipped.
"""
import pytest

from apps.customers import models as customers_models, selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

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


def _account(tenant, *, tag: str):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"1408 Elm St {tag}", city="Ottumwa", state="IA"
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, label=f"Unit {tag}"
    )
    status = customers_models.AccountStatus.objects.filter(
        tenant=tenant, behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES
    ).first()
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        account_no=f"A-8{tag}",
        status=status,
        account_type=customers_models.AccountType.objects.first(),
    )


def test_def2847__a_second_line_and_a_country_survive_the_read(ottumwa):
    """The columns exist and the published read carries them.

    **RED before migration 0038:** `Address(... line2=…, country=…)` raised
    `TypeError: Address() got unexpected keyword arguments: 'line2', 'country'`,
    and the read returned literal `None` for both with a comment saying they
    were not columns.
    """
    with tenant_ctx(ottumwa):
        account = _account(ottumwa, tag="a")
        customers_models.Address.objects.create(
            tenant=ottumwa,
            account=account,
            kind="mailing",
            line1="1408 Elm St",
            line2="Apt 3B",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
            country="USA",
        )
        answer = customers_selectors.mailing_address_for_account(account.id)

    assert answer["line1"] == "1408 Elm St"
    assert answer["line2"] == "Apt 3B"
    assert answer["country"] == "USA"
    assert answer["missing"] == [], "a complete address holds no bill"


def test_def2847__an_address_written_before_the_columns_answers_none(ottumwa):
    """⚠ **THE CLAUSE (a) GUARD.** No value is derived for a row that never had
    one — not from line 1, and not from the tenant's regional setting.

    `"1408 Elm St Apt 3B"` in a single field is exactly the shape a backfill
    would have been tempted to split, and splitting it is the operation
    `BR-NOT-029` clause (a) forbids: *"a guessed address is mail delivered to the
    wrong house."*
    """
    with tenant_ctx(ottumwa):
        account = _account(ottumwa, tag="b")
        customers_models.Address.objects.create(
            tenant=ottumwa,
            account=account,
            kind="mailing",
            line1="1408 Elm St Apt 3B",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
        )
        answer = customers_selectors.mailing_address_for_account(account.id)

    assert answer["line1"] == "1408 Elm St Apt 3B", "line 1 is kept whole"
    assert answer["line2"] is None, "nothing was carved out of line 1"
    assert answer["country"] is None, "the tenant's own country is not the customer's"
    assert answer["missing"] == [], "and neither absence holds the bill"


def test_def2847__neither_new_column_can_hold_a_bill(ottumwa):
    """⚠ **THE CLAUSE (b) GUARD, AND IT IS THE ONE A TIDY FIX BREAKS.**

    Adding the two fields to `REQUIRED_ADDRESS_PARTS` would read as consistency
    and would hold EVERY bill in the product on the day it shipped, because every
    existing row is null on both. The mandatory three are the mandatory three.
    """
    assert customers_selectors.REQUIRED_ADDRESS_PARTS == ("city", "state", "postal_code")

    with tenant_ctx(ottumwa):
        account = _account(ottumwa, tag="c")
        customers_models.Address.objects.create(
            tenant=ottumwa,
            account=account,
            kind="mailing",
            line1="1408 Elm St",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
        )
        answer = customers_selectors.mailing_address_for_account(account.id)
    assert answer["missing"] == []

    # And a genuinely incomplete address still holds, unchanged by this work.
    with tenant_ctx(ottumwa):
        bare = _account(ottumwa, tag="d")
        customers_models.Address.objects.create(
            tenant=ottumwa, account=bare, kind="mailing", line1="1408 Elm St", country="USA"
        )
        held = customers_selectors.mailing_address_for_account(bare.id)
    assert held["missing"] == ["city", "state", "postal_code"]
    assert held["country"] == "USA", "a country does not make up for a missing postcode"


def test_def2847__the_billing_seam_carries_both_across_the_boundary(ottumwa):
    """The manifest is written from the seam's dataclass, not from the model, so
    the two fields have to survive one more hop (B1 — billing never imports
    customers)."""
    from apps.billing import customers_seam

    with tenant_ctx(ottumwa):
        account = _account(ottumwa, tag="e")
        customers_models.Address.objects.create(
            tenant=ottumwa,
            account=account,
            kind="mailing",
            line1="1408 Elm St",
            line2="Suite 200",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
            country="USA",
        )
        mailing = customers_seam.print_address_for_account(account.id)

    assert mailing.readable is True
    assert mailing.is_complete is True
    assert (mailing.line2, mailing.country) == ("Suite 200", "USA")
