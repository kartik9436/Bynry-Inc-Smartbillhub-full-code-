# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §6 lane 1 — *"ONE PATH DECIDES AN API'S URL"*.
# Defects:  DEF-INT-5502 · DEF-INT-4259 · DEF-INT-5488 · DEF-INT-5589 ·
#           DEF-INT-5613 (the two screens disagreed on 9 of 91 operations).
# Rules:    CR-115-BRC05 §3 risk 2 · BR-INT-037 · hard-won law 7.
# Impacts:  apps/integrations/addressing.py · selectors.py · page_policy.py
# ───────────────────────────────────────────────────────
"""THE ADDRESS LADDER, ASSERTED ON EVERY SHIPPED CONNECTOR.

⚠ **THESE ARE NOT THE PROOF OF NO BEHAVIOUR CHANGE — the ENUMERATION is**
(`10-scripts/cr115_one_address_enumeration.py`, whose empty before/after diff
over 286 rows is `CR-115-BRC05` §6's stated deliverable). What lives here is the
part a diff cannot carry into the future: the RULES the ladder encodes, so that
the next lane changing it goes red rather than moving 286 rows and being asked
to explain them.

Every case below is a sentence from `CR-115-BRC05` §6 or from a defect row.
"""

from __future__ import annotations

import pytest

from apps.integrations import addressing, page_policy, selectors
from apps.integrations.registry import ADDRESS_FIELD_KINDS, REGISTRY


def _address_fields(manifest):
    return [one for one in manifest.fields if one.kind in ADDRESS_FIELD_KINDS]


def test_cr115_tc1_the_operations_own_field_wins_and_says_so():
    """Rung 1. `gis_esri`'s `map_tiles` names `tile_url`; its two server
    operations name `base_url`. ONE CONNECTION, TWO HOSTS — `DEF-INT-4259`."""
    manifest = REGISTRY.require("gis_esri")
    settings = {
        "base_url": "https://gis.example.invalid/addr",
        "tile_url": "https://tiles.example.invalid/mt",
    }
    by_name = {one.name: one for one in manifest.operations}

    tiles = addressing.resolve_address(manifest, by_name["map_tiles"], settings=settings)
    assert tiles.value == "https://tiles.example.invalid/mt"
    assert tiles.source == addressing.SOURCE_OPERATION_FIELD
    assert tiles.field == "tile_url"
    assert tiles.is_own and not tiles.is_connectors

    search = addressing.resolve_address(manifest, by_name["address_search"], settings=settings)
    assert search.value == "https://gis.example.invalid/addr"
    assert search.field == "base_url"


def test_cr115_tc2_two_address_fields_answer_none_and_that_is_deliberate():
    """⚠ **`DEF-INT-4259` IS THE RECORD OF WHAT GUESSING BETWEEN TWO HOSTS
    COSTS** — the wrong one went into a security header and the city's own map
    would have been blocked. `CR-115-BRC05` §6 names this `None` as deliberate
    in as many words. A lane "tidying" it goes red here."""
    manifest = REGISTRY.require("gis_esri")
    assert len(_address_fields(manifest)) == 2
    assert addressing.host_fallback_field(manifest) is None

    # `map_tiles` names `tile_url`; with only `base_url` typed there is NO
    # fallback, and the honest answer is nothing at all.
    tiles = [one for one in manifest.operations if one.name == "map_tiles"][0]
    found = addressing.resolve_address(
        manifest, tiles, settings={"base_url": "https://gis.example.invalid/addr"}
    )
    assert found.value is None
    assert found.source == addressing.SOURCE_NONE


def test_cr115_tc3_the_connectors_single_field_is_the_fallback():
    """Rung 2. 15 of 18 manifests named `base_url` and declared no such field,
    so the drawn column was blank on every connector we ship (`DEF-INT-5502`).
    `sso` is the live instance: its operation names `base_url` and the manifest
    declares `metadata_url`."""
    manifest = REGISTRY.require("sso")
    assert addressing.host_fallback_field(manifest) == "metadata_url"
    operation = manifest.operations[0]
    assert operation.host_field == "base_url"

    found = addressing.resolve_address(
        manifest, operation, settings={"metadata_url": "https://idp.example.invalid/meta"}
    )
    assert found.value == "https://idp.example.invalid/meta"
    assert found.source == addressing.SOURCE_CONNECTOR_FIELD
    assert found.field == "metadata_url"
    assert found.is_connectors and not found.is_own


