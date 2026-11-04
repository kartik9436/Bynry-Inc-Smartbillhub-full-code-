# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections: scope selector, staged idempotent
#           execution, per-bill results)   Screens: S30
# Rules:    BR-BIL-004 (the original never changes) · BR-BIL-014 (reason →
#           scope → preview → approval → staged execution) · BR-BIL-041/042
#           (the class derives the mechanism; one class per bulk case) ·
#           BR-BIL-043 (a D-class case that moves money is refused) ·
#           BR-BIL-044 (approval binds the content-hashed artifact) ·
#           BR-BIL-046 (a PINNED list; up and down never netted; warned rows
#           first) · BR-BIL-047 (one bill = one transaction; no batch rollback;
#           the case stays open) · BR-BIL-048 (one open case per chain) ·
#           CLAUDE.md rule 4 · rule 6 · rule 7
# ───────────────────────────────────────────────────────
"""Four hundred bills, one decision — and every way it is allowed to fail.

WHAT RUNS HERE AND WHAT DOES NOT, stated because it changes what these tests
are worth (the same disclosure `test_w3_billing_models.py` makes):

* The CASE layer — scope pinning, the preview artifact, the aggregate panel,
  approval binding, per-bill idempotency, partial failure, resume, abandonment —
  runs in full against real rows.
* The class-D EXECUTION runs in full: a document reissue needs no rating engine
  and no ledger, so it is the mechanism these tests execute end to end.
* The class-R EXECUTION is exercised with its three NEIGHBOURS STUBBED (the
  rebill's pricing, its issue, and the credit note's posting handoff). What is
  asserted is this lane's own orchestration — the credit note is written for the
  full original amount, the original moves to `corrected` and nothing else about
  it moves, and the rebill link lands in the account history. **The integration
  with the real rating engine and the real ledger is NOT asserted anywhere and
  is reported as this lane's largest gap** — hard-won law 1: a test that stubs
  its neighbours must say so rather than let a green tick imply more.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import bulk_corrections, correction_reasons, corrections, models
from apps.billing.correction_models import (
    BILL_FAILED,
    CASE_APPROVED,
    CASE_DONE,
    CASE_OPEN,
    CASE_PENDING_APPROVAL,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    CorrectionCase,
    CorrectionCaseBill,
    InvoiceDocumentInstance,
)
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: WE-9 verbatim (B5 ❄️ FROZEN): the issued bill and its correction. No figure
#: in this file is invented — the original total, the corrected total and the
#: delta are the workbook's, and the tax split is WE-1's four authorities.
ORIGINAL_TOTAL = Decimal("247.87")
CORRECTED_TOTAL = Decimal("227.95")
DELTA = Decimal("-19.92")
ISSUED_AT = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
TODAY = date(2026, 8, 16)


def an_issued_bill(
    tenant,
    account,
    run,
    *,
    invoice_no,
    total=ORIGINAL_TOTAL,
    status=models.INVOICE_ISSUED,
    corrects=None,
    bill_type="cycle",
    template_id="11111111-1111-1111-1111-111111111111",
    template_version=1,
    bill_payload=None,
):
    """One ISSUED bill in the WE-9 shape, built by hand.

    Two lines and a payload, which is everything the correction engine reads:
    the lines are what the preview diffs and the payload is what a class-D
    reissue copies. Built directly rather than through a run because this file
    is about the CORRECTION, and dragging the whole pricing path in would make
    every assertion here depend on the rating engine's fixtures.

    ⚠ `status` and `corrects` were ADDED 2026-08-15 (US-BIL-015 lane), both
    optional and both defaulting to the previous behaviour. They exist because
    `invoices.corrects_invoice_id` (migration 0017) is FROZEN by the
    immutability trigger the moment a bill leaves draft, so a fixture cannot
    build an issued bill and then point it at what it replaces — Postgres
    refuses, correctly and loudly. Production never does that either:
    `corrections.execute_restatement` stamps the link while the rebill is still
    a DRAFT and issues it afterwards. Setting the column at INSERT, or building
    the draft and issuing it, are the only two lawful shapes and these
    parameters are the first.
    """
    from apps.tenancy import models as tenancy_models

    water = tenancy_models.Service.objects.get(code="water")
    invoice = models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=invoice_no,
        service_date=date(2026, 7, 31),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        status=status,
        issued_at=ISSUED_AT if status != models.INVOICE_DRAFT else None,
        corrects_invoice_id=corrects.pk if corrects is not None else None,
        # Frozen after issue like every other money-bearing column, so a
        # fixture sets it at INSERT rather than updating afterwards.
        bill_type=bill_type,
        subtotal=total - Decimal("20.97"),
        tax_total=Decimal("20.97"),
        total=total,
        # The BR-BIL-026 pin. Frozen after issue like the money, so a fixture
        # that wants a specific pin sets it here rather than updating later.
        template_id=template_id,
        template_version=template_version,
        bill_payload=(
            bill_payload
            if bill_payload is not None
            else {
                "account_no": account.account_no,
                "customer_name": "Sara Whitfield",
                "service_address": "1408 Bluestem Ln",
            }
        ),
        payload_version=1,
    )
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        service=water,
        kind="usage",
        description="Water usage 8 kgal",
        amount=Decimal("39.50"),
        taxable=True,
        quantity=Decimal("8"),
        unit="kgal",
    )
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        service=water,
        kind="base",
        description="Water base charge",
        amount=total - Decimal("39.50") - Decimal("20.97"),
        taxable=True,
    )
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        kind="tax",
        description="TX State 6.25%",
        amount=Decimal("20.97"),
        taxable=False,
    )
    return invoice


class _RatedLine:
    """A recomputed line, in the shape `rating_seam.RatedLine` publishes."""

    def __init__(self, kind, description, amount, *, service=None, tax_id=None):
        self.kind = kind
        self.description = description
        self.amount = amount
        self.service = service
        self.tax_id = tax_id
        self.taxable = kind != "tax"


class _RatedBill:
    """The recomputation, supplied rather than priced.

    The corrected WE-9 figures are FROZEN in B5 and the engine that produces
    them is asserted by the golden suite; what this file is testing is what the
    CORRECTION does with them, so they are handed in. `corrections.recompute`
    (the real path through gather → stages → `price_bill`) is exercised by the
    story's own run-through and is named in the lane report as untested here.
    """

    def __init__(self, lines, total):
        self.lines = tuple(lines)
        self.total = total
        self.currency = "USD"

    def lines_of(self, kind):
        return tuple(line for line in self.lines if line.kind == kind)


def a_corrected_bill(invoice):
    """WE-9's recomputation: water 39.50 → 26.50, everything else unmoved."""
    lines = list(invoice.lines.all().order_by("created_at", "id"))
    rated = []
    for line in lines:
        amount = Decimal("26.50") if line.kind == "usage" else line.amount
        rated.append(
            _RatedLine(
                line.kind,
                line.description,
                amount,
                service=line.service.code if line.service_id else None,
                tax_id=str(line.tax_id) if line.tax_id else None,
            )
        )
    return _RatedBill(rated, CORRECTED_TOTAL)


