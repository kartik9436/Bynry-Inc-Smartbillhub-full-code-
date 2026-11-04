# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) / CR-069 wave M task M1 — *"`map_tiles_public`
#           and `geocoder_census` gain connection records and health"*
# Defects:  DEF-INT-4251 (the Census geocoder is a live third-party call with no
#           connection record) · DEF-INT-4252 (the Esri map tiles are a live
#           third-party call with no connection record) — both filed 2026-09-06
#           by this lane, before the fix, per CR-069 §0.3: *"putting them on the
#           substrate is a gap in what we built, filed as a defect row, not a
#           new requirement"*
# Rules:    BR-INT-039 (every attempt is a durable record with a trace id) ·
#           BR-INT-048 (a browser-executed operation carries no tenant secret) ·
#           BR-INT-037 (data, not code) · CR-028 D6 (the geocoder keeps its
#           fill-empties-only rule — unchanged by this file)
# Tests:    06-backend/tests/test_us_int_042_gis.py
# Impacts:  apps/integrations/page_policy.py (the tile host it puts in the CSP
#           comes from the row this creates) · features/assets/AssetMapTab.tsx
#           (reads the same host) · management/commands/seed_gis_city.py
# ───────────────────────────────────────────────────────
"""THE TWO CALLS THE PRODUCT ALREADY MAKES, GIVEN A ROW TO LIVE ON.

WHAT WAS WRONG, IN ONE SENTENCE EACH
--------------------------------------
* **`geocoder_census`** — `apps/metering/geocode.py` has called the US Census
  geocoder since `CR-028` D6. It has no card, no health state, no run row, no
  trace id, and nowhere a utility can switch it off (`DEF-INT-4251`).
* **`map_tiles_public`** — `features/assets/AssetMapTab.tsx` has fetched Esri
  tiles since the same change, *"and therefore the viewport around tenant asset
  locations"*, on every pan. The egress was ACCEPTED by ruling and written into
  the component's own docstring, which reads as compliance — and nobody asked
  the second question: **acceptable to whom, and where does a utility go to see
  it or turn it off** (`DEF-INT-4252`).

Both manifests have existed since phase 1 so the CARDS were honest about what
the product does. What was missing is the row underneath: a manifest with no
connection is a card that says *not set up* over a call that is being made.

WHY THE DEFAULTS ARE HERE AND NOT IN THE MANIFEST
---------------------------------------------------
A manifest is what a provider CAN do (`BR-INT-037`); a connection is what THIS
utility has agreed to. The addresses below are the ones the product is already
using today, so provisioning them changes no behaviour — it makes the existing
behaviour visible and switchable. A utility that points `map_tiles_public` at
its own city's tile server (`R-7`) edits one field on Settings and the
Content-Security-Policy follows it, with no code change anywhere.

⚠ **IT IS IDEMPOTENT AND IT NEVER OVERWRITES.** A tenant that has already
connected either provider — with its own host, or switched off on purpose — is
left exactly as it is. Provisioning that reset a host somebody chose would be
the same class of harm as the missing row.

⚠ **AND IT IS NOT A MIGRATION.** These are tenant rows, and a data migration
writing per-tenant rows runs once, on the tenants that existed that day, and
silently never again — so a utility provisioned next week would be back where
this file started. It is a management command an operator can re-run
(`seed_gis_city`).

⚠ **THIS PARAGRAPH SAID *"a service the tenant-provisioning path calls and a
management command"* UNTIL 2026-09-06, AND THE FIRST HALF WAS NEVER TRUE
(`DEF-INT-4287`, hard-won law 1 — a comment claiming a guarantee is not the
guarantee).** `apps/tenancy/services.py` and `apps/tenancy/sample_data.py`
contain no occurrence of `live_calls`, of `map_tiles` or of `integrations`, and
the lifecycle block below claimed `provisioned by … the tenant fixture path`
with the same absence of evidence. `provision()` has exactly one production
caller — the management command — so **no tenant of the deployment has ever had
either row**, which is how `page_policy.hosts_for` came to grant no tile host to
anybody and the asset map went grey for everyone.

⚠ **THE MAP NO LONGER DEPENDS ON THAT BEING FIXED, AND THE CARD STILL DOES.**
`page_policy.granted()` now offers `LIVE_CALL_DEFAULTS` below to a tenant with
no row, so the policy names the host the product actually fetches whether or not
anybody has ever run the command. What a missing row still costs is everything
this file was written for: the provider card reads *not set up* over a call
being made, there is no health state, and there is nowhere for a utility to
switch it off. **Wiring `provision()` into the tenant-provisioning path is owed
and is not done here** — it belongs to whoever owns `apps/tenancy/services.py`,
and `DEF-INT-4287` carries it.
"""

