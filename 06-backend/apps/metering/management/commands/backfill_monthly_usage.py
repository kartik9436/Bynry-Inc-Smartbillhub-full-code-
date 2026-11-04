# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-871 (nothing recomputed monthly usage when a read was
#           committed — the writer's only non-test caller was the seeder, so
#           the stored table was EMPTY on every real tenant and the S21 Usage
#           tab, the portal home usage tile and the portal Usage screen all
#           drew nothing)
# Rules:    BR-MET-106 (a month's usage is computed from reads, STORED,
#           RESTATED never edited, ABSENT when unread — PO 2026-08-24) ·
#           BR-MET-141 (the same figure per meter and register; both grains
#           move on ONE recompute_account call — PO 2026-08-27) ·
#           CLAUDE.md rule 1 (tenant context is a Postgres GUC) · rule 6
#           (idempotency — the content fingerprint) · rule 7 (audit)
# Questions: OQ-358 (a month whose reads disagree about the unit) — counted and
#           NAMED here, never guessed. OQ-690 (what the caller does with that
#           refusal) — CLOSED 2026-09-05.
# Tests:    06-backend/tests/test_def871_usage_trigger.py
# Impacts:  apps/metering/monthly_usage_service.backfill_tenant (all the logic;
#           this file only resolves the tenant and reports)
# ───────────────────────────────────────────────────────
"""`manage.py backfill_monthly_usage --tenant <subdomain>` — state the months
that were already on file before the recompute trigger existed.

WHY THIS COMMAND EXISTS
-----------------------
`DEF-871`: for nine days nothing called `monthly_usage_service.recompute_account`
outside the sample-data seeder, so on every real tenant the stored monthly-usage
table was EMPTY however many readings had posted. Wiring the trigger into the
read commit fixes readings posted **from now on** and does nothing for the ones
already on file — and an existing customer has months of them. This is the other
half of that fix, and without it the customers who have used the product longest
are exactly the ones whose charts stay blank.

RUN IT ONCE PER TENANT AFTER DEPLOYING THE TRIGGER.

IT IS SAFE TO RUN TWICE
-----------------------
The writer is idempotent by CONTENT (CLAUDE.md rule 6): a month whose reads have
not changed matches its stored fingerprint, so nothing is written and nothing is
audited. A second run over a healthy tenant reports `unchanged: N` and writes
zero rows. `--dry-run` computes the same figures inside a transaction it then
unwinds, so it tells you what a real run would do without leaving anything
behind.

WHAT IT REFUSES TO GUESS
------------------------
`OQ-358` — one account, one service, one month, two units — has no answer yet.
Such a month is LEFT exactly as it was and is NAMED in the report; the command
never picks a unit and never converts. Every other month of the same account
still states, which is the grain `BR-MET-940` sets (*"we accept what is correct
and rejct what i not correct"*).
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from apps.metering import monthly_usage_service
from core import tenancy as core_tenancy


class Command(BaseCommand):
    help = (
        "State the stored monthly usage for every account of a tenant that has "
        "meter reads (DEF-871 backfill). Idempotent; names the months it could "
        "not state rather than guessing a unit."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            help="the tenant's subdomain, e.g. silver-creek-water1",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="every tenant in the database, one after another",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="compute and report, then roll the whole thing back",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            # The same refusal `geocode_premises` and `load_sample_data` make,
            # for the same reason: tenant context is `set_config('app.tenant_id')`
            # and sqlite cannot run it, so the walk would be unscoped
            # (CLAUDE.md hard rule 1). `backfill_tenant` itself is the tested
            # surface and runs under `tenant_ctx` in the suite.
            raise CommandError(
                "backfill_monthly_usage needs PostgreSQL — tenant context is a "
                "GUC and sqlite cannot set one (CLAUDE.md rule 1). "
                "Nothing was written."
            )
        from apps.tenancy import models as tenancy_models

        subdomain = (options.get("tenant") or "").strip()
        every = bool(options.get("all_tenants"))
        if bool(subdomain) == every:
            raise CommandError("give exactly one of --tenant <subdomain> or --all-tenants.")

        try:
            qs = tenancy_models.Tenant.objects.all().order_by("subdomain")
            tenants = list(qs) if every else list(qs.filter(subdomain=subdomain))
        except DatabaseError as exc:  # pragma: no cover — surfaced, never swallowed
            raise CommandError(f"could not read tenants: {exc}") from exc
        if not tenants:
            raise CommandError(
                f"no tenant with subdomain {subdomain!r}. Nothing was written."
                if subdomain
                else "no tenants in this database. Nothing was written."
            )

        dry = bool(options.get("dry_run"))
        grand = {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0, "held": 0}
        for tenant in tenants:
            self.stdout.write(f"── {tenant.subdomain} ──")
            with core_tenancy.tenant_context(str(tenant.id)):
                report = monthly_usage_service.backfill_tenant(dry_run=dry)
            self.stdout.write(
                f"  {report['accounts']} accounts with reads · "
                f"stated {report['stated']} · restated {report['restated']} · "
                f"unchanged {report['unchanged']} · withdrawn {report['withdrawn']}"
            )
            for k in ("stated", "restated", "unchanged", "withdrawn"):
                grand[k] += report[k]
            grand["held"] += report["months_not_restated"]

            # BR-TEN-060's posture, and hard-won law 1: a month that did not
            # state is a NAMED line, not a number in a summary somebody has to
            # go and interpret.
            for row in report["months_not_restated_rows"]:
                where = row["service_id"] or f"{row['asset_id']}/{row['register']}"
                self.stdout.write(
                    self.style.WARNING(
                        f"  NOT stated: account {row['account_id']} · {where} · "
                        f"{row['month']} — its reads disagree about the unit "
                        f"({row['question']}); the month keeps what it said before"
                    )
                )
            for fault in report["faults"]:
                self.stdout.write(
                    self.style.ERROR(
                        f"  FAILED: account {fault['account_id']} — {fault['reason']}"
                    )
                )

        tail = " (DRY RUN — everything above was rolled back)" if dry else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{grand['stated']} months stated, {grand['restated']} restated, "
                f"{grand['unchanged']} already current, {grand['withdrawn']} withdrawn, "
                f"{grand['held']} left alone for OQ-358{tail}"
            )
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-871 / OQ-690 (closed 2026-09-05) — the recompute trigger + backfill
# generated: 2026-09-05 by the metering usage lane
# checklist: A✔ B=n/a(no screen — an operator command) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_def871_usage_trigger.py
# exceptions: refuses off postgres (the geocode_premises posture) — backfill_tenant is the tested surface, under tenant_ctx
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