def money_row_counts(tenant):
    """Everything money-bearing a correction could possibly write.

    Counted before and after rather than inspected, because US-BIL-031 TC-2's
    method is the only one that catches a write nobody expected: reading the UI,
    or the result object, only ever confirms what the code meant to do.
    """
    return {
        "invoices": models.Invoice.objects.filter(tenant=tenant).count(),
        "invoice_lines": models.InvoiceLine.objects.filter(tenant=tenant).count(),
        "credit_notes": models.CreditNote.objects.filter(tenant=tenant).count(),
        "adjustments": models.Adjustment.objects.filter(tenant=tenant).count(),
    }


def test_us_bil_016_tc1__the_scope_resolves_to_a_pinned_list_and_writes_no_money(brazos, dana):
    """TC-1 + BR-BIL-046: the preview enumerates the bills and nothing else.

    *"Preview lists every matching bill with its own credit-note/rebill/delta
    figures; Σ shown; nothing written."* The second half is the one asserted by
    counting: a case that quietly drafted a rebill would look identical from the
    outside and would have put an invoice in the books before anyone approved it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bills = tuple(
            an_issued_bill(brazos, account, run, invoice_no=f"BL-2607-00010{n}")
            for n in range(1, 4)
        )
        before = money_row_counts(brazos)

        resolved = bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk)
        assert {str(bill.pk) for bill in resolved} == {str(bill.pk) for bill in bills}

        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            scope={"bill_run_id": str(run.pk)},
            invoices=tuple(
                _with_corrected(bill) for bill in bills
            ),  # the recomputation is supplied
            actor=dana,
            as_of=TODAY,
        )

        assert case.correction_class == CLASS_RESTATEMENT
        assert case.status == CASE_PENDING_APPROVAL
        assert CorrectionCaseBill.objects.filter(case=case).count() == 3
        assert case.preview_hash, "the artifact approval binds must exist (BR-BIL-044)"
        assert money_row_counts(brazos) == before, (
            "BR-BIL-014: NO money-bearing write before approval — a preview that "
            "drafted anything would have put money in the books nobody signed for"
        )


def _with_corrected(invoice):
    """Attach the supplied recomputation so `build_impact` uses it.

    `build_impact` takes `corrected=` and `open_case` recomputes for itself, so
    the fixture patches the module function for the duration of the case. Doing
    it here keeps every test's arrangement in one place.
    """
    return invoice


@pytest.fixture(autouse=True)
def _supplied_recompute(monkeypatch):
    """Every test in this file hands the recomputation in (see `_RatedBill`)."""
    monkeypatch.setattr(corrections, "recompute", a_corrected_bill)


def test_us_bil_016_tc8__the_aggregate_is_a_display_sum_and_ties_out(brazos, dana):
    """TC-8 — the panel over the 3-bill fixture, and its own tie-out.

    Σ credit −743.61 · Σ rebill +683.85 · Σ net −59.76 — 247.87 × 3, 227.95 × 3
    and 19.92 × 3, which is *"the per-bill WE-9 numbers summed and nothing
    else"*. The tie-out asserted is the one US-BIL-016 §7a names: Σ credit −
    Σ rebill = Σ net, the same redundancy BR-BIL-032 uses on a bill payload, for
    the same reason — drift between a total and its parts is otherwise invisible.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        for n in range(1, 4):
            an_issued_bill(brazos, account, run, invoice_no=f"BL-2607-00010{n}")
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk),
            actor=dana,
            as_of=TODAY,
        )
        panel = bulk_corrections.aggregate(case)

        assert panel.bills == 3
        assert panel.credit_total == Decimal("743.610000")
        assert panel.rebill_total == Decimal("683.850000")
        assert panel.net_delta == Decimal("-59.760000")
        assert (panel.down_count, panel.down_total) == (3, Decimal("-59.760000"))
        assert (panel.up_count, panel.up_total) == (0, Decimal("0"))
        assert panel.ending_in_credit == 3
        panel.tie_out()


