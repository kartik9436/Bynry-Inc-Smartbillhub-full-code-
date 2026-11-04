# ── Trace ──────────────────────────────────────────────
# Change:   CR-160-BRC10 — utility files are stored at
#           t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext] in one
#           bucket per environment, and no file is object-locked for now
#           (PO 2026-10-02, decision log row of that date).
# Rules:    CR-049 decision 3 (AMENDED) · document_storage.py decision 6's lock
#           (SUSPENDED) · BR-TEN-011 (the web name's grammar) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""The storage key layout and the no-lock ruling, asserted.

⚠ **PROVED RED FIRST (law 7).** Every case below was run against the code as it
stood at `2ed37e46c` (the `CR-049` shape, COMPLIANCE by default) before the
change was written; the failures are quoted in the CR file's §5.

Most cases run on any database. The cross-tenant case carries
`requires_postgres`, because the guarantee it asserts — another utility cannot
even SEE the row that names the key — is RLS, and SQLite has none:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL="postgres://…/sbh_cr160" \\
    python -m pytest tests/test_cr160_storage_key_layout.py --reuse-db -q
"""

import datetime as dt
import inspect
import uuid

import pytest
from django.db import connection

from apps.tenancy import document_models, document_storage, document_store
from apps.tenancy.document_models import (
    DOCUMENT_KIND_MODULE,
    DOCUMENT_KINDS,
    STORAGE_MODULES,
    StoredDocument,
)
from core.tenancy import tenant_context
from tests.isolation_helpers import (  # noqa: F401 — fixtures
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)

PDF = b"%PDF-1.7\nSeptember bill for Austin Water\n%%EOF"


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """The SQLite GUC recorder, exactly as `test_cr049_t1_document_store` uses it."""
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
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


@pytest.fixture()
def tenants(db):
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Austin Water", subdomain=f"austin-water-{suffix}")
    beta = Tenant.objects.create(name="Brazos Utility", subdomain=f"brazos-{suffix}")
    return alpha, beta


class Recorder:
    """An S3 client that records every request and answers a lock query."""

    def __init__(self, lock_configuration=None, lock_error=None):
        self.puts = []
        self.objects = {}
        self.lock_configuration = lock_configuration
        self.lock_error = lock_error

    def put_object(self, **request):
        self.puts.append(request)
        self.objects[request["Key"]] = request["Body"]

    def get_object(self, *, Bucket, Key):  # noqa: N803
        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

        return {"Body": _Body(self.objects[Key])}

    def get_object_lock_configuration(self, *, Bucket):  # noqa: N803
        if self.lock_error is not None:
            raise self.lock_error
        return self.lock_configuration


@pytest.fixture()
def aws(settings):
    client = Recorder()
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    settings.DOCUMENT_STORAGE_BUCKET = "sbh-prod"
    settings.DOCUMENT_STORAGE_REGION = "us-east-2"
    settings.DOCUMENT_STORAGE_SSE = "AES256"
    # What a host that sets nothing gets — read from base.py, not assumed.
    from config.settings import base

    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = base.DOCUMENT_STORAGE_OBJECT_LOCK_MODE
    document_storage.set_s3_client_factory(lambda: client)
    yield client
    document_storage.set_s3_client_factory(None)


def _store(kind="bill", content_type="application/pdf", **overrides):
    kwargs = dict(
        kind=kind,
        source_type="invoice",
        source_id=uuid.uuid4(),
        content_type=content_type,
        display_name="bills/2026/09/ACC-1042-INV-000123.pdf",
        payload=PDF,
        process="billing.issue",
    )
    kwargs.update(overrides)
    return document_store.store(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# THE MODULE MAP
# ═══════════════════════════════════════════════════════════════════════════


def test_cr160_tc1__every_kind_maps_to_exactly_one_listed_module():
    """A kind added to DOCUMENT_KINDS without a module fails HERE, not in production."""
    unmapped = sorted(set(DOCUMENT_KINDS) - set(DOCUMENT_KIND_MODULE))
    assert unmapped == [], f"document kinds with no storage module: {unmapped}"
    stray = sorted(set(DOCUMENT_KIND_MODULE) - set(DOCUMENT_KINDS))
    assert stray == [], f"module map names kinds that do not exist: {stray}"
    off_list = {k: m for k, m in DOCUMENT_KIND_MODULE.items() if m not in STORAGE_MODULES}
    assert off_list == {}, f"kinds mapped to a module not on the fixed list: {off_list}"
    # 48 → 49: `work_template_help` (`CR-168-BRC10` P3.14, tenancy/0059, lane SRV-3).
    # 49 → 50: `work_certificate_proof` (`CR-168-BRC10` image 33, tenancy/0060, lane SRV-4).
    # 50 → 51: `tenant_logo` (`CR-172-BRC10`, tenancy/0061, lane LOGO) — the
    # first kind in the `tenancy` folder.
    # 51 → 52: `high_usage_alert` (`CR-182-BRC10`, tenancy/0062, lane HIGHUSE) —
    # the kept high-consumption email, filed under `metering`.
    # 52 → 53: `account_access_email` (`CR-188-BRC10`, tenancy/0065_cr188;
    # `DEF-CWP-10381`'s portal reset maps to the same kind) — an account-access
    # email, kept with its link redacted.
    assert len(DOCUMENT_KINDS) == 53


def test_cr160_tc2__the_module_list_is_the_ruled_twelve_in_lowercase():
    assert STORAGE_MODULES[:12] == (
        "billing",
        "payments",
        "customers",
        "metering",
        "rating",
        "ledger",
        "notifications",
        "work",
        "portal",
        "reports",
        "integrations",
        "tenancy",
    )
    assert all(m == m.lower() and m.isidentifier() for m in STORAGE_MODULES)


def test_cr160_tc3__an_unmapped_kind_is_refused_not_defaulted(tenants, docs_dir, monkeypatch):
    alpha, _ = tenants
    monkeypatch.delitem(document_models.DOCUMENT_KIND_MODULE, "bill")
    with tenant_context(alpha.id):
        with pytest.raises(ValueError, match="has no storage module"):
            _store()
        assert not StoredDocument.objects.filter(tenant_id=alpha.id).exists()
    assert not docs_dir.exists() or not any(docs_dir.rglob("*.pdf"))


# ═══════════════════════════════════════════════════════════════════════════
# THE KEY SHAPE
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("module", STORAGE_MODULES)
def test_cr160_tc4__key_shape_per_module(module):
    doc_id = uuid.UUID("0192f0aa-1111-7222-8333-444455556666")
    moment = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)
    key = document_storage.key_for(
        tenant_folder="austin-water",
        module=module,
        document_id=doc_id,
        moment=moment,
        extension="pdf",
    )
    assert key == f"t/austin-water/{module}/2026/09/{doc_id}.pdf"
    assert document_storage._require_key(key) == key
    bare = document_storage.key_for(
        tenant_folder="austin-water", module=module, document_id=doc_id, moment=moment
    )
    assert bare == f"t/austin-water/{module}/2026/09/{doc_id}"
    assert document_storage._require_key(bare) == bare


@pytest.mark.parametrize(
    "kind,content_type,module,ext",
    [
        ("bill", "application/pdf", "billing", ".pdf"),
        ("bill", "text/html", "billing", ".html"),
        ("payment_receipt", "application/pdf", "payments", ".pdf"),
        ("account_document", "image/png", "customers", ".png"),
        ("service_outage_notice", "text/plain", "metering", ".txt"),
        ("exemption_certificate", "image/jpeg", "rating", ".jpg"),
        ("supplier_invoice", "application/pdf", "ledger", ".pdf"),
        ("account_message", "text/html; charset=utf-8", "notifications", ".html"),
        ("work_order_photo", "image/jpeg", "work", ".jpg"),
        ("scheduled_report_notice", "text/html", "reports", ".html"),
        ("import_source_file", "text/csv", "integrations", ".csv"),
        ("bill", "application/x-unknown", "billing", ""),
    ],
)
def test_cr160_tc5__a_stored_file_lands_under_web_name_module_month(
    tenants, docs_dir, kind, content_type, module, ext
):
    alpha, _ = tenants
    with tenant_context(alpha.id):
        ref = _store(kind=kind, content_type=content_type)
        row = StoredDocument.objects.get(id=ref.id)
        assert document_store.fetch(ref.id) == PDF
    yyyy, mm = f"{row.stored_at:%Y}", f"{row.stored_at:%m}"
    assert row.storage_key == f"t/{alpha.subdomain}/{module}/{yyyy}/{mm}/{ref.id}{ext}"
    assert (docs_dir / row.storage_key).read_bytes() == PDF
    assert not row.storage_key.startswith("t/" + str(alpha.id)), "the old shape was written"


# ═══════════════════════════════════════════════════════════════════════════
# OLD KEYS STILL LOAD; BAD KEYS DO NOT
# ═══════════════════════════════════════════════════════════════════════════


def test_cr160_tc6__a_file_stored_under_the_old_shape_still_opens(tenants, docs_dir):
    """Nothing was moved and no storage_key rewritten — the CR-049 shape must load."""
    alpha, _ = tenants
    doc_id = uuid.uuid4()
    legacy = f"t/{alpha.id}/2026/08/{doc_id}"
    backend = document_storage.backend()
    backend.put(
        key=legacy,
        payload=PDF,
        content_type="application/pdf",
        hex_digest=document_storage.content_hash(PDF),
        retain_for_years=7,
    )
    with tenant_context(alpha.id):
        StoredDocument(
            id=doc_id,
            tenant_id=alpha.id,
            kind="bill",
            source_type="invoice",
            source_id=uuid.uuid4(),
            storage_key=legacy,
            storage_backend=backend.name,
            content_hash=document_storage.content_hash(PDF),
            byte_length=len(PDF),
            content_type="application/pdf",
            display_name="bills/2026/08/ACC-1042-INV-000099.pdf",
            stored_by_process="billing.issue",
        ).save()
        assert document_store.fetch(doc_id) == PDF


@pytest.mark.parametrize(
    "key",
    [
        "t/../../etc/passwd",
        "t/austin-water/billing/2026/09/../../x",
        "t/austin-water/finance/2026/09/0192f0aa-1111-7222-8333-444455556666.pdf",
        "t/Austin-Water/billing/2026/09/0192f0aa-1111-7222-8333-444455556666.pdf",
        "t/austin water/billing/2026/09/0192f0aa-1111-7222-8333-444455556666.pdf",
        "sbh-prod/t/austin-water/billing/2026/09/0192f0aa-1111-7222-8333-444455556666.pdf",
        "t/austin-water/billing/2026/9/0192f0aa-1111-7222-8333-444455556666.pdf",
        "t/austin-water/billing/2026/09/0192f0aa-1111-7222-8333-444455556666.PDF",
        "t/austin-water/billing/2026/09/0192f0aa-1111-7222-8333-444455556666.p/f",
        "t/austin-water/2026/09/0192f0aa-1111-7222-8333-444455556666",
        "",
    ],
)
def test_cr160_tc7__a_malformed_key_is_refused(key, docs_dir):
    with pytest.raises(document_storage.DocumentStorageError):
        document_storage._require_key(key)
    with pytest.raises(document_storage.DocumentStorageError):
        document_storage.backend().get(key=key)


@pytest.mark.parametrize(
    "folder",
    [
        "austin/water",
        "..",
        "a..b/..",
        "austin water",
        "Austin-Water",
        "AUSTIN",
        "-austin",
        "austin-",
        "ab",
        "a" * 64,
        "",
        "austin.water",
        "austin_water",
    ],
)
def test_cr160_tc8__a_folder_that_is_not_a_web_name_is_refused(folder):
    with pytest.raises(document_storage.DocumentStorageError, match="web name"):
        document_storage.key_for(
            tenant_folder=folder,
            module="billing",
            document_id=uuid.uuid4(),
            moment=dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc),
        )


def test_cr160_tc9__a_module_off_the_list_is_refused():
    for module in ("finance", "Billing", "billing/../x", ""):
        with pytest.raises(document_storage.DocumentStorageError, match="fixed module list"):
            document_storage.key_for(
                tenant_folder="austin-water",
                module=module,
                document_id=uuid.uuid4(),
                moment=dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc),
            )


def test_cr160_tc10__a_tenant_whose_web_name_is_bad_writes_nothing(db, docs_dir):
    """A web name that slipped past sign-up never reaches the bucket as a path."""
    from apps.tenancy.models import Tenant

    bad = Tenant.objects.create(name="Bad", subdomain=f"Bad Name/{uuid.uuid4().hex[:6]}")
    with tenant_context(bad.id):
        with pytest.raises(document_storage.DocumentStorageError, match="web name"):
            _store()
        assert not StoredDocument.objects.filter(tenant_id=bad.id).exists()
    assert not docs_dir.exists() or not any(p.is_file() for p in docs_dir.rglob("*"))


def test_cr160_tc11__no_caller_can_name_the_folder_or_the_module():
    """The key's parts come from the row; store() takes neither as an argument."""
    params = set(inspect.signature(document_store.store).parameters)
    for forbidden in (
        "tenant",
        "tenant_id",
        "tenant_folder",
        "subdomain",
        "module",
        "key",
        "storage_key",
    ):
        assert forbidden not in params, forbidden


