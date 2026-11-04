# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 C15 (widen the cost categories — but NOT to capital assets)
#           and C9/C15's T7c (exclude non-commodity costs from the recovery
#           denominator). Tasks T5 and T7c, and they belong together: T7c is a
#           FLAG on the category T5 introduces.
#           Screens: S73 (capture) · S74 (bought vs billed)
# Rules:    BR-LED-029 as AMENDED 2026-09-01 (sixteen categories in five
#           operating-statement groups; five capital names refused BY NAME,
#           pointing at the asset) · BR-LED-031 as AMENDED 2026-09-01 (the
#           exclusion is a per-category flag, not "is this code not a service")
#           · BR-LED-030 (the volume stays OPTIONAL — a volume on an excluded
#           category is INERT, never refused) · BR-LED-037/038 (a cost account
#           nobody signed seeds marked-unsigned and no surface presents it as
#           signed) · CLAUDE.md hard-won law 4 (a template change never reaches
#           a host already provisioned) · law 7 (prove the guard RED first)
# Golden:   LE-12 is UNMOVED by any of this — water 9.00%, electric 5.50%,
#           July's register footer $51,902.50, and the reconciliation still
#           reads FIVE rows and not nineteen.
# ───────────────────────────────────────────────────────
"""The widened cost vocabulary, the capital refusal, and the recovery flag.

**THE TWO TESTS THIS FILE EXISTS FOR** are
`test_t5__a_capital_category_is_refused_by_name_and_points_at_the_asset` and
`test_t7c__payroll_with_a_volume_never_enters_the_water_denominator`. Everything
else is the vocabulary and its plumbing; those two are the rules.

**WHY THE SECOND ONE KEYS A VOLUME ON PURPOSE.** The all-or-nothing rule
(BR-LED-031) protects the denominator against a MISSING volume. It cannot
protect it against a volume that is present and means something else — an hours
figure on contract services, a headcount on payroll. `chart.
enters_recovery_denominator` is what does, and this is the case that proves it,
because every check that reads only `purchases_missing_volume` passes over it.

**AND WHY A SYNTHETIC CATEGORY APPEARS BELOW.** The flag is False on all sixteen
real categories, so a test that only reads real ones would pass with the
function hard-wired to `return False` — a check that cannot fail. The mechanism
is driven from a category whose flag is True for the length of one test, exactly
as `test_us_led_017_cost_chart` drives the unsigned-account mechanism from a
synthetic unsigned code.

WHAT RUNS WHERE. Everything here runs on SQLite and PostgreSQL alike. Nothing in
this file catches a database error and continues, so hard-won law 14's savepoint
requirement does not arise — the one write path that could (the first-use mint)
inserts rows it has already confirmed are absent, inside the caller's atomic
block, and a duplicate would be a bug rather than a row to skip.
"""

from decimal import Decimal

import pytest

from apps.ledger import chart, cost_capture, cost_reconciliation, models as ledger_models
from apps.ledger import selectors as ledger_selectors
from apps.ledger import services as ledger_services

