# ── Trace ──────────────────────────────────────────────
# Change:   "A clerk cannot attach a document to a service request." PO:
#           *"you will have to reduce the size and save them on cloud
#           container etc"*.
# Rules:    BR-SHL-031 · BR-CUS-095 · BR-WRK-047 · NFR-33 · NFR-35 ·
#           BR-TEN-003 (existence must not leak) · CLAUDE.md hard rule 1 and 7.
# ───────────────────────────────────────────────────────
"""A service request can hold a real file — proved against the running code.

⚠ **EVERY CASE HERE WAS SHOWN RED BEFORE IT WAS SHOWN GREEN** (hard-won law 7),
and through `pytest` — the harness that will run them — never through a
`__main__` that exercises a path nobody else takes.

⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY, ASKED BEFORE THEY WERE WRITTEN**
(law 7 habit 2). *"A document row exists"* passes with `storage_ref` empty, and
*"`storage_ref` is set"* passes with a reference to nothing at all — which is
exactly the failure the screen's old sentence described. So the central case
does not assert a row, a flag or a length: **it reads the bytes back out
through the store and compares them with what went in, byte for byte**
(`TestTheBytesComeBack`). A store that records a reference to nothing fails it.

⚠ **AND THE SECOND-PDF CASE IS THE ONE THAT WOULD HAVE SHIPPED BROKEN.**
`uq_stored_documents_filed` allows one artefact per
`(tenant, source_type, source_id, content_type)` where the channel is NULL. Had
this filed under the REQUEST, the first `application/pdf` on a request would
work and the second would be refused by the database — the most ordinary thing
a clerk does. It is here because `tenancy/0040` and `tenancy/0044` had each
already recorded the identical finding, for a technician's ninth photograph and
a clerk's second account document.

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""

import random
import struct
import uuid
import zlib

import pytest

from apps.customers import models, service_request_documents as doc_files
from apps.tenancy.document_models import (
    KIND_SERVICE_REQUEST_DOCUMENT,
    SOURCE_SERVICE_REQUEST_DOCUMENT,
    StoredDocument,
)
from core import document_shrink, errors
from core.tenancy import tenant_context

pytestmark = pytest.mark.django_db

#: A deed. ⚠ **STORED BYTE FOR BYTE — nothing in this product touches a PDF.**
PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Deed, 1408 Elm St) >>\n" + b"D" * 4000 + b"\n%%EOF"


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """`set_config` on sqlite, the REAL GUC on PostgreSQL — the store's own
    fixture, reused verbatim so these files cannot drift about what a tenant
    context is."""
    from django.db import connection as real_connection

    from core import tenancy as core_tenancy
    from tests.test_us_ten_helpers import FakeGucConnection

    if real_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", FakeGucConnection())
    core_tenancy._current_tenant.set(None)
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can see another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


@pytest.fixture()
def two_utilities(db):
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Silver Creek Water", subdomain=f"silver{suffix}")
    beta = Tenant.objects.create(name="Brazos Utility", subdomain=f"brazos{suffix}")
    return alpha, beta


def _request(tenant, request_no="SR-2026-00042"):
    return models.ServiceRequest.objects.create(
        tenant=tenant,
        request_no=request_no,
        address_as_given="1408 Elm St, Ottumwa IA",
    )


class _Upload:
    """One multipart part, as DRF hands it to the endpoint."""

    def __init__(self, payload: bytes, *, name: str, content_type: str):
        self._payload = payload
        self.name = name
        self.content_type = content_type

    def read(self) -> bytes:
        return self._payload


def _actor(user_id=None):
    from types import SimpleNamespace

    return SimpleNamespace(id=user_id)


def _attach(request, *, payload=PDF, name="drivers-licence.pdf", content_type="application/pdf",
            doc_type="proof_of_identity", **extra):
    fields = {"doc_type": doc_type, "name": name}
    fields.update(extra)
    return doc_files.attach_file(
        _actor(), request.pk, fields, _Upload(payload, name=name, content_type=content_type)
    )


def _png(width=900, height=700, *, level=1):
    """A PNG written the way a scanner writes one — fast, not small.

    ⚠ **BUILT WITH `zlib` AND `struct`, NOT WITH AN IMAGE LIBRARY**, because
    this backend ships none and a test that needed one would be a test that
    cannot run (law 7's *incapable of passing*). A PNG is a header, a deflated
    stream of filtered scanlines and a trailer; that is enough to be a real
    PNG that the reduction path really parses.

    ⚠ **THE CONTENT IS DOCUMENT-LIKE ON PURPOSE — bands of dark "text" on
    noisy white "paper" — AND THE FIRST DRAFT WAS NOT.** A smooth arithmetic
    gradient compresses almost identically at level 1 and level 9, so the
    reduction came out at **0.2%** and `len(stored) < len(original)` passed by
    736 bytes. A check that passes by a rounding error is a check that will
    flap, and it would have reported a real saving where there was none.
    Document-like content moves 640,968 → 512,513 bytes (**20.0%**), which is
    in the same country as the **26.4%** measured on 56 real files.
    """
    rng = random.Random(7)
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter byte: None
        ink_band = (y % 37) < 9
        for x in range(width):
            if ink_band and ((x * rng.randint(1, 3)) % 11) < 4:
                value = rng.randint(8, 70)      # a letterform
            else:
                value = rng.randint(238, 255)   # paper, with a scanner's noise
            rows += bytes((value, value, value))

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"pHYs", struct.pack(">IIB", 11811, 11811, 1))  # 300 dpi
        + chunk(b"IDAT", zlib.compress(bytes(rows), level))
        + chunk(b"IEND", b"")
    )


def _pixels(blob):
    """The inflated scanline stream — what a decoder would actually draw."""
    return zlib.decompress(
        b"".join(data for kind, data in document_shrink._png_chunks(blob) if kind == b"IDAT")
    )


# ═══════════════════════════════════════════════════════════════════════════
# §1 · THE CAPABILITY — a request can hold a file
# ═══════════════════════════════════════════════════════════════════════════


class TestAttaching:
    def test_a_clerk_can_attach_a_file(self, two_utilities, docs_dir):
        """The thing that did not exist. `storage_ref` is set and a real
        `stored_documents` row stands behind it under the tenth source type."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request)

            row = models.ServiceRequestDocument.objects.get(pk=filed["id"])
            assert row.storage_ref, "the row was written with no reference to any bytes"
            stored = StoredDocument.objects.get(pk=row.storage_ref)
            assert stored.kind == KIND_SERVICE_REQUEST_DOCUMENT
            assert stored.source_type == SOURCE_SERVICE_REQUEST_DOCUMENT
            # ⚠ THE SOURCE IS THE ATTACHMENT ROW, NOT THE REQUEST. See §2.
            assert stored.source_id == row.id
            assert row.uploaded_by_id is None or row.uploaded_by_id == _actor().id
            assert row.uploaded_at is not None
            assert row.name == "drivers-licence.pdf"

    def test_attaching_is_not_verifying(self, two_utilities, docs_dir):
        """*"Attaching a file is not the same as verifying it."* Every
        attachment lands `Not checked` and stays there until a person looks."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request)
            assert filed["verification_state"] == models.ServiceRequestDocument.NOT_CHECKED
            row = models.ServiceRequestDocument.objects.get(pk=filed["id"])
            assert row.verified_by_id is None and row.verified_at is None

    def test_a_tick_made_earlier_can_be_given_its_file(self, two_utilities, docs_dir):
        """The six rows on the beta cluster are ticks with no file. This is the
        branch that makes them usable rather than a convenience."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            tick = models.ServiceRequestDocument.objects.create(
                tenant=alpha, request=request, doc_type="tenancy_agreement_or_deed",
                required_flag=True,
            )
            assert not tick.storage_ref

            filed = _attach(request, document_id=str(tick.pk), doc_type="tenancy_agreement_or_deed")

            assert filed["id"] == str(tick.pk), "a second row was created instead of filling this one"
            tick.refresh_from_db()
            assert tick.storage_ref and tick.required_flag is True

    def test_a_row_that_already_holds_a_file_is_refused(self, two_utilities, docs_dir):
        """⚠ **THE BYTES ARE WRITE-ONCE.** The first file cannot be deleted, so
        "replacing" it would leave two artefacts and a row naming one of them —
        and *"is this the document the applicant gave us"* would stop having an
        answer."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request)
            with pytest.raises(errors.BizError) as refusal:
                _attach(request, document_id=filed["id"])
            assert refusal.value.code == errors.BIZ_LOCKED


# ═══════════════════════════════════════════════════════════════════════════
# §2 · THE ONE THAT WOULD HAVE SHIPPED BROKEN
# ═══════════════════════════════════════════════════════════════════════════


class TestTwoPdfsOnOneRequest:
    def test_a_request_carries_a_licence_and_a_deed_and_a_site_plan(
        self, two_utilities, docs_dir
    ):
        """Three `application/pdf`s on ONE request, which is what an applicant
        for a new connection actually hands over.

        ⚠ Had this filed under the REQUEST, `uq_stored_documents_filed` would
        refuse the SECOND one — `(tenant, source_type, source_id, content_type)`
        with a NULL channel. The constraint is right and is not widened; the
        source is the attachment row.
        """
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            first = _attach(request, name="licence.pdf", doc_type="proof_of_identity",
                            payload=PDF + b"one")
            second = _attach(request, name="deed.pdf", doc_type="tenancy_agreement_or_deed",
                             payload=PDF + b"two")
            third = _attach(request, name="site-plan.pdf", doc_type="site_plan_or_unit_schedule",
                            payload=PDF + b"three")

            ids = {first["id"], second["id"], third["id"]}
            assert len(ids) == 3
            assert (
                models.ServiceRequestDocument.objects.filter(request=request).count() == 3
            )
            assert (
                StoredDocument.objects.filter(
                    tenant_id=alpha.id, source_type=SOURCE_SERVICE_REQUEST_DOCUMENT
                ).count()
                == 3
            )

    def test_the_trap_this_avoids_is_real_and_not_hypothetical(
        self, two_utilities, docs_dir
    ):
        """⚠ **PROVE THE CONSTRAINT ACTUALLY REFUSES**, rather than asserting
        that it would.

        The case above passes because the source is the attachment row. That is
        only meaningful if the OTHER choice really fails — otherwise it is a
        design note dressed as a test (hard-won law 7: what would make this
        pass wrongly?). So this files two artefacts of the same shape under ONE
        `source_id`, the way a request-scoped source would, and watches
        `uq_stored_documents_filed` refuse the second.

        ⚠ **THE SAVEPOINT IS HARD-WON LAW 14 AND IS NOT DECORATION.** On
        PostgreSQL the failed INSERT aborts the whole transaction, so without
        the nested `atomic()` every later query in this test — and in pytest's
        own rollback — raises `InFailedSqlTransaction`. **SQLite has no aborted
        state**, so the version without it passes the suite green and fails
        only on the database this product actually runs on.
        """
        from django.db import IntegrityError, transaction

        alpha, _ = two_utilities
        shared_source = uuid.uuid4()
        with tenant_context(alpha.id):
            common = dict(
                tenant_id=alpha.id,
                kind=KIND_SERVICE_REQUEST_DOCUMENT,
                source_type=SOURCE_SERVICE_REQUEST_DOCUMENT,
                source_id=shared_source,
                channel=None,
                content_type="application/pdf",
                storage_backend="filesystem",
                byte_length=len(PDF),
                stored_by_process="tests",
            )
            StoredDocument.objects.create(
                storage_key=f"t/{alpha.id}/2026/09/{uuid.uuid4()}",
                content_hash="a" * 64,
                display_name="first.pdf",
                **common,
            )
            with pytest.raises(IntegrityError):
                with transaction.atomic():  # ⚠ THE SAVEPOINT — law 14.
                    StoredDocument.objects.create(
                        storage_key=f"t/{alpha.id}/2026/09/{uuid.uuid4()}",
                        content_hash="b" * 64,
                        display_name="second.pdf",
                        **common,
                    )
            # And the transaction is still usable, which is the half law 14 is
            # actually about.
            assert StoredDocument.objects.filter(source_id=shared_source).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# §3 · THE BYTES COME BACK — the check that cannot pass on an empty reference
# ═══════════════════════════════════════════════════════════════════════════


class TestTheBytesComeBack:
    def test_a_pdf_reads_back_byte_for_byte(self, two_utilities, docs_dir):
        """⚠ **THE CENTRAL CASE.** Store a file, read it back through the store,
        compare it with what went in. A row whose `storage_ref` points at
        nothing fails here and passes every other assertion in this file."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=PDF)
            got = doc_files.fetch_bytes(request.pk, filed["id"])
            assert got == PDF, "what came out of the store is not what went in"

    def test_a_download_link_is_minted_for_a_filed_document(self, two_utilities, docs_dir):
        """`download_url()` wired, tenant-scoped, with its four-hour life
        stated beside it."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request)
            link = doc_files.document_link(request.pk, filed["id"])
            assert link["url"]
            assert link["expires_in_seconds"] == 4 * 60 * 60

    def test_a_tick_with_no_file_is_not_a_404(self, two_utilities, docs_dir):
        """The row is really there and the clerk is looking at it. Saying "not
        found" would send them hunting for a row they can see."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            tick = models.ServiceRequestDocument.objects.create(
                tenant=alpha, request=request, doc_type="other"
            )
            with pytest.raises(errors.BizError) as refusal:
                doc_files.document_link(request.pk, tick.pk)
            assert refusal.value.code == errors.BIZ_COMPLETENESS

    def test_a_seeded_placeholder_reference_is_answered_and_does_not_crash(
        self, two_utilities, docs_dir
    ):
        """⚠ **A REFERENCE TO NOTHING — AND IT IS LIVE DATA, NOT A HYPOTHETICAL
        (`DEF-CUS-5872`).**

        Measured on the beta cluster on 2026-09-19: **all six**
        `service_request_documents` rows carry a `storage_ref` shaped like
        `sample-data://cr030/osei-move-in/tenancy-agreement.pdf`, **none of the
        six resolves to any `stored_documents` row**, every `size` is NULL, and
        **four of them read `verified`** — a clerk having certified a file that
        does not exist. They are seeded sample rows.

        Without the guard, `download_url` reaches `UUID('sample-data://…')` and
        raises `ValueError`, which arrives at a clerk as *"Something went wrong
        on our side"* on a row the screen is showing them. It is answered as
        what it is instead.

        ⚠ **THIS IS WHY THE CENTRAL CASE READS THE BYTES BACK.** Every check
        that only asks *"is `storage_ref` set?"* passes on all six of these.
        """
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            seeded = models.ServiceRequestDocument.objects.create(
                tenant=alpha,
                request=request,
                doc_type="proof_of_identity",
                name="drivers-licence.jpg",
                storage_ref="sample-data://cr030/osei-move-in/drivers-licence.jpg",
                verification_state=models.ServiceRequestDocument.VERIFIED,
            )
            with pytest.raises(errors.BizError) as refusal:
                doc_files.document_link(request.pk, seeded.pk)
            assert refusal.value.code == errors.BIZ_COMPLETENESS
            with pytest.raises(errors.BizError):
                doc_files.fetch_bytes(request.pk, seeded.pk)

    def test_a_placeholder_row_can_still_be_given_a_real_file(
        self, two_utilities, docs_dir
    ):
        """And the seeded rows are not stranded: a placeholder holds no bytes,
        so attaching to it is not "replacing" a filed document and is allowed.
        The write-once refusal is about real artefacts only."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            seeded = models.ServiceRequestDocument.objects.create(
                tenant=alpha, request=request, doc_type="proof_of_identity",
                storage_ref="sample-data://cr030/osei-move-in/drivers-licence.jpg",
            )
            filed = _attach(request, document_id=str(seeded.pk))
            assert filed["id"] == str(seeded.pk)
            assert doc_files.fetch_bytes(request.pk, filed["id"]) == PDF


# ═══════════════════════════════════════════════════════════════════════════
# §4 · REDUCE ON THE WAY IN — and NEVER degrade what a human must read
# ═══════════════════════════════════════════════════════════════════════════


class TestReduction:
    def test_a_pdf_is_never_touched(self, two_utilities, docs_dir):
        """A deed, a signed agreement, a site plan as PDF: byte for byte, and
        `original_size` stays NULL because nothing was done to it."""
        alpha, _ = two_utilities
        big_pdf = b"%PDF-1.7\n" + b"E" * (300 * 1024) + b"\n%%EOF"
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=big_pdf)
            assert doc_files.fetch_bytes(request.pk, filed["id"]) == big_pdf
            assert filed["size_bytes"] == len(big_pdf)
            assert filed["original_size_bytes"] is None, (
                "a PDF that was never touched must not claim to have been shrunk"
            )

    def test_an_oversized_png_is_reduced_and_not_one_pixel_moves(
        self, two_utilities, docs_dir
    ):
        """⚠ **THE WHOLE COMPRESSION ARGUMENT IN ONE CASE.** The file gets
        smaller AND the image a reader decodes is bit-identical."""
        alpha, _ = two_utilities
        original = _png(level=1)
        assert len(original) > document_shrink.MIN_REDUCIBLE_BYTES
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=original, name="site-plan.png",
                            content_type="image/png", doc_type="site_plan_or_unit_schedule")

            stored = doc_files.fetch_bytes(request.pk, filed["id"])
            assert len(stored) < len(original), "nothing was saved"
            # THE CHECK THAT MATTERS: the pixels, not the bytes.
            assert _pixels(stored) == _pixels(original), "the image changed — this is the harm"
            # And the scan is still declared 300 dpi: non-IDAT chunks survive.
            assert b"pHYs" in stored

    def test_both_sizes_are_recorded_when_a_file_is_reduced(self, two_utilities, docs_dir):
        """*"A clerk who is told a file is 3.1 MB and finds 400 KB on disk needs
        the record to say why."*"""
        alpha, _ = two_utilities
        original = _png(level=1)
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=original, name="plan.png",
                            content_type="image/png", doc_type="site_plan_or_unit_schedule")
            assert filed["original_size_bytes"] == len(original)
            assert filed["size_bytes"] < filed["original_size_bytes"]
            row = models.ServiceRequestDocument.objects.get(pk=filed["id"])
            assert row.original_size == len(original) and row.size == len(
                doc_files.fetch_bytes(request.pk, filed["id"])
            )

    def test_an_already_small_file_is_left_alone(self, two_utilities, docs_dir):
        """Below the floor nothing is attempted. The only thing a reduction
        could do to a 20 KB scan is go wrong."""
        alpha, _ = two_utilities
        small = _png(width=40, height=40, level=1)
        assert len(small) < document_shrink.MIN_REDUCIBLE_BYTES
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=small, name="stamp.png",
                            content_type="image/png", doc_type="other")
            assert filed["original_size_bytes"] is None
            assert doc_files.fetch_bytes(request.pk, filed["id"]) == small

    def test_a_file_the_reducer_cannot_parse_is_stored_unchanged(self):
        """An upload we cannot read is STORED AS IT ARRIVED — never refused and
        never half-rewritten. Pure bytes, no database: hard-won law 14 does not
        reach this and the module docstring says why."""
        rubbish = b"\x89PNG\r\n\x1a\n" + b"not really a png" * 8000
        out = document_shrink.reduce_on_the_way_in(rubbish, "image/png")
        assert out.payload == rubbish and out.method is None

    def test_a_reduction_is_never_bigger_than_what_arrived(self):
        """An already-optimal PNG comes back untouched rather than re-wrapped."""
        tight = _png(width=300, height=300, level=9)
        out = document_shrink.reduce_on_the_way_in(tight, "image/png")
        assert out.stored_bytes <= out.original_bytes
        assert _pixels(out.payload) == _pixels(tight)


