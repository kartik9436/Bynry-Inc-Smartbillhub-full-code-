# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 wave 3 — "I need a copy of something": CPB-14 (a copy of any
#           document, not only a bill), CPB-15 (a year of them at once),
#           CPB-19 (view my bill never errors, and the screen and the file
#           agree), CPB-20 (the receipt, on the row a person is looking at)
# Defects:  DEF-CWP-4658 (the read said `available: true` while the file route
#           answered 409 for the same bill in the same second — filed by the
#           test written for DEF-CWP-4657, and CLOSED by this wave) ·
#           DEF-CWP-4699 (a tampered copy reached the customer as a raw 500)
# Rules:    BR-CWP-045 (documents are SERVED, never re-rendered) · BR-NOT-027
#           (a tampered document refuses and never degrades) · BR-CWP-010 (both
#           halves in the query) · BR-CWP-041 (one answer, so nobody can probe)
#           · US-CWP-034 TC-7 (`download` is its own grant) · B14 rule 31
# Tests:    this file
# Impacts:  apps/portal/seams/notifications_seam.stored_document_service ·
#           apps/portal/seams/billing_seam.printed_bill_service /
#           printed_bill_for · apps/portal/selectors.document_file /
#           documents_bundle · apps/portal/api.py document_file /
#           account_documents_bundle
# ───────────────────────────────────────────────────────
"""Wave 3's cases — every one of them proved RED before it was made green.

⚠ **THE TWO FAULTS THIS FILE EXISTS FOR ARE BOTH ABOUT AGREEMENT, NOT ABOUT
FEATURES.**

  1. `printed_bill_for` answered a question about a ROW (*is there a document
     record*) and `bill_document_pdf` answered a question about BYTES (*can I
     hand this over*). Measured on a live portal session: `available: true` and
     a **409** for the same bill in the same second. The screen believes the
     first, so a customer met a broken frame over a bill we had just told them
     we still had.
  2. `ContentHashMismatch` was left uncaught **on purpose**, to keep
     `BR-NOT-027`'s distinction between *we no longer have it* and *what we
     have is not what you received*. The distinction is right. The Django error
     page it produced in front of a customer pressing *view my bill* was not.

⚠ **AND ONE ABOUT A SENTENCE THAT WAS SIMPLY FALSE.** `CWP-031` refused the row
control on every receipt and every letter with the words *"We kept no copy of
this."* — over documents `notifications` freezes at dispatch and the store has
been keeping all along.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.test import Client

from apps.billing import frozen_bill, models as billing_models
from apps.portal import selectors
from apps.portal.seams import billing_seam, notifications_seam
from apps.tenancy import document_store
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)

NUMBER = "BL-2608-0141"
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
ISSUED_AT = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
POSTED_HTML = "<html><body>Pine Hill · BL-2608-0141 · $142.18</body></html>"
POSTED_PDF = b"%PDF-1.4 the page that went in the envelope on 30 August\n%%EOF\n"

#: A receipt, as `notifications` freezes one: against the OUTBOUND MESSAGE that
#: carried it rather than against the payment. That is `_stored`'s SECOND
#: lookup and it is the half `CWP-031` could never reach.
RECEIPT_PDF = b"%PDF-1.4 receipt for $38.44\n%%EOF\n"


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def a_posted_bill(tenant, account, *, number=NUMBER, keep=True):
    invoice = an_issued_bill(
        tenant, account, number=number, total="142.1800", issued_on=AUGUST, due_on=DUE
    )
    billing_models.Invoice.objects.filter(pk=invoice.pk).update(template_version=3)
    invoice.refresh_from_db()
    if keep:
        outcome = frozen_bill.freeze_at_issue(
            invoice,
            SimpleNamespace(body=POSTED_HTML, pdf=POSTED_PDF),
            moment=ISSUED_AT,
        )
        assert outcome.may_issue, outcome.problem
    return invoice


def a_receipt_that_was_sent(tenant, account, *, number="PMT-2608-0042", keep=True):
    """A payment, the queue row that carried its receipt, and the frozen copy.

    ⚠ **THE COPY IS FILED AGAINST THE OUTBOUND MESSAGE, NOT AGAINST THE
    PAYMENT** — `frozen_documents.freeze_for_dispatch`'s own shape, and the
    reason `_stored` asks two places. A fixture that stored it against the
    payment would prove the easy half and skip the one that was broken.

    ⚠ **THE ARTEFACT IS STORED DIRECTLY RATHER THAN RENDERED.**
    `freeze_for_dispatch` needs a published template version, which the demo
    estate does not carry for a receipt (its own dispatch cycle reports
    `render_held_missing_template` on all 68 of them). What is under test here
    is the SERVING path, so the fixture plants exactly what a successful freeze
    plants and says so out loud rather than pretending to exercise the render.
    """
    from apps.notifications import models as notifications_models
    from apps.payments import models as payments_models

    payment = payments_models.Payment.objects.create(
        tenant_id=tenant.id,
        account=account,
        amount=Decimal("38.4400"),
        currency="USD",
        payment_no=number,
        posted_at=datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
    )
    message = notifications_models.OutboundMessage.objects.create(
        tenant_id=tenant.id,
        account=account,
        source_type="payment",
        source_id=payment.pk,
        channel="pdf_print",
        status="queued",
        template_code="receipt",
        # `ck_outbound_msgs_address_or_reason` — a queue row carries the address
        # it will be delivered to, or states why it has none (`BR-BIL-036`).
        recipient_address="1408 Elm St, Pine Hill",
    )
    if keep:
        document_store.store(
            kind="payment_receipt",
            source_type="outbound_message",
            source_id=message.pk,
            channel="pdf_print",
            display_name=f"receipt/2026/08/{number}.pdf",
            content_type="application/pdf",
            payload=RECEIPT_PDF,
            # `store` takes an actor OR a process, and *nobody knows* is not one of
            # the answers a legal document may give.
            process="cr085-w3",
        )
    return payment, message


def signed_in(tenant):
    client = Client()
    answer = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


# ═══════════════════════════════════════════════════════════════════════════
# `CPB-19` — VIEW MY BILL NEVER ERRORS, AND THE TWO READS AGREE
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_cpb19_a_tampered_copy_refuses_BY_NAME_and_is_not_a_500(pine_hill, sarah, docs_dir):
    """`DEF-CWP-4699` — the one input that made this route answer 500.

    RED first, verbatim, at the tip:
        `apps.tenancy.document_storage.ContentHashMismatch: document … hashed to
         53c7bd… and the record says 2d7089… . The bytes in the store are NOT
         the bytes that were frozen.`
        `django.server "GET …/document.pdf?view=1 HTTP/1.1" 500 149`
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        kept = frozen_bill.reproduce(invoice).pdf
        # Somebody has been in the bucket. This is the whole hazard
        # `document_store.fetch`'s hash check exists for.
        path = docs_dir / "/".join(
            document_store._resolve(kept.id).storage_key.split("/")
        )
        path.write_bytes(POSTED_PDF + b"tampered")

        verdict, payload, _ctype, _name = billing_seam.printed_bill_service(
            [account.pk], number=NUMBER
        )
    assert verdict == notifications_seam.DOCUMENT_NOT_TRUSTED
    assert payload is None

    enrol_maria(pine_hill, sarah)
    answer = signed_in(pine_hill).get(
        f"/api/{pine_hill.subdomain}/portal/bills/{NUMBER}/document.pdf?view=1"
    )
    assert answer.status_code != 500, "a customer pressing *view my bill* met a stack trace"
    assert answer.status_code == 409, answer.content
    body = answer.json()
    # ⚠ **`BR-NOT-027` IS KEPT BY THE KEY BEING DIFFERENT.** *Missing* and
    # *tampered* want different things from us, and one shared sentence would
    # have been the softening the rule forbids.
    assert body["message_key"] == "portal.document.notTrusted"
    assert body["message_key"] != "portal.billDocument.notKept"
    assert body["br_ref"] == "BR-NOT-027"


