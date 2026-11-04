# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — the inline address search: candidates in
#           under a second, nothing written until a person picks a row.
#           Screens: the premises create form step 1 (frames 66.1 / 66.2) · S8
# Rules:    BR-INT-048 (`C15` a latency budget, not a job; `C16` disposition
#           `offer`) · BR-INT-038 (an adapter TRANSLATES and decides nothing) ·
#           BR-INT-019 (`test()` is the smallest REAL instance — one address
#           looked up, never "does the key parse") · BR-INT-003 (no secret in
#           a sentence, a log or a `describe()`) · BR-INT-049 (a coordinate
#           carries its measurement frame)
# Tests:    06-backend/tests/test_us_int_042_gis.py · the conformance kit
# Impacts:  apps/integrations/adapters/__init__.py (the ONE line that binds it)
#           · apps/integrations/gis.py (the service that calls it under the
#           breaker) · apps/integrations/manifests/gis_esri.py
# ───────────────────────────────────────────────────────
"""City GIS — translate an address the clerk is typing into candidates.

WHAT IT DOES, AND THE THREE THINGS IT DOES NOT
-----------------------------------------------
`execute()` takes one item — the fragment a clerk has typed — and answers with
the city's candidates, each carrying a parcel key, an address, a coordinate and
its measurement frame. That is the whole job.

It does **not** decide whether a candidate is a *strong* or a *close* match in
words (`gis.py` does, from the city's own number, because a WORD shown to a
clerk is product language and not the provider's); it does **not** write a
premises (`C16` — the disposition is `offer`, and nothing is written until a
person picks); and it does **not** retry, pace or open a breaker
(`runtime.guarded_call` does, and `BR-INT-038` says an adapter that did any of
it would be the same policy in a second place).

THE TRANSPORT IS AN ARGUMENT, NOT A PATCH TARGET
-------------------------------------------------
`apps/metering/geocode.py` established this shape in `CR-028` and it is kept:
one `transport` callable, url → parsed JSON, defaulting to the only `urllib`
call in this file. A test that patched a module attribute would keep passing on
the day somebody renamed the attribute.

⚠ **THE DEADLINE IS THE CALLER'S NUMBER AND IT IS HANDED DOWN, NOT INVENTED
HERE.** `runtime.guarded_call`'s docstring is explicit that Python cannot
interrupt a blocking socket read from outside, so the adapter gives its
transport the timeout it was handed and raises `ProviderTimeout` when the wall
clock passes it. A `requests` timeout hard-coded in this file would be the
`C15` budget written down twice, and the second copy is the one that goes
stale.

⚠ **A `.example` HOST IS NEVER DIALLED.** `US-INT-042` §4's test data is
`https://gis.brazosbend.example/addr`, and RFC 2606 reserves `.example` so it
can never resolve. `gis_fixtures.recorded_transport` serves those hosts and
only those, which is why a walkthrough can prove the 300 ms and the 4,000 ms
branches on a machine with no network and can never accidentally shadow a real
city.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations import gis_layer, gis_search
from apps.integrations.runtime import ProviderTimeout
from apps.integrations.scrubbing import scrub
from core import gis_http

#: `BR-INT-049` — the frame every coordinate this adapter emits is declared in.
#: A number with no frame is the defect that story is about; a number in a
#: PROJECTED frame is refused by name rather than written (wave Q's rule, and
#: this adapter states the frame so that check has something to check).
DECLARED_FRAME = "EPSG:4326"

#: How many candidates a clerk is shown. Frame 66.1 draws four and the blue bar
#: counts them; more than a handful is a list nobody reads.
#:
#: ⚠ **THIS IS THE CAP THE PRODUCT ENFORCES, AND `gis_search.BUILDING_CAP` (20)
#: IS NOT (`DEF-INT-5603`).** Two caps, two different units — this one counts
#: ROWS on the live inline path, that one counts BUILDINGS in a module with no
#: caller (`DEF-INT-5601`). Eight rows can never make twenty buildings, so 20
#: can never bite through here; a reader comparing the two numbers is comparing
#: a fact with a plan. Whichever survives when the grouped path is wired, the
#: number a clerk meets today is this one.
CANDIDATE_CAP = 8

Transport = Callable[[str, float], Any]

logger = logging.getLogger(__name__)


class ForeignFrame(Exception):
    """The City answered in a frame other than the one we asked for — REFUSED.

    ── 2026-10-07 · `DEF-INT-9844` ───────────────────────────────────────────
    Every search now asks for `outSR=4326`. A layer that answers in anything
    else has ignored the question, and its numbers — Michigan State Plane
    (`wkid` 2253) is in FEET, six and seven digits — are not latitude and
    longitude whatever the column they land in is called. **So the whole
    answer is refused by name and nothing in it travels**: not to the screen,
    where a pin would be drawn in the wrong hemisphere, and not to a premises.
    `gis_layer.walk` refuses the same thing on the nightly path, with the same
    reasoning, which is why the two now agree.

    ⚠ **NOT `ProviderTimeout`.** The City answered promptly and correctly
    shaped; reporting *the City is not answering* would send a clerk to wait
    for a fix that is a configuration change, and it would count towards a
    breaker built for silence. `gis.py` turns this into its own catalogue key.
    """

    def __init__(self, wkid: int) -> None:
        super().__init__(
            f"the city answered in EPSG:{wkid} after being asked for "
            f"EPSG:{gis_layer.DECLARED_WKID}; its coordinates are not ours to store"
        )
        self.wkid = wkid


def shown_and_more(found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """The rows a clerk sees, and whether the City had more than that.

    ⚠ **ONE PLACE, BECAUSE A SILENT TRUNCATION IS A LIE TO A CLERK
    (`DEF-INT-5603`).** `search()` answers with up to `CANDIDATE_CAP + 1` rows
    and this is the only thing that cuts them down, so the count on screen and
    the question *was anything dropped* are computed from one number in one
    file. Walked at the tip on 2026-09-17: a City offering SIXTEEN matching
    addresses produced eight on the wire and eight on screen under the line
    *"8 matches from the City's records"*, with no notice of any kind — so the
    row the clerk wanted could be missing and the screen positively asserted it
    was not.
    """
    return found[:CANDIDATE_CAP], len(found) > CANDIDATE_CAP


def _urllib_transport(url: str, timeout_s: float) -> Any:
    """The ONE network call in this file. `timeout_s` is the caller's number.

    `DEF-INT-10019` — through `core.gis_http.fetch_json`, the one function that
    sends `User-Agent: SMARTBillHub-GIS/<version> (support@bynry.io)`.
    """
    return gis_http.fetch_json(url, timeout_s)


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class CityRefused(Exception):
    """The City ANSWERED, and refused us — by HTTP status or by an error body.

    ── `DEF-INT-5620` / `DEF-INT-9846` · 2026-10-07 ────────────────────────────
    ⚠ **A REFUSAL IS NOT SILENCE, AND IT USED TO BE ONE OF TWO WRONG THINGS.**
    An `HTTPError` was re-raised bare and reached the clerk as OUR `500`; an
    ArcGIS `200` with an `error` body was dressed as `ProviderTimeout` and
    reached them as *the City is not answering* while moving the breaker. This
    is the third thing, and the true one: `reason` is one of
    `gis_layer.REFUSED_KEY` / `REFUSED_MOVED` / `REFUSED_ERROR`, and the caller
    says which in words.

    ⚠ **IT DOES NOT TOUCH THE BREAKER, BY CONSTRUCTION.** `runtime.guarded_call`
    re-raises anything that is not `ProviderTimeout` without persisting a
    breaker state — *"an answer, even an unhappy one"* — so a 401 for a rotated
    key can never stop us dialling a City that is answering perfectly well.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        status: int | None = None,
        evidence: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.status = status
        #: `DEF-INT-10019` — `"<status>, <first 200 characters of the body>"`
        #: (e.g. `403, error code: 1010`), kept on the run row's
        #: `provider_error` so who refused us is readable without the server.
        self.evidence = evidence


