"""Public map tiles — the tile call the browser already makes (Maps & addresses · LIVE · browser, no secret).

Field map I-15: `features/assets/AssetMapTab.tsx` fetches Esri tiles today
with no connection record. This manifest is that call, on the substrate:
executor `browser`, no tenant secret (BR-INT-048), and a page-security policy
generated from the registered browser operations. The defect naming the
unrecorded call is `DEF-INT-4252`, filed by wave M on 2026-09-06; the manifest
existed from phase 1 so the card was honest about what the product already
does, and wave M gave the call the CONNECTION ROW that makes it switchable.

⚠ **THE TILE HOST IS THIS CONNECTION'S `config["base_url"]`, NOT A CONSTANT IN
THE COMPONENT.** `features/assets/AssetMapTab.tsx` hardcoded Esri's address
until wave M; it now reads the host off the connection, which is the same fact
`page_policy.py` puts in the Content-Security-Policy — so a policy and a tile
request cannot disagree.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.map_tiles_public.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="map_tiles_public",
    category="maps",
    display_name="Public map tiles",
    summary="The base map the asset screens already draw.",
    disposition=Disposition(kind="live", phase=1),
    auth=Auth(mode="none", placement="none"),
    fields=(
        # The tile server this deployment draws from. NOT a secret (`kind`
        # `host`), so it lives in `integration_connection.config` where the
        # policy generator and the map component both read it.
        #: Seeded (`DEF-INT-5488`). `.example` rather than the live hostname,
        #: for the reason `geocoder_census` gives in full.
        Field(
            name="base_url",
            label="Tile server",
            kind="url",
            default="https://server.arcgisonline.example",
        ),
    ),
    operations=(
        Operation(
            name="map_tiles",
            # 600 — a map draws many tiles at once and the BROWSER places
            # every one of them, so this is the one ceiling a person reaches
            # by ordinary use. Ten a second.
            rate_limit_per_minute=600,
            label="Map tiles",
            description="The browser draws public map tiles behind our pins.",
            direction="in",
            initiative="us",
            transport="browser",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            executor="browser",
            result_disposition="load",
            test_action="Load one tile in the browser.",
        ),
    ),
)