@pytest.mark.django_db
def test_cpb19_the_screens_available_FLAG_agrees_with_what_the_file_route_can_do(
    pine_hill, sarah, docs_dir
):
    """`DEF-CWP-4658` — the promise and the refusal, measured together.

    RED first, verbatim, on the live demo before the fix:
        `GET …/bills/BL-2607-000003/document      → {"available": true}  200`
        `GET …/bills/BL-2607-000003/document.pdf  → 409 portal.billDocument.notKept`
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        kept = frozen_bill.reproduce(invoice).pdf
        # The row stays; the object goes. A redeploy onto a different volume, a
        # restored database, a retention sweep — `printed_bill_bytes`' own list.
        (docs_dir / document_store._resolve(kept.id).storage_key).unlink()

        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)
        verdict, _payload, _ctype, _name = billing_seam.printed_bill_service(
            [account.pk], number=NUMBER
        )

    assert verdict == notifications_seam.DOCUMENT_NOT_KEPT
    assert answer["available"] is False, (
        "the screen would have drawn the frame, the sentence *exactly as it was "
        "printed* and a download link, over a file the server cannot hand over"
    )
    assert answer["unavailable_reason"] == "document_not_stored"


@pytest.mark.django_db
def test_cpb19_a_tampered_copy_gets_its_OWN_reason_on_the_screens_read(
    pine_hill, sarah, docs_dir
):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        kept = frozen_bill.reproduce(invoice).pdf
        (docs_dir / document_store._resolve(kept.id).storage_key).write_bytes(b"not the page")
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)

    assert answer["available"] is False
    assert answer["unavailable_reason"] == "document_bytes_do_not_match"
    # B14 rule 31/32 — a reason CODE for the screen to branch on, and no id.
    assert not {"id", "document_id", "storage_key"} & set(answer)


@pytest.mark.django_db
def test_cpb19_a_kept_bill_is_still_served_byte_for_byte(pine_hill, sarah, docs_dir):
    """The regression guard on the whole of `CPB-19`: nothing above changed the
    ordinary case, which is the one every customer meets."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)
        served = billing_seam.printed_bill_bytes([account.pk], number=NUMBER)

    assert answer["available"] is True
    assert answer["unavailable_reason"] is None
    assert served is not None
    assert served[0] == POSTED_PDF
    assert served[2] == "BL-2608-0141.pdf"


