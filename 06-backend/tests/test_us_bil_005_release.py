# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (phases 4 and 5 — the summary, the gate, the release)
#           Screens: S31 step 5 · S31 step 6
# Rules:    BR-BIL-056 (the pre-release summary — four figures CONFIRMED, the
#           "frozen" half SUPERSEDED 2026-08-11 option B) · BR-BIL-057 (the
#           category axes — PROPOSED, unenumerated) · BR-BIL-058 (five
#           separate confirmations) · BR-BIL-059 (coverage is SHOWN, never
#           enforced) · BR-BIL-055 (a break never blocks the run) ·
#           BR-TEN-043 (event time is named, never a clock) · hard rule 2
#           (money + currency) · rule 3 (a quantity carries its unit) ·
#           rule 4 (financial records are append-only) · rule 7 (audit)
# Tests:    this file
# Impacts:  apps/billing/release.py (the subject) · apps/billing/issue.py (the
#           seam phase 5 calls) · tests/test_us_bil_005_release_gate.py (the
#           RECORD's tests — this file tests the CODE that writes it)
# ───────────────────────────────────────────────────────
"""Phases 4 and 5 of the PO's bill run, as tests.

The sibling file `test_us_bil_005_release_gate.py` pins the RECORD — what the
`bill_run_releases` row must hold once something writes one. It says so itself:
*"these assert the RECORD, not the GATE … Nothing here computes a summary, runs
a compliance check, or refuses a release whose confirmations are false — that is
the run service, which does not exist yet."* This file is that service's tests.

The one reversal that has to stay visible, because a reader who meets these two
files together will otherwise think one of them is wrong:

  * `tc4` over there asserts the SCREEN recalculates when a bill is voided.
  * `tc4b` over there asserts the STORED ROW does not.

Both are true and both are ruled (PO 2026-08-11, option B). `tc41` and `tc42`
below are the same two claims made against the real `summary_for` /
`authorise_release` code rather than against a query written in a test.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db.models import Sum

from apps.billing import issue, models, release
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_unpublished_ledger,
    electric_gl_accounts,
)
from tests.test_us_bil_005_release_gate import a_release
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

CONFIRMED_AT = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)
RELEASED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)

ALL_FIVE = release.Confirmations(
    compliance=True, email_mandate=True, sms_mandate=True, autopay_mandate=True, final=True
)


def a_usage_bill(tenant, account, run, *, service_code, quantity, unit, total, **overrides):
    """A draft carrying ONE usage line with an explicit quantity and unit.

    Built straight rather than through `a_priced_draft` because these cases are
    about the CONSUMPTION axis: the service, the quantity and the unit are the
    variables, and the money is only along for the ride.
    """
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    values = dict(
        tenant=tenant,
        account=account,
        bill_run=run,
        service_date=date(2026, 6, 30),
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        currency="USD",
    )
    values.update(overrides)
    bill = models.Invoice.objects.create(**values)
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=bill,
        account=account,
        service=service,
        kind="usage",
        description=f"{service_code} usage",
        quantity=quantity,
        unit=unit,
        amount=total,
    )
    return bill


# ══ PHASE 4 — the summary ═══════════════════════════════════════════════════


def test_us_bil_005_tc40__the_summary_carries_the_four_figures_the_po_named(brazos, dana):
    """Epic TC-8. Accounts · bills · consumption WITH ITS UNIT · amount + currency.

    The PO named four figures on 2026-08-11 and BR-BIL-056 makes all four
    required. Consumption is the one people forget and the one that tells a
    utility whether a run looks right BEFORE the money goes out — which is why
    it carries its unit per service and is never one summed number.

    Worked so the arithmetic is checkable by eye: two accounts, electric 684
    kWh at 100.58 and water 12.4 kgal at 47.20 → 2 accounts, 2 bills,
    147.78 USD, and TWO consumption rows because kWh and kgal do not add.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50001"),
            run,
            service_code="electric",
            quantity=Decimal("684"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50002"),
            run,
            service_code="water",
            quantity=Decimal("12.4"),
            unit="kgal",
            total=Decimal("47.20"),
        )

        summary = release.summary_for(run)

        assert summary.accounts == 2
        assert summary.bills == 2
        assert summary.amount == Decimal("147.78")
        assert summary.currency == "USD"  # rule 2 — the partner, always
        # rule 3: per service, each with its own unit, NEVER summed together.
        assert [(c.service_code, c.quantity, c.unit) for c in summary.consumption] == [
            ("electric", Decimal("684"), "kWh"),
            ("water", Decimal("12.4"), "kgal"),
        ]


