# ── Trace ──────────────────────────────────────────────
# Story:   CR-112 — the City's address register becomes the source of addresses.
# Rules:   BR-INT-072 (the snapshot is pulled once, paged, all-or-nothing) ·
#          hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Tests:   06-backend/tests/test_cr112_gis_layer.py · test_cr112_gis_match.py
# Impacts: apps/integrations/gis_layer.py (the transport it serves)
# ───────────────────────────────────────────────────────
"""A recorded Esri Feature Service, for hosts that can never resolve.

⚠⚠ **THESE RESPONSES ARE CONSTRUCTED, NOT RECORDED, AND SAYING SO IS THE FIRST
THING THIS FILE DOES (hard-won law 1).** The brief for this wave asked for a
fixture captured from the City of Ann Arbor's real service with *"at most a few
live calls"*. **Zero live calls were made, because none was possible**: this
container's egress proxy refuses `a2mapseg.a2gov.org` by policy —
`CONNECT tunnel failed, response 403` on `curl`, and
`EGRESS_BLOCKED` from the fetch tool. Both were tried once, on 2026-09-17.

**So what is below is the ArcGIS REST PROTOCOL, shaped by hand**, with the field
names the brief documents for that layer and obviously synthetic values. It is
enough to prove the paging, the `outSR` check, the field mapping, the
assembly-from-parts branch and every match rule — all of which are OUR code. It
is **not** evidence about Ann Arbor's actual data: not their real `maxRecordCount`,
not their status vocabulary, not how often `Street` is blank, not whether their
`Unit` values look like ours.

⚠ **WHAT IS STILL UNPROVEN, LISTED SO NOBODY READS THIS FILE AS COVER.** Until
somebody runs this against the real service from a host that can reach it:
  * their real page size (we read it rather than assume it, which is the
    mitigation, but the read itself is untested against them);
  * whether their `Status` vocabulary contains anything that ought to stop a
    run (we filter none of it, by ruling 10, so the risk is bounded);
  * whether their coordinates arrive in 4326 when asked (we refuse anything
    else by name, so this fails loudly rather than quietly);
  * how many of their rows carry a blank `Street` and need assembly.
A `.example` host is used throughout — RFC 2606 reserves it, so a connection
pointed at one could never have worked and this can never shadow a real city.
"""

from __future__ import annotations

import copy
import re
import urllib.parse
from typing import Any

#: The reserved host every fixture below answers for. RFC 2606.
FIXTURE_HOST = "gis.example"
FIXTURE_LAYER = f"https://{FIXTURE_HOST}/arcgis/rest/services/Qualified/FeatureServer/0"

#: ⚠ **DELIBERATELY NOT 1000.** A fixture that used the most common page size
#: would pass identically against an implementation that hard-coded 1000, which
#: is precisely the bug `BR-INT-072` is about. Three rows a page makes the
#: paging visible and makes a hard-coded stride fail.
FIXTURE_PAGE_SIZE = 3

LAYER_METADATA: dict[str, Any] = {
    "currentVersion": 10.91,
    "id": 0,
    "name": "QualifiedAddress",
    "type": "Feature Layer",
    "geometryType": "esriGeometryPoint",
    "objectIdField": "OBJECTID",
    "maxRecordCount": FIXTURE_PAGE_SIZE,
    "supportedQueryFormats": "JSON",
    "advancedQueryCapabilities": {"supportsPagination": True},
    "fields": [
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
        {"name": "St_Number", "type": "esriFieldTypeString"},
        {"name": "St_Number_Sfx", "type": "esriFieldTypeString"},
        {"name": "St_Dir_Pfx", "type": "esriFieldTypeString"},
        {"name": "St_Name", "type": "esriFieldTypeString"},
        {"name": "St_Dir_Sfx", "type": "esriFieldTypeString"},
        {"name": "St_Name_Sfx", "type": "esriFieldTypeString"},
        {"name": "Unit", "type": "esriFieldTypeString"},
        {"name": "Street", "type": "esriFieldTypeString"},
        {"name": "City", "type": "esriFieldTypeString"},
        {"name": "State", "type": "esriFieldTypeString"},
        {"name": "Zip", "type": "esriFieldTypeString"},
        {"name": "Status", "type": "esriFieldTypeString"},
        {"name": "PIN", "type": "esriFieldTypeString"},
        {"name": "FULLPIN", "type": "esriFieldTypeString"},
    ],
}


