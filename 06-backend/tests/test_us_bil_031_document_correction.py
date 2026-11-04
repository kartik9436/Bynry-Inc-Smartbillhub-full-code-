# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-031 (document-only correction: the bill is right, the
#           document is wrong)   Screens: S30
# Rules:    BR-BIL-041 (class D: no credit note, no rebill, no posting; balance
#           delta exactly $0.00) · BR-BIL-043 (a D-class case that moves money
#           is REFUSED) · BR-BIL-049 (a correction never edits master data) ·
#           BR-BIL-030 (the payload is frozen — which is why the artifact is a
#           NEW instance) · BR-BIL-026/031 (the pin travels) · BR-CUS-040 (a
#           reprint renders the issued document) · CLAUDE.md rule 4 · rule 7
# ───────────────────────────────────────────────────────
"""A spelling mistake must never reach the ledger.

Every money assertion here is a ROW COUNT taken before and after, which is
US-BIL-031 §6's own instruction — *"proved by row counts, not by inspection"* —
and the only method that catches a write nobody expected. Reading the result
object confirms what the code meant to do; counting `credit_notes`,
`adjustments`, `invoices` and `invoice_lines` catches what it actually did.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import corrections, document_correction, models
from apps.billing.correction_models import CLASS_DOCUMENT, InvoiceDocumentInstance
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_016_bulk_corrections import (
    TODAY,
    a_corrected_bill,
    an_issued_bill,
    money_row_counts,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db


def a_document_case_impact(invoice, *, reasons=("customer_name",)):
    return corrections.build_impact(invoice, reason_codes=reasons, correction_class=CLASS_DOCUMENT)


def test_us_bil_031_tc1__the_preview_shows_zero_and_says_none_four_times(brazos, dana):
    """TC-1 — all nine sections render, and four of them say "none".

    *"money delta $0.00 · credit note none · rebill none · journal entries none
    · balance before $0.00 → after $0.00 · documents: one reissued instance."*
    The point of rendering the money sections at all is that an approver must
    SEE that nothing moves rather than infer it from an absent section.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        impact = a_document_case_impact(bill)

        assert impact.delta == Decimal("0")
        assert impact.corrected_total == impact.original_total
        assert impact.documents == (
            "one reissued document instance — no credit note, no rebill, no posting",
        )
        assert impact.reallocation_plan == ("nothing re-allocates — no money moved.",)
        assert "reprints the document" in impact.mechanism
        assert all(not line.moved for line in impact.lines)


def test_us_bil_031_tc2__execution_writes_no_money_row_of_any_kind(brazos, dana):
    """TC-2 — asserted by counting rows before and after, not by inspection."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        before = money_row_counts(brazos)

        result = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            master_data_ref="customers:account-edit-4471",
            on_date=TODAY,
            actor=dana,
        )

        assert (
            money_row_counts(brazos) == before
        ), "BR-BIL-041 class D: no credit note, no rebill, no adjustment, no line"
        instance = InvoiceDocumentInstance.objects.get(pk=result.document_instance_id)
        assert instance.instance_no == 1
        assert instance.payload["customer_name"] == "Sarah Whitfield"
        assert (
            instance.payload["service_address"] == "1408 Bluestem Ln"
        ), "everything the document said that was RIGHT is carried through unchanged"
        assert instance.changed_fields == {"customer_name": ["Sara Whitfield", "Sarah Whitfield"]}
        assert instance.master_data_ref == "customers:account-edit-4471"


def test_us_bil_031_tc3__the_original_is_not_marked_corrected_and_does_not_move(brazos, dana):
    """TC-3 — the status stays `issued`/`paid`, **not** `corrected`.

    Nothing about what is owed was corrected, so saying "Corrected" on the bills
    list would tell a clerk the money changed. The payload is byte-identical
    afterwards, which is what makes the reissue a SECOND document rather than an
    edit of the first (BR-BIL-030).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        payload_before = dict(bill.bill_payload)

        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )

        after = models.Invoice.objects.get(pk=bill.pk)
        assert after.status == models.INVOICE_ISSUED
        assert after.bill_payload == payload_before
        assert after.total == Decimal("247.870000")


