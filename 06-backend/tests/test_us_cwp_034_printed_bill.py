# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-034 (EP-CWP-07) — the bill as it was printed. Screen: CWP-029
# Rules:    BR-CWP-045 (serves the issued file from its pinned template; NEVER
#           re-renders) · BR-NOT-027 (a legal document is frozen AS THE
#           DOCUMENT) · BR-BIL-026 (the pin) · BR-BIL-030 (locked at issue) ·
#           BR-CWP-010 (both halves in the query)
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `printed_bill_for` /
#           `printed_bill_bytes` · apps/portal/api.py `bill_document`
# ───────────────────────────────────────────────────────
"""`US-CWP-034`'s cases — and the finding that made the story buildable.

⚠ **THE STORED ARTEFACT EXISTS.** The coordinator asked us to find out whether
the staff app serves a KEPT document or re-renders one, and to say so loudly
either way. It keeps one: `apps/tenancy/document_store` holds the bill's HTML
and its printable page, frozen at issue by `billing.frozen_bill.freeze_at_issue`
under `BR-NOT-027` and `CR-049` task 4, and `frozen_bill.reproduce` answers
WHICH document a caller may serve **without rendering anything**. The portal
calls that same function. So `BR-CWP-045` is kept by asking the module that owns
the bytes, rather than by the portal owning a second renderer.

⚠ **AND THE PORTAL IS STRICTER THAN THE STAFF ROUTE, DELIBERATELY.**
`documents_api` falls back to a rebuild for a CLERK, labelled
`X-Document-Provenance: re_rendered_from_data_not_the_original`, because a clerk
can read the caption and act on it. A customer cannot: this screen's promise is
*"exactly as it was printed and posted on 30 August"*, and a fresh render handed
over under that sentence is the one thing this story exists to prevent. So a
bill with no kept copy answers `available: false`, which is TC-4.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import frozen_bill, models as billing_models
from apps.portal.seams import billing_seam
from apps.tenancy import document_storage, document_store
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

#: The bytes the bill run produced. A stand-in for `RenderedDocument`, because
#: `freeze_at_issue` reads exactly two attributes off it (`ARTEFACTS`) and this
#: file is about what the PORTAL does with a kept artefact — the real render and
#: the real freeze are `test_cr049_t4_bill_freeze.py`'s subject and are proved
#: there against `documents.render_invoice`.
POSTED_HTML = "<html><body>Pine Hill Water &amp; Power · BL-2608-0141 · $142.18</body></html>"
POSTED_PDF = b"%PDF-1.4 the page that went in the envelope on 30 August\n%%EOF\n"


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def a_posted_bill(tenant, account, *, number=NUMBER, keep=True):
    """One issued bill, and — when `keep` — the artefacts frozen at issue."""
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


@pytest.mark.django_db
def test_us_cwp_034_tc1_the_portal_serves_the_KEPT_page_byte_for_byte(
    pine_hill, sarah, docs_dir
):
    """⚠ **BYTE-IDENTICAL TO WHAT THE BILL RUN PRODUCED**, and hash-verified.

    `document_store.fetch` re-computes the hash on this read rather than taking
    it on trust (`CR-049` step 5d(e) decision 7), so a copy whose bytes moved
    refuses instead of being served.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        served = billing_seam.printed_bill_bytes([account.pk], number=NUMBER)

    assert served is not None
    page, content_type, filename = served
    assert page == POSTED_PDF, "the portal served something other than what was posted"
    assert content_type == "application/pdf"
    assert filename == "BL-2608-0141.pdf", "the file is named by the number, never by an id"


@pytest.mark.django_db
def test_us_cwp_034_the_answer_names_its_provenance_and_its_pin(pine_hill, sarah, docs_dir):
    """`original`, never the rebuild, and the pinned version travels (TC-2/3/6).

    ⚠ **`template_version` IS WHAT MAKES TC-2 AND TC-3 UNNECESSARY TO SIMULATE.**
    Publishing `bill-v4` or changing a logo cannot reach this answer, because
    nothing on this path reads a *current* or *latest published* pointer — it
    reads the bill's own pin and the bytes kept beside it. There is no code here
    that a template edit could change the output of.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)

    assert answer["available"] is True
    assert answer["provenance"] == billing_seam.PRINTED_ORIGINAL
    assert answer["unavailable_reason"] is None
    assert answer["template_version"] == 3, "the pin the bill was issued on"
    assert answer["number"] == NUMBER
    assert answer["byte_length"] == len(POSTED_PDF)
    # B14 rule 31 — no id of any kind, not even the template's uuid.
    assert not {"id", "invoice_id", "template_id", "document_id"} & set(answer)


@pytest.mark.django_db
def test_us_cwp_034_tc2_TC3_a_second_read_after_a_template_edit_is_the_same_bytes(
    pine_hill, sarah, docs_dir
):
    """TC-2 and TC-3 together: nothing a tenant changes moves an issued bill.

    Two reads, and the bytes are identical because they are the SAME OBJECT
    rather than two renders that happen to agree. That distinction is the story:
    a re-render is byte-stable only while the layout code is, which is
    `DEF-2553` in one sentence.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        first = billing_seam.printed_bill_bytes([account.pk], number=NUMBER)
        second = billing_seam.printed_bill_bytes([account.pk], number=NUMBER)
    assert first[0] == second[0] == POSTED_PDF


