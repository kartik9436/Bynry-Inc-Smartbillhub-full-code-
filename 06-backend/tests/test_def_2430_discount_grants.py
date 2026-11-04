# ── Trace ──────────────────────────────────────────────
# Defects: DEF-2430 / DEF-BIL-5341 (no discount grant is recorded at issue, so
#          yearly caps, lifetime caps and budgets never count down) ·
#          DEF-RAT-9366 (the cap year had a start and no end)
# Ruling:  PO 2026-10-03, *"A · Yearly caps don't count down - a"* (decision log
#          "FOUR PO ANSWERS" (5))
# Rules:   BR-RAT-075 (caps and budgets are SUMS over discount_grants) ·
#          BR-RAT-068 (subsidy granted is reportable) · BR-RAT-007 (the service
#          date is the pivot) · hard rules 4 (corrections are new rows),
#          6 (idempotency), 7 (audit)
# ───────────────────────────────────────────────────────
"""DEF-2430 — an issued discount line records what it granted, and caps count down.

THE PO'S FIGURE. CAP credit $25.00 a bill under a $300.00 yearly cap, on an
$80.00 bill: eleven bills record $275.00, the twelfth takes the year to $300.00,
and the next bill IN THAT YEAR takes $0.00 off. The engine has always trimmed
correctly when told what was given (a $295.00 year leaves $5.00); what was
missing is the telling — nothing wrote a grant.

Each test below was run RED on the tip before the build (the field, the column,
the two rating writes and the seam did not exist) and is green after it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import issue, models, rating_seam
from apps.rating import discount_services
from apps.rating import discounts as dm

from tests.test_cr166_discounts_round2 import _bind, _discount, _home
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)


def an_account(actor, tenant):
    """An account whose unit is on Residential Standard since 01/01/2026 — the
    plan every discount below is bound to (ruling 2: only a plan that carries a
    discount lets it reach a bill)."""
    from apps.customers import models as customer_models

    _unit, account = _home(actor, tenant)
    account_id = account["id"] if isinstance(account, dict) else account.pk
    return customer_models.Account.objects.get(pk=account_id)


pytestmark = pytest.mark.django_db

D = Decimal
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)


def _cap(actor, code="CAP", value="25", cap_per_year="300"):
    from apps.tenancy import models as tenancy_models

    row = _discount(
        actor,
        code,
        value=value,
        start=date(2026, 1, 1),
        eligibility="household_income_limit",
        discount_type=dm.DISCOUNT_FIXED_AMOUNT,
        cap_per_year=cap_per_year,
    )
    _bind(actor, tenancy_models.Tenant.objects.get(pk=row.tenant_id), row)
    return row


def _enrol(tenant, discount, account):
    return dm.DiscountEnrolment.objects.create(
        tenant=tenant,
        discount=discount,
        account=account,
        enrolled_on=date(2026, 1, 1),
        verification_status=dm.VERIFICATION_VERIFIED,
        currency="USD",
    )


def _cap_left(account, day):
    (rule,) = [
        r for r in discount_services.discount_rules_for_account(account.id, day) if r.code == "CAP"
    ]
    return rule.cap_year_remaining


def _draft_with_cap_line(tenant, account, run, *, code="CAP", amount="25.00", invoice_no):
    draft = a_priced_draft(tenant, account, run, invoice_no=invoice_no)
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=draft,
        account=account,
        kind="discount",
        description="CAP credit",
        amount=-D(amount),
        taxable=False,
        discount_code=code,
    )
    draft.total = D(draft.total) - D(amount)
    draft.save(update_fields=["total"])
    return draft


def _issue(draft, actor):
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )


# ═══ the engine: the discount line names its programme ═══════════════════════
def test_def2430_the_engine_stamps_the_programme_code_on_the_discount_line():
    """RED before: `RatedLine` had no `discount_code`, so an issued bill could
    not say which enrolment its reduction spent."""
    water = rating_seam.TariffConfig(
        service="water",
        model="tiered",
        billed_unit="kgal",
        base_charge=D("8.00"),
        base_charge_code="BASE-W",
        tiers=(
            rating_seam.Tier(upper=D("10"), unit_price=D("4.20")),
            rating_seam.Tier(upper=None, unit_price=D("5.00")),
        ),
    )
    bill = rating_seam.price_bill(
        services=((water, rating_seam.Quantity(amount=D("16"), unit="kgal")),),
        period=PERIOD,
        account=rating_seam.AccountContext(currency="USD"),
        taxes=(),
        discounts=(
            rating_seam.DiscountRule(
                code="CAP",
                name="CAP credit",
                discount_type="fixed_amount",
                value=D("25"),
                currency="USD",
                applies_to="whole_bill",
                cap_year_remaining=D("300"),
            ),
        ),
    )
    (line,) = bill.lines_of("discount")
    assert (line.amount, line.discount_code, line.description) == (
        D("-25.00"),
        "CAP",
        "CAP credit",
    )
    assert bill.total == D("55.00")  # $80.00 − $25.00


# ═══ issue records the grant, and the cap counts down ═══════════════════════
def test_def2430_issuing_a_discounted_bill_records_one_grant_and_the_cap_counts_down(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cap = _cap(dana)
        enrolment = _enrol(brazos, cap, account)
        assert _cap_left(account, date(2026, 6, 30)) == D("300")

        bill = _issue(
            _draft_with_cap_line(
                brazos, account, an_authorised_run(brazos, dana), invoice_no="BL-2430-1"
            ),
            dana,
        )

        (grant,) = dm.DiscountGrant.objects.filter(enrolment=enrolment)
        assert grant.invoice_id == bill.pk
        assert D(grant.amount) == D("25.00")
        assert (grant.period_start, grant.period_end) == (
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        assert grant.discount_version.status == dm.VERSION_ACTIVE
        enrolment.refresh_from_db()
        assert D(enrolment.lifetime_subsidy_amount) == D("25.00")
        assert bill.grants.recorded == 1
        assert _cap_left(account, date(2026, 6, 30)) == D("275.00")
    granted_rows = [r for r in audit_rows if r["action"] == "discount.subsidy_granted"]
    assert [str(r["entity_id"]) for r in granted_rows] == [str(grant.id)]  # hard rule 7
    assert granted_rows[0]["after"]["amount"] == "25.000000"


def test_def2430_the_month_after_295_given_gets_5_and_after_300_gets_nothing(brazos, dana):
    """The PO's figure through the engine, from RECORDED grants: $295.00 given
    leaves $5.00; $300.00 given leaves $0.00, so a CAP bill takes $0.00 off."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cap = _cap(dana)
        _enrol(brazos, cap, account)
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id="00000000-0000-0000-0000-000000002430",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            service_date=date(2026, 5, 31),
            granted={"CAP": D("295.00")},
        )
        lines = (
            discount_services.discount_pricing.BillLine(
                service="water", kind="usage", amount=D("80.00")
            ),
        )
        outcome = discount_services.price_account_discounts(
            account.id, lines, on_day=date(2026, 6, 30)
        )
        assert outcome.total_reduction() == D("5.00")
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id="00000000-0000-0000-0000-000000002431",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=date(2026, 6, 30),
            granted={"CAP": D("5.00")},
        )
        outcome = discount_services.price_account_discounts(
            account.id, lines, on_day=date(2026, 7, 31)
        )
        assert outcome.total_reduction() == D("0")