def test_cr115_tc4_a_door_we_publish_is_last_so_a_typed_host_still_wins():
    """Rung 3, and its ORDER. A connector that both publishes a door and dials a
    vendor would otherwise show its own address beside the vendor's call, which
    is `DEF-INT-4259` a third time."""
    manifest = REGISTRY.require("pay_invoicecloud_partner")
    door = [one for one in manifest.operations if one.served_path][0]

    found = addressing.resolve_address(manifest, door, settings={})
    assert found.value == addressing.OUR_API_ROOT + door.served_path  # DEF-INT-10020: what a partner dials
    assert found.source == addressing.SOURCE_SERVED_PATH
    assert found.field is None


def test_cr115_tc5_a_blank_box_is_an_absence_and_never_an_empty_string():
    """⚠ **THE LADDER IS `or`-SHAPED AND THAT IS LOAD-BEARING.** A field present
    and blank falls through, exactly as the three separate copies of this chain
    did before `CR-115`, and the answer is `None` rather than `""` so a caller
    cannot tell a blank from an absence by accident."""
    manifest = REGISTRY.require("email_smtp")
    operation = manifest.operations[0]
    found = addressing.resolve_address(manifest, operation, settings={"host": ""})
    assert found.value is None
    assert found.source == addressing.SOURCE_NONE


def test_cr115_tc6_a_host_that_is_not_a_url_stays_not_a_url():
    """`CR-115-BRC05` §6 names this case for the browser check: *a `host` that
    is NOT a URL and must stay that way*. SMTP dials a host and a port and
    concatenates them, so nothing here may decorate it with a scheme."""
    manifest = REGISTRY.require("email_smtp")
    operation = manifest.operations[0]
    found = addressing.resolve_address(manifest, operation, settings={"host": "smtp.example.invalid"})
    assert found.value == "smtp.example.invalid"
    assert "://" not in found.value
    assert found.field == "host"


def test_cr115_tc7_the_page_policy_climbs_ONE_rung_and_no_more():
    """Granting a browser an origin is a security decision: hard-won law 3 says
    the permissive answer is the one you type. `sso` is the connector where the
    two answers differ — the ENDPOINT column takes rung 2, the policy refuses
    it — which is what makes this assertion worth making rather than tautological."""
    manifest = REGISTRY.require("sso")
    operation = manifest.operations[0]
    settings = {"metadata_url": "https://idp.example.invalid/meta"}

    column = addressing.resolve_address(manifest, operation, settings=settings)
    policy = addressing.resolve_address(
        manifest, operation, settings=settings, allow=addressing.OWN_FIELD_ONLY
    )
    assert column.value == "https://idp.example.invalid/meta"
    assert policy.value is None
    assert addressing.OWN_FIELD_ONLY == (addressing.SOURCE_OPERATION_FIELD,)


@pytest.mark.parametrize("manifest", list(REGISTRY.all()), ids=lambda one: one.key)
def test_cr115_tc8_every_operation_of_every_connector_resolves_without_raising(manifest):
    """29 connectors, 91 operations. A resolver that raised on one manifest
    would empty that connector's column and nothing else would say so."""
    for operation in manifest.operations:
        found = addressing.resolve_address(manifest, operation, settings={})
        assert found.source in (*addressing.EVERY_SOURCE, addressing.SOURCE_NONE)
        assert found.value is None or isinstance(found.value, str)


def test_cr115_tc9_the_row_a_screen_reads_carries_the_provenance():
    """⚠ **A SCREEN MUST NEVER WORK THIS OUT FOR ITSELF** (`CR-115-BRC05` §6).
    `DEF-INT-5613` was exactly a screen doing so: `ConnectorSetupPage` climbed
    one rung of three and printed a dash on 9 of 91 operations where the
    connection view printed an address. The wire carries the answer AND how it
    was reached, so the per-API work can say *using the connector's address*
    without deriving anything."""
    manifest = REGISTRY.require("gis_esri")
    tiles = [one for one in manifest.operations if one.name == "map_tiles"][0]
    row = selectors._operation_row(
        tiles, None, None, {"tile_url": "https://tiles.example.invalid/mt"}, manifest
    )
    assert row["endpoint"] == "https://tiles.example.invalid/mt"
    assert row["endpoint_source"] == addressing.SOURCE_OPERATION_FIELD
    assert row["endpoint_field"] == "tile_url"
    # The NAME of the field still travels beside the value — the set-up screen
    # shows which box holds the address.
    assert row["host_field"] == "tile_url"


def test_cr115_tc10_there_is_exactly_one_resolver_and_page_policy_asks_it():
    """The refactor's own shape, asserted rather than described. `G128` enforces
    it across the tree; this is the one import that must never come back."""
    source = (
        __import__("pathlib").Path(page_policy.__file__).read_text(encoding="utf-8")
    )
    assert "addressing.resolve_address" in source
    assert "addressing.OWN_FIELD_ONLY" in source
    assert 'getattr(operation, "host_field"' not in source