def test_us_bil_031_tc4__a_document_case_that_moves_money_is_refused(brazos, dana):
    """TC-4 (negative) — BR-BIL-043, and the case it is written for.

    A clerk opens a case with reason "customer name" (class D) and the
    recomputation moves $19.92 because the READ was also wrong. **Refused**,
    naming the delta, before anything is written. Re-opened with "wrong read" it
    proceeds as a restatement.

    PROVED RED against a build without the guard — see the lane report for the
    verbatim failure.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        before = money_row_counts(brazos)

        moving = corrections.build_impact(
            bill,
            reason_codes=("customer_name",),
            correction_class=CLASS_DOCUMENT,
        )
        # A D-class impact never recomputes, so the delta is $0.00 by
        # construction. The refusal is asserted on the guard itself, handed the
        # impact a wrong-reason case WOULD produce: the recomputation moved.
        moving = corrections.BillImpact(**{**moving.__dict__, "delta": Decimal("-19.92")})
        with pytest.raises(BillingRuleError) as refusal:
            corrections.refuse_unless_class_matches_money(moving)
        assert "does not change money" in str(refusal.value)
        assert "-19.92" in str(refusal.value)

        with pytest.raises(BillingRuleError):
            document_correction.execute_document_correction(
                bill,
                impact=moving,
                corrected_payload={"customer_name": "Sarah Whitfield"},
                on_date=TODAY,
                actor=dana,
            )
        assert money_row_counts(brazos) == before
        assert InvoiceDocumentInstance.objects.count() == 0

        # The same bill under the right reason is an ordinary restatement.
        restatement = corrections.build_impact(
            bill,
            reason_codes=("wrong_read",),
            correction_class="restatement",
            corrected=a_corrected_bill(bill),
        )
        assert restatement.delta == Decimal("-19.920000")


def test_us_bil_031_tc4b__a_payload_key_that_moves_money_is_refused(brazos, dana):
    """BR-BIL-043 at the field level — the allow-list, and why it is one.

    A "document correction" that edited `total` or a line would move money
    through a path with no credit note and no ledger entry — worse than the case
    TC-4 guards, because there would be no delta for anything to notice.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        with pytest.raises(BillingRuleError) as refusal:
            document_correction.execute_document_correction(
                bill,
                impact=a_document_case_impact(bill),
                corrected_payload={"total": "1.00"},
                on_date=TODAY,
                actor=dana,
            )
        assert "may not change total" in str(refusal.value)


def test_us_bil_031_tc5__the_case_records_the_master_data_change_and_performs_none(brazos, dana):
    """TC-5 (negative) — BR-BIL-049: two transactions, two audit trails.

    The customers-module edit governs FUTURE documents; this case decides only
    what the already-sent document says. The reference is RECORDED and the edit
    is not offered — there is no import in `document_correction.py` that could
    reach `apps.customers`.
    """
    import apps.billing.document_correction as module

    source = open(module.__file__).read()
    assert "apps.customers" not in source.replace("`apps/customers`", "")
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        result = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            master_data_ref="customers:customer-1042",
            on_date=TODAY,
            actor=dana,
        )
        instance = InvoiceDocumentInstance.objects.get(pk=result.document_instance_id)
        assert instance.master_data_ref == "customers:customer-1042"


