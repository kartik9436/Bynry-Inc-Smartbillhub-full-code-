# ── Trace ──────────────────────────────────────────────
# Change:  Finance blueprint p018 `P5.8` — *"They publish the document numbers.
#          P5.3 cannot be done inside Finance. This is the dependency that gates
#          the phase."* OUTCOME: *"The read exists, so the feed can carry it."*
#          Screens: S59 (Reports → Account ledger)
# Rules:   B14 rule 31 (NOTHING INTERNAL IS EVER VISIBLE TO A UTILITY USER —
#          not an id) · BR-TEN-013 (a module never touches another module's
#          ORM; a cross-module read resolves the owner's published callable) ·
#          BR-TEN-003 (a cross-tenant read is an ABSENCE, never a refusal) ·
#          BR-LED-010 (account + range → dated rows) · BR-SHL-025 (a figure
#          this deployment cannot state is stated WITH its reason) ·
#          CLAUDE.md rule 1 (tenant scoping)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The Reference column reads a DOCUMENT NUMBER, and never an id.

**THE TEST THIS FILE EXISTS FOR** is
`test_p5_8__no_row_of_the_account_ledger_carries_a_uuid`. Every other case here
is a mechanism; that one is the rule. B14 rule 31 is absolute — *not an id* —
and until `P5.8` every single row of S59 printed a primary key at a clerk.

⚠ **THE CASES ARE WRITTEN SO A FALLBACK TO THE ID CANNOT PASS THEM.** Asserting
`reference == "BL-2609-000001"` on a numbered row is necessary and is not
sufficient: a read that answered the number where it could and the uuid where it
could not would satisfy it and would leave the breach in place on exactly the
rows that still have no number. So the uuid case asserts over EVERY row of the
report, by PARSING each reference as a UUID rather than by comparing it to a
known string — a check that compares against one id can only ever see that one.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors
from apps.ledger import billing_seam, models, payments_seam, posting, reporting
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors

from tests.ledger_le_fixtures import JULY_END, JULY_START, POSTED_AT, gl, line, make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


BILL_DAY = date(JULY_START.year, JULY_START.month, 15)


# ═══════════════════════════════════════════════════════════════════════════
# The cast: REAL documents, because a synthetic uuid proves nothing here
# ═══════════════════════════════════════════════════════════════════════════
def _an_invoice(tenant, account, *, number="BL-2607-000001"):
    """An issued bill with a printed number.

    A real `invoices` row rather than a `uuid_for(...)` stand-in, because the
    whole question this file asks is whether the read RESOLVES — and a fixture
    whose ids resolve to nothing would let a broken read pass by returning the
    same empty map a correct one returns.
    """
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        service_date=BILL_DAY,
        period_start=JULY_START,
        period_end=JULY_END,
        status=billing_models.INVOICE_ISSUED,
        subtotal=Decimal("100.000000"),
        tax_total=Decimal("0.000000"),
        total=Decimal("100.000000"),
        currency="USD",
    )


def _a_payment(tenant, account, *, number="PMT-2607-000001"):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=number,
        amount=Decimal("40.000000"),
        currency="USD",
        status="cleared",
        type="payment",
        posted_at=POSTED_AT,
    )


def _a_credit_note(tenant, account, invoice, *, number="CM-0001"):
    return billing_models.CreditNote.objects.create(
        tenant=tenant,
        account=account,
        original_invoice=invoice,
        credit_note_no=number,
        amount=Decimal("-10.000000"),
        currency="USD",
        reason="wrong_read",
        issued_at=POSTED_AT,
    )


