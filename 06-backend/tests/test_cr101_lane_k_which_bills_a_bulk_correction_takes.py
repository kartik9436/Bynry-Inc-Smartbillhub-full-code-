# ── Trace ──────────────────────────────────────────────
# Change:   CR-101-BRC03 §06 lane K — the three PO rulings of 2026-09-15 about
#           WHICH BILLS a bulk correction takes.
# Rules:    BR-CUS-055 (billability is a CLASS, and customers owns it) ·
#           BR-TEN-065 (the run's selector already skips a closed account) ·
#           BR-BIL-018 + OQ-104 option A (the back-bill cap, UPWARD only,
#           theft exempt — unchanged; only the blast radius of its refusal
#           moves) · BR-BIL-1046 (NEW — the months are a consecutive run) ·
#           BR-BIL-014 (the five selectors) · NFR-3 · NFR-5 · CLAUDE.md rule 1
# Tests:    this file
# Impacts:  apps/billing/bulk_corrections.py · apps/billing/corrections.py ·
#           apps/customers/selectors.py (billable_accounts)
# ───────────────────────────────────────────────────────
"""Three rulings, one question: which bills does a bulk correction take?

`DEF-BIL-5377` · `DEF-BIL-5360` · `BR-BIL-1046`.

**Proved RED first (2026-09-15)** against the tip `a5374d48` extracted into a
scratch tree (`git archive a5374d48 06-backend`, this file copied in, the same
`pytest` from the same venv). The failures are quoted in
`04-docs/05-modules/07-billing/conformance/CR-101-BRC03-step2-06-lane-K-which-bills.md`.

⚠ **THE FIXTURES BUILD PERIODS BY HAND AND THAT IS THE POINT OF TWO OF THEM.**
`an_issued_bill` hardcodes July 2026, so every bill it makes is one period and
a contiguity test written on it would pass for the wrong reason — an account
with one period has no gap to find. `_bill_for_period` below is the same helper
with the period opened up, and it is local rather than a change to the shared
one because five other lanes read that file today.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import bulk_corrections, corrections, corrections_api, models
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_016_bulk_corrections import ISSUED_AT, _RatedBill, an_issued_bill
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _supplied_recompute(monkeypatch):
    """The recomputation is HANDED IN, as it is in every correction test here.

    `US-BIL-016`'s own file gives the reason and it holds exactly: the corrected
    figures are frozen in B5, the engine that produces them is asserted by the
    golden suite, and what THIS file tests is which bills a scope takes. The
    default moves money DOWN by a dollar, because a downward correction is
    never capped at any age (OQ-104 option A) — so a test that says nothing
    about the cap is not quietly relying on it.
    """
    monkeypatch.setattr(
        corrections, "recompute", lambda invoice: _RatedBill([], invoice.total - Decimal("1.00"))
    )


@pytest.fixture
def priced(monkeypatch):
    """Re-point the recomputation at a named delta for one test."""

    def apply(delta: Decimal):
        monkeypatch.setattr(
            corrections, "recompute", lambda invoice: _RatedBill([], invoice.total + delta)
        )

    return apply


def _with_status(tenant, account, code: str):
    """Point an account at a NAMED seeded status.

    ⚠ **A queryset `update`, never `save()`.** Moving an account's status
    through the model fires the notification signal, which dispatches to a
    broker this suite does not run; the fixture wants the ROW in a state, not
    the act of moving it, and that act is `customers.disconnects`' own suite to
    prove.
    """
    from apps.customers import models as customer_models

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code=code)
    customer_models.Account.objects.filter(pk=account.pk).update(status=status)
    account.refresh_from_db()
    return account


def _billable_account(actor, tenant, *, account_no):
    """An account that is explicitly **Active**, and the explicitly is the point.

    `an_account` takes `AccountStatus.objects.filter(tenant=tenant).first()`
    and `AccountStatus` declares no `Meta.ordering`, so *first* is whatever the
    database hands back — which on this tenant is a `pending_activation` row,
    behaviour class `non_billable`. Every test in this file turns on whether an
    account is in the billable set, so a fixture that does not SAY which set it
    is in would pass or fail on row order. Found the hard way: the first run of
    this file resolved ZERO bills where it expected one.
    """
    return _with_status(tenant, an_account(actor, tenant, account_no=account_no), "active")


def _closed_account(actor, tenant, *, account_no="A-CLOSED-1"):
    """An account whose status is in the TERMINAL behaviour class.

    Built by pointing the account at the seeded `closed` status rather than by
    walking the disconnect flow: this file is about which bills a SCOPE takes,
    and the fact it turns on is the behaviour CLASS, which is what BR-CUS-055
    says billing keys off and what a tenant renaming the label does not move.
    """
    return _with_status(tenant, an_account(actor, tenant, account_no=account_no), "closed")


def _bill_for_period(tenant, account, run, *, invoice_no, start: date, end: date):
    """One ISSUED bill over a NAMED period. No lines — nothing here prices."""
    return models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=invoice_no,
        service_date=end,
        period_start=start,
        period_end=end,
        status=models.INVOICE_ISSUED,
        issued_at=ISSUED_AT,
        bill_type="cycle",
        subtotal=Decimal("100.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("100.00"),
        template_id="11111111-1111-1111-1111-111111111111",
        template_version=1,
        bill_payload={"account_no": account.account_no},
        payload_version=1,
    )


def _months(year: int, month: int) -> tuple[date, date]:
    """The first and last day of one calendar month."""
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1) - _one_day()
    return start, end


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════════════
# RULING 1 — a bulk correction selects its accounts the way a bulk RUN does
# PO 2026-09-15: *"you will not select the bill/account in first place ; our
# rule to selct account will apply - we do this at the time of bulk billing
# also"*.  `DEF-BIL-5377`
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_k_tc1__a_closed_account_s_bill_is_not_swept_into_a_bulk_scope(brazos, dana):
    """One closed account stopped seventy-nine bills. Now it is simply not there.

    Measured on the demo tenant before the fix: a class-R case over cycle
    `CY-001` refused all **79** bills with *"account 'AC-2026-00042' is not in
    the billable set for its unit"*. After: **77**, and the case opens.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K1")
        live = _billable_account(dana, brazos, account_no="A-LIVE-1")
        closed = _closed_account(dana, brazos)
        an_issued_bill(brazos, live, run, invoice_no="BL-K1-000001")
        an_issued_bill(brazos, closed, run, invoice_no="BL-K1-000002")

        resolved = bulk_corrections.resolve_scope(kind="run", bill_run_id=str(run.pk))

    assert [one.invoice_no for one in resolved] == ["BL-K1-000001"], (
        "the closed account's bill is not in the billable set, so the scope never "
        "offers it — the fix is at SELECTION, not at the refusal"
    )