def test_us_bil_031_tc6__a_later_reprint_renders_the_corrected_copy(brazos, dana):
    """TC-6 — OQ-169 CLOSED. **PO 2026-08-12: _"Reissue a corrected copy"_.**

    July's bill went out with the customer's name spelt `Sara Whitfield` and the
    money right. The case renders a NEW instance from a corrected copy of the
    snapshot and attaches it to the original bill; the bill itself is untouched
    (BR-BIL-004). With two documents on file, a later reprint, re-send or
    dispute copy renders **the corrected one** — *"because that is the document
    the customer is entitled to"*.

    This case USED to assert `NotImplementedError("OQ-169")`. It is rewritten
    rather than deleted so the reversal stays visible: the question was answered,
    not quietly dropped.

    The original is RETAINED and stays reachable by id — it is what the customer
    actually received — and the invoice's own frozen payload never moves, which
    is the whole reason the reissue is a second row (hard rule 4 · BR-BIL-030).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")

        # Before any correction there is one document and the default is it.
        original = document_correction.default_document_for_reprint(bill)
        assert original.source == document_correction.REPRINT_SOURCE_ORIGINAL
        assert original.instance_no == 0 and original.instance_id is None
        assert original.payload["customer_name"] == "Sara Whitfield"

        result = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            master_data_ref="customers:account-edit-4471",
            on_date=TODAY,
            actor=dana,
        )

        chosen = document_correction.default_document_for_reprint(bill)
        assert chosen.source == document_correction.REPRINT_SOURCE_REISSUE
        assert chosen.instance_no == 1
        assert chosen.instance_id == result.document_instance_id
        assert chosen.payload["customer_name"] == "Sarah Whitfield"
        # BR-BIL-026/031: the reissue renders on the pin the ORIGINAL carries.
        assert str(chosen.template_id) == str(bill.template_id)
        assert chosen.template_version == bill.template_version

        # The misspelt document is still on file and still says what it said.
        kept = InvoiceDocumentInstance.objects.filter(invoice=bill)
        assert kept.count() == 1, "the original is on the invoice, never copied to a row"
        assert models.Invoice.objects.get(pk=bill.pk).bill_payload["customer_name"] == (
            "Sara Whitfield"
        )


def test_us_bil_031_tc6b__with_two_reissues_the_default_is_the_latest(brazos, dana):
    """The ruling reaches past the case the PO was shown: *"the corrected one"*.

    Instance 2 is the copy the utility now says the document should have said, so
    it is the one the customer is entitled to and the one a reprint renders.
    Instance 1 was itself superseded.

    This case USED to pin DEF-084 as data: `execute_document_correction` composed
    every reissue from the INVOICE's frozen payload, never from the instance
    before it, so this second reissue — which fixes the address — brought the
    misspelt name back, and the assertion below read `"Sara Whitfield"`. **The PO
    ruled on 2026-08-12: _"Accumilate"_**, and it is rewritten rather than deleted
    so the reversal stays visible. tc6d is the case written for the ruling.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        second = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill, reasons=("service_or_mailing_address",)),
            corrected_payload={"service_address": "22 Rowan Way"},
            on_date=TODAY,
            actor=dana,
        )

        chosen = document_correction.default_document_for_reprint(bill)
        assert chosen.instance_no == 2
        assert chosen.instance_id == second.document_instance_id
        assert chosen.payload["service_address"] == "22 Rowan Way"
        # DEF-084 closed: the name fix instance 1 made is still there.
        assert chosen.payload["customer_name"] == "Sarah Whitfield"


def test_us_bil_031_tc6d__two_corrections_accumulate_and_both_fixes_survive(brazos, dana):
    """DEF-084 — **PO 2026-08-12, verbatim: _"Accumilate"_.**

    The scenario the ruling was given, asserted rather than described: July's bill
    goes out with the name misspelt *Sara Whitfield*. A clerk fixes the name →
    instance 1 reads *Sarah Whitfield*. A week later somebody fixes the service
    address → instance 2 must carry **the corrected address AND the corrected
    name**. Before the fix instance 2 was composed from the invoice's frozen
    payload and brought the misspelt name back, and the reprint ruling of the same
    day makes instance 2 the document the customer actually receives — so the
    second correction silently undid the first on the paper in the envelope.

    Hard rule 4 is asserted in the same test, because the fix must not buy
    accumulation with an edit: the invoice's own payload is byte-identical
    afterwards and instance 1 still says exactly what it said, reachable by id.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        payload_before = dict(bill.bill_payload)
        before = money_row_counts(brazos)

        first = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        second = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill, reasons=("service_or_mailing_address",)),
            corrected_payload={"service_address": "22 Rowan Way"},
            on_date=TODAY,
            actor=dana,
        )

        instance_2 = InvoiceDocumentInstance.objects.get(pk=second.document_instance_id)
        assert instance_2.instance_no == 2
        assert instance_2.payload["service_address"] == "22 Rowan Way", "this correction's fix"
        assert instance_2.payload["customer_name"] == "Sarah Whitfield", (
            "DEF-084: the name fix instance 1 made is CARRIED FORWARD, not reverted — "
            "corrections accumulate (PO 2026-08-12)"
        )
        # The reprint ruling makes this the document the customer receives.
        chosen = document_correction.default_document_for_reprint(bill)
        assert chosen.instance_id == second.document_instance_id
        assert chosen.payload["customer_name"] == "Sarah Whitfield"
        assert chosen.payload["service_address"] == "22 Rowan Way"
        # `changed_fields` is what THIS correction changed on the document it
        # supersedes — instance 2 did not touch the name and must not claim to.
        assert instance_2.changed_fields == {
            "service_address": ["1408 Bluestem Ln", "22 Rowan Way"]
        }

        # Hard rule 4 — nothing behind the accumulation was rewritten.
        assert models.Invoice.objects.get(pk=bill.pk).bill_payload == payload_before
        instance_1 = InvoiceDocumentInstance.objects.get(pk=first.document_instance_id)
        assert instance_1.payload["customer_name"] == "Sarah Whitfield"
        assert instance_1.payload["service_address"] == "1408 Bluestem Ln", (
            "the superseded instance still says what the customer was sent the second "
            "time — accumulation composes a NEW row and never edits the one before it"
        )
        assert money_row_counts(brazos) == before


def test_us_bil_031_tc6e__a_third_correction_keeps_all_three(brazos, dana):
    """A chain that works for two and breaks at three is the same defect one step on.

    Three fixes on one bill — name, then address, then the name again once the
    utility learns she spells it *Whitfield-Nunez*. Instance 3 must carry the
    address fix from instance 2 as well as its own name fix, and its
    `changed_fields` must diff against **instance 2**: the value it superseded is
    *Sarah Whitfield*, not the *Sara Whitfield* on the original bill, which no
    document in this chain has said since instance 1.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")

        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill, reasons=("service_or_mailing_address",)),
            corrected_payload={"service_address": "22 Rowan Way"},
            on_date=TODAY,
            actor=dana,
        )
        third = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield-Nunez"},
            on_date=TODAY,
            actor=dana,
        )

        instance_3 = InvoiceDocumentInstance.objects.get(pk=third.document_instance_id)
        assert instance_3.instance_no == 3
        assert instance_3.payload["customer_name"] == "Sarah Whitfield-Nunez"
        assert (
            instance_3.payload["service_address"] == "22 Rowan Way"
        ), "DEF-084 at three: the address fix from instance 2 survives instance 3"
        assert instance_3.changed_fields == {
            "customer_name": ["Sarah Whitfield", "Sarah Whitfield-Nunez"]
        }, "the 'was' is the document this one supersedes, not the original bill"
        # Everything the ORIGINAL said that nobody corrected is still carried.
        assert instance_3.payload["account_no"] == bill.bill_payload["account_no"]

        chosen = document_correction.default_document_for_reprint(bill)
        assert chosen.instance_no == 3
        assert chosen.payload == instance_3.payload
        # Hard rule 4 — three corrections and the bill still says what it said.
        assert models.Invoice.objects.get(pk=bill.pk).bill_payload["customer_name"] == (
            "Sara Whitfield"
        )
        assert [
            row.instance_no for row in InvoiceDocumentInstance.objects.order_by("instance_no")
        ] == [
            1,
            2,
            3,
        ]


