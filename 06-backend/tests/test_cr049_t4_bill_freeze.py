# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 4 — "The bill: store the PDF and HTML at issue", and
#           DEF-2553, the page titled *view the bill as sent* that rebuilt the
#           bill on every open.
# Rules:    BR-NOT-027 (a legal document is FROZEN AS THE DOCUMENT when it is
#           sent, and a reproduction serves THAT — never a fresh render; PO
#           2026-08-30, and the rule reaches the bill) · BR-BIL-030 (the bill's
#           INPUTS are frozen — which is NOT the same rule, and is why a
#           re-render looks right and can still differ) · BR-BIL-026 (the pin is
#           PROVENANCE) · BR-BIL-033 (a bill that cannot become a document does
#           not issue — extended here to one that cannot be KEPT) · NFR-33 /
#           NFR-35 (write-once, seven years) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 4 (financial immutability) · rule 7 (audit) ·
#           hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee) · law 2 (built is not wired) · law 7 (prove a guard RED
#           first)
# ───────────────────────────────────────────────────────
"""The bill, kept as the bill — proved through the screen's own route.

**THE ONE CASE THIS FILE EXISTS FOR** is `tc2`: issue a bill, change something
that would alter a re-render, then ask the route the S30 page asks — and read
the ORIGINAL back. That is the PO's sentence turned into a test:

    *"any legal document when send - it is freezed … otherwie everytime we
    reproduce it using data in table, we might change something about it and
    that is not correct"*

⚠ **WHY A RE-RENDER LOOKS RIGHT AND IS STILL WRONG.** `BR-BIL-030` freezes the
bill's INPUTS — `bill_payload` and `custom_snapshot`, held by a database trigger
— so every figure, name and date on a re-rendered bill is correct. **What is NOT
frozen is the PRESENTATION, and exactly half of it turned out to be protected
already:** the tenant's chosen template ROW cannot be edited once published
(`billing_template_version_frozen`, billing migration 0019), but **the CODE that
draws the page and the platform's LIBRARY of layouts are guarded by nothing at
all.** A deploy moves the first; a rollback moves the second, and an
already-pinned bill then prints on `_layout_for`'s named stand-in. `tc2` is the
rollback, `tc3` is the deploy, and `tc2b` asserts the protection that does exist
so it is not mistaken for a gap.

⚠ **PROVED RED FIRST (hard-won law 7).** Every case here was run before
`apps/billing/frozen_bill.py` existed. The verbatim failures are quoted in the
case that owns them.

WHAT IS ACTUALLY FROZEN, SAID PLAINLY
--------------------------------------
`documents.render_invoice` produces TWO serialisations of one structure and has
since 2026-08-11: `.body` (HTML) and `.pdf` (a printable US Letter page written
byte by byte with the standard library — no page-render library, which is
`OQ-149` and still open). **Both are real artefacts of the shipped path**, and
both are frozen here. Nothing is rendered at freeze time that the product does
not otherwise produce: this is the same call `issue.py` has always made to
satisfy `BR-BIL-033`, and the result it used to throw away.
"""

from __future__ import annotations

import uuid

import pytest

from apps.billing import documents, documents_api, frozen_bill, issue, models
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import BillTemplate, BillTemplateVersion
from apps.tenancy import document_storage, document_store

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_us_bil_022_documents import a_stage6_payload
from tests.test_w3_billing_models import an_account
from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: The two media types one bill freezes. Spelled here rather than imported, so a
#: change to either is a visible edit to a test as well as to the module.
HTML_TYPE = "text/html; charset=utf-8"
PDF_TYPE = "application/pdf"


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def a_pinned_layout(tenant, dana, *, layout_key=documents.DEFAULT_LAYOUT_KEY):
    """A REAL template version row, so a test can change what a bill pins to.

    The fixtures in `test_us_bil_005_issue` pin a fabricated `TEMPLATE_ID` that
    names no row, which resolves through `_layout_key_of`'s None door to the
    version-number registry. That is the pre-library bill and it is a legitimate
    state — but it has nothing a System Admin could edit, so it cannot express
    the case this file is about.
    """
    template = BillTemplate.objects.create(
        tenant=tenant, name="Residential bill", template_type="bill"
    )
    version = BillTemplateVersion.objects.create(
        tenant=tenant,
        template=template,
        version_no=1,
        status="published",
        layout_key=layout_key,
        created_by=dana.user,
    )
    return template, version


