"""Read back an export file the way the product stores it — from S3, through its row.

Since 2026-10-02 (PO ruling, decision log *"EXPORT FILES MOVE FROM THE SHARED
DISK TO S3 — THE DESIGN IS APPROVED"*) an export job leaves NO file on any disk
and NO path on the job: the file is in the environment's bucket (an S3 emulator
in the suite, tests/conftest.py) and its `job_artifacts` row says where.

Tests that used to open `Path(job.payload["artifact_path"])` call
`exported_file(job_id)` instead: it fetches the object through the real client
and writes it under its IS-11 name into a private temp folder, so `.name`,
`.suffix`, `.read_text()` and `.open()` keep meaning what they meant.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


def exported_row(job_id: Any):
    from apps.tenancy.export_models import JobArtifact

    return JobArtifact.objects.get(job_id=job_id)


def exported_bytes(job_id: Any) -> bytes:
    from apps.tenancy import export_storage

    row = exported_row(job_id)
    store = export_storage.backend()
    return store.client.get_object(Bucket=store.bucket, Key=row.storage_key)["Body"].read()


def exported_file(job_id: Any) -> Path:
    """The stored export, copied to a temp file named with its IS-11 name."""
    row = exported_row(job_id)
    path = Path(tempfile.mkdtemp(prefix="sbh-export-test-")) / row.display_name
    path.write_bytes(exported_bytes(job_id))
    return path