# ═══════════════════════════════════════════════════════════════════════════
# NO LOCK, NO TAG
# ═══════════════════════════════════════════════════════════════════════════


def test_cr160_tc12__base_settings_ship_no_lock():
    from config.settings import base

    assert base.DOCUMENT_STORAGE_OBJECT_LOCK_MODE == "NONE"
    assert document_storage.DEFAULT_OBJECT_LOCK_MODE == "NONE"


@pytest.mark.parametrize(
    "kind",
    [
        "bill",
        "payment_plan_agreement",
        "service_agreement",
        "disconnect_notice",
        "import_source_file",
        "account_document",
        "work_order_report",
    ],
)
def test_cr160_tc13__every_put_carries_no_lock_and_no_expiry_tag(tenants, aws, kind):
    """Legal files included — the PO's words were "dont lock it"."""
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store(kind=kind)
    sent = aws.puts[-1]
    assert "ObjectLockMode" not in sent
    assert "ObjectLockRetainUntilDate" not in sent
    assert "ObjectLockLegalHoldStatus" not in sent
    assert "Tagging" not in sent
    assert "Expires" not in sent
    assert sent["Bucket"] == "sbh-prod"
    assert sent["Key"].startswith(f"t/{alpha.subdomain}/")
    assert "sbh-prod" not in sent["Key"], "the key never names the bucket"
    assert sent["ServerSideEncryption"] == "AES256"