def _refuse_if_the_city_said_no(payload: Any) -> None:
    """An ArcGIS query error arrives as **HTTP 200**. Do not read it as zero.

    ⚠ **THE SECOND SILENT ZERO OF `DEF-INT-5618`, AND THE ONE THAT WOULD HAVE
    OUTLIVED THE FIRST.** A FeatureServer reports a bad field name, an expired
    token or a moved layer with `200 OK` and an `error` object, carrying no
    `features` array at all. `_rows` finds no list and returns `[]`; `search`
    returns `[]`; the endpoint answers 200; and the screen says **"The City has
    no match for that."** So a connector misconfigured on go-live day refuses
    every address in the city, for ever, with nothing red anywhere — the same
    shape as the parse bug one level down, arriving by a different road.

    ⚠ **IT RAISED `ProviderTimeout` UNTIL 2026-10-07, AS A WRITTEN COMPROMISE,
    AND THE COMPROMISE IS OVER (`DEF-INT-5620`, `DEF-INT-9846`).** That
    reached a clerk as *the City is not answering* — untrue, the City answered
    and refused us — and it moved `BR-INT-022`'s breaker, which
    `runtime.after_refusal` says must count SILENCE and only silence. It now
    raises `CityRefused` with the City's own code classified by
    `gis_layer.refusal_reason`, the same classifier the layer walk uses, and
    `gis.search` turns that into the amber box with the reason in words.
    """
    if not isinstance(payload, Mapping):
        return
    problem = payload.get("error")
    if not isinstance(problem, Mapping):
        return
    # The city's own words, scrubbed — never ours invented on top of theirs.
    said = str(problem.get("message") or "").strip()
    code = problem.get("code")
    raise CityRefused(
        gis_layer.refusal_reason(code),
        scrub(f"the city refused the query ({code}): {said}" if said else f"the city refused the query ({code})"),
        evidence=gis_http.evidence(200, {"error": dict(problem)}),
    )