from __future__ import annotations

from typing import Any

from apps.integrations import addressing, models, services
from apps.integrations.registry import REGISTRY, Registry

#: The address `apps/metering/geocode.py` already calls — its own
#: `CENSUS_ONELINE_URL`, minus the path, because a connection holds a HOST.
CENSUS_HOST = "https://geocoding.geo.census.gov"

#: The address `features/assets/AssetMapTab.tsx` already fetches — r10's own
#: Esri World Street Map service, minus the `{z}/{y}/{x}` template.
ESRI_TILE_HOST = "https://server.arcgisonline.com"

#: `provider_key → the non-secret config the product is already using`.
#: ⚠ Two entries, and adding a third is adding a line here — never a branch.
LIVE_CALL_DEFAULTS: dict[str, dict[str, Any]] = {
    "geocoder_census": {"base_url": CENSUS_HOST},
    "map_tiles_public": {"base_url": ESRI_TILE_HOST},
}


def provision(
    actor: Any, tenant_id: Any, *, registry: Registry = REGISTRY
) -> dict[str, str]:
    """Give each live call a connection row, if it has none. Returns what it did.

    `{provider_key: "created" | "kept"}` — *kept* meaning the tenant already has
    a row and this function left every field of it alone.
    """
    done: dict[str, str] = {}
    for provider_key, config in LIVE_CALL_DEFAULTS.items():
        if registry.get(provider_key) is None:  # pragma: no cover — load refuses
            continue
        existing = services.connection_for(tenant_id, provider_key)
        if existing is not None:
            done[provider_key] = "kept"
            continue
        services.connect(
            actor=actor,
            tenant_id=tenant_id,
            provider_key=provider_key,
            environment=models.ENVIRONMENT_PRODUCTION,
            config=dict(config),
            cadence=models.CADENCE_MANUAL,
            registry=registry,
        )
        done[provider_key] = "created"
    return done


def host_for(tenant_id: Any, provider_key: str, *, registry: Registry = REGISTRY) -> str | None:
    """The address this tenant's connection names for this provider, or `None`.

    ⚠ **THIS DOCSTRING CLAIMED A READER IT DOES NOT HAVE, UNTIL 2026-09-17
    (`DEF-INT-5614`, hard-won law 1).** It read *"Read by the assets map through
    `GET /integrations/page-policy` so the tile URL a browser fetches and the
    origin the policy permits come from ONE row."* They do come from one row —
    and not through here. `grep -rn host_for 06-backend` finds three
    occurrences: this definition and two assertions in
    `tests/test_us_int_042_gis.py`. The map reads `page_policy.tile_host`.
    **There is no production caller**, which is hard-won law 2 in Python
    instead of in a React prop, and nothing in this repository asks that
    question of a function.

    ⚠ **AND IT WAS A FOURTH PLACE AN ADDRESS WAS DECIDED.** It read
    `config["base_url"]` — a literal, with no manifest and no operation — while
    the ENDPOINT column, the page policy and a TypeScript function each decided
    the same thing their own way (`CR-115-BRC05` §6). It now asks
    `addressing.connector_address`, which reads the manifest's single declared
    ADDRESS field. For both live-call providers that field IS `base_url`, so the
    answer does not move; what moves is that the name is no longer typed here.

    Whether this function should exist at all belongs with `DEF-INT-4287`, which
    already carries the other unwired half of this file.
    """
    row = services.connection_for(tenant_id, provider_key)
    if row is None or not row.enabled or row.status == models.STATUS_OFF:
        return None
    manifest = registry.get(provider_key)
    if manifest is None:  # pragma: no cover — `load` refuses an unknown key
        return None
    return addressing.connector_address(manifest, row).value


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (CR-069 wave M task M1; DEF-INT-4251 and DEF-INT-4252 filed before the fix)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B✔(the map reads the host through the policy endpoint) C✔ D=PARTIAL — provisioned by the management command ONLY; the tenant-provisioning half was claimed here and never existed (DEF-INT-4287, corrected 2026-09-06) E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py
# exceptions: not a data migration, and the docstring says why — a per-tenant data migration runs once and never for the next utility · ⚠ NO tenant of this deployment holds either row, because nothing on the provisioning path calls `provision()`; the page policy no longer depends on that, the provider CARD and its health still do (DEF-INT-4287)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