from tests.cost_of_service_fixtures import (
    ELECTRIC_PCT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    WATER_PCT,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.test_us_led_020_reconciliation import brazos_july
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# T5 — THE VOCABULARY. Sixteen categories, five groups, fourteen new accounts.
# ═══════════════════════════════════════════════════════════════════════════
def test_t5__the_vocabulary_covers_the_five_operating_statement_groups():
    """CR-060 §6's list, which is what a US utility operating statement prints.

    The failure this replaces is stated in the CR in one sentence: *"a tenant
    cannot record payroll, insurance, a legal bill, fuel or rent anywhere in
    this product"*, so the promise of one place was not true.
    """
    codes = set(chart.COST_CATEGORIES)
    assert len(chart.COST_CATEGORY_SPECS) == 16
    # The two that already existed keep their codes AND their accounts. Rows
    # point at them; renaming or re-coding either would orphan captured money.
    assert chart.COST_CATEGORIES[0] == chart.COST_CATEGORY_OM
    assert chart.COST_CATEGORIES[1] == "om_labour"
    assert chart.COST_CATEGORY_ACCOUNTS[chart.COST_CATEGORY_OM] == "5200"
    assert chart.COST_CATEGORY_ACCOUNTS[chart.COST_CATEGORY_INFRASTRUCTURE] == "5300"
    # The absences the CR names, each now present.
    for wanted in (
        "admin_payroll_benefits",
        "admin_insurance",
        "admin_professional_fees",
        "admin_office_rent",
        "admin_vehicles_fuel",
        "customer_billing_collection",
        "customer_postage_printing",
        "customer_meter_reading",
        "om_labour",
        "om_materials",
        "om_contract_services",
        "tax_property",
        "tax_franchise",
        "tax_payroll",
    ):
        assert wanted in codes, f"{wanted} is missing from the widened vocabulary"
    assert {spec.group for spec in chart.COST_CATEGORY_SPECS} == {
        chart.COST_GROUP_OM,
        chart.COST_GROUP_INFRASTRUCTURE,
        chart.COST_GROUP_CUSTOMER_ACCOUNTS,
        chart.COST_GROUP_ADMIN,
        chart.COST_GROUP_TAXES,
    }
    # One account per category, no code used twice, and none colliding with the
    # signed ladder or the meter-to-cash expense accounts.
    accounts = [spec.account_code for spec in chart.COST_CATEGORY_SPECS]
    assert len(accounts) == len(set(accounts))
    assert {"6800", "6900", "6950"}.isdisjoint(accounts)


def test_t5__payroll_is_labelled_so_nobody_mistakes_it_for_payroll_accounting():
    """CR-060 §6's ONE caution, carried as data rather than as a comment.

    *"A single figure is fine as a record of what left the bank … but it is not
    payroll accounting: the withholdings a utility holds back for the employee
    and remits to the government are a liability, and a one-line record does not
    carry them."* Hard-won law 1 — a comment claiming this is not the claim.
    """
    payroll = chart.COST_CATEGORY_BY_CODE["admin_payroll_benefits"]
    assert payroll.caution is not None
    assert "not payroll accounting" in payroll.caution
    assert "liability" in payroll.caution
    # And it is the only one, so the sentence stays worth reading.
    assert [s.code for s in chart.COST_CATEGORY_SPECS if s.caution] == [
        "admin_payroll_benefits"
    ]


def test_t5__the_fourteen_new_accounts_seed_unsigned_and_every_surface_says_so(
    brazos, dana, marcus
):
    """B5 line 74 is ❄️ FROZEN and carries NO cost accounts at all.

    So a cost account nobody signed seeds `signed=False`, lands in
    `PENDING_FINANCE_RE_SIGN_COST` and is offered MARKED — the route 4160/4170,
    4180 and 4300 each took. **This is what makes T5 landable without a finance
    re-sign**, and the marking is the price.
    """
    assert len(chart.WIDENED_COST_CHART) == 14
    assert [row.code for row in chart.WIDENED_COST_CHART if row.signed] == []
    assert set(chart.PENDING_FINANCE_RE_SIGN_COST) == {
        row.code for row in chart.WIDENED_COST_CHART
    }
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        # A re-run is a REPAIR run and creates nothing when the chart is whole,
        # so the assertion is on what is PRESENT, never on the created count —
        # provisioning has already seeded this tenant.
        ledger_services.seed_chart_of_accounts(dana)
        codes = set(
            ledger_models.LedgerAccount.objects.filter(
                tenant=brazos, deleted_at__isnull=True
            ).values_list("code", flat=True)
        )
        for spec in chart.COST_CATEGORY_SPECS:
            assert spec.account_code in codes, f"{spec.account_code} was not seeded"
        # And every one of the fourteen is marked, on the read the S73 picker
        # uses — offered, never hidden, never presented as finance-signed.
        offered = {row["code"]: row for row in ledger_selectors.cost_accounts()}
        for row in chart.WIDENED_COST_CHART:
            assert offered[row.code]["unsigned"] is True, (
                f"{row.code} is offered as finance-signed and nobody signed it"
            )


def test_t5__an_already_provisioned_tenant_gets_the_account_on_first_use(
    brazos, dana, marcus, audit_rows
):
    """**Hard-won law 4, and it is the reason this path exists at all.**

    `seed_chart_of_accounts` runs at provisioning and nowhere else. A tenant
    live before today would have been offered fourteen categories with no
    account in their chart to point at — the capture refuses, correctly, and
    tells them to pick an account that does not exist.

    So the account is minted on first use, and the audit row carries
    `finance_signed: False` because that is the row a finance reviewer reads.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        # The pre-CR-060 world: this tenant's chart has no 5510.
        ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code__in=[r.code for r in chart.WIDENED_COST_CHART]
        ).delete()
        assert not ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code="5510"
        ).exists()

        captured = cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=JULY_START,
            service="admin_insurance",
            supplier_name="Gulf Coast Mutual",
            amount=Decimal("2400.00"),
            currency="USD",
        )

        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5510")
        assert str(account.id) == str(captured["gl_account_id"])
        assert account.type == "expense"
        # US-LED-017 TC-5 — offered, and MARKED. Never presented as signed.
        assert cost_capture.UNSIGNED_ACCOUNT_NOTE in captured["problems"]

    # BR-LED-015 — a chart change audits, minted on first use as much as at
    # provisioning, and the trail says WHY the account appeared and whether
    # finance had signed it. **That flag is the row a finance reviewer reads**,
    # and this is the first time since the 2026-08-18 re-sign that it is False
    # on a real account rather than only on a synthetic one under test.
    rows_5510 = [
        row
        for row in audit_rows
        if row["action"] == "ledger_account.created"
        and row["after"]["code"] == "5510"
        and row["tenant_id"] == brazos.id
    ]
    # ⚠ There are TWO, and both are correct — which is the point of the
    # `source` field. Provisioning minted 5510 for this tenant and audited it
    # as `provisioning_seed`; the test then deleted the ROW to reproduce a
    # pre-CR-060 chart, and the audit trail is append-only so that first row
    # stays (hard rule 4 — the trail is not rewritten because a row was
    # removed). The capture then minted it again. **The trail therefore holds
    # the whole story and the sources tell the two apart**, which is exactly
    # what a finance reviewer scrolling it needs.
    by_source = {row["after"]["source"]: row for row in rows_5510}
    assert "cost_category_first_use" in by_source, (
        "the first-use mint wrote no audit row. The trail must distinguish an account "
        "minted at signup from one minted the first time a clerk used its category — the "
        "same event to a reader, different stories about why it appeared"
    )
    assert by_source["cost_category_first_use"]["after"]["finance_signed"] is False, (
        "the mint audited finance_signed=True for an account B5 line 74 does not contain. "
        "That flag is the row a finance reviewer reads"
    )


def test_t5__a_retired_account_is_not_resurrected_by_first_use(brazos, dana, marcus):
    """IS-1 deactivate-first, and seed rule 1: the code stays the tenant's.

    A tenant who retires 5510 has said stop using it. Minting it again on the
    next capture would undo that silently, so the capture asks for an account
    instead — the same answer a service with no proposed cost mirror gets.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        ledger_services.seed_chart_of_accounts(dana)
        retired = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5510")
        retired.deleted_at = retired.created_at
        retired.save()

        with pytest.raises(cost_capture.CostCaptureError) as refusal:
            cost_capture.capture_supplier_invoice(
                dana,
                invoice_date=JULY_START,
                service="admin_insurance",
                supplier_name="Gulf Coast Mutual",
                amount=Decimal("2400.00"),
                currency="USD",
            )
        assert "no GL account was given" in str(refusal.value)
        # Still retired. Nothing resurrected it.
        assert ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code="5510", deleted_at__isnull=True
        ).count() == 0


