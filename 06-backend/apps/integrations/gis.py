# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — the inline address search with a latency
#           budget, a result that is OFFERED rather than loaded, and the write
#           a person makes while they wait. Screens: the premises create form
#           step 1 (frames 66.1 / 66.2)
# Rules:    BR-INT-048 (`C15` a latency budget, not a job — candidates in under
#           a second, nothing queued, no progress row; `C16` disposition
#           `offer` — nothing written until a person picks, and the parcel
#           re-checked against live GIS at the moment of the write) ·
#           BR-INT-022 (the breaker opens on a slow provider and the screen
#           says so) · BR-INT-039 (every attempt is a durable record) ·
#           BR-INT-049 (a coordinate carries its measurement frame) ·
#           OQ-INT-1471 RULED 2026-09-04 (b) · OQ-INT-1728 RULED 2026-09-06 (a)
#           · B14 rule 31 (no database id is a visible value) · rule 33 (a
#           refusal is five or six words)
# Tests:    06-backend/tests/test_us_int_042_gis.py (TC-1..7)
# Impacts:  apps/integrations/api.py (the two routes) · adapters/gis_city.py (gis_esri) ·
#           seams/metering.py (the write) · models.RUN_TRIGGERS (`inline`,
#           migration integrations/0007)
# ───────────────────────────────────────────────────────
"""THE INLINE ADDRESS SEARCH — a latency budget, and a list that writes nothing.

THE THREE THINGS `C15` AND `C16` ACTUALLY ASK FOR
--------------------------------------------------
1. **No job.** `US-INT-022`'s runner queues work and answers `202` with a poll
   url. This does none of that: the call goes out inside the request the clerk
   is waiting on, and the answer is the response. There is no `core.jobs` row
   to poll and the screen shows no progress.
2. **A budget, not a timeout.** The manifest declares
   `latency_budget_ms = 1000`. When the City takes longer, the wait is a
   `ProviderTimeout` — which is what feeds `runtime`'s breaker arithmetic — and
   the field says *the city's address service is not answering* instead of
   spinning.
3. **`offer`, not `load`.** Candidates are SHOWN. Nothing is written until a
   person picks one and presses Create, and at that moment the parcel is asked
   for again, live.

ONE RUN ROW PER SEARCH SESSION, AND WHY NOT ONE PER KEYSTROKE
---------------------------------------------------------------
`BR-INT-039` makes every attempt a durable record, and `US-INT-042` TC-1 says
what the record looks like: *"one `inline` run row per search session
summarising 14 lookups · 1 pick"*. A row per keystroke would write fourteen
rows into a yearly-partitioned table to record one thing a clerk did, and S142
would become unreadable on the day somebody typed an address.

**The session is the run row itself.** The first lookup opens it (`outcome =
running`); every later lookup in the same session increments `attempted` on the
row the client hands back; the pick closes it with `changed = 1`. The row is
append-only only once `finished_at` is set (`BR-INT-039`), so counting up while
it is open is lawful.

⚠ **AND A SESSION NOBODY FINISHES IS CLOSED BY THE NEXT ONE, NOT LEFT OPEN.**
A clerk who types four characters and closes the tab would otherwise leave a
`running` row for ever, and a screen reading *running* about a search that
ended yesterday is a claim that was true and is no longer known to be
(hard-won law 1). `_close_stale_sessions` finishes any of this connection's
inline runs older than `SESSION_STALE_AFTER_S` with the honest summary *N
lookups · no pick*.

⚠ **THE RUN ID IS NOT SHOWN TO ANYBODY (B14 rule 31).** It travels in the
request as `session` and the screen never renders it — it is the handle a
browser keeps between keystrokes, in the same way a `?step=` is.

WHAT A CLERK READS INSTEAD OF A SCORE
--------------------------------------
`US-INT-042` §1 and frame 66.1: *"No score is shown as a number, because a
number needs a scale nobody has confirmed."* The City's number is turned into
one of two WORDS here, in one place, and the number never leaves this file.

WHERE THIS STOPS (`BR-INT-054`, `OQ-INT-1728` (a))
----------------------------------------------------
The Create a person presses is integrations' and is built here. What is NOT
here, and is not a stub either, is the same job as a **scheduled** batch and as
a **run-once-on-demand** batch: the PO asked for all three in the same sentence
that ruled this one, and both batch forms run on Runbooks. Reconciling the
City's parcels against our premises is wave `Q` and has moved whole.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError
from django.utils import timezone

from apps.integrations import (
    custom_apis,
    gis_esri_fixtures,
    gis_fixtures,
    gis_parcels,
    gis_search,
    models,
    runtime,
    services,
)
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.gis_city import (
    DECLARED_FRAME,
    CityRefused,
    ForeignFrame,
    GisCityAdapter,
    shown_and_more,
)
from apps.integrations.registry import REGISTRY, Registry
from apps.integrations.seams import metering as metering_seam
from apps.integrations.seams import runbooks as runbooks_seam
from core import errors

#: The manifest this module serves. ⚠ It is a CONSTANT and not a branch: this
#: file is the runner for one operation shape, and `G77` allows a provider key
#: as data in exactly the registry and the adapter binding. It is named here so
#: the route can resolve it and refuse any other key by name.
#: ⚠ `gis_city` UNTIL `CR-110-BRC04` — the blueprint names connector 25
#: **Esri ArcGIS** and the manifest key moved with it. Renamed only: the
#: three operations, the two hosts and this whole file are unchanged.
PROVIDER_KEY = "gis_esri"
SEARCH_OPERATION = "address_search"
#: ⚠ **THE OPERATION THAT HAD NO CALLER (`DEF-INT-5601`).** `gis_parcels`,
#: `gis_layer` and `gis_match` are 1,749 of the 2,044 lines that defect
#: counts, and until `reconcile` below they were invoked by nothing outside
#: their own tests. The manifest has declared this operation since wave M.
RECONCILE_OPERATION = "reconcile_parcels"

#: ── 2026-09-17 · `CR-115-BRC05` R31 — WHICH ROWS GET A *RUN NOW* CONTROL ────
#: ⚠ **A DECLARATIVE MAP, NOT A BRANCH, AND THE DIFFERENCE IS WHAT `G77`
#: CHECKS.** That gate's own docstring draws the line: `if provider_key == …`
#: in a service or a selector is refused; *"a mapping keyed by provider that
#: lives in the registry IS the declarative form"*. This is that mapping, and
#: it lives beside the runner rather than in `registry.py` so that a second
#: run-now operation is added where its runner is, not in a file every module
#: imports.
#:
#: ⚠ **IT EXISTS BECAUSE THE ALTERNATIVE WAS A LIVE BUTTON OVER A DEAD DOOR
#: (hard-won law 2's mirror).** The screen could have decided from the manifest
#: alone — *this operation is an inbound scheduled fetch, so draw Run now* —
#: and `meters_neptune360` and four others declare exactly that shape with no
#: service behind them. The button would render, the clerk would press it, and
#: `POST …/reconcile` would answer the same 404 an invented provider gets. So
#: the SERVER says which rows have a door, the screen draws what it is told,
#: and `selectors._operation_row` serves it as `can_run_now`.
RUN_NOW_OPERATIONS = frozenset({(PROVIDER_KEY, RECONCILE_OPERATION)})


def can_run_now(provider_key: str, operation_name: str) -> bool:
    """Does this operation have a *Run now* door? Membership, never a branch."""
    return (provider_key, operation_name) in RUN_NOW_OPERATIONS


#: `US-INT-042` §1 — *"the parcel is checked against the city at the moment I
#: press Create, not on every keystroke"*. Two characters is not an address.
MIN_QUERY_CHARS = 3

#: How long an unfinished search session may sit before the next one closes it.
#: Five minutes: longer than any clerk spends typing one address, shorter than
#: a shift, so a row is never both open and stale on a screen somebody reads.
SESSION_STALE_AFTER_S = 300

#: The two WORDS frame 66.1 draws, and the boundary between them. The City's
#: own number is normalised to 0–1 first, so a city publishing 0–100 and one
#: publishing 0–1 produce the same words rather than the same digits.
STRONG_MATCH = "strong"
CLOSE_MATCH = "close"
STRONG_AT = Decimal("0.85")


#: The four refusals this module raises, as catalogue keys. ⚠ **A KEY, NEVER A
#: SENTENCE BUILT IN PYTHON.** `core.errors` asserts at the raise that the key
#: resolves, and the eleven catalogues are what make it reach a clerk in their
#: own language; a sentence built here reaches them in English, or — when
#: `params.detail` is suppressed, as the PO ruled on 2026-08-19 — as silence.
REFUSAL_NOT_CONNECTED = "integrations.gis.not_connected"
REFUSAL_CITY_NOT_ANSWERING = "integrations.gis.city_not_answering"
REFUSAL_PARCEL_GONE = "integrations.gis.parcel_gone"
#: `DEF-INT-4273` — the parcel is already on another property here. Picking the
#: same row twice is ORDINARY: two clerks, a re-entry, a reloaded page.
#:
#: ⚠ **WHAT THIS REFUSAL STANDS ON CHANGED ON 2026-09-17 (`BR-MET-1173`).** It
#: used to stand on a DATABASE CONSTRAINT — the parcel lived in
#: `premises.external_ref` under `uq_premises_tenant_external_ref_ci`, and
#: without the check a second pick arrived as a `500` with a psycopg message in
#: it. The parcel now has its own column, `gis_parcel_id`, which carries **no
#: unique index** on purpose: *two premises on one parcel* is a real thing a
#: City does and `BR-INT-073` makes it a difference a person judges.
#:
#: **So this is now a product refusal rather than a caught constraint, and it
#: is kept deliberately.** On the CREATE FORM, a clerk about to put a second
#: property on a parcel that already has one is almost always making the
#: accident it looks like, and one sentence beats one duplicate. A
#: RECONCILIATION RUN never refuses on it — it queues the pair with both
#: premises named. The two callers ask the same selector and do different
#: things with the answer, which is the split `BR-INT-073` rules.
REFUSAL_PARCEL_TAKEN = "integrations.gis.parcel_taken"
#: `CR-115-BRC05` R31 — a reconciliation on a SANDBOX connection.
REFUSAL_SANDBOX = "integrations.refusal.sandbox_only"
#: A person started a run and nobody recorded which person.
REFUSAL_UNNAMED_PERSON = "integrations.gis.run_needs_a_name"
#: Neither `preview` nor `apply`.
REFUSAL_UNKNOWN_MODE = "integrations.gis.unknown_mode"
#: ── `CR-115-BRC05` §7.5 RULE 3 · EVERY ADDRESS LOOKUP IS SWITCHED OFF ───────
#: ⚠ **A SILENT EMPTY LIST WOULD BE THE WORSE ANSWER AND IT WAS THE FIRST
#: DRAFT.** *No matching address found* and *nobody is looking* are different
#: facts, and a clerk who has switched every lookup off is owed the second one —
#: otherwise the switch they just used looks like a City that has stopped
#: answering, and they file a defect against correct behaviour.
REFUSAL_LOOKUP_OFF = "integrations.gis.lookup_off"
#: The nightly sync is switched off, so it does not run (rule 3's other half).
REFUSAL_SYNC_OFF = "integrations.gis.sync_off"
#: ── `DEF-INT-9844` · THE CITY ANSWERED IN ANOTHER FRAME ─────────────────────
#: Every search asks for `outSR=4326`; a layer answering in anything else (State
#: Plane feet, say) is refused WHOLE, so not one projected number reaches the
#: screen or a premises. Its own key — never *the City is not answering*, which
#: is untrue and would send a clerk to wait for a fix that is configuration.
REFUSAL_FOREIGN_FRAME = "integrations.gis.foreign_frame"
#: ── `DEF-INT-9849` (PO GIS review gap 3) · A PAGE LIMIT ON THE PARCEL CHECK ──
#: A page limit asked for with Apply — all or nothing for a write (`BR-INT-072`).
REFUSAL_PAGES_PREVIEW_ONLY = "integrations.gis.pages_preview_only"
#: A page limit that is not a whole number of at least one.
REFUSAL_PAGES_WHOLE_NUMBER = "integrations.gis.pages_whole_number"
#: ── 2026-10-07 · PO GIS review gap 12 and Lane B's leftover (a) ────────────
#: ⚠ **A CONNECTION THAT NAMES NO LAYER IS NOT "NOT CONNECTED" AND WAS A 500.**
#: `gis_parcels.config_from_connection` raises `GisRunRefused` for it, nothing
#: on `POST …/reconcile` caught that, and the attempt row it had already opened
#: was left running for ever. It is refused BEFORE the run row now, by name.
REFUSAL_NO_LAYER = "integrations.gis.no_layer"
#: The connection is set up and its last test failed (`not_working`) — BROKEN,
#: which a clerk must be able to tell from *nobody set one up* (gap 12).
REFUSAL_CONNECTION_BROKEN = "integrations.gis.connection_broken"

#: `city_state()`'s three answers. ⚠ **`none` COVERS "NEVER SET UP" AND
#: "SWITCHED OFF" ALIKE, ON PURPOSE.** Both mean *this utility is not using a
#: City GIS today*, and both hide the City's fields on the premises and unit
#: screens (gap 9). `broken` keeps them, because the utility IS using one and
#: the fields are where its data lives — it is the link that is wrong.
CITY_NONE = "none"
CITY_BROKEN = "broken"
CITY_WORKING = "working"

#: ⚠ **HOW MANY PAGES A BY-HAND PREVIEW READS WHEN NOBODY SAYS (`DEF-INT-9849`).**
#: The judgment, with its arithmetic (decision log 2026-10-07): the web worker
#: is killed at **60 s** (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`); the
#: parcel check waits **6 s** between pages (`rate_limit_per_minute = 10` on the
#: manifest's `reconcile_parcels`); Ann Arbor's register is **~70 pages** — so
#: the old whole-register preview needed ~7 minutes and was killed every time.
#: Three pages is two waits (12 s) plus four requests (the layer's description
#: and three pages) plus one count, which leaves the City ~9 s a request before
#: the worker gives up. A small utility whose register is three pages or fewer
#: still gets the whole of it, and the report says which it got.
#: ⚠ **THE ROUTE'S DEFAULT, NOT `reconcile`'s.** Runbook 20 runs off the web
#: worker and reads the whole register unless its caller asks otherwise.
MANUAL_PREVIEW_PAGES = 3


class GisRefusal(Exception):
    """A refusal a clerk reads, with the catalogue key the screen renders."""

    def __init__(
        self,
        message_key: str,
        *,
        code: str = errors.BIZ_STATE,
        br_ref: str = "BR-INT-048",
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.code = code
        self.br_ref = br_ref
        # `DEF-MET-9847` — what the sentence names (the other property's
        # address). The three routes hand it to the envelope unchanged.
        self.params = dict(params or {})


# ═══════════════════════════════════════════════════════════════════════════
# The pure half — provable with no database, no clock and no network
# ═══════════════════════════════════════════════════════════════════════════


def match_word(score: Any, scale: Any = "0-100") -> str:
    """The City's number → *strong* or *close*. The number never leaves here.

    A candidate with no score at all is `close`, deliberately: *strong* is a
    claim, and a provider that would not say how good the match is has not made
    it. Erring the other way would put the more confident word on the row we
    know least about.
    """
    try:
        value = Decimal(str(score))
    except (InvalidOperation, TypeError, ValueError):
        return CLOSE_MATCH
    text = str(scale or "").strip()
    upper = Decimal("100") if text.endswith("100") else Decimal("1")
    if upper == 0:
        return CLOSE_MATCH
    return STRONG_MATCH if (value / upper) >= STRONG_AT else CLOSE_MATCH


def presented(candidate: dict[str, Any]) -> dict[str, Any]:
    """One candidate, as a screen may see it — WITHOUT the raw score.

    ⚠ **THE SCORE IS DROPPED HERE AND NOT MERELY UNUSED BY THE SCREEN.** A
    number that reaches the client is a number the next lane renders; the only
    way *"no score is shown as a number"* stays true is for the number not to
    be there.
    """
    return {
        "parcel": candidate["parcel"],
        # ⚠ **BOTH OF `CR-112`'s KEYS TRAVEL, AND ONLY ONE USED TO
        # (`DEF-INT-5600`).** Nothing RENDERS this — like `frame` two lines
        # down, it is a fact about the candidate rather than a thing a clerk
        # reads — but a wire that carries one of two keys is a wire the screen
        # and the reconciliation cannot both be right about.
        "point": candidate.get("point"),
        "address_line": candidate["address_line"],
        "city": candidate.get("city"),
        "state": candidate.get("state"),
        "postal_code": candidate.get("postal_code"),
        "lat": candidate.get("lat"),
        "lng": candidate.get("lng"),
        "frame": candidate.get("frame") or DECLARED_FRAME,
        # Ruling 10, 2026-09-17 — as the City gave it, unfiltered
        # (`DEF-INT-5602`).
        "status": candidate.get("status"),
        # `DEF-INT-9845` — the City's `Unit`, as given; `None` on the building's
        # own point. The search row draws it (*"… · Unit A"*, `DEF-MET-10013`);
        # it is what tells a building from its units.
        "unit": candidate.get("unit"),
        "match": match_word(candidate.get("score"), candidate.get("score_scale")),
    }


def frame_is_declared(candidate: dict[str, Any]) -> bool:
    """`BR-INT-049` — a coordinate in another frame is not ours to write.

    A candidate whose frame is not the declared one is still OFFERED (its
    address and parcel are perfectly good); what is dropped is the pin. A
    projected coordinate written into a 9,6 decimal column would put the
    property in the sea, and `US-INT-043` TC-6 refuses exactly that shape one
    wave along.
    """
    return str(candidate.get("frame") or "") == DECLARED_FRAME


# ═══════════════════════════════════════════════════════════════════════════
# The connection, the adapter and the budget
# ═══════════════════════════════════════════════════════════════════════════


def _operation(name: str, *, registry: Registry = REGISTRY) -> Any:
    manifest = registry.get(PROVIDER_KEY)
    if manifest is None:  # pragma: no cover — the registry refuses at load
        raise GisRefusal("integrations.refusal.not_available", br_ref="BR-INT-001")
    for one in manifest.operations:
        if one.name == name:
            return one
    raise GisRefusal("integrations.refusal.not_available", br_ref="BR-INT-001")  # pragma: no cover


def budget_seconds(*, registry: Registry = REGISTRY) -> float:
    """`C15`'s declared budget, in seconds — read from the manifest, never typed."""
    operation = _operation(SEARCH_OPERATION, registry=registry)
    return float(operation.latency_budget_ms) / 1000.0


