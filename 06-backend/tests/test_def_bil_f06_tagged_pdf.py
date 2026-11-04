"""DEF-BIL-10546 — portal accessibility F-06: every customer PDF is a tagged PDF/UA-1 file.

Ruling: decision log 2026-10-23, *"Portal accessibility, Group H (bill PDF,
F-06): tagged PDFs through a PDF library, Liberation Sans, new documents only,
every customer PDF"*.

WHAT THIS PROVES, AND WHAT IT CANNOT
------------------------------------
veraPDF (a Java program) is NOT run here — CI has no Java. It is run by
`10-scripts/a11y/verapdf_customer_pdfs.py` over the SAME samples
(`tests/a11y_pdf_samples.py`), and on 2026-10-23 it reported 0 failed rules on
every one of them. What this file asserts is what a reader can check without a
validator, and it is exactly the four things the QA tester's veraPDF report
named: a structure tree, a `/Lang`, `DisplayDocTitle` true, embedded fonts —
plus the parity the ruling demands: **the tagged page says what the old page
said, the same money in the same order, the remittance stub present.**

RED FIRST (hard-won law 7): `test_the_old_writers_fail_every_marker` asserts the
pre-Group-H writers fail all four markers — that is the defect, kept as a
standing proof that the marker check can tell the two apart.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from apps.billing import documents
from apps.customers import agreement_pdf
from core import tagged_pdf
from tests import a11y_pdf_samples as samples
from tests.test_us_bil_022_documents import pdf_text

BILL_CASES = [
    (utility, language, spec.key)
    for utility in samples.UTILITIES
    for language in samples.LANGUAGES
    for spec in documents.LAYOUT_SPECS
]
AGREEMENT_CASES = [(language, stamped) for language in samples.LANGUAGES for stamped in (False, True)]

MONEY = re.compile(r"-?\d[\d,]*\.\d{2} USD")
SECTION_HEADINGS = (
    documents.HEADING_SUMMARY,
    documents.HEADING_SERVICES,
    documents.HEADING_CHARGES,
    documents.USAGE_HEADING,
    documents.HEADING_MESSAGES,
    documents.HEADING_STUB,
)


def _bill_pages(utility: str, language: str, key: str) -> tuple[str, str, documents.LayoutSpec, dict]:
    document, spec = samples.bill_document(utility, language, key)
    old = documents._pdf(document, spec).data
    new = documents.LAYOUTS_BY_KEY[key].tagged_pdf(document).data
    return old, new, spec, document


def _without_furniture(text: str, footer: str) -> str:
    """Drop the page furniture (`<footer> Page n of N`): where a page breaks is
    geometry, not content, and the two writers break pages differently."""
    return re.sub(re.escape(footer) + r" Page \d+ of \d+", " ", text)


def _words(text: str) -> list[str]:
    return text.casefold().split()


@pytest.mark.parametrize(("utility", "language", "key"), BILL_CASES)
def test_every_bill_layout_is_a_tagged_pdf(utility, language, key):
    """StructTreeRoot, /Lang, DisplayDocTitle, embedded fonts — every layout,
    both utility set-ups, English and Spanish customers."""
    _old, new, _spec, document = _bill_pages(utility, language, key)
    found = tagged_pdf.markers(new)
    assert found["struct_tree_root"] is True
    assert found["marked"] is True
    assert found["lang"] == documents.DOCUMENT_LANGUAGE == "en"
    assert found["display_doc_title"] is True
    assert found["title"] == f"{documents.TITLE} {document['invoice_no']}"
    assert found["embedded_fonts"] is True
    assert found["base14_fonts"] is False
    # One face, Liberation Sans, and no fallback font was pulled in.
    faces = set(re.findall(rb"/BaseFont\s*/[A-Z]{6}\+([\w-]+)", tagged_pdf.inflated(new)))
    assert faces and all(face.startswith(b"SBH-Liberation-Sans") for face in faces), faces


@pytest.mark.parametrize(("language", "stamped"), AGREEMENT_CASES)
def test_every_agreement_is_a_tagged_pdf_in_its_own_language(language, stamped):
    facts, body, stamp, lang = samples.agreement_inputs(language, stamped=stamped)
    new = agreement_pdf.render(facts, body, stamp=stamp, language=lang)
    found = tagged_pdf.markers(new)
    assert found["struct_tree_root"] is True
    assert found["lang"] == language
    assert found["display_doc_title"] is True
    assert found["title"] == facts["agreement_name"]
    assert found["embedded_fonts"] is True
    assert found["base14_fonts"] is False


def test_the_old_writers_fail_every_marker():
    """The defect itself, kept: what QA's veraPDF run found, in four markers."""
    old, _new, _spec, _doc = _bill_pages("a2", "en", documents.DEFAULT_LAYOUT_KEY)
    facts, body, stamp, _lang = samples.agreement_inputs("en", stamped=False)
    for page in (old, agreement_pdf.render_untagged(facts, body, stamp=stamp)):
        found = tagged_pdf.markers(page)
        assert found["struct_tree_root"] is False
        assert found["lang"] is None
        assert found["display_doc_title"] is False
        assert found["embedded_fonts"] is False
        assert found["base14_fonts"] is True