@pytest.mark.django_db
def test_us_cwp_034_tc4_NEGATIVE_a_bill_with_no_kept_copy_says_so_and_never_rebuilds(
    pine_hill, sarah, docs_dir
):
    """⚠ **NOT A RE-RENDER AND NOT A 500** — the story's own words.

    Every bill issued before `v2.88.0` is this case, so it is the common one
    rather than the edge. The bill is still readable line by line on `CWP-028`;
    what is missing is the FILE, and the screen states that absence with a route
    to ask.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account, keep=False)
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)
        assert billing_seam.printed_bill_bytes([account.pk], number=NUMBER) is None

    assert answer is not None, "the BILL exists; it is the document that does not"
    assert answer["available"] is False
    assert answer["provenance"] == billing_seam.PRINTED_RE_RENDERED
    assert answer["unavailable_reason"], "the reason is named, never a bare false"


@pytest.mark.django_db
def test_us_cwp_034_tc5_TENANT_ISOLATION_a_bill_outside_the_account_set_is_absent(
    pine_hill, sarah, docs_dir
):
    """`BR-CWP-010` — the same 404 an unknown number gets.

    A second Pine Hill account holds the bill; the login does not hold that
    account. Both halves are in `bill_in_set`'s own `filter`, so the row is
    never fetched.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        assert billing_seam.printed_bill_for([], number=NUMBER) is None
        assert billing_seam.printed_bill_bytes([], number=NUMBER) is None
        assert billing_seam.printed_bill_for([account.pk], number="BL-9999-0000") is None


@pytest.mark.django_db
def test_us_cwp_034_a_kept_page_is_never_reachable_by_a_storage_key(
    pine_hill, sarah, docs_dir
):
    """⚠ **THE PORTAL HANDS OUT BYTES, NEVER A KEY.**

    `document_storage`'s own rule: a caller must never be able to ask for a key
    it composed. The answer carries the length and the media type so a screen
    can size a download control, and nothing a caller could put in a URL.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)
    assert not {"storage_key", "url", "content_hash", "storage_backend"} & set(answer)


@pytest.mark.django_db
def test_us_cwp_034_the_seam_renders_nothing_even_when_it_could(
    pine_hill, sarah, docs_dir, monkeypatch
):
    """⚠ **THE GUARD PROVED RED FIRST.** `documents.render_invoice` is booby-
    trapped for the length of this test: if the portal path ever reaches for a
    render, this fails by name rather than quietly serving a rebuild.

    That is the check `BR-CWP-045` actually needs. Asserting the BYTES are right
    cannot distinguish *served the kept copy* from *rebuilt one that happens to
    match today*, which is exactly the state `DEF-2553` shipped in.
    """
    from apps.billing import documents

    def refuse(*args, **kwargs):
        raise AssertionError("the portal re-rendered a bill (BR-CWP-045)")

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
        monkeypatch.setattr(documents, "render_invoice", refuse)
        assert billing_seam.printed_bill_for([account.pk], number=NUMBER)["available"] is True
        assert billing_seam.printed_bill_bytes([account.pk], number=NUMBER)[0] == POSTED_PDF
        # …and the no-copy case must not reach for one either.
        a_posted_bill(pine_hill, account, number="BL-2607-0139", keep=False)
        assert (
            billing_seam.printed_bill_for([account.pk], number="BL-2607-0139")["available"]
            is False
        )


@pytest.mark.django_db
def test_us_cwp_034_the_kept_artefacts_are_the_bill_kind_and_carry_no_channel(
    pine_hill, sarah, docs_dir
):
    """A bill freezes at CREATION, not at SEND — so `channel` is None.

    Asserted here because the portal's read goes through
    `document_store.for_source(..., channel=None)`; a bill frozen with a channel
    would be invisible to it and the screen would state an absence over a
    document that exists.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        invoice = a_posted_bill(pine_hill, account)
        found = document_store.for_source(
            source_type="invoice",
            source_id=invoice.pk,
            channel=None,
            content_type="application/pdf",
        )
    assert found.found and found.document.kind == "bill"
    assert found.document.channel is None
    assert isinstance(found.document.stored_at, dt.datetime)