def test_t5__each_new_category_captures(brazos, dana, marcus):
    """Every one of the fourteen records a cost, against its own account."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        ledger_services.seed_chart_of_accounts(dana)
        for spec in chart.COST_CATEGORY_SPECS:
            captured = cost_capture.capture_supplier_invoice(
                dana,
                invoice_date=JULY_START,
                service=spec.code,
                supplier_name=f"Supplier for {spec.code}",
                amount=Decimal("100.00"),
                currency="USD",
            )
            account = ledger_models.LedgerAccount.objects.get(
                tenant=brazos, pk=captured["gl_account_id"]
            )
            assert account.code == spec.account_code, (
                f"{spec.code} defaulted to {account.code}, not {spec.account_code}"
            )
            # And capture still posts NOTHING (OQ-200 is untouched by T5).
            assert captured["posting"]["posted"] is False
        assert ledger_models.JournalLine.objects.filter(tenant=brazos).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# T5 — THE REFUSAL. Capital is refused BY NAME, pointing at the asset.
# ═══════════════════════════════════════════════════════════════════════════
def test_t5__a_capital_category_is_refused_by_name_and_points_at_the_asset(
    brazos, dana, marcus
):
    """**The test this half of the file exists for.**

    A $40,000 truck recorded as an expense overstates this year by $40,000,
    understates the next five years by the depreciation that never happens, and
    leaves the asset off the balance sheet. The refusal is the feature: a silent
    absence reads as a category nobody thought of, a named refusal reads as law
    and says where the money goes instead.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        ledger_services.seed_chart_of_accounts(dana)
        for capital in chart.CAPITAL_CATEGORIES:
            with pytest.raises(cost_capture.CostCaptureError) as refusal:
                cost_capture.capture_supplier_invoice(
                    dana,
                    invoice_date=JULY_START,
                    service=capital,
                    supplier_name="Brazos Fleet & Equipment",
                    amount=Decimal("40000.00"),
                    currency="USD",
                )
            message = str(refusal.value)
            assert capital in message, "the refusal must name the category"
            assert "asset" in message, "the refusal must point at the asset"
            assert refusal.value.br_ref == "BR-LED-029"
            # NOT the generic "unknown category" answer — that is the whole
            # point of refusing these BY NAME rather than by omission.
            assert "is not a cost category this tenant can capture against" not in message
        # No row was written by any of them.
        assert ledger_models.SupplierInvoice.objects.filter(tenant=brazos).count() == 0