def test_cr160_tc14__the_lock_is_still_a_setting_that_can_be_switched_on(tenants, aws, settings):
    settings.DOCUMENT_STORAGE_OBJECT_LOCK_MODE = "COMPLIANCE"
    alpha, _ = tenants
    with tenant_context(alpha.id):
        _store()
    assert aws.puts[-1]["ObjectLockMode"] == "COMPLIANCE"
    assert "Tagging" not in aws.puts[-1]


# ═══════════════════════════════════════════════════════════════════════════
# THE BOOT CHECK REFUSES A BUCKET WITH A DEFAULT RETENTION RULE
# ═══════════════════════════════════════════════════════════════════════════


def test_cr160_tc15__a_bucket_with_default_retention_is_refused_at_boot(aws):
    from django.core.checks import Error

    from core import storage_guard

    aws.lock_configuration = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": 7}},
        }
    }
    found = storage_guard.check_document_storage()
    assert len(found) == 1, found
    issue = found[0]
    assert isinstance(issue, Error)
    assert issue.id == storage_guard.RETENTION_ERROR_ID
    assert "DEFAULT retention rule" in issue.msg
    assert "COMPLIANCE" in issue.msg and "nobody" in issue.msg
    assert "export" in issue.msg


def test_cr160_tc16__a_bucket_without_default_retention_boots(aws):
    from core import storage_guard

    aws.lock_error = RuntimeError(
        "An error occurred (ObjectLockConfigurationNotFoundError) when calling the "
        "GetObjectLockConfiguration operation: Object Lock configuration does not exist"
    )
    assert storage_guard.check_document_storage() == []
    aws.lock_error = None
    aws.lock_configuration = {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}
    assert storage_guard.check_document_storage() == []


