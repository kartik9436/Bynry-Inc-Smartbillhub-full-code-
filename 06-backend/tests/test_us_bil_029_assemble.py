# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (stage 6 of seven — the first stage that writes)
#           Screens: S31 · S30
# Rules:    BR-BIL-039 (only stage 6 writes) · BR-BIL-004 (a draft is
#           discardable; immutability starts at ISSUE) · BR-BIL-063 (the number
#           is allocated HERE, at draft creation — PO 2026-08-11; this header
#           said "minted at issue" until the US-BIL-005 lane found it stale,
#           and the body below already asserted the ruling) · BR-BIL-024 (the
#           due date is derived at issue)
#           · BR-BIL-010 (the GL account is stamped at issue and frozen) ·
#           BR-BIL-023 (drafts are discardable free) · CLAUDE.md rule 2/3
# ───────────────────────────────────────────────────────
"""Stage 6 writes a DRAFT — and the things it deliberately does not write.

Most of this file asserts ABSENCES, which is unusual and is the point. A draft
that already carries an invoice number has consumed a number the customer may
never see; one that carries a due date has dated a document that may never
exist; one that carries a GL stamp has recorded an accounting mapping that may
change before the bill is issued. Each of those is easy to add by accident and
invisible once added, because the resulting bill looks entirely normal.

The end-to-end case (`tc6`) runs the real chain — stage 1, stage 2, then
rating's own priced pass through the seam, then stage 6 — against GT-1's frozen
figures. If billing ever mangles what rating priced, the money in the database
stops matching the money finance signed.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.exceptions import BillingRuleError
from apps.billing.stages import assemble_document as stage6
from apps.billing.stages import measure_consumption as stage2
from apps.billing.stages import resolve_subscription as stage1

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)

# GT-1's frozen fixture: flat electric $0.12/kWh, base $18.50, 684 kWh, tax
# 8.25% on (usage + base) -> 82.08 + 18.50 = 100.58, tax 8.30, total 108.88.
GT1_TARIFF = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.12"),
)
GT1_USAGE = rating_seam.Quantity(amount=Decimal("684"), unit="kWh")
GT1_TAX = (rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),)
GT1_TOTAL = Decimal("108.88")


def billing_data(account, **overrides) -> AccountBillingData:
    values = dict(
        account_id=str(account.id),
        account_no=account.account_no,
        behavior_class=stage1.CLASS_BILLABLE,
        currency="USD",
        tax_exempt=False,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        service_days=30,
        rate_plan_id="plan-1",
        rate_plan_name="Residential Standard",
        rate_plan_version=3,
        tariffs=(GT1_TARIFF,),
        readings=(ServiceReading(service_code="electric", consumption=GT1_USAGE),),
        taxes=GT1_TAX,
        snapshot={
            "customer_name": "Sarah Chen",
            "service_address": "1901 Bluestem Ln, Unit A, Katy TX 77494",
        },
    )
    values.update(overrides)
    return AccountBillingData(**values)


def price(data: AccountBillingData):
    """The real chain: stage 1 -> stage 2 -> rating's priced pass (stages 3–5)."""
    subscription = stage1.resolve_subscription(data)
    usage = stage2.measure_consumption(subscription, data)
    measured = usage.measured[0]
    priced = rating_seam.price_period(
        tariff=measured.tariff,
        consumption=measured.consumption,
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=subscription.taxes,
    )
    return usage, priced


def assemble(tenant, account, run, data):
    usage, priced = price(data)
    return stage6.assemble_document(
        usage=usage,
        priced=priced,
        tenant_id=tenant.id,
        account_id=account.id,
        bill_run=run,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )


def test_us_bil_029_tc10__stage_6_writes_a_draft_and_nothing_more(brazos, dana):
    """BR-BIL-004/022/024/010 — what a draft deliberately does NOT carry.

    Each absence is easy to fill in by accident and invisible afterwards,
    because the bill looks entirely normal either way.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = assemble(brazos, account, run, billing_data(account))

        assert invoice.status == models.INVOICE_DRAFT
        # BR-BIL-063 (PO 2026-08-11) — the draft CARRIES its number, allocated
        # from the tenant series and rendered from the SERVICE date, so a June
        # bill drafted in July numbers as June's (BR-TEN-043's event-time law).
        assert invoice.invoice_no is not None
        assert invoice.invoice_no.startswith("BL-")
        assert invoice.due_date is None  # BR-BIL-024 — derived at issue
        assert invoice.issued_at is None
        for line in invoice.lines.all():
            assert line.gl_account_id is None  # BR-BIL-010 — stamped at issue


def test_us_bil_029_tc11__the_snapshot_is_frozen_at_pricing_not_at_issue(brazos, dana):
    """PO ruling 2026-08-11 — "keep lock data for that bill and save the instance".

    Sarah marries between the run and the release. The draft already holds the
    name the bill was priced under, so the release cannot print the new one on
    a period billed under the old.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = assemble(brazos, account, run, billing_data(account))

        snapshot = models.Invoice.objects.get(pk=invoice.pk).bill_payload
        assert snapshot["customer_name"] == "Sarah Chen"
        assert snapshot["plan"]["version"] == 3  # the version priced, not today's
        assert snapshot["service_address"].startswith("1901 Bluestem")
        assert snapshot["period"]["service_days"] == 30
        # A service that was not read must be VISIBLE on the document, not
        # silently omitted — the customer pays for it.
        assert snapshot["services"][0]["measured"] is True