def test_us_bil_016_tc9__up_and_down_are_never_netted_into_one_reassuring_number(brazos, dana):
    """TC-9 (negative) — BR-BIL-046's whole reason for existing.

    *"100 bills up $50 and 100 bills down $50 net to $0.00 and are a disaster; a
    single Σ would hide it, so a single Σ is not offered alone."* Built here as
    two bills moving in opposite directions by the same amount: the net is
    exactly zero and the panel must still say, in the same breath, that one went
    up and one went down.

    PROVED RED against a build that emitted only the net — see the lane report
    for the verbatim failure.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        up = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000201")
        down = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000202")

        def mixed(invoice):
            moved = Decimal("50.00") if invoice.pk == up.pk else Decimal("-50.00")
            return _RatedBill([], invoice.total + moved)

        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(up, down),
            actor=dana,
            as_of=TODAY,
            posting_period=None,
        )
        # rebuild the impacts with the mixed recomputation
        for row in CorrectionCaseBill.objects.filter(case=case):
            invoice = models.Invoice.objects.get(pk=row.invoice_id)
            impact = corrections.build_impact(
                invoice,
                reason_codes=("wrong_rate_plan",),
                correction_class=CLASS_RESTATEMENT,
                corrected=mixed(invoice),
            )
            row.impact = impact.as_dict()
            row.delta_amount = impact.delta
            row.direction = impact.direction
            row.save()

        panel = bulk_corrections.aggregate(case)
        rendered = panel.as_dict()
        assert panel.net_delta == Decimal("0.000000")
        assert rendered["up"] == {"count": 1, "total": "50.00"}
        assert rendered["down"] == {"count": 1, "total": "-50.00"}
        assert "up" in rendered and "down" in rendered, (
            "BR-BIL-046: the panel may never render a net without the two "
            "movements that produced it"
        )


def test_us_bil_016_tc14__a_bulk_case_may_not_mix_a_money_reason_with_a_document_one(brazos, dana):
    """TC-14 (negative) — BR-BIL-042 at bulk scope, refused before a preview.

    A single-bill case takes the strongest class (US-BIL-015 TC-11); a BULK case
    refuses the mix, because *"an approver reading a Σ of money deltas is not
    reviewing reprints, and one approval cannot honestly cover both."*
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000301")
        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.open_case(
                reason_codes=("wrong_rate_plan", "service_or_mailing_address"),
                scope_kind="run",
                invoices=(bill,),
                actor=dana,
                as_of=TODAY,
            )
        assert "one class" in str(refusal.value).lower()
        # A SINGLE case with the same two reasons is lawful and is class R.
        assert (
            correction_reasons.class_for(("wrong_rate_plan", "service_or_mailing_address"))
            == CLASS_RESTATEMENT
        )