def test_cr160_tc17__a_bucket_that_cannot_be_asked_warns_and_never_passes_silently(aws):
    from django.core.checks import Warning as CheckWarning

    from core import storage_guard

    aws.lock_error = PermissionError("AccessDenied: s3:GetBucketObjectLockConfiguration")
    found = storage_guard.check_document_storage()
    assert len(found) == 1 and isinstance(found[0], CheckWarning), found
    assert "could not ask the bucket" in found[0].msg


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-TENANT — ON POSTGRESQL, WHERE THE GUARANTEE EXISTS
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_cr160_tc18__another_utility_cannot_fetch_even_knowing_the_key(
    tenants, docs_dir, rls  # noqa: F811
):
    """The prefix is a name, not a wall — the ROW is the wall.

    Tenant B is handed tenant A's exact key and document id. It cannot see the
    row that names the key (RLS, under a non-superuser probe role), the store's
    read answers the same as for a document that never existed, and nothing
    above the store accepts a key at all (tc11).
    """
    alpha, beta = tenants
    with tenant_context(alpha.id):
        ref = _store()
        key = StoredDocument.objects.get(id=ref.id).storage_key
    assert key.startswith(f"t/{alpha.subdomain}/billing/")

    with live_tenant_context(beta.id):
        assert rls.count("stored_documents", "storage_key = %s", [key]) == 0
        assert rls.count("stored_documents", "id = %s", [str(ref.id)]) == 0
    with live_tenant_context(alpha.id):
        assert rls.count("stored_documents", "storage_key = %s", [key]) == 1

    with tenant_context(beta.id):
        with pytest.raises(document_store.DocumentStoreError):
            document_store.fetch(ref.id)
        assert not document_store.for_source(source_type="invoice", source_id=ref.source_id).found
    assert connection.vendor == "postgresql"