@pytest.mark.django_db
def test_us_cwp_034_a_draft_bill_has_no_document_and_is_not_reachable(pine_hill, sarah):
    """`BR-CWP-041` again, on this route: a draft is not a bill to a customer."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        billing_models.Invoice.objects.create(
            tenant=pine_hill,
            account=account,
            invoice_no="BL-2609-0999",
            status=billing_models.INVOICE_DRAFT,
            service_date=AUGUST,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            total=Decimal("99.9900"),
        )
        assert billing_seam.printed_bill_for([account.pk], number="BL-2609-0999") is None


@pytest.mark.django_db
def test_def_cwp_3983_view_1_serves_the_SAME_bytes_INLINE_so_the_page_can_be_looked_at(
    pine_hill, sarah, docs_dir
):
    """`DEF-CWP-3983` — `CWP-029` could not be LOOKED at, only downloaded.

    ⚠ **THE POINT IS THAT NOTHING ABOUT THE DOCUMENT CHANGES.** `?view=1`
    reaches the same `printed_bill_bytes`, so this asserts the bytes are
    IDENTICAL to the plain route's and only `Content-Disposition` differs. A
    preview that is a re-render is exactly what `BR-CWP-045` and `BR-NOT-027`
    forbid, and the figures being right would not make it honest.
    """
    from django.test import Client

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    base = f"/api/{pine_hill.subdomain}/portal/bills/{NUMBER}/document.pdf"

    downloaded = client.get(base)
    assert downloaded.status_code == 200, downloaded.content
    assert downloaded["Content-Disposition"] == 'attachment; filename="BL-2608-0141.pdf"'

    viewed = client.get(base + "?view=1")
    assert viewed.status_code == 200, viewed.content
    assert viewed["Content-Disposition"] == 'inline; filename="BL-2608-0141.pdf"'

    # ⚠ SAME BYTES. This is the assertion the whole change stands on.
    assert bytes(viewed.content) == bytes(downloaded.content) == POSTED_PDF
    assert viewed["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_def_cwp_3983_view_1_is_NOT_a_way_round_the_download_permission(
    pine_hill, sarah, docs_dir
):
    """⚠ **A PREVIEW HANDS OVER THE BYTES, SO IT CARRIES THE SAME GRANT.**

    `US-CWP-034` TC-7 makes DOWNLOAD a separate permission from *see*, and the
    browser's own PDF viewer has a save button in it — so a preview gated any
    more loosely than the download would be that rule defeated by a query
    parameter. The check runs BEFORE the disposition branch, and this asserts a
    bill outside the login's account set is the same 404 either way
    (`BR-CWP-010`).
    """
    from django.test import Client

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    missing = f"/api/{pine_hill.subdomain}/portal/bills/BL-9999-0000/document.pdf"
    assert client.get(missing).status_code == 404
    assert client.get(missing + "?view=1").status_code == 404


@pytest.mark.django_db
def test_def_cwp_4657_a_kept_file_GONE_FROM_STORAGE_refuses_like_one_never_kept(
    pine_hill, sarah, docs_dir
):
    """DEF-CWP-4657 — there are TWO ways to have no original and only one was handled.

    TC-4 above covers the first: no document row at all, `printed_bill_bytes`
    answers `None`, and the endpoint states the absence. **The second is a row
    whose BYTES have gone from the store** — a redeploy onto a different volume,
    a restored database, a retention sweep — and it raised `StoredObjectMissing`
    straight through the seam and reached the customer as a raw 500, on the one
    path whose own docstring says *"NOT A 500 AND NOT A RE-RENDER"*.

    The storage layer already draws the distinction this test needs and draws it
    well: `StoredObjectMissing` says *"the row exists, so the object was written
    and has since been removed — which is not the same as no document having
    been stored"*. **Nothing anywhere caught it.** A distinction made carefully
    one layer down and collapsed by every caller is hard-won law 1 — the comment
    was not the guarantee.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account, keep=True)
        # the guard is real before the file goes: this is a KEPT bill
        assert billing_seam.printed_bill_bytes([account.pk], number=NUMBER) is not None

        # the row stays; only the object leaves the store
        gone = [p for p in docs_dir.rglob("*") if p.is_file() and p.suffix != ".meta"]
        assert gone, "nothing was written, so this test would prove nothing"
        for path in gone:
            path.unlink()

        assert billing_seam.printed_bill_bytes([account.pk], number=NUMBER) is None, (
            "a document row whose bytes are gone must answer None, so the caller "
            "states the absence — not raise and become a 500 at the customer"
        )
        answer = billing_seam.printed_bill_for([account.pk], number=NUMBER)

    assert answer is not None, "the BILL exists; it is the file that does not"
    #: ⚠ **`available` IS `False` NOW, AND THIS ASSERTION IS THE EXPIRY TEST
    #: FIRING (`DEF-CWP-4658` CLOSED by `CR-085` `CPB-19`, 2026-09-08).**
    #:
    #: It used to read `is True`, deliberately the wrong-looking way round,
    #: with the note: *"the day that check lands this test goes RED and names
    #: the row to close. A hold with no test that fires when it expires is a
    #: promise nobody keeps."* **It did exactly that** — it is one of the two
    #: reds that told wave 3 the row was ready to close, and it is the reason
    #: this file is worth reading before changing `printed_bill_for`.
    #:
    #: The note also said an honest answer *"needs an existence check the
    #: storage backend does not have — `put`, `get`, `temporary_read_url` and
    #: no `exists`"*. That was true and it was not the only way: `printed_bill_
    #: for` now asks `document_store.fetch` the same question the serving path
    #: asks and throws the bytes away. It costs ONE extra object read per open
    #: of `CWP-029` — one document, for one customer, who is about to fetch the
    #: same object to look at it — and it is why no new backend method was
    #: needed. The LIST (`CWP-031`) deliberately does not do this; forty rows
    #: would be forty object reads to draw a table.
    assert answer["available"] is False, (
        "the row is there and the bytes are not, so the screen must not offer a "
        "download the server will refuse (DEF-CWP-4658)"
    )
    assert answer["unavailable_reason"] == "document_not_stored"