def _arcgis_flat(
    feature: Mapping[str, Any], config: gis_layer.LayerConfig
) -> dict[str, Any] | None:
    """An ArcGIS `feature` → the FLAT shape `candidate_from` reads below.

    ⚠ **`DEF-INT-5618` — THE GOING-LIVE BLOCKER, AND IT IS WHY THIS FUNCTION
    EXISTS RATHER THAN A SECOND PARSER.** An ArcGIS FeatureServer does not
    answer in flat rows: its fields live under `attributes` and its coordinates
    under `geometry`, as `x` (longitude) and `y` (latitude). `candidate_from`
    read flat, lower-case keys, so against a real layer **every field read
    empty, every feature was dropped for having no parcel and no address, and
    the screen drew *"The City has no match for that."* on every address in the
    city** — indistinguishable from a healthy connector talking to a city that
    has never heard of you.

    ⚠ **THE PARSER WAS ALREADY WRITTEN AND HAD NO CALLER.**
    `gis_layer.row_from_feature` reads `attributes`, reads `geometry` in the
    right order, assembles the six-part street when the register publishes the
    parts rather than the whole, keeps a row whose `Status` we do not recognise
    (ruling 10 — we do not own their vocabulary), and refuses a coordinate too
    large for `NUMERIC(9,6)` instead of truncating it into the wrong country.
    Writing a second parser here would have been the seventh URL resolver in a
    different file. This is a SHAPE ADAPTER over that one, nothing more.

    ⚠ **THE FIELD NAMES ARE THE TENANT'S** (`BR-INT-037`), read through
    `gis_layer.field_names_from` — the same reader the nightly reconciliation
    uses, so a city types `PARCELID` into the form once and both paths obey it.
    """
    parsed = gis_layer.row_from_feature(feature, config)
    if parsed is None:
        return None
    return {
        "parcel": parsed.parcel_id,
        "point": parsed.point_id,
        "address": parsed.address_line,
        "city": parsed.city or "",
        "state": parsed.state or "",
        "postal_code": parsed.postal_code or "",
        "lat": parsed.lat,
        "lng": parsed.lng,
        "status": parsed.status or "",
        # ── DEF-INT-9845 · THE CITY'S `Unit`, ON THE WIRE AT LAST ─────────────
        # `row_from_feature` has read it since `CR-112` — through the tenant's
        # `field_mapping`, like `Street` and `PIN` — and this flattening step
        # dropped it, so every candidate looked like a building point and
        # `gis_search.candidates_to_rows` read a `unit` nothing produced.
        "unit": parsed.unit_label or "",
        # ⚠ AN ARCGIS FEATURE CARRIES NO RELEVANCE SCORE. A geocoder ranks its
        # answers; a FeatureServer query returns the rows that matched, in the
        # layer's own order. Inventing a score here would put a confidence word
        # on screen that nothing measured — so there is none, and `match_word`
        # says so rather than guessing.
        "score": feature.get("score"),
    }


