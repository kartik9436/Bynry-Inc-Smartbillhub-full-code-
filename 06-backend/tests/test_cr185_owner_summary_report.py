# ── Trace ──────────────────────────────────────────────
# Change:  CR-185-BRC10 D4 — the OWNER SUMMARY report. PO 2026-10-14: *"one
#          monthly statement with a section per property and a grand total of
#          $85. Each property's account keeps its own books, and they still pay
#          per property."*
# Code:    apps/reports/owner_summary.py · apps/billing/reporting.owner_bill_summary
#          · apps/customers/selectors.owner_properties · reports/0012
# ───────────────────────────────────────────────────────
"""Maple Rentals LLC, three properties, one statement.

The worked figure the PO was shown: **12 Oak St** — empty units **$15.00**,
common areas **$40.00**; **40 Elm Ave** — common areas **$30.00**; **9 Pine
Rd** — nothing billed in September → grand total **$85.00**. A bill issued in
August, a DRAFT, a VOID bill and another owner's bill must not reach it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.ledger import models as ledger_models
from apps.reports import catalogue_read, owner_summary, runner
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_premises, owner_for, tenant_ctx

pytestmark = pytest.mark.django_db

SEPTEMBER = {"from": "2026-09-01", "to": "2026-09-30"}
IN_SEPT = datetime(2026, 9, 5, 15, 0, tzinfo=dt_timezone.utc)
IN_AUG = datetime(2026, 8, 5, 15, 0, tzinfo=dt_timezone.utc)


def D(text: str) -> Decimal:
    return Decimal(text)


def _service(code):
    return tenancy_models.Service.objects.get(code=code)


def _master(tenant, actor, address, number):
    premises = make_premises(
        actor,
        address_line=address,
        premises_type="apartment_complex",
        owner_manager="Maple Rentals LLC",
        owner_id=owner_for(actor, "Maple Rentals LLC"),
        services_available=["electric", "water"],
    )
    return customer_models.Account.objects.create(
        tenant=tenant,
        kind="master",
        premises_id=premises["id"],
        account_no=number,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code="commercial"),
        opened_at=date(2025, 1, 1),
    )


def _holder(tenant, name, accounts):
    customer = customer_models.Customer.objects.create(
        tenant=tenant, kind="company", display_name=name
    )
    for account in accounts:
        customer_models.CustomerAccount.objects.create(
            tenant=tenant, customer=customer, account=account
        )
    return customer


def _bill(tenant, account, lines, *, issued_at=IN_SEPT, status=billing_models.INVOICE_ISSUED):
    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        service_date=date(2026, 8, 31),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        status=status,
        issued_at=issued_at,
        currency="USD",
    )
    for kind, description, amount, service in lines:
        billing_models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=invoice,
            account=account,
            service=_service(service),
            kind=kind,
            description=description,
            amount=D(amount),
        )
    return invoice


def _maple(tenant, actor):
    oak = _master(tenant, actor, "12 Oak St", "AC-2026-00051")
    elm = _master(tenant, actor, "40 Elm Ave", "AC-2026-00052")
    pine = _master(tenant, actor, "9 Pine Rd", "AC-2026-00053")
    _holder(tenant, "Maple Rentals LLC", [oak, elm, pine])
    # 12 Oak St — an empty unit's base ($15.00) and the common areas ($40.00).
    _bill(tenant, oak, [
        ("base", "Unit 2 · water base charge", "15.00", "water"),
        ("usage", "water usage", "30.00", "water"),
        ("base", "water base charge", "10.00", "water"),
    ])
    # 40 Elm Ave — common areas only ($30.00).
    _bill(tenant, elm, [("base", "electric base charge", "30.00", "electric")])
    # 9 Pine Rd — nothing that STANDS in September.
    _bill(tenant, pine, [("base", "electric base charge", "99.00", "electric")], issued_at=IN_AUG)
    _bill(tenant, pine, [("base", "electric base charge", "50.00", "electric")],
          status=billing_models.INVOICE_DRAFT, issued_at=None)
    _bill(tenant, pine, [("base", "electric base charge", "70.00", "electric")],
          status=billing_models.INVOICE_VOID)
    # Another owner's property, billed in September — must not reach Maple.
    birch = _master(tenant, actor, "7 Birch Ln", "AC-2026-00060")
    _holder(tenant, "Birch Holdings Inc", [birch])
    _bill(tenant, birch, [("base", "electric base charge", "500.00", "electric")])
    return oak, elm, pine, birch


def run(params):
    return runner.run(owner_summary.KEY, params).payload


def test_maple_three_properties_one_grand_total_of_85(brazos, dana):
    with tenant_ctx(brazos):
        oak, elm, pine, _birch = _maple(brazos, dana)
        payload = run({**SEPTEMBER, "subject_id": str(elm.id)})  # ANY of the owner's

        assert payload["columns"] == list(owner_summary.COLUMNS) or tuple(
            payload["columns"]
        ) == owner_summary.COLUMNS
        rows = {row["property"]: row for row in payload["rows"]}
        assert set(rows) == {"12 Oak St", "40 Elm Ave", "9 Pine Rd"}
        assert D(rows["12 Oak St"]["empty_units"]) == D("15.00")
        assert D(rows["12 Oak St"]["common_areas"]) == D("40.00")
        assert D(rows["12 Oak St"]["other_charges"]) == D("0")
        assert D(rows["12 Oak St"]["total"]) == D("55.00")
        assert D(rows["40 Elm Ave"]["common_areas"]) == D("30.00")
        assert D(rows["40 Elm Ave"]["total"]) == D("30.00")
        assert D(rows["9 Pine Rd"]["total"]) == D("0")
        assert rows["9 Pine Rd"]["bills"] == 0
        assert rows["12 Oak St"]["account"] == "AC-2026-00051"
        # B14 rule 31 — no uuid is a visible column.
        assert "account_id" not in payload["columns"]

        totals = payload["totals"]
        assert D(totals["total"]) == D("85.00")
        assert D(totals["empty_units"]) == D("15.00")
        assert D(totals["common_areas"]) == D("70.00")
        assert D(totals["other_charges"]) == D("0")
        assert totals["bills"] == 2
        kpis = {kpi["key"]: kpi for kpi in payload["kpis"]}
        assert D(kpis["grand_total"]["value"]) == D("85.00")
        assert kpis["properties"]["value"] == 3
        assert payload["head"]["fields"][0]["value"] == "Maple Rentals LLC"
        assert payload["basis"] == "posting"
        assert payload["controls"]["requires"] == [{"param": "subject_id", "finds": "owner"}]
        assert payload["controls"]["printable"] is True


def test_other_owner_charges_are_their_own_section(brazos, dana):
    with tenant_ctx(brazos):
        _oak, _elm, pine, _birch = _maple(brazos, dana)
        _bill(brazos, pine, [
            ("fee", "Late fee", "5.00", "electric"),
            ("tax", "Sales tax", "1.20", "electric"),
        ])
        payload = run({**SEPTEMBER, "subject_id": str(pine.id)})
        rows = {row["property"]: row for row in payload["rows"]}
        assert D(rows["9 Pine Rd"]["other_charges"]) == D("6.20")
        assert D(payload["totals"]["other_charges"]) == D("6.20")
        assert D(payload["totals"]["total"]) == D("91.20")


def test_the_grand_total_is_the_owners_not_the_pages(brazos, dana):
    """NFR-3: a page of two properties still totals all three."""
    with tenant_ctx(brazos):
        oak, _elm, _pine, _birch = _maple(brazos, dana)
        page_one = run({**SEPTEMBER, "subject_id": str(oak.id), "per": "2", "page": "1"})
        page_two = run({**SEPTEMBER, "subject_id": str(oak.id), "per": "2", "page": "2"})
        assert [r["property"] for r in page_one["rows"]] == ["12 Oak St", "40 Elm Ave"]
        assert [r["property"] for r in page_two["rows"]] == ["9 Pine Rd"]
        assert page_one["page"] == {"page": 1, "per": 2, "total": 3}
        assert D(page_one["totals"]["total"]) == D(page_two["totals"]["total"]) == D("85.00")
        # The export is every property, never the screen's page.
        exported = runner.rows_for(
            owner_summary.KEY, {**SEPTEMBER, "subject_id": str(oak.id)}, whole=True
        )
        assert len(list(exported)) == 3


def test_no_owner_named_reads_nothing_and_says_what_it_needs(brazos, dana):
    with tenant_ctx(brazos):
        _maple(brazos, dana)
        payload = run(dict(SEPTEMBER))
        assert payload["rows"] == []
        assert payload["unavailable"][0]["code"] == "an_owner_summary_names_one_owner"
        assert payload["controls"]["requires"][0]["finds"] == "owner"


def test_a_regular_account_is_not_an_owner(brazos, dana):
    with tenant_ctx(brazos):
        oak, *_ = _maple(brazos, dana)
        from tests.test_us_met_helpers import make_unit

        unit = make_unit(dana, oak.premises_id, label="Unit 9", services=["electric"])
        regular = customer_models.Account.objects.create(
            tenant=brazos,
            kind="regular",
            unit_id=unit["id"],
            premises_id=oak.premises_id,
            account_no="AC-2026-00099",
            status=customer_models.AccountStatus.objects.get(tenant=brazos, code="active"),
            account_type=customer_models.AccountType.objects.get(tenant=brazos, code="commercial"),
            opened_at=date(2025, 1, 1),
        )
        payload = run({**SEPTEMBER, "subject_id": str(regular.id)})
        assert payload["rows"] == []
        assert payload["unavailable"][0]["code"] == "the_account_is_not_an_owner_account"


def test_nothing_in_the_ledger_changes(brazos, dana):
    with tenant_ctx(brazos):
        oak, *_ = _maple(brazos, dana)
        before = ledger_models.JournalLine.objects.filter(tenant=brazos).count()
        run({**SEPTEMBER, "subject_id": str(oak.id)})
        assert ledger_models.JournalLine.objects.filter(tenant=brazos).count() == before


def test_the_card_is_in_the_library_and_available(brazos, dana):
    with tenant_ctx(brazos):
        payload = catalogue_read.catalogue_payload({"per": "100"})
        found = [card for card in payload["cards"] if card.get("key") == owner_summary.KEY]
        assert found, "owner_summary is not in the library"
        assert found[0]["available"] is True
        assert found[0]["group"] == "customers"
        assert found[0]["sub_group"] == "customers_statements"


def test_another_tenant_cannot_open_maples_summary(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        oak, *_ = _maple(brazos, dana)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            run({**SEPTEMBER, "subject_id": str(oak.id)})