@pytest.mark.parametrize(("utility", "language", "key"), BILL_CASES)
def test_the_tagged_bill_says_what_the_old_bill_said(utility, language, key):
    """PARITY (non-negotiable, Group H): same money in the same order, the same
    words, the same sections in the same order, and the stub where it was."""
    old, new, spec, document = _bill_pages(utility, language, key)
    footer = f"Bill {document['invoice_no']}"
    old_text = _without_furniture(pdf_text(old), footer)
    new_text = _without_furniture(tagged_pdf.text_of(new), footer)

    old_money = MONEY.findall(old_text)
    assert old_money, "the sample bill printed no money — the parity check would be empty"
    assert MONEY.findall(new_text) == old_money

    # Every word the old page printed, the tagged page prints, as often. Case is
    # folded because the old page upper-cased its column heads in Python and the
    # tagged page does it in CSS. Order is checked below, per section, because
    # the masthead and the usage grid are LAID OUT differently (the old page
    # wraps twelve months into two rows of six), which is geometry.
    assert Counter(_words(new_text)) == Counter(_words(old_text))

    def headings(text: str) -> list[str]:
        folded = text.casefold()
        found = [(folded.find(h.casefold()), h) for h in SECTION_HEADINGS if h.casefold() in folded]
        return [h for _pos, h in sorted(found)]

    assert headings(new_text) == headings(old_text)

    stub_heading = documents.HEADING_STUB.casefold()
    if spec.stub:
        assert stub_heading in new_text.casefold()
        scan = next(f.value for f in document["stub"] if f.label == documents.LABEL_SCAN)
        assert scan in new_text
        # The stub is still the LAST section, and it carries the amount due.
        folded = new_text.casefold()
        assert folded.rfind(stub_heading) > folded.rfind(documents.HEADING_MESSAGES.casefold())
        assert MONEY.findall(new_text[folded.rfind(stub_heading):]) == [old_money[-1]]
    else:
        assert stub_heading not in new_text.casefold()


@pytest.mark.parametrize(("language", "stamped"), AGREEMENT_CASES)
def test_the_tagged_agreement_says_what_the_old_agreement_said(language, stamped):
    facts, body, stamp, lang = samples.agreement_inputs(language, stamped=stamped)
    old = pdf_text(agreement_pdf.render_untagged(facts, body, stamp=stamp))
    new = tagged_pdf.text_of(agreement_pdf.render(facts, body, stamp=stamp, language=lang))
    footer = facts["agreement_name"]
    assert _words(_without_furniture(new, footer)) == _words(_without_furniture(old, footer))


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("hi", "यह समझौता आपकी सेवा की शर्तें बताता है।"),
        ("ja", "この契約はサービスの条件を定めます。"),
        ("ko", "이 계약은 서비스 조건을 정합니다."),
    ],
)
def test_hindi_japanese_korean_are_no_worse_than_before(language, text):
    """Liberation Sans has no glyphs for them and neither did Base-14 (ruled:
    no other font). Each unrepresentable character prints as `?` exactly as the
    old page printed it, is NAMED, and no fallback face is embedded. The gap is
    a filed defect, not a silent patch."""
    facts, _body, _stamp, _lang = samples.agreement_inputs("en", stamped=False)
    old = pdf_text(agreement_pdf.render_untagged(facts, text))
    new_pdf = agreement_pdf.render(facts, text, language=language)
    new = tagged_pdf.text_of(new_pdf)
    footer = facts["agreement_name"]
    assert _words(_without_furniture(new, footer)) == _words(_without_furniture(old, footer))
    assert "?" in new
    _cleaned, lost = tagged_pdf.representable(text)
    assert lost and all(ch in text for ch in lost)
    assert tagged_pdf.markers(new_pdf)["lang"] == language
    faces = set(re.findall(rb"/BaseFont\s*/[A-Z]{6}\+([\w-]+)", tagged_pdf.inflated(new_pdf)))
    assert all(face.startswith(b"SBH-Liberation-Sans") for face in faces), faces