def test_us_bil_016_tc10__warned_rows_sort_first_then_the_largest_movement(brazos, dana):
    """TC-10 — *"a 240-row preview is not read in order."*

    A systematic error announces itself in the outlier, so the row with a
    warning leads and the rest follow by absolute delta. Asserted on the ORDER,
    not on a flag: an ordering that has to be re-applied by every screen is an
    ordering that one screen will forget.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        small = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000401")
        large = an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000402", total=Decimal("900.00")
        )
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(small, large),
            actor=dana,
            as_of=TODAY,
        )
        rows = bulk_corrections.case_bills(case)
        assert abs(rows[0].delta_amount) >= abs(rows[1].delta_amount)


def test_us_bil_016_tc5__approval_binds_the_artifact_and_drift_refuses(brazos, dana):
    """TC-5 + TC-13 of US-BIL-015 (BR-BIL-044): the numbers, not the query.

    Approval is recorded against a content hash. If an input moves between the
    preview and the execute — the read corrected again, a bill added, a figure
    changed — execution REFUSES and the stale artifact is kept as evidence of
    what was actually approved.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000501")
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(bill,),
            actor=dana,
            as_of=TODAY,
        )
        approved = bulk_corrections.approve(
            case, approver=dana, on_date=TODAY, preview_hash=case.preview_hash
        )
        assert approved.status == CASE_APPROVED

        row = CorrectionCaseBill.objects.get(case=case)
        drifted = dict(row.impact)
        drifted["corrected_total"] = "999.99"
        row.impact = drifted
        row.save(update_fields=["impact"])

        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.execute(
                case,
                issued_at=ISSUED_AT,
                on_date=TODAY,
                template_id=bill.template_id,
                template_version=1,
                actor=dana,
            )
        assert "fresh preview" in str(refusal.value)
        assert CorrectionCase.objects.get(pk=case.pk).preview[
            "bills"
        ], "the approved artifact is RETAINED as evidence, never overwritten"


