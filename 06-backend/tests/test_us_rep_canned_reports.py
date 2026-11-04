# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-001 (S44 library) · US-REP-002 (S46 viewer) · US-REP-003
#           (IS-11 downloads) · US-REP-005 (AR aging) · US-REP-006 (billing
#           register + revenue by service & rate) · US-REP-007 (payments by
#           method)   Screens: S44 · S46
# Rules:    BR-REP-001 (EVERY money header labels its date basis) · BR-REP-002 ·
#           BR-REP-006 (live vocabularies) · BR-REP-008 (the ageing foots to the
#           AR tie-out) · BR-REP-014 (BILL-purpose only in collection framings) ·
#           BR-REP-018 (IS-11 CSV contract) · BR-REP-024 (never a 0 where a
#           figure could not be computed) · BR-PAY-012 · BR-PAY-015 (an intent
#           is not money) · BR-PAY-021 (posting ≠ clearing) · BR-PAY-032 ·
#           BR-TEN-003 / HR-1 (cross-tenant reads as absent) · CLAUDE.md rule 1 ·
#           rule 2 · rule 3
# ───────────────────────────────────────────────────────
"""The four reports a person can now RUN, asserted against the story fixtures.

Every expected figure below is quoted from the story that ratified it — the
register's **553.69** and average **184.56** are US-REP-006 §7 verbatim, the
cash mix's **471.39 / 121.78 / 593.17** is US-REP-007 §7 verbatim. Nothing here
recomputes an expectation from the code, because a test that did would agree
with a broken implementation.

**AND THE NEGATIVE ASSERTIONS ARE THE POINT.** The easy way to make a report
look finished is to fill it: an average bill of 0.00 when no bill was issued, a
band percentage of 0% over an empty receivable, a tie-out tick nobody checked,
a `bill_purpose` total that quietly includes a deposit. Each is a sentence about
money no row in this database supports and each passes a shape test. So this
file asserts they are **null, under their contracted names, with the reason
travelling beside them** — and that every money report names its basis, because
BR-REP-001 makes an unlabeled money render a failure by contract.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.reports import api as reports_api
from apps.reports import catalog, queries
from core import errors

from tests.test_us_bil_025_026_bills_read import a_line, an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

UTC = timezone.utc

# ── US-REP-006 §7, verbatim ─────────────────────────────────────────────────
WE1_BILL = Decimal("247.87")
WE3_BILL = Decimal("16.42")
WE7B_BILL = Decimal("289.40")
REGISTER_TOTAL = Decimal("553.69")  # "247.87 + 16.42 + 289.40"
AVERAGE_BILL = Decimal("184.56")  # "553.69 ÷ 3 = 184.56 (2dp display)"

# ── US-REP-007 §7, verbatim (the PE-10 receipt day) ─────────────────────────
CHECKS = (Decimal("292.87"), Decimal("142.30"), Decimal("36.22"))
CHECK_LINE = Decimal("471.39")  # "292.87 + 142.30 + 36.22"
CASH = (Decimal("105.36"), Decimal("16.42"))
CASH_LINE = Decimal("121.78")  # "105.36 + 16.42"
RECEIPT_DAY_TOTAL = Decimal("593.17")  # "471.39 + 121.78"
DEPOSIT_PAYMENT = Decimal("150.00")  # WE-6 deposit — NEVER a collection figure

JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
AUGUST_END = date(2026, 8, 31)


# ── fixture helpers ─────────────────────────────────────────────────────────
def three_bills(tenant, account):
    """US-REP-006 TC-1's month: WE-1 · WE-3 · WE-7B, the last typed `final`."""
    we1 = an_invoice(
        tenant,
        account,
        invoice_no="BL-2607-000001",
        total=WE1_BILL,
        subtotal=Decimal("226.90"),
        tax_total=Decimal("20.97"),
        issued_at=datetime(2026, 7, 8, 9, 42, tzinfo=UTC),
        due_date=date(2026, 8, 2),
    )
    we3 = an_invoice(
        tenant,
        account,
        invoice_no="BL-2607-000002",
        total=WE3_BILL,
        subtotal=Decimal("15.00"),
        tax_total=Decimal("1.42"),
        issued_at=datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
        due_date=date(2026, 8, 6),
    )
    we7b = an_invoice(
        tenant,
        account,
        invoice_no="BL-2607-000003",
        bill_type="final",
        total=WE7B_BILL,
        subtotal=Decimal("264.41"),
        tax_total=Decimal("24.99"),
        issued_at=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
        due_date=date(2026, 8, 23),
    )
    return we1, we3, we7b