def test_def2430_recording_the_same_bill_twice_counts_it_once(brazos, dana):
    """Hard rule 6: a replayed issue cannot count a subsidy twice."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cap = _cap(dana)
        enrolment = _enrol(brazos, cap, account)
        kwargs = dict(
            account_id=account.id,
            invoice_id="00000000-0000-0000-0000-000000002432",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=date(2026, 6, 30),
            granted={"CAP": D("25.00")},
        )
        first = discount_services.record_grants_for_invoice(dana, **kwargs)
        second = discount_services.record_grants_for_invoice(dana, **kwargs)
        assert (
            len(first["written"]),
            len(second["written"]),
            len(second["already_recorded"]),
        ) == (1, 0, 1)
        assert dm.DiscountGrant.objects.filter(enrolment=enrolment).count() == 1
        enrolment.refresh_from_db()
        assert D(enrolment.lifetime_subsidy_amount) == D("25.00")


def test_def_rat_9522_a_bill_whose_enrolment_ended_after_pricing_still_issues(
    brazos, dana, audit_rows
):
    """⚖️ PO 2026-10-04: *"We cannot hold the bill; we need to make discount value
    to 0 and move on - we cannot stop the billing"*. RED on 2.491.0: the bill
    stayed a DRAFT — *"holds no enrolment … Recalculate the bill"*. The bill
    issues as it was priced; the grant is recorded against the enrolment that
    priced it (ended since), so the cap still counts what was given, and the
    event is on the audit trail for a clerk."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        enrolment = _enrol(brazos, _cap(dana), account)
        enrolment.ended_on = date(2026, 6, 10)  # ended back-dated after pricing
        enrolment.save(update_fields=["ended_on"])
        bill = _issue(
            _draft_with_cap_line(
                brazos, account, an_authorised_run(brazos, dana), invoice_no="BL-2430-2"
            ),
            dana,
        )
        assert bill.status == models.INVOICE_ISSUED
        (grant,) = dm.DiscountGrant.objects.filter(invoice_id=bill.pk)
        assert grant.enrolment_id == enrolment.id and D(grant.amount) == D("25.00")
    assert "discount.grant_after_enrolment_ended" in [r["action"] for r in audit_rows]