def test_us_bil_005_tc41__the_summary_moves_when_a_bill_is_voided(brazos, dana):
    """Epic TC-9(a) — the REVERSAL, against the real code this time.

    The PO was shown *"You approve 480 bills, $52,847.19. Two bills are voided
    next week. The screen still says 480 / $52,847.19"* and chose **B,
    recalculate live**. So `summary_for` is a QUERY, computed on every call, and
    a summary function that read the stored row would fail right here.

    Worked: three bills at 120.40 + 87.15 + 245.60 = 453.15; void the 245.60;
    the panel must read 2 bills / 207.55 — the same figures the sibling file's
    tc4 pins with a hand-written query.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        bills = [
            a_usage_bill(
                brazos,
                an_account(dana, brazos, account_no=account_no),
                run,
                service_code="electric",
                quantity=Decimal("100"),
                unit="kWh",
                total=total,
            )
            for account_no, total in (
                ("A-40001", Decimal("120.40")),
                ("A-40002", Decimal("87.15")),
                ("A-40003", Decimal("245.60")),
            )
        ]

        first = release.summary_for(run)
        assert (first.bills, first.amount) == (3, Decimal("453.15"))
        assert first.consumption[0].quantity == Decimal("300")

        bills[2].status = models.INVOICE_VOID
        bills[2].save(update_fields=["status"])

        second = release.summary_for(run)
        assert (second.bills, second.amount) == (2, Decimal("207.55"))  # it MOVED
        # …and the consumption moved with it: 300 kWh − 100 kWh.
        assert second.consumption[0].quantity == Decimal("200")
        assert second.consumption[0].unit == "kWh"


def test_us_bil_005_tc42__the_stored_row_holds_what_was_shown_and_does_not_move(brazos, dana):
    """Epic TC-9(b) — `authorise_release` stores the panel, and it stays stored.

    The other half of the option-B ruling. The screen recalculates; the
    authorisation record does not, because hard rule 4 makes it append-only and
    after that ruling it is the ONLY answer to *"what did I authorise?"*.

    Worked: authorise at 3 bills / 453.15, void one, re-read. The screen says
    2 / 207.55 (tc41) and this row still says 3 / 453.15.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        bills = [
            a_usage_bill(
                brazos,
                an_account(dana, brazos, account_no=account_no),
                run,
                service_code="electric",
                quantity=Decimal("100"),
                unit="kWh",
                total=total,
            )
            for account_no, total in (
                ("A-40001", Decimal("120.40")),
                ("A-40002", Decimal("87.15")),
                ("A-40003", Decimal("245.60")),
            )
        ]
        shown = release.summary_for(run)
        row = release.authorise_release(
            bill_run=run,
            summary=shown,
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )

        bills[2].status = models.INVOICE_VOID
        bills[2].save(update_fields=["status"])

        stored = models.BillRunRelease.objects.get(pk=row.pk)
        assert stored.bill_count == 3
        assert stored.total_amount == Decimal("453.15")
        assert stored.currency == "USD"
        assert stored.summary["bills"] == 3
        assert stored.summary["amount"] == "453.150000"  # six decimals, rule 2
        assert stored.confirmed_by_id == dana.user.id
        assert stored.confirmed_at == CONFIRMED_AT
        # The two answers now disagree, deliberately — that IS the design.
        assert release.summary_for(run).bills == 2


def test_us_bil_005_tc43__a_quantity_with_no_unit_is_refused_not_counted(brazos, dana):
    """Rule 3, at the summary. "412,880" is not a quantity a human can check.

    `assemble_document` already refuses to WRITE such a line, and that is not
    the guarantee here (hard-won law 1: a comment claiming a guarantee is not
    the guarantee). A bill written by an import, a fixture or a future path
    reaches this function too, and summing a unitless quantity into a
    per-service figure is the mistake that makes the sanity check worthless.

    A refusal, never a zero and never a silent drop.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        bill = a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50010"),
            run,
            service_code="electric",
            quantity=Decimal("684"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        line = bill.lines.get()
        line.unit = None
        line.save(update_fields=["unit"])

        with pytest.raises(BillingRuleError) as refusal:
            release.summary_for(run)
        assert "CLAUDE.md rule 3" in str(refusal.value)
        assert "684" in str(refusal.value)


def test_us_bil_005_tc44__two_units_on_one_service_stay_two_rows(brazos, dana):
    """Never sum across units — including within ONE service.

    The obvious reading of "consumption per service" is one number per service.
    That is wrong the moment a tenant meters water in kgal on one route and in
    m3 on another: 2,317.4 + 88.0 is not a quantity of anything. The group key
    is (service, unit), so the panel shows both and a human sees the mixture
    instead of a plausible total.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50020"),
            run,
            service_code="water",
            quantity=Decimal("2317.4"),
            unit="kgal",
            total=Decimal("30.00"),
        )
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50021"),
            run,
            service_code="water",
            quantity=Decimal("88.0"),
            unit="m3",
            total=Decimal("12.00"),
        )

        summary = release.summary_for(run)
        assert [(c.service_code, c.quantity, c.unit) for c in summary.consumption] == [
            ("water", Decimal("2317.4"), "kgal"),
            ("water", Decimal("88.0"), "m3"),
        ]