def test_t5__depreciation_is_refused_for_its_own_reason(brazos, dana, marcus):
    """It is COMPUTED from the asset's life and book value; nobody invoices it.

    A different sentence from the truck's, deliberately — telling a clerk to
    "record depreciation on the asset" without saying it is computed there would
    send them looking for a field to type it into.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        ledger_services.seed_chart_of_accounts(dana)
        with pytest.raises(cost_capture.CostCaptureError) as refusal:
            cost_capture.capture_supplier_invoice(
                dana,
                invoice_date=JULY_START,
                service="depreciation",
                supplier_name="—",
                amount=Decimal("1200.00"),
                currency="USD",
            )
        message = str(refusal.value)
        assert "never invoiced" in message
        assert "book_value_amount" in message


def test_t5__running_a_vehicle_is_an_operating_cost_and_buying_one_is_not(
    brazos, dana, marcus
):
    """The two are separate names for exactly this reason.

    CR-060 §6 puts *vehicles and fuel* under Administrative & general and
    *capital spending* on the asset. Refusing both would leave a utility with
    nowhere to record a tank of diesel.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        ledger_services.seed_chart_of_accounts(dana)
        captured = cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=JULY_START,
            service="admin_vehicles_fuel",
            supplier_name="Rosenberg Fuel Co",
            amount=Decimal("640.25"),
            currency="USD",
        )
        assert captured["service"] == "admin_vehicles_fuel"
        with pytest.raises(cost_capture.CostCaptureError):
            cost_capture.capture_supplier_invoice(
                dana,
                invoice_date=JULY_START,
                service="vehicle_purchase",
                supplier_name="Rosenberg Truck Center",
                amount=Decimal("40000.00"),
                currency="USD",
            )


def test_t5__the_refusals_are_published_not_only_enforced():
    """A clerk who only ever meets a refusal after typing an invoice learns
    nothing. The picker can offer these as unavailable with their reason."""
    published = {row["code"]: row for row in cost_capture.refused_category_catalog()}
    assert set(published) == set(chart.CAPITAL_CATEGORIES)
    for row in published.values():
        assert row["record_on"] == "asset"
        assert len(row["reason"]) > 40
    # A readable name, served, so the picker never composes a second spelling
    # of one the backend already has. `.capitalize()`, never `.title()`
    # (decision log 2026-08-28, judgment 2 — `.title()` invents *Storm Water*).
    assert published["capital_assets"]["label"] == "Capital assets"
    assert published["plant_and_buildings"]["label"] == "Plant and buildings"


