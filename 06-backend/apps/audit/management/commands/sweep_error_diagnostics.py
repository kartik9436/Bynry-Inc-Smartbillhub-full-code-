# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 task A5 — "Retention sweep, defaulting to 90 days and
#           configurable. Done when: an expired record is gone and its audit row
#           still reads correctly without it."
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — the sweep enters each
#           tenant's context; the table is under FORCE ROW LEVEL SECURITY) ·
#           BR-TEN-074 (per-tenant context, failures isolated) · BR-AUD-002
#           (the audit rows these belonged to are NOT touched)
# Tests:    06-backend/tests/test_cr067_diagnostics.py
# ───────────────────────────────────────────────────────
"""`manage.py sweep_error_diagnostics` — prune the technical half, keep the trail.

WHAT IT REMOVES AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------
It deletes `error_diagnostics` rows past their own stamped `expires_at`, one
tenant at a time. **It touches no `audit_log` row, ever.** That is the whole
shape of CR-067: the permanent row keeps saying *"this failed, and here is why
in plain words"*, with its stable code, its fixed catalogue sentence and its
reference; what expires is the detail that could carry a value.

WHY THE ENUMERATION IS HERE AND THE DELETING IS NOT
-----------------------------------------------------
`apps/audit/diagnostics.sweep_expired()` takes the tenant ids as a parameter and
reads no registry, so the audit module never reaches into the table `apps.tenancy`
owns. This command does that read — the same place `sweep_reference_data` and
`geocode_premises` put theirs.

`--dry-run` reports and deletes nothing; it always exits 0, because refusing to
report was never the point.

EXIT CODES
----------
  0  the sweep ran (or had nothing to do) and every targeted tenant succeeded
  1  refused before any tenant was touched — an unknown `--tenant`
  2  the sweep RAN and at least one tenant FAILED; the failures are named and
     the tenants that succeeded keep their result (BR-TEN-074)
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.audit import diagnostics
from apps.tenancy import models
from core import diagnostics as diagnostics_kernel


class Command(BaseCommand):
    help = (
        "Delete error diagnostics past their retention (DIAGNOSTIC_RETENTION_DAYS, "
        "default 90). The audit rows they were referenced from are untouched and "
        "still read correctly without them."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            dest="subdomain",
            default=None,
            help="Sweep one tenant by subdomain. Default: every tenant.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be removed and remove nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options.get("subdomain")
        tenants = models.Tenant.objects.all().order_by("subdomain")
        if subdomain:
            tenants = tenants.filter(subdomain=subdomain)
            if not tenants.exists():
                raise CommandError(f"no tenant with subdomain {subdomain!r}")
        result = diagnostics.sweep_expired(
            [tenant.id for tenant in tenants], dry_run=bool(options.get("dry_run"))
        )
        verb = "would remove" if result["dry_run"] else "removed"
        self.stdout.write(
            f"{verb} {result['removed']} diagnostic record(s) older than "
            f"{diagnostics_kernel.retention_days()} days, across "
            f"{len(result['by_tenant'])} tenant(s). No audit row was touched."
        )
        if result["failed"]:
            for tenant_id, kind in result["failed"].items():
                self.stderr.write(f"tenant {tenant_id} failed: {kind}")
            raise CommandError(
                f"{len(result['failed'])} tenant(s) failed; the rest were swept",
                returncode=2,
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 task A5 (12-governance/11-change-requests.md) + BR-TEN-074 + 06-backend/apps/tenancy/management/commands/sweep_reference_data.py (the per-tenant sweep precedent this follows)
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B=deferred(a management command draws nothing) C✔ D=deferred(no endpoint) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: (1) it writes NO audit row (see apps/audit/diagnostics.sweep_expired and the decision-log row). (2) it is NOT scheduled by this lane — wiring it to beat alongside the partition jobs is reported, not done, because a schedule is a deployment decision and OQ-1390 may still move the window.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
