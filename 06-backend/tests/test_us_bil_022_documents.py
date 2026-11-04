# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-022 (the pin at issue; a reprint renders the pinned version
#           forever)   Screens: S30 (document panel) · S22 (Print bill)
# Rules:    BR-BIL-026 (pinned template + version; publishing affects only
#           future bills) · BR-BIL-030 (the locked instance; the document joins
#           nothing live) · BR-BIL-031 (payload version is the DATA contract) ·
#           BR-BIL-032 (the instance ties out to its rows) · BR-BIL-033 (a
#           failed render REFUSES the issue) · BR-BIL-035 (the balance-forward
#           figures are stamped) · BR-BIL-055 (a break never blocks the run) ·
#           BR-CUS-040 (a reprint renders, never recomputes) · BR-RAT-003
#           (round at display only) · CLAUDE.md rule 2 (money) · rule 3 (units)
# ───────────────────────────────────────────────────────
"""What the bill document renders FROM, and what it refuses.

TWO CASES CARRY THE WHOLE FILE, and both are about the same failure — a
document that quietly tells a customer something the immutable rows do not say.

`tc1` renames the account holder AFTER the bill is issued and asserts the
document still prints the name that was stamped. `tc2` asserts the render
issues exactly ONE database query, so a live join fails on the count even in
the case where it happens to return the same string. The first is the rule; the
second is the rule made structural, because a renderer only has to reach for
ONE missing field once for the guarantee to be gone.

`tc3`/`tc4` are the other half: a bill renders on the version PINNED to it, not
on the version the tenant published since (BR-BIL-026, US-BIL-022 TC-2/TC-3),
and `tc5` proves the door US-BIL-022 TC-4 says does not exist is really not
there.

`tc17`–`tc17c` are the two rulings of 2026-08-12 — *"issue and report it"*
(OQ-117) and *"print a substitution"* (OQ-150) — and what they really test is
the word REPORT. Issuing was never the hard half: this module already issued a
bill it could not print a total for. The half that did not exist is somebody
being TOLD, and `tc17` fails on a report that has no bill number in it, on a
report with no next step in it, and on a report that never leaves the return
value `issue.py` throws away.

`tc12`–`tc16` are the PAGE (added 2026-08-11 with the PDF serialisation), and
`tc12` is the one that would not exist if nobody had thought about it:
**determinism**. Two renders of one bill must be the same bytes, and almost
every PDF writer breaks that by default with a creation timestamp and a random
document id — invisibly, because every other test reads what the page SAYS.
`tc13` is the anti-drift guard that makes *"one structure, two serialisations"*
a guarantee rather than a description of today's code; `tc14` is BR-BIL-033 for
the half the customer actually holds; `tc15` does the job a PDF reader would do
if one were installed, which it is not.

WHAT THESE TESTS DO NOT COVER, stated so nobody reads a green run as more than
it is: the tenant's edited template BODY (no `bill_template_versions` table),
the DESIGNED bill on paper — the page here is BR-BIL-036's floor, not a logo, a
usage graph or a barcode (OQ-149) — storage and delivery (no table for either),
and the epic's TC-5/TC-6 — a pinned version's delete-lock and the cross-tenant
reprint — which need the template tables and the isolation suite respectively.

⚠ THE LINE ABOVE PREVIOUSLY READ *"PDF output (no PDF library in this build)"*
and was true when written. There is still no PDF library; there is now a PDF.
"""

import html
import logging
import re
import uuid
from decimal import Decimal

import pytest

from apps.billing import documents, issue, models, payments_seam
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    DUE_DATE,
    ISSUED_AT,
    SUBTOTAL,
    TAX_TOTAL,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: A second published template version, of the kind BR-BIL-026 says must NOT
#: reach a bill issued before it. Only ever registered inside a test.
NEWER_TEMPLATE_VERSION = TEMPLATE_VERSION + 1


def a_contact(tenant, account, full_name):
    """The live master-data row the customer name comes from.

    `customers.selectors.primary_contact_name` reads this; the SNAPSHOT holds a
    copy stamped when the bill was priced. The whole of BR-BIL-030 is that
    those two are allowed to disagree, and that the bill shows the copy.
    """
    from apps.customers import models as customer_models

    return customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name=full_name, is_primary=True
    )


def a_stage6_payload(account_no="A-10432", customer_name="Sarah Chen"):
    """The payload STAGE 6 ACTUALLY STAMPS — key for key, not an idealised one.

    Mirrors `apps/billing/stages/assemble_document._snapshot_payload` on top of
    `gather._snapshot_for`. Written out here rather than driving the real run,
    because what these tests are about is the DOCUMENT, and using a hand-made
    payload richer than the real one would prove the renderer copes with data
    the product never produces. When stage 6 stamps more, this fixture and
    `tc8`'s absence list are the two places that must move together.
    """
    return {
        "account_no": account_no,
        "customer_name": customer_name,
        "unit_id": None,
        "unit_label": "Unit A",
        "plan": {"id": None, "name": "Residential Standard", "version": 3},
        "service_date": "2026-06-30",
        "currency": "USD",
        "period": {"cycle_days": 30, "service_days": 30},
        "tax_exempt": True,
        "services": [
            {
                "code": "electric",
                "measured": True,
                "estimated": False,
                "absent_reason": None,
            }
        ],
    }


def an_issued_bill(
    tenant, dana, *, account=None, run=None, before_issue=None, **overrides
):
    """One issued bill, through the real issue path — pin and all.

    ⚠ `before_issue` was ADDED 2026-08-16 and it closes DEF-155. Two cases in
    this file set up their fixture by UPDATEing an ALREADY-ISSUED bill — tc9 the
    line's unit price, tc10 the payload version — and the immutability triggers
    refuse both, correctly and loudly. So both had been ERRORING rather than
    failing since those triggers landed, which reads identically to two tests
    nobody wrote, because `run_gates` G4 runs `pytest -m golden` and no gate
    runs a full pytest.

    The hook is handed the DRAFT. That is the whole fix and it is also the only
    shape production has: a draft is mutable, an issued bill is not, and the way
    a real value gets onto an issued bill is to be there before the issue.
    """
    account = account or an_account(dana, tenant)
    run = run or an_authorised_run(tenant, dana)
    overrides.setdefault("bill_payload", a_stage6_payload())
    draft = a_priced_draft(tenant, account, run, **overrides)
    if before_issue is not None:
        before_issue(draft)
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
    )


def two_registered_layouts(monkeypatch):
    """A world where a NEWER template version exists and is published.

    This is US-BIL-022 TC-2's setup — *"v4 published Sep 1; BL-2608-018410
    reprinted Sep 15 → renders v3"* — expressed with the layouts this build
    actually has. The v2 layout is deliberately distinguishable in one glance,
    because a test that could not tell the two apart would pass on either.

    BOTH serialisations are registered on the newer version, because a `Layout`
    carries the pair: if the pin selected the HTML layout and the PDF fell back
    to the built-in stand-in, BR-BIL-026 would be kept on screen and broken on
    the paper the customer actually holds. `tc3` asserts both.
    """
    monkeypatch.setitem(
        documents.LAYOUTS,
        NEWER_TEMPLATE_VERSION,
        documents.Layout(
            html=lambda doc: "<article>NEWER</article>",
            pdf=lambda doc: documents.PdfSerialisation(
                data=b"%PDF-NEWER", page_count=1
            ),
        ),
    )
    monkeypatch.setattr(documents, "LATEST_REGISTERED_VERSION", NEWER_TEMPLATE_VERSION)