def an_issued_bill(
    tenant,
    dana,
    *,
    template_id=TEMPLATE_ID,
    template_version=TEMPLATE_VERSION,
    invoice_no="BL-2607-000101",
    account=None,
    run=None,
):
    """One bill, issued through the real path — pin, freeze and all."""
    account = account or an_account(dana, tenant)
    run = run or an_authorised_run(tenant, dana)
    draft = a_priced_draft(
        tenant, account, run, invoice_no=invoice_no, bill_payload=a_stage6_payload()
    )
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=template_id,
        template_version=template_version,
    )


def frozen(bill, content_type):
    """The stored artefact for one bill, or None — through the published door."""
    lookup = document_store.for_source(
        source_type="invoice", source_id=bill.pk, content_type=content_type
    )
    return lookup.document


def a_bill_issued_before_the_freeze_existed(monkeypatch):
    """The world as it was before `v2.88.0` — nothing kept, and nothing checking.

    BOTH halves are bypassed, because both are what this task built: the freeze
    itself, and `require_frozen`, which refuses an outcome that kept nothing. A
    bill issued through this is exactly a bill this product issued yesterday, and
    it is the only way to produce one now that the store cannot delete a row.
    """
    monkeypatch.setattr(
        frozen_bill, "freeze_at_issue", lambda *a, **k: frozen_bill.FreezeOutcome(may_issue=True)
    )
    monkeypatch.setattr(frozen_bill, "require_frozen", lambda *a, **k: None)