def _feature(oid: int, attributes: dict[str, Any], x: float, y: float) -> dict[str, Any]:
    base = {
        "OBJECTID": oid,
        "St_Number": "", "St_Number_Sfx": "", "St_Dir_Pfx": "",
        "St_Name": "", "St_Dir_Sfx": "", "St_Name_Sfx": "",
        "Unit": "", "Street": "", "City": "Riverbend", "State": "MI",
        "Zip": "48104", "Status": "ACTIVE", "PIN": "", "FULLPIN": "",
    }
    base.update(attributes)
    return {"attributes": base, "geometry": {"x": x, "y": y}}


#: Seven address points over four parcels, chosen so every branch has a case:
#:
#:   09-01-100  100 North Maple Street  — a house. One point, no unit, so the
#:              premises gets a pin (ruling 6's *happy* side).
#:   09-01-200  220 Oak Avenue          — a four-flat. A BUILDING point with a
#:              blank `Unit` plus units 1 and 2.
#:   09-01-300  330 Elm Court           — units 1 and 2 and **NO building
#:              point**, which is ruling 6's actual case: the premises pin stays
#:              blank rather than borrowing a unit's.
#:   09-01-400  (blank `Street`)        — the assemble-from-parts branch, with a
#:              **leading-zero postcode** so a leading zero is proved to survive.
FEATURES: list[dict[str, Any]] = [
    _feature(1, {
        "Street": "100 N Maple St", "PIN": "09-01-100", "FULLPIN": "09-01-100-0000",
        "St_Number": "100", "St_Dir_Pfx": "N", "St_Name": "Maple", "St_Name_Sfx": "St",
    }, -83.743210, 42.280100),
    _feature(2, {
        "Street": "220 Oak Ave", "PIN": "09-01-200", "FULLPIN": "09-01-200-0000",
    }, -83.744000, 42.281000),
    _feature(3, {
        "Street": "220 Oak Ave", "Unit": "1",
        "PIN": "09-01-200", "FULLPIN": "09-01-200-0001",
    }, -83.744010, 42.281010),
    _feature(4, {
        "Street": "220 Oak Ave", "Unit": "APT 2",
        "PIN": "09-01-200", "FULLPIN": "09-01-200-0002",
    }, -83.744020, 42.281020),
    _feature(5, {
        "Street": "330 Elm Ct", "Unit": "1",
        "PIN": "09-01-300", "FULLPIN": "09-01-300-0001",
    }, -83.745000, 42.282000),
    _feature(6, {
        "Street": "330 Elm Ct", "Unit": "2",
        "PIN": "09-01-300", "FULLPIN": "09-01-300-0002",
    }, -83.745010, 42.282010),
    _feature(7, {
        # `Street` deliberately BLANK — the parts are all there is, and they
        # must assemble in spoken order: number · dir-prefix · name · suffix.
        "St_Number": "44", "St_Dir_Pfx": "W", "St_Name": "Birch",
        "St_Name_Sfx": "Ln", "Zip": "07001",
        "PIN": "09-01-400", "FULLPIN": "09-01-400-0000",
        "Status": "PROVISIONAL",
    }, -83.746000, 42.283000),
]


def _page(offset: int, size: int) -> dict[str, Any]:
    window = FEATURES[offset : offset + size]
    payload: dict[str, Any] = {
        "objectIdFieldName": "OBJECTID",
        "geometryType": "esriGeometryPoint",
        "spatialReference": {"wkid": 4326, "latestWkid": 4326},
        "features": copy.deepcopy(window),
    }
    # ⚠ **ABSENT ON THE LAST PAGE, NOT `false`** — which is how many real
    # services behave and is why `walk` tests truthiness and never presence. A
    # fixture that always set the key would let a presence-testing walk pass.
    if offset + size < len(FEATURES):
        payload["exceededTransferLimit"] = True
    return payload