def a_method(tenant, code, name):
    from apps.tenancy import models as tenancy_models

    row, _ = tenancy_models.PaymentMethod.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name, "is_system": True}
    )
    return row


def a_cleared_payment(tenant, account, *, amount, method, cleared_on, purpose="bill", **extra):
    """A payment row, written directly.

    Through the ORM rather than `services.record_payment`, deliberately: what
    this file asserts is the READ MODEL over payments, and dragging the ledger
    posting service into it would make a reporting failure indistinguishable
    from a posting failure.
    """
    from apps.payments import models as payment_models

    values = dict(
        tenant=tenant,
        account=account,
        method=method,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED
        if hasattr(payment_models, "PAYMENT_CLEARED")
        else "cleared",
        purpose=purpose,
        posted_at=datetime(cleared_on.year, cleared_on.month, cleared_on.day, 10, 0, tzinfo=UTC),
        cleared_at=datetime(cleared_on.year, cleared_on.month, cleared_on.day, 10, 0, tzinfo=UTC),
    )
    values.update(extra)
    return payment_models.Payment.objects.create(**values)


def viewer(tenant, key, *, role="billing_clerk", **query):
    """`GET /reports/{key}` as the S46 parameter bar submits it."""
    return api_call(
        reports_api.report,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        query=query or None,
        key=key,
    )