def test_us_bil_022_tc1__the_document_renders_the_stamped_name_not_the_current_one(
    brazos, dana
):
    """BR-BIL-030 — the PO's *"keep lock data for that bill and save the instance"*.

    Sarah Chen is billed in June and marries in August. The customer record is
    updated, correctly and legitimately, by the customers module (BR-BIL-049:
    *"a correction never edits master data, and a master-data edit is never a
    correction"*). The June bill must still say Sarah Chen, because that is the
    document she was sent and the one she may one day dispute.

    Nothing here runs an edit against the bill. That is exactly why hard rule 4
    does not catch this on its own: a renderer that joined live would rewrite
    what an issued financial document SAYS without writing a single row.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        contact = a_contact(brazos, account, "Sarah Chen")
        bill = an_issued_bill(brazos, dana, account=account)

        contact.full_name = "Sarah Miller"
        contact.save(update_fields=["full_name"])

        document = documents.render_invoice(bill)

        customer = next(f for f in document.meta if f.label == "Customer")
        assert customer.value == "Sarah Chen", (
            "the document printed the CURRENT customer name over a period billed "
            "under the old one (BR-BIL-030)"
        )
        assert "Sarah Chen" in document.body
        assert "Sarah Miller" not in document.body


def test_us_bil_022_tc2__the_render_touches_the_invoices_own_rows_and_nothing_else(
    brazos, dana, django_assert_num_queries
):
    """BR-BIL-030 made structural — the guarantee as a query count.

    TWO queries, and the test names BOTH so the count cannot be raised again by
    someone who only wanted it to go green:

      1. the invoice's own `invoice_lines`. Not master data — this document's
         financial record, frozen by the same trigger that freezes its money.
      2. the PINNED `bill_template_versions` row, added 2026-08-16 when the
         platform layout library landed and `_layout_for` began resolving the
         `layout_key` the bill's own pin names.

    ⚠ **THE COUNT MOVED FROM 1 TO 2 AND THE SECOND QUERY IS ASSERTED BY NAME.**
    A bare `django_assert_num_queries(2)` would let any future reach into
    customers, premises, units, rating or the service catalog take the free slot
    — which would quietly undo the guarantee this test exists for. So the SQL is
    read: exactly one statement may touch `bill_template_versions`, exactly one
    may touch `invoice_lines`, and nothing else may be queried at all.

    The second query is still not a live join: it is a lookup BY THE PIN
    (`template_id` + `version_no`), of a row that is content-frozen once
    published (migration 0019). Publishing a new version cannot change it, which
    is why reading it can never show something other than what was sent.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

        with django_assert_num_queries(2) as captured:
            documents.render_invoice(bill)

        statements = [entry["sql"] for entry in captured.captured_queries]
        touched = " ".join(statements)
        assert (
            sum("bill_template_versions" in sql for sql in statements) == 1
        ), statements
        assert sum("invoice_lines" in sql for sql in statements) == 1, statements
        for master_data in ("accounts", "premises", "units", "rate_plans", "services"):
            assert f" {master_data} " not in touched, (
                f"the render reached into {master_data} — BR-BIL-030 says the document "
                f"comes from the frozen snapshot and this bill's own lines, and nothing "
                f"else. Queries: {statements}"
            )


def test_us_bil_022_tc3__a_bill_renders_its_pinned_version_after_a_newer_is_published(
    brazos, dana, monkeypatch
):
    """BR-BIL-026 / US-BIL-022 TC-2 — *"renders v3, the pinned version"*.

    A newer template version is registered and is the latest published. The
    bill issued before it must render exactly as it did — *"a bill issued on v3
    renders on v3 in 2031 even if v9 is published"* — and the document must say
    which version it rendered on, so nobody has to take the assertion's word.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        two_registered_layouts(monkeypatch)

        document = documents.render_invoice(bill)

        assert document.template_version == TEMPLATE_VERSION
        assert document.body != "<article>NEWER</article>", (
            "the reprint rendered the NEWEST registered layout instead of the bill's "
            "pinned version (BR-BIL-026)"
        )
        # The PAPER follows the pin too. This is the half a customer holds, and
        # a pin honoured only in the HTML would be a pin honoured nowhere that
        # matters (BR-BIL-036 — print is the primary channel).
        assert document.pdf != b"%PDF-NEWER", (
            "the reprint's PDF rendered the NEWEST registered layout instead of the "
            "bill's pinned version (BR-BIL-026)"
        )
        assert document.pdf.startswith(b"%PDF-1.4")
        assert str(TEMPLATE_VERSION) in document.layout_source


def test_us_bil_022_tc4__two_pins_two_renders_from_one_code_path(
    brazos, dana, monkeypatch
):
    """US-BIL-022 TC-3 — the rebill pins the CURRENT version; the original keeps its own.

    *"The rebill pins v4 (current at rebill issue); the original still renders
    v3 — two pins, both stable."* One renderer, two bills, two different
    documents, and neither one moved because the other exists.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        original = an_issued_bill(brazos, dana, account=account, run=run)
        two_registered_layouts(monkeypatch)
        rebill = a_priced_draft(
            brazos, account, run, invoice_no="BL-2607-000102", bill_type="rebill"
        )
        rebill = issue.issue_invoice(
            rebill,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=NEWER_TEMPLATE_VERSION,
        )

        assert documents.render_invoice(original).body != "<article>NEWER</article>"
        assert documents.render_invoice(rebill).body == "<article>NEWER</article>"
        assert documents.render_invoice(original).pdf != b"%PDF-NEWER"
        assert documents.render_invoice(rebill).pdf == b"%PDF-NEWER"


def test_us_bil_022_tc5__there_is_no_render_on_latest_door(brazos, dana):
    """US-BIL-022 TC-4 — *"No such option exists — pinned version only."*

    A caller asking for a different version than the one pinned is refused
    rather than obeyed. This is the case that keeps the pin from becoming a
    default: an argument that silently overrode it would be a render-on-latest
    flag wearing a different name, and the refusal is what makes the reprint
    reproducible for the full retention window.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

        with pytest.raises(BillingRuleError, match="pinned to template version"):
            documents.render_invoice(bill, template_version=NEWER_TEMPLATE_VERSION)

        with pytest.raises(BillingRuleError, match="pinned to template"):
            documents.render_invoice(bill, template_id=uuid.uuid4())


def test_us_bil_022_tc6__a_bill_that_cannot_render_does_not_issue(brazos, dana):
    """BR-BIL-033, CONFIRMED (PO 2026-08-10, OQ-089) — the rule this lane exists for.

    *"Render BEFORE issue; a failed render refuses the issue."* The unrenderable
    bill here carries a payload the layout does not declare it can read
    (BR-BIL-031), which is the realistic shape of the failure: the data contract
    moved and this bill's shape is no longer one the pinned template
    understands.

    Both halves are asserted. The bill does NOT issue — it is still a draft
    afterwards, with no due date, no pin and nothing immutable, exactly as
    EP-BIL-02 TC-9 requires. And the batch is unharmed: the other bill issues,
    the break is reported with a code the screen can group on, and no rollback
    of the morning's work happens (BR-BIL-055).
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        good = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-1"),
            run,
            invoice_no="BL-2607-000201",
        )
        bad = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-2"),
            run,
            invoice_no="BL-2607-000202",
            payload_version=2,
        )

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        assert result.issued == (str(good.pk),)
        assert [(b.reason, b.invoice_no) for b in result.broken] == [
            (issue.ISSUE_RENDER_FAILED, "BL-2607-000202")
        ]
        unrenderable = models.Invoice.objects.get(pk=bad.pk)
        assert unrenderable.status == models.INVOICE_DRAFT
        assert (unrenderable.due_date, unrenderable.template_version) == (None, None)
        assert models.Invoice.objects.get(pk=good.pk).due_date == DUE_DATE


