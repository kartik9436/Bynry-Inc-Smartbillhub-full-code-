# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1 — the document store. Three PO rulings, 2026-08-30:
#           cloud storage; a four-hour link; AWS first but multi-cloud by
#           design.
# Rules:    BR-NOT-027 (a legal document is frozen AS THE DOCUMENT when it is
#           sent — never re-rendered from data) · NFR-33 (STORED ARTIFACTS) ·
#           NFR-35 (write-once immutable object lock, 7-year retention) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE) · rule 4 (financial
#           immutability) · rule 7 (audit) · HR-1 (existence must not leak) ·
#           hard-won law 3 (defaults fail closed) · law 7 (prove a guard RED
#           before trusting it green)
# ───────────────────────────────────────────────────────
"""Every guarantee the document store claims, asserted — and each proved RED.

⚠ **HARD-WON LAW 7: EVERY GUARD BELOW WAS SHOWN FAILING BEFORE IT WAS TRUSTED.**
The transcripts are quoted in the docstring of the case they belong to, against
live PostgreSQL 16, verbatim. They are here rather than only in the lane report
because a lane report is read once and this file is read whenever somebody
doubts one of these guarantees.

WHAT RUNS WHERE, AND WHY IT IS SPLIT
-------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite, which has **no RLS and no
triggers**. So the database half of every guarantee carries
`requires_postgres` and runs only against a live cluster:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL="postgres://…/sbh_cr049_docs" \\
    python -m pytest tests/test_cr049_t1_document_store.py --reuse-db -q

and the service half runs everywhere, because a guarantee that is only checked
on a database no developer runs is a guarantee nobody meets before merge.

**NOTHING WRITES INTO THIS STORE IN THE PRODUCT YET** — that is `CR-049` task 2
and another lane's — so every case here is the store exercised directly. That
is the honest position and not a gap: task 1 is the store, its guarantees and
the proof they hold.
"""

import datetime as dt
import uuid

import pytest
from django.db import DatabaseError, connection, transaction
from django.test import override_settings

from apps.tenancy import document_storage, document_store
from apps.tenancy.document_models import StoredDocument, StoredDocumentImmutable
from core.tenancy import tenant_context

from tests.isolation_helpers import (  # noqa: F401 — fixtures
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)

PDF = b"%PDF-1.7\nthe 48-hour disconnection notice as it was posted\n%%EOF"
NAME = "notices/2026/08/ACC-1042-48HR.pdf"


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """`set_config` on sqlite, and the REAL GUC on PostgreSQL.

    `core.tenancy.tenant_context` issues `SELECT set_config('app.tenant_id',…)`,
    which sqlite does not have. The unit tier's established answer is to swap
    the connection for a recorder (`tests/test_us_ten_helpers.sqlite_guc`); the
    ContextVar mirror stays real, so `current_tenant_id()` still answers and the
    app-layer scoping this file asserts is genuinely exercised.

    ⚠ **ON POSTGRES NOTHING IS SWAPPED**, because the whole point of the
    `requires_postgres` cases is that the SHIPPING kernel sets the GUC the
    policy reads. Faking it there would make every isolation assertion vacuous.
    """
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
def tenants(db):
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Silver Creek Water", subdomain=f"silver{suffix}")
    beta = Tenant.objects.create(name="Brazos Utility", subdomain=f"brazos{suffix}")
    return alpha, beta


def _store(**overrides):
    kwargs = dict(
        kind="disconnect_notice",
        source_type="outbound_message",
        source_id=uuid.uuid4(),
        channel="pdf_print",
        content_type="application/pdf",
        display_name=NAME,
        payload=PDF,
        process="notifications.dispatcher",
    )
    kwargs.update(overrides)
    return document_store.store(**kwargs)


class RecordingS3Client:
    """An S3 client that records what it was asked and honours an expiry.

    ⚠ **THIS PROVES THE REQUEST, NOT AWS.** It asserts the key layout, the
    checksum, the encryption mode, the object-lock parameters and the URL TTL
    this code sends. It does not prove that a real bucket accepts them, and
    `boto3` is not installed in the environment this was written in — stated
    in `document_storage`'s own docstring and in the lane report rather than
    implied by a green test.
    """

    def __init__(self):
        self.puts = []
        self.urls = []
        self.objects = {}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, *, Bucket, Key):  # noqa: N803 — boto3's own spelling
        if Key not in self.objects:
            raise KeyError(f"NoSuchKey: {Key}")

        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

        return {"Body": _Body(self.objects[Key])}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):  # noqa: N803
        issued = dt.datetime.now(dt.timezone.utc)
        self.urls.append({"params": Params, "expires_in": ExpiresIn, "issued": issued})
        expiry = int((issued + dt.timedelta(seconds=ExpiresIn)).timestamp())
        return f"https://bucket.example/{Params['Key']}?X-Amz-Expires={ExpiresIn}&exp={expiry}"

    def fetch(self, url, *, at):
        """What an object store does with an expired signature: refuses it."""
        expiry = int(url.rsplit("exp=", 1)[1])
        if at.timestamp() > expiry:
            raise PermissionError("AccessDenied: Request has expired")
        return self.objects[url.split("?")[0].split("/", 3)[3]]