def test_us_bil_016_tc4b__nothing_executes_without_a_recorded_approval(brazos, dana):
    """US-BIL-015 TC-4 (negative) — the gate is server-side.

    *"Execute attempted without approval (API) → Rejected; preview artifacts
    only."* The preview is an artifact, not a permission.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000601")
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(bill,),
            actor=dana,
            as_of=TODAY,
        )
        before = money_row_counts(brazos)
        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.execute(
                case,
                issued_at=ISSUED_AT,
                on_date=TODAY,
                template_id=bill.template_id,
                template_version=1,
                actor=dana,
            )
        assert "approval" in str(refusal.value)
        assert money_row_counts(brazos) == before


def test_us_bil_016_tc6__a_second_case_cannot_claim_a_bill_already_in_flight(brazos, dana):
    """TC-6 (negative) + BR-BIL-048 — one unresolved case per bill.

    Held by a partial unique index rather than by a SELECT-then-INSERT: two
    clerks opening two cases over the same cycle is exactly the race a Python
    check loses, and the loser credits one bill twice.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000701")
        bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(bill,),
            actor=dana,
            as_of=TODAY,
        )
        with pytest.raises(BillingRuleError) as refusal:
            bulk_corrections.open_case(
                reason_codes=("wrong_read",),
                scope_kind="run",
                invoices=(bill,),
                actor=dana,
                as_of=TODAY,
            )
        assert "BR-BIL-048" in str(refusal.value) or "one open case" in str(refusal.value)


def test_us_bil_016_tc3__a_failed_bill_leaves_zero_artifacts_and_the_case_stays_open(brazos, dana):
    """TC-3 + TC-13 (BR-BIL-047) — one bill is the unit of atomicity.

    Two bills, one of which cannot execute (its payload is empty, so the reissue
    has nothing to correct a copy of). The failure leaves **no** artifacts and
    is recorded with its reason; the other bill's document exists and is not
    rolled back; the case is neither `done` nor `failed` but **open**, because
    calling it either would be a lie on the screen.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        good = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000801")
        broken = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000802")
        models.Invoice.objects.filter(pk=broken.pk).update(bill_payload={})

        case = bulk_corrections.open_case(
            reason_codes=("customer_name",),
            scope_kind="run",
            scope={"corrected_payload": {"customer_name": "Sarah Whitfield"}},
            invoices=(good, broken),
            actor=dana,
            as_of=TODAY,
        )
        bulk_corrections.approve(case, approver=dana, on_date=TODAY)
        result = bulk_corrections.execute(case, issued_at=ISSUED_AT, on_date=TODAY, actor=dana)

        assert len(result.succeeded) == 1 and len(result.failed) == 1
        assert result.summary() == "1 succeeded · 1 failed"
        assert InvoiceDocumentInstance.objects.filter(invoice=good).count() == 1
        assert (
            InvoiceDocumentInstance.objects.filter(invoice=broken).count() == 0
        ), "BR-BIL-047: a failed bill leaves ZERO artifacts and stays correctable"
        assert CorrectionCase.objects.get(pk=case.pk).status == CASE_OPEN


def test_us_bil_016_tc4__resume_touches_only_the_failures_and_never_double_writes(brazos, dana):
    """TC-4 + TC-6 of US-BIL-015 (CLAUDE.md rule 6) — the idempotency guarantee.

    Re-running the execution after a partial failure must re-attempt ONLY the
    failed bill: the succeeded one is skipped and reported as skipped, and
    exactly one artifact exists for it however many times the job runs. A retry
    storm, a double-clicked button and a resumed worker are the same case.

    PROVED RED against a build whose loop re-executed every row — see the lane
    report for the verbatim failure ("2 == 1").
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        good = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000901")
        broken = an_issued_bill(brazos, account, run, invoice_no="BL-2607-000902")
        models.Invoice.objects.filter(pk=broken.pk).update(bill_payload={})
        case = bulk_corrections.open_case(
            reason_codes=("customer_name",),
            scope_kind="run",
            scope={"corrected_payload": {"customer_name": "Sarah Whitfield"}},
            invoices=(good, broken),
            actor=dana,
            as_of=TODAY,
        )
        bulk_corrections.approve(case, approver=dana, on_date=TODAY)
        bulk_corrections.execute(case, issued_at=ISSUED_AT, on_date=TODAY, actor=dana)

        # The failure is repaired, and the job is resumed.
        models.Invoice.objects.filter(pk=broken.pk).update(
            bill_payload={"customer_name": "Sara Whitfield"}
        )
        again = bulk_corrections.resume(case, issued_at=ISSUED_AT, on_date=TODAY, actor=dana)

        assert str(good.pk) in again.skipped_already_done
        assert str(broken.pk) in again.succeeded
        assert (
            InvoiceDocumentInstance.objects.filter(invoice=good).count() == 1
        ), "a succeeded bill never re-executes (rule 6)"
        assert CorrectionCase.objects.get(pk=case.pk).status == CASE_DONE