def test_us_bil_022_tc7__br_bil_032_the_half_that_ties_out_and_the_half_that_cannot(
    brazos, dana
):
    """BR-BIL-032 (PROPOSED) — asserted where it can be, named where it cannot.

    THE ROWS TIE OUT EXACTLY, and the arithmetic is worth writing down because
    the issue lane recorded the opposite. `apps/rating/pricing/stages/finalize`
    rounds every line half-up to 2dp exactly once (BR-RAT-003) and `assemble`
    sets `total` to the SUM of those already-finalized lines, so there is no
    6dp remainder anywhere to lose: GT-10 is 82.08 + 18.50 + 8.13 + 8.30 =
    117.01 to the digit. The fixture here is the same shape — 82.08 + 18.50 +
    8.30 = 108.88 — and equality is safe, not approximate.

    THE PAYLOAD HALF CANNOT BE ASSERTED, and the reason is not rounding: stage
    6 stamps no total and no line set into `bill_payload`, so there is nothing
    to compare `invoices.total` TO. The second assertion below pins that gap.
    It goes RED the day stage 6 stamps a total — which is the day someone
    should be here writing the real tie-out, so the failure is the point.

    THE BILL HERE IS A DRAFT, and that is not a convenience. CORRECTED
    2026-08-11: this paragraph said *"A TAXED bill cannot be issued at all
    today"*, which was true until the PO closed OQ-116 (BR-BIL-069) and stopped
    being true the same day — a tax line names its tax now and resolves its
    authority's own 2200-series account. The fixture still uses a DRAFT, and
    for a reason that never depended on that: **the tie-out is a property of
    the STORED ROWS**, it holds identically at draft and at issue, and a draft
    keeps this case about the arithmetic instead of dragging in the release
    gate, a template pin and the GL map. `a_priced_draft(taxed=True)` builds a
    tax line with no tax behind it, so it would still refuse at issue —
    `test_us_bil_005_issue` tc31 is that case, and it is not this one's
    business.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        bill = a_priced_draft(
            brazos,
            an_account(dana, brazos),
            run,
            taxed=True,
            bill_payload=a_stage6_payload(),
        )

        line_sum = sum((line.amount for line in bill.lines.all()), Decimal("0.00"))
        assert line_sum == bill.total == SUBTOTAL + TAX_TOTAL == Decimal("108.88")

        assert "total" not in bill.bill_payload, (
            "stage 6 now stamps a total — BR-BIL-032's `bill_payload.total == "
            "invoices.total` is assertable and must be asserted, here and at issue"
        )
        assert "lines" not in bill.bill_payload


def test_us_bil_022_tc8__every_a19_field_the_snapshot_lacks_is_a_named_absence(
    brazos, dana
):
    """A19 §1 diffed against what renders — hard-won law 6, on paper instead of pixels.

    The prototype's residential bill (`05-prototype/UtilityBilling.html`, the
    "Bill · residential" designer) prints: masthead with the utility's name,
    address and phone · service address · bill date · service period · days ·
    AMOUNT DUE · due date · per-service groups headed "Electric · meter M-4021"
    with tier lines, usage and rate · a taxes band · current charges, previous
    balance, payments received, TOTAL AMOUNT DUE · a 12-month usage graph ·
    ways to pay · a late-fee footer · a remittance stub.

    Of those, the snapshot carries the account number, the customer name, the
    unit label, the services and their read state, and the period. This test
    asserts the rest are ABSENT AND NAMED — not blank, not fetched, not guessed.

    ⚠ **AMENDED 2026-08-15 (DEF-116) — TOTAL DUE HAS LEFT THIS LIST.** This
    docstring used to single it out: *"total due cannot be printed at all,
    because BR-BIL-035's balance-forward figures are not stamped and
    `invoices.total` is the current charges."* They are stamped now —
    `issue._stamp_balance_forward` writes them into the locked instance before
    the render, which is where BR-BIL-035 always said they belonged — so the
    three balance-forward names are asserted PRESENT here rather than absent.
    The reasoning that put them on the list stands for everything still on it:
    a bill whose largest number is a dash is visibly broken, and a bill whose
    largest number was fetched from live data is invisibly wrong.

    This account has NO earlier bill, so previous balance and payments both read
    **0.00** — computed zeros, from a seam that answered. The case where the
    seam CANNOT answer is `tests/test_us_bil_005_release_issue_api.py::…tc49`,
    and it must never render the same: those figures come back absent.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

        document = documents.render_invoice(bill)

        named = {a.field for a in document.absent}
        # ⚠ **THIS SET LOST FOUR NAMES ON 2026-08-31 (`DEF-2865`) AND THAT IS THE
        # DEFECT CLOSING, NOT A TEST WEAKENING.** It used to require
        # `utility_name`, `utility_contact`, `bill_date` and `cycle` to be
        # ABSENT, and every bill this product issued duly printed an em-dash for
        # all four — the PO's own BL-2608-000048 among them. They are STAMPED
        # now: the utility's name and contact at issue from the tenant profile,
        # the bill date and the cycle from the run. What is asserted below is
        # the mirror image, so this test still fails if the stamp is lost.
        assert {
            "utility_address",
            "service_address",
            "message",
            "ways_to_pay",
            "meter_no · prior_read · current_read",
        } <= named
        # `utility_address` and `service_address` stay on the list ABOVE for a
        # reason that is about this FIXTURE and not about the product: the
        # signup payload writes no mailing address, and `a_stage6_payload` is
        # hand-built and predates the gather-time service-address stamp. Both
        # are filled on a real bill; `tests/test_def_2865_bill_header.py` is
        # where that is asserted.
        assert not (
            {"utility_name", "utility_contact", "bill_date", "cycle"} & named
        ), (
            "DEF-2865 stamps the utility's identity at issue and the bill date and "
            "cycle from the run — an absence here means the stamp did not reach the "
            "payload the renderer reads"
        )
        assert next(f for f in document.masthead if f.label == "Utility").value == (
            "Brazos Bend Utilities"
        )
        assert all(
            a.br_ref and a.detail for a in document.absent
        ), "an absence with no rule and no reason is a blank with a label on it"
        assert not ({"total_due", "previous_balance", "payments_credits"} & named), (
            "BR-BIL-035's figures are stamped at issue since DEF-116 — an absence here "
            "means the stamp did not reach the payload the renderer reads"
        )

        printed = {field.label: field.value for field in document.summary}
        assert printed["Previous balance"] == "0.00 USD"
        assert printed["Payments & credits"] == "0.00 USD"
        assert printed["Current charges"] == "100.58 USD"
        assert printed["Total due"] == "100.58 USD"
        total_due = next(f for f in document.summary if f.label == "Total due")
        assert total_due.absent is None
        # The stub must never disagree with the box above it — a customer pays
        # from the stub.
        assert (
            next(f for f in document.stub if f.label == "Amount due").value
            == total_due.value
        )

        # And what the snapshot DOES carry is on the paper.
        assert next(f for f in document.meta if f.label == "Account").value == "A-10432"
        assert (
            next(f for f in document.meta if f.label == "Due date").value
            == DUE_DATE.isoformat()
        )
        # ⚠ `["electric"]` UNTIL `DEF-2852` (2026-08-31). The band is labelled
        # with the service's NAME now, from the same stamp that stopped the
        # charge blocks being headed with a UUID — B14 rule 32, no internal code
        # in the copy a human reads. This fixture's payload predates the stamp
        # and carries no `name`, so `_service_label` capitalises the code.
        assert [f.label for f in document.services] == ["Electric"]

        # Reported, on every document, rather than in a comment: the PDF is the
        # print FLOOR and not the tenant's designed bill, its character
        # repertoire is WinAnsi, no tenant template body, not handed to a print
        # vendor, no usage graph. `pdf_not_rendered` is GONE because it became
        # false on 2026-08-11 — hard-won law 1 runs in both directions, and a
        # build that kept reporting an absence it had closed would be lying the
        # other way. ⚠ `document_not_stored` went the same way on 2026-08-30
        # (CR-049 task 4): both serialisations are now frozen at issue, and the
        # HALF that is still owed — handing the stored page to a print vendor —
        # is what the replacement code names.
        assert {u["code"] for u in document.unavailable} == {
            "pdf_is_the_print_floor_not_a_designed_template",
            "pdf_character_repertoire_is_winansi",
            "run_problems_are_logged_and_not_stored",
            "tenant_designs_no_page_of_its_own",
            "document_stored_but_not_handed_to_a_print_vendor",
            # ⚠ `usage_history_not_available` went on 2026-08-30 (CR-052 task
            # 8): the eleven earlier periods ARE in the snapshot now, frozen at
            # issue from BR-MET-106's stored monthly grain.
            #
            # ⚠ AND ITS REPLACEMENT, `usage_history_stamped_but_not_drawn`,
            # WENT ON 2026-08-31 (CR-052 task 9) — SO THIS SET IS NOW ONE
            # SHORTER, NOT ONE DIFFERENT. That code said *"the printed page
            # does not yet plot it"*, and every layout now prints the twelve
            # months as a TABLE (the PO's own "table or grpah"), so it stopped
            # being true and was deleted in the commit that made it so. This
            # assertion going RED is what proved the absence was load-bearing.
            #
            # The half that IS still absent — a PLOTTED graph on paper — is
            # named inside `pdf_is_the_print_floor_not_a_designed_template`
            # rather than carrying a code of its own, because that entry is
            # already the list of what the print floor cannot do.
        }