def open_the_page(bill, user, tenant):
    """Exactly what `BillDocumentPage` asks for: `GET /invoices/{id}/document`."""
    return api_call(
        documents_api.invoice_document,
        "get",
        f"/api/invoices/{bill.pk}/document",
        user=user.user,
        role="system_admin",
        tenant=tenant,
        invoice_id=str(bill.pk),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE WRITE — issuing a bill keeps the bill
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t4_tc1__issuing_a_bill_freezes_its_html_and_its_page(brazos, dana, docs_dir):
    """Both artefacts the product actually produces are kept, byte for byte.

    ⚠ RED FIRST, before `frozen_bill.py` and before `issue.py` called it:

        E   ImportError: cannot import name 'frozen_bill' from 'apps.billing'

    and, with that import removed, the store answered `document_not_stored` for
    every bill in the product — which is the sentence `DEF-2553` was filed on
    and the reason the S30 page could not be wired.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

        html = frozen(bill, HTML_TYPE)
        pdf = frozen(bill, PDF_TYPE)
        assert html is not None, "the bill's HTML was not kept at issue (BR-NOT-027)"
        assert pdf is not None, "the bill's printable page was not kept at issue"

        # The bytes are the render's own, not a fresh one made for the store.
        rendered = documents.render_invoice(bill)
        assert document_store.fetch(html.id) == rendered.body.encode("utf-8")
        # DEF-BIL-10546 — the kept page is the TAGGED page made at issue. A
        # re-render of an ISSUED bill stays on the old writer (ruled: no
        # accessible copy of an old bill), so the comparison re-serialises the
        # same mapping through the tagged writer, which is deterministic.
        assert rendered.pdf_tagged is False
        tagged = documents.LAYOUTS[documents.BUILT_IN_LAYOUT_VERSION].tagged_pdf(
            documents.document_mapping(rendered)
        )
        assert document_store.fetch(pdf.id) == tagged.data

        assert html.kind == "bill" and pdf.kind == "bill"
        # `channel` is None: a bill is frozen at CREATION, not at SEND. The
        # letter that ANNOUNCES it is a different document on a channel, frozen
        # by `notifications/frozen_documents.py`.
        assert html.channel is None and pdf.channel is None


def test_cr049_t4_tc2__THE_PAGE_MOVES_UNDER_A_SENT_BILL_AND_THE_ORIGINAL_STILL_APPEARS(
    brazos, dana, docs_dir, monkeypatch
):
    """THE CASE THAT DECIDES THIS TASK — end to end, through the screen's route.

    Issue a bill on the layout a utility had chosen. Then take that layout out of
    the platform's published set — **a rollback to a build that publishes a
    different library, which `documents._layout_for` names by name** — and open
    *"view the bill as sent"*. Nothing about the bill was touched: not its data,
    not its pin, not one invoice row.

    ⚠ **THE FIRST DRAFT OF THIS CASE USED A DIFFERENT LEVER AND POSTGRESQL
    DISPROVED IT — the finding is worth more than the case.** It edited the
    PINNED VERSION ROW's `layout_key`, which passes on SQLite (the suite's
    default, `config/settings/test.py`) and is REFUSED on a real cluster by
    `billing_template_version_frozen`, a trigger whose own message says: *"only
    status may change once a version leaves draft … changing it here would
    rewrite what those customers were sent without touching a single invoice
    row."* `tc2b` below asserts that protection rather than leaving it to be
    rediscovered. **So the tenant's template ROW is already safe, and what is
    NOT safe is the rendering CODE and the platform's layout REGISTRY** — which
    no trigger can reach and which a deploy moves. That is the gap the freeze
    closes, and it is CLAUDE.md hard-won law 14's shape in a second costume: the
    case was green on the suite's database and wrong about production.

    ⚠ RED FIRST. Before this task the same steps produced:

        AssertionError: the page titled 'view the bill as sent' served a
        DIFFERENT document after somebody edited the template:
        platform-layout-standard-letter-v1 at issue,
        platform-layout-compact-letter-v1 today

    because `GET /invoices/{id}/document` called `render_invoice` on every open.
    """
    with tenant_ctx(brazos):
        _template, version = a_pinned_layout(brazos, dana)
        bill = an_issued_bill(
            brazos, dana, template_id=version.template_id, template_version=version.version_no
        )
        sealed = frozen(bill, HTML_TYPE)
        original_html = document_store.fetch(sealed.id).decode("utf-8")
        assert "Services this period" in original_html

        # THE ROLLBACK. This build no longer publishes the key the bill is
        # pinned to, so `_layout_for` falls through to its NAMED stand-in and
        # renders a different page — the door its own docstring describes as
        # *"a row written by a build that published a layout this one does not"*.
        published = dict(documents.LAYOUTS_BY_KEY)
        published.pop(documents.DEFAULT_LAYOUT_KEY)
        published["compact-letter-v1"] = documents.LAYOUTS_BY_KEY["compact-letter-v1"]
        monkeypatch.setattr(documents, "LAYOUTS_BY_KEY", published)
        monkeypatch.setattr(documents, "DEFAULT_LAYOUT_KEY", "compact-letter-v1")

        # The lever works: a re-render TODAY is a different document, and the
        # difference is a whole band gone from a bill a customer is holding.
        today = documents.render_invoice(bill)
        assert today.body != original_html, (
            "this test cannot prove anything if the platform dropping a layout does not "
            "change a re-render — check `documents._layout_for` before reading on"
        )
        assert "Services this period" not in today.body

        response = open_the_page(bill, dana, brazos)
        assert response.status_code == 200, response.data
        assert response.data["provenance"] == "original"
        assert response.data["original_html"] == original_html, (
            "the S30 page served a fresh render of an issued bill (BR-NOT-027)"
        )
        assert response.data["frozen_document"]["content_hash"] == sealed.content_hash
        # And the served original is NOT what the product would render today.
        assert response.data["original_html"] != today.body
        assert "Services this period" in response.data["original_html"]


@requires_postgres
def test_cr049_t4_tc2b__the_database_already_refuses_an_edit_to_a_pinned_template(
    brazos, dana, docs_dir
):
    """The protection this lane found by being wrong, asserted so it is not lost.

    `billing_template_version_frozen` (billing migration 0019) refuses every
    UPDATE to a published version except its status. **It exists on PostgreSQL
    and not on the SQLite the suite runs on**, which is why a case that edited a
    pinned layout passed for an hour and described a production that cannot
    happen.

    It does NOT make the freeze unnecessary and the boundary is the point: the
    trigger protects the ROW a tenant chose. It cannot protect the CODE that row
    names — `tc2` and `tc3` are both about that — and it cannot protect a build
    that publishes a different library.
    """
    from django.db.utils import ProgrammingError

    with tenant_ctx(brazos):
        _template, version = a_pinned_layout(brazos, dana)
        version.layout_key = "compact-letter-v1"
        with pytest.raises(ProgrammingError, match="only status may change"):
            version.save(update_fields=["layout_key", "updated_at"])


def test_cr049_t4_tc3__a_deploy_that_changes_the_layout_cannot_change_a_sent_bill(
    brazos, dana, docs_dir, monkeypatch
):
    """The other lever, and the one no database row records: the CODE moved.

    A layout is Python. The day somebody improves `_html_for` — a heading, a
    column, an escape — every historical bill re-renders differently and no
    audit row anywhere says so. This is the case a stored artefact exists for.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        sealed = frozen(bill, HTML_TYPE)
        original_html = document_store.fetch(sealed.id).decode("utf-8")

        monkeypatch.setitem(
            documents.LAYOUTS,
            TEMPLATE_VERSION,
            documents.Layout(
                html=lambda doc: "<article>A LATER BUILD OF THIS PAGE</article>",
                pdf=lambda doc: documents.PdfSerialisation(data=b"%PDF-LATER", page_count=1),
            ),
        )
        assert documents.render_invoice(bill).body != original_html

        response = open_the_page(bill, dana, brazos)
        assert response.data["provenance"] == "original"
        assert response.data["original_html"] == original_html
        assert "A LATER BUILD OF THIS PAGE" not in response.data["original_html"]


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE PRECONDITION — a bill that cannot be kept does not issue
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t4_tc4__a_bill_that_cannot_be_frozen_stays_a_draft(
    brazos, dana, docs_dir, monkeypatch
):
    """`BR-BIL-033` extended: rendering it is not enough, we must be able to KEEP it.

    The window for this is open only because nothing has been sent yet
    (`CR-049` step 4). It closes at go-live, and after that a refusal like this
    would leave a customer holding a bill the product will not admit to.

    ⚠ RED FIRST: before `require_frozen` the same sabotage issued the bill —

        AssertionError: the bill issued with nothing kept
        assert 'issued' == 'draft'
    """

    def refuse(**kwargs):
        raise document_store.DocumentStoreError("the bucket is not reachable")

    monkeypatch.setattr(document_store, "store", refuse)

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(
            brazos, account, run, invoice_no="BL-2607-000109", bill_payload=a_stage6_payload()
        )
        with pytest.raises(BillingRuleError) as refused:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        assert "kept" in str(refused.value).lower() or "frozen" in str(refused.value).lower()

        again = models.Invoice.objects.get(pk=draft.pk)
        assert again.status == "draft", "the bill issued with nothing kept"
        assert again.issued_at is None


