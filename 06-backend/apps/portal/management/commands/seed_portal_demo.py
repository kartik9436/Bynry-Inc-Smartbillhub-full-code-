# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 · US-CWP-069 · US-CWP-070 §4 — the portal fixture on a
#           running database, for the wave's browser walkthrough.
# Rules:    10-execution-plan.md wave A task A7 (the fixture) · A8 (the
#           walkthrough runs against a database nobody else is seeding)
# Tests:    10-scripts/render-checks/cr068-a-switch-it-on.mjs (the consumer)
# Impacts:  apps/portal/sample_data.py
# ───────────────────────────────────────────────────────
"""seed_portal_demo — provision Pine Hill Water & Power and Oak Ridge, switch
Pine Hill's portal on, **and plant the sample data**, through the real services.

    DATABASE_URL=… python manage.py seed_portal_demo

PostgreSQL only, like `seed_demo`: tenant context is a PostgreSQL GUC and
the RLS-forced tables refuse a write without it. Idempotent — a replay
re-saves the same values and provisions nothing twice.

⚠ **THE SAMPLE DATA USED TO BE ENQUEUED AND NEVER RAN, AND THAT IS WHY EVERY
SCREEN BUILT ON IT OPENED EMPTY (`DEF-CWP-3779`).** Provisioning enqueues
`tenancy.sample_data_plant` for a Celery worker. No worker runs beside this
command, so the job stayed queued and the log said so once, at INFO, in the
middle of a successful-looking run:

    celery: could not dispatch job … (tenancy.sample_data_plant) — the record
    stays queued and is picked up by the next worker that sees it, or by
    `manage.py run_pending_jobs`

**Both halves of that sentence were false here.** No worker was coming, and
`run_pending_jobs` **does not exist in this repository** — the message names a
recovery nobody built (hard-won law 1: a comment claiming a guarantee is not
the guarantee). So a lane would seed the demo, open `CWP-033`, find no usage,
and reasonably conclude the screen was broken.

**A demo command is run by a person at a terminal, so it plants the data
itself** — `tenancy.sample_data.seed_sample_data` is the same function the job
body calls, block by block through each module's own published seeder: plans,
premises, units, meters, accounts, customers, **meter reads**, bills and
payments. `--no-sample-data` skips it for the rare caller that wants only the
two tenants.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.portal import sample_data
from apps.tenancy import sample_data as tenancy_sample_data
from core.tenancy import tenant_context


class Command(BaseCommand):
    help = "Provision the customer-portal demo utilities (Pine Hill, Oak Ridge), switch the portal on, and plant the sample data."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--no-sample-data",
            action="store_true",
            help="provision the tenants only — no plans, meters, reads, bills or payments",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError(
                "seed_portal_demo needs PostgreSQL — tenant context is a GUC and the "
                "portal's tables are RLS-forced; nothing was written."
            )
        import uuid

        plant = not options.get("no_sample_data")
        #: ⚠ **WAVE C's PRICED STREET IS HELD BACK WHEN WE ARE ALSO PLANTING —
        #: `DEF-CWP-3927`, AND IT IS WHY THIS DEMO COULD NOT SHOW A BILL.**
        #: That step mints a base charge code for water, sewer and trash so its
        #: quote plan can publish; the sample plant mints `BASE-W`/`BASE-S`/
        #: `BASE-T` for the same three. Neither is scoped to a customer class,
        #: so both claim every account and the bill run refuses all of them —
        #: *"2 charge codes declare themselves the base"*. Seeded AFTER, the
        #: portal fixture finds the standard base and reuses it.
        rows = sample_data.seed_portal_fixture(with_priced_addresses=not plant)
        for row in rows:
            self.stdout.write(f"  {row['subdomain']}  {row['id']}")

        if not plant:
            self.stdout.write(self.style.WARNING("sample data SKIPPED — the portal screens will be empty"))
        else:
            for row in rows:
                tenant_id = uuid.UUID(row["id"])
                with tenant_context(tenant_id):
                    actor = sample_data._owner_actor(tenant_id, row["owner_email"])
                    #: The same function the queued job body calls — see the
                    #: module docstring for why it is called here instead.
                    summary = tenancy_sample_data.seed_sample_data(actor)
                planted = summary.get("blocks") if isinstance(summary, dict) else None
                self.stdout.write(f"  {row['subdomain']}  sample data: {len(planted or [])} block(s)")
            #: Now wave C's prices, on top of the planted estate.
            pine = rows[0]
            tenant_id = uuid.UUID(pine["id"])
            with tenant_context(tenant_id):
                actor = sample_data._owner_actor(tenant_id, pine["owner_email"])
                if sample_data.PINE_HILL.get("priced_addresses"):
                    sample_data.seed_priced_addresses(actor)
            self.stdout.write(f"  {pine['subdomain']}  wave C prices seeded after the plant")
            #: ⚠ **CR-068 WAVE H — AND IT RUNS LAST FOR A REASON.** The reads
            #: below hang off a meter at `1408 Elm St · A`, and that unit does
            #: not exist until `seed_priced_addresses` above has run. Ordered
            #: any earlier this plants nothing and says so politely, which is
            #: the quietest kind of broken fixture.
            with tenant_context(tenant_id):
                actor = sample_data._owner_actor(tenant_id, pine["owner_email"])
                usage = sample_data.seed_usage_and_equipment(actor)
            if usage.get("seeded"):
                self.stdout.write(
                    f"  {pine['subdomain']}  wave H: {usage['reads_posted']} read(s), "
                    f"{usage['assets_created']} asset(s) on {usage['account_no']}"
                    + (", June corrected" if usage.get("june_corrected") else "")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"  {pine['subdomain']}  wave H SKIPPED — {usage.get('why')}")
                )

        self.stdout.write(self.style.SUCCESS("portal fixture seeded: pine-hill (live), oak-ridge (live)"))
