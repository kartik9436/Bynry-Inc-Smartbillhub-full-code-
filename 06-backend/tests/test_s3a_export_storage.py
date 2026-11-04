"""The export store's S3 adapter — `apps/tenancy/export_storage.py`.

PO ruling 2026-10-02 (decision log, *"EXPORT FILES MOVE FROM THE SHARED DISK TO
S3 — THE DESIGN IS APPROVED"*): every export file is stored at
`t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>`, and the app may delete ONLY
there — *"make sure that you don't delete any other data"*.

These run against an S3 EMULATOR (`moto`) through the real boto3 client: the
same code path every environment uses, with no AWS credentials and no
filesystem stand-in (PO: *"keep the same mechanism everywhere"*).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import urllib.parse
import uuid

import pytest

from apps.tenancy import document_models, document_storage, export_storage

pytestmark = pytest.mark.usefixtures("export_bucket")

MOMENT = dt.datetime(2026, 9, 15, 10, 32, tzinfo=dt.UTC)


def _key(folder: str = "austin-water", ext: str = "csv") -> str:
    return export_storage.export_key(
        tenant_folder=folder, file_id=uuid.uuid4(), moment=MOMENT, extension=ext
    )


def test_export_is_on_the_fixed_module_list_and_zip_has_an_extension():
    assert "export" in document_models.STORAGE_MODULES
    assert document_storage.extension_for("application/zip") == "zip"
    assert document_storage.extension_for("text/csv; charset=utf-8") == "csv"


def test_the_key_is_the_ruled_export_folder():
    file_id = uuid.UUID("01a0fca7-e9e4-7ed6-ac23-ed9f4e92f346")
    key = export_storage.export_key(
        tenant_folder="austin-water", file_id=file_id, moment=MOMENT, extension="csv"
    )
    assert key == f"t/austin-water/export/2026/09/{file_id}.csv"
    assert export_storage.export_prefix("austin-water") == "t/austin-water/export/"


def test_put_file_round_trips_through_s3(tmp_path):
    store = export_storage.backend()
    source = tmp_path / "austin-water_premises.csv"
    body = b"premise_no,address_line\r\nP-00001,1408 Bluestem Ln\r\n"
    source.write_bytes(body)
    key = _key()
    length, digest = store.put_file(
        key=key, tenant_folder="austin-water", path=source, content_type="text/csv; charset=utf-8"
    )
    assert length == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert b"".join(store.open_stream(key=key, tenant_folder="austin-water")) == body


def test_read_url_names_the_file_and_lasts_the_ruled_four_hours(tmp_path):
    store = export_storage.backend()
    key = _key()
    url = store.read_url(
        key=key,
        tenant_folder="austin-water",
        filename="austin-water_premises_full-list_current-state_20260915T1032.csv",
        content_type="text/csv; charset=utf-8",
    )
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert "attachment" in query["response-content-disposition"][0]
    assert "austin-water_premises_full-list" in query["response-content-disposition"][0]
    assert query["response-content-type"][0].startswith("text/csv")
    # SigV4 carries the lifetime (`X-Amz-Expires`); SigV2 carries the moment it
    # ends (`Expires`, epoch seconds). Either way it is four hours from now.
    if "X-Amz-Expires" in query:
        lifetime = int(query["X-Amz-Expires"][0])
    else:
        lifetime = int(query["Expires"][0]) - int(dt.datetime.now(dt.UTC).timestamp())
    assert document_storage.url_ttl_seconds() == 4 * 60 * 60
    assert 4 * 60 * 60 - 60 <= lifetime <= 4 * 60 * 60


def test_delete_removes_an_export_object(tmp_path):
    store = export_storage.backend()
    source = tmp_path / "x.csv"
    source.write_bytes(b"a\r\n")
    key = _key()
    store.put_file(key=key, tenant_folder="austin-water", path=source, content_type="text/csv")
    store.delete(key=key, tenant_folder="austin-water")
    with pytest.raises(document_storage.StoredObjectMissing):
        b"".join(store.open_stream(key=key, tenant_folder="austin-water"))


@pytest.mark.parametrize(
    "module",
    [m for m in document_models.STORAGE_MODULES if m != "export"],
)
def test_delete_refuses_every_key_outside_the_export_folder(module, export_bucket):
    """*"make sure that you don't delete any other data"* — a bill, a notice, a
    receipt: every non-export folder is refused BEFORE any request is made, and
    the object is still there afterwards."""
    store = export_storage.backend()
    key = document_storage.key_for(
        tenant_folder="austin-water",
        module=module,
        document_id=uuid.uuid4(),
        moment=MOMENT,
        extension="pdf",
    )
    export_bucket.put_object(Bucket=store.bucket, Key=key, Body=b"%PDF-1.7 a bill")
    with pytest.raises(export_storage.ExportKeyRefused):
        store.delete(key=key, tenant_folder="austin-water")
    assert export_bucket.get_object(Bucket=store.bucket, Key=key)["Body"].read() == b"%PDF-1.7 a bill"


def test_delete_refuses_another_utilitys_export(export_bucket, tmp_path):
    store = export_storage.backend()
    source = tmp_path / "x.csv"
    source.write_bytes(b"a\r\n")
    theirs = _key(folder="lone-star")
    store.put_file(key=theirs, tenant_folder="lone-star", path=source, content_type="text/csv")
    with pytest.raises(export_storage.ExportKeyRefused):
        store.delete(key=theirs, tenant_folder="austin-water")
    assert export_bucket.get_object(Bucket=store.bucket, Key=theirs)["Body"].read() == b"a\r\n"


@pytest.mark.parametrize(
    "key",
    [
        "t/austin-water/export/../billing/2026/09/x.pdf",
        "t/austin-water/export/",
        "t/austin-water/export/2026/09/not-a-uuid.csv",
        "t/austin-water/exports/2026/09/01a0fca7-e9e4-7ed6-ac23-ed9f4e92f346.csv",
        "",
    ],
)
def test_delete_refuses_a_key_this_store_did_not_compose(key):
    with pytest.raises(export_storage.ExportKeyRefused):
        export_storage.backend().delete(key=key, tenant_folder="austin-water")


def test_no_bucket_is_a_refusal_never_a_disk(settings):
    settings.DOCUMENT_STORAGE_BUCKET = ""
    with pytest.raises(document_storage.StorageNotConfigured, match="DOCUMENT_STORAGE_BUCKET"):
        export_storage.backend()


def test_the_filesystem_document_backend_does_not_reach_exports(settings):
    """The test settings put DOCUMENTS on the filesystem; exports must still go
    to S3 — there is no filesystem stand-in for exports anywhere (PO 2026-10-02)."""
    assert settings.DOCUMENT_STORAGE_BACKEND == "filesystem"
    assert isinstance(export_storage.backend(), export_storage.S3ExportStorage)