def test_us_bil_022_tc9__money_comes_from_the_stored_rows_and_rounds_only_to_print(
    brazos, dana
):
    """CLAUDE.md rule 2 + rule 3, and BR-RAT-003's "display only".

    Every figure on the document is a stored one printed at 2dp with its
    currency: the line amounts as `invoice_lines.amount` and current charges as
    `invoices.total`. Nothing is re-priced, re-prorated or re-summed into a
    number the customer has not already been charged (BR-CUS-040).

    The quantity carries its unit — `684 kWh`, never `684` (rule 3) — and the
    UNIT PRICE is printed as stored rather than rounded, because a rate is not
    a line amount: quantizing $0.142000 to $0.14 would print a rate that does
    not reproduce the line it priced. The prototype shows `$0.1420` for the
    same reason.
    """

    def price_the_usage_line(draft):
        """The rate, set while the bill is still a DRAFT — see `an_issued_bill`.

        This used to run against the issued bill and the immutability trigger
        refused it (DEF-155). An issued line's unit price is frozen with the
        money, so the only lawful way to render one is for it to be there
        before the issue — which is also the only way production produces one.
        """
        line = draft.lines.get(kind="usage")
        line.unit_price = Decimal("0.142000")
        line.save(update_fields=["unit_price"])

    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, before_issue=price_the_usage_line)

        document = documents.render_invoice(models.Invoice.objects.get(pk=bill.pk))

        charges = next(f for f in document.summary if f.label == "Current charges")
        assert charges.value == f"{SUBTOTAL:.2f} USD" == "100.58 USD"
        rows = [row for group in document.groups for row in group.lines]
        usage = next(row for row in rows if row.quantity != documents.ABSENT_MARK)
        assert usage.quantity == "684 kWh"
        # ⚠ **AMENDED 2026-08-27 (OQ-620(a), DEF-1120).** This asserted `"0.142"`
        # — `documents._trim`'s output, which dropped trailing zeros and rounded
        # nothing. That was the right answer while no rule existed and the file
        # said so; the PO ruled one: *"What does a tariff rate show? Four
        # ($0.1420). A rate is not money and not a quantity - 4 decimal
        # places"*. A unit price is a RATE, so it pads to four places and KEEPS
        # its zeros. **Nothing about the money moved** — the amount below is
        # unchanged, and `684 × 0.142 = 82.08` either way; only the printed
        # rate gained the two zeros it was always priced at.
        assert usage.unit_price == "0.142"  # up to 4 places (PO 2026-10-02)
        assert usage.amount == "82.08 USD"
        assert "684 kWh" in document.body