def test_us_bil_031_tc6f__re_supplying_what_the_latest_instance_already_says_is_refused(
    brazos, dana
):
    """tc9's rule, read against the document the correction actually composes from.

    A clerk fixes the name, then somebody submits the same fix again. The value
    differs from the ORIGINAL bill, so a refusal computed against the invoice
    would let it through and write instance 2 as a byte-identical twin of
    instance 1 — two documents on file and no way to say which one anybody meant,
    which is exactly what BR-BIL-041 refuses.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        with pytest.raises(BillingRuleError) as refusal:
            document_correction.execute_document_correction(
                bill,
                impact=a_document_case_impact(bill),
                corrected_payload={"customer_name": "Sarah Whitfield"},
                on_date=TODAY,
                actor=dana,
            )
        assert "already matches" in str(refusal.value)
        assert InvoiceDocumentInstance.objects.filter(invoice=bill).count() == 1


def test_us_bil_031_tc6c__a_bill_with_no_locked_document_has_nothing_to_reprint(brazos, dana):
    """BR-CUS-040: a reprint renders the ISSUED document and never recomputes.

    A bill carrying no locked payload has no issued document to render, and
    rebuilding one from today's customer and premises rows would print today's
    facts over a historical period — the exact failure the snapshot prevents. So
    it refuses, in the same words and on the same rule as the execute path.

    The bill is CREATED without a payload rather than an issued one being
    stripped of its own: an UPDATE on an issued invoice is what hard rule 4 and
    the `0006` trigger forbid, and a test that reached for one would pass on
    SQLite and fail against Postgres for the right reason.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            bill_run=run,
            invoice_no="BL-2608-018411",
            service_date=date(2026, 7, 31),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            status=models.INVOICE_ISSUED,
            subtotal=Decimal("0"),
            tax_total=Decimal("0"),
            total=Decimal("0"),
        )
        assert bill.bill_payload is None
        with pytest.raises(BillingRuleError) as refusal:
            document_correction.default_document_for_reprint(bill)
        assert "BL-2608-018411" in str(refusal.value)