def test_a_bill_name_the_font_cannot_draw_is_substituted_and_named():
    """OQ-150's posture on the tagged page: print `?`, name the character."""
    document, spec = samples.bill_document("wdm", "en", documents.DEFAULT_LAYOUT_KEY)
    document["masthead"] = (
        documents.DocumentField(label="Utility", value="市 Water"),
    ) + tuple(document["masthead"][1:])
    page = documents.LAYOUTS_BY_KEY[spec.key].tagged_pdf(document)
    assert page.characters == ("市",)
    assert page.unrepresentable and "市" in page.unrepresentable[0].detail
    assert "? Water" in tagged_pdf.text_of(page.data)


def test_the_same_document_renders_the_same_bytes():
    """Determinism (the old writer's tc12 property, kept): no clock, a content
    hash for /ID, so a re-serialisation of a kept bill is byte-identical."""
    document, spec = samples.bill_document("a2", "es", "summary-first-letter-v1")
    first = documents.LAYOUTS_BY_KEY[spec.key].tagged_pdf(document).data
    second = documents.LAYOUTS_BY_KEY[spec.key].tagged_pdf(document).data
    assert first == second
    assert b"/CreationDate" not in tagged_pdf.inflated(first)


def test_a_page_without_a_language_or_title_is_refused_not_returned():
    """The renderer's guard: an untagged-in-effect file never reaches a store."""
    with pytest.raises(tagged_pdf.TaggedPdfError, match="no /Lang"):
        tagged_pdf.render("<!doctype html><html><head><title>T</title></head><body><p>x</p></body></html>")
    with pytest.raises(tagged_pdf.TaggedPdfError, match="no /Title"):
        tagged_pdf.render('<!doctype html><html lang="en"><head></head><body><p>x</p></body></html>')


def test_the_html_carries_what_the_tags_need():
    """lang, a title, row and column header scopes, the logo's alt text, one H1,
    and the bars hidden from readers (they repeat the line under them)."""
    document, spec = samples.bill_document("a2", "en", documents.DEFAULT_LAYOUT_KEY)
    body = documents._html_for(spec)(document)
    assert '<html lang="en">' in body
    assert f"<title>{documents.TITLE} {document['invoice_no']}</title>" in body
    assert '<th scope="row">Account</th>' in body
    assert '<th scope="col">Amount</th>' in body
    assert 'alt="Sample City Utilities logo"' in body
    assert body.count("<h1") == 1
    assert 'class="barcode" aria-hidden="true"' in body


# ── The issue path, end to end (run on PostgreSQL too — law 14) ─────────────
from tests.test_cr049_t4_bill_freeze import (  # noqa: E402 — the freeze's own helpers
    PDF_TYPE,
    an_issued_bill,
    docs_dir,  # noqa: F401 — pytest fixture
    frozen,
)
from tests.test_us_met_helpers import *  # noqa: E402,F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: E402


@pytest.mark.django_db
def test_issue_still_freezes_exactly_one_page_and_it_is_the_tagged_one(brazos, dana, docs_dir):  # noqa: F811
    """Issue renders the DRAFT (tagged), keeps that page write-once, and keeps
    ONE of it. A re-render of the issued bill does not replace it."""
    from apps.tenancy import document_models, document_store

    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        pdf = frozen(bill, PDF_TYPE)
        assert pdf is not None
        kept = document_store.fetch(pdf.id)
        found = tagged_pdf.markers(kept)
        assert found["struct_tree_root"] and found["embedded_fonts"] and found["lang"] == "en"
        assert found["title"] == f"{documents.TITLE} {bill.invoice_no}"
        documents.render_invoice(bill)  # a reprint read; writes nothing
        count = document_models.StoredDocument.objects.filter(
            source_type="invoice", source_id=bill.pk, content_type=PDF_TYPE
        ).count()
        assert count == 1
