"""Census geocoder — the one outbound call the product makes today, moved onto the substrate (Maps & addresses · LIVE).

Field map I-15: `apps/metering/geocode.py` (CR-028 D6, run by
`geocode_premises`) calls the Census geocoder with no connection record. This
manifest gives that call a card, a run row and a trace id (BR-INT-039). No
credential (`auth.mode == "none"`); reconcile by the premises it geocodes. The
defect naming the unrecorded call is `DEF-INT-4251`, filed by wave M on
2026-09-06, and wave M gave it the CONNECTION ROW that makes it switchable. ⚠
Every numeric that arrives carries a measurement frame and is checked
(BR-INT-049 🔒) — a coordinate in a projected system is refused by name.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.geocoder_census.*` wins on screen when present, so a
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
    key="geocoder_census",
    category="maps",
    display_name="Census geocoder",
    summary="Put a pin on the map for each address we hold.",
    disposition=Disposition(kind="live", phase=1),
    auth=Auth(mode="none", placement="none"),
    fields=(
        #: Seeded with the service's own published address (`DEF-INT-5488`,
        #: and the PO's phase-1 dummy API).
        #: ⚠ **THE REAL ADDRESS FROM 2026-10-07 (GIS Lane D, `DEF-INT-10006`),
        #: AND IT WAS `geocoding.geo.census.example` UNTIL THEN.** The
        #: convention — a `.example` placeholder, so a test run cannot dial
        #: somebody else's server — is right for a connector we have not
        #: built. This one is LIVE and the product already calls the real host
        #: (`apps/metering/geocode.py`, `live_calls.CENSUS_HOST`), so a
        #: placeholder here was a THIRD address for one service, and with the
        #: adapter now bound, *Save and test* on it would have answered green
        #: from a recording for a service nobody reached. Tests still never
        #: dial it: every one names a `.example` host (`census_fixtures`).
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            default="https://geocoding.geo.census.gov",
        ),
    ),
    operations=(
        Operation(
            name="geocode_address",
            # Sixty a minute. The Census service is a public good with no
            # contract behind it, so the polite default is one a second and
            # the drawn figure is an illustration (B14 rule 37).
            rate_limit_per_minute=60,
            label="Geocode addresses",
            description="We send an address and record the coordinates that come back.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="manual",
            idempotency=Idempotency(mode="reconcile", source="natural_key"),
            completion="immediate",
            codec="json",
            # It WRITES what comes back — into empty coordinates only, which
            # is `CR-028` D6 and is unchanged by wave M.
            result_disposition="load",
            test_action="Geocode one address you type.",
        ),
    ),
)