def test_us_bil_005_tc45__two_currencies_in_one_run_are_refused(brazos, dana):
    """Rule 2's partner, applied the same way rule 3's is.

    Σ(100.58 USD, 47.20 CAD) is not an amount. The tenant currency is
    forward-only (BR-TEN-021) so this should never happen — which is exactly
    why it must refuse loudly rather than produce a number nobody can name.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50030"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50031"),
            run,
            service_code="electric",
            quantity=Decimal("50"),
            unit="kWh",
            total=Decimal("47.20"),
            currency="CAD",
        )

        with pytest.raises(BillingRuleError) as refusal:
            release.summary_for(run)
        assert "CAD" in str(refusal.value) and "USD" in str(refusal.value)


def test_us_bil_005_tc46__consumption_with_no_service_is_named_never_relabelled(brazos, dana):
    """The gap that is real TODAY: stage 6 writes no `service` on its lines.

    So the run's own bills cannot say which service 684 kWh belongs to. Three
    wrong answers were available — guess from the unit (water and sewer both
    meter in kgal), drop the quantity (understating the one figure that exists
    to be sanity-checked), or refuse the whole panel (no run could ever be
    released). The figure is shown with `service_code=None` and the absence is
    NAMED in `problems`, so nobody reads it as attributed.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        bill = a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50040"),
            run,
            service_code="electric",
            quantity=Decimal("684"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        line = bill.lines.get()
        line.service = None
        line.save(update_fields=["service"])

        summary = release.summary_for(run)
        assert [(c.service_code, c.quantity, c.unit) for c in summary.consumption] == [
            (None, Decimal("684"), "kWh")
        ]
        codes = {problem["code"] for problem in summary.problems}
        assert release.SUMMARY_SERVICE_UNATTRIBUTED in codes


def test_us_bil_005_tc47__the_category_axis_set_is_declared_proposed(brazos, dana):
    """BR-BIL-057 is PROPOSED. The PO said *"and various categories"* — no list.

    So what ships is the axes that can be DERIVED, each labelled, plus the
    standing declaration that the SET itself is not ruled. An implementation
    that presented these axes as the answer would be resolving an open question
    by choosing a value, which the prime directive forbids.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50050"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )

        summary = release.summary_for(run)
        assert summary.axes_status == "PROPOSED"
        assert summary.axes_br_ref == "BR-BIL-057"

        axes = {figure.axis for figure in summary.by_category}
        assert {"bill_type", "consumer_category", "service"} <= axes
        by_type = [f for f in summary.by_category if f.axis == "bill_type"]
        assert (by_type[0].key, by_type[0].bills, by_type[0].amount) == (
            "cycle",
            1,
            Decimal("100.58"),
        )

        # The axes BR-BIL-057 proposes that this run cannot derive are NAMED,
        # not quietly absent — a missing axis and an empty axis look identical.
        unavailable = {
            problem["axis"]
            for problem in summary.problems
            if problem["code"] == release.SUMMARY_AXIS_UNAVAILABLE
        }
        assert {"delivery_channel", "behavior_class", "exception_state"} <= unavailable


def test_us_bil_005_tc48__a_superseded_bill_is_shown_at_its_replacements_figure(brazos, dana):
    """OQ-111 CLOSED 2026-08-11 — and since 2026-08-12 its answer is BUILT.

    The PO's worked case, run verbatim: a run issues **$117.01** to ACC-1042 and
    the bill is corrected to **$104.20** in a LATER run. The ruling — *"A
    Replacement counts (panel = what these customers owe now)"* — makes the
    FIRST run's panel read **$104.20** for that account.

    ⚠ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-15, and it was right to.
    Reaching the $104.20 means following the chain from the original to its
    rebill, and `invoices` carried no `corrects_invoice_id` — so the panel
    refused, named the missing column, and this case pinned the refusal. The PO
    closed **OQ-120** on 2026-08-12 (*"Nod to add the link on the new bill"*),
    migration `0017` added the column, and the refusal is gone. What the case
    pins now is the ANSWER.

    The two reachable-but-wrong figures stay asserted as DATA, because they are
    still what a regression would produce: a panel that stayed a filter on
    `invoices.bill_run_id` totals **$117.01** (a figure nobody owes) and one
    that dropped the superseded bill the way a VOID is dropped totals **nothing
    at all** (and this customer owes $104.20). Both were measured under mutation
    — see the lane report's RED transcript, where regressing the walk produced
    exactly `Decimal('117.010000000000')`.
    """
    with tenant_ctx(brazos):
        first_run = a_run(brazos)
        acc_1042 = an_account(dana, brazos, account_no="ACC-1042")
        original = a_usage_bill(
            brazos,
            acc_1042,
            first_run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("117.01"),
            invoice_no="BL-2607-018410",
            status=models.INVOICE_ISSUED,
        )
        # The correction lands in a LATER run: the rebill carries a DIFFERENT
        # `bill_run`, which is the whole reason the panel cannot stay a filter
        # on `invoices.bill_run_id`.
        later_run = a_run(brazos, key="2026-07|cycle-1")
        rebill = a_usage_bill(
            brazos,
            acc_1042,
            later_run,
            service_code="electric",
            quantity=Decimal("88"),
            unit="kWh",
            total=Decimal("104.20"),
            invoice_no="BL-2607-018411",
            bill_type="rebill",
            status=models.INVOICE_ISSUED,
        )
        # The chain edge, written where the PO ruled it belongs — on the NEW
        # bill (OQ-120). Set here by a direct UPDATE only because this fixture
        # builds its bills already-issued; production stamps it on the draft,
        # and the immutability trigger enforces that ordering.
        models.Invoice.objects.filter(pk=rebill.pk).update(corrects_invoice_id=original.pk)
        original.status = models.INVOICE_CORRECTED
        original.save(update_fields=["status"])

        summary = release.summary_for(first_run)

        assert summary.amount == Decimal("104.200000")
        assert summary.bills == 1
        assert summary.accounts == 1

        # The wrong figures stated as DATA, so the ruled answer is pinned by
        # more than one assertion: a panel that stayed a filter on
        # `invoices.bill_run_id` still totals $117.01 here, and dropping the
        # superseded bill the way a VOID is dropped reads $0.00.
        naive = release.counted_bills(first_run).aggregate(total=Sum("total"))["total"]
        assert naive == Decimal("117.010000")
        assert (
            release.counted_bills(first_run)
            .exclude(status__in=release.SUPERSEDED_STATUSES)
            .aggregate(total=Sum("total"))["total"]
            is None
        )


def test_us_bil_005_tc48c__a_corrected_bill_with_no_replacement_still_refuses(brazos, dana):
    """What SURVIVES of the old refusal, and it is narrower than it was.

    A bill marked `corrected` that NOTHING replaces is not a chain, it is a
    hole: the panel cannot say what the customer owes now, and the two figures
    it could reach are the same two that were always wrong. Data written before
    migration `0017` looks exactly like this, which is why the refusal names the
    migration rather than blaming the operator.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        orphan = a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="ACC-1042"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("117.01"),
            invoice_no="BL-2607-018410",
            status=models.INVOICE_ISSUED,
        )
        orphan.status = models.INVOICE_CORRECTED
        orphan.save(update_fields=["status"])

        with pytest.raises(BillingRuleError) as refusal:
            release.summary_for(run)

        message = str(refusal.value)
        assert release.CHAIN_COLUMN in message  # invoices.corrects_invoice_id
        assert "BL-2607-018410" in message
        assert "0017" in message
        # A CLOSED question must never be stubbed as if it were open — G8.
        assert "OQ-111" not in message
        assert "nobody owes" in message and "0.00" in message


