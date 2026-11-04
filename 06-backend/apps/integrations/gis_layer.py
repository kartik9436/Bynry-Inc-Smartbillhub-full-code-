# ── Trace ──────────────────────────────────────────────
# Story:    CR-112 — the City's address register becomes the source of
#           addresses. This file is the PROTOCOL half: an Esri ArcGIS Feature
#           Service, read and paged, with no database and no Django in it.
# Rules:    BR-INT-037 (data, not code — nothing city-specific lives here) ·
#           BR-INT-038 (an adapter TRANSLATES and decides nothing) ·
#           BR-INT-049 (a coordinate carries its measurement frame) ·
#           BR-INT-072 (the snapshot is pulled ONCE, paged, all-or-nothing) ·
#           BR-MET-1173 (the two keys are per-tenant configuration) ·
#           PO rulings 2026-09-17 nos. 4 (never per premises) and 10 (their
#           data problems are theirs)
# Tests:    06-backend/tests/test_cr112_gis_layer.py
# Impacts:  apps/integrations/gis_parcels.py (the only caller) ·
#           apps/integrations/gis_esri_fixtures.py (the recorded answers)
# ───────────────────────────────────────────────────────
"""An Esri ArcGIS Feature Service, read whole — the protocol and nothing else.

WHAT IS IN HERE AND WHAT IS DELIBERATELY NOT
----------------------------------------------
In: how an ArcGIS `/query` is spelled, how its pages are walked, how one
`feature` becomes one of our rows, and how a street is normalised so two
spellings of one address compare equal.

Not in: **anything about Ann Arbor.** Not their URL, not their layer number, not
which of their fields is the parcel id, not which is the point id. `BR-INT-037`
and the PO's own words — *"So adding an API is data, not code"* — so all four
are per-tenant CONFIGURATION read off the connection and handed in as arguments.
Another city with a differently-named layer connects the same connector and
types different field names. **A city name appearing in this file is a defect.**

⚠ **NEVER ASSUME A PAGE SIZE (`BR-INT-072`).** ArcGIS layers publish their own
`maxRecordCount` and it is 1000 on many services, 2000 on some, 500 on others
and whatever an administrator set on the rest. Asking for more than the service
allows does not fail — **it silently returns the service's own maximum**, so a
hard-coded 1000 against a layer capped at 500 walks the register at half the
stride it thinks it has and, with a naive offset, reads every second page twice
and never notices. The size is READ from `/FeatureServer/<layer>?f=json`.

⚠ **`outSR=4326` ON EVERY PAGE, ALWAYS.** A Feature Service returns geometry in
the layer's OWN spatial reference unless told otherwise, and a municipal layer
is very often in a projected State Plane frame where coordinates are six- and
seven-digit foot offsets. Those numbers fit happily into a `NUMERIC(9,6)` column
**by being silently wrong** — `2,112,340.55` truncated into three integer
digits, or refused, depending on the driver's mood. `BR-INT-049` says a
coordinate carries its frame; this asks for the frame we store in, and
`spatial_reference_of` checks that the answer came back in it.

⚠ **A HALF PULL IS NOT A SMALL PULL — IT IS A CLAIM THAT THE CITY DELETED
EVERYTHING IT DID NOT SEND** (`BR-INT-072`, ruling 4). `walk` raises rather than
returning what it has. There is no partial snapshot type in this module on
purpose: a caller cannot accidentally reconcile against one, because one cannot
be constructed.

HOW PAGING ACTUALLY TERMINATES, AND THE TWO WAYS IT GOES WRONG
----------------------------------------------------------------
The service sets `exceededTransferLimit: true` when there is more. It is
**absent** on the last page rather than `false`, on many versions, so the walk
tests it as *truthy* and never as *present*.

Two failure shapes this guards, both of which read as success:

1. **An unstable order.** Without `orderByFields` a service may return rows in
   any order between calls, so offset paging can repeat some rows and skip
   others while every page looks perfectly well formed. The walk orders by the
   layer's own `objectIdField`, which is the one field guaranteed to exist, to
   be unique and to be sortable.
2. **A service that ignores `resultOffset`.** Then page 2 is page 1 again, and a
   naive loop runs until it has read the same thousand rows for ever. The walk
   refuses when a page returns a set of object ids it has already seen, and says
   so by name — which is cheaper than a cap on page count, because a cap is a
   number somebody has to keep correct as the register grows.

WHAT WOULD MAKE THIS READ WRONGLY (hard-won law 7, habit 2)
-------------------------------------------------------------
* **A layer with zero rows and a layer that refused both produce no features.**
  So `walk` distinguishes them: a refusal raises, and an empty layer returns an
  empty snapshot whose `pages` count is 1. A caller can tell *nothing there*
  from *nothing came back*.
* **A field the city renamed** would silently read as blank on every row and
  reconcile as *blank theirs* on the whole register. `attributes_present`
  reports which configured field names were actually found on the first page, so
  the run can stop rather than file 40,000 differences.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from core import gis_http

#: `BR-INT-049` — the one frame this product stores coordinates in, and the one
#: `premises.lat/lng` and `units.lat/lng` are declared for. Asked for on every
#: page and checked on every answer.
DECLARED_FRAME = "EPSG:4326"
DECLARED_WKID = 4326

#: What a `NUMERIC(9,6)` column can actually hold: three integer digits and six
#: decimals. Latitude never needs more than two integer digits and longitude
#: never more than three, so every lawful WGS 84 coordinate fits — and every
#: PROJECTED one does not, which is the point of checking rather than assuming.
#: Ann Arbor sits near 42.28, −83.74: eight significant digits each.
COORDINATE_MAX = Decimal("999.999999")

Transport = Callable[[str, float], Any]


#: ── `DEF-INT-9846` / `DEF-INT-5620` · WHICH REFUSAL IT WAS ─────────────────
#: The three things a City can mean when it ANSWERS and refuses us, each a
#: different job for a different person: a rotated or wrong key is the
#: utility's admin, a moved layer is the City's GIS team, an error on their
#: side is nobody's to fix but time. ⚠ **ONE CLASSIFIER FOR BOTH PROTOCOLS** —
#: the address search (`adapters/gis_city.py`) and the layer walk below read
#: the same numbers, so a 404 cannot mean *moved* on one screen and *error* on
#: the other.
REFUSED_KEY = "key"
REFUSED_MOVED = "moved"
REFUSED_ERROR = "error"
#: ── `DEF-INT-10019` · 2026-10-07 · SOMETHING IN FRONT OF THE CITY SAID NO ──
#: A `403` whose body is NOT ArcGIS's JSON — Cloudflare's `error code: 1010`,
#: a *Just a moment…* challenge page, any HTML or text, an empty body. ArcGIS
#: always answers in JSON; a `403` that does not is a firewall or CDN in front
#: of the service, and the person who fixes it is the City's network team
#: (or ours, by sending an agent they allow) — never the utility's admin with
#: a key it may not even have. PO ruling 2026-10-07, decision log.
REFUSED_FIREWALL = "firewall"

_NO_BODY = object()


def refusal_reason(code: Any, body: Any = _NO_BODY) -> str:
    """An HTTP status (with its body, when there was one) or the `code` in an
    ArcGIS `{"error": {...}}` body → why.

    ArcGIS mirrors HTTP in its error body and adds two of its own: `498`
    (invalid token) and `499` (token required). `400` is how a FeatureServer
    answers a field name or a layer path it no longer has, so it reads as
    *moved* rather than *error* — the fix is the same person's either way.
    Anything unrecognised is *their error*: the honest default when we cannot
    tell, and never a claim about our key.

    ⚠ **A `403` IS READ WITH ITS BODY (`DEF-INT-10019`).** Until 2026-10-07 every
    `403` was *key*, and Ann Arbor's Cloudflare refusing Python's default
    User-Agent with `error code: 1010` reached the clerk as *"The city rejected
    our key"* on a connection that stores no key. With a body that is not
    ArcGIS JSON it is `REFUSED_FIREWALL`; with ArcGIS's own `{"error": ...}`
    it stays *key*. A caller that has only an ArcGIS body's `code` passes no
    body — that code IS ArcGIS speaking — and keeps today's reading.
    """
    try:
        number = int(str(code).strip())
    except (TypeError, ValueError):
        return REFUSED_ERROR
    if number == 403 and body is not _NO_BODY and not gis_http.is_arcgis_error(body):
        return REFUSED_FIREWALL
    if number in (401, 403, 498, 499):
        return REFUSED_KEY
    if number in (400, 404, 410):
        return REFUSED_MOVED
    return REFUSED_ERROR


class LayerRefused(Exception):
    """The service answered, and what it said was not a page of our layer.

    `reason` is one of the three `REFUSED_*` words when the City refused us by
    status or by an `error` body, and `None` for every refusal that is OUR
    reading of a well-formed answer (no features list, the wrong frame) —
    those are not the City saying no, and naming a key for them would send
    somebody to rotate a credential that is fine.
    """

    def __init__(
        self, message: str, *, reason: str | None = None, evidence: str | None = None
    ) -> None:
        super().__init__(message)
        self.reason = reason
        #: `DEF-INT-10019` — `"<status>, <first 200 characters of the body>"`,
        #: what the run row's `provider_error` keeps so the next person can
        #: read who refused us without access to the server.
        self.evidence = evidence


def _refused_by_status(exc: urllib.error.HTTPError, where: str) -> LayerRefused:
    body = gis_http.error_body(exc)
    return LayerRefused(
        f"the city refused {where} with HTTP {exc.code}",
        reason=refusal_reason(exc.code, body),
        evidence=gis_http.evidence(exc.code, body),
    )


def _refused_by_body(problem: Any, where: str) -> LayerRefused:
    code = problem.get("code") if isinstance(problem, Mapping) else None
    return LayerRefused(
        f"the city refused {where}: {problem}",
        reason=refusal_reason(code),
        # ArcGIS answered `200 OK` and refused inside the body.
        evidence=gis_http.evidence(200, {"error": problem}),
    )


class LayerIncomplete(Exception):
    """The walk could not finish. **Nothing partial is ever returned.**"""


def _urllib_transport(url: str, timeout_s: float) -> Any:
    """The ONE network call in this file. `timeout_s` is the caller's number.

    `DEF-INT-10019` — through `core.gis_http.fetch_json`, which sends
    `User-Agent: SMARTBillHub-GIS/<version> (support@bynry.io)`. A bare
    `urlopen` here sent `Python-urllib/3.x`, and a City's Cloudflare refused it.
    """
    return gis_http.fetch_json(url, timeout_s)


# ═══════════════════════════════════════════════════════════════════════════
# The pure half — no network, no clock, no database
# ═══════════════════════════════════════════════════════════════════════════

#: The street-type and direction abbreviations two spellings of one address
#: differ by. Expanded on BOTH sides before comparison, never on the stored
#: value — we keep what each side said and compare a derived form, because a
#: normalised string written back would be us correcting the City's spelling and
#: then reporting no difference.
#:
#: ⚠ **THIS IS A COMPARISON AID AND NOT A POSTAL STANDARD.** It covers what a
#: municipal address register and a utility's own list actually differ by. A
#: pair it does not know simply fails to match and QUEUES, which is the safe
#: direction: an unmatched row is a person's decision, a wrongly-matched row is
#: somebody else's parcel copied onto our premises for ever.
STREET_WORDS: dict[str, str] = {
    "st": "street", "str": "street", "street": "street",
    "ave": "avenue", "av": "avenue", "avenue": "avenue",
    "rd": "road", "road": "road",
    "dr": "drive", "drive": "drive",
    "blvd": "boulevard", "boulevard": "boulevard",
    "ln": "lane", "lane": "lane",
    "ct": "court", "court": "court",
    "pl": "place", "place": "place",
    "ter": "terrace", "terrace": "terrace",
    "cir": "circle", "circle": "circle",
    "pkwy": "parkway", "pky": "parkway", "parkway": "parkway",
    "hwy": "highway", "highway": "highway",
    "trl": "trail", "trail": "trail",
    "way": "way",
    "sq": "square", "square": "square",
    "n": "north", "no": "north", "north": "north",
    "s": "south", "so": "south", "south": "south",
    "e": "east", "east": "east",
    "w": "west", "west": "west",
    "ne": "northeast", "northeast": "northeast",
    "nw": "northwest", "northwest": "northwest",
    "se": "southeast", "southeast": "southeast",
    "sw": "southwest", "southwest": "southwest",
}


def normalise_street(raw: Any) -> str:
    """One street line, reduced to what two spellings of it have in common.

    Case, punctuation and the abbreviations in `STREET_WORDS` all go, so
    `1408 N. Pecan St.` and `1408 north pecan street` are one string.

    ⚠ **THE RESULT IS NEVER STORED.** It is a comparison key computed on both
    sides at compare time. Writing it back would be us quietly correcting the
    City's spelling and then truthfully reporting that we agree with them.
    """
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    cleaned = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text)
    return " ".join(STREET_WORDS.get(word, word) for word in cleaned.split())


def normalise_unit(raw: Any) -> str:
    """A unit label, reduced the same way. `Apt 2B`, `APT. 2-B` and `2b` agree.

    The leading word is dropped when it is one a register uses to mean *this is
    a unit* — they carry no information and the two sides rarely use the same
    one. What is left is the label itself, which is what `units.label` holds.
    """
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
    words = cleaned.split()
    while words and words[0] in ("apt", "apartment", "unit", "ste", "suite", "no", "num", "rm", "room", "#"):
        words = words[1:]
    return "".join(words)


def normalise_postcode(raw: Any) -> str:
    """A postcode, compared on its first five digits.

    ⚠ **KEPT AS TEXT AND NEVER MADE A NUMBER — A LEADING ZERO MUST SURVIVE.**
    `07001` read as an integer is `7001`, which is a different place. The ZIP+4
    suffix is dropped FOR COMPARISON only: a City publishing `48104-1234` and a
    utility holding `48104` are the same postcode, and treating them as a
    difference would file one on every row in the register.
    """
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return digits[:5]


def assemble_street(row: Mapping[str, Any]) -> str:
    """The address line from its parts, in the order a US address is spoken.

    Used only when the register's own assembled `Street` field is EMPTY. The
    parts go number · number-suffix · direction-prefix · name · name-suffix ·
    direction-suffix — `1408`, `½`, `N`, `Pecan`, `St`, `W`.

    ⚠ **THE ORDER IS THE WHOLE VALUE OF THIS FUNCTION.** Prefix and suffix
    directions are different fields that both hold `N`, and a version that
    appended them in field order would turn `1408 N Pecan St` into
    `1408 Pecan St N` — a different, plausible, wrong address that normalises to
    a different key and matches nothing.
    """
    parts = [
        row.get("St_Number"),
        row.get("St_Number_Sfx"),
        row.get("St_Dir_Pfx"),
        row.get("St_Name"),
        row.get("St_Name_Sfx"),
        row.get("St_Dir_Sfx"),
    ]
    return " ".join(str(one).strip() for one in parts if str(one or "").strip())


def decimal_or_none(value: Any, *, places: str = "0.000001") -> Decimal | None:
    """A coordinate at six decimal places, or `None` when it cannot be one.

    ⚠ **A NUMBER TOO BIG FOR THE COLUMN COMES BACK `None`, NOT TRUNCATED.**
    `premises.lat/lng` and `units.lat/lng` are `NUMERIC(9,6)`; a projected
    coordinate is six or seven integer digits and does not fit. Truncating it
    would put the property somewhere real and wrong, which is the one outcome
    worse than having no pin at all (ruling 6: *"leave the building's pin
    blank"*).
    """
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite():
        return None
    if abs(number) > COORDINATE_MAX:
        return None
    return number.quantize(Decimal(places))


def spatial_reference_of(payload: Mapping[str, Any]) -> int | None:
    """The wkid the service actually answered in — `latestWkid` wins.

    ArcGIS reports both `wkid` and `latestWkid`, and for 4326 they agree; where
    they do not, `latestWkid` is the current code. Returning `None` means the
    service did not say, which `walk` treats as a refusal rather than a
    permission — `BR-INT-049`, a coordinate with no frame is the defect.
    """
    reference = payload.get("spatialReference")
    if not isinstance(reference, Mapping):
        return None
    for key in ("latestWkid", "wkid"):
        value = reference.get(key)
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════════
# The shapes
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LayerConfig:
    """Everything city-specific, in ONE place, read off the connection.

    ⚠ **EVERY FIELD HERE IS PER-TENANT CONFIGURATION (`BR-INT-037`).** Not one
    of them has a default that names a real city. `parcel_field` and
    `point_field` are the two the PO's rulings are specifically about: Ann
    Arbor calls them `PIN` and `FULLPIN`, and the next city will not.
    """

    #: The full service address, up to and including the layer — e.g.
    #: `…/FeatureServer/0`. The `/query` and the `?f=json` are this module's.
    layer_url: str
    #: Which of the layer's fields is the PARCEL id (one lot).
    parcel_field: str = "PIN"
    #: Which is the ADDRESS POINT id (one per unit).
    point_field: str = "FULLPIN"
    #: The rest of the mapping, ours ← theirs. Defaults are the field names the
    #: brief documents for Ann Arbor's layer and are **overridden per tenant**;
    #: they are here so an unconfigured connection reads something rather than
    #: nothing, and `attributes_present` reports what was actually found.
    fields: Mapping[str, str] = field(
        default_factory=lambda: {
            "street": "Street",
            "city": "City",
            "state": "State",
            "postcode": "Zip",
            "unit": "Unit",
            "status": "Status",
        }
    )


def field_names_from(
    mapping: Mapping[str, Any] | None, *, layer_url: str = ""
) -> LayerConfig:
    """A connection's `field_mapping` → a `LayerConfig`. **ONE READER OF IT.**

    ⚠ **THIS EXISTS SO THAT A TENANT TYPES THEIR FIELD NAMES ONCE AND BOTH
    PATHS OBEY THEM.** Two things read a city's layer — the nightly parcel
    reconciliation (`gis_parcels`) and the live address search a clerk drives
    (`adapters/gis_city`) — and until `DEF-INT-5618` only the first one read
    this mapping at all. Giving the second its own copy of the merge would have
    been the seventh URL resolver's mistake in a different file: two readers of
    one setting drift, and the drift shows up as *the City has no match* on a
    city that answered perfectly.

    **An unmapped key keeps the documented default** rather than going blank, so
    a connection nobody has configured reads something; `parcel_field` and
    `point_field` are named separately from the other six because the PO's
    rulings of 2026-09-17 are specifically about those two.

    `layer_url` is optional here because the SEARCH path does not need one — it
    builds its own query address — while the reconciliation run does and
    refuses without it. That refusal stays where it belongs, in the caller.
    """
    mapping = dict(mapping or {})
    defaults = LayerConfig(layer_url=layer_url)
    return LayerConfig(
        layer_url=layer_url,
        parcel_field=str(mapping.get("parcel_field") or defaults.parcel_field),
        point_field=str(mapping.get("point_field") or defaults.point_field),
        fields={
            **dict(defaults.fields),
            **{
                key: str(value)
                for key, value in mapping.items()
                if key not in ("parcel_field", "point_field") and value
            },
        },
    )


@dataclass(frozen=True)
class ParcelRow:
    """One address point of the City's, in our words. Frozen: a snapshot row."""

    parcel_id: str
    point_id: str
    address_line: str
    city: str | None
    state: str | None
    postal_code: str | None
    unit_label: str | None
    status: str | None
    lat: Decimal | None
    lng: Decimal | None

    @property
    def street_key(self) -> str:
        return normalise_street(self.address_line)

    @property
    def postcode_key(self) -> str:
        return normalise_postcode(self.postal_code)

    @property
    def unit_key(self) -> str:
        return normalise_unit(self.unit_label)

    @property
    def is_building_point(self) -> bool:
        """No unit on this point, so it is the BUILDING's own.

        Ruling 6 of 2026-09-17: a premises takes its pin from the point whose
        `Unit` is empty, and from no other. *"a) leave the building's pin
        blank"* — never borrow a unit's, never average them.
        """
        return not self.unit_key


@dataclass(frozen=True)
class Snapshot:
    """The whole layer as it was at one moment, pinned to one run.

    ⚠ **A FAILED WALK NEVER BUILDS ONE.** `walk` raises `LayerIncomplete`
    instead of constructing one of these with what it managed to read. A half
    snapshot reconciles as *the City deleted the rows it did not send*.

    ⚠ **AMENDED 2026-10-07 (`DEF-INT-9849`): A PERSON MAY ASK FOR A FEW PAGES.**
    That is a different thing from a failure and it is marked as one —
    `complete = False` — so it can never be read as the register. See `complete`.
    """

    rows: tuple[ParcelRow, ...]
    pages: int
    page_size: int
    wkid: int
    #: Which CONFIGURED field names were actually found on the first page. A
    #: name the City has since renamed reads as blank on every row and would
    #: reconcile as *blank theirs* across the whole register; the run stops on
    #: this rather than filing 40,000 differences.
    attributes_present: tuple[str, ...]
    attributes_missing: tuple[str, ...]
    #: ── `DEF-INT-9849` (PO GIS review gap 3) · A PAGE LIMIT A PERSON ASKED FOR ─
    #: ⚠ **THE ONE PARTIAL SNAPSHOT THAT EXISTS, AND IT CARRIES ITS OWN NAME.**
    #: `complete` is `False` ONLY when a caller passed `stop_after_pages` and the
    #: City still had pages left — never on a failure, which still raises. A
    #: reader cannot mistake it for the register: `gis_parcels.run` refuses to
    #: APPLY one, and every report built from one says *stopped after N of M
    #: pages* (`pages` of `total_pages`) rather than counting what it did not read.
    complete: bool = True
    #: How many rows the City says it holds (`returnCountOnly`), read only when a
    #: walk stops early; `None` when the City would not say. Never guessed.
    total_rows: int | None = None

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def total_pages(self) -> int | None:
        """The City's whole register in pages, or `None` when it would not say."""
        if self.complete:
            return self.pages
        if self.total_rows is None or self.page_size <= 0:
            return None
        return max(-(-int(self.total_rows) // int(self.page_size)), self.pages)


# ═══════════════════════════════════════════════════════════════════════════
# The wire
# ═══════════════════════════════════════════════════════════════════════════


def layer_base(raw: Any) -> str:
    """The LAYER address, with any `/query` the clerk typed taken off the end.

    ⚠ **THIS IS NOT TIDYING — WITHOUT IT THE CONNECTOR'S OWN DEFAULT IS
    BROKEN.** `manifests/gis_esri.py` seeds *Service address* with
    `…/FeatureServer/0/query`, because that is the URL a city publishes and the
    one a clerk has in front of them. This module appends `/query` itself (and
    `?f=json` to the bare layer for metadata), so taking the field at face value
    builds `…/FeatureServer/0/query/query` — a 404 on every page, and a metadata
    read that asks a query endpoint to describe itself.

    Found by reading the manifest default rather than by a test failing, which
    is the direction hard-won law 6 is about: the fixture used a bare layer url
    and would have gone on passing for ever.
    """
    base = str(raw or "").strip().rstrip("/")
    if base.lower().endswith("/query"):
        base = base[: -len("/query")]
    if "://" not in base:
        base = f"https://{base}"
    return base


def query_url(
    config: LayerConfig,
    *,
    where: str,
    api_key: str | None = None,
    return_geometry: bool = True,
    **extra: str,
) -> str:
    """ONE spelling of an ArcGIS `/query` — for the nightly walk AND the search.

    ⚠ **TWO REQUEST BUILDERS WAS THE DEFECT (`DEF-INT-9843`, `DEF-INT-9844`).**
    The walk below always sent `where`, `outSR=4326` and `token`; the live
    address search built its own URL with `q=`, `limit=` and `key=` — a
    geocoder's dialect, which a FeatureServer IGNORES. So the City never
    filtered by what the clerk typed, and a layer stored in State Plane would
    have answered the search in feet. Both callers now come through here, so
    `outSR` cannot be forgotten by one of them again.

    `extra` carries what differs between the callers — paging and ordering for
    the walk, a row count for the search — appended AFTER the shared five.
    """
    base = layer_base(config.layer_url)
    params = {
        "where": where,
        "outFields": "*",
        # `BR-INT-049` — ALWAYS, on every request. See the module docstring for
        # what a projected frame does to a NUMERIC(9,6) column.
        "outSR": str(DECLARED_WKID),
        "returnGeometry": "true" if return_geometry else "false",
        "f": "json",
        **extra,
    }
    if api_key:
        params["token"] = api_key
    return f"{base}/query?{urllib.parse.urlencode(params)}"


def _query_url(config: LayerConfig, *, offset: int, size: int, order_by: str,
               where: str = "1=1", api_key: str | None = None) -> str:
    return query_url(
        config,
        where=where,
        api_key=api_key,
        resultOffset=str(offset),
        resultRecordCount=str(size),
        # Without this a service may answer in any order between calls, and
        # offset paging then repeats some rows and skips others while every
        # page looks well formed.
        orderByFields=order_by,
    )


def _metadata_url(config: LayerConfig, *, api_key: str | None = None) -> str:
    base = layer_base(config.layer_url)
    params = {"f": "json"}
    if api_key:
        params["token"] = api_key
    return f"{base}?{urllib.parse.urlencode(params)}"


def read_layer_metadata(
    config: LayerConfig,
    *,
    transport: Transport | None = None,
    timeout_s: float = 30.0,
    api_key: str | None = None,
) -> tuple[int, str]:
    """`(page_size, object_id_field)` — the layer's OWN numbers, never ours.

    ⚠ **`maxRecordCount` IS READ AND NOT ASSUMED (`BR-INT-072`).** Asking a
    service for more rows than it allows does not fail: it returns the
    service's own maximum, so a hard-coded 1000 against a layer capped at 500
    strides through the register at half the rate the offsets assume. Every
    page after the first would then start in the wrong place.
    """
    send = transport or _urllib_transport
    # ── `DEF-INT-9846` · THE FIRST CALL OF THE WALK HAD NO `try` AT ALL ──────
    # ⚠ **A WRONG KEY OR A MOVED LAYER IS ANSWERED HERE FIRST, AND IT WAS OUR
    # 500.** `walk`'s page loop below turns a failure into `LayerIncomplete`,
    # but this read sat above it bare, so a `401` or a `404` on the metadata
    # escaped `gis_parcels.run` — which catches only this module's two
    # exceptions — and `POST …/reconcile` answered `SYS-INTERNAL`. `HTTPError`
    # is caught FIRST because it is a `URLError`: the City answering *no* is a
    # refusal, and a socket that never opened is not.
    try:
        payload = send(_metadata_url(config, api_key=api_key), timeout_s)
    except urllib.error.HTTPError as exc:
        raise _refused_by_status(exc, "the layer's metadata") from exc
    except LayerRefused:
        raise
    except Exception as exc:  # noqa: BLE001 — silence, not an answer
        raise LayerIncomplete(f"the city could not be reached: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise LayerRefused("the layer's metadata was not an object")
    if "error" in payload:
        raise _refused_by_body(payload.get("error"), "the layer's metadata")
    raw_size = payload.get("maxRecordCount")
    try:
        size = int(raw_size)
    except (TypeError, ValueError):
        # ⚠ **A REFUSAL, NOT A FALLBACK TO 1000.** A layer that does not publish
        # its page size is a layer we cannot page safely, and guessing is how
        # the silent half-stride above happens. Hard-won law 3: the unsafe
        # option must be the one somebody types.
        raise LayerRefused(
            "the layer does not publish maxRecordCount, so its pages cannot be walked safely"
        ) from None
    if size <= 0:
        raise LayerRefused(f"the layer publishes maxRecordCount={size!r}")
    object_id = str(payload.get("objectIdField") or "").strip()
    if not object_id:
        raise LayerRefused("the layer does not name an objectIdField to order by")
    return size, object_id


def row_from_feature(feature: Mapping[str, Any], config: LayerConfig) -> ParcelRow | None:
    """One ArcGIS `feature` → one `ParcelRow`, or `None` when it is unusable.

    ⚠ **A ROW WITH NO PARCEL KEY AND NO POINT KEY IS DROPPED**, because it
    cannot be matched to anything and cannot be stored as a key. That is the
    only row this function refuses. **A row with an unrecognised `Status` is
    KEPT** — ruling 10 of 2026-09-17, we do not own their vocabulary, and a row
    dropped because we did not recognise a word is a row nobody can see we
    dropped.
    """
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        return None
    names = dict(config.fields)

    def pick(key: str) -> str:
        value = attributes.get(names.get(key, ""), "")
        return str(value).strip() if value is not None else ""

    parcel = str(attributes.get(config.parcel_field, "") or "").strip()
    point = str(attributes.get(config.point_field, "") or "").strip()
    if not parcel and not point:
        return None

    street = pick("street")
    if not street:
        # The register publishes an assembled `Street` and also its parts; when
        # the assembled one is blank the parts are what it has.
        street = assemble_street(attributes)

    geometry = feature.get("geometry")
    lat = lng = None
    if isinstance(geometry, Mapping):
        # ArcGIS point geometry is `x` (longitude) and `y` (latitude) — in that
        # naming, which is the reverse of how a coordinate is spoken. Getting
        # this pair the wrong way round puts every property in the Indian Ocean
        # off Somalia, which is at least obvious; getting it round in a city
        # near 42N/83W puts them in Iraq, which is not.
        lat = decimal_or_none(geometry.get("y"))
        lng = decimal_or_none(geometry.get("x"))

    state = pick("state").upper() or None
    return ParcelRow(
        parcel_id=parcel,
        point_id=point,
        address_line=street,
        city=pick("city") or None,
        state=state,
        # ⚠ **TEXT, NEVER A NUMBER — a leading zero must survive.**
        postal_code=pick("postcode") or None,
        unit_label=pick("unit") or None,
        status=pick("status") or None,
        lat=lat,
        lng=lng,
    )


def walk(
    config: LayerConfig,
    *,
    transport: Transport | None = None,
    timeout_s: float = 60.0,
    api_key: str | None = None,
    page_size: int | None = None,
    object_id_field: str | None = None,
    pace: Callable[[int], None] | None = None,
    resume_from: int = 0,
    max_pages: int = 500,
    stop_after_pages: int | None = None,
) -> Snapshot:
    """The whole layer, paged, in one snapshot — or nothing at all.

    ⚠ **ALL OR NOTHING (`BR-INT-072`, ruling 4).** A pull that fails halfway
    raises `LayerIncomplete` and returns no snapshot. Reconciling against a half
    pull reads as *the City deleted the 40,000 addresses it did not send*, and
    under a disposition that applied blanks it would do exactly that to our
    register.

    `pace` is called with the page number before each request after the first —
    that is the THROTTLE, handed in rather than implemented here, so a test can
    walk 40,000 rows instantly and production can be polite. `resume_from` is an
    offset a previous attempt reached; the walk is resumable because a register
    of 70,000 rows over a municipal service is a long read to lose to one
    timeout.

    ⚠ **`max_pages` IS A REFUSAL AND NOT A TRUNCATION.** It is the backstop for
    a service that ignores `resultOffset` in a way the repeat check below cannot
    see. Hitting it raises; it never returns a short snapshot, because
    `BR-RBS-006`'s reasoning applies to a read as much as to a write — a cap
    that truncates reports success over work it did not do.

    ⚠ **`stop_after_pages` IS THE OPPOSITE OF `max_pages` AND THE DIFFERENCE IS
    WHO ASKED (`DEF-INT-9849`, PO GIS review gap 3).** `max_pages` is OUR
    backstop and still refuses. `stop_after_pages` is a PERSON testing the City
    by hand — PO 2026-10-07, *"we will call APi manually and test it first"* —
    inside a web request the worker kills at 60 seconds, against a register of
    ~70 pages read 6 seconds apart. It stops after that many pages and returns a
    snapshot marked `complete = False`, with the City's own row count when the
    City will give it (one `returnCountOnly` request, made ONLY when the walk
    stopped early). It is never truncation dressed as success: the type says so,
    and `gis_parcels.run` refuses to apply one.
    """
    if stop_after_pages is not None and int(stop_after_pages) < 1:
        raise ValueError(f"stop_after_pages must be at least 1, got {stop_after_pages!r}")
    send = transport or _urllib_transport
    if page_size is None or object_id_field is None:
        read_size, read_field = read_layer_metadata(
            config, transport=transport, timeout_s=timeout_s, api_key=api_key
        )
        page_size = page_size or read_size
        object_id_field = object_id_field or read_field

    rows: list[ParcelRow] = []
    seen_signatures: set[tuple[Any, ...]] = set()
    offset = int(resume_from)
    pages = 0
    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    wkid = DECLARED_WKID

    while True:
        if pages >= max_pages:
            raise LayerIncomplete(
                f"the walk reached {max_pages} pages at offset {offset} and stopped rather than "
                "returning a partial snapshot"
            )
        if pages and pace is not None:
            pace(pages)
        url = _query_url(
            config, offset=offset, size=page_size, order_by=object_id_field, api_key=api_key
        )
        try:
            payload = send(url, timeout_s)
        except LayerRefused:
            raise
        except urllib.error.HTTPError as exc:
            # `DEF-INT-9846` — the City ANSWERED, so *it stopped answering* is
            # the wrong sentence; still all-or-nothing, still no snapshot.
            raise _refused_by_status(exc, f"the page at offset {offset}") from exc
        except Exception as exc:  # noqa: BLE001 — their failure, and it stops the run
            raise LayerIncomplete(
                f"the city stopped answering at offset {offset} after {len(rows)} rows: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise LayerRefused(f"page at offset {offset} was not an object")
        if "error" in payload:
            raise _refused_by_body(payload.get("error"), f"the page at offset {offset}")

        features = payload.get("features")
        if not isinstance(features, Sequence) or isinstance(features, (str, bytes)):
            raise LayerRefused(f"page at offset {offset} carried no features list")

        if pages == 0:
            wanted = [config.parcel_field, config.point_field, *dict(config.fields).values()]
            first = features[0].get("attributes") if features else {}
            keys = set(first) if isinstance(first, Mapping) else set()
            present = tuple(name for name in wanted if name in keys)
            missing = tuple(name for name in wanted if name not in keys)
            found = spatial_reference_of(payload)
            if features and found is None:
                # `BR-INT-049` — a coordinate with no frame is the defect that
                # rule is about. We ASKED for 4326; a service that will not say
                # what it answered in has not answered the question.
                raise LayerRefused(
                    "the city returned geometry without naming its spatial reference"
                )
            if found is not None:
                if found != DECLARED_WKID:
                    raise LayerRefused(
                        f"the city answered in EPSG:{found} after being asked for "
                        f"EPSG:{DECLARED_WKID}; its coordinates are not ours to store"
                    )
                wkid = found

        # ⚠ A service that IGNORES `resultOffset` answers page 1 for ever, and
        # every page of it looks perfectly well formed. This is what notices.
        signature = tuple(
            str((one.get("attributes") or {}).get(object_id_field))
            for one in features
            if isinstance(one, Mapping)
        )
        if signature and signature in seen_signatures:
            raise LayerIncomplete(
                f"the city returned the same {len(signature)} rows again at offset {offset}; "
                "it is not honouring resultOffset and the walk cannot be trusted"
            )
        seen_signatures.add(signature)

        for one in features:
            if not isinstance(one, Mapping):
                continue
            row = row_from_feature(one, config)
            if row is not None:
                rows.append(row)

        pages += 1
        # Absent means *the last page*, on many versions — so this is a
        # truthiness test and never a presence test.
        if not payload.get("exceededTransferLimit"):
            break
        offset += len(features) or page_size
        if stop_after_pages is not None and pages >= int(stop_after_pages):
            # `DEF-INT-9849` — the person asked for this many and the City has
            # more. Stop, say so in the type, and ask how many there are.
            return Snapshot(
                rows=tuple(rows),
                pages=pages,
                page_size=int(page_size),
                wkid=wkid,
                attributes_present=present,
                attributes_missing=missing,
                complete=False,
                total_rows=count_rows(config, transport=transport, timeout_s=timeout_s,
                                      api_key=api_key),
            )

    return Snapshot(
        rows=tuple(rows),
        pages=pages,
        page_size=int(page_size),
        wkid=wkid,
        attributes_present=present,
        attributes_missing=missing,
    )


def count_rows(
    config: LayerConfig,
    *,
    transport: Transport | None = None,
    timeout_s: float = 60.0,
    api_key: str | None = None,
) -> int | None:
    """How many rows the City's layer holds — `returnCountOnly` — or `None`.

    ⚠ **`None` IS AN ANSWER AND A GUESS IS NOT.** Read only to say *stopped after
    3 of 70 pages* honestly (`DEF-INT-9849`). A City that refuses the count, or
    answers it with something that is not a whole number, leaves the total
    unknown and the report says *stopped after 3 pages* — never a number we
    made up. Nothing here raises: the pages already read are the answer the
    person asked for, and a failed count must not throw them away.
    """
    send = transport or _urllib_transport
    url = query_url(config, where="1=1", api_key=api_key, return_geometry=False,
                    returnCountOnly="true")
    try:
        payload = send(url, timeout_s)
    except Exception:  # noqa: BLE001 — an unknown total, never a lost walk
        return None
    if not isinstance(payload, Mapping) or "error" in payload:
        return None
    raw = payload.get("count")
    if isinstance(raw, bool):
        return None
    try:
        total = int(raw)
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-112 (the ten PO rulings of 2026-09-17, decision log of that date)
# generated: 2026-09-17 by the CR-112 GIS build lane
# checklist: A✔ B=n/a(no screen reads this) C✔ D=n/a(no route) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr112_gis_layer.py
# exceptions: none — this file holds no city name, no database call and no Django import, which is what makes it the protocol half
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