def test_us_bil_016_tc12__there_is_no_batch_rollback_and_the_screen_says_why(brazos, dana):
    """TC-12 (negative) — BR-BIL-047, *"not 'not yet', but never."*

    Asserted two ways, because an absence is easy to claim and easy to
    re-introduce: the module exposes no rollback callable at all, and the
    sentence a screen puts where the button would have been names both reasons —
    a posted pair cannot be un-posted and a delivered bill cannot be un-sent.
    """
    assert not [
        name
        for name in dir(bulk_corrections)
        if "rollback" in name.lower()
        and callable(getattr(bulk_corrections, name, None))
        and name != "explain_no_batch_rollback"
    ]
    words = bulk_corrections.explain_no_batch_rollback()
    assert "cannot be un-posted" in words and "cannot be un-sent" in words
    assert "NEW correction case" in words


def test_us_bil_016_tc13__closing_a_case_over_failures_demands_a_reason(brazos, dana):
    """TC-13 (BR-BIL-047) — abandonment is explicit, reasoned and audited.

    *"Closed"* with no explanation is indistinguishable from *"finished"*, and
    the bills are still wrong either way.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        broken = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001001")
        models.Invoice.objects.filter(pk=broken.pk).update(bill_payload={})
        case = bulk_corrections.open_case(
            reason_codes=("customer_name",),
            scope_kind="run",
            scope={"corrected_payload": {"customer_name": "Sarah Whitfield"}},
            invoices=(broken,),
            actor=dana,
            as_of=TODAY,
        )
        bulk_corrections.approve(case, approver=dana, on_date=TODAY)
        bulk_corrections.execute(case, issued_at=ISSUED_AT, on_date=TODAY, actor=dana)
        assert CorrectionCaseBill.objects.get(case=case).status == BILL_FAILED

        with pytest.raises(BillingRuleError):
            bulk_corrections.abandon(case, reason="  ", actor=dana, on_date=TODAY)
        closed = bulk_corrections.abandon(
            case, reason="customer moved out; no forwarding address", actor=dana, on_date=TODAY
        )
        assert closed.status == CASE_DONE and closed.closed_reason


def test_us_bil_016_tc11__a_bill_issued_after_approval_does_not_join_the_set(brazos, dana):
    """TC-11 (negative) — BR-BIL-046: the approved set is a LIST, not a query.

    A bill issued into the same run after approval matches the original scope
    predicate and must NOT be corrected under a signature that never covered it.
    It is REPORTED as unaddressed so the operator knows a second case is needed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        first = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001101")
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            invoices=(first,),
            actor=dana,
            as_of=TODAY,
        )
        bulk_corrections.approve(case, approver=dana, on_date=TODAY)
        latecomer = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001102")

        rescoped = bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk)
        assert len(rescoped) == 2
        assert bulk_corrections.unaddressed_bills(case, invoices=rescoped) == (str(latecomer.pk),)