@pytest.fixture()
def aws(settings):
    """The AWS adapter over a recording client."""
    client = RecordingS3Client()
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    settings.DOCUMENT_STORAGE_BUCKET = "silver-creek-documents"
    settings.DOCUMENT_STORAGE_REGION = "us-east-2"
    settings.DOCUMENT_STORAGE_SSE = "AES256"
    document_storage.set_s3_client_factory(lambda: client)
    yield client
    document_storage.set_s3_client_factory(None)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 1 · AN UPDATE IS REFUSED AT THE DATABASE
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_cr049_t1_tc1__update_refused_by_the_database(tenants, docs_dir):
    """The trigger refuses every UPDATE of a stored document.

    **PROVED RED FIRST (law 7).** The same statement, on live PostgreSQL, with
    `stored_documents_write_once` dropped:

        ### RED PROOF 1 — the same UPDATE and DELETE with the trigger DROPPED
        DROP TRIGGER
        UPDATE 1
         hash_after_update
        -------------------
         tampered

    The content hash of a frozen legal document was rewritten and PostgreSQL
    said `UPDATE 1`. With the trigger in place the identical statement gives:

        ERROR:  BR-NOT-027 / NFR-35: stored document
        22222222-2222-4222-8222-222222222222 (disconnect_notice) cannot be
        updated. What the customer read is frozen at the moment it was stored;
        amending or re-rendering it is the exact thing the freeze exists to
        prevent, and a correction is a NEW row.
        CONTEXT:  PL/pgSQL function tenancy_stored_document_write_once() line 7
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        # `QuerySet.update()` bypasses the model's own `save()` guard — which is
        # exactly why the trigger has to exist. This asserts the DATABASE.
        #
        # ⚠ THE SAVEPOINT IS NOT TIDINESS — IT IS HARD-WON LAW 14, AND THIS
        # CASE MET IT. Without the nested `atomic()`, the trigger's refusal
        # aborts the whole PostgreSQL transaction, and the very next statement
        # — `tenant_context`'s own `set_config` on the way out — dies with
        # `django.db.transaction.TransactionManagementError: An error occurred
        # in the current transaction. You can't execute queries until the end
        # of the 'atomic' block.` The case then fails while the guard it is
        # testing is working perfectly. `isolation_helpers.RlsProbe.refused`
        # takes the same precaution for the same reason.
        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic():
                StoredDocument.objects.filter(id=ref.id).update(content_hash="tampered")
    assert "cannot be updated" in str(caught.value)
    assert "BR-NOT-027" in str(caught.value)


@pytest.mark.isolation
@requires_postgres
def test_cr049_t1_tc2__delete_refused_by_the_database(tenants, docs_dir):
    """The trigger refuses every DELETE of a stored document.

    **PROVED RED FIRST.** With the trigger dropped, on live PostgreSQL:

        DELETE 1
         rows_after_delete
        -------------------
                         0

    The evidence a regulator would ask for was gone and nothing objected. With
    the trigger:

        ERROR:  BR-NOT-027 / NFR-35: stored document … cannot be deleted. It is
        the document a customer was sent, kept as evidence for seven years;
        there is no lawful edit and no lawful deletion, and a document that
        changed is a NEW row.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        # The savepoint is law 14 again — see tc1.
        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic():
                StoredDocument.objects.filter(id=ref.id).delete()
    assert "cannot be deleted" in str(caught.value)


