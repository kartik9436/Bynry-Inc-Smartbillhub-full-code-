# ── Trace ──────────────────────────────────────────────
# Change:   Export files move from the shared disk to S3 — PO ruling 2026-10-02,
#           decision log "EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE
#           DESIGN IS APPROVED" (47ffb95ef). Analysis: 09-infra/04-exports-to-s3.md.
# Defect:   DEF-MET-4954 (a worker wrote the export to ITS disk; web answered 404)
# Rules:    CR-160-BRC10 (key t/<web name>/<module>/<yyyy>/<mm>/<file id>[.ext],
#           one bucket per environment, no object lock, no expiry tag) ·
#           BR-REP-018 / IS-11 (the download contract) · the 2026-08-30 4-hour
#           link ruling (document_storage.url_ttl_seconds) · CLAUDE.md law 3
# Tests:    06-backend/tests/test_s3a_export_storage.py
# ───────────────────────────────────────────────────────
"""Where an EXPORT FILE's bytes live: S3, under `t/<web name>/export/`, and nowhere else.

WHY A SIBLING OF THE DOCUMENT STORE AND NOT THE DOCUMENT STORE ITSELF
--------------------------------------------------------------------
Approved by the PO as proposed. Three facts of `document_storage.py` /
`document_models.py` decide it:

1. **A stored document can never be deleted** — migration `0026` refuses every
   UPDATE and DELETE on `stored_documents`. An export MUST be deleted when the
   utility's `file_retention_days` runs out, so it cannot be one of those rows.
2. **`DocumentStorageBackend` has no delete, deliberately** — *"a delete method
   here would be a door onto a locked room"*. Adding one there would weaken the
   legal store's contract for every bill and notice.
3. **It moves whole files in memory.** A print set is 67 MB at the 25,000-bill
   ceiling and ~107 MB at 40,000 accounts (measured, 09-infra/04 §3); this
   adapter uploads from a path in parts and serves a signed link.

WHAT IS SHARED: the bucket (`DOCUMENT_STORAGE_BUCKET`), region, endpoint and SSE
settings, the boto3 client construction, the key builder and its key shape
(`document_storage.key_for` with module `export`), and the 4-hour link cap.

⚠ **THERE IS NO FILESYSTEM BACKEND HERE, IN ANY ENVIRONMENT.** PO, 2026-10-02:
*"keep the same mechanism everywhere we have dedicated s3 bucket for every env"*.
`DOCUMENT_STORAGE_BACKEND = "filesystem"` (tests, a developer machine) changes
where DOCUMENTS go and has no effect on exports. The test suite reaches an S3
EMULATOR through this same client (`tests/conftest.py`); a developer points
`DOCUMENT_STORAGE_BUCKET` at their environment's bucket, or
`DOCUMENT_STORAGE_ENDPOINT_URL` at an S3-compatible emulator.

⚠ **DELETE IS CONFINED TO THE EXPORT FOLDER, AND THIS FILE IS ONE OF THREE
LOCKS.** PO: *"make sure that you don't delete any other data"*. (1) the sweep
acts only on `job_artifacts` rows; (2) `delete()` below refuses any key that is
not a key this store composed under `t/<THAT utility's web name>/export/` —
checked HERE, inside the adapter, so no caller can skip it; (3) the app's IAM
permission to delete is `t/*/export/*` (09-infra/02-aws-runbook.md). No object
in this bucket is locked (`CR-160-BRC10`), so these are the only barriers.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

from django.conf import settings

from apps.tenancy import document_storage

logger = logging.getLogger("smartbillhub.exports")

#: The folder segment every export file is stored under (`document_models.STORAGE_MODULES`).
EXPORT_MODULE = "export"

#: Multipart upload shape. 8 MiB parts, at most 4 in flight: a 107 MB print set
#: uploads with ~32 MiB of buffers rather than the whole archive in memory.
PART_SIZE = 8 * 1024 * 1024
MAX_CONCURRENCY = 4
#: Chunk size a streamed read hands back (`open_stream`).
STREAM_CHUNK = 64 * 1024

#: The one key shape this store will touch: an export key, a 36-char file id
#: and an optional short extension. Composed only by `export_key`.
_EXPORT_KEY_RE = re.compile(
    r"^t/(?P<folder>[a-z0-9](?:[a-z0-9-]{1,61})[a-z0-9])/export/[0-9]{4}/[0-9]{2}/"
    r"[0-9a-f-]{36}(?:\.[a-z0-9]{1,8})?$"
)

#: A download filename is the IS-11 name the writer composed — tenant slug,
#: report slug, period, basis, timestamp. Anything outside this alphabet is
#: refused rather than escaped into a header.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


class ExportKeyRefused(document_storage.DocumentStorageError):
    """A key that is not this utility's export — refused before any request is made."""