def connection_or_refuse(tenant_id: Any) -> models.IntegrationConnection:
    """The tenant's City GIS connection, or a refusal a clerk can read.

    ⚠ **A TENANT WITHOUT ONE IS NOT AN ERROR AND MUST NOT LOOK LIKE ONE.** Most
    utilities have no City GIS; their premises form has no address search on it
    at all, and this refusal is what the screen reads to know that.
    """
    row = services.connection_for(tenant_id, PROVIDER_KEY)
    if row is None or not row.enabled or row.status == models.STATUS_OFF:
        raise GisRefusal(REFUSAL_NOT_CONNECTED, br_ref="BR-INT-002")
    return row


def _layer_address(connection: models.IntegrationConnection) -> str:
    """The address the parcel check would dial — `layer_url`, else `base_url`.

    The same precedence `gis_parcels.config_from_connection` applies; read here
    so a missing one is refused BEFORE a run row is opened (gap 12, leftover a).
    """
    config = dict(connection.config or {})
    return str(config.get("layer_url") or config.get("base_url") or "").strip()


def city_state(tenant_id: Any) -> dict[str, Any]:
    """`GET /integrations/gis_esri/state` — is a City GIS in use here, and is it well?

    ── 2026-10-07 · PO GIS review gaps 9 and 12 ─────────────────────────────
    `{"state": "none" | "broken" | "working", "message_key": str | None}`.

    * **`none`** — no connection row, one never set up, or one switched off or
      disabled. The premises and unit screens then draw NO City field at all —
      no parcel, no point, no *Checked against GIS* — and delete nothing: the
      stored values stay in their columns and come back the day a City is
      connected (gap 9). `message_key` is `integrations.gis.not_connected`, the
      sentence the address search already used for this case.
    * **`broken`** — the utility HAS a City GIS and it is not working: its last
      test failed (`not_working`) or it names no layer to read. The fields stay
      on screen and one line says which of the two (gap 12).
    * **`working`** — anything else, *untested* included: a connection nobody
      has tested yet is not known to be broken.

    ⚠ **IT READS THE ROW AND DIALS NOTHING.** It is asked on every premises and
    unit page; a City call per page view would be a request a clerk never made.
    ⚠ **IT DISCLOSES A STATE AND NOTHING ELSE** — no address, no key, no label —
    which is why a Billing Clerk may read it (`AnyTenantRole`, the reason
    `DEF-INT-4267` gave for the address search beside it).
    """
    row = services.connection_for(tenant_id, PROVIDER_KEY)
    if (
        row is None
        or not row.enabled
        or row.status in (models.STATUS_OFF, models.STATUS_NOT_SET_UP)
    ):
        return {"state": CITY_NONE, "message_key": REFUSAL_NOT_CONNECTED}
    if not _layer_address(row):
        return {"state": CITY_BROKEN, "message_key": REFUSAL_NO_LAYER}
    if row.status == models.STATUS_NOT_WORKING:
        return {"state": CITY_BROKEN, "message_key": REFUSAL_CONNECTION_BROKEN}
    return {"state": CITY_WORKING, "message_key": None}