def test_us_bil_029_tc12__re_running_replaces_the_draft_rather_than_doubling_it(brazos, dana):
    """A run interrupted and restarted must not bill an account twice.

    Legitimate ONLY because BR-BIL-023 makes a draft discardable free. The
    database itself refuses this treatment of an issued bill, which is what
    makes the distinction safe to rely on rather than remember.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        first = assemble(brazos, account, run, billing_data(account))
        second = assemble(brazos, account, run, billing_data(account))

        drafts = models.Invoice.objects.filter(account=account, bill_run=run)
        assert drafts.count() == 1
        assert drafts.first().pk == second.pk
        assert not models.Invoice.objects.filter(pk=first.pk).exists()
        # And the orphan lines went with it — a replaced draft leaving its
        # lines behind would double the bill's total on the next read.
        assert models.InvoiceLine.objects.filter(invoice_id=first.pk).count() == 0


def test_us_bil_029_tc13__a_currency_mismatch_refuses(brazos, dana):
    """CLAUDE.md rule 2 — money never changes currency between stages."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        data = billing_data(account)
        usage, priced = price(data)

        class Wrong:  # a priced bill claiming another currency
            currency = "EUR"
            lines = priced.lines
            taxable_subtotal = priced.taxable_subtotal
            tax_total = priced.tax_total
            total = priced.total

        with pytest.raises(BillingRuleError, match="rule 2"):
            stage6.assemble_document(
                usage=usage,
                priced=Wrong(),
                tenant_id=brazos.id,
                account_id=account.id,
                bill_run=run,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            )


def test_us_bil_029_tc14__an_unpriced_account_refuses_rather_than_drafting_zero(brazos, dana):
    """Nothing priced is not a $0.00 bill — it is an exception for a human."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        data = billing_data(account)
        usage, _ = price(data)

        with pytest.raises(BillingRuleError, match="exception list"):
            stage6.assemble_document(
                usage=usage,
                priced=None,
                tenant_id=brazos.id,
                account_id=account.id,
                bill_run=run,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            )


def test_us_bil_029_tc15__the_stored_bill_equals_the_frozen_gt1_figures(brazos, dana):
    """END TO END, against money finance signed.

    Stage 1 -> stage 2 -> rating's priced pass -> stage 6, then read back from
    the database. GT-1: 684 kWh at $0.12 = 82.08, base 18.50, tax 8.25% of
    100.58 = 8.30, total 108.88. If billing ever mangles what rating priced,
    the money in the database stops matching the money in B5.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = assemble(brazos, account, run, billing_data(account))

        stored = models.Invoice.objects.get(pk=invoice.pk)
        assert stored.total == GT1_TOTAL  # 108.88, frozen
        assert stored.subtotal == Decimal("100.58")
        assert stored.tax_total == Decimal("8.30")
        assert stored.currency == "USD"

        usage_lines = stored.lines.filter(kind="usage")
        assert usage_lines.count() == 1
        line = usage_lines.first()
        assert line.amount == Decimal("82.08")
        assert line.quantity == Decimal("684")
        assert line.unit == "kWh"  # rule 3 — survives from the meter to the row
        assert line.taxable is True

        assert stored.lines.filter(kind="base").first().amount == Decimal("18.50")
        assert stored.lines.filter(kind="tax").first().amount == Decimal("8.30")
        # The lines add up to the header. A bill whose lines do not foot is the
        # defect a customer finds with a calculator.
        assert sum((line.amount for line in stored.lines.all()), Decimal("0")) == GT1_TOTAL


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a stage) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED — see the commit for the mutations run
#         against tc10 (writing an invoice_no on a draft) and tc12 (creating
#         rather than replacing)
# exceptions: tc15 drives the REAL rating seam rather than a stub, so it fails
#         if either module's arithmetic moves — deliberate, but it means a
#         rating regression surfaces here as well as in the golden suite ·
#         does NOT cover issue (US-BIL-005): the due date, the GL stamp and the
#         template pin are that story's, and nothing here asserts them beyond
#         their ABSENCE from a draft. Issue mints NO number (BR-BIL-063 — this
#         line said "number minting" and was stale); tests/test_us_bil_005_issue.py
#         asserts the number is unchanged by issue
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