def test_us_bil_005_tc48b__a_rebill_in_this_run_counts_like_any_other_bill(brazos, dana):
    """The other half of the same ruling: *"A Replacement counts"*.

    A rebill carrying THIS run's `bill_run` is a replacement, and a replacement
    is what the customer owes now — so it is summed like any other bill. Before
    2026-08-11 a run holding one refused outright, which is what the ruling
    overturned. $104.20 beside a $117.01 ordinary bill totals $221.21.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50061"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("117.01"),
        )
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="ACC-1042"),
            run,
            service_code="electric",
            quantity=Decimal("88"),
            unit="kWh",
            total=Decimal("104.20"),
            bill_type="rebill",
        )

        summary = release.summary_for(run)
        assert (summary.bills, summary.amount) == (2, Decimal("221.210000"))


def test_us_bil_005_tc48c__a_credit_note_with_no_replacement_counts_like_a_replacement(
    brazos, dana
):
    """OQ-121 CLOSED — PO 2026-08-12, verbatim: *"no rebill , Count it like a
    replacement"*.

    A class-C correction (goodwill) writes a credit note and issues NO rebill;
    the original stays `issued`. ❄️ GT-6's frozen shape: **$25.00** against a
    **$247.30** invoice, and the panel therefore reads **$222.30** — the credit
    plays the replacement's part, because the panel is *"what these customers
    owe now"* (the OQ-111 parenthetical) and this customer owes 222.30.

    This file USED to assert `NotImplementedError("OQ-121")` here. That refusal
    is gone, not because the question was quietly answered but because the PO
    answered it: the case is rewritten to pin the ruling rather than deleted, so
    the reversal stays visible to whoever reads it next.

    The panel MOVES and the bill is NOT dropped: one bill, one account, and a
    figure $25.00 below what the run produced. A corrected account is therefore
    never invisible to the person signing the run off, which is the whole reason
    the PO was asked.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-50062")
        bill = a_usage_bill(
            brazos,
            account,
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("247.30"),
            status=models.INVOICE_ISSUED,
        )
        models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            credit_note_no="CN-2607-000012",
            # NEGATIVE since DEF-085 / BR-BIL-074 (billing/0020). GT-6's ratified
            # $222.30 is unmoved: the frozen figure is the MAGNITUDE and the
            # resulting balance, neither of which the storage sign touches.
            amount=Decimal("-25.00"),
            currency="USD",
            reason="goodwill",
        )

        summary = release.summary_for(run)
        # The ratified figure, asserted so drift goes RED (CLAUDE.md §sign-off).
        assert summary.amount == Decimal("222.300000")
        assert summary.bills == 1, "the bill is counted, never dropped — it is not a void"
        assert summary.accounts == 1
        # Both halves of the arithmetic are kept, because the stored row is the
        # only surviving answer to "what did I authorise?" once the screen moves.
        assert summary.gross_amount == Decimal("247.300000")
        assert summary.credits_applied == Decimal("25.000000")

        # The PRE-RULING figure, pinned as DATA rather than as a memory: a panel
        # that stayed a plain Σ of `invoices.total` still reads $247.30 here, and
        # that is the number the ruling moved.
        naive = release.counted_bills(run).aggregate(total=Sum("total"))["total"]
        assert naive == Decimal("247.300000")
        assert summary.amount == naive - Decimal("25.00")

        # The panel SAYS it netted, with the figures on the row: a total that
        # moved for an unstated reason is the one a clerk approves by mistake.
        netted = [
            problem
            for problem in summary.problems
            if problem["code"] == release.SUMMARY_CREDITS_NETTED
        ]
        assert len(netted) == 1
        assert "CN-2607-000012" in netted[0]["detail"]
        assert "247.300000" in netted[0]["detail"] and "222.300000" in netted[0]["detail"]

        # The stored payload carries all three figures, not just the net.
        payload = summary.as_payload()
        assert payload["amount"] == "222.300000"
        assert payload["gross_amount"] == "247.300000"
        assert payload["credits_applied"] == "25.000000"

        # The category rows tie out to the headline rather than to the gross —
        # a breakdown that summed to a different total than the figure above it
        # is the discrepancy a sign-off panel exists to prevent.
        by_type = [row for row in summary.by_category if row.axis == "bill_type"]
        assert sum(row.amount for row in by_type) == Decimal("222.300000")