def test_def_rat_9522_a_bill_naming_a_programme_never_held_still_issues(brazos, dana, audit_rows):
    """No enrolment in the programme at all: nothing to count against, so no
    grant — and the bill STILL issues (it stayed a draft on 2.491.0)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _cap(dana)  # the programme exists; this account was never enrolled
        bill = _issue(
            _draft_with_cap_line(
                brazos, account, an_authorised_run(brazos, dana), invoice_no="BL-2430-3"
            ),
            dana,
        )
        assert bill.status == models.INVOICE_ISSUED
        assert not dm.DiscountGrant.objects.exists()
        assert bill.grants.unrecorded == 1
    assert "discount.grant_unrecorded" in [r["action"] for r in audit_rows]


def test_def_rat_9367_a_run_shares_one_budget_across_its_accounts():
    """RED on 2.491.0: every account in a run was priced against the SAME
    remaining budget, so $45.00 left and two $10.00 accounts... in a run where
    $5.00 was left gave $5.00 to BOTH ($50.00 against $45.00). Each account is
    now priced on what is left after the accounts before it in the same run."""
    from apps.billing import runs

    rule = rating_seam.DiscountRule(
        code="FUND",
        name="Fund credit",
        discount_type="fixed_amount",
        value=D("10"),
        currency="USD",
        applies_to="whole_bill",
        budget_remaining=D("5.00"),
    )
    capped = rating_seam.DiscountRule(
        code="CAP",
        name="CAP credit",
        discount_type="fixed_amount",
        value=D("25"),
        currency="USD",
        applies_to="whole_bill",
    )
    first = runs.discounts_net_of_run_spend((rule, capped), {})
    second = runs.discounts_net_of_run_spend((rule, capped), {"FUND": D("5.00")})
    assert [r.budget_remaining for r in first] == [D("5.00"), None]
    assert [r.budget_remaining for r in second] == [D("0.00"), None]


# ═══ a correction gives the grant back — a NEW row, once ════════════════════
def test_def2430_a_correction_reverses_the_grant_once_and_the_cap_comes_back(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cap = _cap(dana)
        enrolment = _enrol(brazos, cap, account)
        invoice_id = "00000000-0000-0000-0000-000000002433"
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id=invoice_id,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=date(2026, 6, 30),
            granted={"CAP": D("25.00")},
        )
        assert _cap_left(account, date(2026, 6, 30)) == D("275.00")
        out = discount_services.reverse_grants_for_invoice(
            dana, invoice_id=invoice_id, reason="meter_read_error"
        )
        again = discount_services.reverse_grants_for_invoice(
            dana, invoice_id=invoice_id, reason="meter_read_error"
        )
        assert (len(out["reversed"]), len(again["reversed"])) == (1, 0)
        rows = list(
            dm.DiscountGrant.objects.filter(enrolment=enrolment).order_by("granted_at", "id")
        )
        assert [D(r.amount) for r in rows] == [D("25.00"), D("-25.00")]
        assert rows[1].reverses_grant_id == rows[0].id
        assert rows[1].period_end == rows[0].period_end  # the same cap year
        assert _cap_left(account, date(2026, 6, 30)) == D("300.00")
        enrolment.refresh_from_db()
        assert D(enrolment.lifetime_subsidy_amount) == D("0")


def test_def2430_a_correction_preview_prices_as_if_the_bill_had_granted_nothing(brazos, dana):
    """The preview must agree with the executed correction, which gives the
    grant back before pricing the rebill."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _enrol(brazos, _cap(dana), account)
        invoice_id = "00000000-0000-0000-0000-000000002434"
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id=invoice_id,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=date(2026, 6, 30),
            granted={"CAP": D("300.00")},
        )
        assert _cap_left(account, date(2026, 6, 30)) == D("0")
        with rating_seam.grants_excluded(invoice_id):
            assert _cap_left(account, date(2026, 6, 30)) == D("300")
        assert _cap_left(account, date(2026, 6, 30)) == D("0")


