# ── Trace ──────────────────────────────────────────────
# Change:   CR-172-BRC10 — the utility logo moves into the common document store.
# Tests:    06-backend/tests/test_cr172_logo_document_store.py
# ───────────────────────────────────────────────────────
"""`manage.py move_logos_to_store [--back]` — finish, or undo, the logo move.

`tenancy/0061` moves every logo it can when it runs. A utility whose logo could
not be stored then (storage down, or a copy that did not match) keeps its bytes
on its row and goes on drawing from there; running this once storage is back
finishes the job. It is the SAME function the migration runs
(`services.move_logos_to_store`), so the two cannot disagree, and it is safe to
run any number of times.

`--back` is the rollback: it copies every stored logo's bytes back onto its row
and restores the `sha256:` reference the previous build reads, so the previous
build can be deployed on this schema. Nothing is deleted from the store.
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.tenancy import services


class Command(BaseCommand):
    help = "Move logos held on tenant rows into the document store (or --back to undo)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--back",
            action="store_true",
            help="Copy every stored logo's bytes back onto its row (the rollback).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["back"]:
            report = services.move_logos_back_to_rows()
            self.stdout.write(
                f"logos: {report['restored']} copied back onto their rows, {report['skipped']} already there"
            )
            return
        report = services.move_logos_to_store()
        self.stdout.write(
            f"logos: {report['moved']} moved to the document store, {report['already']} already there, "
            f"{report['left']} left on the row"
        )
        if report["left"]:
            self.stdout.write("the logos left on the row still draw from it; run this again when storage is available")