def test_us_bil_005_tc48c2__the_stored_sign_of_a_credit_note_does_not_move_the_panel(brazos, dana):
    """The same GT-6 case, written the way the CODE writes one.

    `corrections.execute_credit_only` stores its goodwill credit NEGATIVE —
    `amount = money.finalize(-credited)`, i.e. `-25.000000`.

    **THE AMBIGUITY THIS CASE WAS WRITTEN FOR IS CLOSED (DEF-085, 2026-08-15).**
    It used to read: *"while nothing on `credit_notes` states a sign convention
    and this file's own fixture writes it positive. A panel that added a signed
    column would read **$272.30** on one convention and **$222.30** on the other,
    and both would look plausible."* That was exactly true, and it was the
    defect. `credit_notes.amount <= 0` is now a database CHECK constraint
    (BR-BIL-074, billing/0020), the fixture above was corrected to the ruled
    direction, and a positive amount can no longer be stored by anything.

    The case is KEPT, and its assertion is unchanged: the panel reads the
    magnitude and decides the direction in one place, so the ruled **$222.30**
    is reached from the stored `-25.000000`. What it now proves is that the
    ratified figure survived the constraint — which is the only thing anyone
    should care about when a sign convention lands on a money column.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-50063")
        bill = a_usage_bill(
            brazos,
            account,
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("247.30"),
            status=models.INVOICE_ISSUED,
        )
        models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            credit_note_no="CN-2607-000013",
            amount=Decimal("-25.00"),  # the sign `execute_credit_only` writes
            currency="USD",
            reason="goodwill",
        )

        assert release.summary_for(run).amount == Decimal("222.300000")


def test_us_bil_005_tc48c3__a_credit_note_in_another_currency_is_refused(brazos, dana):
    """Rule 2, on the new arithmetic: money is never netted across currencies.

    A CAD credit against a USD bill has no lawful subtraction — 247.30 USD less
    25.00 CAD is a number with no name, the same reason kWh is never added to
    kgal. BR-TEN-021 makes the tenant currency forward-only, so this should be
    unreachable; that is exactly why it must fail loudly if it is reached.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-50064")
        bill = a_usage_bill(
            brazos,
            account,
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("247.30"),
            status=models.INVOICE_ISSUED,
        )
        models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            credit_note_no="CN-2607-000014",
            # NEGATIVE since DEF-085 / BR-BIL-074 (billing/0020). The CURRENCY is
            # what this case is about and it is unchanged.
            amount=Decimal("-25.00"),
            currency="CAD",
            reason="goodwill",
        )

        with pytest.raises(BillingRuleError) as refusal:
            release.summary_for(run)
        assert "CAD" in str(refusal.value)


def test_us_bil_005_tc49__accounts_counts_the_held_ones_too(brazos, dana):
    """ "480 of 500" is only honest if the 500 counts the ones that produced no bill.

    BR-BIL-055: a partial run issues the clean bills and HOLDS the rest, and the
    held ones are `bill_run_exclusions` rows. An accounts figure that counted
    only the accounts with bills would equal the bills figure on every run and
    would tell a clerk nothing.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50070"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        held = an_account(dana, brazos, account_no="A-50071")
        models.BillRunExclusion.objects.create(
            tenant=brazos, bill_run=run, account=held, reason_code="missing_read"
        )

        summary = release.summary_for(run)
        assert (summary.accounts, summary.bills) == (2, 1)


# ══ PHASE 4 — the gate ══════════════════════════════════════════════════════


def test_us_bil_005_tc50__each_of_the_five_confirmations_is_recorded_separately(brazos, dana):
    """BR-BIL-058 / epic TC-10. Five facts, five values — never one tick.

    *"did anyone check compliance before we billed 500 customers?"* is the
    question the record exists to answer, and one undifferentiated boolean
    cannot answer it. The fifth fact is the final confirm itself: WHO said go
    and WHEN, which is why an unnamed confirmer is not a release.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50080"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )

        stored = models.BillRunRelease.objects.get(pk=row.pk)
        assert stored.compliance_confirmed is True
        assert stored.email_mandate_confirmed is True
        assert stored.sms_mandate_confirmed is True
        assert stored.autopay_mandate_confirmed is True
        # The fifth, recorded as who + when rather than as a boolean.
        assert stored.confirmed_by_id == dana.user.id and stored.confirmed_at == CONFIRMED_AT


@pytest.mark.parametrize(
    "missing_field, expected",
    [
        ("compliance", "compliance"),
        ("email_mandate", "email_mandate"),
        ("sms_mandate", "sms_mandate"),
        ("autopay_mandate", "autopay_mandate"),
        ("final", "final"),
    ],
)
def test_us_bil_005_tc51__a_missing_confirmation_refuses_and_names_itself(
    brazos, dana, missing_field, expected
):
    """Epic TC-10 — *"Refused, naming the untaken confirmation."*

    Naming it is the requirement, not an extra: a refusal that says only "not
    confirmed" sends a clerk round all five toggles. Each of the five is
    withheld in turn so no single one can be the only one that is checked —
    a gate that enforced four of five would pass a test that only tried one.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50090"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        confirmations = release.Confirmations(
            compliance=missing_field != "compliance",
            email_mandate=missing_field != "email_mandate",
            sms_mandate=missing_field != "sms_mandate",
            autopay_mandate=missing_field != "autopay_mandate",
            final=missing_field != "final",
        )

        with pytest.raises(BillingRuleError) as refusal:
            release.authorise_release(
                bill_run=run,
                summary=release.summary_for(run),
                confirmations=confirmations,
                confirmed_by=dana.user,
                confirmed_at=CONFIRMED_AT,
            )
        assert expected in str(refusal.value)
        assert "BR-BIL-058" in str(refusal.value)
        assert not models.BillRunRelease.objects.filter(bill_run=run).exists()


def test_us_bil_005_tc52__an_account_with_no_email_never_blocks_the_release(brazos, dana):
    """BR-BIL-059 / epic TC-11 — coverage is SHOWN, not enforced.

    *"An account with no email address … still bills, still renders, still
    dispatches and never blocks the release"* — print is the primary channel and
    the floor (BR-BIL-036). The confirmations attest that the operator SAW the
    coverage, not that every account is covered. So a run where nobody has an
    email address authorises and releases exactly like any other.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-50100")
        assert not account.contact_set.exists() if hasattr(account, "contact_set") else True
        a_usage_bill(
            brazos,
            account,
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )

        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        assert row.pk is not None
        # And the reason it did not block is on the record: the coverage this
        # deployment cannot compute is NAMED rather than silently zero, because
        # "0 of 1,122 have email" and "we could not count" are different facts.
        codes = {problem["code"] for problem in row.summary["problems"]}
        assert release.SUMMARY_COVERAGE_UNAVAILABLE in codes