@pytest.mark.django_db
def test_def_cwp_4657_the_ENDPOINT_states_the_absence_instead_of_answering_500(
    pine_hill, sarah, docs_dir
):
    """The same fault seen from where it actually hurt: the HTTP answer.

    The seam test above proves the value; this proves what a customer gets.
    Before the fix this request answered **500** with a `FileNotFoundError`
    traceback, on the endpoint documented as *"NOT A 500"*.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account, keep=True)
        for path in [p for p in docs_dir.rglob("*") if p.is_file() and p.suffix != ".meta"]:
            path.unlink()
    from django.test import Client

    enrol_maria(pine_hill, sarah)
    client = Client()
    signed_in = client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert signed_in.status_code == 200, signed_in.content[:200]
    answer = client.get(
        f"/api/{pine_hill.subdomain}/portal/bills/{NUMBER}/document.pdf?view=1"
    )
    assert answer.status_code != 500, "a missing kept file must never be a server error"
    assert answer.status_code == 409, answer.content[:300]


@pytest.mark.django_db
def test_def_cwp_4657_a_TAMPERED_file_is_never_softened_into_no_copy_kept(
    pine_hill, sarah, docs_dir
):
    """The other half, and the reason the fix answers three cases and not two.

    `BR-NOT-027`: a tampered document REFUSES and never degrades into a
    re-render. Missing and tampered are different facts and get different
    answers — swallowing `ContentHashMismatch` alongside the missing case would
    turn *"these are not the bytes the customer received"* into a quiet
    *"no copy kept"*, which is the one outcome that must never happen here.

    ⚠ **AMENDED BY `CR-085` `CPB-19` (`DEF-CWP-4699`), AND THE RULE IS
    UNCHANGED.** This case used to assert that `printed_bill_bytes` RAISED,
    because leaving `ContentHashMismatch` uncaught was how the distinction was
    kept. What nobody had measured is where that raise came out: as a Django
    error page in front of a customer pressing *view my bill*, on the route
    whose own docstring says *"NOT A 500 AND NOT A RE-RENDER"*. The
    distinction now lives in a THIRD verdict rather than in an uncaught
    exception, so the rule is kept and the stack trace is not — and this test
    asserts the thing the rule actually cares about: that the tampered answer
    is not the missing one.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_posted_bill(pine_hill, account, keep=True)
        written = [p for p in docs_dir.rglob("*") if p.is_file() and p.suffix != ".meta"]
        assert written, "nothing was written, so this test would prove nothing"
        for path in written:
            path.write_bytes(b"%PDF-1.4 not the page that went in the envelope\n%%EOF\n")

        from apps.portal.seams import notifications_seam

        verdict, payload, _ctype, _name = billing_seam.printed_bill_service(
            [account.pk], number=NUMBER
        )
        # ⚠ **THE NEGATIVE IS THE RULE.** Two different refusals, and the
        # tampered one is NOT the missing one.
        assert verdict == notifications_seam.DOCUMENT_NOT_TRUSTED
        assert verdict != notifications_seam.DOCUMENT_NOT_KEPT
        assert payload is None, "not one byte of a document we cannot vouch for"
        # The two-valued caller still answers None rather than raising, so no
        # route reaches the customer as a 500 (`test_cr085_w3_document_copies`
        # asserts the 409 at the edge).
        assert billing_seam.printed_bill_bytes([account.pk], number=NUMBER) is None