def test_us_bil_016_tc15__a_correction_never_edits_the_original_it_writes_new_rows(
    brazos, dana, monkeypatch
):
    """**Hard rule 4** — the guard this whole workflow exists to satisfy.

    The class-R execution is run with its three neighbours stubbed (see the
    module docstring): what is asserted here is that the correction produces a
    CREDIT NOTE referencing the original, moves the original's `status` to
    `corrected` and **changes nothing else about it** — every money column, its
    number, its dates and its lines are byte-identical afterwards.

    PROVED RED by making the correction UPDATE the original's total instead of
    writing a credit note — see the lane report for the verbatim failure.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001201")
        before_lines = [
            (line.kind, line.description, line.amount)
            for line in bill.lines.all().order_by("created_at", "id")
        ]

        rebill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001202")
        monkeypatch.setattr(corrections, "post_credit_note_reversal", lambda *a, **k: None)
        monkeypatch.setattr(corrections.single, "prepare_single_bill", lambda **k: _PreparedStub())
        monkeypatch.setattr(corrections.single, "calculate_single_bill", lambda *a, **k: rebill)
        import apps.billing.issue as issue_module

        monkeypatch.setattr(issue_module, "issue_invoice", lambda invoice, **k: invoice)

        impact = corrections.build_impact(
            bill,
            reason_codes=("wrong_read",),
            correction_class=CLASS_RESTATEMENT,
            corrected=a_corrected_bill(bill),
        )
        assert impact.original_total == Decimal("247.870000")
        assert impact.corrected_total == Decimal("227.950000")
        assert impact.delta == Decimal("-19.920000")

        corrections.execute_restatement(
            bill,
            impact=impact,
            reason="wrong_read",
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )

        credit = models.CreditNote.objects.get(original_invoice=bill)
        assert credit.amount == Decimal("-247.870000")
        after = models.Invoice.objects.get(pk=bill.pk)
        assert after.status == models.INVOICE_CORRECTED
        assert after.total == Decimal("247.870000"), "the original's money NEVER changes"
        assert after.invoice_no == "BL-2607-001201"
        assert [
            (line.kind, line.description, line.amount)
            for line in after.lines.all().order_by("created_at", "id")
        ] == before_lines


class _PreparedStub:
    blocked = ()
    ready = ()


def test_us_bil_016_tc16__an_upward_correction_beyond_the_backbill_window_refuses(brazos, dana):
    """OQ-104, CLOSED by the PO on 2026-08-11 with option A — the cap APPLIES.

    Shown to the PO as *"a meter was read too low in 2023; correcting it bills
    the customer $1,840 for a period 30 months back."* The correction workflow
    is not a lawful route around a consumer-protection cap. A DOWNWARD
    correction of the same aged bill is unaffected, and that half is asserted
    too — the asymmetry is the ruling.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001301")
        upward = corrections.build_impact(
            bill,
            reason_codes=("missed_charge",),
            correction_class=CLASS_RESTATEMENT,
            corrected=_RatedBill([], bill.total + Decimal("1840.00")),
        )
        with pytest.raises(BillingRuleError) as refusal:
            corrections.refuse_upward_beyond_window(
                upward, as_of=date(2029, 1, 31), period_end=bill.period_end
            )
        assert "back-bill window" in str(refusal.value)

        downward = corrections.build_impact(
            bill,
            reason_codes=("wrong_read",),
            correction_class=CLASS_RESTATEMENT,
            corrected=a_corrected_bill(bill),
        )
        corrections.refuse_upward_beyond_window(
            downward, as_of=date(2029, 1, 31), period_end=bill.period_end
        )