# ═══════════════════════════════════════════════════════════════════════════
# §5 · THE GUARDS — `BR-SHL-031`, quoted rather than chosen
# ═══════════════════════════════════════════════════════════════════════════


class TestGuards:
    def test_a_file_outside_the_allowlist_is_a_415(self, two_utilities, docs_dir):
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            with pytest.raises(doc_files.UploadRefused) as refusal:
                _attach(request, payload=b"MZ" + b"x" * 500, name="thing.exe",
                        content_type="application/x-msdownload")
            assert refusal.value.status == 415

    def test_a_file_over_the_cap_is_a_413(self, two_utilities, docs_dir):
        """⚠ **MEASURED ON WHAT ARRIVED, NOT ON WHAT WE WOULD STORE.** Letting a
        40 MB file through because it would compress under 10 MB would defeat
        the guard."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            oversized = b"%PDF-1.7\n" + b"F" * (doc_files.MAX_UPLOAD_BYTES + 1)
            with pytest.raises(doc_files.UploadRefused) as refusal:
                _attach(request, payload=oversized)
            assert refusal.value.status == 413

    def test_an_empty_file_is_refused(self, two_utilities, docs_dir):
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            with pytest.raises(errors.ValidationError):
                _attach(request, payload=b"")

    def test_a_doc_type_outside_the_vocabulary_is_refused(self, two_utilities, docs_dir):
        """`BR-CUS-095` — a tick can only be satisfied if the thing attached
        carries the same name as the thing ticked."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            with pytest.raises(errors.ValidationError):
                _attach(request, doc_type="photo_id")

    def test_the_media_type_is_compared_without_its_parameters(
        self, two_utilities, docs_dir
    ):
        """`image/jpeg; charset=binary` is a legal header. A browser that adds a
        parameter must not get a 415 for a file that is on the list."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request, payload=b"\xff\xd8\xff\xd9" * 50, name="scan.jpg",
                            content_type="image/jpeg; charset=binary", doc_type="other")
            assert filed["attached"] is True


# ═══════════════════════════════════════════════════════════════════════════
# §6 · TENANT SCOPING — existence must not leak (CLAUDE.md hard rule 1, HR-1)
# ═══════════════════════════════════════════════════════════════════════════


class TestAnotherUtilityCannotReachIt:
    def test_another_utility_gets_a_404_not_a_403(self, two_utilities, docs_dir):
        """⚠ **THE SAME ANSWER AS FOR A REQUEST THAT NEVER EXISTED.** A 403
        would confirm it is there."""
        alpha, beta = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
            filed = _attach(request)
        with tenant_context(beta.id):
            with pytest.raises(errors.NotFoundError):
                doc_files.document_link(request.pk, filed["id"])
            with pytest.raises(errors.NotFoundError):
                doc_files.fetch_bytes(request.pk, filed["id"])

    def test_another_utility_cannot_attach_to_it_either(self, two_utilities, docs_dir):
        alpha, beta = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
        with tenant_context(beta.id):
            with pytest.raises(errors.NotFoundError):
                _attach(request)

    def test_no_tenant_context_at_all_is_refused(self, two_utilities, docs_dir):
        """CLAUDE.md hard rule 1 — never touch a tenant table without
        `app.tenant_id`."""
        alpha, _ = two_utilities
        with tenant_context(alpha.id):
            request = _request(alpha)
        with pytest.raises(errors.AuthError):
            _attach(request)