# ═══ DEF-RAT-9366 — the cap year has an end ═════════════════════════════════
def test_def_rat_9366_next_years_grant_is_not_counted_against_this_years_cap(brazos, dana):
    """RED before: `period_end >= 1 Jan` with no end — a 2027 grant reduced a
    re-priced 2026 bill's cap."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _enrol(brazos, _cap(dana), account)
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id="00000000-0000-0000-0000-000000002435",
            period_start=date(2027, 1, 1),
            period_end=date(2027, 1, 31),
            service_date=date(2027, 1, 31),
            granted={"CAP": D("25.00")},
        )
        assert _cap_left(account, date(2026, 12, 31)) == D("300")
        assert _cap_left(account, date(2027, 1, 31)) == D("275.00")


# ═══ hard rule 4, at the database (PostgreSQL only) ══════════════════════════
def test_def2430_a_grant_cannot_be_edited_or_deleted_on_postgresql(brazos, dana):
    if connection.vendor != "postgresql":
        pytest.skip("the append-only trigger is PostgreSQL's (rating/0065); SQLite has none")
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _enrol(brazos, _cap(dana), account)
        discount_services.record_grants_for_invoice(
            dana,
            account_id=account.id,
            invoice_id="00000000-0000-0000-0000-000000002436",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=date(2026, 6, 30),
            granted={"CAP": D("25.00")},
        )
        grant = dm.DiscountGrant.objects.get()
        for act in (
            lambda: dm.DiscountGrant.objects.filter(pk=grant.pk).update(amount=D("1")),
            lambda: dm.DiscountGrant.objects.filter(pk=grant.pk).delete(),
        ):
            with pytest.raises(DatabaseError, match="append-only"):
                with transaction.atomic():
                    act()


# ═══ DEF-BIL-9501 — a discounted bill's credit note balances ════════════════
def test_def_bil_9501_the_credit_note_of_a_discounted_bill_balances(brazos, dana):
    """RED before: every bucket of the original was reversed as a DEBIT,
    including the discount bucket that was itself a debit — *"UNBALANCED —
    debits 105.00 <> credits 55.00"* on an $80.00 bill with $25.00 off — so a
    discounted bill could never be corrected. The reversal is each bucket on
    the OPPOSITE of its own side."""
    from apps.billing import corrections
    from apps.ledger import chart as ledger_chart
    from apps.ledger import models as ledger_models
    from apps.ledger import selectors as ledger_selectors

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _enrol(brazos, _cap(dana), account)
        bill = _issue(
            _draft_with_cap_line(
                brazos, account, an_authorised_run(brazos, dana), invoice_no="BL-9501-1"
            ),
            dana,
        )
        note = models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            amount=-D(bill.total),
            currency="USD",
            reason="meter_read_error",
            issued_at=ISSUED_AT,
        )
        lines = list(models.InvoiceLine.objects.filter(invoice=bill).order_by("created_at", "id"))
        corrections.post_credit_note_reversal(
            note, invoice=bill, lines=lines, posted_at=ISSUED_AT, actor=dana
        )

        entry = ledger_models.JournalEntry.objects.get(tenant=brazos, source_type="credit_note")
        rows = list(
            ledger_models.JournalLine.objects.filter(journal_entry=entry).values_list(
                "ledger_account_id", "side", "amount"
            )
        )
        debits = sum(a for _i, s, a in rows if s == "debit")
        credits = sum(a for _i, s, a in rows if s == "credit")
        assert debits == credits
        discount_gl = ledger_selectors.gl_account_id_for_designation(
            ledger_chart.DISCOUNT_CONTRA_REVENUE
        )
        assert [(s, a) for i, s, a in rows if str(i) == str(discount_gl)] == [
            ("credit", D("25.00"))
        ]


# ═══ the details page reads what was recorded ═══════════════════════════════
def test_def2430_granted_this_month_and_an_accounts_this_month_read_the_grants(brazos, dana):
    """RED before: both were served `null` for ever (`DEF-2430` open)."""
    from apps.rating import discount_reads

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cap = _cap(dana)
        enrolment = _enrol(brazos, cap, account)
        for invoice_id, end, amount in (
            ("00000000-0000-0000-0000-000000002437", date(2026, 5, 31), "25.00"),
            ("00000000-0000-0000-0000-000000002438", date(2026, 6, 30), "25.00"),
        ):
            discount_services.record_grants_for_invoice(
                dana,
                account_id=account.id,
                invoice_id=invoice_id,
                period_start=end.replace(day=1),
                period_end=end,
                service_date=end,
                granted={"CAP": D(amount)},
            )
        assert discount_reads.granted_this_month(cap, date(2026, 6, 15)) == "$25.00"
        assert discount_reads.granted_this_month(cap, date(2026, 7, 15)) == "$0.00"
        from unittest import mock

        with mock.patch.object(
            discount_reads.seams, "tenant_today", return_value=date(2026, 6, 15)
        ):
            (row,) = discount_reads.discount_account_rows(
                [
                    type(
                        "R",
                        (),
                        {
                            "id": enrolment.id,
                            "account_id": account.id,
                            "account_number": None,
                            "plan_name": "x",
                            "enrolled_on": date(2026, 1, 1),
                            "recertification_due_on": None,
                            "row_status": "receiving",
                        },
                    )()
                ]
            )
        assert row["this_month"] == "$25.00"