class ExportObjectMissing(document_storage.DocumentStorageError):
    """The upload returned but the bucket does not hold the file it was given (DEF-TEN-9190)."""


def export_prefix(tenant_folder: str) -> str:
    """`t/<web name>/export/` — the only folder this store reads, writes or deletes in."""
    folder = str(tenant_folder or "")
    if not document_storage.TENANT_FOLDER_RE.match(folder):
        raise ExportKeyRefused(f"{folder!r} is not a utility web name (BR-TEN-011).")
    return f"t/{folder}/{EXPORT_MODULE}/"


def export_key(
    *, tenant_folder: str, file_id: UUID | str, moment: dt.datetime, extension: str
) -> str:
    """`t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>` — through CR-160's key builder."""
    return document_storage.key_for(
        tenant_folder=tenant_folder,
        module=EXPORT_MODULE,
        document_id=file_id,
        moment=moment,
        extension=extension,
    )


def require_export_key(key: str, tenant_folder: str) -> str:
    """`key`, if it is an export key of THIS utility; otherwise `ExportKeyRefused`.

    Prefix AND shape: `startswith` alone would accept `…/export/../billing/…`,
    which S3 treats as a literal key but a reader would not; the full pattern
    makes the answer unambiguous for both.
    """
    prefix = export_prefix(tenant_folder)
    match = _EXPORT_KEY_RE.match(key or "")
    if not match or not key.startswith(prefix):
        raise ExportKeyRefused(
            f"{key!r} is not an export file of {tenant_folder!r}. This store acts only on "
            f"keys under {prefix} that it composed itself; a bill, a notice or another "
            "utility's file is refused before any request is made (PO 2026-10-02: "
            "\"make sure that you don't delete any other data\")."
        )
    return key


def content_disposition(filename: str) -> str:
    """`attachment; filename="<IS-11 name>"` — refused, never escaped, when unusual."""
    if not _FILENAME_RE.match(filename or ""):
        raise document_storage.DocumentStorageError(f"{filename!r} is not a download name.")
    return f'attachment; filename="{filename}"'


