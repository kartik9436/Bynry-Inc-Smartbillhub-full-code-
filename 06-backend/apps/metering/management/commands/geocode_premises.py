# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W5 T3 (§10-D6 — the geocoder's LIVE path)
# Rules:    §10-D6 (accepted third-party geocoding; the selection and its
#           worked address are recorded in apps/metering/geocode.py) ·
#           CLAUDE.md rule 1 (tenant context — a Postgres GUC, so this
#           refuses off postgres exactly as load_sample_data does)
# Tests:    06-backend/tests/test_cr028_new_tabs.py (the batch function with a
#           stubbed transport; the sqlite refusal)
# Impacts:  apps/metering/geocode.py (all logic lives there — this file only
#           resolves the tenant and reports)
# ───────────────────────────────────────────────────────
"""`geocode_premises --tenant <subdomain>` — fill missing premises coordinates.

THE LIVE PATH of the §10-D6 geocoder: iterates the tenant's premises that
have NO coordinates yet, asks the US Census Bureau geocoder for each (see
apps/metering/geocode.py for the selection record and its worked address),
and writes lat/lng. Idempotent — a filled row is never re-asked and NEVER
overwritten; failures are printed BY NAME so an operator can fix the address
or set the pin by hand.

It talks to the network on purpose (that is its whole job) and it is the ONLY
thing in the product that does for geocoding: the sample seed writes
deterministic offline coordinates, and no request-path code ever geocodes.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from apps.metering import geocode
from core import tenancy as core_tenancy


class Command(BaseCommand):
    help = (
        "Geocode every premises of a tenant that has no coordinates yet, via "
        "the US Census Bureau geocoder (free, no key, US addresses). "
        "Idempotent; never overwrites a set coordinate; names its failures."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            required=True,
            help="the tenant's subdomain, e.g. silver-creek-water",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            # Tenant context is a Postgres GUC (core/tenancy.py) — the same
            # refusal load_sample_data makes, for the same reason: on sqlite
            # the write would run with no tenant scoping at all.
            raise CommandError(
                "geocoding needs PostgreSQL — tenant context is set with "
                "set_config('app.tenant_id', …) and sqlite cannot run it "
                "(CLAUDE.md rule 1). Nothing was written."
            )
        from apps.tenancy import models as tenancy_models

        subdomain = str(options["tenant"]).strip()
        try:
            tenant = tenancy_models.Tenant.objects.filter(subdomain=subdomain).first()
        except DatabaseError as exc:  # pragma: no cover - surfaced, never swallowed
            raise CommandError(f"could not read tenants: {exc}") from exc
        if tenant is None:
            raise CommandError(f"no tenant with subdomain {subdomain!r}. Nothing was written.")
        with core_tenancy.tenant_context(str(tenant.id)):
            summary = geocode.geocode_missing()
        self.stdout.write(self.style.SUCCESS(f"  {summary['filled']} premises geocoded"))
        for name in summary["failed"]:
            # BR-TEN-060's posture: a row that did not fill is a NAMED line.
            self.stdout.write(self.style.WARNING(f"  NOT geocoded: {name} — no match returned"))
        if not summary["failed"]:
            self.stdout.write(self.style.SUCCESS("  every missing premises resolved"))


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 §4.6 + §10-D6 (AST-W5 T3)
# generated: 2026-08-22 by the CR-028 AST-W5 lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr028_new_tabs.py::test_w5_t3__the_command_refuses_off_postgres
# exceptions: refuses off postgres (the load_sample_data posture) — the batch function itself is the tested surface, under tenant_ctx with a stubbed transport
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
