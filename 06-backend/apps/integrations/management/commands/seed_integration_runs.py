# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 §4 · US-INT-021 §4 — the run fixture the wave C
#           walkthrough clicks, on a running database.
# Rules:    10-execution-plan.md wave C task C4 (the seed) · C5 (the
#           walkthrough runs against a database nobody else is seeding) ·
#           CLAUDE.md hard rule 1 (tenant context is a PostgreSQL GUC)
# Tests:    10-scripts/render-checks/cr069-c-run-record.mjs (the consumer)
# Impacts:  apps/integrations/sample_runs.py
# ───────────────────────────────────────────────────────
"""seed_integration_runs — Brazos Bend's Billing mailbox, and its four runs.

    DATABASE_URL=… python manage.py seed_integration_runs [--tenant brazosbend]

It connects the `email_smtp` provider for the tenant if it is not connected
(status `untested` — no adapter is registered in this release, so nothing is
claimed about whether it works) and writes the four runs through the real
services, so the outcome words are COMPUTED and never typed.

PostgreSQL only, like `seed_demo` and `seed_portal_demo`: tenant context is a
GUC and these tables are RLS-forced. Idempotent — `integration_run` is
append-only, so a replay that found the fixture's trace id writes nothing at
all rather than pretending to correct it.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection as db_connection

from apps.integrations import models, sample_runs
from core.tenancy import tenant_context, tenant_id_for_slug

PROVIDER = "email_smtp"


class Command(BaseCommand):
    help = "Seed the Billing mailbox's four runs (US-INT-020 §4) for the wave C walkthrough."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")

    def handle(self, *args: Any, **options: Any) -> None:
        if db_connection.vendor != "postgresql":
            raise CommandError(
                "seed_integration_runs needs PostgreSQL — tenant context is a GUC and "
                "integration_run is RLS-forced and partitioned; nothing was written."
            )
        subdomain = options["tenant"]
        # ⚠ THE SLUG IS RESOLVED THROUGH `core.tenancy`'S REGISTERED SEAM, NOT
        # BY IMPORTING `apps.tenancy.models`. `apps.tenancy` owns the tenants
        # table (B1) and registers the lookup at startup; a cross-module import
        # of another app's models is what B2 §2 forbids and G6 refuses.
        tenant_id = tenant_id_for_slug(subdomain)
        if tenant_id is None:
            raise CommandError(f"no tenant with subdomain {subdomain!r} — run seed_demo first.")
        with tenant_context(tenant_id):
            conn, created = models.IntegrationConnection.objects.get_or_create(
                tenant_id=tenant_id,
                provider_key=PROVIDER,
                environment=models.ENVIRONMENT_PRODUCTION,
                defaults={
                    "label": "billing@brazosbend.example",
                    "status": models.STATUS_UNTESTED,
                    "enabled": True,
                    "cadence": models.CADENCE_MANUAL,
                    "config": {
                        "host": "mail.brazosbend.example",
                        "port": "587",
                        "username": "billing@brazosbend.example",
                        "send_from": "billing@brazosbend.example",
                    },
                },
            )
            written = sample_runs.seed_runs(conn)
        if not written:
            self.stdout.write(
                self.style.WARNING(
                    f"  already seeded — support reference {sample_runs.DEMO_TRACE} is "
                    "present; runs are append-only and nothing was written."
                )
            )
            return
        self.stdout.write(f"  connection {'created' if created else 'reused'}: {PROVIDER}")
        for run in written:
            self.stdout.write(
                f"  {run.started_at:%Y-%m-%d %H:%M}  {run.outcome:<12} "
                f"{run.succeeded} of {run.attempted}  {run.trace_id}"
            )
        self.stdout.write(
            self.style.SUCCESS(f"{len(written)} runs seeded for {subdomain}; support reference {sample_runs.DEMO_TRACE}")
        )
