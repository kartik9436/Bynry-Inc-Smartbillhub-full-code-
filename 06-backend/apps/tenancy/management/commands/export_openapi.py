"""BE-11 — export the OpenAPI schema for CI diffing and client generation.

`python manage.py export_openapi [--out PATH]` writes the drf-spectacular
schema as deterministic, sorted JSON (default: 06-backend/openapi/schema.json).
No 10-scripts involvement — the export is a plain management command so CI and
developers run the identical code path (TD-19; B13 row BE-11).

CI-DIFF CLAUSE (A11 Addendum r2): the contract baseline is A11 + 11b COMBINED.
CI re-exports on every change and diffs against the committed snapshot; ANY
drift fails the build — an endpoint cannot change shape without the contract
docs (and the FI-01 generated client) moving in the same review.

That clause was DESCRIBED here from 2026-08-09 and did not exist: no workflow
ran the export, and openapi/schema.json was never committed, so the sentence
above was a promise the repository did not keep. Both halves landed 2026-08-10
— the snapshot (83 paths: 77 tenant-scoped, 6 tenant-less) and the
`OpenAPI contract diff` step in .github/workflows/ci-backend.yml. Regenerate
with `python manage.py export_openapi` and commit the result whenever an
endpoint changes shape.

Hosted by apps.tenancy because management commands must live in an installed
app and tenancy is the platform module (same hosting disposition as the jobs /
bell tables — build report).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "openapi" / "schema.json"


class Command(BaseCommand):
    help = "Export the OpenAPI schema (deterministic JSON) for CI diff + client generation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=str(DEFAULT_OUT),
            help="Output path (default: 06-backend/openapi/schema.json). '-' writes to stdout.",
        )

    def handle(self, *args, **options):
        # Import here so the command fails loudly and legibly if the schema
        # stack is absent, instead of breaking every manage.py invocation.
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        # sort_keys + fixed separators: byte-stable output — the CI diff must
        # only ever show real contract drift, never serialization noise.
        payload = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        out = options["out"]
        if out == "-":
            self.stdout.write(payload)
            return
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        self.stdout.write(f"OpenAPI schema written to {out_path}")