def _adapter(connection: models.IntegrationConnection) -> GisCityAdapter:
    """The adapter, with the recorded transport bound for a reserved host.

    `gis_fixtures.transport_for` answers `None` for every host that could
    resolve, so a real city is always dialled for real.
    """
    base = str(dict(connection.config or {}).get("base_url") or "")
    return GisCityAdapter(transport=gis_fixtures.transport_for(base))



def _view_at(connection: models.IntegrationConnection, url: str) -> ConnectionView:
    """The connection as an adapter sees it, pointed at ONE resolved address.

    ⚠ **THIS IS NOT A SECOND RESOLVER AND THE DIFFERENCE MATTERS** (`§7.7`,
    `G128`). It DECIDES nothing: `custom_apis.lookup_addresses` has already
    asked `addressing.resolve_address` — the one ladder — and this only places
    the answer where the adapter already looks. The alternative was teaching
    `GisCityAdapter` about per-API rows, which would have been an eighth place
    that decides an address, in the one directory this lane must not touch.
    """
    return ConnectionView(
        provider_key=connection.provider_key,
        environment=connection.environment,
        config={**dict(connection.config or {}), "base_url": url},
        label=connection.label,
    )


def _adapter_at(url: str) -> GisCityAdapter:
    """The adapter with the recorded transport bound for THIS address.

    `_adapter` below asks the same question of the connector's own address.
    A custom row may point somewhere else entirely, so the transport has to be
    chosen per call or a clerk's second layer would be dialled for real while
    the first was answered from a recording — two different worlds inside one
    merged result list.
    """
    return GisCityAdapter(transport=gis_fixtures.transport_for(url))


def _merge_key(candidate: Mapping[str, Any]) -> tuple:
    """What makes two candidates from two layers THE SAME PLACE.

    ⚠ **THE POINT ID IS PART OF IT, AND LEAVING IT OUT COLLAPSED A BLOCK OF
    FLATS INTO ONE ROW.** A qualified-address layer answers one row per PARCEL
    and an address-points layer answers one per DOOR, so several points share a
    parcel legitimately. De-duplicating on the parcel alone would silently drop
    every unit but one — the exact opposite of what merging two layers is for.
    """
    return (
        str(candidate.get("parcel") or ""),
        str(candidate.get("point_id") or ""),
        str(candidate.get("address_line") or "").strip().lower(),
        str(candidate.get("unit") or ""),
    )