def test_cr049_t1_tc3__update_and_delete_refused_in_python_on_every_vendor(tenants, docs_dir):
    """The same two refusals without a database that can hold them.

    SQLite has no triggers and `config/settings/test.py` hardcodes it, so the
    two cases above are skipped on the run a developer actually does. These
    are the ones that are not — and they are honestly weaker: `QuerySet.
    update()` and `QuerySet.delete()` walk straight past them, which is stated
    on the model rather than left to be discovered.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        row = StoredDocument.objects.get(id=ref.id)

        row.content_hash = "tampered"
        with pytest.raises(StoredDocumentImmutable) as on_save:
            row.save()
        assert "cannot be updated" in str(on_save.value)

        with pytest.raises(StoredDocumentImmutable) as on_delete:
            row.delete()
        assert "cannot be deleted" in str(on_delete.value)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 2 · ANOTHER TENANT CANNOT READ A STORED DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_cr049_t1_tc4__another_tenant_cannot_read_the_row(tenants, docs_dir, rls):  # noqa: F811
    """The DATABASE refuses, under a role RLS actually applies to.

    Asserted through `sbh_rls_probe` — NOLOGIN NOSUPERUSER NOBYPASSRLS —
    because a superuser bypasses RLS unconditionally and every assertion made
    on the app role would pass without the policy existing.

    **PROVED RED FIRST, AND THE FIRST SABOTAGE WAS THE WRONG ONE, WHICH IS
    WORTH KEEPING.** Dropping the POLICY proved nothing: with RLS still
    ENABLE + FORCE and no policy, PostgreSQL denies every row, so the table
    failed CLOSED and the probe saw 0. **The guard is `ENABLE + FORCE`, not the
    policy alone** — so the sabotage that matters is a table that never had RLS
    turned on. With `ALTER TABLE stored_documents DISABLE ROW LEVEL SECURITY`:

              who      | rows_tenant_b_can_see |           and_its_name            |  and_its_key
        ---------------+-----------------------+-----------------------------------+--------------
         sbh_rls_probe |                     1 | notices/2026/08/ACC-1042-48HR.pdf | t/1111…/2026/08/2222…

    ⚠ **READ THE LAST COLUMN.** The leak is not only the document's name: it is
    the STORAGE KEY, which is the one thing that turns "a prefix is not
    isolation" from a design note into a read of another utility's bytes. With
    ENABLE + FORCE restored the same query returns 0.
    """
    alpha, beta = tenants
    with tenant_context(alpha.id):
        ref = _store()

    with live_tenant_context(beta.id):
        assert (
            rls.count("stored_documents") == 0
        ), "LEAK — a second tenant can see stored_documents rows through the database"
    with live_tenant_context(alpha.id):
        assert (
            rls.count("stored_documents", "id = %s", [str(ref.id)]) == 1
        ), "the owning tenant cannot see its own document — the fixture proves nothing"
    # Deny-by-default: no context sees nothing (DEF-639's NULLIF predicate).
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id','',false)")
    assert rls.count("stored_documents") == 0


@pytest.mark.isolation
@requires_postgres
def test_cr049_t1_tc5__tenant_b_gets_the_same_answer_as_for_nothing_at_all(tenants, docs_dir):
    """HR-1 — existence must not leak.

    A caller in tenant B asking for tenant A's document, and the same caller
    asking about a source that never existed, must be **indistinguishable**.
    They are, and not because this module remembers to make them so: the read
    is an RLS-scoped query, so tenant A's row is not in the set the answer is
    computed from.
    """
    alpha, beta = tenants
    with tenant_context(alpha.id):
        ref = _store()
        mine = document_store.for_source(source_type="outbound_message", source_id=ref.source_id)
        assert mine.found and mine.document.display_name == NAME

    with tenant_context(beta.id):
        theirs = document_store.for_source(source_type="outbound_message", source_id=ref.source_id)
        fictional = document_store.for_source(
            source_type="outbound_message", source_id=uuid.uuid4()
        )

    assert theirs == fictional, (
        "tenant B's answer for tenant A's document differs from its answer for a "
        "document that never existed — that difference IS the existence leak"
    )
    assert theirs.unavailable_reason == document_store.DOCUMENT_NOT_STORED
    assert theirs.document is None


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 3 · THE HASH
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc6__same_bytes_same_hash_changed_byte_changed_hash():
    """Decision 7's premise, before anything relies on it."""
    once = document_storage.content_hash(PDF)
    twice = document_storage.content_hash(bytes(PDF))
    assert once == twice
    assert len(once) == 64 and once == once.lower()

    tampered = PDF.replace(b"48-hour", b"96-hour")
    assert len(tampered) == len(PDF), "the fixture must change a byte, not the length"
    assert document_storage.content_hash(tampered) != once


def test_cr049_t1_tc7__a_changed_byte_is_refused_on_read(tenants, docs_dir):
    """A silent byte change is what the freeze exists to prevent.

    **PROVED RED FIRST.** With the comparison in `fetch()` removed, the
    tampered bytes were returned with no error at all and `fetch()` answered
    with a 96-hour notice where a 48-hour notice had been frozen — a document
    the utility would have handed a regulator as the one it served. With the
    comparison, the same read raises `ContentHashMismatch`.

    The tamper is done ON THE STORE, behind the store's back, which is the real
    threat model: nothing in this product can rewrite those bytes, and the
    check exists for everything that is not this product.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        assert document_store.fetch(ref.id) == PDF

        row = StoredDocument.objects.get(id=ref.id)
        target = docs_dir / row.storage_key
        target.write_bytes(PDF.replace(b"48-hour", b"96-hour"))

        with pytest.raises(document_storage.ContentHashMismatch) as caught:
            document_store.fetch(ref.id)
    assert "are NOT the bytes that were frozen" in str(caught.value)
    assert ref.content_hash in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 4 · "NONE STORED" IS AN ANSWER, NOT AN EMPTY SUCCESS
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc8__no_artefact_answers_none_stored(tenants, docs_dir):
    """A source with no frozen document says so, rather than raising or
    returning something that looks like success.

    **PROVED RED FIRST** in the shape that matters: an earlier draft returned
    `StoredDocumentRef | None`, and a caller doing `if not doc: render()` would
    have been silently correct — which is exactly how a fresh render gets
    served as the original. The wrapper makes that impossible to write by
    accident: there is no falsy document without a reason beside it.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        answer = document_store.for_source(source_type="invoice", source_id=uuid.uuid4())
    assert answer.found is False
    assert answer.document is None
    assert answer.unavailable_reason == document_store.DOCUMENT_NOT_STORED