def test_us_bil_031_tc8__a_second_reissue_is_a_second_instance_never_an_edit(brazos, dana):
    """BR-BIL-030's argument, applied to the artifact it created.

    A reissued document is what the customer was sent the SECOND time, so it is
    a snapshot for the same reason the original is. Correcting a reissue counts
    up to instance 2; nothing is ever rewritten. (The database enforces this with
    an append-only trigger on Postgres; the service layer is what SQLite runs.)
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        first = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        second = document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill, reasons=("service_or_mailing_address",)),
            corrected_payload={"service_address": "22 Rowan Way"},
            on_date=TODAY,
            actor=dana,
        )
        instances = InvoiceDocumentInstance.objects.filter(invoice=bill).order_by("instance_no")
        assert [row.instance_no for row in instances] == [1, 2]
        assert first.document_instance_id != second.document_instance_id
        # Instance 0 is NOT stored: the original lives on the invoice. That
        # numbering was chosen while OQ-169 was open, and it is what the closed
        # ruling now leans on — `default_document_for_reprint` returns the
        # HIGHEST instance_no, so a copied "instance 0" row would be a second
        # claimant to a question the PO has answered (tc6).
        assert not instances.filter(instance_no=0).exists()


def test_us_bil_031_tc9__a_reissue_that_changes_nothing_is_refused(brazos, dana):
    """A second identical document leaves two on file and no way to tell them
    apart — which is the ambiguity, not a fix for it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        with pytest.raises(BillingRuleError) as refusal:
            document_correction.execute_document_correction(
                bill,
                impact=a_document_case_impact(bill),
                corrected_payload={"customer_name": "Sara Whitfield"},
                on_date=TODAY,
                actor=dana,
            )
        assert "already matches" in str(refusal.value)


def test_us_bil_031_tc7__a_document_case_never_reaches_another_tenants_bill(brazos, dana):
    """TC-7 (isolation) — the instance is scoped by the invoice it hangs from.

    The RLS half is the G5 suite's against Postgres; this is the inner
    guarantee, taken from the invoice row rather than from ambient context — the
    same reasoning `documents._lines_of` records.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        document_correction.execute_document_correction(
            bill,
            impact=a_document_case_impact(bill),
            corrected_payload={"customer_name": "Sarah Whitfield"},
            on_date=TODAY,
            actor=dana,
        )
        assert (
            InvoiceDocumentInstance.objects.filter(tenant=brazos).count()
            == InvoiceDocumentInstance.objects.count()
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-031@c41f9a2 (the packet apps/billing/document_correction.py carries — these
#         are that slice's tests, stamped here on first amendment; G1/G11 scan 06-backend/apps
#         only, so this trailer is convention rather than gate-enforced)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no S30 correction endpoint exists) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · this file 15/15✔ · backend suite 2061 passed, 132 skipped,
#         1 xfailed✔ · run_gates 17-PASS/3-FAIL — all three failures belong to
#         other live lanes and none touch billing's document path (G1+G11 on
#         07-frontend/src/features/tenancy/SettingsTimezone.test.tsx, the timezone
#         lane's untrailered file; G8 on apps/billing/backbill.py:89, the
#         back-bill lane, which went FAIL mid-session between two runs of this
#         lane's own gate sweep).
# exceptions: (1) AMENDED 2026-08-15 (DEF-084 lane) — tc6d, tc6e and tc6f added
#         and tc6b flipped. **PROVED RED FIRST** (hard-won law 7) against the
#         unfixed build, verbatim:
#           tc6d  AssertionError: DEF-084: the name fix instance 1 made is
#                 CARRIED FORWARD, not reverted — corrections accumulate
#                 (PO 2026-08-12) / assert 'Sara Whitfield' == 'Sarah Whitfield'
#           tc6e  AssertionError: DEF-084 at three: the address fix from
#                 instance 2 survives instance 3 /
#                 assert '1408 Bluestem Ln' == '22 Rowan Way'
#           tc6f  Failed: DID NOT RAISE BillingRuleError
#         The first is the misspelt name coming back on the document the reprint
#         ruling puts in the customer's envelope — the defect, measured.
#         (2) tc6b's `assert chosen.payload["customer_name"] == "Sara Whitfield"`
#         PINNED THE DEFECT AS DATA while it was unruled. It is flipped, not
#         deleted, so the reversal stays visible in one file.
#         (3) THE THREE-CORRECTION CHAIN (tc6e) IS THIS LANE'S READING OF A CASE
#         THE PO WAS NOT SHOWN — they were shown two. Instance 3 composes from
#         instance 2 for the same reason instance 2 composes from instance 1, and
#         its `changed_fields` diffs the document it SUPERSEDES rather than the
#         original bill. Stated so it can be disagreed with.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