def test_us_bil_022_tc10__an_unrenderable_payload_version_refuses(brazos, dana):
    """BR-BIL-031 — the payload is a DATA contract and the template DECLARES its range.

    *"A template DECLARES which payload versions it can render."* A bill whose
    payload shape the layout has never seen is refused rather than rendered
    from keys it is guessing at — because the alternative is a reprint that
    prints blanks wherever the contract moved, silently, on every historical
    bill at once.

    ⚠ THIS CASE HAD BEEN ERRORING, NOT FAILING, SINCE THE IMMUTABILITY TRIGGERS
    LANDED (DEF-155). It set `payload_version` on an ALREADY-ISSUED bill and the
    database refused, correctly — the version is frozen with the money. Setting
    it on the DRAFT instead revealed something better than the original case:
    such a bill **cannot be issued at all**, because BR-BIL-033 renders BEFORE
    issue and refuses on the failure. So the rule is asserted at both points it
    binds, and the second one is the one that matters — a bill that cannot be
    rendered never becomes immutable and unprintable.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run, bill_payload=a_stage6_payload())
        models.Invoice.objects.filter(pk=draft.pk).update(payload_version=2)
        draft.refresh_from_db()

        # 1 · the RENDERER refuses, naming the version and the declared range.
        with pytest.raises(BillingRuleError, match="carries payload version"):
            documents.render_invoice(
                draft, template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION
            )

        # 2 · and therefore the ISSUE refuses (BR-BIL-033: render before issue).
        # The bill is still a correctable draft and nothing immutable was made.
        with pytest.raises(BillingRuleError, match="carries payload version"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


def test_us_bil_022_tc11__a_draft_renders_against_the_pin_issue_is_about_to_write(
    brazos, dana
):
    """BR-BIL-033's mechanics — the pre-issue render is the SAME document.

    A draft has no pin, because the pin is written at issue. So the check that
    gates the issue is handed the pin the issue is about to write, and the
    document it produces is the document the customer gets — rendered on the
    same version, from the same locked instance, by the same code. A pre-issue
    check that rendered on some other template would be checking a document
    nobody ever receives.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(
            brazos, an_account(dana, brazos), run, bill_payload=a_stage6_payload()
        )

        before = documents.render_invoice(
            draft, template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION
        )
        after = documents.render_invoice(
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        )

        assert before.template_version == after.template_version == TEMPLATE_VERSION
        # The draft has no due date yet, so the two documents differ in exactly
        # the field issue fills in — and in nothing else.
        assert (
            next(f for f in before.meta if f.label == "Due date").value
            == documents.ABSENT_MARK
        )
        assert (
            next(f for f in after.meta if f.label == "Due date").value
            == DUE_DATE.isoformat()
        )
        # Filling in the TWO due-date cells — the meta band and the remittance
        # stub, which A19 §1.8 requires to agree — turns the pre-issue document
        # into the issued one, byte for byte. A blanket dash-replacement would
        # also swap every other absence and would pass on a renderer that had
        # changed something else entirely.
        filled = before.body.replace(
            f'<tr class="absent"><th scope="row">Due date</th><td>{documents.ABSENT_MARK}</td></tr>',
            f'<tr class="field"><th scope="row">Due date</th><td>{DUE_DATE.isoformat()}</td></tr>',
        ).replace(
            f'<tr class="field"><th scope="row">Due date</th><td>{documents.ABSENT_MARK}</td></tr>',
            f'<tr class="field"><th scope="row">Due date</th><td>{DUE_DATE.isoformat()}</td></tr>',
        )
        # ⚠ AMENDED 2026-08-15 (DEF-116) — ISSUE NOW FILLS IN FOUR THINGS, NOT
        # ONE, and this is the case that says which. BR-BIL-035's arrears are
        # stamped at issue (`issue._stamp_balance_forward`), so the summary box
        # and the remittance stub gain their figures at the same moment the due
        # date appears. A test that only knew about the due date would have
        # reported that as "the renderer changed something else entirely",
        # which is exactly what it is for — so the three names are listed ONE BY
        # ONE with the figures they take, and the byte-for-byte equality below
        # is untouched.
        #
        # THE PRE-ISSUE RENDER THAT MATTERS IS NOT THIS ONE. `before` is a
        # render this test performs on an unstamped draft; the render that GATES
        # the issue happens inside `issue_invoice` AFTER the stamp, so the
        # document BR-BIL-033 checks is still the document the customer gets —
        # which is what this case exists to protect.
        for label, value in (
            ("Previous balance", "0.00 USD"),
            ("Payments &amp; credits", "0.00 USD"),
            ("Total due", "100.58 USD"),
            ("Amount due", "100.58 USD"),
        ):
            filled = filled.replace(
                f'<tr class="absent"><th scope="row">{label}</th><td>{documents.ABSENT_MARK}</td></tr>',
                f'<tr class="field"><th scope="row">{label}</th><td>{value}</td></tr>',
            )
        # ⚠ AMENDED AGAIN 2026-08-31 (`DEF-2865`) — ISSUE NOW FILLS IN NINE
        # THINGS. A19 §1.1's masthead and §1.2's bill date and cycle were never
        # stamped by anything, so every bill this product issued printed an
        # em-dash for all of them; they are stamped at issue now, from the
        # tenant profile and the run.
        #
        # These four are listed BY NAME like the four above, and for the same
        # reason — a blanket dash-replacement would swap every other absence and
        # pass on a renderer that had changed something else entirely. What
        # differs is where their VALUES come from: the four above are figures
        # this fixture fixes, and these depend on the tenant the fixture
        # provisioned and the cycle `a_run` built. So the label is named here
        # and the value is read off the issued document, with the two that carry
        # a checkable fact asserted outright below.
        for label in ("Bill date", "Cycle"):
            stamped = next(
                field
                for field in (*after.masthead, *after.meta)
                if field.label == label
            )
            filled = filled.replace(
                f'<tr class="absent"><th scope="row">{label}</th><td>{documents.ABSENT_MARK}</td></tr>',
                f'<tr class="field"><th scope="row">{label}</th>'
                f"<td>{html.escape(str(stamped.value))}</td></tr>",
            )

        # ⚠ AMENDED 2026-09-07 (`DEF-BIL-4524`) — *Utility* and *Contact* MOVED
        # OUT OF THAT LIST BECAUSE THE MASTHEAD IS A LETTERHEAD NOW. It carries
        # no labels on either serialisation, so there is no `<th>Utility</th>`
        # to key a replacement on and the two stamped lines are patched by their
        # POSITION in the letterhead instead. The property this case exists for
        # is unchanged and is the reason this is not a blanket swap: *Address*
        # is deliberately left at `before`'s value, so a renderer that started
        # filling it in — or that changed anything else in the letterhead —
        # still fails the byte-for-byte equality below.
        def letterhead(fields):
            return "".join(
                f'<p class="{"utility" if index == 0 else "utility-line"}'
                f'{" absent" if field.absent else ""}">'
                f"{html.escape(str(field.value))}</p>"
                for index, field in enumerate(fields)
            )

        stamped_lines = list(before.masthead)
        for index, field in enumerate(after.masthead):
            if field.label in ("Utility", "Contact"):
                stamped_lines[index] = field
        assert letterhead(before.masthead) in filled, (
            "the letterhead this case patches is not in the pre-issue document — "
            "the markup moved and this replacement is now measuring nothing"
        )
        filled = filled.replace(letterhead(before.masthead), letterhead(stamped_lines))
        # `Address` is deliberately NOT in that list: this tenant's signup wrote
        # no mailing address, so it is an absence before AND after, and a stamp
        # that started filling it would break the equality below — correctly.
        assert (
            next(f for f in after.masthead if f.label == "Utility").value == brazos.name
        )
        assert (
            next(f for f in after.meta if f.label == "Bill date").value
            != documents.ABSENT_MARK
        )
        assert (
            next(f for f in after.meta if f.label == "Cycle").value
            != documents.ABSENT_MARK
        )
        # ⚠ AMENDED 2026-09-30 — ISSUE NOW ADDS ONE WHOLE ROW, NOT A FILLED
        # DASH: the remittance line on the stub (`CR-139-BRC07` `P5.10`, landed
        # in `955f1d64c` on 2026-09-23 — this case was red from that commit).
        # `remittance.compose_for_invoice` reads the stamped `total_due`, which
        # a draft does not have, so the draft carries NO `Scan` row at all (an
        # honest absence, never a scannable line for nothing) and the issued
        # bill carries one as the stub's last row. It is appended here by NAME
        # and its value is CHECKED rather than copied: the account, the bill
        # number and the amount this fixture fixes must all be in it, so a
        # line built from anything else still breaks the equality below.
        scan = next(f for f in after.stub if f.label == documents.LABEL_SCAN)
        assert f">{documents.LABEL_SCAN}<" not in before.body, (
            "the draft now carries a remittance line — it has no stamped total "
            "and must not (`compose_for_invoice` returns None)"
        )
        # Account, bill number, then the amount due in cents (100.58 USD, the
        # figure asserted above) — the check character after it is
        # `remittance`'s own subject and is not re-derived here.
        assert scan.value.startswith("A-10432$BL-2607-000101$10058"), scan.value
        stub_close = "</table></section></article></body></html>"
        assert filled.endswith(stub_close)
        filled = (
            filled[: -len(stub_close)]
            # DEF-BIL-10546 — the scan line sits in its own table under its
            # bars (`documents._stub_tables`), which are decoration.
            + "</table>"
            + documents._barcode_html(scan.value)
            + f'<table><tr class="field"><th scope="row">{documents.LABEL_SCAN}</th>'
            + f"<td>{html.escape(str(scan.value))}</td></tr>"
            + stub_close
        )
        assert filled == after.body

        with pytest.raises(BillingRuleError, match="carries no template pin"):
            documents.render_invoice(
                a_priced_draft(
                    brazos,
                    an_account(dana, brazos, account_no="A-3"),
                    run,
                    invoice_no="BL-2607-000303",
                )
            )