def test_lane_k_tc2__the_case_opens_over_the_rest_instead_of_refusing_them_all(brazos, dana):
    """The defect itself: the whole case died because one account was closed."""
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K2")
        live = _billable_account(dana, brazos, account_no="A-LIVE-2")
        closed = _closed_account(dana, brazos, account_no="A-CLOSED-2")
        an_issued_bill(brazos, live, run, invoice_no="BL-K2-000001")
        an_issued_bill(brazos, closed, run, invoice_no="BL-K2-000002")

        case = bulk_corrections.open_case(
            reason_codes=("wrong_read",),
            scope_kind="run",
            scope={"bill_run_id": str(run.pk)},
            invoices=bulk_corrections.resolve_scope(kind="run", bill_run_id=str(run.pk)),
            actor=dana,
            as_of=date(2026, 8, 15),
        )
        assert len(case.preview["bills"]) == 1
        assert case.preview["bills"][0]["invoice_no"] == "BL-K2-000001"
        assert case.preview["excluded"] == [], (
            "the closed account's bill never reached the case, so it is not an "
            "EXCLUSION either — it was never in the scope to be excluded from it"
        )


def test_lane_k_tc3__a_clerk_who_picks_that_bill_directly_may_still_correct_it(brazos, dana):
    """The PO's own carve-out, recorded with the ruling and asserted here.

    *"The ruling narrows what a SCOPE sweeps up, never what a clerk may correct
    on purpose."* A utility may have overbilled somebody who has since left,
    and refusing that for ever would be wrong.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K3")
        closed = _closed_account(dana, brazos, account_no="A-CLOSED-3")
        bill = an_issued_bill(brazos, closed, run, invoice_no="BL-K3-000001")

        by_scope = bulk_corrections.resolve_scope(kind="run", bill_run_id=str(run.pk))
        by_hand = bulk_corrections.resolve_scope(kind="single", invoice_ids=(str(bill.pk),))

    assert by_scope == (), "a SCOPE does not sweep a closed account up"
    assert [one.invoice_no for one in by_hand] == ["BL-K3-000001"], (
        "a clerk naming the BILL still gets it — the single path is untouched"
    )


def test_lane_k_tc4__the_step_1_table_and_the_case_answer_the_same_question(brazos, dana):
    """Not a silent filter: the table a clerk reads is the same one filter.

    The ruling's second caveat — an excluded bill is *"visibly not there rather
    than dropped behind their back"*. There is one selector, so the table's
    totals and the case's pinned count cannot disagree; this asserts the
    equality rather than the shared line of code, because the shared line can
    be un-shared by the next lane and the equality cannot.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K4")
        live = _billable_account(dana, brazos, account_no="A-LIVE-4")
        closed = _closed_account(dana, brazos, account_no="A-CLOSED-4")
        an_issued_bill(brazos, live, run, invoice_no="BL-K4-000001")
        an_issued_bill(brazos, live, run, invoice_no="BL-K4-000002")
        an_issued_bill(brazos, closed, run, invoice_no="BL-K4-000003")

        # The scope FIRST, the API second: `api_call` opens and then CLOSES a
        # tenant context of its own, which leaves `app.tenant_id` unset for
        # anything that follows it inside this block. Reading the queryset
        # afterwards refused with AUTH-003 and looked like a tenancy bug in the
        # code under test rather than in the test's own ordering.
        pinned = bulk_corrections.resolve_scope(kind="run", bill_run_id=str(run.pk))
        response = api_call(
            corrections_api.correction_scope_resolve,
            "get",
            user=dana.user,
            role="billing_clerk",
            tenant=brazos,
            query={"scope_kind": "run", "bill_run_id": str(run.pk)},
        )

    assert response.status_code == 200, response.data
    assert response.data["totals"]["bills"] == 2 == len(pinned)
    assert [row["invoice_no"] for row in response.data["results"]] == [
        "BL-K4-000001",
        "BL-K4-000002",
    ]
    assert bulk_corrections.EXCLUDED_ACCOUNT_NOT_BILLABLE in response.data["narrowed_by"], (
        "a declared blind spot with no number beside it is indistinguishable from an "
        "empty one — the table says WHICH narrowings ran (hard-won law 7)"
    )


