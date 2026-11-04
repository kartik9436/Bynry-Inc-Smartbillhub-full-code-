"""BE-10 — the partition create-ahead job (NFR-24/28; B2 §5: pre-create ahead).

`python manage.py maintain_partitions` ensures, idempotently, that every ACTIVE
table in the NFR-24 registry has the partitions it needs: the current period
plus the runway its registry entry asks for. Two granularities since the PO
ruling of 2026-08-12 ("Nod to split both by year", OQ-107) — `audit_log` and
`meter_reads` are MONTHLY with 3 months ahead, `invoice_lines` and
`journal_lines` are YEARLY with 1 year ahead. Platform DDL: no tenant context is
involved.

⚠ THIS DOCSTRING USED TO END THAT PARAGRAPH WITH *"RLS on the parent keeps
queries tenant-scoped regardless of partition."* That was measured FALSE on the
live cluster on 2026-08-10 (DEF-027) and it is corrected here in the past tense
rather than deleted: a partition queried DIRECTLY consults only its OWN
policies, so `core.partitioning.create_partition_sql` emits the B2 §3 tenant
policy in the same statement batch as the CREATE, and this job also REPAIRS any
partition it finds unguarded.

Scheduling: celery-beat wiring lands with the jobs-table story (TD-17); until
then ops/CI run this command directly (deploy runbook, 09-infra).

Pruning posture (NFR-25 — the contract, stated where the operator looks):
nothing is EVER dropped here or anywhere; financial tables are never pruned;
past the 2-year hot window partitions become DETACH candidates only, and the
DETACH execution belongs to the EP-AUD-03 archival story with its cold-storage
target. This command only reports candidates.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import connection

from core import partitioning


class Command(BaseCommand):
    help = "Create-ahead partitions (current period + runway) for the active NFR-24 tables."

    def handle(self, *args, **options):
        today = date.today()
        for table in sorted(partitioning.ACTIVE_TABLES):
            names = partitioning.ensure_partitions(table, today)
            if connection.vendor == "postgresql":
                self.stdout.write(f"{table}: ensured {', '.join(names)}")
            else:
                self.stdout.write(
                    f"{table}: non-Postgres vendor — no partition DDL (plain table); "
                    f"would ensure {', '.join(names)}"
                )