def test_t5__the_catalog_carries_the_grouping_and_keeps_the_flat_list(brazos, dana, marcus):
    """`categories` stays the contract; `category_catalog` is additive."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        enable_le11_services(dana)
        flat = cost_capture.cost_category_vocabulary()
        catalog = cost_capture.cost_category_catalog()
        assert [row["code"] for row in catalog] == list(flat)
        by_code = {row["code"]: row for row in catalog}
        assert by_code["water"]["group"] == "cost_of_service"
        # The SERVICE half reads as a name too, since 2026-09-01: the picker
        # showed a bare `water` beside "Payroll & benefits" otherwise, which
        # reads as two kinds of thing in one list.
        assert by_code["water"]["label"] == "Water"
        assert by_code["admin_payroll_benefits"]["label"] == "Payroll & benefits"
        assert by_code["water"]["enters_recovery_denominator"] is True
        assert by_code["admin_payroll_benefits"]["group_label"] == "Administrative & general"
        assert by_code["admin_payroll_benefits"]["enters_recovery_denominator"] is False
        assert by_code["admin_payroll_benefits"]["caution"] is not None
        # A capital name is NOT in the capturable catalog — it is refused, and
        # its reason is served on the other key.
        assert set(chart.CAPITAL_CATEGORIES).isdisjoint(by_code)


# ═══════════════════════════════════════════════════════════════════════════
# T7c — THE FLAG. Non-commodity costs never enter bought-versus-billed.
# ═══════════════════════════════════════════════════════════════════════════
def test_t7c__payroll_and_insurance_are_excluded_and_the_flag_is_the_reason():
    """The rule, read straight off the declaration."""
    assert chart.enters_recovery_denominator("admin_payroll_benefits") is False
    assert chart.enters_recovery_denominator("admin_insurance") is False
    # Every one of the sixteen, and a service is not one of them.
    assert set(chart.RECOVERY_DENOMINATOR_EXCLUDED) == set(chart.COST_CATEGORIES)
    assert chart.enters_recovery_denominator("water") is True
    assert chart.enters_recovery_denominator("electric") is True


def test_t7c__the_flag_is_read_and_not_decoration(monkeypatch):
    """**The mechanism, driven from a SYNTHETIC category whose flag is True.**

    The flag is False on all sixteen real categories, so a test reading only
    real ones would pass with the function hard-wired to `return False` — a
    check that cannot fail and reads as protection. Precedent:
    `test_us_led_017_cost_chart` keeps the unsigned-account mechanism alive the
    same way.
    """
    synthetic = chart.CostCategory(
        "synthetic_bulk_commodity", "5999", "Synthetic bulk commodity",
        chart.COST_GROUP_OM, "Operations & maintenance", True,
    )
    monkeypatch.setattr(
        chart, "COST_CATEGORY_BY_CODE", {**chart.COST_CATEGORY_BY_CODE, synthetic.code: synthetic}
    )
    assert chart.enters_recovery_denominator(synthetic.code) is True
    assert chart.enters_recovery_denominator("admin_payroll_benefits") is False


def test_t7c__payroll_with_a_volume_never_enters_the_water_denominator(
    brazos, dana, marcus
):
    """**The test this half of the file exists for.**

    BR-LED-030 keeps the volume optional and refuses nothing, so a clerk CAN key
    a figure on payroll — headcount, hours, anything. The all-or-nothing rule
    cannot see it: every purchase carries a volume, so `purchases_missing_volume`
    is zero and every check that reads only that number passes.

    The flag is what stops it. Water still reads **9.00%** and electric
    **5.50%**, unchanged, and payroll's own row carries no percentage at all.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        enable_le11_services(dana)
        ledger_services.seed_chart_of_accounts(dana)
        brazos_july(brazos, marcus)

        cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=JULY_START,
            service="admin_payroll_benefits",
            supplier_name="Brazos Bend WSC payroll",
            amount=Decimal("12000.00"),
            # ⚠ A VOLUME, ON PURPOSE. 160 hours is a real thing a clerk types.
            volume=Decimal("160"),
            volume_unit="hours",
            currency="USD",
        )
        cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=JULY_START,
            service="admin_insurance",
            supplier_name="Gulf Coast Mutual",
            amount=Decimal("2400.00"),
            currency="USD",
        )

        result = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
        rows = {row["service"]: row for row in result["rows"]}

        assert rows["water"]["unaccounted_for_pct"] == WATER_PCT
        assert rows["electric"]["unaccounted_for_pct"] == ELECTRIC_PCT

        payroll = rows["admin_payroll_benefits"]
        assert payroll["unaccounted_for_pct"] is None
        assert payroll["enters_recovery_denominator"] is False
        assert cost_reconciliation.NO_VOLUME_DENOMINATOR in payroll["problems"]
        # The volume IS kept on the row and the reason says it counts for
        # nothing — an inert figure with no explanation reads as a figure.
        assert "Administrative & general" in payroll["reason"]
        assert "enters no ratio" in payroll["reason"]
        assert payroll["bought_volume"] == Decimal("160")

        insurance = rows["admin_insurance"]
        assert insurance["unaccounted_for_pct"] is None
        assert cost_reconciliation.NO_VOLUME_DENOMINATOR in insurance["problems"]

        # And the money is not lost — it is in the footer, where it belongs.
        assert result["total_bought_cost"] == LE11_REGISTER_TOTAL + Decimal("14400.00")