def library(tenant, *, role="billing_clerk"):
    """`GET /reports` — the S44 card grid."""
    return api_call(
        reports_api.report_library, "get", user=FakeUser(), role=role, tenant=tenant
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-006 — the billing register
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_006_tc1__the_register_foots_to_553_69_with_an_average_of_184_56(brazos, dana):
    """US-REP-006 TC-1 verbatim: *"3 bills · billed 553.69 · average 184.56 ·
    WE-7B row typed `final` · usage shown with units"*.

    The average is asserted at 2dp DISPLAY precision, which is where B4 rounds —
    the read model publishes the exact quotient (184.563333…) and rounding it
    here rather than in the engine is the rule, not a convenience.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        we1, we3, we7b = three_bills(brazos, account)
        a_line(brazos, we1, account, quantity=Decimal("684"), unit="kWh")

        body = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data

        assert [row["invoice_no"] for row in body["rows"]] == [
            "BL-2607-000001",
            "BL-2607-000002",
            "BL-2607-000003",
        ]
        assert body["totals"]["bills"] == 3
        assert Decimal(body["totals"]["billed"]) == REGISTER_TOTAL
        average = next(kpi for kpi in body["kpis"] if kpi["key"] == "average_bill")
        assert Decimal(average["value"]).quantize(Decimal("0.01")) == AVERAGE_BILL
        assert body["rows"][2]["bill_type"] == "final"
        # CLAUDE.md rule 3 — the quantity NEVER travels without its unit.
        assert body["rows"][0]["usage"] == [{"quantity": "684", "unit": "kWh"}]


def test_us_rep_006_tc2__the_bill_type_filter_selects_and_excludes(brazos, dana):
    """US-REP-006 TC-2: the `bill_type` filter is first-class (A14 item 6).

    `cycle` must EXCLUDE the final bill — a filter that only ever adds rows is
    not a filter, and this is the half that a shape test never exercises.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        three_bills(brazos, account)
        window = {"from": JULY_START.isoformat(), "to": JULY_END.isoformat()}

        finals = viewer(brazos, catalog.KEY_BILLING_REGISTER, bill_type="final", **window).data
        assert [row["invoice_no"] for row in finals["rows"]] == ["BL-2607-000003"]

        cycles = viewer(brazos, catalog.KEY_BILLING_REGISTER, bill_type="cycle", **window).data
        assert "BL-2607-000003" not in [row["invoice_no"] for row in cycles["rows"]]
        assert len(cycles["rows"]) == 2


def test_us_rep_006_tc2b__an_unknown_bill_type_is_refused_with_the_vocabulary(brazos, dana):
    """A hand-edited `bill_type` is VAL-005 naming the six, never a silent
    full-set render (US-REP-002 TC-6's posture applied to this filter)."""
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        response = viewer(
            brazos,
            catalog.KEY_BILLING_REGISTER,
            bill_type="anual",
            **{"from": JULY_START.isoformat(), "to": JULY_END.isoformat()},
        )
        assert response.status_code == 422
        assert response.data["code"] == errors.VAL_UNKNOWN_LOOKUP
        assert "cycle" in response.data["params"]["values"]


def test_us_rep_006_tc6__a_draft_never_appears_in_the_register(brazos, dana):
    """US-REP-006 TC-6 verbatim: *"Never appears in the register — the register
    reads issued, immutable invoices only"*.

    A draft is replaceable (BR-BIL-023 lets a re-run discard it), so a register
    that counted drafts would change its own history between two runs of the
    same report.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        three_bills(brazos, account)
        an_invoice(
            brazos,
            account,
            invoice_no="BL-2607-000009",
            status=billing_models.INVOICE_DRAFT,
            issued_at=None,
            due_date=None,
            total=Decimal("145.70"),
        )

        body = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        assert "BL-2607-000009" not in [row["invoice_no"] for row in body["rows"]]
        assert Decimal(body["totals"]["billed"]) == REGISTER_TOTAL


def test_us_rep_006_tc5__the_register_names_its_basis(brazos, dana):
    """US-REP-006 TC-5 / BR-REP-001: *"an unlabeled money render = FAIL"*."""
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        assert body["basis"] == "posting"


def test_us_rep_006_the_exceptions_kpi_is_null_with_its_reason_not_zero(brazos, dana):
    """BR-REP-024 — a figure that cannot be computed prints its REASON.

    A14 draws an *Exceptions* tile and `bill_run_exclusions` is keyed to a RUN,
    not to a date window, so a register spanning two runs has no single count.
    Zero would be a claim that nothing was excepted.
    """
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        tile = next(kpi for kpi in body["kpis"] if kpi["key"] == "exceptions")
        assert tile["value"] is None
        assert tile["reason_code"] == "exception_count_is_per_run_not_per_window"


def test_us_rep_006_an_empty_window_has_no_average_and_says_so(brazos, dana):
    """No bills ⇒ the average is NULL with a reason, never 0.00.

    Dividing by zero is not a figure. A tile reading $0.00 average tells a
    utility its bills averaged nothing, which is a different and false statement
    from "there were no bills".
    """
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": "2026-01-01", "to": "2026-01-31"
        }).data
        tile = next(kpi for kpi in body["kpis"] if kpi["key"] == "average_bill")
        assert tile["value"] is None
        assert tile["reason_code"] == "no_bills_in_window"


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-006 ② — revenue by service & rate
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_006_tc3__revenue_splits_usage_base_and_tax_and_foots(brazos, dana):
    """A14 item 9: an INVOICE-LINE read-model, split by line kind.

    Σ(usage) + Σ(base) + Σ(tax) = Σ(lines), so no line can fall between the
    columns unnoticed — which is exactly how a revenue report stops footing to
    the register beside it.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        we1, _, _ = three_bills(brazos, account)
        a_line(brazos, we1, account, kind="usage", amount=Decimal("100.60"))
        a_line(brazos, we1, account, kind="base", amount=Decimal("18.00"), quantity=None, unit=None)
        a_line(brazos, we1, account, kind="tax", amount=Decimal("20.97"), quantity=None, unit=None)

        body = viewer(brazos, catalog.KEY_REVENUE_BY_SERVICE, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data

        assert body["basis"] == "posting"
        totals = body["totals"]
        assert Decimal(totals["usage_revenue"]) == Decimal("100.60")
        assert Decimal(totals["base"]) == Decimal("18.00")
        assert Decimal(totals["tax"]) == Decimal("20.97")
        assert Decimal(totals["total"]) == Decimal("139.57")
        assert Decimal(totals["usage_revenue"]) + Decimal(totals["base"]) + Decimal(
            totals["tax"]
        ) == Decimal(totals["total"])


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-007 — payments by method
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_007_tc1__the_receipt_day_foots_to_471_39_121_78_593_17(brazos, dana):
    """US-REP-007 §7 verbatim: checks **471.39**, cash **121.78**, total
    **593.17**, with a percentage per method over the total."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        check = a_method(brazos, "check", "Check")
        cash = a_method(brazos, "cash", "Cash")
        for amount in CHECKS:
            a_cleared_payment(
                brazos, account, amount=amount, method=check, cleared_on=date(2026, 7, 15)
            )
        for amount in CASH:
            a_cleared_payment(
                brazos, account, amount=amount, method=cash, cleared_on=date(2026, 7, 15)
            )

        body = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data

        by_name = {row["method_name"]: row for row in body["rows"]}
        assert Decimal(by_name["Check"]["amount"]) == CHECK_LINE
        assert Decimal(by_name["Cash"]["amount"]) == CASH_LINE
        assert Decimal(body["totals"]["amount"]) == RECEIPT_DAY_TOTAL
        assert by_name["Check"]["share_pct"] == "79.5"
        assert len(body["details"]) == 5


def test_us_rep_007_tc2__a_deposit_never_enters_a_collection_figure(brazos, dana):
    """US-REP-007 TC-2 / BR-REP-014: a deposit-purpose payment appears under
    `deposit` and NEVER inside any bill-collection line or percentage.

    The rule is made structural rather than remembered: `bill_purpose_amount` is
    published under its own name, so a caller computing a collection percentage
    reaches for it and *cannot* reach a total with a deposit folded in.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        cash = a_method(brazos, "cash", "Cash")
        a_cleared_payment(
            brazos, account, amount=CASH[0], method=cash, cleared_on=date(2026, 7, 15)
        )
        a_cleared_payment(
            brazos,
            account,
            amount=DEPOSIT_PAYMENT,
            method=cash,
            cleared_on=date(2026, 7, 15),
            purpose="deposit",
        )

        body = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data

        assert Decimal(body["totals"]["amount"]) == CASH[0] + DEPOSIT_PAYMENT
        assert Decimal(body["totals"]["bill_purpose_amount"]) == CASH[0]
        purposes = {row["purpose"]: row for row in body["purposes"]}
        assert Decimal(purposes["deposit"]["amount"]) == DEPOSIT_PAYMENT


def test_us_rep_007_tc3__a_payment_belongs_to_the_month_it_was_POSTED_in(brazos, dana):
    """US-REP-007 TC-3, SUPERSEDED 2026-10-21 (`DEF-PAY-10321`). It read
    *"Payment posted Jul 31, cleared Aug 2 → appears in AUGUST's clearing-basis
    report"*. Since `cleared` means reconciled with the bank (CR-186-BRC10), the
    PO moved this report to the POSTING date: the payment is JULY's.

    Both dates still ride on the detail row (BR-PAY-021), and the retired
    *"posted but not yet cleared in this window"* problem is not served.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        cash = a_method(brazos, "cash", "Cash")
        a_cleared_payment(
            brazos,
            account,
            amount=Decimal("80.00"),
            method=cash,
            cleared_on=date(2026, 8, 2),
            posted_at=datetime(2026, 7, 31, 16, 0, tzinfo=UTC),
        )

        july = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        august = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": "2026-08-01", "to": AUGUST_END.isoformat()
        }).data

        assert august["details"] == []
        assert len(july["details"]) == 1
        row = july["details"][0]
        assert row["posted_on"] == "2026-07-31"
        assert row["cleared_on"] == "2026-08-02"
        assert not any(
            problem["code"] == "posted_but_not_yet_cleared_in_this_window"
            for problem in july["unavailable"] + august["unavailable"]
        )


def test_us_rep_007_tc4__the_cash_report_names_the_posting_basis(brazos, dana):
    """US-REP-007 TC-4 / BR-REP-001 — the basis is named on the answer. It was
    `clearing` until the PO ruling of 2026-10-21 (`DEF-PAY-10321`)."""
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        assert body["basis"] == "posting"


def test_def_pay_10321__a_card_payment_taken_14_oct_is_in_the_14_oct_report(brazos, dana):
    """The PO's worked figure, 2026-10-21 (decision log *"Two CR-186 follow-up
    rulings"*, item 2): *"a card payment taken 14 Oct and reconciled 16 Oct"* →
    *"The 14 Oct payment appears in the 14 Oct report, the day the money was
    taken and applied."*

    $40.00 is in the 14 Oct window and not the 16 Oct one, BEFORE the batch is
    reconciled (status `posted`, no clearing date) and AFTER it (status
    `cleared`, cleared 16 Oct). A cancelled $25.00 taken the same day is never
    in either.
    """
    from apps.payments import models as payment_models

    def window(day):
        return viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": day, "to": day
        }).data

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        card = a_method(brazos, "card", "Card")
        taken = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        card_payment = a_cleared_payment(
            brazos,
            account,
            amount=Decimal("40.00"),
            method=card,
            cleared_on=date(2026, 10, 14),
            status=payment_models.PAYMENT_POSTED,
            posted_at=taken,
            cleared_at=None,
        )
        a_cleared_payment(
            brazos,
            account,
            amount=Decimal("25.00"),
            method=card,
            cleared_on=date(2026, 10, 14),
            status=payment_models.PAYMENT_CANCELLED,
            posted_at=taken,
            cleared_at=None,
        )

        before_14, before_16 = window("2026-10-14"), window("2026-10-16")
        assert Decimal(before_14["totals"]["amount"]) == Decimal("40.00")
        assert before_14["totals"]["count"] == 1
        assert before_14["details"][0]["cleared_on"] is None
        assert before_16["details"] == []

        # The deposit batch is reconciled on 16 Oct. Written directly, as every
        # row in this file is — the read model is what is under test.
        payment_models.Payment.objects.filter(pk=card_payment.pk).update(
            status=payment_models.PAYMENT_CLEARED,
            cleared_at=datetime(2026, 10, 16, 11, 0, tzinfo=UTC),
        )

        after_14, after_16 = window("2026-10-14"), window("2026-10-16")
        assert Decimal(after_14["totals"]["amount"]) == Decimal("40.00")
        assert after_14["totals"]["count"] == 1
        assert after_14["details"][0]["posted_on"] == "2026-10-14"
        assert after_14["details"][0]["cleared_on"] == "2026-10-16"
        assert after_16["details"] == []


def test_us_rep_007_tc5__an_autopay_capture_intent_is_counted_nowhere(brazos, dana):
    """US-REP-007 TC-5 / BR-PAY-015: *"intents are not money"*.

    An open intent is a promise to take money later. Counting one would tell a
    utility it had received cash it has not received.
    """
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        payment_models.AutopayCaptureIntent.objects.create(
            tenant=brazos,
            account=account,
            invoice_id=uuid.uuid4(),
            amount=Decimal("247.87"),
            currency="USD",
            scheduled_on=date(2026, 7, 20),
        )

        body = viewer(brazos, catalog.KEY_PAYMENTS_BY_METHOD, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        assert body["rows"] == []
        assert body["details"] == []
        assert body["totals"]["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-005 — AR ageing
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_005_tc1__each_open_bill_ages_on_its_own_due_date(brazos, dana):
    """A14's table: one account, two bills, TWO columns.

    S34's collections list puts a whole balance in one band chosen by the oldest
    debt; this report is a different document and ages each bill on its own due
    date. A customer with a fresh 200 and a four-month-old 50 reads **200 in the
    young band and 50 in 90+**, never 250 in 90+.

    ⚠ **THE YOUNG BAND IS `d1_30` AND NOT `current` SINCE `P2.21`
    (2026-09-24, `DEF-REP-6659`).** This report served FOUR money columns and
    folded `current` and `1-30` into the first of them. `BR-REP-030` is
    PO-confirmed at FIVE — *"Current / 1–30 / 31–60 / 61–90 / 90+"* — the
    Dashboard has shown five since it was built, and the Finance blueprint p035
    draws five and names five as its `f.band` values. The epic's own column
    list (`EP-REP-02` §US-REP-005, A14's table) is stamped with that
    supersession at the same date.

    **No total moved:** this bill is due 2026-08-25 and read `as_of`
    2026-08-31, so it is **six days late** — `1-30` was always where the rule
    put it, and the old column simply did not exist to hold it. `total`,
    `d31_60`, `d61_90`, `d90_plus` and the tie-out are byte-for-byte what they
    were; one column became two.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        an_invoice(
            brazos, account, invoice_no="BL-2608-1", total=Decimal("200.00"),
            due_date=date(2026, 8, 25), issued_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        an_invoice(
            brazos, account, invoice_no="BL-2604-1", total=Decimal("50.00"),
            due_date=date(2026, 4, 25), issued_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        )

        body = viewer(brazos, catalog.KEY_AR_AGING, **{
            "from": "2026-08-01", "to": AUGUST_END.isoformat()
        }).data

        assert body["basis"] == "posting"
        row = body["rows"][0]
        assert Decimal(row["d1_30"]) == Decimal("200.00")
        # And `current` is now what it says — NOTHING is not yet due here.
        assert Decimal(row["current"]) == Decimal("0")
        assert Decimal(row["d90_plus"]) == Decimal("50.00")
        assert Decimal(row["total"]) == Decimal("250.00")
        assert Decimal(body["totals"]["total"]) == Decimal("250.00")
        # BR-PAY-032 — days late anchors on the OLDEST unpaid due date.
        assert row["days_late"] == (AUGUST_END - date(2026, 4, 25)).days


def test_us_rep_005_tc6__money_posted_by_the_due_date_is_not_past_due(brazos, dana):
    """US-REP-005 TC-6 verbatim: *"the clearing date never drives aging"*.

    A settled bill is simply not in the receivable, so this falls out of reading
    allocations and is a special case nowhere in the code.
    """
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        bill = an_invoice(
            brazos, account, invoice_no="BL-2604-2", total=Decimal("50.00"),
            due_date=date(2026, 4, 25), issued_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        )
        payment = a_cleared_payment(
            brazos,
            account,
            amount=Decimal("50.00"),
            method=a_method(brazos, "check", "Check"),
            cleared_on=date(2026, 4, 20),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=bill, amount=Decimal("50.00")
        )

        body = viewer(brazos, catalog.KEY_AR_AGING, **{
            "from": "2026-08-01", "to": AUGUST_END.isoformat()
        }).data
        assert body["rows"] == []
        assert Decimal(body["totals"]["total"]) == Decimal("0")


def test_us_rep_005_the_missing_opening_buckets_are_named_on_every_run(brazos, dana):
    """BR-REP-008 / BR-CUS-048 — `account_opening_buckets` is UNBUILT.

    A tenant that migrated from another system carries balances this report
    cannot see. It says so, every run, with the read that closes it named — a
    tie-out short by exactly the opening balances otherwise looks like a
    reconciliation failure.
    """
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_AR_AGING, **{
            "from": "2026-08-01", "to": AUGUST_END.isoformat()
        }).data
        gap = next(
            entry
            for entry in body["unavailable"]
            if entry["code"] == "imported_opening_buckets_are_not_built"
        )
        assert "apps.customers.selectors.opening_buckets_as_of" in gap["wanted_reads"]


def test_us_rep_005_a_bucket_share_over_an_empty_receivable_is_null_not_zero(brazos, dana):
    """BR-REP-024 — a percentage of nothing is UNDEFINED, not 0%.

    "0% of your receivable is 90+ days old" is a reassuring sentence about a
    utility that has no receivable at all.
    """
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        body = viewer(brazos, catalog.KEY_AR_AGING, **{
            "from": "2026-08-01", "to": AUGUST_END.isoformat()
        }).data
        tile = next(kpi for kpi in body["kpis"] if kpi["key"] == "d90_plus")
        assert tile["detail"] is None


# ═══════════════════════════════════════════════════════════════════════════
# US-REP-001 / US-REP-002 — the library and the viewer shell
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_001_tc1__the_library_lists_every_report_in_its_group(brazos):
    """US-REP-001 TC-1: all three groups, with the BR-REP-007 additions."""
    with tenant_ctx(brazos):
        body = library(brazos).data
        keys = {card["key"] for card in body["cards"]}
        assert {"ar_aging", "billing_register", "trial_balance", "account_ledger"} <= keys
        # BR-REP-007's six additions are all present as cards.
        assert {
            "bill_corrections",
            "back_bills_and_penalties",
            "write_offs",
            "budget_billing_status",
            "delivery_queue_health",
            "returned_mail",
        } <= keys
        assert list(body["groups"]) == ["financial", "operations", "compliance"]


def test_us_rep_001_tc4__an_unproducible_report_says_so_and_opens_no_viewer(brazos):
    """The hard constraint of this lane, asserted: **never draw a screen over an
    absent dimension.**

    An unavailable card carries `available: false` AND a reason, and its key is
    NOT in the served viewer set — so the screen cannot route to a report that
    would render confident emptiness.
    """
    with tenant_ctx(brazos):
        body = library(brazos).data
        unavailable = [card for card in body["cards"] if not card["available"]]
        # ⚠ **THIS WENT RED ON 2026-09-27 WHEN THE LAST SIX DATASETS WERE
        # REGISTERED, AND IT WAS RIGHT TO** (`DEF-REP-6894`): availability was
        # read off *does the dataset have an engine*, so for one run every one
        # of the forty-six cards claimed to be producible while twenty-eight
        # refused on grain when opened. `catalogue_read` asks both questions
        # now; this assertion is unchanged and is the one that caught it.
        assert unavailable, "the catalogue claims every report is producible"
        for card in unavailable:
            assert card["reason_code"], f"{card['key']} refuses with no reason"
            assert card["reason_detail"]
            assert card["key"] not in reports_api.SERVED_KEYS


def test_us_rep_002_tc1__the_service_filter_is_the_tenants_enabled_set(brazos):
    """US-REP-002 TC-1 / BR-REP-006: never the prototype's hardcoded trio."""
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        enabled = set(tenancy_selectors.enabled_service_codes())
        body = library(brazos).data
    offered = {row["code"] for row in body["vocabularies"]["services"]}
    assert offered == enabled


def test_us_rep_002_tc6__an_inverted_custom_range_is_refused(brazos):
    """US-REP-002 TC-6: *"Validation rejects the range"* — never an
    empty-but-plausible report."""
    with tenant_ctx(brazos):
        response = viewer(brazos, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_END.isoformat(), "to": JULY_START.isoformat()
        })
        assert response.status_code == 422
        assert response.data["code"] == errors.VAL_RANGE


def test_us_rep_002_every_served_report_names_a_basis(brazos, dana):
    """BR-REP-001, enforced over the WHOLE served set rather than report by
    report — a seventh report added without a basis fails here on the day it is
    added, not on the day somebody notices a header."""
    with tenant_ctx(brazos):
        an_account(brazos, dana)
        for key in queries.VIEWERS:
            body = viewer(brazos, key, **{
                "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
            }).data
            assert body["basis"] in {"posting", "clearing"}, key


# ═══════════════════════════════════════════════════════════════════════════
# Isolation — a report reads a tenant's WHOLE history (US-REP-00x TC-7)
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_rep_tc7__a_report_never_shows_another_tenants_rows(brazos, lonestar, dana):
    """Every canned report's TC-7. A report reads a tenant's whole history and is
    exactly where a cross-tenant leak would show — and would be believed."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        three_bills(brazos, account)

    with tenant_ctx(lonestar):
        body = viewer(lonestar, catalog.KEY_BILLING_REGISTER, **{
            "from": JULY_START.isoformat(), "to": JULY_END.isoformat()
        }).data
        assert body["rows"] == []
        assert body["totals"]["bills"] == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-001@c6c35b2 (co-packets US-REP-002/003/005/006/007; 04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md · EP-REP-02-canned-reports.md · 12-reports/02-business-rules.md · 04-docs/01-spec/14-reports-and-exports.md)
# screens: S44 · S46
# generated: 2026-08-16 by story-coder (reports lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in this file failed before its read model existed; the register/ageing/cash keys answered VAL-005 "unknown key" enumerating only account_ledger and by_premises. ruff✔ black✔ pytest✔
# exceptions: (1) payments are written through the ORM rather than `services.record_payment`, deliberately — this file asserts the READ model, and dragging the ledger posting service in would make a reporting failure indistinguishable from a posting failure · (2) US-REP-005 TC-2's GT-16 forward-ageing case is NOT asserted: `account_opening_buckets` is unbuilt, so there is nothing to age forward; the ABSENCE is asserted instead, by name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