def candidate_from(
    row: Mapping[str, Any],
    config: gis_layer.LayerConfig | None = None,
    *,
    frame: str | None = None,
) -> dict[str, Any] | None:
    """One of the city's rows, in our shape — or `None` when it is unusable.

    ⚠ **TWO SHAPES ARRIVE HERE AND BOTH ARE REAL** (`DEF-INT-5618`). A geocoder
    answers in FLAT rows and an ArcGIS FeatureServer answers in `features` with
    `attributes` and `geometry`. **The flat path below is untouched** — every
    recorded fixture in this repo is flat, and swapping one shape for the other
    would have broken every city that answers a geocoder. A row carrying
    `attributes` is flattened first; anything else falls through exactly as it
    always did.

    ⚠ **A ROW WITHOUT A PARCEL KEY IS DROPPED RATHER THAN SHOWN.** The entire
    value of picking a candidate over typing one is that the premises carries
    the city's key; a candidate with no key is a nicely formatted address a
    clerk could have typed themselves, and offering it would make the two cases
    look identical on screen — which is the danger `OQ-INT-1471` named.
    """
    # ⚠ **DETECTED BY SHAPE, NEVER BY CONNECTOR KEY.** `G77` fails a gate on
    # `provider_key` branching, and rightly: the same city can move from a
    # geocoder to a FeatureServer without changing which connector it is, and a
    # second city on the same connector may answer the other way. The question
    # is *what did this row arrive as*, and the row itself is the only honest
    # witness to that.
    if isinstance(row.get("attributes"), Mapping):
        flattened = _arcgis_flat(row, config or gis_layer.field_names_from(None))
        if flattened is None:
            return None
        row = flattened

    parcel = str(row.get("parcel") or row.get("parcel_id") or "").strip()
    address = str(row.get("address") or row.get("address_line") or "").strip()
    if not parcel or not address:
        return None
    # ── DEF-INT-5600 · THE SECOND KEY, AND `CR-112` IS ABOUT BOTH OF THEM ───
    # The PO's mapping of 2026-09-17: `PIN` → `premises.gis_parcel_id` and
    # **`FULLPIN` → `unit.gis_point_id`**, and ruling 3 of the same sitting makes
    # THIS SEARCH where both of them arrive — *"we will need to use 2 - Address
    # search - at first time to map pacle ID and Point ID … when we create the
    # premsies and Unit first time"*. This function extracted the first and
    # nothing anywhere extracted the second, so `units.gis_point_id` had no
    # producer on any live path and was NULL on every row ever created.
    #
    # ⚠ **A ROW WITH NO POINT KEY IS STILL OFFERED**, unlike a row with no
    # parcel. The parcel is what makes a candidate worth picking over typing;
    # a City that publishes no per-address point key would otherwise have no
    # address search at all.
    point = str(
        row.get("point")
        or row.get("point_id")
        or row.get("fullpin")
        or row.get("FULLPIN")
        or ""
    ).strip()
    lat = _decimal(row.get("lat") if row.get("lat") is not None else row.get("y"))
    lng = _decimal(row.get("lng") if row.get("lng") is not None else row.get("x"))
    score = _decimal(row.get("score"))
    return {
        "parcel": parcel,
        "point": point or None,
        "address_line": address,
        "city": str(row.get("city") or "").strip() or None,
        "state": str(row.get("state") or "").strip() or None,
        "postal_code": str(row.get("postal_code") or row.get("zip") or "").strip() or None,
        "lat": str(lat) if lat is not None else None,
        "lng": str(lng) if lng is not None else None,
        # BR-INT-049 — the frame travels WITH the number, never beside it in a
        # comment. `frame` is the city's own if it states one; ours otherwise,
        # and wave Q refuses anything that is not `DECLARED_FRAME`.
        # ⚠ **THE FRAME IS THE CITY'S TO STATE, AND ARCGIS STATES IT ON THE
        # PAYLOAD RATHER THAN THE ROW** — which `_rows` throws away, so
        # `search` reads it and passes it here (`DEF-INT-5618`). Defaulting to
        # `DECLARED_FRAME` for a projected layer would assert WGS84 over Web
        # Mercator and write a coordinate ~10^5 out as though it were degrees;
        # naming the frame honestly lets `gis.frame_is_declared` drop the PIN
        # and keep the address, which is what `BR-INT-049` asks for.
        # ⚠ A service that states NOTHING is still assumed `DECLARED_FRAME` —
        # unchanged, deliberately, because that is what ships today and every
        # flat fixture relies on it. `DEF-INT-5631` carries the remainder.
        "frame": str(
            row.get("frame") or row.get("spatial_reference") or frame or DECLARED_FRAME
        ),
        # ⚠ THE RAW SCORE TRAVELS AND IS NEVER SHOWN. `US-INT-042` §1: *"no
        # score is shown as a number, because a number needs a scale nobody has
        # confirmed"*. `gis.py` turns it into a WORD; a screen never sees this.
        "score": str(score) if score is not None else None,
        "score_scale": str(row.get("score_scale") or "0-100"),
        # ── DEF-INT-5602 · THE CITY'S OWN WORD FOR ITS OWN RECORD ───────────
        # Ruling 10 of 2026-09-17: `Status` → `gis_status`, **stored as given
        # and never filtered** — we do not own their vocabulary, and a row
        # dropped for an unrecognised status is a row nobody can see we dropped.
        # `seams/metering.py::payload_from` has read `candidate["status"]` since
        # `CR-112` landed and this dict had eleven keys and no `status`, so the
        # expression was always `None` and the column always NULL. A `.get()`
        # for a key nothing produces is silent in Python and invisible to mypy,
        # to every gate and to every test that builds its own candidate by hand.
        "status": str(row.get("status") or "").strip() or None,
        # `DEF-INT-9845` — the City's `Unit`, as given. `None` means the row is
        # the BUILDING's own point (ruling 6 of 2026-09-17), which is exactly
        # the distinction `gis_search.group_by_building` needs and never had.
        "unit": str(row.get("unit") or "").strip() or None,
    }