def test_cr049_t1_tc9__a_removed_object_is_not_the_same_as_no_document(tenants, docs_dir):
    """The row is there and the bytes are gone — a different, worse condition.

    Collapsing it into "none stored" would let a document this product LOST
    read as one it never produced, which is a far worse thing to hide.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        row = StoredDocument.objects.get(id=ref.id)
        (docs_dir / row.storage_key).unlink()

        # The lookup still finds the RECORD — the document was produced.
        assert document_store.for_source(
            source_type="outbound_message", source_id=ref.source_id
        ).found
        # And the bytes say plainly that they are gone.
        with pytest.raises(document_storage.StoredObjectMissing) as caught:
            document_store.fetch(ref.id)
    assert "which is not the same as no document having been stored" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 5 · A MISSING BUCKET REFUSES RATHER THAN FALLING BACK TO DISK
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc10__no_bucket_refuses_and_does_not_fall_back(settings):
    """Hard-won law 3, at the point it would actually cost something.

    **PROVED RED FIRST, AND THE FIRST DRAFT REALLY DID THIS.** Before the
    refusal was written, `backend()` with no bucket configured returned a
    `FilesystemStorage` pointed at a default directory — so a production
    deployment would have written seven years of legal documents to a
    container's scratch space and reported success every time. The transcript
    was one line: `backend() -> FilesystemStorage(...)`.
    """
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_BUCKET = ""
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True  # even so
    settings.DOCUMENT_STORAGE_DIR = "/tmp/whatever"

    with pytest.raises(document_storage.StorageNotConfigured) as caught:
        document_storage.backend()
    message = str(caught.value)
    assert "DOCUMENT_STORAGE_BUCKET is not set" in message
    assert "does NOT fall back to local disk" in message


def test_cr049_t1_tc11__local_disk_needs_two_settings_not_one(settings):
    """The unsafe option is the one somebody has to type — twice."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_DIR = "/tmp/documents"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False

    with pytest.raises(document_storage.StorageNotConfigured) as caught:
        document_storage.backend()
    assert "does not allow it" in str(caught.value)

    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    assert document_storage.backend().name == "filesystem"


@override_settings(
    DOCUMENT_STORAGE_BACKEND="aws_s3",
    DOCUMENT_STORAGE_BUCKET="silver-creek-documents",
    DOCUMENT_STORAGE_SSE="",
)
def test_cr049_t1_tc12__empty_encryption_is_refused_not_obeyed():
    """Emptying the encryption setting would write customer documents in clear."""
    with pytest.raises(document_storage.StorageNotConfigured) as caught:
        document_storage.backend()
    assert "unencrypted" in str(caught.value)


def test_cr049_t1_tc13__base_settings_are_the_ones_that_fail_closed():
    """The DEFAULTS, read from `config.settings.base` rather than asserted about.

    Law 1: a docstring saying the defaults fail closed is not the defaults
    failing closed. This reads the module the deployment actually loads.
    """
    import importlib

    base = importlib.import_module("config.settings.base")
    assert base.DOCUMENT_STORAGE_BACKEND == "aws_s3"
    assert base.DOCUMENT_STORAGE_ALLOW_FILESYSTEM is False
    assert base.DOCUMENT_STORAGE_BUCKET == ""
    assert base.DOCUMENT_STORAGE_SSE == "AES256"
    assert base.DOCUMENT_STORAGE_RETENTION_YEARS == 7


def test_cr049_t1_tc14__an_unknown_cloud_is_refused_by_name(settings):
    """A second cloud is an adapter and a migration, never a settings change."""
    settings.DOCUMENT_STORAGE_BACKEND = "gcs"
    with pytest.raises(document_storage.StorageNotConfigured) as caught:
        document_storage.backend()
    assert "a new adapter" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 6 · THE TEMPORARY URL EXPIRES
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc15__the_link_lives_four_hours_and_then_does_not(tenants, aws):
    """PO ruling 2026-08-30 — *"dont expire it in minutes - exprise it in 3 or
    4 hours"* — and the expiry itself.

    **PROVED RED FIRST**: with the `ExpiresIn` argument dropped from the call,
    the recording client issued a URL with no expiry at all and the simulated
    fetch five hours later succeeded — a permanent link to a customer's
    disconnection notice. With it, the same fetch raises
    `AccessDenied: Request has expired`.

    ⚠ **WHAT THIS DOES AND DOES NOT PROVE.** It proves the TTL this code asks
    for and that a store honouring that TTL refuses afterwards. It does not
    prove AWS's implementation of signature expiry — `boto3` is not installed
    in this environment, and that is stated rather than implied.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        url = document_store.download_url(ref.id)

    assert aws.urls[-1]["expires_in"] == 4 * 60 * 60, "the PO ruled hours, not minutes"
    issued = aws.urls[-1]["issued"]

    assert aws.fetch(url, at=issued + dt.timedelta(hours=3, minutes=59)) == PDF
    with pytest.raises(PermissionError) as caught:
        aws.fetch(url, at=issued + dt.timedelta(hours=4, seconds=1))
    assert "expired" in str(caught.value)


@override_settings(DOCUMENT_STORAGE_URL_TTL_SECONDS=86400)
def test_cr049_t1_tc16__a_longer_ttl_is_refused_rather_than_clamped():
    """The setting shortens a link's life and cannot lengthen it.

    Refused rather than silently clamped, because an operator debugging a link
    that expires sooner than the number they typed is a worse afternoon than
    one reading an error that names both numbers.
    """
    with pytest.raises(document_storage.StorageNotConfigured) as caught:
        document_storage.url_ttl_seconds()
    assert "86400" in str(caught.value) and "14400" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# THE AWS ADAPTER — the request it makes
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc17__the_key_is_tenant_first_and_dated(tenants, aws):
    """Decision 3, AS AMENDED 2026-10-02 BY `CR-160-BRC10`:
    `t/<utility web name>/<module>/<yyyy>/<mm>/<document_id>[.ext]`.

    It read `t/<tenant_id>/<yyyy>/<mm>/<document_id>` until then. Utility first
    so a prefix is a utility; dated so a lifecycle rule moves cold objects
    **without reading the database** — which is the difference between about $8
    a month and about $27 for a hundred utilities' seven-year archive. The full
    layout is asserted per module in `tests/test_cr160_storage_key_layout.py`.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
    key = aws.puts[-1]["Key"]
    now = dt.datetime.now(dt.timezone.utc)
    # A disconnect notice is a collections letter: the payments module's folder.
    assert key == f"t/{alpha.subdomain}/payments/{now:%Y}/{now:%m}/{ref.id}.pdf"