def test_t7c__an_empty_category_gets_no_row_and_july_still_reads_seven(
    brazos, dana, marcus
):
    """Sixteen categories unioned unconditionally would make July 21 rows,
    fourteen of them empty — on the one screen whose value is worst-first.

    A SERVICE the tenant sells still always gets a row (workbook V-8), because
    the absence of a water purchase is information about water. The absence of a
    payroll run is not.

    ⚠ **SEVEN, NOT FIVE, AND THE DIFFERENCE IS WORTH ONE SENTENCE.** LE-12's
    illustration lists five rows because it prints only the rows carrying
    content; the SERVED table is the fixture's five services plus O&M plus
    Infrastructure. This asserts the served count, because a membership check
    alone would have passed on either number — which is how the wrong one gets
    quoted in a decision log.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        enable_le11_services(dana)
        ledger_services.seed_chart_of_accounts(dana)
        brazos_july(brazos, marcus)

        result = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
        codes = [row["service"] for row in result["rows"]]

        # O&M and Infrastructure are here because CI-8 and CI-9 are real
        # purchases in this window — not because they are hardcoded.
        assert chart.COST_CATEGORY_OM in codes
        assert chart.COST_CATEGORY_INFRASTRUCTURE in codes
        # And nothing nobody bought anything in.
        for spec in chart.COST_CATEGORY_SPECS:
            if spec.code in (chart.COST_CATEGORY_OM, chart.COST_CATEGORY_INFRASTRUCTURE):
                continue
            assert spec.code not in codes, f"{spec.code} got a row with no purchases"
        assert len(codes) == 7, f"the served table is {len(codes)} rows: {codes}"
        assert result["total_bought_cost"] == LE11_REGISTER_TOTAL


def test_t7c__an_excluded_category_never_reaches_the_billed_volume_read(
    brazos, dana, marcus, monkeypatch
):
    """The structural half: the flag decides which codes are even ASKED about.

    A category that reached `billed_volume_by_service` would be answered
    "unknown" and reported absent — the right answer for the wrong reason, and
    one line of drift away from being answered with somebody else's volume.
    """
    from apps.ledger import billing_seam

    asked: list[tuple[str, ...]] = []
    real = billing_seam.billed_volume_by_service

    def spy(*args, **kwargs):
        asked.append(tuple(kwargs.get("services") or ()))
        return real(*args, **kwargs)

    monkeypatch.setattr(billing_seam, "billed_volume_by_service", spy)

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        enable_le11_services(dana)
        ledger_services.seed_chart_of_accounts(dana)
        cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=JULY_START,
            service="admin_payroll_benefits",
            supplier_name="Brazos Bend WSC payroll",
            amount=Decimal("12000.00"),
            currency="USD",
        )
        cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)

    assert asked, "the billed read was never called"
    for services in asked:
        assert set(services).isdisjoint(chart.COST_CATEGORIES), (
            f"a non-commodity category reached the billed-volume read: {services}"
        )