def test_cr049_t4_tc5__the_status_cannot_move_without_the_freeze_answer(brazos, dana, docs_dir):
    """The SECOND guarantee, which is not the order of two statements.

    `_mark_issued` takes the freeze outcome as a REQUIRED argument, so a future
    call site cannot omit it and a refactor that moves the freeze after the
    status move goes RED here rather than shipping an unkept bill.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        with pytest.raises(frozen_bill.NotFrozen):
            frozen_bill.require_frozen(bill, None)
        with pytest.raises(frozen_bill.NotFrozen):
            frozen_bill.require_frozen(bill, frozen_bill.FreezeOutcome(may_issue=False))


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE HONEST HALF — a bill with no original SAYS SO
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t4_tc6__a_bill_issued_before_this_shipped_is_a_reconstruction(
    brazos, dana, docs_dir, monkeypatch
):
    """`CR-049` task 7's sentence, for the bill. The two states are DIFFERENT.

    The freeze is bypassed exactly as the world was before it existed, and the
    route must then answer *re-rendered from data, not the original* — with NO
    document attached, so a screen cannot draw a fresh render under a caption
    that says it is the bill.
    """
    a_bill_issued_before_the_freeze_existed(monkeypatch)
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert frozen(bill, HTML_TYPE) is None

        response = open_the_page(bill, dana, brazos)
        assert response.status_code == 200
        assert response.data["provenance"] == "re_rendered_from_data_not_the_original"
        assert response.data["frozen_document"] is None
        assert response.data["original_html"] is None
        assert response.data["unavailable_reason"] == "document_not_stored"
        assert response.data["message_key"] == "billing.document.reRendered"


def test_cr049_t4_tc7__the_two_states_are_visibly_different_on_one_response(
    brazos, dana, docs_dir, monkeypatch
):
    """A reproduction is the original or it says it is not. There is no third state."""
    with tenant_ctx(brazos):
        kept = an_issued_bill(
            brazos,
            dana,
            invoice_no="BL-2607-000111",
            account=an_account(dana, brazos, account_no="A-10111"),
        )
        first = open_the_page(kept, dana, brazos).data

    a_bill_issued_before_the_freeze_existed(monkeypatch)
    with tenant_ctx(brazos):
        unkept = an_issued_bill(
            brazos,
            dana,
            invoice_no="BL-2607-000112",
            account=an_account(dana, brazos, account_no="A-10112"),
            run=an_authorised_run(brazos, dana, key="2026-06|cycle-2"),
        )
        second = open_the_page(unkept, dana, brazos).data

    assert first["provenance"] != second["provenance"]
    assert first["message_key"] != second["message_key"]
    assert (first["original_html"] is None) != (second["original_html"] is None)


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE PRINTABLE PAGE, THE HASH, THE NAME, THE TRAIL
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t4_tc8__the_pdf_route_serves_the_frozen_page(brazos, dana, docs_dir, monkeypatch):
    """`/document.pdf` is the copy that was kept, not one made on the way out."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        sealed_pdf = document_store.fetch(frozen(bill, PDF_TYPE).id)

        monkeypatch.setitem(
            documents.LAYOUTS,
            TEMPLATE_VERSION,
            documents.Layout(
                html=lambda doc: "<article>LATER</article>",
                pdf=lambda doc: documents.PdfSerialisation(data=b"%PDF-LATER", page_count=1),
            ),
        )
        response = api_call(
            documents_api.invoice_document_pdf,
            "get",
            f"/api/invoices/{bill.pk}/document.pdf",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            invoice_id=str(bill.pk),
        )
        assert response.status_code == 200
        assert response.content == sealed_pdf
        assert response.content != b"%PDF-LATER"
        assert response["X-Document-Provenance"] == "original"


