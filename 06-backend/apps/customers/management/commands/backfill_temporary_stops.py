"""`manage.py backfill_temporary_stops [--dry-run]` — DEF-CUS-10161.

Gives every OPEN portal *stop my service* request raised before 2.580.0 the
temporary-stop row the portal has written since then, so it reads *Temporary
stop* and its Approve window works. `customers/0086` runs this once on upgrade;
this command is the SAME function (`temporary_stop_backfill.backfill_all_tenants`),
so the two cannot disagree, and it is safe to run any number of times — a
request that already has its row is not touched.

A request whose sentence cannot be read, or that names an account this utility
does not hold, is left exactly as it is and named in the output, for a clerk.
`--dry-run` counts and names without writing.
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.customers import temporary_stop_backfill


class Command(BaseCommand):
    help = "Give pre-2.580 portal stop-service requests their temporary-stop row (DEF-CUS-10161)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count and name what would be written, and write nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        report = temporary_stop_backfill.backfill_all_tenants(dry_run=options["dry_run"])
        prefix = "DRY RUN — nothing written. " if options["dry_run"] else ""
        self.stdout.write(
            f"{prefix}{report['tenants']} utility(ies) checked. "
            + temporary_stop_backfill.summary(report)
        )