def pdf_text(pdf: bytes) -> str:
    """Every string the PAGE actually draws, in draw order, whitespace-collapsed.

    Reads the content streams directly, which is possible only because this
    build writes them UNCOMPRESSED — a deliberate property of `_pdf_file`, for
    exactly this reason and for the human who one day diffs two reprints.

    Collapsing whitespace is what makes `tc13` a real anti-drift guard rather
    than a formatting test: a value that wraps across two rows is two `Tj`
    strings, and the question being asked is whether the VALUE reached the
    page, not where the line broke.
    """
    drawn: list[str] = []
    for match in re.finditer(rb"\((.*?)\) Tj", pdf, re.S):
        raw = match.group(1)
        out = bytearray()
        index = 0
        while index < len(raw):
            if raw[index] == 0x5C:  # a backslash escapes the next byte
                index += 1
            out.append(raw[index])
            index += 1
        drawn.append(bytes(out).decode("cp1252"))
    return " ".join(" ".join(" ".join(drawn).split()).split())


def test_us_bil_022_tc12__the_same_bill_renders_byte_identical_pdfs(brazos, dana):
    """The property a PDF writer breaks by DEFAULT, asserted rather than assumed.

    Almost every PDF writer stamps `/CreationDate`, `/ModDate` and a random
    `/ID` into the file. Two reprints of one bill then differ byte-for-byte
    while looking identical on paper — and nothing catches it, because every
    other test compares what the page SAYS. The person who finds out is
    whoever, years later, diffs an archived bill against a reprint in a dispute
    and cannot tell a rendering artefact from a tampered document.

    So: two renders of the same bill are the same bytes, there is no date
    anywhere in the file, and two DIFFERENT bills are not the same bytes — the
    last one because "always return the same constant" would satisfy the first
    two and be worthless.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        bill = an_issued_bill(brazos, dana, account=an_account(dana, brazos), run=run)
        other = an_issued_bill(
            brazos,
            dana,
            account=an_account(dana, brazos, account_no="A-99"),
            run=run,
            invoice_no="BL-2607-000999",
        )

        first = documents.render_invoice(bill).pdf
        second = documents.render_invoice(models.Invoice.objects.get(pk=bill.pk)).pdf

        assert first == second, (
            "two renders of ONE bill produced different bytes — a reprint is no longer "
            "provably the document that was issued (BR-BIL-026 / BR-CUS-040)"
        )
        assert b"/CreationDate" not in first and b"/ModDate" not in first, (
            "the PDF carries a clock, which is both non-deterministic and a G6/BR-TEN-043 "
            "violation in a money path"
        )
        assert b"/Info" not in first
        assert documents.render_invoice(other).pdf != first, (
            "two DIFFERENT bills rendered the same bytes — determinism was bought by "
            "returning a constant"
        )


def test_us_bil_022_tc13__the_pdf_and_the_html_say_the_same_things(brazos, dana):
    """One structure, two serialisations — asserted field by field.

    Hard-won law 5's reasoning applied to OUTPUT: two renderings of one bill
    that can drift apart WILL, and the drift is invisible because each one
    passes its own tests. So every label and every value on the structured
    document is required to reach BOTH the HTML and the page, and a field added
    to one serialisation and forgotten in the other fails here.

    This is the test that makes "the PDF renders from the same
    `RenderedDocument`" a guarantee rather than a claim about how the code is
    arranged today.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(an_issued_bill(brazos, dana))

        page = pdf_text(document.pdf)
        markup = html.unescape(document.body)
        bands = (
            document.meta
            + document.services
            + document.summary
            + document.footer
            + document.stub
        )
        for field in bands:
            value = " ".join(str(field.value).split())
            assert value in page, f"{field.label!r}'s value never reached the PAGE"
            assert value in markup, f"{field.label!r}'s value never reached the HTML"
            if (
                documents.text_width(
                    field.label, documents.FONT_REGULAR, documents.SIZE_LABEL
                )
                <= documents.COL_LABEL_WIDTH
            ):
                assert (
                    field.label in page
                ), f"{field.label!r} is not printed on the PAGE"
                assert field.label in markup
        # ⚠ **THE MASTHEAD IS ASSERTED THE OTHER WAY ROUND, AND THAT IS
        # STRONGER RATHER THAN WEAKER (`DEF-BIL-4524`, 2026-09-07).** It used to
        # be in the band above, so both serialisations had to print the words
        # *Utility*, *Address* and *Contact* down the left of a bill — the three
        # lines the Product Owner read back off the running screen. Nobody
        # labels their own letterhead. So the VALUES must still reach both, and
        # the LABELS must now reach NEITHER: a layout that put one back on the
        # page, or on the markup, fails here. The HTML check is scoped to the
        # letterhead block because the document's `<title>` legitimately says
        # *Utility bill*, and a substring test over the whole page would be
        # asserting against that instead.
        letterhead = markup.split('<header class="masthead">', 1)[1].split(
            "</header>", 1
        )[0]
        for field in document.masthead:
            value = " ".join(str(field.value).split())
            assert (
                value in page
            ), f"the letterhead's {field.label!r} never reached the PAGE"
            assert (
                value in markup
            ), f"the letterhead's {field.label!r} never reached the HTML"
            assert field.label not in page, (
                f"{field.label!r} is printed on the PAGE — a letterhead names the utility, "
                "not the field it is stored in"
            )
            assert field.label not in letterhead, (
                f"{field.label!r} is in the HTML letterhead — the two serialisations have "
                "drifted on the one thing this case was amended to pin"
            )
        for group in document.groups:
            assert group.heading in page and group.heading in markup
            for line in group.lines:
                for cell in (
                    line.description,
                    line.quantity,
                    line.unit_price,
                    line.amount,
                ):
                    cell = " ".join(str(cell).split())
                    assert cell in page, f"charge cell {cell!r} never reached the PAGE"
                    assert (
                        cell in markup
                    ), f"charge cell {cell!r} never reached the HTML"


def test_us_bil_022_tc14__a_bill_whose_PAGE_cannot_be_made_does_not_issue(
    brazos, dana, monkeypatch
):
    """BR-BIL-033, for the half the customer actually holds.

    *"Render BEFORE issue; a failed render refuses the issue."* The HTML half
    is `tc6`. This is the PDF half, and it is not the same test: print is the
    PRIMARY channel (BR-BIL-036), so a bill that produces markup and no page is
    a bill that cannot be delivered by the one channel every account has.

    The failure is deliberately NOT a `BillingRuleError` — it is the shape a
    real defect takes, an ordinary exception out of a serialiser. Two things
    are asserted about it: the bill does not issue, AND the batch survives with
    ONE named break (BR-BIL-055), because a serialiser that raised through
    `issue_run` would take down a run of five hundred bills over one of them.

    ⚠ **THE SABOTAGE USED TO REACH A DOOR THE RENDER NO LONGER TAKES, SO THIS
    CASE MEASURED NOTHING AND SAID SO IN RED — `DEF-2764` / `DEF-2898`.** It
    patched `documents.LAYOUTS[TEMPLATE_VERSION]`, the pre-library registry
    keyed by template VERSION NUMBER. `documents._layout_for` asks
    `_layout_key_of` FIRST and, since the platform layout library landed on
    2026-08-16, renders `LAYOUTS_BY_KEY[<the pinned row's layout_key>]` whenever
    the pin resolves to a row — and `issue_run` has resolved the pin PER ACCOUNT
    through `templates_service.resolve_for` since CR-052 task 12, so it always
    does. The fake was never consulted, the "unprintable" bill rendered
    perfectly, both bills issued and the case failed with *"Left contains one
    more item"*. Nothing about the product was wrong; the guard was.

    **SO THE FAKE IS INSTALLED ON EVERY DOOR `_layout_for` CAN RETURN**, keyed
    by `layout_key` and by version number alike, each one WRAPPING that door's
    own real layout rather than replacing it. That is deliberately not "patch
    the key the pin happens to carry today": the pin is resolved inside
    `issue_run` from the tenant's own templates, so a test that reproduced that
    resolution would be asserting against a second copy of the code under test —
    and would go quiet again the next time the resolution moved. Wrapping every
    door cannot go quiet: whichever one the render takes is a wrapped one.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        good = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-1"),
            run,
            invoice_no="BL-2607-000401",
        )
        bad = a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no="A-2"),
            run,
            invoice_no="BL-2607-000402",
        )

        def unprintable_through(real):
            """`real`'s own page for every bill but one, and a raise for that one."""

            def pdf(document):
                if document["invoice_no"] == "BL-2607-000402":
                    raise RuntimeError("the page could not be composed")
                return real.pdf(document)

            return documents.Layout(html=real.html, pdf=pdf)

        for key, layout in list(documents.LAYOUTS_BY_KEY.items()):
            monkeypatch.setitem(
                documents.LAYOUTS_BY_KEY, key, unprintable_through(layout)
            )
        for version, layout in list(documents.LAYOUTS.items()):
            monkeypatch.setitem(documents.LAYOUTS, version, unprintable_through(layout))

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )

        assert result.issued == (str(good.pk),)
        assert [(b.reason, b.invoice_no) for b in result.broken] == [
            (issue.ISSUE_RENDER_FAILED, "BL-2607-000402")
        ]
        unprintable_bill = models.Invoice.objects.get(pk=bad.pk)
        assert unprintable_bill.status == models.INVOICE_DRAFT
        assert (unprintable_bill.due_date, unprintable_bill.template_version) == (
            None,
            None,
        )