class GisCityAdapter(Adapter):
    """The city's address service, translated. Four methods and no fifth."""

    # ⚠ RENAMED WITH THE MANIFEST (`CR-110-BRC04`): `gis_city` → `gis_esri`.
    # p162: *"Renamed only. Fields, operations and adapters are untouched."*
    # Nothing about how this adapter WORKS changed; the key it binds to did,
    # and `adapters/register_all` refuses a class whose key does not match
    # the name it is registered under, so this could not have been forgotten.
    # The class name and this file's name are left alone deliberately —
    # moving them multiplies the blast radius of a rename that is a string.
    key = "gis_esri"

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport

    # ── validate ────────────────────────────────────────────────────────────

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Nothing this provider knows beyond the manifest's own shape check.

        `base_url` is declared `host`, so `validate_fields` has already refused
        a scheme typed into it; there is no port, no mailbox and no format to
        argue with. Returning an empty list is the honest answer and is not a
        stub — an adapter with nothing provider-specific to say says nothing.
        """
        return []

    # ── the wire ────────────────────────────────────────────────────────────

    def _url(self, conn: ConnectionView, query: str, secrets: Mapping[str, str]) -> str:
        """The FeatureServer `/query` for what the clerk typed.

        ── 2026-10-07 · `DEF-INT-9843` / `DEF-INT-9844` ───────────────────────
        ⚠ **THIS SENT `q=`, `limit=` AND `key=` UNTIL TODAY — A GEOCODER'S
        WORDS, AND A FEATURESERVER IGNORES ALL THREE.** So the City never
        filtered by the typed text, never capped the rows and never saw the
        key. The PO proved the working form BY HAND against the live Ann Arbor
        layer — `where=UPPER(Street) LIKE UPPER('%2670 SEQUOIA%')`, `outFields=*`,
        `outSR=4326`, `f=json` — and it answered *2670 Sequoia Pkwy, Ann Arbor*.

        **ONE BUILDER, NOT TWO.** The `where` is `gis_search.where_clause`
        (which escapes the clerk's text and had no caller) and the URL is
        `gis_layer.query_url` — the SAME function the nightly walk uses — so
        `outSR=4326` and `token=` are no longer something one path can forget.
        The street field is the tenant's (`field_mapping`, default `Street`),
        read through the one reader both paths share.
        """
        settings = dict(conn.config or {})
        config = gis_layer.field_names_from(
            settings.get("field_mapping"), layer_url=str(settings.get("base_url") or "")
        )
        street_field = dict(config.fields).get("street") or "Street"
        # `Auth(mode="we_hold_theirs", placement="query")` — the manifest says
        # WHERE the key goes; `query_url` sends it as ArcGIS's `token`. The key
        # itself is optional (a city that publishes an open service needs none).
        api_key = (secrets or {}).get("api_key") or None
        return gis_layer.query_url(
            config,
            where=gis_search.where_clause(query, street_field),
            api_key=api_key,
            # The pin on screen needs the point, so geometry comes back.
            return_geometry=True,
            # ⚠ **`CANDIDATE_CAP + 1`, AND THE `+ 1` IS THE WHOLE OF
            # `DEF-INT-5603`.** Asking for exactly the cap makes the City do the
            # truncating, and a list of eight is then indistinguishable from
            # *all the matches there were*. One spare row is the cheapest way to
            # know the difference, and it is never shown — `shown_and_more`
            # drops it.
            resultRecordCount=str(CANDIDATE_CAP + 1),
        )

    def _call(
        self, conn: ConnectionView, secrets: Mapping[str, str], query: str, timeout_s: float
    ) -> Any:
        url = self._url(conn, query, secrets)
        send = self._transport or _urllib_transport
        started = time.monotonic()
        try:
            payload = send(url, timeout_s)
        except TimeoutError as exc:  # socket timeout, the transport's own
            raise ProviderTimeout(str(exc) or "the city did not answer") from exc
        except urllib.error.HTTPError as exc:
            # ⚠ **THE CITY ANSWERED, UNHAPPILY, AND THAT IS A REFUSAL RATHER
            # THAN SILENCE.** `HTTPError` is a subclass of `URLError`, so it has
            # to be caught ABOVE the branch below or a `401` for a wrong key
            # would count towards a breaker built for a provider that is not
            # there. `runtime.guarded_call` lets a refusal through to the caller,
            # which is where `BR-INT-038` puts it.
            #
            # ⚠ **IT WAS RE-RAISED BARE UNTIL 2026-10-07 AND NOTHING ABOVE
            # CAUGHT IT, SO A 401 OR A 503 WAS OUR 500 (`DEF-INT-5620`).** It is
            # translated now — the adapter's one job — into the refusal the
            # caller knows how to say, keeping the status for the run row.
            #
            # ⚠ **AND THE BODY IS READ, BECAUSE A 403 IS NOT ALWAYS THE CITY
            # (`DEF-INT-10019`).** Ann Arbor's Cloudflare answered `403` with
            # `error code: 1010` and this said *"The city rejected our key"*.
            body = gis_http.error_body(exc)
            raise CityRefused(
                gis_layer.refusal_reason(exc.code, body),
                f"the city refused the lookup with HTTP {exc.code}",
                status=exc.code,
                evidence=gis_http.evidence(exc.code, body),
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            # ── DEF-INT-5599 · A SOCKET THAT NEVER OPENS IS NOT AN ANSWER ────
            # ⚠ **THIS BRANCH DID NOT EXIST UNTIL 2026-09-17 AND ITS ABSENCE
            # REACHED A CLERK AS A VANISHING SCREEN.** DNS, a refused
            # connection, a TLS failure and this environment's egress proxy
            # answering *Tunnel connection failed: 403 Forbidden* all arrive
            # here as `URLError` wrapping an `OSError` — and only `TimeoutError`
            # was caught. `runtime.guarded_call`'s `except Exception: raise`
            # then re-raised them as *an answer, even an unhappy one*, which a
            # failure to connect is precisely not. Three things followed, every
            # one of them seen in a browser at the tip:
            #   1. DRF answered `500 SYS-INTERNAL`, so `gis.search` never
            #      reached its `timed_out` branch and frame 66.2's amber *The
            #      City is not answering* box COULD NOT BE SHOWN by this cause;
            #   2. `FindTheAddress.tsx` mapped the 500 to `absent` and the whole
            #      panel disappeared mid-keystroke, taking the clerk's typed
            #      text off the screen with it;
            #   3. `BR-INT-022`'s breaker counted nothing —
            #      `consecutive_timeouts = 0` after four failing searches — so it
            #      could never open and every keystroke went on dialling a host
            #      that was not there.
            # `TimeoutError` is itself an `OSError` and stays ABOVE this branch,
            # because *we stopped waiting* is the honest sentence for a deadline
            # and *we never got in* is the honest sentence for this.
            raise ProviderTimeout(f"the city could not be reached: {exc}") from exc
        # ⚠ A transport that IGNORED the deadline is recorded honestly as *we
        # stopped waiting* rather than accepted late — `runtime.guarded_call`'s
        # own docstring asks for exactly this.
        if (time.monotonic() - started) > timeout_s:
            raise ProviderTimeout("the city answered after we stopped waiting")
        return payload

    @staticmethod
    def _rows(payload: Any) -> list[Mapping[str, Any]]:
        if isinstance(payload, Mapping):
            for key in ("candidates", "results", "addresses", "features"):
                found = payload.get(key)
                if isinstance(found, Sequence) and not isinstance(found, (str, bytes)):
                    return [one for one in found if isinstance(one, Mapping)]
            return []
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            return [one for one in payload if isinstance(one, Mapping)]
        return []

    def search(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        query: str,
        *,
        timeout_s: float,
    ) -> list[dict[str, Any]]:
        """The city's candidates for one fragment. Raises `ProviderTimeout`."""
        payload = self._call(conn, secrets, query, timeout_s)
        _refuse_if_the_city_said_no(payload)
        # ⚠ **THE TENANT'S OWN FIELD NAMES** (`BR-INT-037`, `DEF-INT-5618`).
        # Ann Arbor calls them `PIN` and `FULLPIN`; the next city will not, and
        # the `field_mapping` editor on the connector form is where they say so.
        # Read through the SAME function the nightly reconciliation reads, so a
        # city types them once and both paths obey them.
        config = gis_layer.field_names_from(dict(conn.config or {}).get("field_mapping"))
        # ⚠ **THE FRAME IS ON THE PAYLOAD AND `_rows` DISCARDS IT**, so it is
        # read here and carried in. A layer answering in Web Mercator is then
        # named as such instead of being silently asserted to be WGS84.
        frame: str | None = None
        if isinstance(payload, Mapping):
            wkid = gis_layer.spatial_reference_of(payload)
            if wkid is not None and wkid != gis_layer.DECLARED_WKID:
                # `DEF-INT-9844` — we ASKED for 4326 on this very request. An
                # answer in another frame is refused whole, loudly and by name;
                # not one coordinate from it travels (see `ForeignFrame`).
                logger.warning(
                    "gis address search refused: %s (%s) answered in EPSG:%s, not EPSG:%s",
                    conn.label or conn.provider_key,
                    conn.environment,
                    wkid,
                    gis_layer.DECLARED_WKID,
                )
                raise ForeignFrame(wkid)
            if wkid is not None:
                frame = f"EPSG:{wkid}"
        found: list[dict[str, Any]] = []
        for row in self._rows(payload):
            candidate = candidate_from(row, config, frame=frame)
            if candidate is not None:
                found.append(candidate)
            # One PAST the cap, so the caller can say *there were more* rather
            # than assert a total it cannot know (`DEF-INT-5603`).
            if len(found) > CANDIDATE_CAP:
                break
        return found

    # ── test ────────────────────────────────────────────────────────────────

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """`BR-INT-019` — ONE REAL LOOKUP, never *does the key parse*.

        The manifest's `test_action` is *Look up one address you type*, so the
        typed address arrives as `recipient` (the same slot a mailbox test uses
        for the address it sends to). With none, a deliberately common fragment
        is used — a lookup that answers zero candidates still proves the city
        answered, which is what the card is asking.
        """
        query = (recipient or "1").strip() or "1"
        try:
            found = self.search(conn, secrets, query, timeout_s=5.0)
        except ProviderTimeout as exc:
            return TestResult(
                ok=False,
                # B14 rule 33 — five or six words.
                sentence="The city is not answering.",
                provider_text=scrub(str(exc)),
            )
        except CityRefused as exc:
            # `DEF-INT-10019` — the same reading the search box gives, and the
            # status with the start of the body for whoever reads the run.
            return TestResult(
                ok=False,
                sentence=(
                    "The city's firewall blocked us."
                    if exc.reason == gis_layer.REFUSED_FIREWALL
                    else "The city refused the lookup."
                ),
                provider_text=scrub(exc.evidence or str(exc)),
            )
        except Exception as exc:  # noqa: BLE001 — their refusal, not our crash
            return TestResult(
                ok=False,
                sentence="The city refused the lookup.",
                provider_text=scrub(str(exc)),
            )
        shown, more = shown_and_more(found)
        return TestResult(
            ok=True,
            # B14 rule 33 — six words. The `+` is what stops this sentence
            # becoming the same silent truncation one level down.
            sentence=f"The city answered with {len(shown)}{'+' if more else ''} candidates.",
        )

    # ── execute ─────────────────────────────────────────────────────────────

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One lookup per item, per-item outcomes, never a boolean.

        The inline path hands ONE item — the fragment being typed. The shape is
        a batch because the protocol is a batch and because wave Q's night uses
        the same adapter for many.
        """
        items: list[ItemResult] = []
        answers: list[dict[str, Any]] = []
        timeout_s = float((work[0] if work else {}).get("timeout_s") or 5.0)
        for one in work:
            query = str(one.get("q") or one.get("query") or "").strip()
            if not query:
                items.append(ItemResult(ref="", outcome=ITEM_FAILED, detail="nothing typed"))
                continue
            try:
                found = self.search(conn, secrets, query, timeout_s=timeout_s)
            except ProviderTimeout:
                raise
            except Exception as exc:  # noqa: BLE001
                items.append(
                    ItemResult(
                        ref=query,
                        outcome=ITEM_FAILED,
                        detail="the city refused the lookup",
                        provider_text=scrub(str(exc)),
                    )
                )
                continue
            shown, more = shown_and_more(found)
            answers.extend(shown)
            items.append(
                ItemResult(
                    ref=query,
                    outcome=ITEM_SUCCEEDED,
                    detail=f"{len(shown)} candidates" + (" · more were held back" if more else ""),
                )
            )
        result = RunResult(items=tuple(items), confirmed=True)
        # The candidates ride alongside the per-item outcomes. `RunResult` is
        # frozen and carries no payload slot, so the caller reads them here —
        # `gis.py` is the only caller and its docstring says so.
        object.__setattr__(result, "candidates", answers)  # type: ignore[misc]
        return result

    # ── describe ────────────────────────────────────────────────────────────

    def describe(self, conn: ConnectionView) -> str:
        """The masked line on the card. NO key, ever (`BR-INT-003`)."""
        base = str(dict(conn.config or {}).get("base_url") or "").strip()
        return f"{base} · City GIS" if base else "City GIS"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 story + BR-INT-048/038/019/003/049 verbatim)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B=n/a(no screen calls an adapter) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py · the conformance kit runs this class unchanged
# exceptions: `execute` attaches `candidates` to a frozen RunResult through object.__setattr__ — the protocol has no payload slot and adding one would touch every adapter; named here rather than left to be discovered
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