class S3ExportStorage:
    """Export files in the environment's S3 bucket."""

    name = document_storage.BACKEND_AWS_S3

    def __init__(self, *, bucket: str, client: Any, sse: str) -> None:
        self.bucket = bucket
        self.client = client
        self.sse = sse

    def put_file(
        self, *, key: str, tenant_folder: str, path: Path, content_type: str
    ) -> tuple[int, str]:
        """Upload `path` to `key` in parts. Returns (byte length, sha256 hex).

        The hash is read from the FILE, before the upload, so the record says
        what was handed over rather than what a response claimed.
        """
        require_export_key(key, tenant_folder)
        digest = hashlib.sha256()
        length = 0
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                length += len(block)
        from boto3.s3.transfer import TransferConfig

        self.client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ServerSideEncryption": self.sse},
            Config=TransferConfig(
                multipart_threshold=PART_SIZE,
                multipart_chunksize=PART_SIZE,
                max_concurrency=MAX_CONCURRENCY,
            ),
        )
        # ⚠ DEF-TEN-9190 — THE OBJECT IS LOOKED AT BEFORE ANYONE IS TOLD IT IS
        # THERE. An upload that "returned" is a claim by the transfer library; a
        # HEAD of the key is the bucket's own answer. A file that is absent or
        # the wrong size here is a FAILED export, never a stored one.
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 — classified by the caller
            raise ExportObjectMissing(
                f"the export store uploaded {key!r} and then could not find it: {exc}"
            ) from exc
        stored = int(head.get("ContentLength", -1))
        if stored != length:
            raise ExportObjectMissing(
                f"the export store uploaded {length} byte(s) to {key!r} and the bucket "
                f"holds {stored}"
            )
        return length, digest.hexdigest()

    def exists(self, *, key: str, tenant_folder: str) -> bool:
        """Does the bucket hold this export right now? One HEAD (DEF-TEN-9190).

        Asked before the download route redirects a browser to the file: a
        signed link to a missing object lands the person on S3's own error
        document. Any failure to answer reads as "not there".
        """
        require_export_key(key, tenant_folder)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception:  # noqa: BLE001 — absent, denied or unreachable: not handed over
            return False
        return True

    def describe(self) -> str:
        """`s3://<bucket> via <endpoint or AWS> in <region>` — for logs; holds no secret."""
        meta = getattr(self.client, "meta", None)
        endpoint = getattr(meta, "endpoint_url", None) or "AWS"
        region = getattr(meta, "region_name", None) or "?"
        return f"s3://{self.bucket} via {endpoint} in {region}"

    def read_url(
        self,
        *,
        key: str,
        tenant_folder: str,
        filename: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> str:
        """A signed GET that names the file — 4 hours (the 2026-08-30 ruling's cap).

        A bearer link for ONE file, exactly as `document_store.download_url` is.
        `expires_in` can only shorten it: `url_ttl_seconds()` refuses a setting
        above the cap.
        """
        require_export_key(key, tenant_folder)
        ttl = document_storage.url_ttl_seconds()
        if expires_in is not None:
            ttl = min(int(expires_in), ttl)
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": content_disposition(filename),
                "ResponseContentType": content_type,
            },
            ExpiresIn=ttl,
        )

    def open_stream(self, *, key: str, tenant_folder: str) -> Iterator[bytes]:
        """The object's bytes in chunks — for a caller that must not redirect."""
        require_export_key(key, tenant_folder)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 — see document_storage.AwsS3Storage.get
            raise document_storage.StoredObjectMissing(
                f"the export store could not read the object at {key!r}: {exc}"
            ) from exc
        body = response["Body"]
        try:
            yield from body.iter_chunks(chunk_size=STREAM_CHUNK)
        finally:
            body.close()

    def delete(self, *, key: str, tenant_folder: str) -> None:
        """Delete ONE export object of THIS utility. Anything else is refused.

        Idempotent: S3 answers a delete of a missing key with success, so a
        sweep that ran twice, or a row whose object is already gone, is fine.
        """
        require_export_key(key, tenant_folder)
        self.client.delete_object(Bucket=self.bucket, Key=key)


#: How the S3 client is obtained — replaceable, as `document_storage`'s is, so
#: the suite can hand in an EMULATED client (tests/conftest.py). Separate from
#: `document_storage.set_s3_client_factory` on purpose: the document tests
#: inject recorders for the DOCUMENT adapter, and an export must never be
#: written into one of those by accident.
_client_factory: Callable[[], Any] | None = None


def set_client_factory(factory: Callable[[], Any] | None) -> None:
    global _client_factory
    _client_factory = factory


def backend() -> S3ExportStorage:
    """The environment's bucket — or a refusal naming the setting. Never a disk."""
    bucket = getattr(settings, "DOCUMENT_STORAGE_BUCKET", "") or ""
    if not bucket:
        raise document_storage.StorageNotConfigured(
            "DOCUMENT_STORAGE_BUCKET is not set, so this environment has nowhere to put an "
            "export file. Exports are stored in S3 in every environment (PO 2026-10-02) and "
            "never fall back to a disk: a file written to one container's disk is a 404 on "
            "every other (DEF-MET-4954). Set DOCUMENT_STORAGE_BUCKET and "
            "DOCUMENT_STORAGE_REGION on this host."
        )
    sse = getattr(settings, "DOCUMENT_STORAGE_SSE", "") or ""
    if not sse:
        raise document_storage.StorageNotConfigured(
            "DOCUMENT_STORAGE_SSE is empty, which would write export files unencrypted. "
            "The default is 'AES256'; emptying it is refused rather than obeyed."
        )
    factory = _client_factory or document_storage._client_factory or document_storage._default_client
    return S3ExportStorage(bucket=bucket, client=factory(), sse=sse)


# ── Lifecycle ─────────────────────────────────────────────
# packet: exports-to-S3 build step 1 (09-infra/04-exports-to-s3.md §6; decision log 2026-10-02 "EXPORT FILES MOVE FROM THE SHARED DISK TO S3")
# generated: 2026-10-02 by the s3a lane
# checklist: A✔ B✔ C✔ D=deferred(no API — the store, step 3) E=n/a F✔ G✔ H=n/a
# gates: RED PROVED FIRST — the suite failed to import this module before it existed; the prefix guard was shown letting a billing/ key through with require_export_key's check removed, and refusing it with the check in place (tests/test_s3a_export_storage.py)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
