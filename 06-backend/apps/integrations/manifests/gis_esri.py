"""Esri ArcGIS — address search, the parcel check and the map (Maps · LIVE, phase 4).

**Connector 25 of 28. RENAMED ONLY** (`CR-110-BRC04`, blueprint p162: *"Renamed
only. Fields, operations and adapters are untouched — the safest two in the
list."*). The key moved from `gis_city` to `gis_esri` and the display name from
*City GIS* to *Esri ArcGIS*; the three fields, the three operations, their
directions, triggers, latency budget, result dispositions and the two-host
arrangement are byte-for-byte what they were. Measured safe: **0 `gis_city`
connection rows** across all four tenants of the development database (read
under RLS, tenant by tenant, because an aggregate read without `app.tenant_id`
returns zero over real rows).

⚠ **THE OPERATION NAMES DID NOT MOVE, AND THAT IS DELIBERATE.** The naming
format we own would make these `fetch_address`, `fetch_parcel` and
`fetch_tile`. They are shipped: `gis.py`, `page_policy.py`, the adapter, a seed
command, a Runbooks definition, six test files and the front end all name them,
and `integration_run.operation` records them as data already written. Renaming
a shipped operation orphans its own run history, which is a different change
with a different blast radius. The format is applied in full to the fourteen
connectors that are new in this wave; the drift on the shipped ones is filed
rather than fixed here.

⚠ **THE TWO ADDRESSES ARE `kind="url"` AND NOT `kind="host"` — `DEF-INT-5589`,
PO ruling 2026-09-17 (*"a) build it now with the Edit fix"*).** They were
`host` until then, and a `host` is a bare name: no scheme, no path, no port. So
the City of Ann Arbor's real service address —
`https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query`
— **could not be typed into the product at all**, while the hostname alone,
which names no layer and answers nothing, was accepted. The PATH is what names
the layer. `host` was deliberately NOT widened: SMTP's `host` and the two file
drops' are dialled as host-and-port and concatenated into a connection string.

⚠ **NO TIME OF DAY.** CFG-25 draws a clock in *When it runs* — *"1 of 3 run on
a clock"* — and the blueprint says of it *"is accepted, validated, saved … and
nothing will ever read it."* PO ruling 2026-09-16: scheduling belongs to
Runbooks, *"conenctor i a conenctor not a logic to to ETL"*. Drawn,
deliberately not built.

Three operations on one credential: an INLINE address search with a latency
budget and result disposition `offer` — the list is shown and nothing is
written until a person picks a row (BR-INT-048, C15/C16); a nightly parcel
reconciliation with a per-field scope of authority that never writes the three
columns that decide tax (BR-INT-051 🔒); and the map tiles the browser draws.
⚠ THE THREE QUESTIONS THIS DOCSTRING CALLED OPEN WERE ALL RULED ON
2026-09-04 AND THIS PARAGRAPH SAID `OPEN` UNTIL 2026-09-06 (CR-069 wave M).
`OQ-INT-1470` — the GIS parameters are the match key. `OQ-INT-1471` — *"(b)
type it, marked unchecked"*: when the city cannot answer, a clerk CREATES the
premises and it is marked **unchecked** until a later run checks it, so the
unreachable branch is a BUILD and not a stub. `OQ-INT-1472` — the night creates
nothing. ⚠ `reconcile_parcels` IS NO LONGER A STUB (this sentence said it was
until 2026-10-07): its runner is `apps.integrations.gis.reconcile` (*Preview* /
*Apply* on the connection page, `CR-112`), and Runbook 20 reads it through
`apps/runbooks/seams/integrations_seam.city_parcels` (`DEF-INT-9848`). The
label still says *Nightly*; no nightly run exists, and what one would do is the
PO's deferred question (decision log 2026-10-07).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.gis_esri.*` wins on screen when present, so a
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
    key="gis_esri",
    category="maps",
    display_name="Esri ArcGIS",
    summary="Find an address and keep parcels in step.",
    disposition=Disposition(kind="live", phase=4),
    auth=Auth(mode="we_hold_theirs", placement="query"),
    fields=(
        # ⚠ **THE DEFAULT CARRIES A PATH, AND THAT IS THE WHOLE LESSON OF
        # `DEF-INT-5589`.** An ArcGIS feature service is named by its path, not
        # by its host: the City of Ann Arbor's qualified-address layer is
        # `/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query`
        # on a host that also serves everything else the city publishes. A
        # placeholder showing only a host would teach a clerk to type the one
        # thing that cannot work, so this one shows the shape.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://gis.vendor.example/arcgis/rest/services/Addresses/FeatureServer/0/query",
        ),
        # ⚠ **A SECOND HOST ON ONE CONNECTION, AND IT IS NOT THE SAME MACHINE
        # AS THE ADDRESS SERVICE** (`US-INT-042` §4 names both: the address
        # service and the city-run tile server). `map_tiles` declares this
        # field as its own host, so the generated page policy permits the tile
        # server and not the address service — which is `DEF-INT-4259`, found
        # by reading a real response header.
        Field(
            name="tile_url",
            label="Map tile server",
            kind="url",
            required=False,
            default="https://tile.arcgisonline.example",
        ),
        Field(name="api_key", label="API key", kind="secret", required=False),
        # ── 2026-09-17 · `BR-INT-076` — WHICH OF THEIR FIELDS IS WHICH ───────
        # ⚠ **THE TWO KEYS ARE CONFIGURATION, NOT CODE, AND THIS IS WHERE A
        # CLERK SAYS SO.** Ann Arbor's layer calls the parcel `PIN` and the
        # address point `FULLPIN`; the next city calls them something else.
        # `BR-INT-037` and the PO's own words — *"So adding an API is data, not
        # code"* — so `apps/integrations/gis_layer.py` holds no city's field
        # name and reads every one of them from here.
        #
        # `mapping_editor` is the kind `bank_lockbox_file` already uses for a
        # file's column mapping (`BR-INT-043`), and it is the right shape for
        # the same reason: a set of OUR names against a set of THEIRS, which no
        # plain field can express. It takes no `default` — the registry refuses
        # one on this kind, because there is no value a clerk could have typed.
        #
        # ⚠ **A LAYER THAT NAMES THESE DIFFERENTLY AND IS NOT MAPPED DOES NOT
        # SILENTLY RECONCILE AS BLANK.** `gis_parcels.run` stops when the
        # snapshot reports the parcel or point field missing from their rows,
        # rather than filing one *blank theirs* difference per row over the
        # whole register — which on a 40,000-row register is the difference
        # between a refusal somebody reads and a mess somebody inherits.
        Field(
            name="field_mapping",
            label="Which field is which",
            kind="mapping_editor",
            required=False,
        ),
    ),
    operations=(
        Operation(
            name="address_search",
            label="Address search",
            description="We look an address up in the city's records as a clerk types.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            # C15 — *"candidates in under a second"* (US-INT-042 §1). Not a
            # job: no queue row, no progress row, no poll.
            latency_budget_ms=1000,
            # C16 — the list is SHOWN and nothing is written until a person
            # picks a row. A clerk typing an address has not asked for a
            # premises to exist.
            result_disposition="offer",
            # A clerk typing an address makes one call per pause in the typing,
            # and they are waiting for it. Ten a second is a busy counter and
            # still refuses a script. Outward, so the number is what the city
            # allows us — 600 until a contract says otherwise.
            rate_limit_per_minute=600,
            test_action="Look up one address you type.",
        ),
        Operation(
            name="reconcile_parcels",
            # ⚠ **"Parcel check", NOT "Nightly parcel check" — 2026-10-07
            # (`DEF-INT-10007`).** The PO deferred any nightly run that day
            # (decision log *"NO NEW NIGHTLY CODE"*); the check is run by hand,
            # from Preview or Runbook 20. `trigger` below stays `scheduled`:
            # it is what the API row's WHEN column and the runner key off, and
            # a schedule for one named utility is still the ruled future.
            label="Parcel check",
            description="We compare the city's parcels with our premises.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="scheduled",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            result_disposition="load",
            # It runs once a night. Anything above ten a minute is a retry
            # storm, which is what a ceiling is for.
            rate_limit_per_minute=10,
        ),
        Operation(
            name="map_tiles",
            label="Map tiles",
            description="The browser draws the city's map tiles.",
            direction="in",
            initiative="us",
            transport="browser",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            executor="browser",
            # `DEF-INT-4259` — the TILE server, never the address service.
            host_field="tile_url",
            # A map draws many tiles at once and the BROWSER places every one of
            # them, so this is the one ceiling on this connector that a person
            # can reach by ordinary use. 600 is ten a second.
            rate_limit_per_minute=600,
            # The browser draws what it fetches; there is nothing to offer and
            # nothing of ours to write. ⚠ And no `latency_budget_ms`: we are
            # not the one waiting, so a deadline here would be a guarantee we
            # could not keep (the validator refuses one).
            result_disposition="load",
        ),
    ),
)