def test_us_bil_022_tc15__what_this_file_writes_is_a_structurally_valid_pdf(
    brazos, dana
):
    """The guard that asks whether a PDF was actually produced, not merely bytes.

    No PDF library is installed — that is the whole point of `_pdf` — so
    nothing else in this suite would notice if the writer emitted a plausible
    header over a broken cross-reference table. A reader opening it would; this
    test does the same job the reader does.

    Checked: the header, one xref entry per object with every offset landing on
    that object's own `N 0 obj`, `startxref` landing on the table, `/Size`
    agreeing with the object count, the page tree's `/Count` agreeing with the
    page count reported to the caller, and every stream's declared `/Length`
    matching the bytes actually written.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(an_issued_bill(brazos, dana))
        pdf = document.pdf

        assert pdf.startswith(b"%PDF-1.4\n")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert document.pdf_content_type == "application/pdf"
        assert document.pdf_page_count >= 1
        assert b"/Count %d" % document.pdf_page_count in pdf

        table = pdf.split(b"xref\n", 1)[1]
        header, entries = table.split(b"\n", 1)
        first, count = (int(part) for part in header.split())
        assert first == 0
        for number in range(1, count):
            offset = int(entries[number * 20 : number * 20 + 10])
            assert pdf[offset:].startswith(b"%d 0 obj" % number), (
                f"xref says object {number} is at byte {offset} and it is not — every "
                "reader resolves objects through this table"
            )
        assert b"/Size %d" % count in pdf
        start = int(re.search(rb"startxref\n(\d+)\n%%EOF", pdf).group(1))
        assert pdf[start:].startswith(b"xref\n")
        for stream in re.finditer(rb"<< /Length (\d+) >>\nstream\n", pdf):
            declared = int(stream.group(1))
            assert pdf[stream.end() + declared :].startswith(b"\nendstream")


def test_us_bil_022_tc16__a_name_the_page_cannot_spell_is_named_never_silently_mangled(
    brazos, dana
):
    """OQ-150 — the limit of an unembedded Base-14 font, on the document.

    The page encodes WinAnsi and nothing else, so `Núñez` prints correctly and
    `Nowałczyk` cannot: `ł` has no code point in that repertoire and no font is
    embedded to supply one. This build SUBSTITUTES and NAMES the substitution
    rather than refusing the bill — OQ-117's reasoning, applied to a defect in
    the floor document rather than in the stamp. ⚠ This docstring previously
    ended *"and OQ-150 puts the other reading to the PO"*, which was true when
    written: **the PO CLOSED OQ-150 on 2026-08-12 — _"print a substitution"_**,
    so the shipped behaviour is the ruled behaviour. `tc17c` asserts the other
    half the ruling requires: the run NAMES the bill and the character.

    What must never happen is the silent version, which is why this test
    exists: a customer whose name quietly loses a letter is a customer nobody
    knows was mis-addressed. The HTML is asserted UNAFFECTED in the same
    breath, because the value is not missing — the page cannot show it.
    """
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        payload = a_stage6_payload(customer_name="Zofia Nowałczyk")
        bill = an_issued_bill(
            brazos,
            dana,
            account=an_account(dana, brazos),
            run=run,
            bill_payload=payload,
        )

        document = documents.render_invoice(bill)

        assert "Zofia Nowałczyk" in document.body, (
            "the HTML lost a character it can perfectly well encode — the WinAnsi limit "
            "belongs to the PAGE and must not reach the markup"
        )
        assert [a.field for a in document.pdf_unrepresentable] == ["pdf_text"]
        named = document.pdf_unrepresentable[0]
        assert "ł" in named.detail and "OQ-150" in named.br_ref
        assert "Nowa?czyk" in pdf_text(document.pdf)

        # And a name the repertoire DOES cover is untouched and unreported —
        # otherwise this would flag every accented name in Texas.
        plain = documents.render_invoice(
            an_issued_bill(
                brazos,
                dana,
                account=an_account(dana, brazos, account_no="A-2"),
                run=run,
                invoice_no="BL-2607-000501",
                bill_payload=a_stage6_payload(customer_name="María Núñez"),
            )
        )
        assert plain.pdf_unrepresentable == ()
        assert "María Núñez" in pdf_text(plain.pdf)


# ── TC-17 · OQ-117 CLOSED — "issue and report it" ───────────────────────────
def test_us_bil_022_tc17__a_bill_that_cannot_print_its_total_issues_and_is_reported(
    brazos, dana, caplog, monkeypatch
):
    """OQ-117, CLOSED by the PO on 2026-08-12: **_"issue and report it"_**.

    The question was whether a bill that renders its charge lines correctly and
    then cannot fill in TOTAL DUE is a *failed render* that BR-BIL-033 must
    refuse. It is not. The charge lines are correct and the customer needs
    them, so the document goes out — and the missing total is raised as a run
    problem NAMING THE BILL, which is the half this build did not have: the
    absence was recorded on a result that `issue_invoice` discards, so nobody
    was ever told.

    Three things are asserted and each is a separate way to get this wrong:

      1. **The bill ISSUED.** Reading (A) — refuse — would stop every bill this
         system currently produces, which is why the PO was asked.
      2. **The problem NAMES THE BILL and gives a reason a person can act on.**
         A code alone is not a report: a clerk holding `total_due_not_printable`
         with no bill number and no next step has been told nothing.
      3. **Somebody is actually told.** The only caller of `render_invoice`
         throws the document away (`issue.py` renders to prove renderability),
         so a report that lives only on the returned object is hard-won law 2 —
         built, unwired, and indistinguishable from silence.

    ⚠ **AMENDED 2026-08-15 (DEF-116) — THE CASE HAS TO BE ARRANGED NOW, AND
    THAT IS THE FIX WORKING.** Until today EVERY bill this system produced was
    this case, because nothing stamped BR-BIL-035's figures at all;
    `issue._stamp_balance_forward` does, so an ordinary bill now prints its
    total and `tc17b` is the ordinary path. The case is still REACHABLE and
    still has to behave exactly this way: the arrears are payments' figure, read
    through a seam, and a deployment whose payments module publishes nothing
    cannot know them. The seam is made unreachable here — the same shape
    `an_unpublished_ledger` uses for the GL map — so the bill goes out with its
    charge lines right, its total absent, and somebody told.
    """
    monkeypatch.setattr(payments_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert bill.status == models.INVOICE_ISSUED, (
            "OQ-117 was ruled ISSUE AND REPORT — a bill whose total cannot be printed is "
            "not withheld from the customer whose charge lines are correct"
        )

        with caplog.at_level(logging.WARNING, logger=documents.LOGGER_NAME):
            document = documents.render_invoice(bill)

        # The document the customer gets, with the charges on it.
        assert document.body and document.pdf
        assert [line.amount for group in document.groups for line in group.lines] != []

        reported = {problem.code: problem for problem in document.problems}
        assert "total_due_not_printable" in reported, (
            "the missing total is the RUN PROBLEM the PO ruled must be raised; recording "
            "it only as a row in `absent` is what nobody was told"
        )
        problem = reported["total_due_not_printable"]
        assert problem.invoice_no == bill.invoice_no
        assert problem.invoice_id == str(bill.pk)
        assert bill.invoice_no in problem.detail, "a report that does not name the bill"
        assert "OQ-117" in problem.br_ref and "BR-BIL-035" in problem.br_ref
        # A reason a person can act on: what is missing, and where it is stamped.
        assert "balance-forward" in problem.detail
        assert "assemble_document" in problem.detail

        emitted = [record.getMessage() for record in caplog.records]
        assert any(bill.invoice_no in message for message in emitted), (
            "the run problem reached nobody. `issue.py` discards the RenderedDocument, so "
            "a report carried only on the return value is a report that does not exist."
        )

        # Unchanged and still true: the figure itself is NOT invented. The box
        # and the stub both print the dash, and they agree with each other.
        total_due = next(f for f in document.summary if f.label == "Total due")
        assert total_due.value == documents.ABSENT_MARK
        assert (
            next(f for f in document.stub if f.label == "Amount due").value
            == total_due.value
        )


def test_us_bil_022_tc17b__a_bill_that_can_print_its_total_reports_nothing(
    brazos, dana, caplog
):
    """The other half, and the one that stops this becoming noise.

    When the balance-forward section is stamped the absence closes, and the
    report must close with it — a run that warns on every bill forever is a run
    nobody reads, and the warning that mattered is lost among five hundred that
    did not.

    ⚠ **REWRITTEN 2026-08-15 (DEF-116) — THIS CASE NO LONGER HAND-STAMPS THE
    PAYLOAD.** It used to write `total_due = "153.88 USD"` into the fixture and
    assert it back, because nothing in the product wrote that key and the test
    had to stand in for the fix ("written from the payload side because that is
    where the fix lands"). The fix landed: `issue._stamp_balance_forward`
    computes and writes it inside the issue transaction, so a hand-set value is
    now OVERWRITTEN by the real one — which is exactly what it should be, and is
    how this case failed when the stamp arrived (`assert '100.58 USD' ==
    '153.88 USD'`). So the arrears are made REAL instead: one earlier bill of
    **45.00** that nobody has paid, beside **100.58** of current charges, and
    the box reads **145.58**.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        a_priced_draft(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000090",
            status=models.INVOICE_ISSUED,
            issued_at=ISSUED_AT,
            subtotal=Decimal("45.00"),
            tax_total=Decimal("0"),
            total=Decimal("45.00"),
            bill_payload=a_stage6_payload(),
        )
        bill = an_issued_bill(brazos, dana, account=account, run=run)

        with caplog.at_level(logging.WARNING, logger=documents.LOGGER_NAME):
            document = documents.render_invoice(bill)

        assert [p.code for p in document.problems] == []
        printed = {field.label: field.value for field in document.summary}
        assert printed["Previous balance"] == "45.00 USD"
        assert printed["Payments & credits"] == "0.00 USD"
        assert printed["Total due"] == "145.58 USD"
        assert [
            r.getMessage() for r in caplog.records if r.name == documents.LOGGER_NAME
        ] == []


def test_us_bil_022_tc17c__a_substituted_name_is_reported_on_the_same_channel(
    brazos, dana, caplog
):
    """OQ-150, ruled the SAME DAY and the same way: *"print a substitution"*.

    Both rulings say tell somebody rather than withhold the bill, so both
    reports leave by the same door. Asserted here because a substitution named
    only on the return value reaches exactly as few people as the missing total
    did — the ruling says the run *names the bill and the character*, and this
    is the assertion that the run does.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(
            brazos, dana, bill_payload=a_stage6_payload(customer_name="Zofia Nowałczyk")
        )

        with caplog.at_level(logging.WARNING, logger=documents.LOGGER_NAME):
            document = documents.render_invoice(bill)

        reported = {problem.code: problem for problem in document.problems}
        assert "pdf_character_substituted" in reported
        problem = reported["pdf_character_substituted"]
        assert problem.invoice_no == bill.invoice_no
        assert bill.invoice_no in problem.detail and "ł" in problem.detail
        assert any(
            bill.invoice_no in r.getMessage() and "ł" in r.getMessage()
            for r in caplog.records
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-022@5397d5f (sha1[:7] of the four sources, concatenated in
#         order: 04-docs/01-spec/19-document-templates.md ·
#         04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md
#         · 07-billing/02-business-rules.md · 07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-document lane) · AMENDED
#         2026-08-12 by story-coder (OQ-117 + OQ-150 CLOSED — tc17/tc17b/tc17c
#         added, tc8's `unavailable` set gains the run-problem storage gap, and
#         tc16's "OQ-150 puts the other reading to the PO" corrected)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices/{id}/document is not mounted) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · 19 passed · every guard here proved RED by mutation
#         before it was trusted green — the original nine and the PDF lane's
#         further SIX (a random /ID · a creation timestamp · the page rendered
#         on the latest template rather than the pin · BR-BIL-033 unwired for
#         the page · a band dropped from one serialisation only · a silently
#         mangled name · an off-by-one xref table), each quoted verbatim in
#         12-governance/09-human-review-ledger.md
# exceptions: epic TC-5 (a pinned version can never be deleted) and TC-6 (a
#         cross-tenant reprint) are NOT covered: the first needs
#         `bill_template_versions`, which does not exist, and the second belongs
#         to the isolation suite, which drives RLS on a live cluster. Both are
#         named rather than approximated with a test that would pass for the
#         wrong reason · `tc7` asserts a GAP (`bill_payload` has no total) and
#         is designed to go RED when the gap closes · the two-layout world in
#         `two_registered_layouts` is a monkeypatch, because this build ships
#         one layout; without a second one, "renders the pinned version" would
#         be true of any implementation at all · `tc15` validates the PDF's own
#         structure BY HAND (xref offsets, startxref, /Size, /Count, stream
#         /Length) because no PDF library is installed to open the output —
#         which is the point of `_pdf`, and means nothing else in this suite
#         would notice a plausible header over a broken file · `tc16` asserts
#         the WinAnsi substitution this build SHIPS, which the PO RULED on
#         2026-08-12 (*"print a substitution"*); this line previously read
#         "(OQ-150 asks whether it should refuse the issue instead), so it goes
#         RED the day that is ruled" and was true when written · `tc17`–`tc17c`
#         assert the REPORT half of OQ-117/OQ-150 through the LOG, because
#         `issue.py` discards the rendered document and an assertion on the
#         return value alone would pass on a report nobody ever receives
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