# ═══════════════════════════════════════════════════════════════════════════
# `CPB-14` — A COPY OF ANY DOCUMENT, NOT ONLY A BILL
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_cpb14_a_RECEIPT_can_be_taken_away_by_the_number_on_it(pine_hill, sarah, docs_dir):
    """The wave in one case. RED first:
    `KeyError`/`AttributeError: module 'apps.portal.selectors' has no attribute
     'document_file'` — there was no serving path for anything but a bill."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
        served = selectors.document_file([account.pk], reference="PMT-2608-0042")

    assert served["verdict"] == notifications_seam.DOCUMENT_OK
    assert served["payload"] == RECEIPT_PDF
    # ⚠ THE NUMBER, AND NOT THE STORE'S `display_name` — that name carries
    # somebody's account number and a directory path.
    assert served["filename"] == "PMT-2608-0042.pdf"


@pytest.mark.django_db
def test_cpb14_a_number_that_is_not_this_logins_answers_the_SAME_404_as_one_that_never_existed(
    pine_hill, sarah, docs_dir
):
    """`BR-CWP-041` — one answer, so a customer cannot probe what exists."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
        # An empty account set is *somebody else's login*, expressed in the one
        # place `BR-CWP-010` lives.
        not_mine = selectors.document_file([], reference="PMT-2608-0042")
        never_was = selectors.document_file([account.pk], reference="PMT-9999-9999")

    assert not_mine["verdict"] == "not_found"
    assert never_was["verdict"] == "not_found"
    assert not_mine == never_was, "two different refusals is a way to enumerate documents"


@pytest.mark.django_db
def test_cpb14_a_document_we_kept_no_copy_of_says_exactly_that_and_serves_nothing(
    pine_hill, sarah, docs_dir
):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account, keep=False)
        served = selectors.document_file([account.pk], reference="PMT-2608-0042")

    assert served["verdict"] == notifications_seam.DOCUMENT_NOT_KEPT
    assert served["payload"] is None