def recorded_transport(url: str, timeout_s: float) -> Any:
    """Serve `gis.example` from the fixtures above. Never dials anything."""
    # `DEF-INT-9846` — the four refusing hosts refuse the LAYER too, the same
    # way they refuse the search, so a walkthrough of *Run now* can show the
    # parcel check's reason by editing one field on the connection.
    from apps.integrations import gis_fixtures

    refused = gis_fixtures.refusal_for(url)
    if refused is not None:
        return refused
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if not parsed.path.endswith("/query"):
        return copy.deepcopy(LAYER_METADATA)
    if params.get("returnCountOnly") == ["true"]:
        # `DEF-INT-9849` — ArcGIS's own answer to *how many rows*, read only
        # when a walk stopped after the pages a person asked for.
        assert params.get("outSR") == ["4326"], f"outSR was {params.get('outSR')!r}, not 4326"
        return {"count": len(FEATURES)}
    # ⚠ The fixture ASSERTS what the caller asked for, so a walk that forgot
    # `outSR` fails here rather than passing and being wrong in production.
    assert params.get("outSR") == ["4326"], f"outSR was {params.get('outSR')!r}, not 4326"
    assert params.get("where") == ["1=1"] or params.get("where"), "no where clause"
    assert params.get("orderByFields"), "no orderByFields — paging would be unstable"
    offset = int((params.get("resultOffset") or ["0"])[0])
    size = int((params.get("resultRecordCount") or [str(FIXTURE_PAGE_SIZE)])[0])
    # A real service caps the request at its own maximum; so does this.
    return _page(offset, min(size, FIXTURE_PAGE_SIZE))


def half_way_transport(url: str, timeout_s: float) -> Any:
    """Answers the first page and then fails — `BR-INT-072`'s all-or-nothing.

    A half snapshot reads as *the City deleted 40,000 addresses*, so this is the
    fixture that proves `walk` raises instead of returning what it has.
    """
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if not parsed.path.endswith("/query"):
        return copy.deepcopy(LAYER_METADATA)
    if int((params.get("resultOffset") or ["0"])[0]) > 0:
        raise TimeoutError("the city stopped answering")
    return _page(0, FIXTURE_PAGE_SIZE)


def projected_transport(url: str, timeout_s: float) -> Any:
    """Answers in State Plane feet however politely it was asked for 4326.

    The numbers are six and seven integer digits — they do not fit a
    `NUMERIC(9,6)` column, and truncating them would put every property
    somewhere real and wrong.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.path.endswith("/query"):
        return copy.deepcopy(LAYER_METADATA)
    page = _page(0, FIXTURE_PAGE_SIZE)
    page["spatialReference"] = {"wkid": 2253, "latestWkid": 2253}
    for one in page["features"]:
        one["geometry"] = {"x": 13312340.55, "y": 288765.42}
    return page


def stuck_offset_transport(url: str, timeout_s: float) -> Any:
    """Ignores `resultOffset` and answers page 1 for ever, well-formed.

    Every page looks perfect. Without the repeat check in `walk` this loops
    until something else runs out.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.path.endswith("/query"):
        return copy.deepcopy(LAYER_METADATA)
    page = _page(0, FIXTURE_PAGE_SIZE)
    page["exceededTransferLimit"] = True
    return page


def empty_layer_transport(url: str, timeout_s: float) -> Any:
    """A layer with no rows. Must NOT read the same as a refusal."""
    parsed = urllib.parse.urlparse(url)
    if not parsed.path.endswith("/query"):
        return copy.deepcopy(LAYER_METADATA)
    return {
        "objectIdFieldName": "OBJECTID",
        "spatialReference": {"wkid": 4326, "latestWkid": 4326},
        "features": [],
    }


def no_page_size_transport(url: str, timeout_s: float) -> Any:
    """Metadata without `maxRecordCount` — refused rather than guessed at."""
    parsed = urllib.parse.urlparse(url)
    if not parsed.path.endswith("/query"):
        payload = copy.deepcopy(LAYER_METADATA)
        payload.pop("maxRecordCount")
        return payload
    return _page(0, FIXTURE_PAGE_SIZE)


