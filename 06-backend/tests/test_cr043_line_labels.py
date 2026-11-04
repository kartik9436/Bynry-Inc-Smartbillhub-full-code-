# ── Trace ──────────────────────────────────────────────
# Story:    CR-043 finding 3 / DEF-937 — raw database keys in the two columns
#           that exist so a clerk can check the books.
#           Screens: BIL-02 Charges tab
# Rules:    BR-BIL-010 (the GL account is STAMPED at issue and never
#           re-resolved) · BR-RAT-007 (a bill prices on the version in force at
#           the service date) · DEF-206's standing rule (never print the raw key
#           at a person) · B1 (a cross-module read goes through the owner's
#           published selector)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The RESOLVED half of the two stamps — asserted against real rows.

`test_us_bil_025_026_bills_read.py` asserts the FALLBACK: an id whose label
cannot be resolved keeps its id, so a deleted chart row never blanks a column
headed ACCOUNTING CODE. That test passed throughout DEF-937, because its fixture
stamps ids that are not rows in any chart — which is exactly how a defect hides
behind a green suite.

So this file seeds a real `ledger_accounts` row and a real `tariff_versions`
row, stamps them on a line, and asks the selector what it serves.

RED-FIRST RECORD (hard-won law 7) — run against the tree before
`ledger.selectors.account_labels` and `rating.selectors.tariff_version_labels`
were published, the verbatim failures were:

    AssertionError: assert None == '4110'
    AssertionError: assert None is not None
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models, selectors
from apps.ledger import models as ledger_models, selectors as ledger_selectors
from apps.rating import models as rating_models, selectors as rating_selectors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def test_cr043_f3__the_ledger_publishes_labels_for_a_set_of_account_ids():
    """`apps.ledger.selectors.account_labels` — the seam DEF-937 needed."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # The tenant's chart is seeded at provisioning — this reads one of its
        # own rows rather than inventing a code, which is also what the bill
        # screen does.
        account = ledger_models.LedgerAccount.objects.filter(tenant=tenant).order_by("code").first()
        assert account is not None, "no chart seeded — this test would be vacuous"
        labels = ledger_selectors.account_labels([str(account.id)])

    assert labels == {str(account.id): {"code": account.code, "name": account.name}}
    # An id this tenant does not own is ABSENT, never another tenant's label and
    # never an exception (hard rule 1).
    with tenant_ctx(tenant):
        assert ledger_selectors.account_labels(["01a00000-0000-7000-8000-000000000000"]) == {}
        assert ledger_selectors.account_labels([]) == {}
        assert ledger_selectors.account_labels(None) == {}


def test_cr043_f3__a_deactivated_account_still_has_a_readable_name():
    """DEACTIVATED ROWS ARE INCLUDED, and that is the deliberate difference from
    `_live_accounts`. An account a tenant retired last month still has bills
    posted to it, and dropping the label would put the uuid back on exactly the
    bills that most need reading. Liveness gates POSTING, not reading a name."""
    from django.utils import timezone

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = ledger_models.LedgerAccount.objects.create(
            tenant=tenant,
            code="4900",
            name="Retired revenue",
            type="revenue",
            deleted_at=timezone.now(),
        )
        labels = ledger_selectors.account_labels([str(account.id)])

    assert labels[str(account.id)]["code"] == "4900"


def test_cr043_f3__rating_publishes_a_version_label_built_from_columns_it_has():
    """`tariff_version_labels` — the schedule and the date it took effect.

    NOT an ordinal: rating stores no "v3" and inventing one would print a number
    a clerk could not find anywhere else in the product.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        service = _any_service(tenant)
        tariff = rating_models.Tariff.objects.create(
            tenant=tenant, name="Sample — Water (Residential)", service=service
        )
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant, tariff=tariff, model="tiered", effective_from=date(2026, 6, 1)
        )
        draft = rating_models.TariffVersion.objects.create(
            tenant=tenant, tariff=tariff, model="tiered", effective_from=None
        )
        labels = rating_selectors.tariff_version_labels([str(version.id), str(draft.id)])

    assert labels[str(version.id)] == "Sample — Water (Residential) · from 2026-06-01"
    # BR-RAT-031's resumable draft has no window and can never have priced
    # anything. It labels as the schedule alone — VISIBLE rather than hidden,
    # because a bill line pointing at a draft version is a defect to see.
    assert labels[str(draft.id)] == "Sample — Water (Residential)"


def _any_service(tenant):
    from apps.tenancy import models as ten_models

    return ten_models.Service.objects.first()


def test_cr043_f3__the_bill_detail_serves_the_code_the_name_and_the_version():
    """END TO END, which is the only thing that would have caught DEF-937.

    Both seams can be published and correct while `invoice_line_row` still
    serves the hardcoded `None` it shipped with — that is precisely the state
    the product was in, since `ledger_accounts` had carried `code` and `name`
    for days.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = ledger_models.LedgerAccount.objects.filter(tenant=tenant).order_by("code").first()
        assert account is not None, "no chart seeded — this test would be vacuous"
        service = _any_service(tenant)
        tariff = rating_models.Tariff.objects.create(
            tenant=tenant, name="Sample — Water (Residential)", service=service
        )
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant, tariff=tariff, model="tiered", effective_from=date(2026, 6, 1)
        )
        line = billing_models.InvoiceLine(
            tenant_id=tenant.id,
            kind="usage",
            description="water usage tier 1 (0-5 kgal)",
            quantity=Decimal("5"),
            unit="kgal",
            unit_price=Decimal("4"),
            amount=Decimal("20"),
            taxable=True,
            gl_account_id=account.id,
            tariff_version_id=version.id,
        )
        gl_labels, version_labels = selectors._labels_for_lines([line])
        row = selectors.invoice_line_row(line, gl_labels=gl_labels, version_labels=version_labels)

    assert row["gl_account_code"] == account.code
    assert row["gl_account_name"] == account.name
    # NON-VACUOUS: a name that came back empty would satisfy the equality above
    # against an empty column, which is the shape of the defect this replaces.
    assert row["gl_account_code"] and row["gl_account_name"]
    assert row["tariff_version_label"] == "Sample — Water (Residential) · from 2026-06-01"
    # The STAMPS are untouched — the label is what the row is CALLED, never a
    # re-resolution of which account or version the line used (BR-BIL-010).
    assert row["gl_account_id"] == str(account.id)
    assert row["tariff_version_id"] == str(version.id)