@pytest.mark.django_db
def test_cpb14_the_edge_serves_it_as_an_attachment_and_inline_on_view_1(
    pine_hill, sarah, docs_dir
):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
    enrol_maria(pine_hill, sarah)
    client = signed_in(pine_hill)
    base = f"/api/{pine_hill.subdomain}/portal/documents/PMT-2608-0042/file"

    downloaded = client.get(base)
    assert downloaded.status_code == 200, downloaded.content
    assert downloaded["Content-Disposition"] == 'attachment; filename="PMT-2608-0042.pdf"'
    assert bytes(downloaded.content) == RECEIPT_PDF

    viewed = client.get(base + "?view=1")
    assert viewed.status_code == 200
    assert viewed["Content-Disposition"] == 'inline; filename="PMT-2608-0042.pdf"'
    # ⚠ SAME BYTES — the same assertion `DEF-CWP-3983` stands on for the bill.
    assert bytes(viewed.content) == bytes(downloaded.content)


@pytest.mark.django_db
def test_cpb14_an_unauthenticated_caller_gets_nothing(pine_hill, sarah, docs_dir):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
    answer = Client().get(f"/api/{pine_hill.subdomain}/portal/documents/PMT-2608-0042/file")
    assert answer.status_code in {401, 403}, answer.content


@pytest.mark.django_db
def test_cpb14_the_two_places_a_document_can_be_frozen_are_BOTH_asked(
    pine_hill, sarah, docs_dir
):
    """`stored_document_service` is the ONE place that question is written now.

    ⚠ **THE SECOND LOOKUP IS THE ONE THAT MATTERS HERE.** A bill freezes
    against its own source at ISSUE; everything else freezes against the
    OUTBOUND MESSAGE at DISPATCH. Asking only the first would report *no file
    was kept* over half the documents in the list — which is what the screen
    was doing in words.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        _payment, message = a_receipt_that_was_sent(pine_hill, account)

        by_source = notifications_seam.stored_document_service(
            source_type="invoice", source_id=invoice.pk
        )
        by_message = notifications_seam.stored_document_service(
            source_type="payment", source_id=message.source_id
        )

    assert by_source[0] == notifications_seam.DOCUMENT_OK
    assert by_source[1] == POSTED_PDF
    assert by_message[0] == notifications_seam.DOCUMENT_OK
    assert by_message[1] == RECEIPT_PDF


# ═══════════════════════════════════════════════════════════════════════════
# `CPB-15` — A YEAR OF DOCUMENTS AT ONCE
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_cpb15_a_year_of_documents_arrives_as_one_zip_of_the_frozen_files(
    pine_hill, sarah, docs_dir
):
    """RED first: `AttributeError: module 'apps.portal.selectors' has no
    attribute 'documents_bundle'`, and on the screen the control read
    *Downloads are not ready yet*."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        from apps.notifications import models as notifications_models

        notifications_models.OutboundMessage.objects.create(
            tenant_id=pine_hill.id,
            account=account,
            source_type="invoice",
            source_id=invoice.pk,
            channel="pdf_print",
            status="queued",
            template_code="bill_ready_notice",
            recipient_address="1408 Elm St, Pine Hill",
        )
        a_receipt_that_was_sent(pine_hill, account)
        bundle = selectors.documents_bundle(account, today=date(2026, 9, 8))

    assert bundle["verdict"] == "ok"
    assert bundle["kept"] == 2
    assert bundle["listed"] == 2
    with zipfile.ZipFile(io.BytesIO(bundle["payload"])) as archive:
        names = sorted(archive.namelist())
        assert names == ["BL-2608-0141.pdf", "PMT-2608-0042.pdf"]
        # ⚠ **BYTE FOR BYTE.** Nothing is merged, nothing is re-rendered, and
        # no cover page is composed — all three would be a document the
        # customer was never sent (`BR-CWP-045`).
        assert archive.read("BL-2608-0141.pdf") == POSTED_PDF
        assert archive.read("PMT-2608-0042.pdf") == RECEIPT_PDF