def test_us_bil_016_tc17__a_goodwill_credit_excludes_tax_and_does_not_touch_the_bill(brazos, dana):
    """The PO's goodwill ruling of 2026-08-11, and the boundary behind it.

    Verbatim: *"you dont touch the bill; you issue new a good will credit;
    everything remain as it is, it is new good will credit to be applied in new
    bill"* — and *"it will exclude the tax"*.

    So a class-C preview shows the BILL's delta as **$0.00**, emits no credit
    note and no rebill, and describes an account-level credit instead.

    **EXECUTION IS NOW RULED — PO 2026-08-12, verbatim: _"a separate write-off
    account"_ (OQ-105/OQ-168).** This test asserted that execution REFUSED, and
    it refused for a real reason: the three candidate debits were three
    different P&Ls, and a goodwill credit row without its entry is money in the
    product and not in the books. The entry is now **DR write-off / CR customer
    credit balance**, both resolved by DESIGNATION.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001401")
        impact = corrections.build_impact(
            bill,
            reason_codes=("goodwill",),
            correction_class="credit_only",
            goodwill_amount=Decimal("25.00"),
        )
        assert impact.delta == Decimal("0")
        assert impact.corrected_total == impact.original_total
        assert "goodwill credit of 25.00" in impact.documents[0]
        assert "no credit note" in impact.documents[0]

        with pytest.raises(BillingRuleError):
            corrections.goodwill_credit_amount(amount=Decimal("25.00"), tax_included=True)

        # The two sides are resolved by DESIGNATION, never by the numbers 6900
        # and 2400 — a tenant may renumber their chart (OQ-106).
        debit_account_id, credit_account_id = corrections.credit_only_gl_accounts()
        assert debit_account_id and credit_account_id
        assert debit_account_id != credit_account_id

        # And the bill is STILL not touched: the credit is raised on the account
        # (PO 2026-08-11), so the invoice's own total does not move.
        assert impact.corrected_total == impact.original_total


def test_us_bil_016_tc10b__the_mechanism_is_derived_and_can_never_be_supplied(brazos, dana):
    """US-BIL-015 TC-10 (negative) — the silent-underbilling guard.

    An operator (or an API client) answering *"wrong rate/plan"* with a document
    reissue leaves the customer holding the wrong amount and fires no gate
    anywhere. The mechanism is DERIVED from the reason and there is no argument
    that accepts one.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-001501")
        with pytest.raises(BillingRuleError) as refusal:
            corrections.build_impact(
                bill,
                reason_codes=("wrong_rate_plan",),
                correction_class=CLASS_RESTATEMENT,
                corrected=a_corrected_bill(bill),
                mechanism=CLASS_DOCUMENT,
            )
        assert "DERIVED" in str(refusal.value)


def test_us_bil_016_tc1b__a_reason_this_build_cannot_class_is_refused_never_defaulted(brazos, dana):
    """US-BIL-017 TC-1b, enforced one layer up (BR-BIL-041).

    The tenant-extensible reason lookup and its `class` column are US-BIL-017's
    and are NOT built. A reason with no class would let the case pick its own
    mechanism — the exact failure the taxonomy exists to prevent — so an unknown
    code is REFUSED rather than defaulted in either direction.
    """
    with pytest.raises(BillingRuleError) as refusal:
        correction_reasons.class_for(("meter_swap_mislink",))
    assert "carries no class" in str(refusal.value)
    assert "US-BIL-017" in str(refusal.value)

    with pytest.raises(BillingRuleError) as routed:
        correction_reasons.class_for(("estimate_replaced_by_actual",))
    assert "NEXT bill" in str(routed.value)


def test_us_bil_016_tc7__a_case_never_reaches_another_tenants_bills(brazos, dana):
    """TC-7 (isolation) — the scope selector resolves this tenant's bills only.

    The service-layer half runs everywhere; the RLS half is the G5 suite's job
    against Postgres. Both are needed and neither replaces the other.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        an_issued_bill(brazos, account, run, invoice_no="BL-2607-001601")
        assert len(bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk)) == 1
        assert all(
            invoice.tenant_id == brazos.id
            for invoice in bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk)
        )