def _merged(found: Sequence[Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    """Every enabled lookup's candidates, in ONE list, de-duplicated.

    `CR-115-BRC05` §7.5 rule 2: *"Address lookup MERGES — search every enabled
    lookup URL, merge the candidates, **rank them together** … a city with a
    qualified-address layer AND an address-points layer just works."*

    ⚠ **THIS FUNCTION DOES THE MERGING AND NOT THE RANKING, AND THAT SPLIT IS
    THE WHOLE POINT.** `search()` already puts the flat list through
    `gis_search.rank_candidates` — the GIS lane put it there on 2026-09-17
    (`DEF-INT-5601`) and its docstring calls it *"one ordering for every caller
    instead of none"*. So *ranked together* is true **by construction**: two
    layers become one list here, and the one ranker downstream sorts it.

    ⚠ **THE FIRST BUILD OF THIS FUNCTION RANKED HERE TOO, AND THAT WAS A SECOND
    RANKER — THE SAME MISTAKE AS A SECOND ADDRESS RESOLVER, ONE FIELD OVER.**
    It was written while `rank_candidates` did not yet exist, and it survived a
    rebase onto the tip where it did. Two orderings that agree today are two
    that can disagree tomorrow, and nothing would have gone red when they did.
    Ranking here also changed what a ONE-layer tenant sees, which turned
    `test_us_int_042_gis.py`'s TC-1 red — **a sibling suite's red was the
    finding** (CLAUDE.md law 7 habit 1) — and by the time of the merge that
    sibling had ruled the new order correct for its own reasons.

    ⚠ **THE POINT ID IS PART OF THE DE-DUPLICATION KEY, AND LEAVING IT OUT
    COLLAPSED A BLOCK OF FLATS INTO ONE ROW.** A qualified-address layer answers
    one row per PARCEL and an address-points layer one per DOOR, so several
    points share a parcel legitimately. De-duplicating on the parcel alone would
    silently drop every unit but one — the opposite of what merging two layers
    is for.
    """
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for batch in found:
        for candidate in batch:
            key = _merge_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append(dict(candidate))
    return unique


def _view(connection: models.IntegrationConnection) -> ConnectionView:
    return ConnectionView(
        provider_key=connection.provider_key,
        environment=connection.environment,
        config=dict(connection.config or {}),
        label=connection.label,
    )


# ═══════════════════════════════════════════════════════════════════════════
# The session run row
# ═══════════════════════════════════════════════════════════════════════════


def _close_stale_sessions(connection: models.IntegrationConnection) -> int:
    """Finish any inline run on this connection that nobody came back to."""
    cutoff = timezone.now() - timezone.timedelta(seconds=SESSION_STALE_AFTER_S)
    stale = models.IntegrationRun.objects.filter(
        tenant_id=connection.tenant_id,
        connection=connection,
        trigger="inline",
        finished_at__isnull=True,
        started_at__lt=cutoff,
    )
    closed = 0
    for run in stale:
        services.finish_run(
            run,
            attempted=run.attempted,
            succeeded=run.attempted,
            failed=0,
            skipped=0,
            confirmed=True,
            changed=0,
            summary=_session_summary(run.attempted, picks=0),
        )
        closed += 1
    return closed


def _session_summary(lookups: int, *, picks: int) -> str:
    """*14 lookups · 1 pick* — `US-INT-042` TC-1's own words, pluralised."""
    left = f"{lookups} lookup" + ("" if lookups == 1 else "s")
    if picks == 0:
        return f"{left} · no pick"
    return f"{left} · {picks} pick" + ("" if picks == 1 else "s")


def _session(
    connection: models.IntegrationConnection, session_id: Any
) -> models.IntegrationRun:
    """The open run row for this session, or a new one.

    A `session_id` that names a finished run, another tenant's run, or nothing
    at all starts a FRESH session rather than raising: a stale handle in a
    browser tab is an ordinary thing and losing one lookup off a count is not
    worth a refusal a clerk cannot act on.
    """
    if session_id:
        found = models.IntegrationRun.objects.filter(
            tenant_id=connection.tenant_id,
            connection=connection,
            id=session_id,
            trigger="inline",
            finished_at__isnull=True,
        ).first()
        if found is not None:
            return found
    return services.start_run(
        connection=connection,
        operation=SEARCH_OPERATION,
        direction=models.RUN_DIRECTION_INBOUND_READ,
        trigger="inline",
        # ⚠ **NO `job_id`, AND ITS ABSENCE IS THE POINT** (`C15`). An inline
        # operation has no queue row to point at; a run row carrying one would
        # invite S142 to offer a poll for something that already answered.
        job_id=None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# The search
# ═══════════════════════════════════════════════════════════════════════════


def search(
    tenant_id: Any,
    *,
    query: str,
    session_id: Any = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`GET /integrations/gis_esri/address-search?q=` — the whole of `C15`+`C16`.

    Returns `{session, candidates, truncated, ranking_note_key, elapsed_ms,
    budget_ms, reachable, message_key}`. **Nothing is written to `premises`
    here, ever.**

    ⚠ **`truncated` IS NEW ON 2026-09-17 AND IT IS NOT DECORATION
    (`DEF-INT-5603`).** The screen prints *"N matches from the City's records"*,
    which a clerk reads as ALL of them. Eight was silently the most it could
    ever be, so the row somebody wanted could be missing while the count
    asserted it was not.

    ⚠ **THE ORDER IS OURS SINCE `DEF-INT-5601`, AND IT USED TO BE THE CITY's.**
    A FeatureServer answers in the layer's own order, so the eight rows this
    returned were eight arbitrary matches — typing `100 N Maple` could show
    eight addresses without `100 N Maple` among them, under a count line that
    reads as a total. `gis_search.rank_candidates` is the one ordering, shared
    with the reconciliation match, and `ranking_note_key` is what makes the
    screen say whose order it is rather than implying the City's.
    """
    connection = connection_or_refuse(tenant_id)
    typed = (query or "").strip()
    operation = _operation(SEARCH_OPERATION, registry=registry)
    budget_ms = int(operation.latency_budget_ms)
    if len(typed) < MIN_QUERY_CHARS:
        # No call, no run row, no refusal — two characters is a clerk still
        # typing, and answering it with an error would light the form up red
        # on the way to a perfectly good address.
        return {
            "session": None,
            "candidates": [],
            "truncated": False,
            "ranking_note_key": None,
            "elapsed_ms": 0,
            "budget_ms": budget_ms,
            "reachable": True,
            "message_key": None,
        }

    # ── `CR-115-BRC05` §7.5 rules 2 and 3 · WHICH LAYERS ARE SEARCHED ──────
    # ⚠ **EVERY ENABLED LOOKUP, AND ONLY THE ENABLED ONES.** The connector's own
    # address first, then each custom Address lookup a clerk added, each already
    # resolved by the ONE ladder (`addressing.resolve_address`) — this function
    # decides no address of its own (§7.7, `G128`).
    manifest = registry.get(PROVIDER_KEY)
    addresses = custom_apis.lookup_addresses(connection, manifest, operation)
    if not addresses:
        # Rule 3, said out loud. A clerk who switched every lookup off gets the
        # reason rather than an empty list that reads as *the City has nothing*.
        # ⚠ **NO RUN ROW AND NO CALL**: nothing was dialled, so recording an
        # attempt would put a run in the history that never happened
        # (`BR-INT-039` records ATTEMPTS, and this is not one).
        return {
            "session": None,
            "candidates": [],
            "truncated": False,
            "elapsed_ms": 0,
            "budget_ms": budget_ms,
            "reachable": True,
            "message_key": REFUSAL_LOOKUP_OFF,
        }

    _close_stale_sessions(connection)
    run = _session(connection, session_id)
    secrets = services.credential_secrets(connection)
    timeout_s = budget_ms / 1000.0

    started = time.monotonic()
    batches: list[list[dict[str, Any]]] = []
    outcome = None
    for address in addresses:
        # ⚠ **ONE `guarded_adapter_call` PER LAYER, SO THE BREAKER STILL SEES
        # EACH CALL** (`BR-INT-022`). Wrapping the whole loop in one guard would
        # hide a layer that times out every night behind a sibling that answers.
        url = address["url"]
        try:
            one = services.guarded_adapter_call(
                connection=connection,
                operation=operation,
                call=lambda url=url: _adapter_at(url).search(
                    _view_at(connection, url), secrets, typed, timeout_s=timeout_s
                ),
            )
        except ForeignFrame as exc:
            # `DEF-INT-9844` — REFUSED BY NAME, and the run row says why. The
            # City answered (so `reachable` stays true and no breaker counts
            # it); what it answered is not ours to show. No candidate from ANY
            # layer is returned: a merged list with one layer quietly missing is
            # `DEF-INT-5603`'s truncation one level up.
            models.IntegrationRun.objects.filter(pk=run.pk).update(attempted=run.attempted + 1)
            run.refresh_from_db()
            services.finish_run(
                run,
                attempted=run.attempted,
                succeeded=max(run.attempted - 1, 0),
                failed=1,
                skipped=0,
                confirmed=True,
                summary=str(exc),
            )
            return {
                "session": None,
                "candidates": [],
                "truncated": False,
                "ranking_note_key": None,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "budget_ms": budget_ms,
                "reachable": True,
                "message_key": REFUSAL_FOREIGN_FRAME,
            }
        except CityRefused as exc:
            # ── `DEF-INT-5620` / `DEF-INT-9846` · THE CITY SAID NO ──────────
            # ⚠ **THIS WAS OUR `500 SYS-INTERNAL` UNTIL 2026-10-07** — a 401
            # after a key rotation, a 404 after the City moved its layer, a 503
            # on a Monday morning, each re-raised by the adapter and caught by
            # nobody. It is frame 66.2's amber box now (`reachable: false`),
            # with the reason as its own key so the clerk can tell *call our
            # admin* from *wait*. ⚠ **THE BREAKER IS NOT TOUCHED** — the City
            # answered, and `runtime.guarded_call` persists no breaker state for
            # an answer (`after_refusal`: the breaker counts silence only).
            # Like a silent layer, the first refusing layer decides the answer:
            # a merged list with one layer missing is `DEF-INT-5603` again.
            models.IntegrationRun.objects.filter(pk=run.pk).update(attempted=run.attempted + 1)
            run.refresh_from_db()
            services.finish_run(
                run,
                attempted=run.attempted,
                succeeded=max(run.attempted - 1, 0),
                failed=1,
                skipped=0,
                confirmed=True,
                summary=gis_parcels.REFUSAL_HEADLINES.get(exc.reason, str(exc)),
                # `DEF-INT-10019` — `403, error code: 1010`: the status and the
                # first 200 characters of what refused us, scrubbed by
                # `finish_run`, so the next person need not reach the server.
                provider_error=exc.evidence,
            )
            return {
                "session": None,
                "candidates": [],
                "truncated": False,
                "ranking_note_key": None,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "budget_ms": budget_ms,
                "reachable": False,
                "message_key": gis_parcels.REFUSAL_KEYS.get(
                    exc.reason, REFUSAL_CITY_NOT_ANSWERING
                ),
            }
        if one.skipped or one.timed_out:
            # ⚠ **THE FIRST LAYER TO GO SILENT DECIDES THE ANSWER, AND THAT IS
            # DELIBERATE.** Showing a clerk a merged list with one layer quietly
            # missing is the truncation `DEF-INT-5603` was filed for, one level
            # up: the screen would assert *these are the matches* over a search
            # that only half happened. *The City is not answering* is the honest
            # sentence when any enabled layer is not answering.
            outcome = one
            break
        batches.append(list(one.value or []))
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if outcome is None:
        # ⚠ `runtime.Outcome` and NOT a namespace built here — the branches
        # below read `.skipped`, `.timed_out` and `.sentence` off it, and a
        # look-alike is the kind of near-miss that behaves until one of those
        # three fields grows a meaning.
        outcome = runtime.Outcome(value=_merged(batches))

    if outcome.skipped or outcome.timed_out:
        # `BR-INT-022` / `BR-INT-024` — the breaker is open, or this call is
        # the one that opened it. The session is CLOSED here rather than left
        # running: the clerk is about to be told the City is not answering, so
        # there is no session to come back to.
        models.IntegrationRun.objects.filter(pk=run.pk).update(attempted=run.attempted + 1)
        run.refresh_from_db()
        services.finish_run(
            run,
            attempted=run.attempted,
            succeeded=max(run.attempted - 1, 0),
            failed=0 if outcome.skipped else 1,
            skipped=1 if outcome.skipped else 0,
            confirmed=True,
            never_dialled=bool(outcome.skipped),
            summary=outcome.sentence,
        )
        return {
            "session": None,
            "candidates": [],
            "truncated": False,
            "ranking_note_key": None,
            "elapsed_ms": elapsed_ms,
            "budget_ms": budget_ms,
            "reachable": False,
            # The one sentence frame 66.2's amber box is built from. It is a
            # KEY, not the sentence — the screen renders it in the reader's own
            # language (B14 rule 35, G32).
            "message_key": REFUSAL_CITY_NOT_ANSWERING,
        }

    models.IntegrationRun.objects.filter(pk=run.pk).update(attempted=run.attempted + 1)
    run.refresh_from_db()
    # `DEF-INT-5603` — the adapter answers one row PAST the cap so that this
    # line can tell *eight* from *eight of many*. The spare row is dropped here
    # and never reaches a screen.
    shown, more = shown_and_more(list(outcome.value or []))
    # ⚠ **RANKED ON THE ADAPTER'S SHAPE, THEN PRESENTED.** `candidates_to_rows`
    # is documented as the bridge from THAT shape; `presented` below is the WIRE
    # shape, and ranking it instead would make the order depend on what we
    # happen to publish rather than on what the City actually said.
    ranked = gis_search.rank_candidates(shown, typed)
    return {
        "session": str(run.id),
        "candidates": [presented(one) for one in ranked["candidates"]],
        "truncated": more,
        # *"Ordered by us, not the city."* — a KEY, never a sentence built here.
        "ranking_note_key": ranked["ranking_note_key"],
        "elapsed_ms": elapsed_ms,
        "budget_ms": budget_ms,
        "reachable": True,
        "message_key": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# `CR-177-BRC10` task 2 · `BR-MET-1191` — ONE "Check address" REQUEST
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-09, verbatim: *"below this address - we need a button to check
# address validdity - uisng gis api or city map … if integration is done for
# that tenant - then address matches then it will shwo the detials otherwise it
# will show that this integration not available and adderss cannjot be
# validated"*. So the City is asked ONCE, when the clerk presses the button,
# and never while they type (`DEF-MET-10034`: the old box searched on every
# pause, even at a utility with no City at all).

CHECK_NOT_CONNECTED = "not_connected"
CHECK_MATCH = "match"
CHECK_NO_MATCH = "no_match"
#: The utility HAS a City map and it could not answer — broken, refusing or
#: silent. Not one of the drawing's three; it is the honest fourth, and its
#: sentence is the City's own refusal key (`message_key`).
CHECK_UNAVAILABLE = "unavailable"


def _zip5(raw: Any) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return digits[:5]


def check_address(
    tenant_id: Any,
    *,
    address_line: Any,
    city: Any = None,
    state: Any = None,
    postal_code: Any = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`POST /integrations/gis_esri/check-address` → `{result, match, session,
    message_key}`. **Nothing is written.**

    * `not_connected` — no City map here (`city_state` = `none`); nothing is
      dialled. The screen says the address saves as typed.
    * `match` — the City's best row for the street, as `presented` gives it
      (address, parcel, point, lat/lng), and the search `session` the create
      closes. ⚠ **WHICH ROW:** the building's own row (no `unit`) whose ZIP
      agrees with the typed one; else the first building row; else the first
      row — the City's ranking as `search` already ordered it.
    * `no_match` — the City answered with nothing.
    * `unavailable` — a City map exists and could not answer; `message_key` is
      the reason `search` already gives the address box.
    """
    state_now = city_state(tenant_id)
    if state_now["state"] == CITY_NONE:
        return {
            "result": CHECK_NOT_CONNECTED,
            "match": None,
            "session": None,
            "message_key": REFUSAL_NOT_CONNECTED,
        }
    if state_now["state"] == CITY_BROKEN:
        return {
            "result": CHECK_UNAVAILABLE,
            "match": None,
            "session": None,
            "message_key": state_now["message_key"],
        }
    try:
        answer = search(tenant_id, query=str(address_line or ""), registry=registry)
    except GisRefusal as refusal:
        return {
            "result": CHECK_UNAVAILABLE,
            "match": None,
            "session": None,
            "message_key": refusal.message_key,
        }
    if not answer.get("reachable", True) or answer.get("message_key"):
        return {
            "result": CHECK_UNAVAILABLE,
            "match": None,
            "session": None,
            "message_key": answer.get("message_key") or REFUSAL_CITY_NOT_ANSWERING,
        }
    candidates = list(answer.get("candidates") or [])
    if not candidates:
        return {"result": CHECK_NO_MATCH, "match": None, "session": answer.get("session"), "message_key": None}
    typed_zip = _zip5(postal_code)
    buildings = [row for row in candidates if not row.get("unit")]
    same_zip = [row for row in buildings if typed_zip and _zip5(row.get("postal_code")) == typed_zip]
    chosen = (same_zip or buildings or candidates)[0]
    return {"result": CHECK_MATCH, "match": chosen, "session": answer.get("session"), "message_key": None}


# ═══════════════════════════════════════════════════════════════════════════
# The write — a person's synchronous Create (OQ-INT-1728 (a))
# ═══════════════════════════════════════════════════════════════════════════


def _picked_rows(
    rows: Sequence[Mapping[str, Any]], parcel: str, point: str | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """`DEF-MET-10013` — `(the building's row, the picked unit's row or None)`.

    Of the re-check's rows on `parcel`: the building's row is the one with no
    `unit`; the picked row is the one whose `point` is `point`. With no `point`
    (a screen older than this fix) nothing was picked beyond the parcel, so the
    building's row is taken, then — only when the City sent no building row —
    the first row, exactly as before. A `point` the City no longer returns is
    `(None, None)`, which the caller refuses as a parcel gone: the clerk picked
    THAT row and silently writing another would be a choice nobody made.
    """
    same = [dict(one) for one in rows if str(one.get("parcel")) == str(parcel)]
    building = next((one for one in same if not str(one.get("unit") or "").strip()), None)
    if point:
        picked = next((one for one in same if str(one.get("point") or "") == str(point)), None)
        if picked is None:
            return None, None
        if not str(picked.get("unit") or "").strip():
            return picked, None
        return building, picked
    if building is not None:
        return building, None
    return (same[0] if same else None), None


def create_premises(
    actor: Any,
    tenant_id: Any,
    *,
    parcel: str | None,
    typed: dict[str, Any],
    session_id: Any = None,
    point: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """Write the premises the clerk asked for. TWO branches, both builds.

    `point` — the picked row's own address-point key (`DEF-MET-10013`). It
    tells a building's row from its units' on one parcel; see `_picked_rows`.

    **The picked branch (`parcel` given).** `C16`: the parcel is re-checked
    against live GIS **at the moment of the write**, not trusted from the list
    the clerk was looking at — a City may have split a parcel between the
    lookup and the press. A parcel the City no longer returns is refused by
    name; the clerk searches again.

    **The typed branch (`parcel` absent).** `OQ-INT-1471`, ruled 2026-09-04
    option (b), PO verbatim *"(b) type it, marked unchecked"*: the premises IS
    created, carries no parcel key, and is marked `gis_unchecked` so the two
    cases are not identical on any screen. ⚠ **THIS BRANCH USED TO RAISE
    `NotImplementedError("OQ-INT-1471")` in the plan's own task table, in the
    epic's TC-4 and in the screen-layout deviation note — all three were
    written before the ruling and all three were stale.** The register's status
    column said CLOSED for two days; this build follows the status column.
    """
    connection = connection_or_refuse(tenant_id)
    chosen: dict[str, Any] | None = None
    picked_unit: dict[str, Any] | None = None
    picks = 0

    if parcel:
        adapter = _adapter(connection)
        view = _view(connection)
        secrets = services.credential_secrets(connection)
        operation = _operation(SEARCH_OPERATION, registry=registry)
        try:
            outcome = services.guarded_adapter_call(
                connection=connection,
                operation=operation,
                call=lambda: adapter.search(
                    view,
                    secrets,
                    str(typed.get("address_line") or parcel),
                    timeout_s=budget_seconds(registry=registry),
                ),
            )
        except ForeignFrame as exc:
            # `DEF-INT-9844` — the re-check answered in another frame; nothing
            # from it is written, and the clerk is told which refusal this is.
            raise GisRefusal(REFUSAL_FOREIGN_FRAME, br_ref="BR-INT-049") from exc
        except CityRefused as exc:
            # `DEF-INT-9846` — the re-check REFUSED (a rotated key, a moved
            # layer, their outage). Our 500 until 2026-10-07; now the same
            # reason the search box shows, and never a silent downgrade to the
            # typed branch (the note below says why).
            raise GisRefusal(
                gis_parcels.REFUSAL_KEYS.get(exc.reason, REFUSAL_CITY_NOT_ANSWERING),
                br_ref="BR-INT-048",
            ) from exc
        if outcome.skipped or outcome.timed_out:
            # ⚠ **THE RE-CHECK FAILING IS NOT THE TYPED BRANCH.** A clerk who
            # picked a row asked for THAT parcel; silently downgrading them to
            # an unchecked premises would write the very row `OQ-INT-1471`'s
            # question warns about, without anybody choosing it.
            raise GisRefusal(REFUSAL_CITY_NOT_ANSWERING, br_ref="BR-INT-022")
        # ── DEF-MET-10013 · WHICH ROW, NOT ONLY WHICH PARCEL ─────────────────
        # ⚠ **A BUILDING AND ITS UNITS SHARE ONE PARCEL**, so *the first row
        # with this parcel* was whichever the City listed first: a City that
        # lists unit A before its building gave the PREMISES unit A's point.
        # The screen now sends the picked row's own point key; the premises
        # takes the BUILDING's row (hard rule 8 — a unit refines it by LABEL),
        # and a picked unit's own point goes onto the unit (`BR-MET-1162`).
        chosen, picked_unit = _picked_rows(outcome.value or [], parcel, point)
        if chosen is None and picked_unit is None:
            raise GisRefusal(REFUSAL_PARCEL_GONE)
        if chosen is not None and not frame_is_declared(chosen):
            # `BR-INT-049` — offer the address, never the pin.
            chosen = {**chosen, "lat": None, "lng": None}
        if picked_unit is not None and not frame_is_declared(picked_unit):
            picked_unit = {**picked_unit, "lat": None, "lng": None}
        if chosen is None:
            # The City sent the unit and no building row: the address is the
            # unit's (one street, one parcel) and the premises gets NO point —
            # never the unit's, which is the defect. The City check fills it.
            chosen = {**picked_unit, "lat": None, "lng": None, "point": None, "unit": None}
        picks = 1

    payload = metering_seam.payload_from(chosen, typed, unit_candidate=picked_unit)
    if parcel:
        # ⚠ **CHECKED BEFORE THE WRITE, AND CAUGHT AFTER IT (`DEF-INT-4273`).**
        # The check answers the ordinary case in words a clerk can act on; the
        # catch is the race between two clerks pressing Create on the same
        # candidate. Both are needed and neither is enough.
        #
        # ⚠ The catch is OUTSIDE `create_premises`'s own `transaction.atomic()`
        # deliberately — hard-won law 14. On PostgreSQL a failed statement
        # aborts the whole transaction, so catching an `IntegrityError` and
        # carrying on INSIDE the block would raise `InFailedSqlTransaction` on
        # the next query and lose the work at COMMIT. Here the block has
        # already rolled back and we only refuse, which is safe. The test suite
        # runs on SQLite, which has no aborted-transaction state, so a version
        # that got this wrong would pass everything.
        if metering_seam.parcel_is_taken(tenant_id, parcel):
            # `DEF-MET-9847` — the sentence names WHERE the parcel already is
            # (*"This parcel already belongs to {{address}}."*), the same words
            # the typed path and the Edit form now say.
            raise GisRefusal(
                REFUSAL_PARCEL_TAKEN,
                params={
                    "value": str(parcel),
                    "address": metering_seam.parcel_holder_address(tenant_id, parcel)
                    or str(parcel),
                },
            )
    try:
        premises = metering_seam.create(actor, payload)
    except IntegrityError:
        # ⚠ **THIS CATCH NO LONGER HAS A CONSTRAINT TO CATCH, AND IT STAYS
        # ANYWAY (2026-09-17).** It was keyed on `"external_ref" in str(exc)`,
        # which was the unique index the parcel used to share with the import
        # match key. `gis_parcel_id` carries no unique index (`BR-MET-1173`), so
        # the race between two clerks picking the same candidate no longer ends
        # in an `IntegrityError` at all — it ends in two premises on one parcel,
        # which is a queued difference and a legitimate row.
        #
        # What is still reachable here is any OTHER integrity failure the
        # create can raise — a duplicate premise number from a series that
        # wrapped, an owner deleted between the check and the write. Those are
        # not this refusal and must not be dressed up as it, so the branch that
        # renamed them is gone and they are re-raised.
        raise

    if session_id:
        run = models.IntegrationRun.objects.filter(
            tenant_id=connection.tenant_id,
            connection=connection,
            id=session_id,
            trigger="inline",
            finished_at__isnull=True,
        ).first()
        if run is not None:
            services.finish_run(
                run,
                attempted=run.attempted,
                succeeded=run.attempted,
                failed=0,
                skipped=0,
                confirmed=True,
                changed=picks,
                summary=_session_summary(run.attempted, picks=picks),
            )
    return premises



# ═══════════════════════════════════════════════════════════════════════════
# 2026-09-17 · `CR-115-BRC05` R31 — RUN NOW: the door onto the parcel run
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim: *"i dont have Run button here"*.
#
# ⚠ **THIS IS THE CALLER `DEF-INT-5601` SAID DID NOT EXIST.** `gis_parcels`,
# `gis_layer`, `gis_match` and `gis_search` were 2,044 lines invoked by nothing
# outside their own tests — hard-won law 2 in its purest form. Everything below
# is the door; it adds no reconciliation logic of its own, on purpose, because a
# second implementation of *what the City said versus what we hold* is the one
# outcome this wave must not produce.
#
# ⚠ **RE-MEASURED 2026-09-17, AND THE COUNT IS NO LONGER FOUR.** Three of the
# four now have real, non-test importers and one is still partly dark:
#
#   * `gis_parcels` — this file and `api.py`'s `POST …/reconcile`. LIVE.
#   * `gis_layer` — `gis_parcels`, `gis_match`, `gis_search`, and since
#     `DEF-INT-5618` the live address-search adapter itself. LIVE.
#   * `gis_match` — `gis_parcels`, which is now reachable. LIVE.
#   * `gis_search` — `search()` above, for the RANKING, and since 2026-10-07
#     the adapter's request for its `where` builder (`where_clause`,
#     `DEF-INT-9843`). Its GROUPING (`group_by_building`, `Building`,
#     `BUILDING_CAP`) still has no caller.
#
# ⚠ **THE FIELD THE GROUPING WAS BLOCKED ON IS NOW ON THE WIRE (`DEF-INT-9845`,
# 2026-10-07)** — `candidate_from` carries the City's `Unit` as `unit`, so a
# candidate can at last say whether it is a building point or a unit, and
# `gis_search.candidates_to_rows` reads it. **What still stands between this
# endpoint and `group_by_building` is the SCREEN**: `FindTheAddress.tsx` renders
# a flat list of candidates, and serving buildings-with-units would change the
# wire shape it reads. That is a screen change with its own drawing step, not a
# field, and it is deliberately not taken here.


def _reconcile_settings(tenant_id: Any) -> dict[str, Any] | None:
    """Which address fields the utility has turned on. **Today: none, anywhere.**

    ⚠ **THERE IS NO SCREEN THAT SETS THESE AND THAT IS NOT AN OVERSIGHT — IT IS
    PO RULING R28 OF 2026-09-17 ARRIVING AS CODE.** The ruling is *"(c) never
    touch by default"*, and `gis_match.disposition_for` resolves an absent
    policy to `NEVER_TOUCH` for every field. So this returns `None`, every
    address difference is FOUND and REPORTED and none is applied, and
    `MatchReport.headline` says exactly that in words — *"N differences found,
    0 applied, all M fields set to never touch"* — because a report showing two
    zeroes with no reason is a screen a clerk files a defect against.
    **`gis_field_dispositions` is read from nowhere; grep says so.**

    ⚠ **AN APPLY IS STILL NOT A NO-OP, AND CONFLATING THE TWO WOULD BE THE
    WRONG READING OF R28.** The ruling governs ADDRESS FIELDS. The two KEYS —
    `premises.gis_parcel_id` and `unit.gis_point_id` — and the verified stamp
    are written on every apply, and they are the whole of what the going-live
    customer asked for: R29, *"our job is the keep parcel ID updated"*.

    Where a clerk will eventually turn a field on is a Settings family
    (`apps/tenancy/settings_families.py` holds five already) and it is not in
    this wave's scope. It is a stated absence rather than a stub, because
    *never touch* is the ruled BEHAVIOUR and not a gap awaiting an answer.
    """
    return None


def _layer_transport(base_url: str) -> Any:
    """The transport the LAYER WALK uses, or `None` for *dial it for real*.

    ⚠ **NOT `gis_fixtures.transport_for`, AND THE DIFFERENCE IS A REAL BUG
    AVOIDED RATHER THAN A TIDINESS.** This connector has two recorded fixtures
    because it has two protocols on one host: `gis_fixtures` records the ADDRESS
    SEARCH and answers `{"candidates": [...]}` to any URL, and
    `gis_esri_fixtures` records the ESRI FEATURE SERVICE — the metadata
    document, the paging, `outSR`, `resultOffset`. Handing the search fixture to
    `gis_layer.walk` gets a metadata read that is a perfectly good JSON object
    with no `maxRecordCount` in it, so the walk refuses with *the layer
    publishes maxRecordCount=None* — an honest refusal that says nothing about
    our code, on every reserved host, for ever.

    `gis_fixtures.serves` still decides WHETHER a host is recorded, so the one
    rule about what `.example` means lives in one place (RFC 2606).
    """
    return gis_esri_fixtures.recorded_transport if gis_fixtures.serves(base_url) else None


def _pace_for(base_url: str) -> Any:
    """The throttle between pages — polite against a municipal service.

    ⚠ **HANDED IN RATHER THAN IMPLEMENTED IN `gis_layer`**, which is that
    module's own shape and the reason a test can walk 40,000 rows instantly.
    `None` against a RECORDED transport, because a fixture host that can never
    resolve is not a service anybody has to be polite to and sleeping there
    would make the test suite the slowest thing in the repo.
    """
    if gis_fixtures.serves(base_url):
        return None
    interval = 60.0 / float(max(_operation(RECONCILE_OPERATION).rate_limit_per_minute or 10, 1))

    def pace(_page: int) -> None:
        time.sleep(interval)

    return pace


def pages_or_refuse(raw: Any) -> int | None:
    """A page limit as a whole number of at least one, `None` for none, or a refusal.

    `DEF-INT-9849`. Read from a query string (`?pages=3`), a JSON body or a
    runbook parameter, so a string of digits is accepted and anything else —
    `0`, `-1`, `2.5`, `true`, `three` — is refused by name rather than quietly
    read as *the whole register*, which would be the slow answer to a person who
    asked for a quick one.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, bool):
        raise GisRefusal(REFUSAL_PAGES_WHOLE_NUMBER, code=errors.VAL_FORMAT, br_ref="BR-INT-072")
    text = str(raw).strip()
    if not text.isdigit() or int(text) < 1:
        raise GisRefusal(REFUSAL_PAGES_WHOLE_NUMBER, code=errors.VAL_FORMAT, br_ref="BR-INT-072")
    return int(text)


def reconcile(
    actor: Any,
    tenant_id: Any,
    *,
    mode: str = gis_parcels.PREVIEW,
    started_by: str = gis_parcels.BY_SCHEDULE,
    started_by_name: str | None = None,
    registry: Registry = REGISTRY,
    max_pages: Any = None,
) -> dict[str, Any]:
    """`POST /integrations/gis_esri/reconcile` — Preview or Apply, and the report.

    ⚠ **TWO CONTROLS AND NOT ONE, WHICH IS THE WHOLE OF R31.** *Run now* as a
    single button is a button that does the dangerous thing; the only way a
    clerk could find out what a reconciliation would change would be to let it
    change it. So the mode is REQUIRED of the caller and `preview` is what a
    missing one means (hard-won law 3 — the unsafe option is the one somebody
    types).

    ⚠ **A PREVIEW WRITES NO PREMISES AND NO UNIT, AND IT DOES WRITE A RUN ROW.**
    Those are not in tension and the distinction is worth stating once:
    `BR-INT-074` is about the rows being RECONCILED — the keys, the address
    fields, the verified stamp — and `BR-INT-039` is about the ATTEMPT. Without
    the run row a preview is invisible in RECENT ACTIVITY and *who ran this and
    what did it change* has no answer for half the runs. The decision log of
    2026-09-17 records the reading with its figure: one `integration_run` row,
    zero `premises` rows, zero `units` rows.

    ⚠ **REFUSED ON A SANDBOX CONNECTION IN BOTH MODES.** `services.request_run`
    refuses one on `BR-INT-026` and this is the same act reached by a different
    route; reasoning that *a preview is harmless anyway* would put the rule in
    two places with two readings, and the second is the one that goes stale.

    ⚠ **IT RUNS INSIDE THE REQUEST AND THAT IS A STATED LIMIT.** `search()`
    above answers 200 rather than 202 because `C15` declares a latency budget;
    this answers 200 because THE REPORT IS THE POINT — a clerk presses Preview
    to read what would happen, and a job id with a poll url hands them nothing
    to read. `gis_layer.walk` refuses past `max_pages=500`, so the pull is
    bounded; at Ann Arbor's ~70,000 rows and a 1,000-row page that is ~70 pages.
    **The SCHEDULED form of this run is Runbooks' and is not built here**
    (`BR-INT-054`, and `seams/metering.py`'s own note on `OQ-INT-1728`'s second
    clause). Nothing below is a stub waiting for it.

    ⚠ **AMENDED 2026-10-07 — "BOUNDED" WAS NOT "FINISHES" (`DEF-INT-9849`).**
    Seventy pages read six seconds apart is ~7 minutes, and the web worker is
    killed at 60 seconds, so the whole-register preview a clerk pressed never
    answered at Ann Arbor's size. `max_pages` stops the walk after that many
    pages and the report says so (`complete: False`, *Stopped after 3 of 70
    pages*); the ROUTE passes `MANUAL_PREVIEW_PAGES` when nobody asks for a
    number, and refuses a page limit on Apply. **Runbook 20 calls this with no
    limit** (PO 2026-10-07: the parcel check runs through Runbook 20) — it is the
    caller that runs off the web worker. ⚠ **AN APPLY OVER THE WEB STILL READS
    THE WHOLE REGISTER AND CAN STILL OUTLAST THE WORKER at that size** — it must
    be all or nothing, and what an unattended run does is the PO's deferred
    question (decision log 2026-10-07), not this function's to answer.
    """
    if mode not in gis_parcels.MODES:
        raise GisRefusal(REFUSAL_UNKNOWN_MODE, code=errors.VAL_FORMAT, br_ref="BR-INT-074")
    pages = pages_or_refuse(max_pages)
    if pages is not None and mode == gis_parcels.APPLY:
        # `DEF-INT-9849` — refused BEFORE anything is dialled or recorded. A
        # write reconciled against part of the register is the half pull
        # `BR-INT-072` ruling 4 forbids.
        raise GisRefusal(REFUSAL_PAGES_PREVIEW_ONLY, code=errors.VAL_FORMAT, br_ref="BR-INT-072")
    if started_by == gis_parcels.BY_PERSON and not (started_by_name or "").strip():
        # The question somebody asks a week later. Refused rather than recorded
        # as anonymous — `gis_parcels.run` refuses it too, and this one is here
        # so the refusal reaches a clerk as a sentence instead of a 500.
        raise GisRefusal(REFUSAL_UNNAMED_PERSON, code=errors.VAL_REQUIRED, br_ref="BR-INT-039")

    connection = connection_or_refuse(tenant_id)
    if connection.environment == models.ENVIRONMENT_SANDBOX:
        raise GisRefusal(REFUSAL_SANDBOX, br_ref="BR-INT-026")
    operation = _operation(RECONCILE_OPERATION, registry=registry)
    # ── `CR-115-BRC05` §7.5 RULE 3 · A DISABLED API IS NOT SCHEDULED AND NOT
    # CALLED ────────────────────────────────────────────────────────────────
    # ⚠ **THE SWITCH HAS TO BITE HERE OR IT IS DECORATION** — hard-won law 2's
    # mirror, where a control that renders and changes nothing looks identical
    # to a working one. This is the ONE door into the parcel reconciliation
    # (`gis_parcels.run` has no other caller), so refusing here refuses it for
    # the Run-now button, for a Runbook and for the nightly schedule alike,
    # rather than once per caller.
    #
    # ⚠ **IT IS CHECKED BEFORE `start_run`, SO A SWITCHED-OFF SYNC LEAVES NO RUN
    # ROW AT ALL.** A run recorded and then refused would put a failure in
    # RECENT ACTIVITY every night for a connector working exactly as its owner
    # told it to, and would drag `last_outcome` on the row beside the switch.
    if not custom_apis.is_enabled(connection, operation.name):
        raise GisRefusal(REFUSAL_SYNC_OFF, code=errors.BIZ_STATE, br_ref="BR-INT-078")
    # ── 2026-10-07 · Lane B's leftover (a) — NO LAYER, REFUSED IN WORDS ──────
    # ⚠ **THIS WAS A 500 AND A RUN ROW LEFT RUNNING.** `gis_parcels.run` raises
    # `GisRunRefused` for a connection with no address to read, after the run
    # row below had been opened and before anything finished it. Checked here,
    # with the same precedence the walk uses, so nothing is recorded for a call
    # that was never going to be made (`BR-INT-039` records ATTEMPTS).
    if not _layer_address(connection):
        raise GisRefusal(REFUSAL_NO_LAYER, code=errors.BIZ_STATE, br_ref="BR-INT-037")

    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=models.RUN_DIRECTION_INBOUND_READ,
        # `scheduled` when the schedule started it, `manual` when a person did.
        # ⚠ This is why there is no `started_by` COLUMN: `trigger` already
        # carries that half, and only the person's NAME needed a new one.
        trigger="scheduled" if started_by == gis_parcels.BY_SCHEDULE else "manual",
        registry=registry,
    )
    models.IntegrationRun.objects.filter(pk=run.pk).update(
        mode=mode, started_by_name=(started_by_name or None)
    )

    # ⚠ **THE SAME PRECEDENCE `config_from_connection` APPLIES, READ ONCE HERE
    # SO THE FIXTURE AND THE THROTTLE JUDGE THE ADDRESS THE WALK WILL ACTUALLY
    # DIAL.** A connection keeping a separate layer address and a `.example`
    # service address would otherwise get the recorded transport pointed at a
    # real layer, or the reverse.
    config = dict(connection.config or {})
    layer_address = str(config.get("layer_url") or config.get("base_url") or "")

    report = gis_parcels.run(
        actor,
        connection_config=config,
        ours=metering_seam.reconciliation_set(),
        mode=mode,
        started_by=started_by,
        started_by_name=started_by_name,
        settings=_reconcile_settings(tenant_id),
        transport=_layer_transport(layer_address),
        api_key=(services.credential_secrets(connection) or {}).get("api_key"),
        pace=_pace_for(layer_address),
        update_premises=metering_seam.update_premises,
        update_unit=metering_seam.update_unit,
        max_pages=pages,
    )

    counts = dict(report.get("counts") or {})
    applied = dict(report.get("applied") or {})
    stopped = bool(report.get("stopped"))
    # `DEF-INT-10019` — the refusal's evidence belongs on the RUN ROW, not on
    # the wire; the response keeps the shape it had.
    provider_error = report.pop("provider_error", None)
    # `DEF-INT-9849` — a walk a person stopped after N pages read only part of
    # the register, so the far end has not confirmed the WHOLE of it.
    complete = bool(report.get("complete", not stopped))
    examined = int(counts.get("premises_examined") or 0) + int(counts.get("units_examined") or 0)
    # ⚠ **`changed` IS THE FIFTH COUNT AND IT IS ZERO ON A PREVIEW BY
    # CONSTRUCTION**, never by a branch: `applied` is `{}` unless `_persist`
    # ran, so the number a clerk reads as *what this actually did* cannot
    # disagree with what the mode allowed.
    changed = (
        int(applied.get("keys_taken") or 0)
        + int(applied.get("keys_replaced") or 0)
        + int(applied.get("fields_applied") or 0)
    )
    refused = int(applied.get("rows_refused") or 0)
    services.finish_run(
        run,
        attempted=examined,
        succeeded=max(examined - refused, 0),
        failed=refused,
        skipped=0,
        # ⚠ **`confirmed` IS *DID THE FAR END ANSWER*, AND A COMPLETED WALK IS
        # THE STRONGEST ANSWER THIS OPERATION CAN GET** (`BR-INT-018`). A
        # stopped run is `False`, which is what the amber *Unconfirmed* word is
        # for; a pull that read every page and matched our whole register is
        # `succeeded` and must not wear it.
        confirmed=not stopped and complete,
        changed=changed,
        # The one sentence `R28` makes necessary — see `MatchReport.headline`.
        summary=str(report.get("headline") or ""),
        provider_error=provider_error,
    )
    return {
        **report,
        "run_id": str(run.id),
        "trace_id": run.trace_id,
        # Where the differences a PERSON has to judge are worked (`BR-INT-074`).
        # The address, not a label: a screen that composed its own would be a
        # second source for one fact, and the runbook's key is what the route
        # is built from.
        "queue_runbook_key": runbooks_seam.GIS_RUNBOOK_KEY,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 story + BR-INT-048/022/039/049 verbatim; OQ-INT-1471 and OQ-INT-1728 rulings)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B✔(features/metering/FindTheAddress.tsx) C✔ D✔(two routes in api.py) E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py · 10-scripts/render-checks/cr069-m-address-search.mjs (the browser)
# exceptions: `PROVIDER_KEY` is a provider key as DATA in a runner, the shape G77 allows in the registry and the adapter binding — this file IS the runner for one operation shape and says so
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
