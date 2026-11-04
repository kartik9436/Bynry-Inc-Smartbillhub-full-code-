# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-020 (metering — the 2-yr hot → cold job, "never manual") ·
#           US-AUD-007 (audit — the same job over `audit_log`, self-audited)
#           Screens: — (scheduler-only; the UI touchpoints are the S25/S61
#           archive opt-ins, which READ what this writes)
# Rules:    BR-MET-055 · BR-AUD-012 (AUTOMATIC scheduled job, never manual,
#           audited; 2 yr hot, 7 yr total) · BR-AUD-002 (moves partitions,
#           never mutates rows) · NFR-25 (financial tables never pruned)
# Tests:    06-backend/tests/test_us_met_020_tc_archival.py ·
#           06-backend/tests/test_us_aud_007_tc_archival.py
# Impacts:  09-infra scheduler (celery-beat wiring, TD-17 — see below) ·
#           core/archival.py (the law) · apps/audit `archive_job_runs`
# ───────────────────────────────────────────────────────
"""`manage.py archive_partitions` — the ONLY entry point archival has.

BR-MET-055 and BR-AUD-012 both say the same three words: **never manual.** That
is why this command is the whole surface. There is no API endpoint, no service
function, no BE-07 job kind and no admin action for archival anywhere in this
codebase, and `core.archival.run_archival` refuses any caller that does not hold
the scheduler token this command holds (US-MET-020 TC-4 / US-AUD-007 TC-4).

"But a human can run a management command." Yes — and that is the same hand
that edits the crontab, i.e. the operator, not a product user. What the rule
forbids is a PRODUCT path: a button, an endpoint, a support tool that lets
archival be triggered, skipped or brought forward for one tenant. None exists,
and `--dry-run` below is the only thing a curious operator is offered.

SCHEDULE: monthly, 1st, 02:00 UTC (US-MET-020 §4 / US-AUD-007 §4). celery-beat
wiring lands with TD-17, exactly as `maintain_partitions` records for itself;
until then ops run this from the deploy runbook (09-infra). Both commands are
idempotent, so running them in either order, twice, changes nothing.

WHAT A RUN DOES, in the order the law states it:
  1. detach every partition of `meter_reads` and `audit_log` that is FULLY
     older than the 2-year hot window, with a row count and SHA-256 manifest;
  2. purge — DROP — already-detached partitions past the 7-year total bound;
  3. record the run in `archive_job_runs` and write one `audit_log` row per
     affected tenant for each partition touched.
Re-firing on the same day is a recorded no-op, never a second detachment and
never an error (US-MET-020 TC-5 / US-AUD-007 TC-5).
"""

from datetime import date

from django.core.management.base import BaseCommand

from core import archival


class Command(BaseCommand):
    help = "Retention job: detach partitions past the 2-year hot window; purge past 7 years."

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what WOULD be detached and purged; touch nothing.",
        )
        parser.add_argument(
            "--as-of",
            default=None,
            help="ISO date to plan against (testing/backfill). Defaults to today.",
        )

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        today = date.fromisoformat(options["as_of"]) if options.get("as_of") else date.today()
        self.stdout.write(
            f"retention: {archival.HOT_WINDOW_MONTHS} months hot, "
            f"{archival.RETENTION_YEARS} years total (BR-MET-055 / BR-AUD-012)"
        )
        for table in archival.ARCHIVED_TABLES:
            if options.get("dry_run"):
                self._plan(table, today)
                continue
            run = archival.run_archival(table, today, invoked_by=archival.SCHEDULER)
            if run.status != "success":
                self.stdout.write(f"{table}: {run.status} — {run.note}")
                continue
            archived = ", ".join(entry["partition"] for entry in run.archived) or "nothing"
            purged = ", ".join(entry["partition"] for entry in run.purged) or "nothing"
            self.stdout.write(f"{table}: detached {archived}; purged {purged}")

    def _plan(self, table: str, today: date) -> None:
        """--dry-run: the candidates, from the same planner the run uses."""
        from core import partitioning

        attached = partitioning.partition_children(table)
        detached = archival.detached_partitions(table)
        self.stdout.write(
            f"{table}: would detach {archival.archivable(table, today, attached) or 'nothing'}; "
            f"would purge {archival.purgeable(table, today, detached) or 'nothing'}"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-020@f4a1c02 (EP-MET-03 archival story; co-packet US-AUD-007@6b3d915 — EP-AUD-03)
# generated: 2026-08-15 by story-coder v1 (metering + assets + audit lane)
# checklist: A✔ B✔ C✔ D=deferred(no API by law — BR-MET-055 "never manual") E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ · pytest tests/test_us_met_020_tc_archival.py tests/test_us_aud_007_tc_archival.py✔
# exceptions: the command lives under apps/audit/management because that app already hosts maintain_partitions and `archive_job_runs`; it archives METERING's partitions too, which is a platform storage op and NOT a cross-module write (it touches no metering ROW and no metering model — see core/archival.py) · celery-beat scheduling is still TD-17, unchanged by this lane and REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