def _post_ar(tenant, account, *, source_type, source_id, amount, side, key, entry_date=BILL_DAY):
    """One balanced pair whose AR leg carries the account dimension.

    The AR leg is what `account_ledger` reports (its docstring: *"only the AR
    leg appears"*), so the OTHER leg deliberately lands on a GL account with no
    account dimension — a shape the report has to ignore, which is a second
    thing this fixture keeps honest.
    """
    ar = gl(tenant, "1200", "asset")
    other = gl(tenant, "4100", "revenue")
    debit, credit = (ar, other) if side == models.SIDE_DEBIT else (other, ar)
    return posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=POSTED_AT,
            currency="USD",
            source_type=source_type,
            source_id=source_id,
            memo="P5.8 fixture",
            lines=(
                line(
                    debit,
                    models.SIDE_DEBIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if debit is ar else {}),
                ),
                line(
                    credit,
                    models.SIDE_CREDIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if credit is ar else {}),
                ),
            ),
        )
    )


@pytest.fixture()
def one_of_each(brazos, dana):
    """An account carrying a bill, a payment and a credit note — all numbered."""
    with tenant_ctx(brazos):
        return _one_of_each(brazos, dana)


def _one_of_each(brazos, dana):
    accounts = make_accounts(dana, brazos, {})
    account = accounts["ACC-1042"]
    invoice = _an_invoice(brazos, account)
    payment = _a_payment(brazos, account)
    credit_note = _a_credit_note(brazos, account, invoice)
    _post_ar(
        brazos,
        account,
        source_type="invoice",
        source_id=invoice.id,
        amount="100.000000",
        side=models.SIDE_DEBIT,
        key="p58-invoice",
    )
    _post_ar(
        brazos,
        account,
        source_type="payment",
        source_id=payment.id,
        amount="40.000000",
        side=models.SIDE_CREDIT,
        key="p58-payment",
    )
    _post_ar(
        brazos,
        account,
        source_type="credit_note",
        source_id=credit_note.id,
        amount="10.000000",
        side=models.SIDE_CREDIT,
        key="p58-credit-note",
    )
    return {
        "account": account,
        "invoice": invoice,
        "payment": payment,
        "credit_note": credit_note,
    }


def _report(account):
    return reporting.account_ledger(
        account.id, start=JULY_START, end=JULY_START + timedelta(days=30)
    )