# ═══════════════════════════════════════════════════════════════════════════
# The ADDRESS SEARCH — `DEF-INT-9843` / `9844` / `9845`, 2026-10-07
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠⚠ **CONSTRUCTED FROM THE PO'S EVIDENCE, NOT CAPTURED — SAID FIRST, AS THIS
# FILE'S OPENING SAYS OF EVERYTHING ABOVE.** On 2026-10-07 the PO ran, by hand,
# against the live Ann Arbor layer:
#
#     …/SEUQualifiedAddress/FeatureServer/0/query
#         ?where=UPPER(Street) LIKE UPPER('%2670 SEQUOIA%')
#         &outFields=*&outSR=4326&returnGeometry=false&f=json
#
# and it answered *"2670 Sequoia Pkwy, Ann Arbor"*. One request from this
# container was tried the same day and the egress proxy refused it
# (`CONNECT tunnel failed, response 403`), so what follows is that answer in
# ArcGIS's documented shape: the street and city are the PO's, every key and
# coordinate is synthetic, and the second row (a `Unit`) is ours, there to
# prove the unit travels. **It is evidence about the PROTOCOL, never about
# Ann Arbor's data.**

SEQUOIA_FEATURES: list[dict[str, Any]] = [
    _feature(101, {
        "Street": "2670 Sequoia Pkwy", "City": "Ann Arbor", "Zip": "48103",
        "PIN": "09-00-00-000-001", "FULLPIN": "09-00-00-000-001-0000",
    }, -83.790000, 42.300000),
    _feature(102, {
        "Street": "2670 Sequoia Pkwy", "City": "Ann Arbor", "Zip": "48103",
        "Unit": "A",
        "PIN": "09-00-00-000-001", "FULLPIN": "09-00-00-000-001-000A",
    }, -83.790010, 42.300010),
    _feature(103, {
        "Street": "2700 Packard St", "City": "Ann Arbor", "Zip": "48108",
        "PIN": "09-00-00-000-002", "FULLPIN": "09-00-00-000-002-0000",
    }, -83.700000, 42.250000),
]


def _asked_for(params: dict[str, list[str]]) -> str:
    """What the search asked for, ASSERTED — so a URL that drops one fails here."""
    assert params.get("outSR") == ["4326"], f"outSR was {params.get('outSR')!r}, not 4326"
    assert params.get("outFields") == ["*"], f"outFields was {params.get('outFields')!r}"
    assert params.get("f") == ["json"], f"f was {params.get('f')!r}"
    assert params.get("resultRecordCount"), "no resultRecordCount — the City would choose the cap"
    for geocoder_word in ("q", "limit", "key"):
        assert geocoder_word not in params, f"{geocoder_word}= is a geocoder's word; ArcGIS ignores it"
    where = (params.get("where") or [""])[0]
    match = re.search(r"^UPPER\((\w+)\) LIKE UPPER\('%(.*)%'\)", where)
    assert match, f"not the search's where clause: {where!r}"
    return match.group(2).replace("''", "'").upper()


def search_transport(url: str, timeout_s: float) -> Any:
    """A FeatureServer answering a SEARCH, filtered as the City would filter."""
    parsed = urllib.parse.urlparse(url)
    assert parsed.path.endswith("/query"), f"not a /query: {parsed.path!r}"
    params = urllib.parse.parse_qs(parsed.query)
    typed = _asked_for(params)
    size = int(params["resultRecordCount"][0])
    hits = [
        one for one in SEQUOIA_FEATURES
        if typed in str(one["attributes"].get("Street") or "").upper()
    ][:size]
    return {
        "objectIdFieldName": "OBJECTID",
        "geometryType": "esriGeometryPoint",
        "spatialReference": {"wkid": 4326, "latestWkid": 4326},
        "features": copy.deepcopy(hits),
    }


def projected_search_transport(url: str, timeout_s: float) -> Any:
    """The same search answered in Michigan State Plane feet — however asked.

    `wkid` 2253 is NAD83 / Michigan South (ft). Six- and seven-digit numbers
    that are not degrees; `DEF-INT-9844` refuses the whole answer.
    """
    page = search_transport(url, timeout_s)
    page["spatialReference"] = {"wkid": 2253, "latestWkid": 2253}
    for one in page["features"]:
        one["geometry"] = {"x": 13284512.31, "y": 284120.77}
    return page