def test_cr049_t1_tc18__encryption_checksum_and_a_seven_year_lock(tenants, aws, settings):
    """Decisions 6 and 7, as parameters on the wire — WHEN THE LOCK IS TYPED.

    ⚠ `CR-160-BRC10` (2026-10-02) made NONE the default, so this case now types
    COMPLIANCE to prove the switch still works; the no-lock default is
    asserted in `test_cr160_storage_key_layout.py`.

    ⚠ The retain-until date proves what this code ASKS FOR. **The lock itself
    is a bucket setting AWS can only accept at bucket creation**, so no test in
    this repo can assert it — that is on the deployment checklist in
    `document_storage`'s docstring, stated rather than claimed (law 1).
    """
    import base64

    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "COMPLIANCE"
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store()
    sent = aws.puts[-1]
    assert sent["ServerSideEncryption"] == "AES256"
    assert sent["ObjectLockMode"] == "COMPLIANCE"
    expected = base64.b64encode(bytes.fromhex(document_storage.content_hash(PDF))).decode()
    assert sent["ChecksumSHA256"] == expected
    years = sent["ObjectLockRetainUntilDate"].year - dt.datetime.now(dt.timezone.utc).year
    assert years == 7, "NFR-35 is seven years"


def test_cr049_t1_tc19__a_row_written_on_one_backend_is_not_fetched_from_another(
    tenants, aws, settings, tmp_path
):
    """Switching clouds does not move the objects, and the row says so."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        assert ref.storage_backend == "aws_s3"

        settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
        settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
        settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "elsewhere")
        with pytest.raises(document_store.DocumentStoreError) as caught:
            document_store.fetch(ref.id)
    assert "does not move them" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE PATH'S OWN REFUSALS
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc20__a_document_needs_a_human_name(tenants, docs_dir):
    """An export of 532,000 files named after their UUIDs is not an export."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        with pytest.raises(document_store.DocumentStoreError) as caught:
            _store(display_name="   ")
        assert "needs a display_name" in str(caught.value)

        for bad in ("/etc/passwd", "../../escape.pdf", "a" * 256):
            with pytest.raises(document_store.DocumentStoreError):
                _store(display_name=bad)


def test_cr049_t1_tc21__a_document_needs_an_author_and_real_bytes(tenants, docs_dir):
    """ "Nobody knows" is not an answer a legal document may give."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        with pytest.raises(document_store.DocumentStoreError) as no_author:
            _store(process=None)
        assert "needs an author" in str(no_author.value)

        with pytest.raises(document_store.DocumentStoreError) as empty:
            _store(payload=b"")
        assert "empty document" in str(empty.value)


def test_cr049_t1_tc22__an_unruled_kind_is_refused(tenants, docs_dir):
    """A kind nobody has ruled on is how a store becomes a junk drawer."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        with pytest.raises(document_store.DocumentStoreError) as caught:
            _store(kind="marketing_leaflet")
        assert "junk drawer" in str(caught.value)


def test_cr049_t1_tc23__no_tenant_context_refuses_before_the_database_does(docs_dir, db):
    """Hard rule 1, with a sentence that says why rather than a psycopg error."""
    with pytest.raises(document_store.DocumentStoreError) as caught:
        _store()
    assert "no tenant context is set" in str(caught.value)


def test_cr049_t1_tc24__the_bytes_are_written_before_the_row(tenants, docs_dir, monkeypatch):
    """A failed upload must leave NO row — because a row can never be removed.

    This is the argument in `document_store`'s docstring, asserted: with the
    upload failing, the store must have written nothing at all. Written the
    other way round, this product would carry a permanent record of a document
    that does not exist, and every reprint of it would answer *"stored"* and
    then fail to produce anything.
    """
    alpha, _ = tenants

    def boom(_self, **_kwargs):
        raise OSError("the object store was unreachable")

    with tenant_context(alpha.id):
        before = StoredDocument.objects.count()
        monkeypatch.setattr(document_storage.FilesystemStorage, "put", boom)
        with pytest.raises(OSError):
            _store()
        assert StoredDocument.objects.count() == before


# ═══════════════════════════════════════════════════════════════════════════
# ENUMERATION IS A DATABASE QUERY
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc25__the_seam_offers_no_way_to_list_a_bucket(docs_dir):
    """There is no `list()` and no `delete()`, and both absences are the design.

    A `list()` would be reached for the day somebody builds the bulk export,
    and it is the day the export starts crossing tenants: a bucket listing is
    scoped by a prefix, which is a string. A `delete()` would be a door onto a
    room `NFR-35` locks.
    """
    backend = document_storage.backend()
    for forbidden in ("list", "list_objects", "delete", "delete_object", "remove"):
        assert not hasattr(backend, forbidden), (
            f"{forbidden}() exists on the storage seam — enumeration is always a "
            "database query and deletion is refused by NFR-35"
        )