def test_us_bil_005_tc53__the_authorisation_writes_an_audit_row(brazos, dana, audit_rows):
    """Hard rule 7. Authorising a release is the decision that money goes out.

    Asserted against the BE-03 capture sink, the same way the issue lane's
    tc25 does — the sink is what `core.audit` actually writes through.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a_usage_bill(
            brazos,
            an_account(dana, brazos, account_no="A-50110"),
            run,
            service_code="electric",
            quantity=Decimal("100"),
            unit="kWh",
            total=Decimal("100.58"),
        )
        release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )

        rows = [row for row in audit_rows if row["action"] == "bill_run.release_authorised"]
        assert len(rows) == 1
        after = rows[0]["after"]
        assert rows[0]["entity_type"] == "bill_run" and rows[0]["actor_user_id"] == dana.user.id
        assert after["bill_count"] == 1
        # Rule 2: money travels as a STRING of the stored decimal with its
        # currency beside it — never a JSON number, which is a float.
        assert after["total_amount"] == "100.580000" and after["currency"] == "USD"
        # BR-BIL-058: all five, separately, in the trail as well as the row.
        assert after["compliance_confirmed"] is True
        assert after["sms_mandate_confirmed"] is True
        assert after["confirmed_at"] == CONFIRMED_AT.isoformat()


# ══ PHASE 5 — the release ═══════════════════════════════════════════════════


def an_issuable_run(tenant, dana, *, key="2026-06|cycle-1"):
    """A run with one draft that `issue.issue_run` can actually issue today.

    Uses the issue lane's own fixture, which stamps the `service` stage 6 omits
    and bills a tax-exempt account — the two conditions under which a bill can
    be issued at all on this deployment (that lane's tc26/tc31 are the cases
    that say so).
    """
    run = a_run(tenant, key=key)
    account = an_account(dana, tenant, account_no="A-51000")
    a_priced_draft(tenant, account, run)
    return run


def test_us_bil_005_tc54__release_issues_the_bills_and_stamps_released_at(brazos, dana):
    """Phase 5 — *"and then release the bills"*.

    Release does not re-implement issue: it calls the issue lane's
    `issue_run` and stamps `released_at` when it comes back. `released_at` is a
    PARAMETER (BR-TEN-043) so a resumed release stamps the moment the business
    event happened rather than the moment the retry ran.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()  # the seeded chart splits 4100/4105
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        assert row.released_at is None  # authorised, not yet released

        outcome = release.release_run(
            bill_run=run,
            release_row=row,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )

        assert outcome.issued.issued_count == 1
        assert outcome.issued.broken == ()
        stored = models.BillRunRelease.objects.get(pk=row.pk)
        assert stored.released_at == RELEASED_AT
        bill = models.Invoice.objects.get(bill_run=run)
        assert bill.status == models.INVOICE_ISSUED


def test_us_bil_005_tc55__authorised_but_not_released_survives_a_re_read(brazos, dana):
    """Epic TC-13 — the state a crash between phase 4 and phase 5 leaves.

    Without it a restart either asks for authorisation a second time — for a
    release the user already gave — or assumes it was given and sends bills
    nobody approved. `pending_releases` is what a resume looks at, and the row
    it finds is the one it continues rather than re-authorises.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )

        # The crash: nothing else happens. A fresh read has to find the row.
        pending = release.pending_releases(bill_run=run)
        assert [r.pk for r in pending] == [row.pk]

        resumed = models.BillRunRelease.objects.get(pk=row.pk)
        release.release_run(
            bill_run=run,
            release_row=resumed,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )
        assert not release.pending_releases(bill_run=run).exists()


def test_us_bil_005_tc56__a_released_row_is_never_released_twice(brazos, dana):
    """Epic TC-6/TC-13 — a resumed batch must not issue anything a second time.

    A second release of a run is a second ROW (the sibling file's tc7 — a
    catch-up sub-run is its own authorised event). Re-releasing the SAME row is
    not that: it is a double-click or a replayed job, and it is refused.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        release.release_run(
            bill_run=run,
            release_row=row,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )

        with pytest.raises(BillingRuleError) as refusal:
            release.release_run(
                bill_run=run,
                release_row=models.BillRunRelease.objects.get(pk=row.pk),
                released_at=datetime(2026, 7, 2, 8, 0, tzinfo=UTC),
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana.user,
            )
        assert "already released" in str(refusal.value)
        assert models.BillRunRelease.objects.get(pk=row.pk).released_at == RELEASED_AT


def test_us_bil_005_tc57__a_break_never_blocks_the_release(brazos, dana, monkeypatch):
    """BR-BIL-055 — *"a run that issues 1,122 of 1,124 and queues 2 WORKED"*.

    One bill that cannot issue is recorded as a named break and the release
    still completes: `released_at` is stamped, because the release DID happen
    for everything that could go. The breaks travel on the outcome so nothing
    is silently skipped — and they are NOT auto-queued into the pending-billing
    table, because "mark for later" is a staff decision (BR-BIL-053) and taking
    it here would leave no record that anyone had.
    """
    with tenant_ctx(brazos):
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        an_unpublished_ledger(monkeypatch)  # the GL stamp cannot resolve

        outcome = release.release_run(
            bill_run=run,
            release_row=row,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )

        assert outcome.issued.issued_count == 0
        assert len(outcome.issued.broken) == 1
        assert outcome.issued.broken[0].reason == issue.ISSUE_GL_MAP_UNPUBLISHED
        assert models.BillRunRelease.objects.get(pk=row.pk).released_at == RELEASED_AT
        assert not models.BillRunExclusion.objects.filter(bill_run=run).exists()


