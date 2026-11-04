# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 §4 Test Data — the `gis_city` connection for Brazos Bend
#           (*"address service https://gis.brazosbend.example/addr, tile server
#           https://tiles.brazosbend.example (city-run — R-7's case)"*), and
#           CR-069 wave M task M1's *"connection records for the two live calls
#           that have none"*
# Rules:    BR-INT-048 · BR-INT-037 · CR-069 wave M
# Tests:    10-scripts/render-checks/cr069-m-address-search.mjs (the consumer)
# Impacts:  apps/integrations/live_calls.py · apps/integrations/gis_fixtures.py
# ───────────────────────────────────────────────────────
"""seed_gis_city — the City connection the wave M walkthrough clicks.

    DATABASE_URL=… python manage.py seed_gis_city [--tenant brazosbend] [--slow]

Three things, on a running database:

1. **The two live calls get their connection rows** (`DEF-INT-4251`,
   `DEF-INT-4252`) — the Census geocoder and the public map tiles, at the
   addresses the product is already using, through `live_calls.provision`.
2. **`gis_city` is connected** at `US-INT-042` §4's own address. ⚠ The host is
   a `.example` name, which RFC 2606 reserves so it can never resolve — the
   recorded City in `gis_fixtures.py` serves it, and only names ending that
   way, so this can never stand in front of a real city.
3. **`--slow` points it at the four-second City** instead of the 300 ms one, so
   a walkthrough proves the breaker branch by editing a connection rather than
   by restarting anything. That is the same affordance `payments_sandbox`'s
   `behaviour` field is, for the same reason: *"the product's real refusal path
   runs"*.

⚠ **`--slow` REWRITES ONLY `base_url` AND CLEARS ONLY THE BREAKER.** It is a
walkthrough switch, and a switch that reset anything else would be a fixture
quietly editing a utility's connection.

PostgreSQL only, like every other seed command here: tenant context is a GUC
and these tables are RLS-forced.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection as db_connection

from apps.integrations import gis_fixtures, live_calls, models, runtime
from core.tenancy import tenant_context, tenant_id_for_slug

#: ⚠ `gis_city` until `CR-110-BRC04`; connector 25 is **Esri ArcGIS**. The
#: command's own name is left alone — renaming a management command breaks
#: every runbook, walkthrough and note that types it.
PROVIDER = "gis_esri"

#: `US-INT-042` §4 — the city-run tile server, which is `R-7`'s case: a city
#: that runs its own map server points the same operation at the body that
#: already owns the data, and the generated policy follows it.
CITY_TILE_HOST = "https://tiles.brazosbend.example"


class _Seeder:
    """The acting user for `services.connect`'s role gate.

    ⚠ **`role`, NOT `tenant_role`, AND NOT THE DISPLAY NAME.**
    `core.permissions.require_role` reads `actor.role` and compares it with
    A4's own constants (`system_admin`), so a seeder declaring `tenant_role =
    "System Admin"` is refused `AUTH-002` — which reads, from a command line,
    exactly like a broken database. Found by running the command.
    """

    id = None
    role = "system_admin"


class Command(BaseCommand):
    help = "Connect City GIS and the two live calls for the wave M walkthrough."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
        parser.add_argument(
            "--slow",
            action="store_true",
            help="point City GIS at the 4,000 ms recording instead of the 300 ms one",
        )
        parser.add_argument(
            "--city-tiles",
            action="store_true",
            help="point the tile connection at the CITY's own server (R-7) instead of Esri",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if db_connection.vendor != "postgresql":
            raise CommandError(
                "seed_gis_city needs PostgreSQL — tenant context is a GUC and these "
                "tables are RLS-forced; nothing was written."
            )
        subdomain = options["tenant"]
        tenant_id = tenant_id_for_slug(subdomain)
        if tenant_id is None:
            raise CommandError(f"no tenant with subdomain {subdomain!r} — run seed_demo first.")
        host = gis_fixtures.SLOW_HOST if options["slow"] else gis_fixtures.FAST_HOST
        base_url = f"https://{host}/addr"

        with tenant_context(tenant_id):
            done = live_calls.provision(_Seeder(), tenant_id)
            for key, what in sorted(done.items()):
                self.stdout.write(f"  {key:<20} {what}")

            row, created = models.IntegrationConnection.objects.get_or_create(
                tenant_id=tenant_id,
                provider_key=PROVIDER,
                environment=models.ENVIRONMENT_PRODUCTION,
                defaults={
                    "label": "City of Brazos Bend",
                    "status": models.STATUS_UNTESTED,
                    "enabled": True,
                    "cadence": models.CADENCE_NIGHTLY,
                    "config": {"base_url": base_url},
                },
            )
            config = dict(row.config or {})
            if config.get("base_url") != base_url:
                config["base_url"] = base_url
                # A fresh City is a City nobody has failed to reach yet.
                config.pop(runtime.BREAKER_KEY, None)
                row.config = config
                row.status = models.STATUS_UNTESTED
                row.last_test_ok = None
                row.last_test_text = None
                row.save(
                    update_fields=[
                        "config", "status", "last_test_ok", "last_test_text", "updated_at"
                    ]
                )
            self.stdout.write(f"  {PROVIDER:<20} {'created' if created else 'pointed'} → {base_url}")

            if options["city_tiles"]:
                tiles = models.IntegrationConnection.objects.filter(
                    tenant_id=tenant_id, provider_key="map_tiles_public"
                ).first()
                if tiles is not None:
                    tiles.config = {**dict(tiles.config or {}), "base_url": CITY_TILE_HOST}
                    tiles.save(update_fields=["config", "updated_at"])
                    self.stdout.write(f"  map_tiles_public     → {CITY_TILE_HOST} (R-7)")

        self.stdout.write(
            self.style.SUCCESS(
                f"City GIS ready for {subdomain} — "
                f"{'4,000 ms' if options['slow'] else '300 ms'} recording"
            )
        )