def _is_uuid(value) -> bool:
    """Does this string parse as a UUID?

    ⚠ **THE POINT OF PARSING RATHER THAN COMPARING.** A case that asserted
    `reference != str(invoice.id)` can only ever see the one id it was handed,
    so it passes over a row that leaked a DIFFERENT id — which is precisely the
    row a partial fix leaves behind. This asks the question the rule asks.
    """
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# 1 · The published reads
# ═══════════════════════════════════════════════════════════════════════════
def test_p5_8__billing_publishes_the_invoice_numbers(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        invoice = _an_invoice(brazos, accounts["ACC-1042"], number="BL-2607-000042")
        assert billing_selectors.invoice_numbers_for([invoice.id]) == {
            str(invoice.id): "BL-2607-000042"
        }


def test_p5_8__billing_publishes_the_credit_note_numbers(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1042"]
        note = _a_credit_note(brazos, account, _an_invoice(brazos, account), number="CM-0007")
        assert billing_selectors.credit_note_numbers_for([note.id]) == {
            str(note.id): "CM-0007"
        }


def test_p5_8__payments_publishes_the_payment_numbers(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        payment = _a_payment(brazos, accounts["ACC-1042"], number="PMT-2607-000099")
        assert payment_selectors.payment_numbers_for([payment.id]) == {
            str(payment.id): "PMT-2607-000099"
        }


def test_p5_8__an_id_that_resolves_to_nothing_is_an_ABSENT_KEY_never_the_uuid(brazos, dana):
    """The single most important property of all three reads.

    A read that fell back to the id would return `{id: id}` here and every
    caller downstream would render a uuid believing it had a document number.
    """
    stranger = "01a0d23c-fb90-728e-bdfc-dd2d67560499"
    with tenant_ctx(brazos):
        make_accounts(dana, brazos, {})
        for read in (
            billing_selectors.invoice_numbers_for,
            billing_selectors.credit_note_numbers_for,
            payment_selectors.payment_numbers_for,
        ):
            answer = read([stranger])
            assert answer == {}, f"{read.__name__} answered {answer!r} for an unknown id"


def test_p5_8__an_empty_ask_costs_no_query(django_assert_num_queries, brazos, dana):
    with tenant_ctx(brazos):
        make_accounts(dana, brazos, {})
    with tenant_ctx(brazos), django_assert_num_queries(0):
        assert billing_selectors.invoice_numbers_for([]) == {}
        assert billing_selectors.credit_note_numbers_for(()) == {}
        assert payment_selectors.payment_numbers_for(None) == {}


def test_p5_8__a_document_with_no_number_is_absent_rather_than_blank(brazos, dana):
    """A NULL `invoice_no` is a real, lawful state — `BR-BIL-063`'s own note.

    It answers as an absent key, so `numbers.get(id)` is `None` and nothing
    renders the string "None" at a clerk.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        invoice = _an_invoice(brazos, accounts["ACC-1042"], number=None)
        assert billing_selectors.invoice_numbers_for([invoice.id]) == {}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · The seams — the ledger asks by NAME and imports nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_p5_8__the_ledger_seams_resolve_all_three_kinds(one_of_each, brazos):
    with tenant_ctx(brazos):
        wanted = {
            "invoice": {str(one_of_each["invoice"].id)},
            "credit_note": {str(one_of_each["credit_note"].id)},
            "payment": {str(one_of_each["payment"].id)},
            "opening_balance": {"01a0d23c-fb90-728e-bdfc-dd2d67560499"},
        }
        resolved = dict(billing_seam.document_numbers_for(wanted))
        resolved.update(payments_seam.document_numbers_for(wanted))
    assert resolved == {
        ("invoice", str(one_of_each["invoice"].id)): "BL-2607-000001",
        ("credit_note", str(one_of_each["credit_note"].id)): "CM-0001",
        ("payment", str(one_of_each["payment"].id)): "PMT-2607-000001",
    }


def test_p5_8__neither_ledger_seam_imports_the_module_it_reads():
    """`BR-TEN-013` / gate `G6`, asserted on the source rather than trusted.

    The seams resolve `apps.billing.selectors` and `apps.payments.selectors`
    by NAME at call time; a lane "simplifying" that into a module-level import
    would bind the ledger to another module's internals and this case is what
    says so.
    """
    for module in (billing_seam, payments_seam):
        source = open(module.__file__, encoding="utf-8").read()
        for banned in ("from apps.billing import models", "from apps.payments import models"):
            assert banned not in source, f"{module.__name__} imports {banned}"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · The screen half — B14 rule 31
# ═══════════════════════════════════════════════════════════════════════════
def test_p5_8__the_reference_column_reads_the_printed_numbers(one_of_each, brazos):
    with tenant_ctx(brazos):
        report = _report(one_of_each["account"])
    by_type = {row.source_type: row.reference for row in report["rows"]}
    assert by_type == {
        "invoice": "BL-2607-000001",
        "payment": "PMT-2607-000001",
        "credit_note": "CM-0001",
    }


def test_p5_8__no_row_of_the_account_ledger_carries_a_uuid(one_of_each, brazos):
    """B14 rule 31, over EVERY row, by parsing rather than by comparing.

    ⚠ **THIS CASE POSTS A FIFTH ROW THAT CANNOT BE RESOLVED, AND THE REASON IS
    THAT WITHOUT IT THE CASE COULD NOT FAIL.** Measured: with the fixture's
    three perfectly numbered documents alone, sabotaging `invoice_numbers_for`
    into `{id: found.get(id, id)}` — the exact fallback this task exists to
    remove — left every assertion here GREEN, because a fallback never fires on
    a row that resolves. A rule-31 check whose fixture has nothing to leak is
    the *structurally incapable of failing* shape hard-won law 7 names.
    """
    account = one_of_each["account"]
    with tenant_ctx(brazos):
        _post_ar(
            brazos,
            account,
            source_type="invoice",
            source_id="01a0d23c-fb90-728e-bdfc-dd2d67560499",  # names no invoice
            amount="7.000000",
            side=models.SIDE_DEBIT,
            key="p58-unresolvable",
        )
        report = _report(account)
    assert len(report["rows"]) == 4, "the unresolvable row is what makes this case able to fail"
    leaked = [row.reference for row in report["rows"] if _is_uuid(row.reference)]
    assert leaked == [], f"the Reference column printed {len(leaked)} internal id(s): {leaked}"


def test_p5_8__a_clean_page_does_not_apologise(one_of_each, brazos):
    """No gap is reported when every document row carries its number.

    A refusal that outlives what it refused over is `DEF-CWP-3925`'s shape and
    it is how a stated absence stops being read at all.
    """
    with tenant_ctx(brazos):
        report = _report(one_of_each["account"])
    codes = {gap["code"] for gap in report["unavailable"]}
    assert reporting.GAP_DOCUMENT_HAS_NO_NUMBER["code"] not in codes


def test_p5_8__a_document_we_cannot_name_states_its_absence(brazos, dana):
    """A refund's AR movement: `refunds` carries no number column at all.

    The cell is EMPTY and the report says so once, under the table. Nothing
    invents a number — that one arrives with `P3.3`.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1042"]
        _post_ar(
            brazos,
            account,
            source_type="refund",
            source_id="01a0d23c-fb90-728e-bdfc-dd2d67560499",
            amount="12.000000",
            side=models.SIDE_DEBIT,
            key="p58-refund",
        )
        report = _report(account)
    assert [row.reference for row in report["rows"]] == [None]
    codes = {gap["code"] for gap in report["unavailable"]}
    assert reporting.GAP_DOCUMENT_HAS_NO_NUMBER["code"] in codes


def test_p5_8__an_opening_balance_is_not_a_missing_document(brazos, dana):
    """19 of the demo tenant's 167 entries are opening balances.

    An opening balance HAS no document, so an empty Reference on one is the
    right answer and reporting a gap over it would be an apology for a
    correctly-blank cell — which trains a clerk to ignore the gap that matters.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1042"]
        _post_ar(
            brazos,
            account,
            source_type="opening_balance",
            source_id="01a0d23c-fb90-728e-bdfc-dd2d67560499",
            amount="45.000000",
            side=models.SIDE_DEBIT,
            key="p58-opening",
        )
        report = _report(account)
    assert [row.reference for row in report["rows"]] == [None]
    codes = {gap["code"] for gap in report["unavailable"]}
    assert reporting.GAP_DOCUMENT_HAS_NO_NUMBER["code"] not in codes


def test_p5_8__the_retired_gap_code_is_gone_from_the_read_model(one_of_each, brazos):
    """The old sentence said billing and payments publish nothing. They do now.

    A key whose sentence has become false is the rot hard rule 4 records on
    `amendment_history_is_not_a_permanent_record`; this case is what stops it
    coming back.
    """
    with tenant_ctx(brazos):
        report = _report(one_of_each["account"])
    codes = {gap["code"] for gap in report["unavailable"]}
    assert "reference_is_the_source_id_not_the_document_number" not in codes


def test_p5_8__one_page_costs_one_query_per_document_kind(
    django_assert_max_num_queries, one_of_each, brazos
):
    """The reads are asked for the WHOLE page, never per row.

    Three document kinds on the page, three seam queries, however many rows
    there are — the shape `integrations.seams.ledger.page_context` already
    uses. A per-row read here would be N+1 over a report a clerk runs for a
    whole year.
    """
    with tenant_ctx(brazos):
        with django_assert_max_num_queries(12):
            report = _report(one_of_each["account"])
    assert len(report["rows"]) == 3