def test_us_bil_005_tc58__the_downstream_batches_are_named_and_none_of_them_ran(brazos, dana):
    """*"run the batches in background for downstream jobs"* — honestly reported.

    There is no worker on this deployment: `celery` is a declared dependency
    with zero `tasks.py`, and `JOBS_EAGER` runs a job body in-process (TD-17,
    open). So "background" is not yet true.

    ⚠ AMENDED 2026-08-11 — this paragraph ended *"and the render, the delivery
    queue and the posting handoff are not built either"*, and all three of those
    are built now: issue renders before the status moves (BR-BIL-033), writes
    the queue rows (BR-BIL-016) and emits the balanced posting handoff
    (BR-BIL-011), each inside the bill's own transaction. What is still owed is
    the BACKGROUND BATCH and the SEND. Every handoff is still named on the
    outcome with the rule it owes and with whether it `ran`, so a caller cannot
    read "the run released" as "the bills went out".
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        outcome = release.release_run(
            bill_run=run,
            release_row=row,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )

        codes = {handoff["code"] for handoff in outcome.handoffs}
        assert {
            # AMENDED 2026-08-31 (CR-051 task 4): this read
            # `not_run_in_background`, whose detail told every caller there was
            # no worker on this deployment. There has been one since 2026-08-19
            # and `run_jobs.ISSUE_JOB` runs THIS function in it, so the entry is
            # replaced by what actually happens. Named in BOTH directions below
            # so a silent revert to the old code goes red.
            "issue_runs_in_a_worker_when_the_caller_asks",
            "document_rendered_at_issue_but_not_stored",
            "delivery_queued_but_not_dispatched",
            "posting_handoff_emitted_at_issue",
        } <= codes
        assert "posting_handoff_not_emitted" not in codes
        assert "not_run_in_background" not in codes
        # AMENDED 2026-08-11 (delivery-queue lane, then the bill-document lane).
        # This used to require EVERY handoff to carry `ran: False`, and TWO of
        # them no longer do: the delivery-queue write RAN — issue writes one row
        # per bill per channel (BR-BIL-016) through
        # `delivery_seam.queue_bill_delivery` — and the DOCUMENT RENDER ran too,
        # because `issue_invoice` calls `documents.render_invoice` before the
        # status moves (BR-BIL-033). That handoff was renamed from
        # `document_render_not_run` on the same change, because a code that says
        # "not run" about something that runs is the defect hard-won law 1 is
        # about. Flipping the blanket assertion rather than deleting it keeps
        # what it was for: a handoff that runs must say `True` and one that does
        # not must say `False`, so neither can quietly change meaning.
        # AMENDED AGAIN 2026-08-11 (stage-7 lane): the POSTING handoff joins the
        # `ran: True` set. It was `posting_handoff_not_emitted` / False, on the
        # argument that stage 7 was "a separate act" and the posting service was
        # "still a stub"; neither survived — `issue_invoice` emits the balanced
        # entry inside each bill's own transaction, so a released run now moves
        # money into the books.
        # AMENDED AGAIN 2026-08-31 (CR-051 task 4): the TRANSPORT handoff joins
        # the `ran: True` set, and it is the only one here that is a statement
        # about where the pass executes rather than about a downstream batch.
        ran = {
            "delivery_queued_but_not_dispatched",
            "document_rendered_at_issue_but_not_stored",
            "posting_handoff_emitted_at_issue",
            "issue_runs_in_a_worker_when_the_caller_asks",
        }
        by_code = {handoff["code"]: handoff for handoff in outcome.handoffs}
        assert all(by_code[code]["ran"] is True for code in ran)
        assert all(
            handoff["ran"] is False for handoff in outcome.handoffs if handoff["code"] not in ran
        )
        # …and RAN never means SENT. The rows rest queued; R4 is where email is
        # switched on, and nothing in this path contacts a provider.
        assert "Nothing was SENT" in by_code["delivery_queued_but_not_dispatched"]["detail"]
        # ⚠ AMENDED 2026-10-01 (billing red triage): this read
        # `delivery_queued == len(issued)` — one row per bill — and has been red
        # since `5b6aaa823` (2026-09-07, `CR-084`, PO: *"can you swithc on this
        # now - Customer portal"*). `delivery_queued` counts QUEUE ROWS, one per
        # bill per CHANNEL (BR-BIL-016, `IssuedRun`'s own docstring), and since
        # CR-084 the platform offers the PORTAL on `bill_ready` beside the print
        # floor. So one bill queues TWO rows, `pdf_print` and `portal` — two
        # channels, not a duplicate delivery. Asserted by channel rather than
        # by count alone, so a real duplicate (the same channel twice for one
        # bill) still goes red here.
        from apps.notifications import models as notification_models

        rows = list(
            notification_models.OutboundMessage.objects.filter(
                source_id__in=outcome.issued.issued
            ).values_list("source_id", "channel")
        )
        assert sorted(channel for _, channel in rows) == ["pdf_print", "portal"]
        assert len(set(rows)) == len(rows), f"a channel was queued twice for one bill: {rows}"
        assert outcome.issued.delivery_queued == 2 * len(outcome.issued.issued)
        # BR-BIL-011: every bill this release issued reached the books, and the
        # two counters foot to the issued count exactly.
        assert outcome.issued.posted == len(outcome.issued.issued)
        assert outcome.issued.already_posted == 0


def test_us_bil_005_tc59__release_refuses_a_row_whose_gate_is_incomplete(brazos, dana):
    """Epic TC-14 — the gate cannot be walked around from this side either.

    `issue_run` already refuses a run with no authorised release. This is the
    same door from the other direction: a release ROW that exists but whose
    confirmations are not all recorded is not an authorisation, and phase 5
    refuses it before it reaches issue. Two checks, deliberately, because the
    forged-POST case (TC-14) and the half-filled-row case are different bugs.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_issuable_run(brazos, dana)
        row = a_release(brazos, run, dana, sms_mandate_confirmed=False)

        with pytest.raises(BillingRuleError) as refusal:
            release.release_run(
                bill_run=run,
                release_row=row,
                released_at=RELEASED_AT,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana.user,
            )
        assert "sms_mandate" in str(refusal.value)
        assert models.Invoice.objects.get(bill_run=run).status == models.INVOICE_DRAFT
        assert models.BillRunRelease.objects.get(pk=row.pk).released_at is None