@pytest.mark.django_db
def test_cpb15_a_document_with_no_kept_copy_is_ABSENT_and_the_count_says_so(
    pine_hill, sarah, docs_dir
):
    """A short archive that looked complete would be a check that cannot fail."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
        a_receipt_that_was_sent(pine_hill, account, number="PMT-2608-0043", keep=False)
        bundle = selectors.documents_bundle(account, today=date(2026, 9, 8))

    assert bundle["kept"] == 1
    assert bundle["listed"] == 2, "the shortfall is REPORTED, not hidden"


@pytest.mark.django_db
def test_cpb15_an_account_with_nothing_kept_is_refused_rather_than_sent_an_empty_zip(
    pine_hill, sarah, docs_dir
):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account, keep=False)
        bundle = selectors.documents_bundle(account, today=date(2026, 9, 8))
    assert bundle["verdict"] == "empty"
    assert bundle["payload"] is None

    enrol_maria(pine_hill, sarah)
    answer = signed_in(pine_hill).get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/documents/year.zip"
    )
    assert answer.status_code == 409, answer.content
    assert answer.json()["message_key"] == "portal.documents.yearEmpty"


@pytest.mark.django_db
def test_cpb15_the_window_is_TWELVE_CALENDAR_MONTHS_including_this_one(
    pine_hill, sarah, docs_dir
):
    """October of last year through September of this one, for somebody
    pressing *Download a year* in September — and nothing older."""
    assert selectors._months_back(date(2026, 9, 8), 12) == date(2025, 10, 1)
    assert selectors._months_back(date(2026, 1, 3), 12) == date(2025, 2, 1)

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _payment, message = a_receipt_that_was_sent(pine_hill, account)
        from apps.notifications import models as notifications_models

        # Older than the window by one day.
        notifications_models.OutboundMessage.objects.filter(pk=message.pk).update(
            created_at=datetime(2025, 9, 30, 9, 0, tzinfo=UTC)
        )
        bundle = selectors.documents_bundle(account, today=date(2026, 9, 8))
    assert bundle["verdict"] == "empty"
    assert bundle["listed"] == 0


@pytest.mark.django_db
def test_cpb15_the_edge_serves_the_zip_with_the_counts_on_it(pine_hill, sarah, docs_dir):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        from apps.notifications import models as notifications_models

        notifications_models.OutboundMessage.objects.create(
            tenant_id=pine_hill.id,
            account=account,
            source_type="invoice",
            source_id=billing_models.Invoice.objects.get(invoice_no=NUMBER).pk,
            channel="pdf_print",
            status="queued",
            template_code="bill_ready_notice",
            recipient_address="1408 Elm St, Pine Hill",
        )
    enrol_maria(pine_hill, sarah)
    answer = signed_in(pine_hill).get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/documents/year.zip"
    )
    assert answer.status_code == 200, answer.content
    assert answer["Content-Type"] == "application/zip"
    assert answer["X-Documents-Kept"] == "1"
    assert answer["X-Documents-Listed"] == "1"
    assert answer["Content-Disposition"].startswith('attachment; filename="')
    with zipfile.ZipFile(io.BytesIO(answer.getvalue())) as archive:
        assert archive.read("BL-2608-0141.pdf") == POSTED_PDF


# ═══════════════════════════════════════════════════════════════════════════
# `CPB-20` — THE RECEIPT IS ADDRESSED BY THE PAYMENT NUMBER, NOT BY `reference`
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_cpb20_the_money_row_carries_the_PMT_number_beside_the_cheque_number(
    pine_hill, sarah, docs_dir
):
    """⚠ **TWO FACTS, TWO FIELDS.** `reference` prefers the CHEQUE number the
    customer wrote, because that is what they can find in their own bank
    statement. The receipt is filed under the payment's own number. Serving it
    off `reference` would answer *not found* on every cheque — the row a person
    most often wants a receipt for."""
    from apps.portal.seams import payments_seam

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_receipt_that_was_sent(pine_hill, account)
        rows = payments_seam.money_list([account.pk])

    payments = [row for row in rows if row["kind"] == "payment"]
    assert payments, "the fixture wrote no payment the money list can see"
    assert payments[0]["receipt_reference"] == "PMT-2608-0042"
    # B14 rule 31 — a number printed on paper, never a row id.
    assert "-" in payments[0]["receipt_reference"]
    assert len(payments[0]["receipt_reference"]) < 36