def test_lane_k_tc5__a_single_scope_is_narrowed_by_neither_rule_and_says_so(brazos, dana):
    """`narrowed_by` is empty for `single`, and that is the honest answer."""
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K5")
        account = _billable_account(dana, brazos, account_no="A-LIVE-5")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-K5-000001")
        response = api_call(
            corrections_api.correction_scope_resolve,
            "get",
            user=dana.user,
            role="billing_clerk",
            tenant=brazos,
            query={"scope_kind": "single", "invoice_id": str(bill.pk)},
        )
    assert response.status_code == 200, response.data
    assert response.data["narrowed_by"] == []


def test_lane_k_tc5b__a_caller_that_does_not_say_which_scope_is_told_so(brazos, dana):
    """An unstated scope kind reads as UNKNOWN, never as *"nothing was narrowed"*.

    `scope_table`'s `scope_kind` defaulted to `single` when it was first
    written, so a caller that simply forgot it was told no narrowing had run —
    a confident, wrong answer over a queryset that had in fact been narrowed.
    Under-reporting is the dangerous direction here, and this is hard-won law
    7's fifth shape applied to a function written to satisfy it.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K5b")
        account = _billable_account(dana, brazos, account_no="A-LIVE-5B")
        an_issued_bill(brazos, account, run, invoice_no="BL-K5B-000001")
        queryset = bulk_corrections.resolve_scope_queryset(kind="run", bill_run_id=str(run.pk))
        silent = bulk_corrections.scope_table(tuple(queryset), queryset=queryset)
    assert silent["narrowed_by"] == [bulk_corrections.NARROWING_NOT_STATED]
    assert silent["narrowed_by"] != [], "an unknown answer must not read as an empty one"


def test_lane_k_tc6__billing_asks_customers_and_refuses_when_nobody_answers(brazos, dana, monkeypatch):
    """The rule is customers' and billing keeps no copy of it.

    If the seam disappears the scope REFUSES. The alternative — carry on
    unfiltered — is `DEF-BIL-5377` restored silently on the day somebody
    renames a selector, and hard-won law 1 is that a comment claiming a
    guarantee is not the guarantee.
    """
    from apps.customers import selectors as customer_selectors

    monkeypatch.delattr(customer_selectors, "billable_accounts")
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-K6")
        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.resolve_scope(kind="run", bill_run_id=str(run.pk))
    assert "billable_accounts" in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
# RULING 2 — the capped month is EXCLUDED; the rest of the case proceeds
# PO 2026-09-15: *"in such sitution 6 bills only ; 7th is not valid case"*.
# `DEF-BIL-5360`
# ═══════════════════════════════════════════════════════════════════════════
def _seven_months(brazos, dana, *, account_no, key):
    """Seven monthly bills, January–July 2026 — the PO's own shape.

    Which of them is past the cap is decided by the `as_of` each test passes,
    never by this fixture: `BR-TEN-043` makes the day an argument, so a test
    that wants one month outside the window moves the DAY rather than the
    bills.
    """
    account = _billable_account(dana, brazos, account_no=account_no)
    run = a_run(brazos, key=key)
    bills = []
    for index, month in enumerate((1, 2, 3, 4, 5, 6, 7), start=1):
        start, end = _months(2026, month)
        bills.append(
            _bill_for_period(
                brazos,
                account,
                run,
                invoice_no=f"BL-{key[-2:]}-{index:06d}",
                start=start,
                end=end,
            )
        )
    return account, run, bills


def test_lane_k_tc7__six_bills_proceed_and_the_seventh_is_named_with_its_reason(
    brazos, dana, priced
):
    """*"in such sitution 6 bills only ; 7th is not valid case"*, worked.

    Seven monthly periods **January–July 2026**, judged on **15 February 2027**
    against the tenant's default **12-month** window. January ended 13 months
    before, so January is the seventh and February is inside at exactly 12 —
    which is p137's *"Beyond the 12-month cap"* drawn as a real case. Before
    today the whole case refused and a clerk got NOTHING, including the six
    months that were lawful.
    """
    priced(Decimal("40.00"))
    with tenant_ctx(brazos):
        account, run, bills = _seven_months(brazos, dana, account_no="A-CAP-1", key="2026-07|K7")

        case = bulk_corrections.open_case(
            reason_codes=("missed_charge",),
            scope_kind="date_range",
            scope={"period_start": "2026-01-01", "period_end": "2026-07-31"},
            invoices=tuple(bills),
            actor=dana,
            as_of=date(2027, 2, 15),
        )

    kept = [one["invoice_no"] for one in case.preview["bills"]]
    excluded = case.preview["excluded"]
    assert len(kept) == 6, f"six bills only; got {kept}"
    assert len(excluded) == 1, "and the seventh is not a valid case"
    seventh = excluded[0]
    assert seventh["code"] == corrections.BEYOND_BACKBILL_WINDOW
    assert seventh["months"] == 13 and seventh["window_months"] == 12
    assert seventh["period_end"] == "2026-01-31"
    assert Decimal(seventh["delta"]) == Decimal("40.00") and seventh["currency"] == "USD"
    assert "BR-BIL" not in str(excluded), (
        "the excluded rows carry CODES and figures; the words a clerk reads are the "
        "catalogue's and carry no rule id (B14 rule 32)"
    )


def test_lane_k_tc8__when_nothing_survives_the_case_refuses_and_says_why(brazos, dana, priced):
    """One bill, and it is the 7th month — so *"the 7th is not valid case"*.

    The blast radius moved from the case to the bill; where the case IS one
    bill the two coincide, which is why the single-bill path needs no branch of
    its own and gets the same sentence it always got.
    """
    priced(Decimal("40.00"))
    with tenant_ctx(brazos):
        account = _billable_account(dana, brazos, account_no="A-CAP-2")
        run = a_run(brazos, key="2026-07|K8")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-K8-000001")
        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.open_case(
                reason_codes=("missed_charge",),
                scope_kind="date_range",
                scope={},
                invoices=(bill,),
                actor=dana,
                as_of=date(2029, 1, 31),
            )
    assert "back-bill window" in str(refusal.value)
    assert "12-month" in str(refusal.value), "the window is named in figures, as it always was"
    assert refusal.value.br_ref == "BR-BIL-018", "the API maps this exactly as before"


def test_lane_k_tc9__a_downward_correction_of_the_same_aged_bills_is_untouched(
    brazos, dana, priced
):
    """The asymmetry IS the ruling (OQ-104 option A), and it did not move.

    Same seven bills, same aged `as_of`, prices going DOWN — nothing excluded.
    """
    priced(Decimal("-40.00"))
    with tenant_ctx(brazos):
        account, run, bills = _seven_months(brazos, dana, account_no="A-CAP-3", key="2026-07|K9")
        case = bulk_corrections.open_case(
            reason_codes=("wrong_read",),
            scope_kind="date_range",
            scope={},
            invoices=tuple(bills),
            actor=dana,
            as_of=date(2029, 1, 31),
        )
    assert case.preview["excluded"] == []
    assert len(case.preview["bills"]) == 7


# ═══════════════════════════════════════════════════════════════════════════
# RULING 3 — the months are a CONSECUTIVE run (`BR-BIL-1046`, new)
# PO 2026-09-15: *"we take consicative bills ; not like in 24 months - latest
# 12 and then 18 one - 18th is not valid and it will not be taken into
# processing at all"*.
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_k_tc10__the_bill_before_a_gap_is_not_offered_at_all(brazos, dana):
    """The PO's own example, at the shape a 24-month window produces.

    The account has bills for **February 2025** and then for **January–December
    2026**, so 2025 sits behind an eleven-month hole. A date range over both
    takes the twelve and does not offer the one — *"18th is not valid and it
    will not be taken into processing at all"*.
    """
    with tenant_ctx(brazos):
        account = _billable_account(dana, brazos, account_no="A-GAP-1")
        run = a_run(brazos, key="2026-07|K10")
        old_start, old_end = _months(2025, 2)
        _bill_for_period(
            brazos, account, run, invoice_no="BL-K10-000001", start=old_start, end=old_end
        )
        for month in range(1, 13):
            start, end = _months(2026, month)
            _bill_for_period(
                brazos,
                account,
                run,
                invoice_no=f"BL-K10-{month + 1:06d}",
                start=start,
                end=end,
            )
        resolved = bulk_corrections.resolve_scope(
            kind="date_range",
            period_start=date(2025, 1, 1),
            period_end=date(2026, 12, 31),
        )

    numbers = [one.invoice_no for one in resolved]
    assert len(numbers) == 12, f"the twelve consecutive months, and only those: {numbers}"
    assert "BL-K10-000001" not in numbers, "February 2025 is behind a gap"


def test_lane_k_tc11__an_unbroken_run_is_taken_whole(brazos, dana):
    """The rule must not fire on an ordinary account, which is every account.

    Twelve consecutive monthly periods, all twelve taken. Written because a
    contiguity rule that excludes something on a healthy account is worse than
    no rule at all: it would silently shrink every bulk correction in the
    product and nothing on screen would say so.
    """
    with tenant_ctx(brazos):
        account = _billable_account(dana, brazos, account_no="A-GAP-2")
        run = a_run(brazos, key="2026-07|K11")
        for month in range(1, 13):
            start, end = _months(2026, month)
            _bill_for_period(
                brazos, account, run, invoice_no=f"BL-K11-{month:06d}", start=start, end=end
            )
        resolved = bulk_corrections.resolve_scope(
            kind="date_range", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
        )
    assert len(resolved) == 12


def test_lane_k_tc12__a_quarterly_account_is_consecutive_at_ninety_day_steps(brazos, dana):
    """The gap is measured against the PERIOD, never against the calendar.

    A cycle in this product may be Daily · Weekly · Fortnightly · Monthly ·
    Bimonthly · Quarterly · Semiannual or Annual, so a *"one month"* threshold
    would read every quarterly account as one long gap and refuse corrections
    nobody asked to refuse. Four abutting quarters are ONE run; skipping the
    third quarter makes the first two a gap away.
    """
    with tenant_ctx(brazos):
        account = _billable_account(dana, brazos, account_no="A-GAP-3")
        run = a_run(brazos, key="2026-07|K12")
        quarters = [
            (date(2026, 1, 1), date(2026, 3, 31)),
            (date(2026, 4, 1), date(2026, 6, 30)),
            (date(2026, 7, 1), date(2026, 9, 30)),
            (date(2026, 10, 1), date(2026, 12, 31)),
        ]
        for index, (start, end) in enumerate(quarters, start=1):
            _bill_for_period(
                brazos, account, run, invoice_no=f"BL-K12-{index:06d}", start=start, end=end
            )
        whole = bulk_corrections.resolve_scope(
            kind="date_range", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
        )
    assert len(whole) == 4, "four abutting quarters are one unbroken run"

    with tenant_ctx(brazos):
        models.Invoice.objects.filter(tenant=brazos, invoice_no="BL-K12-000003").delete()
        gapped = bulk_corrections.resolve_scope(
            kind="date_range", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
        )
    assert [one.invoice_no for one in gapped] == ["BL-K12-000004"], (
        "a missing quarter is a gap, so only the quarter after it is taken"
    )


def test_lane_k_tc13__one_account_s_gap_does_not_shrink_another_s_run(brazos, dana):
    """Contiguity is per ACCOUNT. Two accounts in one scope, judged separately."""
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|K13")
        gapped = _billable_account(dana, brazos, account_no="A-GAP-4")
        whole = _billable_account(dana, brazos, account_no="A-GAP-5")
        for month in (1, 5, 6):
            start, end = _months(2026, month)
            _bill_for_period(
                brazos, gapped, run, invoice_no=f"BL-K13-G{month:05d}", start=start, end=end
            )
        for month in (1, 2, 3):
            start, end = _months(2026, month)
            _bill_for_period(
                brazos, whole, run, invoice_no=f"BL-K13-W{month:05d}", start=start, end=end
            )
        resolved = bulk_corrections.resolve_scope(
            kind="date_range", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
        )
    numbers = sorted(one.invoice_no for one in resolved)
    assert numbers == [
        "BL-K13-G00005",
        "BL-K13-G00006",
        "BL-K13-W00001",
        "BL-K13-W00002",
        "BL-K13-W00003",
    ], f"only the gapped account loses its January: {numbers}"


def test_lane_k_tc14__a_clerk_naming_one_bill_behind_a_gap_still_gets_it(brazos, dana):
    """Same carve-out as ruling 1, and for the same reason: a SCOPE filters."""
    with tenant_ctx(brazos):
        account = _billable_account(dana, brazos, account_no="A-GAP-6")
        run = a_run(brazos, key="2026-07|K14")
        old_start, old_end = _months(2025, 2)
        old = _bill_for_period(
            brazos, account, run, invoice_no="BL-K14-000001", start=old_start, end=old_end
        )
        start, end = _months(2026, 6)
        _bill_for_period(brazos, account, run, invoice_no="BL-K14-000002", start=start, end=end)
        by_hand = bulk_corrections.resolve_scope(kind="single", invoice_ids=(str(old.pk),))
    assert [one.invoice_no for one in by_hand] == ["BL-K14-000001"]


# ═══════════════════════════════════════════════════════════════════════════
# The arithmetic of the gap test, on its own — no database
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "earlier_end,later_start,shortest,consecutive,why",
    [
        (date(2026, 8, 31), date(2026, 9, 1), 31, True, "monthly, abutting"),
        (date(2026, 8, 31), date(2026, 10, 1), 31, False, "a whole month missing"),
        (date(2026, 8, 31), date(2026, 9, 3), 31, True, "two days of move-in wobble"),
        (date(2026, 3, 31), date(2026, 4, 1), 90, True, "quarterly, abutting"),
        (date(2026, 3, 31), date(2026, 7, 1), 90, False, "a whole quarter missing"),
        (date(2026, 8, 31), date(2026, 8, 20), 31, True, "periods that overlap are one run"),
    ],
)
def test_lane_k_tc15__the_hole_is_measured_against_the_period(
    earlier_end, later_start, shortest, consecutive, why
):
    """Half a billing period is the threshold, and here is why each way.

    A missing bill leaves a hole one period MINUS A DAY wide, so a whole-period
    threshold could never fire; half also absorbs the two or three days a
    move-in or a final bill puts on a boundary, which is not a missing bill and
    must not read as one.
    """
    assert (
        bulk_corrections._periods_are_consecutive(earlier_end, later_start, shortest)
        is consecutive
    ), why