def test_us_bil_005_tc60__the_release_writes_an_audit_row(brazos, dana, audit_rows):
    """Hard rule 7 — release is the money action. Bills leave the building."""
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )
        release.release_run(
            bill_run=run,
            release_row=row,
            released_at=RELEASED_AT,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )

        rows = [row for row in audit_rows if row["action"] == "bill_run.released"]
        assert len(rows) == 1
        after = rows[0]["after"]
        assert after["issued"] == 1 and after["broken"] == 0
        assert after["released_at"] == RELEASED_AT.isoformat()
        # What was AUTHORISED travels beside what was RELEASED, so the trail can
        # answer "did they release what they signed for?" without a second read.
        assert after["bill_count_authorised"] == 1
        assert after["total_amount_authorised"] == "100.580000"


def test_us_bil_005_tc61__a_crash_during_issue_leaves_the_row_unreleased(brazos, dana, monkeypatch):
    """Epic TC-13, at the exact instant it happens — the ORDER is the guarantee.

    `released_at` is what marks a release done, so it is stamped only AFTER the
    issue pass returns. Stamping it first would turn a crash mid-issue into a
    run that claims to have gone out and a resume that skips it: bills nobody
    sent, recorded as sent.

    The crash is simulated at the seam rather than inside issue, because what is
    being pinned is release's ordering, not issue's failure modes.
    """
    with tenant_ctx(brazos):
        run = an_issuable_run(brazos, dana)
        row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=ALL_FIVE,
            confirmed_by=dana.user,
            confirmed_at=CONFIRMED_AT,
        )

        def a_dying_worker(*args, **kwargs):
            raise RuntimeError("the box went away mid-issue")

        monkeypatch.setattr(release.issue, "issue_run", a_dying_worker)
        with pytest.raises(RuntimeError):
            release.release_run(
                bill_run=run,
                release_row=row,
                released_at=RELEASED_AT,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana.user,
            )

        # Authorised, not released — and a resume finds it rather than asking
        # for authorisation a second time.
        assert models.BillRunRelease.objects.get(pk=row.pk).released_at is None
        assert [r.pk for r in release.pending_releases(bill_run=run)] == [row.pk]


def test_us_bil_005_tc62__a_figure_that_will_not_fit_its_column_refuses(brazos, dana):
    """Rule 2 — a display helper never takes a B4 rounding decision.

    Money columns are NUMERIC(18,6). Serialising a value at six places is a
    FORMAT for a figure that already has that scale; a value with more places
    would be silently rounded on its way into the authorisation record, and B4's
    rounding law is finance-signed and frozen. So it refuses.

    Worked: 1.0000005 has seven places. Rounding it to 1.000001 (or 1.000000)
    would put a number in the record that nobody was shown.
    """
    del brazos, dana  # a pure function — no rows, no tenant, no clock
    assert release._money_text(Decimal("52847.19")) == "52847.190000"
    with pytest.raises(BillingRuleError) as refusal:
        release._money_text(Decimal("1.0000005"))
    assert "round only at finalization" in str(refusal.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 bill-run lane — the PO's phases 4-5)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED before green — every guarantee below was
#         broken deliberately and the measured failure quoted in the lane report
# exceptions: (1) NO ENDPOINT AND NO SCREEN. These drive `apps/billing/release.py`
#         directly; S31 step 5 does not exist and nothing in the running product
#         calls this (hard-won law 2, stated rather than implied).
#         (2) AMENDED 2026-08-11 (correction-chain lane): OQ-111 is CLOSED, so
#         tc48 no longer pins "no ruling". It pins the ruling's answer as far as
#         the schema allows — tc48b asserts a rebill in this run COUNTS
#         (117.01 + 104.20 = 221.21) and tc48 asserts that a SUPERSEDED bill
#         refuses with a `BillingRuleError` naming `invoices.corrects_invoice_id`,
#         NOT a stub against a closed question. The two wrong figures the PO's
#         ruling rules out are pinned as data ($117.01 from a bill_run_id
#         filter, $0.00 from dropping it like a void) and were measured under
#         mutation.
#         (2b) AMENDED 2026-08-15 (correction-rulings lane): OQ-121 IS CLOSED
#         TOO. tc48c used to pin the refusal — *"a credit note with no
#         replacement is routed, not chosen"* — and now pins the PO's ruling of
#         2026-08-12, *"no rebill , Count it like a replacement"*: GT-6's
#         $247.30 invoice with its $25.00 goodwill credit shows **222.30**, the
#         bill still counts, and the pre-ruling $247.30 is pinned as data beside
#         it. tc48c2 pins that the stored SIGN of the credit note does not move
#         the figure (`execute_credit_only` writes -25.000000; the fixtures write
#         +25.00) and tc48c3 pins the rule-2 refusal of a credit in another
#         currency. All three were run RED against the pre-ruling build first.
#         (3) the coverage counts BR-BIL-059 requires are asserted as
#         UNAVAILABLE, not as figures: the email address lives in a customers
#         table billing has no reviewed FK to, and the SMS opt-in column does
#         not exist at all (PROPOSED-SCHEMA, unbuilt)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