def test_cr049_t4_tc9__a_tampered_bill_refuses_and_is_never_softened(brazos, dana, docs_dir):
    """A changed byte is REPORTED. It must not degrade into "re-rendered from data".

    ⚠ `DEF-2554`'s lesson, applied: this corrupts the file it CHOSE, not
    whichever one the filesystem yielded first. The filesystem backend writes a
    payload and a `.meta` sidecar per document, and corrupting the sidecar
    proves nothing while looking exactly like a broken hash check.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        sealed = frozen(bill, HTML_TYPE)
        kept_bytes = document_store.fetch(sealed.id)

        payloads = [p for p in docs_dir.rglob("*") if p.is_file() and p.suffix != ".meta"]
        target = next(p for p in payloads if p.read_bytes() == kept_bytes)
        target.write_bytes(b"<article>a different bill entirely</article>")

        with pytest.raises(document_storage.ContentHashMismatch):
            document_store.fetch(sealed.id)

        response = open_the_page(bill, dana, brazos)
        # 409, not 422: `BIZ-STATE`. The bill is complete and renderable; what is
        # wrong is the STATE of the copy we kept, which is a different refusal
        # from "this bill is still a draft".
        assert response.status_code == 409, response.data
        assert response.data["message_key"] == "billing.document.hashMismatch"
        assert "reRendered" not in str(response.data), (
            "a corrupted seven-year record was softened into 're-rendered from data'"
        )


def test_cr049_t4_tc10__the_human_name_carries_the_account_and_the_bill_number(
    brazos, dana, docs_dir
):
    """A bulk export of half a million files unpacks to names a utility can read.

    Billing is in a better position than the dispatcher here: `bill_payload`
    carries `account_no`, stamped at draft, so no cross-module read is needed
    and no `MSG-0198f3c2` fallback is reached.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, invoice_no="BL-2607-000133")
        html = frozen(bill, HTML_TYPE)
        pdf = frozen(bill, PDF_TYPE)
        assert html.display_name.startswith("bill/")
        assert "A-10432" in html.display_name and "BL-2607-000133" in html.display_name
        assert html.display_name.endswith(".html")
        assert pdf.display_name.endswith(".pdf")