def test_cr049_t1_tc26__the_manifest_is_scoped_and_newest_first(tenants, docs_dir):
    """The bulk export's enumeration: this tenant's documents, newest first.

    Not the export — that is another task and another lane's. This is the read
    the export will use, and it is a database query over
    `(tenant, stored_at)`. Half a million rows unindexed is where the 4.4 hours
    come back.
    """
    alpha, beta = tenants
    with tenant_context(alpha.id):
        first = _store(display_name="notices/2026/08/one.pdf")
        second = _store(kind="bill", source_type="invoice", display_name="bills/2026/08/two.pdf")
    with tenant_context(beta.id):
        _store(display_name="notices/2026/08/theirs.pdf")

    with tenant_context(alpha.id):
        rows = document_store.manifest()
        assert [r.id for r in rows] == [second.id, first.id]
        assert {r.display_name for r in rows} == {
            "notices/2026/08/one.pdf",
            "bills/2026/08/two.pdf",
        }
        assert [r.id for r in document_store.list_for_kind(kind="bill")] == [second.id]

    with tenant_context(beta.id):
        assert len(document_store.manifest()) == 1, "the manifest crossed a tenant boundary"


def test_cr049_t1_tc27__a_caller_is_never_handed_a_storage_key(tenants, docs_dir):
    """A caller that could name a key could name one it composed.

    Decision 4 in one assertion: the published dataclass carries everything a
    screen needs and nothing that addresses the bucket.
    """
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
    assert not hasattr(ref, "storage_key")
    assert "storage_key" not in vars(ref)


def test_cr049_t1_tc28__a_key_this_store_did_not_compose_is_refused(docs_dir):
    """Path traversal is impossible rather than unlikely."""
    backend = document_storage.backend()
    for hostile in (
        "../../../etc/passwd",
        "t/../../etc/passwd",
        "",
        "t/not-a-uuid/2026/08/also-not-a-uuid",
    ):
        with pytest.raises(document_storage.DocumentStorageError):
            backend.get(key=hostile)


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUND TRIP, AND THE AUDIT ROW
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc29__store_then_fetch_returns_the_exact_bytes(tenants, docs_dir):
    """The whole point, in six lines."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store()
        assert ref.byte_length == len(PDF)
        assert ref.content_hash == document_storage.content_hash(PDF)
        assert ref.display_name == NAME
        assert document_store.fetch(ref.id) == PDF

        found = document_store.for_source(source_type="outbound_message", source_id=ref.source_id)
        assert found.found and found.document.id == ref.id
        assert found.unavailable_reason is None


def test_cr049_t1_tc30__freezing_a_document_writes_an_audit_row(tenants, docs_dir):
    """ "Who froze this, and when" is the question that follows "show me it"."""
    from core import audit as core_audit

    # ⚠ SAVE AND RESTORE, NEVER CLEAR. `apps.audit` registers the REAL sink at
    # AppConfig.ready, and handing back None instead of what was found silently
    # disarms every later test that writes an audit row — which is exactly what
    # the first draft of this case did, and tc31 went red on
    # `AuditWriteError: no audit sink registered`. `tests/test_us_ten_helpers`
    # states the same rule for the same reason.
    previous = core_audit._sink
    written = []
    core_audit.set_audit_sink(written.append)
    try:
        alpha, _ = tenants
        with tenant_context(alpha.id):
            ref = _store()
    finally:
        core_audit.set_audit_sink(previous)

    rows = [r for r in written if r["action"] == "document.stored"]
    assert len(rows) == 1
    assert rows[0]["entity_id"] == ref.id
    assert rows[0]["after"]["content_hash"] == ref.content_hash
    assert rows[0]["after"]["display_name"] == NAME


def test_cr049_t1_tc31__a_bill_stores_a_pdf_and_an_html_of_one_document(tenants, docs_dir):
    """Two representations of one thing, not two documents — which is why
    `content_type` is in the uniqueness key.

    `channel` is NULL on both: a bill frozen at issue was stored when it was
    CREATED, not when it was sent. That NULL is a fact, not an absence of
    knowledge.
    """
    alpha, _ = tenants
    invoice = uuid.uuid4()
    with tenant_context(alpha.id):
        pdf = _store(
            kind="bill",
            source_type="invoice",
            source_id=invoice,
            channel=None,
            content_type="application/pdf",
            display_name="bills/2026/08/ACC-1042-INV-000123.pdf",
            process="billing.issue",
        )
        html = _store(
            kind="bill",
            source_type="invoice",
            source_id=invoice,
            channel=None,
            content_type="text/html",
            display_name="bills/2026/08/ACC-1042-INV-000123.html",
            payload=b"<html>the bill as issued</html>",
            process="billing.issue",
        )
        assert pdf.id != html.id
        assert pdf.channel is None and html.channel is None
        narrowed = document_store.for_source(
            source_type="invoice", source_id=invoice, content_type="text/html"
        )
        assert narrowed.document.id == html.id


# ═══════════════════════════════════════════════════════════════════════════
# GUARD 11 · WHICH OBJECT LOCK, AND WHAT IT COSTS TO WEAKEN IT
#
# PO 2026-09-03, mid S3 setup: "Until we are in beta mode We should able to
# delete these pdfs". NFR-35 is NOT amended — these cases exist to prove that
# the strict lock is what a deployment gets when it says nothing, and that
# every weaker value is a sentence somebody typed.
#
# ⚠ WHY "NONE" EXISTS AT ALL, AND IT IS NOT A CONVENIENCE. On 2026-09-03 the
# bucket was created, the credentials were right, and tenant creation still
# stopped at step 8 — "Bills, first month" — with
#
#     InvalidRequest: An error occurred (InvalidRequest) when calling the
#     PutObject operation: Bucket is missing ObjectLockConfiguration
#
# because Object Lock had not been ticked at bucket creation and AWS cannot
# switch it on afterwards. GOVERNANCE would have been refused by S3 in exactly
# the same way: both locking modes need the bucket setting. So the only value
# that writes to the bucket that already exists is one that sends no lock at
# all — and tc35 is the case that proves it sends none, rather than sending an
# empty one, which S3 reads as a malformed request and refuses too.
#
# ⚠ HARD-WON LAW 7, AND THE HONEST SCORE IS FOUR OUT OF SIX. These cases were
# run against the PREVIOUS commit's code — same test file, old module, in a
# private `git worktree` so the shared tree was never moved — and it said:
#
#     FAILED …::test_cr049_t1_tc33__governance_is_written_when_a_deployment_types_it
#     FAILED …::test_cr049_t1_tc34__lower_case_and_spacing_are_accepted_a_misspelling_is_not
#     FAILED …::test_cr049_t1_tc35__none_omits_the_lock_parameters_it_does_not_send_them_empty
#     FAILED …::test_cr049_t1_tc36__base_settings_ship_the_strict_lock
#     4 failed, 2 passed
#
# **tc32 and tc37 were green on the old code too, and neither is a proof of
# this change** — said here rather than left for a reader to assume, because a
# case that cannot fail is the thing law 7 exists to catch. tc32 is green
# because COMPLIANCE was already the only mode; it earns its place as tc33's
# pair, since a default is only proved by something that MOVES beside it.
# tc37 is green because the old `backend()` read no setting at all; it is a
# regression guard for the future adapter, not evidence for today.
# ═══════════════════════════════════════════════════════════════════════════


def test_cr049_t1_tc32__the_default_lock_is_none_since_cr160_and_nobody_typed_it(
    tenants, aws, settings
):
    """Say nothing, get NO lock — `CR-160-BRC10`, PO 2026-10-02: *"dont lock it"*.

    ⚠ **SUPERSEDED ASSERTION, KEPT AS HISTORY:** until 2026-10-02 this case was
    `…the_default_lock_is_compliance…` and asserted `ObjectLockMode ==
    "COMPLIANCE"` with the flag True (NFR-35, hard-won law 3). The PO ruled the
    lock off for now, so an unset setting must now send no lock parameter at
    all, and the flag must say honestly that nothing is guaranteed.
    """
    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = ""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store()
    sent = aws.puts[-1]
    assert "ObjectLockMode" not in sent
    assert "ObjectLockRetainUntilDate" not in sent
    assert document_storage.backend().guarantees_immutable_retention is False


def test_cr049_t1_tc33__governance_is_written_when_a_deployment_types_it(tenants, aws, settings):
    """The weaker lock reaches the wire, and the guarantee flag goes with it.

    ⚠ **THE SECOND ASSERTION IS THE POINT (hard-won law 1).** The adapter used
    to answer `guarantees_immutable_retention = True` as a constant. Under
    GOVERNANCE a principal holding `s3:BypassGovernanceRetention` deletes the
    object, so a flag still answering True would be a comment claiming a
    guarantee — and `backend()`'s last guard, the only thing that reads it,
    would wave a deletable store through as a seven-year record.
    """
    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "GOVERNANCE"
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store()
    sent = aws.puts[-1]
    assert sent["ObjectLockMode"] == "GOVERNANCE"
    years = sent["ObjectLockRetainUntilDate"].year - dt.datetime.now(dt.timezone.utc).year
    assert years == 7, "the retention is unchanged; only who may break it moves"
    assert document_storage.backend().guarantees_immutable_retention is False


def test_cr049_t1_tc34__lower_case_and_spacing_are_accepted_a_misspelling_is_not(
    tenants, aws, settings
):
    """`governance` works; `GOVERNENCE` is refused by name rather than defaulted.

    Falling back to the default on an unrecognised value is the dangerous
    tidy-up here, in both directions: a misspelling that quietly became
    COMPLIANCE strands a beta on a bucket it cannot write to, and one that
    quietly became NONE drops the guarantee on production. Neither failure
    mentions the setting.
    """
    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "  governance "
    assert document_storage.object_lock_mode() == "GOVERNANCE"

    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "GOVERNENCE"
    with pytest.raises(document_storage.StorageNotConfigured) as refusal:
        document_storage.object_lock_mode()
    said = str(refusal.value)
    assert "GOVERNENCE" in said
    for value in ("COMPLIANCE", "GOVERNANCE", "NONE"):
        assert value in said, "the refusal names every value that would have worked"


def test_cr049_t1_tc35__none_omits_the_lock_parameters_it_does_not_send_them_empty(
    tenants, aws, settings
):
    """The DEF-3489 case: a bucket created without Object Lock.

    ⚠ **`ObjectLockMode=""` IS NOT "NO LOCK" TO S3, IT IS A MALFORMED REQUEST**,
    and it would fail on the very bucket this value exists to write to. So the
    assertion is `not in`, on both keys, and it is written that way on purpose:
    an assertion that the value is falsey would pass on the broken version.

    Everything that is NOT the lock still goes: the encryption mode and the
    checksum are decisions 6 and 7 and are not what the PO gave up.
    """
    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "NONE"
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store()
    sent = aws.puts[-1]
    assert "ObjectLockMode" not in sent
    assert "ObjectLockRetainUntilDate" not in sent
    assert sent["ServerSideEncryption"] == "AES256"
    assert sent["ChecksumSHA256"], "the corruption check survives the lock going away"
    assert document_storage.backend().guarantees_immutable_retention is False


def test_cr049_t1_tc36__base_settings_ship_no_lock_since_cr160(settings):
    """What an unconfigured production host gets, read from `base.py` itself.

    ⚠ **AMENDED 2026-10-02 (`CR-160-BRC10`):** this asserted `COMPLIANCE`
    (`…ship_the_strict_lock`) until the PO ruled *"we dont want this to be
    enabled right now - dont lock it"*. It still reads the settings module a
    deployment actually loads, so an edit that quietly turned the lock back on
    for every host turns this red.
    """
    from config.settings import base

    assert base.DOCUMENT_STORAGE_OBJECT_LOCK_MODE == "NONE"


def test_cr049_t1_tc37__a_weaker_lock_passes_the_guard_only_because_it_was_typed(
    tenants, aws, settings
):
    """Both weaker modes resolve; an adapter that answers False on its own does not.

    `backend()`'s last guard refuses a store that cannot promise immutable
    retention. That guard now has to let GOVERNANCE and NONE through — a
    deployment typed them — while still refusing the case it was written for:
    a future adapter that answers False without anybody having said so.

    ⚠ **GREEN BEFORE THE CHANGE AS WELL**, because the old `backend()` read no
    setting, so its loop could not discriminate. Kept as the regression guard
    for the day a GCS or Azure adapter arrives — which is the only thing the
    original guard was ever for — and NOT counted as evidence for this change.
    """
    for mode in ("COMPLIANCE", "GOVERNANCE", "NONE"):
        settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = mode
        assert document_storage.backend().name == "aws_s3"

    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "COMPLIANCE"
    resolved = document_storage.backend()
    monkey = type(resolved)
    original = monkey.guarantees_immutable_retention
    monkey.guarantees_immutable_retention = property(lambda self: False)
    try:
        with pytest.raises(document_storage.StorageNotConfigured) as refusal:
            document_storage.backend()
        assert "immutable retention" in str(refusal.value)
    finally:
        monkey.guarantees_immutable_retention = original


def test_cr049_t1_tc38__the_missing_object_lock_refusal_says_what_to_do_about_it(
    tenants, aws, settings, monkeypatch
):
    """DEF-2363: S3's sentence is accurate and unusable; ours names both fixes.

    RED FIRST is trivial here and is stated rather than dressed up: before this
    change the adapter had no `except` around `put_object` at all, so S3's
    string reached the seeding screen verbatim and this case could not pass.

    ⚠ **THE LAST BLOCK IS THE ONE THAT MATTERS.** A layer that paraphrased every
    S3 failure would be guessing about errors it has never seen, and a wrong
    guess about somebody else's error is worse than the error. So a permissions
    failure must come back untouched — same class, same words.
    """

    def refuse_no_lock(**kwargs):
        raise RuntimeError(
            "An error occurred (InvalidRequest) when calling the PutObject "
            "operation: Bucket is missing ObjectLockConfiguration"
        )

    alpha, _ = tenants
    monkeypatch.setattr(aws, "put_object", refuse_no_lock)
    with tenant_context(alpha.id), pytest.raises(document_storage.StorageWriteRefused) as refusal:
        _store()

    said = str(refusal.value)
    assert "cannot be fixed in place" in said.lower(), "the bucket is replaced, not repaired"
    assert "DOCUMENT_STORAGE_OBJECT_LOCK_MODE=NONE" in said, "way out (2), typed exactly"
    assert "DOCUMENT_STORAGE_BUCKET" in said, "way out (1)"
    assert "ObjectLockConfiguration" in said, "S3's own words are kept, not replaced"

    def refuse_access(**kwargs):
        raise RuntimeError("An error occurred (AccessDenied) when calling the PutObject operation")

    monkeypatch.setattr(aws, "put_object", refuse_access)
    with tenant_context(alpha.id), pytest.raises(RuntimeError) as passed_through:
        _store()
    assert not isinstance(passed_through.value, document_storage.DocumentStorageError)
    assert "AccessDenied" in str(passed_through.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(e) and its 2026-08-30 amendments · BR-NOT-027 · NFR-33/NFR-35 · 12-governance/02-decision-log.md 2026-08-30)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — nothing is mounted until CR-049 task 3) E=deferred(no-frontend-half — CR-049 task 3) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every guard PROVED RED FIRST on live PostgreSQL 16 — transcripts quoted in the case docstrings, not only in the lane report
# exceptions: (1) The AWS adapter is exercised against an INJECTED client — the request is proved, a real bucket round trip is NOT, and `boto3` is not installed in this environment. (2) Object Lock is a bucket setting AWS accepts only at bucket creation, so no test here can assert the lock itself. (3) The four cases carrying `requires_postgres` are SKIPPED on the default sqlite run; their guarantees are ALSO asserted at the service layer, which runs everywhere.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