def test_cr049_t4_tc11__freezing_a_bill_writes_the_trail(brazos, dana, docs_dir, audit_rows):
    """Hard rule 7, and the question a regulator asks after seeing the document.

    Two trails, deliberately, because two different people ask two different
    questions. `document.stored` answers *"who kept this document, and when"* and
    is written by the store itself, once per artefact. `invoice.issued` carries
    `documents_frozen` and the two hashes, which answers the same question asked
    the other way round — from the bill — so a regulator holding a bill does not
    have to go to a second register to learn whether an original exists.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

    stored = [row for row in audit_rows if row["action"] == "document.stored"]
    assert len(stored) == 2, "one trail row per artefact kept"
    assert {row["after"]["content_type"] for row in stored} == {HTML_TYPE, PDF_TYPE}
    assert {row["after"]["kind"] for row in stored} == {"bill"}

    issued = [
        row
        for row in audit_rows
        if row["action"] == "invoice.issued" and row["entity_id"] == str(bill.pk)
    ]
    assert len(issued) == 1
    assert issued[0]["after"]["documents_frozen"] == 2
    assert set(issued[0]["after"]["document_hashes"]) == {HTML_TYPE, PDF_TYPE}


def test_cr049_t4_tc12__another_tenants_bill_is_indistinguishable_from_a_missing_one(
    brazos, dana, docs_dir
):
    """Existence must not leak (HR-1). Nothing here implements that — RLS does."""
    from apps.tenancy.models import Tenant

    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert frozen(bill, HTML_TYPE) is not None

    other = Tenant.objects.create(
        name="Silver Creek Water", subdomain=f"silver{uuid.uuid4().hex[:8]}"
    )
    with tenant_ctx(other):
        lookup = document_store.for_source(
            source_type="invoice", source_id=bill.pk, content_type=HTML_TYPE
        )
        assert lookup.document is None
        assert lookup.unavailable_reason == "document_not_stored"


def test_cr049_t4_tc13__the_frozen_bill_is_immutable_and_a_correction_is_a_new_row(
    brazos, dana, docs_dir
):
    """Hard rule 4, restated where the document lives.

    Storing an artefact touches no issued invoice row: the pointer is
    `stored_documents.source_id`, which is why nothing on the bill had to be
    written after issue.
    """
    from apps.tenancy.document_models import StoredDocument, StoredDocumentImmutable

    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        row = StoredDocument.objects.get(pk=frozen(bill, HTML_TYPE).id)
        with pytest.raises(StoredDocumentImmutable):
            row.display_name = "something else"
            row.save(update_fields=["display_name"])
        with pytest.raises(StoredDocumentImmutable):
            row.delete()
